#!/usr/bin/env bash
# scripts/hooks/during-install/zfs-datasets-create.sh
#
# Create the per-profile ZFS datasets with operator-specified
# recordsize / compression / sync / copies / redundant_metadata.
# Reads hardware.storage.datasets from the active profile.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

STEP_ID="zfs-datasets-create"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

: "${SOVEREIGN_OS_POOL_NAME:=tank}"
: "${SOVEREIGN_OS_MOUNT_BASE:=/mnt/vault}"

log_step_header "${STEP_ID}" "create ZFS datasets in pool ${SOVEREIGN_OS_POOL_NAME}"

emit_datasets_metric() {
  emit_metric sovereign_os_during_install_datasets_create_total 1 \
    "pool=\"${SOVEREIGN_OS_POOL_NAME}\",result=\"$1\""
}

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN — would create datasets per profile in pool ${SOVEREIGN_OS_POOL_NAME}"
  emit_datasets_metric skip-dry-run
  exit 0
fi

require_root
require_command zfs

if ! zpool list "${SOVEREIGN_OS_POOL_NAME}" >/dev/null 2>&1; then
  log_error "pool ${SOVEREIGN_OS_POOL_NAME} does not exist; run zfs-pool-create.sh first"
  emit_datasets_metric missing-pool
  exit 1
fi

# Iterate over datasets from profile. Guard the create pipeline: a failed
# `zfs create` (bad recordsize/compression value, pool full, dataset-name
# collision) raises in the inner python (check=True) and, under set -e, aborts
# the hook WITHOUT emit_datasets_metric fail — unlike every other exit path
# here (skip-dry-run / missing-pool / success). Capture it so a half-created
# dataset layout is VISIBLE in during_install_datasets_create_total.
datasets_rc=0
python3 -c "
import os, yaml, json
with open(os.environ['SOVEREIGN_OS_PROFILE_FILE']) as f:
    d = yaml.safe_load(f)
datasets = ((d.get('hardware') or {}).get('storage') or {}).get('datasets') or []
print(json.dumps(datasets))
" | python3 -c "
import sys, json, subprocess, os
datasets = json.load(sys.stdin)
pool = os.environ.get('SOVEREIGN_OS_POOL_NAME', 'tank')
mount_base = os.environ.get('SOVEREIGN_OS_MOUNT_BASE', '/mnt/vault')
for ds in datasets:
    name = ds.get('name')
    if not name or not name.startswith(pool + '/'):
        continue
    suffix = name.split('/', 1)[1]
    mountpoint = f'{mount_base}/{suffix}'
    # Build zfs create args
    args = ['zfs', 'create']
    args += ['-o', f'mountpoint={mountpoint}']
    if 'recordsize' in ds:
        args += ['-o', f'recordsize={ds[\"recordsize\"]}']
    if 'compression' in ds:
        args += ['-o', f'compression={ds[\"compression\"]}']
    if 'copies' in ds:
        args += ['-o', f'copies={ds[\"copies\"]}']
    if 'sync' in ds:
        args += ['-o', f'sync={ds[\"sync\"]}']
    if 'redundant_metadata' in ds:
        args += ['-o', f'redundant_metadata={ds[\"redundant_metadata\"]}']
    if ds.get('encryption') and ds['encryption'] != 'off':
        enc = ds['encryption']
        key_pass = os.environ.get('SOVEREIGN_OS_ENCRYPT_PASSPHRASE', '')
        if key_pass:
            args += ['-o', f'encryption={enc}', '-o', 'keyformat=passphrase']
        else:
            print(f'  [WARN] dataset {name} requests encryption={enc} but SOVEREIGN_OS_ENCRYPT_PASSPHRASE is unset; creating UNENCRYPTED (degraded)')
    args += [name]
    # Check existence
    chk = subprocess.run(['zfs', 'list', name], capture_output=True)
    if chk.returncode == 0:
        print(f'  [SKIP] {name} already exists')
        continue
    print(f'  [CREATE] {\" \".join(args)}')
    if ds.get('encryption') and ds['encryption'] != 'off' and os.environ.get('SOVEREIGN_OS_ENCRYPT_PASSPHRASE', ''):
        proc = subprocess.Popen(args, stdin=subprocess.PIPE, text=True)
        proc.communicate(input=os.environ['SOVEREIGN_OS_ENCRYPT_PASSPHRASE'] + '\n' + os.environ['SOVEREIGN_OS_ENCRYPT_PASSPHRASE'] + '\n')
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, args)
    else:
        subprocess.run(args, check=True)
    print(f'           purpose: {ds.get(\"purpose\", \"-\")}')
" || datasets_rc=$?
if [ "${datasets_rc}" -ne 0 ]; then
  log_error "dataset creation failed (rc=${datasets_rc}) — bad property value, pool full, or name collision; layout may be partial"
  emit_datasets_metric fail
  exit 1
fi

# Final state
log_info "datasets after create:"
zfs list -r "${SOVEREIGN_OS_POOL_NAME}" -o name,used,available,mountpoint,recordsize,compression,sync || true

emit_datasets_metric success
log_info "${STEP_ID} complete"
