#!/usr/bin/env bash
# tests/chroot/scaffold.sh — Layer 3 chroot test harness scaffold.
#
# Usage: tests/chroot/scaffold.sh <profile-id>
#
# This is a SCAFFOLD only. Per SDD-008, substantive chroot stage-
# acceptance tests are added alongside each script's implementation
# at Stage 2+. This scaffold proves the harness mechanism: load a
# profile + start a chroot environment + execute a stub assertion.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PROFILE="${1:-sain-01}"

profile_file="${REPO_ROOT}/profiles/${PROFILE}.yaml"
if [ ! -f "${profile_file}" ]; then
  echo "profile not found: ${profile_file}" >&2
  exit 1
fi

echo "tests/chroot/scaffold.sh — profile=${PROFILE}"
echo "  (Layer 3 chroot harness scaffold; substantive tests at Stage 2+)"

# Smoke: verify the friction-audit-spec hook executes against the
# profile (it's pure metadata validation; no real chroot needed yet).
SOVEREIGN_OS_PROFILE="${PROFILE}" \
  bash "${REPO_ROOT}/scripts/hooks/pre-install/friction-audit-spec.sh" >/dev/null

echo "  PASS — friction-audit-spec runs against profile=${PROFILE}"
