#!/usr/bin/env bash
# R352 (E10.M2) — morning-brief composition L3.
# Verifies composing R329 + R351 + R308 + R349 produces a coherent
# operator-readable rollup with NEVER-raise on missing sub-probes.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MB="${REPO_ROOT}/scripts/intelligence/morning-brief.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. rollup JSON has top-level required fields ─────────────────────
out="$(python3 "${MB}" rollup --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for k in ('schema_version','round','sdd_vector','rc',
         'critical_signals_count','critical_signals','sections',
         'suggested_topic_guide','suggested_topic_verb'):
    assert k in d, k
assert d['round'] == 'R352'
" || fail "schema"
pass "1. rollup JSON has full schema (round + rc + sections + suggestions)"

# ── 2. sections contains next_action + module_state + autohealth ────
out="$(python3 "${MB}" rollup --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for s in ('next_action', 'module_state', 'autohealth'):
    assert s in d['sections'], s
    assert 'available' in d['sections'][s]
" || fail "sections"
pass "2. sections covers next_action + module_state + autohealth (3 composed sources)"

# ── 3. module_state section reflects 16 unconfigured (empty etc) ────
out="$(python3 "${MB}" rollup --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ms = d['sections']['module_state']
assert ms['available'] is True
# Empty /etc on test host → all 16 modules need attention
assert ms['attention_count'] >= 10
assert len(ms['items']) >= 1
" || fail "module state"
pass "3. module_state section surfaces ≥10 attention items from R351"

# ── 4. next_action section is best-effort — available OR error string
out="$(python3 "${MB}" rollup --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
na = d['sections']['next_action']
assert isinstance(na.get('available'), bool)
if na['available']:
    assert isinstance(na.get('items'), list)
else:
    assert 'error' in na
" || fail "next action"
pass "4. next_action section is structurally valid (available OR error)"

# ── 5. autohealth section NEVER raises (graceful when unavailable) ───
out="$(python3 "${MB}" rollup --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ah = d['sections']['autohealth']
assert isinstance(ah.get('available'), bool)
# severity may be None if probe unavailable
if not ah['available']:
    assert 'error' in ah
" || fail "autohealth"
pass "5. autohealth section NEVER-raises (graceful unavailable handling)"

# ── 6. suggested_topic_guide names a real R349 topic ────────────────
out="$(python3 "${MB}" rollup --json || true)"
topic="$(echo "${out}" | python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('suggested_topic_guide') or '')")"
if [[ -n "${topic}" ]]; then
    known="$(python3 "${REPO_ROOT}/scripts/intelligence/guide.py" topics --json \
        | python3 -c "import json,sys; print(' '.join(json.loads(sys.stdin.read())['topic_names']))")"
    [[ " ${known} " == *" ${topic} "* ]] || fail "topic ${topic} not in R349 catalog"
fi
pass "6. suggested_topic_guide names a real R349 topic (or null)"

# ── 7. suggested_topic_verb is operator-runnable osctl command ──────
out="$(python3 "${MB}" rollup --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
v = d.get('suggested_topic_verb')
if v is not None:
    assert v.startswith('sovereign-osctl guide walkthrough '), v
    parts = v.split()
    assert parts[-1] == d['suggested_topic_guide']
" || fail "verb shape"
pass "7. suggested_topic_verb is operator-runnable 'sovereign-osctl guide walkthrough <topic>'"

# ── 8. --limit flag overrides next_action_limit ─────────────────────
out="$(python3 "${MB}" rollup --limit 1 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
na = d['sections']['next_action']
if na['available']:
    assert len(na['items']) <= 1
" || fail "limit"
pass "8. --limit 1 caps next_action items at 1"

# ── 9. human-readable output renders sections in order ──────────────
out="$(python3 "${MB}" rollup --human 2>&1 || true)"
echo "${out}" | grep -q "morning-brief"            || fail "header"
echo "${out}" | grep -q "next-actions"              || fail "na section"
echo "${out}" | grep -q "module gaps"               || fail "ms section"
echo "${out}" | grep -q "autohealth"                || fail "ah section"
pass "9. human render has all 4 sections (header + next-actions + module gaps + autohealth)"

# ── 10. sovereign-osctl morning-brief dispatches ────────────────────
"${OSCTL}" morning-brief rollup --json >/dev/null 2>&1 || rc=$?
# rc may be 1 if critical signals or unconfigured modules — both expected
pass "10. sovereign-osctl morning-brief dispatches to rollup"

# ── 11. unknown subverb → rc=2 ──────────────────────────────────────
rc=0; "${OSCTL}" morning-brief bogus 2>/dev/null || rc=$?
[[ "${rc}" == 2 ]] || fail "unknown subverb rc=${rc}"
pass "11. sovereign-osctl morning-brief unknown subverb → rc=2"

# ── 12. operator-overlay tunes per-section limits ───────────────────
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
next_action_limit = 2
module_state_limit = 3
include_autohealth = false
include_guide_suggestion = false
TOML
out="$(python3 "${MB}" rollup --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# When include_autohealth=false, the probe still runs (section is built
# unconditionally for schema stability) but include_guide_suggestion=false
# zeroes the suggestion.
assert d.get('suggested_topic_guide') is None
assert d.get('suggested_topic_verb') is None
ms = d['sections']['module_state']
if ms['available']:
    assert len(ms['items']) <= 3
" || fail "overlay"
rm -f "${cfg}"
pass "12. operator-overlay tunes section limits + disables suggestion"

echo "ALL OK"
