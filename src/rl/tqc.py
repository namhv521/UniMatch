from __future__ import annotations

from gymnasium import spaces


def require_tqc_compatible(env) -> None:
    if not isinstance(env.action_space, spaces.Box):
        raise ValueError("TQC requires a continuous Box action space; MatchingEnv is Discrete")
