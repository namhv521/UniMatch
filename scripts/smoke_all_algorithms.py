import subprocess, sys
from pathlib import Path

root = Path(__file__).parents[1]
compatible = ["dqn", "qrdqn", "maskable_ppo", "trpo", "ars", "recurrent_ppo"]
for name in compatible:
    subprocess.run([sys.executable, str(root / "scripts" / f"train_{name}.py"), "--smoke", "--output-dir", str(root / "outputs/training-smoke")], check=True)
tqc = subprocess.run([sys.executable, str(root / "scripts/train_tqc.py"), "--smoke"])
if tqc.returncode != 2: raise SystemExit("TQC did not fail closed as expected")
print("six smoke runs passed; TQC incompatibility correctly blocked")
