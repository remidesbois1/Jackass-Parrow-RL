import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import torch
from stable_baselines3 import PPO
from src.rl.courses import CourseEnv, SCHEMA
from src.rl.env import JackassParrowEnv
from src.rl.transfer import initialize_without_guidance


class UnguidedTransferTests(unittest.TestCase):
    def test_guidance_columns_removed_and_shared_weights_preserved(self):
        guided_env=CourseEnv(course_stage=8,replay_probability=0)
        plain_env=JackassParrowEnv()
        try:
            guided=PPO('MlpPolicy',guided_env,n_steps=8,batch_size=8,seed=2,
                       policy_kwargs={'net_arch':[128,128]},device='cpu')
            plain=PPO('MlpPolicy',plain_env,n_steps=8,batch_size=8,seed=3,
                      policy_kwargs={'net_arch':[128,128]},device='cpu')
            with tempfile.TemporaryDirectory() as folder:
                path=Path(folder)
                guided.save(path/'model')
                (path/'config.json').write_text(json.dumps({'schema':SCHEMA}),encoding='utf-8')
                initialize_without_guidance(plain,path/'model.zip')
                obs,_=plain_env.reset(seed=15)
                padded=np.pad(obs,(0,20))
                with torch.no_grad():
                    a,v,p=plain.policy(torch.as_tensor(obs[None]),deterministic=True)
                    a2,v2,p2=guided.policy(torch.as_tensor(padded[None]),deterministic=True)
                torch.testing.assert_close(a,a2)
                torch.testing.assert_close(v,v2)
                torch.testing.assert_close(p,p2)
                self.assertEqual(plain.policy.mlp_extractor.policy_net[0].in_features,454)
                self.assertFalse(hasattr(plain_env.engine,'navigation_goal'))
        finally:
            plain_env.close()
            guided_env.close()


if __name__=='__main__':
    unittest.main()
