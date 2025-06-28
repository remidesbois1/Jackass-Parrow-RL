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
        self.boss_Killed = None
        self.boss = None


        self.tom = None
        self.close_lore_button_rect = None
        self.lore_button_rect = None
        self.sounds = None
        self.HUDfont = None
        self.menu = None
        self.leaderboard_button_rect = None
        self.start_button_rect = None
        self.levelCollection = None
        self.Blocs = None
        self.background = None
        self.player = None
        self.clock = pygame.time.Clock()
        self.waveNumber = None
        self.idNiveau = 0

        self._running = True
        self.gameSurface = None
        self.size = self.weight, self.height = 1280, 800
        self.bullets = None
        self.enemies = None
        self.enemy_bullets = None

        self.activeMenu = None
        self.show_start_menu = True
        self.show_lore = False
        self.start_button_rect = pygame.Rect(0, 0, 0, 0)

        self.game_over = False
        self.game_over_time = 0

        self.input_box = pygame.Rect(self.weight // 2 - 100, self.height // 1.6, 200, 50)
        self.input_box_color = (255, 255, 255)
        self.active = False
        self.user_text = ''
        self.score_saved = False
        self.save_button_rect = None

        self.show_leaderboard = False
        self.close_button_rect = None
        self.show_leaderboard_button = True

        self.boss_mode = False
        self.fight_boss = False
        self.boss_button_rect = pygame.Rect(0, 0, 0, 0)
        self.redBg = False

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
        self.bullets = pygame.sprite.Group()
        self.enemies = EnemyGroup(self.gameSurface)
        self.enemy_bullets = pygame.sprite.Group()

        self.player = Player()
        self.background = pygame.image.load(str(BACKGROUND_IMAGE_PATH)).convert_alpha()
        self.Blocs = BlockGroup(self.gameSurface, self.enemies)
        self.levelCollection = LevelCollection(self.Blocs)

        self.loadTableau()

    def start_boss_mode(self):
        self.boss_mode = True
        self.fight_boss = True
        self.enemy_bullets = pygame.sprite.Group()
        self.boss = Boss(self.gameSurface, self.enemy_bullets)
        self.waveNumber = 1
        self.bullets = pygame.sprite.Group()
        self.enemies = EnemyGroup(self.gameSurface)

        self.player = Player()
        self.background = pygame.image.load(str(BACKGROUND_IMAGE_PATH)).convert_alpha()
        self.Blocs = BlockGroup(self.gameSurface, self.enemies)
        self.levelCollection = LevelCollection(self.Blocs)

        self.loadTableau(1000)

    def start(self):
        pygame.init()
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        pygame.mixer.music.set_volume(0.15)
        pygame.mixer.music.load(str(MAIN_THEME_PATH))
        pygame.mixer.music.play(-1)
        self.sounds = Sound()
        self.menu = Menu(self)
        self.gameSurface = pygame.display.set_mode(
            self.size, pygame.HWSURFACE | pygame.DOUBLEBUF
        )
        self._running = True
        self.player = Player()
        self.background = pygame.image.load(str(BACKGROUND_IMAGE_PATH)).convert_alpha()
        self.Blocs = BlockGroup(self.gameSurface, self.enemies)
        self.levelCollection = LevelCollection(self.Blocs)
        self.redBg = False

        self.HUDfont = pygame.font.Font(str(CAT_COMIC_FONT_PATH), 36)

    def handleEvent(self, event):
        if event.type == pygame.QUIT:
            self._running = False

        self.menu.handleMenu(event, self)

        if self.game_over:
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
        if self.activeMenu == "game":
            keys = pygame.key.get_pressed()
            self.Blocs.update()
            self.player.handleMove(keys, self.bullets)
            self.enemies.update(self.player, self.enemy_bullets, self.bullets)
            self.enemy_bullets.update(self.weight, self.Blocs, self.player)

            if self.fight_boss:
                self.bullets.update(self.weight, self.Blocs.sprites() + self.boss.bouclier.sprites())
            else:
                self.bullets.update(self.weight, self.Blocs)

            if self.player.health <= 0 and not self.game_over:
                self.game_over = True
                self.game_over_time = pygame.time.get_ticks()

            if self.game_over and not self.score_saved:
                self.menu.show_end_screen()

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
                    self.boss = Boss(self.gameSurface, self.enemy_bullets)
                    self.fight_boss = True
                else:
                    self.loadTableau()

    def restart(self):
        pygame.mixer.music.load(str(MAIN_THEME_PATH))
        pygame.mixer.music.play(-1)
        self.waveNumber = 0
        self.startGame()
        self.boss_mode = False
        self.fight_boss = False
        self.show_start_menu = True
        if self.boss is not None:
            self.boss.kill()
        self.boss_Killed = False
        self.game_over = False
        self.game_over_time = 0
        self.redBg = False

    def save_score(self):
        try:
            with open(SCORES_FILE_PATH, "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = []

        data.append({"pseudo": self.user_text, "score": self.player.score})

        with open(SCORES_FILE_PATH, "w") as f:
            json.dump(data, f)

        self.restart()

    def render(self):
        if self.waveNumber == 10 and not self.redBg:
            self.background = pygame.image.load(str(BACKGROUND_RED_IMAGE_PATH)).convert_alpha()
            self.gameSurface.blit(self.background, (0, 0))
            self.redBg = True
        if self.show_start_menu:
            self.menu.show_start_screen()
        else:
            self.gameSurface.blit(self.background, (0, 0))
            self.player.update(self.gameSurface, self.Blocs, self.enemy_bullets)
            self.Blocs.draw(self.gameSurface)
            self.bullets.draw(self.gameSurface)
            self.enemies.draw(self.gameSurface)
            self.enemy_bullets.draw(self.gameSurface)
            if self.fight_boss:
                self.boss.update(self.bullets, self.player, self.menu, self)

        if self.game_over:
            self.menu.show_end_screen()

        if self.activeMenu == "game":
            score_text = self.HUDfont.render(f"Score: {self.player.score}", True, (255, 255, 255))
            health_text = self.HUDfont.render(f"Vie: {self.player.health}", True, (255, 255, 255))
            self.gameSurface.blit(score_text, (10, 10))
            self.gameSurface.blit(health_text, (10, 40))

    def shutdown(self):
        pygame.quit()

    def execute(self):
        self._running = True

        while self._running:
            for event in pygame.event.get():
                self.handleEvent(event)
            self.onLoop()
            self.render()
            pygame.display.flip()
            self.clock.tick(60)
        self.shutdown()
