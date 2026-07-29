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
# Honour the pipeline's output dir. Hardcoding sain-01 meant any other
# profile silently wrote its ISO into sain-01's output (2026-07-26).
OUT="${SOVEREIGN_OS_BUILD_OUT:-${REPO}/build/${SOVEREIGN_OS_PROFILE:-sain-01}/output}"
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
  # FAIL NOW, not in 25 minutes. The old behaviour was to warn "the install will
  # use the stock kernel" and continue -- but linux-image-6.12.0 and
  # linux-headers-6.12.0 are REQUIRED entries in profiles/sovereign.packages and
  # in pkgsel/include, so the build does not fall back: it downloads the whole
  # mirror and then dies with "missing required packages from profile sovereign".
  # That warning was simply wrong, and it costs a full mirror build to discover
  # on any machine that is not the one the kernel was compiled on (2026-07-27).
  echo "‼ custom kernel .debs not found in ${KDIR}" >&2
  echo "  The package lists REQUIRE linux-image-6.12.0 and linux-headers-6.12.0," >&2
  echo "  so this build cannot succeed without them. Either:" >&2
  echo "    • point at them:  SOVEREIGN_OS_KERNEL_DEBS_DIR=/path/to/kernel-debs" >&2
  echo "    • or build them:  scripts/build/orchestrate.sh run   (steps 02-04)" >&2
  echo "  Refusing now rather than after the mirror download." >&2
  exit 1
fi

# ── 2. build the sovereign-os-cockpit .deb from this repo ──
# The builder moved to scripts/build/lib/cockpit-deb.sh when the Ubuntu
# autoinstall substrate needed the identical package (2026-07-28). One copy,
# both installers — a second inline copy is exactly how the operator-deps and
# PEP 668 fixes ended up landing in one caller and not the other.
# shellcheck source=../lib/cockpit-deb.sh
. "${REPO}/scripts/build/lib/cockpit-deb.sh"
build_cockpit_deb "${REPO}" "${WORK}" "${LOCAL_PKGS}"

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
# simple-cdd reads 'mirror_components' (simple_cdd/variables.py). The name
# 'mirror_files_include' is not a simple-cdd variable at all, so it was
# silently ignored and the mirror carried only 'main' — build-simple-cdd
# then died with "missing required packages from profile sovereign:
# amd64-microcode firmware-amd-graphics …", every one of them
# non-free-firmware (2026-07-26).
export mirror_components="main contrib non-free-firmware"
local_packages="${LOCAL_PKGS}"
simple_cdd_dir="${HERE}"
# local d-i images (bypass simple-cdd's broken i386 auto-fetch on trixie)
custom_installer="${CI}"
export custom_installer="${CI}"
# amd64-only CD: trixie DROPPED the i386 installer, so tell debian-cd's boot-x86
# NOT to pull the 32-bit UEFI files (installer-i386/.../cd_info_i386 → 404/missing).
# The target is a 64-bit-UEFI znver5 box; 32-bit UEFI (Baytrail/old iMac) is moot.
export DISABLE_UEFI_32=1
# debian-cd, not simple-cdd, reads these two.
#
# NONFREE_COMPONENTS: tools/which_deb does
#   push @components, split / /, ENV{NONFREE_COMPONENTS}   if ENV{NONFREE}
# so with NONFREE set and this unset it splits undef -- the non-free components
# are DROPPED from the component list, with only an "uninitialized value"
# warning to show for it.
#
# DEP11=0: make_disc_trees.pl runs generate_firmware_patterns over
#   dists/CODENAME/COMPONENT/dep11/Components-ARCH.yml.gz
# to build the installer firmware-lookup patterns. Our offline mirror is built
# by reprepro and carries no DEP-11 AppStream metadata, so that step died with
#   missing metadata file .../main/dep11/Components-amd64.yml.gz
#   generate_firmware_patterns failed: 512
# the dep11 flag gates exactly ONE block (make_disc_trees.pl:1370) -- nothing else is
# skipped. The patterns only power d-i's "detect missing firmware" prompt; this
# profile installs firmware-* explicitly, so it never needs the lookup.
# NONFREE and NONFREE_COMPONENTS are DELIBERATELY NOT EXPORTED HERE.
# They live in profiles/sovereign.conf. Setting them in this environment does
# not work, and the failure is silent — see that file for the full derivation
# (root-caused 2026-07-29 after seven failed builds).
export CONTRIB=1
export DEP11=0
# Localization baked into every boot entry (simple-cdd adds debian-installer/locale
# + keyboard-configuration to the kernel line) so there's no language/keyboard
# prompt — the install goes straight to the substantive steps.
locale=en_US.UTF-8
export locale
keyboard=us
export keyboard
# GUIDED install: we deliberately do NOT set auto=true/priority=critical, and we do
# NOT redirect the console to serial — the installer must run ON THE OPERATOR'S
# SCREEN (tty0, the default). d-i uses the preseed for defaults (accounts, KDE +
# znver5 kernel + cockpit, the LVM recipe) but stops for the operator to pick and
# confirm the target disk. (An earlier build forced console=ttyS0 as the primary
# console for headless testing, which sent the whole installer UI to the serial
# port — off-screen on real hardware, looking frozen.)
CONF
# These two are copied because they get RENDERED below (hardware substitution).
cp "${HERE}/profiles/${PROFILE}.preseed"  "${WORK}/"
cp "${HERE}/profiles/${PROFILE}.packages" "${WORK}/"
# profiles/<PROFILE>.conf is deliberately NOT copied. build-simple-cdd finds it
# via find_profile_files(), which looks in "<d>/profiles/<name>" for each entry
# in simple_cdd_dirs — and simple_cdd_dir is HERE (the checkout), so the file is
# read where it sits. Copying it to "${WORK}/" would put it OUTSIDE that search
# path ("${WORK}/profiles/" is what would be scanned) and silently do nothing.

