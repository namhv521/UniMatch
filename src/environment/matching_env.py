"""
Gymnasium-based Matching Environment.
Implements the MDP formulation with Action Masking.
"""

from math import ceil

import gymnasium as gym
import numpy as np
from gymnasium import spaces


class MatchingEnv(gym.Env):
    """
    Student-Advisor Matching Environment using MDP formulation.
    
    State: 3*M = 117 dims (compatibility + remaining capacity + load ratio)
    Action: Discrete(39) - assign student to advisor
    Reward: w_comp*comp + w_fair*var_reduction - w_pen*invalid
    """
    
    metadata = {"render_modes": []}  # noqa: RUF012 - Gymnasium class-level metadata contract
    
    def __init__(
        self,
        n_students: int = 198,
        n_advisors: int = 39,
        max_quota: int | None = None,
    ):
        if not isinstance(n_students, int) or not isinstance(n_advisors, int):
            raise ValueError('Student and advisor counts must be integers')  # noqa: TRY004 - public validation contract
        if n_students <= 0 or n_advisors <= 0:
            raise ValueError('Student and advisor counts must be positive')
        max_quota = ceil(n_students / n_advisors) if max_quota is None else max_quota
        if not isinstance(max_quota, int) or max_quota <= 0:
            raise ValueError('Quota must be a positive integer')
        if n_advisors * max_quota < n_students:
            raise ValueError('Total capacity is smaller than cohort')
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
        self.invalid_proposals = 0
    
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.invalid_proposals = 0
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

    def action_masks(self):
        return self.load < self.max_quota
    
    def step(self, action):
        if self.compatibility is None or self.current_step >= self.n_students:
            raise RuntimeError('Call reset before stepping a new episode')
        if not self.action_space.contains(action):
            raise ValueError('Action is outside the advisor action space')
        valid = self.load[action] < self.max_quota
        before = float(np.var(self.load))
        reward = -2.0
        if valid:
            self.load[action] += 1
            reward = float(self.compatibility[self.current_step, action]) + 0.15 * (
                before - float(np.var(self.load))
            )
            self.current_step += 1
        else:
            self.invalid_proposals += 1
        done = self.current_step >= self.n_students
        obs = self._get_obs()
        return obs, reward, done, False, {
            "action_mask": self._get_action_mask(),
            "invalid_proposals": self.invalid_proposals,
            "quota_violations": int(np.maximum(self.load - self.max_quota, 0).sum()),
        }
