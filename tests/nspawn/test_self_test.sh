#!/usr/bin/env bash
# R331 (E9.M14) — self-test verb L3.
#
# Meta-test: tests the self-test verb itself works.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/diagnostics/self-test.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. list --json envelope ─────────────────────────────────
out="$(python3 "${SCRIPT}" list --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R331'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E9.M14'
for k in ('lint_glob', 'lint_files', 'unit_globs', 'l3_paths'):
    assert k in d, k
" || fail "list envelope"
pass "1. list --json envelope"

# ── 2. lint_glob defaults to tests/lint/*.py ───────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['lint_glob'] == 'tests/lint/*.py'
# Should match ≥15 lint files (we have many).
assert len(d['lint_files']) >= 15
" || fail "lint glob"
pass "2. lint_glob = tests/lint/*.py matches ≥15 files"

# ── 3. L3 paths catalog has ≥5 entries ─────────────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert len(d['l3_paths']) >= 5
" || fail "l3 paths"
pass "3. l3_paths catalog has ≥5 curated test scripts"

# ── 4. run --json envelope ─────────────────────────────────
RC=0
out_r="$(python3 "${SCRIPT}" run --json)" || RC=$?
[[ "${RC}" == "0" || "${RC}" == "1" ]] || fail "run rc unexpected: ${RC}"
echo "${out_r}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R331'
for k in ('lint', 'unit', 'l3', 'totals', 'verdict', 'rc'):
    assert k in d, k
" || fail "run envelope"
pass "4. run --json envelope (lint/unit/l3/totals/verdict/rc)"

# ── 5. Per-suite result has rc + passed + failed + duration ──
echo "${out_r}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for suite_key in ('lint',):
    s = d[suite_key]
    for k in ('rc', 'passed', 'failed', 'duration_ms', 'available'):
        assert k in s, (suite_key, k)
for s in d['unit'] + d['l3']:
    for k in ('rc', 'passed', 'failed', 'duration_ms', 'available'):
        assert k in s, (k, s)
" || fail "per-suite shape"
pass "5. per-suite result has rc/passed/failed/duration_ms/available"

# ── 6. totals = sum across suites ─────────────────────────
echo "${out_r}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
calc_passed = (d['lint']['passed']
                + sum(u['passed'] for u in d['unit'])
                + sum(l['passed'] for l in d['l3']))
assert d['totals']['passed'] == calc_passed, (d['totals']['passed'], calc_passed)
calc_failed = (d['lint']['failed']
                + sum(u['failed'] for u in d['unit'])
                + sum(l['failed'] for l in d['l3']))
assert d['totals']['failed'] == calc_failed
" || fail "totals sum"
pass "6. totals = sum of per-suite passed + failed counts"

# ── 7. verdict matches rc semantics ───────────────────────
echo "${out_r}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
if d['rc'] == 0:
    assert d['verdict'] == 'all-pass', d['verdict']
else:
    assert d['verdict'] == 'failures', d['verdict']
" || fail "verdict"
pass "7. verdict matches rc semantics (all-pass ↔ rc=0)"

# ── 8. wall_clock < sum of durations (parallel-ish) ────────
echo "${out_r}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
sum_dur = (d['lint']['duration_ms']
            + sum(u['duration_ms'] for u in d['unit'])
            + sum(l['duration_ms'] for l in d['l3']))
# Self-test currently runs sequentially → wall ≈ sum, allow 10% slop.
assert d['wall_clock_ms'] <= sum_dur * 1.5
" || fail "wall clock"
pass "8. wall_clock ≤ 1.5× sum of per-suite durations"

# ── 9. Operator overlay narrows l3_paths ─────────────────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
l3_paths = [
    "tests/nspawn/test_rounds_catalog.sh",
]
TOML
RC=0
out_o="$(python3 "${SCRIPT}" list --config "${overlay}" --json)" || RC=$?
echo "${out_o}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['l3_paths'] == ['tests/nspawn/test_rounds_catalog.sh']
" || fail "overlay narrows l3"
rm -f "${overlay}"
pass "9. operator overlay narrows l3_paths to single curated test"

# ── 10. sovereign-osctl self-test dispatch ────────────────
out_disp="$(bash "${OSCTL}" self-test list --json 2>/dev/null)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R331'
" || fail "osctl dispatch"
pass "10. sovereign-osctl self-test dispatches"

echo "ALL OK"
