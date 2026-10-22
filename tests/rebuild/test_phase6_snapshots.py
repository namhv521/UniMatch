"""Technical fixtures for immutable semester history; no real approval/outcomes."""
import copy
import hashlib
import json

import pytest

from src.data_pipeline.semester_snapshots import (create_snapshot, drift_report,
                                                outcome_availability, verify_snapshot)


@pytest.fixture
def supplied(tmp_path):
    source = tmp_path / 'technical.csv'
    source.write_text('technical_source_only\n', encoding='utf-8')
    return {'store': tmp_path / 'snapshots', 'semester_id': 'TECHNICAL-TERM',
            'captured_at': '2026-10-22T12:00:00Z', 'feature_sha256': 'a'*64,
            'taxonomy_sha256': 'b'*64, 'policy_sha256': 'c'*64,
            'files': {'evidence/technical.csv': source}}


def assignment(supplied):
    return {'assignment_id': 'technical-assignment', 'semester_id': supplied['semester_id'],
            'student_id': 'technical-student', 'advisor_id': 'technical-advisor',
            'review_status': 'approved', 'reviewer': 'technical-fixture-only',
            'reviewed_at': '2026-10-21T12:00:00Z',
            'provenance': {'source_ref': 'evidence/technical.csv',
                           'source_sha256': hashlib.sha256(next(iter(supplied['files'].values())).read_bytes()).hexdigest()}}


def outcome(supplied):
    return {'outcome_id': 'technical-outcome', 'assignment_id': 'technical-assignment',
            'semester_id': supplied['semester_id'], 'outcome_name': 'technical_metric', 'value': 0,
            'observed_at': '2026-10-21T13:00:00Z', 'review_status': 'approved',
            'reviewer': 'technical-fixture-only', 'reviewed_at': '2026-10-21T14:00:00Z',
            'provenance': assignment(supplied)['provenance']}


def test_snapshot_is_content_addressed_atomic_and_repeat_is_idempotent(supplied):
    original = copy.deepcopy(supplied)
    first = create_snapshot(**supplied)
    again = create_snapshot(**supplied)
    assert first == again and len(first['snapshot_id']) == 64
    assert verify_snapshot(supplied['store'], first['snapshot_id']) == first
    assert len(list(supplied['store'].iterdir())) == 1
    assert supplied == original
    assert first['status'] == 'draft' and first['closed_at'] is None
    assert first['assignments'] == [] and first['outcomes'] == []
    assert first['outcomes_status'] == 'unknown_not_supplied'


def test_changed_content_creates_new_version_and_never_mutates_prior_assignments(supplied):
    assignments = [assignment(supplied)]
    original = copy.deepcopy(assignments)
    first = create_snapshot(**supplied, assignments=assignments)
    second = create_snapshot(**supplied, assignments=assignments, status='research')
    assert first['snapshot_id'] != second['snapshot_id']
    assert verify_snapshot(supplied['store'], first['snapshot_id'])['assignments'] == original
    assert assignments == original
    next(iter(supplied['files'].values())).write_text('new technical source\n', encoding='utf-8')
    third = create_snapshot(**supplied)
    assert third['snapshot_id'] != first['snapshot_id']


def test_artifact_and_manifest_tampering_and_extra_files_are_rejected(supplied):
    snapshot = create_snapshot(**supplied)
    folder = supplied['store'] / snapshot['snapshot_id']
    artifact = folder / 'files/evidence/technical.csv'
    saved = artifact.read_bytes()
    artifact.write_bytes(b'tampered')
    with pytest.raises(ValueError, match='artifact'):
        verify_snapshot(supplied['store'], snapshot['snapshot_id'])
    with pytest.raises(ValueError):
        create_snapshot(**supplied)
    artifact.write_bytes(saved)
    extra = folder / 'files/untracked.txt'
    extra.write_text('untracked')
    with pytest.raises(ValueError, match='unexpected'):
        verify_snapshot(supplied['store'], snapshot['snapshot_id'])
    extra.unlink()
    manifest = folder / 'manifest.json'
    changed = json.loads(manifest.read_text(encoding='utf-8'))
    changed['semester_id'] = 'forged'
    manifest.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match='hash'):
        verify_snapshot(supplied['store'], snapshot['snapshot_id'])


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'C:/outside', 'a\\b', 'a/../../b',
                                 'a//b', './file', 'NUL', 'a:stream', 'a./file'])
def test_portable_paths_cannot_escape_snapshot(supplied, name):
    supplied['files'] = {name: next(iter(supplied['files'].values()))}
    with pytest.raises(ValueError, match='artifact_path'):
        create_snapshot(**supplied)
    assert not supplied['store'].exists() or not list(supplied['store'].iterdir())


@pytest.mark.parametrize('changes', [dict(feature_sha256=''), dict(policy_sha256='X'*64),
                                   dict(captured_at='2026-10-22'),
                                   dict(semester_start='2026-10-21T00:00:00Z', semester_end='2026-09-01T00:00:00Z'),
                                   dict(captured_at='2026-01-01T00:00:00Z', closed_at='2026-09-01T00:00:00Z'),
                                   dict(status='closed'), dict(semester_id=' ')])
