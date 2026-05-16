#!/usr/bin/env bash
# tests/nspawn/scaffold.sh — Layer 3 systemd-nspawn scaffold.
#
# Substantive service-startup tests land alongside each hook impl
# at Stage 2+.

set -euo pipefail

PROFILE="${1:-sain-01}"

echo "tests/nspawn/scaffold.sh — profile=${PROFILE}"
echo "  (Layer 3 nspawn harness scaffold; substantive tests at Stage 2+)"
echo "  PASS — scaffold reachable"
