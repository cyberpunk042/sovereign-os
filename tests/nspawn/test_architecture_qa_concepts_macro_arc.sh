#!/usr/bin/env bash
# R364 (E10.M9) — architecture-qa concepts C-20/C-21/C-22/C-23 L3.
# Operator-verbatim macro-arc plan dump 2026-05-16 — post-Plan
# refinements: SFIF / IaC quality bar / Debian-as-Ark / Q-016.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AQ="${REPO_ROOT}/scripts/intelligence/architecture-qa.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. concepts catalog ≥23 with C-20..C-23 ─────────────────────────
out="$(python3 "${AQ}" concepts --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['concept_count'] >= 23
ids = {c['id'] for c in d['concepts']}
for must in ('C-20','C-21','C-22','C-23'):
    assert must in ids, f'missing {must}'
" || fail "23 concepts"
pass "1. concepts catalog ≥23; C-20/C-21/C-22/C-23 present"

# ── 2. C-20 SFIF discipline verbatim ────────────────────────────────
out="$(python3 "${AQ}" show C-20 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['item']
must = [
    'Scaffold → Foundation → Infrastructure → Features',
    'PRs 1-3 = Scaffold',
    'PRs 4-8 = Foundation',
    'PRs 9-10 begin Infrastructure',
    'Stage 2 onwards delivers Infrastructure + Features',
    'TDD harness',
    'gate criteria',
]
for phrase in must:
    assert phrase in c['explanation'], f'missing verbatim phrase: {phrase!r}'
" || fail "C-20 verbatim"
pass "2. C-20 SFIF — 7 verbatim phrases (full Scaffold→…→Features arc + PR ranges + gate criteria)"

# ── 3. C-21 IaC quality bar verbatim ────────────────────────────────
out="$(python3 "${AQ}" show C-21 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['item']
must = [
    'high-quality scripts + libs + configuration',
    'easily tweakable + customisable',
    'env-var-driven',
    'restart-from-state',
    'Build pipeline is resumable + observable',
    'not one-shot',
    'triple-gate apply ceremony',
    'SOVEREIGN_OS_CONFIRM_DESTROY=YES',
    'Layer B prometheus metrics',
    'JSONL apply-audit',
    'state-snapshot',
    'pause + restart at any phase boundary',
]
for phrase in must:
    assert phrase in c['explanation'], f'missing verbatim phrase: {phrase!r}'
" || fail "C-21 verbatim"
pass "3. C-21 IaC quality bar — 12 verbatim phrases (operator's exact 7-property requirement + observability stack)"

# ── 4. C-22 Debian-as-Ark framing verbatim ──────────────────────────
out="$(python3 "${AQ}" show C-22 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['item']
must = [
    \"'Debian as Ark' framing\",
    'Debian 13 is the starting boat, not the destination',
    'unlock material new potential',
    'stay on Debian + customize the boat',
    \"'boat' metaphor\",
    'known-stable foundation',
    'NOT building a Debian derivative',
    'Sovereign OS that happens to sail on Debian-13 hull',
]
for phrase in must:
    assert phrase in c['explanation'], f'missing verbatim phrase: {phrase!r}'
" || fail "C-22 verbatim"
pass "4. C-22 Debian-as-Ark — 8 verbatim phrases (starting boat + customize-the-boat + NOT-derivative)"

# ── 5. C-23 Q-016 distro reconsideration verbatim ───────────────────
out="$(python3 "${AQ}" show C-23 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['item']
must = [
    'Q-016 distro-base reconsideration',
    'switching from Debian 13',
    'unlock material new potential',
    'Stays open through PR 4 substrate survey',
    'resolved at Stage Gate 2',
    'Q-001',
    'NixOS',
    'declarative + rollback + reproducibility',
    'Fedora Silverblue + ostree',
    'Arch Linux',
    'upstream entropy',
    'Buildroot/Yocto',
    'Working hypothesis from operator',
    'stay on Debian + customize the boat',
    'formal honesty gate',
]
for phrase in must:
    assert phrase in c['explanation'], f'missing verbatim phrase: {phrase!r}'
