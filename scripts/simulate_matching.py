"""Trace a synthetic capacity-constrained episode; never a research benchmark."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np

from src.environment.gym_matching_env import GymMatchingEnv

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--steps', type=int, default=5)
args = parser.parse_args()
if args.steps <= 0:
    parser.error('steps must be positive')
env = GymMatchingEnv(np.random.default_rng(42).random((args.steps, 3)), [args.steps] * 3)
env.reset(seed=42)
for step in range(args.steps):
    feasible = np.flatnonzero(env.action_masks())
    action = int(feasible[np.argmax(env.compatibility[step, feasible])])
    _, reward, terminated, truncated, info = env.step(action)
    print(json.dumps({'synthetic_demo': True, 'step': step, 'advisor': action, 'reward': reward,
                      'loads': env.load.tolist(), 'quota_violations': info['quota_violations']}))
