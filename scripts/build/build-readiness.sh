#!/usr/bin/env bash
# scripts/build/build-readiness.sh — can THIS host complete THIS build, right now?
#
# WHY. The existing preflight hooks (scripts/hooks/pre-install/*) check the
# TARGET machine — network, storage, TPM. Nothing checked whether the BUILD host
# can actually produce an artifact, so every gap was discovered the expensive
# way: after a 30-minute kernel compile, or after a multi-GB mirror download.
# The installer-cdd builder learned this once already and added its own
# kernel-.deb check "rather than after the mirror download" (2026-07-27); this
# generalises that instinct to the whole pipeline.
#
# It is ARTIFACT- and DISTRO-aware: it demands only what the selected path
# needs. Building the Debian installer does not require mkosi or a root
# password; building the mkosi appliance does not require simple-cdd.
#
# Read-only. Installs nothing, mounts nothing, writes nothing.
#
# Usage:
#   scripts/build/build-readiness.sh                 # the active/default path
#   SOVEREIGN_OS_DISTRO=ubuntu SOVEREIGN_OS_ARTIFACT=installer  ...
#   scripts/build/build-readiness.sh --all           # every artifact x distro
#
# Exit: 0 ready · 1 blocking gap(s) · never fails on warnings alone.
set -uo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib/distro.sh
. "${__SCRIPT_DIR}/lib/distro.sh"

: "${SOVEREIGN_OS_ARTIFACT:=image}"
: "${SOVEREIGN_OS_PROFILE:=sain-01}"
: "${SOVEREIGN_OS_FORGE_DIR:=/mnt/kernel_forge}"

BLOCKERS=0
WARNINGS=0

c_ok=$'\033[32m'; c_bad=$'\033[31m'; c_warn=$'\033[33m'; c_dim=$'\033[2m'; c_off=$'\033[0m'
[ -t 1 ] || { c_ok=""; c_bad=""; c_warn=""; c_dim=""; c_off=""; }

ok()    { printf '  %sok%s      %s\n' "$c_ok" "$c_off" "$1"; }
blocker(){ printf '  %sBLOCK%s   %s\n' "$c_bad" "$c_off" "$1"; [ -n "${2:-}" ] && printf '          %sfix: %s%s\n' "$c_dim" "$2" "$c_off"; BLOCKERS=$((BLOCKERS+1)); }
warn()  { printf '  %swarn%s    %s\n' "$c_warn" "$c_off" "$1"; [ -n "${2:-}" ] && printf '          %s%s%s\n' "$c_dim" "$2" "$c_off"; WARNINGS=$((WARNINGS+1)); }
head_() { printf '\n%s── %s%s\n' "$c_dim" "$1" "$c_off"; }

# A tool counts as present if it is anywhere a ROOT build would find it.
# /sbin and /usr/sbin are NOT on a normal user's PATH, so `command -v losetup`
# reports missing on a host where the actual build (which runs as root via
# pkexec/sudo) would find it perfectly well. Checking the sbin paths directly
# avoids sending the operator to install something they already have.
have() {
  command -v "$1" >/dev/null 2>&1 && return 0
  for d in /sbin /usr/sbin /usr/local/sbin; do [ -x "$d/$1" ] && return 0; done
  return 1
}

need_tool() { # <tool> <apt-package> <why>
  if have "$1"; then ok "$1 — $3"
  else blocker "$1 MISSING — $3" "sudo apt install $2"; fi
}

# ── the resolved plan ────────────────────────────────────────────────────────
report_plan() {
  distro_validate || exit 1
  case "${SOVEREIGN_OS_ARTIFACT}:${SOVEREIGN_OS_DISTRO}" in
    installer:ubuntu)  SUBSTRATE=ubuntu-autoinstall ;;
    installer:*)       SUBSTRATE=installer-cdd ;;
    installer-live:*)  SUBSTRATE=live-build ;;
    *)                 SUBSTRATE=mkosi ;;
  esac
  printf '%s══ build readiness ══%s  profile=%s  distro=%s (%s)  artifact=%s  → substrate=%s\n' \
    "$c_dim" "$c_off" "${SOVEREIGN_OS_PROFILE}" "${SOVEREIGN_OS_DISTRO}" \
    "$(distro_suite)" "${SOVEREIGN_OS_ARTIFACT}" "${SUBSTRATE}"
}

check_common() {
  head_ "common"
  need_tool python3  python3      "profile/YAML handling in every step"
  need_tool git      git          "kernel fetch + repo signature"
  need_tool dpkg-deb dpkg-dev     "builds the sovereign-os-cockpit package"
  need_tool make     make         "kernel build"

  local free_g; free_g=$(df -BG --output=avail . 2>/dev/null | tail -1 | tr -dc '0-9')
  if [ "${free_g:-0}" -ge 60 ]; then ok "disk: ${free_g}G free"
  else blocker "disk: only ${free_g}G free — a mirror + ISO needs ~60G" "free space or set SOVEREIGN_OS_BUILD_OUT elsewhere"; fi
}

