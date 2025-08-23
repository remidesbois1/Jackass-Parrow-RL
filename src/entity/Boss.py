import random
import time

import pygame

from src.block.Block import Block
from src.block.BlockGroup import BlockGroup
from src.entity.EnemyBullet import EnemyBullet
from pathlib import Path

from src.entity.Player import Player
from src.gui.MenuContext import MenuContext

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOM_IMAGE_PATH = PROJECT_ROOT / "assets" / "img" / "entity" / "tom.png"
TOM_DAMAGE_IMAGE_PATH = PROJECT_ROOT / "assets" / "img" / "entity" / "tomDamage.png"

BOSS_THEME_PATH = PROJECT_ROOT / "assets" / "sounds" / "bossTheme.mp3"
MAIN_THEME_PATH = PROJECT_ROOT / "assets" / "sounds" / "mainTheme.mp3"

class Boss(pygame.sprite.Sprite):
    X = 900
    Y = 110
    SIZE =(144,286)
    START_TIME = pygame.time.get_ticks()
    

    def __init__(self,game_surface,enemy_bullets):
        pygame.sprite.Sprite.__init__(self)

        self.start_timer = time.time()

        self.game_surface = game_surface

        # Surface
        self.TEXTURE_TOM = pygame.transform.scale(pygame.image.load(str(TOM_IMAGE_PATH)),(self.SIZE[0]*2,self.SIZE[1]*2)).convert_alpha()
        self.TEXTURE_TOM_DAMAGE = pygame.transform.scale(pygame.image.load(str(TOM_DAMAGE_IMAGE_PATH)),(self.SIZE[0]*2,self.SIZE[1]*2)).convert_alpha()
        self.image = pygame.transform.scale(pygame.image.load(str(TOM_IMAGE_PATH)),(self.SIZE[0]*2,self.SIZE[1]*2)).convert_alpha()
        self.rect = self.image.get_rect(x=self.X, y=self.Y)

        self.health = 10

        self.lastEvasiveTime = 0
        self.deathTime = 0
        self.outroFinished = False
        self.elapsed_time = None


        self.index_hole = 0
        self.attackSpeed = 1000
        self.bullets = enemy_bullets
        self.timeLastBullet = 0

        self.bouclier = BlockGroup(self.game_surface)
        pygame.mixer.music.load(str(BOSS_THEME_PATH))
        pygame.mixer.music.play(-1)

    def generateBouclier(self):
        self.bouclier.clear(self.game_surface,self.game_surface)
        self.bouclier.empty()
        choice = [0,1,2]
        # évite de laisser 2 fois le même trou de bouclier d'affilée
        choice.remove(self.index_hole)
        self.index_hole = random.choice(choice)

        for i in range(3):
            if i != self.index_hole:
                self.bouclier.add(Block(15,12-(i*4),1,3))
        self.bouclier.draw(self.game_surface)

    def update(self, player_bullets, player : Player, menu_context: MenuContext):

        self.game_surface.blit(self.image, self.rect)

        self.bouclier.update()
        

        #la fonction update est appelée uniquement si l'active_menu est INGAME_MENU
        
        # si le boss est mort
        if self.health <= 0:
            # si deathTime n'a jamais été initialisé
            if self.deathTime == 0:
                self.bullets.empty()
                self.deathTime = time.time()
            menu_context.set_active_modal(MenuContext.OUTRO_BOSS_MENU)
            

            #self.attackSpeed = 999999 # assez lent pour ne plus tirer avant la fin
            self.image.fill((0,0,0,0))
            self.image.blit(self.TEXTURE_TOM_DAMAGE, (0, 0))

            #fin de l'outro
            if time.time() - self.deathTime > 5:
                self.outroFinished = True
                pygame.mixer.music.load(str(MAIN_THEME_PATH))
                pygame.mixer.music.play(-1)
        else:
            # gestion des tirs
            if time.time() - self.timeLastBullet > self.attackSpeed / 1000.0:
                self.timeLastBullet = time.time()
                ybullet = player.rect.y
                self.bullets.add(EnemyBullet(self.rect.midleft[0] - 100, ybullet, 'gauche'))

            # si pas evasif
            if  time.time() - self.lastEvasiveTime > 2:
                for bullet in player_bullets:
                    if pygame.sprite.collide_rect(self, bullet):
                        self.generateBouclier()
                        self.health -= 1
                        self.lastEvasiveTime = time.time()
                        bullet.kill()
                        # colère
                        if self.health <= 3:
                            self.attackSpeed = 700
                self.image.fill((0,0,0,0))
                self.image.blit(self.TEXTURE_TOM, (0, 0))
                self.image.set_alpha(255)

            #si evasif
            else:
                self.image.fill((0,0,0,0))
                self.image.blit(self.TEXTURE_TOM_DAMAGE, (0, 0))
                if int(time.time() * 1000) % 200 <= 100:
                    self.image.set_alpha(200)
                else:
                    self.image.set_alpha(150)
                
