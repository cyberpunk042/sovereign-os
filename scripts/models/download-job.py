#!/usr/bin/env python3
"""Catalog-only privileged download jobs; no user-provided paths or commands."""
import argparse
import fcntl
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import runpy
import shutil
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
VAULT = Path('/mnt/vault/models')
STATE = Path('/var/lib/sovereign-os/model-downloads')
SAFE_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}')


def entry(model_id):
    import yaml
    if not SAFE_ID.fullmatch(model_id) or '..' in model_id:
        raise ValueError('Invalid catalog model ID')
    rows = yaml.safe_load((ROOT / 'models/catalog.yaml').read_text())['catalog']['models']
    row = next((r for r in rows if r['id'] == model_id), None)
    if not row or not row.get('hf_repo_id'):
        raise ValueError('Model must have a catalogued Hugging Face repository')
    if row.get('status') not in ('verified-real', 'operator-must-confirm'):
        raise ValueError('This catalog entry is not downloadable')
    if not row.get('hf_include_patterns'):
        raise ValueError('Catalog must select exact artifact patterns before cockpit download')
    return row


def select_files(row, siblings):
    selected = []
    for item in siblings:
        name = item.rfilename
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name:
            raise ValueError('Unsafe repository filename')
        if any(fnmatch.fnmatchcase(name, p) for p in row['hf_include_patterns']):
            lfs = item.lfs
            digest = getattr(lfs, 'sha256', None)
            if isinstance(lfs, dict):
                digest = lfs.get('sha256')
            selected.append({'path': name, 'size': item.size, 'sha256': digest})
    weights = [f for f in selected if f['path'].endswith(('.gguf', '.safetensors'))]
    for pattern in row['hf_include_patterns']:
        if pattern.endswith(('.gguf', '.safetensors')) and not any(
                fnmatch.fnmatchcase(f['path'], pattern) for f in weights):
            raise ValueError('A selected weight artifact is missing from the repository')
    shards = {}
    for item in weights:
        match = re.fullmatch(r'(.+)-(\d{5})-of-(\d{5})\.gguf', item['path'])
        if match:
            prefix, index, count = match.groups()
            shards.setdefault((prefix, int(count)), set()).add(int(index))
    if any(indices != set(range(1, count + 1)) for (_, count), indices in shards.items()):
        raise ValueError('All GGUF shards must be selected')
    if not weights or any(not f['size'] or not f['sha256'] for f in weights):
        raise ValueError('Selected weights need sizes and LFS SHA256 metadata')
    if any(f['size'] is None for f in selected):
        raise ValueError('Repository file size unavailable')
    return selected


def write_state(model_id, value):
    value = dict(value, updated_at=time.time())
    tmp = STATE / (model_id + '.tmp')
    tmp.write_text(json.dumps(value))
    tmp.chmod(0o644)
    tmp.replace(STATE / (model_id + '.json'))


def reject_symlinks(path):
    # No recursive chmod/chown and no traversal through an existing symlink.
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError('Download paths must not contain symlinks')
    if path.exists() and any(p.is_symlink() for p in path.rglob('*')):
        raise ValueError('Download destination contains a symlink')


def readiness(model_id, row, vault=VAULT, state_dir=STATE):
    """Read-only cockpit projection; a directory alone is never readiness."""
    if not SAFE_ID.fullmatch(model_id) or '..' in model_id:
        return False, {}
    target = vault / model_id
    try:
        job = json.loads((state_dir / (model_id + '.json')).read_text())
    except (OSError, ValueError):
        job = {}
    if job.get('status') in ('queued', 'preflight', 'downloading', 'verifying'):
        # Interrupted/rebooted jobs must not remain a permanent spinner.
        try:
            pid = int(job.get('pid', 0))
            if pid <= 0:
                raise ValueError('missing worker PID')
            os.kill(pid, 0)
        except PermissionError:
            pass  # root-owned worker is alive but not signalable
        except (ProcessLookupError, ValueError):
            job = dict(job, status='interrupted')
        return False, job
    if job:
        files = job.get('files', [])
        ready = job.get('status') == 'complete' and bool(files)
        ready = ready and all((target / f['path']).is_file() and
                              (target / f['path']).stat().st_size == f['size'] for f in files)
        return ready, job
    patterns = row.get('hf_include_patterns', [])
    if patterns:
        weight_patterns = [p for p in patterns if p.endswith(('.gguf', '.safetensors'))]
        return bool(weight_patterns) and all(any(f.is_file() and f.stat().st_size > 0
               for f in target.glob(p)) for p in weight_patterns), {}
    return target.is_dir() and any(f.is_file() and f.stat().st_size > 0
               for suffix in ('*.gguf', '*.safetensors', '*.bin')
               for f in target.rglob(suffix)), {}


