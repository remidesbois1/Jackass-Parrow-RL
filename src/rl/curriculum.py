"""Versioned skill curriculum; the production engine is unchanged in normal mode."""
import numpy as np
from gymnasium import spaces
from src.headless.engine import HeadlessEnv, Enemy, Platform, Rect
from src.system import mechanics as m
from .env import JackassParrowEnv
from .observations import OBSERVATION_SIZE

SCHEMA = "JackassParrowCurriculum-v1"
STAGES = ("move", "platform", "aim", "shoot", "combat", "normal")


class ExerciseEngine(HeadlessEnv):
    stage = 5
    exercise_active = False

    def _load_level(self, *, boss=False):
        if self.exercise_active and self.stage < 5:
            self.terminated = True
        else:
            super()._load_level(boss=boss)

    def _update_enemies(self):
        if self.exercise_active and self.stage < 3:
            return  # visible, harmless targets for locomotion exercises
        if self.exercise_active and self.stage == 3:
            for enemy in self.enemies:
                enemy.last_shot = self.ticks  # static shooting exercise, no enemy fire
        super()._update_enemies()


class CurriculumEnv(JackassParrowEnv):
    def __init__(self, *, curriculum_stage=0, replay_probability=0.0,
                 shaping_strength=1.0, **kwargs):
        self.stage = self.requested_stage = int(curriculum_stage)
        if not 0 <= self.stage < len(STAGES):
            raise ValueError("invalid curriculum stage")
        if not 0 <= replay_probability <= 1 or not 0 <= shaping_strength <= 1:
            raise ValueError("replay probability and shaping strength must be in [0,1]")
        self.replay_probability = replay_probability
        self.shaping_strength = shaping_strength
        self.target = None
        self.goal = (0.0, 0.0)
        self.best_distance = 0.0
        self.hold = 0
        self.aim_paid = False
        super().__init__(**kwargs)
        self.engine = ExerciseEngine(config=self.engine.config)
        # 4 relative coordinates, 6 stage flags, progress memory, hold, aim flag, strength
        self.observation_space = spaces.Box(-10, 10, shape=(OBSERVATION_SIZE + 14,), dtype=np.float32)

    def set_stage(self, stage, shaping_strength=1.0):
        if not 0 <= stage < len(STAGES) or not 0 <= shaping_strength <= 1:
            raise ValueError("invalid stage or shaping strength")
        self.requested_stage = int(stage)  # applies on next episode only
        self.shaping_strength = shaping_strength

    def _select_target(self):
        e, p = self.engine, self.engine.player.rect
        candidates = list(e.enemies) + ([e.boss] if e.boss is not None else [])
        self.target = min(candidates, key=lambda t: abs(t.rect.x-p.x)+abs(t.rect.y-p.y)) if candidates else None
        if self.target is not None:
            t = self.target.rect
            side = -1 if p.x < t.x else 1
            self.goal = (float(np.clip(t.x + side * 180, 50, 1150)), t.y + t.h)
        else:
            self.goal = (p.x, p.y+p.h)
        self.best_distance = self._distance()
        self.hold, self.aim_paid = 0, False

    def _distance(self):
        p = self.engine.player.rect
        return abs(p.x-self.goal[0])/1280 + 2*abs(p.y+p.h-self.goal[1])/800

    def _aligned(self):
        if self.target is None:
            return False
        e, p, t = self.engine, self.engine.player, self.target.rect
        y = p.rect.y + 50
        correct_facing = -p.direction == (1 if t.x > p.rect.x else -1)
        clear = not any(not b.transparent and b.y < y+23 and b.y+b.h > y
                        and b.x < max(p.rect.x,t.x) and b.x+b.w > min(p.rect.x,t.x)+p.rect.w
                        for b in e.blocks)
        return (p.on_ground and abs(p.rect.x-self.goal[0]) < 65
                and t.y < y+23 and t.y+t.h > y and correct_facing and clear)

    def reset(self, *, seed=None, options=None):
        self.engine.exercise_active = False
        self.target = None
        super().reset(seed=seed, options=options)
        self.stage = self.requested_stage
        if self.stage > 0 and self.np_random.random() < self.replay_probability:
            self.stage = int(self.np_random.integers(0, self.stage))
        e = self.engine
        e.stage = self.stage
        if self.stage < 5:
            elevated = self.stage == 1 or (self.stage >= 2 and self.np_random.random() < 0.5)
            floor = Platform(-10, 775, 1300, 50)
            px = int(self.np_random.integers(80, 180))
            tx = int(self.np_random.integers(500, 950))
            if self.np_random.random() < 0.5:
                px, tx = 1200-px, 1200-tx
            height = int(self.np_random.choice([80, 110, 140])) if elevated else 0
            platform = Platform(max(50, tx-250), 775-height, 500, 25, True, True) if elevated else floor
            e.blocks = (floor, Platform(-60,-425,50,1400), Platform(1290,-425,50,1400)) + ((platform,) if elevated else ())
            e.player.rect.x, e.player.rect.y = px, 776-m.PLAYER_SIZE[1]
            e.player.on_ground = True
            e.enemies = [Enemy(Rect(tx, platform.y-m.KNIGHT_SIZE[1], *m.KNIGHT_SIZE), 0, platform)]
            e.bullets.clear()
            e.enemy_bullets.clear()
            e.boss = None
            e.exercise_active = True
        self._select_target()
        if self.stage in (0,1):
            self.goal = (self.target.rect.x, self.target.rect.y+self.target.rect.h)
            self.best_distance = self._distance()
        return self._result()

    def _result(self, score_delta=0):
        obs, info = super()._result(score_delta)
        p = self.engine.player.rect
        t = self.target.rect if self.target is not None else p
        extra = [(self.goal[0]-p.x)/1280, (self.goal[1]-p.y-p.h)/800,
                 (t.x-p.x)/1280, (t.y-p.y)/800]
        extra += [float(self.stage == i) for i in range(6)]
        extra += [self.best_distance, min(self.hold/3,1), float(self.aim_paid), self.shaping_strength]
        info["curriculum_stage"] = self.stage
        return np.concatenate((obs, np.clip(np.array(extra,dtype=np.float32),-10,10))), info

    def step(self, action):
        previous_health = self.engine.player.health
        _, score, terminated, truncated, _ = super().step(action)
        e, p = self.engine, self.engine.player
        # High-water progress: retracing one's steps never creates another bonus.
        distance = self._distance()
        progress = max(0.0, self.best_distance-distance)
        self.best_distance = min(self.best_distance, distance)
        aligned = self._aligned()
        if self.stage in (0,1):
            reached = p.on_ground and abs(p.rect.x-self.goal[0]) < 40 and abs(p.rect.y+p.rect.h-self.goal[1]) < 8
        else:
            reached = aligned
        self.hold = self.hold+1 if reached else 0
        aim_reward = 0.0
        if self.hold >= 3 and not self.aim_paid:
            self.aim_paid = True
            aim_reward = 1.0 if self.stage >= 2 else 0.0
        success = (self.hold >= 3 if self.stage < 3 else score > 0) and p.health > 0
        if self.stage < 5 and success:
            terminated, truncated = True, False
            e.terminated, e.truncated = True, False
            self._needs_reset = True
        reward = score*0.02 - 0.5*max(0,previous_health-p.health) - 3.0*float(p.health <= 0) - 0.001
        reward += self.shaping_strength*(4*progress + aim_reward)
        if self.stage < 5 and success:
            reward += 10.0
        if self.stage == 5 and self.target is not None and not any(self.target is x for x in e.enemies) and self.target is not e.boss:
            self._select_target()  # no shaping reward for changing targets
        obs, info = self._result(score)
        info.update(is_success=bool(success if self.stage < 5 else e.levels_cleared > 0),
                    shaping_reward=self.shaping_strength*(4*progress+aim_reward))
        return obs, float(reward), terminated, truncated, info
