import pygame
from pygame import Surface
from entity.Enemy import  Enemy
from random import randint


class Block(pygame.sprite.Sprite):
    def __init__(self, x, y, width, height, spawnable=False, transparent=False):
        super().__init__()
        self.spawnable = spawnable
        self.transparent = transparent
        self.image = pygame.Surface([width * 50, height * 50], pygame.SRCALPHA)

        if not self.transparent:
            if (y == 16):
                texture = pygame.image.load("img/dirt.png").convert_alpha()
            else:
                texture = pygame.image.load("img/block.png").convert_alpha()

            for textureY in range(height):
                for textureX in range(width):
                    self.image.blit(texture, ((textureX * 50), (textureY * 50)))
        else:
             self.image.fill((200,0,0,0))

        self.rect = self.image.get_rect(x=(x * 50) + 40, y=y * 50 - 25)
        self.size = width, height



