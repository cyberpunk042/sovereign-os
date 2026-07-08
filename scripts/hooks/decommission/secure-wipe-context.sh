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
  # IMPORTANT: shred / in-place overwrite does NOT securely erase on ZFS. ZFS is
  # copy-on-write, compressed (zstd-9), and keeps copies=2 + snapshots — an
  # overwrite writes NEW blocks and leaves the originals (and the second copy,
  # and any snapshot) intact on the NVMe. Worse, each shred pass writes MORE
  # copies of the sensitive state-fabric to disk. So this step does an honest
  # LOGICAL removal only; TRUE block erasure on this unencrypted pool is the
  # device-level hardware secure-erase in secure-wipe.sh (nvme format --ses=1 /
  # blkdiscard), the only method effective against ZFS CoW.
  find "${SOVEREIGN_OS_CONTEXT_PATH}" -type f -print0 | xargs -0 -r rm -f 2>&1 | tail -10
  find "${SOVEREIGN_OS_CONTEXT_PATH}" -depth -type d -empty -delete 2>/dev/null || true
  log_info "state-fabric files removed (logical) — block-level secure erasure is performed by secure-wipe.sh (nvme secure-erase); shred is ineffective on ZFS CoW"
fi

# Snapshot destroy (if ZFS)
if zfs list "${SOVEREIGN_OS_POOL_NAME}/context" >/dev/null 2>&1; then
  zfs list -t snapshot -H -o name "${SOVEREIGN_OS_POOL_NAME}/context" | while read -r snap; do
    zfs destroy "${snap}" || true
  done
  log_info "ZFS snapshots of tank/context destroyed"
fi

log_info "secure-wipe-context complete"
