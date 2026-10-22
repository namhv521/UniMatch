"""Offline semester controls. Queuing never executes learning in a web request."""
import copy
import json
import math
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from src.data_pipeline.reconcile import _digest
from src.data_pipeline.review_decisions import record_hash


def _time(value):
    if not isinstance(value,str):
        raise ValueError('explicit_timezone_timestamp_required')
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('explicit_timezone_timestamp_required')
    return parsed


def _sha(value):
    return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None


def temporal_split(terms):
    """Check three supplied closed-term contracts; newest held out.

    Source-group identifiers must cover document aliases/duplicate reports.
    This validates syntax/isolation, never infers dates or authenticates receipts.
    Callers must resolve and verify referenced snapshot and approval bytes first.
    """
    if len(terms)<3:
        raise ValueError('three_verified_terms_required')
    seen_students,seen_groups,seen_terms=set(),set(),set()
    ordered=sorted(terms,key=lambda row:_time(row['semester_start']))
    previous=None
    for row in ordered:
        name=row.get('semester_id')
        if not name or name in seen_terms or row.get('status')!='closed':
            raise ValueError('unique_closed_semesters_required')
        if not _sha(row.get('snapshot_sha256')) or not _sha(row.get('approval_receipt_sha256')):
            raise ValueError('verified_snapshot_and_approval_required')
        start,end=_time(row['semester_start']),_time(row['closed_at'])
        if start>=end or (previous is not None and previous>=start):
            raise ValueError('nonoverlapping_chronology_required')
        if _time(row['features_available_at'])>start:
            raise ValueError('prediction_time_feature_leakage')
        students,groups=row.get('student_ids'),row.get('source_groups')
        if (not isinstance(students,list) or not students or len(set(students))!=len(students)
                or not isinstance(groups,list) or not groups or len(set(groups))!=len(groups)):
            raise ValueError('explicit_unique_students_and_sources_required')
        if seen_students.intersection(students) or seen_groups.intersection(groups):
            raise ValueError('temporal_holdout_overlap')
        seen_students.update(students);seen_groups.update(groups);seen_terms.add(name);previous=end
    result={'train':[r['semester_id'] for r in ordered[:-2]],
            'validation':[ordered[-2]['semester_id']],'test':[ordered[-1]['semester_id']],
            'terms_sha256':record_hash(ordered),'policy':'chronological-closed-terms/1.0'}
    result['split_sha256']=record_hash(result)
    return result


def forgetting_report(before,after,*,max_drop):
    """Absolute score loss, paired on identical immutable evaluation cohorts."""
    if isinstance(max_drop,bool) or not isinstance(max_drop,(int,float)) or not math.isfinite(max_drop) or max_drop<0:
        raise ValueError('declared_nonnegative_regression_tolerance_required')
    if not before and not after:
        return {'status':'unavailable','passed':False,'max_forgetting':None,'terms':[],
                'reason':'No frozen historical semester evaluations supplied.'}
    if set(before)!=set(after):
        raise ValueError('same_frozen_cohorts_required')
    rows=[]
    for name in sorted(before):
        old,new=before[name],after[name]
        if not _sha(old.get('cohort_sha256')) or old['cohort_sha256']!=new.get('cohort_sha256'):
            raise ValueError('same_frozen_cohorts_required')
        values=[old.get('mean_compatibility'),new.get('mean_compatibility')]
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1 for v in values):
            raise ValueError('finite_observed_compatibility_required')
        safe=all(row.get('coverage')==1. and row.get('constraint_violations')==0 for row in (old,new))
        loss=values[0]-values[1]
        rows.append({'semester_id':name,'cohort_sha256':old['cohort_sha256'],
                     'before':values[0],'after':values[1],'forgetting':max(0.,loss),
                     'signed_loss':loss,'safety_passed':safe,'passed':safe and loss<=max_drop+1e-12})
    return {'status':'measured','max_drop':max_drop,'passed':all(r['passed'] for r in rows),
            'max_forgetting':max(r['forgetting'] for r in rows),'terms':rows}


