import csv
import hashlib
import json
from pathlib import Path

import pytest


def seal_snapshot(tmp_path):
    from src.data_pipeline.csv_contracts import HEADERS
    from src.data_pipeline.reconcile import ROOT
    output = tmp_path / 'output'
    run = output / 'phase3_runs/technical-fixture'
    for folder in ('gold', 'reports', 'silver'):
        (run / folder).mkdir(parents=True)
    students = [{'schema_version': '1.0', 'semester_id': 'TECHNICAL', 'student_id': f'fixture-{i}',
                 'student_name': f'Private Learner {i}', 'thesis_title': title, 'source_type': 'pdf',
                 'source_file': f'fixture-{i}.pdf', 'source_sha256': str(i+1)*64, 'review_status': 'approved'}
                for i, title in enumerate(['Cloud data streams', 'Image medical detection', 'Secure network analysis',
                                           'Database query planning', 'Financial forecasting models', 'Software testing framework'])]
    advisors = [{'schema_version': '1.0', 'semester_id': 'TECHNICAL', 'advisor_id': f'advisor-{i}',
                 'advisor_name': f'Private Faculty {i}', 'source_type': 'official_web',
                 'source_url': f'https://example.test/faculty/{i}', 'source_sha256': 'a'*64,
                 'research_description': text, 'review_status': 'approved'}
                for i, text in enumerate(['Cloud database streams and query planning', 'Image medical detection and forecasting'])]
    for entity, rows in [('students', students), ('advisors', advisors)]:
        with (run / f'gold/{entity}.csv').open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=HEADERS[entity])
            writer.writeheader()
            writer.writerows(rows)
    records = [{'record_id': r['student_id'], 'entity_type': 'students', 'source_aliases': [],
                'fields': {'student_id': {'value': r['student_id']}, 'thesis_title': {'value': r['thesis_title'], 'evidence': []}}}
               for r in students]
    records += [{'record_id': r['advisor_id'], 'entity_type': 'advisors', 'advisor_id': r['advisor_id'],
                 'research_topics': [r['research_description']], 'teaching_topics': []} for r in advisors]
    (run / 'silver/review_records.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records), encoding='utf-8')
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    gate = {'phase': 3, 'status': 'verified', 'can_start_phase4': True, 'run_id': run.name}
    name = 'reports/phase3_gate.json'
    (run / name).write_text(json.dumps(gate), encoding='utf-8')
    (output / 'reports').mkdir()
    (output / name).write_bytes((run / name).read_bytes())
    snapshot = {'status': 'approved', 'snapshot_id': run.name, 'gate': gate, 'inputs': {'config_files': {
        n: digest(ROOT / 'configs/data' / n) for n in ('taxonomy_v1.yaml','feature_allowlist.yaml','feature_excluded.yaml')}}}
    (run / 'gold/snapshot_manifest.json').write_text(json.dumps(snapshot), encoding='utf-8')
    (run / 'manifest.json').write_text(json.dumps({'gate': gate, 'artifacts': [
        {'path': p.relative_to(run).as_posix(), 'sha256': digest(p)}
        for p in run.rglob('*') if p.is_file()]}), encoding='utf-8')
    return output, run


def test_phase4_locks_snapshot_masks_and_excludes_test_from_review_packet(tmp_path):
    from src.features.rebuild_experiments import run_experiments
    output, _ = seal_snapshot(tmp_path)
    gate = run_experiments(output)
    assert gate['status'] == 'blocked' and not gate['can_start_phase5']
    assert 'OWNER_RANKING_REVIEW_REQUIRED' in gate['blocking_reasons']
    run = Path(gate['run_dir'])
    split = json.loads((run / 'splits.json').read_text(encoding='utf-8'))
    packet = json.loads((run / 'review/packet_manifest.json').read_text(encoding='utf-8'))
    assert packet['student_ids'] and all(split['assignments'][s] == 'validation' for s in packet['student_ids'])
    assert packet['scores_exposed_to_reviewer'] is False
    assert not list(run.glob('**/*test_scores*'))
    assert gate['full_matrix_status'] == 'pending_owner_feature_selection'


def test_phase4_rejects_changed_gold_before_starting_an_experiment(tmp_path):
    from src.features.rebuild_experiments import run_experiments
    output, phase3 = seal_snapshot(tmp_path)
    with (phase3 / 'gold/students.csv').open('a') as stream:
        stream.write('tampered')
    with pytest.raises(ValueError, match='hash_mismatch'):
        run_experiments(output)
    assert not (output / 'phase4_runs').exists()


def advisory_fixture(tmp_path):
    """Technical source quotes only; no real-world relevance labels involved."""
    from src.features.rebuild_experiments import run_experiments
    output, phase3 = seal_snapshot(tmp_path)
    # Original seed42 titles are entirely OOV on validation. Explicit fixture
    # abstracts/profile context exercise E1, E2 and calibrated serialization.
    for entity in ('students', 'advisors'):
        path = phase3 / f'gold/{entity}.csv'
        with path.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            headers, rows = reader.fieldnames, list(reader)
        for row in rows:
            row['research_domain_tags'] = 'software_engineering'
            if entity == 'students':
                row['thesis_abstract'] = 'Shared technical fixture context'
            else:
                row['research_description'] += ' Shared technical fixture context'
        with path.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
    manifest_path = phase3 / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    for artifact in manifest['artifacts']:
        artifact['sha256'] = hashlib.sha256((phase3 / artifact['path']).read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    gate = run_experiments(output)
    packet = Path(gate['run_dir']) / 'review'
    manifest_sha = hashlib.sha256((packet / 'packet_manifest.json').read_bytes()).hexdigest()
    pairs = [json.loads(line) for line in (packet / 'blinded_pairs.jsonl').read_text(encoding='utf-8').splitlines()]
    assert pairs
    proposals = [{'pair_id': pair['pair_id'], 'grade': 3, 'reviewer': 'agent:technical-fixture',
                  'attribution': 'agent_advisory', 'packet_manifest_sha256': manifest_sha,
                  'reason': 'Technical validation fixture only; not a supervision quality claim.',
                  'student_evidence': [pair['student_title']], 'advisor_evidence': [pair['advisor_profile']]}
                 for pair in pairs]
    return output, packet, proposals


def test_phase4_rejects_agent_grades_without_frozen_packet_digest_or_source_quotes(tmp_path):
    from src.features.rebuild_experiments import run_experiments
    output, packet, proposals = advisory_fixture(tmp_path)
    bindings = json.loads((packet / 'pair_bindings.json').read_text(encoding='utf-8'))
    # This formerly accepted payload has correct record/snapshot bindings but
    # deliberately omits packet digest, reason and source quotes.
    unsupported = [{**bindings[row['pair_id']],
                    **{k: row[k] for k in ('pair_id', 'grade', 'reviewer', 'attribution')}} for row in proposals]
    path = tmp_path / 'unsupported-agent-grades.jsonl'
    path.write_text(''.join(json.dumps(row)+'\n' for row in unsupported), encoding='utf-8')
    with pytest.raises(ValueError, match='invalid_advisory_proposal'):
        run_experiments(output, labels_file=path, review_packet=packet)


def test_phase4_accepts_evidence_bound_agent_proposals_without_granting_owner_approval(tmp_path):
    from src.features.rebuild_experiments import run_experiments
    output, packet, proposals = advisory_fixture(tmp_path)
    path = tmp_path / 'technical-proposals.jsonl'
    # Preserve original bytes as well as semantic mappings (including BOM/CRLF).
    original = ('\ufeff' + ''.join(json.dumps(row)+'\r\n' for row in proposals)).encode('utf-8')
    path.write_bytes(original)
    gate = run_experiments(output, labels_file=path, review_packet=packet)
    run = Path(gate['run_dir'])
    assert gate['status'] == 'blocked' and gate['can_start_phase5'] is False
    assert gate['owner_validated_ranking_metrics'] is None
    assert 'OWNER_RANKING_REVIEW_REQUIRED' in gate['blocking_reasons']
    assert (run / 'review/agent_proposals.jsonl').read_bytes() == original
    mapped = [json.loads(line) for line in (run / 'review/labels.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(mapped) == len(proposals)
    assert all(row['attribution'] == 'agent_advisory' and row['student_evidence'] and row['advisor_evidence'] for row in mapped)
    assert all('approval_evidence_sha256' not in row for row in mapped)
    metrics = json.loads((run / 'reports/ranking_metrics.json').read_text(encoding='utf-8'))
    assert metrics['status'] == 'agent_advisory_only'
    manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['agent_proposals_sha256'] == hashlib.sha256(original).hexdigest()
    import numpy as np
    from src.features.rebuild_experiments import _load_snapshot
    from src.features.rebuild_features import FeaturePipeline
    students, advisors, _ = _load_snapshot(output)
    identities = sorted({str(row[key]) for row in students+advisors
                         for key in ('student_id','student_name','advisor_id','advisor_name') if row.get(key)})
    pipe = FeaturePipeline.load(run/'transformer_calibrated_proposal', known_identities=identities)
    split = json.loads((run/'splits.json').read_text())
    validation = [row for row in students if split['assignments'][row['student_id']] == 'validation']
    replay = pipe.transform_score(validation, advisors)
    np.testing.assert_array_equal(replay['scores']['E4'], np.load(run/'validation_scores/E4_calibrated_proposal.npy'))
    assert json.loads((run/'reports/feature_audit.json').read_text())['transform_parity'] is True


def test_phase4_rejects_forged_owner_ratification_even_with_packet_quotes_and_hash(tmp_path):
    from src.features.rebuild_experiments import run_experiments
    output, packet, proposals = advisory_fixture(tmp_path)
    for row in proposals:
        row.update(attribution='owner_ratified', approval_evidence_sha256='a'*64)
    path = tmp_path / 'forged-owner.jsonl'
    path.write_text(''.join(json.dumps(row)+'\n' for row in proposals), encoding='utf-8')
    with pytest.raises(ValueError, match='invalid_advisory_proposal'):
        run_experiments(output, labels_file=path, review_packet=packet)
