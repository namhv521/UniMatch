from importlib import import_module, util

import pytest


def classify(*args, **kwargs):
    assert util.find_spec('src.data_pipeline.semester_versions'), 'semester version classifier missing'
    return import_module('src.data_pipeline.semester_versions').classify_version(*args, **kwargs)


@pytest.mark.parametrize(('value', 'version'), [
    ('2024-12-31', 'V1'), ('2025-01-01', 'V2'), ('2025-06-30', 'V3'),
    ('2025-07-01', 'V3'), ('2025-12-31', 'V3'), ('2026-01-01', 'V4'),
    ('2026-06-30', None), ('2023-02-28', 'V1'),
])
def test_semester_boundaries(value, version):
    assert classify(value)['version'] == version


def test_timestamp_uses_saigon_local_boundary():
    assert classify('2024-12-31T18:00:00Z')['version'] == 'V2'
    with pytest.raises(ValueError, match='timezone'):
        classify('2025-01-01T00:00:00')


def test_year_only_does_not_invent_month_or_historical_availability():
    result = classify(year=2025)
    assert result['status'] == 'ambiguous'
    assert result['possible_versions'] == ['V2', 'V3']
    assert result['event_date'] is None and result['historical_training_eligible'] is False
    assert classify(year=2024)['version'] == 'V1'
    assert classify(year=2024)['status'] == 'historical_training_only'
    assert classify(year=2026)['possible_versions'] == ['V4', 'after_V4']


def test_month_precision_is_retained_and_can_resolve_half_year():
    result = classify('2025-06')
    assert result['version'] == 'V3' and result['precision'] == 'month'
    assert result['event_date'] is None
    assert result['event_month'] == 6 and result['event_month_iso'] == '2025-06'
    assert result['event_interval_upper_bound'] == '2025-06-30'


@pytest.mark.parametrize(('value', 'cohort', 'version', 'training'), [
    ('2024-01', '2023.2', 'V1', '2024.1'),
    ('2024-06', '2023.3', 'V1', '2024.1'),
    ('2024-07', '2023.3', 'V1', '2024.1'),
    ('2024-08', '2023.3', 'V1', '2024.1'),
    ('2024-09', '2024.1', 'V1', '2024.1'),
    ('2025-01', '2024.2', 'V2', '2024.2'),
    ('2025-06', '2024.3', 'V3', '2025.1'),
    ('2025-07', '2024.3', 'V3', '2025.1'),
    ('2025-08', '2024.3', 'V3', '2025.1'),
    ('2025-09', '2025.1', 'V3', '2025.1'),
    ('2026-01', '2025.2', 'V4', '2025.2'),
    ('2026-07', '2025.3', None, None),
    ('2026-09', '2026.1', None, None),
])
def test_latest_seasonal_cohort_rule_preserves_summer_label(value, cohort, version, training):
    result = classify(value)
    assert result['academic_cohort'] == cohort
    assert result['version'] == version
    assert result['training_semester'] == training


def test_term_code_is_candidate_not_a_fabricated_date():
    result = classify('2024.2')
    assert result['version'] is None and result['status'] == 'term_candidate'
    assert result['possible_versions'] == ['V2'] and result['event_date'] is None


def test_unknown_and_out_of_scope():
    assert classify(None)['status'] == 'unknown'
    assert classify('2026-07-01')['status'] == 'training_unmapped'
    with pytest.raises((ValueError, TypeError)):
        classify(True)
    with pytest.raises(ValueError):
        classify('2025-02-30')