def continue_ppo(parent_directory,old_env,new_env,*,old_contract,new_contract,bridge_proof=None):
    """Copy only compatible weights/optimizer; a fresh rollout buffer is mandatory."""
    from src.rl.continual_dqn import validate_continual_contracts
    from src.rl.rebuild_ppo import MaskedPPOAgent
    validate_continual_contracts(old_contract,new_contract,bridge_proof=bridge_proof)
    declared=new_contract.get('training_student_ids')
    if not isinstance(declared,list) or not declared or len(set(declared))!=len(declared):
        raise ValueError('ppo_candidate_training_registry_required')
    provenance=new_env.training_provenance
    if not provenance or any(row['metadata'].get('split')!='train' for row in provenance):
        raise ValueError('ppo_candidate_train_only_required')
    if any(not set(row['student_ids']).issubset(set(declared)) for row in provenance):
        raise ValueError('ppo_candidate_training_registry_mismatch')
    if new_env.reward_weights!=new_contract['reward_weights']:
        raise ValueError('ppo_candidate_reward_contract_mismatch')
    if any(row['metadata'].get('policy_version')!=new_contract['quota_policy_version'] for row in provenance):
        raise ValueError('ppo_candidate_policy_contract_mismatch')
    parent=MaskedPPOAgent.load(parent_directory,old_env,expected_contract=old_contract)
    candidate=MaskedPPOAgent(new_env,contract=new_contract,**parent.config)
    candidate.model.policy.load_state_dict(copy.deepcopy(parent.model.policy.state_dict()))
    candidate.model.policy.optimizer.load_state_dict(copy.deepcopy(parent.model.policy.optimizer.state_dict()))
    candidate.model.num_timesteps=parent.model.num_timesteps
    candidate.continuation_provenance={'parent_directory':str(Path(parent_directory).resolve()),
        'parent_state_sha256':_digest(Path(parent_directory)/'state.pt'),
        'parent_contract_sha256':record_hash(old_contract),'candidate_contract_sha256':record_hash(new_contract),
        'rollouts':'fresh_only','bridge_sha256':record_hash(bridge_proof) if bridge_proof else None}
    return candidate


class OfflineJobs:
    """Local durable job state, single transactional claim, no training callback.

    A crashed worker stays running; an operator must inspect artifacts before
    submitting a new explicit attempt. Never silently rerun a half-written job.
    """
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, request TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT, result_path TEXT, result_sha256 TEXT)')

    def _connect(self):
        return sqlite3.connect(self.path,timeout=30)

    def enqueue(self,request):
        if (not isinstance(request,dict) or request.get('scope') not in ('research_rehearsal','semester_candidate')
                or not _sha(request.get('snapshot_sha256')) or not _sha(request.get('parent_contract_sha256'))):
            raise ValueError('source_bound_offline_job_request_required')
        job_id=record_hash(request)
        with self._connect() as db:
            db.execute('INSERT OR IGNORE INTO jobs(id,request,status,created_at) VALUES (?,?,?,?)',
                       (job_id,json.dumps(request,sort_keys=True,allow_nan=False),'queued',datetime.now(timezone.utc).isoformat()))
        self.get(job_id)
        return job_id

    def get(self,job_id):
        with self._connect() as db:
            db.row_factory=sqlite3.Row
            row=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        if row is None: raise ValueError('unknown_offline_job')
        row=dict(row);row['request']=json.loads(row['request'])
        if record_hash(row['request'])!=job_id: raise ValueError('offline_job_request_hash_mismatch')
        if row['result_path'] and _digest(Path(row['result_path']))!=row['result_sha256']:
            raise ValueError('offline_job_result_hash_mismatch')
        return row

    def claim(self,job_id):
        self.get(job_id)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            updated=db.execute("UPDATE jobs SET status='running',started_at=? WHERE id=? AND status='queued'",
                               (datetime.now(timezone.utc).isoformat(),job_id)).rowcount
            if updated!=1: raise ValueError('offline_job_not_queued')
        return self.get(job_id)

    def finish(self,job_id,status,result_path):
        if status not in ('succeeded','failed','blocked'): raise ValueError('invalid_offline_job_terminal_status')
        path=Path(result_path).resolve();digest=_digest(path)
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            updated=db.execute('UPDATE jobs SET status=?,finished_at=?,result_path=?,result_sha256=? WHERE id=? AND status=?',
                (status,datetime.now(timezone.utc).isoformat(),str(path),digest,job_id,'running')).rowcount
            if updated!=1: raise ValueError('offline_job_not_running')
        return self.get(job_id)
