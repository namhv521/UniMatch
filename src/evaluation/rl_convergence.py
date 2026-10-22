"""Predeclared local more-steps experiment; validation only, frozen final test."""
from __future__ import annotations

import json
import math
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from scipy.stats import t

from src.data_pipeline.rebuild_cohorts import build_research_suite
from src.data_pipeline.reconcile import ROOT, _digest
from src.data_pipeline.review_decisions import record_hash
from src.environment.rebuild_env import MatchingEnv
from src.evaluation.rebuild_benchmark import evaluate_problem, problem_payload
from src.evaluation.semester_rehearsal import load_phase5_parent
from src.features.rebuild_acceptance import _verified_manifest
from src.rl.continual_dqn import ContinualDQN
from src.rl.rebuild_dqn import MaskedDQN
from src.rl.rebuild_ppo import MaskedPPOAgent
from src.rl.semester_learning import continue_ppo


SEEDS = (42,43,44,45,46)
PARENT_STEPS = 16384
CHECKPOINT_STEPS = (24576,32768)
METRICS = ('objective','mean_compatibility','coverage','constraint_violations','invalid_action_count','elapsed_seconds')


def _write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    encoded=json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)
    temporary=path.with_suffix(path.suffix+'.pending');temporary.write_text(encoded,encoding='utf-8');temporary.replace(path)


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _stats(values):
    values=np.asarray(values,dtype=float)
    if not len(values) or not np.isfinite(values).all():raise ValueError('finite metric observations required')
    n=len(values);mean=float(values.mean());std=float(values.std(ddof=1)) if n>1 else 0.
    half=float(t.ppf(.975,n-1)*std/math.sqrt(n)) if n>1 else None
    return {'n':n,'mean':mean,'std':std,'ci95':[mean-half,mean+half] if half is not None else None}


def _metric(row,key):
    value=row[key] if key in ('invalid_action_count','elapsed_seconds') else row['metrics'][key]
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError('finite numeric metric required')
    return value


def paired_statistics(before,after):
    def indexed(rows):
        result={r['seed']:r for r in rows}
        if len(result)!=len(rows):raise ValueError('duplicate paired seeds')
        return result
    old,new=indexed(before),indexed(after)
    if not old or set(old)!=set(new):raise ValueError('same paired seed set required')
    result={}
    for key in METRICS:
        a=[_metric(old[s],key) for s in sorted(old)];b=[_metric(new[s],key) for s in sorted(old)]
        delta=_stats(np.subtract(b,a))
        result[key]={'before':_stats(a),'after':_stats(b),'n':delta['n'],
            'delta_mean':delta['mean'],'delta_std':delta['std'],'delta_ci95':delta['ci95']}
    return result


def _safe(row):
    return (row['metrics'].get('coverage')==1. and row['metrics'].get('constraint_violations')==0
            and row.get('invalid_action_count')==0 and row.get('reload_trace_equal') is True)


def select_candidate(rows,algorithm):
    chosen=[r for r in rows if r['algorithm']==algorithm]
    parent=[r for r in chosen if r['total_steps']==PARENT_STEPS]
    if {r['seed'] for r in parent}!=set(SEEDS) or len(parent)!=len(SEEDS) or not all(_safe(r) for r in parent):
        raise ValueError('complete safe frozen parent evaluation required')
    base_mean=_stats([r['metrics']['objective'] for r in parent])['mean']
    representative=next(r for r in parent if r['seed']==42)
    selected=parent;best_mean=base_mean
    for steps in CHECKPOINT_STEPS:
        stage=[r for r in chosen if r['total_steps']==steps]
        if len(stage)!=len(SEEDS) or {r['seed'] for r in stage}!=set(SEEDS) or not all(_safe(r) and r.get('weights_changed') is True for r in stage):continue
        mean=_stats([r['metrics']['objective'] for r in stage])['mean']
        fixed=next(r for r in stage if r['seed']==42)
        if mean>best_mean+1e-12 and fixed['metrics']['objective']>=representative['metrics']['objective']-1e-12:
            selected=stage;best_mean=mean
    result=dict(next(r for r in selected if r['seed']==42))
    result.update(improved_on_validation=best_mean>base_mean+1e-12,validation_stats=paired_statistics(parent,selected),
        fallback='hungarian',production_promoted=False,
        selection_rule='Highest safe five-seed mean validation objective; strict mean improvement, fixed seed42 non-regression, ties earlier steps.')
    return result


