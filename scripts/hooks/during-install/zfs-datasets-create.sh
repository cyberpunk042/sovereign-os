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

STEP_ID="zfs-datasets-create"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

: "${SOVEREIGN_OS_POOL_NAME:=tank}"
: "${SOVEREIGN_OS_MOUNT_BASE:=/mnt/vault}"

log_step_header "${STEP_ID}" "create ZFS datasets in pool ${SOVEREIGN_OS_POOL_NAME}"

require_root
require_command zfs

if ! zpool list "${SOVEREIGN_OS_POOL_NAME}" >/dev/null 2>&1; then
  log_error "pool ${SOVEREIGN_OS_POOL_NAME} does not exist; run zfs-pool-create.sh first"
  exit 1
fi

# Iterate over datasets from profile
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
    args += [name]
    # Check existence
    chk = subprocess.run(['zfs', 'list', name], capture_output=True)
    if chk.returncode == 0:
        print(f'  [SKIP] {name} already exists')
        continue
    print(f'  [CREATE] {\" \".join(args)}')
    subprocess.run(args, check=True)
    print(f'           purpose: {ds.get(\"purpose\", \"-\")}')
"

# Final state
log_info "datasets after create:"
zfs list -r "${SOVEREIGN_OS_POOL_NAME}" -o name,used,available,mountpoint,recordsize,compression,sync || true

log_info "${STEP_ID} complete"
