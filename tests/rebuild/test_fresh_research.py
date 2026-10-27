"""The research runner must preserve a rejected lineage, never restart later terms."""
import importlib
import json


def test_rejected_round_blocks_later_terms_without_reinitializing(tmp_path, monkeypatch):
    m = importlib.import_module('scripts.run_fresh_research')
    source = tmp_path / 'data_rebuild/nested_rl_20261028/run'
    source.mkdir(parents=True)
    calls = []

    def prepare(root, out, *, version, **kwargs):
        out.mkdir(parents=True)
        payload = {'train': [], 'validation': {'version': version}, 'contract': {},
                   'round': {'algorithm': 'ppo', 'semester_id': version, 'round_id': version + '-r1'}}
        (out / 'suite.json').write_text(json.dumps(payload), encoding='utf-8')
        (out / 'encoder.json').write_text('{}', encoding='utf-8')
        return {'status': 'ready_research_only'}

    def train(problems, validation, contract, spec, out, **kwargs):
        calls.append((validation['version'], kwargs['parent']))
        return {'decision': 'accepted' if len(calls) == 1 else 'rejected', 'production_promoted': False}

    monkeypatch.setattr(m, 'prepare_suite', prepare)
    monkeypatch.setattr(m, 'decode_problem', lambda value: value)
    monkeypatch.setattr(m, 'run_round', train)
    result = m.run_research(source, source / 'research', mode='retrospective_document_proxy', algorithms=['ppo'])
    assert [v for v, _ in calls] == ['V1', 'V2']
    assert calls[0][1] is None and calls[1][1] is not None
    assert result['rounds']['ppo']['V3']['status'] == 'blocked_parent_not_accepted'
    assert result['inner_feedback_rounds']['status'] == 'unavailable'
    assert not result['test_evaluated']


def test_missing_bootstrap_encoder_blocks_dependent_suites(tmp_path, monkeypatch):
    m = importlib.import_module('scripts.run_fresh_research')
    root = tmp_path / 'data_rebuild/nested_rl_20261028/run'
    root.mkdir(parents=True)
    calls = []
    def blocked(root, out, *, version, **kwargs):
        calls.append(version)
        return {'status': 'blocked_data_insufficient'}
    monkeypatch.setattr(m, 'prepare_suite', blocked)
    result = m.run_research(root, root / 'research', mode='retrospective_document_proxy', algorithms=['ppo'])
    assert calls == ['V1']
    assert result['suites']['V2']['status'] == 'blocked_bootstrap_unavailable'
