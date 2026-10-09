import runpy
from pathlib import Path
import yaml
import jsonschema

ROOT = Path(__file__).resolve().parents[1]


def test_image_profile_uses_requested_backend_and_precision():
    document = yaml.safe_load((ROOT / 'profiles/orchestration/qwen-image-flux-dual.yaml').read_text())
    jsonschema.validate(document, yaml.safe_load((ROOT / 'schemas/orchestration-profile.schema.yaml').read_text()))
    images = document['orchestration_profile']['allocations'][:2]
    assert [x['engine'] for x in images] == ['stable-diffusion.cpp'] * 2
    assert [x['target_hardware'] for x in images] == ['cuda:1', 'cuda:0']
    assert all(x['image_settings']['dtype'] == 'bfloat16' for x in images)


def test_native_artifact_arguments_do_not_requantize_or_redownload():
    args = runpy.run_path(str(ROOT / 'scripts/inference/activate-image-profile.py'))['model_arguments']
    qwen, flux = args('qwen'), args('flux')
    assert qwen[qwen.index('--diffusion-model') + 1].endswith('UC-BF16.gguf')
    assert flux[flux.index('--diffusion-model') + 1].endswith('flux2-dev-native-bf16.safetensors')
    assert flux[flux.index('--llm') + 1].endswith('flux2-text-encoder-native-bf16.safetensors')
    assert '--type' not in qwen + flux


