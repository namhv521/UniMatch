"""Sequential arrival simulation with persistent quota, without future-student access."""
import numpy as np

from src.baselines.classical import allocate
from src.models.data_contract import validate_matching_data


class StreamingMatcher:
    """Local single-process greedy allocation. A failed arrival never changes state."""

    def __init__(self, quotas):
        values = np.asarray(quotas, dtype=float)
        if (values.ndim != 1 or not values.size or not np.isfinite(values).all()
                or np.any(values < 0) or np.any(values >= 2**63)
                or np.any(values != np.floor(values))):
            raise ValueError('Quotas must be a nonempty vector of nonnegative integers')
        self._quotas = values.astype(np.int64)
        self._loads = np.zeros(len(values), dtype=np.int64)
        self._assignments = {}

    @property
    def loads(self):
        return self._loads.copy()

    @property
    def assignments(self):
        return self._assignments.copy()

    def assign(self, student_id, compatibility):
        if not isinstance(student_id, str) or not student_id.strip():
            raise ValueError('A nonempty student ID is required')
        if student_id in self._assignments:
            raise ValueError('Student already assigned')
        row = np.asarray(compatibility, dtype=float)
        if row.shape != self._quotas.shape:
            raise ValueError('One compatibility score required per advisor')
        advisor = int(allocate(row[None, :], self._quotas - self._loads,
                               strategy='greedy')[0])
        self._loads[advisor] += 1
        self._assignments[student_id] = advisor
        return advisor


def simulate_streaming(scores, quotas, *, seed=42, arrival_rate=1.0):
    """Seeded random order and exponential interarrival times, in simulated time.

    No wall-clock sleeps; no future scores are passed to the matcher. This is
    an online greedy baseline, not evidence that an RL policy generalizes.
    """
    scores, _ = validate_matching_data(scores, quotas)
    if not np.isfinite(arrival_rate) or arrival_rate <= 0:
        raise ValueError('Arrival rate must be finite and positive')
    matcher = StreamingMatcher(quotas)
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(scores))
    times = np.cumsum(rng.exponential(1 / arrival_rate, len(scores)))
    events = []
    for student, timestamp in zip(order, times):
        advisor = matcher.assign(str(student), scores[student])
        events.append({'student_index': int(student), 'advisor_index': advisor,
                       'arrival_time': float(timestamp),
                       'compatibility': float(scores[student, advisor]),
                       'loads': matcher.loads.tolist()})
    return events
