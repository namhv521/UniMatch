"""Run reward invariants using explicitly synthetic preference/role inputs."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.environment.extended_rewards import ExtendedRewardEnv


def main():
    env = ExtendedRewardEnv([[.8, .2], [.9, .1]], [1, 1],
                            preferences=[[1, 0], [1, 0]], role_matches=[[1, 0], [1, 0]],
                            preference_weight=.2, role_weight=.1, fairness_weight=0)
    env.reset(seed=42)
    assert abs(env.step(0)[1] - 1.1) < 1e-6
    assert env.step(0)[1] == -2
    _, reward, done, truncated, info = env.step(1)
    assert abs(reward - .1) < 1e-6 and done and not truncated
    assert info['quota_violations'] == 0 and info['assigned_count'] == 2
    print('PASS: synthetic reward bonuses, invalid-action penalty and quota invariants')


if __name__ == '__main__':
    main()
