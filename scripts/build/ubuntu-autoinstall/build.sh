#!/usr/bin/env bash
# scripts/build/ubuntu-autoinstall/build.sh — the Ubuntu 26.04 LTS installer ISO.
#
# Produces a bootable installer that installs Ubuntu 26.04 "Resolute Raccoon"
# + KDE Plasma + the custom znver5 kernel + the sovereign-os cockpit onto the
# operator-selected NVMe, using the STANDARD Ubuntu installer (Subiquity)
# driven by an autoinstall answer file.
#
# WHY NOT simple-cdd/debian-installer, like the Debian path:
#   Ubuntu dropped debian-installer at 20.04. Subiquity does not read debconf
#   preseeds, so scripts/build/installer-cdd/ cannot be reused at all — not the
#   builder, not default.preseed. This remasters the OFFICIAL Ubuntu ISO
#   instead, which keeps the "it must be the normal installer" requirement from
#   the 2026-07-26 directive intact for Ubuntu.
#
# Unlike simple-cdd, xorriso is perfectly happy as root, so there is no
# drop-privileges dance here.
#
# Env:
#   SOVEREIGN_OS_BUILD_OUT       where the .iso lands (required in-pipeline)
#   SOVEREIGN_OS_PROFILE         profile id, names the artifact (default sain-01)
#   SOVEREIGN_OS_SUITE           ubuntu codename (default resolute)
#   SOVEREIGN_OS_KERNEL_DEBS_DIR custom kernel .debs (default: resolved by
#                                lib/kernel-debs.sh — step 04's state file, then
#                                the forge dir, then /mnt/kernel_forge)
#   SOVEREIGN_OS_UBUNTU_ISO      pre-downloaded ISO to remaster (skips fetch)
#   SOVEREIGN_OS_UBUNTU_ISO_CACHE cache dir (default /var/tmp/sovereign-ubuntu-iso)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${HERE}/../../.." && pwd)"
PROFILE="${SOVEREIGN_OS_PROFILE:-sain-01}"
SUITE="${SOVEREIGN_OS_SUITE:-resolute}"
RELEASE="26.04"
# Single-sourced: the two builders once had DIFFERENT hardcoded fallbacks,
# neither of which existed on the operator's machine (2026-07-29).
# shellcheck disable=SC1090,SC1091
. "$(dirname "$(dirname "$(readlink -f "$0")")")/lib/kernel-debs.sh"
KDIR="$(kernel_debs_dir)"
OUT="${SOVEREIGN_OS_BUILD_OUT:-${REPO}/build/${PROFILE}/output}"
# Scratch lives OUTSIDE the repo, exactly as installer-cdd does
# (SOVEREIGN_OS_CDD_WORK defaults to /var/tmp/sovereign-cdd).
#
# This was ${HERE}/tmp — inside the checkout — and build_cockpit_deb copies
# ${REPO}/scripts into ${WORK}/cockpit-pkg/opt/sovereign-os/, so the copy landed
# inside its own source and cp refused outright:
#   cp: cannot copy a directory, '…/scripts', into itself,
#       '…/scripts/build/ubuntu-autoinstall/tmp/cockpit-pkg/opt/sovereign-os/scripts'
# Caught on the first real Ubuntu build (2026-07-29). Also keeps a 6 GB ISO
# remaster and a multi-GB package pool out of the git working tree.
WORK="${SOVEREIGN_OS_UBUNTU_WORK:-/var/tmp/sovereign-ubuntu-work}"
POOL="${WORK}/pool"
ISO_CACHE="${SOVEREIGN_OS_UBUNTU_ISO_CACHE:-/var/tmp/sovereign-ubuntu-iso}"

log() { printf '\033[36m━━ ubuntu: %s\033[0m\n' "$*" >&2; }
die() { printf '\033[31m‼ ubuntu: %s\033[0m\n' "$*" >&2; exit 1; }

command -v xorriso >/dev/null || die "xorriso is required (sudo apt install xorriso)"

rm -rf "${WORK}"; mkdir -p "${WORK}" "${POOL}" "${OUT}" "${ISO_CACHE}"

# ── 1. custom kernel .debs ───────────────────────────────────────────────────
# FAIL NOW, not after a 3 GB download. The autoinstall pins linux-image-6.12.0
# as the GRUB default, so a build without it produces an ISO that installs a
# system booting the stock kernel — silently not what was asked for. The Debian
# path learned this the expensive way (2026-07-27).
log "staging custom kernel .debs from ${KDIR}"
if ls "${KDIR}"/linux-image-6.12.0_*.deb >/dev/null 2>&1; then
  cp -v "${KDIR}"/linux-{image,headers}-6.12.0_*.deb "${POOL}/"
else
  echo "‼ custom kernel .debs not found in ${KDIR}" >&2
  echo "  The autoinstall REQUIRES linux-image-6.12.0 / linux-headers-6.12.0." >&2
  echo "  Either:" >&2
  echo "    • point at them:  SOVEREIGN_OS_KERNEL_DEBS_DIR=/path/to/kernel-debs" >&2
  echo "    • or build them:  scripts/build/orchestrate.sh run   (steps 02-04)" >&2
  echo "  Refusing now rather than after the ISO download." >&2
  exit 1
