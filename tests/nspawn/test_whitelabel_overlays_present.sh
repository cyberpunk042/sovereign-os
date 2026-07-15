#!/usr/bin/env bash
# tests/nspawn/test_whitelabel_overlays_present.sh
#
# Layer 3 test for Round 33 — verifies the substantive whitelabel
# overlay content (plymouth + grub themes) is well-formed and lands
# into both substrate output trees (mkosi.extra + live-build
# config/includes.chroot) intact.
#
# Asserts:
#   - source overlays (whitelabel/default/overlays/{plymouth,grub}-theme)
#     have the expected file shape + content
#   - plymouth script has refresh_callback + operator motd verbatim
#     + password-prompt callback (LUKS-ready)
#   - grub theme.txt has boot_menu + progress_bar + operator motd
#   - rendering for mkosi puts overlays under mkosi.extra/
#   - rendering for live-build puts overlays under
#     config/includes.chroot/

set -euo pipefail

PYTHON3="${PYTHON3:-python3}"
if ! "${PYTHON3}" -c "import yaml" >/dev/null 2>&1; then
  if /usr/bin/python3 -c "import yaml" >/dev/null 2>&1; then
    PYTHON3=/usr/bin/python3
  fi
fi

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_whitelabel_overlays_present.sh"
echo

# ----------- source overlays present ---------------

plymouth_dir="${__REPO_ROOT}/whitelabel/default/overlays/plymouth-theme"
grub_dir="${__REPO_ROOT}/whitelabel/default/overlays/grub-theme"

[ -d "${plymouth_dir}" ] && ok "plymouth-theme overlay dir present" || ko "plymouth-theme dir missing"
[ -d "${grub_dir}" ] && ok "grub-theme overlay dir present" || ko "grub-theme dir missing"

[ -f "${plymouth_dir}/sovereign.plymouth" ] && ok "plymouth theme manifest present" || ko "sovereign.plymouth missing"
[ -f "${plymouth_dir}/sovereign.script" ] && ok "plymouth script present" || ko "sovereign.script missing"
[ -f "${grub_dir}/theme.txt" ] && ok "grub theme.txt present" || ko "grub theme.txt missing"
[ -f "${grub_dir}/README.md" ] && ok "grub theme README present (operator drop-in guide)" || ko "grub theme README missing"

# ----------- plymouth script content ---------------

if grep -q "refresh_callback" "${plymouth_dir}/sovereign.script"; then
  ok "plymouth script: refresh_callback function declared (animation hook)"
else
  ko "plymouth script: no refresh_callback (boot splash will be static)"
fi

if grep -q "SetRefreshFunction" "${plymouth_dir}/sovereign.script"; then
  ok "plymouth script: refresh hook wired to Plymouth runtime"
else
  ko "plymouth script: refresh hook not wired"
fi

if grep -q "SetDisplayPasswordFunction" "${plymouth_dir}/sovereign.script"; then
  ok "plymouth script: password-prompt callback (LUKS/fscrypt-ready)"
else
  ko "plymouth script: no password-prompt callback"
fi

if grep -q "SetDisplayMessageFunction" "${plymouth_dir}/sovereign.script"; then
  ok "plymouth script: status-message callback (cryptsetup/fsck-ready)"
else
  ko "plymouth script: no status-message callback"
fi

# Operator motd (sacrosanct verbatim) at boot
if grep -qF "quality over quantity" "${plymouth_dir}/sovereign.script"; then
  ok "plymouth script: operator motd 'quality over quantity' surfaced at boot"
else
  ko "plymouth script: missing operator motd"
fi

if grep -qF "honesty over cheats and lies" "${plymouth_dir}/sovereign.script"; then
  ok "plymouth script: operator motd 'honesty over cheats and lies' (full verbatim)"
else
  ko "plymouth script: missing second motd line"
fi

# ----------- grub theme content ---------------

if grep -q "+ boot_menu {" "${grub_dir}/theme.txt"; then
  ok "grub theme: boot_menu section declared"
else
  ko "grub theme: no boot_menu"
fi

if grep -q "+ progress_bar {" "${grub_dir}/theme.txt"; then
  ok "grub theme: progress_bar section declared (timeout indicator)"
else
  ko "grub theme: no progress_bar"
fi

if grep -q "scrollbar = true" "${grub_dir}/theme.txt"; then
  ok "grub theme: boot_menu has scrollbar (long-list-readable)"
else
  ko "grub theme: no scrollbar (long menus unreadable)"
fi

if grep -qF "quality over quantity" "${grub_dir}/theme.txt" \
   && grep -qF "honesty over cheats and lies" "${grub_dir}/theme.txt"; then
  ok "grub theme: operator motd verbatim surfaced in vbox label"
else
  ko "grub theme: missing operator motd"
fi

# ----------- render to mkosi → overlays land in mkosi.extra ---------------

tmp_mkosi="$(mktemp -d)"
"${PYTHON3}" "${__REPO_ROOT}/scripts/whitelabel/render.py" \
  --profile "${__REPO_ROOT}/profiles/sain-01.yaml" \
  --whitelabel "${__REPO_ROOT}/whitelabel/default.yaml" \
  --out "${tmp_mkosi}" --substrate mkosi >/dev/null

# The render engine emits to whatever absolute path the whitelabel
# YAML's overlay surface specifies. We just verify the overlay made
# the trip — find a file from each theme.
if find "${tmp_mkosi}" -path '*plymouth-theme/sovereign.script' -type f | grep -q .; then
  ok "mkosi emit: plymouth-theme/sovereign.script propagated"
else
  ko "mkosi emit: plymouth script not propagated"
fi

if find "${tmp_mkosi}" -path '*grub-theme/theme.txt' -type f | grep -q .; then
  ok "mkosi emit: grub-theme/theme.txt propagated"
else
  ko "mkosi emit: grub theme not propagated"
fi

# Content survives the copy
rendered_plymouth="$(find "${tmp_mkosi}" -path '*plymouth-theme/sovereign.script' -type f | head -1)"
if [ -n "${rendered_plymouth}" ] && grep -qF "quality over quantity" "${rendered_plymouth}"; then
  ok "mkosi emit: operator motd survives the overlay copy"
else
  ko "mkosi emit: operator motd lost in overlay copy"
fi

rm -rf "${tmp_mkosi}"

# ----------- render to live-build → overlays land in includes.chroot ---------------

tmp_lb="$(mktemp -d)"
"${PYTHON3}" "${__REPO_ROOT}/scripts/whitelabel/render.py" \
  --profile "${__REPO_ROOT}/profiles/sain-01.yaml" \
  --whitelabel "${__REPO_ROOT}/whitelabel/default.yaml" \
  --out "${tmp_lb}" --substrate live-build >/dev/null

if find "${tmp_lb}/config/includes.chroot" -path '*plymouth-theme/sovereign.script' -type f | grep -q .; then
  ok "live-build emit: plymouth-theme/sovereign.script lands in includes.chroot"
else
  ko "live-build emit: plymouth script not in chroot"
fi

if find "${tmp_lb}/config/includes.chroot" -path '*grub-theme/theme.txt' -type f | grep -q .; then
  ok "live-build emit: grub-theme/theme.txt lands in includes.chroot"
else
  ko "live-build emit: grub theme not in chroot"
fi

rm -rf "${tmp_lb}"

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_whitelabel_overlays_present: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
