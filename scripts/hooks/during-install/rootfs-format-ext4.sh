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
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

STEP_ID="rootfs-format-ext4"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

: "${SOVEREIGN_OS_ROOTFS_DEV:=}"

log_step_header "${STEP_ID}" "format rootfs (ext4)"

emit_format_metric() {
  emit_metric sovereign_os_during_install_rootfs_format_total 1 \
    "device=\"${SOVEREIGN_OS_ROOTFS_DEV:-unset}\",result=\"$1\""
}

layout="$(profile_field hardware.storage.layout)"
if [ "${layout}" != "ext4" ]; then
  log_info "profile layout is '${layout}' (not ext4); skipping"
  emit_format_metric skip-layout
  exit 0
fi

if [ -z "${SOVEREIGN_OS_ROOTFS_DEV}" ]; then
  log_error "SOVEREIGN_OS_ROOTFS_DEV must be set (e.g. /dev/sda3)"
  emit_format_metric missing-device
  exit 1
fi

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN — would mkfs.ext4 -L sovereign-rootfs ${SOVEREIGN_OS_ROOTFS_DEV}"
  emit_format_metric skip-dry-run
  exit 0
fi

require_root
require_command mkfs.ext4

# Refuse if device looks mounted
if mount | grep -q "^${SOVEREIGN_OS_ROOTFS_DEV} "; then
  log_error "device ${SOVEREIGN_OS_ROOTFS_DEV} is currently mounted; refusing to format"
  emit_format_metric refuse-mounted
  exit 1
fi

# Refuse without explicit confirmation (SOVEREIGN_OS_ASSUME_YES bypass
# for scripted installer flows)
if [ "${SOVEREIGN_OS_ASSUME_YES:-}" != "1" ]; then
  if ! confirm "Format ${SOVEREIGN_OS_ROOTFS_DEV} as ext4? THIS WIPES ALL DATA." default-no; then
    log_info "aborted by operator"
    emit_format_metric refuse-confirm
    exit 1
  fi
fi

log_info "formatting ${SOVEREIGN_OS_ROOTFS_DEV} as ext4"
if mkfs.ext4 -L sovereign-rootfs "${SOVEREIGN_OS_ROOTFS_DEV}" 2>&1 | sed 's/^/  /'; then
  emit_format_metric success
  log_info "${STEP_ID} complete"
else
  rc=${PIPESTATUS[0]}
  log_error "mkfs.ext4 failed (rc=${rc})"
  emit_format_metric fail
  exit 1
fi
