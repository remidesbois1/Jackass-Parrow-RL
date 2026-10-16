"""Headless game kernel: no pygame, assets, wall clock, UI or global RNG.

``advance`` is the allocation-light path; ``step`` takes an observation snapshot.
One action is a bit mask, held for ``frame_skip`` fixed 1/60-second ticks.
"""

from dataclasses import dataclass
from enum import IntFlag
from functools import lru_cache
from random import Random

from src.system import mechanics as m
from src.system.level_data import BOSS_JUNGLE, LEVELS
from src.system.GameConfig import DIFFICULTY, worlds_config

OLD_WORLD_LEVELS = worlds_config[DIFFICULTY.OLD][0]["nb_level"]


class Action(IntFlag):
    IDLE = 0
    LEFT = 1
    RIGHT = 2
    JUMP = 4
    DOWN = 8
    FIRE = 16


@dataclass(frozen=True, slots=True)
class Config:
    frame_skip: int = 1
    max_episode_steps: int | None = 36_000
    boss_mode: bool = False

    def __post_init__(self):
        if type(self.frame_skip) is not int or self.frame_skip < 1:
            raise ValueError("frame_skip must be a positive integer")
        if self.max_episode_steps is not None and (
            type(self.max_episode_steps) is not int or self.max_episode_steps < 1
        ):
            raise ValueError("max_episode_steps must be a positive integer or None")


@dataclass(slots=True)
class Rect:
    x: float
    y: float
    w: float
    h: float

    def overlaps(self, other):
        return (self.x < other.x + other.w and self.x + self.w > other.x
                and self.y < other.y + other.h and self.y + self.h > other.y)


@dataclass(frozen=True, slots=True)
class Platform:
    # Immutable geometry is cached once per process and shared by all environments.
    x: int
    y: int
    w: int
    h: int
    spawnable: bool = False
    transparent: bool = False


@lru_cache(maxsize=11)
def level_geometry(level_id):
    data = BOSS_JUNGLE if level_id == 0 else LEVELS[level_id - 1]
    blocks = [Platform(-10, 775, 1300, 50),
              Platform(-60, -425, 50, 1400), Platform(1290, -425, 50, 1400)]
    spawn = (0, 0)
    for item in data:
        if len(item) == 2:
            spawn = (item[0] * 50, item[1] * 50)
        else:
            x, y, w, h, *flags = item
            blocks.append(Platform(x * 50 + 40, y * 50 - 25, w * 50, h * 50,
                                   bool(flags and flags[0]), bool(len(flags) > 1 and flags[1])))
    return tuple(blocks), spawn, tuple(b for b in blocks if b.spawnable)


@dataclass(slots=True)
class Player:
    rect: Rect
    speed: float = 0
    gravity: float = 0
    knockback: float = 0
    direction: int = -1
    health: int = 3
    score: int = 0
    on_ground: bool = False
    shield: bool = False
    last_shot: int = 0
    last_hit: int = -1_000_000


@dataclass(slots=True)
class Enemy:
    rect: Rect
    kind: int  # 0 knight, 1 angry knight, 2 kamikaze
    platform: Platform
    last_shot: int = 0
    direction: int = 1
    alive: bool = True


@dataclass(slots=True)
class Projectile:
    rect: Rect
    velocity: int
    blockers: tuple
    active: bool = True


@dataclass(slots=True)
class Boss:
    rect: Rect
    health: int = 10
    last_hit: int = -1_000_000
    last_shot: int = -1_000_000
    hole: int = 0
    shields: tuple = ()


