"""Read-only source audit; never invent missing curated records."""
import argparse
import csv
import json
from pathlib import Path

SCHEMAS = {
    'theses.csv': ('thesis_id', 'student_id', 'submission_year', 'thesis_title'),
    'advisors.csv': ('advisor_id', 'advisor_name', 'quota', 'skill_text'),
}


def audit_curated(directory):
    directory = Path(directory)
    report = {'ready': True, 'missing_files': [], 'tables': {}}
    for filename, columns in SCHEMAS.items():
        path = directory / filename
        if not path.is_file():
            report['missing_files'].append(filename)
            report['ready'] = False
            continue
        with path.open(encoding='utf-8-sig', newline='') as source:
            reader = csv.DictReader(source)
            fields = reader.fieldnames or []
            rows = list(reader)
        missing = sorted(set(columns) - set(fields))
        ids = [row.get(columns[0], '') for row in rows]
        nulls = {column: sum(not str(row.get(column, '')).strip() for row in rows) / len(rows)
                 if rows else 1.0 for column in columns}
        table = {'rows': len(rows), 'missing_columns': missing,
                 'duplicate_ids': len(ids) - len(set(ids)), 'null_rates': nulls}
        report['tables'][filename] = table
        if not rows or missing or table['duplicate_ids'] or any(nulls.values()):
            report['ready'] = False
    # This flag means structural readiness only, not provenance/semantic approval.
    report['scope'] = 'structural audit; year, skill provenance and identity still require validation'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path('data/curated'))
    args = parser.parse_args()
    report = audit_curated(args.data_dir)
    args.data_dir.mkdir(parents=True, exist_ok=True)
    (args.data_dir / 'quality_report_v2.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report['ready'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
