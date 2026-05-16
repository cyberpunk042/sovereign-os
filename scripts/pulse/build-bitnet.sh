#!/usr/bin/env bash
# scripts/pulse/build-bitnet.sh — Build the Pulse runtime (bitnet.cpp) from source.
#
# Master spec § 15-16 (1-Bit Paradigm + AVX-512 Fusion) + § 17 Module 1
# (The Pulse). Compiles bitnet.cpp from Microsoft's upstream with the
# operator's znver5 + AVX-512 + VNNI flags, fetches the BitNet-b1.58
# default model into the operator's model dataset, and installs
# bitnet-cli to /usr/local/bin/.
#
# Operator runs this ONCE per host after sovereign-os is installed.
# Re-runs are idempotent: if bitnet-cli is already installed and the
# source tree is current, the build is skipped.
#
# Env vars (all overridable):
#   BITNET_REPO         git URL (default: https://github.com/microsoft/BitNet)
#   BITNET_TAG          git tag to checkout (default: main)
#   BITNET_BUILD_DIR    workspace for source + build (default: /var/lib/sovereign-os/pulse-build)
#   BITNET_INSTALL_DIR  binary install prefix (default: /usr/local)
#   BITNET_MODEL_REPO   HuggingFace model id (default: microsoft/bitnet-b1.58-2B-4T)
#   BITNET_MODEL_DIR    model destination (default: /mnt/vault/models/microsoft__bitnet-b1.58-2B-4T)
#   BITNET_SKIP_MODEL   set to 1 to skip the model fetch
#   BITNET_SKIP_BUILD   set to 1 to only fetch the model
#   SOVEREIGN_OS_DRY_RUN print intent + exit 0 without writing/building
#
# Layer B metrics:
#   sovereign_os_pulse_build_total{result="success|skip|fail"}
#   sovereign_os_pulse_build_last_run_timestamp

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/.." && pwd)"
# shellcheck source=../build/lib/common.sh
. "${__REPO_ROOT}/build/lib/common.sh" 2>/dev/null || true
# shellcheck source=../build/lib/observability.sh
. "${__REPO_ROOT}/build/lib/observability.sh" 2>/dev/null || true

# Fallback log/metric functions if libs not sourceable
type log_info >/dev/null 2>&1 || log_info() { echo "INFO  [pulse-build] $*"; }
type log_warn >/dev/null 2>&1 || log_warn() { echo "WARN  [pulse-build] $*"; }
type log_error >/dev/null 2>&1 || log_error() { echo "ERROR [pulse-build] $*" >&2; }
type emit_metric >/dev/null 2>&1 || emit_metric() { :; }

: "${BITNET_REPO:=https://github.com/microsoft/BitNet}"
: "${BITNET_TAG:=main}"
: "${BITNET_BUILD_DIR:=/var/lib/sovereign-os/pulse-build}"
: "${BITNET_INSTALL_DIR:=/usr/local}"
: "${BITNET_MODEL_REPO:=microsoft/bitnet-b1.58-2B-4T}"
: "${BITNET_MODEL_DIR:=/mnt/vault/models/microsoft__bitnet-b1.58-2B-4T}"

log_info "==== sovereign-os Pulse runtime build (bitnet.cpp) ===="
log_info "  master spec § 15-16 (1-Bit Paradigm + 512-bit AVX-512 Fusion)"
log_info "  master spec § 17 Module 1 (The Pulse)"
log_info "  compile target: -march=znver5 -O3 -mavx512* (per master spec § 16)"
log_info "  repo:     ${BITNET_REPO}"
log_info "  tag:      ${BITNET_TAG}"
log_info "  build:    ${BITNET_BUILD_DIR}"
log_info "  install:  ${BITNET_INSTALL_DIR}/bin/bitnet-cli"
log_info "  model:    ${BITNET_MODEL_REPO} → ${BITNET_MODEL_DIR}"

