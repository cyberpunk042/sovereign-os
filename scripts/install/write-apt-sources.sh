#!/bin/sh
# Give the installed system working apt sources.
#
# WHY. The d-i profile installs entirely offline from the CD mirror, so the
# preseed sets apt-setup/use_mirror=false, cdrom/set-first=false and an empty
# services-select. That is correct DURING the install -- there is no network
# guarantee and every package is on the disc -- but it leaves the installed
# system with no usable sources at all: `apt install` fails and no security
# update ever arrives. The operator hit "a lot was missing" and then could not
# install the missing pieces either (2026-07-27).
#
# Run at the END of the install (d-i late_command, in-target). It only WRITES
# the file; it deliberately does not run `apt-get update`, which would need
# network the install was designed not to require.
#
# Components mirror the operator's working Debian 13 exactly:
#   main non-free-firmware contrib non-free
# non-free-firmware matters here -- it is where firmware-amd-graphics lives.
set -eu

# Ubuntu needs a different archive, a different security host AND different
# components. Writing Debian sources onto an Ubuntu install leaves it with no
# usable apt at all — the first real Ubuntu install's self-check said exactly
# that: "PROBLEM: no network apt sources -- apt install will fail"
# (2026-07-29). Detect at RUNTIME; this executes on the installed machine.
. "$(dirname "$0")/lib/target-distro.sh" 2>/dev/null \
  || . /opt/sovereign-os/scripts/install/lib/target-distro.sh 2>/dev/null || true
if ! command -v target_apt_mirror >/dev/null 2>&1; then
  target_apt_mirror()     { printf 'http://deb.debian.org/debian'; }
  target_apt_security()   { printf 'http://security.debian.org/debian-security'; }
  target_apt_components() { printf 'main non-free-firmware contrib non-free'; }
  target_default_suite()  { printf 'trixie'; }
fi

SUITE="${1:-$(target_default_suite)}"
LIST=/etc/apt/sources.list
COMPONENTS="$(target_apt_components)"
MIRROR="$(target_apt_mirror)"
SECURITY="$(target_apt_security)"

# Never clobber sources the operator already has.
if [ -s "${LIST}" ] && grep -qE "^deb .*(deb\.debian\.org|security\.debian\.org|archive\.ubuntu\.com|security\.ubuntu\.com)" "${LIST}" 2>/dev/null; then
  echo "write-apt-sources: ${LIST} already has network sources — leaving it alone"
  exit 0
fi

cat > "${LIST}" <<LIST_EOF
# Written by sovereign-os at install time. The install itself was offline (the
# CD carried every package); these are for everything afterwards.
deb ${MIRROR} ${SUITE} ${COMPONENTS}
deb ${SECURITY} ${SUITE}-security ${COMPONENTS}
deb ${MIRROR} ${SUITE}-updates ${COMPONENTS}
LIST_EOF

echo "write-apt-sources: wrote ${LIST} ($(target_distro 2>/dev/null || echo debian) ${SUITE}, ${COMPONENTS})"
exit 0
