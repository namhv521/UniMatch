import sys
from types import SimpleNamespace

import pytest


def test_launcher_requires_explicit_artifacts_before_creating_token(tmp_path):
    from scripts.serve_github_unimatch_local import main
    token = tmp_path/'access.token'
    with pytest.raises(SystemExit) as error:
        main(['--token-file', str(token)])
    assert error.value.code == 2 and not token.exists()


def test_launcher_reuses_private_token_and_binds_only_loopback(tmp_path, monkeypatch, capsys):
    from scripts import serve_github_unimatch_local as launcher
    monkeypatch.setattr(launcher, 'ROOT', tmp_path)
    token = tmp_path/'data_rebuild/runtime/access.token'
    token.parent.mkdir(parents=True)
    token.write_text('private-fixture-token-that-is-never-printed')
    calls = []
    app = object()
    monkeypatch.setattr(launcher, 'make_app', lambda **kw: calls.append(kw) or app)
    monkeypatch.setitem(sys.modules, 'uvicorn', SimpleNamespace(run=lambda *a, **kw: calls.append((a, kw))))
    launcher.main(['--bundle', str(tmp_path/'bundle.json'), '--selection', str(tmp_path/'selection.json'),
                   '--runtime', str(tmp_path/'data_rebuild/runtime/github'), '--token-file', str(token), '--port', '8768'])
    assert calls[0]['token'] == token.read_text()
    assert calls[0]['bundle_path'] == (tmp_path/'bundle.json').resolve()
    assert calls[0]['selection_path'] == (tmp_path/'selection.json').resolve()
    assert calls[1] == ((app,), {'host':'127.0.0.1', 'port':8768, 'access_log':False})
    assert token.read_text() not in capsys.readouterr().out


@pytest.mark.parametrize('unsafe_argument', ['token', 'runtime'])
def test_launcher_rejects_public_paths_before_creating_any_token(tmp_path, monkeypatch, unsafe_argument):
    from scripts import serve_github_unimatch_local as launcher
    monkeypatch.setattr(launcher, 'ROOT', tmp_path)
    monkeypatch.setattr(launcher, 'make_app', lambda **kw: object())
    monkeypatch.setitem(sys.modules, 'uvicorn', SimpleNamespace(run=lambda *a, **kw: None))
    token = tmp_path/('frontend/access.token' if unsafe_argument == 'token' else 'data_rebuild/runtime/access.token')
    runtime = tmp_path/('frontend' if unsafe_argument == 'runtime' else 'data_rebuild/runtime/github')
    with pytest.raises(ValueError, match='private_local_path_required'):
        launcher.main(['--bundle', str(tmp_path/'bundle.json'), '--selection', str(tmp_path/'selection.json'),
                       '--runtime', str(runtime), '--token-file', str(token)])
    assert not token.exists()


def test_private_path_rejects_traversal(tmp_path, monkeypatch):
    from scripts import serve_github_unimatch_local as launcher
    monkeypatch.setattr(launcher, 'ROOT', tmp_path)
    with pytest.raises(ValueError, match='private_local_path_required'):
        launcher.private_path(tmp_path/'data_rebuild/runtime/../../frontend/access.token')


def test_private_path_rejects_redirected_private_root(tmp_path, monkeypatch):
    from scripts import serve_github_unimatch_local as launcher
    monkeypatch.setattr(launcher, 'ROOT', tmp_path)
    public = tmp_path/'frontend'
    public.mkdir()
    private = tmp_path/'data_rebuild/runtime'
    private.parent.mkdir()
    try:
        private.symlink_to(public, target_is_directory=True)
    except OSError:
        pytest.skip('Directory symlinks unavailable to this Windows account')
    with pytest.raises(ValueError, match='private_local_path_required'):
        launcher.private_path(private/'access.token')
