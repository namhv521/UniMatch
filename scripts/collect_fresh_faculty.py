"""Collect a new live official faculty snapshot into a fresh private namespace."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data_pipeline.fresh_faculty import collect_external_profiles, collect_faculty, reparse_publications, verify_collection, verify_publication_dates


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed-csv', type=Path)
    parser.add_argument('--directory-html', type=Path)
    parser.add_argument('--delay', type=float, default=1.0)
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--reparse-from', type=Path)
    parser.add_argument('--external-from', type=Path)
    parser.add_argument('--verify-dates', action='store_true')
    args = parser.parse_args()
    if args.external_from:
        report = collect_external_profiles(args.external_from, args.output, delay=args.delay)
    elif args.reparse_from:
        report = reparse_publications(args.reparse_from, args.output)
    elif args.verify_dates:
        report = verify_publication_dates(args.output)
    else:
        report = verify_collection(args.output) if args.verify else collect_faculty(
            args.output, seed_csv=args.seed_csv, directory_html=args.directory_html, delay=args.delay)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    raise SystemExit(0 if report.get('collection_status', 'collected') == 'collected' else 2)
