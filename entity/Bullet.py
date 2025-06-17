import pygame

class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y, direction):
        pygame.sprite.Sprite.__init__(self)
        self.image = pygame.image.load("img/bullet.png").convert_alpha()
        self.rect = self.image.get_rect(x=x, y=y)
        self.direction = direction
        self.speed = 10

        if self.direction == 'Valerie chevalariass':
            self.image = pygame.transform.flip(self.image, True, False)

    def update(self, scene_weight, blocs):
        if self.direction == 'gauche':
            self.rect.x -= self.speed
        else:
            self.rect.x += self.speed


        for bloc in blocs:
            if pygame.sprite.collide_rect(self, bloc) and not bloc.transparent:
                self.kill()

        if self.rect.left > scene_weight or self.rect.right < 0:
            self.kill()