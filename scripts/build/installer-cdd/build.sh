#!/usr/bin/env bash
# scripts/build/installer-cdd/build.sh — build the OFFLINE debian-installer ISO
# for sovereign-os (SDD-013 amended path: standard d-i, fresh LVM install).
#
# Produces an installer CD (via simple-cdd) that installs Debian 13 + KDE + the
# custom znver5 kernel + the sovereign-os cockpit onto the target NVMe, fully
# offline (the CD carries the package mirror). Everything the install needs is
# on the CD — no downloads at install time.
#
# The custom kernel + the cockpit ride as LOCAL packages in the CD's apt repo:
#   - linux-image-6.12.0 / linux-headers-6.12.0  (from the kernel forge)
#   - sovereign-os-cockpit                        (built here from this repo)
# so d-i installs them the normal apt way (preseed pkgsel/include).
#
# Needs network at BUILD time (simple-cdd downloads the KDE mirror ~GBs).
# Run as a NON-root user — simple-cdd refuses root:  scripts/build/installer-cdd/build.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${HERE}/../../.." && pwd)"
PROFILE="sovereign"
DIST="${SOVEREIGN_OS_SUITE:-trixie}"
KDIR="${SOVEREIGN_OS_KERNEL_DEBS_DIR:-/mnt/kernel_forge/kernel-debs}"
WORK="${SOVEREIGN_OS_CDD_WORK:-/var/tmp/sovereign-cdd}"
OUT="${REPO}/build/sain-01/output"
LOCAL_PKGS="${WORK}/local-packages"

log() { printf '\033[36m━━ cdd: %s\033[0m\n' "$*" >&2; }
[ "$(id -u)" -ne 0 ] || { echo "run as a NON-root user — simple-cdd refuses to run as root" >&2; exit 1; }
command -v build-simple-cdd >/dev/null || { echo "install simple-cdd" >&2; exit 1; }

rm -rf "${WORK}"; mkdir -p "${WORK}" "${LOCAL_PKGS}" "${OUT}"

# simple-cdd writes its scratch (partial mirror + reprepro db) to ${HERE}/tmp —
# INSIDE the repo. A stale/partial tree from a failed prior run causes reprepro
# checksum collisions and confusing debian-cd errors, so start clean by default.
# The (expensive) d-i images live in their own cache, untouched. Keep the mirror
# across runs only when explicitly iterating: SOVEREIGN_OS_CDD_KEEP_TMP=1.
if [ "${SOVEREIGN_OS_CDD_KEEP_TMP:-0}" != "1" ]; then
  rm -rf "${HERE}/tmp"
fi

# ── 1. custom kernel .debs → local packages ──
log "staging custom kernel .debs"
if ls "${KDIR}"/linux-image-6.12.0_*.deb >/dev/null 2>&1; then
  cp -v "${KDIR}"/linux-{image,headers}-6.12.0_*.deb "${LOCAL_PKGS}/"
else
  echo "‼ custom kernel .debs not in ${KDIR} — the install will use the stock kernel" >&2
fi

# ── 2. build the sovereign-os-cockpit .deb from this repo ──
log "building sovereign-os-cockpit.deb (the cockpit + reflash scripts + first-boot)"
PKGROOT="${WORK}/cockpit-pkg"
rm -rf "${PKGROOT}"; mkdir -p "${PKGROOT}/DEBIAN" "${PKGROOT}/opt/sovereign-os"
for d in scripts webapp profiles config systemd share; do
  [ -d "${REPO}/${d}" ] && cp -a "${REPO}/${d}" "${PKGROOT}/opt/sovereign-os/"
done
# CRITICAL: the cockpit payload is SOURCE ONLY. simple-cdd's scratch mirror lands
# at scripts/build/installer-cdd/tmp (inside the repo); copying it would bloat the
# .deb to multi-GB and collide in reprepro. Strip all build scratch + py caches.
rm -rf "${PKGROOT}/opt/sovereign-os/scripts/build/installer-cdd/tmp"
find "${PKGROOT}/opt/sovereign-os" -depth -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find "${PKGROOT}/opt/sovereign-os" -type f -name '*.pyc' -delete 2>/dev/null || true
_cksz="$(du -sm "${PKGROOT}/opt/sovereign-os" | cut -f1)"
[ "${_cksz}" -lt 200 ] || { echo "‼ cockpit payload is ${_cksz}MB — build scratch leaked in; refusing" >&2; exit 1; }
cat > "${PKGROOT}/DEBIAN/control" <<CTRL
Package: sovereign-os-cockpit
Version: 1.0.0
Architecture: all
Section: admin
Priority: optional
Maintainer: cyberpunk042 <noreply@sovereign-os>
Depends: python3, python3-yaml, bash
Description: sovereign-os cockpit + operator tooling
 The sovereign-os dashboards/cockpit, operator scripts, profiles and configs,
 installed to /opt/sovereign-os. Its postinst wires the GUI dashboards.
CTRL
cat > "${PKGROOT}/DEBIAN/postinst" <<'POSTINST'
#!/bin/sh
set -e
# best-effort: wire the dashboards launcher (the desktop is installed by the task)
if [ -x /opt/sovereign-os/scripts/install/install-gui-dashboards.sh ]; then
  SOVEREIGN_OS_SRC=/opt/sovereign-os SOVEREIGN_OS_FRONTEND=kde-plasma \
    bash /opt/sovereign-os/scripts/install/install-gui-dashboards.sh || true
