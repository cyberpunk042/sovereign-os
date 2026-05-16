#!/usr/bin/env bash
# scripts/hooks/decommission/zfs-pool-destroy.sh
#
# Decommission step: destroy the ZFS pool. Idempotent. Destructive —
# confirms first AND requires SOVEREIGN_OS_CONFIRM_DESTROY=YES env.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"

: "${SOVEREIGN_OS_POOL_NAME:=tank}"

log_step_header "zfs-pool-destroy" "destroy pool ${SOVEREIGN_OS_POOL_NAME}"

require_root

if [ "${SOVEREIGN_OS_CONFIRM_DESTROY:-}" != "YES" ]; then
  log_error "Pool destroy requires SOVEREIGN_OS_CONFIRM_DESTROY=YES env var"
  log_error "  This protects against accidental invocation."
  exit 1
fi

if ! confirm "Destroy ZFS pool ${SOVEREIGN_OS_POOL_NAME}? ALL DATA WILL BE LOST." default-no; then
  log_info "aborted by operator"
  exit 1
fi

if ! zpool list "${SOVEREIGN_OS_POOL_NAME}" >/dev/null 2>&1; then
  log_info "pool ${SOVEREIGN_OS_POOL_NAME} does not exist; nothing to destroy"
  exit 0
fi

# Unmount any mounted datasets first
zfs unmount -a 2>/dev/null || true
zpool export "${SOVEREIGN_OS_POOL_NAME}" 2>/dev/null || true

log_info "destroying pool ${SOVEREIGN_OS_POOL_NAME}"
zpool destroy -f "${SOVEREIGN_OS_POOL_NAME}"

log_info "zfs-pool-destroy complete"
