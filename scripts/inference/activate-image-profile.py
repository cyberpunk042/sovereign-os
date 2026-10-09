#!/usr/bin/env python3
"""Transactional image-runtime activation, using verified local artifacts."""
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
PROFILE = 'qwen-image-flux-dual'
MARKER = Path('/etc/sovereign-os/active-runtime-profile')
SERVICES = ('sovereign-image-qwen', 'sovereign-image-flux')
LLMS = ('sovereign-logic-engine', 'sovereign-oracle-core')


def run(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError(f'{args[0]} failed: {result.stderr.strip()}')
    return result


def model_arguments(kind):
    vault = Path('/mnt/vault/models')
    if kind == 'qwen':
        base = vault / 'Qwen-Image-2.1-Uncensored-BF16'
        return ['--diffusion-model', str(base / 'qwen-image-2.1-UC-BF16.gguf'),
                '--vae', str(base / 'vae/qwen_image_2.1_vae_bf16.safetensors'),
                '--llm', str(base / 'text_encoders/qwen3vl_8b_bf16.safetensors'),
                '--cfg-scale', '6.0']
    if kind == 'flux':
        base = vault / 'FLUX.2-dev'
        return ['--diffusion-model', str(ROOT / '.runtime/image-artifacts/flux2-dev-native-bf16.safetensors'),
                '--vae', str(base / 'vae/diffusion_pytorch_model.safetensors'),
                '--llm', str(ROOT / '.runtime/image-artifacts/flux2-text-encoder-native-bf16.safetensors'),
                '--cfg-scale', '1.0', '--guidance', '4.0']
    raise ValueError('Unknown image allocation')


def ready(port):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/v1/models', timeout=3) as r:
            return any(m.get('id') == 'sd-cpp-local' for m in json.load(r).get('data', []))
    except Exception:
        return False


def main():
    if os.geteuid() != 0:
        raise RuntimeError('Use the privileged profile switch rail')
    binary = ROOT / '.runtime/stable-diffusion.cpp/build-cuda133/bin/sd-server'
    if not binary.is_file():
        raise RuntimeError('Image runtime installation is missing')
    for model in ('Qwen-Image-2.1-Uncensored-BF16', 'FLUX.2-dev'):
        state = json.loads((Path('/var/lib/sovereign-os/model-downloads') / (model + '.json')).read_text())
        if state.get('status') != 'complete':
            raise RuntimeError(f'{model}: download verification must complete first')
        for f in state['files']:
            p = Path('/mnt/vault/models') / model / f['path']
            if not p.is_file() or p.stat().st_size != f['size']:
                raise RuntimeError(f'{model}: verified artifact missing or changed')
    run(str(binary), '--version')
    if not all((ROOT / '.runtime/image-artifacts' / name).is_file() for name in
               ('flux2-dev-native-bf16.safetensors', 'flux2-text-encoder-native-bf16.safetensors')):
        raise RuntimeError('FLUX native-layout preparation is not complete; running models were not changed')
    operator = pwd.getpwuid(ROOT.stat().st_uid)
    gpu_rows = run('nvidia-smi', '--query-gpu=uuid,name', '--format=csv,noheader').stdout.splitlines()
    devices = []
    for label in ('RTX 5090', 'RTX PRO 6000'):
        matches = [line.split(',')[0].strip() for line in gpu_rows if label in line]
        if len(matches) != 1:
            raise RuntimeError(f'Cannot uniquely resolve {label}')
        devices.append(matches[0])
    old = MARKER.read_text().strip()
    if old == PROFILE and ready(8188) and ready(8189):
        subprocess.run([sys.executable, str(ROOT / 'scripts/inference/sync-openclaw-models.py'),
                        '--profile', PROFILE], check=False)
        print('Image services already active; no restart needed')
        return
    active_llms = [s for s in LLMS if subprocess.run(['systemctl', 'is-active', '--quiet', s]).returncode == 0]
    try:
        for s in active_llms:
            run('systemctl', 'stop', s)
        for service, gpu, port, kind in zip(SERVICES, devices, (8188, 8189), ('qwen', 'flux')):
            subprocess.run(['systemctl', 'stop', service], capture_output=True)
            # These services are session-scoped until boot restoration is qualified.
            run('systemd-run', '--collect', '--unit=' + service,
                '--uid=' + operator.pw_name, '--property=WorkingDirectory=' + str(ROOT),
                '--setenv=HOME=' + operator.pw_dir,
                '--setenv=CUDA_VISIBLE_DEVICES=' + gpu,
                '--setenv=LD_LIBRARY_PATH=' + str(ROOT / '.runtime/sd-cuda133/nvidia/cu13/lib') + ':/opt/sovereign-os/venv/vllm/lib/python3.14/site-packages/nvidia/cu13/lib',
                str(binary), '--listen-ip', '127.0.0.1', '--listen-port', str(port),
                '--backend', 'te=cpu', '--mmap', '--diffusion-fa',
                '--sampling-method', 'euler', '--steps', '28', *model_arguments(kind))
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            for service in SERVICES:
                state = subprocess.run(['systemctl', 'is-active', service], capture_output=True, text=True).stdout.strip()
                if state in ('failed', 'inactive', 'unknown'):
                    raise RuntimeError(f'{service} stopped during startup; inspect its journal for the model-loader error')
            if ready(8188) and ready(8189):
                # Service readiness only: cockpit must not call weights resident
                # until an actual image workflow has loaded them.
                tmp = MARKER.with_suffix('.image-tmp')
                tmp.write_text(PROFILE + '\n')
                tmp.chmod(0o644)
                tmp.replace(MARKER)
                # Wire OpenClaw's image_generate tool to the live sd-cpp
                # endpoint and reload the gateway, so the operator can
                # generate images without touching OpenClaw config by hand.
                # Non-fatal: a sync failure leaves images reachable by API but
                # must not roll back already-running image services.
                subprocess.run([sys.executable, str(ROOT / 'scripts/inference/sync-openclaw-models.py'),
                                '--profile', PROFILE], check=False)
                print('Image workflow services ready: Qwen :8188, FLUX :8189. Weights load on generation; qualification pending.')
                return
            time.sleep(2)
        raise RuntimeError('Image workflow services did not become ready within 300 seconds')
    except Exception:
        for service in SERVICES:
            subprocess.run(['systemctl', 'stop', service], capture_output=True)
        MARKER.write_text(old + '\n')
        for service in active_llms:
            subprocess.run(['systemctl', 'start', service], capture_output=True)
        raise


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Image activation failed: {exc}', flush=True)
        raise SystemExit(1)
