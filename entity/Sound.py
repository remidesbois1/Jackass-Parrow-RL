import pygame

class Sound:
    def __init__(self):
        self.son_tir = pygame.mixer.Sound("sound/tir.wav")
        self.son_button = pygame.mixer.Sound("sound/button.wav")
        self.son_hurt = pygame.mixer.Sound("sound/hurt.wav")
        self.son_knight_hurt = pygame.mixer.Sound("sound/knight_hurt.wav")
        self.son_enemy_fire = pygame.mixer.Sound("sound/enemyFire.wav")
        self.son_parade = pygame.mixer.Sound("sound/parade.wav")