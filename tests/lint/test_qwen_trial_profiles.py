from pathlib import Path
import runpy
import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_trials_are_resolvable_by_control_rail_and_preserve_worker():
    rail = runpy.run_path(str(ROOT / 'scripts/operator/_action_exec.py'))
    control = rail['load_registry']()['orchestration-profile']
    baseline = yaml.safe_load((ROOT / 'profiles/orchestration/deepseek-70b-qwen-dual.yaml').read_text())['orchestration_profile']
    worker = [a for a in baseline['allocations'] if a['tier'] in ('embed', 'rerank')]
    for name in ('qwen38-dual-trial', 'qwen-next-dual-trial'):
        argv, error = rail['resolve_argv'](control, {'verb': name})
        assert error is None
        assert argv[-1] == name
        profile = yaml.safe_load((ROOT / 'profiles/orchestration' / (name + '.yaml')).read_text())['orchestration_profile']
        assert [a for a in profile['allocations'] if a['tier'] in ('embed', 'rerank')] == worker
        assert profile['readiness'] == 'candidate'
        for allocation in profile['allocations']:
            if allocation['tier'] in ('logic', 'oracle'):
                expected = ({'logic': 98304, 'oracle': 131072}
                            if name == 'qwen38-dual-trial' else {'logic': 65536, 'oracle': 65536})
                assert allocation['max_model_len'] == expected[allocation['tier']]
                assert '--parallel 1' in allocation['extra_args']
