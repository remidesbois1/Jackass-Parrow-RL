import pygame
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

BULLET_IMAGE_PATH = PROJECT_ROOT / "assets" / "img" / "entity" / "bullet.png"


class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y, direction):
        pygame.sprite.Sprite.__init__(self)
        self.image = pygame.image.load(str(BULLET_IMAGE_PATH)).convert_alpha()
        self.rect = self.image.get_rect(x=x, y=y)
        self.direction = direction
        self.speed = 600

        if self.direction == 'Valerie chevalariass':
            self.image = pygame.transform.flip(self.image, True, False)

    def update(self, scene_width, blocs, delta_time: float):
        if self.direction == 'gauche':
            self.rect.x -= self.speed * delta_time
        else:
            self.rect.x += self.speed * delta_time


        for bloc in blocs:
            if pygame.sprite.collide_rect(self, bloc) and not bloc.transparent:
                self.kill()

        if self.rect.left > scene_width or self.rect.right < 0:
            self.kill()