"""
Gymnasium-based Matching Environment.
Implements the MDP formulation with Action Masking.
"""

import numpy as np
import gymnasium as gym
from gymnasium import spaces
from typing import Dict, Tuple, Any


class MatchingEnv(gym.Env):
    """
    Student-Advisor Matching Environment using MDP formulation.
    
    State: 3*M = 117 dims (compatibility + remaining capacity + load ratio)
    Action: Discrete(39) - assign student to advisor
    Reward: w_comp*comp + w_fair*var_reduction - w_pen*invalid
    """
    
    metadata = {"render_modes": []}
    
    def __init__(
        self,
        n_students: int = 198,
        n_advisors: int = 39,
        max_quota: int = 5,
    ):
        self.n_students = n_students
        self.n_advisors = n_advisors
        self.max_quota = max_quota
        
        state_dim = 3 * n_advisors
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(state_dim,), dtype=np.float32
        )
        self.action_space = spaces.Discrete(n_advisors)
        
        self.current_step = 0
        self.load = np.zeros(n_advisors, dtype=np.int32)
        self.compatibility = None
    
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.load = np.zeros(self.n_advisors, dtype=np.int32)
        self.compatibility = self.np_random.uniform(
            0, 1, (self.n_students, self.n_advisors)
        ).astype(np.float32)
        return self._get_obs(), {}
    
    def _get_obs(self):
        idx = min(self.current_step, self.n_students - 1)
        comp = self.compatibility[idx]
        remaining = np.clip((self.max_quota - self.load) / self.max_quota, 0, 1)
        load_ratio = np.clip(self.load / self.max_quota, 0, 1)
        return np.concatenate([comp, remaining, load_ratio]).astype(np.float32)
    
    def _get_action_mask(self):
        return (self.load < self.max_quota).astype(np.uint8)
    
    def step(self, action):
        valid = self.load[action] < self.max_quota
        reward = float(self.compatibility[self.current_step, action]) if valid else -10.0
        if valid:
            self.load[action] += 1
        self.current_step += 1
        done = self.current_step >= self.n_students
        obs = self._get_obs()
        return obs, reward, done, False, {"action_mask": self._get_action_mask()}
