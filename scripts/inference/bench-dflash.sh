#!/usr/bin/env bash
# scripts/inference/bench-dflash.sh — Benchmark DFlash speculative decoding.
#
# Measures tokens/sec with and without DFlash on a code-generation task.
# Requires the DFlash library installed at /opt/dflash and a resident
# Oracle-tier model (default: the active Oracle model).
#
# Env vars:
#   DFLASH_PATH              (default: /opt/dflash)
#   ORACLE_MODEL             (default: read from active profile provisioning.model)
#   ORACLE_ENDPOINT          (default: http://127.0.0.1:8083)
#   BENCH_PROMPT             (default: a Python function implementation task)
#   BENCH_MAX_TOKENS         (default: 256)
#   SOVEREIGN_OS_DRY_RUN     print intent + exit 0
#
# Outputs:
#   Layer B metric: sovereign_os_dflash_bench_ratio (vanilla_tok_per_sec / dflash_tok_per_sec)
#   Prints a human-readable comparison table.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh" 2>/dev/null || true
# shellcheck source=../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh" 2>/dev/null || true

type log_info >/dev/null 2>&1 || log_info() { echo "INFO  [bench-dflash] $*"; }
type log_warn >/dev/null 2>&1 || log_warn() { echo "WARN  [bench-dflash] $*"; }
type emit_metric >/dev/null 2>&1 || emit_metric() { :; }

: "${DFLASH_PATH:=/opt/dflash}"
: "${ORACLE_ENDPOINT:=http://127.0.0.1:8083}"
: "${BENCH_MAX_TOKENS:=256}"

BENCH_PROMPT="${BENCH_PROMPT:-Write a Python function \`is_prime(n)\` that returns True if n is prime, using the Miller-Rabin test for large n. Include docstring and type hints.}"

log_info "==== DFlash speculative-decoding benchmark ===="

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN: would benchmark with/without DFlash on Oracle endpoint ${ORACLE_ENDPOINT}"
  exit 0
fi

# Resolve active Oracle model from profile if not set
if [ -z "${ORACLE_MODEL:-}" ]; then
  ORACLE_MODEL="$(python3 -c "
import os, yaml
pf = os.environ.get('SOVEREIGN_OS_PROFILE_FILE', '/etc/sovereign-os/active-profile')
path = pf if os.path.isfile(pf) else None
if not path:
    print('')
    sys.exit(0)
with open(path) as f:
    d = yaml.safe_load(f) or {}
print((d.get('provisioning') or {}).get('model', {}).get('repo', ''))
" 2>/dev/null || true)"
fi
: "${ORACLE_MODEL:=local-oracle}"

if [ ! -d "${DFLASH_PATH}" ]; then
  log_error "DFlash not installed at ${DFLASH_PATH}"
  log_error "  run: scripts/hooks/post-install/dflash-install.sh"
  exit 1
fi

# Check Oracle endpoint is reachable
if ! curl -sf "${ORACLE_ENDPOINT}/health" >/dev/null 2>&1 && ! curl -sf "${ORACLE_ENDPOINT}/v1/models" >/dev/null 2>&1; then
  log_warn "Oracle endpoint ${ORACLE_ENDPOINT} not responding — starting it first"
  log_warn "  run: systemctl start sovereign-oracle-core (or scripts/inference/start-oracle-core.sh)"
  exit 1
fi

run_bench() {
  local dflash_enabled="$1"
  local task_type="code"
  local payload
  payload="$(cat <<EOF
{
  "model": "${ORACLE_MODEL}",
  "messages": [{"role": "user", "content": "${BENCH_PROMPT}"}],
  "max_tokens": ${BENCH_MAX_TOKENS},
  "stream": false
}
EOF
)"
  local start end duration
  start="$(date +%s.%N)"
  if [ "${dflash_enabled}" = "1" ]; then
    # Use dflash-wrap.sh to inject speculative-decoding flags
    python3 "${__REPO_ROOT}/scripts/inference/backends/vllm_backend.py" --task-type "${task_type}" --dflash-path "${DFLASH_PATH}" --payload "${payload}" --endpoint "${ORACLE_ENDPOINT}" 2>/dev/null || true
  else
    curl -sf -X POST "${ORACLE_ENDPOINT}/v1/chat/completions" \
      -H "Content-Type: application/json" \
      -d "${payload}" >/dev/null 2>&1 || true
  fi
  end="$(date +%s.%N)"
  duration="$(python3 -c "print(f'${end}' - f'${start}')")"
  printf '%s\n' "${duration}"
}

log_info "warming up Oracle (single request)..."
run_bench 0 >/dev/null 2>&1 || true
sleep 2

log_info "benchmarking VANILLA decoding (no DFlash)..."
vanilla_time="$(run_bench 0)"
log_info "  duration: ${vanilla_time}s"

log_info "benchmarking DFlash speculative decoding..."
dflash_time="$(run_bench 1)"
log_info "  duration: ${dflash_time}s"

# Compute speedup ratio (higher is better for DFlash)
ratio="$(python3 -c "
v = float('${vanilla_time}')
d = float('${dflash_time}')
if d <= 0:
    print('inf')
else:
    print(f'{v/d:.2f}')
")"

log_info ""
log_info "==== Results ===="
printf "  %-20s %10ss\n" "Vanilla:" "${vanilla_time}"
printf "  %-20s %10ss\n" "DFlash:" "${dflash_time}"
printf "  %-20s %10sx\n" "Speedup:" "${ratio}"

emit_metric sovereign_os_dflash_bench_ratio "${ratio}" ""
log_info ""
log_info "Target: >=3x speedup on code/math tasks (operator-verbatim Block 7)"
