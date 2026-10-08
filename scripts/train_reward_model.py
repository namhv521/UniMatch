import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from src.rlhf.collector import load_preferences
from src.rlhf.reward_model import validate_training_readiness
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--preferences", type=Path, required=True)
    parser.add_argument("--minimum-records", type=int, default=100)
    parser.add_argument("--minimum-agreement", type=float, default=0.7)
    args = parser.parse_args()
    try:
        result = validate_training_readiness(load_preferences(args.preferences), args.minimum_records, args.minimum_agreement)
        print(json.dumps({**result, "status": "ready", "training": "not implemented; post-MVP design required"}))
    except (ValueError, OSError) as error:
        print(json.dumps({"status": "blocked", "reason": str(error)}))
        raise SystemExit(2)
