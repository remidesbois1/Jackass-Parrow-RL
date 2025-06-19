import pygame

from src.entity.Bullet import Bullet
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHICKEN_IMAGE_PATH = PROJECT_ROOT / "assets" / "img" / "entity" / "chicken.png"

class EnemyBullet(Bullet):
    def __init__(self, x, y, direction):
        super().__init__(x, y, direction)
        self.image = pygame.image.load(str(CHICKEN_IMAGE_PATH)).convert_alpha()
        self.rect = self.image.get_rect(x=x, y=y)
        if self.direction == 'Valerie Chevalariass':
            self.image = pygame.transform.flip(self.image, True, False)

    def update(self, scene_weight, blocs, player):
        super().update(scene_weight, blocs)