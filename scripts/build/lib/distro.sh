#!/usr/bin/env bash
# scripts/build/lib/distro.sh — the DISTRO axis (debian | ubuntu).
# Source from any step, adapter or substrate build that needs to know which
# distribution the image is being built FROM.
#
# Why this exists (2026-07-28): sovereign-os could build exactly one distro.
# `SOVEREIGN_OS_SUITE` existed but is a *suite* name, and the adapters bypassed
# it anyway -- mkosi-emit.sh hardcoded `Distribution=debian` / `Release=trixie`
# and live-build-emit.sh hardcoded `--distribution trixie`. Adding Ubuntu 26.04
# LTS (resolute) as a panel option therefore needed a real axis, not another
# hardcode.
#
# DISTRO is ORTHOGONAL to SUBSTRATE. mkosi builds either distro; only the
# INSTALLER differs, because the mechanisms are genuinely incompatible:
#   debian -> installer-cdd      (simple-cdd -> debian-cd -> d-i + preseed)
#   ubuntu -> ubuntu-autoinstall (Subiquity + autoinstall YAML)
# Ubuntu dropped debian-installer at 20.04 and preseed does NOT work with
# Subiquity, so the installer-cdd path cannot be reused for Ubuntu at all.
#
# SOVEREIGN_OS_SUITE stays an explicit override; when unset it is DERIVED from
# the distro, so `SOVEREIGN_OS_DISTRO=ubuntu` alone is a complete instruction.

if [ -n "${__SOVEREIGN_OS_DISTRO_LIB_LOADED:-}" ]; then
  return 0
fi
__SOVEREIGN_OS_DISTRO_LIB_LOADED=1

# Default is debian: every existing build, profile and test must keep its
# current behaviour when the operator sets nothing.
: "${SOVEREIGN_OS_DISTRO:=debian}"
export SOVEREIGN_OS_DISTRO

# ---- validation ------------------------------------------------------------
# Fail loudly and early. A typo'd distro that falls through to a default would
# silently build the wrong OS -- the same class of bug as the substrate that
# reported installer-cdd at step 05 and ran live-build at step 07 (2026-07-26).
distro_validate() {
  case "${SOVEREIGN_OS_DISTRO}" in
    debian|ubuntu) return 0 ;;
    *)
      echo "unknown distro: ${SOVEREIGN_OS_DISTRO} (valid: debian, ubuntu)" >&2
      return 1
      ;;
  esac
}

# ---- suite (release codename) ----------------------------------------------
distro_default_suite() {
  case "${SOVEREIGN_OS_DISTRO}" in
    ubuntu) echo "resolute" ;;   # Ubuntu 26.04 LTS "Resolute Raccoon" (2026-04-23)
    *)      echo "trixie"   ;;   # Debian 13
  esac
}

# Resolve the suite ONCE, honouring an explicit override.
distro_suite() {
  if [ -n "${SOVEREIGN_OS_SUITE:-}" ]; then
    echo "${SOVEREIGN_OS_SUITE}"
  else
    distro_default_suite
  fi
}

# ---- apt archive shape -----------------------------------------------------
# The component list is UNCONDITIONAL on both distros: `main` alone strands the
# GPU/ZFS stack. On Debian nvidia-* live in non-free and zfs* in contrib; on
# Ubuntu both live in restricted/multiverse. Same lesson, different names.
distro_components() {
  case "${SOVEREIGN_OS_DISTRO}" in
    ubuntu) echo "main restricted universe multiverse" ;;
    *)      echo "main contrib non-free non-free-firmware" ;;
  esac
}

distro_mirror() {
  case "${SOVEREIGN_OS_DISTRO}" in
    ubuntu) echo "http://archive.ubuntu.com/ubuntu" ;;
    *)      echo "http://deb.debian.org/debian" ;;
  esac
}

# Reproducibility pin. Both projects run a snapshot service; the URL shapes
# differ, so callers ask here rather than string-building a Debian URL.
distro_snapshot_mirror() {
  _snap="${1:-}"
  [ -n "${_snap}" ] || return 1
  case "${SOVEREIGN_OS_DISTRO}" in
    ubuntu) echo "https://snapshot.ubuntu.com/ubuntu/${_snap}" ;;
    *)      echo "http://snapshot.debian.org/archive/debian/${_snap}" ;;
  esac
}

