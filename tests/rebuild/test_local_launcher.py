import pytest


def test_local_token_is_reused_and_never_replaced_silently(tmp_path):
    from scripts.serve_unimatch_local import load_local_token
    path=tmp_path/'runtime/access.token'
    first=load_local_token(path)
    assert len(first)>=32 and load_local_token(path)==first
    path.write_text('short')
    with pytest.raises(ValueError,match='token'):load_local_token(path)


def test_latest_selection_path_cannot_escape_local_convergence_store(tmp_path):
    import json
    from scripts.serve_unimatch_local import local_selection_path
    assert local_selection_path(tmp_path) is None
    reports=tmp_path/'reports';reports.mkdir()
    gate=reports/'convergence_gate.json'
    gate.write_text(json.dumps({'status':'verified','run_id':'one','run_dir':str(tmp_path/'convergence_runs/one')}))
    assert local_selection_path(tmp_path)==tmp_path/'convergence_runs/one/selection_manifest.json'
    gate.write_text(json.dumps({'status':'verified','run_id':'one','run_dir':str(tmp_path/'unrelated/one')}))
    with pytest.raises(ValueError):local_selection_path(tmp_path)


def test_assistant_entrypoint_requires_verified_local_phase8_gate(tmp_path):
    import json
    from scripts.serve_unimatch_local import local_app_entrypoint
    assert local_app_entrypoint(tmp_path)=='backend.app.rebuild_api:app'
    reports=tmp_path/'reports';reports.mkdir()
    p=reports/'phase8_local_gate.json'
    p.write_text(json.dumps({'phase':8,'status':'partial','scope':'owner_authorized_local_release'}))
    assert local_app_entrypoint(tmp_path)=='backend.app.rebuild_api:app'
    p.write_text(json.dumps({'phase':8,'status':'verified','scope':'owner_authorized_local_release'}))
    assert local_app_entrypoint(tmp_path)=='backend.app.rebuild_assistant_api:app'
