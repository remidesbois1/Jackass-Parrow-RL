"""Deterministic, asset-free simulation. Importing this package never imports SDL."""

from .engine import Action, Config, HeadlessEnv
from .vector import BatchEnv

__all__ = ["Action", "BatchEnv", "Config", "HeadlessEnv"]
