import unittest
import numpy as np
from gymnasium.utils.env_checker import check_env
from src.rl.courses import CourseEnv, platform_route
from src.rl.env import JackassParrowEnv


class CourseTests(unittest.TestCase):
    def test_gym_contract_every_course(self):
        for stage in range(9):
            env=CourseEnv(course_stage=stage,replay_probability=0,episode_limit=10)
            check_env(env,skip_render_check=True)
            env.close()

    def test_upward_courses_physically_reachable(self):
        for stage in range(3):
            for seed in range(20):
                env=CourseEnv(course_stage=stage,replay_probability=0,episode_limit=750)
                env.reset(seed=seed)
                for _ in range(750):
                    p=env.engine.player
                    dx=env.goal[0]-p.rect.x
                    move=(2 if dx>0 else 1) if abs(dx)>12 else 0
                    elevated=env.goal[1] < p.rect.y+p.rect.h-8
                    b=min(env.engine.blocks,key=lambda b:abs(b.y-env.goal[1])+max(b.x-env.goal[0],env.goal[0]-b.x-b.w,0))
                    edge=b.x if dx>0 else b.x+b.w
                    jump=int(elevated and p.on_ground and abs(p.rect.x+p.rect.w/2-edge)<115)
                    _,_,done,trunc,info=env.step([move,jump,0,0])
                    if done or trunc:
                        break
                self.assertTrue(info['is_success'],(stage,seed,env.route_index,env.route,env.engine.player.rect))
                self.assertGreaterEqual(info['checkpoints'],3)
                env.close()

    def test_normal_physics_stays_identical(self):
        a=CourseEnv(course_stage=8,replay_probability=0)
        b=JackassParrowEnv()
        ao,_=a.reset(seed=42)
        bo,_=b.reset(seed=42)
        np.testing.assert_array_equal(ao[:454],bo)
        rng=np.random.default_rng(99)
        for _ in range(100):
            action=[int(rng.integers(3)),*rng.integers(2,size=3).tolist()]
            ao,_,at,ax,ai=a.step(action)
            bo,_,bt,bx,bi=b.step(action)
            np.testing.assert_array_equal(ao[:454],bo)
            self.assertEqual((at,ax),(bt,bx))
            if at or ax:
                break
        a.close(); b.close()

    def test_checkpoint_is_paid_only_once(self):
        env=CourseEnv(course_stage=0,replay_probability=0)
        env.reset(seed=0)
        first=env.goal
        p=env.engine.player
        p.rect.x,p.rect.y=first[0],first[1]+1-p.rect.h
        for _ in range(3):
            env.step([0,0,0,0])
        self.assertEqual(env.checkpoints,1)
        p.rect.x,p.rect.y=first[0],first[1]+1-p.rect.h
        for _ in range(3):
            env.step([0,0,0,0])
        self.assertEqual(env.checkpoints,1)
        env.close()

    def test_course_marker_renders(self):
        env=CourseEnv(course_stage=0,render_mode='rgb_array')
        env.reset(seed=2)
        self.assertEqual(env.render().shape,(800,1280,3))
        env.close()


if __name__=='__main__':
    unittest.main()
