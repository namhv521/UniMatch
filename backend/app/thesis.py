"""Semester registration, advisor decisions and dean allocation."""
import json
import os
import re
from collections import Counter
from contextlib import contextmanager
from uuid import uuid4

from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool

from .email_auth import normalized_email
from .thesis_assessment import ASSESSMENT_VERSION, assess, public_assessment, scoring_row


def role_roster():
    from .portal import hashed
    raw = json.loads(os.environ.get('UNIMATCH_ROLE_ROSTER', '{}'))
    if not isinstance(raw, dict):
        raise ValueError('invalid_role_roster')
    roles = {}
    advisor_ids = set()
    for identity, entry in raw.items():
        if not re.fullmatch(r'(google|github|facebook):[^\s:]+', identity) or not isinstance(entry, dict):
            raise ValueError('invalid_role_roster')
        role, advisor_id = entry.get('role'), entry.get('advisor_id')
        if role == 'dean' and set(entry) == {'role'}:
            roles[hashed(identity)] = entry
        elif (role == 'faculty' and isinstance(advisor_id, str) and advisor_id.strip() == advisor_id
              and advisor_id and advisor_id not in advisor_ids and set(entry) == {'role', 'advisor_id'}):
            advisor_ids.add(advisor_id)
            roles[hashed(identity)] = entry
        else:
            raise ValueError('invalid_role_roster')
    return roles


def role_for(user_id, roster):
    return roster.get(user_id, {'role': 'student'})


def advisor_catalog(active):
    return [{'advisor_id': advisor['advisor_id'], 'advisor_name': advisor['advisor_name']}
            for advisor in active.advisors]


def compatibility(active, profiles):
    rows = [scoring_row(profile['user_id'], profile['profile']) for profile in profiles]
    scored = active.pipeline.transform_score(rows, active.advisors)
    scores, known = scored['scores']['E4'], scored['available']['E4']
    for index, row in enumerate(rows):
        if not row['topic_tags']:
            scores[index] = 0
            known[index] = False
    return scores, known


def allocation(active, students, requests, selected):
    import numpy as np

    from src.baselines.rebuild_baselines import solve
    from src.domain.rebuild_matching import AllocationProblem, equal_quotas

    ids = active.advisor_ids
    fixed = {r['user_id']: r['advisor_id'] for r in requests if r['status'] == 'accepted'}
    if not set(fixed.values()) <= set(selected):
        raise HTTPException(409, 'include_accepted_advisors')
    accepted = Counter(fixed.values())
    remaining = equal_quotas(len(students) - len(fixed), ids, selected)
    capacities = remaining + np.array([accepted[a] for a in ids])
    scores, known = compatibility(active, students)
    student_ids = tuple(s['user_id'] for s in students)
    student_index = {sid: i for i, sid in enumerate(student_ids)}
    advisor_index = {aid: j for j, aid in enumerate(ids)}
    eligible = np.ones_like(known)
    preferences = np.zeros_like(scores)
    for r in requests:
        if r['advisor_id'] not in advisor_index:
            continue
        i, j = student_index[r['user_id']], advisor_index[r['advisor_id']]
        if r['status'] == 'rejected':
            eligible[i, j] = False
        elif r['status'] == 'pending':
            preferences[i, j] = (4 - r['rank']) / 3
    problem = AllocationProblem(scores=np.clip(scores, 0, 1), available=np.ones_like(known),
        student_ids=student_ids, advisor_ids=ids, capacities=capacities, eligible=eligible,
        present=np.array([a in selected for a in ids]), fixed_assignments=fixed,
        preferences=preferences, preference_known=preferences.astype(bool))
    result = solve(problem)
    for row in result['assignments']:
        i, j = student_index[row.pop('student_id')], advisor_index[row['advisor_id']]
        row.update(user_id=student_ids[i], student_name=students[i]['name'],
                   advisor_name=active.advisors[j]['advisor_name'],
                   score=row['score'] if known[i, j] else None, accepted=student_ids[i] in fixed)
    return {'id': uuid4().hex, 'status': result['status'], 'assignments': result['assignments'],
            'quotas': [{**a, 'accepted': accepted[a['advisor_id']], 'remaining': int(remaining[j]),
                        'total': int(capacities[j])}
                       for j, a in enumerate(advisor_catalog(active)) if a['advisor_id'] in selected],
            'encoder': active.versions.get('encoder_sha256')}


