import pygame
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

TIR_SOUND_PATH = PROJECT_ROOT / "assets" / "sounds" / "tir.wav"
BUTTON_SOUND_PATH = PROJECT_ROOT / "assets" / "sounds" / "button.wav"
HURT_SOUND_PATH = PROJECT_ROOT / "assets" / "sounds" / "hurt.wav"
KNIGHT_HURT_SOUND_PATH = PROJECT_ROOT / "assets" / "sounds" / "knight_hurt.wav"
ENEMY_FIRE_SOUND_PATH = PROJECT_ROOT / "assets" / "sounds" / "enemyFire.wav"
PARADE_SOUND_PATH = PROJECT_ROOT / "assets" / "sounds" / "parade.wav"


class Sound:
    def __init__(self):
        self.son_tir = pygame.mixer.Sound(str(TIR_SOUND_PATH))
        self.son_button = pygame.mixer.Sound(str(BUTTON_SOUND_PATH))
        self.son_hurt = pygame.mixer.Sound(str(HURT_SOUND_PATH))
        self.son_knight_hurt = pygame.mixer.Sound(str(KNIGHT_HURT_SOUND_PATH))
        self.son_enemy_fire = pygame.mixer.Sound(str(ENEMY_FIRE_SOUND_PATH))
        self.son_parade = pygame.mixer.Sound(str(PARADE_SOUND_PATH))
