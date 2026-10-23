"""Isolated, from-scratch advisor-feature experiment; never promotes serving models."""
from __future__ import annotations

import copy
import ctypes
import importlib.metadata
import json
import os
import random
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

from src.data_pipeline.reconcile import ROOT, _digest
from src.data_pipeline.review_decisions import record_hash
from src.domain.rebuild_matching import AllocationProblem, feasible
from src.environment.rebuild_env import MatchingEnv
from src.evaluation.rebuild_benchmark import evaluate_problem, problem_payload
from src.evaluation.rl_convergence import (
    _write, _read, _stats, _metric, _safe, _native_files, paired_statistics,
    checkpoint_weights_sha256,
)
from src.features.rebuild_acceptance import _verified_manifest
from src.rl.rebuild_dqn import MaskedDQN
from src.rl.rebuild_ppo import MaskedPPOAgent


PLAN = {
    'schema_version':'github-advisor-retraining-plan/1.0',
    'seeds':[42,43,44,45,46], 'algorithms':['ppo','dqn'],
    'milestones':[16384,24576,32768,49152,65536,98304,131072],
    'evaluation_steps':list(range(8192,131073,8192)),
    'initialization':'from_scratch', 'test_evaluated':False,
    'selection':'Highest safe five-seed mean validation objective at declared milestones; '
                'fixed seed42 must not regress relative to16384; ties earlier. No test selection.',
    'plateau':{'evaluations':3, 'max_mean_compatibility_range':.005,
               'policy':'Final three complete safe evaluations; descriptive paired95%tCI, no early stopping.',
               'mathematical_convergence_proven':False},
    'exploration':'Global DQN epsilon linear1->0.05 for first16384 steps, then constant0.05.',
    'reset_policy':'Native DQN.learn resets seeded training env at each8192 chunk; PPO keeps live rollout state. '
                   'No training model reload between chunks. Eval/reload restores Torch/Python/NumPy RNG.',
    'hyperparameters':'Unmodified native MaskedPPOAgent and MaskedDQN defaults; CPU1 thread per process.',
    'test_scope':'Test30 was seen by Phase5; reserved here and never evaluated or tuned.',
    'memory_profile':{'scope':'Windows CPU native512-step synthetic fixture, observation472/actions35; not a full-budget peak guarantee.',
        'ppo_peak_working_set_bytes':651489280,'dqn_peak_working_set_bytes':651960320,
        'admission_worker_peak_bytes':640*1024**2,'per_worker_growth_allowance_bytes':128*1024**2,
        'system_reserve_bytes':768*1024**2},
}


def freeze_code(paths=None):
    if paths is None:
        paths=[ROOT/name for name in (
            'src/evaluation/github_retraining.py', 'scripts/train_github_advisor_models.py',
            'tests/rebuild/test_github_retraining.py', 'src/evaluation/rl_convergence.py',
            'src/evaluation/rebuild_benchmark.py', 'src/rl/rebuild_ppo.py', 'src/rl/rebuild_dqn.py',
            'src/environment/rebuild_env.py', 'src/domain/rebuild_matching.py',
            'src/baselines/rebuild_baselines.py', 'src/features/github_enrichment.py',
            'src/data_pipeline/github_advisors.py')]
    return {str(Path(path).resolve()):_digest(Path(path)) for path in paths}


def verify_code(hashes):
    if not hashes or any(not Path(path).is_file() or _digest(Path(path))!=sha for path,sha in hashes.items()):
        raise ValueError('training source changed after freeze')


def _verify_artifacts(artifacts):
    if not isinstance(artifacts,list) or not artifacts:
        raise ValueError('source and frozen encoder artifacts required')
    seen=set()
    for artifact in artifacts:
        path=Path(artifact['path'])
        if (not path.is_absolute() or str(path) in seen or not path.is_file()
                or _digest(path)!=artifact['sha256']):
            raise ValueError('source or encoder artifact changed')
        seen.add(str(path))


def _problem(payload):
    raw=copy.deepcopy(payload)
    for key in ('scores','student_features','preferences'):
        a=np.asarray(raw[key])
        if a.dtype.kind not in 'fiu':raise ValueError('numeric problem arrays required')
        raw[key]=a.astype(float)
    for key in ('available','eligible','present','student_feature_known','preference_known','capacities'):
        raw[key]=np.asarray(raw[key])
    result=AllocationProblem(**raw)
    if problem_payload(result)!=payload:raise ValueError('noncanonical frozen problem payload')
    return result