" || fail "C-23 verbatim"
pass "5. C-23 Q-016 — 15 verbatim phrases (5 candidate distros + Stage Gate 2 + honesty gate)"

# ── 6. spec_ref correctness for C-20..C-23 ──────────────────────────
out="$(python3 "${AQ}" concepts --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
by_id = {c['id']: c for c in d['concepts']}
for cid in ('C-20','C-21','C-22','C-23'):
    sr = by_id[cid]['spec_ref']
    assert 'macro-arc plan' in sr, f'{cid} spec_ref missing macro-arc plan reference'
    assert '2026-05-16' in sr, f'{cid} spec_ref missing dump date'
    assert 'post-Plan' in sr, f'{cid} spec_ref missing post-Plan tag'
" || fail "spec_ref"
pass "6. C-20/21/22/23 spec_ref cite 'macro-arc plan dump 2026-05-16 post-Plan' uniformly"

# ── 7. search 'sfif' finds C-20 ─────────────────────────────────────
out="$(python3 "${AQ}" search 'sfif' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ids = [c['id'] for c in d['matched_concepts']]
assert 'C-20' in ids, ids
" || fail "search sfif"
pass "7. search 'sfif' → C-20 (operator-named discipline shorthand preserved)"

# ── 8. search 'debian as ark' finds C-22 ────────────────────────────
out="$(python3 "${AQ}" search 'debian as ark' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ids = [c['id'] for c in d['matched_concepts']]
assert 'C-22' in ids, ids
" || fail "search debian as ark"
pass "8. search 'debian as ark' → C-22 (operator's verbatim framing phrase)"

# ── 9. search 'q-016' finds C-23 ────────────────────────────────────
out="$(python3 "${AQ}" search 'q-016' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ids = [c['id'] for c in d['matched_concepts']]
assert 'C-23' in ids, ids
" || fail "search q-016"
pass "9. search 'q-016' → C-23 (distro reconsideration seed-list addition)"

# ── 10. search 'restart-from-state' finds C-21 ──────────────────────
out="$(python3 "${AQ}" search 'restart-from-state' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ids = [c['id'] for c in d['matched_concepts']]
assert 'C-21' in ids, ids
" || fail "search restart-from-state"
pass "10. search 'restart-from-state' → C-21 (IaC quality bar operator phrase)"

# ── 11. C-22 + C-23 are cross-linked (both reference distro topic) ─
out="$(python3 "${AQ}" search 'distro' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ids = {c['id'] for c in d['matched_concepts']}
assert 'C-22' in ids and 'C-23' in ids
" || fail "cross-link"
pass "11. search 'distro' → C-22 AND C-23 cross-linked (Debian-as-Ark + Q-016 mutually reinforcing)"

# ── 12. All sibling architecture-qa L3 tests still green ───────────
for sibling in test_architecture_qa.sh \
                test_architecture_qa_concepts.sh \
                test_architecture_qa_concepts_extended.sh \
                test_architecture_qa_concepts_final.sh \
                test_architecture_qa_concepts_security_storage.sh \
                test_architecture_qa_concepts_hardware_summary.sh; do
    if bash "${REPO_ROOT}/tests/nspawn/${sibling}" >/dev/null 2>&1; then
        true
    else
        fail "${sibling} regressed"
    fi
done
pass "12. All 6 architecture-qa sibling L3 tests still green (no regression)"

# ── 13. operator-overlay still extends concepts ────────────────────
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
[[concepts]]
id = "C-OVERLAY-MACRO"
name = "overlay macro test"
explanation = "test"
tags = ["test"]
spec_ref = "overlay test 2026-05-18"
TOML
out="$(python3 "${AQ}" concepts --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ids = [c['id'] for c in d['concepts']]
assert 'C-OVERLAY-MACRO' in ids
" || fail "overlay"
rm -f "${cfg}"
pass "13. operator-overlay still extends concepts list (R283/SDD-030 lists-replace)"

echo "ALL OK"
