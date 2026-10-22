"""Versioned research splits: group related documents before any learned transform."""
import hashlib
import json
import math
import random
import re
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher


SPLIT_VERSION = 'non-temporal-connected-student-groups-v1'
NEAR_TITLE_THRESHOLD = .92


def _normalized_title(value):
    return ' '.join(re.findall(r'\w+', unicodedata.normalize('NFKC', value).casefold()))


def make_grouped_split(students: list[dict], seed=42, train_fraction=.7, validation_fraction=.15):
    """Return ID-keyed research partitions; identity keys are never learned features.

    Call on canonical gold CSV rows. Duplicate IDs require upstream reconciliation.
    Shared source/alias hashes and exact/near titles form transitive components.
    Fractions allocate independent groups, not documents; large groups can skew
    student counts. Test membership must be preserved untouched during selection.
    """
    fractions = (train_fraction, validation_fraction)
    if (type(seed) is not int or any(type(f) not in (int, float) or not math.isfinite(f) or not 0 < f < 1
                                   for f in fractions) or sum(fractions) >= 1):
        raise ValueError('invalid_split_configuration')
    index = {}
    for row in students:
        key = row.get('student_id')
        if not isinstance(key, str) or not key.strip() or key != key.strip():
            raise ValueError('invalid_student_id')
        if key in index:
            raise ValueError('duplicate_student_id')
        title = row.get('thesis_title')
        if not isinstance(title, str) or not _normalized_title(title):
            raise ValueError('invalid_thesis_title')
        hashes = [row.get('source_sha256')]
        aliases = row.get('source_aliases', [])
        if not isinstance(aliases, list) or any(not isinstance(a, dict) for a in aliases):
            raise ValueError('invalid_source_aliases')
        hashes.extend(alias.get('source_sha256') for alias in aliases)
        if any(not isinstance(h, str) or not re.fullmatch('[0-9a-f]{64}', h) for h in hashes):
            raise ValueError('invalid_source_sha256')
        index[key] = {'title': _normalized_title(title), 'hashes': set(hashes)}
    keys = sorted(index)
    parent = {key: key for key in keys}

    def find(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(left, right):
        a, b = sorted((find(left), find(right)))
        parent[b] = a

    reasons = Counter()
    for position, left in enumerate(keys):
        for right in keys[position + 1:]:
            a, b = index[left], index[right]
            if a['hashes'] & b['hashes']:
                union(left, right)
                reasons['shared_source_or_alias_sha256'] += 1
            if a['title'] == b['title']:
                union(left, right)
                reasons['exact_normalized_title'] += 1
            elif max(SequenceMatcher(None, a['title'], b['title'], autojunk=False).ratio(),
                     SequenceMatcher(None, b['title'], a['title'], autojunk=False).ratio()) >= NEAR_TITLE_THRESHOLD:
                union(left, right)
                reasons['near_normalized_title'] += 1
    components = defaultdict(list)
    for key in keys:
        components[find(key)].append(key)
    if len(components) < 3:
        raise ValueError('at_least_three_independent_groups_required')
    group_members = {}
    for members in components.values():
        encoded = json.dumps(members, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        group_members['group_' + hashlib.sha256(encoded).hexdigest()] = members
    order = sorted(group_members)
    random.Random(seed).shuffle(order)
    count = len(order)
    train_count = min(max(1, int(count * train_fraction)), count - 2)
    validation_count = min(max(1, int(count * validation_fraction)), count - train_count - 1)
    assignments, groups = {}, {}
    for number, group_id in enumerate(order):
        split = 'train' if number < train_count else 'validation' if number < train_count + validation_count else 'test'
        for key in group_members[group_id]:
            assignments[key], groups[key] = split, group_id
    return {'assignments': dict(sorted(assignments.items())), 'groups': dict(sorted(groups.items())),
            'metadata': {'split_version': SPLIT_VERSION, 'split_kind': 'non_temporal_grouped', 'seed': seed,
                         'requested_fractions': {'train': train_fraction, 'validation': validation_fraction,
                                                 'test': 1 - train_fraction - validation_fraction},
                         'group_count': count, 'student_count': len(keys),
                         'group_counts': {'train': train_count, 'validation': validation_count,
                                          'test': count - train_count - validation_count},
                         'student_counts': dict(sorted(Counter(assignments.values()).items())),
                         'grouping_edge_counts': dict(sorted(reasons.items())),
                         'near_title_threshold': NEAR_TITLE_THRESHOLD,
                         'near_title_algorithm': 'max of bidirectional difflib.SequenceMatcher ratios; autojunk=False',
                         'title_normalization': 'Unicode NFKC + casefold + Unicode word tokens + single spaces',
                         'chronological_validation': False, 'identity_fields_are_features': False,
                         'test_policy': 'untouched_until_final_evaluation',
                         'fit_policy': 'learned vocabulary, IDF and transforms fit on train only',
                         'limitations': ['Non-temporal research split: no confirmed semester chronology or cohort year.',
                                         'Not evidence of generalization to unseen future semesters.',
                                         'Fractions apply to independent groups; student proportions may differ.']}}
