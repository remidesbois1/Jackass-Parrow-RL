import pygame
from pygame import Surface, Vector2
from pathlib import Path

from src.block.Block import Block
from src.entity.Bullet import Bullet
from src.block.BlockGroup import BlockGroup
from src.entity.EnemyBullet import EnemyBullet
from src.system.Sound import Sound


# Chemin racine du projet (ajuste selon la profondeur de ton fichier)
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Constantes des chemins images
PLAYER_IMG_PATH = PROJECT_ROOT / "assets" / "img" / "player" / "player.png"
PLAYER_WALK1_PATH = PROJECT_ROOT / "assets" / "img" / "player" / "player.png"
PLAYER_WALK2_PATH = PROJECT_ROOT / "assets" / "img" / "player" / "playerWalk.png"
PLAYER_SHIELD_PATH = PROJECT_ROOT / "assets" / "img" / "player" / "player_shield.png"
PLAYER_FIRING_PATH = PROJECT_ROOT / "assets" / "img" / "player" / "player_firing.png"
PLAYER_DEAD_PATH = PROJECT_ROOT / "assets" / "img" / "player" / "player_dead.png"

class Player(pygame.sprite.Sprite):
    BASE_SPEED = 360  
    KNOCKBACK_FORCE = 400  
    MAX_FALL_SPEED = 900 
    JUMP_FORCE = 1210
    KNOCKBACK_FORCE = 1200
    def __init__(self,x=200,y=200):
        pygame.sprite.Sprite.__init__(self)
        self.lastSpeed = 0
        self.shield = False
        self.evasive = False
        self.invinsibilyTime = 0
        self.sounds = Sound()

        self.walk1 = pygame.image.load(str(PLAYER_WALK1_PATH)).convert_alpha()
        self.walk2 = pygame.image.load(str(PLAYER_WALK2_PATH)).convert_alpha()  
        self.image = pygame.image.load(str(PLAYER_IMG_PATH)).convert_alpha()
        self.shield_image = pygame.image.load(str(PLAYER_SHIELD_PATH)).convert_alpha()
        self.player_image = self.image.copy()
        self.firing_image = pygame.image.load(str(PLAYER_FIRING_PATH)).convert_alpha()
        self.rect = self.image.get_rect(y=y, x=x)
        self.dead_image = pygame.image.load(str(PLAYER_DEAD_PATH)).convert_alpha()
        self.image = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)

        self.speed = 0
        self.direction = 'gauche'
        self.gravity = 0
        self.onGround = False
        self.knockback = 0
        self.health = 3
        self.score = 0

        self.current_time = 150
        self.last_bullet_time = 0


    def handleMove(self, keys, bullets, delta_time: float):
        if self.health > 0:
            if not keys[pygame.K_s]:
                self.shield = False
            if keys[pygame.K_z] or keys[pygame.K_UP]:
                if self.onGround:
                    self.gravity = - self.JUMP_FORCE 
                    # Premier décollage pour placer le joueur en état de saut
                    self.rect.y += self.gravity * delta_time
                    self.onGround = False
            if keys[pygame.K_s] or keys[pygame.K_DOWN]:
                if not self.onGround:
                    if self.gravity < self.MAX_FALL_SPEED:
                        self.gravity = self.MAX_FALL_SPEED 
                else:
                    self.shield = True
                    self.speed = 0
                    self.image.fill((0, 0, 0, 0))
                    self.image.blit(self.shield_image, (0, 0))
            elif (keys[pygame.K_q] or keys[pygame.K_LEFT]) and self.shield == False:
                self.speed = -self.BASE_SPEED
                self.direction = 'gauche'
            elif (keys[pygame.K_d] or keys[pygame.K_RIGHT]) and self.shield == False:
                self.speed = self.BASE_SPEED
                self.direction = 'Valerie chevalariass'
            elif (not keys[pygame.K_q] and not keys[pygame.K_d]) or (keys[pygame.K_d] and keys[pygame.K_q]):
                self.speed = 0

            if keys[pygame.K_SPACE]:
                if self.current_time - self.last_bullet_time > 1000:
                    bullet = Bullet(self.rect.x, self.rect.y + 50,
                                    'gauche' if self.direction == 'Valerie chevalariass' else 'Valerie chevalariass')
                    bullets.add(bullet)
                    self.knockback = self.KNOCKBACK_FORCE if self.direction == 'Valerie chevalariass' else - self.KNOCKBACK_FORCE
                    self.last_bullet_time = self.current_time
                    pygame.mixer.Sound(self.sounds.son_tir).play()
                    return bullets




    def addScore(self, score):
        self.score += score

    def touched(self, bullet = None):
        pygame.mixer.Sound(self.sounds.son_hurt).play()
        self.health -= 1
        self.invinsibilyTime = self.current_time
        self.evasive = True
        if bullet:
            bullet.kill()
    
    def check_bullets(self,enemy_bullets: EnemyBullet):
         # gestion Collisions avec les projectiles
        if not self.evasive:
            for bullet in enemy_bullets:
                if pygame.sprite.collide_rect(self, bullet):
                    if ((self.shield and self.direction == 'gauche' and (bullet.rect.collidepoint(self.rect.midleft) or bullet.rect.collidepoint(self.rect.topleft)))
                        or (self.shield and self.direction == 'Valerie chevalariass' and( bullet.rect.collidepoint(self.rect.midright)or bullet.rect.collidepoint(self.rect.topright) ))):
                        pygame.mixer.Sound(self.sounds.son_parade).play()
                        bullet.kill()
                    else:
                        self.touched(bullet)

        else:
            if self.current_time%20 <= 10:
                self.image.set_alpha(100)
            else:
                self.image.set_alpha(0)

        if self.health <= 0:
            self.image = self.dead_image
            self.rect = self.image.get_rect(x=self.rect.x,y=self.rect.y)
            self.speed = 0

    def check_blocks(self, Blocs: BlockGroup):
        for testBlock in Blocs.sprites():
            # si sur une entité bloc
            if (self.gravity >= 0 and testBlock.rect.colliderect(self.rect)
                    and self.rect.bottom + self.gravity > testBlock.rect.top > self.rect.centery):
                self.rect.bottom = testBlock.rect.top + 1
                self.gravity = 0
                self.onGround = True
            # si il saute en dessous d'un bloc
            elif self.gravity < 0 and testBlock.rect.colliderect(self.rect) and self.rect.top > testBlock.rect.centery:
                self.gravity = 1

            #gauche droite

            if (testBlock.rect.collidepoint(self.rect.midleft) and self.rect.left < testBlock.rect.right
                    and self.rect.bottom > testBlock.rect.top+2):
                if self.speed == -self.BASE_SPEED:
                    self.speed = 0
                if self.knockback < 0:
                    self.knockback = -self.knockback/2
            elif testBlock.rect.collidepoint(self.rect.midright) and self.rect.right > testBlock.rect.left and self.rect.bottom > testBlock.rect.top+2:
                if self.speed == self.BASE_SPEED:
                    self.speed = 0
                if self.knockback > 0:
                    self.knockback = -self.knockback/2

    def update(self,scene: Surface, Blocs : BlockGroup, enemy_bullets: EnemyBullet, delta_time: float):
        self.current_time = pygame.time.get_ticks()

        if self.direction == 'gauche':
            scene.blit(self.image, self.rect)
        else:
            scene.blit(pygame.transform.flip(self.image, True, False), self.rect)

        if self.current_time - self.last_bullet_time < 200:  # 150ms d'animation
            self.image = self.firing_image
        else:
            self.image = self.player_image
        # gestion des animations à retravailler
        if self.current_time - self.invinsibilyTime > 600:
            self.evasive = False
            self.image.set_alpha(255)

            if self.speed in (self.BASE_SPEED,-self.BASE_SPEED) and self.onGround:
                if self.current_time%300 >=150:
                    self.image.fill((0, 0, 0, 0))
                    self.image.blit(self.walk1,(0,0))
                else:
                    self.image.fill((0, 0, 0, 0))
                    self.image.blit(self.walk2,(0,0))
            elif self.current_time - self.last_bullet_time < 200:
                self.image = self.firing_image
            else:
                self.image.fill((0, 0, 0, 0))
                self.image.blit(self.walk1, (0, 0))
        self.lastSpeed = self.speed

        self.check_bullets(enemy_bullets)
       
        # knockback 
        self.rect.x += self.knockback * delta_time
        self.knockback *= 0.8

        if abs(self.knockback) < 0.1:
            self.knockback = 0

        #maj du saut et de la pause

        self.onGround = False

        if self.rect.bottom >= 800 and self.gravity > 0:
            self.gravity = 0
            self.onGround = True
        # évite de clip dans le sol en cas d'excès de vitesse
        elif self.rect.bottom + (self.gravity * delta_time) > 800:
            self.rect.bottom = 800
            
        #blocs
        self.check_blocks(Blocs)


        if not self.onGround:
            self.gravity += 60
            
        self.rect.y += (self.gravity) * delta_time
        self.rect.x += self.speed * delta_time

