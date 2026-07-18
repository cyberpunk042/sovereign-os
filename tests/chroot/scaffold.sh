#!/usr/bin/env bash
# tests/chroot/scaffold.sh — Layer 3 chroot harness entrypoint (F-2026-052).
#
# Historically a bare friction-audit smoke. The substantive chroot stage-
# acceptance harness now lives in tests/chroot/run.sh (precondition probes +
# real filesystem assertions against a built rootfs + skip-clean when the rootfs
# is absent). This entrypoint delegates to it so the older path name keeps
# working; prefer `bash tests/chroot/run.sh <profile>` directly.
#
# Usage: tests/chroot/scaffold.sh <profile-id>
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec bash "${REPO_ROOT}/tests/chroot/run.sh" "$@"
