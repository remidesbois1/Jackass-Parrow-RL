import pygame
import json
import pygame_gui
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
from src.system.GameManager import GameManager


# === CONSTANTES DE CHEMINS ===
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Images
BACKGROUND_IMAGE_PATH = PROJECT_ROOT / "assets" / "img" / "background" / "fondGameJam.png"
BACKGROUND_RED_IMAGE_PATH = PROJECT_ROOT / "assets" / "img" / "background" / "fondGameJamRed.png"

# Sons
MAIN_THEME_PATH = PROJECT_ROOT / "assets" / "sounds" / "mainTheme.mp3"

# Police
CAT_COMIC_FONT_PATH = PROJECT_ROOT / "assets" / "fonts" / "Cat Comic.ttf"

# Fichier de score
SCORES_FILE_PATH = PROJECT_ROOT / "scores.json"





class App:
    def __init__(self):
        
        self.close_lore_button_rect = None
        self.lore_button_rect = None
        self.sounds = None
        self.HUDfont = None
        self.menu = None
        self.leaderboard_button_rect = None
        self.start_button_rect = None
        

        self.background = None
        self.clock = pygame.time.Clock()
        self.delta_time = 1

        self._running = True
        self.gameSurface = None
        self.size = self.width, self.height = 1280, 800


        self.activeMenu = 'start'
        self.show_start_menu = True
        self.show_lore = False
        self.start_button_rect = pygame.Rect(0, 0, 0, 0)

        self.input_box = pygame.Rect(self.width // 2 - 100, self.height // 1.6, 200, 50)

        self.ui_manager = None

        self.input_box_color = (255, 255, 255)
        self.active = False
        self.user_text = ''
        self.save_button_rect = None

        self.show_leaderboard = False
        self.close_button_rect = None
        self.show_leaderboard_button = True

 
        self.boss_button_rect = pygame.Rect(0, 0, 0, 0)
        
        self.game_manager : GameManager = None

   

    def start(self):
        pygame.init()
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        pygame.mixer.music.set_volume(0.15)
        pygame.mixer.music.load(str(MAIN_THEME_PATH))
        pygame.mixer.music.play(-1)
        self.sounds = Sound()
        self.gameSurface = pygame.display.set_mode(
            self.size, pygame.HWSURFACE | pygame.DOUBLEBUF
        )
        self._running = True
        self.background = pygame.image.load(str(BACKGROUND_IMAGE_PATH)).convert_alpha()

        self.HUDfont = pygame.font.Font(str(CAT_COMIC_FONT_PATH), 36)
        self.game_manager = GameManager(self.gameSurface)
        self.ui_manager = pygame_gui.UIManager(self.size, str(PROJECT_ROOT / "assets" / "themes" / "theme.json"))
        self.menu = Menu(self.ui_manager,self.gameSurface)

    def handleEvent(self, event):
        self.ui_manager.process_events(event)
        if event.type == pygame.QUIT:
            self._running = False

        self.menu.handleMenu(event, self)

        if self.game_manager.game_over:
            if event.type == pygame.MOUSEBUTTONDOWN:
                if self.input_box.collidepoint(event.pos):
                    self.active = not self.active
                else:
                    self.active = False
                if self.save_button_rect.collidepoint(event.pos):
                    self.save_score()
                self.input_box_color = (0, 150, 0) if self.active else (255, 255, 255)
            if event.type == pygame.KEYDOWN:
                if self.active:
                    if event.key == pygame.K_RETURN:
                        self.save_score()
                    elif event.key == pygame.K_BACKSPACE:
                        self.user_text = self.user_text[:-1]
                    else:
                        self.user_text += event.unicode

        
    def onLoop(self):
        """
        manage all calculation and detection process on the current loop
        """
        self.ui_manager.update(60)
        if self.activeMenu == "game":
            keys = pygame.key.get_pressed()
            
            self.game_manager.on_loop(self.delta_time,keys,self)

            if self.game_manager.game_over and not self.game_manager.score_saved:
                self.menu.show_end_screen(self)



    def restart(self):
        pygame.mixer.music.load(str(MAIN_THEME_PATH))
        pygame.mixer.music.play(-1)
        self.game_manager.start_game()
        self.show_start_menu = True
 
        

    def save_score(self):
        try:
            with open(SCORES_FILE_PATH, "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = []

        data.append({"pseudo": self.user_text, "score": self.game_manager.player.score})

        with open(SCORES_FILE_PATH, "w") as f:
            json.dump(data, f)

        self.restart()

    def render(self)->None:
        """
        manages all rendering processes on the current loop.
        """
        #print(self.show_start_menu)
        if self.show_start_menu:
            self.menu.show_start_screen(self)
        else:
            self.game_manager.render_game(self,self.delta_time)

        if self.game_manager.game_over:
            self.menu.show_end_screen(self)

        if self.activeMenu == "game":
            score_text = self.HUDfont.render(f"Score: {self.game_manager.player.score}", True, (255, 255, 255))
            health_text = self.HUDfont.render(f"Vie: {self.game_manager.player.health}", True, (255, 255, 255))
            self.gameSurface.blit(score_text, (10, 10))
            self.gameSurface.blit(health_text, (10, 40))
        
        self.ui_manager.draw_ui(self.gameSurface)


    def shutdown(self)->None:
        """
        Close the game windows
        """
        pygame.quit()

    def execute(self)->None:
        """
        Run the main loop of the game who is divided in 3 main functions (handleEvent, onLoop & render)
        """
        self._running = True

        while self._running:
            for event in pygame.event.get():
                self.handleEvent(event)
            self.onLoop()
            self.render()
            pygame.display.flip()
            self.delta_time =  self.clock.tick(60) / 1000.0
        self.shutdown()
