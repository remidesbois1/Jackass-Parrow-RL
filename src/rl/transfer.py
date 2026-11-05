"""Transfer only the shared game-state inputs from an existing guided policy."""
import json
from pathlib import Path
import torch
from stable_baselines3 import PPO
from .observations import OBSERVATION_SIZE


def initialize_without_guidance(model, checkpoint):
    path=Path(checkpoint)
    config=json.loads((path.parent/'config.json').read_text(encoding='utf-8'))
    if config.get('schema') not in ('JackassParrowCurriculum-v1','JackassParrowCourses-v2'):
        raise ValueError('expected a versioned curriculum checkpoint')
    previous=PPO.load(path,device='cpu')
    if previous.action_space != model.action_space or model.observation_space.shape != (OBSERVATION_SIZE,):
        raise ValueError('incompatible observation or action spaces')
    source=previous.policy.state_dict()
    destination=model.policy.state_dict()
    first_layers=('mlp_extractor.policy_net.0.weight','mlp_extractor.value_net.0.weight')
    with torch.no_grad():
        for key,value in destination.items():
            old=source[key]
            if key in first_layers:
                if old.ndim != 2 or old.shape[0] != value.shape[0] or old.shape[1] <= OBSERVATION_SIZE:
                    raise ValueError('incompatible first layer')
                value.copy_(old[:,:OBSERVATION_SIZE])
            elif value.shape == old.shape:
                value.copy_(old)
            else:
                raise ValueError(f'incompatible tensor {key}')
        model.policy.load_state_dict(destination)
