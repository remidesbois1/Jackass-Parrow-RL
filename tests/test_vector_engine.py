"""Tick-by-tick parity of the torch vector engine with the reference kernel."""

from random import Random
import unittest

try:
    import torch
except ImportError:  # optional training extra
    torch = None

from src.headless import Config, HeadlessEnv
from src.headless.engine import level_geometry
from src.system.level_data import HARD_LEVEL_IDS, NORMAL_LEVEL_IDS

if torch is not None:
    from src.rl.vector.engine import VectorEngine
    from src.rl.vector.sync import sync_from_headless

PLAYER_FIELDS = ("px", "py", "speed", "grav", "kb", "dirn", "health", "score", "last_shot",
                 "last_hit", "on_ground", "shield")


def _player(env):
    p = env.player
    return (p.rect.x, p.rect.y, p.speed, p.gravity, p.knockback, p.direction, p.health,
            p.score, p.last_shot, p.last_hit, p.on_ground, p.shield)


def _active(vec, prefix):
    act = getattr(vec, prefix + "_act")[0]
    order = getattr(vec, prefix + "_seq")[0][act].argsort()
    return [tuple(getattr(vec, prefix + k)[0][act][order].tolist()) for k in ("_x", "_y", "_v")]


def _ambiguous_shot(env):
    tick = env.ticks + 1
    for e in env.enemies:
        if e.kind == 2:
            continue
        lo, hi = (1120, 1540) if e.kind == 1 else (1600, 2200)
        if lo * 60 < (tick - e.last_shot) * 1000 <= hi * 60:
            return True
    return False


