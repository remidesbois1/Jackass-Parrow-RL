"""Fast PPO on the batched torch engine (schema JackassParrow-v2), CPU or GPU.

Simulation, features, rollouts and updates all stay on one device; nothing is
copied per step between processes. Training happens only when run explicitly:

python -m examples.train_vector --timesteps 200000000 --output runs/hard-v1
python -m examples.train_vector --resume runs/hard-v1/final.pt --timesteps 100000000 --output runs/hard-v1b
"""

import argparse
from dataclasses import asdict
from importlib.metadata import version
import json
import math
from pathlib import Path
import time

from src.rl.rewards import RewardWeights
from .train_ppo import nonnegative_float, positive_int

# Learning reward for this schema: same components as LearningReward.
VECTOR_REWARD = RewardWeights(score=0.01, boss_damage=1.0, level_cleared=1.0, boss_defeated=5.0,
                              health_lost=-1.0, death=-2.0, tick=-0.00025)


def build_parser():
    p = argparse.ArgumentParser(description="Train a Jackass-Parrow agent with on-device PPO")
    p.add_argument("--output", type=Path, required=True, help="new run directory")
    p.add_argument("--resume", type=Path, help="continue from a checkpoint (.pt) of this schema")
    p.add_argument("--device", default="auto", help="auto, cpu, cuda or cuda:N")
    p.add_argument("--timesteps", type=positive_int, default=100_000_000, help="decisions to train")
    p.add_argument("--envs", type=positive_int, help="parallel games (default 8192 on GPU, 1024 on CPU)")
    p.add_argument("--n-steps", type=positive_int, default=64, help="decisions per game per rollout")
    p.add_argument("--epochs", type=positive_int, default=4)
    p.add_argument("--minibatches", type=positive_int, default=8)
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--final-lr-fraction", type=nonnegative_float, default=0.1)
    p.add_argument("--gamma", type=float, default=0.995)
    p.add_argument("--gae-lambda", type=float, default=0.95)
    p.add_argument("--clip", type=float, default=0.2)
    p.add_argument("--ent-coef", type=nonnegative_float, default=0.01)
    p.add_argument("--vf-coef", type=nonnegative_float, default=0.5)
    p.add_argument("--max-grad-norm", type=float, default=0.5)
    p.add_argument("--hidden", type=positive_int, nargs="+", default=[256, 256])
    p.add_argument("--frame-skip", type=positive_int, default=4)
    p.add_argument("--episode-limit", type=positive_int, default=3600, help="decisions per episode")
    p.add_argument("--random-start", type=float, default=0.5,
                   help="fraction of training games started at a random tableau, Tom or loop 2")
    p.add_argument("--shaping", type=nonnegative_float, default=1.0,
                   help="potential-based line-of-fire shaping coefficient (0 disables)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--eval-every", type=positive_int, default=20_000_000, help="decisions between evaluations")
    p.add_argument("--eval-envs", type=positive_int, default=256, help="games per evaluation (normal start)")
    p.add_argument("--checkpoint-every", type=positive_int, default=20_000_000)
    p.add_argument("--torch-threads", type=positive_int, help="CPU threads for torch")
    p.add_argument("--no-cuda-graph", action="store_true", help="launch simulation kernels eagerly on CUDA")
    return p


class ReturnScaler:
    """Divide rewards by the running std of the discounted return (VecNormalize-style)."""

    def __init__(self, n, gamma, device):
        import torch
        self.gamma = gamma
        self.ret = torch.zeros(n, dtype=torch.float64, device=device)
        self.mean = torch.zeros((), dtype=torch.float64, device=device)
        self.var = torch.ones((), dtype=torch.float64, device=device)
        self.count = torch.tensor(1e-4, dtype=torch.float64, device=device)

    def __call__(self, reward, done):
        self.ret = self.ret * self.gamma + reward
        batch_mean, batch_var, n = self.ret.mean(), self.ret.var(unbiased=False), self.ret.numel()
        delta = batch_mean - self.mean
        total = self.count + n
        self.mean = self.mean + delta * n / total
        self.var = (self.var * self.count + batch_var * n + delta * delta * self.count * n / total) / total
        self.count = total
        self.ret = self.ret * (~done)
        return reward / (self.var.sqrt() + 1e-8)

    def state_dict(self):
        return {"mean": self.mean, "var": self.var, "count": self.count}

    def load_state_dict(self, state):
        self.mean, self.var, self.count = (state[k].to(self.mean.device) for k in ("mean", "var", "count"))


