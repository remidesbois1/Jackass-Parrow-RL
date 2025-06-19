import pygame
from src.entity.Enemy import Enemy, EnemyAngwy
from random import randint,sample

from src.entity.EnemyKamikaze import EnemyKamikaze


class BlockGroup(pygame.sprite.Group):
    def __init__(self,scene,enemies):
        super().__init__()
        self.enemyGroup = enemies
        self.scene = scene

    def get_spawnable(self)->list:
        spawables = []
        for bloc in self.sprites():
            if bloc.spawnable:
                spawables.append(bloc)
        return spawables


    def spawn(self,nb):
        max = len(self.get_spawnable())
        if nb> 6:
            angry = True
        else:
            angry = False
        if nb > max:
            nb = max
        for bloc in sample(self.get_spawnable(),nb):
            x = randint(bloc.rect.x,(bloc.rect.x+bloc.rect.width)- (Enemy.SIZE[0]//2))
            y = bloc.rect.y - 90

            if randint(0, 3) == 0:
                y = bloc.rect.y - 70
                new_enemy = EnemyKamikaze(x, y, bloc)
            else:
                if angry:
                    new_enemy = EnemyAngwy(x,y)
                else:
                    new_enemy = Enemy(x, y)
            self.enemyGroup.add(new_enemy)
        self.enemyGroup.draw(self.scene)

    def update(self):
        self.draw(self.scene)