#!/usr/bin/env bash
# tests/nspawn/test_virt_info.sh — R255 (SDD-026 Z-19).
# Virtualization + PCIe + container-runtime probe.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/virt-info.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_virt_info.sh"
echo

[ -x "${SCRIPT}" ] && ok "virt-info.py executable" \
  || { ko "missing virt-info.py"; exit 1; }
grep -q "R255" "${SCRIPT}" && ok "virt-info.py cites R255" || ko "R255 missing"
grep -q "^  virt-info)" "${OSCTL}" \
  && ok "osctl bridges 'virt-info'" || ko "osctl dispatch missing"
grep -q "virt-info show" "${OSCTL}" \
  && ok "osctl help documents 'virt-info'" || ko "osctl help missing"

TMP="$(mktemp -d -t r255.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT

# ---- cpu --json: schema stable + relevant flags map ----
out="$(python3 "${SCRIPT}" cpu --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R255', d
assert d['vector'].startswith('SDD-026 Z-19'), d
for f in ('vendor_flag','virt_supported','nested_paging_supported','flags_relevant'):
    assert f in d, f'missing {f}'
# Every flag we care about is represented.
for flag in ('vmx','svm','ept','npt'):
    assert flag in d['flags_relevant'], f'missing flag {flag}'
" \
  && ok "cpu --json: vendor + virt_supported + relevant flags map" \
  || ko "cpu shape wrong"

# ---- kvm --json: 5 stable fields ----
out="$(python3 "${SCRIPT}" kvm --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R255', d
for f in ('kvm_module_loaded','kvm_intel_loaded','kvm_amd_loaded','dev_kvm_present','nested_virt'):
    assert f in d, f'missing {f}'
" \
  && ok "kvm --json: kvm/intel/amd module + /dev/kvm + nested" \
  || ko "kvm shape wrong"

# ---- iommu --json: cmdline parsing + advisory present when disabled ----
out="$(python3 "${SCRIPT}" iommu --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R255', d
for f in ('iommu_devices','iommu_enabled_sysfs','kernel_cmdline_intel_iommu_on',
         'kernel_cmdline_amd_iommu_on','kernel_cmdline_acs_override','advisory'):
    assert f in d, f'missing {f}'
# When IOMMU is OFF (typical CI), advisory non-None.
if not d['iommu_enabled_sysfs'] and not (
    d['kernel_cmdline_intel_iommu_on'] or d['kernel_cmdline_amd_iommu_on']
):
    assert d['advisory'] is not None, d
    assert 'intel_iommu' in d['advisory'] or 'amd_iommu' in d['advisory']
" \
  && ok "iommu --json: sysfs+cmdline fields + actionable advisory when off" \
  || ko "iommu shape wrong"

# ---- pci --json: graceful when lspci absent (CI) or present ----
set +e
out="$(python3 "${SCRIPT}" pci --json 2>/dev/null)"
rc=$?
set -e
# rc=0 normally; rc=2 if lspci runtime errored.
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 2 ]; then
  ok "pci --json rc ∈ {0,2} (got ${rc})"
else
  ko "pci rc unexpected ${rc}"
fi
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R255', d
# Either 'devices' / 'interesting' OR 'error' present.
assert ('interesting' in d) or ('error' in d), d
" \
  && ok "pci --json: stable shape regardless of lspci availability" \
  || ko "pci shape wrong"

# ---- runtimes --json: 6 known runtimes probed ----
out="$(python3 "${SCRIPT}" runtimes --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R255', d
names={r['name'] for r in d['runtimes']}
for needle in ('docker','podman','containerd','nerdctl','crun','runc'):
    assert needle in names, f'missing runtime {needle}'
" \
  && ok "runtimes --json: 6 container runtimes probed" \
  || ko "runtimes shape wrong"

# ---- show --json: aggregates all 5 sub-sections ----
out="$(python3 "${SCRIPT}" show --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R255', d
for s in ('cpu','kvm','iommu','pci','runtimes'):
    assert s in d, f'show missing {s}'
" \
  && ok "show --json: aggregates cpu+kvm+iommu+pci+runtimes" \
  || ko "show shape wrong"

# ---- human render: banner + key sections ----
out_h="$(python3 "${SCRIPT}" show)"
echo "${out_h}" | grep -q "R255 sovereign-os virt-info show" \
  && ok "show human banner present" || ko "banner missing"
for needle in CPU KVM IOMMU PCI; do
  echo "${out_h}" | grep -q "${needle}" \
    && ok "human render mentions ${needle}" || ko "${needle} missing"
done

# ---- osctl bridge ----
set +e
"${OSCTL}" virt-info cpu --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl virt-info cpu rc=0" \
  || ko "osctl bridge rc=${rc}"
python3 -c "
import json
d=json.load(open('${TMP}/osctl.out'))
assert d['round']=='R255', d
" \
  && ok "osctl bridge surfaces R255 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" virt-info nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown virt-info subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

echo
total=$((pass + fail))
echo "test_virt_info: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
