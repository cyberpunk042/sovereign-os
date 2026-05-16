#!/usr/bin/env bash
# tests/nspawn/test_whitelabel_render_live_build.sh
#
# Layer 3 test for scripts/whitelabel/render.py's emit_for_live_build()
# path. The mkosi path is tested in test_whitelabel_render_to_disk.sh;
# this asserts the live-build substrate gets functionally equivalent
# content (substrate-agnosticism), and validates the live-build output
# tree shape (config/includes.chroot/ + config/auto/config.d/).
#
# Asserts:
#   - /etc/os-release rendered into config/includes.chroot/etc/os-release
#   - /etc/issue contains the operator-verbatim motd
#   - dpkg origins file present with Parent: Debian
#   - legal-floor files (/etc/debian_version, /usr/share/doc/) NOT
#     created in includes.chroot
#   - whitelabel-manifest.json emitted at output root
#   - the operator's brand placeholders are substituted (no ${var} leaks)

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

PROFILE="${1:-sain-01}"
profile_file="${__REPO_ROOT}/profiles/${PROFILE}.yaml"
wl_file="${__REPO_ROOT}/whitelabel/default.yaml"

[ -f "${profile_file}" ] || { echo "FAIL: profile missing"; exit 1; }
[ -f "${wl_file}" ] || { echo "FAIL: whitelabel missing"; exit 1; }

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

python3 "${__REPO_ROOT}/scripts/whitelabel/render.py" \
  --profile "${profile_file}" \
  --whitelabel "${wl_file}" \
  --out "${tmpdir}" \
  --substrate live-build >/dev/null

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_whitelabel_render_live_build.sh (profile=${PROFILE})"
echo "  output: ${tmpdir}"
echo

chroot_root="${tmpdir}/config/includes.chroot"

# ----------- output-tree shape ---------------

[ -d "${chroot_root}" ] && ok "config/includes.chroot/ exists" \
  || ko "config/includes.chroot/ missing"

# Live-build's lb_config snippet for build-time env should land here
[ -d "${tmpdir}/config/auto/config.d" ] && ok "config/auto/config.d/ created (build-time env target)" \
  || ko "config/auto/config.d/ missing (build-time env target gone)"

# Manifest at output root (substrate-agnostic)
[ -f "${tmpdir}/whitelabel-manifest.json" ] && ok "whitelabel-manifest.json emitted at output root" \
  || ko "whitelabel-manifest.json missing"

# ----------- /etc/os-release ---------------

os_release="${chroot_root}/etc/os-release"
if [ -f "${os_release}" ]; then
  ok "/etc/os-release rendered into chroot"
else
  ko "/etc/os-release missing"
fi

if grep -q "ID=sovereign" "${os_release}"; then
  ok "/etc/os-release has ID=sovereign (whitelabel branding.os_id)"
else
  ko "/etc/os-release missing ID=sovereign"
fi

if grep -q "ID_LIKE=debian" "${os_release}"; then
  ok "/etc/os-release preserves ID_LIKE=debian (legal-floor provenance)"
else
  ko "/etc/os-release missing ID_LIKE=debian provenance line"
fi

# ----------- /etc/issue contains operator motd ---------------

issue_file="${chroot_root}/etc/issue"
if grep -q "quality over quantity" "${issue_file}" 2>/dev/null; then
  ok "/etc/issue contains operator-verbatim 'quality over quantity'"
else
  ko "/etc/issue missing operator-verbatim motd"
fi

if grep -q "honesty over cheats" "${issue_file}" 2>/dev/null; then
  ok "/etc/issue contains 'honesty over cheats' (full verbatim)"
else
  ko "/etc/issue missing full verbatim line"
fi

# ----------- dpkg origins (Debian-derivative provenance) ---------------

origins="${chroot_root}/etc/dpkg/origins/sovereign"
if grep -q "Parent: Debian" "${origins}" 2>/dev/null; then
  ok "dpkg origins preserves 'Parent: Debian' provenance"
else
  ko "dpkg origins missing 'Parent: Debian'"
fi

# ----------- legal floor: must-NOT-touch files absent ---------------

[ ! -e "${chroot_root}/etc/debian_version" ] && ok "/etc/debian_version legal-floor preserved (not in chroot)" \
  || ko "/etc/debian_version overwrote (legal floor violation)"

[ ! -d "${chroot_root}/usr/share/doc" ] && ok "/usr/share/doc/ legal-floor preserved (not in chroot)" \
  || ko "/usr/share/doc/ rendered (legal floor violation)"

# ----------- placeholder leak detection ---------------
# After render, no file in the chroot should still contain unsubstituted
# ${var} sigils — that would mean the operator's branding didn't reach
# the template. Operator framing: "we will still see it written somewhere
# in the /etc/issue for example" — but it should be the operator's
# strings, not template variables.

# Ignore comment lines (start with # or //) — templates legitimately
# document their own variable syntax in comments.
leaked=""
while IFS= read -r f; do
  if grep -vE '^\s*(#|//)' "$f" | grep -qE '\$\{[a-z_]+\}'; then
    leaked="${leaked}${f}\n"
  fi
done < <(find "${chroot_root}" -type f)
if [ -z "${leaked}" ]; then
  ok "no \${var} placeholder leaks in rendered chroot files (active content)"
else
  ko "placeholder leaks detected in: ${leaked}"
fi

# ----------- substrate-agnosticism cross-check ---------------
# The same logical surfaces (e.g. /etc/os-release) should be rendered
# both for mkosi (skeleton/etc/os-release) and live-build
# (config/includes.chroot/etc/os-release). Confirm content equivalence
# between the two emits.

mkosi_dir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}" "${mkosi_dir}"' EXIT

python3 "${__REPO_ROOT}/scripts/whitelabel/render.py" \
  --profile "${profile_file}" \
  --whitelabel "${wl_file}" \
  --out "${mkosi_dir}" \
  --substrate mkosi >/dev/null

mkosi_osrelease="${mkosi_dir}/mkosi.skeleton/etc/os-release"
if [ -f "${mkosi_osrelease}" ] && [ -f "${os_release}" ]; then
  if diff -q "${mkosi_osrelease}" "${os_release}" >/dev/null 2>&1; then
    ok "substrate-agnostic: /etc/os-release content identical for mkosi + live-build"
  else
    ko "substrate-agnostic violation: /etc/os-release differs between mkosi + live-build"
    diff "${mkosi_osrelease}" "${os_release}" | head -5
  fi
else
  ko "could not compare /etc/os-release across substrates (one or both missing)"
fi

# ----------- result -----------

echo
total=$((pass + fail))
echo "test_whitelabel_render_live_build: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