def test_explicit_metadata_and_timestamps_are_required_without_invented_closure(supplied, changes):
    supplied.update(changes)
    with pytest.raises(ValueError):
        create_snapshot(**supplied)


def test_approved_outcomes_require_bound_approved_assignment_and_real_provenance(supplied):
    row, label = assignment(supplied), outcome(supplied)
    snapshot = create_snapshot(**supplied, assignments=[row], outcomes=[label], status='closed',
                               semester_start='2026-08-01T00:00:00Z', semester_end='2026-10-20T00:00:00Z',
                               closed_at='2026-10-22T00:00:00Z')
    assert snapshot['outcomes'][0]['value'] == 0
    for field, value in [('assignment_id', 'missing'), ('observed_at', '2026-10-23T00:00:00Z'),
                         ('reviewer', ''), ('reviewed_at', '2026-10-20T00:00:00Z')]:
        bad = copy.deepcopy(label)
        bad[field] = value
        with pytest.raises(ValueError, match='provenance'):
            create_snapshot(**supplied, assignments=[row], outcomes=[bad])
    bad = copy.deepcopy(label)
    bad['provenance']['source_sha256'] = 'd'*64
    with pytest.raises(ValueError, match='provenance'):
        create_snapshot(**supplied, assignments=[row], outcomes=[bad])
    pending = dict(row, review_status='pending')
    with pytest.raises(ValueError, match='provenance'):
        create_snapshot(**supplied, assignments=[pending], outcomes=[label])


def test_future_label_and_unreviewed_outcome_never_enter_asof_training(supplied):
    label = outcome(supplied)
    report = outcome_availability([label], as_of='2026-10-21T12:30:00Z')
    assert report['available_outcome_ids'] == []
    assert 'not_observed_as_of' in report['blocked'][0]['codes']
    assert outcome_availability([label], as_of='2026-10-21T15:00:00Z')['available_outcome_ids'] == ['technical-outcome']
    assert not outcome_availability([dict(label, review_status='pending')], as_of='2026-10-22T00:00:00Z')['available_outcome_ids']


def test_drift_retains_namespace_and_missingness_without_imputation():
    previous = [{'topic_tags': 'nlp', 'research_domain_tags': 'ai', 'title': 'old', 'value': 0},
                {'topic_tags': '', 'title': None, 'value': False}]
    current = [{'topic_tags': 'cv;nlp', 'research_domain_tags': '', 'title': 'new', 'value': 0}]
    report = drift_report(previous, current, tag_fields=['topic_tags', 'research_domain_tags'], required_fields=['title', 'value'])
    assert report['tags']['topic_tags']['new_tags'] == ['cv']
    assert report['tags']['research_domain_tags']['removed_tags'] == ['ai']
    assert report['missingness']['title']['previous']['missing'] == 1
    assert report['missingness']['value']['previous']['missing'] == 0
    assert drift_report([], [], tag_fields=['topic_tags'], required_fields=['title'])['missingness']['title']['current']['rate'] is None


def test_interrupted_copy_cannot_publish_partial_snapshot(supplied, monkeypatch):
    import src.data_pipeline.semester_snapshots as snapshots
    def interrupted(source, target):
        target.write_bytes(b'partial')
        raise OSError('technical simulated disk failure')
    monkeypatch.setattr(snapshots.shutil, 'copyfile', interrupted)
    with pytest.raises(OSError, match='disk failure'):
        create_snapshot(**supplied)
    assert not list(supplied['store'].iterdir())


def test_concurrent_identical_ingests_conserve_one_verified_snapshot(supplied):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as pool:
        manifests = list(pool.map(lambda _: create_snapshot(**supplied), range(8)))
    assert all(m == manifests[0] for m in manifests)
    assert len(list(supplied['store'].iterdir())) == 1
    assert verify_snapshot(supplied['store'], manifests[0]['snapshot_id']) == manifests[0]


def test_case_colliding_directories_and_parent_artifacts_are_rejected(supplied):
    source = next(iter(supplied['files'].values()))
    for files in [{'A/x.csv': source, 'a/y.csv': source}, {'a': source, 'a/child.csv': source}]:
        with pytest.raises(ValueError, match='artifact_paths'):
            create_snapshot(**dict(supplied, files=files))


def test_approved_identity_and_duplicate_assignments_are_validated(supplied):
    row = assignment(supplied)
    for records in [[row, row], [dict(row, student_id=[])], ['invalid']]:
        with pytest.raises(ValueError, match='provenance'):
            create_snapshot(**supplied, assignments=records)


def test_closed_assignments_do_not_fabricate_missing_outcomes(supplied):
    snapshot = create_snapshot(**supplied, assignments=[assignment(supplied)], status='closed',
                               semester_start='2026-08-01T00:00:00Z', semester_end='2026-10-20T00:00:00Z',
                               closed_at='2026-10-22T00:00:00Z')
    assert snapshot['outcomes'] == [] and snapshot['outcomes_status'] == 'unknown_not_supplied'


def test_manifest_size_limit_fails_before_publishing(supplied, monkeypatch):
    import src.data_pipeline.semester_snapshots as snapshots
    monkeypatch.setattr(snapshots, 'MAX_MANIFEST_BYTES', 100)
    with pytest.raises(ValueError, match='size_limit'):
        create_snapshot(**supplied)
    assert not supplied['store'].exists()
