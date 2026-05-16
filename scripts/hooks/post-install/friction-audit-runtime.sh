#!/usr/bin/env bash
# scripts/hooks/post-install/friction-audit-runtime.sh
#
# Runtime hardware audit on the installed system. Verifies the
# profile's hardware target matches actual lspci / dmidecode / lscpu
# state. Runs at first boot and on demand (operator can invoke
# anytime).
#
# Corrects the L0 dump's bug per SDD-006: this version scopes the
# x8/x8 GPU lane check to the actual GPU BDFs, not "every x8 link
# anywhere in lspci". GPU BDFs are computed by matching PCI IDs
# from the profile against `lspci -nn` output.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

STEP_ID="friction-audit-runtime"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

log_step_header "${STEP_ID}" "runtime friction audit (profile=${SOVEREIGN_OS_PROFILE})"

fail=0
warn=0

# ----------------- CPU checks -----------------

march="$(profile_field hardware.cpu.march)"
case "${march}" in
  znver5)
    if grep -q "model name.*Ryzen.*9\|Zen 5\|znver5" /proc/cpuinfo; then
      log_info "  PASS — CPU matches profile march=znver5"
    else
      log_warn "  WARN — running CPU may not be Zen 5 (profile march=znver5)"
      warn=$((warn + 1))
    fi
    ;;
esac

# Required AVX-512 features
required_features="$(python3 -c "
import os, yaml
with open(os.environ['SOVEREIGN_OS_PROFILE_FILE']) as f:
    d = yaml.safe_load(f)
print(' '.join((d['hardware']['cpu'].get('features') or {}).get('required') or []))
")"

for feat in ${required_features}; do
  if grep -qw "${feat}" /proc/cpuinfo; then
    log_info "  PASS — CPU feature ${feat} present"
  else
    log_error "  FAIL — CPU feature ${feat} missing (profile requires)"
    fail=$((fail + 1))
  fi
done

# ----------------- GPU + PCIe x8/x8 lanes check (corrected) -----------------

require_command lspci

# Collect expected GPU PCI IDs from profile
gpu_ids="$(python3 -c "
import os, yaml
with open(os.environ['SOVEREIGN_OS_PROFILE_FILE']) as f:
    d = yaml.safe_load(f)
for g in (d.get('hardware') or {}).get('gpu') or []:
    pid = g.get('pci_id', '')
    if pid and '?' not in pid:
        print(pid)
")"

if [ -z "${gpu_ids}" ]; then
  log_warn "  WARN — no concrete GPU PCI IDs in profile (Q6-A may still be open for Blackwell)"
  warn=$((warn + 1))
else
  for pid in ${gpu_ids}; do
    # Find BDF for this PCI ID
    bdf="$(lspci -nn | grep -i "\[${pid}\]" | awk '{print $1}' | head -1)"
    if [ -z "${bdf}" ]; then
      log_warn "  WARN — GPU with PCI ID ${pid} not present on this system"
      warn=$((warn + 1))
      continue
    fi
    # Check link width via lspci -vvv on the specific BDF
    width="$(lspci -vvv -s "${bdf}" 2>/dev/null | grep -i 'lnksta:' | grep -oP 'Width x\K[0-9]+' | head -1)"
    if [ -z "${width}" ]; then
      log_warn "  WARN — could not read link width for ${pid} (BDF ${bdf})"
      warn=$((warn + 1))
      continue
    fi
    if [ "${width}" -ge 8 ]; then
      log_info "  PASS — GPU ${pid} (BDF ${bdf}) at PCIe x${width}"
    else
      log_error "  FAIL — GPU ${pid} (BDF ${bdf}) at PCIe x${width} (expected ≥ x8). Check M.2_2 bifurcation."
      fail=$((fail + 1))
    fi
  done
fi

# ----------------- IOMMU groups separation (sain-01 specific) -----------------

if [ "${SOVEREIGN_OS_PROFILE}" = "sain-01" ] && [ -d /sys/kernel/iommu_groups ]; then
  log_info "  checking IOMMU group separation"
  primary_pid="$(python3 -c "
