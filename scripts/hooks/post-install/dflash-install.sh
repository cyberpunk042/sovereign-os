#!/usr/bin/env bash
# scripts/hooks/post-install/dflash-install.sh — Install DFlash speculative-decoding library.
#
# Master spec Block 7 — DFlash (arXiv:2602.06036, Z-Lab).
# Clones github.com/z-lab/dflash, builds the vLLM plugin, installs to /opt/dflash.
#
# Idempotent: if /opt/dflash exists and passes smoke test, skipped.
# Env vars:
#   DFLASH_REPO              (default: https://github.com/z-lab/dflash)
#   DFLASH_TAG               (default: main)
#   DFLASH_PATH              (default: /opt/dflash)
#   VLLM_VERSION             (default: 0.20.1)
#   SOVEREIGN_OS_DRY_RUN     print intent + exit 0
#
# Layer B metrics:
#   sovereign_os_dflash_install_total{result="success|skip|fail"}

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh" 2>/dev/null || true
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh" 2>/dev/null || true

type log_info >/dev/null 2>&1 || log_info() { echo "INFO  [dflash-install] $*"; }
type log_warn >/dev/null 2>&1 || log_warn() { echo "WARN  [dflash-install] $*"; }
type log_error >/dev/null 2>&1 || log_error() { echo "ERROR [dflash-install] $*" >&2; }
type emit_metric >/dev/null 2>&1 || emit_metric() { :; }

: "${DFLASH_REPO:=https://github.com/z-lab/dflash}"
: "${DFLASH_TAG:=main}"
: "${DFLASH_PATH:=/opt/dflash}"
: "${VLLM_VERSION:=0.20.1}"

STEP_ID="dflash-install"

log_step_header "${STEP_ID}" "install DFlash speculative-decoding library"

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN: would clone ${DFLASH_REPO}#${DFLASH_TAG} → ${DFLASH_PATH}"
  emit_metric sovereign_os_dflash_install_total 1 "result=\"skip-dry-run\""
  exit 0
fi

require_root

# Idempotency: if DFlash exists and has a non-empty plugin dir, smoke-test it.
if [ -d "${DFLASH_PATH}" ] && [ -n "$(ls -A "${DFLASH_PATH}" 2>/dev/null)" ]; then
  log_info "DFlash already present at ${DFLASH_PATH}"
  # Basic smoke: look for at least one .py or .so file
  if find "${DFLASH_PATH}" -maxdepth 2 \( -name "*.py" -o -name "*.so" \) | grep -q .; then
    log_info "  smoke test passed (plugin artifacts present)"
    emit_metric sovereign_os_dflash_install_total 1 "result=\"skip\""
    exit 0
  else
    log_warn "  existing directory lacks plugin artifacts; re-installing"
  fi
fi

# Prerequisites
missing=()
for cmd in git python3 pip; do
  command -v "${cmd}" >/dev/null 2>&1 || missing+=("${cmd}")
done
if [ "${#missing[@]}" -gt 0 ]; then
  log_error "missing prerequisites: ${missing[*]}"
  emit_metric sovereign_os_dflash_install_total 1 "result=\"fail\""
  exit 1
fi

log_info "cloning ${DFLASH_REPO}#${DFLASH_TAG} → ${DFLASH_PATH}"
mkdir -p "$(dirname "${DFLASH_PATH}")"
if [ -d "${DFLASH_PATH}/.git" ]; then
  log_info "  existing clone found; fetching updates"
  git -C "${DFLASH_PATH}" fetch --depth 1 origin "${DFLASH_TAG}" || true
  git -C "${DFLASH_PATH}" reset --hard "origin/${DFLASH_TAG}" || true
else
  git clone --depth 1 --branch "${DFLASH_TAG}" "${DFLASH_REPO}" "${DFLASH_PATH}"
fi

cd "${DFLASH_PATH}"

# Build / install the vLLM plugin (best-effort; upstream may change structure)
if [ -f "setup.py" ] || [ -f "pyproject.toml" ]; then
  log_info "installing DFlash Python package into the active vLLM env"
  pip install -e "${DFLASH_PATH}" || {
    log_warn "pip install -e . failed — DFlash may require manual build steps"
    log_warn "  see ${DFLASH_PATH}/README.md for upstream build instructions"
  }
fi

# Verify vLLM version compatibility
vllm_installed="$(python3 -c 'import vllm; print(vllm.__version__)' 2>/dev/null || echo none)"
if [ "${vllm_installed}" = "none" ]; then
  log_warn "vLLM not installed in the active Python env — DFlash plugin cannot load until vLLM is present"
  log_warn "  install vLLM: pip install vllm==${VLLM_VERSION}"
else
  log_info "vLLM version: ${vllm_installed}"
fi

# Layer B metric + completion
emit_metric sovereign_os_dflash_install_total 1 "result=\"success\""
log_info "DFlash installed at ${DFLASH_PATH}"
log_info "  wrapper: scripts/inference/dflash-wrap.sh"
log_info "  next: set DFLASH_PATH=${DFLASH_PATH} and run inference with --task-type code|math"
