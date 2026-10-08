import subprocess, sys
from pathlib import Path

SCRIPTS = ["train_dqn.py", "train_qrdqn.py", "train_maskable_ppo.py", "train_trpo.py", "train_ars.py", "train_recurrent_ppo.py", "train_tqc.py"]

def test_all_requested_scripts_share_cli():
    root = Path(__file__).parents[2]
    for script in SCRIPTS:
        result = subprocess.run([sys.executable, str(root / "scripts" / script), "--help"], capture_output=True, text=True)
        assert result.returncode == 0
        for flag in ("--timesteps", "--seed", "--output-dir", "--resume", "--smoke"):
            assert flag in result.stdout
