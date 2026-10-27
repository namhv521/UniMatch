import importlib.util
from pathlib import Path

import pytest


def module():
    path = Path(__file__).resolve().parents[2] / 'src/data_pipeline/evidence_quality.py'
    assert path.exists(), 'Evidence quality rubric implementation missing'
    spec = importlib.util.spec_from_file_location('evidence_quality', path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def tag(**checks):
    return {'tag': 'python', 'group': 'programming_languages', 'output_column': 'programming_languages',
            'source_field': 'technology_mentions', 'matched_text': 'Python', 'start': 0, 'end': 6,
            'source_sha256': 'b' * 64, 'evidence_sha256': 'c' * 64,
            'checks': {'source': 'pass', 'span': 'pass', 'semantic': 'pass', **checks}}


def second_tag(**checks):
    return {**tag(**checks), 'tag': 'java', 'matched_text': 'Java', 'end': 4}


def test_completed_checks_return_observed_fraction_and_raw_counts():
    result = module().evaluate_tag_checks('record-1', 'a' * 64, [tag(), second_tag(semantic='fail')])
    assert result['score'] == 0.5
    assert (result['passed'], result['total'], result['failed'], result['pending']) == (1, 2, 1, 0)
    assert result['metric'] == 'evidence_check_fraction'
    assert result['is_probability'] is False and result['is_proficiency'] is False


@pytest.mark.parametrize('state', ['pending', 'uncertain'])
def test_untested_or_uncertain_tag_does_not_receive_numeric_score(state):
    result = module().evaluate_tag_checks('record-1', 'a' * 64, [tag(), second_tag(semantic=state)])
    assert result['score'] is None
    assert result['passed'] == 1 and result['pending'] == 1 and result['total'] == 2


def test_zero_tags_and_missing_checks_remain_unknown():
    helper = module()
    assert helper.evaluate_tag_checks('record-1', 'a' * 64, [])['score'] is None
    one = tag()
    del one['checks']['semantic']
    assert helper.evaluate_tag_checks('record-1', 'a' * 64, [one])['score'] is None


def test_stable_tag_identity_does_not_change_when_verdict_changes():
    helper = module()
    first = helper.evaluate_tag_checks('record-1', 'a' * 64, [tag()])
    changed = helper.evaluate_tag_checks('record-1', 'a' * 64, [tag(semantic='fail')])
    assert first['tags'][0]['tag_id'] == changed['tags'][0]['tag_id']
    assert first['tags'][0]['tag_sha256'] == changed['tags'][0]['tag_sha256']
    assert first['assessment_sha256'] != changed['assessment_sha256']
    assert first == helper.evaluate_tag_checks('record-1', 'a' * 64, [tag()])
    assert first['tags'][0]['tag_id'] != helper.evaluate_tag_checks('record-2', 'a' * 64, [tag()])['tags'][0]['tag_id']


def test_malformed_status_and_record_hash_are_rejected():
    helper = module()
    with pytest.raises(ValueError, match='invalid_check_status'):
        helper.evaluate_tag_checks('record-1', 'a' * 64, [tag(semantic='approved')])
    with pytest.raises(ValueError, match='invalid_record_binding'):
        helper.evaluate_tag_checks('record-1', 'not-a-hash', [tag()])
    with pytest.raises(ValueError, match='duplicate_tag_identity'):
        helper.evaluate_tag_checks('record-1', 'a' * 64, [tag(), tag()])
    with pytest.raises(ValueError, match='duplicate_tag_identity'):
        helper.evaluate_tag_checks('record-1', 'a' * 64, [tag(), {**tag(), 'evidence_sha256': 'd' * 64}])
    with pytest.raises(ValueError, match='invalid_record_binding'):
        helper.evaluate_tag_checks('record-1', None, [tag()])
    with pytest.raises(ValueError, match='invalid_check_status'):
        helper.evaluate_tag_checks('record-1', 'a' * 64, [tag(semantic=[])])
