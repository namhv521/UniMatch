"""V2 batch allocation with explicit Top-3 preferences and past-only feedback."""
import numpy as np

from src.baselines.classical import allocate
from src.environment.extended_rewards import validated_signal
from src.models.data_contract import validate_matching_data


def preference_matrix(rankings, n_advisors):
    """Ranked advisor indices become [1, 2/3, 1/3]; unlisted advisors get zero.

    Empty lists mean no preference. Callers must obtain rankings directly,
    never derive them from the historical assigned-advisor label.
    """
    if isinstance(n_advisors, bool) or not isinstance(n_advisors, int) or n_advisors <= 0:
        raise ValueError('Advisor count must be a positive integer')
    result = np.zeros((len(rankings), n_advisors), dtype=float)
    for student, ranking in enumerate(rankings):
        if len(ranking) > 3:
            raise ValueError('At most three preferences are supported')
        seen = set()
        for rank, advisor in enumerate(ranking):
            if (isinstance(advisor, (bool, np.bool_))
                    or not isinstance(advisor, (int, np.integer))
                    or not 0 <= advisor < n_advisors or advisor in seen):
                raise ValueError('Preferences must be distinct valid advisor indices')
            result[student, advisor] = (3 - rank) / 3
            seen.add(advisor)
    return result


def allocate_with_preferences(scores, quotas, preferences=None, *, preference_weight=0,
                              feedback=None, feedback_weight=0, strategy='exact', seed=42):
    """Maximize (compatibility + wp*preference + wf*feedback)/(1+wp+wf).

    Feedback must be supplied from outcomes available before the cohort cutoff;
    this numerical layer cannot verify source dates. Default weights are zero.
    The normalization preserves the additive objective while keeping [0,1].
    """
    scores, quotas = validate_matching_data(scores, quotas)
    prefs = validated_signal(preferences, scores.shape, preference_weight, 'Preference')
    past = validated_signal(feedback, scores.shape, feedback_weight, 'Feedback')
    # Scale first to avoid overflow with individually finite, very large weights.
    scale = max(1, preference_weight, feedback_weight)
    weights = np.array([1 / scale, preference_weight / scale, feedback_weight / scale])
    weights /= weights.sum()
    objective = weights[0] * scores + weights[1] * prefs + weights[2] * past
    return allocate(np.clip(objective, 0, 1), quotas, strategy=strategy, seed=seed)