# ── render the HARDWARE-SPECIFIC bits from the shared definition ──
# nomodeset and the amdgpu/nouveau blacklist were chosen for ONE machine, where
# no GPU driver binds at all. On different hardware they are not neutral: they
# disable a driver that may work perfectly well, costing acceleration for no
# benefit. Baking them into the repo preseed made every ISO carry one box's
# workarounds (2026-07-27).
#
# installed-system.sh is the ONE definition of these; both values are
# overridable by environment. Render the WORK copy so a different profile or a
# different machine produces a correct ISO without editing a preseed by hand.
# The repo files keep the sain-01 values, so they stay valid and lint-checkable.
_isd="${REPO}/scripts/install/lib/installed-system.sh"
if [ -r "${_isd}" ]; then
  # shellcheck disable=SC1090
  . "${_isd}"
  _cmdline="${SOVEREIGN_OS_KERNEL_CMDLINE}"
  _blacklist="${SOVEREIGN_OS_MODULE_BLACKLIST}"
  log "rendering hardware config into the preseed:"
  log "  kernel cmdline : ${_cmdline}"
  log "  module blacklist: ${_blacklist}"
  sed -i \
    -e "s|^d-i debian-installer/add-kernel-opts string .*|d-i debian-installer/add-kernel-opts string ${_cmdline}|" \
    -e "s|for m in [a-z0-9 _-]*; do echo blacklist|for m in ${_blacklist}; do echo blacklist|" \
    "${WORK}/${PROFILE}.preseed"
  # default.preseed is the file d-i actually loads; render it the same way.
  if [ -f "${HERE}/profiles/default.preseed" ]; then
    cp "${HERE}/profiles/default.preseed" "${WORK}/"
    sed -i \
      -e "s|^d-i debian-installer/add-kernel-opts string .*|d-i debian-installer/add-kernel-opts string ${_cmdline}|" \
      -e "s|for m in [a-z0-9 _-]*; do echo blacklist|for m in ${_blacklist}; do echo blacklist|" \
      "${WORK}/default.preseed"
  fi

  # The PROFILE NAME and the machine identity are hardcoded to sain-01 too.
  # Building profile "test-02" produced an ISO that still wrote
  # /etc/sovereign-os/active-profile=sain-01 and set the hostname to
  # sovereign-os, so the installed system disagreed with the build that made it
  # (2026-07-27). Hostname and username stay overridable but default to the
  # existing values, so a plain sain-01 build is byte-identical to before.
  _hostname="${SOVEREIGN_OS_HOSTNAME:-sovereign-os}"
  _username="${SOVEREIGN_OS_USERNAME:-jfortin}"
  log "  profile        : ${PROFILE}"
  log "  hostname       : ${_hostname}"
  log "  primary user   : ${_username}"
  for _f in "${WORK}/${PROFILE}.preseed" "${WORK}/default.preseed"; do
    [ -f "${_f}" ] || continue
    sed -i \
      -e "s|echo sain-01 > /etc/sovereign-os/active-profile|echo ${PROFILE} > /etc/sovereign-os/active-profile|" \
      -e "s|echo SOVEREIGN_OS_PROFILE=sain-01|echo SOVEREIGN_OS_PROFILE=${PROFILE}|" \
      -e "s|^d-i netcfg/get_hostname string .*|d-i netcfg/get_hostname string ${_hostname}|" \
      -e "s|^d-i netcfg/hostname string .*|d-i netcfg/hostname string ${_hostname}|" \
      -e "s|^d-i passwd/user-fullname string .*|d-i passwd/user-fullname string ${_username}|" \
      -e "s|^d-i passwd/username string .*|d-i passwd/username string ${_username}|" \
      "${_f}"
  done
