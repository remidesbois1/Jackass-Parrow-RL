import pygame
import json
from pathlib import Path
from random import randint
from src.block.Block import Block
from src.block.BlockGroup import BlockGroup
from src.entity.Boss import Boss
from src.entity.Enemy import Enemy
from src.gui.Menu import Menu
from src.entity.Player import Player
from src.system.LevelCollection import LevelCollection
from src.entity.EnemyGroup import EnemyGroup
from src.system.Sound import Sound
from pygame.surface import Surface
from pygame.key import ScancodeWrapper

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKGROUND_IMAGE_PATH = PROJECT_ROOT / "assets" / "img" / "background" / "fondGameJam.png"
BACKGROUND_RED_IMAGE_PATH = PROJECT_ROOT / "assets" / "img" / "background" / "fondGameJamRed.png"

class GameManager:
    def __init__(self,game_surface:Surface):
        # game system
        self.levelCollection = None
        self.game_surface = game_surface
    

        # game state
        self.waveNumber = None
        self.idNiveau = 0
        self.game_over = False
        self.game_over_time = 0
        self.fight_boss = False
        self.boss_Killed = None
        self.boss_mode = False #Séparer Game Manager et BossModeManager
        self.score_saved = False
        
        # entities 
        self.player = None
        self.bullets = None
        self.enemies = None
        self.enemy_bullets = None
        self.Blocs = None
        self.boss = None
        self.tom = None
        
        
    def onLoop(self,delta_time:float, keys: ScancodeWrapper):
        WIDTH = 1280
        self.Blocs.update()
        self.player.handleMove(keys, self.bullets,delta_time)
        self.enemies.update(self.player, self.enemy_bullets, self.bullets)
        self.enemy_bullets.update(WIDTH, self.Blocs, delta_time)
        
        if self.fight_boss:
                self.bullets.update(WIDTH, self.Blocs.sprites() + self.boss.bouclier.sprites(),delta_time)
        else:
            self.bullets.update(WIDTH, self.Blocs, delta_time)
        
        if self.player.health <= 0 and not self.game_over:
                self.game_over = True
                self.game_over_time = pygame.time.get_ticks()

        if self.boss_mode and self.boss.die:
            self.restart()

        if self.waveNumber == 8 and self.boss_Killed:
            self.waveNumber += 1
            self.loadTableau()

        if self.enemies.nbAlive() == 0 and not self.boss_mode and not self.idNiveau == 1000:
            self.enemies.empty()
            self.Blocs.empty()
            if self.waveNumber == 8:
                self.loadTableau(1000)
                self.player.speed = 0
                self.player.knockback = 0
                self.boss = Boss(self.game_surface, self.enemy_bullets)
                self.fight_boss = True
            else:
                self.loadTableau()
    
    def loadTableau(self, id=None):
        self.enemy_bullets.empty()
        if id == 1000:
            self.idNiveau = 1000
        else:
            if self.waveNumber > 8:
                self.idNiveau = randint(5, 10)
            else:
                self.idNiveau = randint(1, 5)
        self.levelCollection.load(self.idNiveau)
        self.player.rect.x, self.player.rect.y = self.levelCollection.playerSpawn
        self.waveNumber += 1
        self.Blocs.spawn(self.waveNumber)

    def startGame(self):
        self.waveNumber = 0
        self.boss_mode = False
        self.fight_boss = False
        self.boss_Killed = False
        self.game_over = False
        self.game_over_time = 0
        self.redBg = False
        
        if self.boss is not None:
            self.boss.kill()
        
        self.bullets = pygame.sprite.Group()
        self.enemies = EnemyGroup(self.game_surface)
        self.enemy_bullets = pygame.sprite.Group()

        self.player = Player()
        self.background = pygame.image.load(str(BACKGROUND_IMAGE_PATH)).convert_alpha()
        self.Blocs = BlockGroup(self.game_surface, self.enemies)
        self.levelCollection = LevelCollection(self.Blocs)
        
        

        self.loadTableau()

    def start_boss_mode(self):
        self.boss_mode = True
        self.fight_boss = True
        self.enemy_bullets = pygame.sprite.Group()
        self.boss = Boss(self.game_surface, self.enemy_bullets)
        self.waveNumber = 1
        self.bullets = pygame.sprite.Group()
        self.enemies = EnemyGroup(self.game_surface)

        self.player = Player()
        self.background = pygame.image.load(str(BACKGROUND_IMAGE_PATH)).convert_alpha()
        self.Blocs = BlockGroup(self.game_surface, self.enemies)
        self.levelCollection = LevelCollection(self.Blocs)

        self.loadTableau(1000)
    
    def renderGameBackground(self,app:"App"):
        if self.waveNumber == 10 and not app.redBg:
            app.background = pygame.image.load(str(BACKGROUND_RED_IMAGE_PATH)).convert_alpha()
            self.game_surface.blit(self.background, (0, 0))
            app.redBg = True
        else:
            self.game_surface.blit(self.background, (0, 0))
    
    def renderGame(self,app:"App"):
        """AJOUTER DOCSTRINGEEEEEE"""
        self.renderGameBackground(app)
        self.player.update(self.game_surface, self.Blocs, self.enemy_bullets,app.delta_time)
        self.Blocs.draw(self.game_surface)
        self.bullets.draw(self.game_surface)
        self.enemies.draw(self.game_surface)
        self.enemy_bullets.draw(self.game_surface)
        if self.fight_boss:
            self.boss.update(self.bullets, self.player, self.menu, self)
        if self.game_over:
            app.menu.show_end_screen()