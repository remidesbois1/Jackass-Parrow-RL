"""Train a gated curriculum, keeping the same policy between stages."""
import argparse
import json
from pathlib import Path
from time import perf_counter

import numpy as np
import torch
from stable_baselines3 import PPO
from src.rl.curriculum import CurriculumEnv, SCHEMA, STAGES
from src.rl.parallel import FastDummyVecEnv, GroupedSubprocVecEnv


def evaluate(model, stage, *, episodes=24, seed=100000, episode_limit=360, shaping_strength=1.0, courses=False):
    if courses:
        from src.rl.courses import CourseEnv, STAGES as names
        env_class, stage_arg = CourseEnv, 'course_stage'
    else:
        env_class, stage_arg, names = CurriculumEnv, 'curriculum_stage', STAGES
    env = FastDummyVecEnv([lambda: env_class(**{stage_arg:stage}, replay_probability=0.0, episode_limit=episode_limit,
                         shaping_strength=shaping_strength) for _ in range(episodes)])
    env.seed(seed)
    rng = np.random.default_rng(seed)
    finished = np.zeros(episodes, dtype=bool)
    results = [None]*episodes
    try:
        obs = env.reset()
        for step in range(episode_limit):
            actions = (model.predict(obs, deterministic=True)[0] if model is not None
                       else np.column_stack([rng.integers(0,3,episodes), rng.integers(0,2,(episodes,3))]))
            obs, _, dones, infos = env.step(actions)
            for i in np.flatnonzero(dones & ~finished):
                info = infos[i]
                results[i] = {"seed": seed+int(i), "success": bool(info['is_success']),
                              "score": info['score'], "levels": info['levels_cleared'],
                              "health": info['health'], "seconds": info['ticks']/60,
                              "checkpoints":info.get('checkpoints',0),"route_found":info.get('route_found',True)}
                finished[i] = True
            if finished.all():
                break
        if not finished.all():
            raise RuntimeError("evaluation did not terminate within episode limit")
        return {"stage": names[stage], "episodes": episodes,
                "success_rate": float(np.mean([r['success'] for r in results])),
                "mean_score": float(np.mean([r['score'] for r in results])),
                "mean_levels": float(np.mean([r['levels'] for r in results])),
                "deaths": sum(r['health'] <= 0 for r in results), "results": results}
    finally:
        env.close()


