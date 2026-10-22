"""Create a fresh, unlabelled source review package from a verified Phase 1 run."""
import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data_pipeline.reconcile import _read_bound_phase
from src.data_pipeline.review_metrics import REVIEW_FIELDS, sample_candidates


def prepare(output):
    output = Path(output).resolve()
    gate, path = _read_bound_phase(output, 1, 'bronze/student_candidates.jsonl')
    candidates = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    selected = sample_candidates(candidates)
    folder = output / 'review' / ('sample-' + gate['run_id'])
    folder.mkdir(parents=True, exist_ok=True)
    rows, sections = [], [f"# Source review — {gate['run_id']}",
        'Agent findings are advisory. Owner labels and approvals remain blank.',
        'The deterministic sample covers available source layouts; it is not a random accuracy estimate.']
    for candidate in candidates:
        key = candidate['candidate_id']
        if key not in selected:
            continue
        sections += [f"## {key}", f"Source: `{candidate['source_file']}`", f"SHA256: `{candidate['source_sha256']}`",
                     'Strata: ' + ', '.join(sorted(selected[key])),
                     'Archive chain: ' + json.dumps(candidate.get('archive_chain', []), ensure_ascii=False)]
        for field in sorted(REVIEW_FIELDS):
            item = candidate['fields'].get(field, {})
            if field == 'technology_mentions':
                value = json.dumps([m['value'] for m in candidate.get(field, [])], ensure_ascii=False)
                evidence = [ev for m in candidate.get(field, []) for ev in m['evidence']]
            else:
                value, evidence = item.get('value', ''), item.get('evidence', [])
            rows.append({'run_id': gate['run_id'], 'candidate_id': key,
                         'source_file': candidate['source_file'], 'source_sha256': candidate['source_sha256'],
                         'field_name': field, 'candidate_value': value,
                         'sample_strata': ';'.join(sorted(selected[key])),
                         'evidence_refs_json': json.dumps(evidence, ensure_ascii=False),
                         'review_status': 'pending', 'reviewer': '', 'reviewed_at': '',
                         'field_verdict': '', 'reviewer_corrected_value': '', 'reviewer_notes': ''})
            sections += [f'### {field}', str(value) or '(missing)',
                         *[f"- `{ev.get('locator', '')}`: {ev.get('snippet', '')}" for ev in evidence]]
    csv_path = folder / 'sample.csv'
    # Never overwrite labels already entered in a previous package.
    if csv_path.exists():
        raise ValueError('review_package_exists; preserve existing labels and package')
    with csv_path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (folder / 'evidence.md').write_text('\n\n'.join(sections), encoding='utf-8')
    manifest = {'run_id': gate['run_id'], 'candidate_artifact_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'sample_documents': len(selected), 'sample_fields': len(rows),
                'candidate_strata': {k: sorted(v) for k, v in selected.items()},
                'unlabelled_csv_sha256': hashlib.sha256(csv_path.read_bytes()).hexdigest(),
                'status': 'pending_owner_review', 'human_labels': 0}
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return {'folder': str(folder), **manifest}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('data_rebuild/v1'))
    print(json.dumps(prepare(parser.parse_args().output), ensure_ascii=True))