fi

# ── 2. the cockpit .deb (shared builder — see lib/cockpit-deb.sh) ───────────
# shellcheck source=../lib/cockpit-deb.sh
. "${REPO}/scripts/build/lib/cockpit-deb.sh"
build_cockpit_deb "${REPO}" "${WORK}" "${POOL}"

# ── 3. the official Ubuntu ISO ──────────────────────────────────────────────
# Cached across runs: it is ~3 GB and never changes for a given point release.
BASE_ISO="${SOVEREIGN_OS_UBUNTU_ISO:-}"
if [ -z "${BASE_ISO}" ]; then
  BASE_ISO="${ISO_CACHE}/ubuntu-${RELEASE}-desktop-amd64.iso"
  if [ ! -f "${BASE_ISO}" ]; then
    _url="https://releases.ubuntu.com/${RELEASE}/ubuntu-${RELEASE}-desktop-amd64.iso"
    log "downloading ${_url} (once, cached in ${ISO_CACHE})"
    command -v wget >/dev/null || die "wget is required to fetch the Ubuntu ISO"
    wget -q --show-progress -O "${BASE_ISO}.part" "${_url}" \
      || die "Ubuntu ISO download failed — fetch it manually and pass SOVEREIGN_OS_UBUNTU_ISO=/path/to.iso"
    mv "${BASE_ISO}.part" "${BASE_ISO}"
  else
    log "reusing cached ISO: ${BASE_ISO}"
  fi
fi
[ -f "${BASE_ISO}" ] || die "base ISO not found: ${BASE_ISO}"

# ── 4. the autoinstall answer file ──────────────────────────────────────────
# `meta-data` must exist and may be empty — cloud-init's NoCloud datasource
# refuses the seed directory without it, and Subiquity then falls through to a
# fully interactive install with no explanation.
AI="${WORK}/autoinstall"
mkdir -p "${AI}"
cp "${HERE}/autoinstall/user-data" "${AI}/user-data"
: > "${AI}/meta-data"

# Render the profile into the answer file so building profile "test-02" cannot
# emit an ISO that writes active-profile=sain-01 — the exact bug the d-i builder
# had to fix (2026-07-26).
if [ "${PROFILE}" != "sain-01" ]; then
  log "rendering profile ${PROFILE} into the answer file"
  sed -i "s|echo sain-01 > /etc/sovereign-os/active-profile|echo ${PROFILE} > /etc/sovereign-os/active-profile|g; \
          s|SOVEREIGN_OS_PROFILE=sain-01|SOVEREIGN_OS_PROFILE=${PROFILE}|g" "${AI}/user-data"
fi

# ── render the KERNEL CMDLINE from the profile, TRANSLATED for Ubuntu ────────
# The profile's cmdline is written for the operator's proven Debian box, where
# `nomodeset` is load-bearing. On Ubuntu it is FATAL — 26.04's Plasma is
# Wayland-only and Wayland needs the DRM device nomodeset removes. Without this
# translation, a profile edit silently ships an Ubuntu ISO that installs a
# system booting to a blinking cursor (operator decision, 2026-07-29).
#
# distro_kernel_cmdline() strips nomodeset and guarantees nvidia-drm.modeset=1,
# preserving everything else the profile asked for. Same single source the
# runtime checks use via target_seat_cmdline_option().
_isd="${REPO}/scripts/install/lib/installed-system.sh"
_dsh="${REPO}/scripts/build/lib/distro.sh"
if [ -r "${_isd}" ] && [ -r "${_dsh}" ]; then
  # shellcheck disable=SC1090
  . "${_isd}"
  # shellcheck disable=SC1090
  SOVEREIGN_OS_DISTRO=ubuntu . "${_dsh}"
  _cmdline="$(SOVEREIGN_OS_DISTRO=ubuntu distro_kernel_cmdline "${SOVEREIGN_OS_KERNEL_CMDLINE}")"
  log "kernel cmdline for the installed system: ${_cmdline}"
  case "${_cmdline}" in
    *nomodeset*)
      die "refusing to build: the rendered cmdline still contains nomodeset (${_cmdline}). On Ubuntu that guarantees a dark screen." ;;
  esac
  # Both GRUB_CMDLINE_LINUX writers in the answer file, in one pass.
  sed -i "s|GRUB_CMDLINE_LINUX=\\\\\"[^\\\\]*\\\\\"|GRUB_CMDLINE_LINUX=\\\\\"${_cmdline}\\\\\"|g" \
    "${AI}/user-data"
else
  log "WARNING: cannot read the shared cmdline definition — shipping the answer file's default"
fi

