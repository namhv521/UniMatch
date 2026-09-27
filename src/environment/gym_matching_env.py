"""Gymnasium matching environment driven by a verified compatibility matrix."""
import gymnasium as gym
import numpy as np
from gymnasium import spaces

from src.models.data_contract import validate_matching_data


class GymMatchingEnv(gym.Env):
    metadata = {'render_modes': []}  # noqa: RUF012 - Gymnasium class-level metadata contract

    def __init__(self, compatibility, quotas, fairness_weight=.15, max_proposals=None):
        scores, _ = validate_matching_data(compatibility, quotas)
        if not np.isfinite(fairness_weight) or fairness_weight < 0:
            raise ValueError('Fairness weight must be finite and nonnegative')
        self.compatibility = scores.astype(np.float32)
        self.quotas = np.asarray(quotas, dtype=np.int64)
        self.n_students, self.n_advisors = scores.shape
        self.fairness_weight = fairness_weight
        self.max_proposals = 10 * self.n_students if max_proposals is None else max_proposals
        if not isinstance(self.max_proposals, int) or self.max_proposals < self.n_students:
            raise ValueError('Proposal limit must be at least cohort size')
        self.observation_space = spaces.Box(0, 1, (3 * self.n_advisors,), dtype=np.float32)
        self.action_space = spaces.Discrete(self.n_advisors)
        self._started = False

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.proposals = 0
        self.invalid_proposals = 0
        self.load = np.zeros(self.n_advisors, dtype=np.int64)
        self.assignments = np.full(self.n_students, -1, dtype=np.int64)
        self._started = True
        self._finished = False
        return self._get_obs(), self._info()

    def _get_obs(self):
        comp = (self.compatibility[self.current_step] if self.current_step < self.n_students
                else np.zeros(self.n_advisors, dtype=np.float32))
        denominator = np.maximum(self.quotas, 1)
        return np.concatenate([comp, (self.quotas - self.load) / denominator,
                               self.load / denominator]).astype(np.float32)

    def action_masks(self):
        return self.load < self.quotas

    def _get_action_mask(self):
        return self.action_masks().astype(np.uint8)

    def _info(self):
        assigned = self.assignments >= 0
        total = float(self.compatibility[np.flatnonzero(assigned), self.assignments[assigned]].sum())
        return {'action_mask': self.action_masks(), 'invalid_proposals': self.invalid_proposals,
                'quota_violations': int(np.maximum(self.load - self.quotas, 0).sum()),
                'assigned_count': int(assigned.sum()), 'assignments': self.assignments.tolist(),
                'mean_compatibility': total / self.n_students,
                'load_variance': float(np.var(self.load))}

    def step(self, action):
        if not self._started or self._finished:
            raise RuntimeError('Call reset before stepping a new episode')
        if not self.action_space.contains(action):
            raise ValueError('Action is outside the advisor action space')
        self.proposals += 1
        reward = -2.0
        if self.load[action] < self.quotas[action]:
            before = float(np.var(self.load))
            self.load[action] += 1
            reward = float(self.compatibility[self.current_step, action]) + self.fairness_weight * (
                before - float(np.var(self.load)))
            self.assignments[self.current_step] = action
            self.current_step += 1
        else:
            self.invalid_proposals += 1
        terminated = self.current_step == self.n_students
        truncated = self.proposals >= self.max_proposals and not terminated
        self._finished = terminated or truncated
        return self._get_obs(), reward, terminated, truncated, self._info()
