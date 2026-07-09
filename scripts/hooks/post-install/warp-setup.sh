#!/usr/bin/env bash
# scripts/hooks/post-install/warp-setup.sh — R558 (SDD-070) install NVIDIA Warp.
#
# Installs the `warp-lang` Python/CUDA library (the `particles` tool in
# config/science-tools.yaml) into the system python3 so scripts/science/
# warp-runner.py can import it. The pip wheel bundles the CUDA 12 runtime, so
# GPU works with just the NVIDIA driver; on a GPU-less host Warp runs on CPU.
#
# Idempotent (short-circuits when `import warp` already works). Emits a Layer B
# metric on every terminal path. Honors SOVEREIGN_OS_DRY_RUN. First-boot unit:
# systemd/system/sovereign-warp-setup.service.

set -uo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"

# Degrade-safe sourcing — the hook may run outside the repo layout (first boot).
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh" 2>/dev/null || {
  log_info()  { echo "INFO  [warp-setup] $*"; }
  log_warn()  { echo "WARN  [warp-setup] $*" >&2; }
  log_error() { echo "ERROR [warp-setup] $*" >&2; }
  require_root() { [ "$(id -u)" -eq 0 ] || { log_error "must run as root"; exit 1; }; }
  log_step_header() { echo "── $1: $2 ──"; }
}
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh" 2>/dev/null || emit_metric() { :; }

STEP_ID="warp-setup"
: "${SOVEREIGN_OS_PROFILE:=sain-01}"

log_step_header "${STEP_ID}" "install NVIDIA Warp (warp-lang) Python/CUDA library"

emit_warp_metric() {
  emit_metric sovereign_os_post_install_warp_setup_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"$1\""
}

# DRY-RUN: print intent, touch nothing, exit clean (before require_root so it
# runs in unprivileged CI / preview).
if [ "${SOVEREIGN_OS_DRY_RUN:-0}" = "1" ]; then
  log_info "[dry-run] would: python3 -m pip install warp-lang (when 'import warp' fails)"
  exit 0
fi

require_root

# Idempotency guard — already importable ⇒ nothing to do.
if python3 -c 'import warp' 2>/dev/null; then
  log_info "warp already importable — nothing to do (idempotent)"
  emit_warp_metric already-present
  exit 0
fi

if ! python3 -m pip --version >/dev/null 2>&1; then
  log_error "python3 -m pip unavailable; cannot install warp-lang (install python3-pip)"
  emit_warp_metric fail
  exit 1
fi

log_info "installing warp-lang via pip …"
# Debian 13 (trixie) marks the system python as externally-managed (PEP 668);
# installing a library into the OS image at first boot is exactly the intentional
# override, so pass --break-system-packages when this pip supports it.
pip_args=(warp-lang)
if python3 -m pip install --help 2>/dev/null | grep -q -- '--break-system-packages'; then
  pip_args=(--break-system-packages warp-lang)
fi
if python3 -m pip install "${pip_args[@]}" 2>&1 | sed 's/^/  /'; then
  if python3 -c 'import warp' 2>/dev/null; then
    log_info "warp-lang installed + importable"
    emit_warp_metric installed
    log_info "${STEP_ID} complete"
    exit 0
  fi
  log_error "pip reported success but 'import warp' still fails"
  emit_warp_metric fail
  exit 1
fi

log_error "pip install warp-lang failed"
emit_warp_metric fail
exit 1
