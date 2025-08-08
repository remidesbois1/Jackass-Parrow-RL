import pygame
from pathlib import Path
from src.block.BlockGroup import BlockGroup
from src.entity.Boss import Boss
from src.entity.Player import Player
from src.system.LevelCollection import LevelCollection
from src.entity.EnemyGroup import EnemyGroup
from pygame.surface import Surface
from pygame.key import ScancodeWrapper
from typing import TYPE_CHECKING
from src.system.WorldManager import WorldManager
from src.system.GameConfig import DIFICULTY, WorldType

if TYPE_CHECKING:
    from src.app import App

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKGROUND_IMAGE_PATH = PROJECT_ROOT / "assets" / "img" / "background" / "fondGameJam.png"
BACKGROUND_RED_IMAGE_PATH = PROJECT_ROOT / "assets" / "img" / "background" / "fondGameJamRed.png"



class GameManager:
    def __init__(self,game_surface:Surface):
        # game systemR
        self.levelCollection = None
        self.game_surface = game_surface
        self.background_list = [
                            pygame.image.load(str(BACKGROUND_IMAGE_PATH)).convert_alpha(),
                            pygame.image.load(str(BACKGROUND_RED_IMAGE_PATH)).convert_alpha() 
                            ]
        self.worldManager = None

        # game state
        self.waveNumber = None
        self.idNiveau = 0
        self.game_over = False
        self.game_over_time = 0
        self.fight_boss = False
        self.boss_mode = False #Séparer Game Manager et BossModeManager
        self.score_saved = False
        
        # entities 
        self.player = None
        self.bullets = None
        self.enemy_group = None
        self.enemy_bullets = None
        self.Blocs = None
        self.boss = None
        self.tom = None
        
        
    def onLoop(self,delta_time:float, keys: ScancodeWrapper,app:"App"):
        WIDTH = 1280
        self.Blocs.update()
        self.player.handleMove(keys, self.bullets,delta_time)
        self.enemy_group.update(self.player, self.enemy_bullets, self.bullets)
        self.enemy_bullets.update(WIDTH, self.Blocs, delta_time)
        
        # si combat de boss on ajoute les boucliers du boss aux blocs
        if self.fight_boss:
                self.bullets.update(WIDTH, self.Blocs.sprites() + self.boss.bouclier.sprites(),delta_time)
        else:
            self.bullets.update(WIDTH, self.Blocs, delta_time)
        
        #check player mort
        if self.player.health <= 0 and not self.game_over:
                self.game_over = True
                self.game_over_time = pygame.time.get_ticks()
                

        # check boss mort
        if self.fight_boss and self.boss.health <= 0 and self.boss.outroFinished:
            if self.boss_mode:
                app.restart()
                self.boss.outroFinished = False
            else:
                self.fight_boss = False
                self.Blocs.empty()
                self.worldManager.next_world()
                self.loadTableau()
                self.boss = None

        # si tous les ennemis sont morts et que la propriété bosse est null on passe au niveau suivant
        if self.enemy_group.nbAlive() == 0 and self.boss is None and not self.boss_mode:
            self.enemy_group.empty()
            self.Blocs.empty()
            if self.worldManager.current_world.current_level >= self.worldManager.current_world.nb_levels:
                self.load_tableau_boss()
                self.player.speed = 0
                self.player.knockback = 0
                self.boss = Boss(self.game_surface, self.enemy_bullets)
                self.fight_boss = True
            else:
                self.loadTableau()
    
    def loadTableau(self):
        self.enemy_bullets.empty()
        idNiveau = self.worldManager.current_world.get_next_level_id()
        self.levelCollection.load(idNiveau)
        self.player.rect.x, self.player.rect.y = self.levelCollection.playerSpawn
        self.Blocs.spawn(self.worldManager.current_world.current_level,self.enemy_group)
    
    def load_tableau_boss(self):
        """ Charge le tableau du boss du monde, vide les groupes ennemis et les groupes blocs"""
        self.enemy_bullets.empty()
        self.levelCollection.load_boss(self.worldManager.current_world.monde_index)
        self.player.rect.x, self.player.rect.y = self.levelCollection.playerSpawn
        self.Blocs.spawn(self.worldManager.current_world.current_level,self.enemy_group)



    def startGame(self):
        self.waveNumber = 0
        self.boss_mode = False
        self.fight_boss = False
        self.game_over = False
        self.game_over_time = 0
        
        if self.boss is not None:
            self.boss.kill()
        
        self.bullets = pygame.sprite.Group()
        self.enemy_group = EnemyGroup(self.game_surface)
        self.enemy_bullets = pygame.sprite.Group()

        self.player = Player()
        self.Blocs = BlockGroup(self.game_surface)
        self.levelCollection = LevelCollection(self.Blocs)
        self.worldManager = WorldManager(DIFICULTY.OLD, self.levelCollection)
        
        self.loadTableau()

    def start_boss_mode(self):
        self.boss_mode = True
        self.fight_boss = True
        self.enemy_bullets = pygame.sprite.Group()
        self.boss = Boss(self.game_surface, self.enemy_bullets)
        
        self.bullets = pygame.sprite.Group()
        self.enemy_group = EnemyGroup(self.game_surface)

        self.player = Player()
        self.Blocs = BlockGroup(self.game_surface)
        self.levelCollection = LevelCollection(self.Blocs)
        self.worldManager = WorldManager(DIFICULTY.OLD, self.levelCollection)

        self.load_tableau_boss()
    
    def renderGameBackground(self):
        if self.worldManager.current_world.monde_index == WorldType.MONDE_VOLCAN:
            self.game_surface.blit(self.background_list[1], (0, 0))
        elif self.worldManager.current_world.monde_index == WorldType.MONDE_JUNGLE:
            self.game_surface.blit(self.background_list[0], (0, 0))
        else:
            raise NotImplementedError(f"Le monde {self.worldManager.current_world.monde_index} n'a pas de fond de jeu défini.")


    
    def renderGame(self,app:"App",delta_time:float):
        """AJOUTER DOCSTRINGEEEEEE"""
        self.renderGameBackground()
        self.player.update(self.game_surface, self.Blocs, self.enemy_bullets,delta_time)
        self.Blocs.draw(self.game_surface)
        self.bullets.draw(self.game_surface)
        self.enemy_group.draw(self.game_surface)
        self.enemy_bullets.draw(self.game_surface)
        if self.fight_boss:
            self.boss.update(self.bullets, self.player, app.menu, app)
        if self.game_over:
            app.menu.show_end_screen()