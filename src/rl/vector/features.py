"""Egocentric numeric observation (schema ``JackassParrow-v2``) for a VectorEngine.

Positions are relative to the player's centre, so the same situation looks the
same anywhere on the map. Enemies, bullets and projectiles are sorted by
distance. Derived aiming facts (vertical alignment with the bullet line, clear
line of fire, bullet heading) are computed from the exact game geometry; the
policy still has to learn to move, face away from its target and fire.

The 14 actions are the meaningful button combinations: DOWN overrides any
horizontal input, and JUMP+DOWN cancels the jump in the reference controls.
"""

from types import MappingProxyType

import torch

from src.system import mechanics as m
from .engine import (BOSS_H, BOSS_X, BOSS_Y, LEVEL_COUNT, MAX_BLOCKS, MAX_ENEMIES, PBH, PBW, PH, PW,
                     EBH, EBW, SHIELD_H)

# v2: HARD tableaux in later loops (11 level ids, 12 blocks, 8 enemy slots).
SCHEMA = "JackassParrow-v2"
W, H = float(m.WIDTH), float(m.HEIGHT)
NEAREST_ENEMY_BULLETS = 8
NEAREST_BULLETS = 3

FEATURE_SHAPES = MappingProxyType({
    "player": (11,),
    "context": (LEVEL_COUNT + 4,),
    "enemies": (MAX_ENEMIES, 13),
    "enemy_bullets": (NEAREST_ENEMY_BULLETS, 5),
    "bullets": (NEAREST_BULLETS, 4),
    "boss": (11,),
    "blocks": (MAX_BLOCKS, 6),
})
_offset = 0
_slices = {}
for _name, _shape in FEATURE_SHAPES.items():
    _size = 1
    for _dim in _shape:
        _size *= _dim
    _slices[_name] = slice(_offset, _offset + _size)
    _offset += _size
FEATURE_SLICES = MappingProxyType(_slices)
FEATURE_SIZE = _offset

# (move 0 idle / 1 left / 2 right, jump, down, fire) for each compact action.
ACTION_BUTTONS = tuple([(move, jump, 0, fire) for move in range(3) for jump in range(2) for fire in range(2)]
                       + [(0, 0, 1, 0), (0, 0, 1, 1)])
ACTION_COUNT = len(ACTION_BUTTONS)


def action_masks(device):
    """Reference bit mask of every compact action."""
    return torch.tensor([(0, 1, 2)[mv] | (j << 2) | (d << 3) | (f << 4) for mv, j, d, f in ACTION_BUTTONS],
                        dtype=torch.int64, device=device)


