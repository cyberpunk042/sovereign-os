#!/usr/bin/env bash
# tests/nspawn/test_whitelabel_render_to_disk.sh
#
# Substantive Layer 3 test (per SDD-008 § Layer 3 stage acceptance):
# Validates that the whitelabel render engine produces files that
# match the operator-specified branding when copied into a fake root
# filesystem.
#
# Stack: tmpdir as a fake rootfs (no real chroot needed for file
# content checks — chroot would be needed for `dpkg -l` style
# verification; file-presence + content is plain `cat`).
#
# Asserts:
#   - render.py emits /etc/os-release with profile.whitelabel.profile's
#     branding.os_id substituted in
#   - render.py emits /etc/issue with the operator-verbatim motd
#   - render.py emits /etc/dpkg/origins/sovereign with Parent: Debian
#     (provenance preserved per SDD-006 legal floor)
#   - render.py refuses to emit /etc/debian_version (must-not-touch)
#
# Idempotent + isolated: every run uses a fresh tmpdir.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

PROFILE="${1:-sain-01}"
profile_file="${__REPO_ROOT}/profiles/${PROFILE}.yaml"
wl_file="${__REPO_ROOT}/whitelabel/default.yaml"

if [ ! -f "${profile_file}" ] || [ ! -f "${wl_file}" ]; then
  echo "FAIL: missing profile or whitelabel"
  exit 1
fi

# Fake rootfs in a temp dir
tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

# Run the render engine
python3 "${__REPO_ROOT}/scripts/whitelabel/render.py" \
  --profile "${profile_file}" \
  --whitelabel "${wl_file}" \
  --out "${tmpdir}" \
  --substrate mkosi >/dev/null

fail=0
pass=0

assert_file_exists() {
  local f="$1" desc="$2"
  if [ -f "$f" ]; then
    echo "  PASS — ${desc} (${f})"
    pass=$((pass + 1))
  else
    echo "  FAIL — ${desc} missing (${f})"
    fail=$((fail + 1))
  fi
}

assert_file_contains() {
  local f="$1" needle="$2" desc="$3"
  if [ -f "$f" ] && grep -qF "${needle}" "$f"; then
    echo "  PASS — ${desc}"
    pass=$((pass + 1))
  else
    echo "  FAIL — ${desc} (looking for '${needle}' in $f)"
    fail=$((fail + 1))
  fi
}

assert_not_present() {
  local f="$1" desc="$2"
  if [ ! -e "$f" ]; then
    echo "  PASS — ${desc} (legal floor preserved)"
    pass=$((pass + 1))
  else
    echo "  FAIL — ${desc} (legal-floor file should not be rendered)"
    fail=$((fail + 1))
  fi
}

# ----------- assertions -----------

echo "tests/nspawn/test_whitelabel_render_to_disk.sh (profile=${PROFILE})"
echo "  output dir: ${tmpdir}"
echo

# 1. os-release exists + contains operator-chosen ID
assert_file_exists "${tmpdir}/mkosi.skeleton/etc/os-release" "os-release rendered"
assert_file_contains "${tmpdir}/mkosi.skeleton/etc/os-release" "ID=sovereign" "os-release has ID=sovereign (from whitelabel branding.os_id)"

# 2. /etc/issue has the operator-verbatim motd
assert_file_contains "${tmpdir}/mkosi.skeleton/etc/issue" "quality over quantity" \
  "/etc/issue contains operator-verbatim motd"
assert_file_contains "${tmpdir}/mkosi.skeleton/etc/issue" "honesty over cheats" \
  "/etc/issue contains 'honesty over cheats' (full verbatim)"

# 3. /etc/dpkg/origins/sovereign preserves Debian provenance
assert_file_contains "${tmpdir}/mkosi.skeleton/etc/dpkg/origins/sovereign" "Parent: Debian" \
  "dpkg origins file preserves 'Parent: Debian' provenance"

# 4. /etc/debian_version must NOT be in the skeleton (legal floor)
assert_not_present "${tmpdir}/mkosi.skeleton/etc/debian_version" \
  "/etc/debian_version legal-floor preservation"

# 5. /usr/share/doc/* must NOT have rendered copyright overrides
assert_not_present "${tmpdir}/mkosi.skeleton/usr/share/doc" \
  "/usr/share/doc/ legal-floor preservation"

# ----------- result -----------

echo
total=$((pass + fail))
echo "test_whitelabel_render_to_disk: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL (${fail} assertion(s) failed)"
  exit 1
fi
echo "PASS"