# mkosi's [Distribution] Distribution= value.
distro_mkosi_name() {
  case "${SOVEREIGN_OS_DISTRO}" in
    ubuntu) echo "ubuntu" ;;
    *)      echo "debian" ;;
  esac
}

# ---- package-name translation ----------------------------------------------
# The ~93-entry package list is common to both distros EXCEPT the desktop task
# and the firmware bundle. Keeping the mapping here (rather than a second copy
# of the list) means the two installers cannot drift apart silently.

# The KDE Plasma desktop metapackage.
distro_desktop_task() {
  case "${SOVEREIGN_OS_DISTRO}" in
    ubuntu) echo "kubuntu-desktop" ;;
    *)      echo "task-kde-desktop" ;;
  esac
}

# The browser. Debian ships the ESR line as firefox-esr and has no `firefox`
# package at all; Ubuntu ships `firefox` (a snap-backed transitional deb on
# recent releases). Installing the Debian name on Ubuntu is a hard "package not
# found", which in an OFFLINE install aborts the run after partitioning.
distro_browser() {
  case "${SOVEREIGN_OS_DISTRO}" in
    ubuntu) echo "firefox" ;;
    *)      echo "firefox-esr" ;;
  esac
}

# Firmware. Debian splits it across four firmware-* packages out of
# non-free-firmware; Ubuntu ships one linux-firmware in main.
distro_firmware_packages() {
  case "${SOVEREIGN_OS_DISTRO}" in
    ubuntu) echo "linux-firmware" ;;
    *)      echo "firmware-amd-graphics firmware-nvidia-graphics firmware-linux-free firmware-misc-nonfree" ;;
  esac
}

# The Debian firmware packages that collapse to a single Ubuntu one.
distro_debian_firmware_packages() {
  echo "firmware-amd-graphics firmware-nvidia-graphics firmware-linux-free firmware-misc-nonfree"
}

# Rewrite a whitespace-separated package list from its Debian spelling into the
# spelling of the ACTIVE distro. A no-op when DISTRO=debian, so callers can pipe
# the canonical list through unconditionally.
#
# Token-wise via awk rather than a chain of seds. The sed version replaced the
# FIRST firmware-* with linux-firmware and deleted the rest, so a list carrying
# (say) firmware-nvidia-graphics but not firmware-amd-graphics lost its firmware
# entirely and gained nothing — a silent package loss, which is precisely the
# failure that shipped an install with no firmware and a dark screen (2026-07-26).
# Here every known firmware name maps to the replacement and duplicates collapse,
# so the result is correct regardless of which subset appears or in what order.
distro_map_packages() {
  if [ "${SOVEREIGN_OS_DISTRO}" = "debian" ]; then
    cat
    return 0
  fi
  awk -v desktop="$(distro_desktop_task)" \
      -v browser="$(distro_browser)" \
      -v fw_new="$(distro_firmware_packages)" \
      -v fw_old="$(distro_debian_firmware_packages)" '
    BEGIN { n = split(fw_old, a, " "); for (i = 1; i <= n; i++) isfw[a[i]] = 1 }
    {
      out = ""
      for (i = 1; i <= NF; i++) {
        t = $i
        if (t == "task-kde-desktop")   t = desktop
        else if (t == "firefox-esr")   t = browser
        else if (isfw[t])              t = fw_new
        if (seen[t]++) continue
        out = (out == "" ? t : out " " t)
      }
      print out
    }'
}

# ---- the installer substrate for this distro -------------------------------
# The single place that encodes "ARTIFACT=installer means something different
# per distro". orchestrate.sh reads this instead of branching inline.
distro_installer_substrate() {
  case "${SOVEREIGN_OS_DISTRO}" in
    ubuntu) echo "ubuntu-autoinstall" ;;
    *)      echo "installer-cdd" ;;
  esac
}

# Human label for logs and the build report.
distro_label() {
  case "${SOVEREIGN_OS_DISTRO}" in
    ubuntu) echo "Ubuntu 26.04 LTS (resolute)" ;;
    *)      echo "Debian 13 (trixie)" ;;
  esac
}
