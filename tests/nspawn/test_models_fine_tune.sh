#!/usr/bin/env bash
# tests/nspawn/test_models_fine_tune.sh — R244 (SDD-026 Z-2 fine-tune).
# LoRA / QLoRA / SFT / DPO planner + DRY-RUN dispatcher + history.

set -euo pipefail
PYTHON3="${PYTHON3:-python3}"
if ! "${PYTHON3}" -c "import yaml" >/dev/null 2>&1; then
  if /usr/bin/python3 -c "import yaml" >/dev/null 2>&1; then
    PYTHON3=/usr/bin/python3
  fi
fi


__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/models/fine_tune.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"
TOOLCHAINS="${__REPO_ROOT}/scripts/models/toolchains.py"

echo "tests/nspawn/test_models_fine_tune.sh"
echo

[ -x "${SCRIPT}" ] && ok "fine_tune.py executable" \
  || { ko "missing fine_tune.py"; exit 1; }
grep -q "R244" "${SCRIPT}" && ok "fine_tune.py cites R244" || ko "R244 missing"
grep -q "models fine-tune" "${OSCTL}" \
  && ok "osctl help documents 'fine-tune'" || ko "osctl help missing"
grep -q "    fine-tune)" "${OSCTL}" \
  && ok "osctl dispatches 'fine-tune'" || ko "osctl dispatch missing"

TMP="$(mktemp -d -t r244.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
export SOVEREIGN_OS_FINE_TUNE_STATE="${TMP}/ft.jsonl"

# ---- list-methods: 4 methods ----
out="$("${PYTHON3}" "${SCRIPT}" list-methods --json)"
echo "${out}" | "${PYTHON3}" -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R244', d
m=d['methods']
for k in ('lora-unsloth','qlora-trl','sft-trl','dpo-trl'):
    assert k in m, f'missing method {k}'
    e=m[k]
    for f in ('name','harness','method_kind','harness_args_template',
             'applicable_base_classes','operator_role',
             'cost_estimate_hours','vram_gib_required_min'):
        assert f in e, f'{k} missing {f}'
" \
  && ok "list-methods: 4 methods with required fields" \
  || ko "list-methods shape wrong"

# ---- plan with applicable base + method ----
out="$("${PYTHON3}" "${SCRIPT}" plan Phi-4-mini-instruct --method lora-unsloth --dataset op/ds --json)"
echo "${out}" | "${PYTHON3}" -c "
import json,sys
d=json.load(sys.stdin)
assert d['base']['id']=='Phi-4-mini-instruct', d
assert d['method']['key']=='lora-unsloth', d
assert d['dataset']=='op/ds', d
assert d['command'][0]=='unsloth', d
# Template variables resolved.
cstr=d['command_str']
assert 'microsoft/Phi-4-mini-instruct' in cstr, cstr
assert 'op/ds' in cstr, cstr
assert d['next_step'].startswith('sovereign-osctl models fine-tune run'), d
" \
  && ok "plan emits resolved harness command" \
  || ko "plan shape wrong"

# ---- plan with non-applicable base class → rc=2 ----
# BitNet is class=ternary-lm; lora-unsloth applies to llm/slm/code only.
set +e
out_bad="$("${PYTHON3}" "${SCRIPT}" plan BitNet-b1.58-2B-4T --method lora-unsloth --dataset op/ds 2>&1)"
rc_bad=$?
set -e
[ "${rc_bad}" -eq 2 ] && ok "plan with non-applicable base class → rc=2" \
  || ko "expected rc=2, got ${rc_bad}: ${out_bad}"
echo "${out_bad}" | grep -q "not applicable" \
  && ok "non-applicable error cites mismatch" || ko "no hint"

# ---- plan with unknown base → rc=2 ----
set +e
"${PYTHON3}" "${SCRIPT}" plan never-existed --method lora-unsloth --dataset op/ds > /dev/null 2>&1
rc_bad=$?
set -e
[ "${rc_bad}" -eq 2 ] && ok "plan with unknown base → rc=2" \
  || ko "expected rc=2, got ${rc_bad}"

