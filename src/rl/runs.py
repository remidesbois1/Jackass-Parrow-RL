"""Shared saved-run loading for numerical evaluation and graphical playback."""

import json
from pathlib import Path

from . import ENV_ID, JackassParrowEnv, LearningReward, RewardWeights


def load_config(path=None):
    config = json.loads(Path(path).read_text(encoding="utf-8")) if path else {}
    if not isinstance(config, dict):
        raise ValueError("run config must be a JSON object")
    if config.get("schema", ENV_ID) not in (ENV_ID, "JackassParrowCurriculum-v1", "JackassParrowCourses-v2",
                                            "JackassParrow-v2"):
        raise ValueError("config schema does not match this environment version")
    if config.get("reward_mode", "learning") not in ("score", "learning"):
        raise ValueError("config reward_mode must be score or learning")
    return config


def make_run_env(config, *, render_mode=None):
    kwargs = dict(config.get("env_kwargs", {}))
    kwargs["render_mode"] = render_mode
    if config.get("schema") == "JackassParrowCourses-v2":
        from .courses import CourseEnv
        return CourseEnv(**kwargs)
    if config.get("schema") == "JackassParrowCurriculum-v1":
        from .curriculum import CurriculumEnv
        return CurriculumEnv(**kwargs)
    if config.get("schema") == "JackassParrow-v2":
        from .vector.env import FeatureEnv
        env = FeatureEnv(**kwargs)
    else:
        env = JackassParrowEnv(**kwargs)
    if config.get("reward_mode", "learning") == "learning":
        weights = config.get("reward_weights")
        env = LearningReward(env, RewardWeights(**weights) if weights else None)
    return env


def load_policy(path, env):
    import torch

    # Small inference batches benefit from avoiding CPU thread oversubscription.
    torch.set_num_threads(1)
    if Path(path).suffix == ".pt":
        from .vector.policy import VectorPolicy
        model = VectorPolicy.load(path)
        if env.observation_space.shape != (model.model.norm.mean.numel(),):
            raise ValueError("model spaces do not match this environment/schema")
        return model
    from stable_baselines3 import PPO

    model = PPO.load(path, device="cpu")
    if model.observation_space != env.observation_space or model.action_space != env.action_space:
        raise ValueError("model spaces do not match this environment/schema")
    return model
