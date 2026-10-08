import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from src.rl.ars import train_ars
from src.rl.cli import run_training
if __name__ == "__main__": run_training("ARS", train_ars)
