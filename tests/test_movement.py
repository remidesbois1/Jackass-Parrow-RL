import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from src.block.Block import Block
from src.entity.Bullet import Bullet
from src.entity.Enemy import Enemy
from src.entity.EnemyBullet import EnemyBullet
from src.entity.EnemyKamikaze import EnemyKamikaze
from src.entity.Player import Player


def frame_times(fps, duration=1.0):
    count = int(fps * duration)
    steps = [1 / fps] * count
    remainder = duration - count / fps
    if remainder > 1e-10:
        steps.append(remainder)
    return steps


class MovementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1280, 800), pygame.HIDDEN)

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.blocks = pygame.sprite.Group()
        self.bullets = pygame.sprite.Group()

    def test_player_speed_at_different_and_irregular_frame_rates(self):
        schedules = [frame_times(fps) for fps in (30, 60, 144)]
        schedules.append([0.015, 0.016, 0.017, 0.018] * 15)
        for steps in schedules:
            with self.subTest(frame_count=len(steps)):
                player = Player(x=100, y=100)
                player.speed = player.BASE_SPEED
                for dt in steps:
                    player.update(None, self.blocks, self.bullets, dt)
                self.assertAlmostEqual(player.rect.x - 100, 400 * sum(steps), delta=0.01)

    def test_both_projectile_types_keep_their_speed_in_both_directions(self):
        for bullet_type in (Bullet, EnemyBullet):
            for direction, sign in (("gauche", -1), ("droite", 1)):
                for fps in (30, 60, 144):
                    with self.subTest(kind=bullet_type.__name__, direction=direction, fps=fps):
                        bullet = bullet_type(3000, 100, direction)
                        for dt in frame_times(fps):
                            bullet.update(10000, self.blocks, dt)
                        self.assertAlmostEqual(bullet.rect.x - 3000, sign * 600, delta=0.05)

    def test_gravity_and_knockback_use_elapsed_time(self):
        for fps in (30, 60, 144):
            with self.subTest(fps=fps):
                player = Player(x=100, y=0)
                player.knockback = player.KNOCKBACK_FORCE
                for dt in frame_times(fps, duration=0.1):
                    player.update(None, self.blocks, self.bullets, dt)
                self.assertAlmostEqual(player.gravity, 360, places=5)
                self.assertAlmostEqual(player.knockback, 1500 * 0.85 ** 6, places=5)

    def test_kamikaze_and_dead_knight_speed_at_different_frame_rates(self):
        platform = Block(0, 10, 100, 1)
        player = Player(x=3000, y=0)
        for fps in (30, 60, 144):
            with self.subTest(fps=fps):
                chicken = EnemyKamikaze(100, 100, platform)
                knight = Enemy(100, 500)
                knight.alive = False
                for dt in frame_times(fps):
                    chicken.update(player, self.bullets, self.bullets, dt)
                    knight.update(player, self.bullets, self.bullets, dt)
                self.assertAlmostEqual(chicken.rect.x, 400, delta=0.01)
                self.assertAlmostEqual(knight.rect.y, 200, delta=0.01)

    def test_projectiles_still_collide_with_integer_block_rectangles(self):
        self.blocks.add(Block(4, 3, 1, 1))
        for bullet_type in (Bullet, EnemyBullet):
            with self.subTest(kind=bullet_type.__name__):
                bullet = bullet_type(230, 130, "droite")
                group = pygame.sprite.Group(bullet)
                bullet.update(1280, self.blocks, 1 / 144)
                self.assertEqual(len(group), 0)

    def test_player_lands_and_stays_on_the_floor(self):
        floor = Block(-1, 16, 26, 1)
        self.blocks.add(floor)
        for fps in (30, 60, 144):
            with self.subTest(fps=fps):
                player = Player(x=100, y=500)
                for dt in frame_times(fps, duration=2):
                    player.update(None, self.blocks, self.bullets, dt)
                self.assertTrue(player.onGround)
                self.assertAlmostEqual(player.rect.bottom, floor.rect.top + 1, delta=0.01)


if __name__ == "__main__":
    unittest.main()
