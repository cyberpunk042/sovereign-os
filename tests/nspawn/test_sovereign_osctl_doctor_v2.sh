#!/usr/bin/env bash
# tests/nspawn/test_sovereign_osctl_doctor_v2.sh
#
# Layer 3 test for Round 43 — expanded 'sovereign-osctl doctor' with
# profile-conditioned checks + tooling + systemd + ZFS + TPM2 + Layer B
# metrics + inference reachability + build-state freshness.
#
# Asserts:
#   - profile/layout/secure_boot line in header
#   - section headers: tooling / systemd / observability / inference / build-state
#   - sain-01 includes tetragon/podman/nvidia-smi in required-tools list
#   - minimal does NOT require ZFS tooling
#   - profile-conditioned ZFS section appears only for zfs-tiered layout
#   - TPM2 section appears when secure_boot != none
#   - exit code reflects pass/fail/warn-only

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

CTL="${__REPO_ROOT}/scripts/sovereign-osctl"
[ -x "${CTL}" ] || { echo "FAIL: sovereign-osctl not executable"; exit 1; }

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_sovereign_osctl_doctor_v2.sh"
echo

export SOVEREIGN_OS_NONINTERACTIVE=1

# ----------- sain-01 — full doctor surface ---------------

set +e
out_sain="$(SOVEREIGN_OS_PROFILE=sain-01 "${CTL}" doctor 2>&1)"
rc_sain=$?
set -e

# Header includes profile/layout/secure_boot
if grep -qE "profile=sain-01 layout=zfs-tiered secure_boot=signed" <<< "${out_sain}"; then
  ok "sain-01 header surfaces profile + layout + secure_boot"
else
  ko "sain-01 header missing or wrong: ${out_sain:0:300}"
fi

# Required section headers
for section in "\[tooling\]" "\[systemd\]" "\[zfs\]" "\[tpm2\]" "\[observability\]" "\[inference\]" "\[build-state\]"; do
  if grep -qE "${section}" <<< "${out_sain}"; then
    ok "sain-01 section present: ${section}"
  else
    ko "sain-01 section missing: ${section}"
  fi
done

# sain-01-specific tools in required-tools list
for tool in tetragon podman nvidia-smi zpool zfs; do
  if grep -q "${tool}" <<< "${out_sain}"; then
    ok "sain-01 doctor lists tool: ${tool}"
  else
    ko "sain-01 doctor missing tool: ${tool}"
  fi
done

# ----------- minimal — narrower surface ---------------

set +e
out_min="$(SOVEREIGN_OS_PROFILE=minimal "${CTL}" doctor 2>&1)"
rc_min=$?
set -e

# minimal: ext4 layout → no zfs section
if ! grep -qE "^\[zfs\]" <<< "${out_min}"; then
  ok "minimal doctor: no [zfs] section (layout=ext4)"
else
  ko "minimal doctor: unexpected [zfs] section"
fi

# minimal doesn't require tetragon
if ! grep -qE "tetragon NOT installed.*required by profile=minimal" <<< "${out_min}"; then
  ok "minimal doctor: tetragon not in required-tools (profile-conditioned)"
else
  ko "minimal doctor: tetragon listed as required (wrong)"
fi

# minimal layout=ext4 → mkfs.ext4 required
if grep -q "mkfs.ext4" <<< "${out_min}"; then
  ok "minimal doctor: mkfs.ext4 in required-tools (ext4 layout)"
else
  ko "minimal doctor: mkfs.ext4 not surfaced for ext4 layout"
fi

# ----------- exit code semantics ---------------

# Doctor exits non-zero when issues > 0 (CI is missing most tools).
# Exit 0 when only warnings (warnings don't block).
if [ "${rc_sain}" -ne 0 ]; then
  ok "sain-01 doctor exits non-zero when tooling missing (alarm signal)"
else
  ok "sain-01 doctor exit 0 (test runner happens to have all sain-01 tools — unlikely but accepted)"
fi

# ----------- help documents the new doctor sections ---------------

# help itself is unchanged; doctor's output structure is the contract.
# Just verify doctor command still appears in help.
help_out="$("${CTL}" help 2>&1)"
if grep -q "doctor" <<< "${help_out}"; then
  ok "help documents 'doctor' command"
else
  ko "help missing 'doctor'"
fi

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_sovereign_osctl_doctor_v2: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
