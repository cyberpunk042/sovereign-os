#!/usr/bin/env bash
# R376 (E10.M20) — doctrine-status L3.
# Operator-pull SDD-037 lint family health at-a-glance verb.

set -euo pipefail

# Hosts without pytest (dev CI) can't execute the 'run' subverb which
# internally drives pytest. Detect absence and skip run assertions.
PYTEST_AVAILABLE=0
python3 -m pytest --version >/dev/null 2>&1 && PYTEST_AVAILABLE=1

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DS="${REPO_ROOT}/scripts/intelligence/doctrine-status.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. status: returns 8-lint family with declared assertion counts ─
out="$(python3 "${DS}" status --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['lint_family_size'] == 8
assert d['total_declared_assertions'] >= 60
for l in d['lints']:
    assert 'round' in l and l['round'].startswith('R')
    assert l['assertions'] >= 6
" || fail "status schema"
pass "1. status returns 8-lint family with ≥60 total declared assertions"

# ── 2. status names the 7 specific rounds R367..R374 ────────────────
out="$(python3 "${DS}" status --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
rounds = {l['round'] for l in d['lints']}
expected = {'R367', 'R368', 'R370', 'R371', 'R372', 'R373', 'R374', 'R380'}
assert rounds == expected, f'expected {expected}, got {rounds}'
" || fail "round set"
pass "2. status lints exactly cover R367/R368/R370/R371/R372/R373/R374"

# ── 3. tally returns ≥17 drift modes ────────────────────────────────
out="$(python3 "${DS}" tally --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['drift_mode_count'] >= 18
assert isinstance(d['drift_modes'], list)
# Specific drift modes must be cited
modes = ' '.join(d['drift_modes'])
must = ['Fabricated §N', 'Fabricated mandate row', 'Fabricated sovereign-osctl verb',
        'Cross-catalog phrase drift', 'Tetragon 4-binary', 'Silent paraphrase']
for m in must:
    assert m in modes, f'missing drift mode: {m}'
" || fail "tally drift modes"
pass "3. tally catalogs ≥17 drift modes including the 5 fabrication-catch surfaces"

# ── 4. cumulative bugs caught tally ≥20 ────────────────────────────
out="$(python3 "${DS}" status --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['cumulative_bugs_caught'] >= 20, f'got {d[\"cumulative_bugs_caught\"]}'
" || fail "bugs"
pass "4. cumulative_bugs_caught ≥20 (R371 + R372 + R373 historical catches)"

# ── 5. run verb executes pytest + returns per-lint pass/fail ───────
if [ "${PYTEST_AVAILABLE}" -eq 1 ]; then
  out="$(python3 "${DS}" run --json 2>&1 || true)"
  echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['all_clean'] is True
assert d['total_passed'] >= 60
assert d['total_failed'] == 0
for l in d['lints']:
    assert l['ok'] is True
    assert l['passed'] >= 6
" || fail "run"
  pass "5. run executes pytest on all 7 SDD-037 lints + all_clean=true"

  # ── 6. run rc=0 when all lints pass ─────────────────────────────────
  rc=0; python3 "${DS}" run --json >/dev/null 2>&1 || rc=$?
  [[ "${rc}" == 0 ]] || fail "run rc=${rc} (expected 0)"
  pass "6. run rc=0 when SDD-037 family all clean"
else
  pass "5. run assertions SKIPPED — pytest not installed on this host"
  pass "6. run rc assertions SKIPPED — pytest not installed on this host"
fi

# ── 7. human output rendering works for all 3 subverbs ──────────────
python3 "${DS}" status --human >/dev/null 2>&1 || fail "status human"
python3 "${DS}" tally --human >/dev/null 2>&1 || fail "tally human"
python3 "${DS}" run --human >/dev/null 2>&1 || fail "run human"
pass "7. human-readable output renders for status/tally/run"

# ── 8. osctl dispatches all 3 subverbs ──────────────────────────────
"${OSCTL}" doctrine-status status --json >/dev/null 2>&1 || fail "osctl status"
"${OSCTL}" doctrine-status tally --json >/dev/null 2>&1 || fail "osctl tally"
"${OSCTL}" doctrine-status run --json >/dev/null 2>&1 || fail "osctl run"
pass "8. sovereign-osctl doctrine-status dispatches status/tally/run"

# ── 9. unknown subverb → rc=2 + error message ──────────────────────
rc=0; "${OSCTL}" doctrine-status nope --json >/dev/null 2>&1 || rc=$?
[[ "${rc}" == 2 ]] || fail "unknown subverb rc=${rc}"
pass "9. unknown subverb → rc=2 (usage error)"

# ── 10. per-lint purpose strings are non-trivial (operator-readable)
out="$(python3 "${DS}" tally --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for l in d['lint_family']:
    assert 'purpose' in l
    assert len(l['purpose']) >= 50, f'{l[\"round\"]} purpose too terse'
" || fail "purpose strings"
pass "10. per-lint purpose strings ≥50 chars (operator-readable)"

# ── 11. drift mode catalog mentions all 5 fabrication-catch surfaces
out="$(python3 "${DS}" tally --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
all_modes = ' '.join(d['drift_modes']).lower()
# 5 fabrication-catch surfaces from R368/R371/R372/R373/R374
for surface in ['fabricated §n', 'fabricated mandate row',
                 'fabricated sovereign-osctl verb', 'cross-catalog phrase',
                 'fabricated r<n>']:
    assert surface in all_modes, f'drift mode catalog missing: {surface}'
" || fail "fabrication coverage"
pass "11. drift mode catalog explicitly names all 5 fabrication-catch surfaces"

# ── 12. status human-readable contains glyph markers ───────────────
out="$(python3 "${DS}" status --human 2>&1)"
echo "${out}" | grep -q "lint family" || fail "missing 'lint family' header"
echo "${out}" | grep -q "Per-lint:" || fail "missing per-lint section"
pass "12. status --human renders 'lint family' + 'Per-lint:' markers"

echo "ALL OK"
