"""Finite throughput benchmark; multiprocessing exchanges aggregate results only."""

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing
import os
from time import perf_counter
import tracemalloc

from .engine import Config
from .vector import BatchEnv


def _run_chunk(start, count, seed, steps, frame_skip, observe, memory, boss_mode=False):
    if memory:
        tracemalloc.start()
    batch = BatchEnv(count, seed=seed + start, config=Config(frame_skip=frame_skip, boss_mode=boss_mode))
    # A fixed action schedule exercises movement, jump, shield, fire and reset.
    # It is a benchmark driver, not a trained or learning policy.
    actions = [0] * count
    episodes = ticks = score = 0
    for step in range(steps):
        for i in range(count):
            phase = (step + (start + i) * 13) % 240
            actions[i] = 16 | (2 if phase < 120 else 1) | (4 if phase % 60 < 20 else 0)
            if 100 <= phase < 115:
                actions[i] = 8 | 16
        batch.advance(actions)
        if observe:
            for env in batch.envs:
                env.observe()
        for env in batch.envs:
            if env.done:
                episodes += 1
                ticks += env.ticks
                score += env.player.score
        batch.reset_done()
    ticks += sum(e.ticks for e in batch.envs)
    score += sum(e.player.score for e in batch.envs)
    result = {"ticks": ticks, "episodes": episodes, "score": score,
              "player_bullets": sum(len(e.bullets) for e in batch.envs),
              "enemy_bullets": sum(len(e.enemy_bullets) for e in batch.envs)}
    if memory:
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        result.update(python_bytes=current, python_peak_bytes=peak)
    return result


def positive_int(value):
    value = int(value)
    if value < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description="Jackass-Parrow headless throughput benchmark (no training)")
    parser.add_argument("--envs", type=positive_int, default=64, help="total simultaneous environments (default: 64)")
    parser.add_argument("--steps", type=positive_int, default=1000, help="decisions per environment (default: 1000)")
    parser.add_argument("--workers", type=positive_int, default=1, help="processes; many environments share each process")
    parser.add_argument("--frame-skip", type=positive_int, default=1, help="60 Hz physics ticks per decision")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--boss-mode", action="store_true", help="start directly against Tom")
    parser.add_argument("--observe", action="store_true", help="include numeric observation snapshot cost")
    parser.add_argument("--memory", action="store_true", help="trace Python allocations (slows the benchmark)")
    args = parser.parse_args(argv)
    workers = min(args.workers, args.envs)
    jobs = []
    offset = 0
    for worker in range(workers):
        count = args.envs // workers + (worker < args.envs % workers)
        jobs.append((offset, count, args.seed, args.steps, args.frame_skip, args.observe, args.memory, args.boss_mode))
        offset += count
    started = perf_counter()
    if workers == 1:
        results = [_run_chunk(*jobs[0])]
    else:
        # Spawn also on Unix: deterministic isolation and Windows compatibility.
        # Only W coarse jobs and W small results cross process boundaries.
        with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn")) as pool:
            futures = [pool.submit(_run_chunk, *job) for job in jobs]
            results = [future.result() for future in futures]
    elapsed = perf_counter() - started
    totals = {key: sum(result[key] for result in results) for key in results[0]}
    decisions = args.envs * args.steps
    report = {"environments": args.envs, "workers": workers, "cpu_count": os.cpu_count(),
              "decisions": decisions, "frame_skip": args.frame_skip,
              "boss_mode": args.boss_mode, "seed": args.seed,
              "observations": args.observe, "memory_tracing": args.memory,
              "elapsed_seconds": round(elapsed, 6),
              "decisions_per_second": round(decisions / elapsed),
              "physics_ticks_per_second": round(totals["ticks"] / elapsed),
              "simulated_seconds_per_second": round(totals["ticks"] / 60 / elapsed, 2),
              **totals}
    print(json.dumps(report, indent=2))
    return report
