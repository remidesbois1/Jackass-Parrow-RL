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
from src.system.GameConfig import DIFFICULTY, WorldType

if TYPE_CHECKING:
    from src.app import App

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKGROUND_IMAGE_PATH = (
    PROJECT_ROOT / "assets" / "img" / "background" / "fondGameJam.png"
)
BACKGROUND_RED_IMAGE_PATH = (
    PROJECT_ROOT / "assets" / "img" / "background" / "fondGameJamRed.png"
)


class GameManager:
    """
    Classe principale gérant le déroulement du jeu.

    Cette classe centralise le cycle de vie des parties :
    chargement des niveaux, gestion du joueur, des ennemis,
    des boss, et affichage des éléments graphiques.

    Attributes:
        level_collection (LevelCollection): Gestionnaire des niveaux.
        game_surface (Surface): Surface Pygame où le jeu est rendu.
        background_list (list[Surface]): Liste des images de fond pour chaque monde.
        world_manager (WorldManager): Gestionnaire des mondes
        game_over (bool): Indique si la partie est terminée.
        game_over_time (int): Temps écoulé depuis la fin de partie.
        fight_boss (bool): Indique si un combat de boss est en cours.
        boss_mode (bool): Indique si le jeu est en mode Boss.
        score_saved (bool): Indique si le score a été sauvegardé.
        player (Player): Le joueur contrôlé.
        bullets (pygame.sprite.Group): Projectiles du joueur.
        enemy_group (EnemyGroup): Groupe d’ennemis.
        enemy_bullets (pygame.sprite.Group): Projectiles ennemis.
        blocks (BlockGroup): Groupe de blocs responsable de l'apparition des enemies.
        boss (Boss): Instance de boss actuel.
    """
    def __init__(self, game_surface: Surface):
        """
        Initialise un gestionnaire de jeu.

        Args:
            game_surface (Surface): Surface sur laquelle le jeu est affiché.
        """
        # game systemR
        self.level_collection = None
        self.game_surface = game_surface
        self.background_list = [
            pygame.image.load(str(BACKGROUND_IMAGE_PATH)).convert_alpha(),
            pygame.image.load(str(BACKGROUND_RED_IMAGE_PATH)).convert_alpha(),
        ]
        self.world_manager = None

        # game state
        self.game_over : bool = False
        self.game_over_time : int = 0
        self.fight_boss : bool = False
        self.boss_mode: bool = False  
        self.score_saved: bool = False
        
        # entities
        self.player: Player = None
        self.boss = None
        
        # groups
        self.bullets: pygame.sprite.Group = None
        self.enemy_group : EnemyGroup = None
        self.enemy_bullets : pygame.sprite.Group = None
        self.blocks : BlockGroup = None
        

    def load_tableau(self):
        """
        Charge un niveau normal (non boss) et initialise les entités.
        """
        idNiveau = self.world_manager.get_next_level_id()
        self.level_collection.load(idNiveau)
        
        self.enemy_bullets.empty()
        self.player.rect.x, self.player.rect.y = self.level_collection.playerSpawn
        self.blocks.spawn(self.world_manager.get_danger_level(), self.enemy_group)

    def load_tableau_boss(self):
        """
        Charge un niveau de boss (uniquement tom pour l'instant)
        """
        self.enemy_bullets.empty()
        self.level_collection.load_boss(self.world_manager.get_current_world_type())
        self.player.rect.x, self.player.rect.y = self.level_collection.playerSpawn

    def start_game(self):
        """
        Initialise une nouvelle partie en mode normal.
        """
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
        self.blocks = BlockGroup(self.game_surface)
        self.level_collection = LevelCollection(self.blocks)
        self.world_manager = WorldManager(DIFFICULTY.OLD, self.level_collection)

        self.load_tableau()

    def start_boss_mode(self):
        """
        Initialise une partie en mode boss.
        """
        self.boss_mode = True
        self.fight_boss = True

        self.bullets = pygame.sprite.Group()
        self.enemy_group = EnemyGroup(self.game_surface)
        self.enemy_bullets = pygame.sprite.Group()

        self.player = Player()
        self.blocks = BlockGroup(self.game_surface)
        self.boss = Boss(self.game_surface, self.enemy_bullets)

        self.level_collection = LevelCollection(self.blocks)
        self.world_manager = WorldManager(DIFFICULTY.OLD, self.level_collection)

        self.load_tableau_boss()

    def render_game_background(self):
        """
        dessine le fond du jeu selon le monde actuel.
        """
        if self.world_manager.get_current_world_type() == WorldType.MONDE_VOLCAN:
            self.game_surface.blit(self.background_list[1], (0, 0))
        elif self.world_manager.get_current_world_type() == WorldType.MONDE_JUNGLE:
            self.game_surface.blit(self.background_list[0], (0, 0))
        else:
            raise NotImplementedError(
                f"Le monde {WorldType(self.world_manager.get_current_world_type()).name} n'a pas de fond de jeu défini."
            )

    def render_game(self, app: "App", delta_time: float):
        """
        Dessine l'ensemble des éléments du jeu sur l'écran.

        Args:
            app (App): Instance principale de l'application.
            delta_time (float): Temps écoulé depuis la dernière frame.
        """
        self.render_game_background()
        
        
        self.player.render(self.game_surface)
        self.blocks.draw(self.game_surface)
        self.bullets.draw(self.game_surface)
        self.enemy_group.draw(self.game_surface)
        self.enemy_bullets.draw(self.game_surface)
        if self.fight_boss:
            self.boss.render()
            
        if self.game_over:
            app.menu.show_end_screen(app)

    def on_loop(self, delta_time: float, keys: ScancodeWrapper, app: "App"):
        """
        Met à jour la logique du jeu pour un cycle.

        Args:
            delta_time (float): Temps écoulé depuis la dernière frame.
            keys (ScancodeWrapper): État des touches clavier.
            app (App): Instance principale de l'application.
        """
        WIDTH = 1280
        
        # arrêt du jeu pendant l'affichage d'un menu modal
        if app.menu_context.get_active_modal() is None:
            
            self.player.update(
                self.game_surface, 
                self.blocks, 
                self.enemy_bullets, 
                delta_time
            )
            if self.fight_boss:
                self.boss.update(self.bullets, self.player, app.menu.menu_context)
                
            self.blocks.render()
            self.player.handleMove(keys, self.bullets, delta_time)
            self.enemy_group.update(self.player, self.enemy_bullets, self.bullets)
            self.enemy_bullets.update(WIDTH, self.blocks, delta_time)

            # si combat de boss contre tom on ajoute les boucliers du boss aux blocs
            if self.fight_boss and self.world_manager.get_current_world_type() == WorldType.MONDE_JUNGLE:
                self.bullets.update(
                    WIDTH, self.blocks.sprites() + self.boss.bouclier.sprites(), delta_time
                )
            else:
                self.bullets.update(WIDTH, self.blocks, delta_time)

        # check player mort
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
                self.blocks.empty()
                self.world_manager.next_world()
                self.load_tableau()
                self.boss = None

        # si tous les ennemis sont morts et que la propriété boss est null on passe au niveau suivant
        if self.enemy_group.nbAlive() == 0 and self.boss is None and not self.boss_mode:
            self.enemy_group.empty()
            self.blocks.empty()
            if (
                self.world_manager.get_current_level() == self.world_manager.get_world_max_level()
            ):
                self.load_tableau_boss()
                self.player.speed = 0
                self.player.knockback = 0
                self.boss = Boss(self.game_surface, self.enemy_bullets)
                self.fight_boss = True
            elif self.world_manager.get_current_level() < self.world_manager.get_world_max_level():
                self.load_tableau()
            else:
                raise ValueError("le niveau actuelle ne peut pas être supérieur au niveau max du monde")