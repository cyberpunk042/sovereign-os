#!/usr/bin/env bash
# tests/nspawn/test_live_build_adapter.sh
#
# Layer 3 test for scripts/build/adapters/live-build-emit.sh (ALT-A
# substrate path per SDD-003). Validates substrate-agnostic adapter
# pattern: same profile YAML produces functionally-equivalent config
# tree for a different substrate.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

PROFILE="${1:-sain-01}"
profile_file="${__REPO_ROOT}/profiles/${PROFILE}.yaml"

[ -f "${profile_file}" ] || { echo "FAIL: profile missing"; exit 1; }

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

"${__REPO_ROOT}/scripts/build/adapters/live-build-emit.sh" "${profile_file}" "${tmpdir}" >/dev/null

fail=0; pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_live_build_adapter.sh (profile=${PROFILE})"
echo "  output: ${tmpdir}"
echo

# ----------- top-level live-build config tree ---------------

[ -f "${tmpdir}/config/auto/config" ] && ok "config/auto/config emitted" || ko "config/auto/config missing"
[ -f "${tmpdir}/config/auto/build" ] && ok "config/auto/build emitted" || ko "config/auto/build missing"
[ -f "${tmpdir}/config/auto/clean" ] && ok "config/auto/clean emitted" || ko "config/auto/clean missing"
[ -x "${tmpdir}/config/auto/config" ] && ok "config/auto/config is executable" || ko "config/auto/config not executable"
[ -x "${tmpdir}/config/auto/build" ] && ok "config/auto/build is executable" || ko "config/auto/build not executable"
[ -d "${tmpdir}/config/package-lists" ] && ok "package-lists/ dir emitted" || ko "package-lists/ missing"
[ -d "${tmpdir}/config/includes.chroot" ] && ok "includes.chroot/ dir emitted (whitelabel renders here)" || ko "includes.chroot/ missing"
[ -d "${tmpdir}/config/hooks/normal" ] && ok "hooks/normal/ dir emitted" || ko "hooks/normal/ missing"
[ -f "${tmpdir}/README.md" ] && ok "README.md emitted at output root" || ko "README.md missing"

# ----------- config/auto/config content ---------------

if grep -q "distribution trixie" "${tmpdir}/config/auto/config"; then
  ok "lb_config targets Debian trixie"
else
  ko "lb_config doesn't target trixie"
fi

if grep -q "architectures amd64" "${tmpdir}/config/auto/config"; then
  ok "lb_config targets amd64 architecture"
else
  ko "lb_config doesn't target amd64"
fi

if grep -q "binary-images iso-hybrid" "${tmpdir}/config/auto/config"; then
  ok "lb_config produces iso-hybrid binary"
else
  ko "lb_config doesn't produce iso-hybrid"
fi

# ----------- package-lists content ---------------

pkg_list="${tmpdir}/config/package-lists/sovereign.list.chroot"
if [ -f "${pkg_list}" ]; then
  ok "sovereign.list.chroot emitted"
else
  ko "sovereign.list.chroot missing"
fi

# Profile packages must appear; kernel-image must not
if [ "${PROFILE}" = "sain-01" ]; then
  for p in openssh-server podman tetragon zfsutils-linux; do
    if grep -q "^${p}\$" "${pkg_list}"; then
      ok "package list includes: ${p}"
    else
      ko "package list missing: ${p}"
    fi
  done

  if grep -qE "^linux-image-|^linux-headers-" "${pkg_list}"; then
    ko "kernel-image package leaked into package list (should go via includes.chroot)"
  else
    ok "kernel-image properly excluded from package list"
  fi

  # Deny-list packages must NOT appear as active entries (live-build skips them)
  if grep -qE "^(popularity-contest|apport|whoopsie|snapd|ubuntu-advantage-tools)\$" "${pkg_list}"; then
    ko "deny-list package leaked into package list"
  else
    ok "deny-list packages excluded from package list"
  fi
fi

# ----------- README ---------------

if grep -q "live-build" "${tmpdir}/README.md"; then
  ok "README mentions live-build"
else
  ko "README doesn't mention live-build"
fi

# ----------- substrate-agnosticism check: same profile → both adapters succeed ---------------

# This is the substrate-agnostic invariant: a single profile YAML can be
# consumed by EITHER adapter without modification. We already ran live-build
# above; rerun mkosi against the same profile in a fresh dir.
mkosi_dir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}" "${mkosi_dir}"' EXIT

if "${__REPO_ROOT}/scripts/build/adapters/mkosi-emit.sh" "${profile_file}" "${mkosi_dir}" >/dev/null 2>&1; then
  ok "same profile YAML feeds BOTH adapters cleanly (substrate-agnostic invariant)"
else
  ko "mkosi adapter failed against the profile that live-build succeeded against"
fi

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_live_build_adapter: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
