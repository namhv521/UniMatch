"""Five-seed, eight-algorithm checkpoint validation entrypoint."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.rl.evaluate_checkpoints import main

if __name__ == '__main__':
    raise SystemExit(main())