def validate_training_suite(suite,inputs):
    train=suite['train'];train_ids=[s for p in train for s in p.student_ids]
    validation=set(suite['validation'].student_ids);test=set(suite['test'].student_ids)
    if (len(set(train_ids))!=len(train_ids) or set(train_ids)&(validation|test) or validation&test
            or set(train_ids)!=set(inputs['model_contract']['training_student_ids'])):
        raise ValueError('frozen training/heldout membership mismatch')
    if any(p.metadata.get('split')!='train' for p in train):raise ValueError('train-only source cohorts required')
    if [problem_payload(p) for p in train]!=inputs['training_problems']:
        raise ValueError('frozen train payload mismatch')
    if problem_payload(suite['validation'])!=inputs['evaluation_problems']['validation']:
        raise ValueError('frozen validation payload mismatch')
    return {'holdout_isolated':True,'training_count':len(train_ids),'validation_count':len(validation),
            'reserved_test_count':len(test),'final_test_evaluated':False}


def checkpoint_weights_sha256(model,algorithm):
    import hashlib
    state=model.model.policy.state_dict() if algorithm=='ppo' else model.online.state_dict()
    result=hashlib.sha256()
    for key,value in sorted(state.items()):
        result.update(key.encode());result.update(value.detach().cpu().contiguous().numpy().tobytes())
    return result.hexdigest()


def _native_files(directory):
    directory=Path(directory)
    return {p.relative_to(directory).as_posix():_digest(p) for p in sorted(directory.rglob('*')) if p.is_file()}


def load_selection(path):
    path=Path(path).resolve();directory=path.parent
    manifest=_verified_manifest(directory)
    if manifest.get('gate',{}).get('status')!='verified' or manifest['gate'].get('test_evaluated') is not False:
        raise ValueError('completed verified convergence run required')
    bound={a['path']:a['sha256'] for a in manifest['artifacts']}
    if bound.get('selection_manifest.json')!=_digest(path):raise ValueError('selection manifest not frozen')
    result=_read(path)
    if result.get('schema_version')!='rl-convergence-selection/1.0' or result.get('test_evaluated') is not False:
        raise ValueError('selection schema/scope mismatch')
    for algorithm,candidate in result['candidates'].items():
        files=_native_files(candidate['path'])
        if algorithm not in ('ppo','dqn') or candidate['algorithm']!=algorithm or files!=candidate['checkpoint_files'] or record_hash(files)!=candidate['checkpoint_sha256']:
            raise ValueError('selected checkpoint changed')
        if record_hash(candidate['native_contract'])!=candidate['native_contract_sha256'] or record_hash(candidate['frozen_encoder'])!=candidate['frozen_encoder_sha256']:
            raise ValueError('selected encoder or contract binding mismatch')
    return result


