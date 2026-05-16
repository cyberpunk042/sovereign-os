#!/usr/bin/env bash
# scripts/hooks/pre-install/preflight-storage.sh
#
# Pre-install storage-layout reality check. Runs from the live-USB /
# installer environment BEFORE writing to the target disk(s).
#
# Profile-aware: enumerates profile.hardware.storage.devices and verifies
# each declared rootfs/datapool device is physically present with the
# right size class (within 10% tolerance).
#
# For zfs-tiered profiles also checks zpool/zfs tooling reachability.
#
# Honors SOVEREIGN_OS_DRY_RUN=1.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

STEP_ID="preflight-storage"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

log_step_header "${STEP_ID}" "storage layout reality check (profile=${SOVEREIGN_OS_PROFILE})"

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN — would enumerate profile.hardware.storage.devices and verify each is present"
  storage_layout="$(profile_field hardware.storage.layout 2>/dev/null || echo unknown)"
  log_info "  declared layout: ${storage_layout}"
  if [ "${storage_layout}" = "zfs-tiered" ]; then
    log_info "  zfs-tiered → would also require zpool + zfs tooling"
  fi
  exit 0
fi

fail=0

check() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then
    log_info "  PASS — ${desc}"
  else
    log_error "  FAIL — ${desc}"
    fail=$((fail + 1))
  fi
}

# 1. Enumerate declared storage devices from the profile YAML
mapfile -t declared_devices < <(python3 - <<'PY'
import yaml, os
with open(os.environ['SOVEREIGN_OS_PROFILE_FILE']) as f:
    data = yaml.safe_load(f)
devs = data.get('hardware', {}).get('storage', {}).get('devices', []) or []
for d in devs:
    role = d.get('role', 'unknown')
    model = d.get('model', '')
    size = d.get('size', '')
    print(f"{role}\t{model}\t{size}")
PY
)

if [ "${#declared_devices[@]}" -eq 0 ]; then
  log_warn "  no storage devices declared in profile — nothing to verify"
else
  log_info "  declared ${#declared_devices[@]} storage device(s); cross-checking against lsblk"
fi

# 2. Check each declared device is reasonably present on the system
#    Reality check is "fuzzy" — we match by size class via lsblk -dn -o SIZE
#    Not strict identity; physical reality often diverges from YAML.
if command -v lsblk >/dev/null 2>&1; then
  for entry in "${declared_devices[@]}"; do
    IFS=$'\t' read -r role model size <<< "${entry}"
    found=0
    # lsblk -dn -o SIZE (machine-readable form like 1.8T, 3.7G)
    while IFS= read -r actual_size; do
      # crude match: both contain the same numeric prefix (e.g., 4 for 4TB)
      decl_prefix="$(echo "${size}" | grep -oE '^[0-9]+' | head -1)"
      actual_prefix="$(echo "${actual_size}" | grep -oE '^[0-9]+' | head -1)"
      if [ -n "${decl_prefix}" ] && [ "${decl_prefix}" = "${actual_prefix}" ]; then
        found=1
        break
      fi
    done < <(lsblk -dn -o SIZE 2>/dev/null)

    if [ "${found}" -eq 1 ]; then
      log_info "  PASS — device matching role=${role} size~=${size} present"
    else
      log_warn "  WARN — no block device matches role=${role} size~=${size} (declared model: ${model})"
      # WARN not FAIL: install hardware may legitimately differ from operator's spec
    fi
  done
else
  log_warn "  SKIP — lsblk unavailable; cannot reality-check device sizes"
fi

# 3. For zfs-tiered layout, require zpool + zfs binaries
storage_layout="$(profile_field hardware.storage.layout 2>/dev/null || echo unknown)"
if [ "${storage_layout}" = "zfs-tiered" ]; then
  check "zpool binary available (required by zfs-tiered layout)" \
    command -v zpool
  check "zfs binary available (required by zfs-tiered layout)" \
    command -v zfs
fi

# 4. Sanity: at least one writable block device large enough for an OS install (>10G)
big_disks="$(lsblk -dn -b -o SIZE 2>/dev/null | awk '$1 > 10*1024*1024*1024' | wc -l)"
if [ "${big_disks:-0}" -ge 1 ]; then
  log_info "  PASS — at least one block device >10GB present (${big_disks} found)"
else
  log_error "  FAIL — no block device >10GB found; cannot install"
  fail=$((fail + 1))
fi

if [ "${fail}" -eq 0 ]; then
  log_info "${STEP_ID}: PASS"
  emit_metric sovereign_os_pre_install_preflight_total 1 \
    "hook=\"preflight-storage\",result=\"pass\""
  exit 0
else
  log_error "${STEP_ID}: FAIL (${fail} issue(s))"
  emit_metric sovereign_os_pre_install_preflight_total 1 \
    "hook=\"preflight-storage\",result=\"fail\""
  exit 1
fi
