import json
from pathlib import Path
import subprocess
import sys
import unittest

from src.headless import Action, BatchEnv, Config, HeadlessEnv
from src.headless.engine import Enemy, Platform, Rect, level_geometry

ROOT = Path(__file__).resolve().parents[1]


def sandbox(**config):
    env = HeadlessEnv(42, Config(**config))
    floor = Platform(-10, 775, 1300, 50)
    env.blocks = (floor,)
    # Keep a living enemy outside the playfield to avoid automatic level changes.
    env.enemies = [Enemy(Rect(4000, -10000, 75, 90), 0, floor)]
    env.player.rect.x, env.player.rect.y = 200, 100
    return env


class HeadlessTests(unittest.TestCase):
    def test_runs_without_site_packages_or_pygame(self):
        code = """
import sys
from src.headless import BatchEnv
b = BatchEnv(8)
for _ in range(500):
    b.advance([16] * 8)
    b.reset_done()
assert not any(n.startswith(('pygame', 'numpy', 'torch')) for n in sys.modules)
"""
        result = subprocess.run([sys.executable, "-S", "-c", code], cwd=ROOT,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_seeded_replay_is_independent_of_other_environments(self):
        a, b, noise = HeadlessEnv(17), HeadlessEnv(17), HeadlessEnv(99)
        for i in range(1000):
            action = (i * 17) % 32
            self.assertEqual(a.step(action), b.step(action))
            noise.advance((i * 7) % 32)
            if a.done:
                self.assertEqual(a.reset(), b.reset())
            if noise.done:
                noise.reset(observe=False)
        self.assertEqual(a.rng.getstate(), b.rng.getstate())
        initial, _ = a.reset(seed=17)
        self.assertEqual(initial, HeadlessEnv(17).observe())

    def test_geometry_shared_and_mutable_entities_isolated(self):
        a, b = HeadlessEnv(1), HeadlessEnv(1)
        self.assertIs(a.blocks, b.blocks)
        self.assertIsNot(a.player, b.player)
        self.assertIsNot(a.enemies[0], b.enemies[0])
        a.player.health = 1
        a.enemies[0].rect.x += 100
        self.assertEqual(b.player.health, 3)
        self.assertNotEqual(a.enemies[0].rect.x, b.enemies[0].rect.x)

    def test_bad_actions_do_not_mutate_state(self):
        env = HeadlessEnv(3)
        before = env.observe(), env.rng.getstate()
        for action in (-1, 32, 1.5, "left", None, True):
            with self.subTest(action=action), self.assertRaises(ValueError):
                env.advance(action)
            self.assertEqual(before, (env.observe(), env.rng.getstate()))

    def test_config_validation(self):
        for value in (0, -1, 1.5, True):
            with self.assertRaises(ValueError):
                Config(frame_skip=value)
            with self.assertRaises(ValueError):
                Config(max_episode_steps=value)
        for count in (0, -1, 1.5, True):
            with self.assertRaises(ValueError):
                BatchEnv(count)

    def test_frame_skip_is_repeated_physics_not_a_larger_dt(self):
        a, b = HeadlessEnv(17, Config(frame_skip=4)), HeadlessEnv(17)
        for i in range(150):
            action = (i * 11) % 32
            score = a.advance(action)
            expected = 0
            for _ in range(4):
                expected += b.advance(action)
                if b.done:
                    break
            self.assertEqual(score, expected)
            oa, ob = a.observe(), b.observe()
            oa.pop("context")
            ob.pop("context")
            self.assertEqual(oa, ob)
            self.assertEqual(a.ticks, b.ticks)
            if a.done:
                a.reset(observe=False)
                b.reset(observe=False)

    def test_episode_limit_and_explicit_reset(self):
        env = sandbox(frame_skip=4, max_episode_steps=2)
        env.advance(0)
        _, _, terminated, truncated, info = env.step(0)
        self.assertFalse(terminated)
        self.assertTrue(truncated)
        self.assertEqual(info["ticks"], 8)
        snapshot = env.observe()
        with self.assertRaises(RuntimeError):
            env.advance(0)
        self.assertEqual(snapshot, env.observe())
        env.reset(observe=False)
        self.assertFalse(env.done)

    def test_death_stops_frame_skip_immediately(self):
        env = sandbox(frame_skip=10)
        env.player.health = 1
        env._shoot(env.enemy_bullets, 200, 100, -1, True)
        env.advance(0)
        self.assertTrue(env.terminated)
        self.assertFalse(env.truncated)
        self.assertEqual(env.ticks, 1)

    def test_landing_jumping_and_fast_fall(self):
        env = sandbox()
        for _ in range(90):
            env.advance(0)
        p = env.player
        self.assertTrue(p.on_ground)
        self.assertEqual(p.rect.y + p.rect.h, 776)
        env.advance(Action.JUMP)
        self.assertFalse(p.on_ground)
        self.assertEqual(p.gravity, -1250)
        env.advance(Action.DOWN)
        self.assertEqual(p.gravity, 1000)

    def test_backwards_fire_recoil_and_cooldown(self):
        env = sandbox()
        env.player.last_shot = -60
        env.advance(Action.RIGHT | Action.FIRE)
        self.assertEqual(len(env.bullets), 1)
        self.assertEqual(env.bullets[0].velocity, -600)
        self.assertEqual(env.player.knockback, 1500)
        env.advance(Action.FIRE)
        self.assertEqual(len(env.bullets), 1)

    def test_shield_only_blocks_facing_side(self):
        for direction, health in ((-1, 3), (1, 2)):
            with self.subTest(direction=direction):
                env = sandbox()
                env.player.shield = True
                env.player.direction = direction
                env._shoot(env.enemy_bullets, 180, 100, 1, True)
                env.advance(0)
                self.assertEqual(env.player.health, health)
                self.assertEqual(len(env.enemy_bullets), 0)

    def test_damage_immunity_including_multiple_chickens(self):
        env = sandbox()
        env.enemies.extend(Enemy(Rect(200, 100, 60, 70), 2, env.blocks[0]) for _ in range(2))
        env.advance(0)
        self.assertEqual(env.player.health, 2)
        env._hit_player()
        self.assertEqual(env.player.health, 2)
        env.ticks += 37
        env._hit_player()
        self.assertEqual(env.player.health, 1)

    def test_enemy_death_awards_score_once_and_cleans_up(self):
        env = sandbox()
        env.enemies.append(Enemy(Rect(500, 100, 75, 90), 1, env.blocks[0]))
        env._shoot(env.bullets, 500, 100, 1)
        env._shoot(env.bullets, 500, 100, 1)
        self.assertEqual(env.advance(0), 150)
        self.assertEqual(len(env.enemies), 1)
        self.assertEqual(len(env.bullets), 1)
        self.assertEqual(env.advance(0), 0)
        self.assertEqual(env.player.score, 150)

    def test_projectiles_collide_filter_transparent_and_leave_world(self):
        env = sandbox()
        env.blocks = (Platform(220, 100, 50, 100, transparent=True),)
        env._shoot(env.bullets, 200, 100, 1)
        env.advance(0)
        self.assertEqual(len(env.bullets), 1)
        env.blocks = (Platform(220, 100, 50, 100),)
        env.bullets.clear()
        env._shoot(env.bullets, 200, 100, 1)
        env.advance(0)
        self.assertFalse(env.bullets)
        for direction, x in ((1, 1280), (-1, -36)):
            env._shoot(env.bullets, x, -1000, direction)
        env.advance(0)
        self.assertFalse(env.bullets)

    def test_transition_to_boss_and_next_world_danger(self):
        env = HeadlessEnv(1)
        for expected in range(2, 8):
            previous = env.level_id
            env.enemies.clear()
            env.advance(0)
            self.assertEqual(env.level, expected)
            self.assertNotEqual(env.level_id, previous)
        env.enemies.clear()
        env.advance(0)
        self.assertIsNotNone(env.boss)
        self.assertEqual(env.level_id, 0)
        env.boss.health = 0
        env.advance(0)
        self.assertIsNone(env.boss)
        self.assertEqual((env.world, env.level, env.danger), (1, 1, 4))
        self.assertFalse(env.done)

    def test_boss_hit_immunity_gap_and_boss_mode_win(self):
        env = HeadlessEnv(1, Config(boss_mode=True))
        boss = env.boss
        for _ in range(2):
            env._shoot(env.bullets, 950, 120, 1)
        env.advance(0)
        self.assertEqual(boss.health, 9)
        self.assertEqual(len(boss.shields), 2)
        gap_y = 575 - boss.hole * 200
        self.assertNotIn(gap_y, [b.y for b in boss.shields])
        env.advance(0)
        self.assertEqual(boss.health, 9)
        boss.health = 0
        env.advance(0)
        self.assertTrue(env.terminated)

    def test_shields_block_player_bullets_but_not_enemy_bullets(self):
        env = HeadlessEnv(1, Config(boss_mode=True))
        env.boss.shields = (Platform(790, 375, 50, 150),)
        env._shoot(env.bullets, 780, 400, 1)
        env._shoot(env.enemy_bullets, 780, 400, 1, True)
        env.advance(0)
        self.assertFalse(env.bullets)
        self.assertTrue(env.enemy_bullets)

    def test_observation_is_serializable_detached_and_includes_timers(self):
        env = HeadlessEnv(1)
        obs = env.observe()
        saved = json.dumps(obs)
        env.advance(31)
        self.assertEqual(json.dumps(obs), saved)
        self.assertEqual(len(obs["player"]), 13)

    def test_rebind_projectile_geometry_on_level_change(self):
        env = HeadlessEnv(1)
        env._shoot(env.bullets, 100, 100, 1)
        bullet = env.bullets[0]
        env._load_level(boss=True)
        self.assertEqual(bullet.blockers, env._blockers(bullet.rect))
        self.assertTrue(all(b in env.blocks for b in bullet.blockers))

    def test_batch_matches_individual_seeds_and_reuses_buffers(self):
        batch = BatchEnv(3, seed=17, config=Config(max_episode_steps=3))
        singles = [HeadlessEnv(17 + i, Config(max_episode_steps=3)) for i in range(3)]
        rewards = batch.rewards
        for _ in range(3):
            self.assertIs(batch.advance([1, 16, 4]), rewards)
            for env, single, action in zip(batch.envs, singles, (1, 16, 4)):
                single.advance(action)
                self.assertEqual(env.observe(), single.observe())
        self.assertEqual(batch.reset_done(), 3)
        self.assertFalse(any(batch.truncated))
        self.assertEqual(batch.reset_done(), 0)

    def test_invalid_batch_is_atomic(self):
        batch = BatchEnv(2)
        before = [e.observe() for e in batch.envs]
        for actions in ([1], [1, 32]):
            with self.assertRaises(ValueError):
                batch.advance(actions)
            self.assertEqual(before, [e.observe() for e in batch.envs])
        batch.envs[1].terminated = True
        with self.assertRaises(RuntimeError):
            batch.advance([1, 1])
        self.assertEqual(before, [e.observe() for e in batch.envs])

    def test_long_run_has_bounded_entities_and_geometry_cache(self):
        batch = BatchEnv(16, config=Config(max_episode_steps=2000))
        for i in range(5000):
            batch.advance([16 | (i % 16)] * 16)
            for env in batch.envs:
                self.assertLess(len(env.bullets), 8)
                self.assertLess(len(env.enemy_bullets), 80)
                self.assertLessEqual(len(env.enemies), 6)
            batch.reset_done()
        self.assertLessEqual(level_geometry.cache_info().currsize, 11)

    def test_multiprocess_benchmark_matches_single_process(self):
        command = [sys.executable, "main.py", "--headless", "--envs", "7", "--steps", "300"]
        reports = []
        for workers in (1, 3):
            result = subprocess.run(command + ["--workers", str(workers)], cwd=ROOT,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            reports.append(json.loads(result.stdout))
        for key in ("ticks", "episodes", "score", "player_bullets", "enemy_bullets"):
            self.assertEqual(reports[0][key], reports[1][key], key)


if __name__ == "__main__":
    unittest.main()
