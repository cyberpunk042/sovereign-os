#!/usr/bin/env bash
# scripts/inference/dflash-wrap.sh — DFlash speculative-decoding wrapper.
#
# Master spec Block 7 — DFlash addition (verbatim operator text):
#
#   "And there is also Dflash I recently learned about that somehow
#    with code task on model that fit in memory like any functional
#    model in general it can work 3 times faster, does not work on
#    creative tasks in general but interesting topic and place of
#    introspection and knowledge"
#
# Provenance (L0 ingest 2026-05-15):
#   - Paper: arXiv:2602.06036 — "DFlash: Block Diffusion for Flash
#     Speculative Decoding" (Z-Lab, Feb 2026)
#   - Repo:  github.com/z-lab/dflash
#
# This wrapper:
#   1. Detects the requested task_type (code | math | conversational |
#      creative) and gates DFlash on/off accordingly. Operator framing
#      is verbatim: code+math get the 3× speedup; creative is GATED
#      OFF by default to preserve sampling quality.
#   2. Wraps a backend invocation argv (vllm / llama.cpp / transformers)
#      with --speculative-decoding flags when DFlash is enabled
#   3. Emits Layer B counters per invocation
#
# CLI:
#   dflash-wrap.sh --task-type <code|math|conversational|creative>
#                  --backend <vllm|llama_cpp|transformers>
#                  -- <backend argv ...>
#
# Env vars:
#   DFLASH_ENABLE_OVERRIDE   force-enable for any task type (operator
#                            override; default empty — gating respected)
#   DFLASH_DISABLE_OVERRIDE  force-disable for any task type
#   DFLASH_PATH              dir of the cloned z-lab/dflash repo
#                            (default: /opt/dflash)
#   SOVEREIGN_OS_DRY_RUN     print decision + argv, do not exec
#
# Layer B metrics:
#   sovereign_os_dflash_decision_total{task_type,decision}
#   sovereign_os_dflash_last_invocation_timestamp

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh" 2>/dev/null || true
# shellcheck source=../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh" 2>/dev/null || true

type log_info >/dev/null 2>&1 || log_info() { echo "INFO  [dflash-wrap] $*"; }
type log_warn >/dev/null 2>&1 || log_warn() { echo "WARN  [dflash-wrap] $*"; }
type log_error >/dev/null 2>&1 || log_error() { echo "ERROR [dflash-wrap] $*" >&2; }
type emit_metric >/dev/null 2>&1 || emit_metric() { :; }

: "${DFLASH_PATH:=/opt/dflash}"

TASK_TYPE=""
BACKEND=""
BACKEND_ARGV=()

while [ $# -gt 0 ]; do
  case "$1" in
    --task-type) TASK_TYPE="$2"; shift 2 ;;
    --backend)   BACKEND="$2"; shift 2 ;;
    --) shift; BACKEND_ARGV=("$@"); break ;;
    -h|--help)
      cat <<EOF
usage: dflash-wrap.sh --task-type {code|math|conversational|creative}
                     --backend {vllm|llama_cpp|transformers}
                     -- <backend argv ...>

Master spec Block 7 — DFlash speculative-decoding wrapper.

Gating policy (operator verbatim: "3× faster on code, doesn't work on
creative"):
  code         → DFlash enabled
  math         → DFlash enabled
  conversational → DFlash disabled (moderate gains, not worth the
                   quantization noise)
  creative     → DFlash disabled (sampling quality degradation)

Env vars override:
  DFLASH_ENABLE_OVERRIDE=1   force-enable regardless of task_type
  DFLASH_DISABLE_OVERRIDE=1  force-disable regardless of task_type
EOF
      exit 0
      ;;
    *)
      log_error "unknown arg: $1"
      exit 2
      ;;
  esac
done

if [ -z "${TASK_TYPE}" ] || [ -z "${BACKEND}" ]; then
  log_error "both --task-type and --backend required"
  exit 2
fi

case "${TASK_TYPE}" in
  code|math|conversational|creative) ;;
  *)
    log_error "unknown --task-type '${TASK_TYPE}' — must be one of: code|math|conversational|creative"
    exit 2
    ;;
esac

case "${BACKEND}" in
  vllm|llama_cpp|transformers) ;;
  *)
    log_error "unknown --backend '${BACKEND}' — must be one of: vllm|llama_cpp|transformers"
    exit 2
    ;;
esac

# ---------- gating decision ----------
DECISION=""
DECISION_REASON=""

if [ -n "${DFLASH_DISABLE_OVERRIDE:-}" ]; then
  DECISION="disabled"
  DECISION_REASON="operator-override (DFLASH_DISABLE_OVERRIDE)"
elif [ -n "${DFLASH_ENABLE_OVERRIDE:-}" ]; then
  DECISION="enabled"
  DECISION_REASON="operator-override (DFLASH_ENABLE_OVERRIDE)"
else
  case "${TASK_TYPE}" in
    code|math)
      DECISION="enabled"
      DECISION_REASON="task-type '${TASK_TYPE}' matches operator's 3× speedup pattern"
      ;;
    conversational|creative)
      DECISION="disabled"
      DECISION_REASON="task-type '${TASK_TYPE}' — operator: 'does not work on creative tasks in general'"
      ;;
  esac
fi

log_info "==== DFlash decision ===="
log_info "  task type:  ${TASK_TYPE}"
log_info "  backend:    ${BACKEND}"
log_info "  decision:   ${DECISION}"
log_info "  reason:     ${DECISION_REASON}"
log_info "  DFlash dir: ${DFLASH_PATH}"

emit_metric sovereign_os_dflash_decision_total 1 \
  "task_type=\"${TASK_TYPE}\",decision=\"${DECISION}\""
emit_metric sovereign_os_dflash_last_invocation_timestamp "$(date +%s)" \
  "task_type=\"${TASK_TYPE}\""

# ---------- build final argv ----------
FINAL_ARGV=("${BACKEND_ARGV[@]}")

if [ "${DECISION}" = "enabled" ]; then
  if [ ! -d "${DFLASH_PATH}" ]; then
    log_warn "DFlash not installed at ${DFLASH_PATH}"
    log_warn "  install via: git clone https://github.com/z-lab/dflash ${DFLASH_PATH}"
    log_warn "               cd ${DFLASH_PATH} && pip install -e ."
    log_warn "  falling back to vanilla decoding for this invocation"
    DECISION="disabled-no-install"
  else
    case "${BACKEND}" in
      vllm)
        FINAL_ARGV+=("--speculative-config")
        FINAL_ARGV+=("{\"method\":\"dflash\",\"path\":\"${DFLASH_PATH}\"}")
        ;;
      llama_cpp)
        FINAL_ARGV+=("--draft-model")
        FINAL_ARGV+=("${DFLASH_PATH}/draft.gguf")
        ;;
      transformers)
        # transformers integration loads dflash as a generation strategy
        export PYTHONPATH="${DFLASH_PATH}:${PYTHONPATH:-}"
        ;;
    esac
  fi
fi

log_info "  final argv: ${FINAL_ARGV[*]}"

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN: would exec the above argv — exiting 0"
  exit 0
fi

if [ "${#FINAL_ARGV[@]}" -eq 0 ]; then
  log_error "no backend argv supplied after --"
  exit 2
fi

exec "${FINAL_ARGV[@]}"
