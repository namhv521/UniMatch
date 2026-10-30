import csv
import importlib.util
import json
from pathlib import Path

import pytest


def contract():
    path = Path(__file__).resolve().parents[2] / 'src/data_pipeline/csv_contracts.py'
    assert path.exists(), 'CSV contracts implementation is missing'
    spec = importlib.util.spec_from_file_location('csv_contracts', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def row(entity='students', **updates):
    value = {'schema_version': '1.0', 'semester_id': 'TEST-TERM', 'source_type': 'technical_fixture',
             'source_sha256': 'a' * 64, 'review_status': 'approved'}
    if entity == 'students':
        value.update(student_id='TEST-001', thesis_title='Technical C++ / C# parser example', source_file='fixture.pdf')
    else:
        value.update(advisor_id='ADVISOR-001', advisor_name='Technical fixture', source_url='https://example.test/lecturer/1')
    return value | updates


def csv_file(path, entity='students', rows=None, *, headers=None, bom=True):
    module = contract()
    headers = headers or module.export_json_schema(entity)['x-csv-headers']
    with path.open('w', encoding='utf-8-sig' if bom else 'utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        for value in rows or []:
            writer.writerow(value)


@pytest.mark.parametrize('entity', ['students', 'advisors'])
def test_headers_match_supplied_templates_and_models_generate_schema(entity):
    module = contract()
    schema = module.export_json_schema(entity)
    template = Path(__file__).resolve().parents[2] / f'docs/{entity}_import.csv'
    with template.open(encoding='utf-8-sig', newline='') as stream:
        headers = next(csv.reader(stream))
    assert schema['x-csv-headers'] == headers
    assert list(schema['properties']) == headers
    assert schema['additionalProperties'] is False
    assert module.validate_row(row(entity), entity, mode='gold') == []


def test_pending_is_staging_only_and_missing_proficiency_stays_nullable():
    module = contract()
    value = row(review_status='pending', skill_proficiency_json='')
    assert module.validate_row(value, 'students', mode='staging') == []
    assert module.validate_row(value, 'students', mode='gold')
    model = module.MODELS['students'].model_validate(value)
    assert model.skill_proficiency_json is None


@pytest.mark.parametrize('updates', [
    {'schema_version': '2.0'}, {'student_id': ''}, {'source_sha256': 'A' * 64},
    {'source_sha256': 'a' * 63}, {'source_url': 'javascript:bad'},
    {'extracted_at': '2026-10-21T12:00:00'}, {'extracted_at': '123456789'},
    {'extracted_at': 'not-a-date'}, {'unexpected': 'column'},
])
def test_invalid_scalar_contract_is_rejected(updates):
    assert contract().validate_row(row(**updates), 'students')


def test_timezone_evidence_tags_and_taxonomy_membership():
    module = contract()
    value = row(extracted_at='2026-10-21T12:00:00+07:00', skills_tags='cpp;csharp',
                skill_evidence_type='self_reported', skill_evidence_refs='source:paragraph:1', skill_confidence='0.7')
    assert module.validate_row(value, 'students', taxonomy_ids={'cpp', 'csharp'}) == []
    assert module.validate_row(value, 'students', taxonomy_ids={'cpp'})
    for field in ('skill_evidence_type', 'skill_evidence_refs', 'skill_confidence'):
        assert module.validate_row(value | {field: ''}, 'students')
    for tags in ('Cpp', 'cpp;cpp', 'cpp;;csharp', 'cpp;not canonical'):
        assert module.validate_row(value | {'skills_tags': tags}, 'students')


@pytest.mark.parametrize('proficiency', [
    '{"python":0}', '{"python":6}', '{"python":true}', '{"python":1.5}',
    '{"python":NaN}', '{"python":3,"python":4}', '[1,2]', '{"unknown":3}',
])
def test_proficiency_rejects_unverified_invalid_or_undeclared_values(proficiency):
    value = row(skills_tags='python', skill_evidence_type='self_reported',
                skill_evidence_refs='source:paragraph:2', skill_confidence='1', skill_proficiency_json=proficiency)
    assert contract().validate_row(value, 'students', taxonomy_ids={'python'})


def test_proficiency_only_with_declared_tags_and_evidence_no_thesis_mastery():
    module = contract()
    value = row(skills_tags='python', skill_evidence_type='self_reported', skill_evidence_refs='survey:scale1to5',
                skill_confidence='1', skill_proficiency_json='{"python":3}')
    assert module.validate_row(value, 'students') == []
    assert module.validate_row(value | {'skill_evidence_type': 'inferred_from_thesis'}, 'students')
    assert module.validate_row(value | {'skills_tags': ''}, 'students')


@pytest.mark.parametrize('value', ['=SUM(1,2)', '+cmd', '-1+2', '@SUM(1,2)', '\t=SUM(1,2)', '  =HYPERLINK("x")', '\u00a0=SUM(1,2)'])
def test_formula_injection_rejected_but_cpp_csharp_prose_is_valid(value):
    module = contract()
    assert module.validate_row(row(thesis_title=value), 'students')
    assert module.validate_row(row(thesis_title='C++ and C# technical description'), 'students') == []


def test_capacity_is_nullable_for_gold_but_allocation_requires_confirmed_participation():
    module = contract()
    value = row('advisors')
    assert module.validate_row(value, 'advisors', mode='gold') == []
    assert module.validate_row(value, 'advisors', mode='allocation')
    ready = value | {'active_for_semester': 'true', 'capacity_max': '3', 'existing_load': '0'}
    assert module.validate_row(ready, 'advisors', mode='allocation') == []
    for updates in ({'existing_load': '4'}, {'capacity_max': '-1'}, {'capacity_min': '4'},
                    {'capacity_max': True}, {'existing_load': ''}, {'active_for_semester': 'false'}):
        assert module.validate_row(ready | updates, 'advisors', mode='allocation')


def test_csv_duplicate_headers_row_overflow_and_duplicate_semester_ids(tmp_path):
    module = contract()
    path = tmp_path / 'students.csv'
    csv_file(path, rows=[row(), row()])
    report = module.validate_csv(path, 'students', mode='gold')
    assert not report['valid']
    assert any(e['code'] == 'duplicate_identity' for e in report['errors'])
    csv_file(path, rows=[row(), row(semester_id='ANOTHER-TERM')], bom=False)
    assert module.validate_csv(path, 'students')['valid']
    path.write_text('schema_version,schema_version\n1.0,1.0\n', encoding='utf-8')
    assert any(e['code'] == 'duplicate_headers' for e in module.validate_csv(path, 'students')['errors'])
    csv_file(path)
    with path.open('a', encoding='utf-8') as stream:
        stream.write(','.join([''] * 41) + '\n')
    assert any(e['code'] == 'row_width' for e in module.validate_csv(path, 'students')['errors'])


def test_csv_header_missing_extra_bad_encoding_size_and_empty_gold(tmp_path, monkeypatch):
    module = contract()
    path = tmp_path / 'students.csv'
    path.write_text('student_id,unknown\nx,y\n', encoding='utf-8')
    assert any(e['code'] == 'header_contract' for e in module.validate_csv(path, 'students')['errors'])
    path.write_bytes(b'\xff\xfe\x00\x00')
    assert not module.validate_csv(path, 'students')['valid']
    csv_file(path)
    assert module.validate_csv(path, 'students', mode='staging')['valid']
    assert not module.validate_csv(path, 'students', mode='gold')['valid']
    monkeypatch.setattr(module, 'MAX_CSV_BYTES', 1)
    assert any(e['code'] == 'file_size_limit' for e in module.validate_csv(path, 'students')['errors'])


def test_taxonomy_group_context_rejects_global_id_in_wrong_column_for_row_and_csv(tmp_path):
    module = contract()
    groups = {'programming_languages': {'python', 'cpp'}, 'topic_tags': {'nlp'}}
    value = row(programming_languages='nlp', skill_evidence_type='self_reported',
                skill_evidence_refs='technical:paragraph:1', skill_confidence='0.8')
    assert module.validate_row(value, 'students', taxonomy_ids={'python', 'cpp', 'nlp'}) == []
    errors = module.validate_row(value, 'students', taxonomy_ids={'python', 'cpp', 'nlp'}, taxonomy_groups=groups)
    assert any(e['field'] == 'programming_languages' and e['code'] == 'taxonomy_group_mismatch' for e in errors)
    path = tmp_path / 'technical.csv'
    csv_file(path, rows=[value])
    assert not module.validate_csv(path, 'students', taxonomy_groups=groups)['valid']
    assert module.validate_row(value | {'programming_languages': 'cpp'}, 'students', taxonomy_groups=groups) == []
    assert module.validate_row(value | {'programming_languages': 'cpp'}, 'students', taxonomy_groups={})


def test_advisor_topic_projection_and_skill_group_fallback():
    module = contract()
    groups = {'topic_tags': {'nlp'}, 'programming_languages': {'python'}}
    advisor = row('advisors', expertise_topic_tags='nlp', expertise_evidence_type='verified_web',
                  expertise_evidence_refs='https://example.test/research', expertise_confidence='0.8')
    assert module.validate_row(advisor, 'advisors', taxonomy_groups=groups) == []
    assert module.validate_row(advisor | {'expertise_topic_tags': 'python'}, 'advisors', taxonomy_groups=groups)
    student = row(skills_tags='python', skill_evidence_type='self_reported',
                  skill_evidence_refs='technical:paragraph:1', skill_confidence='0.8')
    assert module.validate_row(student, 'students', taxonomy_groups=groups) == []
    assert module.validate_row(student | {'skills_tags': 'nlp'}, 'students', taxonomy_groups=groups)
    schema = module.export_json_schema('advisors')
    assert schema['x-context-validation']['taxonomy_group_projections']['expertise_topic_tags'] == 'topic_tags'


def test_long_evidence_json_has_dedicated_bound_without_relaxing_other_text(tmp_path):
    module = contract()
    evidence = json.dumps([{'locator': 'technical:paragraph:1', 'snippet': 'x' * 71460}])
    value = row(programming_languages='python', skill_evidence_type='self_reported',
                skill_evidence_refs=evidence, skill_confidence='0.8')
    assert len(evidence.encode()) > 71500
    assert module.validate_row(value, 'students') == []
    path = tmp_path / 'technical.csv'
    csv_file(path, rows=[value])
    assert module.validate_csv(path, 'students')['valid']
    assert module.validate_row(value | {'skill_evidence_refs': 'x' * (128*1024 + 1)}, 'students')
    assert module.validate_row(value | {'thesis_title': 'x' * 20001}, 'students')
    assert module.validate_row(value | {'skill_confidence': ''}, 'students')
