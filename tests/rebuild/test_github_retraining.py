import copy
import random
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pytest
import torch

from src.evaluation.github_retraining import (
    PLAN, validate_bundle, epsilon_window, preserve_rng, plateau_diagnostic,
    select_checkpoint, _train_job, _digest, _write, freeze_code, verify_code,
)
from src.data_pipeline.review_decisions import record_hash
from src.domain.rebuild_matching import AllocationProblem
from src.environment.rebuild_env import MatchingEnv
from src.evaluation.rebuild_benchmark import problem_payload


def bound_bundle(path,payload):
    _write(path,payload)
    _write(path.parent/'manifest.json',{'gate':{'status':'verified'},
        'artifacts':[{'path':path.name,'sha256':_digest(path)}]})


def bundle(tmp_path):
    def problem(ids, split):
        return AllocationProblem(scores=np.tile([.9, .7], (len(ids), 1)),
            available=np.ones((len(ids), 2), bool), student_ids=tuple(ids),
            advisor_ids=('a', 'b'), capacities=np.array([len(ids)//2, len(ids)-len(ids)//2]),
            eligible=np.ones((len(ids), 2), bool), present=np.ones(2, bool),
            student_features=np.ones((len(ids), 1), np.float32),
            student_feature_known=np.ones((len(ids), 1), bool),
            metadata={'split':split, 'feature_contract_sha256':'a'*64,
                      'taxonomy_feature_order_sha256':'b'*64})
    train=[problem([f't{i}' for i in range(j*45, (j+1)*45)], 'train') for j in range(3)]
    validation=problem([f'v{i}' for i in range(29)], 'validation')
    test=problem([f'x{i}' for i in range(30)], 'test')
    source=tmp_path/'source.json';source.write_text('{}', encoding='utf-8')
    split=tmp_path/'splits.json'
    _write(split,{'assignments':{s:p.metadata['split'] for p in [*train,validation,test] for s in p.student_ids}})
    env=MatchingEnv(train, shuffle_students=True)
    return {'schema_version':'github-advisor-training-bundle/1.0',
        'training_problems':[problem_payload(p) for p in train],
        'evaluation_problems':{'validation':problem_payload(validation), 'test':problem_payload(test)},
        'model_contract':{'training_student_ids':[s for p in train for s in p.student_ids],
            'state_contract':env.state_contract, 'reward_weights':env.reward_weights,
            'feature_contract_sha256':'a'*64, 'taxonomy_feature_order_sha256':'b'*64,
            'training_problem_sha256':[record_hash(problem_payload(p)) for p in train]},
        'frozen_encoder':{'artifacts':[{'path':str(source.resolve()), 'sha256':_digest(source)}]},
        'source_artifacts':[{'path':str(source.resolve()), 'sha256':_digest(source)},
                            {'path':str(split.resolve()), 'sha256':_digest(split)}],
        'student_split_sha256':_digest(split), 'comparators':{'old_scope':'different advisor features'}}


def result(seed, steps, objective, **kwargs):
    return {'algorithm':'dqn', 'seed':seed, 'total_steps':steps,'case':'validation',
        'checkpoint_path':f'/private/{steps}/{seed}', 'reload_trace_equal':True,
        'trace_replay_verified':True,'reload_checked':True,
        'weights_changed':True, 'invalid_action_count':0, 'elapsed_seconds':.01,
        'metrics':{'objective':objective, 'mean_compatibility':objective/29,
            'min_compatibility':.1, 'p10_compatibility':.2,
            'coverage':1., 'constraint_violations':0}, **kwargs}


def test_plan_predeclared_dense_eval_and_no_test_tuning():
    assert PLAN['seeds']==[42,43,44,45,46]
    assert PLAN['milestones']==[16384,24576,32768,49152,65536,98304,131072]
    assert PLAN['evaluation_steps']==list(range(8192,131073,8192))
    assert PLAN['initialization']=='from_scratch' and PLAN['test_evaluated'] is False


def test_bundle_hashes_membership_state_and_feature_semantics_are_bound(tmp_path):
    b=bundle(tmp_path); s=validate_bundle(b)
    assert [len(p.student_ids) for p in s['train']]==[45,45,45]
    for mutate in ('overlap','duplicate','feature','layout','source','split','encoder'):
        bad=copy.deepcopy(b)
        if mutate=='overlap':bad['evaluation_problems']['test']['student_ids'][0]='t0'
        if mutate=='duplicate':bad['model_contract']['training_student_ids'].append('t0')
        if mutate=='feature':bad['training_problems'][1]['metadata']['feature_contract_sha256']='f'*64
        if mutate=='layout':bad['model_contract']['state_contract']['dimension']=999
        if mutate=='source':bad['source_artifacts'][0]['sha256']='0'*64
        if mutate=='split':bad['training_problems'][0]['metadata']['split']='test'
        if mutate=='encoder':bad['frozen_encoder']['artifacts'][0]['sha256']='0'*64
        with pytest.raises(ValueError):validate_bundle(bad)


def test_global_epsilon_schedule_has_no_chunk_reset_or_endpoint_gap():
    assert epsilon_window(0,8192)==pytest.approx((1.,1.-.95*8191/16383))
    assert epsilon_window(8192,8192)==pytest.approx((1.-.95*8192/16383,.05))
    assert epsilon_window(16384,8192)==pytest.approx((.05,.05))
    with pytest.raises(ValueError):epsilon_window(-1,8192)


def test_declared_split_file_and_problem_hashes_cannot_be_self_claims(tmp_path):
    original=bundle(tmp_path)
    for mutation in ('missing_split','wrong_assignments','problem_hash'):
        bad=copy.deepcopy(original)
        if mutation=='missing_split':bad['student_split_sha256']='d'*64
        if mutation=='wrong_assignments':
            path=tmp_path/'bad-splits.json'
            _write(path,{'assignments':{'t0':'test'}})
            bad['source_artifacts'].append({'path':str(path.resolve()),'sha256':_digest(path)})
            bad['student_split_sha256']=_digest(path)
        if mutation=='problem_hash':bad['model_contract']['training_problem_sha256'][0]='d'*64
        with pytest.raises(ValueError):validate_bundle(bad)


def test_reload_rng_guard_restores_python_numpy_and_torch_even_on_error():
    random.seed(9);np.random.seed(9);torch.manual_seed(9)
    expected=(random.random(), np.random.random(), torch.rand(1).item())
    random.seed(9);np.random.seed(9);torch.manual_seed(9)
    with pytest.raises(RuntimeError):
        with preserve_rng():
            random.seed(42);np.random.seed(42);torch.manual_seed(42)
            raise RuntimeError('technical fixture')
    assert (random.random(),np.random.random(),torch.rand(1).item())==expected


def test_plateau_requires_three_complete_safe_evaluations_and_is_not_convergence():
    rows=[result(s,step,5.+j*.01) for j,step in enumerate((8192,16384,24576)) for s in PLAN['seeds']]
    report=plateau_diagnostic(rows,'dqn')
    assert report['plateau_in_tested_budget'] is True
    assert report['mathematical_convergence_proven'] is False
    assert report['last_interval_paired']['mean_compatibility']['n']==5
    assert report['compatibility_slope_per8192']['mean']==pytest.approx(.01/29)
    assert plateau_diagnostic(rows[:-1],'dqn')['plateau_in_tested_budget'] is False
    rows[-1]['metrics']['objective']=10;rows[-1]['metrics']['mean_compatibility']=10/29
    assert plateau_diagnostic(rows,'dqn')['plateau_in_tested_budget'] is False


def test_selection_uses_all_five_seeds_no_cherry_picking_and_no_unsafe_stage():
    data=[result(s,step,5+(step==24576)) for step in PLAN['milestones'] for s in PLAN['seeds']]
    chosen=select_checkpoint(data,'dqn')
    assert chosen['total_steps']==24576 and chosen['seed']==42
    next(r for r in data if r['total_steps']==24576 and r['seed']==42)['metrics']['objective']=4
    assert select_checkpoint(data,'dqn')['total_steps']==16384
    data.pop()
    with pytest.raises(ValueError):select_checkpoint(data,'dqn')


def test_selection_rejects_heldout_rows_even_when_their_scores_look_better():
    data=[result(s,step,5,case='validation') for step in PLAN['milestones'] for s in PLAN['seeds']]
    data[-1]['case']='test'
    with pytest.raises(ValueError):select_checkpoint(data,'dqn')


def test_code_freeze_detects_modified_file(tmp_path):
    path=tmp_path/'owned.py';path.write_text('x=1\n')
    hashes=freeze_code([path]);verify_code(hashes)
    path.write_text('x=2\n')
    with pytest.raises(ValueError):verify_code(hashes)


def test_future_admission_requires_verified_manifest_bound_bundle_and_original_sources(tmp_path,monkeypatch):
    from src.evaluation.github_retraining import load_bundle
    from src.data_pipeline import github_advisors
    b=bundle(tmp_path);path=tmp_path/'bundle.json';_write(path,b)
    with pytest.raises(FileNotFoundError):load_bundle(path)
    bound_bundle(path,b);assert load_bundle(path)==b
    manifest=path.parent/'manifest.json'
    _write(manifest,{'gate':{'status':'failed'},'artifacts':[{'path':path.name,'sha256':_digest(path)}]})
    with pytest.raises(ValueError):load_bundle(path)
    _write(manifest,{'gate':{'status':'verified'},'artifacts':[]})
    with pytest.raises(ValueError):load_bundle(path)
    bound_bundle(path,b);path.write_text(path.read_text()+' ')
    with pytest.raises(ValueError):load_bundle(path)
    b['serving']={'github_source_run':str(tmp_path/'source-capture')}
    bound_bundle(path,b)
    calls=[]
    def reject_source_inventory(run):
        calls.append(run);raise ValueError('technical source inventory changed')
    monkeypatch.setattr(github_advisors,'verify_run',reject_source_inventory)
    with pytest.raises(ValueError,match='inventory'):load_bundle(path)
    assert calls==[b['serving']['github_source_run']]


def test_future_worker_and_cli_reject_unmanifested_bundle_before_training(tmp_path,monkeypatch):
    from scripts import train_github_advisor_models as cli
    b=bundle(tmp_path);path=tmp_path/'bundle.json';_write(path,b)
    spec={'bundle_path':str(path),'bundle_sha256':_digest(path),'run':str(tmp_path/'run'),
        'algorithm':'dqn','seed':42,'evaluation_steps':[256],'milestones':[256],
        'code_sha256':freeze_code([Path(__file__)])}
    with pytest.raises(FileNotFoundError):_train_job(spec)
    assert not (tmp_path/'run').exists()
    monkeypatch.setattr('sys.argv',['train','--bundle',str(path),'--output',str(tmp_path/'out')])
    with pytest.raises(FileNotFoundError):cli.main()
    assert not (tmp_path/'out').exists()


def test_cli_reports_failed_quality_gate_as_nonzero_exit(tmp_path,monkeypatch):
    from scripts import train_github_advisor_models as cli
    monkeypatch.setattr(cli,'run_retraining',lambda *args,**kwargs:{'status':'failed'})
    monkeypatch.setattr('sys.argv',['train','--bundle',str(tmp_path/'bundle.json'),
                                   '--output',str(tmp_path/'out'),'--execute'])
    with pytest.raises(SystemExit) as error:cli.main()
    assert error.value.code==2


@pytest.mark.parametrize('algorithm',['ppo','dqn'])
def test_actual_native_training_saves_safe_reloads_and_never_evaluates_test(tmp_path,algorithm):
    torch.set_num_threads(1)
    b=bundle(tmp_path);bundle_path=tmp_path/'bundle.json';bound_bundle(bundle_path,b)
    run=tmp_path/'run';run.mkdir()
    spec={'bundle_path':str(bundle_path),'bundle_sha256':_digest(bundle_path),'run':str(run),
        'algorithm':algorithm,'seed':42,'evaluation_steps':[256,512], 'milestones':[512],
        'code_sha256':freeze_code([Path(__file__)])}
    output=_train_job(spec)
    assert [r['total_steps'] for r in output['rows']]==[256,512]
    assert output['rows'][0]['reload_checked'] is False
    assert output['rows'][0]['reload_trace_equal'] is None
    assert output['rows'][1]['reload_checked'] and output['rows'][1]['reload_trace_equal']
    assert all(r['weights_changed'] for r in output['rows'])
    assert all(r['metrics']['coverage']==1 and r['invalid_action_count']==0 for r in output['rows'])
    assert output['test_evaluated'] is False
    assert len(output['training'])==2
    assert all(r['training_available_student_count']==135 for r in output['training'])
    assert all(r['metrics']['coverage']==1 for r in output['baselines'])


def test_memory_admission_uses_measured_peak_and_bounds_concurrency():
    from src.evaluation.github_retraining import choose_worker_count
    mib=1024**2
    assert choose_worker_count(2,1800*mib,worker_peak_bytes=640*mib)==1
    assert choose_worker_count(2,2400*mib,worker_peak_bytes=640*mib)==2
    assert choose_worker_count(1,2400*mib,worker_peak_bytes=640*mib)==1
    with pytest.raises(RuntimeError):choose_worker_count(2,1000*mib,worker_peak_bytes=640*mib)


@pytest.mark.parametrize('algorithm',['ppo','dqn'])
def test_spawned_native_worker_records_actual_peak_working_set(tmp_path,algorithm):
    b=bundle(tmp_path);path=tmp_path/'bundle.json';bound_bundle(path,b)
    for payload in [*b['training_problems'],*b['evaluation_problems'].values()]:
        for key in ('scores','available','eligible','preferences','preference_known'):
            payload[key]=np.pad(np.asarray(payload[key]),((0,0),(0,33))).tolist()
        for key in ('capacities','present'):
            payload[key]=np.pad(np.asarray(payload[key]),(0,33)).tolist()
        for key in ('student_features','student_feature_known'):
            payload[key]=np.tile(np.asarray(payload[key]),(1,78)).tolist()
        payload['advisor_ids']=['a','b',*[f'advisor{i}' for i in range(33)]]
    from src.evaluation.github_retraining import _problem
    env=MatchingEnv([_problem(p) for p in b['training_problems']],shuffle_students=True)
    assert env.observation_space.shape==(472,) and env.action_space.n==35
    b['model_contract']['state_contract']=env.state_contract
    b['model_contract']['training_problem_sha256']=[record_hash(p) for p in b['training_problems']]
    bound_bundle(path,b)
    run=tmp_path/'spawn-run';run.mkdir()
    spec={'bundle_path':str(path),'bundle_sha256':_digest(path),'run':str(run),
        'algorithm':algorithm,'seed':42,'evaluation_steps':[256,512],'milestones':[512],
        'code_sha256':freeze_code([Path(__file__)])}
    with ProcessPoolExecutor(max_workers=1) as pool:
        output=pool.submit(_train_job,spec).result(timeout=120)
    assert output['peak_working_set_bytes']>0
    print('MEASURED_NATIVE512_'+algorithm.upper()+'_WORKER_PEAK_BYTES='+str(output['peak_working_set_bytes']))
