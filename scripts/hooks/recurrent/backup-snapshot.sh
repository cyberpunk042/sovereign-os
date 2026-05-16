#!/usr/bin/env bash
# scripts/hooks/recurrent/backup-snapshot.sh
#
# Daily ZFS snapshot of tank/context (the irreplaceable state-fabric
# per SDD-017). Snapshot retention: configurable. Snapshot-replicate
# to external storage is operator-driven (binding plan in SDD-017,
# not implemented here).
#
# Snapshot naming: tank/context@sovereign-YYYY-MM-DDTHH:MM:SS
# Retention: keep the latest SOVEREIGN_OS_SNAPSHOT_KEEP (default 30)
# snapshots; destroy older ones.
#
# Honors SOVEREIGN_OS_DRY_RUN=1.
#
# Tunable env:
#   SOVEREIGN_OS_POOL_NAME          default: tank
#   SOVEREIGN_OS_SNAPSHOT_DATASET   default: tank/context
#   SOVEREIGN_OS_SNAPSHOT_PREFIX    default: sovereign
#   SOVEREIGN_OS_SNAPSHOT_KEEP      default: 30 (latest N to retain)

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

: "${SOVEREIGN_OS_POOL_NAME:=tank}"
: "${SOVEREIGN_OS_SNAPSHOT_DATASET:=tank/context}"
: "${SOVEREIGN_OS_SNAPSHOT_PREFIX:=sovereign}"
: "${SOVEREIGN_OS_SNAPSHOT_KEEP:=30}"

log_step_header "backup-snapshot" "snapshot ${SOVEREIGN_OS_SNAPSHOT_DATASET} (keep latest ${SOVEREIGN_OS_SNAPSHOT_KEEP})"

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN — would snapshot ${SOVEREIGN_OS_SNAPSHOT_DATASET}@${SOVEREIGN_OS_SNAPSHOT_PREFIX}-<ts>"
  log_info "DRY-RUN — would prune snapshots beyond keep=${SOVEREIGN_OS_SNAPSHOT_KEEP}"
  exit 0
fi

emit_metrics() {
  local created="$1" pruned="$2" total="$3"
  emit_metric_set backup-snapshot \
    '# HELP sovereign_os_snapshot_count Total snapshots present after this run' \
    '# TYPE sovereign_os_snapshot_count gauge' \
    "sovereign_os_snapshot_count{dataset=\"${SOVEREIGN_OS_SNAPSHOT_DATASET}\"} ${total}" \
    '# HELP sovereign_os_snapshot_last_created_timestamp Unix timestamp of the last successful snapshot' \
    '# TYPE sovereign_os_snapshot_last_created_timestamp gauge' \
    "sovereign_os_snapshot_last_created_timestamp{dataset=\"${SOVEREIGN_OS_SNAPSHOT_DATASET}\"} $(date +%s)" \
    '# HELP sovereign_os_snapshot_pruned_total Snapshots pruned in the last run' \
    '# TYPE sovereign_os_snapshot_pruned_total gauge' \
    "sovereign_os_snapshot_pruned_total{dataset=\"${SOVEREIGN_OS_SNAPSHOT_DATASET}\"} ${pruned}" \
    '# HELP sovereign_os_snapshot_created_total Snapshots created in the last run (0 or 1)' \
    '# TYPE sovereign_os_snapshot_created_total gauge' \
    "sovereign_os_snapshot_created_total{dataset=\"${SOVEREIGN_OS_SNAPSHOT_DATASET}\"} ${created}"
}

# Graceful no-op when ZFS isn't installed (test runners, ext4 profiles)
if ! command -v zfs >/dev/null 2>&1; then
  log_warn "zfs binary not available — not a ZFS-tiered profile; skipping"
  emit_metrics 0 0 0
  exit 0
fi

if ! zfs list "${SOVEREIGN_OS_SNAPSHOT_DATASET}" >/dev/null 2>&1; then
  log_warn "dataset ${SOVEREIGN_OS_SNAPSHOT_DATASET} not present; skipping"
  emit_metrics 0 0 0
  exit 0
fi

snap_name="${SOVEREIGN_OS_SNAPSHOT_DATASET}@${SOVEREIGN_OS_SNAPSHOT_PREFIX}-$(date -u +%Y-%m-%dT%H:%M:%S)"

require_root

# Create the new snapshot
log_info "creating snapshot: ${snap_name}"
zfs snapshot "${snap_name}"

# Prune oldest beyond the keep window
mapfile -t all_snaps < <(zfs list -H -o name -t snapshot \
  -s creation "${SOVEREIGN_OS_SNAPSHOT_DATASET}" \
  | grep "@${SOVEREIGN_OS_SNAPSHOT_PREFIX}-")

total="${#all_snaps[@]}"
pruned=0
if [ "${total}" -gt "${SOVEREIGN_OS_SNAPSHOT_KEEP}" ]; then
  excess=$((total - SOVEREIGN_OS_SNAPSHOT_KEEP))
  log_info "pruning ${excess} snapshot(s) beyond keep=${SOVEREIGN_OS_SNAPSHOT_KEEP}"
  for ((i = 0; i < excess; i++)); do
    log_info "  destroying: ${all_snaps[$i]}"
    zfs destroy "${all_snaps[$i]}" || log_warn "    failed to destroy ${all_snaps[$i]}"
    pruned=$((pruned + 1))
  done
fi

final_count=$((total + 1 - pruned))
log_info "snapshot complete: created 1, pruned ${pruned}, total ${final_count}"
emit_metrics 1 "${pruned}" "${final_count}"
exit 0
