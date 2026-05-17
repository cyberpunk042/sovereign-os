#!/usr/bin/env bash
# R327 (E9.M11) — apply-audit log + helper module L3.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/diagnostics/apply-audit.py"
HEAT_SCRIPT="${REPO_ROOT}/scripts/hardware/heat-oc-autothrottle.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. Helper module record_apply() round-trips a row ─────
state=$(mktemp -u)
python3 -c "
import sys, json, os, pathlib
sys.path.insert(0, '${REPO_ROOT}/scripts/lib')
import apply_audit

os.environ['SOVEREIGN_OS_APPLY_AUDIT_PATH'] = '${state}'

row = apply_audit.record_apply(
    verb='test-verb-1',
    round_origin='R327',
    gates_satisfied=True,
    gates_detail={'--apply': True, '--confirm-test': True,
                  'SOVEREIGN_OS_CONFIRM_DESTROY=YES': True},
    what_was_written={'key': 'value'},
    target_path='/tmp/whatever',
    wrote=True,
    rc=0,
)
assert row['_audit_log_wrote'] is True
assert row['verb'] == 'test-verb-1'
assert row['gates_satisfied'] is True

# Read back via query()
rows = apply_audit.query(audit_path_override='${state}')
assert len(rows) == 1
assert rows[0]['verb'] == 'test-verb-1'
print('PASS')
" || fail "round-trip"
rm -f "${state}"
pass "1. helper record_apply() round-trips a row through query()"

# ── 2. record_apply() never raises on audit-write failure ──
python3 -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/scripts/lib')
import apply_audit

# Path that's not writable (/dev/null parent isn't a real dir for mkdir)
row = apply_audit.record_apply(
    verb='test-verb-2',
    round_origin='R327',
    gates_satisfied=False,
    gates_detail={},
    audit_path_override='/dev/null/cannot-create/here.jsonl',
)
# Returns the row even on failure.
assert row['_audit_log_wrote'] is False
assert '_audit_log_error' in row
print('PASS')
" || fail "no-raise"
pass "2. record_apply() never raises on audit-write failure (audit failure ≠ apply failure)"

# ── 3. query() filters by verb ─────────────────────────────
state=$(mktemp -u)
SOVEREIGN_OS_APPLY_AUDIT_PATH="${state}" python3 -c "
import sys, os
sys.path.insert(0, '${REPO_ROOT}/scripts/lib')
import apply_audit
for v, ok in [('v1', True), ('v2', False), ('v1', True), ('v3', True)]:
    apply_audit.record_apply(verb=v, round_origin='R0',
                             gates_satisfied=ok, gates_detail={}, wrote=ok)
rows = apply_audit.query(audit_path_override='${state}', verb='v1')
assert len(rows) == 2, rows
assert all(r['verb'] == 'v1' for r in rows)
print('PASS')
"
rm -f "${state}"
pass "3. query(verb=v1) filters to v1-only rows"

# ── 4. query() wrote_only filters out dry-run rows ─────────
state=$(mktemp -u)
python3 -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/scripts/lib')
import apply_audit
apply_audit.record_apply(verb='v1', round_origin='R0',
                         gates_satisfied=True, gates_detail={},
                         wrote=True, audit_path_override='${state}')
apply_audit.record_apply(verb='v2', round_origin='R0',
                         gates_satisfied=False, gates_detail={},
                         wrote=False, audit_path_override='${state}')
rows = apply_audit.query(audit_path_override='${state}', wrote_only=True)
assert len(rows) == 1
assert rows[0]['verb'] == 'v1'
print('PASS')
"
rm -f "${state}"
pass "4. query(wrote_only=True) filters out dry-run rows"

# ── 5. CLI list --json envelope ────────────────────────────
state=$(mktemp -u)
python3 -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/scripts/lib')
import apply_audit
apply_audit.record_apply(verb='cli-test', round_origin='R0',
                         gates_satisfied=True, gates_detail={},
                         audit_path_override='${state}')
"
out="$(SOVEREIGN_OS_APPLY_AUDIT_PATH=${state} python3 "${SCRIPT}" list --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R327'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E9.M11'
assert d['row_count'] >= 1
" || fail "CLI envelope"
rm -f "${state}"
pass "5. CLI list --json envelope (round/schema/sdd_vector/row_count)"

