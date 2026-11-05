"""Evaluate saved PPO or random actions on a fixed, held-out set of seeds."""

import argparse
import json
from pathlib import Path
from statistics import mean, pstdev

from src.rl.runs import load_config, load_policy, make_run_env
from .train_ppo import positive_int


def main(argv=None):
    parser = argparse.ArgumentParser(description="Evaluate a PPO policy or a random baseline (no learning)")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--model", type=Path)
    source.add_argument("--random", action="store_true")
    parser.add_argument("--config", type=Path, help="training config.json; use the same file for fair comparisons")
    parser.add_argument("--episodes", type=positive_int, default=20)
    parser.add_argument("--seed", type=int, default=200_000, help="first held-out seed")
    args = parser.parse_args(argv)
    if args.seed < 0:
        parser.error("seed must be non-negative")
    if args.model is not None and args.config is None:
        parser.error("--model requires its training --config to restore environment/reward settings")
    try:
        config = load_config(args.config)
    except ValueError as error:
        parser.error(str(error))
    env = make_run_env(config)
    model = None
    try:
        if args.model is not None:
            model = load_policy(args.model, env)
        episodes = []
        for episode in range(args.episodes):
            seed = args.seed + episode
            obs, info = env.reset(seed=seed)
            env.action_space.seed(seed)
            total_reward = 0.0
            while True:
                action = env.action_space.sample() if model is None else model.predict(obs, deterministic=True)[0]
                obs, reward, terminated, truncated, info = env.step(action)
                total_reward += reward
                if terminated or truncated:
                    break
            episodes.append({"seed": seed, "reward": total_reward, "score": info["score"],
                             "levels_cleared": info["levels_cleared"],
                             "boss_damage": info["boss_damage"], "bosses_defeated": info["bosses_defeated"],
                             "simulated_seconds": info["ticks"] / 60,
                             "success": info["is_success"], "truncated": truncated})
        metrics = ("score", "levels_cleared", "boss_damage", "bosses_defeated", "simulated_seconds", "reward")
        report = {"policy": "random" if model is None else str(args.model),
                  "episodes": args.episodes, "seed": args.seed,
                  "mean": {key: mean(e[key] for e in episodes) for key in metrics},
                  "std": {key: pstdev(e[key] for e in episodes) for key in metrics},
                  "results": episodes}
        print(json.dumps(report, indent=2))
        return report
    finally:
        env.close()


if __name__ == "__main__":
    main()
