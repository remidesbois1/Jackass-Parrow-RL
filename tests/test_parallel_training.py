"""Behavioral parity for grouped training environments on Windows spawn."""
import tempfile
import unittest
from functools import partial

import numpy as np
from stable_baselines3.common.env_util import make_vec_env

from examples.train_ppo import make_training_env
from src.rl import RewardWeights
from src.rl.parallel import GroupedSubprocVecEnv, FastDummyVecEnv


class ParallelParityTests(unittest.TestCase):
    def test_grouped_matches_single_process_including_resets(self):
        kwargs = {"episode_limit": 4, "frame_skip": 4}
        weights = RewardWeights(score=0.02, death=-5)
        metrics = ("score", "levels_cleared", "health")
        with tempfile.TemporaryDirectory() as directory:
            grouped = GroupedSubprocVecEnv(4, 2, kwargs, "learning", weights, directory, metrics)
            reference = make_vec_env(partial(make_training_env, kwargs, "learning", weights),
                                     n_envs=4, seed=42, vec_env_cls=FastDummyVecEnv,
                                     monitor_kwargs={"info_keywords": metrics})
            try:
                grouped.seed(42)
                np.testing.assert_array_equal(grouped.reset(), reference.reset())
                old_obs = None
                for n in range(10):
                    actions = np.array([[n % 3, n % 2, 0, 1]] * 4)
                    obs, rewards, dones, infos = grouped.step(actions)
                    expected, r2, d2, i2 = reference.step(actions)
                    np.testing.assert_array_equal(obs, expected)
                    np.testing.assert_allclose(rewards, r2)
                    np.testing.assert_array_equal(dones, d2)
                    for a, b in zip(infos, i2):
                        self.assertEqual(a['score'], b['score'])
                        if 'terminal_observation' in a:
                            np.testing.assert_array_equal(a['terminal_observation'], b['terminal_observation'])
                            self.assertEqual(a['TimeLimit.truncated'], b['TimeLimit.truncated'])
                    if old_obs is not None:
                        np.testing.assert_array_equal(old_obs, old_snapshot)
                    old_obs, old_snapshot = obs, obs.copy()
                self.assertEqual(grouped.get_attr('render_mode'), [None] * 4)
            finally:
                grouped.close()
                reference.close()


if __name__ == '__main__':
    unittest.main()
