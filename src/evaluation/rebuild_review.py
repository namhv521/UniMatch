"""Bind blinded agent proposals to a frozen packet without granting owner approval."""
import json
from pathlib import Path

from src.data_pipeline.reconcile import _digest
from src.data_pipeline.review_decisions import record_hash


def combine_advisory_reviews(primary, crosschecks):
    """Retain independent opinions; disputed grades await owner adjudication.

    This agreement sample is a diagnostic, not representative domain validation.
    Call map_advisory_labels on the combined output to verify source evidence.
    """
    primary, crosschecks = list(primary), list(crosschecks)
    rows = {r['pair_id']: dict(r) for r in primary}
    if len(rows) != len(primary) or len({r['pair_id'] for r in crosschecks}) != len(crosschecks):
        raise ValueError('duplicate_pair_review')
    disputed, differences, same = [], [], 0
    for other in crosschecks:
        key = other['pair_id']
        if key not in rows:
            raise ValueError('unknown_crosscheck_pair')
        original = rows[key]
        if other['reviewer'] == original['reviewer']:
            raise ValueError('independent_reviewer_required')
        if any(r.get('attribution') != 'agent_advisory' for r in (original, other)):
            raise ValueError('advisory_authority_required')
        for row in (original, other):
            grade = row.get('grade')
            if grade != 'uncertain' and (type(grade) is not int or not 0 <= grade <= 3):
                raise ValueError('invalid_relevance_grade')
        agrees = original['grade'] == other['grade']
        same += agrees
        if type(original['grade']) is int and type(other['grade']) is int:
            differences.append(abs(original['grade'] - other['grade']))
        original['crosscheck'] = {'primary_grade': original['grade'], 'independent': dict(other), 'exact_agreement': agrees}
        if not agrees:
            disputed.append(key)
            original['grade'] = 'uncertain'
            original['reason'] += ' Independent review disagrees; owner adjudication required. ' + other['reason']
    return [rows[key] for key in sorted(rows)], {
        'primary_pairs': len(primary), 'sampled_pairs': len(crosschecks),
        'exact_agreement': same / len(crosschecks) if crosschecks else None,
        'mean_absolute_grade_difference': sum(differences)/len(differences) if differences else None,
        'disputed_pairs': disputed, 'disagreement_policy': 'uncertain_pending_owner_adjudication',
        'scope': 'Systematic overlap sample; not representative or independent human domain validation.'}


def map_advisory_labels(packet, proposals):
    packet = Path(packet)
    path = packet / 'packet_manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if (manifest['blinded_pairs_sha256'] != _digest(packet / 'blinded_pairs.jsonl')
            or manifest['pair_bindings_sha256'] != _digest(packet / 'pair_bindings.json')):
        raise ValueError('modified_review_packet')
    pairs = {r['pair_id']: r for r in (json.loads(line) for line in
              (packet / 'blinded_pairs.jsonl').read_text(encoding='utf-8').splitlines() if line.strip())}
    bindings = json.loads((packet / 'pair_bindings.json').read_text(encoding='utf-8'))
    proposals = list(proposals)
    if len({r['pair_id'] for r in proposals}) != len(proposals) or {r['pair_id'] for r in proposals} != set(bindings):
        raise ValueError('review_pair_coverage_mismatch')
    labels = []
    for proposal in proposals:
        key = proposal['pair_id']
        grade = proposal.get('grade')
        if ((grade != 'uncertain' and (type(grade) is not int or not 0 <= grade <= 3))
                or proposal.get('packet_manifest_sha256') != _digest(path)
                or proposal.get('attribution') != 'agent_advisory'
                or not str(proposal.get('reviewer', '')).startswith('agent:')
                or not str(proposal.get('reason', '')).strip()):
            raise ValueError('invalid_advisory_proposal')
        if record_hash(bindings[key]) != key:
            raise ValueError('review_pair_identity_mismatch')
        for field, text in [('student_evidence', pairs[key]['student_title']+'\n'+pairs[key]['student_abstract']),
                            ('advisor_evidence', pairs[key]['advisor_profile'])]:
            refs = proposal.get(field, [])
            if (not isinstance(refs, list) or (grade != 'uncertain' and not refs)
                    or any(not isinstance(ref, str) or not ref.strip() or ref not in text for ref in refs)):
                raise ValueError('unsupported_advisory_evidence')
        labels.append({**bindings[key], 'grade': grade, 'attribution': 'agent_advisory',
                       'reviewer': proposal['reviewer'], 'reason': proposal['reason'],
                       'student_evidence': proposal.get('student_evidence', []),
                       'advisor_evidence': proposal.get('advisor_evidence', []),
                       'packet_manifest_sha256': _digest(path), 'proposal_sha256': record_hash(proposal)})
    return sorted(labels, key=lambda r: (r['student_id'], r['advisor_id']))
