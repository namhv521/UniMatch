"""Technical fixtures for approval-bound feature publication; no real labels."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from test_phase4_experiments import advisory_fixture


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def accepted_fixture(tmp_path):
    from src.features.rebuild_experiments import run_experiments
    output, packet, proposals = advisory_fixture(tmp_path)
    package = tmp_path/'owner-package'; package.mkdir()
    raw = package/'combined_proposals.jsonl'
    raw.write_text(''.join(json.dumps(row)+'\n' for row in proposals), encoding='utf-8')
    gate = run_experiments(output, labels_file=raw, review_packet=packet)
    run = Path(gate['run_dir'])
    calibration = json.loads((run/'reports/hybrid_calibration.json').read_text())
    assert calibration['weights']
    write(package/'feature_selection_proposal.json', {
        'status':'proposal_pending_owner_approval', 'selected_proposal':'E4_calibrated_proposal',
        'source_snapshot':gate['phase3_snapshot'], 'e4_calibrated_weights':calibration['weights'],
        'expected_full_matrix_shape':[6,2], 'matrix_generated':False, 'owner_approval':None})
    write(package/'crosscheck_audit.json', {'primary_pairs':len(proposals), 'disputed_pairs':[]})
    write(package/'manifest.json', {'run_id':run.name, 'run_manifest_sha256':digest(run/'manifest.json'),
        'packet_manifest_sha256':digest(packet/'packet_manifest.json'),
        'artifacts':[{'path':p.name,'sha256':digest(p)} for p in sorted(package.iterdir()) if p.is_file()]})
    receipt = tmp_path/'receipt.json'
    write(receipt, {'kind':'phase4_owner_acceptance','decision':'approve',
        'authorization_source':'explicit_user_message','reviewer':'owner:technical-fixture',
        'recorded_at':'2026-10-22T07:00:00+00:00',
        'approval_message':{'question':'Approve this technical fixture report?', 'answer':'Approve; retain unknown grades.'},
        'owner_package_dir':str(package), 'owner_package_manifest_sha256':digest(package/'manifest.json'),
        'approved_experiment_run_id':run.name, 'approved_run_manifest_sha256':digest(run/'manifest.json'),
        'approved_feature_selection_sha256':digest(package/'feature_selection_proposal.json'),
        'selected_variant':'E4_calibrated_proposal','hybrid_weights':calibration['weights'],
        'keep_uncertain':True,'uncertain_count':0})
    return output, package, receipt, run


def test_owner_acceptance_freezes_full_matrix_without_refitting_and_replays_idempotently(tmp_path, monkeypatch):
    from src.features.rebuild_acceptance import finalize_features, load_approved_features
    from src.features.rebuild_features import FeaturePipeline
    output, package, receipt, experiment = accepted_fixture(tmp_path)
    def forbidden_fit(*args, **kwargs):
        raise AssertionError('approved transformer must never refit')
    monkeypatch.setattr(FeaturePipeline, 'fit', forbidden_fit)
    gate = finalize_features(output, receipt)
    assert gate['status']=='verified' and gate['can_start_phase5'] is True
    assert gate['full_matrix_shape']==[6,2] and gate['uncertain_labels']==0
    assert finalize_features(output, receipt)==gate
    data = load_approved_features(output)
    assert data['scores'].shape==(6,2) and data['available'].dtype==np.bool_
    assert data['index']['student_ids']==sorted(data['index']['student_ids'])
    final = Path(gate['run_dir'])
    assert digest(final/'transformer/idf.npz')==digest(experiment/'transformer_calibrated_proposal/idf.npz')
    assert digest(final/'transformer/transformer.json')==digest(experiment/'transformer_calibrated_proposal/transformer.json')
    assert json.loads((final/'reports/acceptance_checks.json').read_text())['validation_slice_matches_approved_scores'] is True
    assert json.loads((final/'feature_contract.json').read_text())['test_policy']['independent_test_metrics_computed'] is False


@pytest.mark.parametrize('field,value', [('owner_package_manifest_sha256','f'*64),
    ('hybrid_weights',{'E1':1,'E2':0,'E3':0}), ('keep_uncertain',False), ('decision','pending')])
def test_acceptance_rejects_stale_or_unapproved_receipt(tmp_path, field, value):
    from src.features.rebuild_acceptance import finalize_features
    output, _, receipt, _ = accepted_fixture(tmp_path)
    data = json.loads(receipt.read_text()); data[field]=value; write(receipt,data)
    with pytest.raises(ValueError):
        finalize_features(output, receipt)
    assert json.loads((output/'reports/phase4_gate.json').read_text())['status']=='blocked'


def test_changed_owner_artifact_and_published_matrix_are_rejected(tmp_path):
    from src.features.rebuild_acceptance import finalize_features, load_approved_features
    output, package, receipt, _ = accepted_fixture(tmp_path)
    artifact = package/'crosscheck_audit.json'; original=artifact.read_bytes(); artifact.write_bytes(b'{}')
    with pytest.raises(ValueError, match='artifact_hash_mismatch'):
        finalize_features(output, receipt)
    artifact.write_bytes(original)
    gate = finalize_features(output, receipt)
    matrix = Path(gate['run_dir'])/'features/compatibility_matrix.npy'
    values=np.load(matrix); values[0,0]=.123; np.save(matrix,values,allow_pickle=False)
    with pytest.raises(ValueError, match='hash_mismatch'):
        load_approved_features(output)


def test_ratification_retains_unknown_and_original_reviewer():
    from src.features.rebuild_acceptance import ratify_labels
    rows=[{'grade':'uncertain','reviewer':'agent:fixture','attribution':'agent_advisory'}]
    accepted=ratify_labels(rows, reviewer='owner:fixture', receipt_sha256='a'*64)
    assert accepted[0]['grade']=='uncertain' and rows[0]['attribution']=='agent_advisory'
    assert accepted[0]['proposal_reviewer']=='agent:fixture'
    assert accepted[0]['review_kind']=='owner_ratified_agent_report'


def reseal_final_run(output, run):
    """Simulate a mistaken integrity-only repair; authority must still govern."""
    gate=json.loads((run/'reports/phase4_gate.json').read_text())
    gate['feature_contract_sha256']=digest(run/'feature_contract.json')
    write(run/'reports/phase4_gate.json',gate); write(output/'reports/phase4_gate.json',gate)
    manifest=json.loads((run/'manifest.json').read_text()); manifest['gate']=gate
    for row in manifest['artifacts']:
        row['sha256']=digest(run/row['path'])
    write(run/'manifest.json',manifest)


@pytest.mark.parametrize('change',['weights','matrix'])
def test_resealed_output_cannot_override_approved_weights_or_transform(tmp_path, change):
    from src.features.rebuild_acceptance import finalize_features, load_approved_features
    output, _, receipt, _=accepted_fixture(tmp_path)
    run=Path(finalize_features(output,receipt)['run_dir'])
    contract=json.loads((run/'feature_contract.json').read_text())
    if change=='weights':
        contract['hybrid_weights']={'E1':1,'E2':0,'E3':0}
    else:
        path=run/'features/compatibility_matrix.npy'; values=np.load(path)
        values[0,0]=.123; np.save(path,values,allow_pickle=False)
        contract['matrix_sha256']=digest(path)
    write(run/'feature_contract.json',contract); reseal_final_run(output,run)
    with pytest.raises(ValueError,match='approved_feature_selection_binding_mismatch|approved_matrix_transform_mismatch'):
        load_approved_features(output)
