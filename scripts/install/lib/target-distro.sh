#!/bin/sh
# scripts/install/lib/target-distro.sh — what distro am I RUNNING on?
#
# The build side has scripts/build/lib/distro.sh, which answers "what are we
# building FOR". This is its runtime twin: the scripts under scripts/install/
# execute ON the installed machine, long after the build, so they must ask the
# system itself rather than inherit a build-time variable.
#
# WHY IT EXISTS (2026-07-29). The first full Ubuntu install ran to completion in
# a VM and the disk inspection found the cockpit deploy had died:
#
#     E: Package 'firefox-esr' has no installation candidate
#     FAILED (rc=100)
#
# `install-gui-dashboards.sh` pkg_ensure'd `firefox-esr` — the DEBIAN name — on
# an Ubuntu system, where the package is `firefox`. Exactly the shape that
# `xdg-utils` had a day earlier: a package name that is correct on one distro,
# absent on the other, and fatal to a `set -e` deploy. The install self-check
# reported the same class twice more (`MISSING firmware-amd-graphics`, and apt
# sources pointing at deb.debian.org on Ubuntu).
#
# POSIX sh: sourced by install-gui-dashboards.sh (bash), verify-installed-system.sh
# and write-apt-sources.sh (both /bin/sh).

if [ -n "${__SOVEREIGN_OS_TARGET_DISTRO_LOADED:-}" ]; then
  return 0 2>/dev/null || true
fi
__SOVEREIGN_OS_TARGET_DISTRO_LOADED=1

# ID from os-release; SOVEREIGN_OS_DISTRO overrides (tests, chroots).
target_distro() {
  if [ -n "${SOVEREIGN_OS_DISTRO:-}" ]; then
    printf '%s' "${SOVEREIGN_OS_DISTRO}"
    return 0
  fi
  _id=""
  if [ -r /etc/os-release ]; then
    _id="$(. /etc/os-release 2>/dev/null && printf '%s' "${ID:-}")"
  fi
  case "${_id}" in
    ubuntu) printf 'ubuntu' ;;
    *)      printf 'debian' ;;   # unknown → the historical default
  esac
}

# The browser. Debian has firefox-esr and NO `firefox`; Ubuntu has `firefox`.
target_browser() {
  case "$(target_distro)" in
    ubuntu) printf 'firefox' ;;
    *)      printf 'firefox-esr' ;;
  esac
}

# Firmware. Debian splits it across firmware-* in non-free-firmware; Ubuntu
# ships one linux-firmware in main.
target_firmware_package() {
  case "$(target_distro)" in
    ubuntu) printf 'linux-firmware' ;;
    *)      printf 'firmware-amd-graphics' ;;
  esac
}

# The KDE desktop metapackage.
target_desktop_task() {
  case "$(target_distro)" in
    ubuntu) printf 'kubuntu-desktop' ;;
    *)      printf 'task-kde-desktop' ;;
  esac
}

# apt archive shape, for write-apt-sources.sh.
target_apt_mirror() {
  case "$(target_distro)" in
    ubuntu) printf 'http://archive.ubuntu.com/ubuntu' ;;
    *)      printf 'http://deb.debian.org/debian' ;;
  esac
}
target_apt_security() {
  case "$(target_distro)" in
    ubuntu) printf 'http://security.ubuntu.com/ubuntu' ;;
    *)      printf 'http://security.debian.org/debian-security' ;;
  esac
}
# Ubuntu's security suite is <suite>-security on the SAME archive layout as
# Debian's, but the components differ.
target_apt_components() {
  case "$(target_distro)" in
    ubuntu) printf 'main restricted universe multiverse' ;;
    *)      printf 'main non-free-firmware contrib non-free' ;;
  esac
}
target_default_suite() {
  case "$(target_distro)" in
    ubuntu) printf 'resolute' ;;
    *)      printf 'trixie' ;;
  esac
}

# ── HOW THIS DISTRO GETS A GRAPHICAL SEAT ───────────────────────────────────
# logind only reports CanGraphical=yes when udev has tagged something
# `master-of-seat`. /usr/lib/udev/rules.d/71-seat.rules offers two routes:
#
#   rules 23/28  fb[0-9]        ONLY under IMPORT{cmdline}="nomodeset"
#   rule 35      drm card[0-9]* needs a KMS driver actually bound
#
# The distros must take DIFFERENT routes, and using the wrong one is a silent
# total failure in both directions (established 2026-07-29):
#
#   debian  Plasma ships /usr/share/xsessions/plasmax11.desktop, so X11 runs on
#           the EFI framebuffer. Route: nomodeset. LOAD-BEARING.
#   ubuntu  26.04's Plasma is WAYLAND-ONLY (/usr/share/xsessions/ is EMPTY), and
#           Wayland requires a DRM device. nomodeset removes exactly that, so it
#           is FATAL. Route: a bound KMS driver — the NVIDIA driver with
#           nvidia-drm.modeset=1 (operator decision, 2026-07-29).
#
# Returns: "nomodeset" or "drm"
target_seat_route() {
  case "$(target_distro)" in
    ubuntu) echo "drm" ;;
    *)      echo "nomodeset" ;;
  esac
}

# The kernel cmdline option this distro needs for that route.
target_seat_cmdline_option() {
  case "$(target_seat_route)" in
    drm) echo "nvidia-drm.modeset=1" ;;
    *)   echo "nomodeset" ;;
  esac
}
