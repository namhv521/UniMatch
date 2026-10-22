"""Verify complete, non-overlapping agent review coverage of a frozen staging run."""
import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data_pipeline.review_decisions import record_hash


def summarize(run, audit_folder):
    run, audit_folder = Path(run).resolve(), Path(audit_folder).resolve()
    manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
    path = run / 'silver/review_records.jsonl'
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    expected = next(a['sha256'] for a in manifest['artifacts'] if a['path'] == 'silver/review_records.jsonl')
    if digest(path) != expected:
        raise ValueError('staging_artifact_hash_mismatch')
    records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    index = {r['record_id']: r for r in records}
    if len(index) != len(records):
        raise ValueError('duplicate_staging_record')
    seen, reviews, receipts, errors = set(), [], [], []
    for name in ('pdf_extract', 'phase0', 'word_archive'):
        audit = audit_folder / (name + '.jsonl')
        content = audit.read_bytes()
        receipts.append({'file': audit.name, 'sha256': hashlib.sha256(content).hexdigest()})
        for row in [json.loads(line) for line in content.decode('utf-8-sig').splitlines() if line.strip()]:
            key = row.get('record_id')
            source = index.get(key)
            if (source is None or key in seen or row.get('record_sha256') != record_hash(source)
                    or row.get('source_sha256') != source['source_sha256']
                    or row.get('entity_type') != source['entity_type']
                    or row.get('review_kind') != 'agent_advisory'
                    or row.get('reviewer') != 'agent:' + name):
                errors.append({'record_id': key, 'code': 'invalid_or_duplicate_agent_binding', 'file': audit.name})
            seen.add(key)
            reviews.append(row)
    missing = set(index) - seen
    summary = {'status': 'verified_advisory_coverage' if not errors and not missing else 'blocked',
               'phase3_run_id': manifest['gate']['run_id'], 'staging_sha256': expected,
               'source_records': len(index), 'review_rows': len(reviews), 'unique_records_reviewed': len(seen),
               'entity_counts': dict(Counter(r['entity_type'] for r in records)),
               'reviewer_counts': dict(Counter(r.get('reviewer') for r in reviews)),
               'recommendations': dict(Counter(r.get('recommendation') for r in reviews)),
               'records_with_findings': sum(bool(r.get('findings')) for r in reviews),
               'finding_codes': dict(Counter(f.get('code', 'unclassified') if isinstance(f, dict) else str(f)
                                             for r in reviews for f in r.get('findings', []))),
               'finding_severities': dict(Counter(f.get('severity', 'unspecified') if isinstance(f, dict) else 'unspecified'
                                                  for r in reviews for f in r.get('findings', []))),
               'missing_record_ids': sorted(missing), 'errors': errors, 'audit_inputs': receipts,
               'human_approvals': 0, 'human_accuracy': None,
               'limitation': 'Agent evidence review is advisory; it is not human approval or a calibrated accuracy estimate.',
               'created_at': datetime.now(timezone.utc).isoformat()}
    target = audit_folder / 'coverage_report.json'
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    if summary['status'] == 'verified_advisory_coverage':
        proposals = []
        for name in ('pdf_extract', 'phase0', 'word_archive'):
            proposal_path = audit_folder / (name + '_proposals.jsonl')
            if proposal_path.exists():
                proposals += [json.loads(line) for line in proposal_path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
        if len({p['record_id'] for p in proposals}) != len(proposals):
            raise ValueError('duplicate_agent_proposal_record')
        for proposal in proposals:
            if (proposal.get('decision') != 'needs_review' or proposal.get('evidence_confidence') is not None
                    or proposal.get('record_sha256') != record_hash(index[proposal['record_id']])):
                raise ValueError('invalid_agent_proposal_authority')
        (audit_folder / 'combined_proposals.jsonl').write_text(
            ''.join(json.dumps(p, ensure_ascii=False)+'\n' for p in proposals), encoding='utf-8')
        summary['proposal_records'] = len(proposals)
        summary['proposed_field_changes'] = sum(len(p.get('corrections', {})) + len(p.get('remove_fields', [])) for p in proposals)
        target.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        def cell(value):
            return str(value).replace('|', '\\|').replace('\n', ' ')
        lines = ['# UniMatch — Báo cáo bằng chứng để chủ sở hữu duyệt',
                 f"Run staging được rà: `{summary['phase3_run_id']}`. SHA256: `{expected}`.",
                 f"**{len(reviews)}/{len(index)} hồ sơ được ba agent rà, không trùng hoặc thiếu. Chưa có phê duyệt của người dùng.**",
                 'Phương pháp: kiểm tra hash nguồn và từng evidence reference bằng chương trình; agent đọc trường chính cùng ngữ cảnh nguồn. '
                 'Bốn bìa có lỗi font/layout được xem ảnh. Không tuyên bố đã đọc trực quan toàn bộ 18.225 trang, '
                 'đo accuracy OCR, xác minh năng lực cá nhân hoặc phê duyệt điều kiện hướng dẫn.',
                 f"Có {len(proposals)} hồ sơ được đề xuất thay đổi {summary['proposed_field_changes']} trường. "
                 'Mọi đề xuất vẫn needs_review; không gán confidence, proficiency hay preference.',
                 '## Toàn bộ hồ sơ']
        table_lines = ['| Record | Nhóm | Nguồn | Kết quả/giới hạn |', '|---|---|---|---|']
        for review in reviews:
            record = index[review['record_id']]
            findings = '; '.join(f.get('code', str(f)) if isinstance(f, dict) else str(f) for f in review.get('findings', []))
            table_lines.append('| ' + ' | '.join(cell(v) for v in (record['record_id'][:12], record['entity_type'],
                          record.get('source_file', record.get('source_url', '')), findings or review['recommendation'])) + ' |')
        lines.append('\n'.join(table_lines))
        lines += ['## Đề xuất sửa có bằng chứng',
                  'Các bản JSONL lưu đầy đủ SHA256 record, locator, snippet và lý do. Bảng dưới là phần đọc nhanh; '
                  'chủ sở hữu có thể giữ chờ hoặc từ chối từng record.']
        for proposal in proposals:
            record = index[proposal['record_id']]
            lines += [f"### {record['record_id']}",
                      f"Nguồn: {record.get('source_file', record.get('source_url', ''))}",
                      f"SHA256 nguồn: `{record['source_sha256']}`", str(proposal.get('notes', ''))]
            for field, changed in proposal.get('corrections', {}).items():
                old = record.get('fields', {}).get(field, record.get(field))
                old_value = old.get('value') if isinstance(old, dict) else old
                new_value = changed.get('value') if isinstance(changed, dict) else changed
                lines += [f'**{field}**', 'Trước: ' + str(old_value), 'Đề xuất: ' + str(new_value)]
                if isinstance(changed, dict):
                    lines += [f"- `{ev.get('locator', '')}`: {ev.get('snippet', '')}" for ev in changed.get('evidence', [])]
            for field in proposal.get('remove_fields', []):
                lines += [f'**Loại trường {field} bị phân loại nhầm**',
                          str(record['fields'][field].get('value', ''))]
        lines += ['## Phần chủ sở hữu cần duyệt',
                  '1. Chấp nhận/loại/giữ chờ từng hồ sơ và các đề xuất sửa; nguồn mâu thuẫn không tự hợp nhất.',
                  '2. Duyệt taxonomy/allowlist/exclusions và rubric confidence. Confidence còn thiếu hiện chặn gold của các hàng có tag.',
                  '3. Duyệt nhãn mẫu 14 tài liệu/84 trường tại `../sample-20261021T154719Z-b40d7836/`; '
                  'nhãn gốc còn trống, chưa có accuracy của người dùng.',
                  'Chỉ sau phê duyệt có attribution, validator và snapshot gate mới được chuyển Phase 4. '
                  'Website hiện tại chưa được thay đổi.']
        (audit_folder / 'owner_evidence_report.md').write_text('\n\n'.join(lines), encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--audit-folder', type=Path, default=Path('data_rebuild/v1/review/full_audit'))
    args = parser.parse_args()
    result = summarize(args.run, args.audit_folder)
    print(json.dumps(result, ensure_ascii=True))
    raise SystemExit(0 if result['status'] == 'verified_advisory_coverage' else 2)
