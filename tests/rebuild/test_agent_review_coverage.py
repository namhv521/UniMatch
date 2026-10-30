import hashlib
import json

from scripts.summarize_rebuild_review import summarize
from src.data_pipeline.review_decisions import record_hash


def test_audit_report_rejects_duplicate_and_stale_agent_coverage(tmp_path):
    run, audits = tmp_path / 'run', tmp_path / 'audit'
    (run / 'silver').mkdir(parents=True)
    audits.mkdir()
    record = {'record_id': 'technical-only', 'entity_type': 'students', 'source_sha256': 'a'*64}
    artifact = run / 'silver/review_records.jsonl'
    artifact.write_text(json.dumps(record)+'\n', encoding='utf-8')
    (run / 'manifest.json').write_text(json.dumps({'gate': {'run_id': 'fixture'}, 'artifacts': [
        {'path': 'silver/review_records.jsonl', 'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest()}]}))
    row = {**record, 'record_sha256': record_hash(record), 'review_kind': 'agent_advisory',
           'reviewer': 'agent:pdf_extract', 'findings': [], 'recommendation': 'accept_core'}
    for name in ('pdf_extract', 'phase0', 'word_archive'):
        (audits / (name+'.jsonl')).write_text(json.dumps(row)+'\n' if name == 'pdf_extract' else '')
    assert summarize(run, audits)['status'] == 'verified_advisory_coverage'
    (audits / 'phase0.jsonl').write_text(json.dumps({**row, 'reviewer': 'agent:phase0'})+'\n')
    assert summarize(run, audits)['status'] == 'blocked'
    (audits / 'phase0.jsonl').write_text('')
    (audits / 'pdf_extract.jsonl').write_text(json.dumps({**row, 'record_sha256': 'b'*64})+'\n')
    assert summarize(run, audits)['status'] == 'blocked'
