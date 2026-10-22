"""Publish an approved feature matrix without refitting or changing agent labels.

The receipt is an operator record of an observed explicit owner message. Local
hashes bind that authorization to artifacts; they are not a digital signature.
"""
import hashlib
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from src.data_pipeline.reconcile import ROOT, _digest, _read_bound_phase
from src.data_pipeline.review_decisions import record_hash
from src.evaluation.rebuild_diagnostics import rank_matrix, summarize_matrix
from src.evaluation.rebuild_ranking import ranking_metrics, validate_pair_labels
from src.evaluation.rebuild_review import map_advisory_labels
from .rebuild_experiments import _load_snapshot
from .rebuild_features import FeaturePipeline


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def _write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def _lines(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def _verified_manifest(directory, expected_sha256=None):
    directory = Path(directory).resolve()
    path = directory/'manifest.json'
    if expected_sha256 is not None and _digest(path) != expected_sha256:
        raise ValueError('approval_manifest_hash_mismatch')
    manifest = _read(path)
    seen = set()
    for entry in manifest['artifacts']:
        name = entry['path']
        target = (directory/name).resolve()
        if (not isinstance(name, str) or Path(name).is_absolute()
                or not target.is_relative_to(directory) or name in seen):
            raise ValueError('invalid_artifact_path')
        seen.add(name)
        if _digest(target) != entry['sha256']:
            raise ValueError('approval_artifact_hash_mismatch')
    return manifest


def ratify_labels(labels, *, reviewer, receipt_sha256):
    """Overlay ratification after caller verifies authority; retain raw judgments."""
    return [{**row, 'proposal_reviewer':row['reviewer'], 'reviewer':reviewer,
             'attribution':'owner_ratified', 'review_kind':'owner_ratified_agent_report',
             'approval_evidence_sha256':receipt_sha256} for row in labels]


def _approved_inputs(output, authority):
    receipt_bytes = Path(authority).read_bytes()
    receipt = json.loads(receipt_bytes.decode('utf-8-sig'))
    if (receipt.get('kind') != 'phase4_owner_acceptance' or receipt.get('decision') != 'approve'
            or receipt.get('authorization_source') != 'explicit_user_message'
            or not str(receipt.get('reviewer','')).startswith('owner:')
            or receipt.get('keep_uncertain') is not True
            or not all(str(receipt.get('approval_message',{}).get(k,'')).strip() for k in ('question','answer'))):
        raise ValueError('explicit_owner_acceptance_required')
    if datetime.fromisoformat(receipt['recorded_at'].replace('Z','+00:00')).tzinfo is None:
        raise ValueError('receipt_timezone_required')
    package = Path(receipt['owner_package_dir']).resolve()
    package_manifest = _verified_manifest(package, receipt['owner_package_manifest_sha256'])
    run_id = receipt['approved_experiment_run_id']
    if not run_id or Path(run_id).name != run_id or package_manifest['run_id'] != run_id:
        raise ValueError('invalid_approved_experiment')
    experiment = output/'phase4_runs'/run_id
    expected_run_sha = receipt['approved_run_manifest_sha256']
    if package_manifest['run_manifest_sha256'] != expected_run_sha:
        raise ValueError('approved_experiment_binding_mismatch')
    experiment_manifest = _verified_manifest(experiment, expected_run_sha)
    proposal_path = package/'feature_selection_proposal.json'
    if _digest(proposal_path) != receipt['approved_feature_selection_sha256']:
        raise ValueError('approved_feature_selection_hash_mismatch')
    proposal = _read(proposal_path)
    weights = receipt['hybrid_weights']
    if (receipt['selected_variant'] != 'E4_calibrated_proposal'
            or proposal['selected_proposal'] != receipt['selected_variant']
            or weights != proposal['e4_calibrated_weights']
            or weights != _read(experiment/'reports/hybrid_calibration.json')['weights']):
        raise ValueError('approved_weights_or_variant_mismatch')
    students, advisors, snapshot = _load_snapshot(output)
    if (snapshot != proposal['source_snapshot'] or snapshot != experiment_manifest['gate']['phase3_snapshot']
            or proposal['expected_full_matrix_shape'] != [len(students),len(advisors)]):
        raise ValueError('approved_snapshot_or_dimensions_mismatch')
    if any(_digest(ROOT/name) != sha for name,sha in experiment_manifest['gate']['code_sha256'].items()):
        raise ValueError('approved_experiment_code_changed')
    packet = experiment/'review'
    if _digest(packet/'packet_manifest.json') != package_manifest['packet_manifest_sha256']:
        raise ValueError('approved_review_packet_mismatch')
    raw = package/'combined_proposals.jsonl'
    if _digest(raw) != _digest(experiment/'review/agent_proposals.jsonl'):
        raise ValueError('approved_proposals_mismatch')
    labels = map_advisory_labels(packet, _lines(raw))
    if labels != _lines(experiment/'review/labels.jsonl'):
        raise ValueError('approved_label_mapping_mismatch')
    uncertain = sum(row['grade']=='uncertain' for row in labels)
    if type(receipt.get('uncertain_count')) is not int or receipt['uncertain_count'] != uncertain:
        raise ValueError('approved_uncertain_count_mismatch')
    split = _read(experiment/'splits.json')
    if (set(split['assignments']) != {r['student_id'] for r in students}
            or any(split['assignments'][row['student_id']] != 'validation' for row in labels)):
        raise ValueError('approval_split_mismatch')
    return receipt_bytes, receipt, package, experiment, students, advisors, snapshot, labels, split


def finalize_features(output, authority):
    output = Path(output).resolve()
    inputs = _approved_inputs(output, authority)
    receipt_bytes, receipt, package, experiment, students, advisors, snapshot, labels, split = inputs
    receipt_sha = hashlib.sha256(receipt_bytes).hexdigest()
    alias = output/'reports/phase4_gate.json'
    if alias.exists():
        previous = _read(alias)
        if previous.get('status')=='verified' and previous.get('authority_receipt_sha256')==receipt_sha:
            return load_approved_features(output)['gate']
    source_code = {str(Path(__file__).relative_to(ROOT)):_digest(Path(__file__))}
    selected_path = experiment/'transformer_calibrated_proposal'
    identities = sorted({str(r[k]) for r in students+advisors
                         for k in ('student_id','student_name','advisor_id','advisor_name') if r.get(k)})
    pipeline = FeaturePipeline.load(selected_path, known_identities=identities)
    if pipeline.weights != receipt['hybrid_weights'] or pipeline.preference_weight != 0:
        raise ValueError('selected_transformer_contract_mismatch')
    # Selection is frozen by approval before transforming the complete snapshot.
    # The 30 heldout rows get scores for the required full matrix, never labels
    # or a test metric, and never enter fitting/calibration.
    result = pipeline.transform_score(students, advisors)
    student_ids, advisor_ids = [r['student_id'] for r in students], [r['advisor_id'] for r in advisors]
    scores, available = result['scores']['E4'], result['available']['E4']
    rank_matrix(scores,available,student_ids,advisor_ids)
    original_index = _read(experiment/'validation_scores/index.json')
    positions = [student_ids.index(key) for key in original_index['student_ids']]
    matches = (advisor_ids==original_index['advisor_ids']
        and np.array_equal(scores[positions],np.load(experiment/'validation_scores/E4_calibrated_proposal.npy',allow_pickle=False))
        and np.array_equal(available[positions],np.load(experiment/'validation_scores/E4_calibrated_proposal_available.npy',allow_pickle=False)))
    if not matches:
        raise ValueError('approved_validation_score_mismatch')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    run = output/'phase4_runs'/run_id
    for folder in ('features','review','reports'):
        (run/folder).mkdir(parents=True,exist_ok=False)
    shutil.copytree(selected_path,run/'transformer')
    (run/'review/owner_receipt.json').write_bytes(receipt_bytes)
    for name in ('combined_proposals.jsonl','crosscheck_audit.json'):
        shutil.copyfile(package/name,run/'review'/name)
    _write(run/'approved_experiment_binding.json', {'run_id':experiment.name,
        'manifest_sha256':_digest(experiment/'manifest.json'),
        'owner_package_manifest_sha256':_digest(package/'manifest.json')})
    _write(run/'splits.json',split)
    accepted = ratify_labels(labels,reviewer=receipt['reviewer'],receipt_sha256=receipt_sha)
    validate_pair_labels(accepted, student_hashes={r['student_id']:record_hash(r) for r in students},
                         advisor_hashes={r['advisor_id']:record_hash(r) for r in advisors}, snapshot_sha256=snapshot['snapshot_sha256'])
    (run/'review/owner_labels.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in accepted),encoding='utf-8')
    metrics = ranking_metrics(rank_matrix(scores[positions],available[positions],original_index['student_ids'],advisor_ids),accepted)
    _write(run/'reports/owner_ratified_ranking_metrics.json', {'review_kind':'owner_ratified_agent_report',
        'scope':'Validation only; not independently human-authored grades or heldout test performance.', 'metrics':metrics})
    np.save(run/'features/compatibility_matrix.npy',scores,allow_pickle=False)
    np.save(run/'features/compatibility_available.npy',available,allow_pickle=False)
    index = {'student_ids':student_ids,'advisor_ids':advisor_ids,'shape':list(scores.shape),'dtype':str(scores.dtype),
             'snapshot_sha256':snapshot['snapshot_sha256'],'ordering':'canonical_id_ascending'}
    _write(run/'features/index.json',index)
    contract = {'schema_version':'rebuild-feature-contract/1.0','status':'approved',
        'variant':receipt['selected_variant'],'hybrid_weights':pipeline.weights,'preference_weight':0,
        'snapshot':snapshot,'authority_receipt_sha256':receipt_sha,
        'approved_experiment_run_id':experiment.name,'fit_policy':'Frozen train-only vocabulary/IDF; no refit at approval.',
        'split_counts':split['metadata']['student_counts'],'splits_sha256':_digest(run/'splits.json'),
        'input_feature_manifest':_read(experiment/'feature_manifest.json'),
        'transformer_json_sha256':_digest(run/'transformer/transformer.json'),
        'transformer_idf_sha256':_digest(run/'transformer/idf.npz'),
        'matrix_sha256':_digest(run/'features/compatibility_matrix.npy'),
        'availability_sha256':_digest(run/'features/compatibility_available.npy'),'index_sha256':_digest(run/'features/index.json'),
        'shape':list(scores.shape),'dtype':str(scores.dtype),
        'missing_policy':'Unobserved scores require false availability mask; storage zero is not observed relevance.',
        'roster_scope':'Approved profile catalog only; participation/eligibility/capacity not inferred.',
        'label_policy':{'attribution':'owner_ratified_agent_report','uncertain_retained':receipt['uncertain_count']},
        'test_policy':{'included_in_full_snapshot_transform':True,'used_for_selection':False,
                       'used_for_fitting_or_calibration':False,'independent_test_metrics_computed':False},
        'limitations':['Non-temporal grouped split; no future-semester quality claim.',
                      'No approved abstracts/publication summaries or confirmed preferences.',
                      'Source confidence is evidence quality, not proficiency or supervision outcomes.']}
    _write(run/'feature_contract.json',contract)
    replay = FeaturePipeline.load(run/'transformer',known_identities=identities).transform_score(students,advisors)
    parity = np.array_equal(scores,replay['scores']['E4']) and np.array_equal(available,replay['available']['E4'])
    checks = {'validation_slice_matches_approved_scores':matches,'full_transformer_roundtrip_parity':parity,
              'matrix':summarize_matrix(scores,available),'uncertain_labels_retained':receipt['uncertain_count'],
              'train_only_idf_unchanged':_digest(run/'transformer/idf.npz')==_digest(selected_path/'idf.npz'),
              'independent_test_metrics_computed':False}
    if not parity or not checks['train_only_idf_unchanged']:
        raise ValueError('approved_transformer_roundtrip_mismatch')
    # Re-read pinned inputs after materializing output, before publishing the gate.
    again = _approved_inputs(output, authority)
    if (again[0]!=receipt_bytes or again[6]!=snapshot
            or any(_digest(ROOT/name)!=sha for name,sha in source_code.items())):
        raise ValueError('approval_inputs_or_code_changed_during_run')
    _write(run/'reports/acceptance_checks.json',checks)
    gate = {'phase':4,'status':'verified','can_start_phase5':True,'run_id':run_id,'run_dir':str(run),
        'blocking_reasons':[],'phase3_snapshot':snapshot,'approved_experiment_run_id':experiment.name,
        'authority_receipt_sha256':receipt_sha,'owner_package_manifest_sha256':receipt['owner_package_manifest_sha256'],
        'selected_variant':receipt['selected_variant'],'hybrid_weights':pipeline.weights,
        'full_matrix_status':'verified','full_matrix_shape':list(scores.shape),
        'feature_contract_sha256':_digest(run/'feature_contract.json'), 'split_counts':split['metadata']['student_counts'],
        'uncertain_labels':receipt['uncertain_count'],'owner_ratified_ranking_metrics':{k:v for k,v in metrics.items() if k!='per_query'},
        'independent_test_metrics':None,'production_deployed':False,
        'code_sha256':{**_read(experiment/'manifest.json')['gate']['code_sha256'],**source_code},
        'created_at':datetime.now(timezone.utc).isoformat()}
    _write(run/'reports/phase4_gate.json',gate)
    _write(run/'manifest.json',{'gate':gate,'artifacts':[{'path':p.relative_to(run).as_posix(),'sha256':_digest(p)}
             for p in sorted(run.rglob('*')) if p.is_file()]})
    # Last disk readback catches incomplete writes before the shared alias moves.
    _verified_manifest(run)
    _check_matrix(run,contract,students,advisors)
    temporary = alias.with_name('phase4_gate.'+uuid.uuid4().hex+'.tmp')
    _write(temporary,gate); temporary.replace(alias)
    return gate


def _check_matrix(run,contract,students,advisors):
    index = _read(run/'features/index.json')
    scores = np.load(run/'features/compatibility_matrix.npy',allow_pickle=False)
    available = np.load(run/'features/compatibility_available.npy',allow_pickle=False)
    if (index['student_ids']!=[r['student_id'] for r in students]
            or index['advisor_ids']!=[r['advisor_id'] for r in advisors]
            or list(scores.shape)!=contract['shape'] or index['shape']!=contract['shape']
            or scores.dtype!=np.float64 or available.dtype!=np.bool_ or available.shape!=scores.shape
            or index['dtype']!=contract['dtype'] or index['snapshot_sha256']!=contract['snapshot']['snapshot_sha256']):
        raise ValueError('approved_matrix_index_or_dtype_mismatch')
    rank_matrix(scores,available,index['student_ids'],index['advisor_ids'])
    if (scores[~available]!=0).any():
        raise ValueError('unavailable_scores_must_use_storage_zero')
    for name,key in [('compatibility_matrix.npy','matrix_sha256'),('compatibility_available.npy','availability_sha256'),('index.json','index_sha256')]:
        if _digest(run/'features'/name)!=contract[key]:
            raise ValueError('approved_matrix_hash_mismatch')
    return {'scores':scores,'available':available,'index':index,'contract':contract}


def load_approved_features(output):
    """Phase 5 must read this verified binding rather than an old matrix path."""
    output=Path(output).resolve()
    gate,path = _read_bound_phase(output,4,'feature_contract.json')
    run=path.parent; _verified_manifest(run)
    contract=_read(path)
    students,advisors,snapshot=_load_snapshot(output)
    if (contract['status']!='approved' or contract['snapshot']!=snapshot
            or gate['feature_contract_sha256']!=_digest(path)
            or _digest(run/'review/owner_receipt.json')!=gate['authority_receipt_sha256']
            or contract['authority_receipt_sha256']!=gate['authority_receipt_sha256']):
        raise ValueError('approved_feature_contract_binding_mismatch')
    inputs=_approved_inputs(output,run/'review/owner_receipt.json')
    _,receipt,_,experiment,_,_,_,labels,split=inputs
    if (contract['variant']!=receipt['selected_variant'] or contract['hybrid_weights']!=receipt['hybrid_weights']
            or gate['hybrid_weights']!=receipt['hybrid_weights'] or contract['preference_weight']!=0
            or _read(run/'splits.json')!=split
            or _digest(run/'transformer/transformer.json')!=contract['transformer_json_sha256']
            or _digest(run/'transformer/idf.npz')!=contract['transformer_idf_sha256']
            or _digest(run/'transformer/transformer.json')!=_digest(experiment/'transformer_calibrated_proposal/transformer.json')
            or _digest(run/'transformer/idf.npz')!=_digest(experiment/'transformer_calibrated_proposal/idf.npz')):
        raise ValueError('approved_feature_selection_binding_mismatch')
    expected=ratify_labels(labels,reviewer=receipt['reviewer'],receipt_sha256=gate['authority_receipt_sha256'])
    if _lines(run/'review/owner_labels.jsonl')!=expected:
        raise ValueError('owner_ratified_labels_changed')
    if any(_digest(ROOT/name)!=sha for name,sha in gate['code_sha256'].items()):
        raise ValueError('approved_feature_code_changed')
    result=_check_matrix(run,contract,students,advisors)
    identities=sorted({str(r[k]) for r in students+advisors
                       for k in ('student_id','student_name','advisor_id','advisor_name') if r.get(k)})
    replay=FeaturePipeline.load(run/'transformer',known_identities=identities).transform_score(students,advisors)
    if not (np.array_equal(result['scores'],replay['scores']['E4']) and np.array_equal(result['available'],replay['available']['E4'])):
        raise ValueError('approved_matrix_transform_mismatch')
    return {**result,'gate':gate}
