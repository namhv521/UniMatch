"""Executable P6 technical rehearsal; never claims a new academic semester."""
import csv
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

from src.data_pipeline.rebuild_cohorts import build_research_suite
from src.data_pipeline.reconcile import ROOT, _digest
from src.data_pipeline.review_decisions import record_hash
from src.data_pipeline.semester_snapshots import create_snapshot, verify_snapshot, drift_report
from src.environment.rebuild_env import MatchingEnv
from src.evaluation.rebuild_benchmark import evaluate_problem, problem_payload
from src.features.rebuild_acceptance import _verified_manifest
from src.rl.continual_dqn import ContinualDQN
from src.rl.rebuild_dqn import MaskedDQN
from src.rl.rebuild_ppo import MaskedPPOAgent
from src.rl.semester_learning import OfflineJobs, continue_ppo, forgetting_report


def _write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


def load_phase5_parent(output):
    output=Path(output).resolve()
    gate=json.loads((output/'reports/phase5_gate.json').read_text(encoding='utf-8'))
    if gate.get('status')!='verified' or gate.get('can_start_phase6') is not True:
        raise ValueError('verified_phase5_required')
    directory=Path(gate['run_dir']).resolve()
    if directory.parent!=output/'phase5_runs' or directory.name!=gate['run_id']:
        raise ValueError('phase5_run_path_mismatch')
    manifest=_verified_manifest(directory)
    if manifest['gate']!=gate:
        raise ValueError('phase5_gate_manifest_mismatch')
    inputs=json.loads((directory/'input_manifest.json').read_text(encoding='utf-8'))
    if record_hash(inputs['model_contract'])!=gate['model_contract_sha256']:
        raise ValueError('phase5_model_contract_mismatch')
    for name,digest in inputs['code_sha256'].items():
        if _digest(ROOT/name)!=digest: raise ValueError('phase5_source_code_changed')
    return directory,inputs


def phase6_gate(run_id,checks):
    required=('idempotent_upload','offline_learning','reload_reproducible',
              'rollback_preserves_assignments','no_holdout_training')
    return {'phase':6,'run_id':run_id,'status':'partial','can_start_phase7':False,
        'scope':'research_rehearsal_only','technical_implementation_verified':all(checks.get(k) is True for k in required),
        'checks':checks,'models_promoted':False,'operational_allocation_authorized':False,
        'production_deployed':False,'recommended_default':'hungarian','temporal_forgetting':None,
        'unseen_semester_performance':None,
        'blocking_reasons':['No curated closed-semester snapshots with prediction-time feature evidence and bound approvals.',
            'No frozen independent chronological train/validation/test terms; P4 splits and current parent are non-temporal.',
            'No verified semester outcome records; new source folder duplicates original documents.'],
        'limitations':['Fresh transitions on existing P4 training rows are rehearsal, not new-semester data.',
            'P4 validation is reused for regression; the P4 final test is not evaluated again here.',
            'Technical drill fixtures are not academic approvals or real assignments.']}


def _registry_drill(directory,contract,checkpoint,before_checkpoint,evaluation):
    from src.serving.rebuild_registry import CandidateRegistry, checkpoint_digest, content_sha256
    registry=CandidateRegistry(directory/'registry.sqlite3',compatible_contract=contract,scope='technical_drill')
    ids=[]
    for label,path in [('previous',before_checkpoint),('candidate',checkpoint)]:
        gate={'status':'verified','can_promote_candidate':True,'scope':'technical_drill',
              'checks':{'safety_passed':True,'frozen_evaluation_passed':True},
              'checkpoint_sha256':checkpoint_digest(path),'contract_sha256':content_sha256(contract),
              'frozen_evaluation_sha256':_digest(evaluation)}
        gate_path=directory/(label+'_gate.json');_write(gate_path,gate)
        reports={'gate':gate_path,'evaluation':evaluation}
        candidate_id=registry.register(path,contract,reports);ids.append(candidate_id)
        receipt={'kind':'sandbox_candidate_promotion','decision':'approve','scope':'technical_drill',
            'authorization_source':'automated_test_fixture','reviewer':'phase6-drill',
            'approval_quote':'Technical rollback drill only; no operational authorization.',
            'candidate_id':candidate_id,'contract_sha256':content_sha256(contract),
            'evaluation_sha256':{k:_digest(v) for k,v in reports.items()}}
        _write(directory/(label+'_receipt.json'),receipt)
        registry.promote(candidate_id,receipt)
    assignments=[{'student_id':'technical-fixture-student','advisor_id':'technical-fixture-advisor'}]
    source={'scope':'technical_drill','source_ref':'explicit_synthetic_test_fixture','source_sha256':record_hash(assignments)}
    batch_id='rollback-fixture';batch={'batch_id':batch_id,'assignments':assignments,'source':source}
    receipt={'kind':'sandbox_assignment_approval','decision':'approve','scope':'technical_drill',
        'authorization_source':'automated_test_fixture','reviewer':'phase6-drill',
        'approval_quote':'Synthetic fixture to verify immutable history only.',
        'batch_sha256':content_sha256(batch),'source_sha256':content_sha256(source)}
    registry.record_assignments(batch_id,assignments,source=source,owner_receipt=receipt)
    old=registry.get_assignments(batch_id)
    previous=json.loads((directory/'previous_receipt.json').read_text(encoding='utf-8'))
    previous['kind']='sandbox_candidate_rollback'
    registry.rollback(ids[0],previous)
    return {'scope':'technical_drill','operational_authorization':False,
            'candidate_ids':ids,'active':registry.active(),
            'assignment_history_sha256':content_sha256(old),
            'assignments_unchanged':old==registry.get_assignments(batch_id)}


