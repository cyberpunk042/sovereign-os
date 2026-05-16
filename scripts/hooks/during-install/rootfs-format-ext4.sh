#!/usr/bin/env bash
# scripts/hooks/during-install/rootfs-format-ext4.sh
#
# Format the rootfs device as ext4. Used for old-workstation profile
# (constrained hardware; ZFS overkill). Reads device from
# SOVEREIGN_OS_ROOTFS_DEV env var.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"

STEP_ID="rootfs-format-ext4"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

: "${SOVEREIGN_OS_ROOTFS_DEV:=}"

log_step_header "${STEP_ID}" "format rootfs (ext4)"

layout="$(profile_field hardware.storage.layout)"
if [ "${layout}" != "ext4" ]; then
  log_info "profile layout is '${layout}' (not ext4); skipping"
  exit 0
fi

if [ -z "${SOVEREIGN_OS_ROOTFS_DEV}" ]; then
  log_error "SOVEREIGN_OS_ROOTFS_DEV must be set (e.g. /dev/sda3)"
  exit 1
fi

require_root
require_command mkfs.ext4

# Refuse if device looks mounted
if mount | grep -q "^${SOVEREIGN_OS_ROOTFS_DEV} "; then
  log_error "device ${SOVEREIGN_OS_ROOTFS_DEV} is currently mounted; refusing to format"
  exit 1
fi

# Refuse without explicit confirmation
if ! confirm "Format ${SOVEREIGN_OS_ROOTFS_DEV} as ext4? THIS WIPES ALL DATA." default-no; then
  log_info "aborted by operator"
  exit 1
fi

log_info "formatting ${SOVEREIGN_OS_ROOTFS_DEV} as ext4"
mkfs.ext4 -L sovereign-rootfs "${SOVEREIGN_OS_ROOTFS_DEV}" 2>&1 | sed 's/^/  /'

log_info "${STEP_ID} complete"
