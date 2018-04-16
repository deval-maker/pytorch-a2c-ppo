import argparse
import gym
import gym_minigrid
from gym_minigrid.wrappers import *
import time
import numpy as np
import torch

import ac_rl
from utils import get_model_path, load_model, save_model

"""parse arguments"""
parser = argparse.ArgumentParser(description='PyTorch RL example')
parser.add_argument('--algo', required=True,
                    help='algorithm to use: a2c | ppo')
parser.add_argument('--env', required=True,
                    help='name of the environment to train on')
parser.add_argument('--model', default=None,
                    help='name of the pre-trained model'),
parser.add_argument('--reset', action='store_true', default=False,
                    help='initialize model with random parameters')
parser.add_argument('--seed', type=int, default=1,
                    help='random seed (default: 1)')
parser.add_argument('--processes', type=int, default=16,
                    help='number of processes (default: 16)')
parser.add_argument('--total-frames', type=int, default=10**7,
                    help='number of frames during full training (default: 10e6)')
parser.add_argument('--log-interval', type=int, default=10,
                    help='interval between log display (default: 10)')
parser.add_argument('--save-interval', type=int, default=0,
                    help="interval between model saving (default: 0, 0 means no saving)")
parser.add_argument('--step-frames', type=int, default=5,
                    help='number of frames per agent during a training step (default: 5)')
parser.add_argument('--discount', type=float, default=0.99,
                    help='discount factor (default: 0.99)')
parser.add_argument('--lr', type=float, default=7e-4,
                    help='learning rate (default: 7e-4)')
parser.add_argument('--gae-tau', type=float, default=0.95,
                    help='tau coefficient in GAE formula (default: 0.95, 1 means no gae)')
parser.add_argument('--entropy-coef', type=float, default=0.01,
                    help='entropy term coefficient (default: 0.01)')
parser.add_argument('--value-loss-coef', type=float, default=0.5,
                    help='value loss term coefficient (default: 0.5)')
parser.add_argument('--max-grad-norm', type=float, default=0.5,
                    help='maximum norm of gradient (default: 0.5)')
parser.add_argument('--optim-eps', type=float, default=1e-5,
                    help='Adam and RMSprop optimizer epsilon (default: 1e-5)')
parser.add_argument('--optim-alpha', type=float, default=0.99,
                    help='RMSprop optimizer apha (default: 0.99)')
parser.add_argument('--clip-eps', type=float, default=0.2,
                    help='clipping epsilon for PPO')
parser.add_argument('--epochs', type=int, default=4,
                    help='number of epochs for PPO (default: 4)')
parser.add_argument('--batch-size', type=int, default=32,
                    help='batch size for PPO (default: 32, 0 means all)')
args = parser.parse_args()

"""set numpy and pytorch seeds"""
ac_rl.seed(args.seed)

"""generate environments"""
envs = []
for i in range(args.processes):
    env = gym.make(args.env)
    env.seed(args.seed + i)
    env = FlatObsWrapper(env)
    envs.append(env)

"""define model path"""
model_name = args.model if args.model != None else args.env+"_"+args.algo
model_path = get_model_path(model_name)

"""define actor-critic model"""
from_path = None if args.reset else model_path
acmodel = load_model(envs[0].observation_space, envs[0].action_space, from_path)
if ac_rl.use_gpu:
    acmodel = acmodel.cuda()

"""define actor-critic algo"""
if args.algo == "a2c":
    algo = ac_rl.A2CAlgo(envs, args.step_frames, acmodel, args.discount, args.lr,
                         args.gae_tau, args.entropy_coef, args.value_loss_coef, args.max_grad_norm,
                         args.optim_alpha, args.optim_eps)
elif args.algo == "ppo":
    algo = ac_rl.PPOAlgo(envs, args.step_frames, acmodel, args.discount, args.lr,
                         args.gae_tau, args.entropy_coef, args.value_loss_coef, args.max_grad_norm,
                         args.optim_eps, args.clip_eps, args.epochs, args.batch_size)
else:
    raise ValueError

"""train model"""
num_steps = args.total_frames // args.processes // args.step_frames
num_frames = 0

for step in range(num_steps):
    """train model for one step"""
    start_time = time.time()
    log = algo.step()
    end_time = time.time()

    """print log"""
    if step % args.log_interval == 0:
        step_num_frames = args.processes * args.step_frames
        num_frames += step_num_frames
        fps = step_num_frames/(end_time - start_time)

        print("Step {}, {} frames, {:.0f} FPS, mean/median return {:.1f}/{:.1f}, min/max return {:.1f}/{:.1f}, entropy {:.3f}, value loss {:.3f}, action loss {:.3f}".
            format(step, num_frames, fps,
                   np.mean(log["return"]), np.median(log["return"]), np.amin(log["return"]), np.amax(log["return"]),
                   log["entropy"], log["value_loss"], log["action_loss"]))

    """save model"""
    if args.save_interval > 0 and step > 0 and step % args.save_interval == 0:
        save_model(acmodel, model_path)