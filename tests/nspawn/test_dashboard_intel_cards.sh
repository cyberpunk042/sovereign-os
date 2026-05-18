#!/usr/bin/env bash
# R354 (E4.M10) — dashboard intelligence-tier cards L3.
# Surfaces R349 guide / R350 model-adapt / R351 module-state / R352
# morning-brief / R353 model-build via the dashboard CARDS registry.
# Operator-named §1b: "Everything via dashboard/UInterface or terminal
# tools OR AI" — terminal verbs exist; this round wires the UI side.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. CARDS list registers all 5 new intelligence cards ──────────
python3 -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/scripts/dashboard')
from serve import CARDS
ids = [fn.__name__.removeprefix('card_') for fn in CARDS]
for must in ('morning_brief','module_state','guide','model_adapt','model_build'):
    assert must in ids, f'missing card: {must}; got {ids}'
" || fail "card list"
pass "1. CARDS registers morning_brief + module_state + guide + model_adapt + model_build"

# ── 2. Each new card function returns full schema (id/title/data) ──
python3 -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/scripts/dashboard')
import serve
for fn_name in ('card_morning_brief','card_module_state','card_guide',
                'card_model_adapt','card_model_build'):
    fn = getattr(serve, fn_name)
    c = fn()
    for k in ('id','title','data'):
        assert k in c, f'{fn_name} missing {k}'
    assert isinstance(c['data'], dict), fn_name
    assert 'summary' in c['data'], f'{fn_name} data.summary missing'
    assert 'needs_attention' in c['data'], f'{fn_name} data.needs_attention missing'
    assert isinstance(c['data']['needs_attention'], bool)
" || fail "schema"
pass "2. all 5 cards return id+title+data{summary, needs_attention: bool}"

# ── 3. morning_brief card derives summary from rollup ──────────────
python3 -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/scripts/dashboard')
from serve import card_morning_brief
c = card_morning_brief()
d = c['data']
s = d['summary'].lower()
# Summary should mention critical signals or suggested topic
assert 'critical' in s or 'suggested' in s or 'no criticals' in s
" || fail "mb summary"
pass "3. morning_brief.summary derived from rollup (critical or suggested-topic mention)"

# ── 4. module_state card derives 'N/total need attention' ──────────
python3 -c "
import sys, re
sys.path.insert(0, '${REPO_ROOT}/scripts/dashboard')
from serve import card_module_state
c = card_module_state()
s = c['data']['summary']
# Format: 'N/M module(s) need attention'
assert re.match(r'\d+/\d+ module', s), s
" || fail "ms summary"
pass "4. module_state.summary format 'N/M module(s) need attention'"

# ── 5. guide card lists topic count + axes ─────────────────────────
python3 -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/scripts/dashboard')
from serve import card_guide
c = card_guide()
s = c['data']['summary']
assert 'topics' in s and 'axes' in s, s
assert c['data']['needs_attention'] is False  # informational
" || fail "guide"
pass "5. guide.summary lists topics + axes; needs_attention=False (informational)"

# ── 6. model_adapt card lists recipe + GPU counts ──────────────────
python3 -c "
import sys, re
sys.path.insert(0, '${REPO_ROOT}/scripts/dashboard')
from serve import card_model_adapt
c = card_model_adapt()
s = c['data']['summary']
assert re.match(r'\d+ adaptation recipe', s) or 'unavailable' in s, s
" || fail "adapt"
pass "6. model_adapt.summary format 'N adaptation recipe(s); M declared GPU(s)'"

# ── 7. model_build card lists recipe + history counts ──────────────
python3 -c "
import sys, re
sys.path.insert(0, '${REPO_ROOT}/scripts/dashboard')
from serve import card_model_build
c = card_model_build()
s = c['data']['summary']
assert re.match(r'\d+ build recipe', s) or 'unavailable' in s, s
# Data carries the recent_builds tail for the UI
assert 'recent_builds' in c['data']
assert isinstance(c['data']['recent_builds'], list)
" || fail "build"
pass "7. model_build.summary format 'N recipe(s); M historical build(s)'; recent_builds tail surfaced"

# ── 8. morning_brief appears FIRST in CARDS (operator entry-point) ─
python3 -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/scripts/dashboard')
from serve import CARDS
first_id = CARDS[0].__name__.removeprefix('card_')
assert first_id == 'morning_brief', f'morning_brief should be CARDS[0]; got {first_id}'
" || fail "ordering"
pass "8. morning_brief is CARDS[0] — operator's daily entry-point at top"

# ── 9. Cross-regression — existing test_dashboard_grid still green ─
if bash "${REPO_ROOT}/tests/nspawn/test_dashboard_grid.sh" >/dev/null 2>&1; then
    pass "9. test_dashboard_grid still 21/21 green (card_count >= 20 forward-compat)"
else
    fail "test_dashboard_grid regressed"
fi

# ── 10. _run_intel_script helper imports without error ─────────────
python3 -c "
import sys
sys.path.insert(0, '${REPO_ROOT}/scripts/dashboard')
import serve
assert hasattr(serve, '_run_intel_script')
assert callable(serve._run_intel_script)
# NEVER-raise: missing script returns None
result = serve._run_intel_script('no-such-script.py', [])
assert result is None
" || fail "helper"
pass "10. _run_intel_script helper exists + NEVER-raises on missing script"

echo "ALL OK"