@unittest.skipIf(torch is None, "torch is not installed")
class VectorEngineParityTests(unittest.TestCase):
    def assertState(self, ref, vec, *, entities=True, position=True, label=""):
        expected = _player(ref)
        for name, value in zip(PLAYER_FIELDS, expected):
            if not position and name in ("px", "py"):
                continue
            self.assertAlmostEqual(float(getattr(vec, name)[0]), float(value), places=9,
                                   msg=f"{label} {name}")
        for name in ("ticks", "levels_cleared", "bosses_defeated", "boss_damage", "world"):
            self.assertEqual(int(getattr(vec, name)[0]), getattr(ref, name), f"{label} {name}")
        if ref.boss is not None:
            self.assertEqual(int(vec.boss_health[0]), ref.boss.health, label)
        if not entities:
            return
        alive = vec.e_alive[0]
        self.assertEqual(int(alive.sum()), len(ref.enemies), f"{label} enemies")
        for name, values in (("e_x", [e.rect.x for e in ref.enemies]),
                             ("e_dir", [e.direction for e in ref.enemies]),
                             ("e_last", [e.last_shot for e in ref.enemies])):
            got = getattr(vec, name)[0][alive].tolist()
            for g, v in zip(got, values):
                self.assertAlmostEqual(g, v, places=9, msg=f"{label} {name}")
        for prefix, bullets in (("pb", ref.bullets), ("qb", ref.enemy_bullets)):
            xs, ys, vs = _active(vec, prefix)
            self.assertEqual(len(xs), len(bullets), f"{label} {prefix} count")
            for b, x, y, v in zip(bullets, xs, ys, vs):
                self.assertAlmostEqual(x, b.rect.x, places=9, msg=f"{label} {prefix} x")
                self.assertAlmostEqual(y, b.rect.y, places=9, msg=f"{label} {prefix} y")
                self.assertEqual(v, b.velocity, f"{label} {prefix} v")

    def test_every_tick_matches_reference_from_synchronised_states(self):
        loads = hits = kills = 0
        # (seed, boss mode, second loop): the second loop plays the HARD tableaux.
        for seed, boss_mode, loop in ((0, False, False), (1, False, False), (2, True, False),
                                      (3, False, False), (4, True, False), (5, False, True), (6, False, True)):
            ref = HeadlessEnv(seed=seed, config=Config(frame_skip=1, max_episode_steps=None,
                                                       boss_mode=boss_mode))
            vec = VectorEngine(1, frame_skip=1, episode_limit=None, boss_mode=boss_mode, seed=seed)
            rng = Random(seed)
            action = 0
            for tick in range(1500):
                if ref.terminated or (loop and tick == 0):
                    ref.reset()
                    if loop:
                        ref.world, ref.level = 1, 0
                        ref._load_level()
                if rng.random() < 0.004 and ref.boss is None:
                    ref.enemies.clear()  # visit more tableaux, including level loads
                if rng.random() < 0.15:
                    action = rng.randrange(32)
                if rng.random() < 0.01:
                    # Explore collisions everywhere, including fractional edges.
                    p = ref.player
                    p.rect.x, p.rect.y = rng.uniform(-20, 1220), rng.uniform(-50, 720)
                    p.gravity = rng.uniform(-1250, 1000)
                    p.speed = rng.choice((-400, 0, 400))
                    p.knockback = rng.uniform(-1500, 1500)
                sync_from_headless(vec, 0, ref)
                ambiguous = _ambiguous_shot(ref)
                before = (ref.levels_cleared, ref.bosses_defeated, ref.boss_damage, ref.player.health,
                          ref.player.score)
                ref._tick(action)
                vec._tick(torch.tensor([action]))
                loaded = (ref.levels_cleared, ref.bosses_defeated) != before[:2]
                loads += loaded
                hits += ref.player.health != before[3]
                kills += ref.player.score != before[4]
                self.assertState(ref, vec, entities=not (loaded or ambiguous), position=not loaded,
                                 label=f"seed={seed} tick={tick}")
        self.assertGreater(loads, 3)
        self.assertGreater(hits, 3)
        self.assertGreater(kills, 3)

    def test_decision_events_stop_at_death_like_reference(self):
        ref = HeadlessEnv(seed=5, config=Config(frame_skip=4, max_episode_steps=50))
        vec = VectorEngine(1, frame_skip=4, episode_limit=50, seed=5)
        ref.player.health = 1
        ref._shoot(ref.enemy_bullets, ref.player.rect.x + 10, ref.player.rect.y + 10, 1, True)
        sync_from_headless(vec, 0, ref)
        ref.advance(0)
        events = vec.step(torch.tensor([0]))
        self.assertTrue(ref.terminated)
        self.assertTrue(bool(vec.terminated[0]))
        self.assertEqual(int(events["ticks"][0]), ref.ticks)
        self.assertEqual(int(events["death"][0]), 1)
        self.assertEqual(int(events["health_lost"][0]), 1)
        self.assertEqual(int(vec.steps[0]), ref.steps)

    def test_level_loads_follow_reference_spawning_rules(self):
        n = 256
        vec = VectorEngine(n, seed=7)
        everyone = torch.ones(n, dtype=torch.bool)
        for world, (lo, hi) in ((0, NORMAL_LEVEL_IDS), (1, HARD_LEVEL_IDS)):
            seen = set()
            for _ in range(20):
                previous = vec.level_id.clone()
                vec.world.fill_(world)
                vec._load_level(everyone, torch.zeros(n, dtype=torch.bool))
                lid = vec.level_id
                self.assertTrue(bool(((lid >= lo) & (lid <= hi)).all()))
                self.assertFalse(bool((previous == lid).any()))
                seen.update(lid.tolist())
                for i in range(0, n, 37):
                    blocks, spawn, spawnable = level_geometry(int(lid[i]))
                    alive = vec.e_alive[i]
                    danger = int(vec.danger[i])
                    self.assertEqual(danger, world * 3 + int(vec.level[i]))
                    self.assertEqual(int(alive.sum()), min(danger, len(spawnable)))
                    self.assertEqual((float(vec.px[i]), float(vec.py[i])), spawn)
                    platforms = set()
                    for e in torch.nonzero(alive).flatten().tolist():
                        plat = next(b for b in spawnable if b.x == vec.e_plx[i, e] and b.w == vec.e_plw[i, e]
                                    and b.y == vec.e_y[i, e] + vec.e_h[i, e])
                        platforms.add(plat)
                        self.assertTrue(plat.x <= vec.e_x[i, e] <= plat.x + plat.w - 37)
                        kind = int(vec.e_kind[i, e])
                        self.assertIn(kind, (2, int(danger > 5)))
                    self.assertEqual(len(platforms), int(alive.sum()))
            self.assertEqual(seen, set(range(lo, hi + 1)))
            vec.reset(everyone)

    def test_varied_starts_cover_every_tableau_tom_and_second_loop(self):
        from src.rl.vector.game import VectorGame

        game = VectorGame(2048, random_start=1.0, seed=3)
        game.reset()
        e = game.engine
        boss = e.boss_on
        self.assertTrue(bool((e.danger[~boss] == e.world[~boss] * 3 + e.level[~boss]).all()))
        self.assertEqual(set(e.level[~boss].tolist()), set(range(1, 8)))
        self.assertEqual(set(e.world.tolist()), {0, 1})
        self.assertTrue(bool((e.level[boss] == 7).all()) and int(boss.sum()) > 0)
        self.assertFalse(bool(game.normal_start.any()))

    def test_feature_env_runs_reference_game_with_vector_features(self):
        from gymnasium.utils.env_checker import check_env
        from src.rl.vector.env import FeatureEnv
        from src.rl.vector.features import FEATURE_SIZE

        env = FeatureEnv(frame_skip=4, episode_limit=20)
        try:
            check_env(env, skip_render_check=True)
            obs, _ = env.reset(seed=1)
            self.assertEqual(obs.shape, (FEATURE_SIZE,))
            for _ in range(20):
                obs, _, terminated, truncated, info = env.step(env.action_space.sample())
                if terminated or truncated:
                    break
            self.assertTrue(truncated or terminated)
        finally:
            env.close()


if __name__ == "__main__":
    unittest.main()
