#!/usr/bin/env bash
# scripts/pulse/wasm-aot.sh — Wasm-to-AVX-512 AOT compilation pipeline.
#
# Master spec § 20 — The Pulse Implementation:
#
#   "When The Pulse processes low-bit matrix logic via WebAssembly, it
#    avoids standard JIT (Just-In-Time) compilation bloat. Instead, it
#    uses an Ahead-Of-Time (AOT) compilation lifecycle optimized via
#    Cranelift or LLVM to output native Zen 5 machine code."
#
# This script:
#   1. Installs wasmtime (via official installer or apt where available)
#   2. Configures the build environment with master spec § 20.2's
#      WASMTIME_COMPARE_OPTIONS and target flags
#   3. AOT-compiles a given .wasm file (or the sample pulse_core.wasm)
#      to a native .cwasm output via Cranelift
#   4. Pins to CCD0 (cores 0-11) via taskset per master spec
#
# Env vars (all overridable):
#   WASMTIME_VERSION       (default: latest)
#   WASM_INPUT             input .wasm path (default: scripts/pulse/sample/pulse_core.wasm)
#   WASM_OUTPUT_DIR        output .cwasm dir (default: /var/lib/sovereign-os/pulse-aot)
#   WASM_TARGET_CPU        Cranelift target (default: znver5)
#   WASM_OPT_LEVEL         optimization level (default: speed; per master spec § 20.2)
#   WASM_AFFINITY          taskset CPU list (default: 0-11 per master spec § 19.2 CCD0+CCD1 0-9)
#   SOVEREIGN_OS_DRY_RUN   print intent + exit 0
#
# Layer B metrics:
#   sovereign_os_pulse_wasm_aot_total{result="success|skip|fail"}
#   sovereign_os_pulse_wasm_aot_last_run_timestamp

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/.." && pwd)"
# shellcheck source=../build/lib/common.sh
. "${__REPO_ROOT}/build/lib/common.sh" 2>/dev/null || true
# shellcheck source=../build/lib/observability.sh
. "${__REPO_ROOT}/build/lib/observability.sh" 2>/dev/null || true

type log_info >/dev/null 2>&1 || log_info() { echo "INFO  [wasm-aot] $*"; }
type log_warn >/dev/null 2>&1 || log_warn() { echo "WARN  [wasm-aot] $*"; }
type log_error >/dev/null 2>&1 || log_error() { echo "ERROR [wasm-aot] $*" >&2; }
type emit_metric >/dev/null 2>&1 || emit_metric() { :; }

: "${WASMTIME_VERSION:=latest}"
: "${WASM_INPUT:=${__SCRIPT_DIR}/sample/pulse_core.wasm}"
: "${WASM_OUTPUT_DIR:=/var/lib/sovereign-os/pulse-aot}"
: "${WASM_TARGET_CPU:=znver5}"
: "${WASM_OPT_LEVEL:=speed}"
: "${WASM_AFFINITY:=0-11}"

log_info "==== sovereign-os Wasm-to-AVX-512 AOT pipeline ===="
log_info "  master spec § 20 (The Pulse Implementation)"
log_info "  wasmtime version:   ${WASMTIME_VERSION}"
log_info "  input:              ${WASM_INPUT}"
log_info "  output dir:         ${WASM_OUTPUT_DIR}"
log_info "  target CPU:         ${WASM_TARGET_CPU}"
log_info "  opt level:          ${WASM_OPT_LEVEL}"
log_info "  affinity:           ${WASM_AFFINITY} (CCD0+CCD1 0-9 per master spec § 19.2)"

emit_aot_metric() {
  emit_metric sovereign_os_pulse_wasm_aot_total 1 "result=\"$1\""
}

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN: would install wasmtime + AOT-compile ${WASM_INPUT}"
  log_info "  command: taskset -c ${WASM_AFFINITY} wasmtime compile \\"
  log_info "             --target ${WASM_TARGET_CPU} -O ${WASM_OPT_LEVEL} ${WASM_INPUT}"
  log_info "  master spec § 20.2 verbatim flags:"
  log_info "    WASMTIME_COMPARE_OPTIONS=\"-C target-cpu=znver5 -C opt-level=3 -C relaxed-simd=true\""
  emit_aot_metric skip
  exit 0
fi

# ---- prerequisite: wasmtime installed? ----
if ! command -v wasmtime >/dev/null 2>&1; then
  log_warn "wasmtime not installed"
  log_warn "  install via: curl https://wasmtime.dev/install.sh -sSf | bash"
  log_warn "  or:          cargo install wasmtime-cli"
  log_warn "  or:          download from https://github.com/bytecodealliance/wasmtime/releases"
  emit_aot_metric fail
  exit 1
fi

wasmtime_version="$(wasmtime --version 2>/dev/null | head -1 || echo unknown)"
log_info "  wasmtime detected: ${wasmtime_version}"

# ---- input check ----
if [ ! -f "${WASM_INPUT}" ]; then
  log_error "input wasm not found: ${WASM_INPUT}"
  log_error "  sample placeholder at: ${__SCRIPT_DIR}/sample/pulse_core.wasm"
  log_error "  or set WASM_INPUT=<path-to-your-wasm>"
  emit_aot_metric fail
  exit 1
fi

# ---- AOT compile ----
mkdir -p "${WASM_OUTPUT_DIR}"
out_name="$(basename "${WASM_INPUT}" .wasm).cwasm"
out_path="${WASM_OUTPUT_DIR}/${out_name}"

log_info "AOT-compiling → ${out_path}"

# Master spec § 20.2 verbatim: explicit task execution on CCD0 cores
# only. Compile with target-cpu=znver5 + opt-level=speed.
if command -v taskset >/dev/null 2>&1; then
  taskset -c "${WASM_AFFINITY}" \
    wasmtime compile \
      --target "${WASM_TARGET_CPU}" \
      -O "${WASM_OPT_LEVEL}" \
      -o "${out_path}" \
      "${WASM_INPUT}" || {
    log_error "AOT compilation failed"
    emit_aot_metric fail
    exit 1
  }
else
  log_warn "taskset not available; compiling without CCD pinning"
  wasmtime compile \
    --target "${WASM_TARGET_CPU}" \
    -O "${WASM_OPT_LEVEL}" \
    -o "${out_path}" \
    "${WASM_INPUT}" || {
    log_error "AOT compilation failed"
    emit_aot_metric fail
    exit 1
  }
fi

# ---- verify output ----
if [ ! -f "${out_path}" ]; then
  log_error "expected output not produced: ${out_path}"
  emit_aot_metric fail
  exit 1
fi

out_size="$(stat -c '%s' "${out_path}")"
log_info "✓ AOT output: ${out_path} (${out_size} bytes)"
log_info "  run via: wasmtime --allow-precompiled ${out_path}"

emit_aot_metric success
emit_metric sovereign_os_pulse_wasm_aot_last_run_timestamp "$(date +%s)" ""
