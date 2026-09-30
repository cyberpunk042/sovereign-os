from pathlib import Path
import runpy
import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_extended_context_profile_keeps_rollback_and_worker():
    def load(name):
        return yaml.safe_load((ROOT / 'profiles/orchestration' / (name + '.yaml')).read_text())['orchestration_profile']
    original = load('qwen38-dual-agent')
    extended = load('qwen38-dual-agent-long')
    for before, after in zip(original['allocations'], extended['allocations']):
        assert {k:v for k,v in before.items() if k != 'max_model_len'} == {k:v for k,v in after.items() if k != 'max_model_len'}
        if before['tier'] in ('logic', 'oracle'):
            assert before['max_model_len'] == {'logic':98304,'oracle':131072}[before['tier']]
            assert after['max_model_len'] == {'logic':131072,'oracle':196608}[after['tier']]
    rail = runpy.run_path(str(ROOT / 'scripts/operator/_action_exec.py'))
    assert rail['resolve_argv'](rail['load_registry']()['orchestration-profile'],
                                {'verb':'qwen38-dual-agent-long'})[1] is None
    maximum = load('qwen38-dual-agent-256k')
    assert len(maximum['allocations']) == len(extended['allocations'])
    for before, after in zip(extended['allocations'], maximum['allocations']):
        if before['tier'] == 'oracle':
            assert after['max_model_len'] == 262144
            assert {k:v for k,v in before.items() if k != 'max_model_len'} == {k:v for k,v in after.items() if k != 'max_model_len'}
        else:
            assert before == after
    assert maximum['context_budget']['initial_tokens']['cuda:0'] == 262144
    assert maximum['context_budget']['initial_tokens']['cuda:1'] == 131072
    assert rail['resolve_argv'](rail['load_registry']()['orchestration-profile'],
                                {'verb':'qwen38-dual-agent-256k'})[1] is None


def test_trials_are_resolvable_by_control_rail_and_preserve_worker():
    rail = runpy.run_path(str(ROOT / 'scripts/operator/_action_exec.py'))
    control = rail['load_registry']()['orchestration-profile']
    baseline = yaml.safe_load((ROOT / 'profiles/orchestration/deepseek-70b-qwen-dual.yaml').read_text())['orchestration_profile']
    worker = [a for a in baseline['allocations'] if a['tier'] in ('embed', 'rerank')]
    for name in ('qwen38-dual-agent', 'qwen-next-dual-trial'):
        argv, error = rail['resolve_argv'](control, {'verb': name})
        assert error is None
        assert argv[-1] == name
        profile = yaml.safe_load((ROOT / 'profiles/orchestration' / (name + '.yaml')).read_text())['orchestration_profile']
        assert [a for a in profile['allocations'] if a['tier'] in ('embed', 'rerank')] == worker
        assert profile['readiness'] == ('ready' if name == 'qwen38-dual-agent' else 'candidate')
        if name == 'qwen38-dual-agent':
            assert profile['name'] == 'Qwen 3.8 Dual Agent — 96K / 128K'
            assert profile['context_budget']['initial_tokens']['cuda:1'] == 98304
            assert profile['context_budget']['initial_tokens']['cuda:0'] == 131072
        for allocation in profile['allocations']:
            if allocation['tier'] in ('logic', 'oracle'):
                expected = ({'logic': 98304, 'oracle': 131072}
                            if name == 'qwen38-dual-agent' else {'logic': 65536, 'oracle': 65536})
                assert allocation['max_model_len'] == expected[allocation['tier']]
                assert '--parallel 1' in allocation['extra_args']
