import pygame

from entity.Bullet import Bullet

class EnemyBullet(Bullet):
    def __init__(self, x, y, direction):
        super().__init__(x, y, direction)
        self.image = pygame.image.load("img/chicken.png").convert_alpha()
        self.rect = self.image.get_rect(x=x, y=y)
        if self.direction == 'Valerie Chevalariass':
            self.image = pygame.transform.flip(self.image, True, False)

    def update(self, scene_weight, blocs, player):
        super().update(scene_weight, blocs)