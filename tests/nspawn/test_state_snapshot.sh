#!/usr/bin/env bash
# R322 (E2.M18) — unified state snapshot L3.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/diagnostics/state-snapshot.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. audit --json envelope + ≥15 probes ─────────────────
out_a="$(python3 "${SCRIPT}" audit --json)"
echo "${out_a}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R322'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E2.M18'
assert d['probe_count'] >= 15
" || fail "audit envelope"
pass "1. audit --json envelope + ≥15 probes catalogued"

# ── 2. Every probe has full schema ─────────────────────────
echo "${out_a}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for p in d['probes']:
    for k in ('name', 'axis', 'script', 'args'):
        assert k in p, (k, p)
    assert isinstance(p['args'], list)
" || fail "probe schema"
pass "2. every probe carries (name, axis, script, args) schema"

# ── 3. Probe catalog covers all operator-named axes ────────
echo "${out_a}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
axes = {p['axis'] for p in d['probes']}
must = {'hardware', 'power', 'thermal', 'memory', 'posture',
        'storage', 'diagnostics', 'lifecycle', 'kernel',
        'hardening', 'network', 'install', 'model'}
missing = must - axes
assert not missing, missing
" || fail "axis coverage"
pass "3. probe catalog covers 13 operator-named axes"

# ── 4. snapshot --json envelope ────────────────────────────
out_s="$(python3 "${SCRIPT}" snapshot --json)"
echo "${out_s}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R322'
for k in ('snapshot_at', 'snapshot_at_epoch', 'snapshot_duration_ms',
          'max_workers', 'per_probe_timeout_sec', 'probe_count',
          'available_count', 'failed_count', 'probes'):
    assert k in d, k
" || fail "snapshot envelope"
pass "4. snapshot --json envelope"

# ── 5. Per-probe result has full shape ────────────────────
echo "${out_s}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for p in d['probes']:
    for k in ('name', 'axis', 'script', 'rc', 'duration_ms',
              'available', 'output'):
        assert k in p, (k, p)
" || fail "probe result shape"
pass "5. per-probe result carries (rc, duration_ms, available, output)"

# ── 6. Snapshot runs in parallel (faster than serial) ─────
echo "${out_s}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# Sum of per-probe durations should be substantially more than
# the wall-clock duration when parallelism actually engaged.
sum_durations = sum(p['duration_ms'] for p in d['probes'])
wall = d['snapshot_duration_ms']
# With max_workers=8 + 19 probes, wall should be < 50% of sum.
# (Loose threshold to allow CI variance.)
assert wall * 2 < sum_durations, (wall, sum_durations)
" || fail "parallel"
pass "6. snapshot runs probes in parallel (wall clock << sum of durations)"

# ── 7. Stable probe order regardless of completion order ──
f1=$(mktemp); f2=$(mktemp)
python3 "${SCRIPT}" snapshot --json > "${f1}"
python3 "${SCRIPT}" snapshot --json > "${f2}"
python3 -c "
import json
d1 = json.load(open('${f1}'))
d2 = json.load(open('${f2}'))
n1 = [p['name'] for p in d1['probes']]
n2 = [p['name'] for p in d2['probes']]
assert n1 == n2, (n1, n2)
" || fail "stable order"
rm -f "${f1}" "${f2}"
pass "7. snapshot probe order is stable across runs"

# ── 8. Operator overlay sets max_workers + timeout ────────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
max_workers = 2
per_probe_timeout_sec = 5
TOML

out_ov="$(python3 "${SCRIPT}" snapshot --config "${overlay}" --json)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['max_workers'] == 2
assert d['per_probe_timeout_sec'] == 5
" || fail "overlay knobs"
rm -f "${overlay}"
pass "8. operator overlay (R283/SDD-030) sets max_workers + per_probe_timeout_sec"

# ── 9. Operator can append custom probe via overlay ────────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
[[probes]]
name   = "test-custom-probe"
axis   = "test"
script = "scripts/hardware/inventory-catalog.py"
args   = ["audit", "--json"]
TOML

out_cust="$(python3 "${SCRIPT}" audit --config "${overlay}" --json)"
echo "${out_cust}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = [p['name'] for p in d['probes']]
# Overlay REPLACES the probes list per R283 list-replace.
assert names == ['test-custom-probe'], names
" || fail "custom probe"
rm -f "${overlay}"
pass "9. operator overlay replaces probe catalog (list-replace per R283)"

# ── 10. sovereign-osctl snapshot dispatch ─────────────────
out_disp="$(bash "${OSCTL}" snapshot audit --json 2>/dev/null)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R322'
" || fail "osctl dispatch"
pass "10. sovereign-osctl snapshot dispatches"

echo "ALL OK"