def validate_bundle(bundle):
    if bundle.get('schema_version')!='github-advisor-training-bundle/1.0':
        raise ValueError('unsupported training bundle')
    _verify_artifacts(bundle['source_artifacts'])
    _verify_artifacts(bundle['frozen_encoder']['artifacts'])
    if (not isinstance(bundle.get('student_split_sha256'),str)
            or len(bundle['student_split_sha256'])!=64 or not isinstance(bundle.get('comparators'),dict)):
        raise ValueError('frozen split hash and comparator scope required')
    suite={'train':[_problem(p) for p in bundle['training_problems']],
           **{name:_problem(bundle['evaluation_problems'][name]) for name in ('validation','test')}}
    contract=bundle['model_contract'];train_ids=[s for p in suite['train'] for s in p.student_ids]
    validation=set(suite['validation'].student_ids);test=set(suite['test'].student_ids)
    declared=contract.get('training_student_ids',[])
    if ([len(p.student_ids) for p in suite['train']]!=[45,45,45] or len(validation)!=29 or len(test)!=30
            or len(set(train_ids))!=135 or len(declared)!=135 or set(declared)!=set(train_ids)
            or set(train_ids)&(validation|test) or validation&test):
        raise ValueError('frozen135/29/30 disjoint membership required')
    split_artifacts=[a for a in bundle['source_artifacts'] if a['sha256']==bundle['student_split_sha256']]
    expected_assignments={s:split for split,problems in (
        ('train',suite['train']),('validation',[suite['validation']]),('test',[suite['test']]))
        for p in problems for s in p.student_ids}
    if not split_artifacts or any(_read(a['path']).get('assignments')!=expected_assignments for a in split_artifacts):
        raise ValueError('actual frozen split file assignments mismatch')
    if contract.get('training_problem_sha256')!=[record_hash(p) for p in bundle['training_problems']]:
        raise ValueError('native training problem hashes mismatch')
    env=MatchingEnv(suite['train'],shuffle_students=True)
    if contract.get('state_contract')!=env.state_contract or contract.get('reward_weights')!=env.reward_weights:
        raise ValueError('native environment/reward contract mismatch')
    for split,problems in [('train',suite['train']),('validation',[suite['validation']]),('test',[suite['test']])]:
        for p in problems:
            if p.metadata.get('split')!=split or p.advisor_ids!=env.advisor_ids or not feasible(p):
                raise ValueError('split, registry or feasibility mismatch')
            for key in ('feature_contract_sha256','taxonomy_feature_order_sha256'):
                if (not isinstance(contract.get(key),str) or len(contract[key])!=64
                        or p.metadata.get(key)!=contract[key]):
                    raise ValueError('feature semantics contract mismatch')
    return suite


def load_bundle(path):
    """Future admission requires the verified bundle and original GitHub inventory."""
    from src.features.github_enrichment import load_training_bundle
    bundle=load_training_bundle(path)
    validate_bundle(bundle)
    return bundle


def epsilon_window(start, count):
    if type(start) is not int or type(count) is not int or start<0 or count<1:
        raise ValueError('nonnegative global start and positive chunk required')
    def epsilon(step):return max(.05,1.-.95*min(step,16383)/16383)
    return epsilon(start),epsilon(start+count-1)


@contextmanager
def preserve_rng():
    python_state=random.getstate();numpy_state=np.random.get_state()
    try:
        with torch.random.fork_rng(devices=[]):yield
    finally:
        random.setstate(python_state);np.random.set_state(numpy_state)


def _stage(rows,algorithm,steps):
    stage=[r for r in rows if r['algorithm']==algorithm and r['total_steps']==steps]
    if any(r.get('case')!='validation' for r in stage):raise ValueError('validation-only checkpoint selection required')
    if len(stage)!=5 or {r['seed'] for r in stage}!=set(PLAN['seeds']):return []
    return stage


def _allocation_safe(row):
    return (row['metrics'].get('coverage')==1. and row['metrics'].get('constraint_violations')==0
            and row.get('invalid_action_count')==0 and row.get('trace_replay_verified') is True
            and (not row.get('reload_checked') or row.get('reload_trace_equal') is True))


