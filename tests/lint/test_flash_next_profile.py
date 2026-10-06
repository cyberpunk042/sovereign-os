from pathlib import Path
import runpy

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[2]
MODEL = 'Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S'
PROFILE = 'qwen38-flash-next-dual'


def profile(name):
    return yaml.safe_load((ROOT / 'profiles/orchestration' / f'{name}.yaml').read_text())['orchestration_profile']


def test_flash_profile_preserves_logic_and_4090_and_resolves_control():
    baseline, candidate = profile('qwen38-dual-agent-256k'), profile(PROFILE)
    assert candidate['readiness'] == 'candidate'
    assert [a for a in candidate['allocations'] if a['tier'] != 'oracle'] == [
        a for a in baseline['allocations'] if a['tier'] != 'oracle']
    oracle = next(a for a in candidate['allocations'] if a['tier'] == 'oracle')
    assert oracle['model'] == MODEL
    assert oracle['max_model_len'] == 65536
    assert candidate['context_budget']['initial_tokens']['cuda:0'] == 65536
    for flag in ('--load-mode mmap', '--lazy-mode on', '--split-mode none', '--parallel 1', '--cache-type-k f16'):
        assert flag in oracle['extra_args']
    rail = runpy.run_path(str(ROOT / 'scripts/operator/_action_exec.py'))
    argv, error = rail['resolve_argv'](rail['load_registry']()['orchestration-profile'], {'verb': PROFILE})
    assert error is None and argv[-1] == PROFILE


def test_download_selects_only_both_iq3s_shards():
    entries = yaml.safe_load((ROOT / 'models/catalog.yaml').read_text())['catalog']['models']
    model = next(m for m in entries if m['id'] == MODEL)
    assert model['status'] == 'operator-must-confirm'
    assert model['hf_repo_id'] == 'ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF'
    assert model['hf_include_patterns'] == [
        f'IQ3_S/{MODEL}-00001-of-00002.gguf', f'IQ3_S/{MODEL}-00002-of-00002.gguf', 'README.md']
    oracle = next(a for a in profile(PROFILE)['allocations'] if a['tier'] == 'oracle')
    assert oracle['model_path'] == f'/mnt/vault/models/{MODEL}/' + model['hf_include_patterns'][0]
    schema = yaml.safe_load((ROOT / 'schemas/model-catalog.schema.yaml').read_text())
    jsonschema.validate({'schema_version': '1.0.0', 'catalog': {'version': 'qualification', 'models': [model]}}, schema)
    schema = yaml.safe_load((ROOT / 'schemas/orchestration-profile.schema.yaml').read_text())
    jsonschema.validate({'schema_version': '1.0.0', 'orchestration_profile': profile(PROFILE)}, schema)


def test_openclaw_metadata_and_bounded_reasoning_for_fresh_config():
    sync = runpy.run_path(str(ROOT / 'scripts/inference/sync-openclaw-models.py'))
    cfg, changes = {}, []
    allocs = {a['tier']: a for a in profile(PROFILE)['allocations']}
    sync['_ensure_qwen38_sampling'](cfg, allocs, changes)
    sync['_ensure_local_agent_completion'](cfg, allocs, changes)
    sync['_ensure_profile_primary_model'](cfg, PROFILE, changes)
    defaults = cfg['agents']['defaults']
    assert defaults['model']['primary'] == 'sovereign/gpu-oracle'
    body = defaults['models']['sovereign/gpu-oracle']['params']['extra_body']
    assert body['reasoning_budget_tokens'] == 2048
    assert body['temperature'] == 1 and body['top_k'] == 20
    before = len(changes)
    sync['_ensure_qwen38_sampling'](cfg, allocs, changes)
    sync['_ensure_local_agent_completion'](cfg, allocs, changes)
    sync['_ensure_profile_primary_model'](cfg, PROFILE, changes)
    assert len(changes) == before


def test_extended_profile_only_changes_oracle_context():
    baseline, extended = profile(PROFILE), profile('qwen38-flash-next-256k')
    for before, after in zip(baseline['allocations'], extended['allocations']):
        if before['tier'] == 'oracle':
            assert after['max_model_len'] == 262144
            assert {k:v for k,v in before.items() if k != 'max_model_len'} == {k:v for k,v in after.items() if k != 'max_model_len'}
        else:
            assert before == after
    assert extended['context_budget']['initial_tokens'] == {'cuda:0':262144,'cuda:1':131072,'cuda:2':8192}
    rail = runpy.run_path(str(ROOT / 'scripts/operator/_action_exec.py'))
    argv, error = rail['resolve_argv'](rail['load_registry']()['orchestration-profile'], {'verb':'qwen38-flash-next-256k'})
    assert error is None
    assert argv[-1] == 'qwen38-flash-next-256k'
