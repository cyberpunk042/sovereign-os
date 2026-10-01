import runpy
from pathlib import Path

ensure = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/inference/sync-openclaw-models.py'))['_ensure_qwen38_sampling']


def test_modes_and_idempotence():
    cfg = {'agents': {'defaults': {'models': {'sovereign/gpu-logic': {'params': {'extra_body': {'chat_template_kwargs': {'enable_thinking': False}}}}}}}}
    allocs = {tier: {'model': 'Qwen3.8-27B-Q8_0'} for tier in ('logic', 'oracle')}
    changes = []
    ensure(cfg, allocs, changes)
    models = cfg['agents']['defaults']['models']
    assert models['sovereign/gpu-logic']['params']['extra_body']['temperature'] == 0.7
    assert models['sovereign/gpu-oracle']['params']['extra_body']['temperature'] == 1.0
    assert models['sovereign/gpu-oracle']['params']['extra_body']['min_p'] == 0
    ensure(cfg, allocs, [])
    assert len(changes) == 12


def test_other_models_and_operator_values_untouched():
    cfg = {'agents': {'defaults': {'models': {'sovereign/gpu-oracle': {'params': {'temperature': 0.3, 'extra_body': {'min_p': 0.1}}}}}}}
    ensure(cfg, {'oracle': {'model': 'Qwen3.8-27B-Q8_0'}}, [])
    params = cfg['agents']['defaults']['models']['sovereign/gpu-oracle']['params']
    assert 'temperature' not in params['extra_body']
    assert params['extra_body']['min_p'] == 0.1
    empty = {}
    ensure(empty, {'logic': {'model': 'Another-model'}}, [])
    assert empty == {}
