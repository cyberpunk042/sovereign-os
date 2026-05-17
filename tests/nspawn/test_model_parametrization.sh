#!/usr/bin/env bash
# R311 (E5.M7 closure) — LLM-runtime parametrization advisor L3.
#
# Operator-named (§1b mandate row): "Model variants + quantizations +
# advanced features parametrization".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/models/parametrization.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. list --json envelope + ≥10 parameters ─────────────
out="$(python3 "${SCRIPT}" list --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R311'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E5.M7'
assert d['total_count'] >= 10
" || fail "envelope"
pass "1. list --json envelope + ≥10 parameters"

# ── 2. Operator-named anchor parameters present ────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = {p['name'] for p in d['parameters']}
must = {'context_size', 'n_gpu_layers', 'cache_type_k', 'cache_type_v',
        'batch_size', 'parallel', 'mlock', 'mmap', 'flash_attn',
        'temperature', 'top_p'}
missing = must - names
assert not missing, missing
" || fail "anchors"
pass "2. operator-named anchors present (context/n_gpu_layers/cache/batch/parallel/mlock/mmap/flash_attn)"

# ── 3. Every parameter has full schema ──────────────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for p in d['parameters']:
    for k in ('name', 'axis', 'type', 'default', 'rationale',
              'tradeoff_low', 'tradeoff_high', 'recommend_per_vram_gib'):
        assert k in p, (k, p['name'])
    # recommend_per_vram_gib must have all 4 buckets
    rec = p['recommend_per_vram_gib']
    for b in ('<16', '16-24', '24-48', '>48'):
        assert b in rec, (b, p['name'])
" || fail "schema"
pass "3. every parameter carries full schema (8 fields + 4-bucket VRAM map)"

# ── 4. --axis filter narrows ──────────────────────────────
out_kv="$(python3 "${SCRIPT}" list --axis kv-cache --json)"
echo "${out_kv}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert all(p['axis'] == 'kv-cache' for p in d['parameters'])
assert d['filtered_count'] == 2  # cache_type_k + cache_type_v
" || fail "axis filter"
pass "4. --axis kv-cache filter narrows (cache_type_k + cache_type_v)"

# ── 5. recommend differs by VRAM bucket ──────────────────
out_low="$(python3 "${SCRIPT}" recommend --vram-gib 8 --json)"
out_high="$(python3 "${SCRIPT}" recommend --vram-gib 96 --json)"
python3 -c "
import json
low = json.loads('''${out_low}''')
high = json.loads('''${out_high}''')
ctx_low = next(r['recommended'] for r in low['recommendations'] if r['name'] == 'context_size')
ctx_high = next(r['recommended'] for r in high['recommendations'] if r['name'] == 'context_size')
assert ctx_low < ctx_high, (ctx_low, ctx_high)
# Low-VRAM recommends cache_type_k=q4_0; high-VRAM recommends f16.
k_low = next(r['recommended'] for r in low['recommendations'] if r['name'] == 'cache_type_k')
k_high = next(r['recommended'] for r in high['recommendations'] if r['name'] == 'cache_type_k')
assert k_low == 'q4_0', k_low
assert k_high == 'f16', k_high
" || fail "vram bucket differentiation"
pass "5. recommend differentiates by VRAM bucket (context_size 8GiB < 96GiB; cache_type_k q4_0 vs f16)"

# ── 6. vram_bucket function maps boundaries correctly ─────
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('p', 'scripts/models/parametrization.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert m.vram_bucket(8.0) == '<16'
assert m.vram_bucket(16.0) == '16-24'
assert m.vram_bucket(23.9) == '16-24'
assert m.vram_bucket(24.0) == '24-48'
assert m.vram_bucket(47.9) == '24-48'
assert m.vram_bucket(48.0) == '>48'
assert m.vram_bucket(96.0) == '>48'
assert m.vram_bucket(None) == '16-24'  # safe default
print('PASS')
" || fail "vram_bucket"
pass "6. vram_bucket() maps 8/16/24/48 GiB boundaries correctly"

# ── 7. show <param> renders detail ────────────────────────
out_s="$(python3 "${SCRIPT}" show n_gpu_layers --vram-gib 48 --json)"
echo "${out_s}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
p = d['parameter']
assert p['name'] == 'n_gpu_layers'
assert d['vram_bucket'] == '>48'
assert d['recommended_value'] == -1
" || fail "show shape"
pass "7. show n_gpu_layers --vram-gib 48 → recommended=-1 (bucket >48)"

# ── 8. Unknown parameter → rc=1 + structured error ────────
RC=0
python3 "${SCRIPT}" show no-such-param --json 2>/dev/null || RC=$?
[[ "${RC}" == "1" ]] || fail "show unknown rc expected 1; got ${RC}"
pass "8. show unknown parameter → rc=1 + structured error"

# ── 9. Operator pin overrides recommendation ──────────────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
[recommendation_pin]
context_size = 65536
parallel = 16
TOML

out_ov="$(python3 "${SCRIPT}" recommend --vram-gib 48 --config "${overlay}" --json)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ctx = next(r for r in d['recommendations'] if r['name'] == 'context_size')
assert ctx['recommended'] == 65536, ctx
assert ctx['operator_pinned'] is True
par = next(r for r in d['recommendations'] if r['name'] == 'parallel')
assert par['recommended'] == 16
assert par['operator_pinned'] is True
# Unpinned parameter still uses VRAM bucket.
ng = next(r for r in d['recommendations'] if r['name'] == 'n_gpu_layers')
assert ng['operator_pinned'] is False
" || fail "operator pin"
rm -f "${overlay}"
pass "9. operator pin overrides recommendation (preserves operator_pinned flag)"

# ── 10. sovereign-osctl model-params dispatch ──────────────
out_disp="$(bash "${OSCTL}" model-params recommend --json 2>/dev/null)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R311'
" || fail "sovereign-osctl dispatch"
pass "10. sovereign-osctl model-params dispatches"

echo "ALL OK"
