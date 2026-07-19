#!/usr/bin/env bash
# tests/nspawn/test_oracle_hybrid_start.sh — 2026-07-19 oracle-alternatives
# evaluation: the llama.cpp RAM+VRAM hybrid start script for big-MoE
# candidates (GLM-4.7 / MiniMax-M3). Validates DRY_RUN honor, argv shape
# (--n-cpu-moe + --tensor-split + -ngl 999 + port 8086), tier metric label,
# bench-endpoint (not-a-router-tier) framing, and the backend adapter's
# for_sain01_hybrid constructor.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/inference/start-oracle-hybrid.sh"
ADAPTER="${__REPO_ROOT}/scripts/inference/backends/llama_cpp.py"

echo "tests/nspawn/test_oracle_hybrid_start.sh"
echo

[ -x "${SCRIPT}" ] && ok "start-oracle-hybrid.sh executable" \
  || { ko "missing start-oracle-hybrid.sh"; exit 1; }

# ----------- DRY_RUN run ---------------
set +e
out="$(SOVEREIGN_OS_DRY_RUN=1 SOVEREIGN_OS_METRICS_DISABLE= "${SCRIPT}" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "exits 0 under DRY_RUN" \
  || ko "rc=${rc}: ${out:0:200}"

echo "${out}" | grep -q "argv:" && ok "logs argv" || ko "missing argv log"
echo "${out}" | grep -q -- "--n-cpu-moe" \
  && ok "argv carries --n-cpu-moe (experts-in-RAM hybrid)" \
  || ko "argv missing --n-cpu-moe"
echo "${out}" | grep -q -- "--tensor-split 3,1" \
  && ok "argv carries --tensor-split 3,1 (PRO 6000 + 5090 VRAM ratio)" \
  || ko "argv missing --tensor-split 3,1"
echo "${out}" | grep -q -- "-ngl 999" \
  && ok "argv carries -ngl 999 (dense layers on GPU)" \
  || ko "argv missing -ngl 999"
echo "${out}" | grep -q "8086" \
  && ok "port 8086 (bench endpoint; 8081-8085 are taken tiers)" \
  || ko "port 8086 missing"
echo "${out}" | grep -q 'tier="oracle_hybrid"' \
  && ok "metric label tier=oracle_hybrid" \
  || ko "metric label missing"
echo "${out}" | grep -qi "NOT a router tier" \
  && ok "declares bench-endpoint framing (not a router tier)" \
  || ko "not-a-router-tier framing missing"
echo "${out}" | grep -q "models eval run" \
  && ok "prints the throughput-gate next step" \
  || ko "bench next-step missing"

# ----------- env overrides ---------------
set +e
out2="$(SOVEREIGN_OS_DRY_RUN=1 HYBRID_N_CPU_MOE=40 HYBRID_PORT=18186 \
        HYBRID_TENSOR_SPLIT=1,1 "${SCRIPT}" 2>&1)"
rc2=$?
set -e
[ "${rc2}" -eq 0 ] && ok "env-override run exits 0" || ko "override rc=${rc2}"
echo "${out2}" | grep -q -- "--n-cpu-moe 40" \
  && ok "HYBRID_N_CPU_MOE honored (tune-down path)" \
  || ko "HYBRID_N_CPU_MOE not honored"
echo "${out2}" | grep -q -- "--port 18186" \
  && ok "HYBRID_PORT honored" || ko "HYBRID_PORT not honored"
echo "${out2}" | grep -q -- "--tensor-split 1,1" \
  && ok "HYBRID_TENSOR_SPLIT honored" || ko "HYBRID_TENSOR_SPLIT not honored"

# ----------- idempotency guard present ---------------
grep -q "already listening" "${SCRIPT}" \
  && ok "idempotent no-op-on-listen guard present" \
  || ko "idempotency guard missing"

# ----------- adapter contract ---------------
grep -q "for_sain01_hybrid" "${ADAPTER}" \
  && ok "llama_cpp.py ships for_sain01_hybrid()" \
  || ko "for_sain01_hybrid missing"
grep -q -- "--n-cpu-moe" "${ADAPTER}" \
  && ok "llama_cpp.py emits --n-cpu-moe" \
  || ko "--n-cpu-moe missing in adapter"

echo
echo "test_oracle_hybrid_start: ${pass}/$((pass + fail)) passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