def plateau_diagnostic(rows,algorithm):
    steps=sorted({r['total_steps'] for r in rows if r['algorithm']==algorithm})[-3:]
    stages=[_stage(rows,algorithm,s) for s in steps]
    complete=len(steps)==3 and all(stages) and all(_allocation_safe(r) for group in stages for r in group)
    result={'algorithm':algorithm,'evaluation_steps':steps,'complete_safe_window':complete,
        'criterion':copy.deepcopy(PLAN['plateau']), 'plateau_in_tested_budget':False,
        'mathematical_convergence_proven':False}
    if complete:
        means=[_stats([_metric(r,'mean_compatibility') for r in group])['mean'] for group in stages]
        span=max(means)-min(means)
        result.update(mean_compatibility=means,range=span,
            plateau_in_tested_budget=span<=PLAN['plateau']['max_mean_compatibility_range'],
            last_interval_paired=paired_statistics(stages[-2],stages[-1]),
            window_paired=paired_statistics(stages[0],stages[-1]))
        indexed=[{r['seed']:r for r in group} for group in stages]
        x=(np.asarray(steps,dtype=float)-steps[0])/8192
        result['compatibility_slope_per8192']=_stats([
            float(np.polyfit(x,[_metric(group[s],'mean_compatibility') for group in indexed],1)[0])
            for s in PLAN['seeds']])
    return result


def select_checkpoint(rows,algorithm):
    stages=[_stage(rows,algorithm,steps) for steps in PLAN['milestones']]
    if not all(stages) or not all(_safe(r) and r.get('checkpoint_path') for g in stages for r in g):
        raise ValueError('all seven complete safe checkpoint stages required')
    base=stages[0];fixed=next(r for r in base if r['seed']==42)
    selected=base;best=_stats([_metric(r,'objective') for r in base])['mean']
    for stage in stages[1:]:
        mean=_stats([_metric(r,'objective') for r in stage])['mean']
        representative=next(r for r in stage if r['seed']==42)
        if mean>best+1e-12 and _metric(representative,'objective')>=_metric(fixed,'objective')-1e-12:
            selected=stage;best=mean
    result=dict(next(r for r in selected if r['seed']==42))
    result.update(validation_stats=paired_statistics(base,selected),production_promoted=False,
        selection_rule=PLAN['selection'], fallback='hungarian')
    return result


