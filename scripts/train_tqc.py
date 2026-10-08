import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from src.rl.tqc import require_tqc_compatible
from src.rl.training import add_common_arguments, build_environment, config_from_args
if __name__ == "__main__":
    parser = argparse.ArgumentParser(); add_common_arguments(parser)
    config = config_from_args("TQC", parser.parse_args())
    try: require_tqc_compatible(build_environment(config))
    except ValueError as error:
        print(json.dumps({"algorithm": "TQC", "status": "blocked", "reason": str(error)}))
        raise SystemExit(2)