def write_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stage-budget', type=int, default=1_500_000)
    parser.add_argument('--chunk', type=int, default=131072)
    parser.add_argument('--envs', type=int, default=128)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--eval-episodes', type=int, default=24)
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--threshold', type=float, default=0.75)
    parser.add_argument('--courses', action='store_true')
    parser.add_argument('--init-model', type=Path)
    parser.add_argument('--reference-model', type=Path, help='v1 normal-game checkpoint for final comparison')
    parser.add_argument('--resume-from', type=Path, help='checkpoint with a sibling config.json; preserves optimizer and stage')
    parser.add_argument('--final-budget', type=int, help='additional decisions for normal gameplay')
    args = parser.parse_args()
    if min(args.stage_budget,args.chunk,args.envs,args.workers,args.eval_episodes) < 1 or args.workers > args.envs or not 0 < args.threshold <= 1:
        parser.error('invalid budget, environment count, or threshold')
    if args.final_budget is not None and args.final_budget < 1:
        parser.error('--final-budget must be positive')
    if args.resume_from and args.init_model:
        parser.error('--resume-from and --init-model are mutually exclusive')
    if args.courses:
        from src.rl.courses import STAGES as names, SCHEMA as schema
        stage_arg = 'course_stage'
    else:
        names,schema,stage_arg=STAGES,SCHEMA,'curriculum_stage'
    final_stage=len(names)-1
    start_stage=0
    if args.resume_from:
        if not args.resume_from.is_file():
            parser.error('resume checkpoint does not exist')
        saved=json.loads((args.resume_from.parent/'config.json').read_text(encoding='utf-8'))
        if saved.get('schema') != schema or saved.get('stage') not in names:
            parser.error('resume configuration does not match the selected curriculum')
        start_stage=names.index(saved['stage'])
    args.output.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(2)
    started = perf_counter()
    metrics = ('score','levels_cleared','health','is_success','curriculum_stage')
    env = None
    model = None
    history = []
    status = {"status":"running", "schema":schema, "stage":names[start_stage], "history":history,
              "settings": {**vars(args), "output":str(args.output),"init_model":str(args.init_model) if args.init_model else None,
                           "reference_model":str(args.reference_model) if args.reference_model else None,
                           "resume_from":str(args.resume_from) if args.resume_from else None}}
    write_json(args.output/'status.json',status)
    try:
        for stage, name in enumerate(names):
            if stage < start_stage:
                continue  # already completed in the source run
            budget=args.final_budget if stage == final_stage and args.final_budget else args.stage_budget
            folder = args.output/name
            folder.mkdir()
            limit = (750 if args.courses else 360) if stage < final_stage else 1800
            kwargs = dict(**{stage_arg:stage}, replay_probability=0.15 if stage else 0,
                          episode_limit=limit, shaping_strength=1.0 if stage < final_stage else 0.3)
            (folder/'train-monitor').mkdir()
            env = GroupedSubprocVecEnv(args.envs,args.workers,kwargs,'learning',None,folder/'train-monitor',metrics)
            env.seed(args.seed+stage*10000)
            config = {"schema":schema,"algorithm":"PPO","policy":"MlpPolicy","reward_mode":"learning",
                      "env_kwargs":{**kwargs,"replay_probability":0.0,
                                    "shaping_strength":1.0 if stage < final_stage else 0.0},
                      "training_env_kwargs":kwargs,"stage":name,
                      "hyperparameters":{"n_steps":64,"batch_size":1024,"n_epochs":5,
                                           "gamma":0.995,"ent_coef":0.02,"learning_rate":0.0003},
                      "seed":args.seed,"envs":args.envs,"workers":args.workers}
            write_json(folder/'config.json',config)
            resuming=model is None and args.resume_from is not None
            if resuming:
                model=PPO.load(args.resume_from,env=env,device='cpu')
                model.set_random_seed(args.seed+stage*10000)
                config['resumed_from']=str(args.resume_from)
                write_json(folder/'config.json',config)
            elif model is None:
                model = PPO('MlpPolicy',env,n_steps=64,batch_size=min(1024,args.envs*64),n_epochs=5,
                            gamma=0.995,ent_coef=0.02,seed=args.seed,device='cpu',verbose=0,
                            policy_kwargs={'net_arch':[128,128]})
                if args.init_model:
                    previous=PPO.load(args.init_model,device='cpu')
                    source=previous.policy.state_dict()
                    destination=model.policy.state_dict()
                    for key,value in destination.items():
                        old=source[key]
                        if value.shape == old.shape:
                            value.copy_(old)
                        elif key in ('mlp_extractor.policy_net.0.weight','mlp_extractor.value_net.0.weight') and value.shape[0] == old.shape[0] and value.shape[1] >= old.shape[1]:
                            value.zero_()
                            value[:,:old.shape[1]].copy_(old)
                        else:
                            raise ValueError(f'incompatible warm start tensor: {key}')
                    model.policy.load_state_dict(destination)
            else:
                model.set_env(env)
            stage_start = model.num_timesteps
            passed = False
            best_key = None
            if resuming:
                baseline=evaluate(model,stage,episodes=args.eval_episodes,seed=100000+stage*1000,
                                  episode_limit=limit,shaping_strength=1.0 if stage < final_stage else 0.0,courses=args.courses)
                best_key=((baseline['success_rate'],baseline['mean_score']) if stage < final_stage else
                          (baseline['mean_score'],baseline['mean_levels']))
                model.save(folder/'best')
                write_json(folder/'initial-evaluation.json',baseline)
                write_json(folder/'best-evaluation.json',baseline)
            while model.num_timesteps-stage_start < budget:
                spent = model.num_timesteps-stage_start
                strength = 1.0 if stage < final_stage else 0.3*max(0,1-spent/(budget*0.7))
                if stage == final_stage:
                    env.env_method('set_stage',stage,shaping_strength=strength)
                model.learn(total_timesteps=min(args.chunk,budget-spent),reset_num_timesteps=False)
                result = evaluate(model,stage,episodes=args.eval_episodes,seed=100000+stage*1000,
                                  episode_limit=limit,shaping_strength=1.0 if stage < final_stage else 0.0,courses=args.courses)
                result.update(timesteps=model.num_timesteps,stage_timesteps=model.num_timesteps-stage_start,
                              elapsed=perf_counter()-started)
                history.append(result)
                key = ((result['success_rate'],result['mean_score']) if stage < final_stage else
                       (result['mean_score'],result['mean_levels']))
                if best_key is None or key > best_key:
                    best_key = key
                    model.save(folder/'best')
                    write_json(folder/'best-evaluation.json',result)
                model.save(folder/'latest')
                status.update(stage=name,timesteps=model.num_timesteps,elapsed=perf_counter()-started,
                              stage_timesteps=model.num_timesteps-stage_start,stage_budget=budget)
                write_json(args.output/'status.json',status)
                print(json.dumps({k:v for k,v in result.items() if k!='results'}),flush=True)
                if stage < final_stage and result['success_rate'] >= args.threshold:
                    # A second set of seeds confirms promotion; never used to select checkpoints.
                    confirmation = evaluate(model,stage,episodes=args.eval_episodes,seed=300000+stage*1000,
                                            episode_limit=limit,courses=args.courses)
                    write_json(folder/'confirmation.json',confirmation)
                    if confirmation['success_rate'] >= args.threshold:
                        passed = True
                        break
            model.save(folder/'final')
            env.close()
            env = None
            if stage < final_stage and not passed:
                status.update(status='stage_budget_exhausted',stage=name,
                              message='Skill threshold not reached; later stages were not skipped.')
                write_json(args.output/'status.json',status)
                print(status['message'],flush=True)
                return
        # Report true game performance without shaping, including a random reference.
        test_model = PPO.load(args.output/'normal'/'best.zip',device='cpu')
        report = {'model':evaluate(test_model,final_stage,episodes=40,seed=600000,episode_limit=1800,shaping_strength=0,courses=args.courses),
                  'random':evaluate(None,final_stage,episodes=40,seed=600000,episode_limit=1800,shaping_strength=0,courses=args.courses)}
        if args.reference_model:
            reference=PPO.load(args.reference_model,device='cpu')
            report['previous_model']=evaluate(reference,5,episodes=40,seed=600000,episode_limit=1800,shaping_strength=0)
        write_json(args.output/'final-comparison.json',report)
        status.update(status='complete',elapsed=perf_counter()-started)
        write_json(args.output/'status.json',status)
    except BaseException as error:
        if model is not None:
            model.save(args.output/'interrupted')
        status.update(status='failed',error=repr(error))
        write_json(args.output/'status.json',status)
        raise
    finally:
        if env is not None:
            env.close()


if __name__ == '__main__':
    main()
