"""Play a saved PPO policy in the original graphics using headless physics.

python -m examples.watch_ppo --model runs/demo/final.zip --config runs/demo/config.json
"""

import argparse
import json
import math
import os
from pathlib import Path
import sys
from time import perf_counter

from src.rl.runs import load_config, load_policy, make_run_env
from .train_ppo import positive_int


class ViewerClosed(Exception):
    pass


class RestartEpisode(Exception):
    def __init__(self, replay):
        self.replay = replay


def positive_speed(value):
    number = float(value)
    if not math.isfinite(number) or number < 0.1 or number > 8:
        raise argparse.ArgumentTypeError("speed must be finite and between 0.1 and 8")
    return number


class ViewerControls:
    def __init__(self, renderer, *, screenshot=None):
        import pygame

        self.pygame = pygame
        self.renderer = renderer
        self.clock = pygame.time.Clock()
        self.screenshot = screenshot
        self.screenshot_saved = False

    def _events(self):
        p = self.pygame
        r = self.renderer
        for event in p.event.get():
            if event.type == p.QUIT or (event.type == p.KEYDOWN and event.key == p.K_ESCAPE):
                raise ViewerClosed
            if event.type != p.KEYDOWN:
                continue
            if event.key == p.K_SPACE:
                r.paused = not r.paused
            elif event.key == p.K_TAB:
                r.stochastic = not r.stochastic
            elif event.key in (p.K_r, p.K_n):
                raise RestartEpisode(replay=event.key == p.K_r)
            elif event.key in (p.K_LEFT, p.K_RIGHT):
                speeds = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0)
                index = min(range(len(speeds)), key=lambda i: abs(speeds[i] - r.speed))
                r.speed = speeds[max(0, min(len(speeds) - 1, index + (-1 if event.key == p.K_LEFT else 1)))]

    def capture(self):
        if self.screenshot and not self.screenshot_saved:
            self.screenshot.parent.mkdir(parents=True, exist_ok=True)
            self.pygame.image.save(self.renderer.surface, str(self.screenshot))
            self.screenshot_saved = True

    def on_tick(self, engine):
        while True:
            self._events()
            self.renderer.draw(engine)
            if engine.ticks >= 60:
                self.capture()
            self.clock.tick(max(1, round(60 * self.renderer.speed)))
            if not self.renderer.paused:
                return

    def hold(self, engine, seconds=1.2):
        until = perf_counter() + seconds
        while perf_counter() < until or self.renderer.paused:
            self.on_tick(engine)


def build_parser():
    parser = argparse.ArgumentParser(description="Watch a saved PPO agent play Jackass-Parrow")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--speed", type=positive_speed, default=1.0)
    parser.add_argument("--stochastic", action="store_true", help="sample actions from the learned policy")
    parser.add_argument("--episodes", type=positive_int, help="stop after this many episodes; default loops until closed")
    parser.add_argument("--max-decisions", type=positive_int, help="stop after a finite number of policy decisions")
    parser.add_argument("--screenshot", type=Path, help="save one frame after one simulated second")
    parser.add_argument("--log-file", type=Path, help="optional JSON-lines log for detached launches")
    parser.add_argument("--time-limit", action="store_true",
                        help="keep the training episode limit; by default a game only ends on death")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.seed < 0:
        parser.error("seed must be non-negative")
    if not args.model.is_file():
        parser.error(f"model not found: {args.model}")
    try:
        config = load_config(args.config)
    except ValueError as error:
        parser.error(str(error))
    if not args.time_limit and config.get("schema") not in ("JackassParrowCurriculum-v1", "JackassParrowCourses-v2"):
        # Watching plays the real game: no decision limit, the game ends on death.
        config = {**config, "env_kwargs": {**config.get("env_kwargs", {}), "episode_limit": None}}

    def report(event, **values):
        line = json.dumps({"event": event, **values})
        if sys.stdout is not None:
            print(line, flush=True)
        if args.log_file:
            args.log_file.parent.mkdir(parents=True, exist_ok=True)
            with args.log_file.open("a", encoding="utf-8") as stream:
                stream.write(line + "\n")

    # Loading the policy precedes window creation so a bad file leaves no window.
    env = make_run_env(config, render_mode="human")
    controls = None
    episode = completed = decisions = 0
    seed = args.seed
    try:
        model = load_policy(args.model, env)
        import torch

        renderer = env.unwrapped.renderer
        renderer.policy_name = args.model.parent.name if args.model.parent.name != "best" else args.model.parent.parent.name
        renderer.speed = args.speed
        renderer.stochastic = args.stochastic
        controls = ViewerControls(renderer, screenshot=args.screenshot)
        env.unwrapped.on_render_tick = controls.on_tick
        report("viewer_ready", pid=os.getpid(), model=str(args.model), seed=seed,
               deterministic=not renderer.stochastic)
        while args.episodes is None or completed < args.episodes:
            try:
                renderer.episode = episode + 1
                renderer.paused = False
                torch.manual_seed(seed)
                obs, info = env.reset(seed=seed)
                while True:
                    controls._events()
                    if renderer.paused:
                        controls.on_tick(env.unwrapped.engine)
                    action, _ = model.predict(obs, deterministic=not renderer.stochastic)
                    obs, _, terminated, truncated, info = env.step(action)
                    decisions += 1
                    if args.max_decisions is not None and decisions >= args.max_decisions:
                        controls.capture()
                        report("viewer_finished", decisions=decisions, score=info["score"], ticks=info["ticks"])
                        return
                    if terminated or truncated:
                        # Draw after final decision accounting (including truncation).
                        renderer.draw(env.unwrapped.engine)
                        report("episode_finished", episode=episode + 1, seed=seed,
                               score=info["score"], ticks=info["ticks"],
                               levels_cleared=info["levels_cleared"],
                               boss_damage=info["boss_damage"], bosses_defeated=info["bosses_defeated"])
                        controls.hold(env.unwrapped.engine)
                        completed += 1
                        episode += 1
                        seed += 1
                        break
            except RestartEpisode as restart:
                if not restart.replay:
                    seed += 1
                    episode += 1
    except (ViewerClosed, KeyboardInterrupt):
        report("viewer_closed", decisions=decisions)
    finally:
        env.close()


if __name__ == "__main__":
    main()
