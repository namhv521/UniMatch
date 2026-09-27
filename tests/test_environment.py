"""Test for src.environment module import."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_environment_import():
    """Test that src.environment can be imported."""
    import src.environment
    assert hasattr(src.environment, "MatchingEnv")
    print("✅ src.environment import successful")


def test_matching_env_creation():
    """Test that MatchingEnv can be instantiated."""
    from src.environment import MatchingEnv
    env = MatchingEnv(n_students=10, n_advisors=5, max_quota=3)
    assert env is not None
    assert env.n_students == 10
    assert env.n_advisors == 5
    print("✅ MatchingEnv instantiation successful")


def test_env_reset():
    """Test that environment reset works."""
    from src.environment import MatchingEnv
    env = MatchingEnv(n_students=10, n_advisors=5, max_quota=3)
    obs, _info = env.reset(seed=42)
    assert obs.shape == (15,)  # 3*5
    print("✅ Environment reset successful")


if __name__ == "__main__":
    test_environment_import()
    test_matching_env_creation()
    test_env_reset()
    print("\n✅ All environment tests passed!")
