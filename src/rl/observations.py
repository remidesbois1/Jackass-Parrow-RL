"""Fixed-size numeric observation codec, independent of rendering and ML.

Every entity row starts with a presence mask. Overflow keeps the nearest
entities and is reported, never silently confused with an empty slot.
"""

from types import MappingProxyType

import numpy as np

from src.system import mechanics as m
from src.headless.engine import OLD_WORLD_LEVELS


OBSERVATION_SHAPES = MappingProxyType({
    "player": (13,),
    "context": (6,),
    "enemies": (8, 10),
    "blocks": (16, 6),
    "bullets": (8, 6),
    "enemy_bullets": (32, 6),
    "boss": (9,),
    "boss_shields": (2, 5),
})
_offset = 0
_slices = {}
for _key, _shape in OBSERVATION_SHAPES.items():
    _size = int(np.prod(_shape))
    _slices[_key] = slice(_offset, _offset + _size)
    _offset += _size
OBSERVATION_SLICES = MappingProxyType(_slices)
OBSERVATION_SIZE = _offset  # 454 float32 values, 1816 bytes per snapshot.


def _rect_values(rect):
    return rect.x / m.WIDTH, rect.y / m.HEIGHT, rect.w / m.WIDTH, rect.h / m.HEIGHT


def _remaining(ticks, last, milliseconds):
    # Firing and immunity use a strict '>' comparison on 60 Hz integer ticks.
    return max(0, milliseconds * 60 // 1000 + 1 - (ticks - last)) / 60


def _nearest(entities, capacity, player_rect):
    if len(entities) <= capacity:
        return entities
    px, py = player_rect.x + player_rect.w / 2, player_rect.y + player_rect.h / 2

    def distance(entity):
        rect = getattr(entity, "rect", entity)
        return (rect.x + rect.w / 2 - px) ** 2 + (rect.y + rect.h / 2 - py) ** 2

    return sorted(entities, key=distance)[:capacity]


class ObservationEncoder:
    def __init__(self):
        self._blocks = None
        self._template = np.zeros(OBSERVATION_SIZE, dtype=np.float32)

    def encode(self, engine):
        p = engine.player
        # Cache static map features until a tableau changes. Output snapshots
        # are independent arrays, safe for replay buffers and terminal states.
        if self._blocks is not engine.blocks or len(engine.blocks) > 16:
            self._blocks = engine.blocks
            rows = self._template[OBSERVATION_SLICES["blocks"]].reshape(16, 6)
            rows.fill(0)
            for i, block in enumerate(_nearest(engine.blocks, 16, p.rect)):
                rows[i] = (1, *_rect_values(block), int(block.transparent))
        obs = self._template.copy()
        obs[OBSERVATION_SLICES["player"]] = (
            *_rect_values(p.rect), p.speed / m.PLAYER_SPEED,
            p.gravity / m.JUMP_FORCE, p.knockback / m.KNOCKBACK_FORCE,
            p.direction, p.health / 3, int(p.on_ground), int(p.shield),
            _remaining(engine.ticks, p.last_shot, m.SHOT_DELAY_MS),
            _remaining(engine.ticks, p.last_hit, m.INVULNERABILITY_MS),
        )
        limit = engine.config.max_episode_steps
        obs[OBSERVATION_SLICES["context"]] = (
            engine.world / (engine.world + 1), engine.level / OLD_WORLD_LEVELS,
            engine.level_id / 10, engine.danger / (engine.danger + 1),
            max(0, 1 - engine.steps / limit) if limit else 1,
            int(engine.config.boss_mode),
        )
        rows = obs[OBSERVATION_SLICES["enemies"]].reshape(8, 10)
        for i, enemy in enumerate(_nearest(engine.enemies, 8, p.rect)):
            rows[i] = (1, *_rect_values(enemy.rect), enemy.kind / 2, enemy.direction,
                       min((engine.ticks - enemy.last_shot) / 132, 1),
                       enemy.platform.x / m.WIDTH,
                       (enemy.platform.x + enemy.platform.w) / m.WIDTH)
        for name, entities, capacity in (("bullets", engine.bullets, 8),
                                         ("enemy_bullets", engine.enemy_bullets, 32)):
            rows = obs[OBSERVATION_SLICES[name]].reshape(capacity, 6)
            for i, bullet in enumerate(_nearest(entities, capacity, p.rect)):
                rows[i] = (1, *_rect_values(bullet.rect), bullet.velocity / m.PROJECTILE_SPEED)
        boss = engine.boss
        shields = () if boss is None else boss.shields
        if boss is not None:
            obs[OBSERVATION_SLICES["boss"]] = (
                1, *_rect_values(boss.rect), boss.health / 10, boss.hole / 2,
                _remaining(engine.ticks, boss.last_hit, 2000),
                _remaining(engine.ticks, boss.last_shot, 700 if boss.health <= 3 else 1000),
            )
            rows = obs[OBSERVATION_SLICES["boss_shields"]].reshape(2, 5)
            for i, shield in enumerate(_nearest(shields, 2, p.rect)):
                rows[i] = (1, *_rect_values(shield))
        # The original game permits off-screen movement. Retain a broad range
        # without claiming positions stay strictly inside the viewport.
        np.clip(obs, -10, 10, out=obs)
        overflow = {name: max(0, len(items) - capacity) for name, items, capacity in (
            ("blocks", engine.blocks, 16), ("enemies", engine.enemies, 8),
            ("bullets", engine.bullets, 8), ("enemy_bullets", engine.enemy_bullets, 32),
            ("boss_shields", shields, 2),
        )}
        return obs, overflow
