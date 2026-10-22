"""Content-addressed semester evidence; no fabricated closure, outcomes or approvals."""
import hashlib
import json
import re
import shutil
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath


SCHEMA_VERSION = 'semester-snapshot/1.0'
MAX_MANIFEST_BYTES = 32 * 1024**2


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _sha(value):
    return hashlib.sha256(_json(value)).hexdigest()


def _digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise ValueError('explicit_lowercase_sha256_required')
    return value


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _time(value):
    if not isinstance(value, str):
        raise ValueError('explicit_timezone_timestamp_required')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as error:
        raise ValueError('explicit_timezone_timestamp_required') from error
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('explicit_timezone_timestamp_required')
    return result


def _artifact_name(name):
    if (not isinstance(name, str) or not name or '\\' in name or name != str(PurePosixPath(name))
            or PurePosixPath(name).is_absolute() or PureWindowsPath(name).drive):
        raise ValueError('invalid_artifact_path')
    for part in name.split('/'):
        if (part in {'', '.', '..'} or part.endswith(('.', ' ')) or re.search(r'[<>:"|?*\x00-\x1f]', part)
                or re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', part, re.I)):
            raise ValueError('invalid_artifact_path')
    return name


def validate_provenance(assignments, outcomes, semester_id, *, artifacts=None, captured_at=None):
    """Check supplied approval metadata and bound bytes, never invent human verdicts.

    `artifacts` maps source_ref to {sha256,size_bytes}. Without it this helper
    checks record syntax only; create/verify always supply actual artifact hashes.
    """
    errors, assignment_index, outcome_ids, approved_students = [], {}, set(), set()
    cutoff = _time(captured_at) if captured_at is not None else None
    for entity, rows in [('assignments', assignments), ('outcomes', outcomes)]:
        if not isinstance(rows, list):
            errors.append({'entity': entity, 'code': 'records_must_be_list'})
            continue
        for position, row in enumerate(rows):
            codes = []
            if not isinstance(row, dict):
                errors.append({'entity': entity, 'row': position, 'codes': ['invalid_record']})
                continue
            key_name = 'assignment_id' if entity == 'assignments' else 'outcome_id'
            key = row.get(key_name)
            if not _text(key):
                codes.append('record_id_required')
            if row.get('semester_id') != semester_id:
                codes.append('semester_mismatch')
            status = row.get('review_status')
            if status not in {'pending', 'needs_review', 'approved', 'rejected'}:
                codes.append('invalid_review_status')
            reviewed = None
            if status == 'approved':
                if not _text(row.get('reviewer')):
                    codes.append('approved_reviewer_required')
                try:
                    reviewed = _time(row.get('reviewed_at'))
                    if cutoff and reviewed > cutoff:
                        codes.append('review_after_capture')
                except ValueError:
                    codes.append('approved_review_timestamp_required')
            provenance = row.get('provenance')
            if not isinstance(provenance, dict):
                codes.append('source_provenance_required')
            else:
                try:
                    ref = _artifact_name(provenance.get('source_ref'))
                    sha = _hash(provenance.get('source_sha256'))
                    if artifacts is not None and (ref not in artifacts or artifacts[ref]['sha256'] != sha):
                        codes.append('source_artifact_binding_mismatch')
                except ValueError:
                    codes.append('invalid_source_provenance')
            if entity == 'assignments':
                if not _text(row.get('student_id')) or not _text(row.get('advisor_id')):
                    codes.append('assignment_identity_required')
                if isinstance(key, str) and key in assignment_index:
                    codes.append('duplicate_assignment_id')
                if status == 'approved':
                    if isinstance(row.get('student_id'), str) and row['student_id'] in approved_students:
                        codes.append('duplicate_approved_student_assignment')
                    if isinstance(row.get('student_id'), str):
                        approved_students.add(row['student_id'])
                if isinstance(key, str):
                    assignment_index[key] = row
            else:
                if isinstance(key, str) and key in outcome_ids:
                    codes.append('duplicate_outcome_id')
                if isinstance(key, str):
                    outcome_ids.add(key)
                assignment_key = row.get('assignment_id')
                linked = assignment_index.get(assignment_key) if isinstance(assignment_key, str) else None
                if linked is None or (status == 'approved' and linked.get('review_status') != 'approved'):
                    codes.append('approved_assignment_reference_required')
                if not _text(row.get('outcome_name')) or 'value' not in row or row['value'] is None:
                    codes.append('explicit_observed_outcome_required')
                try:
                    observed = _time(row.get('observed_at'))
                    if cutoff and observed > cutoff:
                        codes.append('outcome_after_capture')
                    if reviewed and observed > reviewed:
                        codes.append('outcome_after_review')
                except ValueError:
                    codes.append('outcome_observed_timestamp_required')
            if codes:
                errors.append({'entity': entity, 'row': position, 'record_id': key, 'codes': codes})
    try:
        _json([assignments, outcomes])
    except (ValueError, TypeError):
        errors.append({'code': 'nonfinite_or_non_json_record'})
    return errors


def _validate(payload):
    if (payload.get('schema_version') != SCHEMA_VERSION or not _text(payload.get('semester_id'))
            or payload.get('status') not in {'draft', 'research', 'approved', 'closed'}):
        raise ValueError('invalid_snapshot_metadata')
    for name in ('feature_sha256', 'taxonomy_sha256', 'policy_sha256'):
        _hash(payload[name])
    captured = _time(payload['captured_at'])
    dates = {name: _time(payload[name]) if payload[name] is not None else None
             for name in ('semester_start', 'semester_end', 'closed_at')}
    ordered = [dates[name] for name in ('semester_start', 'semester_end', 'closed_at') if dates[name] is not None]
    if ordered != sorted(ordered) or any(value > captured for value in ordered):
        raise ValueError('invalid_semester_timestamp_order')
    if payload['closed_at'] is not None and payload['status'] != 'closed':
        raise ValueError('closure_timestamp_requires_closed_status')
    errors = validate_provenance(payload['assignments'], payload['outcomes'], payload['semester_id'],
                                 artifacts=payload['artifacts'], captured_at=payload['captured_at'])
    if errors:
        raise ValueError('invalid_record_provenance: ' + json.dumps(errors, ensure_ascii=True))
    if payload['status'] == 'closed' and (any(value is None for value in dates.values())
                                         or not payload['assignments']
                                         or any(row.get('review_status') != 'approved' for row in payload['assignments'])):
        raise ValueError('closed_semester_requires_explicit_dates_and_approved_assignments')


def verify_snapshot(store, snapshot_id):
    """Verify immutable manifest identity, complete artifact inventory and source refs."""
    _hash(snapshot_id)
    folder = Path(store).resolve() / snapshot_id
    manifest_path = folder / 'manifest.json'
    if folder.is_symlink() or manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError('invalid_snapshot_manifest_path')
    if manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError('snapshot_manifest_size_limit')
    encoded = manifest_path.read_bytes()
    manifest = json.loads(encoded.decode('utf-8'))
    if not isinstance(manifest, dict) or not isinstance(manifest.get('artifacts'), dict) or not manifest['artifacts']:
        raise ValueError('invalid_snapshot_manifest')
    payload = {key: value for key, value in manifest.items() if key != 'snapshot_id'}
    if encoded != _json(manifest) or manifest.get('snapshot_id') != snapshot_id or _sha(payload) != snapshot_id:
        raise ValueError('snapshot_manifest_hash_mismatch')
    expected = {'manifest.json'}
    for name, artifact in payload['artifacts'].items():
        _artifact_name(name)
        path = folder / 'files' / name
        expected.add('files/' + name)
        if (path.is_symlink() or not path.resolve().is_relative_to(folder.resolve()) or not path.is_file()
                or path.stat().st_size != artifact['size_bytes'] or _digest(path) != artifact['sha256']):
            raise ValueError('snapshot_artifact_hash_mismatch')
    actual = set()
    for path in folder.rglob('*'):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError('unexpected_snapshot_artifact_path')
        if path.is_file():
            actual.add(path.relative_to(folder).as_posix())
    if actual != expected:
        raise ValueError('unexpected_snapshot_artifacts')
    _validate(payload)
    return manifest


def create_snapshot(store, *, semester_id, captured_at, feature_sha256, taxonomy_sha256,
                    policy_sha256, files, status='draft', semester_start=None, semester_end=None,
                    closed_at=None, assignments=None, outcomes=None):
    """Atomically ingest supplied bytes; repeated exact content returns the same ID."""
    if not isinstance(files, dict) or not files:
        raise ValueError('supplied_snapshot_files_required')
    names = sorted(_artifact_name(name) for name in files)
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError('case_colliding_artifact_paths')
    for name in names:
        if any(str(parent).casefold() in {n.casefold() for n in names} for parent in PurePosixPath(name).parents if str(parent) != '.'):
            raise ValueError('conflicting_artifact_paths')
    prefixes = {}
    for name in names:
        for prefix in [PurePosixPath(name), *PurePosixPath(name).parents]:
            value = str(prefix)
            if value.casefold() in prefixes and prefixes[value.casefold()] != value:
                raise ValueError('case_colliding_artifact_paths')
            prefixes[value.casefold()] = value
    sources = {name: Path(files[name]) for name in names}
    if any(not source.is_file() for source in sources.values()):
        raise ValueError('supplied_artifact_file_required')
    artifacts = {name: {'sha256': _digest(source), 'size_bytes': source.stat().st_size}
                 for name, source in sources.items()}
    assignments = [] if assignments is None else assignments
    outcomes = [] if outcomes is None else outcomes
    payload = {'schema_version': SCHEMA_VERSION, 'semester_id': semester_id, 'status': status,
               'captured_at': captured_at, 'semester_start': semester_start, 'semester_end': semester_end,
               'closed_at': closed_at, 'feature_sha256': feature_sha256, 'taxonomy_sha256': taxonomy_sha256,
               'policy_sha256': policy_sha256, 'artifacts': artifacts,
               'assignments': assignments, 'outcomes': outcomes,
               'outcomes_status': 'supplied_records' if outcomes else 'unknown_not_supplied',
               'provenance_validation_scope': 'Artifact hashes, record identities, supplied review metadata and timestamps; no automatic human approval or semantic outcome verification.'}
    _validate(payload)
    payload = json.loads(_json(payload))  # Detach all caller-owned mutable values.
    snapshot_id = _sha(payload)
    manifest = {'snapshot_id': snapshot_id, **payload}
    encoded = _json(manifest)
    if len(encoded) > MAX_MANIFEST_BYTES:
        raise ValueError('snapshot_manifest_size_limit')
    store = Path(store).resolve()
    store.mkdir(parents=True, exist_ok=True)
    target = store / snapshot_id
    if target.exists():
        return verify_snapshot(store, snapshot_id)
    with tempfile.TemporaryDirectory(prefix='.pending-', dir=store) as temporary:
        folder = Path(temporary) / 'snapshot'
        folder.mkdir()
        for name, source in sources.items():
            destination = folder / 'files' / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            if (_digest(destination) != artifacts[name]['sha256'] or _digest(source) != artifacts[name]['sha256']
                    or destination.stat().st_size != artifacts[name]['size_bytes']):
                raise ValueError('source_artifact_changed_during_ingest')
        (folder / 'manifest.json').write_bytes(encoded)
        # Never replace an existing snapshot; a concurrent identical ingest is verified.
        try:
            folder.rename(target)
        except OSError:
            if not target.exists():
                raise
        return verify_snapshot(store, snapshot_id)


def outcome_availability(outcomes, *, as_of):
    """Expose future-label/prediction-time exclusions without deleting later outcomes."""
    cutoff = _time(as_of)
    available, blocked = [], []
    for row in outcomes:
        codes = []
        if row.get('review_status') != 'approved':
            codes.append('not_approved')
        for field, code in [('observed_at', 'not_observed_as_of'), ('reviewed_at', 'not_reviewed_as_of')]:
            try:
                if _time(row.get(field)) > cutoff:
                    codes.append(code)
            except ValueError:
                codes.append('invalid_' + field)
        if codes:
            blocked.append({'outcome_id': row.get('outcome_id'), 'codes': codes})
        else:
            available.append(row['outcome_id'])
    return {'as_of': as_of, 'available_outcome_ids': available, 'blocked': blocked,
            'scope': 'Availability filter only; source-bound snapshot validation remains required.'}


def drift_report(previous_rows, current_rows, *, tag_fields, required_fields):
    """Descriptive per-namespace prevalence and missingness; never fills missing data."""
    def missing(value):
        return value is None or isinstance(value, str) and not value.strip() or isinstance(value, list) and not value

    def counts(rows, field):
        result = Counter()
        for row in rows:
            value = row.get(field)
            if missing(value):
                continue
            tags = value.split(';') if isinstance(value, str) else value
            if not isinstance(tags, list) or any(not isinstance(tag, str) or not re.fullmatch('[a-z0-9_]+', tag) for tag in tags):
                raise ValueError('invalid_drift_tag_column')
            result.update(set(tags))
        return result

    tags, missingness = {}, {}
    for field in tag_fields:
        previous, current = counts(previous_rows, field), counts(current_rows, field)
        prevalence = {}
        for tag in sorted(set(previous) | set(current)):
            before = previous[tag]/len(previous_rows) if previous_rows else None
            after = current[tag]/len(current_rows) if current_rows else None
            prevalence[tag] = {'previous': before, 'current': after, 'delta': after-before if before is not None and after is not None else None}
        tags[field] = {'new_tags': sorted(set(current)-set(previous)), 'removed_tags': sorted(set(previous)-set(current)),
                       'prevalence': prevalence}
    for field in required_fields:
        missingness[field] = {}
        for label, rows in [('previous', previous_rows), ('current', current_rows)]:
            count = sum(missing(row.get(field)) for row in rows)
            missingness[field][label] = {'missing': count, 'rows': len(rows), 'rate': count/len(rows) if rows else None}
    return {'schema_version': 'semester-drift/1.0', 'tags': tags, 'missingness': missingness,
            'scope': 'Descriptive source prevalence only; no outcome/proficiency inference or fabricated thresholds.'}
