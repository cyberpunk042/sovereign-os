#!/usr/bin/env bash
# scripts/install/setup-lvm-dualboot.sh — Phase 1 of the dual-boot,
# shared-/home install.
#
# Operator architecture (verbatim direction 2026-06-10):
#   - old Debian (nvme0) and sovereign-os COEXIST, neither breaks the other
#   - LVM for flexible data management, no wasted space
#   - ONE /home, ALWAYS, shared between both OSes
#   - jfortin (uid 1000) sudoer + root, in both OSes
#   - reflashing sovereign root must NEVER touch /home
#
# This phase builds the LVM home on the EMPTY second NVMe. It does NOT
# touch the running OS disk. It is idempotent-guarded and aborts on any
# ambiguity. Run: sudo scripts/install/setup-lvm-dualboot.sh
set -euo pipefail

# ── tunables (override via env) ──
TARGET="${SOVEREIGN_OS_LVM_DISK:-/dev/nvme1n1}"   # the EMPTY disk to consume
VG="${SOVEREIGN_OS_VG:-sovereign}"
LV_ROOT_SIZE="${SOVEREIGN_OS_LV_ROOT_SIZE:-100G}" # sovereign-os root (reflashable)
LV_HOME_SIZE="${SOVEREIGN_OS_LV_HOME_SIZE:-1.4T}" # the ONE shared /home
ESP_SIZE="${SOVEREIGN_OS_ESP_SIZE:-1GiB}"

red()  { printf '\033[31m%s\033[0m\n' "$*"; }
grn()  { printf '\033[32m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }

[ "$(id -u)" -eq 0 ] || { red "must run as root: sudo $0"; exit 1; }

echo "━━━ sovereign-os dual-boot LVM setup ━━━"
info "target disk : ${TARGET}  (will be PARTITIONED)"
info "volume group: ${VG}"
info "  lv_root    : ${LV_ROOT_SIZE}  (sovereign-os root — reflashable)"
info "  lv_home    : ${LV_HOME_SIZE}  (THE shared /home)"
echo

# ── SAFETY GATES — refuse to touch the wrong disk ──
[ -b "${TARGET}" ] || { red "ABORT: ${TARGET} is not a block device"; exit 1; }

ROOT_SRC="$(findmnt -no SOURCE / )"
ROOT_DISK="/dev/$(lsblk -no PKNAME "${ROOT_SRC}" | head -1)"
if [ "${ROOT_DISK}" = "${TARGET}" ]; then
  red "ABORT: ${TARGET} hosts the RUNNING root (${ROOT_SRC}). Never."
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
Created (nothing on your old Debian was touched):
  ESP   : ${ESP_PART}            → sovereign-os bootloader
  VG    : ${VG}
   /dev/${VG}/root  (${LV_ROOT_SIZE})  → sovereign-os root  [reflash target]
   /dev/${VG}/home  (${LV_HOME_SIZE})  → THE shared /home   [never reflashed]

Free space remains in VG '${VG}' for tank/models, swap, growth:
$(vgs --noheadings -o vg_free "${VG}" 2>/dev/null | xargs echo "  vg free:")

Next: scripts/install/migrate-home.sh  (copy current /home onto lv_home,
then mount it from BOTH OSes as the single /home).
EOF
