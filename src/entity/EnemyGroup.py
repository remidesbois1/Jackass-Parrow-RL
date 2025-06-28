import pygame
from src.entity.Enemy import  Enemy
from random import randint,sample

class EnemyGroup(pygame.sprite.Group):
    def __init__(self,scene):
        super().__init__()
        self.scene = scene

    def nbAlive(self):
        count = 0
        for enemy in self.sprites():
            if enemy.alive:
                count += 1
        return count
