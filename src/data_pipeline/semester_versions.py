"""Owner-defined non-overlapping semester windows; precision is never fabricated."""
from __future__ import annotations

from datetime import date, datetime
from calendar import monthrange
import re
from zoneinfo import ZoneInfo


TIMEZONE = ZoneInfo('Asia/Saigon')
SEMESTER_BY_VERSION = {'V1': '2024.1', 'V2': '2024.2', 'V3': '2025.1', 'V4': '2025.2'}
VERSION_WINDOWS = (
    {'version': 'V1', 'semester_id': '2024.1', 'start_inclusive': None, 'end_exclusive': '2025-01-01'},
    {'version': 'V2', 'semester_id': '2024.2', 'start_inclusive': '2025-01-01', 'end_exclusive': '2025-06-01'},
    {'version': 'V3', 'semester_id': '2025.1', 'start_inclusive': '2025-06-01', 'end_exclusive': '2026-01-01'},
    {'version': 'V4', 'semester_id': '2025.2', 'start_inclusive': '2026-01-01', 'end_exclusive': '2026-06-01'},
)


def _version(day):
    for row in VERSION_WINDOWS:
        start, end = row['start_inclusive'], row['end_exclusive']
        if (start is None or day >= date.fromisoformat(start)) and day < date.fromisoformat(end):
            return row['version']
    return 'after_V4'


def classify_version(value=None, *, year=None):
    """Classify date, timezone-aware timestamp, YYYY-MM, year, or term candidate.

    This groups event time only. A resolved version is NOT evidence that a feature
    existed at decision time, and never sets historical_training_eligible=True.
    """
    if value is not None and year is not None:
        raise ValueError('provide_value_or_year_not_both')
    if year is not None:
        value = year
    result = {'version': None, 'semester_id': None, 'status': 'unknown', 'possible_versions': [],
              'precision': None, 'event_date': None, 'event_month': None, 'event_month_iso': None, 'event_year': None,
              'academic_cohort': None, 'training_semester': None,
              'event_interval_lower_bound': None, 'event_interval_upper_bound': None,
              'historical_training_eligible': False, 'timezone': 'Asia/Saigon'}
    if value is None or value == '':
        return result
    if isinstance(value, bool):
        raise TypeError('boolean_is_not_date_or_year')
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError('timestamp_timezone_required')
        day = value.astimezone(TIMEZONE).date()
        result.update(precision='timestamp', event_date=day.isoformat(), event_year=day.year)
    elif isinstance(value, date):
        day = value
        result.update(precision='day', event_date=day.isoformat(), event_year=day.year)
    elif isinstance(value, int) or (isinstance(value, str) and re.fullmatch(r'\d{4}', value)):
        number = int(value)
        if not 1000 <= number <= 9999:
            raise ValueError('invalid_event_year')
        possible = ['V1'] if number <= 2024 else (['V2', 'V3'] if number == 2025 else (['V4', 'after_V4'] if number == 2026 else ['after_V4']))
        result.update(precision='year', event_year=number, possible_versions=possible)
        result.update(event_interval_lower_bound=f'{number}-01-01', event_interval_upper_bound=f'{number}-12-31',
                      status='ambiguous')
        if number <= 2024:
            result.update(version='V1', semester_id='2024.1', training_semester='2024.1',
                          status='historical_training_only')
        return result
    elif isinstance(value, str) and value in SEMESTER_BY_VERSION.values():
        result.update(status='term_candidate', precision='academic_term', candidate_semester_id=value,
                      possible_versions=[k for k, v in SEMESTER_BY_VERSION.items() if v == value])
        return result
    elif isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}', value):
        day = date.fromisoformat(value + '-01')
        result.update(precision='month', event_month=day.month, event_month_iso=value, event_year=day.year)
    elif isinstance(value, str):
        if 'T' in value or ' ' in value:
            timestamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
            return classify_version(timestamp)
        day = date.fromisoformat(value)
        result.update(precision='day', event_date=day.isoformat(), event_year=day.year)
    else:
        raise TypeError('date_timestamp_month_or_year_required')
    version = _version(day)
    result.update(version=version if version != 'after_V4' else None,
                  semester_id=SEMESTER_BY_VERSION.get(version), possible_versions=[version],
                  status='classified' if version != 'after_V4' else 'training_unmapped')
    cohort = f'{day.year}.1' if day.month >= 9 else f'{day.year - 1}.{2 if day.month <= 5 else 3}'
    upper = day if result['event_date'] else day.replace(day=monthrange(day.year, day.month)[1])
    result.update(academic_cohort=cohort, training_semester=result['semester_id'],
                  event_month=day.month, event_month_iso=day.strftime('%Y-%m'),
                  event_interval_lower_bound=day.isoformat(), event_interval_upper_bound=upper.isoformat())
    return result
