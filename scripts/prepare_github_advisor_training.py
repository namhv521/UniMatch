"""Build an immutable, source-reviewed faculty refresh; never mutate the active run."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.features.github_enrichment import prepare_bundle

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('data_rebuild/v1'))
    parser.add_argument('--github-run', type=Path, required=True)
    parser.add_argument('--quality-review', type=Path, required=True)
    args = parser.parse_args()
    print(prepare_bundle(args.output, args.github_run, args.quality_review))
