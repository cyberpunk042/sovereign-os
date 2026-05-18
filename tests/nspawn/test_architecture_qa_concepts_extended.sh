#!/usr/bin/env bash
# R360 (E10.M5) — architecture-qa concepts extension L3 (C-06..C-10).
# 5 more operator-verbatim §17.1 + §10 + §21 + §11 + §20 concepts.
# /goal contract enforced: NO MINIMIZING / NO REPHRASING / NO COMPRESSING.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AQ="${REPO_ROOT}/scripts/intelligence/architecture-qa.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. concepts now returns ≥10 C-NN (C-01..C-10) ───────────────────
out="$(python3 "${AQ}" concepts --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['concept_count'] >= 10
ids = {c['id'] for c in d['concepts']}
for must in ('C-06','C-07','C-08','C-09','C-10'):
    assert must in ids, f'missing {must}'
" || fail "10 concepts"
pass "1. concepts catalog ≥10 entries; new C-06..C-10 present"

# ── 2. C-06 §17.1 Layered Responsibility verbatim — 3 agents named ─
out="$(python3 "${AQ}" show C-06 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['item']
# §17.1 operator-verbatim per-agent phrases — MUST appear unchanged
must = [
    'The Conductor Agent (CPU Bound)',
    'The Logic Engine (GPU 0 - RTX 3090)',
    'The Oracle Core (GPU 1 - Blackwell PRO 6000)',
    'evaluates incoming user intent' if False else 'Evaluates incoming user intent',
    'updates CLAUDE.md',
    'enforces state rules in SOUL.md',
    'Q4_K_M or IQ4_NL',
    '24GB VRAM ceiling',
    '96GB Blackwell memory pool',
    'absolute accuracy during complex system optimization',
]
for phrase in must:
    assert phrase in c['explanation'], f'missing verbatim phrase: {phrase!r}'
" || fail "C-06 verbatim"
pass "2. C-06 §17.1 verbatim — 10 phrases: 3 agent titles + per-agent runtime/justification text"

# ── 3. C-07 §10 Native Guardian Event Loop verbatim ─────────────────
out="$(python3 "${AQ}" show C-07 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['item']
must = [
    'SecureToast.ps1',
    'Tetragon eBPF UNIX socket',
    'autonomous circuit breaker',
    '/usr/local/bin/guardian-core',
    'SIGKILL',
    'BindsTo=tetragon.service',
    'guardian-core script will stall on its read loop',
    'blinding your real-time exploit containment system',
]
for phrase in must:
    assert phrase in c['explanation'], f'missing verbatim phrase: {phrase!r}'
" || fail "C-07 verbatim"
pass "3. C-07 §10 verbatim — 8 phrases: SecureToast.ps1, BindsTo, circuit breaker, stall blinding"

# ── 4. C-08 §21 Atomic State Transition Protocol verbatim ───────────
out="$(python3 "${AQ}" show C-08 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['item']
must = [
    'lockless loopback write sequence',
    'memory-mapped /mnt/vault/context/CLAUDE.md',
    'O_DIRECT / POSIX AIO',
    'sync=always',
    'atomic NVMe block commit',
    'O_WRONLY | O_CREAT | O_TRUNC | O_DIRECT | O_SYNC',
    'NVMe physical block alignment (4K boundary)',
    'atomic rename so no reader ever views a partially written file',
]
for phrase in must:
    assert phrase in c['explanation'], f'missing verbatim phrase: {phrase!r}'
" || fail "C-08 verbatim"
pass "4. C-08 §21 verbatim — 8 phrases: lockless loopback, O_DIRECT|O_SYNC, 4K alignment, atomic rename"

# ── 5. C-09 §11 Consolidated Execution Strategy verbatim (5 phases) ─
out="$(python3 "${AQ}" show C-09 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['item']
must = [
    'Phase I (Iron Validation)',
    'friction-audit',
    'x8/x8 hardware lane topology',
    'Phase II (The Engine)',
    '-march=znver5',
    'Phase III (The OS Image)',
    'Phase IV (The File System)',
    'Phase V (The Perimeter)',
    '120GB multi-GPU execution array',
    'No hacks, no shortcuts, no compromises',
]
for phrase in must:
    assert phrase in c['explanation'], f'missing verbatim phrase: {phrase!r}'