class Evaluator:
    """Deterministic policy, normal starts, first episode of every evaluation game."""

    def __init__(self, args, device, seed, graph):
        import torch
        from src.rl.vector.game import GraphedStep, VectorGame

        self.limit = args.episode_limit
        self.game = VectorGame(args.eval_envs, device=device, frame_skip=args.frame_skip,
                               episode_limit=args.episode_limit, weights=VECTOR_REWARD, seed=seed)
        self.pending = torch.ones(args.eval_envs, dtype=torch.bool, device=device)
        self.game.count_mask = self.pending
        self.step = GraphedStep(self.game) if graph else self.game.step
        self.reset = self.step.reset if graph else self.game.reset

    def __call__(self, model):
        import torch

        self.pending.fill_(True)
        obs = self.reset()
        self.game.pop_stats()
        with torch.no_grad():
            for i in range(self.limit):
                logits, _ = model(obs)
                obs, _, terminated, truncated, _ = self.step(logits.argmax(-1))
                self.pending &= ~(terminated | truncated)
                if i % 32 == 31 and not bool(self.pending.any()):
                    break
        return self.game.pop_stats()


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("output already exists; choose a new --output directory")
    import torch
    from torch.utils.tensorboard import SummaryWriter
    from src.rl.vector.features import ACTION_COUNT, FEATURE_SIZE, SCHEMA
    from src.rl.vector.game import GraphedStep, VectorGame
    from src.rl.vector.policy import ActorCritic, load_checkpoint, save_checkpoint

    device = torch.device(("cuda" if torch.cuda.is_available() else "cpu") if args.device == "auto" else args.device)
    if args.torch_threads:
        torch.set_num_threads(args.torch_threads)
    envs = args.envs or (8192 if device.type == "cuda" else 1024)
    batch = envs * args.n_steps
    if batch % args.minibatches:
        parser.error("envs * n-steps must be divisible by --minibatches")
    minibatch = batch // args.minibatches
    torch.manual_seed(args.seed)
    # Distribution argument checks synchronise with the GPU on every step.
    torch.distributions.Distribution.set_default_validate_args(False)
    graph = device.type == "cuda" and not args.no_cuda_graph

    start_step = 0
    if args.resume:
        model, payload = load_checkpoint(args.resume, device)
        start_step = payload.get("timesteps", 0)
    else:
        model = ActorCritic(hidden=args.hidden).to(device)
        payload = {}
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr, eps=1e-5)
    if "optimizer" in payload:
        optimizer.load_state_dict(payload["optimizer"])
    scaler = ReturnScaler(envs, args.gamma, device)
    if "return_scaler" in payload:
        scaler.load_state_dict(payload["return_scaler"])

    game = VectorGame(envs, device=device, frame_skip=args.frame_skip, episode_limit=args.episode_limit,
                      weights=VECTOR_REWARD, shaping=args.shaping, gamma=args.gamma,
                      random_start=args.random_start, seed=args.seed)
    args.output.mkdir(parents=True)
    manifest = {
        "schema": SCHEMA, "algorithm": "PPO (on-device)", "policy": "ActorCritic",
        "env_kwargs": {"frame_skip": args.frame_skip, "episode_limit": args.episode_limit, "boss_mode": False},
        "reward_mode": "learning", "reward_weights": asdict(VECTOR_REWARD),
        "training_aids": {"shaping": args.shaping, "random_start": args.random_start},
        "resumed_from": str(args.resume) if args.resume else None,
        "seed": args.seed, "device": str(device), "envs": envs, "requested_timesteps": args.timesteps,
        "observation_size": FEATURE_SIZE, "actions": ACTION_COUNT,
        "versions": {name: version(name) for name in ("torch", "gymnasium", "numpy")},
        "hyperparameters": {k: getattr(args, k) for k in (
            "n_steps", "epochs", "minibatches", "lr", "final_lr_fraction", "gamma", "gae_lambda", "clip",
            "ent_coef", "vf_coef", "max_grad_norm")} | {"hidden": list(model.hidden)},
    }
    (args.output / "config.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    writer = SummaryWriter(str(args.output / "tensorboard"))
    metrics_file = (args.output / "metrics.jsonl").open("a", encoding="utf-8")

    T, N = args.n_steps, envs
    obs_buf = torch.zeros(T, N, FEATURE_SIZE, device=device)
    act_buf = torch.zeros(T, N, dtype=torch.long, device=device)
    logp_buf = torch.zeros(T, N, device=device)
    val_buf = torch.zeros(T, N, device=device)
    rew_buf = torch.zeros(T, N, device=device)
    done_buf = torch.zeros(T, N, device=device)
    updates = math.ceil(args.timesteps / batch)
    global_step = start_step
    best = payload.get("best_progress", -1.0)
    next_eval = global_step + args.eval_every
    next_checkpoint = global_step + args.checkpoint_every

    def extra():
        return {"timesteps": global_step, "best_progress": best, "return_scaler": scaler.state_dict(),
                "config": manifest}

    def log(values, step):
        for key, value in values.items():
            if isinstance(value, (int, float)):
                writer.add_scalar(key, value, step)
        metrics_file.write(json.dumps({"timesteps": step, **values}) + "\n")
        metrics_file.flush()

    step = GraphedStep(game) if graph else game.step
    obs = step.reset() if graph else game.reset()
    game.pop_stats()
    evaluator = Evaluator(args, device, args.seed + 1_000_003, graph)
    started = time.perf_counter()
    try:
        for update in range(updates):
            frac = update / max(1, updates)
            lr = args.lr * (1 - frac * (1 - args.final_lr_fraction))
            for group in optimizer.param_groups:
                group["lr"] = lr
            t0 = time.perf_counter()
            with torch.no_grad():
                for t in range(T):
                    model.norm.update(obs)
                    x = model.norm(obs)
                    logits, value = model.heads(x)
                    dist = torch.distributions.Categorical(logits=logits)
                    action = dist.sample()
                    obs_buf[t], act_buf[t], logp_buf[t], val_buf[t] = x, action, dist.log_prob(action), value
                    obs, reward, terminated, truncated, final_obs = step(action)
                    done = terminated | truncated
                    reward = scaler(reward.double(), done).float()
                    # Bootstrap games cut by the time limit (not real terminal states).
                    reward = reward + args.gamma * model(final_obs)[1] * truncated
                    rew_buf[t], done_buf[t] = reward, done.float()
                next_value = model(obs)[1]
                adv = torch.zeros_like(rew_buf)
                last = torch.zeros(N, device=device)
                for t in reversed(range(T)):
                    nonterminal = 1.0 - done_buf[t]
                    following = next_value if t == T - 1 else val_buf[t + 1]
                    delta = rew_buf[t] + args.gamma * following * nonterminal - val_buf[t]
                    last = delta + args.gamma * args.gae_lambda * nonterminal * last
                    adv[t] = last
                returns = adv + val_buf
            rollout_time = time.perf_counter() - t0
            t1 = time.perf_counter()
            b_obs, b_act, b_logp = obs_buf.reshape(batch, -1), act_buf.reshape(batch), logp_buf.reshape(batch)
            b_adv, b_ret = adv.reshape(batch), returns.reshape(batch)
            stats = torch.zeros(5, device=device)
            for _ in range(args.epochs):
                perm = torch.randperm(batch, device=device)
                for start in range(0, batch, minibatch):
                    idx = perm[start:start + minibatch]
                    logits, value = model.heads(b_obs[idx])
                    dist = torch.distributions.Categorical(logits=logits)
                    logp = dist.log_prob(b_act[idx])
                    ratio = (logp - b_logp[idx]).exp()
                    a = b_adv[idx]
                    a = (a - a.mean()) / (a.std() + 1e-8)
                    pg = torch.max(-a * ratio, -a * ratio.clamp(1 - args.clip, 1 + args.clip)).mean()
                    vf = 0.5 * (value - b_ret[idx]).square().mean()
                    entropy = dist.entropy().mean()
                    loss = pg + args.vf_coef * vf - args.ent_coef * entropy
                    optimizer.zero_grad(set_to_none=True)
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(model.parameters(), args.max_grad_norm)
                    optimizer.step()
                    with torch.no_grad():
                        log_ratio = logp - b_logp[idx]
                        stats += torch.stack((pg, vf, entropy, ((ratio - 1) - log_ratio).mean(),
                                              ((ratio - 1).abs() > args.clip).float().mean())).detach()
            stats = (stats / (args.epochs * args.minibatches)).tolist()
            update_time = time.perf_counter() - t1
            global_step += batch
            var_y = b_ret.var()
            explained = float(1 - (b_ret - val_buf.reshape(batch)).var() / var_y) if var_y > 0 else 0.0
            values = {"train/policy_loss": stats[0], "train/value_loss": stats[1], "train/entropy": stats[2],
                      "train/approx_kl": stats[3], "train/clip_fraction": stats[4],
                      "train/explained_variance": explained, "train/lr": lr,
                      "time/sps": batch / (rollout_time + update_time),
                      "time/rollout_s": rollout_time, "time/update_s": update_time}
            episode = game.pop_stats()
            if episode["episodes"]:
                values.update({f"game/{k}": v for k, v in episode.items()})
            log(values, global_step)
            print(f"[{global_step:>12,}] sps={values['time/sps']:,.0f} "
                  f"ent={stats[2]:.2f} kl={stats[3]:.4f} ev={explained:.2f} "
                  + (f"| ep={episode['episodes']} prog={episode['progress']:.2f} "
                     f"score={episode['score']:.0f} boss={episode['boss_damage']:.2f} "
                     f"deaths={episode['deaths']:.2f} len={episode['length']:.0f}" if episode["episodes"] else ""),
                  flush=True)
            if global_step >= next_eval or update == updates - 1:
                next_eval += args.eval_every
                model.eval()
                result = evaluator(model)
                model.train()
                log({f"eval/{k}": v for k, v in result.items()}, global_step)
                print(f"  eval: {json.dumps(result)}", flush=True)
                if result.get("episodes") and result["progress"] > best:
                    best = result["progress"]
                    save_checkpoint(args.output / "best.pt", model, extra=extra() | {"eval": result})
            if global_step >= next_checkpoint:
                next_checkpoint += args.checkpoint_every
                save_checkpoint(args.output / "checkpoints" / f"step_{global_step}.pt", model,
                                optimizer=optimizer, extra=extra())
    except KeyboardInterrupt:
        save_checkpoint(args.output / "interrupted.pt", model, optimizer=optimizer, extra=extra())
        print(f"Interrupted model saved to {args.output / 'interrupted.pt'}")
        return
    finally:
        writer.close()
        metrics_file.close()
    save_checkpoint(args.output / "final.pt", model, optimizer=optimizer, extra=extra())
    manifest["actual_timesteps"] = global_step
    manifest["wall_seconds"] = time.perf_counter() - started
    (args.output / "config.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