check_kernel() {
  head_ "custom kernel (znver5)"
  local kdir="${SOVEREIGN_OS_KERNEL_DEBS_DIR:-${SOVEREIGN_OS_FORGE_DIR}}"
  if ls "${kdir}"/linux-image-6.12.0_*.deb >/dev/null 2>&1; then
    ok "kernel .debs present in ${kdir}"
    return
  fi
  # Both installers REQUIRE these; the appliance can fall back to the stock kernel.
  case "${SUBSTRATE}" in
    installer-cdd|ubuntu-autoinstall)
      blocker "no linux-image-6.12.0 .deb in ${kdir} — both installers require it" \
              "scripts/build/orchestrate.sh run   (steps 02-04, ~30min) — or set SOVEREIGN_OS_KERNEL_DEBS_DIR" ;;
    *)
      warn "no custom kernel .debs in ${kdir}" \
           "the appliance will ship the substrate's stock kernel" ;;
  esac

  if mountpoint -q "${SOVEREIGN_OS_FORGE_DIR}" 2>/dev/null; then
    ok "forge tmpfs mounted at ${SOVEREIGN_OS_FORGE_DIR}"
  else
    warn "no tmpfs at ${SOVEREIGN_OS_FORGE_DIR} (step 01 mounts it; needs root)" \
         "sudo scripts/build/orchestrate.sh run   — or it builds on disk, slower"
  fi
  local avail_g; avail_g=$(free -g | awk '/^Mem:/{print $7}')
  if [ "${avail_g:-0}" -ge 64 ]; then ok "RAM: ${avail_g}G available (forge wants 64G)"
  else warn "RAM: only ${avail_g}G available; the forge tmpfs wants 64G" \
            "lower SOVEREIGN_OS_FORGE_SIZE, or build on disk"; fi
  for t in bison flex bc cpio; do
    have "$t" || warn "kernel build dep '$t' missing" "step 01 installs it (needs root)"
  done
}

check_mkosi() {
  head_ "substrate: mkosi (appliance image)"
  need_tool mkosi    mkosi        "builds the whole-disk image"
  need_tool losetup  util-linux   "loop-mounts the image"
  # mkosi-emit HARD-FAILS on these two; better to learn now than at step 05.
  if [ -n "${SOVEREIGN_OS_ROOT_PASSWORD:-}" ] || [ -n "${SOVEREIGN_OS_ALLOW_LOCKED_ROOT:-}" ]; then
    ok "root password posture set"
  else
    blocker "no SOVEREIGN_OS_ROOT_PASSWORD — mkosi-emit refuses (an image whose root is locked boots to a prompt nobody can satisfy)" \
            "export SOVEREIGN_OS_ROOT_PASSWORD=...   (or SOVEREIGN_OS_ALLOW_LOCKED_ROOT=1 to ship locked on purpose)"
  fi
  check_secureboot
}

check_secureboot() {
  local posture
  posture=$(python3 - "$@" <<'PY' 2>/dev/null || echo none
import os, sys, yaml, pathlib
root = pathlib.Path(os.environ.get("SOVEREIGN_OS_ROOT", "."))
prof = root / "profiles" / f"{os.environ.get('SOVEREIGN_OS_PROFILE','sain-01')}.yaml"
try:
    p = yaml.safe_load(prof.read_text())
except Exception:
    print("none"); raise SystemExit
k = p.get("kernel") or {}
print((k.get("cmdline") or {}).get("secure_boot") or k.get("secure_boot") or "none")
PY
)
  case "${posture}" in
    none|disabled) ok "secure boot: ${posture} — no operator key needed" ;;
    *)
      need_tool sbsign   sbsigntool "signs the kernel (posture=${posture})"
      need_tool sbverify sbsigntool "verifies the signature"
      local keydir="${SOVEREIGN_OS_KEY_DIR:-/etc/sovereign-os/keys}"
      if [ -n "${SOVEREIGN_OS_MOK_KEY:-}${SOVEREIGN_OS_PK_KEY:-}" ]; then
        ok "operator signing key supplied via env"
      elif [ -r "${keydir}/mok.key" ] && [ -r "${keydir}/mok.crt" ]; then
        ok "operator MOK at ${keydir}"
      elif [ -w "${keydir}" ] || [ -w "${keydir%/*}" ]; then
        ok "no key yet, but ${keydir} is writable — the build will mint one"
      else
        blocker "secure_boot=${posture} but no operator key at /etc/sovereign-os/keys" \
                "a ROOT build mints it automatically; for a non-root build point it somewhere writable: export SOVEREIGN_OS_KEY_DIR=\$HOME/.sovereign-keys  (or supply SOVEREIGN_OS_MOK_KEY/_CERT). SDD-015: keys never live in the repo."
      fi ;;
  esac
}

