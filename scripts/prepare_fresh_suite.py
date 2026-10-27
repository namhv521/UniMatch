"""Build a frozen research suite only from a freshly collected run."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.features.fresh_suite import prepare_suite


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--version', choices=['V1', 'V2', 'V3', 'V4'], required=True)
    parser.add_argument('--mode', choices=['retrospective_document_proxy'], required=True)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--encoder', type=Path)
    parser.add_argument('--student-collection', type=Path)
    args = parser.parse_args()
    result = prepare_suite(args.run, args.output, version=args.version, mode=args.mode,
                           seed=args.seed, frozen_encoder=args.encoder, student_collection=args.student_collection)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    raise SystemExit(0 if result['status'] == 'ready_research_only' else 2)
