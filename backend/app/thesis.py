"""Semester registration, profile normalization, RAG agent, advisor decisions, dean allocation & post-assignment lifecycle."""
import csv
import hashlib
import hmac
import io
import json
import os
import re
import threading
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from . import thesis_history
from .advisor_skills import enrich_advisors, export_advisor_skills_csv, save_advisor_skills_csv
from .email_auth import normalized_email
from .thesis_assessment import ASSESSMENT_VERSION, assess, public_assessment, scoring_row
from .thesis_intake import compare_models, load_intake, read_roster, semester_students

MILESTONE_DEFS = (
    ('proposal', 'Đề cương khóa luận'),
    ('midterm', 'Báo cáo tiến độ giữa kỳ'),
    ('final', 'Bản nộp hoàn chỉnh & Slide bảo vệ'),
)


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


def advisor_catalog(active, *, db=None, request_counts=None):
    enriched = enrich_advisors(active, db=db)
    counts = request_counts or {}
    rows = []
    for advisor in enriched:
        sp = advisor['skill_profile']
        aid = sp['advisor_id']
        stat = counts.get(aid, {'accepted': 0, 'pending': 0})
        rows.append({
            'advisor_id': aid,
            'advisor_name': sp['advisor_name'],
            'department': sp['department'],
            'academic_title': sp['academic_title'],
            'summary': sp['summary'],
            'display_skills': sp['display_skills'],
            'grouped_labels': sp['grouped_labels'],
            'skill_count': sp['skill_count'],
            'fairness_ready': sp['fairness_ready'],
            'target_quota': sp['target_quota'],
            'source_url': sp['source_url'],
            'scholar_url': sp['scholar_url'],
            'github_url': sp['github_url'],
            'accepted_count': stat['accepted'],
            'pending_count': stat['pending'],
        })
    return rows


def compatibility(active, profiles, *, db=None):
    enriched = enrich_advisors(active, db=db)
    rows = [scoring_row(profile['user_id'], profile['profile'], dossier=profile.get('dossier')) for profile in profiles]
    scored = active.pipeline.transform_score(rows, enriched)
    scores, known = scored['scores']['E4'], scored['available']['E4']
    for index, row in enumerate(rows):
        if not row['topic_tags'] and not row.get('thesis_title'):
            scores[index] = 0
            known[index] = False
    return scores, known


def allocation(active, students, requests, selected, *, db=None, custom_quotas=None):
    import numpy as np

    from src.baselines.rebuild_baselines import solve
    from src.domain.rebuild_matching import AllocationProblem, equal_quotas

    ids = active.advisor_ids
    fixed = {r['user_id']: r['advisor_id'] for r in requests if r['status'] == 'accepted'}
    if not set(fixed.values()) <= set(selected):
        raise HTTPException(409, 'include_accepted_advisors')
    accepted = Counter(fixed.values())
    if isinstance(custom_quotas, dict) and custom_quotas:
        capacities = np.array([int(custom_quotas.get(a, 0)) if a in selected else 0 for a in ids], dtype=int)
        if any(capacities[j] < accepted[a] for j, a in enumerate(ids) if a in selected) or int(capacities.sum()) < len(students):
            raise HTTPException(422, 'insufficient_custom_quota')
        remaining = np.maximum(0, capacities - np.array([accepted[a] for a in ids], dtype=int))
    else:
        remaining = equal_quotas(len(students) - len(fixed), ids, selected)
        capacities = remaining + np.array([accepted[a] for a in ids])
    scores, known = compatibility(active, students, db=db)
    enriched = enrich_advisors(active, db=db)
    student_ids = tuple(s['user_id'] for s in students)
    student_index = {sid: i for i, sid in enumerate(student_ids)}
    advisor_index = {aid: j for j, aid in enumerate(ids)}
    eligible = np.ones_like(known)
    preferences = np.zeros_like(scores)
    for r in requests:
        if r['advisor_id'] not in advisor_index or r['user_id'] not in student_index:
            continue
        i, j = student_index[r['user_id']], advisor_index[r['advisor_id']]
        if r['status'] == 'rejected':
            eligible[i, j] = False
        elif r['status'] == 'pending':
            preferences[i, j] = (4 - (r['rank'] or 1)) / 3
    problem = AllocationProblem(scores=np.clip(scores, 0, 1), available=np.ones_like(known),
        student_ids=student_ids, advisor_ids=ids, capacities=capacities, eligible=eligible,
        present=np.array([a in selected for a in ids]), fixed_assignments=fixed,
        preferences=preferences, preference_known=preferences.astype(bool))
    result = solve(problem)
    for row in result['assignments']:
        i, j = student_index[row.pop('student_id')], advisor_index[row['advisor_id']]
        row.update(user_id=student_ids[i], student_name=students[i]['name'],
                   advisor_name=enriched[j]['advisor_name'],
                   score=row['score'] if known[i, j] else None, accepted=student_ids[i] in fixed)
    return {'id': uuid4().hex, 'status': result['status'], 'assignments': result['assignments'],
            'quotas': [{'advisor_id': a['advisor_id'], 'advisor_name': a['advisor_name'],
                        'skills': a['display_skills'], 'accepted': accepted[a['advisor_id']],
                        'remaining': int(remaining[j]), 'total': int(capacities[j])}
                       for j, a in enumerate(advisor_catalog(active, db=db)) if a['advisor_id'] in selected],
            'encoder': active.versions.get('encoder_sha256')}