check_installer_cdd() {
  head_ "substrate: installer-cdd (Debian d-i ISO)"
  need_tool build-simple-cdd simple-cdd "builds the d-i ISO"
  need_tool reprepro         reprepro   "the local package repo on the CD"
  need_tool debootstrap      debootstrap "bootstraps the CD's package pool"
  need_tool xorriso          xorriso    "writes the ISO"
  if [ "$(id -u)" -eq 0 ]; then
    if [ -n "${SUDO_USER:-}" ]; then ok "running as root with SUDO_USER=${SUDO_USER} — step 07 can drop privileges"
    else blocker "simple-cdd refuses to run as root and no SUDO_USER is set" "run the build via sudo (not a root login shell)"; fi
  else ok "non-root user — simple-cdd is happy"; fi
  check_network "deb.debian.org" "the CD mirror download"
}

check_ubuntu_autoinstall() {
  head_ "substrate: ubuntu-autoinstall (Subiquity ISO)"
  need_tool xorriso xorriso "remasters the official ISO"
  need_tool wget    wget    "fetches the Ubuntu ISO"
  local cache="${SOVEREIGN_OS_UBUNTU_ISO_CACHE:-/var/tmp/sovereign-ubuntu-iso}"
  if [ -n "${SOVEREIGN_OS_UBUNTU_ISO:-}" ] && [ -f "${SOVEREIGN_OS_UBUNTU_ISO}" ]; then
    ok "base ISO supplied: ${SOVEREIGN_OS_UBUNTU_ISO}"
  elif ls "${cache}"/ubuntu-*-desktop-amd64.iso >/dev/null 2>&1; then
    ok "base ISO cached in ${cache}"
  else
    warn "no cached Ubuntu ISO — the build downloads ~3-6 GB once" \
         "pre-fetch to ${cache}, or set SOVEREIGN_OS_UBUNTU_ISO=/path/to.iso"
    check_network "releases.ubuntu.com" "the Ubuntu ISO download"
  fi
}

check_live_build() {
  head_ "substrate: live-build"
  need_tool lb live-build "builds the live ISO"
  [ "${SOVEREIGN_OS_DISTRO}" = "ubuntu" ] && warn \
    "live-build on Ubuntu is wired but UNTESTED (Ubuntu uses livecd-rootfs)" \
    "prefer SOVEREIGN_OS_ARTIFACT=installer for Ubuntu"
}

check_network() { # <host> <why>
  if getent hosts "$1" >/dev/null 2>&1; then ok "DNS resolves $1 — $2"
  else blocker "cannot resolve $1 — $2 will fail" "check networking; the build is offline-INSTALL but online-BUILD"; fi
}

run_one() {
  report_plan
  check_common
  check_kernel
  case "${SUBSTRATE}" in
    mkosi)              check_mkosi ;;
    installer-cdd)      check_installer_cdd; check_secureboot ;;
    ubuntu-autoinstall) check_ubuntu_autoinstall; check_secureboot ;;
    live-build)         check_live_build ;;
  esac
}

summarise() { # <blockers> <warnings> <label>
  printf '\n'
  if [ "$1" -eq 0 ]; then
    printf '%sREADY%s — %d warning(s)%s. Nothing blocks %s.\n' \
      "$c_ok" "$c_off" "$2" "" "$3"
    return 0
  fi
  printf '%sNOT READY%s — %d blocker(s), %d warning(s). Fix the BLOCK lines above.\n' \
    "$c_bad" "$c_off" "$1" "$2"
  return 1
}

if [ "${1:-}" = "--all" ]; then
  # Each path runs in a SUBSHELL, so its BLOCKERS/WARNINGS counters cannot reach
  # this scope — the first version summed nothing and cheerfully printed
  # "READY — 0 warnings" directly under eight BLOCK lines (2026-07-28). A
  # preflight that reports success while blockers are on screen is worse than no
  # preflight. Aggregate the subshell EXIT STATUS instead, which does cross.
  not_ready=0; paths=0
  for d in debian ubuntu; do
    for a in image installer; do
      paths=$((paths+1))
      ( export SOVEREIGN_OS_DISTRO="$d" SOVEREIGN_OS_ARTIFACT="$a"
        # re-source so the derived suite follows the distro
        __SOVEREIGN_OS_DISTRO_LIB_LOADED= . "${__SCRIPT_DIR}/lib/distro.sh"
        run_one
        summarise "${BLOCKERS}" "${WARNINGS}" "this path" >/dev/null
        exit $(( BLOCKERS > 0 ? 1 : 0 )) )
      [ $? -eq 0 ] || { not_ready=$((not_ready+1)); printf '  %s^ this path is NOT READY%s\n' "$c_bad" "$c_off"; }
      echo
    done
  done
  printf '\n'
  if [ "${not_ready}" -eq 0 ]; then
    printf '%sREADY%s — all %d artifact×distro paths can build.\n' "$c_ok" "$c_off" "${paths}"
    exit 0
  fi
  printf '%sNOT READY%s — %d of %d paths blocked. Fix the BLOCK lines above.\n' \
    "$c_bad" "$c_off" "${not_ready}" "${paths}"
  exit 1
fi

run_one
summarise "${BLOCKERS}" "${WARNINGS}" "this build"
