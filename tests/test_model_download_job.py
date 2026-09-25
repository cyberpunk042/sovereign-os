import importlib.util
import json
import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('download_job', ROOT / 'scripts/models/download-job.py')
job = importlib.util.module_from_spec(spec)
spec.loader.exec_module(job)


@pytest.mark.parametrize('value', ['../x', '/tmp/x', 'x;id', 'x y', '--worker', 'no-such-model'])
def test_invalid_catalog_id_rejected(value):
    with pytest.raises(ValueError):
        job.entry(value)


def test_selected_quant_only():
    row = {'hf_include_patterns': ['wanted.gguf', 'README.md']}
    files = [SimpleNamespace(rfilename=n, size=3, lfs={'sha256': 'a'*64})
             for n in ['wanted.gguf', 'other.gguf', 'README.md']]
    assert [f['path'] for f in job.select_files(row, files)] == ['wanted.gguf', 'README.md']


def test_missing_or_unsafe_weights_rejected():
    with pytest.raises(ValueError):
        job.select_files({'hf_include_patterns': ['*.gguf']}, [])
    with pytest.raises(ValueError):
        job.select_files({'hf_include_patterns': ['*.gguf']},
                         [SimpleNamespace(rfilename='../x.gguf')])


def test_incomplete_shard_selection_rejected():
    with pytest.raises(ValueError):
        job.select_files({'hf_include_patterns': ['*.gguf']}, [SimpleNamespace(
            rfilename='model-00001-of-00002.gguf', size=3, lfs={'sha256':'a'*64})])


def test_empty_directory_and_partial_not_ready(tmp_path):
    target = tmp_path / 'model'
    target.mkdir()
    row = {'hf_include_patterns': ['weights.gguf']}
    (target / 'weights.gguf.incomplete').write_bytes(b'abc')
    assert not job.readiness('model', row, tmp_path, tmp_path)[0]


def test_verified_job_requires_artifacts(tmp_path):
    target = tmp_path / 'model'
    target.mkdir()
    state = {'status': 'complete', 'files': [{'path': 'weights.gguf', 'size': 3}]}
    (tmp_path / 'model.json').write_text(json.dumps(state))
    assert not job.readiness('model', {}, tmp_path, tmp_path)[0]
    (target / 'weights.gguf').write_bytes(b'abc')
    assert job.readiness('model', {}, tmp_path, tmp_path)[0]
    state['status'] = 'failed'
    (tmp_path / 'model.json').write_text(json.dumps(state))
    assert not job.readiness('model', {}, tmp_path, tmp_path)[0]


def test_symlink_target_rejected(tmp_path):
    (tmp_path / 'model').symlink_to(tmp_path / 'elsewhere')
    with pytest.raises(ValueError):
        job.reject_symlinks(tmp_path / 'model')


def test_start_is_detached_fixed_argv(monkeypatch):
    calls = []
    monkeypatch.setattr(job.subprocess, 'run', lambda args, **kw: calls.append(args))
    job.start('Qwen3.8-27B-Q4_K_M')
    assert calls[0][0] == '/usr/bin/systemd-run'
    assert '--worker' in calls[0]
    assert calls[0][-1] == 'Qwen3.8-27B-Q4_K_M'
    assert not any('HF_TOKEN' in a for a in calls[0])


@pytest.mark.parametrize('corrupt', [False, True])
def test_worker_verifies_and_keeps_token_out_of_state(tmp_path, monkeypatch, corrupt):
    monkeypatch.setattr(job, 'STATE', tmp_path / 'states')
    monkeypatch.setattr(job, 'VAULT', tmp_path / 'vault')
    monkeypatch.setattr(job, 'entry', lambda _: {
        'hf_repo_id': 'test/model', 'hf_include_patterns': ['weights.gguf']})
    monkeypatch.setattr(job.runpy, 'run_path', lambda _: {
        'token_environment': lambda _: {'HF_TOKEN': 'secret-test-value'}})
    item = SimpleNamespace(rfilename='weights.gguf', size=3,
                           lfs={'sha256': hashlib.sha256(b'abc').hexdigest()})
    class Api:
        def __init__(self, token):
            assert token == 'secret-test-value'
        def model_info(self, repo, **kw):
            return SimpleNamespace(sha='pinned-revision', siblings=[item])
    def download(**kw):
        assert kw['revision'] == 'pinned-revision'
        assert kw['allow_patterns'] == ['weights.gguf']
        (Path(kw['local_dir']) / 'weights.gguf').write_bytes(b'bad' if corrupt else b'abc')
    monkeypatch.setitem(sys.modules, 'huggingface_hub', SimpleNamespace(
        HfApi=Api, snapshot_download=download))
    assert job.worker('model') == (1 if corrupt else 0)
    raw = (job.STATE / 'model.json').read_text()
    assert 'secret-test-value' not in raw
    assert json.loads(raw)['status'] == ('failed' if corrupt else 'complete')


def test_control_download_installation_error(monkeypatch):
    spec = importlib.util.spec_from_file_location('actions_download_test', ROOT / 'scripts/operator/_action_exec.py')
    actions = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(actions)
    monkeypatch.setattr(actions, 'operator_key_loaded', lambda: True)
    monkeypatch.setattr(actions, '_compat_pre_change', lambda *a: None)
    monkeypatch.setattr(actions, '_stepup_enabled', lambda: False)
    monkeypatch.setattr(actions, '_emit_audit', lambda *a, **kw: None)
    monkeypatch.setattr(actions, '_emit_metric', lambda *a: None)
    monkeypatch.setattr(actions.subprocess, 'run', lambda *a, **kw:
                        SimpleNamespace(returncode=1, stdout='', stderr='sudo: a password is required'))
    result = actions.execute('model-download', {'model':'Qwen3.8-27B-Q4_K_M'}, confirm=True, dry_run=False)
    assert result['code'] == 503
    assert result['installation_required'] is True
