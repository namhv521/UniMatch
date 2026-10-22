"""Owner-authorized local release gates; historical phase evidence stays immutable."""
import json
from pathlib import Path

from src.data_pipeline.reconcile import _digest
from src.features.rebuild_acceptance import _verified_manifest


def verify_local_phase6(previous_run,convergence_run,authority_path):
    previous_run,convergence_run,authority_path=map(Path,(previous_run,convergence_run,authority_path))
    authority=json.loads(authority_path.read_text(encoding='utf-8'))
    requirements={'semester_verification_required':False,'local_csv_inference':True,
                  'more_steps_experiment':True,'continue_following_phases':True}
    if (authority.get('kind')!='local_release_scope_amendment'
            or authority.get('authorization_source')!='explicit_user_message'
            or not str(authority.get('reviewer','')).startswith('owner:')
            or authority.get('requirements')!=requirements
            or not str(authority.get('user_message','')).strip()):
        raise ValueError('explicit_owner_scope_amendment_required')
    previous=_verified_manifest(previous_run)
    old=previous['gate']
    technical=('idempotent_upload','offline_learning','reload_reproducible',
               'rollback_preserves_assignments','no_holdout_training')
    if (old.get('phase')!=6 or old.get('technical_implementation_verified') is not True
            or not all(old.get('checks',{}).get(key) is True for key in technical)):
        raise ValueError('prior_phase6_technical_evidence_required')
    experiment=_verified_manifest(convergence_run)
    gate=experiment['gate']
    checks=('no_train_holdout_overlap','zero_invalid_actions','zero_constraint_violations',
            'reload_exact','code_unchanged','final_test_not_reused')
    if 'checkpoint_steps' in gate:
        declared_steps=gate['checkpoint_steps']
        native_checks=('budget_completed','all_weights_changed','all_reloads_match',
                       'all_allocations_valid','train_holdout_isolated','test_not_evaluated','code_unchanged')
        safe=(all(gate.get('checks',{}).get(key) is True for key in native_checks)
              and all(gate.get(key) is True for key in checks[:-1])
              and gate.get('test_evaluated') is False)
    else:
        declared_steps=gate.get('stages')
        safe=all(gate.get('checks',{}).get(key) is True for key in checks)
    if (gate.get('status')!='verified' or gate.get('completed_seeds')!=[42,43,44,45,46]
            or gate.get('parent_steps')!=16384 or declared_steps!=[24576,32768]
            or gate.get('models_promoted') is not False
            or not safe):
        raise ValueError('completed_source_bound_convergence_experiment_required')
    return {'phase':6,'status':'verified','scope':'owner_authorized_local_non_temporal',
            'can_start_phase7':True,'historical_phase6_status':old['status'],
            'historical_phase6_manifest_sha256':_digest(previous_run/'manifest.json'),
            'convergence_manifest_sha256':_digest(convergence_run/'manifest.json'),
            'authority_sha256':_digest(authority_path),
            'checks':{**{key:True for key in technical},**{key:True for key in checks}},
            'semester_verification_required':False,'temporal_forgetting':None,
            'models_promoted':False,'production_deployed':False,
            'note':'Gate authorizes a local CSV inference release, not unseen-semester accuracy or cloud publication.'}