def _train_job(spec):
    """One independent native model, never load old weights; only parent schedules jobs."""
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    verify_code(spec['code_sha256'])
    bundle_path=Path(spec['bundle_path'])
    if _digest(bundle_path)!=spec['bundle_sha256']:raise ValueError('training bundle changed')
    bundle=load_bundle(bundle_path);suite=validate_bundle(bundle);contract=bundle['model_contract']
    algorithm=spec['algorithm'];seed=spec['seed'];run=Path(spec['run'])
    if algorithm not in ('ppo','dqn'):raise ValueError('unsupported training algorithm')
    directory=run/'jobs'/f'{algorithm}-{seed}';directory.mkdir(parents=True,exist_ok=False)
    make_env=lambda:MatchingEnv(suite['train'],shuffle_students=True)
    env=make_env()
    model=MaskedPPOAgent(env,seed=seed,contract=contract) if algorithm=='ppo' else MaskedDQN(
        env.observation_space.shape[0],env.action_space.n,seed=seed,contract=contract)
    rows=[];training=[];baselines=[];previous=0
    for name in ('hungarian','greedy','random'):
        with preserve_rng():baseline=evaluate_problem(suite['validation'],name,seed=seed)
        trace=baseline.pop('trace');_write(directory/f'baseline-{name}-trace.json',trace)
        baseline.update(algorithm=name,seed=seed,total_steps=0,reload_trace_equal=True,case='validation')
        baselines.append(baseline)
    for steps in spec['evaluation_steps']:
        verify_code(spec['code_sha256'])
        _write(directory/'progress.json',{'status':'training','algorithm':algorithm,'seed':seed,'target_steps':steps})
        before=checkpoint_weights_sha256(model,algorithm);started=time.perf_counter();count=steps-previous
        epsilon=epsilon_window(previous,count)
        report=model.learn(count) if algorithm=='ppo' else model.learn(env,count,epsilon_start=epsilon[0],epsilon_end=epsilon[1])
        elapsed=time.perf_counter()-started
        actual=int(model.model.num_timesteps) if algorithm=='ppo' else model.total_timesteps
        if actual!=steps or report['actual_timesteps']!=count or not report['losses']:
            raise ValueError('training budget mismatch or empty optimizer logs')
        changed=checkpoint_weights_sha256(model,algorithm)!=before
        if not changed:raise ValueError('model weights did not change')
        checkpoint=None;parity=None
        with preserve_rng():
            evaluated=evaluate_problem(suite['validation'],algorithm,model=model,seed=seed)
            trace=evaluated.pop('trace');_write(directory/f'trace-{steps}.json',trace)
            if steps in spec['milestones']:
                checkpoint=run/'checkpoints'/algorithm/f'seed-{seed}'/f'steps-{steps}'
                model.save(checkpoint)
                loaded=MaskedPPOAgent.load(checkpoint,make_env(),expected_contract=contract) if algorithm=='ppo' else MaskedDQN.load(checkpoint,expected_contract=contract)
                reloaded=evaluate_problem(suite['validation'],algorithm,model=loaded,seed=seed)
                parity=trace==reloaded['trace'] and evaluated['assignments']==reloaded['assignments']
                del loaded
        evaluated.update(algorithm=algorithm,seed=seed,total_steps=steps,case='validation',
            checkpoint_path=str(checkpoint) if checkpoint else None,weights_changed=changed,
            reload_trace_equal=parity,reload_checked=checkpoint is not None)
        if not _allocation_safe(evaluated):raise ValueError('unsafe allocation or failed checkpoint reload')
        rows.append(evaluated)
        report.update(algorithm=algorithm,seed=seed,total_steps=steps,train_seconds=elapsed,
            weights_changed=changed,test_evaluated=False,
            global_epsilon_start=epsilon[0] if algorithm=='dqn' else None,
            global_epsilon_end=epsilon[1] if algorithm=='dqn' else None)
        training.append(report);_write(directory/f'training-{steps}.json',report)
        _write(directory/'validation_results.json',rows)
        _write(directory/'progress.json',{'status':'checkpoint_complete','algorithm':algorithm,'seed':seed,'total_steps':steps})
        print(f'GitHub retraining {algorithm} seed={seed} steps={steps} objective={evaluated["metrics"]["objective"]:.6f}',flush=True)
        previous=steps
    verify_code(spec['code_sha256'])
    if _digest(bundle_path)!=spec['bundle_sha256']:raise ValueError('training bundle changed during training')
    load_bundle(bundle_path)
    config=model.config if algorithm=='ppo' else {
        **{key:getattr(model,key) for key in ('seed','learning_rate','gamma','hidden_sizes','batch_size',
            'learning_starts','target_update_interval','train_frequency')},'buffer_size':model.replay.capacity}
    result={'rows':rows,'training':training,'baselines':baselines,'test_evaluated':False,
            'algorithm':algorithm,'seed':seed,'model_config':config,
            'peak_working_set_bytes':peak_working_set_bytes()}
    _write(directory/'result.json',result);_write(directory/'progress.json',{'status':'completed','total_steps':previous})
    return result


def peak_working_set_bytes():
    if os.name=='nt':
        class ProcessMemory(ctypes.Structure):
            _fields_=[('length',ctypes.c_ulong),('page_faults',ctypes.c_ulong),
                *[(name,ctypes.c_size_t) for name in ('peak_working_set','working_set','peak_paged_pool',
                    'paged_pool','peak_nonpaged_pool','nonpaged_pool','pagefile','peak_pagefile','private')]]
        counters=ProcessMemory();counters.length=ctypes.sizeof(counters)
        read=ctypes.windll.psapi.GetProcessMemoryInfo
        read.argtypes=(ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong)
        if not read(ctypes.c_void_p(-1),ctypes.byref(counters),ctypes.sizeof(counters)):
            raise RuntimeError('worker peak RAM inspection failed')
        return int(counters.peak_working_set)
    import resource
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*1024


def available_ram_bytes():
    if os.name=='nt':
        class MemoryStatus(ctypes.Structure):
            _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong),
                      *[(name,ctypes.c_ulonglong) for name in ('total_physical','available_physical','total_page','available_page','total_virtual','available_virtual','extended')]]
        status=MemoryStatus();status.length=ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):raise RuntimeError('RAM inspection failed')
        return int(status.available_physical)
    data=Path('/proc/meminfo').read_text()
    return int(next(line.split()[1] for line in data.splitlines() if line.startswith('MemAvailable:')))*1024


