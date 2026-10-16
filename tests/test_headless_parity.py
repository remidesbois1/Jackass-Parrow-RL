"""Cross-check the separate fast kernel against the graphical implementation."""

from collections import defaultdict
import os
from pathlib import Path
import struct
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from src.block.BlockGroup import BlockGroup
from src.entity.Player import Player
from src.headless import HeadlessEnv
from src.headless.engine import level_geometry
from src.system.GameConfig import WorldType
from src.system.LevelCollection import LevelCollection
from src.system import mechanics as m


class HeadlessParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.scene = pygame.display.set_mode((1280, 800), pygame.HIDDEN)

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_all_level_geometry_and_spawn_points_match_graphical_game(self):
        for level_id in range(11):
            with self.subTest(level_id=level_id):
                group = BlockGroup(self.scene)
                collection = LevelCollection(group)
                if level_id == 0:
                    collection.load_boss(WorldType.MONDE_JUNGLE)
                else:
                    collection.load(level_id)
                blocks, spawn, _ = level_geometry(level_id)
                self.assertEqual(spawn, collection.playerSpawn)
                self.assertEqual([(b.x, b.y, b.w, b.h, b.spawnable, b.transparent) for b in blocks],
                                 [(b.rect.x, b.rect.y, b.rect.w, b.rect.h, b.spawnable, b.transparent)
                                  for b in group])

    def test_player_physics_controls_and_recoil_match_at_60hz(self):
        for level_id in (1, 3, 5, 0):
            with self.subTest(level_id=level_id):
                group = BlockGroup(self.scene)
                collection = LevelCollection(group)
                if level_id:
                    collection.load(level_id)
                else:
                    collection.load_boss(WorldType.MONDE_JUNGLE)
                visual = Player(*collection.playerSpawn)
                headless = HeadlessEnv(1)
                headless.blocks, spawn, _ = level_geometry(level_id)
                headless.player.rect.x, headless.player.rect.y = spawn
                bullets, incoming = pygame.sprite.Group(), pygame.sprite.Group()
                for tick in range(1, 301):
                    phase = tick % 150
                    action = (2 if phase < 75 else 1) | (4 if phase % 45 < 10 else 0)
                    if phase > 120:
                        action = 8
                    if tick in (61, 180):
                        action |= 16
                    keys = defaultdict(bool, {pygame.K_q: bool(action & 1),
                                              pygame.K_d: bool(action & 2),
                                              pygame.K_z: bool(action & 4),
                                              pygame.K_s: bool(action & 8),
                                              pygame.K_SPACE: bool(action & 16)})
                    visual.current_time = tick * 1000 / 60
                    visual.update(self.scene, group, incoming, 1 / 60)
                    visual.handleMove(keys, bullets, 1 / 60)
                    headless.ticks = tick
                    headless._update_player(action)
                    p = headless.player
                    self.assertAlmostEqual(visual.rect.x, p.rect.x, delta=0.03, msg=f"x at tick {tick}")
                    self.assertAlmostEqual(visual.rect.y, p.rect.y, delta=0.03, msg=f"y at tick {tick}")
                    self.assertAlmostEqual(visual.gravity, p.gravity, delta=0.01)
                    self.assertAlmostEqual(visual.knockback, p.knockback, delta=0.01)
                    self.assertEqual(visual.onGround, p.on_ground)
                    self.assertEqual(visual.speed, p.speed)
                self.assertEqual(len(bullets), len(headless.bullets))

    def test_collision_size_constants_match_png_assets(self):
        root = Path(__file__).resolve().parents[1] / "assets" / "img"
        for name, expected in (("player/player.png", m.PLAYER_SIZE),
                               ("entity/bullet.png", m.PLAYER_BULLET_SIZE),
                               ("entity/chicken.png", m.ENEMY_BULLET_SIZE),
                               ("entity/chevalier.png", m.KNIGHT_SIZE),
                               ("entity/chicken_bomb.png", m.CHICKEN_SIZE)):
            with self.subTest(asset=name):
                size = struct.unpack(">II", (root / name).read_bytes()[16:24])
                self.assertEqual(size, expected)


if __name__ == "__main__":
    unittest.main()
