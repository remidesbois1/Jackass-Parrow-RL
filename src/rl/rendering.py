"""Read-only, cached Pygame presentation of the exact headless simulation.

Imported lazily by render modes only. No graphical-game entity, sound, UI or
update method is involved; animation is derived exclusively from engine ticks.
"""

from pathlib import Path

import numpy as np
import pygame

from src.system import mechanics as m


ASSETS = Path(__file__).resolve().parents[2] / "assets"


class HeadlessRenderer:
    def __init__(self, mode="rgb_array"):
        if mode not in ("human", "rgb_array"):
            raise ValueError("render mode must be human or rgb_array")
        self.mode = mode
        self.closed = False
        self.window_closed = False
        self.action = (0, 0, 0, 0)
        self.episode = 1
        self.policy_name = "IA"
        self.paused = False
        self.speed = 1.0
        self.stochastic = False
        self.hitboxes = False
        self._clock = pygame.time.Clock()
        self._display_started = False
        self._font_started = not pygame.font.get_init()
        if self._font_started:
            pygame.font.init()
        if mode == "human":
            self._display_started = not pygame.display.get_init()
            pygame.display.init()
            self.surface = pygame.display.set_mode((m.WIDTH, m.HEIGHT))
            pygame.display.set_caption("Jackass-Parrow — Spectateur IA")
        else:
            # Off-screen rendering does not require SDL video or audio startup.
            self.surface = pygame.Surface((m.WIDTH, m.HEIGHT))
        self._textures = {}
        for name, path in (
            ("background", "background/fondGameJam.png"),
            ("background_red", "background/fondGameJamRed.png"),
            ("block", "block/block.png"), ("dirt", "block/dirt.png"),
            ("player", "player/player.png"), ("walk", "player/playerWalk.png"),
            ("shield", "player/player_shield.png"), ("firing", "player/player_firing.png"),
            ("dead", "player/player_dead.png"), ("knight", "entity/chevalier.png"),
            ("angry", "entity/chevalier_angwy.png"), ("chicken", "entity/chicken_bomb.png"),
            ("chicken_walk", "entity/chicken_bomb_walk.png"),
            ("bullet", "entity/bullet.png"), ("enemy_bullet", "entity/chicken.png"),
            ("boss", "entity/tom.png"), ("boss_hit", "entity/tomDamage.png"),
        ):
            picture = pygame.image.load(str(ASSETS / "img" / path))
            if name.startswith("boss"):
                picture = pygame.transform.scale(picture, m.BOSS_SIZE)
            if name.startswith("background") and picture.get_size() != (m.WIDTH, m.HEIGHT):
                picture = pygame.transform.scale(picture, (m.WIDTH, m.HEIGHT))
            self._textures[name, False] = picture
            self._textures[name, True] = pygame.transform.flip(picture, True, False)
        self._font = pygame.font.Font(str(ASSETS / "fonts" / "Dimbo Regular.ttf"), 25)
        self._small_font = pygame.font.Font(str(ASSETS / "fonts" / "Dimbo Regular.ttf"), 20)
        self._title_font = pygame.font.Font(str(ASSETS / "fonts" / "Dimbo Regular.ttf"), 42)
        self._blocks = None
        self._map = None
        self._panel = pygame.Surface((670, 116), pygame.SRCALPHA)
        self._panel.fill((10, 17, 25, 215))
        self._footer = pygame.Surface((m.WIDTH, 31), pygame.SRCALPHA)
        self._footer.fill((10, 17, 25, 215))

    def _draw_sprite(self, name, rect, *, flip=False, alpha=255):
        sprite = self._textures[name, flip]
        sprite.set_alpha(alpha)
        self.surface.blit(sprite, (round(rect.x), round(rect.y)))
        if self.hitboxes:
            pygame.draw.rect(self.surface, (255, 220, 70),
                             pygame.Rect(round(rect.x), round(rect.y), rect.w, rect.h), 1)

    def _draw_tiled(self, surface, block, texture):
        area = pygame.Rect(block.x, block.y, block.w, block.h)
        clipped = area.clip(surface.get_rect())
        if not clipped:
            return
        # Tile only visible map portions, including the invisible outer walls.
        x0 = block.x + max(0, (clipped.x - block.x) // 50) * 50
        y0 = block.y + max(0, (clipped.y - block.y) // 50) * 50
        previous_clip = surface.get_clip()
        surface.set_clip(clipped)
        for y in range(y0, clipped.bottom, 50):
            for x in range(x0, clipped.right, 50):
                surface.blit(texture, (x, y))
        surface.set_clip(previous_clip)

    def _draw_map(self, engine):
        if self._blocks is not engine.blocks:
            self._blocks = engine.blocks
            self._map = pygame.Surface((m.WIDTH, m.HEIGHT), pygame.SRCALPHA)
            for block in engine.blocks:
                if not block.transparent or hasattr(engine, "course_title"):
                    texture = self._textures["dirt" if block.y == 775 else "block", False]
                    self._draw_tiled(self._map, block, texture)
        self.surface.blit(self._map, (0, 0))

    def _text(self, text, position, color=(245, 245, 235), *, small=False):
        font = self._small_font if small else self._font
        self.surface.blit(font.render(text, True, color), position)

    def _draw_hud(self, engine):
        self.surface.blit(self._panel, (12, 12))
        self._text(f"IA · {self.policy_name[:34]}    |    Épisode {self.episode}", (25, 20), (255, 215, 106))
        self._text(f"Score {engine.player.score}     Vie {max(0, engine.player.health)}/3"
                   f"     Tableau {engine.level}     Temps {engine.ticks / 60:.1f}s", (25, 50))
        move, jump, down, fire = self.action
        actions = [name for active, name in ((move == 1, "GAUCHE"), (move == 2, "DROITE"),
                                              (jump, "SAUT"), (down, "PARADE / CHUTE"),
                                              (fire, "TIR")) if active]
        self._text("Actions : " + (" + ".join(actions) or "IMMOBILE"), (25, 82), small=True)
        status = "PAUSE" if self.paused else f"x{self.speed:g}"
        mode = "Échantillonnage" if self.stochastic else "Déterministe"
        self._text(f"{status} · {mode}", (950, 22), (255, 225, 125))
        self.surface.blit(self._footer, (0, m.HEIGHT - 31))
        self._text("ESPACE pause   ·   GAUCHE / DROITE vitesse   ·   R rejouer   ·   N nouvelle partie"
                   "   ·   TAB mode IA   ·   ÉCHAP quitter", (15, m.HEIGHT - 27), small=True)

    def draw(self, engine):
        """Return pixels/present a window without advancing RNG, timers or state."""
        if self.closed:
            raise RuntimeError("renderer is closed")
        # Red sky from the second loop on, where the HARD tableaux are played.
        background = "background_red" if engine.world > 0 else "background"
        self.surface.blit(self._textures[background, False], (0, 0))
        self._draw_map(engine)
        boss = engine.boss
        if boss is not None:
            name = "boss_hit" if engine.ticks - boss.last_hit <= 120 else "boss"
            self._draw_sprite(name, boss.rect)
            for shield in boss.shields:
                self._draw_tiled(self.surface, shield, self._textures["block", False])
        for enemy in engine.enemies:
            if enemy.kind == 2:
                name = "chicken_walk" if engine.ticks // 6 % 2 else "chicken"
            else:
                name = "angry" if enemy.kind == 1 else "knight"
            self._draw_sprite(name, enemy.rect, flip=enemy.direction > 0)
        for bullets, name in ((engine.bullets, "bullet"), (engine.enemy_bullets, "enemy_bullet")):
            for bullet in bullets:
                self._draw_sprite(name, bullet.rect, flip=bullet.velocity > 0)
        p = engine.player
        if p.health <= 0:
            name = "dead"
        elif p.shield:
            name = "shield"
        elif p.last_shot > 0 and engine.ticks - p.last_shot < 12:
            name = "firing"
        elif p.on_ground and p.speed and engine.ticks // 9 % 2:
            name = "walk"
        else:
            name = "player"
        alpha = 110 if engine.ticks - p.last_hit <= 36 and engine.ticks // 4 % 2 else 255
        self._draw_sprite(name, p.rect, flip=p.direction > 0, alpha=alpha)
        self._draw_hud(engine)
        if hasattr(engine, "navigation_goal"):
            gx, gy = engine.navigation_goal
            pygame.draw.circle(self.surface, (80, 235, 255), (round(gx + 37), round(gy - 8)), 12, 3)
            self._text("Objectif : " + getattr(engine, "course_title", "parcours"), (15, 75), small=True)
        if engine.done:
            label = "PARTIE TERMINÉE" if p.health <= 0 else ("VICTOIRE !" if engine.terminated else "FIN DE LA DÉMO")
            banner = self._title_font.render(label, True, (255, 230, 145))
            self.surface.blit(banner, banner.get_rect(center=(m.WIDTH // 2, m.HEIGHT // 2)))
        if self.mode == "human":
            pygame.display.flip()
            return None
        # surfarray is width-major; Gymnasium requires height × width × RGB.
        return np.transpose(pygame.surfarray.array3d(self.surface), (1, 0, 2)).copy()

    def present(self, engine):
        if self.mode == "human":
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    self.window_closed = True
        result = self.draw(engine)
        if self.mode == "human":
            self._clock.tick(60)
        return result

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self._display_started:
            pygame.display.quit()
        if self._font_started:
            pygame.font.quit()
