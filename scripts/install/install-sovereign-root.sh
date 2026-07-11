#!/usr/bin/env bash
# scripts/install/install-sovereign-root.sh — Phase 3 of the single-OS
# reflash-root layout.
#
# Installs a REAL, MUTABLE Debian-13 root into the sovereign-root LV, running
# the custom znver5 kernel, with jfortin + root, mounting the SHARED
# sovereign-home LV as /home. This is the reflash-root procedure: re-running
# it rebuilds the sovereign root WITHOUT touching the shared /home. Boots via
# GRUB-EFI on sovereign's own ESP.
#
# Why mutable Debian (not the mkosi appliance image): the operator wants to
# control + change everything (apt, GUI later, toggle modules). The mkosi
# image is immutable (no apt/dpkg) and boots by whole-disk auto-discovery —
# the wrong shape for a reflashable LV root. This reuses the crown jewel (the
# custom kernel .deb) on a normal, controllable root.
#
# Inherits from the RUNNING Debian (no questions, matches what you use):
#   keyboard · locale · timezone · root + jfortin password entries.
#
# Run: sudo scripts/install/install-sovereign-root.sh
set -euo pipefail

ROOT_LV="${SOVEREIGN_OS_ROOT_LV:-/dev/sovereign/root}"
HOME_LV="${SOVEREIGN_OS_HOME_LV:-/dev/sovereign/home}"
ESP_PART="${SOVEREIGN_OS_ESP:-/dev/nvme1n1p1}"     # sovereign's own ESP (Phase 1)
PRIMARY_USER="${SOVEREIGN_OS_USER:-jfortin}"
SUITE="${SOVEREIGN_OS_SUITE:-trixie}"
MIRROR="${SOVEREIGN_OS_MIRROR:-http://deb.debian.org/debian}"
MNT=/mnt/sovereign-install
REPO_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# GUI desktop + dashboards on by default (operator directive 2026-07-02).
# Set SOVEREIGN_OS_INSTALL_GUI=0 for a headless install.
INSTALL_GUI="${SOVEREIGN_OS_INSTALL_GUI:-1}"