emit_pulse_metric() {
  emit_metric sovereign_os_pulse_build_total 1 "result=\"$1\""
}

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN: would clone, configure, build, install, fetch model"
  emit_pulse_metric skip
  exit 0
fi

# ---- prerequisite check ----
missing_pkgs=()
for cmd in git cmake make g++; do
  command -v "${cmd}" >/dev/null 2>&1 || missing_pkgs+=("${cmd}")
done
if [ "${#missing_pkgs[@]}" -gt 0 ]; then
  log_error "missing build tools: ${missing_pkgs[*]}"
  log_error "install: sudo apt install -y git cmake build-essential clang"
  emit_pulse_metric fail
  exit 1
fi

# AVX-512 check — master spec § 16 demands native 512-bit width
if ! grep -q "avx512_vnni" /proc/cpuinfo 2>/dev/null; then
  log_warn "CPU lacks avx512_vnni — Pulse will be degraded (master spec § 16 demands this)"
  log_warn "  this builds, but won't achieve master-spec performance targets"
fi

# ---- idempotency check ----
if [ "${BITNET_SKIP_BUILD:-0}" = "1" ]; then
  log_info "BITNET_SKIP_BUILD=1; skipping build step"
elif command -v bitnet-cli >/dev/null 2>&1; then
  installed_path="$(command -v bitnet-cli)"
  log_info "bitnet-cli already installed at ${installed_path}; skipping build"
  log_info "  set BITNET_SKIP_BUILD=0 BITNET_REBUILD=1 to force rebuild"
else
  # ---- clone ----
  sudo mkdir -p "${BITNET_BUILD_DIR}"
  if [ ! -d "${BITNET_BUILD_DIR}/BitNet/.git" ]; then
    log_info "cloning ${BITNET_REPO}#${BITNET_TAG}..."
    sudo git clone --depth 1 --branch "${BITNET_TAG}" "${BITNET_REPO}" "${BITNET_BUILD_DIR}/BitNet"
  else
    log_info "BitNet source already cloned at ${BITNET_BUILD_DIR}/BitNet"
    log_info "  (operator can rm -rf and re-run to refresh)"
  fi

  # ---- configure with znver5 + AVX-512 flags (master spec § 16) ----
  # R168 (original): derived CFLAGS from selfdef SD-R10 capabilities JSON
  # via inline Python.
  # R174: switched to the R173 selfdef-tune.sh shell library, which has
  # 3 source-of-truth paths in preference order — selfdefctl (SD-R19),
  # capabilities-JSON (SD-R10), native fallback — and ZMM-width hinting.
  # Canonical capabilities-JSON path is /var/lib/selfdef/hardware-capabilities.json
  # (operator override: BITNET_CAPABILITIES_FILE → SELFDEF_CAPABILITIES_FILE alias).
  # Operator can still override by setting BITNET_CFLAGS explicitly OR
  # by pre-setting SELFDEF_HARDWARE_MARCH (the lib respects both).
  if [ -z "${BITNET_CFLAGS:-}" ]; then
    # Legacy alias: BITNET_CAPABILITIES_FILE points at the JSON. The
    # lib's SELFDEF_CAPABILITIES_FILE is the new canonical name.
    if [ -n "${BITNET_CAPABILITIES_FILE:-}" ]; then
      export SELFDEF_CAPABILITIES_FILE="${BITNET_CAPABILITIES_FILE}"
    fi
    # shellcheck source=../build/lib/selfdef-tune.sh
    . "${__REPO_ROOT}/build/lib/selfdef-tune.sh"
    selfdef_tune_load
    case "${SELFDEF_HARDWARE_TUNE_SOURCE}" in
      selfdefctl|capabilities_json)
        BITNET_CFLAGS="${SELFDEF_HARDWARE_CFLAGS} -O3"
        log_info "R168/R174: BITNET_CFLAGS from selfdef-tune (source=${SELFDEF_HARDWARE_TUNE_SOURCE})"
        ;;
      *)
        # Fallback / native / operator-set without VNNI on a SAIN-01
        # target → keep the master-spec § 16 hardcoded default.
        ;;
    esac
  fi
  : "${BITNET_CFLAGS:=-march=znver5 -O3 -mavx512f -mavx512dq -mavx512bw -mavx512vl -mavx512bf16 -mavx512fp16}"
  log_info "configuring with CFLAGS=${BITNET_CFLAGS}"
  cd "${BITNET_BUILD_DIR}/BitNet"
  export CFLAGS="${BITNET_CFLAGS}"
  export CXXFLAGS="${CFLAGS}"
  export GGML_AVX512=1
  export GGML_AVX512_VBMI=1
  export GGML_AVX512_VNNI=1

  # Build per BitNet upstream README (cmake-based as of 2026 era)
  sudo -E mkdir -p build
  sudo -E cmake -B build -DCMAKE_BUILD_TYPE=Release \
       -DCMAKE_C_FLAGS_RELEASE="${CFLAGS}" \
       -DCMAKE_CXX_FLAGS_RELEASE="${CXXFLAGS}" || {
    log_error "cmake configure failed"
    emit_pulse_metric fail
    exit 1
  }

  log_info "compiling (this takes 5-15 min on SAIN-01-class hardware)..."
  sudo -E cmake --build build --parallel "$(nproc)" || {
    log_error "cmake build failed"
    emit_pulse_metric fail
    exit 1
  }

  # ---- install ----
  log_info "installing bitnet-cli → ${BITNET_INSTALL_DIR}/bin/"
  if [ -x build/bin/bitnet-cli ]; then
    sudo install -m 0755 build/bin/bitnet-cli "${BITNET_INSTALL_DIR}/bin/"
  elif [ -x build/bitnet-cli ]; then
    sudo install -m 0755 build/bitnet-cli "${BITNET_INSTALL_DIR}/bin/"
  else
    log_error "bitnet-cli binary not found after build"
    log_error "  searched: build/bin/bitnet-cli, build/bitnet-cli"
    emit_pulse_metric fail
    exit 1
  fi
  log_info "✓ bitnet-cli installed at ${BITNET_INSTALL_DIR}/bin/bitnet-cli"
