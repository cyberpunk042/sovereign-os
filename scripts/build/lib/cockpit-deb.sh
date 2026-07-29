#!/usr/bin/env bash
# scripts/build/lib/cockpit-deb.sh — build the sovereign-os-cockpit .deb.
#
# Extracted from installer-cdd/build.sh on 2026-07-28 when the Ubuntu
# autoinstall substrate landed and needed the SAME package. Keeping a second
# copy would have guaranteed drift: this session alone found two live instances
# of exactly that (bootstrap-host.sh kept a broken operator-deps invocation
# provision.sh had already fixed; operator-deps.py never picked up the PEP 668
# handling warp-setup.sh already had). One builder, both installers.
#
# The payload is arch:all and depends only on python3/python3-yaml/bash, so the
# identical .deb installs on Debian 13 and Ubuntu 26.04 alike.
#
# Usage:  build_cockpit_deb <repo-root> <work-dir> <out-dir>

if [ -n "${__SOVEREIGN_OS_COCKPIT_DEB_LIB_LOADED:-}" ]; then
  return 0
fi
__SOVEREIGN_OS_COCKPIT_DEB_LIB_LOADED=1

build_cockpit_deb() {
  local REPO="${1:?usage: build_cockpit_deb <repo> <work> <out>}"
  local WORK="${2:?usage: build_cockpit_deb <repo> <work> <out>}"
  local LOCAL_PKGS="${3:?usage: build_cockpit_deb <repo> <work> <out>}"
  local PKGROOT _cksz
  # Callers that predate this lib define their own log(); fall back when absent.
  if ! declare -F log >/dev/null 2>&1; then
    log() { printf '\033[36m\xe2\x94\x81\xe2\x94\x81 cockpit-deb: %s\033[0m\n' "$*" >&2; }
  fi
  mkdir -p "${LOCAL_PKGS}"

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
  rm -rf "${PKGROOT}/opt/sovereign-os/scripts/build/installer-cdd/tmp" \
         "${PKGROOT}/opt/sovereign-os/scripts/build/installer-cdd/images"
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
# The dashboards deploy is NOT run here. install-gui-dashboards.sh calls
# `apt-get install`, and dpkg runs maintainer scripts while holding the dpkg
# lock — Debian Policy forbids apt from a maintainer script for exactly that
# reason. Running it here meant its first pkg_ensure would fail on the lock and
# the cockpit would never land (2026-07-27).
# d-i's late_command runs it instead, after pkgsel and outside dpkg:
#   scripts/install/deploy-dashboards.sh
mkdir -p /etc/sovereign-os 2>/dev/null || true
[ -f /etc/sovereign-os/active-profile ] \
  || echo sain-01 > /etc/sovereign-os/active-profile 2>/dev/null || true

# The compatibility symlink (/usr/local/lib/sovereign-os -> /opt/sovereign-os)
# is NOT created here. install-gui-dashboards.sh deploys the real app tree to
# that path and explicitly leaves a SYMLINK alone:
#     [ -L "${PREFIX_LIB}" ] || { [ -e "${PREFIX_LIB}" ] && rm -rf ...; }
# so a pre-existing symlink turns its deploy into `cp -a /opt/sovereign-os/x/.`
# into `/opt/sovereign-os/x/` -- a directory copying into itself. The symlink is
# a FALLBACK for when the deploy did not run; it belongs after it, which is
# where deploy-dashboards.sh now creates it (2026-07-27).

# Make the sovereign units DISCOVERABLE -- and enable NOTHING.
# They shipped to /opt/sovereign-os/systemd/system, where systemd never looks,
# so even a deliberate `systemctl enable sovereign-firstboot.target` failed with
# "unit not found". Installing them to /lib/systemd/system makes that command
# work when the operator chooses to run it.
#
# Deliberately NOT enabled: sovereign-firstboot.target Wants= a dozen heavy
# services (nvidia-driver-install, tetragon-install, inference-model-provision)
# and enabling it is exactly what hung a boot at "Reached Target
# sovereign-firstboot.target" (2026-07-26). Presence is not activation.
if [ -d /opt/sovereign-os/systemd/system ]; then
  for u in /opt/sovereign-os/systemd/system/*.service /opt/sovereign-os/systemd/system/*.target; do
    [ -f "$u" ] || continue
    cp -a "$u" /lib/systemd/system/ 2>/dev/null || true
  done
  systemctl daemon-reload 2>/dev/null || true
fi
exit 0
POSTINST
  chmod 0755 "${PKGROOT}/DEBIAN/postinst"
  dpkg-deb --root-owner-group --build "${PKGROOT}" "${LOCAL_PKGS}/sovereign-os-cockpit_1.0.0_all.deb"
}
