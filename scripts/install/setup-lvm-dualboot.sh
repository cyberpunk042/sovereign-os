#!/usr/bin/env bash
# scripts/install/setup-lvm-dualboot.sh — Phase 1 of the single-OS
# reflash-root LVM layout. (Filename keeps the historical "dualboot" name;
# the dual-boot coexistence design was dropped in the 2026-06-10 single-OS
# pivot — but the LVM layout it builds is what the single-OS world uses.)
#
# Builds the `sovereign` VG on the second NVMe with two LVs:
#   - sovereign-home — the ONE shared /home; survives every root reflash
#   - sovereign-root — the (re)flashable sovereign-os root; idle until
#                      install-sovereign-root.sh (Phase 3) populates it
#
# Standing operator principle (verbatim 2026-06-10, still in force):
#   reflashing the sovereign root must NEVER touch /home; jfortin (uid 1000)
#   is sudoer + root; LVM for flexible data management, no wasted space.
#
# Does NOT touch the running OS disk. Idempotent-guarded; aborts on any
# ambiguity. Run: sudo scripts/install/setup-lvm-dualboot.sh
set -euo pipefail

# ── tunables (override via env) ──
# NO DEFAULT TARGET DISK. This used to default to /dev/nvme1n1, which on this
# very machine is the RUNNING Debian (root=/dev/nvme1n1p2) — the default was
# stale, left over from when the two NVMes had the opposite roles. Only the
# safety gates stopped it, and on any other machine that device name means
# something else entirely.
#
# A device name is not an identity. The same stale-name assumption sat in the
# d-i preseed, where a rule written to protect nvme0n1 ended up selecting the
# operator's working system (2026-07-27). Refuse to guess: name the disk.
TARGET="${SOVEREIGN_OS_LVM_DISK:-}"   # the EMPTY disk to consume
if [ -z "${TARGET}" ]; then
  red "ABORT: no target disk. Set SOVEREIGN_OS_LVM_DISK=/dev/..."
  red "  Candidates (whole disks with nothing mounted):"
  lsblk -dno NAME,SIZE,MODEL 2>/dev/null | while read -r _n _rest; do
    [ "$(lsblk -nro MOUNTPOINTS "/dev/${_n}" 2>/dev/null | grep -c .)" = 0 ] \
      && red "    /dev/${_n}  ${_rest}"
  done
  exit 1
fi
VG="${SOVEREIGN_OS_VG:-sovereign}"
LV_ROOT_SIZE="${SOVEREIGN_OS_LV_ROOT_SIZE:-100G}" # sovereign-os root (reflashable)
LV_HOME_SIZE="${SOVEREIGN_OS_LV_HOME_SIZE:-1.4T}" # the ONE shared /home
ESP_SIZE="${SOVEREIGN_OS_ESP_SIZE:-1GiB}"

