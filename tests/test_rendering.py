import os
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

GYM_AVAILABLE = importlib.util.find_spec("gymnasium") is not None
if GYM_AVAILABLE:
    import numpy as np
    import pygame

    from src.headless import Config, HeadlessEnv
    from src.rl import JackassParrowEnv
    from src.rl.rendering import HeadlessRenderer


@unittest.skipUnless(GYM_AVAILABLE, "install the rl extra for rendering tests")
class RenderingTests(unittest.TestCase):
    def test_rgb_rendering_without_display_or_audio_and_without_state_changes(self):
        pygame.display.quit()
        pygame.mixer.quit()
        env = JackassParrowEnv(render_mode="rgb_array")
        try:
            obs, info = env.reset(seed=42)
            before = env.engine.observe(), env.engine.info(), env.engine.rng.getstate()
            pixels = env.render()
            self.assertEqual(pixels.shape, (800, 1280, 3))
            self.assertEqual(pixels.dtype, np.uint8)
            self.assertTrue(pixels.flags.c_contiguous)
            self.assertGreater(int(pixels.std()), 10)
            np.testing.assert_array_equal(pixels, env.render())
            self.assertEqual(before, (env.engine.observe(), env.engine.info(), env.engine.rng.getstate()))
            np.testing.assert_array_equal(obs, env._result()[0])
            self.assertFalse(pygame.display.get_init())
            self.assertIsNone(pygame.mixer.get_init())
            pixels.fill(0)
            self.assertGreater(int(env.render().sum()), 0)
        finally:
            env.close()
            env.close()

    def test_assets_are_loaded_once_and_maps_are_cached(self):
        env = HeadlessEnv(1)
        with patch("pygame.image.load", wraps=pygame.image.load) as load:
            renderer = HeadlessRenderer()
            try:
                count = load.call_count
                renderer.draw(env)
                cached = renderer._map
                renderer.draw(env)
                self.assertIs(renderer._map, cached)
                env._load_level(boss=True)
                renderer.draw(env)
                self.assertIsNot(renderer._map, cached)
                self.assertEqual(count, load.call_count)
                with patch("pygame.image.load", side_effect=AssertionError("unexpected asset IO")):
                    env.boss.last_hit = env.ticks
                    env.boss.shields = (env.blocks[0],)
                    renderer.draw(env)
            finally:
                renderer.close()

    def test_render_callback_matches_fast_path_including_termination(self):
        for boss_mode in (False, True):
            config = Config(frame_skip=4, boss_mode=boss_mode)
            fast, rendered = HeadlessEnv(7, config), HeadlessEnv(7, config)
            visited = []
            for i in range(150):
                action = i * 11 % 32
                before = rendered.ticks
                self.assertEqual(fast.advance(action),
                                 rendered.advance(action, on_tick=lambda e: visited.append(e.ticks)))
                self.assertEqual(fast.observe(), rendered.observe())
                self.assertEqual(fast.info(), rendered.info())
                self.assertEqual(fast.rng.getstate(), rendered.rng.getstate())
                self.assertEqual(visited[-(rendered.ticks - before):], list(range(before + 1, rendered.ticks + 1)))
                if fast.done:
                    break

    def test_human_mode_draws_each_physics_tick_and_closes(self):
        plain = JackassParrowEnv(frame_skip=4)
        env = JackassParrowEnv(render_mode="human", frame_skip=4)
        try:
            a, _ = plain.reset(seed=7)
            b, _ = env.reset(seed=7)
            np.testing.assert_array_equal(a, b)
            frames = []

            def present(engine):
                frames.append(engine.ticks)
                env.renderer.draw(engine)

            env.on_render_tick = present
            action = [2, 1, 0, 1]
            a, *expected = plain.step(action)
            b, *actual = env.step(action)
            np.testing.assert_array_equal(a, b)
            self.assertEqual(expected, actual)
            self.assertEqual(frames, [1, 2, 3, 4])
            self.assertEqual(env.renderer.action, tuple(action))
        finally:
            plain.close()
            env.close()

    def test_nonrendered_environment_does_not_load_pygame(self):
        # Fresh interpreter proves imports do not leak into training/headless.
        import subprocess
        import sys

        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, "-c", """
import sys
from src.rl import JackassParrowEnv
e = JackassParrowEnv()
e.reset(seed=0)
e.step([0, 0, 0, 1])
assert 'pygame' not in sys.modules
assert 'src.rl.rendering' not in sys.modules
assert e.render() is None
e.close()
"""], cwd=root, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
