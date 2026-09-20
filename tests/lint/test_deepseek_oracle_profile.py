from pathlib import Path
import runpy
import yaml

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    return yaml.safe_load((ROOT / 'profiles/orchestration' / (name + '.yaml')).read_text())['orchestration_profile']


def test_deepseek_is_additive_and_preserves_other_cards():
    profile = load('deepseek-70b-qwen-dual')
    original = load('dual-agent-autocomplete')
    allocs = {a['tier']: a for a in profile['allocations']}
    old = {a['tier']: a for a in original['allocations']}
    for tier in ('logic', 'embed', 'rerank'):
        assert {k:v for k,v in allocs[tier].items() if k!='agent_id'} == {k:v for k,v in old[tier].items() if k!='agent_id'}
    oracle = allocs['oracle']
    assert oracle['engine'] == 'llama.cpp'
    assert oracle['model_path'].endswith('/DeepSeek-R1-Distill-Llama-70B-Q4_K_M.gguf')
    assert oracle['max_model_len'] == 131072
    assert oracle['max_output_tokens'] == 8192
    assert '--parallel 1' in oracle['extra_args']
    assert '--split-mode none' in oracle['extra_args']
    assert original['allocations'][1]['engine'] == 'vllm'


def test_openclaw_catalog_advertises_deepseek_and_matching_limits():
    mod = runpy.run_path(str(ROOT / 'scripts/inference/sync-openclaw-models.py'))
    allocation = next(a for a in load('deepseek-70b-qwen-dual')['allocations'] if a['tier']=='oracle')
    entry = mod['_derive_entry'](allocation, mod['_catalog_index'](), 'gpu-oracle')
    assert entry['contextWindow'] == 131072
    assert entry['maxTokens'] == 8192
    assert entry['reasoning'] is True
    assert 'DeepSeek' in entry['name']
    cfg, changes = {}, []
    mod['_ensure_profile_primary_model'](cfg, 'deepseek-70b-qwen-dual', changes)
    assert cfg['agents']['defaults']['model']['primary'] == 'sovereign/gpu-oracle'


def test_gguf_launcher_does_not_fall_through_to_vllm():
    source = (ROOT / 'scripts/inference/start-oracle-core.sh').read_text()
    start = source.index('if [ "$(runtime_profile_get_tier_field oracle engine)" = "llama.cpp" ]')
    end = source.index('# As with Logic', start)
    branch = source[start:end]
    assert 'oracle model_path' in branch
    assert 'os.execv(argv[0], argv)' in branch
    assert 'CUDA_VISIBLE_DEVICES' in branch
    assert "'-ngl', '999'" in branch
    assert "shlex.split" in branch
    assert 'SOVEREIGN_OS_DRY_RUN' in branch


def test_profile_activation_does_not_overwrite_installed_reconciler():
    source = (ROOT / 'scripts/sovereign-osctl').read_text()
    helper = source.split('  _sync_runtime_activation_contract() {', 1)[1].split('\n  case "${sub}" in', 1)[0]
    assert '/usr/local/lib/sovereign-os/gpu-route-apply.sh' not in helper
