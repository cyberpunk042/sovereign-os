#!/usr/bin/env python3
"""Transactional activation for image-companion profiles.

An image-companion profile keeps ONE llama.cpp chat resident (the Oracle
allocation, so the OpenClaw assistant survives a model reload) and puts ONE
stable-diffusion.cpp runtime on the RTX 5090. Unlike the dual image profile
this is a mixed transaction: chat tiers move through the systemd launchers
(which re-read the marker written here), image tiers use persistent,
profile-conditioned systemd units, and OpenClaw is re-synced only after both halves are
ready. Any failure restores the previous marker and chat services.
"""
import argparse
import importlib.util
import json
import os
import pwd
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
_boot_spec = importlib.util.spec_from_file_location('image_profile_boot', ROOT / 'scripts/inference/image-profile-boot.py')
boot = importlib.util.module_from_spec(_boot_spec)
_boot_spec.loader.exec_module(boot)
MARKER = Path('/etc/sovereign-os/active-runtime-profile')
SD_SERVER = ROOT / '.runtime/stable-diffusion.cpp/build-cuda133/bin/sd-server'
CARD_NAME = {'cuda:0': 'RTX PRO 6000', 'cuda:1': 'RTX 5090', 'cuda:2': 'RTX 4090'}
# Reuse the artifact arguments verified by the dual-image qualification run;
# the companion profiles must not drift their own copy of these paths.
_spec = importlib.util.spec_from_file_location(
    'image_dual_arguments', ROOT / 'scripts/inference/activate-image-profile.py')
_dual = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_dual)
MODEL_KIND = {'Qwen-Image-2.1-Uncensored-BF16': 'qwen', 'FLUX.2-dev': 'flux'}
UNIT = {'qwen': 'sovereign-image-qwen', 'flux': 'sovereign-image-flux'}
TIER_UNIT = {'oracle': 'sovereign-oracle-core', 'logic': 'sovereign-logic-engine'}
IMAGE_UNITS_ALL = tuple(UNIT.values())


