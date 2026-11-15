"""CSV roster intake and inference on the portal's frozen matching models."""
import csv
import io
import json
import re
from collections import Counter
from uuid import uuid4

from fastapi import HTTPException

from .email_auth import normalized_email
from .portal import hashed
from .thesis_assessment import scoring_row

CSV_COLUMNS = {'student_id': 80, 'name': 160, 'email': 254, 'phone': 24, 'topic': 1000, 'skills': 1000}
REQUIRED = {'student_id', 'name', 'email'}


def read_roster(text):
    if not isinstance(text, str) or '\x00' in text:
        raise HTTPException(422, 'invalid_roster_csv')
    roster, ids = {}, set()
    try:
        reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff'), newline=''), strict=True)
        headers = reader.fieldnames or []
        if len(set(headers)) != len(headers) or not REQUIRED <= set(headers) <= CSV_COLUMNS.keys():
            raise HTTPException(422, 'invalid_roster_headers')
        for row in reader:
            if not any(row.values()):
                continue
            if None in row or any(value is None for value in row.values()):
                raise HTTPException(422, {'code': 'invalid_roster_row', 'row': reader.line_num})
            data = {key: row.get(key, '').strip() for key in CSV_COLUMNS}
            try:
                data['email'] = normalized_email(data['email'])
            except HTTPException:
                raise HTTPException(422, {'code': 'invalid_roster_row', 'row': reader.line_num}) from None
            user_id = hashed('email:' + data['email'])
            if (any(not data[key] for key in REQUIRED)
                    or any(len(data[key]) > limit for key, limit in CSV_COLUMNS.items())
                    or (data['phone'] and not re.fullmatch(r'\+?[0-9][0-9 .()-]{7,23}', data['phone']))):
                raise HTTPException(422, {'code': 'invalid_roster_row', 'row': reader.line_num})
            key = data['student_id'].casefold()
            if user_id in roster or key in ids:
                raise HTTPException(422, {'code': 'duplicate_roster_identity', 'row': reader.line_num})
            if len(roster) >= 500:
                raise HTTPException(422, 'roster_limit')
            roster[user_id] = data
            ids.add(key)
    except (csv.Error, UnicodeError):
        raise HTTPException(422, 'invalid_roster_csv') from None
    if not roster:
        raise HTTPException(422, 'invalid_registration_count')
    return roster


def semester_students(roster, assessments, topics):
    profiles = {s['user_id']: s['profile'] for s in assessments}
    students = [{**entry, 'user_id': uid, 'submitted': uid in profiles,
                 'profile': profiles.get(uid, {'skills': []}), 'description': topics.get(uid, '')}
                for uid, entry in roster.items()]
    return sorted(students, key=lambda s: (not s['submitted'], s['student_id']))


