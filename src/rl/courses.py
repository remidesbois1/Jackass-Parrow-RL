"""Multi-platform courses and geometry-guided transfer to the original maps.

Waypoints describe destinations only: the policy still chooses every button.
The v1 environment and checkpoints remain unchanged.
"""
from collections import deque
import math
import numpy as np
from gymnasium import spaces
from src.headless.engine import Enemy, Platform, Rect
from src.system import mechanics as m
from .curriculum import CurriculumEnv
from .env import JackassParrowEnv

SCHEMA = 'JackassParrowCourses-v2'
STAGES = ('stairs_low','stairs_high','zigzag','descent','course_shoot',
          'map_navigation','map_shoot','map_combat','normal')
TASKS = (1,1,1,1,3,1,3,4,5)


def platform_route(blocks, start, destination):
    """Conservative geometric graph, not an exact physics reachability oracle."""
    platforms = [b for b in blocks if 100 <= b.y <= 775 and b.w >= 100]
    if not platforms:
        return []
    sx, sy = start
    source = min(range(len(platforms)), key=lambda i: abs(platforms[i].y-sy)
                 + max(platforms[i].x-sx, sx-(platforms[i].x+platforms[i].w-75),0))
    target = min(range(len(platforms)),key=lambda i: abs(platforms[i].y-destination[1])
                 + max(platforms[i].x-destination[0],destination[0]-(platforms[i].x+platforms[i].w-75),0))
    parent = {source:None}
    queue = deque([source])
    while queue:
        i = queue.popleft()
        if i == target:
            break
        a = platforms[i]
        for j,b in enumerate(platforms):
            rise = a.y-b.y
            if j in parent or rise > 205 or rise < -380:
                continue
            gap = max(b.x-(a.x+a.w), a.x-(b.x+b.w),0)
            # Ballistic airborne time at destination height, with a safety margin.
            discriminant = m.JUMP_FORCE**2-2*m.GRAVITY*max(rise,0)
            reach = m.PLAYER_SPEED*(m.JUMP_FORCE+math.sqrt(max(0,discriminant)))/m.GRAVITY
            if gap+75 <= reach-20:
                parent[j]=i
                queue.append(j)
    if target not in parent:
        return []
    chain=[]
    cursor=target
    while parent[cursor] is not None:
        chain.append(cursor)
        cursor=parent[cursor]
    chain.reverse()
    points=[]
    px,py=sx,platforms[source].y
    previous=platforms[source]
    for i in chain:
        b=platforms[i]
        # Approach from outside the platform so jumping does not hit its underside.
        if b.y < py-8:
            left = abs(px-(b.x-100)) <= abs(px-(b.x+b.w+25))
            approach=b.x-100 if left else b.x+b.w+25
            if previous.x <= approach <= previous.x+previous.w-75:
                points.append((float(approach),float(py)))
            landing = b.x+25 if left else b.x+b.w-100
        else:
            landing=float(np.clip(px,b.x+15,b.x+b.w-90))
        points.append((float(landing),float(b.y)))
        px,py=landing,b.y
        previous=b
    points.append(tuple(map(float,destination)))
    return points


