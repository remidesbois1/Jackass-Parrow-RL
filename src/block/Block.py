import pygame
from pygame import Surface
from src.entity.Enemy import  Enemy
from random import randint
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BLOCK_IMAGE_PATH = PROJECT_ROOT/ "assets" / "img" / "block" / "block.png"
DIRT_IMAGE_PATH = PROJECT_ROOT / "assets" / "img" / "block" / "dirt.png"

class Block(pygame.sprite.Sprite):
    def __init__(self, x:int, y:int, width:int, height:int, spawnable=False, transparent=False):
        super().__init__()
        self.spawnable = spawnable
        self.transparent = transparent
        self.image = pygame.Surface([width * 50, height * 50], pygame.SRCALPHA)

        if not self.transparent:
            if (y == 16):
                texture = pygame.image.load(str(DIRT_IMAGE_PATH)).convert_alpha()
            else:
                texture = pygame.image.load(str(BLOCK_IMAGE_PATH)).convert_alpha()

            for textureY in range(height):
                for textureX in range(width):
                    self.image.blit(texture, ((textureX * 50), (textureY * 50)))
        else:
             self.image.fill((200,0,0,0))

        self.rect = self.image.get_rect(x=(x * 50) + 40, y=y * 50 - 25)
        self.size = width, height



