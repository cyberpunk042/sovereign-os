#!/usr/bin/env bash
# tests/qemu/scaffold.sh — Layer 4 QEMU integration scaffold.
#
# Substantive image-boot tests run via 'sovereign-os-build run' →
# the build pipeline's step 09-image-verify already QEMU-boots the
# produced image. This scaffold exposes the same path for label-
# triggered CI runs.

set -euo pipefail

PROFILE="${1:-sain-01}"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

echo "tests/qemu/scaffold.sh — profile=${PROFILE}"
echo "  (Layer 4 QEMU harness scaffold; bridges to build/09-image-verify.sh)"

# Smoke (no real boot in CI without KVM); verify the verify script exists.
if [ -x "${REPO_ROOT}/scripts/build/09-image-verify.sh" ]; then
  echo "  PASS — 09-image-verify.sh present (full boot test requires built image)"
else
  echo "  FAIL — 09-image-verify.sh missing"
  exit 1
fi
