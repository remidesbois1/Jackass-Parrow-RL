"""First PPO experiment. Training happens only when this CLI is explicitly run.

python -m examples.train_ppo --check-only
python -m examples.train_ppo --timesteps 1000000 --envs 16 --output runs/ppo-seed0
"""

import argparse
import csv
from dataclasses import asdict
from functools import partial
from importlib.metadata import version
import json
import math
from pathlib import Path

from src.rl import JackassParrowEnv, LearningReward, RewardWeights


def positive_int(value):
    value = int(value)
    if value < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return value


def nonnegative_float(value):
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise argparse.ArgumentTypeError("must be a finite non-negative number")
    return value


def make_training_env(env_kwargs, reward_mode, reward_weights=None):
    if "course_stage" in env_kwargs:
        from src.rl.courses import CourseEnv
        return CourseEnv(**env_kwargs)
    if "curriculum_stage" in env_kwargs:
        from src.rl.curriculum import CurriculumEnv
        return CurriculumEnv(**env_kwargs)
    env = JackassParrowEnv(**env_kwargs)
    if reward_mode == "learning":
        env = LearningReward(env, reward_weights)
    return env


def build_parser():
    parser = argparse.ArgumentParser(description="Train your own Jackass-Parrow PPO agent")
    parser.add_argument("--check-only", action="store_true", help="validate Gymnasium/SB3; do not train or create a run")
    parser.add_argument("--init-from-guide", type=Path, help="reuse game-state weights while deleting all guidance inputs")
    parser.add_argument("--timesteps", type=positive_int, default=1_000_000)
    parser.add_argument("--envs", type=positive_int, default=16)
    parser.add_argument("--backend", choices=("dummy", "fast", "subproc", "grouped"), default="dummy")
    parser.add_argument("--workers", type=positive_int, default=4,
                        help="processes for grouped backend")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--frame-skip", type=positive_int, default=4)
    parser.add_argument("--episode-limit", type=positive_int, default=9000)
    parser.add_argument("--boss-mode", action="store_true")
    parser.add_argument("--reward", choices=("score", "learning"), default="learning")
    parser.add_argument("--reward-profile", choices=("original", "combat"), default="original")
    parser.add_argument("--tick-penalty", type=nonnegative_float, default=0.0001,
                        help="positive penalty per physics tick (learning reward only)")
    parser.add_argument("--output", type=Path, default=Path("runs/ppo-seed0"))
    parser.add_argument("--torch-threads", type=positive_int, default=4)
    parser.add_argument("--n-steps", type=positive_int, default=512, help="rollout decisions per environment")
    parser.add_argument("--batch-size", type=positive_int, default=256)
    parser.add_argument("--epochs", type=positive_int, default=10)
    parser.add_argument("--eval-every", type=positive_int, default=50_000, help="aggregate agent decisions")
    parser.add_argument("--eval-episodes", type=positive_int, default=10)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.seed < 0:
        parser.error("seed must be non-negative")
    if args.backend == "grouped" and args.workers > args.envs:
        parser.error("--workers cannot exceed --envs")
    if args.envs * args.n_steps <= 1:
        parser.error("--envs times --n-steps must be greater than 1")
    # Imported only by this explicit training/validation entry point, never by
    # src.headless or the Gymnasium adapter itself.
    import torch
    from gymnasium.utils.env_checker import check_env
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import BaseCallback, CheckpointCallback, EvalCallback
    from stable_baselines3.common.env_checker import check_env as sb3_check
    from stable_baselines3.common.env_util import make_vec_env
    from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

    env_kwargs = {"frame_skip": args.frame_skip, "episode_limit": args.episode_limit,
                  "boss_mode": args.boss_mode}
    candidate = JackassParrowEnv(**env_kwargs)
    try:
        check_env(candidate, skip_render_check=True)
        sb3_check(candidate)
    finally:
        candidate.close()
    if args.check_only:
        print("Gymnasium and Stable-Baselines3 checks passed. No training started.")
        return
    if args.output.exists():
        parser.error("output already exists; choose a new --output directory for this experiment")

    torch.set_num_threads(args.torch_threads)
    metrics = ("score", "levels_cleared", "boss_damage", "bosses_defeated", "health", "is_success")

    class GameMetricsCallback(BaseCallback):
        def _on_step(self):
            return True

        def _on_rollout_end(self):
            episodes = self.model.ep_info_buffer
            if episodes:
                for key in metrics:
                    self.logger.record(f"game/{key}_mean", sum(e[key] for e in episodes) / len(episodes))

    class GameEvalCallback(EvalCallback):
        """Keep SB3 reward selection, and also save by game score on fixed seeds."""
        def __init__(self, *callback_args, **callback_kwargs):
            super().__init__(*callback_args, **callback_kwargs)
            self.best_game_key = None

        def _on_step(self):
            evaluating = self.eval_freq > 0 and self.n_calls % self.eval_freq == 0
            if evaluating:
                self.eval_env.seed(args.seed + 100_000)
            result = super()._on_step()
            if evaluating:
                with (args.output / "eval-monitor" / "0.monitor.csv").open(newline="", encoding="utf-8") as stream:
                    next(stream)
                    rows = list(csv.DictReader(stream))[-args.eval_episodes:]
                if len(rows) == args.eval_episodes:
                    mean_score = sum(float(row["score"]) for row in rows) / len(rows)
                    mean_levels = sum(float(row["levels_cleared"]) for row in rows) / len(rows)
                    mean_health = sum(float(row["health"]) for row in rows) / len(rows)
                    game_key = (mean_score, mean_levels, mean_health)
                    print(f"Evaluation game score={mean_score:.1f}, levels={mean_levels:.2f}, health={mean_health:.2f}", flush=True)
                    if self.best_game_key is None or game_key > self.best_game_key:
                        self.best_game_key = game_key
                        self.model.save(args.output / "best" / "best_game")
                        (args.output / "best" / "best_game.json").write_text(json.dumps({
                            "timesteps": self.num_timesteps, "mean_score": mean_score,
                            "mean_levels": mean_levels, "mean_health": mean_health,
                            "evaluation_seed": args.seed + 100_000,
                            "episodes": len(rows)}, indent=2), encoding="utf-8")
            return result

    reward_weights = (RewardWeights(score=0.02, level_cleared=1.0, health_lost=-0.5,
                                    death=-5.0, tick=-args.tick_penalty)
                      if args.reward_profile == "combat" else RewardWeights(tick=-args.tick_penalty))
    factory = partial(make_training_env, env_kwargs, args.reward, reward_weights)
    from src.rl.parallel import FastDummyVecEnv, GroupedSubprocVecEnv
    backend = {"dummy": DummyVecEnv, "fast": FastDummyVecEnv,
               "subproc": SubprocVecEnv}.get(args.backend)
    vec_kwargs = {"start_method": "spawn"} if args.backend == "subproc" else {}
    train_env = eval_env = None
    args.output.mkdir(parents=True, exist_ok=False)
    try:
        if args.backend == "grouped":
            (args.output / "train-monitor").mkdir()
            train_env = GroupedSubprocVecEnv(args.envs, args.workers, env_kwargs,
                                              args.reward, reward_weights,
                                              args.output / "train-monitor", metrics)
            train_env.seed(args.seed)
        else:
            train_env = make_vec_env(factory, n_envs=args.envs, seed=args.seed,
                                     vec_env_cls=backend, vec_env_kwargs=vec_kwargs,
                                     monitor_dir=str(args.output / "train-monitor"),
                                     monitor_kwargs={"info_keywords": metrics})
        # Training and evaluation use distinct random sequences and environments.
        eval_env = make_vec_env(factory, n_envs=1, seed=args.seed + 100_000,
                                vec_env_cls=DummyVecEnv,
                                monitor_dir=str(args.output / "eval-monitor"),
                                monitor_kwargs={"info_keywords": metrics})
        manifest = {
            "schema": "JackassParrow-v0", "algorithm": "PPO", "policy": "MlpPolicy",
            "env_kwargs": env_kwargs, "reward_mode": args.reward,
            "reward_weights": asdict(reward_weights) if args.reward == "learning" else None,
            "reward_profile": args.reward_profile,
            "navigation_guidance": False,
            "initialization": str(args.init_from_guide) if args.init_from_guide else None,
            "seed": args.seed, "evaluation_seed": args.seed + 100_000,
            "requested_timesteps": args.timesteps, "envs": args.envs, "backend": args.backend,
            "workers": args.workers if args.backend == "grouped" else None,
            "versions": {name: version(name) for name in ("gymnasium", "stable-baselines3", "numpy", "torch")},
            "hyperparameters": {"n_steps": args.n_steps, "batch_size": args.batch_size, "n_epochs": args.epochs,
                                "learning_rate": 3e-4, "gamma": 0.995,
                                "gae_lambda": 0.95, "ent_coef": 0.01,
                                "net_arch": [128, 128], "device": "cpu"},
        }
        (args.output / "config.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        callbacks = [
            GameMetricsCallback(),
            GameEvalCallback(eval_env, eval_freq=max(args.eval_every // args.envs, 1),
                         n_eval_episodes=args.eval_episodes, deterministic=True,
                         best_model_save_path=str(args.output / "best"),
                         log_path=str(args.output / "eval")),
            CheckpointCallback(save_freq=max(args.eval_every // args.envs, 1),
                               save_path=str(args.output / "checkpoints"), name_prefix="ppo"),
        ]
        model = PPO("MlpPolicy", train_env, n_steps=args.n_steps, batch_size=args.batch_size,
                    n_epochs=args.epochs, learning_rate=3e-4, gamma=0.995, gae_lambda=0.95,
                    ent_coef=0.01, seed=args.seed, device="cpu",
                    policy_kwargs={"net_arch": [128, 128]},
                    tensorboard_log=str(args.output / "tensorboard"), verbose=1)
        if args.init_from_guide:
            from src.rl.transfer import initialize_without_guidance
            initialize_without_guidance(model, args.init_from_guide)
            model.save(args.output / "initial")
        try:
            model.learn(total_timesteps=args.timesteps, callback=callbacks, tb_log_name="PPO")
        except KeyboardInterrupt:
            model.save(args.output / "interrupted")
            print(f"Interrupted model saved to {args.output / 'interrupted.zip'}")
            return
        model.save(args.output / "final")
        manifest["actual_timesteps"] = model.num_timesteps
        (args.output / "config.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    finally:
        if eval_env is not None:
            eval_env.close()
        if train_env is not None:
            train_env.close()


if __name__ == "__main__":
    main()
