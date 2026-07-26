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
# Answers (keyboard/locale/tz/target) come from a baked answers file (default
# /opt/sovereign-os/install-answers.env). PASSWORDS are asked for here, in a
# whiptail passwordbox: the baked file ships a placeholder, and an install must
# never go out on it. Unattended (SOVEREIGN_OS_NONINTERACTIVE=1) requires a real
# password in the answers file, or SOVEREIGN_OS_ALLOW_DEFAULT_PASSWORD=1 to
# accept the built-in default deliberately.
#
# This header previously claimed the answers were "pre-filled into a whiptail
# form the operator confirms". No such form existed — the TUI asked only for the
# disk — so every installer-USB install shipped root:sovereign and
# <user>:sovereign (audited 2026-07-26).
set -euo pipefail

# whiptail/newt hard-fail without TERM, and a systemd service inherits none.
# The unit sets it, but the script must stand alone too (a rescue shell, an
# operator running it by hand) — otherwise every dialog exits 1 and the
# installer looks hung.
: "${TERM:=linux}"; export TERM

OSDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANSWERS="${SOVEREIGN_OS_ANSWERS:-/opt/sovereign-os/install-answers.env}"
# set -a so EVERY answer (keyboard/locale/creds/frontend/ROOTFS_SQUASHFS/…) is
# exported to install-sovereign-root.sh, which reads them from the environment.
# shellcheck source=/dev/null
if [ -r "${ANSWERS}" ]; then set -a; . "${ANSWERS}"; set +a; fi