fi

# ---- fetch model ----
if [ "${BITNET_SKIP_MODEL:-0}" = "1" ]; then
  log_info "BITNET_SKIP_MODEL=1; skipping model fetch"
elif [ -d "${BITNET_MODEL_DIR}" ] && [ -n "$(ls -A "${BITNET_MODEL_DIR}" 2>/dev/null)" ]; then
  log_info "model already present at ${BITNET_MODEL_DIR}; skipping fetch"
else
  log_info "fetching model ${BITNET_MODEL_REPO} → ${BITNET_MODEL_DIR}"
  sudo mkdir -p "${BITNET_MODEL_DIR}"
  if command -v huggingface-cli >/dev/null 2>&1; then
    sudo huggingface-cli download "${BITNET_MODEL_REPO}" --local-dir "${BITNET_MODEL_DIR}" || {
      log_error "huggingface-cli download failed"
      log_error "  set HF_TOKEN if gated, or use 'sovereign-osctl models pull' alternative"
      emit_pulse_metric fail
      exit 1
    }
  else
    log_warn "huggingface-cli not installed (pip install huggingface_hub)"
    log_warn "  alternative: sovereign-osctl models pull ${BITNET_MODEL_REPO}"
    log_warn "  skipping model fetch; bitnet-cli installed but no default model"
  fi
fi

emit_pulse_metric success
emit_metric sovereign_os_pulse_build_last_run_timestamp "$(date +%s)" ""
log_info "==== Pulse runtime ready ===="
log_info "  next: sovereign-osctl trinity profile switch <profile> (e.g. ultra-sovereign-efficiency)"
log_info "  then: systemctl start sovereign-pulse  (or scripts/inference/start-pulse.sh)"
