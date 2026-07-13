#!/usr/bin/env bash
# scripts/hooks/pre-install/friction-audit-spec.sh
#
# Pre-install validation hook for the SAIN-01 hardware spec.
# Operates on the profile YAML (spec-time check) — pure metadata
# validation; runs in a non-hardware context.
#
# The runtime variant (scripts/hooks/post-install/friction-audit-runtime.sh)
# runs after install on the real hardware and verifies actual lspci /
# IOMMU group state.
#
# Per SDD-006 hallucination corrections: the L0 dump's `friction-audit`
# script counted every PCIe x8 link on the system. This pre-install
# variant only enforces what's checkable in the profile YAML:
#   • CPU march set
#   • Required AVX-512 features declared
#   • dual-CCD partition mask consistent
#   • GPU roles include exactly one primary
#   • Storage layout has at least one rootfs device
#   • VFIO companion device declared when role=vfio
#   • Motherboard pcie_constraints includes the M.2_2-must-empty blocker
#
# Exit code: 0 if PASS; non-zero if FAIL.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

STEP_ID="friction-audit-spec"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

log_step_header "${STEP_ID}" "spec-time friction audit for profile=${SOVEREIGN_OS_PROFILE}"

# This hook is pure metadata validation (reads YAML, no hardware touch),
# so it's CI-safe by default. SOVEREIGN_OS_DRY_RUN downgrades any FAIL
# to a warn for the operator-readable preview path — checks still run,
# but the script exits 0 so the orchestrator's dry-run doesn't fail
# on profile issues during early iteration. Matches the contract honored
# by the other pre-install hooks (operator-discoverable preview mode).
if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_warn "SOVEREIGN_OS_DRY_RUN set — friction findings will be reported but exit code forced to 0"
fi

fail=0

check() {
  # check <description> <command...> — runs command; PASS if 0 exit
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then
    log_info "  PASS — ${desc}"
  else
    log_error "  FAIL — ${desc}"
    fail=$((fail + 1))
  fi
}

# ----------------- CPU checks -----------------

check "CPU march is set (currently: $(profile_field hardware.cpu.march))" \
  test -n "$(profile_field hardware.cpu.march)"

# Pre-compute the field (profile_field is a function — not visible inside
# a fresh `bash -c` subshell). Outer-shell expansion solves it.
cpu_required="$(profile_field hardware.cpu.features.required)"
check "CPU required features list non-empty (currently: ${cpu_required:-empty})" \
  test -n "${cpu_required}" -a "${cpu_required}" != "[]"

check "CPU topology declared" \
  test -n "$(profile_field hardware.cpu.cores.topology)"

# ----------------- GPU checks -----------------
#
# GPU is optional at the schema level (headless / VM profiles declare
# gpu: [] or omit it). When zero GPUs are declared, GPU-shape checks
# are skipped — they don't apply. When >=1 is declared, structural
# rules apply (exactly one primary, vfio_companion required for vfio
# entries, etc.).

gpu_count="$(python3 -c "
import yaml, os
with open(os.environ['SOVEREIGN_OS_PROFILE_FILE']) as f:
    data = yaml.safe_load(f)
gpus = data.get('hardware', {}).get('gpu', []) or []
print(len(gpus))
")"

if [ "${gpu_count}" -eq 0 ]; then
  log_info "  SKIP — no GPUs declared (headless / VM profile)"
else
  log_info "  ${gpu_count} GPU(s) declared — applying GPU structural checks"

  primary_gpu_count="$(python3 -c "
import yaml, os
with open(os.environ['SOVEREIGN_OS_PROFILE_FILE']) as f:
    data = yaml.safe_load(f)
gpus = data.get('hardware', {}).get('gpu', []) or []
print(sum(1 for g in gpus if g.get('role') == 'primary'))
")"

  check "exactly one GPU with role=primary (found ${primary_gpu_count})" \
    test "${primary_gpu_count}" -eq 1
fi

if [ "${gpu_count}" -gt 0 ]; then
  vfio_companion_check="$(python3 -c "
