"""Optional Gymnasium integration. Import explicitly to register the environment.

The standalone headless package never imports this module or its dependencies.
"""

from gymnasium.envs.registration import register, registry

from .env import JackassParrowEnv
from .rewards import LearningReward, RewardWeights

ENV_ID = "JackassParrow-v0"

if ENV_ID not in registry:
    register(id=ENV_ID, entry_point="src.rl.env:JackassParrowEnv")

__all__ = ["ENV_ID", "JackassParrowEnv", "LearningReward", "RewardWeights"]
