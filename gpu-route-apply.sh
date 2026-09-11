#!/usr/bin/env bash
# Stable systemd entry point for the GPU-route reconciler.
#
# Module 84 installs sovereign-gpu-route-reconcile.service with ExecStart at
# /usr/local/lib/sovereign-os/gpu-route-apply.sh.  On a live-linked developer
# checkout that location resolves to this repository root, whereas the actual
# implementation intentionally lives under scripts/iac/assets/. Keep this tiny
# executable forwarding entry point so boot and periodic reconciliation cannot
# disappear merely because the deployment is a symlink.
set -euo pipefail

__ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${__ROOT}/scripts/iac/assets/gpu-route-apply.sh" "$@"
