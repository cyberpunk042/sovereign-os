#!/bin/sh
# Fail the BUILD if the ISO cannot satisfy its own install list.
#
# WHY THIS EXISTS. A stock Debian installer pulls from a network mirror with
# full dependency resolution; ours installs a fixed set from a fixed offline CD.
# pkgsel/include is FATAL: one missing package and d-i aborts -- after
# partitioning, formatting and unpacking. That has already happened here
# ("Unable to install zstd", a base-installer dependency absent from the
# mirror), and it costs an hour to discover.
#
# So check it where it is cheap: right after the ISO is produced, before anyone
# flashes it. A missing package fails the build in seconds instead of the
# install in an hour.
#
# Usage: verify-iso-has-packages.sh <iso> <preseed>
set -eu

ISO="${1:?usage: verify-iso-has-packages.sh <iso> <preseed>}"
PRESEED="${2:?usage: verify-iso-has-packages.sh <iso> <preseed>}"

[ -r "${ISO}" ]     || { echo "verify-iso: cannot read ${ISO}" >&2; exit 1; }
[ -r "${PRESEED}" ] || { echo "verify-iso: cannot read ${PRESEED}" >&2; exit 1; }
command -v xorriso >/dev/null 2>&1 || {
  echo "verify-iso: xorriso not available — skipping (install xorriso to enable)" >&2
  exit 0
}

# The install list: one `d-i pkgsel/include string ...` value, backslash-continued.
want=$(awk '
  /^d-i pkgsel\/include string/ { inlist=1; sub(/^d-i pkgsel\/include string[[:space:]]*/, ""); }
  inlist {
    line=$0; sub(/\\$/, "", line); printf "%s ", line;
    if ($0 !~ /\\$/) exit;
  }
' "${PRESEED}")

[ -n "${want}" ] || { echo "verify-iso: no pkgsel/include found in ${PRESEED}" >&2; exit 1; }

pool=$(xorriso -indev "${ISO}" -find /pool -name '*.deb' 2>/dev/null | tr -d "'" || true)
[ -n "${pool}" ] || { echo "verify-iso: no .deb files found in ${ISO}" >&2; exit 1; }

missing=""
count=0
for pkg in ${want}; do
  count=$((count + 1))
  # pool files are <name>_<version>_<arch>.deb; match on the name boundary so
  # "sddm" does not match "sddm-theme-breeze".
  if ! printf '%s\n' "${pool}" | grep -q "/${pkg}_[^/]*\.deb$"; then
    missing="${missing} ${pkg}"
  fi
done

if [ -n "${missing}" ]; then
  echo "verify-iso: ${ISO} is MISSING packages its own preseed will install:" >&2
  for m in ${missing}; do echo "    ${m}" >&2; done
  echo "  d-i would abort AFTER partitioning and unpacking. Do NOT flash this." >&2
  exit 1
fi

echo "verify-iso: all ${count} pkgsel/include package(s) present in the ISO pool"
exit 0
