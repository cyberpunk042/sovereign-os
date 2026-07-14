#!/usr/bin/env bash
# scripts/inference/dspark-wrap.sh — DSpark speculative-decoding wrapper
# (the DFlash successor). Operator directive (2026-07-13, verbatim):
#
#   "search for Dspark from Deepseek online and we are going to implement that
#    ... opt-in like we want everything but on by default for now and we find
#    it a proper place an a panel, like for the LM Orchestrator Features GPUs
#    section"
#
# DSpark (DeepSeek, open-sourced 2026-06-27) is speculative decoding built ON
# TOP of DFlash: DFlash is the parallel draft BACKBONE; DSpark adds a lightweight
# sequential "Markov head" + domain confidence thresholding, and verifies the
# whole draft block in ONE target forward pass via rejection sampling — so it is
# LOSSLESS (preserves the target model's output distribution EXACTLY). Shipped
# default is DSpark-5 (a 5-token draft block). 60-85% faster per-user generation
# (V4-Flash) / 57-78% (Pro) over MTP-1.
#
# Key difference from dflash-wrap.sh: because DSpark is LOSSLESS + confidence-
# gated, it defaults ENABLED for EVERY task type (code | math | conversational |
# creative), not just code/math. It is opt-in but ON BY DEFAULT for now.
#
# Sources (research 2026-07-13): marktechpost.com/2026/06/27/deepseek-releases-
# dspark-...; venturebeat.com/orchestration/deepseek-open-sources-dspark-...;
# fullstack.com/labs/.../what-deepseeks-dspark-means-for-llm-performance.
#
# CLI:
#   dspark-wrap.sh --task-type <code|math|conversational|creative>
#                  --backend <vllm|llama_cpp|transformers>
#                  -- <backend argv ...>
#
# Env vars:
#   DSPARK_ENABLE_OVERRIDE   force-enable regardless of the toggle (operator)
#   DSPARK_DISABLE_OVERRIDE  force-disable regardless of the toggle
#                            (DISABLE wins when both are set)
#   DSPARK_BLOCK             draft block size (default 5 = DSpark-5; tested to 16)
#   DSPARK_PATH              dir of the cloned DSpark repo (default: /opt/dspark)
#   DFLASH_PATH              DFlash install for the graceful fallback (default /opt/dflash)
#   DSPARK_STATE             toggle state file (default /etc/sovereign-os/dspark.toml);
#                            `enabled = false` there turns it off (opt-in default-on)
#   SOVEREIGN_OS_DRY_RUN     print decision + argv, do not exec
#
# Layer B metrics:
#   sovereign_os_dspark_decision_total{task_type,decision}
#   sovereign_os_dspark_last_invocation_timestamp

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh" 2>/dev/null || true
# shellcheck source=../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh" 2>/dev/null || true

type log_info >/dev/null 2>&1 || log_info() { echo "INFO  [dspark-wrap] $*"; }
type log_warn >/dev/null 2>&1 || log_warn() { echo "WARN  [dspark-wrap] $*"; }
type log_error >/dev/null 2>&1 || log_error() { echo "ERROR [dspark-wrap] $*" >&2; }
type emit_metric >/dev/null 2>&1 || emit_metric() { :; }

: "${DSPARK_PATH:=/opt/dspark}"
: "${DFLASH_PATH:=/opt/dflash}"
: "${DSPARK_BLOCK:=5}"
: "${DSPARK_STATE:=/etc/sovereign-os/dspark.toml}"

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
usage: dspark-wrap.sh --task-type {code|math|conversational|creative}
                     --backend {vllm|llama_cpp|transformers}
                     -- <backend argv ...>

DSpark speculative-decoding wrapper — the DFlash successor (DeepSeek, 2026-06-27).

Gating policy: DSpark is LOSSLESS (rejection-sampling verify preserves the target
distribution exactly) + confidence-gated, so it defaults ENABLED for EVERY task
type. Opt-in but ON BY DEFAULT for now.

Env vars override:
  DSPARK_ENABLE_OVERRIDE=1   force-enable regardless of the toggle
  DSPARK_DISABLE_OVERRIDE=1  force-disable (DISABLE wins when both set)
  DSPARK_BLOCK=<n>           draft block size (default 5 = DSpark-5)