else
  # If the operator ASKED for a different target, silently shipping the built-in
  # sain-01 config is a wrong answer, not a degraded one: the panel would accept
  # hostname=lab-box, report success, and hand back an ISO that installs
  # "sovereign-os". Fail loudly in that case; warn only when nothing was asked
  # for (2026-07-27).
  if [ -n "${SOVEREIGN_OS_HOSTNAME:-}${SOVEREIGN_OS_USERNAME:-}${SOVEREIGN_OS_KERNEL_CMDLINE:-}${SOVEREIGN_OS_MODULE_BLACKLIST+set}" ]; then
    echo "‼ target-machine settings were supplied but ${_isd} is unreadable," >&2
    echo "  so they cannot be applied. Refusing to build an ISO that silently" >&2
    echo "  carries this box's hostname, user and GPU workarounds instead." >&2
    exit 1
  fi
  log "WARNING: ${_isd} unreadable — preseed keeps its built-in hardware config"
fi

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
# --profiles collects the profile's {preseed,packages}; --auto-profiles (-a) is
# what actually SELECTS it at install time — it emits the 'simple-cdd/profiles=
# sovereign' boot arg so the simple-cdd-profiles udeb ships + applies our
# sovereign.preseed (root pw, LVM recipe, tasksel KDE, late_command). Without
# --auto-profiles the profile is merely "available" and d-i falls back to the
# stock default.preseed → the install stalls asking for a root password, etc.
# STREAM it. This was `| tail -60`, which buffers the ENTIRE run and prints only
# the tail at the end -- so the longest phase of the build (mirror download,
# ~25 min) showed the operator nothing and was indistinguishable from a hang
# (2026-07-27). `sed -u` is unbuffered, so lines appear as produced. The full
# log is kept because the live stream scrolls past. `set -o pipefail` is in
# effect, so build-simple-cdd's own exit status still governs the pipeline.
_cddlog="${WORK}/build-simple-cdd.log"
_t0=$(date +%s)
build-simple-cdd --dvd --dist "${DIST}" \
  --profiles "${PROFILE}" --auto-profiles "${PROFILE}" \
  --local-packages "${LOCAL_PKGS}" \
  --conf "${WORK}/sovereign.conf" 2>&1 \
  | tee "${_cddlog}" \
  | sed -u 's/^/    cdd: /'
_el=$(( $(date +%s) - _t0 ))
log "build-simple-cdd finished in $((_el / 60))m $((_el % 60))s (full log: ${_cddlog})"

# simple-cdd writes the ISO to ${simple_cdd_dir}/images (= ${HERE}/images), not
# the CWD/WORK. Look there first, then WORK, for robustness.
_iso="$(ls -1t "${HERE}"/images/*.iso "${WORK}"/images/*.iso 2>/dev/null | head -1 || true)"
if [ -z "${_iso}" ]; then
  echo "‼ no ISO produced — check the build-simple-cdd output above" >&2
  exit 1
fi

# ── 5. post-process the ISO so it AUTO-BOOTS the installer ──
# debian-cd's grub.cfg + isolinux.cfg have NO timeout (the stock d-i behaviour is
# "wait for the operator to pick"), so a flashed USB would sit on the menu forever.
# Append a grub timeout + default: the TEXT "Install" entry, which needs no GPU
# (the graphical entry can hang on very new hardware like znver5). On screen only
# — no serial redirect (that hid the whole installer off-screen on real hardware).
log "post-processing: grub auto-boot (timeout=10, default=text Install)"
cat > "${WORK}/grub-add.cfg" <<'GRUBADD'

# ── sovereign-os: auto-boot the text installer on screen after 10s ──
set timeout=10
set default='Install'
GRUBADD
xorriso -osirrox on -indev "${_iso}" -cpx /boot/grub/grub.cfg "${WORK}/grub.cfg.orig" 2>/dev/null || {
  echo "‼ could not read grub.cfg from the ISO" >&2; exit 1; }
cat "${WORK}/grub.cfg.orig" "${WORK}/grub-add.cfg" > "${WORK}/grub.cfg.new"
_iso_final="${WORK}/sain-01-installer.iso"
rm -f "${_iso_final}"
xorriso -indev "${_iso}" -outdev "${_iso_final}" \
  -boot_image any replay -overwrite on \
  -map "${WORK}/grub.cfg.new" /boot/grub/grub.cfg 2>&1 | tail -4
[ -s "${_iso_final}" ] || { echo "‼ re-master produced no ISO" >&2; exit 1; }

cp -v "${_iso_final}" "${OUT}/sain-01-installer.iso"
log "installer ISO → ${OUT}/sain-01-installer.iso ($(du -h "${OUT}/sain-01-installer.iso" | cut -f1))"
