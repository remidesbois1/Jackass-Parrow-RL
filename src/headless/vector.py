"""Many environments per process, with reusable output buffers on the hot path."""

from .engine import HeadlessEnv


class BatchEnv:
    __slots__ = ("envs", "rewards", "terminated", "truncated")

    def __init__(self, count, *, seed=0, config=None):
        if type(count) is not int or count < 1:
            raise ValueError("count must be a positive integer")
        self.envs = [HeadlessEnv(seed + i, config) for i in range(count)]
        self.rewards = [0] * count
        self.terminated = [False] * count
        self.truncated = [False] * count

    def advance(self, actions):
        """Advance a batch; return a reused rewards buffer (copy to retain it).

        Validate the entire input before mutation. Done environments must first
        be reset explicitly; this prevents losing a final state during training.
        """
        if len(actions) != len(self.envs):
            raise ValueError("one action is required per environment")
        for env, action in zip(self.envs, actions):
            env.validate_action(action)
            if env.done:
                raise RuntimeError("batch contains a done episode; call reset_done()")
        for i, (env, action) in enumerate(zip(self.envs, actions)):
            self.rewards[i] = env._advance(int(action))
            self.terminated[i] = env.terminated
            self.truncated[i] = env.truncated
        return self.rewards

    def step(self, actions):
        self.advance(actions)
        return (tuple(env.observe() for env in self.envs), tuple(self.rewards),
                tuple(self.terminated), tuple(self.truncated),
                tuple(env.info() for env in self.envs))

    def reset_done(self):
        """Reset completed episodes only, continuing each environment's own RNG."""
        count = 0
        for i, env in enumerate(self.envs):
            if env.done:
                env.reset(observe=False)
                self.rewards[i] = 0
                self.terminated[i] = self.truncated[i] = False
                count += 1
        return count
