from random import randint

import pygame

from src.entity.EnemyBullet import EnemyBullet
from src.system.Sound import Sound
from src.system import mechanics
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHEVALIER_IMAGE_PATH = PROJECT_ROOT / "assets" / "img" / "entity" / "chevalier.png"
CHEVALIER_MORT_IMAGE_PATH = PROJECT_ROOT / "assets" / "img" /"entity" / "chevalierMort.png"
CHEVALIER_ANGWY_IMAGE_PATH = PROJECT_ROOT / "assets" / "img" / "entity" / "chevalier_angwy.png"

class Enemy(pygame.sprite.Sprite):
    SIZE = mechanics.KNIGHT_SIZE
    def __init__(self, x, y):
        pygame.sprite.Sprite.__init__(self)
        self.sounds = Sound()
        self.direction = 'gauche'
        self.image = pygame.image.load(str(CHEVALIER_IMAGE_PATH)).convert_alpha()
        self.rect = self.image.get_frect(x=x, y=y)
        self.alive = True
        self.last_shot_time = 0
        self.angryCoef = 1
        self.score = 100

    def update(self, player, bullet_group, player_bullets, delta_time):
        min_speed, max_speed = int(1600*self.angryCoef),int(2200*self.angryCoef)
        current_time = pygame.time.get_ticks()
        if current_time - self.last_shot_time > randint(min_speed,max_speed) and self.alive and player.health > 0:
            self.shoot(bullet_group, player)
            self.last_shot_time = current_time

        for bullet in player_bullets:
            if pygame.sprite.collide_rect(self, bullet):
                self.killed()
                bullet.kill()
                player.addScore(self.score)
        if not self.alive:
            self.rect.y -= 300 * delta_time



    def shoot(self, bullet_group, player):
        direction = 'gauche' if self.rect.centerx > player.rect.centerx else 'Valerie Chevalariass'
        if self.direction != direction:
            self.image = pygame.transform.flip(self.image, True, False)
        self.direction = direction

        pygame.mixer.Sound(self.sounds.son_enemy_fire).play()
        bullet = EnemyBullet(self.rect.centerx, self.rect.centery, direction)
        bullet_group.add(bullet)

    def killed(self):
        pygame.mixer.Sound(self.sounds.son_knight_hurt).play()
        self.image.fill((0, 0, 255))
        self.alive = False
        self.image = pygame.image.load(str(CHEVALIER_MORT_IMAGE_PATH)).convert_alpha()
        self.image.set_alpha(150)

class EnemyAngwy(Enemy):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.score = 150
        self.angryCoef = 0.7
        self.image = pygame.image.load(str(CHEVALIER_ANGWY_IMAGE_PATH)).convert_alpha()
        self.rect = self.image.get_frect(x=x, y=y)
