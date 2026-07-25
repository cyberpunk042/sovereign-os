#!/usr/bin/env bash
# scripts/build/build-target-rootfs.sh — build the COMPLETE sovereign-os target
# rootfs at BUILD time and squash it, so the installer USB is fully self-contained
# (offline install: no debootstrap/apt over the network on the target).
#
# Produces a squashfs of a mutable Debian 13 root with: the stock kernel, LVM +
# GRUB-EFI tooling, KDE Plasma (+ sddm) + the sovereign-os dashboards, python +
# node_exporter, and the sovereign-os repo baked at /opt/sovereign-os-src. The
# installer (install-sovereign-root.sh in SQUASHFS mode) unsquashes this onto the
# sovereign-root LV and does only the per-machine wiring (fstab/GRUB/identity).
#
# Deliberately NOT machine-specific: no fstab UUIDs, no grub-install, no ESP — the
# installer adds those. The GPU/AI/model stack is out of scope (installed-off,
# hardware-dependent, huge) — enabled on-demand post-install.
#
# Env: SOVEREIGN_OS_STAGE_DIR (required, staging root) · SOVEREIGN_OS_ROOTFS_OUT
#      (required, output .squashfs) · SOVEREIGN_OS_FRONTEND (default kde-plasma) ·
#      SOVEREIGN_OS_SUITE (trixie) · SOVEREIGN_OS_MIRROR · SOVEREIGN_OS_ROOT (repo)
set -euo pipefail

STAGE="${SOVEREIGN_OS_STAGE_DIR:?set SOVEREIGN_OS_STAGE_DIR}"
OUT="${SOVEREIGN_OS_ROOTFS_OUT:?set SOVEREIGN_OS_ROOTFS_OUT}"
SUITE="${SOVEREIGN_OS_SUITE:-trixie}"
MIRROR="${SOVEREIGN_OS_MIRROR:-http://deb.debian.org/debian}"
FRONTEND="${SOVEREIGN_OS_FRONTEND:-kde-plasma}"
FRONTEND_INSTALL="${SOVEREIGN_OS_FRONTEND_INSTALL:-kde-plasma,gnome,dashboards-kiosk}"
REPO_SRC="${SOVEREIGN_OS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

log()  { printf '\033[36m━━ build-rootfs: %s\033[0m\n' "$*" >&2; }
info() { printf '  %s\n' "$*" >&2; }

[ "$(id -u)" -eq 0 ] || { echo "must run as root" >&2; exit 1; }
command -v debootstrap >/dev/null || { info "installing debootstrap…"; apt-get install -y debootstrap; }
command -v mksquashfs  >/dev/null || { info "installing squashfs-tools…"; apt-get install -y squashfs-tools; }

# ── clean staging ──
rm -rf "${STAGE}"; mkdir -p "${STAGE}"

log "debootstrap ${SUITE} → staging (downloads the base — a few minutes)"
debootstrap --arch=amd64 --components=main,contrib,non-free,non-free-firmware \
  "${SUITE}" "${STAGE}" "${MIRROR}"

# ── chroot bind mounts ──
mount -o bind /dev  "${STAGE}/dev"
mount -o bind /dev/pts "${STAGE}/dev/pts"
mount -o bind /proc "${STAGE}/proc"
mount -o bind /sys  "${STAGE}/sys"
cp /etc/resolv.conf "${STAGE}/etc/resolv.conf"
cleanup() {
  umount -l "${STAGE}/dev/pts" 2>/dev/null || true
  umount -l "${STAGE}/dev"     2>/dev/null || true
  umount -l "${STAGE}/proc"    2>/dev/null || true
  umount -l "${STAGE}/sys"     2>/dev/null || true
}
trap cleanup EXIT

# ── base OS packages (mirror install-sovereign-root's chroot list) + stock kernel ──
log "installing base OS + stock kernel + LVM/GRUB tooling"
cat > "${STAGE}/etc/apt/sources.list" <<APT
deb ${MIRROR} ${SUITE} main contrib non-free non-free-firmware
deb ${MIRROR} ${SUITE}-updates main contrib non-free non-free-firmware
deb http://security.debian.org/debian-security ${SUITE}-security main contrib non-free non-free-firmware
APT
chroot "${STAGE}" env DEBIAN_FRONTEND=noninteractive bash -c '
  set -e
  apt-get update
  apt-get install -y --no-install-recommends \
    lvm2 grub-efi-amd64 efibootmgr initramfs-tools \
    sudo locales console-setup keyboard-configuration \
    systemd-resolved netbase iproute2 isc-dhcp-client \
    python3 python3-yaml python3-jsonschema prometheus-node-exporter \
    ca-certificates curl nano less \
    linux-image-amd64 linux-headers-amd64
  systemctl enable systemd-networkd systemd-resolved
'

# ── KDE desktop + sovereign-os dashboards (the "everything" that must be offline) ──
log "installing ${FRONTEND} desktop + sovereign-os dashboards"
STAGE_SRC=/opt/sovereign-os-src
mkdir -p "${STAGE}${STAGE_SRC}"
for d in scripts webapp profiles config systemd share; do
  [ -d "${REPO_SRC}/${d}" ] && cp -a "${REPO_SRC}/${d}" "${STAGE}${STAGE_SRC}/"
done
chroot "${STAGE}" env \
  DEBIAN_FRONTEND=noninteractive \
  SOVEREIGN_OS_SRC="${STAGE_SRC}" \
  SOVEREIGN_OS_FRONTEND="${FRONTEND}" \
  SOVEREIGN_OS_FRONTEND_INSTALL="${FRONTEND_INSTALL}" \
  SOVEREIGN_OS_DESKTOP="${FRONTEND}" \
  bash "${STAGE_SRC}/scripts/install/install-gui-dashboards.sh"

# ── shrink: drop the apt cache (the target repo isn't needed — it's all installed) ──
chroot "${STAGE}" apt-get clean
rm -rf "${STAGE}/var/lib/apt/lists/"* "${STAGE}/tmp/"* "${STAGE}/var/tmp/"*

cleanup; trap - EXIT

# ── squash ──
log "squashing rootfs → ${OUT}"
mkdir -p "$(dirname "${OUT}")"
rm -f "${OUT}"
mksquashfs "${STAGE}" "${OUT}" -comp zstd -noappend -no-progress
info "rootfs squashfs: $(du -h "${OUT}" | cut -f1)  ${OUT}"
log "done — a complete, offline-installable KDE + sovereign-os root"