def choose_worker_count(requested,available,*,worker_peak_bytes=None):
    if type(requested) is not int or not 1<=requested<=2:raise ValueError('one or two worker processes required')
    profile=PLAN['memory_profile']
    peak=profile['admission_worker_peak_bytes'] if worker_peak_bytes is None else worker_peak_bytes
    if type(peak) is not int or peak<1 or type(available) is not int or available<0:
        raise ValueError('positive measured worker peak and available RAM required')
    per_worker=peak+profile['per_worker_growth_allowance_bytes']
    for workers in range(requested,0,-1):
        if available>=profile['system_reserve_bytes']+workers*per_worker:return workers
    raise RuntimeError('insufficient available RAM for one profiled worker and system reserve')


def load_selection(path):
    path=Path(path).resolve();manifest=_verified_manifest(path.parent)
    if manifest['gate']['status']!='verified':raise ValueError('verified experiment required')
    if {a['path']:a['sha256'] for a in manifest['artifacts']}.get(path.name)!=_digest(path):
        raise ValueError('selection manifest changed')
    result=_read(path)
    if result['schema_version']!='github-advisor-model-selection/1.0' or result['test_evaluated'] is not False:
        raise ValueError('unexpected selection schema or test scope')
    for algorithm,candidate in result['candidates'].items():
        files=_native_files(candidate['path'])
        if (algorithm!=candidate['algorithm'] or files!=candidate['checkpoint_files']
                or record_hash(files)!=candidate['checkpoint_sha256']
                or record_hash(candidate['native_contract'])!=candidate['native_contract_sha256']
                or record_hash(candidate['frozen_encoder'])!=candidate['frozen_encoder_sha256']):
            raise ValueError('selected model or feature contract changed')
        _verify_artifacts(candidate['frozen_encoder']['artifacts'])
    return result


