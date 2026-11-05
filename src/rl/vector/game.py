"""Batched training environment: engine + features + rewards + automatic reset.

The game reward uses the same components and weights as ``LearningReward``.
Training adds two explicit, documented aids that never change the game rules:

* potential-based shaping ``coef * (gamma * phi(s') - phi(s))`` toward a line
  of fire (``phi`` from ``features.encode``; zero after a terminal state), which
  leaves the optimal policy unchanged (Ng et al., 1999);
* optional varied starts: a fraction of games start at a random tableau, at
  Tom, or in the second loop, so late-game situations are practised early.
  Statistics are reported separately for games started normally.
"""

import torch

from src.headless.engine import OLD_WORLD_LEVELS
from ..rewards import RewardWeights
from .engine import VectorEngine
from .features import ACTION_COUNT, action_masks, encode

STAT_KEYS = ("episodes", "score", "levels_cleared", "boss_damage", "bosses_defeated", "deaths",
             "length", "game_return", "progress")


def game_reward(events, weights):
    """LearningReward for a batch of per-decision events (float64)."""
    w = weights
    return (events["score"] * w.score + events["boss_damage"] * w.boss_damage
            + events["levels_cleared"] * w.level_cleared + events["bosses_defeated"] * w.boss_defeated
            + events["health_lost"] * w.health_lost + events["death"] * w.death
            + events["ticks"] * w.tick).double()


class VectorGame:
    def __init__(self, num_envs, *, device="cpu", frame_skip=4, episode_limit=3600, boss_mode=False,
                 weights=None, shaping=0.0, gamma=0.995, random_start=0.0, seed=0):
        if not 0.0 <= random_start <= 1.0:
            raise ValueError("random_start must be within [0, 1]")
        self.engine = VectorEngine(num_envs, device=device, frame_skip=frame_skip,
                                   episode_limit=episode_limit, boss_mode=boss_mode, seed=seed)
        self.n = num_envs
        self.device = self.engine.device
        self.weights = weights if weights is not None else RewardWeights()
        self.shaping = shaping
        self.gamma = gamma
        self.random_start = random_start
        self.masks = action_masks(self.device)
        zeros = lambda: torch.zeros(num_envs, dtype=torch.float64, device=self.device)
        self.normal_start = torch.ones(num_envs, dtype=torch.bool, device=self.device)
        self.potential = zeros()
        # Per-episode totals from live ticks only (a dead player's game is frozen).
        self.episode_return = zeros()
        self.totals = {key: zeros() for key in ("score", "levels_cleared", "boss_damage", "bosses_defeated")}
        self._stats = {key: torch.zeros((), dtype=torch.float64, device=self.device) for key in STAT_KEYS}
        # Optional bool[N]: only games still marked are recorded (evaluation uses
        # it to keep the first episode of every game, without a bias to short ones).
        self.count_mask = None

    def _restart(self, mask):
        e = self.engine
        if self.random_start > 0 and not e.boss_mode:
            varied = mask & (e._rand(self.n) < self.random_start)
            world = (e._rand(self.n) < 0.25).long()
            level = (e._rand(self.n) * (OLD_WORLD_LEVELS + 1)).long() + 1
            e.reset(mask, world=torch.where(varied, world, 0), level=torch.where(varied, level, 1))
            self.normal_start = torch.where(mask, ~varied, self.normal_start)
        else:
            e.reset(mask)
        self.episode_return = torch.where(mask, 0.0, self.episode_return)
        for key, value in self.totals.items():
            self.totals[key] = torch.where(mask, 0.0, value)

    def reset(self):
        self._restart(torch.ones(self.n, dtype=torch.bool, device=self.device))
        obs, self.potential = encode(self.engine)
        return obs

    def step(self, actions):
        """Apply compact actions; return (obs, reward, terminated, truncated, final_obs).

        ``obs`` already belongs to the next episode where a game ended;
        ``final_obs`` is the last observation of the finished episode, needed to
        bootstrap the value of games cut by the time limit.
        """
        e = self.engine
        events = e.step(self.masks[actions])
        final_obs, potential = encode(e)
        terminated, truncated = e.terminated.clone(), e.truncated.clone()
        done = terminated | truncated
        game = game_reward(events, self.weights)
        next_potential = torch.where(terminated, 0.0, potential)
        reward = game + self.shaping * (self.gamma * next_potential - self.potential)
        self.episode_return = self.episode_return + game
        for key in self.totals:
            self.totals[key] = self.totals[key] + events[key]
        self._record(done, events)
        self._restart(done)
        obs, self.potential = encode(e)
        return obs, reward.float(), terminated, truncated, final_obs

    def _record(self, done, events):
        counted = done & self.normal_start
        if self.count_mask is not None:
            counted = counted & self.count_mask
        c = counted.double()
        s, t = self._stats, self.totals
        s["episodes"] += c.sum()
        for key in t:
            s[key] += (t[key] * c).sum()
        s["deaths"] += (events["death"] * c).sum()
        s["length"] += (self.engine.steps * c).sum()
        s["game_return"] += (self.episode_return * c).sum()
        s["progress"] += ((t["levels_cleared"] + t["boss_damage"] / 10) * c).sum()

    def pop_stats(self):
        """Means over normally started episodes finished since the last call."""
        values = {k: float(v) for k, v in self._stats.items()}
        for v in self._stats.values():
            v.zero_()
        count = values.pop("episodes")
        if count == 0:
            return {"episodes": 0}
        result = {k: v / count for k, v in values.items()}
        result["episodes"] = int(count)
        return result


class GraphedStep:
    """Replay ``VectorGame.step`` as one CUDA graph instead of ~10k kernel launches.

    Every tensor of the game and its engine is kept in a static buffer: after
    each captured step, rebound attributes are copied back into those buffers.
    Outputs are overwritten by the next replay; consume or copy them first.
    Use ``reset()`` instead of ``game.reset()`` once the graph exists.
    """

    def __init__(self, game, warmup=3):
        if game.device.type != "cuda":
            raise ValueError("CUDA graphs need a CUDA game")
        self.game = game
        self.actions = torch.zeros(game.n, dtype=torch.long, device=game.device)
        game.reset()
        self._slots = list(self._state_slots())
        stream = torch.cuda.Stream()
        stream.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(stream):
            for _ in range(warmup):
                self._body()
        torch.cuda.current_stream().wait_stream(stream)
        self.graph = torch.cuda.CUDAGraph()
        self.graph.register_generator_state(game.engine.gen)
        with torch.cuda.graph(self.graph):
            self.outputs = self._body()

    def _state_slots(self):
        for owner in (self.game.engine, self.game):
            for name, value in list(vars(owner).items()):
                if isinstance(value, torch.Tensor):
                    yield owner, name, value
                elif isinstance(value, dict):
                    for key, item in value.items():
                        if isinstance(item, torch.Tensor):
                            yield value, key, item

    def _restore(self):
        for owner, name, static in self._slots:
            current = owner[name] if isinstance(owner, dict) else getattr(owner, name)
            if current is not static:
                static.copy_(current)
                if isinstance(owner, dict):
                    owner[name] = static
                else:
                    setattr(owner, name, static)

    def _body(self):
        outputs = self.game.step(self.actions)
        self._restore()
        return outputs

    def reset(self):
        obs = self.game.reset()
        self._restore()
        return obs

    def __call__(self, actions):
        self.actions.copy_(actions)
        self.graph.replay()
        return self.outputs


__all__ = ["ACTION_COUNT", "STAT_KEYS", "GraphedStep", "VectorGame", "game_reward"]
