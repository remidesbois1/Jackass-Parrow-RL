"""Gymnasium adapter; gameplay remains entirely in the headless kernel."""

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from src.headless import Config, HeadlessEnv
from .observations import OBSERVATION_SIZE, ObservationEncoder


class JackassParrowEnv(gym.Env):
    """Numeric, headless-only environment with simultaneous button actions.

    Actions: [movement (0 idle, 1 left, 2 right), jump, down, fire].
    Reward is the original score delta. LearningReward is an optional wrapper.
    episode_limit counts decisions; frame_skip counts physics ticks per decision.
    """

    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 60}

    def __init__(self, *, frame_skip=4, episode_limit=9000, boss_mode=False, render_mode=None):
        if render_mode not in (None, "human", "rgb_array"):
            raise ValueError("render_mode must be None, human or rgb_array")
        self.render_mode = render_mode
        self._renderer = None
        self.on_render_tick = None
        self.engine = HeadlessEnv(config=Config(frame_skip=frame_skip,
                                               max_episode_steps=episode_limit,
                                               boss_mode=boss_mode))
        self.action_space = spaces.MultiDiscrete([3, 2, 2, 2])
        self.observation_space = spaces.Box(-10, 10, shape=(OBSERVATION_SIZE,), dtype=np.float32)
        self._encoder = ObservationEncoder()
        self._needs_reset = True

    def decode_action(self, action):
        values = np.asarray(action)
        if (values.shape != (4,) or not np.issubdtype(values.dtype, np.integer)
                or not self.action_space.contains(values)):
            raise ValueError("action must be four integers: [movement 0..2, jump 0..1, down 0..1, fire 0..1]")
        move, jump, down, fire = (int(value) for value in values)
        return (0, 1, 2)[move] | (jump << 2) | (down << 3) | (fire << 4)

    def _result(self, score_delta=0):
        obs, overflow = self._encoder.encode(self.engine)
        info = self.engine.info()
        info.update(score_delta=score_delta, observation_overflow=overflow,
                    is_success=bool(self.engine.terminated and self.engine.player.health > 0))
        return obs, info

    def reset(self, *, seed=None, options=None):
        if options:
            raise ValueError("reset options are not supported; configure the environment constructor")
        super().reset(seed=seed)
        self.engine.reset(seed=seed, observe=False)
        self._needs_reset = False
        if self.render_mode == "human":
            self.render()
        return self._result()

    def step(self, action):
        if self._needs_reset:
            raise gym.error.ResetNeeded("call reset() before step() or after an episode ends")
        mask = self.decode_action(action)
        if self.render_mode == "human":
            renderer = self.renderer
            renderer.action = tuple(int(v) for v in action)
            reward = self.engine.advance(mask, on_tick=self.on_render_tick or renderer.present)
        else:
            reward = self.engine.advance(mask)
        self._needs_reset = self.engine.done
        obs, info = self._result(reward)
        return obs, float(reward), self.engine.terminated, self.engine.truncated, info

    @property
    def renderer(self):
        if self.render_mode is None:
            return None
        if self._renderer is None:
            from .rendering import HeadlessRenderer

            self._renderer = HeadlessRenderer(self.render_mode)
        return self._renderer

    def render(self):
        if self.render_mode is None:
            return None
        return self.renderer.present(self.engine)

    def close(self):
        if self._renderer is not None:
            self._renderer.close()
            self._renderer = None
        self._needs_reset = True