Toggle state:
  ${DSPARK_STATE} with 'enabled = false' turns DSpark off (opt-in default-on)
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

# ---------- toggle state (opt-in, ON BY DEFAULT) ----------
# Absent state file → ENABLED (on-by-default). `enabled = false` → OFF.
TOGGLE_OFF=""
if [ -f "${DSPARK_STATE}" ] && grep -Eq '^[[:space:]]*enabled[[:space:]]*=[[:space:]]*false' "${DSPARK_STATE}" 2>/dev/null; then
  TOGGLE_OFF="1"
fi

# ---------- gating decision (DISABLE wins > ENABLE > toggle > default-ON) ----------
DECISION=""
DECISION_REASON=""

if [ -n "${DSPARK_DISABLE_OVERRIDE:-}" ]; then
  DECISION="disabled"
  DECISION_REASON="operator-override (DSPARK_DISABLE_OVERRIDE)"
elif [ -n "${DSPARK_ENABLE_OVERRIDE:-}" ]; then
  DECISION="enabled"
  DECISION_REASON="operator-override (DSPARK_ENABLE_OVERRIDE)"
elif [ -n "${TOGGLE_OFF}" ]; then
  DECISION="disabled"
  DECISION_REASON="toggle off in ${DSPARK_STATE} (enabled = false)"
else
  DECISION="enabled"
  DECISION_REASON="opt-in default-on — DSpark is lossless, enabled for task-type '${TASK_TYPE}'"
fi

log_info "==== DSpark decision ===="
log_info "  task type:   ${TASK_TYPE}"
log_info "  backend:     ${BACKEND}"
log_info "  block size:  DSpark-${DSPARK_BLOCK}"
log_info "  decision:    ${DECISION}"
log_info "  reason:      ${DECISION_REASON}"
log_info "  DSpark dir:  ${DSPARK_PATH}"

emit_metric sovereign_os_dspark_decision_total 1 \
  "task_type=\"${TASK_TYPE}\",decision=\"${DECISION}\""
emit_metric sovereign_os_dspark_last_invocation_timestamp "$(date +%s)" \
  "task_type=\"${TASK_TYPE}\""

# ---------- build final argv ----------
FINAL_ARGV=("${BACKEND_ARGV[@]}")

if [ "${DECISION}" = "enabled" ]; then
  if [ ! -d "${DSPARK_PATH}" ]; then
    # Graceful degradation — never a hard failure. Fall back to the DFlash draft
    # backbone (code/math) if it is installed, else vanilla decoding.
    log_warn "DSpark not installed at ${DSPARK_PATH}"
    log_warn "  install via: git clone https://github.com/deepseek-ai/dspark ${DSPARK_PATH}"
    log_warn "               cd ${DSPARK_PATH} && pip install -e ."
    if { [ "${TASK_TYPE}" = "code" ] || [ "${TASK_TYPE}" = "math" ]; } && [ -d "${DFLASH_PATH}" ]; then
      log_warn "  falling back to the DFlash draft backbone (M083) for this invocation"
      DECISION="downshift-dflash"
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
          export PYTHONPATH="${DFLASH_PATH}:${PYTHONPATH:-}"
          ;;
      esac
    else
      log_warn "  falling back to vanilla decoding for this invocation"
      DECISION="disabled-no-install"
    fi
  else
    case "${BACKEND}" in
      vllm)
        FINAL_ARGV+=("--speculative-config")
        FINAL_ARGV+=("{\"method\":\"dspark\",\"num_speculative_tokens\":${DSPARK_BLOCK},\"path\":\"${DSPARK_PATH}\"}")
        ;;
      llama_cpp)
        FINAL_ARGV+=("--draft-model")
        FINAL_ARGV+=("${DSPARK_PATH}/draft.gguf")
        ;;
      transformers)
        # transformers integration loads dspark as a generation strategy
        export PYTHONPATH="${DSPARK_PATH}:${PYTHONPATH:-}"
        ;;
    esac
  fi
fi

log_info "  final argv:  ${FINAL_ARGV[*]}"

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN: would exec the above argv — exiting 0"
  exit 0
fi

if [ "${#FINAL_ARGV[@]}" -eq 0 ]; then
  log_error "no backend argv supplied after --"
  exit 2
fi

exec "${FINAL_ARGV[@]}"
