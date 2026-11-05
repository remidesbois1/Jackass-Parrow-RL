"""Explicit, optional learning rewards; never change the game's raw score."""

from dataclasses import dataclass
import math

import gymnasium as gym


@dataclass(frozen=True, slots=True)
class RewardWeights:
    score: float = 0.01
    boss_damage: float = 0.25
    level_cleared: float = 1.0
    boss_defeated: float = 5.0
    health_lost: float = -0.25
    death: float = -1.0
    tick: float = -0.0001

    def __post_init__(self):
        if not all(math.isfinite(getattr(self, name)) for name in self.__dataclass_fields__):
            raise ValueError("reward weights must be finite")


class LearningReward(gym.Wrapper):
    """A starting heuristic to tune, not a claim of optimal reward design.

    No positive survival reward; standing still with a shield earns no points.
    Event counters capture boss hits and transitions even inside frame skipping.
    """

    def __init__(self, env, weights=None):
        super().__init__(env)
        self.weights = RewardWeights() if weights is None else weights

    def step(self, action):
        engine = self.unwrapped.engine
        before = (engine.boss_damage, engine.levels_cleared, engine.bosses_defeated,
                  engine.player.health, engine.ticks)
        obs, score_delta, terminated, truncated, info = self.env.step(action)
        w = self.weights
        components = {
            "score": score_delta * w.score,
            "boss_damage": (engine.boss_damage - before[0]) * w.boss_damage,
            "level_cleared": (engine.levels_cleared - before[1]) * w.level_cleared,
            "boss_defeated": (engine.bosses_defeated - before[2]) * w.boss_defeated,
            "health_lost": max(0, before[3] - engine.player.health) * w.health_lost,
            "death": float(terminated and engine.player.health <= 0) * w.death,
            "tick": (engine.ticks - before[4]) * w.tick,
        }
        info["reward_components"] = components
        return obs, float(sum(components.values())), terminated, truncated, info