" || fail "C-09 verbatim"
pass "5. C-09 §11 verbatim — 10 phrases: 5 phase titles + per-phase content + 'no hacks' closing"

# ── 6. C-10 §20 Wasm-to-AVX-512 AOT Pipeline verbatim ───────────────
out="$(python3 "${AQ}" show C-10 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['item']
must = [
    'Ahead-Of-Time (AOT) compilation',
    'Cranelift or LLVM',
    'native Zen 5 machine code',
    'VPDPBUSD',
    'WASMTIME_COMPARE_OPTIONS',
    '-C target-cpu=znver5',
    '-C relaxed-simd=true',
    'taskset -c 0-11 wasmtime compile --target znver5',
    'pulse_core.wasm',
    'native vector cores (CCD 0)',
]
for phrase in must:
    assert phrase in c['explanation'], f'missing verbatim phrase: {phrase!r}'
" || fail "C-10 verbatim"
pass "6. C-10 §20 verbatim — 10 phrases: AOT, Cranelift/LLVM, WASMTIME flags, taskset CCD 0"

# ── 7. C-06 spec_ref cites §17.1; C-07 cites §10; C-08 cites §21 ───
out="$(python3 "${AQ}" concepts --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
by_id = {c['id']: c for c in d['concepts']}
assert '§17.1' in by_id['C-06']['spec_ref']
assert '§10' in by_id['C-07']['spec_ref']
assert '§21' in by_id['C-08']['spec_ref']
assert '§11' in by_id['C-09']['spec_ref']
assert '§20' in by_id['C-10']['spec_ref']
" || fail "spec_ref"
pass "7. C-06/C-07/C-08/C-09/C-10 spec_ref cite §17.1/§10/§21/§11/§20 correctly"

# ── 8. search 'cranelift' finds C-10 (Wasm AOT) ─────────────────────
out="$(python3 "${AQ}" search cranelift --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ids = [c['id'] for c in d['matched_concepts']]
assert 'C-10' in ids, ids
" || fail "search cranelift"
pass "8. search 'cranelift' → C-10 (Wasm-to-AVX-512 AOT Pipeline)"

# ── 9. search 'phase iii' finds C-09 ────────────────────────────────
out="$(python3 "${AQ}" search 'phase iii' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ids = [c['id'] for c in d['matched_concepts']]
assert 'C-09' in ids, ids
" || fail "search phase iii"
pass "9. search 'phase iii' → C-09 (Consolidated Execution Strategy)"

# ── 10. search 'o_direct' finds C-08 ────────────────────────────────
out="$(python3 "${AQ}" search 'o_direct' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ids = [c['id'] for c in d['matched_concepts']]
assert 'C-08' in ids, ids
" || fail "search o_direct"
pass "10. search 'o_direct' → C-08 (Atomic State Transition Protocol)"

# ── 11. existing R357 L3 still green (cross-regression) ─────────────
if bash "${REPO_ROOT}/tests/nspawn/test_architecture_qa_concepts.sh" >/dev/null 2>&1; then
    pass "11. R357 architecture_qa_concepts L3 still 13/13 green (no regression)"
else
    fail "R357 regressed"
fi

# ── 12. existing R355 L3 still green ────────────────────────────────
if bash "${REPO_ROOT}/tests/nspawn/test_architecture_qa.sh" >/dev/null 2>&1; then
    pass "12. R355 architecture_qa L3 still 12/12 green (no regression)"
else
    fail "R355 regressed"
fi

# ── 13. tag-based filter on new concepts works ──────────────────────
out="$(python3 "${AQ}" concepts --tag binds-to --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ids = [c['id'] for c in d['concepts']]
assert 'C-07' in ids
" || fail "tag binds-to"
pass "13. concepts --tag binds-to → C-07 (Guardian Event Loop) via tag filter"

echo "ALL OK"
