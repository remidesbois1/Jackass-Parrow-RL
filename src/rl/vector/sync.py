"""Copy a reference ``HeadlessEnv`` state into one game of a ``VectorEngine``.

Used to encode reference games with the vector feature code (graphical viewer,
held-out evaluation) and to check physics parity tick by tick.
"""

import torch

from .engine import MAX_BULLETS, MAX_ENEMIES, MAX_ENEMY_BULLETS


def _put(tensor, index, values, capacity):
    row = torch.zeros(capacity, dtype=tensor.dtype)
    if values:
        row[:len(values)] = torch.tensor(values, dtype=tensor.dtype)
    tensor[index] = row.to(tensor.device)


def sync_from_headless(vec, index, env):
    """Overwrite game ``index`` of ``vec`` with the state of reference ``env``."""
    p = env.player
    if len(env.enemies) > MAX_ENEMIES or len(env.bullets) > MAX_BULLETS \
            or len(env.enemy_bullets) > MAX_ENEMY_BULLETS:
        raise ValueError("reference state exceeds vector engine capacity")
    scalars = {
        "px": p.rect.x, "py": p.rect.y, "speed": p.speed, "grav": p.gravity, "kb": p.knockback,
        "dirn": p.direction, "health": p.health, "score": p.score, "last_shot": p.last_shot,
        "last_hit": p.last_hit, "on_ground": p.on_ground, "shield": p.shield,
        "level_id": env.level_id, "level": env.level, "world": env.world, "danger": env.danger,
        "ticks": env.ticks, "steps": env.steps, "boss_damage": env.boss_damage,
        "bosses_defeated": env.bosses_defeated, "levels_cleared": env.levels_cleared,
        "terminated": env.terminated, "truncated": env.truncated,
        "seq": len(env.bullets) + len(env.enemy_bullets),
        "boss_on": env.boss is not None,
    }
    boss = env.boss
    if boss is not None:
        scalars.update(boss_health=boss.health, boss_last_hit=boss.last_hit,
                       boss_last_shot=boss.last_shot, boss_hole=boss.hole,
                       boss_shields=len(boss.shields) > 0)
    for name, value in scalars.items():
        getattr(vec, name)[index] = value
    t = vec.tables
    lid = max(env.level_id, 0)
    for name, table in (("bx", t.x), ("by", t.y), ("bw", t.w), ("bh", t.h),
                        ("b_trans", t.transparent), ("b_valid", t.valid)):
        getattr(vec, name)[index] = table[lid]
    enemies = env.enemies
    for name, values in (
        ("e_x", [e.rect.x for e in enemies]), ("e_y", [e.rect.y for e in enemies]),
        ("e_w", [e.rect.w for e in enemies]), ("e_h", [e.rect.h for e in enemies]),
        ("e_plx", [e.platform.x for e in enemies]), ("e_plw", [e.platform.w for e in enemies]),
        ("e_dir", [e.direction for e in enemies]), ("e_kind", [e.kind for e in enemies]),
        ("e_last", [e.last_shot for e in enemies]), ("e_alive", [e.alive for e in enemies]),
    ):
        _put(getattr(vec, name), index, values, MAX_ENEMIES)
    offset = 0
    for prefix, bullets, capacity in (("pb", env.bullets, MAX_BULLETS),
                                      ("qb", env.enemy_bullets, MAX_ENEMY_BULLETS)):
        _put(getattr(vec, prefix + "_x"), index, [b.rect.x for b in bullets], capacity)
        _put(getattr(vec, prefix + "_y"), index, [b.rect.y for b in bullets], capacity)
        _put(getattr(vec, prefix + "_v"), index, [b.velocity for b in bullets], capacity)
        _put(getattr(vec, prefix + "_act"), index, [b.active for b in bullets], capacity)
        _put(getattr(vec, prefix + "_seq"), index, list(range(offset, offset + len(bullets))), capacity)
        offset += len(bullets)
