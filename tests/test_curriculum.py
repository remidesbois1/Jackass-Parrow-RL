import unittest
import numpy as np
from gymnasium.utils.env_checker import check_env
from src.rl.curriculum import CurriculumEnv
from src.rl.env import JackassParrowEnv


class CurriculumTests(unittest.TestCase):
    def test_gym_contract_all_stages(self):
        for stage in range(6):
            env = CurriculumEnv(curriculum_stage=stage,episode_limit=10)
            check_env(env,skip_render_check=True)
            env.close()

    def test_ground_targets_reachable_both_directions(self):
        for seed in range(20):
            env = CurriculumEnv(curriculum_stage=0,episode_limit=300)
            env.reset(seed=seed)
            success = False
            for _ in range(300):
                dx = env.goal[0]-env.engine.player.rect.x
                move = (2 if dx>0 else 1) if abs(dx)>15 else 0
                _,_,done,trunc,info = env.step([move,0,0,0])
                if done or trunc:
                    success = info['is_success']
                    break
            self.assertTrue(success,seed)
            env.close()

    def test_progress_cannot_be_farmed_by_round_trips(self):
        env = CurriculumEnv(curriculum_stage=0)
        env.reset(seed=0)
        original = env.engine.player.rect.x
        halfway = (original+env.goal[0])/2
        env.engine.player.rect.x = halfway
        _,_,_,_,first = env.step([0,0,0,0])
        self.assertGreater(first['shaping_reward'],0)
        env.engine.player.rect.x = original
        env.step([0,0,0,0])
        env.engine.player.rect.x = halfway
        _,_,_,_,second = env.step([0,0,0,0])
        self.assertEqual(second['shaping_reward'],0)
        env.close()

    def test_platform_exercises_are_reachable(self):
        for seed in range(20):
            env = CurriculumEnv(curriculum_stage=1, episode_limit=360)
            env.reset(seed=seed)
            platform = env.engine.blocks[-1]
            for _ in range(360):
                p = env.engine.player
                dx = env.goal[0]-p.rect.x
                move = (2 if dx > 0 else 1) if abs(dx) > 15 else 0
                edge = platform.x if dx > 0 else platform.x+platform.w
                jump = int(p.on_ground and p.rect.y+p.rect.h > platform.y+8
                           and abs(p.rect.x + p.rect.w/2-edge) < 110)
                _,_,done,trunc,info = env.step([move,jump,0,0])
                if done or trunc:
                    break
            self.assertTrue(info['is_success'], seed)
            env.close()

    def test_shooting_success_stops_before_loading_another_level(self):
        env = CurriculumEnv(curriculum_stage=3)
        env.reset(seed=5)
        p = env.engine.player
        p.rect.x,p.rect.y = env.goal[0],env.goal[1]+1-p.rect.h
        p.direction = -1 if env.target.rect.x > p.rect.x else 1
        for _ in range(100):
            _,_,done,trunc,info = env.step([0,0,0,1])
            if done or trunc:
                break
        self.assertTrue(info['is_success'])
        self.assertEqual(info['score'],100)
        self.assertEqual(len(env.engine.enemies),0)
        env.close()

    def test_normal_physics_and_observation_parity(self):
        a = CurriculumEnv(curriculum_stage=5)
        b = JackassParrowEnv()
        ao,_ = a.reset(seed=24)
        bo,_ = b.reset(seed=24)
        np.testing.assert_array_equal(ao[:454],bo)
        rng = np.random.default_rng(4)
        for _ in range(80):
            action = [int(rng.integers(3)),*rng.integers(2,size=3).tolist()]
            ao,_,at,ax,ai = a.step(action)
            bo,_,bt,bx,bi = b.step(action)
            np.testing.assert_array_equal(ao[:454],bo)
            self.assertEqual((at,ax),(bt,bx))
            self.assertEqual(ai['score'],bi['score'])
            if at or ax:
                break
        a.close()
        b.close()


if __name__ == '__main__':
    unittest.main()
