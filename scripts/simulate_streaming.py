"""Run an explicitly synthetic, seeded streaming demonstration."""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.simulator.streaming_arrival import simulate_streaming

if __name__ == '__main__':
    events = simulate_streaming(np.random.default_rng(42).random((5, 3)), [2, 2, 2])
    print(json.dumps({'synthetic_demo': True, 'events': events}, indent=2))
