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

# ONE definition of what an installed root contains — shared with the from-host
# installer (scripts/install/install-sovereign-root.sh). Both surfaces used to
# carry their own copy of the package list, so the bootable installer would have
# built the same terminal-less desktop even after the other was fixed.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../install" && pwd)/lib/installed-system.sh"
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

# ── kernel: the CUSTOM znver5 kernel (crown jewel) if built, else stock + a LOUD
#    warning (never a silent fallback — the custom kernel is core to sovereign-os).
#    SOVEREIGN_OS_STOCK_KERNEL=1 forces stock; SOVEREIGN_OS_REQUIRE_CUSTOM_KERNEL=1
#    makes a missing custom kernel FATAL. ──
KDIR="${SOVEREIGN_OS_KERNEL_DEBS_DIR:-}"
if [ -z "${KDIR}" ] && [ -r /root/.sovereign-os/build-state/env-kernel-debs.sh ]; then
  # shellcheck source=/dev/null
  . /root/.sovereign-os/build-state/env-kernel-debs.sh || true
  KDIR="${SOVEREIGN_OS_KERNEL_DEBS_DIR:-}"
fi
KERNEL_PKGS="linux-image-amd64 linux-headers-amd64"
if [ "${SOVEREIGN_OS_STOCK_KERNEL:-0}" != "1" ] && [ -n "${KDIR}" ] && ls "${KDIR}"/linux-image-6.12.0_*.deb >/dev/null 2>&1; then
  _kimg="$(ls -1 "${KDIR}"/linux-image-6.12.0_*.deb | grep -v dbg | sort -V | tail -1)"
  _khdr="$(ls -1 "${KDIR}"/linux-headers-6.12.0_*.deb 2>/dev/null | sort -V | tail -1 || true)"
  cp "${_kimg}" "${STAGE}/tmp/"; [ -n "${_khdr}" ] && cp "${_khdr}" "${STAGE}/tmp/" || true
  KERNEL_PKGS="/tmp/$(basename "${_kimg}") $([ -n "${_khdr}" ] && echo "/tmp/$(basename "${_khdr}")")"
  log "custom znver5 kernel → $(basename "${_kimg}")"
else
  red "‼ custom kernel .debs NOT found (SOVEREIGN_OS_KERNEL_DEBS_DIR='${KDIR:-unset}') — building with the STOCK Debian kernel."
  red "  build the znver5 kernel first: sudo scripts/build/orchestrate.sh rewind 02 && … run"
  if [ "${SOVEREIGN_OS_REQUIRE_CUSTOM_KERNEL:-0}" = "1" ]; then
    red "  SOVEREIGN_OS_REQUIRE_CUSTOM_KERNEL=1 set — refusing to build a stock-kernel rootfs."; exit 1
  fi
fi

log "installing base OS + kernel + LVM/GRUB tooling"
cat > "${STAGE}/etc/apt/sources.list" <<APT
deb ${MIRROR} ${SUITE} main contrib non-free non-free-firmware
deb ${MIRROR} ${SUITE}-updates main contrib non-free non-free-firmware
deb http://security.debian.org/debian-security ${SUITE}-security main contrib non-free non-free-firmware
APT
chroot "${STAGE}" env DEBIAN_FRONTEND=noninteractive KERNEL_PKGS="${KERNEL_PKGS}" \
  SOVEREIGN_OS_INSTALLED_PACKAGES="$(sovereign_os_installed_packages)" bash -c '
  set -e
  apt-get update
  apt-get install -y --no-install-recommends ${SOVEREIGN_OS_INSTALLED_PACKAGES}
  # kernel last (may be local .deb paths for the custom znver5 kernel)
  apt-get install -y ${KERNEL_PKGS}
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
