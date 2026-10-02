import importlib.util
import json
from pathlib import Path


def module():
    path = Path(__file__).resolve().parents[1] / 'scripts/warp/warp_manage.py'
    spec = importlib.util.spec_from_file_location('warp_results', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_render_publishes_unique_result(monkeypatch, tmp_path):
    mod = module()
    monkeypatch.setattr(mod, 'render_store', lambda: tmp_path)
    monkeypatch.setattr(mod, 'shaders_root', lambda: tmp_path)
    monkeypatch.setattr(mod, '_validate_scene', lambda scene: None)
    def runner(name, args, *rest):
        Path(args[args.index('--out')+1]).write_bytes(b'\x89PNG\r\n\x1a\nfixture')
        return 0
    monkeypatch.setattr(mod, '_run_runner', runner)
    assert mod.cmd_render('ai_training', False, []) == 0
    first = mod.latest_render()
    assert first['scene'] == 'ai_training'
    assert first['image_url'].startswith('data:image/png;base64,')
    assert mod.cmd_render('canyon', False, []) == 0
    assert mod.latest_render()['id'] != first['id']
    assert (tmp_path / (first['id']+'.png')).exists()
    monkeypatch.setattr(mod, '_run_runner', lambda *args: 1)
    assert mod.cmd_render('failed', False, []) == 1
    assert mod.latest_render()['scene'] == 'canyon'


def test_reader_rejects_paths_and_symlinks(monkeypatch, tmp_path):
    mod = module()
    monkeypatch.setattr(mod, 'render_store', lambda: tmp_path)
    (tmp_path/'latest.json').write_text(json.dumps({'id':'../secret'}))
    assert mod.latest_render() is None
    identity = 'a'*32
    (tmp_path/'latest.json').write_text(json.dumps({'id':identity}))
    (tmp_path/(identity+'.png')).symlink_to(tmp_path/'secret')
    assert mod.latest_render() is None