def compare_models(active, students, requests, selected):
    import numpy as np

    from src.data_pipeline.normalization import normalize_mentions
    from src.domain.rebuild_matching import AllocationProblem, equal_quotas
    from src.environment.rebuild_env import MatchingEnv
    from src.evaluation.rebuild_benchmark import evaluate_problem
    from src.serving.rebuild_service import POLICY_VERSION

    checkpoint = 'V3' if active.checkpoint_versions else None
    models, contracts, advisors = (active.checkpoint_versions[checkpoint] if checkpoint else
                                    (active.models, active.model_contracts, active.advisors))
    algorithms = ('ppo', 'dqn')
    if not all(models.get(name) is not None for name in algorithms):
        raise HTTPException(503, 'matching_models_unavailable')

    ids = active.advisor_ids
    fixed = {r['user_id']: r['advisor_id'] for r in requests if r['status'] == 'accepted'}
    if not set(fixed.values()) <= set(selected):
        raise HTTPException(409, 'include_accepted_advisors')
    students = sorted(students, key=lambda student: student['user_id'] not in fixed)
    student_ids = tuple(s['user_id'] for s in students)
    indexes = {sid: i for i, sid in enumerate(student_ids)}
    advisor_indexes = {aid: j for j, aid in enumerate(ids)}
    accepted = Counter(fixed.values())
    remaining = equal_quotas(len(students) - len(fixed), ids, selected)
    capacities = remaining + np.array([accepted[a] for a in ids])
    rows = []
    feature_indexes = {tag: i for i, tag in enumerate(active.tag_order)}
    features = np.zeros((len(students), len(active.tag_order)), dtype=np.float32)
    for index, student in enumerate(students):
        row = scoring_row(student['user_id'], student['profile'])
        row.update(student_name=student['name'], thesis_title=student['topic'], thesis_abstract=student['description'],
                   skills_tags=student['skills'])
        text = ' '.join(row[key] for key in ('thesis_title', 'thesis_abstract', 'thesis_keywords', 'skills_tags'))
        groups = {}
        for match in normalize_mentions(text, active.taxonomy):
            groups.setdefault(match['group'], set()).add(match['tag'])
        groups.setdefault('topic_tags', set()).update(filter(None, row['topic_tags'].split(';')))
        for group, tags in groups.items():
            row[group] = ';'.join(sorted(tags))
            for tag in tags:
                if (group, tag) in feature_indexes:
                    features[index, feature_indexes[group, tag]] = 1
        rows.append(row)
    scored = active.pipeline.transform_score(rows, advisors)
    known = scored['available']['E4']
    preferences = np.zeros(known.shape)
    eligible = np.ones_like(known)
    for r in requests:
        if r['advisor_id'] not in advisor_indexes:
            continue
        i, j = indexes[r['user_id']], advisor_indexes[r['advisor_id']]
        if r['status'] == 'rejected':
            eligible[i, j] = False
        elif r['status'] == 'pending':
            preferences[i, j] = (4 - r['rank']) / 3
    problem = AllocationProblem(scores=np.clip(scored['scores']['E4'], 0, 1), available=known,
        student_ids=student_ids, advisor_ids=ids, capacities=capacities, eligible=eligible,
        present=np.array([a in selected for a in ids]), fixed_assignments=fixed,
        student_features=features, student_feature_known=features.astype(bool), preferences=preferences,
        preference_known=preferences.astype(bool), allow_unscored=True)
    env = MatchingEnv([problem])
    policy = active.versions.get('quota_policy_version', POLICY_VERSION)
    results = {}
    for name in algorithms:
        contract = contracts.get(name, {})
        if (contract.get('state_contract') != env.state_contract or contract.get('reward_weights') != env.reward_weights
                or contract.get('quota_policy_version') != policy):
            raise HTTPException(503, 'matching_model_contract_mismatch')
        result = evaluate_problem(problem, name, model=models[name])
        assignments = []
        for assignment in result['assignments']:
            uid, aid = assignment['student_id'], assignment['advisor_id']
            i, j = indexes[uid], advisor_indexes[aid]
            student = students[i]
            assignments.append({'user_id': uid, 'student_id': student['student_id'], 'student_name': student['name'],
                'advisor_id': aid, 'advisor_name': advisors[j]['advisor_name'], 'submitted': student['submitted'],
                'score': float(problem.scores[i, j]) if known[i, j] else None, 'accepted': uid in fixed})
        evidence = [row['score'] for row in assignments if row['score'] is not None]
        results[name] = {'status': result['status'], 'assignments': assignments,
                         'metrics': {**result['metrics'], 'mean_compatibility': float(np.mean(evidence)) if evidence else None,
                                     'scored_students': len(evidence)},
                         'elapsed_seconds': result['elapsed_seconds']}
    quotas = []
    for j, advisor in enumerate(advisors):
        aid = advisor['advisor_id']
        if aid not in selected:
            continue
        terms = normalize_mentions(advisor.get('research_description', ''), active.taxonomy)
        skills = list(dict.fromkeys(item['matched_text'].casefold() for item in terms))[:12]
        quotas.append({'advisor_id': aid, 'advisor_name': advisor['advisor_name'], 'skills': skills,
                       'accepted': accepted[aid], 'remaining': int(remaining[j]), 'total': int(capacities[j])})
    return {'id': uuid4().hex, 'status': 'feasible' if all(r['status'] == 'feasible' for r in results.values()) else 'infeasible',
            'checkpoint': checkpoint, 'encoder': active.versions.get('encoder_sha256'), 'quotas': quotas,
            'results': results}


def load_intake(db, semester):
    row = db.execute('SELECT roster,closed FROM thesis_intake WHERE semester=?', (semester,)).fetchone()
    return (json.loads(row['roster']), bool(row['closed'])) if row else (None, False)