# ---- plan with unknown method → rc=2 ----
set +e
"${PYTHON3}" "${SCRIPT}" plan Phi-4-mini-instruct --method nope --dataset op/ds > /dev/null 2>&1
rc_bad=$?
set -e
[ "${rc_bad}" -eq 2 ] && ok "plan with unknown method → rc=2" \
  || ko "expected rc=2, got ${rc_bad}"

# ---- run --dry-run: records intent without exec ----
out="$("${PYTHON3}" "${SCRIPT}" run Phi-4-mini-instruct --method lora-unsloth --dataset op/ds --dry-run --json)"
echo "${out}" | "${PYTHON3}" -c "
import json,sys
d=json.load(sys.stdin)
assert d['outcome']=='dry-run', d
assert d['dry_run'] is True, d
assert d['base_id']=='Phi-4-mini-instruct', d
assert d['method']=='lora-unsloth', d
assert d['command'][0]=='unsloth', d
" \
  && ok "run --dry-run records intent with outcome=dry-run" \
  || ko "dry-run shape wrong"

# State file appended.
[ -f "${SOVEREIGN_OS_FINE_TUNE_STATE}" ] \
  && [ "$(wc -l < "${SOVEREIGN_OS_FINE_TUNE_STATE}")" -eq 1 ] \
  && ok "dry-run appended 1 line to JSONL state" \
  || ko "state file wrong"

# ---- second dry-run different method appends ----
# sft-trl applies to llm/slm — Phi-4-mini is class=slm.
"${PYTHON3}" "${SCRIPT}" run Phi-4-mini-instruct --method sft-trl --dataset op/ds --dry-run > /dev/null
[ "$(wc -l < "${SOVEREIGN_OS_FINE_TUNE_STATE}")" -eq 2 ] \
  && ok "second dry-run appends to state (2 lines now)" \
  || ko "state file did not grow"

# ---- history --json: 2 rows ----
out="$("${PYTHON3}" "${SCRIPT}" history --json)"
echo "${out}" | "${PYTHON3}" -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R244', d
assert d['count']==2, d
methods=sorted(r['method'] for r in d['rows'])
assert methods==['lora-unsloth','sft-trl'], methods
" \
  && ok "history --json lists 2 rows" \
  || ko "history shape wrong"

# ---- history --method filter ----
out="$("${PYTHON3}" "${SCRIPT}" history --method lora-unsloth --json)"
echo "${out}" | "${PYTHON3}" -c "
import json,sys
d=json.load(sys.stdin)
assert d['count']==1, d
assert d['rows'][0]['method']=='lora-unsloth', d
" \
  && ok "history --method filters to one row" \
  || ko "history --method wrong"

# ---- history --base filter ----
out="$("${PYTHON3}" "${SCRIPT}" history --base Phi-4-mini-instruct --json)"
echo "${out}" | "${PYTHON3}" -c "
import json,sys
d=json.load(sys.stdin)
assert d['count']==2, d
" \
  && ok "history --base filter matches" \
  || ko "history --base wrong"

# ---- toolchains catalog also lists lm-link (R244 expansion) ----
out="$(python3 "${TOOLCHAINS}" list --json)"
echo "${out}" | "${PYTHON3}" -c "
import json,sys
d=json.load(sys.stdin)
names={t['name'] for t in d['toolchains']}
assert 'lm-link' in names, f'lm-link missing: {names}'
" \
  && ok "toolchains catalog now includes lm-link" \
  || ko "lm-link missing"

# ---- osctl bridge ----
set +e
"${OSCTL}" models fine-tune list-methods --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl models fine-tune list-methods rc=0" \
  || ko "osctl bridge rc=${rc}"
"${PYTHON3}" -c "
import json
d=json.load(open('${TMP}/osctl.out'))
assert d['round']=='R244', d
" \
  && ok "osctl bridge surfaces R244 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" models fine-tune nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown fine-tune subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

echo
total=$((pass + fail))
echo "test_models_fine_tune: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
