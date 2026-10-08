from __future__ import annotations

import gymnasium as gym
import numpy as np

from .action_mask import feasible_action_mask
from .reward import matching_reward


class MatchingEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, compatibility: np.ndarray, capacities: np.ndarray):
        self.compatibility = np.asarray(compatibility, dtype=np.float32)
        self.capacities = np.asarray(capacities)
        if self.compatibility.ndim != 2 or self.capacities.ndim != 1:
            raise ValueError("compatibility and capacities must be matrix/vector")
        if self.compatibility.shape[1] != self.capacities.size:
            raise ValueError("advisor count must match capacities")
        if 0 in self.compatibility.shape or not np.all(np.isfinite(self.compatibility)):
            raise ValueError("compatibility must be finite and non-empty")
        if np.any((self.compatibility < 0) | (self.compatibility > 1)):
            raise ValueError("compatibility must be between 0 and 1")
        if np.any(self.capacities < 0) or not np.issubdtype(self.capacities.dtype, np.integer):
            raise ValueError("capacities must be non-negative integers")
        if int(self.capacities.sum()) < self.compatibility.shape[0]:
            raise ValueError("insufficient capacity for all students")

        self.n_students, self.n_advisors = self.compatibility.shape
        self.action_space = gym.spaces.Discrete(self.n_advisors)
        self.observation_space = gym.spaces.Box(0.0, 1.0, shape=(3 * self.n_advisors,), dtype=np.float32)
        self.loads = np.zeros(self.n_advisors, dtype=np.int64)
        self.student_index = 0

    def _observation(self) -> np.ndarray:
        if self.student_index >= self.n_students:
            return np.zeros(3 * self.n_advisors, dtype=np.float32)
        safe_capacity = np.where(self.capacities == 0, 1, self.capacities)
        remaining = np.where(self.capacities == 0, 0, (self.capacities - self.loads) / safe_capacity)
        load_ratio = np.where(self.capacities == 0, 0, self.loads / safe_capacity)
        return np.concatenate((self.compatibility[self.student_index], remaining, load_ratio)).astype(np.float32)

    def action_masks(self) -> np.ndarray:
        return feasible_action_mask(self.loads, self.capacities)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.loads.fill(0)
        self.student_index = 0
        return self._observation(), {"student_index": 0}

    def step(self, action: int):
        if self.student_index >= self.n_students:
            raise ValueError("episode already terminated; reset before stepping")
        valid = self.action_space.contains(action) and self.action_masks()[action]
        if not valid:
            reward = matching_reward(0.0, self.loads, self.loads, invalid=True)
            return self._observation(), reward, False, False, {
                "student_index": self.student_index,
                "invalid_action": True,
            }

        before = self.loads.copy()
        self.loads[action] += 1
        reward = matching_reward(float(self.compatibility[self.student_index, action]), before, self.loads)
        self.student_index += 1
        terminated = self.student_index == self.n_students
        return self._observation(), reward, terminated, False, {
            "student_index": self.student_index,
            "invalid_action": False,
        }