red()  { printf '\033[31m%s\033[0m\n' "$*"; }
grn()  { printf '\033[32m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }

[ "$(id -u)" -eq 0 ] || { red "must run as root: sudo $0"; exit 1; }

echo "━━━ sovereign-os reflash-root LVM setup ━━━"
info "target disk : ${TARGET}  (will be PARTITIONED)"
info "volume group: ${VG}"
info "  lv_root    : ${LV_ROOT_SIZE}  (sovereign-os root — reflashable)"
info "  lv_home    : ${LV_HOME_SIZE}  (THE shared /home)"
echo

# ── SAFETY GATES — refuse to touch the wrong disk ──
[ -b "${TARGET}" ] || { red "ABORT: ${TARGET} is not a block device"; exit 1; }

# Walk UP to the physical disk. PKNAME is the IMMEDIATE parent, so for a plain
# partition root (/dev/nvme1n1p2) it yields the disk -- but this script CREATES
# an LVM root, and for /dev/mapper/sovereign-root PKNAME yields the PV
# PARTITION (nvme0n1p2), which never equals a TARGET of /dev/nvme0n1. The gate
# meant to protect the running system would have passed and let the disk hosting
# it be zapped -- precisely the "reflash" case this script exists for
# (2026-07-27). Loop until there is no parent left; this also covers LUKS and md.
_parent_disk_of() {
  _d="$1"
  while :; do
    _p="$(lsblk -no PKNAME "${_d}" 2>/dev/null | head -1 | tr -d ' ')"
    [ -n "${_p}" ] || break
    _d="/dev/${_p}"
  done
  printf '%s\n' "${_d}"
}
ROOT_SRC="$(findmnt -no SOURCE / )"
ROOT_DISK="$(_parent_disk_of "${ROOT_SRC}")"
if [ "${ROOT_DISK}" = "${TARGET}" ]; then
  red "ABORT: ${TARGET} hosts the RUNNING root (${ROOT_SRC}). Never."
  exit 1
fi
# Never partition the disk we BOOTED from (installer USB / live medium). The
# running-root gate above misses this when the live root is a squashfs, so the
# installer-TUI passes the boot-medium disk explicitly.
if [ -n "${SOVEREIGN_OS_FORBID_DISK:-}" ] && [ "${TARGET}" = "${SOVEREIGN_OS_FORBID_DISK}" ]; then
  red "ABORT: ${TARGET} is the boot medium (SOVEREIGN_OS_FORBID_DISK) — refusing."
  exit 1
fi

# refuse if the disk already carries partitions or a filesystem/PV signature
if lsblk -no NAME "${TARGET}" | grep -q "$(basename "${TARGET}")p"; then
  red "ABORT: ${TARGET} already has partitions:"; lsblk "${TARGET}"
  red "If you intend to WIPE it, do so manually first — this script won't destroy existing data."
  exit 1
fi
if blkid "${TARGET}" >/dev/null 2>&1; then
  red "ABORT: ${TARGET} carries a filesystem/LVM signature; refusing to overwrite blindly."
  exit 1
fi
grn "✓ ${TARGET} is empty and is not the running OS — proceeding"

command -v pvcreate >/dev/null || { info "installing lvm2…"; apt-get install -y lvm2; }
command -v sgdisk   >/dev/null || { info "installing gdisk…"; apt-get install -y gdisk; }

# ── partition: p1 = ESP, p2 = LVM PV ──
info "partitioning ${TARGET} (GPT: ESP + LVM)…"
sgdisk --zap-all "${TARGET}"
sgdisk -n1:0:+"${ESP_SIZE}" -t1:ef00 -c1:"sovereign-esp"  "${TARGET}"
sgdisk -n2:0:0              -t2:8e00 -c2:"sovereign-lvm"  "${TARGET}"
partprobe "${TARGET}"; sleep 1

# partition node naming (nvme → p1/p2)
case "${TARGET}" in
  *[0-9]) ESP_PART="${TARGET}p1"; PV_PART="${TARGET}p2" ;;
  *)      ESP_PART="${TARGET}1";  PV_PART="${TARGET}2"  ;;
esac

# ── ESP filesystem ──
info "formatting ESP ${ESP_PART} (vfat)…"
mkfs.fat -F32 -n SOV-ESP "${ESP_PART}"

# ── LVM ──
info "creating PV/VG/LVs…"
pvcreate -ff -y "${PV_PART}"
vgcreate "${VG}" "${PV_PART}"
lvcreate -y -n root -L "${LV_ROOT_SIZE}" "${VG}"
lvcreate -y -n home -L "${LV_HOME_SIZE}" "${VG}"

# ── filesystems on the LVs ──
info "formatting lv_root + lv_home (ext4)…"
mkfs.ext4 -q -L sovereign-root "/dev/${VG}/root"
mkfs.ext4 -q -L home          "/dev/${VG}/home"

echo
grn "━━━ Phase 1 complete ━━━"
lsblk "${TARGET}"
echo
cat <<EOF
Created (nothing on your existing Debian was touched):
  ESP   : ${ESP_PART}            → sovereign-os bootloader
  VG    : ${VG}
   /dev/${VG}/root  (${LV_ROOT_SIZE})  → sovereign-os root  [reflash target]
   /dev/${VG}/home  (${LV_HOME_SIZE})  → THE shared /home   [never reflashed]

Free space remains in VG '${VG}' for tank/models, swap, growth:
$(vgs --noheadings -o vg_free "${VG}" 2>/dev/null | xargs echo "  vg free:")

Next: scripts/install/migrate-home.sh  (copy current /home onto the
sovereign-home LV so it becomes the single, reflash-surviving /home).
EOF