# ── 6. CLI tail --n returns at most N rows ─────────────────
state=$(mktemp -u)
python3 -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/scripts/lib')
import apply_audit
for i in range(10):
    apply_audit.record_apply(verb=f'v{i}', round_origin='R0',
                             gates_satisfied=True, gates_detail={},
                             audit_path_override='${state}')
"
out="$(SOVEREIGN_OS_APPLY_AUDIT_PATH=${state} python3 "${SCRIPT}" tail --n 3 --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['row_count'] == 3
" || fail "tail count"
rm -f "${state}"
pass "6. CLI tail --n 3 returns last 3 rows"

# ── 7. CLI audit returns rollup ───────────────────────────
state=$(mktemp -u)
python3 -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/scripts/lib')
import apply_audit
apply_audit.record_apply(verb='v1', round_origin='R0', gates_satisfied=True,
                         gates_detail={}, wrote=True,
                         audit_path_override='${state}')
apply_audit.record_apply(verb='v1', round_origin='R0', gates_satisfied=False,
                         gates_detail={}, wrote=False,
                         audit_path_override='${state}')
apply_audit.record_apply(verb='v2', round_origin='R0', gates_satisfied=True,
                         gates_detail={}, wrote=True,
                         audit_path_override='${state}')
"
out="$(SOVEREIGN_OS_APPLY_AUDIT_PATH=${state} python3 "${SCRIPT}" audit --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['total_rows'] == 3
assert d['wrote_count'] == 2
assert d['gate_violations'] == 1
assert d['by_verb'] == {'v1': 2, 'v2': 1}
" || fail "audit"
rm -f "${state}"
pass "7. CLI audit rollup (total_rows / by_verb / gate_violations / wrote_count)"

# ── 8. R318 heat-oc-throttle apply integrates with audit log ──
state=$(mktemp -u)
target=$(mktemp -u)
SOVEREIGN_OS_APPLY_AUDIT_PATH="${state}" python3 "${HEAT_SCRIPT}" apply \
    --target "${target}" --json >/dev/null 2>&1 || true
[[ -f "${state}" ]] || fail "R318 apply must write to audit log"
rows=$(wc -l < "${state}")
[[ "${rows}" -ge 1 ]] || fail "expected ≥1 audit row from R318 apply; got ${rows}"
# Inspect the row.
grep -q '"verb": "heat-oc-throttle apply"' "${state}" \
    || fail "expected verb='heat-oc-throttle apply' in audit log"
grep -q '"round_origin": "R318"' "${state}" \
    || fail "expected round_origin='R318' in audit log"
rm -f "${state}" "${target}"
pass "8. R318 heat-oc-throttle apply writes audit row (verb + round_origin)"

# ── 9. Operator overlay sets audit_path_override ─────────
cfg=$(mktemp --suffix=.toml)
audit_target=$(mktemp -u)
cat > "${cfg}" <<TOML
audit_path_override = "${audit_target}"
TOML
# Pre-populate the audit file via direct write.
python3 -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/scripts/lib')
import apply_audit
apply_audit.record_apply(verb='overlay-test', round_origin='R0',
                         gates_satisfied=True, gates_detail={},
                         audit_path_override='${audit_target}')
"
out="$(python3 "${SCRIPT}" tail --n 5 --config "${cfg}" --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['row_count'] == 1
assert d['rows'][0]['verb'] == 'overlay-test'
" || fail "overlay knob"
rm -f "${cfg}" "${audit_target}"
pass "9. operator overlay (R283/SDD-030) sets audit_path_override"

# ── 10. sovereign-osctl apply-audit dispatch ──────────────
state=$(mktemp -u)
out_disp="$(SOVEREIGN_OS_APPLY_AUDIT_PATH=${state} bash "${OSCTL}" apply-audit audit --json 2>/dev/null)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R327'
" || fail "osctl dispatch"
rm -f "${state}"
pass "10. sovereign-osctl apply-audit dispatches"

echo "ALL OK"