def run_convergence(output):
    output=Path(output).resolve();parent,inputs=load_phase5_parent(output)
    if inputs['budget']['timesteps_per_algorithm_seed']!=PARENT_STEPS or tuple(inputs['budget']['seeds'])!=SEEDS or inputs['budget']['smoke']:
        raise ValueError('predeclared five-seed16384 parent required')
    suite=build_research_suite(output);membership=validate_training_suite(suite,inputs)
    p6gate=_read(output/'reports/phase6_gate.json');p6dir=output/'phase6_runs'/p6gate['run_id']
    p6manifest=_verified_manifest(p6dir)
    if not p6manifest['gate'].get('technical_implementation_verified'):
        raise ValueError('verified technical phase6 checkpoint required')
    contract=inputs['model_contract'];env=lambda:MatchingEnv(suite['train'],shuffle_students=True)
    # Independently verify both existing native and continual P6 checkpoints.
    MaskedPPOAgent.load(p6dir/'checkpoints/ppo',env(),expected_contract=contract)
    ContinualDQN.load(p6dir/'checkpoints/dqn',expected_contract=contract)
    feature=_read(output/'phase4_runs'/contract['phase4_run_id']/'feature_contract.json')
    encoder={k:feature[k] for k in ('transformer_json_sha256','transformer_idf_sha256')}
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    run=output/'convergence_runs'/run_id;run.mkdir(parents=True,exist_ok=False)
    paths=['src/evaluation/rl_convergence.py','scripts/evaluate_rl_convergence.py',
        'src/rl/semester_learning.py','src/rl/continual_dqn.py']+list(inputs['code_sha256'])
    code={name:_digest(ROOT/name) for name in sorted(set(paths))}
    _write(run/'input_manifest.json',{'scope':'offline_more_steps','parent_run_id':parent.name,
        'parent_manifest_sha256':_digest(parent/'manifest.json'),'phase6_manifest_sha256':_digest(p6dir/'manifest.json'),
        'native_contract':contract,'frozen_encoder':encoder,'membership':membership,'seeds':SEEDS,
        'parent_steps':PARENT_STEPS,'checkpoint_steps':CHECKPOINT_STEPS,'increment_steps':8192,
        'selection_rule':'Aggregate five-seed validation objective; fixed seed42 representative non-regression; ties earlier. Hungarian default.',
        'exploration':'DQN epsilon constant0.05 for both continuation stages; parent terminal epsilon0.05, no stage reset.',
        'optimizer_restart':'Both restore Adam states. PPO fresh seeded rollouts; P5 checkpoint lacks RNG/scheduler progress, so this is not proof of uninterrupted32768-step equivalence. Default learning rate is constant.',
        'training_problems':inputs['training_problems'],'validation_problem':inputs['evaluation_problems']['validation'],
        'test_evaluated':False,'code_sha256':code})
    rows=[];logs=[];completed=[]
    progress=lambda **extra:_write(run/'progress.json',{'run_id':run_id,'status':'running','completed':completed,**extra})
    progress(stage='starting');print(f'CONVERGENCE_RUN={run}',flush=True)
    try:
        for seed in SEEDS:
            baseline=evaluate_problem(suite['validation'],'hungarian',seed=seed)
            baseline.pop('trace');baseline.update(seed=seed,algorithm='hungarian',total_steps=0,reload_trace_equal=True)
            rows.append(baseline)
            for algorithm in ('ppo','dqn'):
                source=parent/'checkpoints'/algorithm/f'seed-{seed}'
                old=MaskedPPOAgent.load(source,env(),expected_contract=contract) if algorithm=='ppo' else MaskedDQN.load(source,expected_contract=contract)
                before=evaluate_problem(suite['validation'],algorithm,model=old,seed=seed)
                trace=before.pop('trace');_write(run/f'traces/{algorithm}-{seed}-{PARENT_STEPS}.json',trace)
                before.update(seed=seed,algorithm=algorithm,total_steps=PARENT_STEPS,checkpoint_path=str(source),reload_trace_equal=True,weights_changed=False)
                rows.append(before)
                model=continue_ppo(source,env(),env(),old_contract=contract,new_contract=contract) if algorithm=='ppo' else old
                previous_steps=PARENT_STEPS
                for steps in CHECKPOINT_STEPS:
                    progress(seed=seed,algorithm=algorithm,target_steps=steps,stage='training')
                    before_weights=checkpoint_weights_sha256(model,algorithm);started=time.perf_counter()
                    report=model.learn(steps-previous_steps) if algorithm=='ppo' else model.learn(env(),steps-previous_steps,epsilon_start=.05,epsilon_end=.05)
                    train_seconds=time.perf_counter()-started
                    actual=model.model.num_timesteps if algorithm=='ppo' else model.total_timesteps
                    if actual!=steps or report['actual_timesteps']!=steps-previous_steps or not report['losses']:
                        raise ValueError('incomplete continuation training or empty optimization logs')
                    target=run/f'checkpoints/{algorithm}/seed-{seed}/steps-{steps}'
                    changed=checkpoint_weights_sha256(model,algorithm)!=before_weights
                    model.save(target)
                    loaded=MaskedPPOAgent.load(target,env(),expected_contract=contract) if algorithm=='ppo' else MaskedDQN.load(target,expected_contract=contract)
                    result=evaluate_problem(suite['validation'],algorithm,model=model,seed=seed)
                    replay=evaluate_problem(suite['validation'],algorithm,model=loaded,seed=seed)
                    trace=result.pop('trace');_write(run/f'traces/{algorithm}-{seed}-{steps}.json',trace)
                    parity=trace==replay['trace'] and result['assignments']==replay['assignments']
                    result.update(seed=seed,algorithm=algorithm,total_steps=steps,checkpoint_path=str(target),
                        reload_trace_equal=parity,weights_changed=changed)
                    rows.append(result)
                    report.update(algorithm=algorithm,seed=seed,total_steps=steps,train_seconds=train_seconds,
                                  weights_changed=changed,test_evaluated=False)
                    logs.append(report);_write(run/f'training/{algorithm}-{seed}-{steps}.json',report)
                    completed.append({'algorithm':algorithm,'seed':seed,'total_steps':steps})
                    _write(run/'validation_results.json',rows)
                    progress(seed=seed,algorithm=algorithm,target_steps=steps,stage='checkpoint_complete')
                    print(f'Convergence {algorithm} seed={seed} steps={steps} objective={result["metrics"]["objective"]:.6f}',flush=True)
                    previous_steps=steps
        summaries={};candidates={}
        for algorithm in ('ppo','dqn'):
            parent_rows=[r for r in rows if r['algorithm']==algorithm and r['total_steps']==PARENT_STEPS]
            summaries[algorithm]={str(steps):paired_statistics(parent_rows,[r for r in rows if r['algorithm']==algorithm and r['total_steps']==steps]) for steps in CHECKPOINT_STEPS}
            selected=select_candidate(rows,algorithm);files=_native_files(selected['checkpoint_path'])
            candidates[algorithm]={'algorithm':algorithm,'path':selected['checkpoint_path'],'native_contract':contract,
                'native_contract_sha256':record_hash(contract),'frozen_encoder':encoder,'frozen_encoder_sha256':record_hash(encoder),
                'checkpoint_files':files,'checkpoint_sha256':record_hash(files),'checkpoint_steps':selected['total_steps'],
                'seed':42,'validation_stats':selected['validation_stats'],'improved_on_validation':selected['improved_on_validation'],
                'fallback':'hungarian','production_promoted':False,'selection_rule':selected['selection_rule']}
        hungarian=[r for r in rows if r['algorithm']=='hungarian']
        summaries['hungarian']={key:_stats([_metric(r,key) for r in hungarian]) for key in METRICS}
        for algorithm in ('ppo','dqn'):
            summaries[algorithm]['vs_hungarian']={str(steps):paired_statistics(hungarian,[r for r in rows if r['algorithm']==algorithm and r['total_steps']==steps]) for steps in (PARENT_STEPS,*CHECKPOINT_STEPS)}
        _write(run/'reports/paired_validation_summary.json',summaries)
        curves=[]
        for algorithm in ('ppo','dqn'):
            for steps in (PARENT_STEPS,*CHECKPOINT_STEPS):
                stage_rows=[r for r in rows if r['algorithm']==algorithm and r['total_steps']==steps]
                reports=[_read(parent/f'training/{algorithm}-seed-{s}.json') for s in SEEDS] if steps==PARENT_STEPS else [r for r in logs if r['algorithm']==algorithm and r['total_steps']==steps]
                loss_means=[]
                for report in reports:
                    values=[v['loss'] if isinstance(v,dict) else v for v in report['losses']]
                    loss_means.append(_stats(values)['mean'])
                curves.append({'algorithm':algorithm,'total_steps':steps,
                    'validation':{key:_stats([_metric(r,key) for r in stage_rows]) for key in METRICS},
                    'mean_logged_loss_per_seed':_stats(loss_means),
                    'loss_scope':'Algorithm-specific optimizer loss, not matching accuracy; logging windows differ by budget.'})
        _write(run/'reports/learning_curve.json',curves)
        _write(run/'selection_manifest.json',{'schema_version':'rl-convergence-selection/1.0','scope':'offline_more_steps',
            'run_id':run_id,'candidates':candidates,'test_evaluated':False,'production_default':'hungarian',
            'limitations':['Compatibility/objective are allocation metrics, not classification accuracy or supervision outcomes.',
                'Five seeds quantify training variability on one fixed validation cohort; no new independent final-test estimate.',
                'More steps may worsen quality; confidence intervals do not guarantee benefit or convergence.',
                'All data remain local; no semester or deployment claim.']})
        checks={'budget_completed':len(logs)==20,'all_weights_changed':all(r['weights_changed'] for r in logs),
            'all_reloads_match':all(r['reload_trace_equal'] for r in rows),'all_allocations_valid':all(_safe(r) for r in rows),
            'train_holdout_isolated':membership['holdout_isolated'],'test_not_evaluated':True,
            'code_unchanged':all(_digest(ROOT/name)==sha for name,sha in code.items())}
        gate={'scope':'offline_more_steps','run_id':run_id,'run_dir':str(run),'status':'verified' if all(checks.values()) else 'failed',
            'checks':checks,'test_evaluated':False,'test_reused':False,'models_promoted':False,'production_default':'hungarian',
            'completed_seeds':list(SEEDS),'parent_steps':PARENT_STEPS,'checkpoint_steps':list(CHECKPOINT_STEPS),
            'no_train_holdout_overlap':checks['train_holdout_isolated'],
            'zero_invalid_actions':all(r['invalid_action_count']==0 for r in rows),
            'zero_constraint_violations':all(r['metrics']['constraint_violations']==0 for r in rows),
            'reload_exact':checks['all_reloads_match'],'code_unchanged':checks['code_unchanged']}
        _write(run/'reports/convergence_gate.json',gate)
        _write(run/'progress.json',{'run_id':run_id,'status':'completed','completed':completed})
        artifacts=[{'path':p.relative_to(run).as_posix(),'sha256':_digest(p)} for p in sorted(run.rglob('*')) if p.is_file()]
        _write(run/'manifest.json',{'gate':gate,'artifacts':artifacts})
        if gate['status']=='verified':load_selection(run/'selection_manifest.json')
        _write(output/'reports/convergence_gate.json',gate)
        return gate
    except Exception as error:
        _write(run/'failure.json',{'error_type':type(error).__name__,'error':str(error)})
        progress(stage='failed',error=str(error))
        raise
