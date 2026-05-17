#!/usr/bin/env bash
# tests/nspawn/test_models_eval.sh — R232 (SDD-026 Z-2 expansion):
# model eval planner + DRY-RUN dispatcher + JSONL history. SEED round.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/models/eval.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_models_eval.sh"
echo

[ -x "${SCRIPT}" ] && ok "eval.py executable" \
  || { ko "missing eval.py"; exit 1; }
grep -q "R232" "${SCRIPT}" && ok "eval.py cites R232" || ko "R232 ref missing"
grep -q "models eval" "${OSCTL}" \
  && ok "osctl help documents 'models eval'" || ko "osctl help missing"
grep -q "    eval)" "${OSCTL}" \
  && ok "osctl dispatches 'eval'" || ko "osctl dispatch missing"

TMP="$(mktemp -d -t r232.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
export SOVEREIGN_OS_MODELS_EVAL_STATE="${TMP}/evals.jsonl"

# ---- list-benchmarks: 6 entries minimum ----
out="$(python3 "${SCRIPT}" list-benchmarks --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R232', d
b = d['benchmarks']
for k in ('mmlu','humaneval','gsm8k','arc-challenge','truthfulqa','mteb-retrieval'):
    assert k in b, f'missing benchmark {k}'
    e = b[k]
    for f in ('name','harness','harness_args','measures','applicable_classes','cost_estimate_minutes'):
        assert f in e, f'benchmark {k} missing {f}'
" \
  && ok "list-benchmarks: 6 named benchmarks + required fields" \
  || ko "list-benchmarks shape wrong"

# ---- plan: known slug + applicable benchmark ----
out="$(python3 "${SCRIPT}" plan BitNet-b1.58-2B-4T --benchmark mmlu --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['model']['id']=='BitNet-b1.58-2B-4T', d
assert d['benchmark']['key']=='mmlu', d
assert d['command'][0]=='lm-eval', d
assert '--tasks' in d['command'] and 'mmlu' in d['command'], d
assert d['command_str'].startswith('lm-eval ')
assert isinstance(d['harness_present'], bool)
assert 'sovereign-osctl models eval run' in d['next_step']
" \
  && ok "plan emits well-formed lm-eval invocation + next-step" \
  || ko "plan shape wrong: ${out}"

# ---- plan: benchmark not applicable to model class → rc=2 ----
set +e
out_bad="$(python3 "${SCRIPT}" plan BitNet-b1.58-2B-4T --benchmark mteb-retrieval --json 2>&1)"
rc_bad=$?
set -e
[ "${rc_bad}" -eq 2 ] && ok "plan with non-applicable benchmark → rc=2" \
  || ko "expected rc=2, got ${rc_bad}: ${out_bad}"
echo "${out_bad}" | grep -q "not applicable" \
  && ok "non-applicable error cites the mismatch" \
  || ko "non-applicable error msg wrong"

# ---- plan: unknown slug → rc=2 ----
set +e
out_bad="$(python3 "${SCRIPT}" plan never-existed --benchmark mmlu 2>&1)"
rc_bad=$?
set -e
[ "${rc_bad}" -eq 2 ] && ok "plan with unknown slug → rc=2" \
  || ko "expected rc=2 on bad slug, got ${rc_bad}"

# ---- plan: unknown benchmark → rc=2 ----
set +e
out_bad="$(python3 "${SCRIPT}" plan BitNet-b1.58-2B-4T --benchmark nope 2>&1)"
rc_bad=$?
set -e
[ "${rc_bad}" -eq 2 ] && ok "plan with unknown benchmark → rc=2" \
  || ko "expected rc=2 on bad benchmark, got ${rc_bad}"

# ---- run --dry-run: records intent without executing ----
out="$(python3 "${SCRIPT}" run BitNet-b1.58-2B-4T --benchmark mmlu --dry-run --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['outcome']=='dry-run', d
assert d['rc']==0, d
assert d['dry_run'] is True, d
assert d['model_id']=='BitNet-b1.58-2B-4T', d
assert d['benchmark']=='mmlu', d
assert d['command'][0]=='lm-eval', d
" \
  && ok "run --dry-run records intent with outcome=dry-run rc=0" \
  || ko "dry-run record shape wrong"

# Verify state file was appended.
[ -f "${SOVEREIGN_OS_MODELS_EVAL_STATE}" ] \
  && ok "dry-run wrote state JSONL" \
  || ko "state file missing"
[ "$(wc -l < "${SOVEREIGN_OS_MODELS_EVAL_STATE}")" -eq 1 ] \
  && ok "state file has exactly 1 row after 1 dry-run" \
  || ko "unexpected row count"

# ---- run a second dry-run with a different benchmark ----
python3 "${SCRIPT}" run BitNet-b1.58-2B-4T --benchmark gsm8k --dry-run > /dev/null
[ "$(wc -l < "${SOVEREIGN_OS_MODELS_EVAL_STATE}")" -eq 2 ] \
  && ok "second dry-run appended (state file has 2 rows)" \
  || ko "state file did not grow"

# ---- history: lists both rows ----
out="$(python3 "${SCRIPT}" history --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R232', d
assert d['count']==2, d
benches = sorted(r['benchmark'] for r in d['rows'])
assert benches == ['gsm8k', 'mmlu'], benches
" \
  && ok "history --json lists 2 rows" \
  || ko "history shape wrong"

# ---- history --slug filter ----
out="$(python3 "${SCRIPT}" history --slug BitNet-b1.58-2B-4T --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['count']==2, d
" \
  && ok "history --slug filter matches model rows" \
  || ko "history --slug filter wrong"

# ---- history --benchmark filter ----
out="$(python3 "${SCRIPT}" history --benchmark mmlu --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['count']==1, d
assert d['rows'][0]['benchmark']=='mmlu', d
" \
  && ok "history --benchmark filter matches one row" \
  || ko "history --benchmark filter wrong"

# ---- history --limit ----
out="$(python3 "${SCRIPT}" history --limit 1 --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['count']==1, d
" \
  && ok "history --limit caps the rows" \
  || ko "history --limit wrong"

# ---- osctl bridge ----
set +e
"${OSCTL}" models eval list-benchmarks --json > "${TMP}/osctl.out" 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl models eval list-benchmarks rc=0" \
  || ko "osctl bridge rc=${rc}: $(cat "${TMP}/osctl.out")"
python3 -c "
import json
d=json.load(open('${TMP}/osctl.out'))
assert d['round']=='R232', d
" \
  && ok "osctl bridge surfaces R232 JSON" \
  || ko "osctl JSON wrong"

# ---- human render: plan banner ----
out="$(python3 "${SCRIPT}" plan BitNet-b1.58-2B-4T --benchmark mmlu)"
echo "${out}" | grep -q "R232 sovereign-os models eval plan" \
  && ok "plan human banner shipped" || ko "no plan banner"
echo "${out}" | grep -q "lm-eval --model hf" \
  && ok "plan human render shows full command" || ko "plan command missing"

echo
total=$((pass + fail))
echo "test_models_eval: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