def run_retraining(bundle_path,output,*,max_workers=2):
    if type(max_workers) is not int or not 1<=max_workers<=2:raise ValueError('one or two worker processes required')
    bundle_path=Path(bundle_path).resolve();bundle=load_bundle(bundle_path)
    available=available_ram_bytes()
    requested_workers=max_workers;max_workers=choose_worker_count(max_workers,available)
    code=freeze_code();bundle_sha=_digest(bundle_path)
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    run=Path(output).resolve()/'github_retraining_runs'/run_id;run.mkdir(parents=True,exist_ok=False)
    inputs={'plan':copy.deepcopy(PLAN),'bundle_path':str(bundle_path),'bundle_sha256':bundle_sha,
        'bundle_manifest_sha256':_digest(bundle_path.parent/'manifest.json'),
        'model_contract':bundle['model_contract'],'frozen_encoder':bundle['frozen_encoder'],
        'source_artifacts':bundle['source_artifacts'],'student_split_sha256':bundle['student_split_sha256'],
        'comparators':bundle['comparators'],'code_sha256':code,'available_ram_bytes':available,
        'max_workers_requested':requested_workers,'max_workers':max_workers,
        'versions':{name:importlib.metadata.version(name) for name in ('torch','numpy','gymnasium','stable-baselines3','sb3-contrib')}}
    _write(run/'input_manifest.json',inputs)
    print(f'GITHUB_RETRAINING_RUN={run}',flush=True)
    jobs=[{'bundle_path':str(bundle_path),'bundle_sha256':bundle_sha,'run':str(run),'algorithm':a,
           'seed':s,'evaluation_steps':PLAN['evaluation_steps'],'milestones':PLAN['milestones'],'code_sha256':code}
          for s in PLAN['seeds'] for a in PLAN['algorithms']]
    _write(run/'progress.json',{'status':'starting','run_id':run_id,'completed_jobs':0,'total_jobs':len(jobs)})
    results=[]
    try:
        # Separate processes isolate global policy RNG and cap simultaneous native models.
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            pending={pool.submit(_train_job,job) for job in jobs}
            while pending:
                done,pending=wait(pending,timeout=10,return_when=FIRST_COMPLETED)
                for future in done:
                    if future.exception() is not None:
                        for queued in pending:queued.cancel()
                    results.append(future.result())
                progress=[_read(p) for p in sorted((run/'jobs').glob('*/progress.json'))]
                _write(run/'progress.json',{'status':'running','run_id':run_id,'completed_jobs':len(results),'total_jobs':10,'jobs':progress})
        rows=[r for result in results for r in result['rows']]
        baselines=[r for result in results if result['algorithm']=='ppo' for r in result['baselines']]
        rows.sort(key=lambda r:(r['algorithm'],r['total_steps'],r['seed']))
        curves=[];paired={};candidates={}
        for algorithm in PLAN['algorithms']:
            base=_stage(rows,algorithm,16384);paired[algorithm]={}
            for steps in PLAN['evaluation_steps']:
                stage=_stage(rows,algorithm,steps)
                metric_names=('objective','mean_compatibility','min_compatibility','p10_compatibility',
                              'coverage','constraint_violations','invalid_action_count','elapsed_seconds')
                reports=[r for result in results for r in result['training'] if r['algorithm']==algorithm and r['total_steps']==steps]
                losses=[_stats([v['loss'] if isinstance(v,dict) else v for v in r['losses']])['mean'] for r in reports]
                curves.append({'algorithm':algorithm,'total_steps':steps,
                    'validation':{k:_stats([_metric(r,k) for r in stage]) for k in metric_names},
                    'mean_logged_loss_per_seed':_stats(losses),'loss_scope':'Optimizer-specific window loss; not accuracy.'})
                paired[algorithm][str(steps)]={'vs16384':paired_statistics(base,stage),
                    'vs_hungarian':paired_statistics([r for r in baselines if r['algorithm']=='hungarian'],stage)}
            chosen=select_checkpoint(rows,algorithm);files=_native_files(chosen['checkpoint_path'])
            candidates[algorithm]={'algorithm':algorithm,'path':chosen['checkpoint_path'],
                'checkpoint_steps':chosen['total_steps'],'seed':42,'checkpoint_files':files,'checkpoint_sha256':record_hash(files),
                'native_contract':bundle['model_contract'],'native_contract_sha256':record_hash(bundle['model_contract']),
                'frozen_encoder':bundle['frozen_encoder'],'frozen_encoder_sha256':record_hash(bundle['frozen_encoder']),
                'validation_stats':chosen['validation_stats'],'selection_rule':PLAN['selection'],
                'fallback':'hungarian','production_promoted':False}
        _write(run/'validation_results.json',rows);_write(run/'baseline_results.json',baselines)
        _write(run/'reports/learning_curve.json',curves);_write(run/'reports/paired_validation_summary.json',paired)
        _write(run/'reports/plateau.json',{a:plateau_diagnostic(rows,a) for a in PLAN['algorithms']})
        _write(run/'selection_manifest.json',{'schema_version':'github-advisor-model-selection/1.0',
            'scope':'from_scratch_enriched_advisor_features','run_id':run_id,'candidates':candidates,
            'test_evaluated':False,'production_promoted':False,'comparators':bundle['comparators'],
            'limitations':['New advisor data and initialization differ from old runs; cross-dataset deltas are confounded.',
                'Five training seeds on fixed validation29 do not measure new-cohort generalization.',
                'Compatibility/objective are not academic accuracy. Plateau is not mathematical convergence.',
                'Descriptive95%t intervals are not adjusted for repeated checkpoint selection.',
                'Phase5 already examined test30; this run does not evaluate it.']})
        verify_code(code);load_bundle(bundle_path)
        if _digest(bundle_path)!=bundle_sha:raise ValueError('frozen training bundle changed')
        checks={'ten_jobs_complete':len(results)==10,'dense_curve_complete':len(rows)==160,
            'all_allocations_valid':all(_allocation_safe(r) for r in rows),
            'all_checkpoints_reloaded':sum(r['reload_checked'] for r in rows)==70,
            'all_weights_changed':all(r['weights_changed'] for r in rows),
            'train_holdout_isolated':True,'test_not_evaluated':True,'code_and_sources_unchanged':True}
        gate={'status':'verified' if all(checks.values()) else 'failed','run_id':run_id,'run_dir':str(run),
            'scope':'from_scratch_enriched_advisor_features','checks':checks,'completed_seeds':PLAN['seeds'],
            'test_evaluated':False,'models_promoted':False,'mathematical_convergence_proven':False}
        _write(run/'reports/retraining_gate.json',gate)
        _write(run/'progress.json',{'status':'completed','run_id':run_id,'completed_jobs':10,'total_jobs':10})
        artifacts=[{'path':p.relative_to(run).as_posix(),'sha256':_digest(p)} for p in sorted(run.rglob('*')) if p.is_file()]
        _write(run/'manifest.json',{'gate':gate,'artifacts':artifacts})
        if gate['status']=='verified':load_selection(run/'selection_manifest.json')
        return gate
    except Exception as error:
        _write(run/'failure.json',{'error_type':type(error).__name__,'error':str(error)})
        _write(run/'progress.json',{'status':'failed','run_id':run_id,'error_type':type(error).__name__})
        raise
