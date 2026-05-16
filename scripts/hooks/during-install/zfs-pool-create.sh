#!/usr/bin/env bash
# scripts/hooks/during-install/zfs-pool-create.sh
#
# Create the ZFS pool for the sovereign-os install. Per profile's
# hardware.storage.{devices,topology}. Default for sain-01: RAID-0
# across the dual PCIe-5 NVMe drives. Operator-acknowledged no-
# redundancy trade-off (snapshot-replicate strategy via Q-005).

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"

STEP_ID="zfs-pool-create"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

: "${SOVEREIGN_OS_POOL_NAME:=tank}"
: "${SOVEREIGN_OS_POOL_DEVICES:=}"  # space-separated; operator sets at install time

log_step_header "${STEP_ID}" "create ZFS pool ${SOVEREIGN_OS_POOL_NAME}"

# Layout sanity check
layout="$(profile_field hardware.storage.layout)"
if [ "${layout}" != "zfs-tiered" ]; then
  log_warn "profile storage layout is '${layout}' (not zfs-tiered); skipping pool create"
  exit 0
fi

require_root
require_command zpool

if zpool list "${SOVEREIGN_OS_POOL_NAME}" >/dev/null 2>&1; then
  log_info "pool ${SOVEREIGN_OS_POOL_NAME} already exists"
  zpool status "${SOVEREIGN_OS_POOL_NAME}"
  exit 0
fi

if [ -z "${SOVEREIGN_OS_POOL_DEVICES}" ]; then
  log_error "SOVEREIGN_OS_POOL_DEVICES env not set"
  log_error "  Example: SOVEREIGN_OS_POOL_DEVICES='/dev/nvme0n1 /dev/nvme1n1' $0"
  exit 1
fi

# Topology from profile
topology="$(python3 -c "
import os, yaml
with open(os.environ['SOVEREIGN_OS_PROFILE_FILE']) as f:
    d = yaml.safe_load(f)
devs = ((d.get('hardware') or {}).get('storage') or {}).get('devices') or []
rootfs = next((dev for dev in devs if dev.get('role') == 'rootfs'), None)
print((rootfs or {}).get('topology', 'single'))
")"

case "${topology}" in
  raid0|single)
    # raid0 = listed devices side-by-side; single = first device only
    if [ "${topology}" = "single" ]; then
      set -- ${SOVEREIGN_OS_POOL_DEVICES}
      devices="$1"
    else
      devices="${SOVEREIGN_OS_POOL_DEVICES}"
    fi
    log_info "creating pool ${SOVEREIGN_OS_POOL_NAME} (topology=${topology}) on: ${devices}"
    # shellcheck disable=SC2086
    zpool create -o ashift=12 -O atime=off -O xattr=sa -O acltype=posixacl \
      -O compression=lz4 -O canmount=off \
      -m none "${SOVEREIGN_OS_POOL_NAME}" ${devices}
    ;;
  raid1)
    log_info "creating pool ${SOVEREIGN_OS_POOL_NAME} (mirror) on: ${SOVEREIGN_OS_POOL_DEVICES}"
    # shellcheck disable=SC2086
    zpool create -o ashift=12 -O atime=off -O xattr=sa -O acltype=posixacl \
      -O compression=lz4 -O canmount=off \
      -m none "${SOVEREIGN_OS_POOL_NAME}" mirror ${SOVEREIGN_OS_POOL_DEVICES}
    ;;
  raidz|raidz2|raidz3)
    log_info "creating pool ${SOVEREIGN_OS_POOL_NAME} (${topology}) on: ${SOVEREIGN_OS_POOL_DEVICES}"
    # shellcheck disable=SC2086
    zpool create -o ashift=12 -O atime=off -O xattr=sa -O acltype=posixacl \
      -O compression=lz4 -O canmount=off \
      -m none "${SOVEREIGN_OS_POOL_NAME}" "${topology}" ${SOVEREIGN_OS_POOL_DEVICES}
    ;;
  *)
    log_error "unsupported topology: ${topology}"
    exit 1
    ;;
esac

zpool status "${SOVEREIGN_OS_POOL_NAME}"
log_info "${STEP_ID} complete"
