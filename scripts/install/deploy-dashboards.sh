#!/bin/sh
# Deploy the sovereign-os dashboards + cockpit, recording the outcome.
#
# WHY IT IS NOT IN THE PACKAGE POSTINST. install-gui-dashboards.sh calls
# `apt-get install`. dpkg runs maintainer scripts while holding the dpkg lock,
# so apt from a postinst deadlocks or fails on that lock -- Debian Policy
# forbids it for exactly this reason. On the installer path the deploy ran from
# the cockpit package's postinst, i.e. under dpkg during pkgsel, so its first
# pkg_ensure would fail on the lock and the cockpit would never land
# (2026-07-27).
#
# d-i's late_command runs AFTER pkgsel, outside dpkg, which is the correct
# place. The direct-install path already calls the script from outside dpkg.
#
# This never fails its caller: d-i has already partitioned and unpacked by the
# time late_command runs, and aborting there leaves a half-installed disk. It
# records what happened instead, and verify-installed-system.sh reports it.
set -u

SRC="${SOVEREIGN_OS_SRC:-/opt/sovereign-os}"
DASH="${SRC}/scripts/install/install-gui-dashboards.sh"
LOG=/var/log/sovereign-os/dashboards-install.log
STATUS=/var/lib/sovereign-os/dashboards-install.status
TTY=/dev/tty4

mkdir -p /var/log/sovereign-os /var/lib/sovereign-os 2>/dev/null || true

# Wrap the whole redirection: `cmd > /dev/tty4 2>/dev/null` still lets the
# SHELL report a failed redirect on stderr ("cannot create /dev/tty4"), which
# would spam the install log on any system without that console.
_say() { { echo "sovereign: $*" > "${TTY}"; } 2>/dev/null || true; }
_set() { echo "$1" > "${STATUS}" 2>/dev/null || true; }

if [ ! -f "${DASH}" ]; then
  echo "MISSING: ${DASH}" > "${LOG}" 2>/dev/null || true
  _set missing; _say "dashboards: MISSING ${DASH}"; exit 0
fi
if [ ! -x "${DASH}" ]; then
  # A lost exec bit silently skipped this entire stage once before.
  echo "NOT EXECUTABLE: ${DASH} (mode $(stat -c %a "${DASH}" 2>/dev/null))" \
    > "${LOG}" 2>/dev/null || true
  _set not-executable; _say "dashboards: ${DASH} is not executable"; exit 0
fi

_say "deploying dashboards + cockpit (several minutes; output on tty4)"
_rcf=/tmp/.sovereign-dash-rc
# Stream live AND keep the log. dash has no PIPESTATUS, so the real exit status
# is carried out of the pipeline through a file.
{ SOVEREIGN_OS_SRC="${SRC}" \
  SOVEREIGN_OS_FRONTEND="${SOVEREIGN_OS_FRONTEND:-kde-plasma}" \
  DEBIAN_FRONTEND=noninteractive \
  bash "${DASH}" 2>&1; echo $? > "${_rcf}"; } \
  | { tee "${LOG}" > "${TTY}"; } 2>/dev/null || true
_rc="$(cat "${_rcf}" 2>/dev/null || echo 1)"
rm -f "${_rcf}" 2>/dev/null || true

if [ "${_rc}" = 0 ]; then
  _set ok; _say "dashboards deploy OK"
else
  echo "FAILED (rc=${_rc})" >> "${LOG}" 2>/dev/null || true
  _set failed; _say "dashboards deploy FAILED (rc=${_rc}) — see ${LOG}"
fi
exit 0
