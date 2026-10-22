"""Run private Phase 4 feature diagnostics from a verified Phase 3 gold snapshot."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.features.rebuild_experiments import run_experiments


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('data_rebuild/v1'))
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--labels', type=Path, help='Blinded agent proposal JSONL; source quotes and packet SHA required. No owner ratification is inferred.')
    parser.add_argument('--review-packet', type=Path)
    args = parser.parse_args()
    gate = run_experiments(args.output, seed=args.seed, labels_file=args.labels, review_packet=args.review_packet)
    print(json.dumps(gate, ensure_ascii=True))
    raise SystemExit(0 if gate['status'] == 'verified' else 2)
