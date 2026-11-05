"""Vectorised torch port of ``src.headless.engine`` for thousands of games at once.

Same rules, constants, units and update order as ``HeadlessEnv`` (OLD difficulty:
seven jungle tableaux, Tom, then a new loop with +3 danger). State is float64 so
positions follow the reference arithmetic; random draws follow the reference
*distributions*, not its Python ``Random`` stream. Parity with the reference
kernel is checked tick by tick in ``tests/test_vector_engine.py``.

Entity lists become fixed-capacity slots with masks. List order, which decides
which bullet is consumed first, is kept with a per-game birth sequence number.
The engine runs on CPU or CUDA; it never synchronises with the host on CUDA.
"""

import torch

from src.headless.engine import OLD_WORLD_LEVELS, level_geometry
from src.system import mechanics as m

LEVEL_COUNT = 6  # 0 = boss arena, 1..5 = jungle tableaux used by OLD difficulty
MAX_BLOCKS = 11
MAX_ENEMIES = 6
MAX_BULLETS = 6
MAX_ENEMY_BULLETS = 32
NO_HIT = -1_000_000
_INF_SEQ = 2 ** 62

PW, PH = m.PLAYER_SIZE
PBW, PBH = m.PLAYER_BULLET_SIZE
EBW, EBH = m.ENEMY_BULLET_SIZE
BOSS_X, BOSS_Y = m.BOSS_POSITION
BOSS_W, BOSS_H = m.BOSS_SIZE
SHIELD_X, SHIELD_W, SHIELD_H = 790, 50, 150  # shield i (i != hole) at y = 575 - 200 i
SHOT_TICKS = m.SHOT_DELAY_MS * 60  # compared with elapsed_ticks * 1000
INVULNERABLE_TICKS = m.INVULNERABILITY_MS * 60


def overlaps(ax, ay, aw, ah, bx, by, bw, bh):
    return (ax < bx + bw) & (ax + aw > bx) & (ay < by + bh) & (ay + ah > by)


class LevelTables:
    """Static geometry of every level, padded to MAX_BLOCKS, in reference order."""

    def __init__(self, device):
        f64 = dict(dtype=torch.float64, device=device)
        shape = (LEVEL_COUNT, MAX_BLOCKS)
        self.x, self.y, self.w, self.h = (torch.zeros(shape, **f64) for _ in range(4))
        self.transparent = torch.zeros(shape, dtype=torch.bool, device=device)
        self.valid = torch.zeros(shape, dtype=torch.bool, device=device)
        self.spawnable = torch.zeros(shape, dtype=torch.bool, device=device)
        self.spawn_x = torch.zeros(LEVEL_COUNT, **f64)
        self.spawn_y = torch.zeros(LEVEL_COUNT, **f64)
        for level_id in range(LEVEL_COUNT):
            blocks, spawn, _ = level_geometry(level_id)
            if len(blocks) > MAX_BLOCKS:
                raise ValueError(f"level {level_id} has more than {MAX_BLOCKS} blocks")
            for i, b in enumerate(blocks):
                self.x[level_id, i], self.y[level_id, i] = b.x, b.y
                self.w[level_id, i], self.h[level_id, i] = b.w, b.h
                self.transparent[level_id, i] = b.transparent
                self.spawnable[level_id, i] = b.spawnable
                self.valid[level_id, i] = True
            self.spawn_x[level_id], self.spawn_y[level_id] = spawn
        self.spawn_count = self.spawnable.sum(1)
        if int(self.spawn_count.max()) > MAX_ENEMIES:
            raise ValueError("more spawnable platforms than enemy slots")


