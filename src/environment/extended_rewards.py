"""Optional, explicitly supplied rewards; historical advisor labels are not preferences."""
import numpy as np

from src.environment.gym_matching_env import GymMatchingEnv


def validated_signal(values, shape, weight, name):
    if not np.isfinite(weight) or weight < 0:
        raise ValueError(f'{name} weight must be finite and nonnegative')
    if values is None:
        if weight:
            raise ValueError(f'{name} data required for nonzero weight')
        return np.zeros(shape, dtype=float)
    matrix = np.asarray(values, dtype=float)
    if (matrix.shape != shape or not np.isfinite(matrix).all()
            or np.any((matrix < 0) | (matrix > 1))):
        raise ValueError(f'{name} must have shape {shape} and values in [0, 1]')
    return matrix.copy()


class ExtendedRewardEnv(GymMatchingEnv):
    """Add weighted preference/role signals only after a valid assignment.

    Observation remains 3M for the existing contract. These extra signals are
    not observed by the policy; this wrapper alone does not make V2 Markov.
    Provide real elicited preferences and explicitly verified role matches.
    """

    def __init__(self, compatibility, quotas, *, preferences=None, role_matches=None,
                 preference_weight=0, role_weight=0, **kwargs):
        super().__init__(compatibility, quotas, **kwargs)
        self.preferences = validated_signal(preferences, self.compatibility.shape,
                                            preference_weight, 'Preference')
        self.role_matches = validated_signal(role_matches, self.compatibility.shape,
                                             role_weight, 'Role')
        self.preference_weight = preference_weight
        self.role_weight = role_weight

    def step(self, action):
        student = self.current_step if self._started else 0
        obs, reward, terminated, truncated, info = super().step(action)
        preference_bonus = role_bonus = 0.0
        if self.current_step > student:
            preference_bonus = float(self.preference_weight * self.preferences[student, action])
            role_bonus = float(self.role_weight * self.role_matches[student, action])
        info.update(preference_bonus=preference_bonus, role_bonus=role_bonus)
        return obs, reward + preference_bonus + role_bonus, terminated, truncated, info