def install_thesis(router, app, store, authenticated, check_origin):
    semester = os.environ.get('UNIMATCH_THESIS_SEMESTER', '').strip()
    if semester and not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,39}', semester):
        raise ValueError('invalid_thesis_semester')

    def require(request, role):
        user = authenticated(request)
        if user['role'] != role:
            raise HTTPException(403, 'role_required')
        return user

    @contextmanager
    def term(*, write=False):
        if not semester:
            raise HTTPException(503, 'semester_not_configured')
        with store.connect() as db:
            if write:
                db.execute('INSERT INTO thesis_semesters(semester) VALUES (?) ON CONFLICT(semester) DO NOTHING',
                           (semester,))
                state = db.execute('UPDATE thesis_semesters SET revision=revision+1 '
                                   'WHERE semester=? AND published IS NULL RETURNING *', (semester,)).fetchone()
                if state is None:
                    raise HTTPException(409, 'semester_published')
            else:
                state = db.execute('SELECT * FROM thesis_semesters WHERE semester=?', (semester,)).fetchone()
            yield db, dict(state) if state else {'threshold': 70, 'proposal': None, 'published': None}

    def load_students(db):
        return [{**dict(row), 'profile': json.loads(row['profile'])} for row in db.execute(
            'SELECT s.user_id,u.name,s.profile FROM thesis_students s JOIN users u ON u.id=s.user_id '
            'WHERE s.semester=? ORDER BY s.user_id', (semester,)).fetchall()]

    def load_requests(db, *, user_id=None, advisor_id=None):
        query = ('SELECT r.user_id,r.advisor_id,r.status,p.advisor_ids,p.topic_description FROM thesis_requests r '
                 'LEFT JOIN thesis_preferences p ON p.semester=r.semester AND p.user_id=r.user_id WHERE r.semester=?')
        values = [semester]
        if user_id is not None:
            query += ' AND r.user_id=?'
            values.append(user_id)
        if advisor_id is not None:
            query += ' AND r.advisor_id=?'
            values.append(advisor_id)
        requests = []
        for record in db.execute(query + ' ORDER BY r.advisor_id,r.user_id', values).fetchall():
            row = dict(record)
            ids = json.loads(row.pop('advisor_ids') or 'null')
            if ids is None:
                row['rank'] = None if row['status'] == 'withdrawn' else 1
            else:
                row['rank'] = ids.index(row['advisor_id']) + 1 if row['advisor_id'] in ids else None
            requests.append(row)
        return requests

    def load_preference(db, user_id):
        return db.execute('SELECT advisor_ids,topic_description FROM thesis_preferences WHERE semester=? AND user_id=?',
                          (semester, user_id)).fetchone()

    def load_contact(db, user_id):
        return db.execute('SELECT email,phone FROM thesis_contacts WHERE semester=? AND user_id=?',
                          (semester, user_id)).fetchone()

    def save_contact(db, user_id, raw):
        if not isinstance(raw, dict):
            raise HTTPException(422, 'invalid_contact')
        email = normalized_email(raw.get('email'))
        phone = raw.get('phone')
        if not isinstance(phone, str) or not re.fullmatch(r'\+?[0-9][0-9 .()-]{7,23}', phone.strip()):
            raise HTTPException(422, 'invalid_contact')
        phone = re.sub(r'[ .()-]', '', phone.strip())
        if not 8 <= len(phone.lstrip('+')) <= 15:
            raise HTTPException(422, 'invalid_contact')
        db.execute('INSERT INTO thesis_contacts(semester,user_id,email,phone) VALUES (?,?,?,?) '
                   'ON CONFLICT(semester,user_id) DO UPDATE SET email=excluded.email,phone=excluded.phone',
                   (semester, user_id, email, phone))

    def registered_students(db, advisor_id, requests):
        rows = db.execute('SELECT r.user_id,u.name,c.email,c.phone FROM thesis_requests r JOIN users u ON u.id=r.user_id '
                          'LEFT JOIN thesis_contacts c ON c.semester=r.semester AND c.user_id=r.user_id '
                          'WHERE r.semester=? AND r.advisor_id=?',
                          (semester, advisor_id)).fetchall() if requests else []
        eligible = {r['user_id'] for r in requests if r['rank'] is not None}
        return sorted(({'name': r['name'], 'email': r['email'], 'phone': r['phone']} for r in rows
                       if r['user_id'] in eligible), key=lambda row: row['name'].casefold())

    def active_service():
        return app.state.rebuild_get_service()

    @router.get('/api/thesis')
    def workspace(request: Request):
        user = authenticated(request)
        with term() as (db, state):
            published = json.loads(state['published']) if state['published'] else None
            result = {'semester': semester, 'published': bool(published), 'threshold': state['threshold']}
            if user['role'] == 'student':
                row = db.execute('SELECT profile FROM thesis_students WHERE semester=? AND user_id=?',
                                 (semester, user['id'])).fetchone()
                preference = load_preference(db, user['id'])
                contact = load_contact(db, user['id'])
                email_account = db.execute('SELECT email FROM email_accounts WHERE user_id=?', (user['id'],)).fetchone()
                return {**result, 'assessment_version': ASSESSMENT_VERSION, 'assessment': public_assessment(),
                        'profile': json.loads(row['profile']) if row else None,
                        'requests': load_requests(db, user_id=user['id']),
                        'topic_description': preference['topic_description'] if preference else '',
                        'contact': dict(contact) if contact else {'email': email_account['email'] if email_account else '', 'phone': ''},
                        'assignment': next((r for r in published['assignments'] if r['user_id'] == user['id']), None)
                        if published else None}
            if user['role'] == 'faculty':
                if not user['advisor_id']:
                    raise HTTPException(409, 'advisor_account_unassigned')
                requests = load_requests(db, advisor_id=user['advisor_id'])
                applicants = {row['user_id']: row for row in db.execute(
                    'SELECT s.user_id,u.name,s.profile FROM thesis_students s JOIN users u ON u.id=s.user_id '
                    'JOIN thesis_requests r ON r.semester=s.semester AND r.user_id=s.user_id '
                    "WHERE s.semester=? AND r.advisor_id=? AND r.status IN ('pending','accepted','rejected')",
                    (semester, user['advisor_id'])
                ).fetchall()}
                count = db.execute('SELECT count(*) AS total FROM thesis_students WHERE semester=?', (semester,)).fetchone()
                advisor = next((a for a in advisor_catalog(active_service()) if a['advisor_id'] == user['advisor_id']), None)
                return {**result, 'student_count': count['total'],
                        'advisor_name': advisor['advisor_name'] if advisor else '',
                        'registered_students': registered_students(db, user['advisor_id'], requests) if published else [],
                        'requests': [{**r, 'topic_description': r['topic_description'] if r['status'] != 'rejected' else None,
                                      'name': applicants[r['user_id']]['name'],
                                      'skills': json.loads(applicants[r['user_id']]['profile'])['skills']}
                                     for r in requests if r['user_id'] in applicants],
                        'assignments': [r for r in published['assignments'] if r['advisor_id'] == user['advisor_id']]
                        if published else []}
            count = db.execute('SELECT count(*) AS total FROM thesis_students WHERE semester=?', (semester,)).fetchone()
            return {**result, 'student_count': count['total'],
                    'proposal': published or (json.loads(state['proposal']) if state['proposal'] else None),
                    'accepted_advisors': sorted({r['advisor_id'] for r in load_requests(db) if r['status'] == 'accepted'})}

    @router.get('/api/thesis/catalog')
    def catalog(request: Request):
        authenticated(request)
        return advisor_catalog(active_service())

    @router.get('/api/thesis/recommendations')
    def recommendations(request: Request):
        user = require(request, 'student')
        with term() as (db, _):
            row = db.execute('SELECT profile FROM thesis_students WHERE semester=? AND user_id=?',
                             (semester, user['id'])).fetchone()
        if not row:
            raise HTTPException(409, 'assessment_required')
        active = active_service()
        profile = json.loads(row['profile'])
        scores, known = compatibility(active, [{'user_id': user['id'], 'profile': profile}])
        advisors = advisor_catalog(active)
        indices = sorted((j for j in range(len(advisors)) if known[0, j] and scores[0, j] > 0),
                         key=lambda j: (-scores[0, j], advisors[j]['advisor_id']))
        return [{**advisors[j], 'score': float(scores[0, j])} for j in indices[:5]]

    def mutate(action, request, payload):
        role = {'assessment': 'student', 'choice': 'student', 'topic': 'student', 'contact': 'student', 'decision': 'faculty',
                'threshold': 'dean', 'proposal': 'dean', 'publish': 'dean'}[action]
        user = require(request, role)
        if action == 'contact':
            with term() as (db, _):
                if not any(r['rank'] is not None for r in load_requests(db, user_id=user['id'])):
                    raise HTTPException(409, 'pending_request_required')
                save_contact(db, user['id'], payload)
            return {'ok': True}
        if action == 'choice' and not ('advisor_ids' in payload or 'advisor_id' in payload):
            raise HTTPException(422, 'invalid_advisor_selection')
        advisor_ids = payload.get('advisor_ids', [] if payload.get('advisor_id') is None else [payload['advisor_id']])
        active = active_service() if action == 'proposal' or action == 'choice' and advisor_ids else None
        with term(write=True) as (db, state):
            if action == 'assessment':
                profile = assess(payload)
                db.execute('INSERT INTO thesis_students(semester,user_id,profile) VALUES (?,?,?) '
                           'ON CONFLICT(semester,user_id) DO UPDATE SET profile=excluded.profile',
                           (semester, user['id'], json.dumps(profile, ensure_ascii=False)))
            elif action == 'choice':
                choice(db, user['id'], advisor_ids, active, payload)
            elif action == 'topic':
                if not any(r['status'] in ('pending', 'accepted') for r in load_requests(db, user_id=user['id'])):
                    raise HTTPException(409, 'pending_request_required')
                save_topic(db, user['id'], payload)
            elif action == 'decision':
                if not user['advisor_id']:
                    raise HTTPException(409, 'advisor_account_unassigned')
                decision = payload.get('decision')
                student = payload.get('user_id')
                if decision not in ('accepted', 'rejected') or not isinstance(student, str) or not re.fullmatch('[0-9a-f]{64}', student):
                    raise HTTPException(422, 'invalid_decision')
                row = db.execute('UPDATE thesis_requests SET status=? WHERE semester=? AND user_id=? '
                                 'AND advisor_id=? AND status=? RETURNING status',
                                 (decision, semester, student, user['advisor_id'], 'pending')).fetchone()
                if row is None:
                    raise HTTPException(409, 'pending_request_required')
                if decision == 'accepted':
                    db.execute("UPDATE thesis_requests SET status='withdrawn' WHERE semester=? AND user_id=? AND status='pending'",
                               (semester, student))
            elif action == 'threshold':
                threshold = payload.get('threshold')
                if type(threshold) is not int or not 0 <= threshold <= 100:
                    raise HTTPException(422, 'invalid_threshold')
                db.execute('UPDATE thesis_semesters SET threshold=? WHERE semester=?', (threshold, semester))
                return {'threshold': threshold}
            elif action == 'proposal':
                selected = payload.get('advisor_ids')
                if (not isinstance(selected, list) or not selected or len(selected) > len(active.advisor_ids)
                        or any(not isinstance(a, str) or a not in active.advisor_ids for a in selected)
                        or len(set(selected)) != len(selected)):
                    raise HTTPException(422, 'invalid_advisor_selection')
                students = load_students(db)
                if not students or len(students) > 1000:
                    raise HTTPException(409, 'invalid_registration_count')
                proposal = allocation(active, students, load_requests(db), selected)
                db.execute('UPDATE thesis_semesters SET proposal=? WHERE semester=?',
                           (json.dumps(proposal, ensure_ascii=False), semester))
                return proposal
            elif action == 'publish':
                proposal = json.loads(state['proposal']) if state['proposal'] else None
                if not proposal or proposal['id'] != payload.get('id') or proposal['status'] != 'feasible':
                    raise HTTPException(409, 'stale_or_infeasible_proposal')
                db.execute('UPDATE thesis_semesters SET published=proposal WHERE semester=?', (semester,))
                return {'ok': True}
            db.execute('UPDATE thesis_semesters SET proposal=NULL WHERE semester=?', (semester,))
        return {'ok': True}

    def topic_text(payload, previous=''):
        text = payload.get('topic_description', previous)
        if not isinstance(text, str) or len(text) > 2000 or '\x00' in text:
            raise HTTPException(422, 'invalid_topic_description')
        return text.strip()

    def save_topic(db, student, payload):
        preference = load_preference(db, student)
        ids = json.loads(preference['advisor_ids']) if preference else [
            r['advisor_id'] for r in load_requests(db, user_id=student) if r['status'] in ('pending', 'accepted')]
        upsert_preference(db, student, ids, topic_text(payload))

    def upsert_preference(db, student, ids, topic):
        db.execute('INSERT INTO thesis_preferences(semester,user_id,advisor_ids,topic_description) VALUES (?,?,?,?) '
                   'ON CONFLICT(semester,user_id) DO UPDATE SET advisor_ids=excluded.advisor_ids, '
                   'topic_description=excluded.topic_description', (semester, student, json.dumps(ids), topic))

    def choice(db, student, advisor_ids, active, payload):
        args = (semester, student)
        if (not isinstance(advisor_ids, list) or len(advisor_ids) > 3
                or any(not isinstance(a, str) or a not in active.advisor_ids for a in advisor_ids)
                or len(set(advisor_ids)) != len(advisor_ids)):
            raise HTTPException(422, 'invalid_advisor_selection')
        if not db.execute('SELECT 1 FROM thesis_students WHERE semester=? AND user_id=?', args).fetchone():
            raise HTTPException(409, 'assessment_required')
        requests = load_requests(db, user_id=student)
        if any(r['status'] == 'accepted' for r in requests):
            raise HTTPException(409, 'accepted_request_locked')
        if any(r['advisor_id'] in advisor_ids and r['status'] == 'rejected' for r in requests):
            raise HTTPException(409, 'request_already_rejected')
        db.execute("UPDATE thesis_requests SET status='withdrawn' WHERE semester=? AND user_id=? AND status='pending'", args)
        for advisor_id in advisor_ids:
            db.execute("INSERT INTO thesis_requests VALUES (?,?,?,'pending') "
                       "ON CONFLICT(semester,user_id,advisor_id) DO UPDATE SET status='pending'", (*args, advisor_id))
        previous = load_preference(db, student)
        upsert_preference(db, student, advisor_ids, topic_text(payload, previous['topic_description'] if previous else ''))
        if advisor_ids and 'contact' in payload:
            save_contact(db, student, payload['contact'])

    @router.post('/api/thesis/{action}')
    async def change(action: str, request: Request):
        if action not in {'assessment', 'choice', 'topic', 'contact', 'decision', 'threshold', 'proposal', 'publish'}:
            raise HTTPException(404, 'unknown_thesis_action')
        check_origin(request)
        payload = await app.state.rebuild_read_body(request)
        try:
            return await run_in_threadpool(mutate, action, request, payload)
        except ValueError as error:
            if str(error) == 'assessment_incomplete':
                raise HTTPException(422, 'assessment_incomplete') from None
            raise
