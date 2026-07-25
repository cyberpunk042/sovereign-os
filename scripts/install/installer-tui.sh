#!/usr/bin/env bash
# scripts/install/installer-tui.sh — the on-USB sovereign-os installer driver.
#
# Runs on the LIVE installer medium (boot=live) via sovereign-installer.service.
# Installs the MUTABLE sovereign-os SYSTEM onto an internal disk using the same
# reflash-root trio the from-host `sovereign-osctl install system` uses — but in
# ANSWERS identity mode (there is no host to inherit keyboard/locale/creds from).
#
# Safety: NEVER touches the disk we booted from. Detects an existing `sovereign`
# VG and offers reflash-root (rebuild root, keep /home) vs a fresh partition.
#
# Answers (keyboard/locale/tz/passwords/target) come from a baked answers file
# (default /opt/sovereign-os/install-answers.env) pre-filled into a whiptail form
# the operator confirms; SOVEREIGN_OS_NONINTERACTIVE=1 + complete answers → hands-off.
set -euo pipefail

OSDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANSWERS="${SOVEREIGN_OS_ANSWERS:-/opt/sovereign-os/install-answers.env}"
# shellcheck source=/dev/null
[ -r "${ANSWERS}" ] && . "${ANSWERS}" || true

red()  { printf '\033[31m%s\033[0m\n' "$*"; }
grn()  { printf '\033[32m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
step() { printf '\n\033[36m━━━ %s\033[0m\n' "$*"; }

[ "$(id -u)" -eq 0 ] || { red "installer must run as root"; exit 1; }

# ── 1. the disk we BOOTED from — must never be a target ──
MEDIUM_SRC="$(findmnt -no SOURCE /run/live/medium 2>/dev/null \
  || findmnt -no SOURCE / 2>/dev/null || echo '')"
FORBID_DISK=""
if [ -n "${MEDIUM_SRC}" ] && [ -b "${MEDIUM_SRC}" ]; then
  FORBID_DISK="/dev/$(lsblk -no PKNAME "${MEDIUM_SRC}" 2>/dev/null | head -1)"
fi
export SOVEREIGN_OS_FORBID_DISK="${FORBID_DISK}"

step "sovereign-os installer"
info "boot medium : ${MEDIUM_SRC:-unknown}  (disk ${FORBID_DISK:-unknown} — protected)"

# ── 2. candidate internal disks (NVMe/SATA), excluding the boot medium ──
mapfile -t DISKS < <(
  lsblk -dno NAME,TYPE 2>/dev/null | awk '$2=="disk"{print "/dev/"$1}' \
    | grep -vx "${FORBID_DISK}" || true
)
# prefer NVMe
mapfile -t NVME < <(printf '%s\n' "${DISKS[@]}" | grep -E '/dev/nvme' || true)
[ "${#NVME[@]}" -gt 0 ] && DISKS=("${NVME[@]}")
if [ "${#DISKS[@]}" -eq 0 ]; then
  red "no installable internal disk found (only the boot medium is present). Aborting."
  exit 1
fi

# ── 3. pick the target (answers TARGET_DISK → auto if single → whiptail menu) ──
TARGET="${SOVEREIGN_OS_TARGET_DISK:-}"
if [ -z "${TARGET}" ]; then
  if [ "${#DISKS[@]}" -eq 1 ]; then
    TARGET="${DISKS[0]}"
  elif command -v whiptail >/dev/null 2>&1 && [ -z "${SOVEREIGN_OS_NONINTERACTIVE:-}" ]; then
    menu=(); for d in "${DISKS[@]}"; do
      menu+=("${d}" "$(lsblk -dno MODEL,SIZE "${d}" 2>/dev/null | xargs)")
    done
    TARGET="$(whiptail --title "sovereign-os installer" \
      --menu "Choose the disk to install sovereign-os onto (the boot USB is protected):" \
      20 76 8 "${menu[@]}" 3>&1 1>&2 2>&3)" || { red "cancelled"; exit 1; }
  else
    TARGET="${DISKS[0]}"
    info "multiple disks; auto-selecting ${TARGET} (set TARGET_DISK to override)"
  fi
fi
[ -b "${TARGET}" ] || { red "target ${TARGET} is not a block device"; exit 1; }
[ "${TARGET}" = "${FORBID_DISK}" ] && { red "refusing: ${TARGET} is the boot medium"; exit 1; }

# ── 4. reflash-root vs fresh ──
REFLASH=0
if vgs sovereign >/dev/null 2>&1; then REFLASH=1; fi

FRONTEND="${SOVEREIGN_OS_FRONTEND:-kde-plasma}"
step "install plan"
info "target   : ${TARGET}  ($(lsblk -dno MODEL,SIZE "${TARGET}" 2>/dev/null | xargs))"
info "frontend : ${FRONTEND}"
info "mode     : $([ "${REFLASH}" = 1 ] && echo 'REFLASH-ROOT (sovereign VG exists → rebuild root, KEEP /home)' || echo "FRESH (partition ${TARGET})")"

# ── 5. confirm ──
if [ -z "${SOVEREIGN_OS_NONINTERACTIVE:-}" ]; then
  if command -v whiptail >/dev/null 2>&1; then
    whiptail --title "Confirm" --yesno \
      "Install sovereign-os onto ${TARGET}?\n\nMode: $([ "${REFLASH}" = 1 ] && echo 'reflash root (keep /home)' || echo "FRESH — partitions ${TARGET}")\n\nThe boot USB (${FORBID_DISK}) is never touched." \
      14 72 || { red "cancelled"; exit 1; }
  else
    read -rp "  Type the disk path (${TARGET}) to confirm: " typed
    [ "${typed}" = "${TARGET}" ] || { red "mismatch; aborting"; exit 1; }
  fi
fi

# ── 6. run the trio in ANSWERS identity mode ──
export SOVEREIGN_OS_IDENTITY_MODE=answers
export SOVEREIGN_OS_TARGET_DISK="${TARGET}"
export SOVEREIGN_OS_FRONTEND
export SOVEREIGN_OS_INSTALL_GUI="${SOVEREIGN_OS_INSTALL_GUI:-1}"

if [ "${REFLASH}" -eq 0 ]; then
  step "Phase 1 — partition ${TARGET} + sovereign VG"
  SOVEREIGN_OS_LVM_DISK="${TARGET}" bash "${OSDIR}/setup-lvm-dualboot.sh"
  # No host /home to migrate in the live env — skip Phase 2.
else
  info "sovereign VG present — reflash-root: rebuilding root only, keeping /home"
fi
step "Phase 3 — install mutable Debian + custom kernel + ${FRONTEND}"
bash "${OSDIR}/install-sovereign-root.sh"

grn "━━━ install complete — remove the USB and reboot into 'sovereign-os' ━━━"
if [ -z "${SOVEREIGN_OS_NONINTERACTIVE:-}" ] && command -v whiptail >/dev/null 2>&1; then
  whiptail --title "Done" --msgbox \
    "sovereign-os is installed on ${TARGET}.\n\nRemove the USB and reboot; pick 'sovereign-os' from the firmware boot menu." 12 66 || true
fi
