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

SUITE="${1:-trixie}"
LIST=/etc/apt/sources.list
COMPONENTS="main non-free-firmware contrib non-free"

# Never clobber sources the operator already has.
if [ -s "${LIST}" ] && grep -qE "^deb .*(deb\.debian\.org|security\.debian\.org)" "${LIST}" 2>/dev/null; then
  echo "write-apt-sources: ${LIST} already has network sources — leaving it alone"
  exit 0
fi

cat > "${LIST}" <<LIST_EOF
# Written by sovereign-os at install time. The install itself was offline (the
# CD carried every package); these are for everything afterwards.
deb http://deb.debian.org/debian/ ${SUITE} ${COMPONENTS}
deb http://security.debian.org/debian-security ${SUITE}-security ${COMPONENTS}
deb http://deb.debian.org/debian/ ${SUITE}-updates ${COMPONENTS}
LIST_EOF

echo "write-apt-sources: wrote ${LIST} (${SUITE}, ${COMPONENTS})"
exit 0
