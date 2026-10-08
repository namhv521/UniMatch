import numpy as np
import gymnasium as gym
from src.environment.matching_env import MatchingEnv
from src.rl.ars import train_ars
from src.rl.recurrent_ppo import predict_episode, train_recurrent_ppo
from src.rl.trpo import train_trpo

def env(): return gym.wrappers.TimeLimit(MatchingEnv(np.array([[.9,.1],[.1,.9]], dtype=np.float32), np.array([1,1])), max_episode_steps=8)

def test_policy_algorithms_smoke_and_recurrent_episode():
    assert train_trpo(env(), total_timesteps=16, seed=42)
    assert train_ars(env(), total_timesteps=16, seed=42)
    recurrent = train_recurrent_ppo(env(), total_timesteps=16, seed=42)
    assert 1 <= len(predict_episode(recurrent, env())) <= 8
