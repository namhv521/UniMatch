"""Validate or execute one source-bound nested RL round; never changes serving."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.rl.nested_learning import decode_problem, run_round, validate_round, verify_round


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--parent', type=Path)
    parser.add_argument('--timesteps', type=int, default=256)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--verify', type=Path)
    args = parser.parse_args()
    if args.verify:
        result = verify_round(args.verify)
    else:
        if not args.suite or (not args.dry_run and not args.output):
            parser.error('--suite and --output are required unless using --dry-run or --verify')
        data = json.loads(args.suite.read_text(encoding='utf-8-sig'))
        train = [decode_problem(p) for p in data['train']]
        validation = decode_problem(data['validation'])
        if args.dry_run:
            result = validate_round(train, validation, data['contract'], data['round'], parent=args.parent)
        else:
            result = run_round(train, validation, data['contract'], data['round'], args.output,
                    parent=args.parent, total_timesteps=args.timesteps, model_config=data.get('model_config'),
                    historical_validation={name: decode_problem(p) for name, p in data.get('historical_validation', {}).items()})
    print(json.dumps({key: value for key, value in result.items() if key not in ('training', 'parent', 'candidate', 'baselines')},
                     ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