# Fail before a 20-minute repack if the answer file is not valid YAML.
if command -v python3 >/dev/null; then
  python3 -c 'import sys,yaml; yaml.safe_load(open(sys.argv[1]))' "${AI}/user-data" \
    || die "autoinstall user-data is not valid YAML"
  log "autoinstall user-data parsed OK"
fi

# …and fail before the remaster if it names a package Ubuntu does not ship.
# Subiquity aborts on an unknown name AFTER partitioning; checking the archive
# index costs seconds. Counterpart of installer-cdd/verify-iso-has-packages.sh.
# Skips cleanly when offline — unverifiable is not the same as wrong.
_vpk="${HERE}/verify-packages-exist.sh"
if [ -x "${_vpk}" ]; then
  "${_vpk}" "${AI}/user-data" "${SUITE}" \
    || die "the autoinstall names package(s) Ubuntu ${RELEASE} does not have — refusing to build an ISO that aborts mid-install"
else
  log "WARNING: ${_vpk} missing — package names unverified"
fi

# ── 5. remaster ─────────────────────────────────────────────────────────────
# `-boot_image any replay` copies the ORIGINAL boot record forward, which is
# what keeps the result UEFI-bootable. Hand-rolling -e/-isohybrid options
# against a modern Ubuntu ISO is how you get an image that boots BIOS-only, or
# not at all.
ISO_OUT="${OUT}/${PROFILE}-ubuntu-installer.iso"
rm -f "${ISO_OUT}"
log "remastering → ${ISO_OUT}"
xorriso -indev "${BASE_ISO}" -outdev "${ISO_OUT}" \
  -boot_image any replay \
  -compliance no_emul_toc \
  -map "${AI}" /autoinstall \
  -map "${POOL}" /sovereign/pool \
  -- \
  || die "xorriso remaster failed"

# ── 6. tell the installer to use it ─────────────────────────────────────────
# `autoinstall ds=nocloud;s=/cdrom/autoinstall/` on the kernel line is what
# makes Subiquity read the seed instead of prompting for everything. The
# trailing slash is REQUIRED by the NoCloud datasource.
log "injecting the autoinstall boot argument into grub.cfg"
GRUBCFG="${WORK}/grub.cfg"
xorriso -indev "${ISO_OUT}" -osirrox on -extract /boot/grub/grub.cfg "${GRUBCFG}" 2>/dev/null \
  || die "could not extract grub.cfg from the remastered ISO"
# xorriso -osirrox PRESERVES THE ISO'S PERMISSIONS: the extracted file lands
# mode 0444, so the patcher below dies with
#   PermissionError: [Errno 13] Permission denied: '.../grub.cfg'
# and the build fails after the multi-GB remaster. Caught by running this
# against the real Ubuntu 26.04 ISO (2026-07-29) — a fixture with normal
# permissions never reproduces it.
chmod u+w "${GRUBCFG}" || die "could not make ${GRUBCFG} writable"
python3 - "${GRUBCFG}" <<'PY'
import re, sys

ARG = r"autoinstall ds=nocloud\;s=/cdrom/autoinstall/"

p = sys.argv[1]
t = open(p).read()


def add(m):
    """Insert the autoinstall args BEFORE casper's `---` separator.

    Ubuntu live ISOs end the kernel line with `---`, which separates kernel
    parameters from what is handed on to init/casper. Every documented
    autoinstall recipe puts the argument before it:

        linux /casper/vmlinuz autoinstall ds=nocloud\\;s=/cdrom/autoinstall/ ---

    The first version of this appended to the END of the line, i.e. AFTER the
    separator — which is not where Subiquity looks for it, and would have
    produced an ISO that boots straight into a fully interactive install while
    claiming to be seeded. Caught by testing the patcher against a realistic
    casper grub.cfg before any ISO was ever built (2026-07-28).
    """
    line = m.group(0).rstrip()
    if "autoinstall" in line:
        return line
    if "---" in line:
        head, sep, tail = line.partition("---")
        return f"{head.rstrip()} {ARG} {sep}{tail}".rstrip()
    return f"{line} {ARG}"


t, n = re.subn(r"^\s*linux\s+/casper/vmlinuz.*$", add, t, flags=re.M)
if n == 0:
    sys.exit("grub.cfg: no /casper/vmlinuz boot entries found — "
             "the ISO layout is not what this builder expects; refusing to "
             "ship an unseeded installer")
open(p, "w").write(t)
print(f"grub.cfg: {t.count('autoinstall ds=nocloud')} entr(y/ies) seeded")
PY
xorriso -dev "${ISO_OUT}" -boot_image any keep \
  -map "${GRUBCFG}" /boot/grub/grub.cfg -- \
  || die "could not write the patched grub.cfg back"

[ -s "${ISO_OUT}" ] || die "no ISO produced at ${ISO_OUT}"
log "done: ${ISO_OUT} ($(du -h "${ISO_OUT}" | cut -f1))"
log "  distro: Ubuntu ${RELEASE} LTS (${SUITE})   profile: ${PROFILE}"
log "  the installer STOPS for the operator at the disk pick and the account setup"