class HeadlessEnv:
    """One isolated episode of the original OLD difficulty (seven levels + Tom).

    The kernel keeps gameplay update order and units. Cinematics and corpse
    animations are skipped; terminal states freeze immediately. See doc/headless.md
    for the small, intentional corrections to graphical-game bugs.
    Mutable instances are owned by the caller, never shared between threads.
    """

    __slots__ = ("config", "rng", "player", "enemies", "bullets", "enemy_bullets",
                 "boss", "blocks", "level_id", "level", "world", "danger", "ticks",
                 "steps", "terminated", "truncated", "last_reward", "seed")

    def __init__(self, seed=None, config=None):
        self.config = config if config is not None else Config()
        self.rng = Random(seed)
        self.seed = seed
        self.reset(observe=False)

    def reset(self, *, seed=None, observe=True):
        """Reset; a supplied seed reproduces an episode, None continues the RNG."""
        if seed is not None:
            self.rng.seed(seed)
            self.seed = seed
        self.player = Player(Rect(0, 0, *m.PLAYER_SIZE))
        self.enemies = []
        self.bullets = []
        self.enemy_bullets = []
        self.boss = None
        self.level_id = -1
        self.level = 0
        self.world = 0
        self.danger = 0
        self.ticks = self.steps = 0
        self.terminated = self.truncated = False
        self.last_reward = 0
        self._load_level(boss=self.config.boss_mode)
        if observe:
            return self.observe(), self.info()

    @property
    def done(self):
        return self.terminated or self.truncated

    def _load_level(self, *, boss=False):
        self.enemy_bullets.clear()
        self.enemies.clear()
        if boss:
            self.level_id = 0
            self.boss = Boss(Rect(*m.BOSS_POSITION, *m.BOSS_SIZE))
            self.player.speed = self.player.knockback = 0
        else:
            # The graphical OLD difficulty loops through jungle with +3 danger.
            previous = self.level_id
            self.level_id = self.rng.randint(1, 5)
            while self.level_id == previous:
                self.level_id = self.rng.randint(1, 5)
            self.level += 1
            self.danger = self.world * 3 + self.level
            self.boss = None
        self.blocks, spawn, spawnable = level_geometry(self.level_id)
        self.player.rect.x, self.player.rect.y = spawn
        # The graphical game keeps player bullets between tableaux. Rebind their
        # cached broad phase to the new geometry instead of retaining old blocks.
        for bullet in self.bullets:
            bullet.blockers = self._blockers(bullet.rect)
        if not boss:
            for block in self.rng.sample(spawnable, min(self.danger, len(spawnable))):
                x = self.rng.randint(block.x, block.x + block.w - m.KNIGHT_SIZE[0] // 2)
                chicken = self.rng.randint(0, 3) == 0
                kind = 2 if chicken else int(self.danger > 5)
                size = m.CHICKEN_SIZE if chicken else m.KNIGHT_SIZE
                self.enemies.append(Enemy(Rect(x, block.y - size[1], *size), kind, block))

    def _blockers(self, rect):
        # Projectiles never move vertically. Filter static collision candidates
        # once at birth, rather than scanning every platform on every tick.
        return tuple(b for b in self.blocks if not b.transparent
                     and rect.y < b.y + b.h and rect.y + rect.h > b.y)

    def _shoot(self, target, x, y, direction, enemy=False):
        rect = Rect(x, y, *(m.ENEMY_BULLET_SIZE if enemy else m.PLAYER_BULLET_SIZE))
        target.append(Projectile(rect, direction * m.PROJECTILE_SPEED, self._blockers(rect)))

    def _hit_player(self):
        p = self.player
        if (self.ticks - p.last_hit) * 1000 <= m.INVULNERABILITY_MS * 60:
            return
        p.health -= 1
        p.last_hit = self.ticks

    def _update_player(self, action):
        p = self.player
        r = p.rect
        # As in GameManager.on_loop: incoming hits and physics, then controls.
        if (self.ticks - p.last_hit) * 1000 > m.INVULNERABILITY_MS * 60:
            for bullet in self.enemy_bullets:
                if not bullet.active or not r.overlaps(bullet.rect):
                    continue
                b = bullet.rect
                edge = r.x if p.direction == -1 else r.x + r.w
                blocked = (p.shield and b.x <= edge < b.x + b.w
                           and (b.y <= r.y + r.h / 2 < b.y + b.h
                                or b.y <= r.y < b.y + b.h))
                bullet.active = False
                if not blocked:
                    self._hit_player()
                    break
        p.knockback *= 0.85
        if abs(p.knockback) < 0.1:
            p.knockback = 0
        p.on_ground = False
        if r.y + r.h >= m.HEIGHT and p.gravity > 0:
            p.gravity = 0
            p.on_ground = True
        elif r.y + r.h + p.gravity / 60 > m.HEIGHT:
            r.y = m.HEIGHT - r.h
        # Block.rect is an integer pygame.Rect in the graphical game. Its
        # colliderect/point methods truncate FRect inputs, unlike sprite-vs-sprite
        # collisions. Preserve that behavior at fractional platform edges.
        px, py = int(r.x), int(r.y)
        right = int(r.x + r.w)
        mid_y = int(r.y + r.h / 2)
        for b in self.blocks:
            if (px < b.x + b.w and px + r.w > b.x
                    and py < b.y + b.h and py + r.h > b.y):
                if p.gravity >= 0 and r.y + r.h + p.gravity > b.y > r.y + r.h / 2:
                    r.y = b.y + 1 - r.h
                    py = int(r.y)
                    mid_y = int(r.y + r.h / 2)
                    p.gravity = 0
                    p.on_ground = True
                elif p.gravity < 0 and r.y > b.y + b.h / 2:
                    p.gravity = 1
            if b.y <= mid_y < b.y + b.h and r.y + r.h > b.y + 2:
                if b.x <= px < b.x + b.w:
                    if p.speed == -m.PLAYER_SPEED:
                        p.speed = 0
                    if p.knockback < 0:
                        p.knockback *= -0.5
                elif b.x <= right < b.x + b.w:
                    if p.speed == m.PLAYER_SPEED:
                        p.speed = 0
                    if p.knockback > 0:
                        p.knockback *= -0.5
        if not p.on_ground:
            p.gravity += m.GRAVITY / 60
        r.y += p.gravity / 60
        r.x += (p.speed + p.knockback) / 60
        if p.health <= 0:
            p.speed = 0
            return
        p.shield = False
        # Plain integer masks avoid constructing IntFlag objects in this hot loop.
        if action & 4 and p.on_ground:
            p.gravity = -m.JUMP_FORCE
            r.y += p.gravity / 60
            p.on_ground = False
        if action & 8:
            if not p.on_ground:
                p.gravity = max(p.gravity, m.MAX_FALL_SPEED)
            else:
                p.shield = True
                p.speed = 0
        elif action & 1:
            p.speed = -m.PLAYER_SPEED
            p.direction = -1
        elif action & 2:
            p.speed = m.PLAYER_SPEED
            p.direction = 1
        else:
            p.speed = 0
        if action & 16 and (self.ticks - p.last_shot) * 1000 > m.SHOT_DELAY_MS * 60:
            self._shoot(self.bullets, r.x, r.y + 50, -p.direction)
            p.knockback = p.direction * m.KNOCKBACK_FORCE
            p.last_shot = self.ticks

    def _update_enemies(self):
        p = self.player
        keep = 0
        for enemy in self.enemies:
            r = enemy.rect
            if enemy.kind == 2:
                r.x += m.CHICKEN_SPEED / 60 * enemy.direction
                b = enemy.platform
                if r.x + r.w > b.x + b.w - 15:
                    enemy.direction = -1
                elif r.x < b.x + 15:
                    enemy.direction = 1
                if r.overlaps(p.rect):
                    self._hit_player()
                    enemy.alive = False
            else:
                lo, hi = (1120, 1540) if enemy.kind == 1 else (1600, 2200)
                if ((self.ticks - enemy.last_shot) * 1000 > self.rng.randint(lo, hi) * 60
                        and p.health > 0):
                    direction = -1 if r.x + r.w / 2 > p.rect.x + p.rect.w / 2 else 1
                    enemy.direction = direction
                    self._shoot(self.enemy_bullets, r.x + r.w / 2, r.y + r.h / 2, direction, True)
                    enemy.last_shot = self.ticks
            if enemy.alive:
                for bullet in self.bullets:
                    if bullet.active and r.overlaps(bullet.rect):
                        enemy.alive = bullet.active = False
                        p.score += 150 if enemy.kind == 1 else 100
                        break
            if enemy.alive:
                self.enemies[keep] = enemy
                keep += 1
        del self.enemies[keep:]

    def _update_boss(self):
        boss = self.boss
        delay = 700 if boss.health <= 3 else 1000
        if (self.ticks - boss.last_shot) * 1000 > delay * 60:
            self._shoot(self.enemy_bullets, boss.rect.x - 100, self.player.rect.y, -1, True)
            boss.last_shot = self.ticks
        if (self.ticks - boss.last_hit) <= 120:
            return
        for bullet in self.bullets:
            if bullet.active and boss.rect.overlaps(bullet.rect):
                bullet.active = False
                boss.health -= 1
                boss.last_hit = self.ticks
                # Two opaque shields and one gap, different from the last gap.
                boss.hole = self.rng.choice(tuple(i for i in range(3) if i != boss.hole))
                boss.shields = tuple(Platform(790, 575 - i * 200, 50, 150)
                                     for i in range(3) if i != boss.hole)
                break

    @staticmethod
    def _advance_projectiles(projectiles, shields=()):
        keep = 0
        for bullet in projectiles:
            if not bullet.active:
                continue
            r = bullet.rect
            r.x += bullet.velocity / 60
            if r.x > m.WIDTH or r.x + r.w < 0:
                continue
            blocked = False
            for block in bullet.blockers:
                if r.overlaps(block):
                    blocked = True
                    break
            if not blocked:
                for block in shields:
                    if r.overlaps(block):
                        blocked = True
                        break
            if blocked:
                continue
            projectiles[keep] = bullet
            keep += 1
        del projectiles[keep:]

    def _tick(self, action):
        self.ticks += 1
        self._update_player(action)
        if self.boss is not None:
            self._update_boss()
        self._update_enemies()
        self._advance_projectiles(self.enemy_bullets)
        self._advance_projectiles(self.bullets, self.boss.shields if self.boss else ())
        if self.player.health <= 0:
            self.terminated = True
        elif self.boss is not None and self.boss.health <= 0:
            if self.config.boss_mode:
                self.terminated = True
            else:
                self.world += 1
                self.level = 0
                self._load_level()
        elif self.boss is None and not self.enemies:
            self._load_level(boss=self.level == OLD_WORLD_LEVELS)

    @staticmethod
    def validate_action(action):
        if not isinstance(action, int) or isinstance(action, bool) or not 0 <= action <= 31:
            raise ValueError("action must be an integer bit mask in [0, 31]")

    def advance(self, action=Action.IDLE):
        """Run one decision without building observations; return delta score.

        Calling after termination requires an explicit reset (never autoresets).
        The episode limit counts decisions, not internal physics ticks.
        """
        self.validate_action(action)
        if self.done:
            raise RuntimeError("episode is done; call reset() before advancing")
        return self._advance(int(action))

    def _advance(self, action):
        # Trusted path for BatchEnv, which validates the full batch up front.
        before = self.player.score
        for _ in range(self.config.frame_skip):
            self._tick(action)
            if self.terminated:
                break
        self.steps += 1
        limit = self.config.max_episode_steps
        self.truncated = not self.terminated and limit is not None and self.steps >= limit
        self.last_reward = self.player.score - before
        return self.last_reward

    def step(self, action):
        """Return (observation, delta_score, terminated, truncated, info).

        This tuple is convenient for future adapters; this is not a Gymnasium
        environment and no ML library or training loop is required.
        """
        reward = self.advance(action)
        return self.observe(), reward, self.terminated, self.truncated, self.info()

    def info(self):
        return {"ticks": self.ticks, "steps": self.steps, "score": self.player.score,
                "world": self.world, "level": self.level, "level_id": self.level_id,
                "danger": self.danger, "boss_mode": self.config.boss_mode}

    def observe(self):
        """Detached numeric snapshot in pixels, seconds and HP (no hidden aliasing).

        Player: x,y,w,h,speed,vertical_speed,knockback,facing,hp,ground,shield,
        shot_cooldown_seconds,invulnerability_seconds. Enemies: x,y,w,h,kind,
        direction,last_shot_age_seconds. Projectiles: x,y,w,h,velocity.
        Platforms: x,y,w,h,transparent. Boss: x,y,w,h,hp,gap,invulnerability,
        shot_cooldown. Empty tuple means absent. Static platforms are immutable
        and cached independently; only these small numeric rows are exported.
        """
        p = self.player
        r = p.rect
        boss = self.boss
        cooldown = lambda last, duration: max(0.0, duration - (self.ticks - last) / 60)
        return {
            "player": (r.x, r.y, r.w, r.h, p.speed, p.gravity, p.knockback,
                       p.direction, p.health, int(p.on_ground), int(p.shield),
                       cooldown(p.last_shot, 1), cooldown(p.last_hit, 0.6)),
            "enemies": tuple((e.rect.x, e.rect.y, e.rect.w, e.rect.h, e.kind,
                              e.direction, (self.ticks - e.last_shot) / 60) for e in self.enemies),
            "bullets": tuple((b.rect.x, b.rect.y, b.rect.w, b.rect.h, b.velocity) for b in self.bullets),
            "enemy_bullets": tuple((b.rect.x, b.rect.y, b.rect.w, b.rect.h, b.velocity) for b in self.enemy_bullets),
            "blocks": tuple((b.x, b.y, b.w, b.h, int(b.transparent)) for b in self.blocks),
            "boss": (() if boss is None else
                     (boss.rect.x, boss.rect.y, boss.rect.w, boss.rect.h, boss.health,
                      boss.hole, cooldown(boss.last_hit, 2),
                      cooldown(boss.last_shot, 0.7 if boss.health <= 3 else 1))),
            "boss_shields": (() if boss is None else tuple((b.x, b.y, b.w, b.h) for b in boss.shields)),
            "context": (self.world, self.level, self.level_id, self.danger, self.ticks, self.steps),
        }