red()  { printf '\033[31m%s\033[0m\n' "$*"; }
grn()  { printf '\033[32m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
step() { printf '\n\033[36m━━━ %s\033[0m\n' "$*"; }

[ "$(id -u)" -eq 0 ] || { red "must run as root: sudo $0"; exit 1; }

# ── SAFETY ──
for d in "${ROOT_LV}" "${HOME_LV}" "${ESP_PART}"; do
  [ -b "$d" ] || { red "ABORT: ${d} missing — run setup-lvm-dualboot.sh + migrate-home.sh first"; exit 1; }
done
RUN_ROOT_DISK="/dev/$(lsblk -no PKNAME "$(findmnt -no SOURCE /)" | head -1)"
ESP_DISK="/dev/$(lsblk -no PKNAME "${ESP_PART}" | head -1)"
if [ "${ESP_DISK}" = "${RUN_ROOT_DISK}" ]; then
  red "ABORT: sovereign ESP ${ESP_PART} is on the RUNNING OS disk — wrong target."; exit 1
fi
id "${PRIMARY_USER}" >/dev/null 2>&1 || { red "ABORT: user ${PRIMARY_USER} doesn't exist on this host to inherit"; exit 1; }

# ── locate the custom kernel .debs ──
step "locating custom kernel .debs"
KDIR=""
[ -f /root/.sovereign-os/build-state/env-kernel-debs.sh ] && . /root/.sovereign-os/build-state/env-kernel-debs.sh || true
for cand in "${SOVEREIGN_OS_KERNEL_DEBS_DIR:-}" /mnt/kernel_forge /mnt/kernel_forge/linux-stable/..; do
  [ -n "$cand" ] && ls "$cand"/linux-image-6.12.0_*.deb >/dev/null 2>&1 && { KDIR="$cand"; break; }
done
[ -n "$KDIR" ] || { red "ABORT: can't find linux-image-6.12.0_*.deb (set SOVEREIGN_OS_KERNEL_DEBS_DIR)"; exit 1; }
KIMG=$(printf '%s\n' "$KDIR"/linux-image-6.12.0_*.deb | grep -v dbg | sort -V | tail -1)
KHDR=$(ls -1 "$KDIR"/linux-headers-6.12.0_*.deb 2>/dev/null | sort -V | tail -1 || true)
info "kernel image  : ${KIMG}"
info "kernel headers: ${KHDR:-none found; DKMS cannot build modules later without them}"

command -v debootstrap >/dev/null || { info "installing debootstrap…"; apt-get install -y debootstrap; }

# ── mount target root + bring up ESP + shared home ──
step "mounting lv_root + sovereign ESP"
mkdir -p "${MNT}"
mountpoint -q "${MNT}" || mount "${ROOT_LV}" "${MNT}"
mkdir -p "${MNT}/boot/efi"

# ── base system ──
step "debootstrap ${SUITE} → lv_root (a few minutes)"
if [ ! -x "${MNT}/bin/bash" ]; then
  debootstrap --arch=amd64 --components=main,contrib,non-free,non-free-firmware \
    "${SUITE}" "${MNT}" "${MIRROR}"
else
  info "base already present — skipping debootstrap"
fi

# ── inherit identity from the running host (no questions) ──
step "inheriting keyboard / locale / timezone / credentials"
for f in /etc/default/keyboard /etc/default/locale /etc/locale.gen /etc/localtime; do
  [ -e "$f" ] && cp -a "$f" "${MNT}${f}" && info "inherited ${f}"
done
# root + jfortin account lines (same uid/gid + same passwords)
inherit_user() {
  local u="$1" db
  for db in passwd shadow group gshadow; do
    if getent "$db" "$u" >/dev/null 2>&1 || grep -q "^${u}:" "/etc/${db}" 2>/dev/null; then
      grep "^${u}:" "/etc/${db}" 2>/dev/null | while IFS= read -r line; do
        grep -q "^${u}:" "${MNT}/etc/${db}" \
          && sed -i "s|^${u}:.*|${line}|" "${MNT}/etc/${db}" \
          || echo "$line" >> "${MNT}/etc/${db}"
      done
    fi
  done
}
inherit_user root
inherit_user "${PRIMARY_USER}"
# the user's groups jfortin belongs to (sudo etc.) — ensure sudo membership
info "inherited root + ${PRIMARY_USER} (uid $(id -u "${PRIMARY_USER}")) credentials"

# ── fstab: lv_root / , lv_home /home (THE shared home) , sovereign ESP /boot/efi ──
step "writing fstab (shared /home wired in)"
ROOT_UUID=$(blkid -s UUID -o value "${ROOT_LV}")
HOME_UUID=$(blkid -s UUID -o value "${HOME_LV}")
ESP_UUID=$(blkid -s UUID -o value "${ESP_PART}")
cat > "${MNT}/etc/fstab" <<EOF
# sovereign-os reflash-root — generated $(date -I)
UUID=${ROOT_UUID}  /          ext4  defaults,relatime           0  1
UUID=${HOME_UUID}  /home      ext4  defaults,relatime           0  2
UUID=${ESP_UUID}   /boot/efi  vfat  umask=0077,shortname=winnt  0  1
EOF
info "$(grep -c UUID "${MNT}/etc/fstab") mounts written"

# ── chroot setup ──
step "configuring inside the new root (kernel, lvm, grub, network)"
mount -o bind /dev  "${MNT}/dev"
mount -o bind /dev/pts "${MNT}/dev/pts"
mount -o bind /proc "${MNT}/proc"
mount -o bind /sys  "${MNT}/sys"
mount "${ESP_PART}" "${MNT}/boot/efi"
cp "${KIMG}" "${MNT}/tmp/"; [ -n "${KHDR}" ] && cp "${KHDR}" "${MNT}/tmp/" || true
cp /etc/resolv.conf "${MNT}/etc/resolv.conf"

cat > "${MNT}/tmp/chroot-setup.sh" <<CHROOT
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
echo "sovereign-os" > /etc/hostname
printf '127.0.0.1 localhost\n127.0.1.1 sovereign-os\n' > /etc/hosts

cat > /etc/apt/sources.list <<APT
deb ${MIRROR} ${SUITE} main contrib non-free non-free-firmware
deb ${MIRROR} ${SUITE}-updates main contrib non-free non-free-firmware
deb http://security.debian.org/debian-security ${SUITE}-security main contrib non-free non-free-firmware
APT
apt-get update

# essentials: lvm (root is on LVM!), bootloader, initramfs, login, net, sudo
# + python3 + PyYAML/jsonschema (the dashboard/operator daemons import yaml at
#   runtime) + node_exporter (scrapes the Layer-B textfile metrics).
apt-get install -y --no-install-recommends \
  lvm2 grub-efi-amd64 efibootmgr initramfs-tools \
  sudo locales console-setup keyboard-configuration \
  systemd-resolved netbase iproute2 isc-dhcp-client \
  python3 python3-yaml python3-jsonschema prometheus-node-exporter \
  ca-certificates curl nano less

# regenerate locale we inherited
locale-gen || true

# DHCP on wired interfaces via networkd
cat > /etc/systemd/network/20-wired.network <<NET
[Match]
Name=en* eth*
[Network]
DHCP=yes
NET
systemctl enable systemd-networkd systemd-resolved

# custom znver5 kernel (+ headers for DKMS). Emitted into chroot-setup.sh via the
# UNQUOTED heredoc above: the outer shell expands the basename subshells at
# write-time to bake the real filenames in, and the optional-header word-split is
# intentional. Do NOT use a bash array here — the outer shell would expand it to
# empty at write-time and install no kernel (leaving an unbootable image).
apt-get install -y /tmp/$(basename "${KIMG}") $( [ -n "${KHDR}" ] && echo /tmp/$(basename "${KHDR}") )

# jfortin: ensure sudo
usermod -aG sudo ${PRIMARY_USER} || true

# initramfs WITH lvm (so it can find root on /dev/mapper/sovereign-root)
update-initramfs -u -k all

# GRUB: root=lv_root, install to sovereign's own ESP, own bootloader id
sed -i 's|^GRUB_CMDLINE_LINUX=.*|GRUB_CMDLINE_LINUX="root=/dev/mapper/sovereign-root rw"|' /etc/default/grub
grub-install --target=x86_64-efi --efi-directory=/boot/efi \
  --bootloader-id=sovereign-os --recheck
update-grub
echo "CHROOT-OK"
CHROOT
chmod +x "${MNT}/tmp/chroot-setup.sh"
chroot "${MNT}" /tmp/chroot-setup.sh

# ── GUI desktop + dashboards (default ON — operator directive 2026-07-02) ──
# Runs while dev/proc/sys + resolv.conf are still bound (apt works in-chroot).
if [ "${INSTALL_GUI}" = 1 ]; then
  step "installing GUI desktop + dashboards (SOVEREIGN_OS_INSTALL_GUI=1)"
  STAGE=/opt/sovereign-os-src
  mkdir -p "${MNT}${STAGE}"
  for d in scripts webapp profiles config systemd share; do
    [ -d "${REPO_SRC}/${d}" ] && cp -a "${REPO_SRC}/${d}" "${MNT}${STAGE}/"
  done
  chroot "${MNT}" env \
    DEBIAN_FRONTEND=noninteractive \
    SOVEREIGN_OS_SRC="${STAGE}" \
    SOVEREIGN_OS_DESKTOP="${SOVEREIGN_OS_DESKTOP:-gnome}" \
    bash "${STAGE}/scripts/install/install-gui-dashboards.sh"
  info "GUI + dashboards installed (hub on :8100, launcher in app menu + autostart)"
else
  info "SOVEREIGN_OS_INSTALL_GUI=0 — headless install; run scripts/install/install-gui-dashboards.sh later to add the GUI"
fi

# ── cleanup ──
step "unmounting"
sync
umount "${MNT}/boot/efi" || true
umount "${MNT}/sys" "${MNT}/proc" "${MNT}/dev/pts" "${MNT}/dev" || true
umount "${MNT}" || true

grn "━━━ Phase 3 complete — sovereign-os installed ━━━"
cat <<EOF

Installed into lv_root: Debian ${SUITE} + your custom znver5 kernel, GRUB on
sovereign's ESP (${ESP_PART}), mounting the shared /home, with root + ${PRIMARY_USER}
(same passwords as this machine).

A new firmware boot entry 'sovereign-os' now exists. To boot it:
  reboot → firmware boot menu (F8 / F11 on the ProArt) → 'sovereign-os'
  (or it may appear in the boot order automatically)

Log in as ${PRIMARY_USER} with your usual password. Your files are already there
(shared /home). 'uname -r' → 6.12.0.

Your existing Debian is untouched on ${RUN_ROOT_DISK}; pick it from the same boot menu anytime.

This is a MUTABLE system: apt works. /home survives regardless of what you toggle.
EOF

if [ "${INSTALL_GUI}" = 1 ]; then
  cat <<EOF
GUI + dashboards are ON by default:
  - Debian ${SUITE} desktop (${SOVEREIGN_OS_DESKTOP:-gnome}) boots to graphical.target.
  - The dashboard hub runs on boot (loopback): http://127.0.0.1:8100/
  - Log in and look for "Sovereign Dashboards" — it's in the app menu, on the
    desktop, and auto-opens in the browser on first login.
Add the nvidia + zfs stack anytime (DKMS builds against the headers we installed).
EOF
else
  cat <<EOF
Headless install (SOVEREIGN_OS_INSTALL_GUI=0). Reach the dashboards over ssh /
loopback, or add the GUI later from inside sovereign-os:
  sudo scripts/install/install-gui-dashboards.sh
EOF
fi
