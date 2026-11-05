from functools import partial
from contextlib import closing, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

GYM_AVAILABLE = importlib.util.find_spec("gymnasium") is not None
SB3_AVAILABLE = importlib.util.find_spec("stable_baselines3") is not None

if GYM_AVAILABLE:
    import gymnasium as gym
    import numpy as np
    from gymnasium.utils.env_checker import check_env

    from src.headless import HeadlessEnv
    from src.headless.engine import Enemy, Platform, Rect
    from src.rl import ENV_ID, JackassParrowEnv, LearningReward, RewardWeights
    from src.rl.observations import OBSERVATION_SHAPES, OBSERVATION_SLICES, OBSERVATION_SIZE


@unittest.skipUnless(GYM_AVAILABLE, "install the rl extra for Gymnasium tests")
class GymnasiumTests(unittest.TestCase):
    def test_official_checker_for_campaign_and_boss(self):
        for boss_mode in (False, True):
            with JackassParrowEnv(boss_mode=boss_mode) as env:
                check_env(env, skip_render_check=True)

    def test_registration_and_valid_masked_float32_observations(self):
        with gym.make(ENV_ID) as env:
            obs, info = env.reset(seed=17)
            self.assertEqual(obs.shape, (OBSERVATION_SIZE,))
            self.assertEqual(obs.dtype, np.float32)
            self.assertTrue(env.observation_space.contains(obs))
            rows = obs[OBSERVATION_SLICES["enemies"]].reshape(OBSERVATION_SHAPES["enemies"])
            self.assertEqual(int(rows[:, 0].sum()), len(env.unwrapped.engine.enemies))
            np.testing.assert_array_equal(rows[len(env.unwrapped.engine.enemies):], 0)
            self.assertFalse(any(info["observation_overflow"].values()))
            self.assertEqual(info["score"], 0)

    def test_action_mapping_covers_simultaneous_controls(self):
        env = JackassParrowEnv()
        masks = set()
        for move in range(3):
            for jump in range(2):
                for down in range(2):
                    for fire in range(2):
                        mask = env.decode_action(np.array([move, jump, down, fire], dtype=np.int64))
                        masks.add(mask)
                        self.assertEqual(mask & 3, move)
                        self.assertEqual(bool(mask & 4), bool(jump))
                        self.assertEqual(bool(mask & 8), bool(down))
                        self.assertEqual(bool(mask & 16), bool(fire))
        self.assertEqual(len(masks), 24)

    def test_invalid_action_does_not_advance_or_change_rng(self):
        env = JackassParrowEnv()
        obs, _ = env.reset(seed=1)
        rng = env.engine.rng.getstate()
        for action in (16, [3, 0, 0, 0], [0, 2, 0, 0], [0, 0, 0],
                       [0.0, 0.0, 0.0, 1.0], [True] * 4):
            with self.subTest(action=action), self.assertRaises(ValueError):
                env.step(action)
            np.testing.assert_array_equal(obs, env._result()[0])
            self.assertEqual(env.engine.rng.getstate(), rng)

    def test_seed_replay_and_snapshot_ownership(self):
        a, b = JackassParrowEnv(), JackassParrowEnv()
        a.action_space.seed(123)
        oa, ia = a.reset(seed=7)
        ob, ib = b.reset(seed=7)
        np.testing.assert_array_equal(oa, ob)
        self.assertEqual(ia, ib)
        saved = oa.copy()
        for _ in range(300):
            action = a.action_space.sample()
            oa, *ra = a.step(action)
            ob, *rb = b.step(action)
            np.testing.assert_array_equal(oa, ob)
            self.assertEqual(ra, rb)
            if a.engine.done:
                oa, _ = a.reset()
                ob, _ = b.reset()
                np.testing.assert_array_equal(oa, ob)
        np.testing.assert_array_equal(saved, a.reset(seed=7)[0])
        self.assertFalse(np.shares_memory(saved, oa))

    def test_adapter_retains_engine_rules_and_raw_reward(self):
        adapter = JackassParrowEnv(frame_skip=1)
        adapter.reset(seed=123)
        direct = HeadlessEnv(123)
        for i in range(300):
            action = np.array([i % 3, i % 2, (i // 2) % 2, 1])
            _, reward, terminated, truncated, info = adapter.step(action)
            expected = direct.advance(adapter.decode_action(action))
            self.assertEqual(reward, float(expected))
            self.assertEqual(adapter.engine.observe(), direct.observe())
            self.assertEqual(info["score"], direct.player.score)
            self.assertEqual(terminated, direct.terminated)
            self.assertEqual(truncated, direct.truncated)
            if terminated or truncated:
                adapter.reset()
                direct.reset(observe=False)

    def test_reset_required_and_truncation_retains_final_observation(self):
        env = JackassParrowEnv(frame_skip=4, episode_limit=1)
        with self.assertRaises(gym.error.ResetNeeded):
            env.step([0, 0, 0, 0])
        env.reset(seed=0)
        obs, _, terminated, truncated, info = env.step([0, 0, 0, 0])
        self.assertFalse(terminated)
        self.assertTrue(truncated)
        self.assertEqual((info["ticks"], info["steps"]), (4, 1))
        saved = obs.copy()
        with self.assertRaises(gym.error.ResetNeeded):
            env.step([0, 0, 0, 0])
        env.reset()
        np.testing.assert_array_equal(obs, saved)
        env.close()
        env.close()

    def test_nearest_overflow_reporting_and_finite_bounds(self):
        env = JackassParrowEnv()
        env.reset(seed=0)
        e = env.engine
        e.bullets.clear()
        for x in range(100, 1000, 10):
            e._shoot(e.bullets, x, 100, 1)
        obs, info = env._result()
        self.assertEqual(info["observation_overflow"]["bullets"], 82)
        rows = obs[OBSERVATION_SLICES["bullets"]].reshape(8, 6)
        px = e.player.rect.x + e.player.rect.w / 2
        expected = sorted(e.bullets, key=lambda b: abs(b.rect.x + b.rect.w / 2 - px))[:8]
        np.testing.assert_allclose(rows[:, 1], [b.rect.x / 1280 for b in expected])
        e.player.rect.x = 100_000
        obs, _ = env._result()
        self.assertTrue(env.observation_space.contains(obs))
        self.assertTrue(np.isfinite(obs).all())

    def test_static_map_cache_changes_with_level(self):
        env = JackassParrowEnv()
        first, _ = env.reset(seed=0)
        env.engine._load_level(boss=True)
        second, _ = env._result()
        self.assertFalse(np.array_equal(first[OBSERVATION_SLICES["blocks"]],
                                        second[OBSERVATION_SLICES["blocks"]]))
        self.assertEqual(second[OBSERVATION_SLICES["boss"]][0], 1)

    def test_score_wrapper_components_and_no_score_mutation(self):
        wrapped = LearningReward(JackassParrowEnv(frame_skip=1))
        wrapped.reset(seed=0)
        engine = wrapped.unwrapped.engine
        floor = engine.blocks[0]
        engine.enemies = [Enemy(Rect(500, 100, 75, 90), 1, floor)]
        engine._shoot(engine.bullets, 500, 100, 1)
        _, reward, _, _, info = wrapped.step([0, 0, 0, 0])
        self.assertEqual(info["score"], 150)
        self.assertEqual(info["score_delta"], 150)
        self.assertEqual(info["levels_cleared"], 1)
        self.assertAlmostEqual(reward, 1.5 + 1 - 0.0001)
        self.assertAlmostEqual(reward, sum(info["reward_components"].values()))

    def test_boss_events_survive_frame_skip_and_transition(self):
        env = LearningReward(JackassParrowEnv(frame_skip=4, boss_mode=True))
        env.reset(seed=0)
        engine = env.unwrapped.engine
        engine.boss.health = 1
        engine._shoot(engine.bullets, 950, 120, 1)
        _, reward, terminated, truncated, info = env.step([0, 0, 0, 0])
        self.assertTrue(terminated)
        self.assertFalse(truncated)
        self.assertTrue(info["is_success"])
        self.assertEqual(info["boss_damage"], 1)
        self.assertEqual(info["bosses_defeated"], 1)
        self.assertEqual(info["ticks"], 1)
        self.assertAlmostEqual(reward, 0.25 + 5 - 0.0001)
        env.reset()
        self.assertEqual(engine.boss_damage, 0)
        self.assertEqual(engine.bosses_defeated, 0)

    def test_death_penalty_but_no_penalty_for_time_limit(self):
        env = LearningReward(JackassParrowEnv(frame_skip=4, episode_limit=1))
        env.reset(seed=0)
        _, reward, term, trunc, info = env.step([0, 0, 0, 0])
        self.assertFalse(term)
        self.assertTrue(trunc)
        self.assertEqual(info["reward_components"]["death"], 0)
        env.reset(seed=0)
        e = env.unwrapped.engine
        e.player.health = 1
        e._shoot(e.enemy_bullets, e.player.rect.x, e.player.rect.y, -1, True)
        _, reward, term, trunc, info = env.step([0, 0, 0, 0])
        self.assertTrue(term)
        self.assertFalse(trunc)
        self.assertAlmostEqual(reward, -0.25 - 1 - 0.0001)

    def test_reward_weights_reject_nonfinite(self):
        for value in (float("inf"), float("nan")):
            with self.assertRaises(ValueError):
                RewardWeights(score=value)

    def test_sync_and_spawn_async_vectors(self):
        factories = [partial(JackassParrowEnv, episode_limit=2) for _ in range(2)]
        for vector_class in (gym.vector.SyncVectorEnv, gym.vector.AsyncVectorEnv):
            kwargs = {"context": "spawn"} if vector_class is gym.vector.AsyncVectorEnv else {}
            with closing(vector_class(factories, **kwargs)) as envs:
                obs, _ = envs.reset(seed=17)
                self.assertEqual(obs.shape, (2, OBSERVATION_SIZE))
                obs, reward, term, trunc, info = envs.step(np.zeros((2, 4), dtype=np.int64))
                self.assertFalse(term.any())
                _, _, _, trunc, _ = envs.step(np.zeros((2, 4), dtype=np.int64))
                self.assertTrue(trunc.all())

    @unittest.skipUnless(SB3_AVAILABLE, "install the train extra for SB3 compatibility")
    def test_sb3_checker_and_policy_prediction_without_training(self):
        from stable_baselines3 import PPO
        from stable_baselines3.common.env_checker import check_env as sb3_check
        from stable_baselines3.common.vec_env import DummyVecEnv

        env = JackassParrowEnv()
        sb3_check(env, warn=True)
        with closing(DummyVecEnv([JackassParrowEnv, JackassParrowEnv])) as vector:
            model = PPO("MlpPolicy", vector, n_steps=8, batch_size=8, device="cpu",
                        seed=0, policy_kwargs={"net_arch": [32, 32]})
            obs = vector.reset()
            action, _ = model.predict(obs, deterministic=True)
            self.assertEqual(action.shape, (2, 4))
            vector.step(action)
            self.assertEqual(model.num_timesteps, 0)  # no learn() call
            # Also exercise the saved-model evaluation entry point without
            # training a model or keeping generated artifacts in the repository.
            from examples.evaluate_ppo import main as evaluate

            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                model.save(root / "untrained")
                config = root / "config.json"
                config.write_text(json.dumps({"schema": ENV_ID, "env_kwargs": {"episode_limit": 2},
                                              "reward_mode": "score"}), encoding="utf-8")
                with redirect_stdout(io.StringIO()):
                    report = evaluate(["--model", str(root / "untrained.zip"),
                                       "--config", str(config), "--episodes", "2"])
                self.assertEqual(report["episodes"], 2)
                self.assertTrue(all(e["truncated"] for e in report["results"]))

    @unittest.skipUnless(SB3_AVAILABLE, "install the train extra for SB3 compatibility")
    def test_training_factory_monitor_keeps_game_metrics_and_final_observation(self):
        from stable_baselines3.common.env_util import make_vec_env
        from examples.train_ppo import make_training_env

        factory = partial(make_training_env, {"episode_limit": 1}, "learning")
        with closing(make_vec_env(factory, n_envs=2, seed=0,
                                  monitor_kwargs={"info_keywords": ("score", "levels_cleared")})) as vector:
            vector.reset()
            _, _, done, infos = vector.step(np.zeros((2, 4), dtype=np.int64))
            self.assertTrue(done.all())
            for info in infos:
                self.assertEqual(info["episode"]["score"], info["score"])
                self.assertIn("levels_cleared", info["episode"])
                self.assertIn("terminal_observation", info)

    def test_random_evaluation_replays_fixed_seeds(self):
        from examples.evaluate_ppo import main as evaluate

        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            config.write_text(json.dumps({"schema": ENV_ID, "env_kwargs": {"episode_limit": 3},
                                          "reward_mode": "learning"}), encoding="utf-8")
            args = ["--random", "--config", str(config), "--episodes", "2", "--seed", "17"]
            with redirect_stdout(io.StringIO()):
                first = evaluate(args)
                second = evaluate(args)
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
