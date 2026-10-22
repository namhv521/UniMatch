"""Freeze the advisory evidence package for owner review without granting approval."""
import argparse
import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data_pipeline.reconcile import ROOT


def freeze(output):
    output = Path(output).resolve()
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    gate = json.loads((output / 'reports/phase3_gate.json').read_text(encoding='utf-8'))
    run = output / 'phase3_runs' / gate['run_id']
    manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['gate'] != gate:
        raise ValueError('phase3_gate_binding_mismatch')
    for item in manifest['artifacts']:
        if digest(run / item['path']) != item['sha256']:
            raise ValueError('phase3_artifact_modified')
    audit = output / 'review/full_audit'
    coverage = json.loads((audit / 'coverage_report.json').read_text(encoding='utf-8'))
    if coverage['status'] != 'verified_advisory_coverage':
        raise ValueError('agent_audit_not_complete')
    for item in coverage['audit_inputs']:
        if digest(audit / item['file']) != item['sha256']:
            raise ValueError('audit_modified_after_coverage_check')
    if digest(audit / 'combined_proposals.jsonl') != digest(run / 'review/agent_proposals.jsonl'):
        raise ValueError('proposals_do_not_match_staging')
    package = output / 'review' / ('owner-package-' + gate['run_id'])
    package.mkdir(exist_ok=False)
    for name in ('pdf_extract', 'phase0', 'word_archive'):
        for suffix in ('.jsonl', '_summary.json', '_proposals.jsonl'):
            shutil.copy2(audit / (name+suffix), package / (name+suffix))
    for name in ('coverage_report.json', 'combined_proposals.jsonl', 'owner_evidence_report.md'):
        shutil.copy2(audit / name, package / name)
    tests_log = output / 'reports/rebuild_tests_latest.txt'
    if tests_log.exists():
        shutil.copy2(tests_log, package / 'test_results.txt')
    for folder in ('reports', 'review'):
        shutil.copytree(run / folder, package / ('staging_' + folder))
    shutil.copytree(ROOT / 'configs/data', package / 'configs')
    shutil.copytree(output / 'review' / ('sample-' + gate['student_source_run_id']), package / 'sample')
    sample = list(csv.DictReader((package / 'sample/sample.csv').open(encoding='utf-8-sig')))
    member_manifest = output / 'phase1_runs' / gate['student_source_run_id'] / 'reports/archive_member_manifest.csv'
    members = {row['member_sha256']: row['extracted_path'] for row in
               csv.DictReader(member_manifest.open(encoding='utf-8-sig')) if row['status'] == 'extracted'}
    links = ['# Nguồn gốc các hồ sơ mẫu', 'Chỉ mở nguồn có byte hash trùng. Không sửa file nguồn.']
    seen = set()
    for row in sample:
        if row['candidate_id'] in seen:
            continue
        seen.add(row['candidate_id'])
        path = Path(members.get(row['source_sha256'], ROOT / 'data/1.pdfs' / row['source_file']))
        if not path.exists() or digest(path) != row['source_sha256']:
            raise ValueError('sample_original_source_missing_or_modified')
        links.append(f"- `{row['candidate_id']}`: [{row['source_file']}](<{path.as_posix()}>) — SHA256 `{row['source_sha256']}`")
    (package / 'sample/source_links.md').write_text('\n\n'.join(links), encoding='utf-8')
    with (package / 'owner_evidence_report.md').open('a', encoding='utf-8') as stream:
        stream.write(f"\n\n## Staging sau đề xuất\n\nRun `{gate['run_id']}` áp dụng {coverage['proposal_records']} đề xuất/"
                     f"{coverage['proposed_field_changes']} thay đổi trường, "
                     f"gold có {sum(v['approved'] for v in gate['counts'].values())} hồ sơ approved. "
                     'Chi tiết review_errors và validator nằm trong staging_reports/. '
                     'Website chưa được thay dữ liệu.\n\n'
                     '[Bằng chứng mẫu](sample/evidence.md) · [Nguồn mở trực tiếp](sample/source_links.md) · '
                     '[Nhãn mẫu còn trống](sample/sample.csv) · [Template quyết định sau sửa](staging_review/decisions_template.csv)\n')
    receipt = {'status': 'pending_owner_review', 'phase3_run_id': gate['run_id'],
               'input_manifest_sha256': digest(run / 'manifest.json'), 'human_approvals': 0,
               'artifacts': [{'path': p.relative_to(package).as_posix(), 'sha256': digest(p)}
                             for p in sorted(package.rglob('*')) if p.is_file()]}
    (package / 'package_manifest.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    return {'package': str(package), 'artifacts': len(receipt['artifacts']), 'status': receipt['status']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('data_rebuild/v1'))
    print(json.dumps(freeze(parser.parse_args().output)))
