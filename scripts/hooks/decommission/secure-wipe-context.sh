#!/usr/bin/env bash
# scripts/hooks/decommission/secure-wipe-context.sh
#
# Decommission step: wipe the state-fabric (tank/context) BEFORE pool
# destroy. Used to honor "I want things... at all stages of lifecycle"
# (operator verbatim). Idempotent. Destructive — confirms first.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"

: "${SOVEREIGN_OS_POOL_NAME:=tank}"
: "${SOVEREIGN_OS_CONTEXT_PATH:=/mnt/vault/context}"

log_step_header "secure-wipe-context" "wipe state-fabric"

require_root

# Operator standing mandate: destructive operations require explicit
# SOVEREIGN_OS_CONFIRM_DESTROY=YES env var (matches sibling
# secure-wipe.sh + zfs-pool-destroy.sh hooks). Defense-in-depth alongside
# the interactive confirm() prompt below.
if [ "${SOVEREIGN_OS_CONFIRM_DESTROY:-}" != "YES" ]; then
  log_error "secure-wipe-context requires SOVEREIGN_OS_CONFIRM_DESTROY=YES env var"
  log_error "  Set: SOVEREIGN_OS_CONFIRM_DESTROY=YES $0"
  exit 1
fi

if ! confirm "Securely wipe ${SOVEREIGN_OS_CONTEXT_PATH}? THIS DESTROYS state-fabric DATA." default-no; then
  log_info "wipe aborted by operator"
  exit 1
fi

if [ -d "${SOVEREIGN_OS_CONTEXT_PATH}" ]; then
  # Find all files; shred each then unlink
  find "${SOVEREIGN_OS_CONTEXT_PATH}" -type f -print0 | xargs -0 -r shred -u -n 3 -z 2>&1 | tail -10
  find "${SOVEREIGN_OS_CONTEXT_PATH}" -depth -type d -empty -delete 2>/dev/null || true
  log_info "state-fabric files shredded"
fi

# Snapshot destroy (if ZFS)
if zfs list "${SOVEREIGN_OS_POOL_NAME}/context" >/dev/null 2>&1; then
  zfs list -t snapshot -H -o name "${SOVEREIGN_OS_POOL_NAME}/context" | while read -r snap; do
    zfs destroy "${snap}" || true
  done
  log_info "ZFS snapshots of tank/context destroyed"
fi

log_info "secure-wipe-context complete"
