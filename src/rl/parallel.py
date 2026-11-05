"""Batched subprocess vector environment for SB3 on spawn-based platforms."""
import multiprocessing as mp
import traceback

import numpy as np
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, VecEnv


class FastDummyVecEnv(DummyVecEnv):
    """Avoid recursively copying freshly-created info dicts on every step."""

    def step_wait(self):
        infos = []
        for i, env in enumerate(self.envs):
            obs, self.buf_rews[i], terminated, truncated, info = env.step(self.actions[i])
            self.buf_dones[i] = terminated or truncated
            info["TimeLimit.truncated"] = truncated and not terminated
            if self.buf_dones[i]:
                info["terminal_observation"] = obs
                obs, self.reset_infos[i] = env.reset()
            self._save_obs(i, obs)
            infos.append(info)
        return (self.buf_obs[None].copy(), self.buf_rews.copy(),
                self.buf_dones.copy(), infos)


def _worker(pipe, count, offset, env_kwargs, reward_mode, weights, monitor_dir, metrics):
    env = None
    try:
        from examples.train_ppo import make_training_env
        from pathlib import Path

        def make_one(index):
            def factory():
                instance = make_training_env(env_kwargs, reward_mode, weights)
                return Monitor(instance, filename=str(Path(monitor_dir) / str(index)),
                               info_keywords=metrics)
            return factory

        env = FastDummyVecEnv([make_one(offset + i) for i in range(count)])
        pipe.send((True, (env.observation_space, env.action_space)))
        while True:
            command, data = pipe.recv()
            if command == "step":
                result = env.step(data)
                pipe.send((True, (result, env.reset_infos)))
            elif command == "reset":
                env._seeds, env._options = data
                pipe.send((True, (env.reset(), env.reset_infos)))
            elif command == "get_attr":
                pipe.send((True, env.get_attr(*data)))
            elif command == "set_attr":
                env.set_attr(*data)
                pipe.send((True, None))
            elif command == "env_method":
                name, args, kwargs, indices = data
                pipe.send((True, env.env_method(name, *args, indices=indices, **kwargs)))
            elif command == "env_is_wrapped":
                pipe.send((True, env.env_is_wrapped(*data)))
            elif command == "close":
                pipe.send((True, None))
                break
            else:
                raise ValueError(f"unknown command {command}")
    except EOFError:
        pass
    except BaseException:
        try:
            pipe.send((False, traceback.format_exc()))
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        if env is not None:
            env.close()
        pipe.close()


class GroupedSubprocVecEnv(VecEnv):
    """Parallel groups of environments; one IPC exchange per group, not per env."""

    def __init__(self, num_envs, workers, env_kwargs, reward_mode, weights, monitor_dir, metrics):
        if not 1 <= workers <= num_envs:
            raise ValueError("workers must be between 1 and num_envs")
        self.remotes, self.processes, self.slices = [], [], []
        self.waiting = False
        self.closed = False
        ctx = mp.get_context("spawn")
        offset = 0
        try:
            for i in range(workers):
                count = num_envs // workers + (i < num_envs % workers)
                parent, child = ctx.Pipe()
                process = ctx.Process(target=_worker, args=(child, count, offset, env_kwargs,
                    reward_mode, weights, str(monitor_dir), metrics), daemon=True)
                process.start()
                child.close()
                self.remotes.append(parent)
                self.processes.append(process)
                self.slices.append(slice(offset, offset + count))
                offset += count
            spaces = [self._recv(remote) for remote in self.remotes]
            super().__init__(num_envs, *spaces[0])
        except BaseException:
            for process in self.processes:
                if process.is_alive():
                    process.terminate()
                process.join()
            for remote in self.remotes:
                remote.close()
            raise

    @staticmethod
    def _recv(remote):
        ok, result = remote.recv()
        if not ok:
            raise RuntimeError(f"environment worker failed:\n{result}")
        return result

    def reset(self):
        for remote, group in zip(self.remotes, self.slices):
            remote.send(("reset", (self._seeds[group], self._options[group])))
        responses = [self._recv(remote) for remote in self.remotes]
        self.reset_infos = sum((info for _, info in responses), [])
        self._reset_seeds()
        self._reset_options()
        return np.concatenate([obs for obs, _ in responses])

    def step_async(self, actions):
        for remote, group in zip(self.remotes, self.slices):
            remote.send(("step", actions[group]))
        self.waiting = True

    def step_wait(self):
        responses = [self._recv(remote) for remote in self.remotes]
        self.waiting = False
        results = [result for result, _ in responses]
        self.reset_infos = sum((info for _, info in responses), [])
        obs, rewards, dones, infos = zip(*results)
        return np.concatenate(obs), np.concatenate(rewards), np.concatenate(dones), sum(infos, [])

    def _dispatch(self, command, data, indices):
        wanted = list(self._get_indices(indices))
        result = {}
        for remote, group in zip(self.remotes, self.slices):
            selected = [i for i in wanted if group.start <= i < group.stop]
            if selected:
                local = [i - group.start for i in selected]
                remote.send((command, data(local)))
                values = self._recv(remote)
                if values is not None:
                    result.update(zip(selected, values))
        return [result[i] for i in wanted] if result else []

    def get_attr(self, attr_name, indices=None):
        return self._dispatch("get_attr", lambda idx: (attr_name, idx), indices)

    def set_attr(self, attr_name, value, indices=None):
        self._dispatch("set_attr", lambda idx: (attr_name, value, idx), indices)

    def env_method(self, method_name, *method_args, indices=None, **method_kwargs):
        return self._dispatch("env_method", lambda idx: (method_name, method_args, method_kwargs, idx), indices)

    def env_is_wrapped(self, wrapper_class, indices=None):
        return self._dispatch("env_is_wrapped", lambda idx: (wrapper_class, idx), indices)

    def close(self):
        if self.closed:
            return
        if self.waiting:
            for remote in self.remotes:
                self._recv(remote)
            self.waiting = False
        for remote in self.remotes:
            remote.send(("close", None))
        for remote in self.remotes:
            self._recv(remote)
            remote.close()
        for process in self.processes:
            process.join()
        self.closed = True