def _remaining(ticks, last, milliseconds):
    return (milliseconds * 60 // 1000 + 1 - (ticks - last)).clamp(min=0).double() / 60


def _line_clear(vec, start, end, top, bottom):
    """True where no opaque block crosses the horizontal band between start and end."""
    lo = torch.minimum(start, end)[..., None]
    hi = torch.maximum(start, end)[..., None]
    solid = (vec.b_valid & ~vec.b_trans)[:, None, :]
    bx, by = vec.bx[:, None, :], vec.by[:, None, :]
    blocked = (solid & (bx < hi) & (bx + vec.bw[:, None, :] > lo)
               & (by < bottom[:, None, None]) & (by + vec.bh[:, None, :] > top[:, None, None]))
    return ~blocked.any(2)


def _nearest(distance, present, count):
    key = torch.where(present, distance, torch.full_like(distance, float("inf")))
    return key.argsort(1)[:, :count]


def _onehot(index, classes):
    # Comparison instead of F.one_hot, whose range check synchronises on CUDA.
    return (index[..., None] == torch.arange(classes, device=index.device)).double()


def encode(vec):
    """Return (observation float32 [N, FEATURE_SIZE], shaping potential float64 [N])."""
    px, py = vec.px, vec.py
    pcx, pcy = px + PW / 2, py + PH / 2
    top, bottom = py + 50, py + 50 + PBH  # vertical band covered by the player's bullet
    band_mid = (top + bottom) / 2
    player = torch.stack((px / W, py / H, vec.speed / m.PLAYER_SPEED, vec.grav / m.JUMP_FORCE,
                          vec.kb / m.KNOCKBACK_FORCE, vec.dirn, vec.health.double() / 3,
                          vec.on_ground.double(), vec.shield.double(),
                          _remaining(vec.ticks, vec.last_shot, m.SHOT_DELAY_MS),
                          _remaining(vec.ticks, vec.last_hit, m.INVULNERABILITY_MS)), 1)
    level_onehot = _onehot(vec.level_id.clamp(min=0), LEVEL_COUNT)
    alive = vec.e_alive
    context = torch.cat((level_onehot, torch.stack((
        vec.level.double() / 7, vec.world.clamp(max=3).double() / 3, vec.danger.double() / 10,
        alive.sum(1).double() / MAX_ENEMIES), 1)), 1)

    # Enemies, nearest first.
    ex, ey, ew, eh = vec.e_x, vec.e_y, vec.e_w, vec.e_h
    ecx, ecy = ex + ew / 2, ey + eh / 2
    dx, dy = (ecx - pcx[:, None]) / W, (ecy - pcy[:, None]) / H
    aligned = alive & (top[:, None] < ey + eh) & (bottom[:, None] > ey)
    to_right = ecx > px[:, None]
    start = torch.where(to_right, px[:, None] + PBW, px[:, None])
    end = torch.where(to_right, ex, ex + ew)
    clear = _line_clear(vec, start, end, top, bottom)
    heading = (-vec.dirn[:, None]) * (ecx - (px[:, None] + PBW / 2)) > 0
    kind = _onehot(vec.e_kind, 3)
    enemy_rows = torch.cat((
        alive.double()[..., None], dx[..., None], dy[..., None], kind, vec.e_dir[..., None],
        ((vec.ticks[:, None] - vec.e_last).double() / 132).clamp(max=1)[..., None],
        aligned.double()[..., None], (aligned & clear).double()[..., None], heading.double()[..., None],
        ((vec.e_plx - pcx[:, None]) / W)[..., None], ((vec.e_plx + vec.e_plw - pcx[:, None]) / W)[..., None],
    ), 2) * alive.double()[..., None]
    order = _nearest(dx * dx + dy * dy, alive, MAX_ENEMIES)
    enemy_rows = enemy_rows.gather(1, order[..., None].expand(-1, -1, enemy_rows.shape[2]))

    # Enemy bullets (threats) and the player's own bullets, nearest first.
    def projectile_rows(prefix, w, h, count, threat):
        act = getattr(vec, prefix + "_act")
        bx, by, bv = getattr(vec, prefix + "_x"), getattr(vec, prefix + "_y"), getattr(vec, prefix + "_v")
        bdx, bdy = (bx + w / 2 - pcx[:, None]) / W, (by + h / 2 - pcy[:, None]) / H
        cols = [act.double(), bdx, bdy, torch.sign(bv)]
        if threat:
            approaching = ((bv > 0) & (bdx < 0)) | ((bv < 0) & (bdx > 0))
            same_height = (by < py[:, None] + PH) & (by + h > py[:, None])
            cols.append((approaching & same_height).double())
        rows = torch.stack(cols, 2) * act.double()[..., None]
        idx = _nearest(bdx * bdx + bdy * bdy, act, count)
        return rows.gather(1, idx[..., None].expand(-1, -1, rows.shape[2]))

    enemy_bullet_rows = projectile_rows("qb", EBW, EBH, NEAREST_ENEMY_BULLETS, True)
    bullet_rows = projectile_rows("pb", PBW, PBH, NEAREST_BULLETS, False)

    # Tom: line of fire through the shield gap and the arena blocks.
    on = vec.boss_on
    shielded = torch.zeros_like(on)
    for i in range(3):
        sy = 575 - 200 * i
        shielded = shielded | (vec.boss_shields & (vec.boss_hole != i) & (top < sy + SHIELD_H) & (bottom > sy))
    boss_aligned = on & (top < BOSS_Y + BOSS_H) & (bottom > BOSS_Y)
    boss_clear = boss_aligned & ~shielded & _line_clear(
        vec, (px + PBW)[:, None], torch.full_like(px, float(BOSS_X))[:, None], top, bottom)[:, 0]
    hole = _onehot(vec.boss_hole, 3) * vec.boss_shields.double()[:, None]
    boss = torch.cat((torch.stack((
        on.double(), (BOSS_X - pcx) / W, (BOSS_Y + BOSS_H / 2 - pcy) / H, vec.boss_health.double() / 10,
        vec.boss_shields.double()), 1), hole, torch.stack((
        _remaining(vec.ticks, vec.boss_last_hit, 2000),
        _remaining(vec.ticks, vec.boss_last_shot, 1000) * (vec.boss_health > 3)
        + _remaining(vec.ticks, vec.boss_last_shot, 700) * (vec.boss_health <= 3),
        boss_clear.double()), 1)), 1) * on.double()[:, None]

    valid = vec.b_valid.double()
    block_rows = torch.stack((valid, (vec.bx - pcx[:, None]) / W, (vec.bx + vec.bw - pcx[:, None]) / W,
                              (vec.by - pcy[:, None]) / H, (vec.by + vec.bh - pcy[:, None]) / H,
                              vec.b_trans.double()), 2) * valid[..., None]

    obs = torch.cat((player, context, enemy_rows.flatten(1), enemy_bullet_rows.flatten(1),
                     bullet_rows.flatten(1), boss, block_rows.flatten(1)), 1).clamp(-10, 10).float()

    # Shaping potential in [0, 1]: closeness to the bullet line of a living
    # enemy, plus a clear line of fire; for Tom, a clear line through the gap.
    closeness = torch.exp(-(band_mid[:, None] - ecy).abs() / 60)
    enemy_potential = torch.where(alive, 0.5 * closeness + 0.5 * (aligned & clear).double(), 0.0).amax(1)
    potential = torch.where(on, boss_clear.double(), enemy_potential)
    return obs, potential
