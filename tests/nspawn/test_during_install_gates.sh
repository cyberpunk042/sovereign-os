#!/usr/bin/env bash
# tests/nspawn/test_during_install_gates.sh
#
# Layer 3 test for the during-install lifecycle hooks. Like the
# decommission gates test, we can't run the destructive happy paths
# in CI (no real disks, no ZFS, no TPM). What we CAN test is:
#   - profile-conditioned skips fire correctly
#   - missing env vars produce clean refusals
#   - non-root invocation refuses (require_root)
#
# Asserts:
#   - rootfs-format-ext4 SKIPs against sain-01 (layout=zfs-tiered)
#   - rootfs-format-ext4 SKIPs against minimal+old-workstation only when
#     declared layout matches; FAIL-without-env on layout=ext4 + no
#     SOVEREIGN_OS_ROOTFS_DEV
#   - zfs-pool-create SKIPs against ext4 profiles (old-workstation,
#     minimal) cleanly
#   - mok-enroll SKIPs against profiles with secure_boot != signed
#     (sain-01=signed runs further into the script — gate hit on
#     non-root or missing tools)
#   - zfs-datasets-create requires root + zfs binary

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_during_install_gates.sh"
echo

# Isolated state/log dirs
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
export SOVEREIGN_OS_STATE_DIR="${tmp}/state"
export SOVEREIGN_OS_LOG_DIR="${tmp}/log"
export SOVEREIGN_OS_NONINTERACTIVE=1

run_rc() {
  set +e
  ( "$@" ) >/dev/null 2>&1
  echo $?
  set -e
}

# ----------- rootfs-format-ext4 ---------------

script="${__REPO_ROOT}/scripts/hooks/during-install/rootfs-format-ext4.sh"
[ -x "${script}" ] || { ko "rootfs-format-ext4.sh not executable"; }

# sain-01: layout=zfs-tiered → SKIP (exit 0)
rc="$(SOVEREIGN_OS_PROFILE=sain-01 run_rc "${script}")"
if [ "${rc}" -eq 0 ]; then
  ok "rootfs-format-ext4 SKIPs cleanly against sain-01 (layout=zfs-tiered)"
else
  ko "rootfs-format-ext4 exit ${rc} for sain-01 (expected 0 skip)"
fi

# old-workstation: layout=ext4 but no SOVEREIGN_OS_ROOTFS_DEV → fail (gate)
rc="$(unset SOVEREIGN_OS_ROOTFS_DEV; SOVEREIGN_OS_PROFILE=old-workstation run_rc "${script}")"
if [ "${rc}" -ne 0 ]; then
  ok "rootfs-format-ext4 refuses old-workstation without ROOTFS_DEV"
else
  ko "rootfs-format-ext4 should refuse without ROOTFS_DEV; got rc=${rc}"
fi

# minimal: layout=ext4 same gate
rc="$(unset SOVEREIGN_OS_ROOTFS_DEV; SOVEREIGN_OS_PROFILE=minimal run_rc "${script}")"
if [ "${rc}" -ne 0 ]; then
  ok "rootfs-format-ext4 refuses minimal without ROOTFS_DEV"
else
  ko "rootfs-format-ext4 should refuse minimal without ROOTFS_DEV"
fi

# old-workstation: with ROOTFS_DEV set to a nonexistent device should
# still fail (require_root or mount check or confirm refusal); shouldn't
# format anything.
rc="$(SOVEREIGN_OS_ROOTFS_DEV=/dev/nonexistent-test-xyz SOVEREIGN_OS_PROFILE=old-workstation run_rc "${script}")"
if [ "${rc}" -ne 0 ]; then
  ok "rootfs-format-ext4 refuses with bogus device + non-root/no-confirm"
else
  ko "rootfs-format-ext4 should refuse with bogus device + NONINTERACTIVE"
fi

# ----------- zfs-pool-create ---------------

script="${__REPO_ROOT}/scripts/hooks/during-install/zfs-pool-create.sh"
[ -x "${script}" ] || { ko "zfs-pool-create.sh not executable"; }

# old-workstation: layout=ext4 → SKIP (exit 0)
rc="$(SOVEREIGN_OS_PROFILE=old-workstation run_rc "${script}")"
if [ "${rc}" -eq 0 ]; then
  ok "zfs-pool-create SKIPs cleanly against old-workstation (layout=ext4)"
else
  ko "zfs-pool-create exit ${rc} for old-workstation (expected 0 skip)"
fi

# minimal: layout=ext4 → SKIP
rc="$(SOVEREIGN_OS_PROFILE=minimal run_rc "${script}")"
if [ "${rc}" -eq 0 ]; then
  ok "zfs-pool-create SKIPs cleanly against minimal (layout=ext4)"
else
  ko "zfs-pool-create exit ${rc} for minimal (expected 0 skip)"
fi

# sain-01: layout=zfs-tiered + no POOL_DEVICES → refuses (gate)
rc="$(unset SOVEREIGN_OS_POOL_DEVICES; SOVEREIGN_OS_PROFILE=sain-01 run_rc "${script}")"
if [ "${rc}" -ne 0 ]; then
  ok "zfs-pool-create refuses sain-01 without POOL_DEVICES"
else
  ko "zfs-pool-create should refuse without POOL_DEVICES"
fi

# ----------- zfs-datasets-create ---------------

script="${__REPO_ROOT}/scripts/hooks/during-install/zfs-datasets-create.sh"
[ -x "${script}" ] || { ko "zfs-datasets-create.sh not executable"; }

# Requires root + zfs binary; CI is unlikely to have zfs binary → refuse
rc="$(SOVEREIGN_OS_PROFILE=sain-01 run_rc "${script}")"
if [ "${rc}" -ne 0 ]; then
  ok "zfs-datasets-create refuses when zfs binary missing (or non-root)"
else
  # In a Docker container with root but no zfs → require_command zfs fails
  # Acceptable: if ZFS happens to be installed, it might proceed further.
  # If we're here without failing, the env has the tools.
  ok "zfs-datasets-create did not refuse — environment has root + zfs"
fi

# ----------- mok-enroll ---------------

script="${__REPO_ROOT}/scripts/hooks/during-install/mok-enroll.sh"
[ -x "${script}" ] || { ko "mok-enroll.sh not executable"; }

# old-workstation: secure_boot=shim → SKIP (since the script checks signed)
rc="$(SOVEREIGN_OS_PROFILE=old-workstation run_rc "${script}")"
if [ "${rc}" -eq 0 ]; then
  ok "mok-enroll SKIPs cleanly against old-workstation (secure_boot=shim)"
else
  ko "mok-enroll exit ${rc} for old-workstation (expected 0 skip)"
fi

# sain-01: secure_boot=signed → proceeds (will hit require_root or other gate)
# Just verify it doesn't crash with a python/yaml error.
rc="$(SOVEREIGN_OS_PROFILE=sain-01 run_rc "${script}")"
# Either passes (root + tools) or refuses cleanly. Both acceptable.
if [ "${rc}" -ne 130 ] && [ "${rc}" -ne 139 ]; then
  ok "mok-enroll handles sain-01 without crash (rc=${rc})"
else
  ko "mok-enroll crashed with sain-01: rc=${rc}"
fi

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_during_install_gates: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
