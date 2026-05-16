#!/usr/bin/env bash
# scripts/hooks/recurrent/zfs-scrub.sh
#
# Weekly ZFS scrub. Called by systemd timer (Stage 2+ installs the
# timer unit). Idempotent — skips if a scrub is already in progress.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"

: "${SOVEREIGN_OS_POOL_NAME:=tank}"

log_step_header "zfs-scrub" "weekly ZFS scrub of ${SOVEREIGN_OS_POOL_NAME}"

require_root
require_command zpool

if ! zpool list "${SOVEREIGN_OS_POOL_NAME}" >/dev/null 2>&1; then
  log_warn "pool ${SOVEREIGN_OS_POOL_NAME} not present; nothing to scrub"
  exit 0
fi

# Skip if scrub in progress
if zpool status "${SOVEREIGN_OS_POOL_NAME}" | grep -qi "scrub in progress"; then
  log_info "scrub already in progress; skipping new start"
  exit 0
fi

log_info "starting scrub on ${SOVEREIGN_OS_POOL_NAME}"
zpool scrub "${SOVEREIGN_OS_POOL_NAME}"

log_info "scrub started; monitor with 'zpool status ${SOVEREIGN_OS_POOL_NAME}'"