def run_rehearsal(output,*,timesteps=1024,seed=42):
    if type(timesteps) is not int or timesteps<256 or timesteps%256:
        raise ValueError('rehearsal_budget_multiple_of_256_required')
    output=Path(output).resolve();parent,inputs=load_phase5_parent(output)
    if seed not in inputs['budget']['seeds']:
        raise ValueError('seed_missing_from_verified_parent')
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    now=datetime.now(timezone.utc);run_id=now.strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    directory=output/'phase6_runs'/run_id;directory.mkdir(parents=True,exist_ok=False)
    code_paths=['src/rl/semester_learning.py','src/rl/continual_dqn.py','src/data_pipeline/semester_snapshots.py',
                'src/data_pipeline/semester_evidence.py','src/serving/rebuild_registry.py',
                'src/evaluation/semester_rehearsal.py','scripts/rehearse_semester_learning.py']
    code={name:_digest(ROOT/name) for name in code_paths}
    contract=inputs['model_contract'];suite=build_research_suite(output)
    if [problem_payload(p) for p in suite['train']]!=inputs['training_problems']:
        raise ValueError('rehearsal_frozen_training_mismatch')
    train_ids={s for p in suite['train'] for s in p.student_ids}
    heldout=set(suite['validation'].student_ids)|set(suite['test'].student_ids)
    if train_ids&heldout or train_ids!=set(contract['training_student_ids']):
        raise ValueError('rehearsal_holdout_overlap')
    _write(directory/'input_manifest.json',{'scope':'research_rehearsal','parent_run_id':parent.name,
        'parent_manifest_sha256':_digest(parent/'manifest.json'),'contract':contract,
        'training_problems':inputs['training_problems'],'validation_problem':problem_payload(suite['validation']),
        'training_student_count':len(train_ids),'reserved_holdout_count':len(heldout),
        'seed':seed,'timesteps':timesteps,'code_sha256':code})
    p3=json.loads((output/'reports/phase3_gate.json').read_text(encoding='utf-8'))
    snapshot_args={'semester_id':p3['semester_id'],'captured_at':now.isoformat(),'status':'research',
        'feature_sha256':contract['feature_contract_sha256'],'taxonomy_sha256':p3['taxonomy_sha256'],
        'policy_sha256':record_hash({'policy_version':contract['quota_policy_version'],'scope':'research_only'}),
        'files':{'students.csv':output/'gold/students.csv','advisors.csv':output/'gold/advisors.csv',
                 'gold_manifest.json':output/'gold/snapshot_manifest.json','learning_inputs.json':directory/'input_manifest.json'}}
    snapshot=create_snapshot(output/'semester_store',**snapshot_args)
    same=create_snapshot(output/'semester_store',**snapshot_args)
    verify_snapshot(output/'semester_store',snapshot['snapshot_id'])
    _write(directory/'snapshot_reference.json',{'snapshot_id':snapshot['snapshot_id'],'status':'research',
        'real_closed_semester':False,'idempotent':same==snapshot})
    rows=list(csv.DictReader((output/'gold/students.csv').open(encoding='utf-8-sig')))
    _write(directory/'reports/drift.json',{'scope':'identical_snapshot_integrity_control_only',
        'report':drift_report(rows,rows,tag_fields=['topic_tags','skills_tags'],required_fields=['thesis_abstract'])})
    jobs=OfflineJobs(output/'phase6_jobs.sqlite3')
    request={'scope':'research_rehearsal','snapshot_sha256':snapshot['snapshot_id'],
             'parent_contract_sha256':record_hash(contract),'input_manifest_sha256':_digest(directory/'input_manifest.json'),
             'run_id':run_id,'seed':seed,'timesteps':timesteps}
    job_id=jobs.enqueue(request);assert jobs.enqueue(request)==job_id;jobs.claim(job_id)
    _write(directory/'job_request.json',{'job_id':job_id,'request':request})
    try:
        old_env=MatchingEnv(suite['train'],shuffle_students=True)
        ppo_dir=parent/'checkpoints/ppo'/f'seed-{seed}';dqn_dir=parent/'checkpoints/dqn'/f'seed-{seed}'
        old_ppo=MaskedPPOAgent.load(ppo_dir,old_env,expected_contract=contract)
        old_dqn=MaskedDQN.load(dqn_dir,expected_contract=contract)
        models={'ppo':continue_ppo(ppo_dir,old_env,MatchingEnv(suite['train'],shuffle_students=True),
                                  old_contract=contract,new_contract=contract),
                'dqn':ContinualDQN.from_checkpoint(dqn_dir,old_contract=contract,new_contract=contract)}
        initial={'ppo':old_ppo,'dqn':old_dqn}
        problem=suite['validation'];frozen_hash=record_hash(problem_payload(problem));results={};logs={}
        for algorithm,model in models.items():
            before=evaluate_problem(problem,algorithm,model=initial[algorithm],seed=seed)
            if algorithm=='ppo':
                logs[algorithm]=model.learn(timesteps)
                logs[algorithm]['continuation_provenance']=model.continuation_provenance
            else:
                logs[algorithm]=model.learn(MatchingEnv(suite['train'],shuffle_students=True),timesteps,
                                           epsilon_start=.2,epsilon_end=.05)
            after=evaluate_problem(problem,algorithm,model=model,seed=seed)
            for row in (before,after):row['cohort_sha256']=frozen_hash
            measured=forgetting_report({'reused_p4_validation':{**before['metrics'],'cohort_sha256':frozen_hash}},
                                      {'reused_p4_validation':{**after['metrics'],'cohort_sha256':frozen_hash}},max_drop=0.)
            measured['scope']='reused_non_temporal_research_regression';measured['promotion_tolerance_approved']=False
            results[algorithm]={'before':before,'after':after,'regression':measured}
            target=directory/'checkpoints'/algorithm
            model.save(target)
            loaded=MaskedPPOAgent.load(target,MatchingEnv(suite['train']),expected_contract=contract) if algorithm=='ppo' else ContinualDQN.load(target,expected_contract=contract)
            reloaded=evaluate_problem(problem,algorithm,model=loaded,seed=seed)
            results[algorithm]['reload_trace_equal']=after['trace']==reloaded['trace']
        _write(directory/'training.json',logs);_write(directory/'reports/evaluation.json',results)
        rollback=_registry_drill(directory/'rollback_drill',contract,directory/'checkpoints/ppo',ppo_dir,
                                 directory/'reports/evaluation.json')
        _write(directory/'reports/rollback.json',rollback)
        checks={'idempotent_upload':same==snapshot,'offline_learning':all(r['actual_timesteps']>=timesteps and r['losses'] for r in logs.values()),
                'reload_reproducible':all(r['reload_trace_equal'] for r in results.values()),
                'rollback_preserves_assignments':rollback['assignments_unchanged'],
                'no_holdout_training':not bool(train_ids&heldout),
                'code_unchanged':all(_digest(ROOT/name)==digest for name,digest in code.items()),
                'dqn_exact_stratification':logs['dqn']['replay_origin_samples']['old']==logs['dqn']['replay_origin_samples']['current']>0}
        checks={k:bool(v) for k,v in checks.items()}
        gate=phase6_gate(run_id,checks)
        gate['technical_implementation_verified']=gate['technical_implementation_verified'] and all(checks.values())
        _write(directory/'reports/phase6_gate.json',gate)
        artifacts=[{'path':p.relative_to(directory).as_posix(),'sha256':_digest(p)} for p in sorted(directory.rglob('*')) if p.is_file()]
        _write(directory/'manifest.json',{'gate':gate,'artifacts':artifacts})
        jobs.finish(job_id,'succeeded',directory/'manifest.json')
        _write(output/'reports/phase6_gate.json',gate)
        return gate
    except Exception as error:
        _write(directory/'failure.json',{'error_type':type(error).__name__,'error':str(error)})
        jobs.finish(job_id,'failed',directory/'failure.json')
        raise
