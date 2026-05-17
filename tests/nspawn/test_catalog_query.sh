#!/usr/bin/env bash
# tests/nspawn/test_catalog_query.sh — R213 catalog query verb.
# Filter the R212 catalog by class / tier / purpose / size / quant /
# max-vram / min-context, surface as either table or JSON.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/models/catalog-query.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_catalog_query.sh"
echo

[ -x "${SCRIPT}" ] && ok "catalog-query.py executable" \
  || { ko "missing catalog-query.py"; exit 1; }

grep -q "query)" "${OSCTL}" \
  && ok "osctl bridges 'models query'" \
  || ko "osctl bridge missing"
grep -q "models query \[--class" "${OSCTL}" \
  && ok "osctl help documents models query" \
  || ko "help missing"

# --- single-flag filters ---
set +e
rlm_out="$(python3 "${SCRIPT}" --class rlm)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "--class rlm rc=0" || ko "--class rlm rc=${rc}"
grep -q "DeepSeek-R1-Distill-Llama-70B-FP16" <<< "${rlm_out}" \
  && ok "rlm filter returns FP16 70B" || ko "missing FP16 70B"
grep -q "DeepSeek-R1-Distill-Llama-70B-Q4_K_M" <<< "${rlm_out}" \
  && ok "rlm filter returns Q4_K_M variant" || ko "missing Q4_K_M"

set +e
code_out="$(python3 "${SCRIPT}" --purpose code --status verified-real)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "--purpose code --status verified-real rc=0" \
  || ko "code filter rc=${rc}"
grep -q "Qwen3-Coder-32B-Instruct" <<< "${code_out}" \
  && ok "code filter returns Qwen3-Coder-32B" || ko "missing Qwen3-Coder"

# --- composing AND filters ---
set +e
budget_out="$(python3 "${SCRIPT}" --max-vram 5)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "--max-vram 5 rc=0" || ko "max-vram rc=${rc}"
# 70B FP16 needs 140 GiB → MUST NOT appear in a 5-GiB budget.
! grep -q "DeepSeek-R1-Distill-Llama-70B-FP16" <<< "${budget_out}" \
  && ok "--max-vram 5 excludes 140-GiB model" \
  || ko "70B FP16 leaked through 5-GiB budget"
# BitNet 2B fits.
grep -q "BitNet-b1.58-2B-4T" <<< "${budget_out}" \
  && ok "--max-vram 5 includes 1.5-GiB BitNet" \
  || ko "BitNet 2B missing from 5-GiB budget"

# --- min-context ---
set +e
ctx_out="$(python3 "${SCRIPT}" --min-context 131072)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "--min-context 131072 rc=0" || ko "min-context rc=${rc}"
grep -q "Phi-4-mini-instruct" <<< "${ctx_out}" \
  && ok "min-context filter includes 128k-context Phi-4-mini" \
  || ko "Phi-4-mini missing despite 131072 context"

# --- LoRA adapter filtering ---
set +e
lora_out="$(python3 "${SCRIPT}" --class lora-adapter)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "--class lora-adapter rc=0" || ko "lora filter rc=${rc}"
grep -q "deepseek-coder-loras-rust-systems" <<< "${lora_out}" \
  && ok "lora filter returns the demonstrator adapter" \
  || ko "lora adapter missing"

# --- zero matches → rc=1 ---
set +e
python3 "${SCRIPT}" --class rlm --tier pulse >/dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "zero-match query → rc=1" \
  || ko "expected rc=1 on impossible query, got ${rc}"

# --- JSON mode ---
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT
set +e
python3 "${SCRIPT}" --purpose reasoning --json > "${WORK}/q.json"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "--json --purpose reasoning rc=0" || ko "json rc=${rc}"
python3 - "${WORK}/q.json" <<'PY' 2>/dev/null \
  && ok "JSON shape correct + every entry has purpose=reasoning" \
  || ko "JSON shape wrong"
import json, sys
d = json.load(open(sys.argv[1]))
assert d['count'] >= 2, d
assert all('purpose' in m for m in d['models']), d
assert all('reasoning' in (m.get('purpose') or []) for m in d['models']), d
PY

# --- osctl bridge ---
set +e
out_osctl="$("${OSCTL}" models query --class slm 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl models query --class slm rc=0" \
  || ko "osctl bridge failed (rc=${rc})"
grep -q "Phi-4-mini-instruct\|Qwen3-1.7B" <<< "${out_osctl}" \
  && ok "osctl bridge surfaces SLM matches" || ko "osctl output wrong"

echo
total=$((pass + fail))
echo "test_catalog_query: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
