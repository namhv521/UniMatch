import numpy as np
import gymnasium as gym
from src.environment.matching_env import MatchingEnv
from src.rl.dqn import train_dqn
from src.rl.qrdqn import train_qrdqn

def env(): return gym.wrappers.TimeLimit(MatchingEnv(np.array([[.9,.1],[.1,.9]], dtype=np.float32), np.array([1,1])), max_episode_steps=8)

def test_value_algorithms_smoke():
    assert train_dqn(env(), total_timesteps=16, seed=42)
    assert train_qrdqn(env(), total_timesteps=16, seed=42)