def run(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError(f'{args[0]} failed: {result.stderr.strip()}')
    return result


def image_ready(port):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/v1/models', timeout=3) as r:
            return any(m.get('id') == 'sd-cpp-local' for m in json.load(r).get('data', []))
    except Exception:
        return False


def llm_ready(port):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/v1/models', timeout=5) as r:
            return bool(json.load(r).get('data'))
    except Exception:
        return False


def sync_openclaw(profile_id):
    subprocess.run([sys.executable, str(ROOT / 'scripts/inference/sync-openclaw-models.py'),
                    '--profile', profile_id], check=False)


def sync_activation_contract(profile_yaml):
    """The chat-tier systemd units execute the PACKAGED /opt payload; if this
    profile is newer than that payload, the resolver there cannot find its
    YAML and the launcher silently serves its start-script default — the
    wrong-model activations that forced repeated re-applies (2026-10-09).
    Same single sync `trinity profile switch` uses; a sync failure must abort
    BEFORE any service is touched."""
    fam = Path(profile_yaml).resolve().parent.name
    if fam not in ('runtime', 'orchestration'):
        fam = 'orchestration'  # operator drafts carry the orchestration shape
    result = subprocess.run(
        [sys.executable, str(ROOT / 'scripts/inference/sync-activation-contract.py'),
         fam, str(profile_yaml)], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError('activation contract sync failed: '
                           + (result.stderr or result.stdout).strip())
    for line in result.stdout.strip().splitlines():
        print('  ' + line)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('profile_yaml', help='orchestration profile file (runtime_handler: image-companion)')
    args = ap.parse_args(argv)
    if os.geteuid() != 0:
        raise RuntimeError('Use the privileged profile switch rail')

    document = yaml.safe_load(Path(args.profile_yaml).read_text(encoding='utf-8'))
    profile = document['orchestration_profile']
    profile_id = profile['id']
    if profile.get('runtime_handler') != 'image-companion':
        raise RuntimeError(f'{profile_id}: runtime_handler is not image-companion')
    allocations = [a for a in profile.get('allocations') or [] if a.get('active', True)]
    images = [a for a in allocations if a.get('tier') == 'image']
    chat = {a['tier']: a for a in allocations if a.get('tier') in TIER_UNIT}
    if not images:
        raise RuntimeError('profile declares no active image allocation')
    if 'oracle' not in chat:
        raise RuntimeError('image-companion profiles must keep an Oracle chat resident')

    if not SD_SERVER.is_file():
        raise RuntimeError('Image runtime installation is missing')
    kinds = []
    for alloc in images:
        kind = MODEL_KIND.get(alloc.get('model'))
        if kind is None:
            raise RuntimeError(f"image model {alloc.get('model')!r} has no verified native argument set")
        state = json.loads((Path('/var/lib/sovereign-os/model-downloads') / (alloc['model'] + '.json')).read_text())
        if state.get('status') != 'complete':
            raise RuntimeError(f"{alloc['model']}: download verification must complete first")
        for f in state['files']:
            p = Path('/mnt/vault/models') / alloc['model'] / f['path']
            if not p.is_file() or p.stat().st_size != f['size']:
                raise RuntimeError(f"{alloc['model']}: verified artifact missing or changed")
        if kind == 'flux' and not all((ROOT / '.runtime/image-artifacts' / name).is_file() for name in
                                      ('flux2-dev-native-bf16.safetensors',
                                       'flux2-text-encoder-native-bf16.safetensors')):
            raise RuntimeError('FLUX native-layout preparation is not complete; running models were not changed')
        kinds.append(kind)

    if not (chat['oracle'].get('port') and all(a.get('port') and a.get('target_hardware') in CARD_NAME
                                               for a in images)):
        raise RuntimeError('profile allocations need ports and known cuda target_hardware values')

    gpu_rows = run('nvidia-smi', '--query-gpu=uuid,name', '--format=csv,noheader').stdout.splitlines()

    def uuid_for(hw):
        label = CARD_NAME[hw]
        matches = [line.split(',')[0].strip() for line in gpu_rows if label in line]
        if len(matches) != 1:
            raise RuntimeError(f'Cannot uniquely resolve {label}')
        return matches[0]

    image_units = list(zip(images, kinds))
    old = MARKER.read_text().strip()
    if old == profile_id and all((Path('/etc/systemd/system') / (UNIT[k] + '.service')).is_file() for k in kinds) and llm_ready(chat['oracle']['port']) \
            and all(image_ready(a['port']) for a in images):
        sync_openclaw(profile_id)
        print('Image companion already active; OpenClaw re-synced')
        return

    operator = pwd.getpwuid(ROOT.stat().st_uid)
    # Sync the activation contract BEFORE anything is restarted: a tier that
    # restarts against a payload which cannot resolve the selected profile
    # serves its default weights while the cockpit declares the new model.
    sync_activation_contract(args.profile_yaml)
    try:
        # Free the image GPU first: stop every image unit, then move the chat
        # tier services, which re-read the marker at launch.
        for unit in IMAGE_UNITS_ALL:
            subprocess.run(['systemctl', 'stop', unit], capture_output=True)
        MARKER.write_text(profile_id + '\n')
        MARKER.chmod(0o644)
        for tier, unit in TIER_UNIT.items():
            alloc = chat.get(tier)
            if alloc:
                run('systemctl', 'restart', unit + '.service')
            else:
                subprocess.run(['systemctl', 'stop', unit + '.service'], capture_output=True)
        started_chat = True
        deadline = time.monotonic() + 600
        while not llm_ready(chat['oracle']['port']) and time.monotonic() < deadline:
            state = run('systemctl', 'is-active', TIER_UNIT['oracle'] + '.service').stdout.strip()
            if state in ('failed', 'inactive'):
                raise RuntimeError('oracle service stopped during model reload; inspect its journal')
            time.sleep(5)
        if not llm_ready(chat['oracle']['port']):
            raise RuntimeError('oracle did not become ready within 600 seconds')

        for alloc, kind in image_units:
            boot.install(UNIT[kind], operator, uuid_for(alloc['target_hardware']),
                         alloc['port'], SD_SERVER, _dual.model_arguments(kind), alloc['model'])
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            for alloc, kind in image_units:
                state = run('systemctl', 'is-active', UNIT[kind]).stdout.strip()
                if state in ('failed', 'inactive', 'unknown'):
                    raise RuntimeError(f'{UNIT[kind]} stopped during startup; inspect its journal')
            if all(image_ready(a['port']) for a, _ in image_units):
                sync_openclaw(profile_id)
                print(f'Image companion {profile_id} active: Oracle :{chat["oracle"]["port"]}, '
                      + ', '.join(f'{UNIT[kind]} :{alloc["port"]}' for alloc, kind in image_units)
                      + '. OpenClaw image_generate wired.')
                return
            time.sleep(2)
        raise RuntimeError('image services did not become ready within 300 seconds')
    except Exception:
        for _, kind in image_units:
            subprocess.run(['systemctl', 'stop', UNIT[kind]], capture_output=True)
        MARKER.write_text(old + '\n')
        # Chat launchers re-read the restored marker; restarting both tier
        # units reloads exactly the previous profile's residents.
        for unit in ('sovereign-logic-engine', 'sovereign-oracle-core'):
            subprocess.run(['systemctl', 'restart', unit + '.service'], capture_output=True)
        print(f'Rolled back to profile {old}', flush=True)
        raise


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Image companion activation failed: {exc}', flush=True)
        raise SystemExit(1)
