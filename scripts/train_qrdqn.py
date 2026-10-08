import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from src.rl.cli import run_training
from src.rl.qrdqn import train_qrdqn
if __name__ == "__main__": run_training("QRDQN", train_qrdqn)