class VectorEngine:
    """``num_envs`` independent games advanced together by ``step(actions)``.

    ``actions`` are the reference integer bit masks (LEFT 1, RIGHT 2, JUMP 4,
    DOWN 8, FIRE 16). Finished games stay frozen until ``reset(mask)``; there
    is no hidden auto-reset. Per-decision events are returned by ``step`` and
    only count ticks before a death, like the reference kernel which stops a
    decision immediately on death.
    """

    def __init__(self, num_envs, *, device="cpu", frame_skip=4, episode_limit=1800,
                 boss_mode=False, seed=0):
        if num_envs < 1:
            raise ValueError("num_envs must be positive")
        if type(frame_skip) is not int or frame_skip < 1:
            raise ValueError("frame_skip must be a positive integer")
        if episode_limit is not None and (type(episode_limit) is not int or episode_limit < 1):
            raise ValueError("episode_limit must be a positive integer or None")
        self.n = num_envs
        self.device = torch.device(device)
        self.frame_skip = frame_skip
        self.episode_limit = episode_limit
        self.boss_mode = boss_mode
        # On CUDA, branches never read device values: every masked update runs.
        self._host_branches = self.device.type == "cpu"
        self.gen = torch.Generator(device=self.device)
        self.gen.manual_seed(seed)
        self.tables = LevelTables(self.device)
        self._allocate()
        self.reset(torch.ones(self.n, dtype=torch.bool, device=self.device))

    # ------------------------------------------------------------------ state
    def _allocate(self):
        n, d = self.n, self.device
        f = lambda *s: torch.zeros(n, *s, dtype=torch.float64, device=d)
        i = lambda *s: torch.zeros(n, *s, dtype=torch.int64, device=d)
        b = lambda *s: torch.zeros(n, *s, dtype=torch.bool, device=d)
        # Player
        self.px, self.py, self.speed, self.grav, self.kb, self.dirn = f(), f(), f(), f(), f(), f()
        self.health, self.score, self.last_shot, self.last_hit = i(), i(), i(), i()
        self.on_ground, self.shield = b(), b()
        # Progress
        self.level_id, self.level, self.world, self.danger = i(), i(), i(), i()
        self.ticks, self.steps = i(), i()
        self.boss_damage, self.bosses_defeated, self.levels_cleared = i(), i(), i()
        self.terminated, self.truncated = b(), b()
        self.seq = i()
        # Geometry of the current level
        self.bx, self.by, self.bw, self.bh = (f(MAX_BLOCKS) for _ in range(4))
        self.b_trans, self.b_valid = b(MAX_BLOCKS), b(MAX_BLOCKS)
        # Enemies (slot order = reference list order)
        self.e_x, self.e_y, self.e_w, self.e_h = (f(MAX_ENEMIES) for _ in range(4))
        self.e_plx, self.e_plw, self.e_dir = f(MAX_ENEMIES), f(MAX_ENEMIES), f(MAX_ENEMIES)
        self.e_kind, self.e_last = i(MAX_ENEMIES), i(MAX_ENEMIES)
        self.e_alive = b(MAX_ENEMIES)
        # Projectiles: x, y, velocity, active, birth sequence
        self.pb_x, self.pb_y, self.pb_v = (f(MAX_BULLETS) for _ in range(3))
        self.pb_act, self.pb_seq = b(MAX_BULLETS), i(MAX_BULLETS)
        self.qb_x, self.qb_y, self.qb_v = (f(MAX_ENEMY_BULLETS) for _ in range(3))
        self.qb_act, self.qb_seq = b(MAX_ENEMY_BULLETS), i(MAX_ENEMY_BULLETS)
        # Boss
        self.boss_on, self.boss_shields = b(), b()
        self.boss_health, self.boss_last_hit, self.boss_last_shot, self.boss_hole = i(), i(), i(), i()
        self._enemy_slots = torch.arange(MAX_ENEMIES, device=d)
        self._bullet_slots = torch.arange(MAX_BULLETS, device=d)
        self._enemy_bullet_slots = torch.arange(MAX_ENEMY_BULLETS, device=d)

    @property
    def done(self):
        return self.terminated | self.truncated

    def _rand(self, *shape):
        return torch.rand(*shape, generator=self.gen, device=self.device, dtype=torch.float64)

    # ------------------------------------------------------------------ reset
    def reset(self, mask, *, world=None, level=None):
        """Start new games where ``mask`` is true.

        ``world``/``level`` (int64 per game) optionally start later in a run:
        level 1..7 is a tableau, level 8 is Tom. Without them a game starts
        exactly like ``HeadlessEnv.reset`` (world 0, tableau 1 or Tom in boss mode).
        """
        mk = mask
        for t in (self.speed, self.grav, self.kb, self.score, self.last_shot, self.level,
                  self.world, self.danger, self.ticks, self.steps, self.boss_damage,
                  self.bosses_defeated, self.levels_cleared, self.seq):
            t.masked_fill_(mk, 0)
        self.dirn.masked_fill_(mk, -1)
        self.health.masked_fill_(mk, 3)
        self.last_hit.masked_fill_(mk, NO_HIT)
        self.level_id.masked_fill_(mk, -1)
        for t in (self.on_ground, self.shield, self.terminated, self.truncated, self.boss_on):
            t.masked_fill_(mk, False)
        self.pb_act.masked_fill_(mk[:, None], False)
        boss = mk if self.boss_mode else torch.zeros_like(mk)
        if world is not None:
            self.world = torch.where(mk, world, self.world)
        if level is not None:
            start_boss = mk & (level > OLD_WORLD_LEVELS)
            self.level = torch.where(mk, torch.where(start_boss, OLD_WORLD_LEVELS, level - 1), self.level)
            boss = boss | start_boss
        self._load_level(mk, boss)

    def _load_level(self, mask, boss):
        """Reference ``_load_level`` for games in ``mask``; ``boss`` selects Tom."""
        t = self.tables
        normal = mask & ~boss
        self.qb_act &= ~mask[:, None]
        self.e_alive &= ~mask[:, None]
        # Tom
        self.boss_on = torch.where(mask, boss, self.boss_on)
        self.boss_health = torch.where(boss, 10, self.boss_health)
        self.boss_last_hit = torch.where(boss, NO_HIT, self.boss_last_hit)
        self.boss_last_shot = torch.where(boss, NO_HIT, self.boss_last_shot)
        self.boss_hole = torch.where(boss, 0, self.boss_hole)
        self.boss_shields = torch.where(boss, False, self.boss_shields)
        self.speed = torch.where(boss, 0.0, self.speed)
        self.kb = torch.where(boss, 0.0, self.kb)
        # Jungle: uniform tableau among 1..5, different from the previous one.
        prev = self.level_id
        repeatable = (prev >= 1) & (prev <= 5)
        r = (self._rand(self.n) * torch.where(repeatable, 4, 5)).long() + 1
        new_id = torch.where(repeatable, r + (r >= prev).long(), r)
        self.level_id = torch.where(normal, new_id, torch.where(boss, 0, self.level_id))
        self.level = torch.where(normal, self.level + 1, self.level)
        self.danger = torch.where(normal, self.world * 3 + self.level, self.danger)
        lid = self.level_id.clamp(min=0)
        m2 = mask[:, None]
        self.bx = torch.where(m2, t.x[lid], self.bx)
        self.by = torch.where(m2, t.y[lid], self.by)
        self.bw = torch.where(m2, t.w[lid], self.bw)
        self.bh = torch.where(m2, t.h[lid], self.bh)
        self.b_trans = torch.where(m2, t.transparent[lid], self.b_trans)
        self.b_valid = torch.where(m2, t.valid[lid], self.b_valid)
        self.px = torch.where(mask, t.spawn_x[lid], self.px)
        self.py = torch.where(mask, t.spawn_y[lid], self.py)
        # rng.sample(spawnable, k): a uniformly random ordered subset of platforms.
        keys = torch.where(t.spawnable[lid], self._rand(self.n, MAX_BLOCKS), 2.0)
        order = keys.argsort(1)[:, :MAX_ENEMIES]
        count = torch.minimum(self.danger, t.spawn_count[lid])
        slot = normal[:, None] & (self._enemy_slots < count[:, None])
        sbx, sby, sbw = self.bx.gather(1, order), self.by.gather(1, order), self.bw.gather(1, order)
        x = sbx + (self._rand(self.n, MAX_ENEMIES) * (sbw - m.KNIGHT_SIZE[0] // 2 + 1)).floor()
        chicken = self._rand(self.n, MAX_ENEMIES) < 0.25
        kind = torch.where(chicken, 2, (self.danger > 5).long()[:, None])
        w = torch.where(chicken, float(m.CHICKEN_SIZE[0]), float(m.KNIGHT_SIZE[0]))
        h = torch.where(chicken, float(m.CHICKEN_SIZE[1]), float(m.KNIGHT_SIZE[1]))
        self.e_x = torch.where(slot, x, self.e_x)
        self.e_y = torch.where(slot, sby - h, self.e_y)
        self.e_w = torch.where(slot, w, self.e_w)
        self.e_h = torch.where(slot, h, self.e_h)
        self.e_kind = torch.where(slot, kind, self.e_kind)
        self.e_plx = torch.where(slot, sbx, self.e_plx)
        self.e_plw = torch.where(slot, sbw, self.e_plw)
        self.e_last = torch.where(slot, 0, self.e_last)
        self.e_dir = torch.where(slot, 1.0, self.e_dir)
        self.e_alive = torch.where(m2, slot, self.e_alive)

    # ------------------------------------------------------------- utilities
    def _hit_player(self, mask):
        ok = mask & ((self.ticks - self.last_hit) * 1000 > INVULNERABLE_TICKS)
        self.health = self.health - ok.long()
        self.last_hit = torch.where(ok, self.ticks, self.last_hit)

    def _spawn(self, prefix, slots, do, x, y, v):
        act = getattr(self, prefix + "_act")
        free = ~act
        do = do & free.any(1)
        onehot = (slots == free.int().argmax(1)[:, None]) & do[:, None]
        setattr(self, prefix + "_x", torch.where(onehot, x[:, None], getattr(self, prefix + "_x")))
        setattr(self, prefix + "_y", torch.where(onehot, y[:, None], getattr(self, prefix + "_y")))
        setattr(self, prefix + "_v", torch.where(onehot, v[:, None], getattr(self, prefix + "_v")))
        setattr(self, prefix + "_seq", torch.where(onehot, self.seq[:, None], getattr(self, prefix + "_seq")))
        setattr(self, prefix + "_act", act | onehot)
        self.seq = self.seq + do.long()

    @staticmethod
    def _first(mask, seq):
        """One-hot of the earliest-born candidate per game, and whether one exists."""
        s = torch.where(mask, seq, _INF_SEQ)
        best = s.min(1, keepdim=True).values
        return mask & (seq == best), best[:, 0] < _INF_SEQ

    # ------------------------------------------------------------------ tick
    def _update_player(self, action):
        t = self.ticks
        px, py = self.px, self.py
        # Incoming enemy bullets, in list order, until the first unblocked hit.
        can_hit = (t - self.last_hit) * 1000 > INVULNERABLE_TICKS
        ov = self.qb_act & overlaps(px[:, None], py[:, None], PW, PH, self.qb_x, self.qb_y, EBW, EBH)
        edge = torch.where(self.dirn == -1, px, px + PW)[:, None]
        cy = (py + PH / 2)[:, None]
        qx, qy = self.qb_x, self.qb_y
        blocked = (self.shield[:, None] & (qx <= edge) & (edge < qx + EBW)
                   & (((qy <= cy) & (cy < qy + EBH)) | ((qy <= py[:, None]) & (py[:, None] < qy + EBH))))
        first = torch.where(ov & ~blocked, self.qb_seq, _INF_SEQ).min(1, keepdim=True).values
        self.qb_act = self.qb_act & ~(ov & (self.qb_seq <= first) & can_hit[:, None])
        self._hit_player(can_hit & (first[:, 0] < _INF_SEQ))

        kb = self.kb * 0.85
        kb = kb.masked_fill(kb.abs() < 0.1, 0.0)
        grav = self.grav
        floor = (py + PH >= m.HEIGHT) & (grav > 0)
        grav = grav.masked_fill(floor, 0.0)
        on_ground = floor
        py = py.masked_fill(~floor & (py + PH + grav / 60 > m.HEIGHT), float(m.HEIGHT - PH))
        speed = self.speed
        # pygame.Rect collisions truncate the player's float rectangle. The x
        # position does not change during the scan, so x tests are batched.
        ipx = torch.trunc(px)[:, None]
        right = torch.trunc(px + PW)[:, None]
        bx, b_right = self.bx, self.bx + self.bw
        x_overlap = self.b_valid & (ipx < b_right) & (ipx + PW > bx)
        left_x = self.b_valid & (bx <= ipx) & (ipx < b_right)
        right_x = self.b_valid & ~left_x & (bx <= right) & (right < b_right)
        by, b_bottom = self.by, self.by + self.bh
        b_mid, land_y, ledge = self.by + self.bh / 2, self.by + (1 - PH), self.by + 2
        for i in range(MAX_BLOCKS):
            top = by[:, i]
            ipy = torch.trunc(py)
            ov = x_overlap[:, i] & (ipy < b_bottom[:, i]) & (ipy + PH > top)
            land = ov & (grav >= 0) & (py + PH + grav > top) & (top > py + PH / 2)
            bump = ov & (grav < 0) & (py > b_mid[:, i])
            py = torch.where(land, land_y[:, i], py)
            grav = grav.masked_fill(land, 0.0).masked_fill(bump, 1.0)
            on_ground = on_ground | land
            mid_y = torch.trunc(py + PH / 2)
            side = (top <= mid_y) & (mid_y < b_bottom[:, i]) & (py + PH > ledge[:, i])
            left_wall = side & left_x[:, i]
            right_wall = side & right_x[:, i]
            speed = speed.masked_fill((left_wall & (speed == -m.PLAYER_SPEED))
                                      | (right_wall & (speed == m.PLAYER_SPEED)), 0.0)
            kb = torch.where((left_wall & (kb < 0)) | (right_wall & (kb > 0)), kb * -0.5, kb)
        grav = torch.where(on_ground, grav, grav + m.GRAVITY / 60)
        py = py + grav / 60
        px = px + (speed + kb) / 60
        alive = self.health > 0
        # Controls (dead players keep their last shield flag, like the reference).
        self.shield = self.shield & ~alive
        jump = alive & ((action & 4) != 0) & on_ground
        grav = torch.where(jump, -float(m.JUMP_FORCE), grav)
        py = torch.where(jump, py - m.JUMP_FORCE / 60, py)
        on_ground = on_ground & ~jump
        down = alive & ((action & 8) != 0)
        grav = torch.where(down & ~on_ground, grav.clamp(min=m.MAX_FALL_SPEED), grav)
        guard = down & on_ground
        self.shield = self.shield | guard
        left = alive & ~down & ((action & 1) != 0)
        right_move = alive & ~down & ~left & ((action & 2) != 0)
        speed = torch.where(~alive | guard | (alive & ~down & ~left & ~right_move), 0.0, speed)
        speed = torch.where(left, -float(m.PLAYER_SPEED), torch.where(right_move, float(m.PLAYER_SPEED), speed))
        self.dirn = torch.where(left, -1.0, torch.where(right_move, 1.0, self.dirn))
        fire = alive & ((action & 16) != 0) & ((t - self.last_shot) * 1000 > SHOT_TICKS)
        self._spawn("pb", self._bullet_slots, fire, px, py + 50, -self.dirn * m.PROJECTILE_SPEED)
        kb = torch.where(fire, self.dirn * m.KNOCKBACK_FORCE, kb)
        self.last_shot = torch.where(fire, t, self.last_shot)
        self.px, self.py, self.speed, self.grav, self.kb, self.on_ground = px, py, speed, grav, kb, on_ground

    def _update_boss(self):
        t = self.ticks
        on = self.boss_on
        delay = torch.where(self.boss_health <= 3, 700, 1000)
        shoot = on & ((t - self.boss_last_shot) * 1000 > delay * 60)
        self._spawn("qb", self._enemy_bullet_slots, shoot, torch.full_like(self.py, BOSS_X - 100.0),
                    self.py, torch.full_like(self.py, -float(m.PROJECTILE_SPEED)))
        self.boss_last_shot = torch.where(shoot, t, self.boss_last_shot)
        can = on & ((t - self.boss_last_hit) > 120)
        ov = can[:, None] & self.pb_act & overlaps(self.pb_x, self.pb_y, PBW, PBH, BOSS_X, BOSS_Y, BOSS_W, BOSS_H)
        onehot, hit = self._first(ov, self.pb_seq)
        self.pb_act = self.pb_act & ~onehot
        self.boss_health = self.boss_health - hit.long()
        self.boss_damage = self.boss_damage + hit.long()
        self.boss_last_hit = torch.where(hit, t, self.boss_last_hit)
        r = (self._rand(self.n) < 0.5).long()
        self.boss_hole = torch.where(hit, r + (r >= self.boss_hole).long(), self.boss_hole)
        self.boss_shields = self.boss_shields | hit

    def _update_enemies(self):
        t = self.ticks
        ppx, ppy = self.px, self.py
        shots = self._rand(self.n, MAX_ENEMIES)
        for e in range(MAX_ENEMIES):
            alive = self.e_alive[:, e]
            kind = self.e_kind[:, e]
            ew, eh, ey = self.e_w[:, e], self.e_h[:, e], self.e_y[:, e]
            chicken = alive & (kind == 2)
            direction = self.e_dir[:, e]
            ex = self.e_x[:, e] + torch.where(chicken, m.CHICKEN_SPEED / 60 * direction, 0.0)
            plx, plw = self.e_plx[:, e], self.e_plw[:, e]
            turn_left = chicken & (ex + ew > plx + plw - 15)
            turn_right = chicken & ~turn_left & (ex < plx + 15)
            direction = torch.where(turn_left, -1.0, torch.where(turn_right, 1.0, direction))
            touch = chicken & overlaps(ex, ey, ew, eh, ppx, ppy, PW, PH)
            self._hit_player(touch)
            alive = alive & ~touch
            angry = kind == 1
            lo = torch.where(angry, 1120, 1600)
            hi = torch.where(angry, 1540, 2200)
            threshold = lo + (shots[:, e] * (hi - lo + 1)).long()
            shoot = (alive & (kind != 2) & ((t - self.e_last[:, e]) * 1000 > threshold * 60)
                     & (self.health > 0))
            aim = torch.where(ex + ew / 2 > ppx + PW / 2, -1.0, 1.0)
            direction = torch.where(shoot, aim, direction)
            self._spawn("qb", self._enemy_bullet_slots, shoot, ex + ew / 2, ey + eh / 2,
                        aim * m.PROJECTILE_SPEED)
            self.e_last[:, e] = torch.where(shoot, t, self.e_last[:, e])
            ov = alive[:, None] & self.pb_act & overlaps(self.pb_x, self.pb_y, PBW, PBH,
                                                        ex[:, None], ey[:, None], ew[:, None], eh[:, None])
            onehot, killed = self._first(ov, self.pb_seq)
            self.pb_act = self.pb_act & ~onehot
            self.score = self.score + torch.where(killed, torch.where(angry, 150, 100), 0)
            self.e_x[:, e] = ex
            self.e_dir[:, e] = direction
            self.e_alive[:, e] = alive & ~killed

    def _advance_projectiles(self, prefix, w, h, shields):
        x = getattr(self, prefix + "_x") + getattr(self, prefix + "_v") / 60
        y = getattr(self, prefix + "_y")
        keep = getattr(self, prefix + "_act") & (x <= m.WIDTH) & (x + w >= 0)
        solid = (self.b_valid & ~self.b_trans)[:, None, :]
        hit_block = solid & overlaps(x[:, :, None], y[:, :, None], w, h, self.bx[:, None, :],
                                     self.by[:, None, :], self.bw[:, None, :], self.bh[:, None, :])
        keep = keep & ~hit_block.any(2)
        if shields:
            for i in range(3):
                present = (self.boss_on & self.boss_shields & (self.boss_hole != i))[:, None]
                keep = keep & ~(present & overlaps(x, y, w, h, SHIELD_X, 575 - 200 * i, SHIELD_W, SHIELD_H))
        setattr(self, prefix + "_x", x)
        setattr(self, prefix + "_act", keep)

    def _tick(self, action):
        self.ticks = self.ticks + 1
        self._update_player(action)
        if not self._host_branches or bool(self.boss_on.any()):
            self._update_boss()
        self._update_enemies()
        self._advance_projectiles("qb", EBW, EBH, False)
        self._advance_projectiles("pb", PBW, PBH, True)
        dead = self.health <= 0
        boss_won = ~dead & self.boss_on & (self.boss_health <= 0)
        cleared = ~dead & ~self.boss_on & ~self.e_alive.any(1)
        self.bosses_defeated = self.bosses_defeated + boss_won.long()
        self.levels_cleared = self.levels_cleared + cleared.long()
        if self.boss_mode:
            load = cleared
            won = boss_won
        else:
            self.world = self.world + boss_won.long()
            self.level = torch.where(boss_won, 0, self.level)
            load = cleared | boss_won
            won = torch.zeros_like(boss_won)
        if not self._host_branches or bool(load.any()):
            self._load_level(load, cleared & (self.level == OLD_WORLD_LEVELS))
        return won

    def step(self, actions):
        """Advance every game by one decision of ``frame_skip`` ticks.

        Returns per-decision event counts (int64 tensors) restricted to ticks
        executed before a terminal tick, matching the reference early stop.
        Games already finished must be reset first; their events are zero.
        """
        actions = actions.to(device=self.device, dtype=torch.int64)
        live = ~self.done
        zero = torch.zeros(self.n, dtype=torch.int64, device=self.device)
        events = {"score": zero, "levels_cleared": zero, "boss_damage": zero,
                  "bosses_defeated": zero, "health_lost": zero, "ticks": zero}
        for _ in range(self.frame_skip):
            before = (self.score, self.levels_cleared, self.boss_damage, self.bosses_defeated, self.health)
            won = self._tick(actions)
            gate = live.long()
            events["score"] = events["score"] + (self.score - before[0]) * gate
            events["levels_cleared"] = events["levels_cleared"] + (self.levels_cleared - before[1]) * gate
            events["boss_damage"] = events["boss_damage"] + (self.boss_damage - before[2]) * gate
            events["bosses_defeated"] = events["bosses_defeated"] + (self.bosses_defeated - before[3]) * gate
            events["health_lost"] = events["health_lost"] + (before[4] - self.health).clamp(min=0) * gate
            events["ticks"] = events["ticks"] + gate
            ended = live & ((self.health <= 0) | won)
            self.terminated = self.terminated | ended
            live = live & ~ended
            if self._host_branches and not bool(live.any()):
                break
        was_running = events["ticks"] > 0
        self.steps = self.steps + was_running.long()
        if self.episode_limit is not None:
            self.truncated = self.truncated | (was_running & ~self.terminated & (self.steps >= self.episode_limit))
        events["death"] = (was_running & self.terminated & (self.health <= 0)).long()
        return events
