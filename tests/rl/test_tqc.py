import pytest
from src.rl.training import TrainingConfig, build_environment
from src.rl.tqc import require_tqc_compatible

def test_tqc_refuses_discrete_matching_environment():
    with pytest.raises(ValueError, match="continuous Box"):
        require_tqc_compatible(build_environment(TrainingConfig("TQC")))