def start(model_id):
    entry(model_id)  # validate before elevation-side process creation
    unit = 'sovereign-model-download-' + model_id
    # Same model has one systemd unit. No shell, arbitrary env or caller path.
    argv = ['/usr/bin/systemd-run', '--quiet', '--collect', '--unit=' + unit,
            '--property=UMask=0022', '--property=RuntimeMaxSec=86400',
            '--property=TimeoutStopSec=30',
            '/usr/bin/python3', str(Path(__file__).resolve()), '--worker', model_id]
    subprocess.run(argv, check=True, timeout=20)
    print(json.dumps({'status': 'accepted', 'model_id': model_id, 'unit': unit}))


def worker(model_id):
    row = entry(model_id)
    reject_symlinks(STATE)
    STATE.mkdir(parents=True, exist_ok=True, mode=0o755)
    try:
        previous = json.loads((STATE / (model_id + '.json')).read_text())
    except (OSError, ValueError):
        previous = {}
    state = {'model_id': model_id, 'status': 'queued', 'pid': os.getpid(),
             'bytes_done': 0, 'bytes_total': 0}
    write_state(model_id, state)
    stop = threading.Event()
    monitor = None
    try:
        # Serialize large transfers while keeping the HTTP control rail free.
        with (STATE / '.transfer.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            state['status'] = 'preflight'
            write_state(model_id, state)
            target = VAULT / model_id
            reject_symlinks(target)
            target.mkdir(parents=True, exist_ok=True, mode=0o755)
            auth = runpy.run_path(str(ROOT / 'scripts/models/hf-auth.py'))
            env = auth['token_environment'](os.environ)
            token = env.get('HF_TOKEN')
            from huggingface_hub import HfApi, snapshot_download
            info = HfApi(token=token).model_info(row['hf_repo_id'],
                                               revision=row.get('hf_revision'), files_metadata=True)
            files = select_files(row, info.siblings)
            total = sum(f['size'] for f in files)
            needed = sum(max(0, f['size'] - ((target / f['path']).stat().st_size
                         if (target / f['path']).is_file() else 0)) for f in files)
            if shutil.disk_usage(target).free < needed + 2 * 1024**3:
                raise ValueError('Insufficient vault space, including 2 GiB safety margin')
            state.update(status='downloading', revision=info.sha, bytes_total=total,
                         files=files, repo=row['hf_repo_id'])
            def progress():
                while not stop.is_set():
                    done = sum(min(f['size'], (target / f['path']).stat().st_size)
                               for f in files if (target / f['path']).is_file())
                    done += sum(p.stat().st_size for p in target.rglob('*.incomplete')
                                if p.is_file())
                    state['bytes_done'] = min(total, done)
                    write_state(model_id, state)
                    stop.wait(2)
            monitor = threading.Thread(target=progress, daemon=True)
            monitor.start()
            snapshot_download(repo_id=row['hf_repo_id'], revision=info.sha,
                              allow_patterns=[f['path'] for f in files],
                              local_dir=str(target), token=token, max_workers=2,
                              force_download=previous.get('error_stage') == 'verifying')
            stop.set()
            monitor.join()
            state['status'] = 'verifying'
            write_state(model_id, state)
            for item in files:
                path = target / item['path']
                if path.stat().st_size != item['size']:
                    raise ValueError('Downloaded file size mismatch')
                if item['sha256']:
                    with path.open('rb') as handle:
                        actual = hashlib.file_digest(handle, 'sha256').hexdigest()
                    if actual != item['sha256']:
                        raise ValueError('Downloaded checksum mismatch; artifact not ready')
            state.update(status='complete', bytes_done=total)
    except Exception as exc:
        # No exception text: HTTP diagnostics can contain credential-bearing URLs.
        state.update(error_stage=state['status'], status='failed', error_type=type(exc).__name__,
                     error='Download failed. Check disk space, HF access/token and artifact integrity; retry resumes partial files.')
    finally:
        stop.set()
        if monitor:
            monitor.join()
        write_state(model_id, state)
    return 0 if state['status'] == 'complete' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('model_id')
    args = parser.parse_args()
    if os.geteuid() != 0:
        sys.exit('Download service requires the installed scoped cockpit grant')
    try:
        if args.worker:
            sys.exit(worker(args.model_id))
        start(args.model_id)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        sys.exit(str(exc))
