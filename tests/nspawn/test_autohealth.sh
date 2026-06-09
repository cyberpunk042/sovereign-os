#!/usr/bin/env bash
# R308 (E2.M14) — autohealth periodic synthesizer L3.
#
# Operator-named (§1b mandate row): "autohealth and doctor ,
# notification and messaging".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/diagnostics/autohealth.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# Each test uses an isolated state file via overlay.
mk_cfg() {
    local state_path="$1"
    local extra="${2:-}"
    local cfg
    cfg=$(mktemp --suffix=.toml)
    cat > "${cfg}" <<TOML
state_path = "${state_path}"
${extra}
TOML
    echo "${cfg}"
}

# ── 1. tick --json envelope ─────────────────────────────────
state=$(mktemp -u)
cfg=$(mk_cfg "${state}")
out="$(python3 "${SCRIPT}" tick --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R308'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E2.M14'
for k in ('tick_at', 'tick_at_epoch', 'verdict', 'rc',
          'severity_counts', 'findings', 'notify_commands'):
    assert k in d, k
" || fail "envelope"
rm -f "${cfg}" "${state}"
pass "1. tick --json envelope"

# ── 2. Findings cover all 5 default axes ───────────────────
state=$(mktemp -u)
cfg=$(mk_cfg "${state}")
out="$(python3 "${SCRIPT}" tick --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
axes = {f['axis'] for f in d['findings']}
want = {'operator-posture', 'thermal-oc-budget', 'storage-health',
        'memory-pressure-damper', 'health-scan'}
assert axes == want, (axes, want)
" || fail "axes"
rm -f "${cfg}" "${state}"
pass "2. findings cover 5 default axes"