import os, yaml
with open(os.environ['SOVEREIGN_OS_PROFILE_FILE']) as f:
    d = yaml.safe_load(f)
for g in (d.get('hardware') or {}).get('gpu') or []:
    if g.get('role') == 'primary':
        print(g.get('pci_id', ''))
        break
")"
  vfio_pid="$(python3 -c "
import os, yaml
with open(os.environ['SOVEREIGN_OS_PROFILE_FILE']) as f:
    d = yaml.safe_load(f)
for g in (d.get('hardware') or {}).get('gpu') or []:
    if g.get('role') == 'vfio':
        print(g.get('pci_id', ''))
        break
")"
  if [ -n "${primary_pid}" ] && [ -n "${vfio_pid}" ] && [ "${primary_pid}" != "${vfio_pid}" ]; then
    primary_bdf="$(lspci -nn | grep -i "\[${primary_pid}\]" | awk '{print $1}' | head -1)"
    vfio_bdf="$(lspci -nn | grep -i "\[${vfio_pid}\]" | awk '{print $1}' | head -1)"
    if [ -n "${primary_bdf}" ] && [ -n "${vfio_bdf}" ]; then
      primary_group="$(readlink /sys/bus/pci/devices/0000:${primary_bdf/:/:}/iommu_group 2>/dev/null | xargs -n1 basename)"
      vfio_group="$(readlink /sys/bus/pci/devices/0000:${vfio_bdf/:/:}/iommu_group 2>/dev/null | xargs -n1 basename)"
      if [ -n "${primary_group}" ] && [ -n "${vfio_group}" ] && [ "${primary_group}" != "${vfio_group}" ]; then
        log_info "  PASS — primary GPU (group ${primary_group}) and VFIO GPU (group ${vfio_group}) in distinct IOMMU groups"
      else
        log_error "  FAIL — GPUs share IOMMU group ${primary_group} (need distinct for VFIO)"
        fail=$((fail + 1))
      fi
    fi
  fi
fi

# ----------------- Memory check -----------------

if command -v dmidecode >/dev/null 2>&1; then
  installed_mem_gb=$(($(grep MemTotal /proc/meminfo | awk '{print $2}') / 1024 / 1024))
  min_gb="$(profile_field hardware.memory.minimum_gb)"
  if [ -n "${min_gb}" ] && [ "${installed_mem_gb}" -ge "${min_gb}" ]; then
    log_info "  PASS — memory ${installed_mem_gb}GB ≥ profile minimum ${min_gb}GB"
  else
    log_error "  FAIL — memory ${installed_mem_gb}GB < profile minimum ${min_gb}GB"
    fail=$((fail + 1))
  fi
fi

# ----------------- Result -----------------

emit_metric_set friction-audit \
  '# HELP sovereign_os_friction_audit_failures Number of failing checks in last runtime friction audit' \
  '# TYPE sovereign_os_friction_audit_failures gauge' \
  "sovereign_os_friction_audit_failures{profile=\"${SOVEREIGN_OS_PROFILE}\"} ${fail}" \
  '# HELP sovereign_os_friction_audit_warnings Number of warnings in last runtime friction audit' \
  '# TYPE sovereign_os_friction_audit_warnings gauge' \
  "sovereign_os_friction_audit_warnings{profile=\"${SOVEREIGN_OS_PROFILE}\"} ${warn}" \
  '# HELP sovereign_os_friction_audit_last_run_timestamp Unix timestamp of the last friction-audit run' \
  '# TYPE sovereign_os_friction_audit_last_run_timestamp gauge' \
  "sovereign_os_friction_audit_last_run_timestamp{profile=\"${SOVEREIGN_OS_PROFILE}\"} $(date +%s)"

echo
if [ "${fail}" -eq 0 ]; then
  log_info "friction-audit-runtime: PASS (${warn} warnings)"
  exit 0
else
  log_error "friction-audit-runtime: FAIL (${fail} failures, ${warn} warnings)"
  exit 1
fi
