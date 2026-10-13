#!/usr/bin/env python3
"""Persistent image units and profile-aware boot conditions."""
import json
from pathlib import Path
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[2]


def permitted(tier, model=None, root=ROOT, marker=Path('/etc/sovereign-os/active-runtime-profile')):
    name = marker.read_text().strip()
    if not name or Path(name).name != name:
        raise ValueError('Invalid active profile marker')
    for family in ('runtime', 'orchestration'):
        path = root / 'profiles' / family / (name + '.yaml')
        if not path.exists():
            continue
        doc = yaml.safe_load(path.read_text())
        profile = doc.get('orchestration_profile') or doc.get('runtime_profile') or {}
        # Legacy chat profiles retain their existing startup contract.
        if not str(profile.get('runtime_handler', '')).startswith('image'):
            return tier != 'image'
        return any(a.get('active', True) and a.get('tier') == tier and
                   (model is None or a.get('model') == model)
                   for a in profile.get('allocations', []))
    raise ValueError('Active profile cannot be resolved; refusing stale defaults')


def quote(value):
    return json.dumps(str(value)).replace('%', '%%')


def install(service, operator, gpu, port, binary, arguments, model):
    """Called by the privileged activation transaction after stopping old units."""
    check = ROOT / 'scripts/inference/image-profile-boot.py'
    command = [str(binary), '--listen-ip', '127.0.0.1', '--listen-port', str(port),
               '--backend', 'te=cpu', '--mmap', '--diffusion-fa',
               '--sampling-method', 'euler', '--steps', '28', *arguments]
    libraries = str(ROOT / '.runtime/sd-cuda133/nvidia/cu13/lib') + ':/opt/sovereign-os/venv/vllm/lib/python3.14/site-packages/nvidia/cu13/lib'
    unit = '\n'.join([
        '[Unit]', 'Description=Profile-owned native image runtime',
        'After=local-fs.target nvidia-persistenced.service',
        'RequiresMountsFor=' + quote(ROOT) + ' /mnt/vault/models',
        '[Service]', 'Type=simple', 'User=' + operator.pw_name,
        'WorkingDirectory=' + str(ROOT).replace('%', '%%'),
        'Environment=' + quote('HOME=' + operator.pw_dir),
        'Environment=' + quote('CUDA_VISIBLE_DEVICES=' + gpu),
        'Environment=' + quote('LD_LIBRARY_PATH=' + libraries),
        'ExecCondition=/usr/bin/python3 ' + quote(check) + ' image ' + quote(model),
        'ExecStart=' + ' '.join(map(quote, command)),
        'Restart=on-failure', 'RestartSec=10', 'TimeoutStopSec=120',
        '[Install]', 'WantedBy=multi-user.target', ''])
    (Path('/etc/systemd/system') / (service + '.service')).write_text(unit)
    for tier, chat in [('logic', 'sovereign-logic-engine'), ('oracle', 'sovereign-oracle-core')]:
        drop = Path('/etc/systemd/system') / (chat + '.service.d')
        drop.mkdir(exist_ok=True)
        (drop / '20-profile-allocation.conf').write_text(
            '[Service]\nExecCondition=/usr/bin/python3 ' + quote(check) + ' ' + tier + '\n')
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', 'enable', service + '.service'], check=True)
    subprocess.run(['systemctl', 'start', service + '.service'], check=True)


if __name__ == '__main__':
    try:
        sys.exit(0 if permitted(*sys.argv[1:]) else 1)
    except Exception as exc:
        print(f'Profile boot condition: {exc}', file=sys.stderr)
        sys.exit(1)
