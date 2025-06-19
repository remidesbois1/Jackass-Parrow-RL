import random
import time

import pygame

from src.entity.Block import Block
from src.entity.BlockGroup import BlockGroup
from src.entity.EnemyBullet import EnemyBullet
from pathlib import Path

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
    def __init__(self,scene,allBullets):
        pygame.sprite.Sprite.__init__(self)
        self.start_timer = time.time()
        self.timeLastBullet = time.time()
        self.victory_shown = False
        self.intro_finished = False
        self.scene = scene
        self.imageBase =  pygame.transform.scale(pygame.image.load(str(TOM_IMAGE_PATH)).convert_alpha(),(self.SIZE[0]*2,self.SIZE[1]*2))
        self.image = self.imageBase
        self.imageDamage = pygame.transform.scale( pygame.image.load(str(TOM_DAMAGE_IMAGE_PATH)).convert_alpha(),(self.SIZE[0]*2,self.SIZE[1]*2))
        self.rect = self.image.get_rect(x=self.X, y=self.Y)
        self.health = 10
        self.evasive = False
        self.lastEvasiveTime =0
        self.deathTime = 0
        self.die = False

        self.lastIndexHole = 0
        self.attackSpeed = 1000
        self.bullets = allBullets
        self.timeLastBullet = 0

        self.bouclier = BlockGroup(self.scene,None)
        pygame.mixer.music.load(str(BOSS_THEME_PATH))
        pygame.mixer.music.play(-1)

    def generateBouclier(self):
        self.bouclier.clear(self.scene,self.scene)
        self.bouclier.empty()
        choice = [0,1,2]
        choice.remove(self.lastIndexHole)
        indexHole = random.choice(choice)
        self.lastIndexHole = indexHole
        for i in range(3):
            if i != indexHole:
                self.bouclier.add(Block(15,12-(i*4),1,3))
        self.bouclier.draw(self.scene)

    def update(self, player_bullets, player, menu, game):
        self.bouclier.update()

        elapsed_time = time.time() - self.start_timer

        self.scene.blit(self.image, self.rect)

        if elapsed_time <= 5:
            menu.show_boss_intro()
            return
        else:
            game.activeMenu = 'game'

        if elapsed_time > 5 and not hasattr(self, "intro_finished"):
            self.intro_finished = True

        if elapsed_time > 5:
            if self.health <= 0:
                if game.fight_boss:
                    if self.deathTime == 0:
                        self.bullets.empty()
                        self.deathTime = time.time()
                    menu.show_boss_win()
                    if time.time() - self.deathTime > 5:
                        game.fight_boss = False
                        game.Blocs.empty()
                        game.loadTableau()

                if self.deathTime == 0:
                    self.deathTime = time.time()
                menu.show_boss_win()
                self.attackSpeed = 999999
                self.image = self.imageDamage

                if time.time() - self.deathTime > 5:
                    self.die = True
                    pygame.mixer.music.load(str(MAIN_THEME_PATH))
                    pygame.mixer.music.play(-1)
                    game.boss_Killed = True
                    if not hasattr(self, "victory_shown"):
                        self.victory_shown = True

            if time.time() - self.timeLastBullet > self.attackSpeed / 1000.0:
                self.timeLastBullet = time.time()
                ybullet = player.rect.y
                self.bullets.add(EnemyBullet(self.rect.midleft[0] - 100, ybullet, 'gauche'))

            elif not self.evasive:
                for bullet in player_bullets:
                    if pygame.sprite.collide_rect(self, bullet):
                        self.generateBouclier()
                        self.health -= 1
                        self.evasive = True
                        self.image = self.imageDamage
                        self.lastEvasiveTime = time.time()
                        bullet.kill()
                        # colère
                        if self.health <= 3:
                            self.attackSpeed = 700

            else:
                if int(time.time() * 1000) % 200 <= 100:
                    self.image.set_alpha(200)
                else:
                    self.image.set_alpha(150)
                if time.time() - self.lastEvasiveTime > 2:
                    self.evasive = False
                    self.image = self.imageBase
                    self.image.set_alpha(255)
