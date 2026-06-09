#!/usr/bin/env bash
# tests/nspawn/test_mkosi_adapter.sh
#
# Layer 3 substantive test for scripts/build/adapters/mkosi-emit.sh.
# Validates the substrate-adapter pattern: profile YAML → mkosi-
# native config tree. No mkosi binary needed (we only validate the
# emitted files; we don't run a real build).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

PROFILE="${1:-sain-01}"
profile_file="${__REPO_ROOT}/profiles/${PROFILE}.yaml"

if [ ! -f "${profile_file}" ]; then
  echo "FAIL: profile missing: ${profile_file}"
  exit 1
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

# Run the adapter
"${__REPO_ROOT}/scripts/build/adapters/mkosi-emit.sh" "${profile_file}" "${tmpdir}" >/dev/null

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_mkosi_adapter.sh (profile=${PROFILE})"
echo "  output: ${tmpdir}"
echo

# ----------- top-level files ---------------

[ -f "${tmpdir}/mkosi.conf" ] && ok "mkosi.conf emitted" || ko "mkosi.conf missing"
[ -d "${tmpdir}/mkosi.conf.d" ] && ok "mkosi.conf.d/ dir emitted" || ko "mkosi.conf.d/ missing"
[ -d "${tmpdir}/mkosi.skeleton" ] && ok "mkosi.skeleton/ dir emitted" || ko "mkosi.skeleton/ missing"
[ -d "${tmpdir}/mkosi.extra" ] && ok "mkosi.extra/ dir emitted" || ko "mkosi.extra/ missing"
[ -d "${tmpdir}/mkosi.repart" ] && ok "mkosi.repart/ dir emitted" || ko "mkosi.repart/ missing"

# ----------- mkosi.conf content ---------------

if grep -q "Distribution=debian" "${tmpdir}/mkosi.conf"; then
  ok "mkosi.conf declares Distribution=debian"
else
  ko "mkosi.conf missing Distribution=debian"
fi

if grep -q "Release=trixie" "${tmpdir}/mkosi.conf"; then
  ok "mkosi.conf declares Release=trixie"
else
  ko "mkosi.conf missing Release=trixie"
fi

if grep -q "SecureBoot=yes" "${tmpdir}/mkosi.conf"; then
  ok "mkosi.conf enables SecureBoot"
else
  ko "mkosi.conf missing SecureBoot=yes"
fi

# ----------- per-profile override ---------------

profile_conf="${tmpdir}/mkosi.conf.d/${PROFILE}.conf"
if [ -f "${profile_conf}" ]; then
  ok "profile-specific config emitted at ${profile_conf##*/}"
else
  ko "profile-specific config missing at ${profile_conf}"
fi

# Profile config must contain Packages= from profile.packages.{base,profile}
# minus kernel-image* (which mkosi handles separately)
if grep -q "Packages=" "${profile_conf}"; then
  ok "profile config has Packages= directive"
else
  ko "profile config missing Packages= directive"
fi

# Profile-specific packages from sain-01 — verify a few representative ones
if [ "${PROFILE}" = "sain-01" ]; then
  for pkg in podman tetragon zfsutils-linux; do
    if grep -q "  ${pkg}\|    ${pkg}" "${profile_conf}"; then
      ok "profile config includes package: ${pkg}"
    else
      ko "profile config missing expected package: ${pkg}"
    fi
  done

  # Kernel-image packages must NOT be in the package list (they ship via mkosi.extra)
  if grep -qE "^\s*linux-image-" "${profile_conf}"; then
    ko "kernel-image package leaked into Packages= (should be in mkosi.extra/)"
  else
    ok "kernel-image properly excluded from Packages= (ships via mkosi.extra)"
  fi

  # Deny-list enforcement (sovereignty): denied packages must NOT appear in the
  # Packages= (install) block, and MUST appear under RemovePackages= so mkosi
  # actually purges them (comments alone enforced nothing). Extract each block
  # by directive so an indented entry is attributed correctly.
  pkgs_block="$(awk '/^Packages=/{f=1;next} /^[A-Za-z#[]/{f=0} f' "${profile_conf}")"
  remove_block="$(awk '/^RemovePackages=/{f=1;next} /^[A-Za-z#[]/{f=0} f' "${profile_conf}")"
  if printf '%s\n' "${pkgs_block}" | grep -qE '^\s+(popularity-contest|apport|whoopsie|snapd|ubuntu-advantage-tools)\b'; then
    ko "deny-list package present as an ACTIVE entry in Packages="
  else
    ok "deny-list packages absent from the active Packages= install block"
  fi
  if printf '%s\n' "${remove_block}" | grep -qE '^\s+(snapd|apport|whoopsie)\b'; then
    ok "deny-list enforced via RemovePackages= (actually purged, not just commented)"
  else
    ko "deny-list NOT enforced — denied packages missing from RemovePackages= (sovereignty gap)"
  fi

  # KernelCommandLine should contain vfio-pci.ids
  if grep -q "vfio-pci.ids=" "${profile_conf}"; then
    ok "profile config has KernelCommandLine with vfio-pci.ids"
  else
    ko "profile config missing vfio-pci.ids in cmdline"
  fi
fi

# ----------- mkosi.repart content ---------------

# Both sain-01 (zfs-tiered) and old-workstation (ext4) should have
# 00-esp.conf + 10-*.conf
[ -f "${tmpdir}/mkosi.repart/00-esp.conf" ] && ok "ESP partition declared" || ko "ESP partition missing"

if [ "${PROFILE}" = "sain-01" ]; then
  if [ -f "${tmpdir}/mkosi.repart/10-root-zfs.conf" ]; then
    ok "ZFS root partition declared (zfs-tiered layout)"
    if grep -q "Format=none" "${tmpdir}/mkosi.repart/10-root-zfs.conf"; then
      ok "ZFS partition has Format=none (pool created post-install)"
    else
      ko "ZFS partition should have Format=none"
    fi
  else
    ko "ZFS root partition config missing"
  fi
fi

if [ "${PROFILE}" = "old-workstation" ]; then
  if [ -f "${tmpdir}/mkosi.repart/10-root.conf" ]; then
    ok "ext4 root partition declared"
    if grep -q "Format=ext4" "${tmpdir}/mkosi.repart/10-root.conf"; then
      ok "ext4 partition has Format=ext4"
    else
      ko "ext4 partition should have Format=ext4"
    fi
  else
    ko "ext4 root partition config missing"
  fi
fi

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_mkosi_adapter: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