def install_thesis(router, app, store, authenticated, check_origin):
    semester = os.environ.get('UNIMATCH_THESIS_SEMESTER', '').strip()
    if semester and not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,39}', semester):
        raise ValueError('invalid_thesis_semester')
    agent_lock = threading.Lock()

    def require(request, role):
        user = authenticated(request)
        if user['role'] != role:
            raise HTTPException(403, 'role_required')
        return user

    @contextmanager
    def term(*, write=False, allow_published=False):
        if not semester:
            raise HTTPException(503, 'semester_not_configured')
        with store.connect() as db:
            if write:
                db.execute('INSERT INTO thesis_semesters(semester) VALUES (?) ON CONFLICT(semester) DO NOTHING',
                           (semester,))
                restriction = '' if allow_published else ' AND published IS NULL'
                state = db.execute('UPDATE thesis_semesters SET revision=revision+1 WHERE semester=?'
                                   + restriction + ' RETURNING *', (semester,)).fetchone()
                if state is None:
                    raise HTTPException(409, 'semester_published')
            else:
                state = db.execute('SELECT * FROM thesis_semesters WHERE semester=?', (semester,)).fetchone()
            yield db, dict(state) if state else {'threshold': 70, 'proposal': None, 'published': None, 'revision': 0}

    def load_dossier(db, user_id):
        row = db.execute('SELECT * FROM thesis_dossiers WHERE semester=? AND user_id=?', (semester, user_id)).fetchone()
        if not row:
            return None
        d = dict(row)
        d['normalized_skills'] = json.loads(d['normalized_skills'] or '[]')
        d['taxonomy_tags'] = json.loads(d['taxonomy_tags'] or '{}')
        return d

    def load_all_dossiers(db):
        rows = db.execute('SELECT * FROM thesis_dossiers WHERE semester=?', (semester,)).fetchall()
        out = {}
        for row in rows:
            d = dict(row)
            d['normalized_skills'] = json.loads(d['normalized_skills'] or '[]')
            d['taxonomy_tags'] = json.loads(d['taxonomy_tags'] or '{}')
            out[d['user_id']] = d
        return out

    def save_dossier(db, user_id, dossier):
        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            'INSERT INTO thesis_dossiers '
            '(semester,user_id,raw_title,raw_description,raw_background,formal_title,formal_summary,'
            'methodology_scope,normalized_skills,taxonomy_tags,normalizer_mode,updated_at) '
            'VALUES (?,?,?,?,?,?,?,?,?,?,?,?) '
            'ON CONFLICT(semester,user_id) DO UPDATE SET '
            'raw_title=excluded.raw_title,raw_description=excluded.raw_description,'
            'raw_background=excluded.raw_background,formal_title=excluded.formal_title,'
            'formal_summary=excluded.formal_summary,methodology_scope=excluded.methodology_scope,'
            'normalized_skills=excluded.normalized_skills,taxonomy_tags=excluded.taxonomy_tags,'
            'normalizer_mode=excluded.normalizer_mode,updated_at=excluded.updated_at',
            (
                semester, user_id, dossier.get('raw_title', ''), dossier.get('raw_description', ''),
                dossier.get('raw_background', ''), dossier.get('formal_title', ''),
                dossier.get('formal_summary', ''), dossier.get('methodology_scope', ''),
                json.dumps(dossier.get('normalized_skills', []), ensure_ascii=False),
                json.dumps(dossier.get('taxonomy_tags', {}), ensure_ascii=False),
                dossier.get('normalizer_mode', 'deterministic_academic'), now,
            ),
        )

    def load_milestones(db, user_id):
        saved = {
            row['milestone_key']: dict(row)
            for row in db.execute(
                'SELECT * FROM thesis_milestones WHERE semester=? AND user_id=?',
                (semester, user_id),
            ).fetchall()
        }
        items = []
        for key, label in MILESTONE_DEFS:
            row = saved.get(key)
            items.append({
                'key': key,
                'label': label,
                'official_title': row['official_title'] if row else '',
                'submission_url': row['submission_url'] if row else '',
                'submission_note': row['submission_note'] if row else '',
                'status': row['status'] if row else 'pending',
                'advisor_feedback': row['advisor_feedback'] if row else '',
                'updated_at': row['updated_at'] if row else '',
            })
        return items

    def load_outcome(db, user_id):
        row = db.execute('SELECT * FROM thesis_outcomes WHERE semester=? AND user_id=?', (semester, user_id)).fetchone()
        return dict(row) if row else None

    def is_student_verified_in_roster(db, user_id, roster):
        if roster is None:
            return True, False
        if user_id not in roster:
            return False, False
        entry = roster[user_id]
        req_code = str(entry.get('enrollment_code') or '').strip()
        if not req_code:
            return True, False
        verified = db.execute(
            'SELECT 1 FROM thesis_enrollments WHERE semester=? AND user_id=?',
            (semester, user_id),
        ).fetchone()
        return bool(verified), not bool(verified)

    def load_students(db):
        dossiers = load_all_dossiers(db)
        return [{**dict(row), 'profile': json.loads(row['profile']), 'dossier': dossiers.get(row['user_id'])}
                for row in db.execute(
                    'SELECT s.user_id,u.name,s.profile FROM thesis_students s JOIN users u ON u.id=s.user_id '
                    'WHERE s.semester=? ORDER BY s.user_id', (semester,)
                ).fetchall()]

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

    def request_stats_by_advisor(db):
        stats = {}
        for row in db.execute(
            "SELECT advisor_id, status, count(*) AS cnt FROM thesis_requests "
            "WHERE semester=? AND status IN ('accepted','pending') GROUP BY advisor_id, status",
            (semester,),
        ).fetchall():
            aid = row['advisor_id']
            stats.setdefault(aid, {'accepted': 0, 'pending': 0})
            stats[aid][row['status']] = int(row['cnt'])
        return stats

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

    def assigned_students(db, assignments, advisor_id, roster):
        rows = []
        for row in assignments:
            if row['advisor_id'] != advisor_id:
                continue
            uid = row['user_id']
            entry = (roster or {}).get(uid, {})
            contact = load_contact(db, uid)
            dossier = load_dossier(db, uid)
            student_exists = db.execute(
                'SELECT 1 FROM thesis_students WHERE semester=? AND user_id=?',
                (semester, uid),
            ).fetchone()
            rows.append({
                **row,
                'email': contact['email'] if contact else entry.get('email'),
                'phone': contact['phone'] if contact else entry.get('phone'),
                'dossier': dossier,
                'milestones': load_milestones(db, uid) if student_exists else [],
                'outcome': load_outcome(db, uid) if student_exists else None,
            })
        return rows

    def active_service():
        return app.state.rebuild_get_service()

    def _call_compatibility(active, profiles, db=None):
        import inspect
        if 'db' in inspect.signature(compatibility).parameters:
            return compatibility(active, profiles, db=db)
        return compatibility(active, profiles)

    def compute_student_recommendations(active, user_id, profile, dossier=None, db=None):
        scores, known = _call_compatibility(active, [{'user_id': user_id, 'profile': profile, 'dossier': dossier}], db=db)
        enriched = enrich_advisors(active, db=db)
        advisors = advisor_catalog(active, db=db, request_counts=request_stats_by_advisor(db) if db else None)
        indices = sorted((j for j in range(len(advisors)) if known[0, j] and scores[0, j] > 0),
                         key=lambda j: (-scores[0, j], advisors[j]['advisor_id']))
        basis = scoring_row(user_id, profile, dossier=dossier)
        out = []
        for j in indices[:5]:
            adv_desc = enriched[j].get('research_description', '').casefold()
            matched_kw = [
                term for term in filter(None, basis['thesis_keywords'].split(';'))
                if len(term) >= 2 and re.search(r'(?<!\w)' + re.escape(term.casefold()) + r'(?!\w)', adv_desc)
            ][:8]
            out.append({
                **advisors[j],
                'score': float(scores[0, j]),
                'basis': {
                    'topic_tags': [t for t in basis['topic_tags'].split(';') if t],
                    'keywords': [t for t in basis['thesis_keywords'].split(';') if t],
                    'matched_keywords': matched_kw,
                },
                'explanation': active.pipeline.explain_pair(basis, enriched[j]),
                'scope': 'topic_compatibility_not_proficiency_or_acceptance',
            })
        return out

    def get_rag_agent():
        active = active_service()
        cached = getattr(app.state, 'thesis_rag_agent', None)
        if cached is not None and cached.service is active:
            return cached
        with agent_lock:
            cached = getattr(app.state, 'thesis_rag_agent', None)
            if cached is None or cached.service is not active:
                from src.serving.rag_agent import GuardrailedAcademicAgent
                base_asst = getattr(app.state, 'rebuild_assistant', None)
                cached = GuardrailedAcademicAgent(active, base_assistant=base_asst)
                app.state.thesis_rag_agent = cached
            return cached

    @router.get('/api/thesis')
    def workspace(request: Request):
        user = authenticated(request)
        demo_mode = os.environ.get('UNIMATCH_DEMO_MODE') == '1' and os.environ.get('UNIMATCH_DEPLOYMENT') != 'production'
        with term() as (db, state):
            published = json.loads(state['published']) if state['published'] else None
            roster, closed = load_intake(db, semester)
            result = {
                'semester': semester,
                'published': bool(published),
                'threshold': state['threshold'],
                'preferences_closed': closed,
                'demo_mode': demo_mode,
            }
            if user['role'] == 'student':
                row = db.execute('SELECT profile FROM thesis_students WHERE semester=? AND user_id=?',
                                 (semester, user['id'])).fetchone()
                preference = load_preference(db, user['id'])
                contact = load_contact(db, user['id'])
                dossier = load_dossier(db, user['id'])
                email_account = db.execute('SELECT email FROM email_accounts WHERE user_id=?', (user['id'],)).fetchone()
                assignment = next((r for r in published['assignments'] if r['user_id'] == user['id']), None) if published else None
                in_roster, verification_needed = is_student_verified_in_roster(db, user['id'], roster)
                return {
                    **result,
                    'assessment_version': ASSESSMENT_VERSION,
                    'assessment': public_assessment(),
                    'in_roster': in_roster,
                    'enrollment_verification_required': verification_needed,
                    'roster_student_id': roster[user['id']]['student_id'] if (roster and user['id'] in roster) else '',
                    'profile': json.loads(row['profile']) if row else None,
                    'dossier': dossier,
                    'requests': load_requests(db, user_id=user['id']),
                    'topic_description': preference['topic_description'] if preference else '',
                    'contact': dict(contact) if contact else {'email': email_account['email'] if email_account else '', 'phone': ''},
                    'assignment': {key: assignment[key] for key in ('advisor_id', 'advisor_name')} if assignment else None,
                    'milestones': load_milestones(db, user['id']) if (published and assignment and row) else [],
                    'outcome': load_outcome(db, user['id']) if (published and assignment and row) else None,
                }
            if user['role'] == 'faculty':
                if not user['advisor_id']:
                    raise HTTPException(409, 'advisor_account_unassigned')
                requests = load_requests(db, advisor_id=user['advisor_id'])
                if roster is not None:
                    requests = [r for r in requests if r['user_id'] in roster]
                applicants = {row['user_id']: row for row in db.execute(
                    'SELECT s.user_id,u.name,s.profile FROM thesis_students s JOIN users u ON u.id=s.user_id '
                    'JOIN thesis_requests r ON r.semester=s.semester AND r.user_id=s.user_id '
                    "WHERE s.semester=? AND r.advisor_id=? AND r.status IN ('pending','accepted','rejected')",
                    (semester, user['advisor_id'])
                ).fetchall()}
                count = db.execute('SELECT count(*) AS total FROM thesis_students WHERE semester=?', (semester,)).fetchone()
                active = active_service()
                cat = advisor_catalog(active, db=db)
                advisor = next((a for a in cat if a['advisor_id'] == user['advisor_id']), None)
                dossiers = load_all_dossiers(db)
                # Compute compatibility score for each applicant to this lecturer
                comp_by_uid = {}
                if applicants and user['advisor_id'] in active.advisor_ids:
                    adv_idx = active.advisor_ids.index(user['advisor_id'])
                    prof_rows = [
                        {'user_id': uid, 'profile': json.loads(app_row['profile']), 'dossier': dossiers.get(uid)}
                        for uid, app_row in applicants.items()
                    ]
                    try:
                        sc_mat, kn_mat = _call_compatibility(active, prof_rows, db=db)
                        for idx_u, p_row in enumerate(prof_rows):
                            if kn_mat[idx_u, adv_idx]:
                                comp_by_uid[p_row['user_id']] = float(sc_mat[idx_u, adv_idx])
                    except Exception:
                        comp_by_uid = {}

                proposal = json.loads(state['proposal']) if state['proposal'] else {}
                quota = next((q['total'] for q in (published or proposal.get('manual') or proposal).get('quotas', [])
                              if q['advisor_id'] == user['advisor_id']), None)
                assignments = assigned_students(db, published['assignments'], user['advisor_id'], roster) if published else []
                return {
                    **result,
                    'student_count': len(roster) if roster is not None else count['total'],
                    'advisor_name': advisor['advisor_name'] if advisor else '',
                    'skill_profile': advisor,
                    'teaching_load': {
                        'accepted': sum(r['status'] == 'accepted' for r in requests),
                        'assigned': len(assignments),
                        'quota': quota,
                    },
                    'registered_students': registered_students(db, user['advisor_id'], requests) if published else [],
                    'requests': [
                        {
                            **r,
                            'student_id': (roster or {}).get(r['user_id'], {}).get('student_id', ''),
                            'topic_description': r['topic_description'] if r['status'] != 'rejected' else None,
                            'dossier': dossiers.get(r['user_id']) if r['status'] != 'rejected' else None,
                            'compatibility_score': comp_by_uid.get(r['user_id']),
                            'name': applicants[r['user_id']]['name'],
                            'skills': json.loads(applicants[r['user_id']]['profile'])['skills'],
                        }
                        for r in requests if r['user_id'] in applicants
                    ],
                    'assignments': assignments,
                }
            # Dean workspace
            active = active_service()
            count = db.execute('SELECT count(*) AS total FROM thesis_students WHERE semester=?', (semester,)).fetchone()
            requests = [r for r in load_requests(db) if roster is None or r['user_id'] in roster]
            accepted = Counter(r['advisor_id'] for r in requests if r['status'] == 'accepted')
            submitted_ids = ({row['user_id'] for row in db.execute(
                'SELECT user_id FROM thesis_students WHERE semester=?', (semester,)).fetchall()} & roster.keys()
                if roster is not None else set())
            dossier_ids = {row['user_id'] for row in db.execute(
                'SELECT user_id FROM thesis_dossiers WHERE semester=?', (semester,)).fetchall()}
            preference_ids = {r['user_id'] for r in requests if r['rank'] is not None}
            contact_ids = {row['user_id'] for row in db.execute(
                'SELECT user_id FROM thesis_contacts WHERE semester=?', (semester,)).fetchall()}
            proposal = json.loads(state['proposal']) if state['proposal'] else None
            manual = proposal.pop('manual', None) if proposal else None
            milestone_stats = dict(Counter(
                row['status'] for row in db.execute(
                    'SELECT status FROM thesis_milestones WHERE semester=?', (semester,)
                ).fetchall()
            ))
            outcome_count = db.execute(
                'SELECT count(*) AS c FROM thesis_outcomes WHERE semester=?', (semester,)
            ).fetchone()['c']
            return {
                **result,
                'student_count': len(roster) if roster is not None else count['total'],
                'manual': manual,
                'accepted_assignments': {r['user_id']: r['advisor_id'] for r in requests if r['status'] == 'accepted'},
                'manual_quotas': thesis_history.manual_review(active, roster or {}, requests, proposal or {},
                                                             manual['assignments'] if manual else [])[0],
                'roster_loaded': roster is not None,
                'submitted_count': len(submitted_ids) if roster is not None else count['total'],
                'normalized_count': len(dossier_ids),
                'roster_preview': [
                    {
                        'student_id': row['student_id'],
                        'name': row['name'],
                        'user_id': uid,
                        'submitted': uid in submitted_ids,
                        'normalized': uid in dossier_ids,
                        'incomplete_reasons': ([reason for missing, reason in (
                            (uid not in submitted_ids, 'Chưa nộp khảo sát'),
                            (uid not in preference_ids, 'Chưa gửi nguyện vọng'),
                            (uid not in contact_ids, 'Thiếu thông tin liên hệ')) if missing]),
                    }
                    for uid, row in (roster or {}).items()
                ],
                'pending_count': sum(r['status'] == 'pending' for r in requests),
                'published_algorithm': published.get('algorithm') if published else None,
                'proposal': proposal or (published if published and published.get('algorithm') != 'manual' else None),
                'accepted_counts': dict(accepted),
                'accepted_advisors': sorted(accepted),
                'advisor_skills': advisor_catalog(active, db=db, request_counts=request_stats_by_advisor(db)),
                'lifecycle_summary': {
                    'milestones': milestone_stats,
                    'outcomes_recorded': outcome_count,
                },
            }

    def _collect_export_rows(db, state, user):
        if not state['published']:
            raise HTTPException(409, 'semester_not_published')
        published = json.loads(state['published'])
        roster, _ = load_intake(db, semester)
        dossiers = load_all_dossiers(db)
        rows = []
        for row in published['assignments']:
            if user['role'] == 'faculty' and row['advisor_id'] != user['advisor_id']:
                continue
            uid = row['user_id']
            contact = load_contact(db, uid)
            preference = load_preference(db, uid)
            dossier = dossiers.get(uid) or {}
            entry = (roster or {}).get(uid, {})
            values = {
                'semester': semester,
                'student_id': row.get('student_id', entry.get('student_id', '')),
                'student_name': row.get('student_name', entry.get('name', '')),
                'advisor_id': row['advisor_id'],
                'advisor_name': row['advisor_name'],
                'algorithm': published.get('algorithm', 'hungarian'),
                'revision': published.get('publication_revision', state['revision']),
            }
            if user['role'] == 'faculty':
                values.update(
                    email=contact['email'] if contact else entry.get('email', ''),
                    phone=contact['phone'] if contact else entry.get('phone', ''),
                    topic_description=(
                        dossier.get('formal_title')
                        or (preference['topic_description'] if preference else entry.get('topic', ''))
                    ),
                )
            rows.append((values, dossier))
        return rows

    @router.get('/api/thesis/export')
    def export_official(request: Request):
        user = authenticated(request)
        if user['role'] not in ('dean', 'faculty'):
            raise HTTPException(403, 'role_required')
        if user['role'] == 'faculty' and not user.get('advisor_id'):
            raise HTTPException(409, 'advisor_account_unassigned')
        output = io.StringIO(newline='')
        fields = ['semester', 'student_id', 'student_name', 'advisor_id', 'advisor_name', 'algorithm', 'revision']
        if user['role'] == 'faculty':
            fields += ['email', 'phone', 'topic_description']
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        with term() as (db, state):
            for values, _ in _collect_export_rows(db, state, user):
                writer.writerow({
                    key: "'" + value if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@'))
                    else value for key, value in values.items()
                })
        return Response(output.getvalue().encode('utf-8-sig'), media_type='text/csv; charset=utf-8',
                        headers={'Content-Disposition': f'attachment; filename="unimatch-{semester}-official.csv"',
                                 'Cache-Control': 'private, no-store'})

    @router.get('/api/thesis/export.xlsx')
    def export_official_xlsx(request: Request):
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill

        user = authenticated(request)
        if user['role'] not in ('dean', 'faculty'):
            raise HTTPException(403, 'role_required')
        if user['role'] == 'faculty' and not user.get('advisor_id'):
            raise HTTPException(409, 'advisor_account_unassigned')
        with term() as (db, state):
            collected = _collect_export_rows(db, state, user)
        wb = Workbook()
        ws = wb.active
        ws.title = 'PhanCongKhoaLuan'
        headers = ['Kỳ học', 'Mã sinh viên', 'Họ và tên sinh viên', 'Mã giảng viên', 'Giảng viên hướng dẫn', 'Đề tài chuẩn hóa', 'Phương pháp', 'Phiên bản']
        if user['role'] == 'faculty':
            headers += ['Email liên hệ', 'Số điện thoại']
        ws.append(headers)
        header_fill = PatternFill(start_color='071E41', end_color='071E41', fill_type='solid')
        header_font = Font(color='FFFFFF', bold=True)
        for col_idx, cell in enumerate(ws[1], start=1):
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(vertical='center')
        for values, dossier in collected:
            safe = lambda val: ("'" + val if isinstance(val, str) and val.lstrip().startswith(('=', '+', '-', '@')) else val)
            row_vals = [
                safe(values['semester']),
                safe(values['student_id']),
                safe(values['student_name']),
                safe(values['advisor_id']),
                safe(values['advisor_name']),
                safe(dossier.get('formal_title', '')),
                safe(values['algorithm'].upper()),
                values['revision'],
            ]
            if user['role'] == 'faculty':
                row_vals += [safe(values.get('email', '')), safe(values.get('phone', ''))]
            ws.append(row_vals)
            ws.cell(row=ws.max_row, column=2).number_format = '@'
        for column_cells in ws.columns:
            length = max(len(str(c.value or '')) for c in column_cells)
            ws.column_dimensions[column_cells[0].column_letter].width = min(48, max(14, length + 4))
        buf = io.BytesIO()
        wb.save(buf)
        return Response(
            buf.getvalue(),
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={
                'Content-Disposition': f'attachment; filename="unimatch-{semester}-official.xlsx"',
                'Cache-Control': 'private, no-store',
            },
        )

    @router.get('/api/thesis/advisor-skills.csv')
    def download_advisor_skills_csv(request: Request):
        require(request, 'dean')
        with term() as (db, _):
            csv_body = export_advisor_skills_csv(active_service(), db=db)
        return Response(
            csv_body.encode('utf-8-sig'),
            media_type='text/csv; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename="unimatch-{semester}-advisor-skills.csv"',
                'Cache-Control': 'private, no-store',
            },
        )

    @router.get('/api/thesis/rl-export')
    def export_continual_rl_package(request: Request):
        require(request, 'dean')
        with term() as (db, state):
            if not state['published']:
                raise HTTPException(409, 'semester_not_published')
            published = json.loads(state['published'])
            requests = load_requests(db)
            outcomes = [dict(r) for r in db.execute('SELECT * FROM thesis_outcomes WHERE semester=?', (semester,)).fetchall()]
            dossiers = load_all_dossiers(db)
        anon = lambda uid: hashlib.sha256(f'{semester}:{uid}'.encode()).hexdigest()[:16]
        package = {
            'schema_version': 'continual-rl-semester-feedback/1.0',
            'semester_id': semester,
            'exported_at': datetime.now(timezone.utc).isoformat(),
            'published_algorithm': published.get('algorithm', 'hungarian'),
            'r2_student_preferences': [
                {'student_ref': anon(r['user_id']), 'advisor_id': r['advisor_id'], 'rank': r['rank']}
                for r in requests if r['rank'] is not None
            ],
            'r3_advisor_decisions': [
                {'student_ref': anon(r['user_id']), 'advisor_id': r['advisor_id'], 'decision': r['status']}
                for r in requests if r['status'] in ('accepted', 'rejected')
            ],
            'r4_supervision_outcomes': [
                {
                    'student_ref': anon(o['user_id']),
                    'advisor_id': o['advisor_id'],
                    'rating': o['rating'],
                    'reward_signal': {'excellent': 1.0, 'satisfactory': 0.75, 'needs_improvement': 0.25}[o['rating']],
                    'skills_applied': [s.strip() for s in o['skills_applied'].split(';') if s.strip()],
                    'taxonomy_tags': (dossiers.get(o['user_id']) or {}).get('taxonomy_tags', {}),
                }
                for o in outcomes
            ],
            'published_assignments': [
                {
                    'student_ref': anon(a['user_id']),
                    'advisor_id': a['advisor_id'],
                    'score_e4': a.get('score'),
                    'pre_accepted': bool(a.get('accepted')),
                }
                for a in published.get('assignments', [])
            ],
        }
        return JSONResponse(
            package,
            headers={
                'Content-Disposition': f'attachment; filename="unimatch-{semester}-continual-rl.json"',
                'Cache-Control': 'private, no-store',
            },
        )

    @router.get('/api/thesis/history')
    def history(request: Request, before: int | None = Query(default=None, gt=0)):
        require(request, 'dean')
        with term() as (db, _):
            return thesis_history.read_history(db, semester, before=before)

    @router.get('/api/thesis/history/{revision}')
    def history_detail(request: Request, revision: int):
        require(request, 'dean')
        with term() as (db, _):
            event = thesis_history.read_history(db, semester, revision=revision)
        if event is None:
            raise HTTPException(404, 'history_not_found')
        return event

    @router.get('/api/thesis/catalog')
    def catalog(request: Request):
        authenticated(request)
        with term() as (db, _):
            return advisor_catalog(active_service(), db=db, request_counts=request_stats_by_advisor(db))

    @router.get('/api/thesis/recommendations')
    def recommendations(request: Request):
        user = require(request, 'student')
        with term() as (db, _):
            row = db.execute('SELECT profile FROM thesis_students WHERE semester=? AND user_id=?',
                             (semester, user['id'])).fetchone()
            dossier = load_dossier(db, user['id'])
            if not row:
                raise HTTPException(409, 'assessment_required')
            return compute_student_recommendations(
                active_service(), user['id'], json.loads(row['profile']), dossier=dossier, db=db,
            )

    @router.post('/api/thesis/agent')
    async def ask_agent(request: Request):
        check_origin(request)
        user = authenticated(request)
        payload = await app.state.rebuild_read_body(request)
        question = payload.get('question')
        previous = payload.get('previous_question')
        top_k = payload.get('top_k', 5)
        if (not isinstance(question, str) or not question.strip() or len(question) > 2000
                or (previous is not None and (not isinstance(previous, str) or len(previous) > 2000))
                or type(top_k) is not int or not 1 <= top_k <= 10):
            raise HTTPException(422, 'invalid_agent_question')

        def _execute():
            student_ctx = None
            if user['role'] == 'student' and semester:
                with term() as (db, _):
                    row = db.execute('SELECT profile FROM thesis_students WHERE semester=? AND user_id=?',
                                     (semester, user['id'])).fetchone()
                    if row:
                        prof = json.loads(row['profile'])
                        dossier = load_dossier(db, user['id'])
                        recs = compute_student_recommendations(active_service(), user['id'], prof, dossier=dossier, db=db)
                        student_ctx = {'profile': prof, 'dossier': dossier, 'recommendations': recs}
            agent = get_rag_agent()
            # Refresh enriched skills from DB if Dean updated skills CSV
            with store.connect() as db:
                agent.enriched_advisors = enrich_advisors(active_service(), db=db)
                agent.advisor_by_id = {a['advisor_id']: a for a in agent.enriched_advisors}
            return agent.answer(
                question.strip(),
                top_k=top_k,
                previous_question=previous.strip() if isinstance(previous, str) and previous.strip() else None,
                student_context=student_ctx,
                user_name=user.get('name', ''),
            )

        return await run_in_threadpool(_execute)

    def mutate(action, request, payload):
        role = {
            'assessment': 'student', 'normalize': 'student', 'verify-enrollment': 'student',
            'choice': 'student', 'topic': 'student', 'contact': 'student', 'milestone': 'student',
            'decision': 'faculty', 'milestone-review': 'faculty', 'outcome': 'faculty',
            'threshold': 'dean', 'proposal': 'dean', 'manual': 'dean', 'publish': 'dean',
            'roster': 'dean', 'advisor-skills': 'dean', 'close': 'dean', 'reopen': 'dean', 'revoke': 'dean',
        }[action]
        user = require(request, role)

        # Actions allowed even when semester IS published (post-assignment lifecycle & contact update)
        if action == 'contact':
            with term() as (db, _):
                if not any(r['rank'] is not None for r in load_requests(db, user_id=user['id'])):
                    raise HTTPException(409, 'pending_request_required')
                save_contact(db, user['id'], payload)
            return {'ok': True}

        if action in ('milestone', 'milestone-review', 'outcome'):
            with store.connect() as db:
                sem_row = db.execute('SELECT published FROM thesis_semesters WHERE semester=?', (semester,)).fetchone()
                if not sem_row or not sem_row['published']:
                    raise HTTPException(409, 'semester_not_published')
                published = json.loads(sem_row['published'])
                now = datetime.now(timezone.utc).isoformat()
                if action == 'milestone':
                    assigned = next((a for a in published['assignments'] if a['user_id'] == user['id']), None)
                    if not assigned:
                        raise HTTPException(403, 'assignment_required')
                    mkey = payload.get('milestone_key')
                    if mkey not in {'proposal', 'midterm', 'final'}:
                        raise HTTPException(422, 'invalid_milestone')
                    title = str(payload.get('official_title') or '').strip()[:300]
                    url = str(payload.get('submission_url') or '').strip()[:500]
                    note = str(payload.get('submission_note') or '').strip()[:2000]
                    if url and not re.match(r'^https?://[^\s]+$', url):
                        raise HTTPException(422, 'invalid_submission_url')
                    if not note and not url:
                        raise HTTPException(422, 'milestone_content_required')
                    db.execute('INSERT INTO thesis_students(semester,user_id,profile) VALUES (?,?,?) ON CONFLICT(semester,user_id) DO NOTHING',
                               (semester, user['id'], '{"skills":[]}'))
                    db.execute(
                        'INSERT INTO thesis_milestones '
                        '(semester,user_id,milestone_key,official_title,submission_url,submission_note,status,updated_at) '
                        "VALUES (?,?,?,?,?,?,'submitted',?) "
                        'ON CONFLICT(semester,user_id,milestone_key) DO UPDATE SET '
                        'official_title=excluded.official_title,submission_url=excluded.submission_url,'
                        "submission_note=excluded.submission_note,status='submitted',updated_at=excluded.updated_at",
                        (semester, user['id'], mkey, title, url, note, now),
                    )
                    return {'ok': True, 'milestones': load_milestones(db, user['id'])}

                if action == 'milestone-review':
                    if not user.get('advisor_id'):
                        raise HTTPException(409, 'advisor_account_unassigned')
                    target_uid = payload.get('user_id')
                    mkey = payload.get('milestone_key')
                    mstatus = payload.get('status')
                    feedback = str(payload.get('advisor_feedback') or '').strip()[:2000]
                    if mkey not in {'proposal', 'midterm', 'final'} or mstatus not in {'approved', 'revision_requested'}:
                        raise HTTPException(422, 'invalid_milestone_review')
                    if not any(a['user_id'] == target_uid and a['advisor_id'] == user['advisor_id'] for a in published['assignments']):
                        raise HTTPException(403, 'role_required')
                    updated = db.execute(
                        'UPDATE thesis_milestones SET status=?,advisor_feedback=?,updated_at=? '
                        'WHERE semester=? AND user_id=? AND milestone_key=? RETURNING milestone_key',
                        (mstatus, feedback, now, semester, target_uid, mkey),
                    ).fetchone()
                    if not updated:
                        raise HTTPException(409, 'milestone_not_submitted')
                    return {'ok': True}

                if action == 'outcome':
                    if not user.get('advisor_id'):
                        raise HTTPException(409, 'advisor_account_unassigned')
                    target_uid = payload.get('user_id')
                    rating = payload.get('rating')
                    skills_applied = str(payload.get('skills_applied') or '').strip()[:500]
                    summary_note = str(payload.get('summary_note') or '').strip()[:2000]
                    if rating not in {'excellent', 'satisfactory', 'needs_improvement'}:
                        raise HTTPException(422, 'invalid_outcome')
                    if not any(a['user_id'] == target_uid and a['advisor_id'] == user['advisor_id'] for a in published['assignments']):
                        raise HTTPException(403, 'role_required')
                    db.execute('INSERT INTO thesis_students(semester,user_id,profile) VALUES (?,?,?) ON CONFLICT(semester,user_id) DO NOTHING',
                               (semester, target_uid, '{"skills":[]}'))
                    db.execute(
                        'INSERT INTO thesis_outcomes(semester,user_id,advisor_id,rating,skills_applied,summary_note,updated_at) '
                        'VALUES (?,?,?,?,?,?,?) '
                        'ON CONFLICT(semester,user_id) DO UPDATE SET '
                        'advisor_id=excluded.advisor_id,rating=excluded.rating,skills_applied=excluded.skills_applied,'
                        'summary_note=excluded.summary_note,updated_at=excluded.updated_at',
                        (semester, target_uid, user['advisor_id'], rating, skills_applied, summary_note, now),
                    )
                    return {'ok': True}

        if action == 'verify-enrollment':
            with term() as (db, _):
                roster, _ = load_intake(db, semester)
                if not roster or user['id'] not in roster:
                    raise HTTPException(409, 'not_in_semester_roster')
                entry = roster[user['id']]
                expected_code = str(entry.get('enrollment_code') or '').strip()
                given_code = str(payload.get('enrollment_code') or '').strip()
                given_sid = str(payload.get('student_id') or '').strip()
                if expected_code and not hmac.compare_digest(given_code, expected_code):
                    raise HTTPException(401, 'invalid_enrollment_code')
                if given_sid and given_sid.casefold() != entry['student_id'].casefold():
                    raise HTTPException(401, 'invalid_enrollment_code')
                db.execute('INSERT INTO thesis_semesters(semester) VALUES (?) ON CONFLICT(semester) DO NOTHING', (semester,))
                db.execute(
                    'INSERT INTO thesis_enrollments(semester,user_id,student_id,verified_at) VALUES (?,?,?,?) '
                    'ON CONFLICT(semester,user_id) DO UPDATE SET verified_at=excluded.verified_at',
                    (semester, user['id'], entry['student_id'], datetime.now(timezone.utc).isoformat()),
                )
            return {'ok': True}

        if action == 'choice' and not ('advisor_ids' in payload or 'advisor_id' in payload):
            raise HTTPException(422, 'invalid_advisor_selection')
        advisor_ids = payload.get('advisor_ids', [] if payload.get('advisor_id') is None else [payload['advisor_id']])
        active = active_service() if action in ('proposal', 'manual', 'publish', 'advisor-skills', 'normalize') or action == 'choice' and advisor_ids else None
        replacement = read_roster(payload.get('csv_text')) if action == 'roster' else None

        with term(write=True, allow_published=action == 'revoke') as (db, state):
            roster, closed = load_intake(db, semester)
            if action in ('assessment', 'normalize', 'choice', 'topic') and closed:
                raise HTTPException(409, 'preferences_closed')
            if action in ('choice', 'topic') and roster is not None:
                in_roster, _ = is_student_verified_in_roster(db, user['id'], roster)
                if not in_roster:
                    raise HTTPException(409, 'not_in_semester_roster')
            if action == 'revoke':
                if state['published'] is None:
                    raise HTTPException(409, 'semester_not_published')
                thesis_history.append_history(db, semester, state['revision'], 'revoke', user, json.loads(state['published']))
                db.execute('UPDATE thesis_semesters SET published=NULL WHERE semester=?', (semester,))
                return {'ok': True}
            saved = json.loads(state['proposal']) if state['proposal'] else {}
            manual = saved.pop('manual', None)
            if action == 'roster':
                db.execute('INSERT INTO thesis_intake(semester,roster) VALUES (?,?) '
                           'ON CONFLICT(semester) DO UPDATE SET roster=excluded.roster',
                           (semester, json.dumps(replacement, ensure_ascii=False)))
            elif action == 'advisor-skills':
                info = save_advisor_skills_csv(db, payload.get('csv_text', ''), active.advisor_ids)
                app.state.thesis_rag_agent = None
                db.execute('UPDATE thesis_semesters SET proposal=? WHERE semester=?',
                           (json.dumps({'manual': manual}, ensure_ascii=False) if manual else None, semester))
                return {'ok': True, **info}
            elif action in ('close', 'reopen'):
                if roster is None:
                    raise HTTPException(409, 'semester_roster_required')
                db.execute('UPDATE thesis_intake SET closed=? WHERE semester=?', (int(action == 'close'), semester))
            elif action == 'assessment':
                profile = assess(payload)
                db.execute('INSERT INTO thesis_students(semester,user_id,profile) VALUES (?,?,?) '
                           'ON CONFLICT(semester,user_id) DO UPDATE SET profile=excluded.profile',
                           (semester, user['id'], json.dumps(profile, ensure_ascii=False)))
                # If raw notes were also submitted alongside survey, normalize immediately
                if any(payload.get(k) for k in ('raw_title', 'raw_description', 'raw_background')):
                    from src.serving.profile_normalizer import normalize_student_profile
                    dossier = normalize_student_profile(
                        profile,
                        raw_title=str(payload.get('raw_title') or ''),
                        raw_description=str(payload.get('raw_description') or ''),
                        raw_background=str(payload.get('raw_background') or ''),
                        taxonomy=active_service().taxonomy,
                    )
                    save_dossier(db, user['id'], dossier)
            elif action == 'normalize':
                row = db.execute('SELECT profile FROM thesis_students WHERE semester=? AND user_id=?',
                                 (semester, user['id'])).fetchone()
                if not row:
                    raise HTTPException(409, 'assessment_required')
                from src.serving.profile_normalizer import normalize_student_profile
                profile = json.loads(row['profile'])
                dossier = normalize_student_profile(
                    profile,
                    raw_title=str(payload.get('raw_title') or ''),
                    raw_description=str(payload.get('raw_description') or ''),
                    raw_background=str(payload.get('raw_background') or ''),
                    taxonomy=active.taxonomy,
                )
                if payload.get('formal_title_override'):
                    dossier['formal_title'] = str(payload['formal_title_override']).strip()[:240]
                if payload.get('formal_summary_override'):
                    dossier['formal_summary'] = str(payload['formal_summary_override']).strip()[:1200]
                if payload.get('save', True):
                    save_dossier(db, user['id'], dossier)
                    # Also sync standardized topic description to thesis_preferences if student already has preferences
                    pref = load_preference(db, user['id'])
                    if pref:
                        std_topic = f"{dossier['formal_title']} — {dossier['formal_summary']}"[:2000]
                        upsert_preference(db, user['id'], json.loads(pref['advisor_ids']), std_topic)
                return {'ok': True, 'dossier': dossier}
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
                if roster is not None and student not in roster:
                    raise HTTPException(409, 'not_in_semester_roster')
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
            elif action == 'manual':
                if roster is None:
                    raise HTTPException(409, 'semester_roster_required')
                if payload.get('id') != (manual['id'] if manual else None):
                    raise HTTPException(409, 'stale_manual_assignment')
                choices = payload.get('assignments')
                advisors = {a['advisor_id']: {'advisor_id': a['advisor_id'], 'advisor_name': a['advisor_name']}
                            for a in advisor_catalog(active, db=db)}
                student_ids = {row['student_id']: uid for uid, row in roster.items()}
                if (not isinstance(choices, dict) or not choices.keys() <= student_ids.keys()
                        or any(not isinstance(a, str) or a not in advisors for a in choices.values())):
                    raise HTTPException(422, 'invalid_manual_assignment')
                rows = [{**advisors[choices[row['student_id']]], 'user_id': uid,
                         'student_id': row['student_id'], 'student_name': row['name']}
                        for uid, row in roster.items() if row['student_id'] in choices]
                reason = payload.get('reason', '')
                if not isinstance(reason, str) or len(reason) > 2000 or '\x00' in reason:
                    raise HTTPException(422, 'invalid_manual_reason')
                quotas, exceptions = thesis_history.manual_review(active, roster, load_requests(db), saved, rows)
                manual = {'id': uuid4().hex, 'algorithm': 'manual', 'assignments': rows,
                          'reason': reason.strip(), 'quotas': quotas, 'exceptions': exceptions}
                thesis_history.append_history(db, semester, state['revision'], 'manual_save', user, manual)
                db.execute('UPDATE thesis_semesters SET proposal=? WHERE semester=?',
                           (json.dumps({**saved, 'manual': manual}, ensure_ascii=False), semester))
                return {'ok': True}
            elif action == 'proposal':
                selected = payload.get('advisor_ids')
                custom_quotas = payload.get('custom_quotas')
                if (not isinstance(selected, list) or not selected or len(selected) > len(active.advisor_ids)
                        or any(not isinstance(a, str) or a not in active.advisor_ids for a in selected)
                        or len(set(selected)) != len(selected)):
                    raise HTTPException(422, 'invalid_advisor_selection')
                students = load_students(db)
                requests = load_requests(db)
                if roster is None:
                    if not students or len(students) > 1000:
                        raise HTTPException(409, 'invalid_registration_count')
                    proposal = allocation(active, students, requests, selected, db=db, custom_quotas=custom_quotas)
                else:
                    if not closed:
                        raise HTTPException(409, 'close_preferences_first')
                    requests = [r for r in requests if r['user_id'] in roster]
                    topics = {r['user_id']: r['topic_description'] or '' for r in requests if r['rank'] is not None}
                    dossiers = load_all_dossiers(db)
                    # Preserve compatibility with unit-test monkeypatches that accept 4 positional args
                    import inspect
                    sig = inspect.signature(compare_models)
                    if 'db' in sig.parameters:
                        proposal = compare_models(
                            active,
                            semester_students(roster, students, topics, dossiers=dossiers),
                            requests,
                            selected,
                            db=db,
                            custom_quotas=custom_quotas,
                        )
                    else:
                        proposal = compare_models(active, semester_students(roster, students, topics), requests, selected)
                db.execute('UPDATE thesis_semesters SET proposal=? WHERE semester=?',
                           (json.dumps({**proposal, 'manual': manual}, ensure_ascii=False), semester))
                return proposal
            elif action == 'publish':
                if payload.get('algorithm') == 'manual':
                    if not closed:
                        raise HTTPException(409, 'close_preferences_first')
                    if (not manual or manual['id'] != payload.get('id')
                            or {r['user_id'] for r in manual['assignments']} != set(roster or {})):
                        raise HTTPException(409, 'incomplete_manual_assignment')
                    quotas, exceptions = thesis_history.manual_review(active, roster, load_requests(db), saved, manual['assignments'])
                    reason = payload.get('reason', manual.get('reason', ''))
                    if not isinstance(reason, str) or len(reason) > 2000 or '\x00' in reason:
                        raise HTTPException(422, 'invalid_manual_reason')
                    if any(exceptions.values()) and not reason.strip():
                        raise HTTPException(422, {'code': 'manual_exception_reason_required', 'exceptions': exceptions})
                    published = {**manual, 'reason': reason.strip(), 'quotas': quotas, 'exceptions': exceptions,
                                 'publication_revision': state['revision']}
                    thesis_history.append_history(db, semester, state['revision'], 'publish', user, published)
                    db.execute('UPDATE thesis_semesters SET published=? WHERE semester=?',
                               (json.dumps(published, ensure_ascii=False), semester))
                    return {'ok': True}
                proposal = saved
                if not proposal or proposal['id'] != payload.get('id') or proposal['status'] != 'feasible':
                    raise HTTPException(409, 'stale_or_infeasible_proposal')
                if proposal.get('results'):
                    algorithm = payload.get('algorithm')
                    if algorithm not in ('ppo', 'dqn', 'hungarian') or algorithm not in proposal['results'] or proposal['results'][algorithm]['status'] != 'feasible':
                        raise HTTPException(422, 'publication_algorithm_required')
                    published = {**proposal, 'algorithm': algorithm, 'assignments': proposal['results'][algorithm]['assignments']}
                else:
                    published = proposal
                published = {**published, 'publication_revision': state['revision']}
                thesis_history.append_history(db, semester, state['revision'], 'publish', user, published)
                db.execute('UPDATE thesis_semesters SET published=? WHERE semester=?',
                           (json.dumps(published, ensure_ascii=False), semester))
                return {'ok': True}
            retained = json.dumps({'manual': manual}, ensure_ascii=False) if manual and action != 'roster' else None
            db.execute('UPDATE thesis_semesters SET proposal=? WHERE semester=?', (retained, semester))
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
        raw_t = topic_text(payload)
        upsert_preference(db, student, ids, raw_t)
        if payload.get('auto_normalize') and raw_t:
            row = db.execute('SELECT profile FROM thesis_students WHERE semester=? AND user_id=?', (semester, student)).fetchone()
            if row:
                from src.serving.profile_normalizer import normalize_student_profile
                dossier = normalize_student_profile(json.loads(row['profile']), raw_description=raw_t)
                save_dossier(db, student, dossier)

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
        row = db.execute('SELECT profile FROM thesis_students WHERE semester=? AND user_id=?', args).fetchone()
        if not row:
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
        desc = topic_text(payload, previous['topic_description'] if previous else '')
        upsert_preference(db, student, advisor_ids, desc)
        # Auto-generate standardized dossier if student typed raw description and has no dossier yet
        if desc and not load_dossier(db, student):
            from src.serving.profile_normalizer import normalize_student_profile
            dossier = normalize_student_profile(json.loads(row['profile']), raw_description=desc)
            save_dossier(db, student, dossier)
        if advisor_ids and 'contact' in payload:
            save_contact(db, student, payload['contact'])

    @router.post('/api/thesis/{action}')
    async def change(action: str, request: Request):
        allowed_actions = {
            'assessment', 'normalize', 'verify-enrollment', 'choice', 'topic', 'contact', 'milestone',
            'decision', 'milestone-review', 'outcome', 'threshold', 'proposal', 'publish',
            'roster', 'advisor-skills', 'close', 'reopen', 'revoke', 'manual',
        }
        if action not in allowed_actions:
            raise HTTPException(404, 'unknown_thesis_action')
        check_origin(request)
        payload = await app.state.rebuild_read_body(request)
        try:
            return await run_in_threadpool(mutate, action, request, payload)
        except ValueError as error:
            if str(error) == 'assessment_incomplete':
                raise HTTPException(422, 'assessment_incomplete') from None
            raise