class CourseEnv(CurriculumEnv):
    def __init__(self, *, course_stage=0, replay_probability=0.1, **kwargs):
        if not 0 <= course_stage < len(STAGES):
            raise ValueError('invalid course stage')
        self.course_stage=self.requested_course=int(course_stage)
        self.route=[]
        self.route_index=0
        self.route_found=True
        self.final_goal=(0.0,0.0)
        self.checkpoints=0
        super().__init__(curriculum_stage=TASKS[course_stage],replay_probability=replay_probability,**kwargs)
        self.observation_space=spaces.Box(-10,10,shape=(474,),dtype=np.float32)

    def set_stage(self,stage,shaping_strength=1.0):
        if not 0 <= stage < len(STAGES) or not 0 <= shaping_strength <= 1:
            raise ValueError('invalid course settings')
        self.requested_course=int(stage)
        self.shaping_strength=shaping_strength

    def _install_route(self, points):
        self.route=points
        self.route_index=0
        self.hold=0
        self.aim_paid=False
        self.goal=points[0] if points else self.final_goal
        self.best_distance=self._distance()
        self.engine.navigation_goal=self.goal

    def _plan_enemy(self):
        self._select_target()
        self.final_goal=self.goal
        if self.target is not None and self.stage == 1:
            self.final_goal=(self.target.rect.x,self.target.rect.y+self.target.rect.h)
        if self.target is not None and hasattr(self.target,'platform'):
            b=self.target.platform
            self.final_goal=(float(np.clip(self.final_goal[0],b.x+5,b.x+b.w-80)),float(b.y))
        p=self.engine.player.rect
        points=platform_route(self.engine.blocks,(p.x,p.y+p.h),self.final_goal)
        self.route_found=bool(points)
        self._install_route(points or [self.final_goal])

    def reset(self, *, seed=None, options=None):
        self.engine.exercise_active=False
        self.target=None
        JackassParrowEnv.reset(self,seed=seed,options=options)
        self.course_stage=self.requested_course
        if self.course_stage > 0 and self.np_random.random() < self.replay_probability:
            self.course_stage=int(self.np_random.integers(self.course_stage))
        self.stage=TASKS[self.course_stage]
        e=self.engine
        e.stage=self.stage
        self.checkpoints=0
        self.route_found=True
        if self.course_stage < 5:
            count=2 if self.course_stage == 0 else int(self.np_random.integers(3,5))
            rise=int(self.np_random.choice([90,110])) if self.course_stage == 0 else int(self.np_random.choice([140,160]))
            platforms=[]
            mirror=bool(self.np_random.integers(2))
            zigzag=self.course_stage >= 2
            for i in range(count):
                x=(290+i*150) if not zigzag else (290 if i%2==0 else 590)
                x+=int(self.np_random.integers(-15,16))
                if mirror:
                    x=1280-x-230
                platforms.append(Platform(x,775-(i+1)*rise,230,25,True,True))
            floor=Platform(-10,775,1300,50)
            e.blocks=(floor,Platform(-60,-425,50,1400),Platform(1290,-425,50,1400),*platforms)
            px=1100 if mirror else 100
            e.player.rect.x,e.player.rect.y=px,776-e.player.rect.h
            e.player.on_ground=True
            if self.course_stage == 3:
                top=platforms[-1]
                e.player.rect.x,e.player.rect.y=top.x+75,top.y+1-e.player.rect.h
                tx=150 if mirror else 1050
                target_platform=floor
            else:
                target_platform=platforms[-1]
                tx=target_platform.x+120
            e.enemies=[Enemy(Rect(tx,target_platform.y-90,75,90),0,target_platform)]
            e.bullets.clear()
            e.enemy_bullets.clear()
            e.boss=None
            e.exercise_active=True
            self._select_target()
            if self.course_stage == 4:
                # Reach the same platform before learning rear-facing shots.
                self.final_goal=(target_platform.x+20,target_platform.y)
            else:
                self.final_goal=(float(tx),float(target_platform.y))
            # The descent visits every ledge rather than simply dropping to the floor.
            if self.course_stage == 3:
                points=[(float(b.x+75),float(b.y)) for b in reversed(platforms[:-1])]
                points.append(self.final_goal)
            else:
                points=[]
                previous=floor
                px=e.player.rect.x
                for b in platforms:
                    left=px < b.x+b.w/2
                    approach=b.x-100 if left else b.x+b.w+25
                    if previous.x <= approach <= previous.x+previous.w-75:
                        points.append((float(approach),float(previous.y)))
                    landing=b.x+30 if left else b.x+b.w-105
                    points.append((float(landing),float(b.y)))
                    px=landing
                    previous=b
                points.append(self.final_goal)
            self._install_route(points)
        else:
            e.exercise_active=self.course_stage < 8
            self._plan_enemy()
        e.course_title=STAGES[self.course_stage]
        return self._result()

    def _result(self,score_delta=0):
        obs,info=super()._result(score_delta)
        p=self.engine.player.rect
        extra=np.array([self.route_index/max(1,len(self.route)),len(self.route)/16,
                        (self.final_goal[0]-p.x)/1280,(self.final_goal[1]-p.y-p.h)/800,
                        float(self.route_found),self.course_stage/8],dtype=np.float32)
        info.update(course_stage=self.course_stage,checkpoints=self.checkpoints,route_found=self.route_found)
        return np.concatenate((obs,np.clip(extra,-10,10))),info

    def step(self,action):
        health=self.engine.player.health
        old_target=self.target
        _,score,terminated,truncated,_=JackassParrowEnv.step(self,action)
        e,p=self.engine,self.engine.player
        progress=max(0,self.best_distance-self._distance())
        self.best_distance=min(self.best_distance,self._distance())
        reached=p.on_ground and abs(p.rect.x-self.goal[0])<35 and abs(p.rect.y+p.rect.h-self.goal[1])<8
        self.hold=self.hold+1 if reached else 0
        checkpoint_reward=0.0
        if self.hold >= 3 and self.route_index < len(self.route):
            self.route_index+=1
            self.checkpoints+=1
            checkpoint_reward=2.0
            if self.route_index < len(self.route):
                self.goal=self.route[self.route_index]
                self.best_distance=self._distance()
            self.hold=0
        route_complete=self.route_index >= len(self.route)
        success=(route_complete if self.stage == 1 else score>0) and p.health>0
        if self.course_stage < 8 and success:
            e.terminated, e.truncated=True,False
            terminated,truncated=True,False
            self._needs_reset=True
        reward=score*0.02-0.5*max(0,health-p.health)-3*float(p.health<=0)-0.001
        shaping=4*progress+checkpoint_reward
        if self.stage >= 3 and route_complete and self._aligned() and not self.aim_paid:
            self.aim_paid=True
            shaping+=1
        reward+=self.shaping_strength*shaping
        if self.course_stage < 8 and success:
            reward+=10
        if self.course_stage == 8 and old_target is not None and not any(old_target is x for x in e.enemies) and old_target is not e.boss:
            self._plan_enemy()
        e.navigation_goal=self.goal
        obs,info=self._result(score)
        info.update(is_success=bool(success if self.course_stage < 8 else e.levels_cleared>0),
                    shaping_reward=self.shaping_strength*shaping)
        return obs,float(reward),terminated,truncated,info
