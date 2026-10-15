from random import randint
import pygame
from src.entity.Enemy import Enemy
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHICKEN_BOMB_IMAGE_PATH = PROJECT_ROOT / "assets" / "img" / "entity" / "chicken_bomb.png"
CHICKEN_BOMB_WALK_IMAGE_PATH = PROJECT_ROOT / "assets" / "img" / "entity" / "chicken_bomb_walk.png"

CHICKEN_EXPLOSION_FRAMES = [
    f"{str(PROJECT_ROOT)}/assets/img/entity/explosion_{i}.png" for i in range(1, 5)
]

class EnemyKamikaze(Enemy):
    def __init__(self, x, y, platform):
        super().__init__(x, y)
        self.walk_frames = [
            pygame.image.load(str(CHICKEN_BOMB_IMAGE_PATH)).convert_alpha(),
            pygame.image.load(str(CHICKEN_BOMB_WALK_IMAGE_PATH)).convert_alpha()
        ]
        self.walk_index = 0
        self.image = self.walk_frames[self.walk_index]
        self.rect = self.image.get_frect(x=x, y=y)
        self.platform = platform
        self.speed = 300  # Pixels par seconde (5 pixels par image à 60 FPS).
        self.direction = 1
        self.animation_timer = 0
        self.animation_delay = 100

        # explosion
        self.explosion_frames = [
            pygame.image.load(CHICKEN_EXPLOSION_FRAMES[i]).convert_alpha() for i in range(4)
        ]
        self.explosion_index = 0
        self.explosion_timer = 0
        self.explosion_delay = 50
        self.is_exploding = False

    def update(self, player, bullet_group, player_bullets, delta_time):
        current_time = pygame.time.get_ticks()

        if self.alive:
            self.rect.x += self.speed * self.direction * delta_time

            if self.rect.right > self.platform.rect.right - 15:
                self.direction = -1
            elif self.rect.left < self.platform.rect.left + 15:
                self.direction = 1
            if pygame.sprite.collide_rect(self, player):
                self.touch(player)

            if current_time - self.animation_timer > self.animation_delay:
                self.animation_timer = current_time
                self.walk_index = (self.walk_index + 1) % len(self.walk_frames)
                self.image = self.walk_frames[self.walk_index]

                if self.direction == 1:
                    self.image = pygame.transform.flip(self.image, True, False)
            for bullet in player_bullets:
                if pygame.sprite.collide_rect(self, bullet):
                    self.killed()
                    bullet.kill()
                    player.addScore(100)  # ajoute 100 au score

        if self.is_exploding:
            current_time = pygame.time.get_ticks()
            if current_time - self.explosion_timer > self.explosion_delay:
                self.explosion_timer = current_time
                self.explosion_index += 1
                if self.explosion_index < len(self.explosion_frames):
                    self.image = self.explosion_frames[self.explosion_index]
                else:
                    self.is_exploding = False
                    self.kill()

    def shoot(self, bullet_group, player):
        pass

    def killed(self):
        self.alive = False
        self.is_exploding = True
        self.explosion_index = 0
        self.explosion_timer = pygame.time.get_ticks()
        self.image = self.explosion_frames[self.explosion_index]

    def touch(self, player):
        player.touched()
        self.killed()

