import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from src.rl.cli import run_training
from src.rl.recurrent_ppo import train_recurrent_ppo
if __name__ == "__main__": run_training("RecurrentPPO", train_recurrent_ppo)
