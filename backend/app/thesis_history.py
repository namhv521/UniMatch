"""Transactional snapshots of dean decisions, scoped to the configured semester."""
import json
from collections import Counter
from datetime import datetime, timezone


def manual_review(active, roster, requests, proposal, assignments):
    from src.domain.rebuild_matching import equal_quotas
    ids = active.advisor_ids
    accepted = {r['user_id']: r['advisor_id'] for r in requests
                if r['status'] == 'accepted' and r['user_id'] in roster}
    counts = Counter(accepted.values())
    selected = [q['advisor_id'] for q in proposal.get('quotas', [])] or list(ids)
    selected = sorted(set(selected) | set(accepted.values()))
    extra = equal_quotas(len(roster) - len(accepted), ids, selected)
    quotas = [{'advisor_id': aid, 'total': counts[aid] + int(extra[j])} for j, aid in enumerate(ids)]
    loads = Counter(r['advisor_id'] for r in assignments)
    return quotas, {
        'over_quota': [{**q, 'assigned': loads[q['advisor_id']]} for q in quotas
                       if loads[q['advisor_id']] > q['total']],
        'changed_accepted': [{'student_id': r['student_id'], 'previous_advisor_id': accepted[r['user_id']],
                              'advisor_id': r['advisor_id']}
                             for r in assignments if r['user_id'] in accepted
                             and accepted[r['user_id']] != r['advisor_id']],
    }


def append_history(db, semester, revision, action, user, snapshot):
    # The snapshot and the state change commit or roll back together.
    db.execute('INSERT INTO thesis_history '
               '(semester,revision,action,actor_id,actor_name,created_at,proposal_id,algorithm,reason,snapshot) '
               'VALUES (?,?,?,?,?,?,?,?,?,?)',
               (semester, revision, action, user['id'], user['name'], datetime.now(timezone.utc).isoformat(),
                snapshot['id'], snapshot.get('algorithm', 'hungarian'), snapshot.get('reason', ''),
                json.dumps(snapshot, ensure_ascii=False, allow_nan=False)))


def read_history(db, semester, *, before=None, revision=None):
    if revision is not None:
        row = db.execute('SELECT * FROM thesis_history WHERE semester=? AND revision=?',
                         (semester, revision)).fetchone()
        return {**dict(row), 'snapshot': json.loads(row['snapshot'])} if row else None
    fields = 'revision,action,actor_id,actor_name,created_at,proposal_id,algorithm,reason'
    query = f'SELECT {fields} FROM thesis_history WHERE semester=?'
    params = [semester]
    if before is not None:
        query += ' AND revision<?'
        params.append(before)
    rows = [dict(row) for row in db.execute(query + ' ORDER BY revision DESC LIMIT 21', params).fetchall()]
    return {'items': rows[:20], 'next_before': rows[19]['revision'] if len(rows) > 20 else None}
