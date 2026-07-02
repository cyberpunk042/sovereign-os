#!/usr/bin/env bash
# R350 (E5.M17) — model-adapt task→(recipe, GPU) recommender L3.
# Third consumer of SDD-032 §4 inventory_consult helper (after R315, R252).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ADAPT="${REPO_ROOT}/scripts/models/adapt.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. tasks verb lists operator-meaningful task names ───────────────
out="$(python3 "${ADAPT}" tasks --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for must in ('chat', 'code', 'reasoning', 'agent', 'tool-use',
             'long-context', 'alignment'):
    assert must in d['tasks'], f'missing task: {must}'
assert d['task_count'] >= 10
" || fail "tasks list"
pass "1. tasks verb enumerates ≥10 operator-meaningful task names"

# ── 2. recipes verb lists ≥5 declared adaptation recipes ─────────────
out="$(python3 "${ADAPT}" recipes --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['recipe_count'] >= 5
for r in d['recipes']:
    for k in ('recipe_id','base_class','method','min_vram_gib',
             'finetune_vram_gib','target_tasks','cost_estimate','rationale'):
        assert k in r, (k, r)
" || fail "recipes schema"
pass "2. recipes verb returns ≥5 with full schema (id+base+method+VRAM+tasks+cost+why)"

# ── 3. recommend reasoning → 32B recipe on PRO 6000 ─────────────────
out="$(python3 "${ADAPT}" recommend reasoning --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
rec = d['recommendation']
assert rec is not None, 'no recommendation'
assert rec['fits_on_gpu_index'] == 1  # PRO 6000
assert 'PRO 6000' in rec['fits_on_gpu_model']
assert rec['finetune_vram_gib'] > 24  # won't fit on 4090
" || fail "reasoning"
pass "3. recommend reasoning → recipe fits ONLY on PRO 6000 (>24 GiB FT VRAM)"

# ── 4. recommend code --target-gpu 0 → 4090-fitting recipe ──────────
out="$(python3 "${ADAPT}" recommend code --target-gpu 0 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
rec = d['recommendation']
assert rec is not None
assert rec['fits_on_gpu_index'] == 0  # 4090
assert rec['finetune_vram_gib'] <= 24
assert rec['fits_headroom_gib'] >= 0
" || fail "code 4090"
pass "4. recommend code --target-gpu 0 → recipe fits the 4090 (FT ≤24 GiB)"

# ── 5. recommend unknown task → rc=1 + reason explains ──────────────
rc=0
out="$(python3 "${ADAPT}" recommend no-such-task-xyz --json 2>&1)" || rc=$?
[[ "${rc}" == 1 ]] || fail "unknown rc=${rc}"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['recommendation'] is None
assert 'no recipe' in d['reason'].lower() or 'unknown' in d['reason'].lower()
" || fail "unknown shape"
pass "5. recommend unknown task → rc=1 + reason naming the task"

# ── 6. show <recipe> returns recipe details ─────────────────────────
out="$(python3 "${ADAPT}" show qlora-32b-reasoning --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
r = d['recipe']
assert r['recipe_id'] == 'qlora-32b-reasoning'
assert r['method'] == 'qlora-trl'
assert 'reasoning' in r['target_tasks']
" || fail "show"
pass "6. show qlora-32b-reasoning → returns full recipe schema"

# ── 7. show unknown recipe → rc=1 + structured error ────────────────
rc=0
err="$(python3 "${ADAPT}" show no-such-recipe --json 2>&1 1>/dev/null)" || rc=$?
[[ "${rc}" == 1 ]] || fail "unknown rc=${rc}"
echo "${err}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'error' in d and 'known' in d
assert len(d['known']) >= 5
" || fail "unknown recipe shape"
pass "7. show unknown recipe → rc=1 + structured {error, known: [...]}"

# ── 8. downstream_verbs hand off to R244 fine-tune + R232 eval ──────
out="$(python3 "${ADAPT}" recommend agent --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
verbs = d['downstream_verbs']
joined = ' '.join(verbs)
assert 'fine-tune plan' in joined
assert 'eval plan' in joined
" || fail "downstream"
pass "8. downstream_verbs hand off to fine-tune plan + eval plan (composition)"

# ── 9. operator-overlay can replace recipes/gpus (R283/SDD-030) ─────
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
[[gpus]]
index = 0
model = "Imaginary 5090 Ti Super"
vram_gib = 32
role_hint = "test-only"
TOML
out="$(python3 "${ADAPT}" recipes --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# Overlay replaces declared_gpus list (lists-replace per SDD-030)
g = d['declared_gpus']
assert len(g) == 1
assert g[0]['model'] == 'Imaginary 5090 Ti Super'
" || fail "overlay"
rm -f "${cfg}"
pass "9. operator-overlay replaces declared_gpus list (R283/SDD-030 lists-replace)"

# ── 10. sovereign-osctl model-adapt dispatches all 4 subverbs ───────
"${OSCTL}" model-adapt tasks --json >/dev/null 2>&1 || fail "osctl tasks"
"${OSCTL}" model-adapt recipes --json >/dev/null 2>&1 || fail "osctl recipes"
"${OSCTL}" model-adapt recommend chat --json >/dev/null 2>&1 || fail "osctl recommend"
"${OSCTL}" model-adapt show sft-3b-edge --json >/dev/null 2>&1 || fail "osctl show"
pass "10. sovereign-osctl model-adapt dispatches tasks/recipes/recommend/show"

# ── 11. inventory_consult helper integration — 3rd consumer ─────────
out="$(python3 "${ADAPT}" recipes --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# gpu_caveats key present (may be empty list — depends on catalog state)
assert 'gpu_caveats' in d
assert isinstance(d['gpu_caveats'], list)
" || fail "helper integration"
pass "11. gpu_caveats field present (3rd consumer of SDD-032 §4 helper)"

echo "ALL OK"
