#!/usr/bin/env bash
# R357 (E10.M4) — architecture-qa concepts L3.
# Operator-VERBATIM §15-16 1-Bit Paradigm + Hardware Fusion +
# §19 dual-CCD + Block 6 Trinity Genesis as discoverable concepts.
# /goal contract enforced: NO MINIMIZING / NO REPHRASING / NO COMPRESSING.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AQ="${REPO_ROOT}/scripts/intelligence/architecture-qa.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. concepts verb returns ≥5 C-NN items with full schema ─────────
out="$(python3 "${AQ}" concepts --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['concept_count'] >= 5
for c in d['concepts']:
    for k in ('id','name','explanation','tags','spec_ref'):
        assert k in c, (k, c)
    assert c['id'].startswith('C-')
" || fail "concepts schema"
pass "1. concepts returns ≥5 C-NN with id+name+explanation+tags+spec_ref"

# ── 2. C-01 ternary verbatim — operator's §15.1 elimination of mult.
out="$(python3 "${AQ}" show C-01 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['item']
# §15.1 operator-verbatim phrases — MUST appear unchanged
must_have = [
    '{-1, 0, +1}',
    'log_2(3)',
    '1.585',
    'discrete ternary set',
    'conditional allocation',
    'No-Op',
    'energy-efficient',
]
for phrase in must_have:
    assert phrase in c['explanation'], f'missing verbatim phrase: {phrase!r}'
" || fail "C-01 verbatim"
pass "2. C-01 explanation preserves §15.1 verbatim (7 phrases: ternary set, log_2(3), No-Op, …)"

# ── 3. C-02 ZMM verbatim — operator's §16 single-cycle AVX-512 ──────
out="$(python3 "${AQ}" show C-02 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['item']
must_have = [
    'single-cycle',
    'native AVX-512 (Zen 5)',
    'double-pump',
    '512-bit wide ZMM',
    '64 independent 8-bit integer',
    '128 independent 4-bit packed',
    'bitnet.cpp',
    'T-MAC',
    'Bit-wise Lookup Table',
]
for phrase in must_have:
    assert phrase in c['explanation'], f'missing verbatim phrase: {phrase!r}'
" || fail "C-02 verbatim"
pass "3. C-02 explanation preserves §16 verbatim (9 phrases: single-cycle, 64 INT8, T-MAC, …)"

# ── 4. C-03 VNNI verbatim — §16.1 closing paragraph ─────────────────
out="$(python3 "${AQ}" show C-03 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['item']
must_have = [
    'VNNI (Vector Neural Network Instructions)',
    'multiple INT8 activations',
    'packed ternary weights',
    '32-bit destination registers',
    'fraction of a clock cycle',
    '5–12 tokens/sec',
    'bypassing the PCIe bus bottleneck',
    'GPU memory unencumbered',
]
for phrase in must_have:
    assert phrase in c['explanation'], f'missing verbatim phrase: {phrase!r}'
" || fail "C-03 verbatim"
pass "4. C-03 explanation preserves §16.1 verbatim (8 phrases: VNNI, 5–12 tokens/sec, PCIe bypass, …)"

# ── 5. C-04 dual-CCD verbatim — §19 + §19.1 ─────────────────────────
out="$(python3 "${AQ}" show C-04 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['item']
must_have = [
    'engineering masterpiece',
    'Friction',
    'dual-CCD (Core Complex Die)',
    'CCD 0: Cores 0–5',
    'CCD 1: Cores 6–11',
    '32MB of L3 cache',
    'AMD Infinity Fabric',
    'L3 cache miss',
    'cross-die latency penalty',
]
for phrase in must_have:
    assert phrase in c['explanation'], f'missing verbatim phrase: {phrase!r}'
" || fail "C-04 verbatim"
pass "5. C-04 explanation preserves §19+§19.1 verbatim (9 phrases: engineering masterpiece, 32MB L3, Infinity Fabric, …)"