red()  { printf '\033[31m%s\033[0m\n' "$*"; }
grn()  { printf '\033[32m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
step() { printf '\n\033[36m━━━ %s\033[0m\n' "$*"; }

[ "$(id -u)" -eq 0 ] || { red "installer must run as root"; exit 1; }

# whole-disk device for any block device (partition or disk). Uses sysfs, NOT
# `lsblk -no PKNAME` — that returns MULTIPLE lines when LVs are stacked on the
# partition (the sovereign LVs), and head -1 grabs an LV's parent (the partition)
# instead of the disk. sysfs `<part>/..` is the disk, deterministically.
_whole_disk() {
  local d p; d="$(basename "${1#/dev/}")"
  p="$(basename "$(readlink -f "/sys/class/block/${d}/.." 2>/dev/null)" 2>/dev/null)"
  if [ -n "${p}" ] && [ "${p}" != "block" ] && [ -b "/dev/${p}" ]; then echo "/dev/${p}"
  elif [ -b "/dev/${d}" ]; then echo "/dev/${d}"; fi
}

# ── 1. the disk we BOOTED from — must never be a target ──
# The live medium mounts at /run/live/medium; its backing BLOCK device is the
# boot disk to protect. NEVER fall back to `/` (a live overlay, not a block
# device — feeding it to lsblk is what printed "lsblk: overlay: ...").
_medium_dev=""
for _mp in /run/live/medium /lib/live/mount/medium /run/live/rootfs; do
  _src="$(findmnt -fno SOURCE "${_mp}" 2>/dev/null || true)"
  if [ -n "${_src}" ] && [ -b "${_src}" ]; then _medium_dev="${_src}"; break; fi
done
FORBID_DISK=""
[ -n "${_medium_dev}" ] && FORBID_DISK="$(_whole_disk "${_medium_dev}")"
export SOVEREIGN_OS_FORBID_DISK="${FORBID_DISK}"

step "sovereign-os installer"
info "boot medium : ${_medium_dev:-unknown}  (disk ${FORBID_DISK:-unknown} — protected)"

# ── 2. reflash-root FIRST: if the `sovereign` VG already exists (box prepared
#      with setup-lvm), REUSE it — rebuild the root LV, keep /home. No disk
#      picking, and NO OTHER OS DISK (e.g. your dev Debian on nvme0n1) is ever
#      touched: we only write the sovereign LVs + the ESP on the VG's own disk. ──
REFLASH=0
TARGET=""
if vgs sovereign >/dev/null 2>&1; then
  REFLASH=1
  _pv="$(pvs --noheadings -o pv_name -S vg_name=sovereign 2>/dev/null | awk 'NF{print $1; exit}')"
  [ -n "${_pv}" ] && TARGET="$(_whole_disk "${_pv}")"
  [ -b "${TARGET}" ] || TARGET="${SOVEREIGN_OS_TARGET_DISK:-/dev/nvme1n1}"
else
  # ── FRESH: offer ONLY internal (non-removable, RM=0) whole disks that are not
  #    the boot medium. The USB stick (RM=1) is excluded automatically; lsblk
  #    only lists real block disks, so "overlay" can never reach it. ──
  mapfile -t DISKS < <(
    lsblk -dpno NAME,TYPE,RM 2>/dev/null \
      | awk -v f="${FORBID_DISK}" '$2=="disk" && $3==0 && $1!=f {print $1}'
  )
  mapfile -t NVME < <(printf '%s\n' "${DISKS[@]}" | grep -E '/dev/nvme' || true)
  [ "${#NVME[@]}" -gt 0 ] && DISKS=("${NVME[@]}")
  if [ "${#DISKS[@]}" -eq 0 ]; then
    red "no installable internal disk found (boot medium + removable excluded). Aborting."; exit 1
  fi
  TARGET="${SOVEREIGN_OS_TARGET_DISK:-}"
  if [ -z "${TARGET}" ]; then
    if [ "${#DISKS[@]}" -eq 1 ]; then
      TARGET="${DISKS[0]}"
    elif command -v whiptail >/dev/null 2>&1 && [ -z "${SOVEREIGN_OS_NONINTERACTIVE:-}" ]; then
      menu=(); for d in "${DISKS[@]}"; do
        menu+=("${d}" "$(lsblk -dpno MODEL,SIZE "${d}" 2>/dev/null | xargs)")
      done
      TARGET="$(whiptail --title "sovereign-os installer" \
        --menu "Choose the INTERNAL disk to install onto (the boot USB is protected):" \
        20 78 8 "${menu[@]}" 3>&1 1>&2 2>&3)" || { red "cancelled"; exit 1; }
    else
      TARGET="${DISKS[0]}"; info "auto-selecting ${TARGET} (set TARGET_DISK to override)"
    fi
  fi
fi
[ -b "${TARGET}" ] || { red "target ${TARGET} is not a valid block device"; exit 1; }
[ "${TARGET}" = "${FORBID_DISK}" ] && { red "refusing: ${TARGET} is the boot medium"; exit 1; }

FRONTEND="${SOVEREIGN_OS_FRONTEND:-kde-plasma}"
step "install plan"
info "target   : ${TARGET}  ($(lsblk -dno MODEL,SIZE "${TARGET}" 2>/dev/null | xargs))"
info "frontend : ${FRONTEND}"
info "mode     : $([ "${REFLASH}" = 1 ] && echo 'REFLASH-ROOT (sovereign VG exists → rebuild root, KEEP /home)' || echo "FRESH (partition ${TARGET})")"

# ── 4b. CREDENTIALS ──────────────────────────────────────────────────────────
# The baked answers file ships SOVEREIGN_OS_{ROOT,USER}_PASS=sovereign, and this
# TUI never asked for anything else — so every installer-USB install went out
# with root:sovereign and <user>:sovereign. The header claimed the answers were
# "pre-filled into a whiptail form the operator confirms"; no such form existed
# (audited 2026-07-26). A default credential must be a DELIBERATE choice, never
# the path of least resistance.
_DEFAULT_PASS="sovereign"
_pw_looks_default() { [ "${1:-}" = "${_DEFAULT_PASS}" ] || [ -z "${1:-}" ]; }

if [ -z "${SOVEREIGN_OS_NONINTERACTIVE:-}" ] && command -v whiptail >/dev/null 2>&1; then
  if _pw_looks_default "${SOVEREIGN_OS_USER_PASS:-}"; then
    while :; do
      _p1="$(whiptail --title "sovereign-os installer" --passwordbox \
        "Password for '${SOVEREIGN_OS_USER:-jfortin}' (also used for root).\n\nThis replaces the built-in default." \
        12 68 3>&1 1>&2 2>&3)" || { red "cancelled"; exit 1; }
      _p2="$(whiptail --title "sovereign-os installer" --passwordbox \
        "Confirm the password:" 10 68 3>&1 1>&2 2>&3)" || { red "cancelled"; exit 1; }
      if [ -z "${_p1}" ]; then
        whiptail --title "Empty password" --msgbox \
          "An empty password locks the account — you would boot to a login nobody can pass." 10 68 || true
      elif [ "${_p1}" != "${_p2}" ]; then
        whiptail --title "Mismatch" --msgbox "The two entries differ. Try again." 8 60 || true
      elif case "${_p1}" in *\'*) true ;; *) false ;; esac; then
        # The downstream chroot setup interpolates these into a single-quoted
        # shell string; an apostrophe would break the script mid-install.
        whiptail --title "Unsupported character" --msgbox \
          "The password cannot contain an apostrophe ( ' ). Please choose another." 9 66 || true
      else
        SOVEREIGN_OS_USER_PASS="${_p1}"; SOVEREIGN_OS_ROOT_PASS="${_p1}"
        export SOVEREIGN_OS_USER_PASS SOVEREIGN_OS_ROOT_PASS
        unset _p1 _p2
        info "credentials set for ${SOVEREIGN_OS_USER:-jfortin} + root"
        break
      fi
    done
  else
    info "credentials supplied by the answers file (not the built-in default)"
  fi
else
  # Unattended. Shipping the default here is allowed only on purpose.
  if _pw_looks_default "${SOVEREIGN_OS_USER_PASS:-}"; then
    if [ "${SOVEREIGN_OS_ALLOW_DEFAULT_PASSWORD:-0}" = 1 ]; then
      red "WARNING: installing with the BUILT-IN DEFAULT password — change it at first login."
    else
      red "refusing to install with the built-in default password."
      red "  set SOVEREIGN_OS_USER_PASS / SOVEREIGN_OS_ROOT_PASS in the answers file,"
      red "  or SOVEREIGN_OS_ALLOW_DEFAULT_PASSWORD=1 to accept it deliberately."
      exit 1
    fi
  fi
fi

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