def _load_sync_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location('openclaw_sync_test', ROOT / 'scripts/inference/sync-openclaw-models.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_image_generation_wired_when_image_profile_active():
    module = _load_sync_module()
    images = module._image_allocations(ROOT / 'profiles/orchestration/qwen-image-flux-dual.yaml')
    assert [a['port'] for a in images] == [8188, 8189]
    cfg = {}
    changes = []
    module._ensure_image_generation(cfg, images, changes)
    assert cfg['models']['providers']['openai'] == {'baseUrl': 'http://127.0.0.1:8188/v1', 'apiKey': 'sovereign-local'}
    assert cfg['agents']['defaults']['mediaModels']['image'] == {'primary': 'openai/gpt-image-2', 'timeoutMs': 120000}
    assert cfg['browser']['ssrfPolicy']['dangerouslyAllowPrivateNetwork'] is True
    assert changes


def test_image_generation_removed_but_operator_openai_preserved():
    module = _load_sync_module()
    cfg = {
        'models': {'providers': {'openai': {'baseUrl': 'http://127.0.0.1:8188/v1', 'apiKey': 'sovereign-local'}}},
        'agents': {'defaults': {'mediaModels': {'image': {'primary': 'openai/gpt-image-2', 'timeoutMs': 120000}}}},
    }
    changes = []
    module._ensure_image_generation(cfg, [], changes)
    assert 'openai' not in cfg['models']['providers']
    assert 'image' not in cfg['agents']['defaults']['mediaModels']
    # Operator-owned openai config is never removed and never rewritten.
    cfg = {'models': {'providers': {'openai': {'baseUrl': 'https://api.openai.com/v1', 'apiKey': 'sk-real'}}}}
    changes = []
    module._ensure_image_generation(cfg, [], changes)
    assert cfg['models']['providers']['openai'] == {'baseUrl': 'https://api.openai.com/v1', 'apiKey': 'sk-real'}
    assert changes == []


def test_active_llm_profile_sync_is_dry_run_clean(tmp_path):
    import json
    import subprocess
    config = tmp_path / 'openclaw.json'
    config.write_text(json.dumps({'models': {'providers': {'sovereign': {'models': [{'id': 'gpu-oracle'}]}}}}))
    result = subprocess.run([
        __import__('sys').executable, str(ROOT / 'scripts/inference/sync-openclaw-models.py'),
        '--profile', 'qwen38-flash-next-256k', '--config', str(config), '--dry-run',
    ], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0


def _load_companion_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location('image_companion_test', ROOT / 'scripts/inference/activate-image-companion.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_companion_profiles_pair_one_llm_with_one_image_runtime():
    schema = yaml.safe_load((ROOT / 'schemas/orchestration-profile.schema.yaml').read_text())
    for name in ('codernext-image-companion', 'qwen38-27b-image-companion'):
        document = yaml.safe_load((ROOT / f'profiles/orchestration/{name}.yaml').read_text())
        jsonschema.validate(document, schema)
        profile = document['orchestration_profile']
        assert profile['runtime_handler'] == 'image-companion'
        allocations = profile['allocations']
        tiers = [a['tier'] for a in allocations if a.get('active', True)]
        assert tiers == ['oracle', 'image', 'embed', 'rerank'], name
        assert allocations[0]['engine'] == 'llama.cpp' and allocations[0]['model'] in ('Qwen3-Coder-Next-Q6_K', 'Qwen3.8-27B-Q4_K_M')
        assert allocations[1]['engine'] == 'stable-diffusion.cpp'
        assert allocations[1]['target_hardware'] == 'cuda:1'


def test_companion_activator_refuses_without_installed_runtime(tmp_path, monkeypatch):
    import pytest
    module = _load_companion_module()
    monkeypatch.setattr(module, 'SD_SERVER', tmp_path / 'sd-server')
    monkeypatch.setattr(module, 'MARKER', tmp_path / 'active-runtime-profile')
    module.MARKER.write_text('qwen38-flash-next-256k\n')
    monkeypatch.setattr(module.os, 'geteuid', lambda: 0)
    calls = []
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **k: calls.append(a))
    with pytest.raises(RuntimeError, match='runtime installation is missing'):
        module.main([str(ROOT / 'profiles/orchestration/codernext-image-companion.yaml')])
    assert calls == []


def test_osctl_dispatches_the_companion_handler():
    source = (ROOT / 'scripts/sovereign-osctl').read_text()
    assert '"${runtime_handler}" = image-companion' in source
    assert 'activate-image-companion.py' in source


def test_missing_backend_does_not_stop_running_models(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location('image_activation_test', ROOT / 'scripts/inference/activate-image-profile.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    monkeypatch.setattr(module.os, 'geteuid', lambda: 0)
    calls = []
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **k: calls.append(a))
    import pytest
    with pytest.raises(RuntimeError, match='runtime installation is missing'):
        module.main()
    assert calls == []


def test_profile_switch_stops_transient_image_units_individually():
    """Regression (operator report 2026-10-09): the image units are TRANSIENT
    (systemd-run --collect); one combined `systemctl stop A B` returned
    non-zero for the unit already gone ("Unit ... not loaded") and aborted the
    whole profile switch while any image profile was live. Each unit must be
    stopped on its own: already-gone is success, still-active must refuse."""
    source = (ROOT / 'scripts/sovereign-osctl').read_text()
    assert 'systemctl stop sovereign-image-qwen.service sovereign-image-flux.service' not in source
    assert 'for image_unit in sovereign-image-qwen.service sovereign-image-flux.service' in source
    assert 'refusing to compete for GPU memory' in source


def test_activation_modal_sees_image_tiers():
    """The D-21 activation modal must show declared `tier: image` allocations —
    sd-server is not a gateway route, so grid cells never carry them and the
    stage-3 strip read "1/2 tiers live" with the image row missing entirely.
    The grid payload exposes image_state (declared allocations + live port
    probes, file-driven); the modal renders + counts imageTiers."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'lm_orch_api_image_state', ROOT / 'scripts/operator/lm-orchestration-api.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    single = module._image_allocations(
        ROOT / 'profiles/orchestration/codernext-image-companion.yaml')
    assert single == [{'model': 'Qwen-Image-2.1-Uncensored-BF16', 'port': 8188}]
    dual = module._image_allocations(ROOT / 'profiles/orchestration/qwen-image-flux-dual.yaml')
    assert {a['port'] for a in dual} == {8188, 8189}
    assert {a['model'] for a in dual} == {'Qwen-Image-2.1-Uncensored-BF16', 'FLUX.2-dev'}
    state = module.image_state_view()
    assert set(state) >= {'profile', 'images'}
    api_src = (ROOT / 'scripts/operator/lm-orchestration-api.py').read_text()
    assert '"image_state": image_state_view()' in api_src
    panel = (ROOT / 'webapp/d-21-lm-orchestration/index.html').read_text()
    assert 'imageTiers' in panel and 'image_state' in panel
