"""Gymnasium env on the *reference* kernel with the v1 egocentric features.

Training uses the vector engine; viewing and held-out evaluation use this
adapter, so a v1 model is always judged on the original ``HeadlessEnv`` rules.
"""

import numpy as np
from gymnasium import spaces

from ..env import JackassParrowEnv
from .engine import VectorEngine
from .features import FEATURE_SIZE, encode
from .sync import sync_from_headless


class FeatureEnv(JackassParrowEnv):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.observation_space = spaces.Box(-10, 10, shape=(FEATURE_SIZE,), dtype=np.float32)
        self._mirror = VectorEngine(1, frame_skip=self.engine.config.frame_skip, episode_limit=None)

    def _result(self, score_delta=0):
        sync_from_headless(self._mirror, 0, self.engine)
        obs, _ = encode(self._mirror)
        info = self.engine.info()
        info.update(score_delta=score_delta,
                    is_success=bool(self.engine.terminated and self.engine.player.health > 0))
        return obs[0].numpy(), info
