#!/usr/bin/env bash
# Compatibility entry point for the former manual repair command.
#
# The active orchestration profile is the sole source of model context and
# output-budget metadata. Never hard-code a model's catalog maximum here: it
# can be larger than the resident server and makes OpenClaw overflow it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="$(cat /etc/sovereign-os/active-runtime-profile)"
exec python3 "$ROOT/scripts/inference/sync-openclaw-models.py" --profile "$PROFILE"