# ── 6. C-05 Trinity Genesis verbatim — Block 6 Modules 1/2/3 ────────
out="$(python3 "${AQ}" show C-05 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['item']
must_have = [
    'decoupled software trinity',
    'THE PULSE',
    'MASM (Microsoft Macro Assembler)',
    'WebAssembly (Wasm)',
    'bit-plane transposition',
    'THE WEAVER',
    'Wasm-based sandboxing',
    'THE AUDITOR',
    'automated, immediate circuit breaker',
]
for phrase in must_have:
    assert phrase in c['explanation'], f'missing verbatim phrase: {phrase!r}'
" || fail "C-05 verbatim"
pass "6. C-05 explanation preserves Block 6 verbatim (9 phrases: decoupled trinity, MASM, bit-plane, sandboxing, circuit breaker)"

# ── 7. show unknown id now lists known_concepts too ─────────────────
rc=0
err="$(python3 "${AQ}" show no-such-id --json 2>&1 1>/dev/null)" || rc=$?
[[ "${rc}" == 1 ]] || fail "rc=${rc}"
echo "${err}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'known_concepts' in d
assert len(d['known_concepts']) >= 5
" || fail "unknown shape"
pass "7. show unknown → structured error now lists known_concepts too"

# ── 8. --tag filter narrows concepts ────────────────────────────────
out="$(python3 "${AQ}" concepts --tag vnni --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['concept_count'] >= 1
for c in d['concepts']:
    assert 'vnni' in c['tags']
" || fail "tag filter"
pass "8. concepts --tag vnni → narrows to C-NN with that tag (≥1 hit: C-03)"

# ── 9. search verb now matches across questions + gotchas + concepts
out="$(python3 "${AQ}" search ternary --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
total = d['question_match_count'] + d['gotcha_match_count'] + d['concept_match_count']
assert total >= 1
# 'ternary' should match concepts (C-01 + C-03 mention it)
assert d['concept_match_count'] >= 1
" || fail "search ternary"
pass "9. search 'ternary' → ≥1 concept match (C-01 + C-03 contain it)"

# ── 10. search 'infinity fabric' hits the dual-CCD concept ──────────
out="$(python3 "${AQ}" search 'infinity fabric' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ids = [c['id'] for c in d['matched_concepts']]
assert 'C-04' in ids, ids
" || fail "search infinity fabric"
pass "10. search 'infinity fabric' → C-04 (dual-CCD concept) matches"

# ── 11. operator-overlay can extend concepts list ───────────────────
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
[[concepts]]
id = "C-99"
name = "operator-overlay test concept"
explanation = "operator-overlay test explanation."
tags = ["test","overlay"]
spec_ref = "operator overlay 2026-05-18"
TOML
out="$(python3 "${AQ}" concepts --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ids = [c['id'] for c in d['concepts']]
assert 'C-99' in ids
" || fail "overlay"
rm -f "${cfg}"
pass "11. operator-overlay extends concepts list (R283/SDD-030 lists-replace)"

# ── 12. sovereign-osctl architecture-qa dispatches concepts subverb ─
"${OSCTL}" architecture-qa concepts --json >/dev/null 2>&1 || fail "osctl concepts"
"${OSCTL}" architecture-qa show C-02 --json >/dev/null 2>&1 || fail "osctl show C-02"
"${OSCTL}" architecture-qa search vnni --json >/dev/null 2>&1 || fail "osctl search vnni"
pass "12. sovereign-osctl architecture-qa dispatches concepts/show C-NN/search across concepts"

# ── 13. existing R355 L3 still green (cross-regression) ─────────────
if bash "${REPO_ROOT}/tests/nspawn/test_architecture_qa.sh" >/dev/null 2>&1; then
    pass "13. R355 architecture_qa L3 still 12/12 green (no regression)"
else
    fail "R355 regressed"
fi

echo "ALL OK"