fi
mkdir -p /etc/sovereign-os
[ -f /etc/sovereign-os/active-profile ] || echo sain-01 > /etc/sovereign-os/active-profile
exit 0
POSTINST
chmod 0755 "${PKGROOT}/DEBIAN/postinst"
dpkg-deb --root-owner-group --build "${PKGROOT}" "${LOCAL_PKGS}/sovereign-os-cockpit_1.0.0_all.deb"

# ── 2b. debian-installer images (custom_installer) ──
# simple-cdd's auto-fetch unconditionally downloads the i386 installer for amd64
# builds (build-simple-cdd line ~290), but trixie DROPPED installer-i386 → a
# guaranteed 404 that kills the build. Bypass it: mirror the amd64 d-i images
# locally and point simple-cdd at them via custom_installer (cached across runs).
CI="${WORK}/custom-installer"
CI_CACHE="${SOVEREIGN_OS_CDD_DI_CACHE:-/var/tmp/sovereign-di-images}"
if [ -d "${CI_CACHE}/installer-amd64/current/images" ]; then
  log "reusing cached d-i images: ${CI_CACHE}"
  cp -a "${CI_CACHE}" "${CI}"
else
  log "downloading trixie amd64 debian-installer images (once, cached)…"
  mkdir -p "${CI_CACHE}/installer-amd64"
  wget -q -r -np -nH -e robots=off --cut-dirs=5 -R 'index.html*' \
    -P "${CI_CACHE}/installer-amd64" \
    "http://deb.debian.org/debian/dists/${DIST}/main/installer-amd64/current/" \
    || { echo "d-i image download failed" >&2; exit 1; }
  cp -a "${CI_CACHE}" "${CI}"
fi
[ -d "${CI}/installer-amd64/current/images" ] || { echo "d-i images not laid out as expected under ${CI}" >&2; exit 1; }

# ── 3. simple-cdd config ──
log "writing simple-cdd config"
cat > "${WORK}/sovereign.conf" <<CONF
export PROFILES="${PROFILE}"
export DIST="${DIST}"
profiles="${PROFILE}"
dist="${DIST}"
# offline: bundle everything the profile packages resolve to
export mirror_files_include="main contrib non-free non-free-firmware"
local_packages="${LOCAL_PKGS}"
simple_cdd_dir="${HERE}"
# local d-i images (bypass simple-cdd's broken i386 auto-fetch on trixie)
custom_installer="${CI}"
export custom_installer="${CI}"
# amd64-only CD: trixie DROPPED the i386 installer, so tell debian-cd's boot-x86
# NOT to pull the 32-bit UEFI files (installer-i386/.../cd_info_i386 → 404/missing).
# The target is a 64-bit-UEFI znver5 box; 32-bit UEFI (Baytrail/old iMac) is moot.
export DISABLE_UEFI_32=1
CONF
# simple-cdd looks for <profile>.{preseed,packages,conf} in the profiles dir.
cp "${HERE}/profiles/${PROFILE}.preseed"  "${WORK}/"
cp "${HERE}/profiles/${PROFILE}.packages" "${WORK}/"

# ── 4. build ──
# When reusing tmp (KEEP_TMP), the reprepro db already has the prior run's LOCAL
# packages; a freshly-built cockpit .deb (new DEBIAN/* mtimes → new checksum)
# would collide on re-inclusion. Clear the local records first (keeps the mirror).
_REPRO="${HERE}/tmp/mirror"
if [ -d "${_REPRO}/db" ] && command -v reprepro >/dev/null; then
  log "clearing prior local-package records from reprepro (keeping the mirror)"
  for p in sovereign-os-cockpit linux-image-6.12.0 linux-headers-6.12.0; do
    reprepro -b "${_REPRO}" remove "${DIST}" "$p" >/dev/null 2>&1 || true
  done
fi

log "running build-simple-cdd (downloads the KDE mirror — long)…"
cd "${WORK}"
# --dvd: DISKTYPE=DVD. The KDE + custom-kernel + cockpit closure is ~1.7GB; a
# default CD image (~700MB) placed only 620MB and spilled the rest (all the KDE
# packages, the kernel, the cockpit) onto CD2/3 that we don't build → "missing
# required packages from profile". A single DVD-sized image holds it all.
build-simple-cdd --dvd --dist "${DIST}" --profiles "${PROFILE}" \
  --local-packages "${LOCAL_PKGS}" \
  --conf "${WORK}/sovereign.conf" 2>&1 | tail -60

_iso="$(ls -1 "${WORK}"/images/*.iso 2>/dev/null | head -1 || true)"
if [ -n "${_iso}" ]; then
  cp -v "${_iso}" "${OUT}/sain-01-installer.iso"
  log "installer ISO → ${OUT}/sain-01-installer.iso ($(du -h "${OUT}/sain-01-installer.iso" | cut -f1))"
else
  echo "‼ no ISO produced — check the build-simple-cdd output above" >&2
  exit 1
fi