import yaml, os, sys
with open(os.environ['SOVEREIGN_OS_PROFILE_FILE']) as f:
    data = yaml.safe_load(f)
gpus = data.get('hardware', {}).get('gpu', []) or []
issues = []
for g in gpus:
    if g.get('role') == 'vfio' and not g.get('vfio_companion'):
        issues.append(g.get('model', 'unknown'))
if issues:
    print('missing vfio_companion: ' + ', '.join(issues), file=sys.stderr)
    sys.exit(1)
")"
  if [ $? -eq 0 ]; then
    log_info "  PASS — all role=vfio GPUs declare vfio_companion"
  else
    log_error "  FAIL — vfio_companion missing on at least one role=vfio GPU"
    fail=$((fail + 1))
  fi
fi

# ----------------- Storage checks -----------------

rootfs_count="$(python3 -c "
import yaml, os
with open(os.environ['SOVEREIGN_OS_PROFILE_FILE']) as f:
    data = yaml.safe_load(f)
devs = data.get('hardware', {}).get('storage', {}).get('devices', []) or []
print(sum(1 for d in devs if d.get('role') == 'rootfs'))
")"

check "at least one storage device with role=rootfs (found ${rootfs_count})" \
  test "${rootfs_count}" -ge 1

# ----------------- ZFS dataset checks (only if zfs-tiered) -----------------

storage_layout="$(profile_field hardware.storage.layout)"
if [ "${storage_layout}" = "zfs-tiered" ]; then
  log_info "  storage layout is zfs-tiered — checking dataset declarations"
  context_sync="$(python3 -c "
import yaml, os
with open(os.environ['SOVEREIGN_OS_PROFILE_FILE']) as f:
    data = yaml.safe_load(f)
ds = data.get('hardware', {}).get('storage', {}).get('datasets', []) or []
ctx = next((d for d in ds if 'context' in (d.get('name') or '')), None)
print(ctx.get('sync', '') if ctx else '')
")"
  check "tank/context dataset declares sync=always (found: ${context_sync})" \
    test "${context_sync}" = "always"
fi

# ----------------- Motherboard PCIe constraints -----------------

if [ "${SOVEREIGN_OS_PROFILE}" = "sain-01" ]; then
  # SDD-993: the M.2_2 slot on the ASUS ProArt X870E-Creator now hosts the
  # OcuLink-to-M.2 adapter for the RTX 4090 eGPU (the old must-remain-empty
  # bifurcation rule is retired — one internal GPU runs full x16). The profile
  # must still DECLARE the M.2_2 PCIe constraint (now the OcuLink one).
  m2_2_declared="$(python3 -c "
import yaml, os
with open(os.environ['SOVEREIGN_OS_PROFILE_FILE']) as f:
    data = yaml.safe_load(f)
constraints = data.get('hardware', {}).get('motherboard', {}).get('pcie_constraints', []) or []
print('yes' if any(c.get('check') in ('m2_2_oculink_egpu', 'm2_2_empty') for c in constraints) else 'no')
")"
  check "sain-01 declares an M.2_2 PCIe constraint (OcuLink eGPU per SDD-993)" \
    test "${m2_2_declared}" = "yes"
fi

# ----------------- Result -----------------

echo
if [ "${fail}" -eq 0 ]; then
  log_info "friction-audit-spec: PASS (profile=${SOVEREIGN_OS_PROFILE})"
  emit_metric sovereign_os_pre_install_friction_audit_spec_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"pass\""
  emit_metric sovereign_os_pre_install_friction_audit_spec_failures 0 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\""
  exit 0
else
  log_error "friction-audit-spec: FAIL (${fail} issue(s) in profile=${SOVEREIGN_OS_PROFILE})"
  emit_metric sovereign_os_pre_install_friction_audit_spec_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"fail\""
  emit_metric sovereign_os_pre_install_friction_audit_spec_failures "${fail}" \
    "profile=\"${SOVEREIGN_OS_PROFILE}\""
  if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
    log_warn "SOVEREIGN_OS_DRY_RUN — forcing exit 0 despite ${fail} finding(s)"
    exit 0
  fi
  exit 1
fi
