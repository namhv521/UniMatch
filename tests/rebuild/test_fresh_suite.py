import importlib
import importlib.util
import json
from pathlib import Path

import pytest


def module():
    assert importlib.util.find_spec('src.features.fresh_suite'), 'fresh suite adapter is missing'
    return importlib.import_module('src.features.fresh_suite')


def test_publication_cutoff_uses_precision_without_guessing_months():
    m = module()
    rows = [
        {'advisor_id': 'a', 'title_text': 'Old science (2023)', 'publication_year': 2023},
        {'advisor_id': 'a', 'title_text': 'Uncertain half (2025)', 'publication_year': 2025},
        {'advisor_id': 'a', 'title_text': 'June article', 'publication_year': 2025,
         'publication_date': '2025-06', 'date_precision': 'month'},
        {'advisor_id': 'a', 'title_text': 'July article', 'publication_year': 2025,
         'publication_date': '2025-07', 'date_precision': 'month'},
    ]
    used, withheld = m.select_publications(rows, 'V2')
    assert [r['title_text'] for r in used] == ['Old science (2023)', 'June article']
    assert len(withheld) == 2
    used, _ = m.select_publications(rows, 'V3')
    assert len(used) == 4


def test_proxy_mode_must_be_explicit():
    with pytest.raises(ValueError, match='explicit_retrospective_proxy'):
        module().prepare_suite('unused', 'unused', version='V1', mode='prospective')


def test_suite_cannot_write_into_captured_source_folder(tmp_path):
    m = module()
    root = tmp_path / 'data_rebuild/nested_rl_20261028/run'
    (root / 'students').mkdir(parents=True)
    with pytest.raises(ValueError, match='immutable_source'):
        m.prepare_suite(root, root / 'students/derived', version='V1', mode=m.MODE)


def test_invalid_publication_month_or_inconsistent_year_is_withheld():
    m = module()
    rows = [{'publication_date': '2023-99', 'date_precision': 'month', 'publication_year': 2023},
            {'publication_date': '2023-02-31', 'date_precision': 'day', 'publication_year': 2023},
            {'publication_date': '2023-05', 'date_precision': 'month', 'publication_year': 2025}]
    assert m.select_publications(rows, 'V2') == ([], rows)


def test_event_bound_uses_recorded_range_end_without_inventing_event_date():
    m = module()
    assert m.event_upper_bound({'event_year': 2025, 'event_interval_upper_bound': '2025-06-30'}) == '2025-06-30T23:59:59+07:00'


def test_student_identity_keeps_holdout_across_semesters():
    m = module()
    ids = [f's{i}' for i in range(12)]
    first = {sid: m.student_split(sid, 42) for sid in ids}
    later = {sid: m.student_split(sid, 42) for sid in reversed(ids[3:])}
    assert all(first[sid] == split for sid, split in later.items())
    assert set(first.values()) == {'train', 'validation', 'test'}


def test_frozen_encoder_does_not_learn_later_vocabulary():
    m = module()
    vectorizer, frozen = m.fit_encoder(['database python', 'database java'])
    restored = m.restore_encoder(frozen)
    assert vectorizer.transform(['database']).toarray().tolist() == restored.transform(['database']).toarray().tolist()
    assert 'quant' not in frozen['vocabulary']


def test_prepare_suite_source_isolation_and_no_invented_human_preferences(tmp_path):
    m = module()
    root = tmp_path / 'data_rebuild/nested_rl_20261028/run'
    for name in ('students', 'faculty'):
        (root / name).mkdir(parents=True)
    students = [{'candidate_id': f'candidate{i}', 'source_sha256': str(i) * 64,
        'fields': {'student_id': {'value': f's{i}'}, 'thesis_title': {'value': f'Python database project {i}'}},
        'temporal': {'version': 'V1', 'status': 'classified', 'event_year': 2024},
        'provenance_validation': 'passed', 'captured_at': '2026-10-28T00:00:00Z'} for i in range(12)]
    students += [{'candidate_id': f'later{i}', 'source_sha256': f'later{i}',
        'fields': {'student_id': {'value': f'later{i}'}, 'thesis_title': {'value': f'Python database quantum project {i}'}},
        'temporal': {'version': 'V2', 'event_year': 2025, 'event_month': 4},
        'provenance_validation': 'passed', 'captured_at': '2026-10-28T00:00:00Z'} for i in range(30)]
    m.write_jsonl(root / 'students/students.jsonl', students)
    m.write_jsonl(root / 'faculty/faculty.jsonl', [{'advisor_id': 'a', 'advisor_name': 'Teacher A'},
                                               {'advisor_id': 'b', 'advisor_name': 'Teacher B'}])
    m.write_jsonl(root / 'faculty/publications.jsonl', [
        {'advisor_id': 'a', 'title_text': 'Python database methods', 'publication_year': 2023},
        {'advisor_id': 'b', 'title_text': 'Java database methods', 'publication_year': 2024},
        {'advisor_id': 'a', 'title_text': 'Future leakage secretword', 'publication_year': 2026}])
    for name in ('students', 'faculty'):
        folder = root / name
        m.write_json(folder / 'manifest.json', {'artifacts': {p.name: m.digest(p) for p in folder.iterdir()}})
    result = m.prepare_suite(root, root / 'suite', version='V1', mode='retrospective_document_proxy')
    assert result['status'] == 'ready_research_only'
    suite = json.loads((root / 'suite/suite.json').read_text(encoding='utf-8'))
    sets = [set(suite[name]['student_ids']) for name in ('validation', 'test')]
    train = {s for p in suite['train'] for s in p['student_ids']}
    assert not (train & sets[0] or train & sets[1] or sets[0] & sets[1])
    assert all(not any(any(row) for row in p['preference_known']) for p in [*suite['train'], suite['validation'], suite['test']])
    assert suite['contract']['scope'] == 'retrospective_document_proxy'
    used = m.read_jsonl(root / 'suite/publications_used.jsonl')
    assert len(used) == 2
    assert suite['round']['availability_assumption'] == 'retrospective_event_time_proxy'
    later = m.prepare_suite(root, root / 'later_suite', version='V2', mode=m.MODE,
                            frozen_encoder=root / 'suite/encoder.json')
    assert later['status'] == 'ready_research_only'
    assert later['encoder_sha256'] == result['encoder_sha256']
    assert 'quant' not in json.loads((root / 'suite/encoder.json').read_text())['vocabulary']
    with pytest.raises(FileExistsError):
        m.prepare_suite(root, root / 'suite', version='V1', mode='retrospective_document_proxy')