# ── 3. Severity classifier: critical/attention/informational ──
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('ah', 'scripts/diagnostics/autohealth.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# Critical mappings.
for v in ('degraded', 'critical', 'over-budget', 'pull-oc-now', 'dampen-fully'):
    assert m.classify_severity(v) == 'critical', v
# Attention mappings. 'attention' is the literal mild verdict R269
# memory-pressure emits; omitting it silently downgraded an attention
# axis to informational (under-report) on a health aggregator.
for v in ('attention', 'watch', 'tight', 'drift', 'headroom-tight',
          'thermal-watch', 'psu-watch', 'both-tight', 'dampen-by-1', 'warn'):
    assert m.classify_severity(v) == 'attention', v
# Informational (ok/safe/etc).
for v in ('ok', 'safe', 'healthy', 'no-dampening', None):
    assert m.classify_severity(v) == 'informational', v
print('PASS')
" || fail "classify"
pass "3. severity classifier maps verdicts → critical/attention/informational"

# ── 3b. health-scan axis (needs_attention, no verdict) maps to attention ──
# Regression: health-scan emits needs_attention+summary, NOT a verdict/status
# string. autohealth previously floored it to "informational" (below the
# attention notify threshold), so a health-scan attention NEVER alerted.
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('ah', 'scripts/diagnostics/autohealth.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# A health-scan-shaped doc WITH needs_attention=True (no verdict/status).
m._run_axis = lambda *a, **k: {
    'needs_attention': True,
    'summary': {'total': 6, 'ok': 5, 'attention': 1, 'informational': 0},
    'probes': [],
}
f = m.collect_findings(['health-scan'])[0]
assert f['severity'] == 'attention', f   # was 'informational' (the bug)
assert f['verdict'] == 'needs-attention', f
assert 'probe(s) need attention' in f['message'], f
# And it must now clear the default notify threshold (attention).
cmds = m.notify_commands([f], dict(m.DEFAULTS), {})
assert any(c['axis'] == 'health-scan' and not c.get('suppressed') for c in cmds), cmds
# needs_attention=False stays informational (benign).
m._run_axis = lambda *a, **k: {'needs_attention': False, 'summary': {}, 'probes': []}
g = m.collect_findings(['health-scan'])[0]
assert g['severity'] == 'informational', g
print('PASS')
" || fail "health-scan needs_attention mapping"
pass "3b. health-scan needs_attention → attention finding (clears notify threshold)"

# ── 4. State JSONL persists across ticks ────────────────────
state=$(mktemp -u)
cfg=$(mk_cfg "${state}")
python3 "${SCRIPT}" tick --config "${cfg}" --json >/dev/null || true
python3 "${SCRIPT}" tick --config "${cfg}" --json >/dev/null || true
python3 "${SCRIPT}" tick --config "${cfg}" --json >/dev/null || true
# State file should have 3 rows.
line_count=$(wc -l < "${state}")
[[ "${line_count}" -eq 3 ]] || fail "expected 3 state rows; got ${line_count}"
rm -f "${cfg}" "${state}"
pass "4. state JSONL persists across ticks (3 ticks → 3 rows)"

# ── 5. history verb returns recent ticks ─────────────────
state=$(mktemp -u)
cfg=$(mk_cfg "${state}")
python3 "${SCRIPT}" tick --config "${cfg}" --json >/dev/null || true
python3 "${SCRIPT}" tick --config "${cfg}" --json >/dev/null || true
out_h="$(python3 "${SCRIPT}" history --config "${cfg}" --json || true)"
echo "${out_h}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R308'
assert d['total_rows'] == 2
assert len(d['rows']) == 2
for r in d['rows']:
    assert r['round'] == 'R308'
" || fail "history shape"
rm -f "${cfg}" "${state}"
pass "5. history verb returns recent ticks from state JSONL"

# ── 6. status verb returns last_tick + suppression keys ────
state=$(mktemp -u)
cfg=$(mk_cfg "${state}")
python3 "${SCRIPT}" tick --config "${cfg}" --json >/dev/null || true
out_s="$(python3 "${SCRIPT}" status --config "${cfg}" --json || true)"
echo "${out_s}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R308'
assert d['tick_count'] == 1
assert d['last_tick'] is not None
assert 'suppression_keys' in d
" || fail "status shape"
rm -f "${cfg}" "${state}"
pass "6. status verb returns last_tick + suppression_keys"

# ── 7. notify_min_severity filters notify commands ──────────
state=$(mktemp -u)
# With min_severity=critical, no attention-level finding fires.
cfg=$(mk_cfg "${state}" 'notify_min_severity = "critical"')
out="$(python3 "${SCRIPT}" tick --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# All emitted commands have severity == 'critical' (or none if env has none).
for n in d['notify_commands']:
    assert n['severity'] == 'critical', n
" || fail "notify min severity filter"
rm -f "${cfg}" "${state}"
pass "7. notify_min_severity filters notify commands (critical-only)"

# ── 8. Suppression window prevents duplicate notify within tick ──
state=$(mktemp -u)
# Suppression window = 9999s; second tick of same finding should suppress.
cfg=$(mk_cfg "${state}" 'notify_suppress_seconds = 9999
notify_min_severity = "attention"')
out1="$(python3 "${SCRIPT}" tick --config "${cfg}" --json || true)"
out2="$(python3 "${SCRIPT}" tick --config "${cfg}" --json || true)"
# Second tick: every attention finding that previously emitted should
# be suppressed.
echo "${out2}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# At least one notify_command must show suppressed=True since the
# first tick recorded it.
any_supp = any(n.get('suppressed') for n in d['notify_commands'])
assert any_supp, d['notify_commands']
" || fail "suppression"
rm -f "${cfg}" "${state}"
pass "8. notify_suppress_seconds prevents duplicate notify within window"

# ── 9. Operator overlay (R283/SDD-030) controls config ────
state=$(mktemp -u)
cfg=$(mk_cfg "${state}" 'notify_suppress_seconds = 7200
notify_min_severity = "critical"
axes = ["thermal-oc-budget"]')
out="$(python3 "${SCRIPT}" tick --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['config']
assert c['notify_suppress_seconds'] == 7200, c
assert c['notify_min_severity'] == 'critical', c
assert c['axes'] == ['thermal-oc-budget'], c
# Only 1 finding (thermal-oc-budget) since axes overlay narrowed list.
assert len(d['findings']) == 1, d['findings']
" || fail "overlay"
rm -f "${cfg}" "${state}"
pass "9. operator overlay controls suppression / severity / axes"

# ── 10. sovereign-osctl autohealth dispatch ────────────────
state=$(mktemp -u)
cfg=$(mk_cfg "${state}")
out_disp="$(bash "${OSCTL}" autohealth tick --config "${cfg}" --json 2>/dev/null || true)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R308'
" || fail "sovereign-osctl dispatch"
rm -f "${cfg}" "${state}"
pass "10. sovereign-osctl autohealth dispatches"

echo "ALL OK"
