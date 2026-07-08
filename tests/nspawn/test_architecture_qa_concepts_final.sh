#!/usr/bin/env bash
# R361 (E10.M6) — architecture-qa concepts extension L3 (C-11..C-13).
# Adds §5 Vibe Manager + §9 Dockerfile AVX-512 + §18 Asymmetric_Burst
# JSON. /goal "NO MINIMIZING / NO REPHRASING" enforced via 30+ phrases.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AQ="${REPO_ROOT}/scripts/intelligence/architecture-qa.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. concepts catalog now ≥13 with C-11..C-13 present ─────────────
out="$(python3 "${AQ}" concepts --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['concept_count'] >= 13
ids = {c['id'] for c in d['concepts']}
for must in ('C-11','C-12','C-13'):
    assert must in ids, f'missing {must}'
" || fail "13 concepts"
pass "1. concepts catalog ≥13 entries; C-11 + C-12 + C-13 present"

# ── 2. C-11 §5 Vibe Manager verbatim ────────────────────────────────
out="$(python3 "${AQ}" show C-11 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['item']
must = [
    '120GB total VRAM as a tiered execution fabric',
    'Primary Reasoning',
    '96GB Blackwell',
    '(Direct Host)',
    'Speculative Decoding',
    '24GB 4090',
    '(VFIO Sandbox)',
    'State Persistence',
    '9900X',
    \"manages the 'Vibe'\",
    'tank/context ZFS dataset',
    'atomic writes and data integrity',
]
for phrase in must:
    assert phrase in c['explanation'], f'missing verbatim phrase: {phrase!r}'
" || fail "C-11 verbatim"
pass "2. C-11 §5 Vibe Manager verbatim — 12 phrases (120GB tiered fabric + 3 tiers + ZFS)"

# ── 3. C-12 §9 Dockerfile env vars verbatim ─────────────────────────
out="$(python3 "${AQ}" show C-12 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['item']
must = [
    'single-cycle, native 512-bit AVX-512 data path',
    'double-pumped 256-bit execution models',
    'Manager',
    'llama.cpp',
    'Podman infrastructure',
    'avoid fallback emulation',
    '-march=znver5',
    '-mavx512f',
    '-mavx512dq',
    '-mavx512bw',
    '-mavx512vl',
    '-mavx512bf16',
    '-mavx512fp16',
    'GGML_AVX512=1',
    'GGML_AVX512_VBMI=1',
    'GGML_AVX512_VNNI=1',
    'GGML/vLLM backends',
    '512-bit vector paths',
]
for phrase in must:
    assert phrase in c['explanation'], f'missing verbatim phrase: {phrase!r}'
" || fail "C-12 verbatim"
pass "3. C-12 §9 Dockerfile verbatim — 18 phrases (CFLAGS znver5 + 6 mavx512* + GGML env vars × 3)"

# ── 4. C-13 §18 Asymmetric_Burst JSON verbatim ──────────────────────
out="$(python3 "${AQ}" show C-13 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['item']
must = [
    'Asymmetric Load Balancing',
    'Asymmetric_Burst',
    'conductor_01',
    'core_mask',
    '0-11',
    'bitnet.cpp',
    'BitNet-b1.58-13B',
    'translator_01',
    'cuda:0',
    '22548578304',
    'vllm-vulkan',
    'Qwen-32B-Ternary-Quant',
    'deep_reasoner_01',
    'cuda:1',
    '94489280512',
    'llama.cpp',
    'DeepSeek-R1-Distill-Llama-70B-FP16',
    'VRAM capacity and compute generation',
]
for phrase in must:
    assert phrase in c['explanation'], f'missing verbatim phrase: {phrase!r}'
" || fail "C-13 verbatim"
pass "4. C-13 §18 Asymmetric_Burst verbatim — 18 phrases (3 agent slots × runtime + exact VRAM byte limits)"

# ── 5. spec_ref correctness: C-11 §5, C-12 §9, C-13 §18 ────────────
out="$(python3 "${AQ}" concepts --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
by_id = {c['id']: c for c in d['concepts']}
assert '§5' in by_id['C-11']['spec_ref']
assert '§9' in by_id['C-12']['spec_ref']
assert '§18' in by_id['C-13']['spec_ref']
" || fail "spec_ref"
pass "5. C-11/C-12/C-13 spec_ref cite §5/§9/§18 correctly"

# ── 6. search 'asymmetric_burst' finds C-13 ─────────────────────────
out="$(python3 "${AQ}" search 'asymmetric_burst' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ids = [c['id'] for c in d['matched_concepts']]
assert 'C-13' in ids, ids
" || fail "search asymmetric_burst"
pass "6. search 'asymmetric_burst' → C-13"

# ── 7. search 'GGML_AVX512_VNNI' finds C-12 ─────────────────────────
out="$(python3 "${AQ}" search 'GGML_AVX512_VNNI' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ids = [c['id'] for c in d['matched_concepts']]
assert 'C-12' in ids, ids
" || fail "search GGML_AVX512_VNNI"
pass "7. search 'GGML_AVX512_VNNI' → C-12 (Container Build AVX-512)"

# ── 8. search 'vibe' finds C-11 ─────────────────────────────────────
out="$(python3 "${AQ}" search 'vibe' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ids = [c['id'] for c in d['matched_concepts']]
assert 'C-11' in ids, ids
" || fail "search vibe"
pass "8. search 'vibe' → C-11 (Operational Logic / Vibe Manager)"

# ── 9. R357 sibling L3 still 13/13 green ────────────────────────────
if bash "${REPO_ROOT}/tests/nspawn/test_architecture_qa_concepts.sh" >/dev/null 2>&1; then
    pass "9. R357 architecture_qa_concepts L3 still 13/13 green (no regression)"
else
    fail "R357 regressed"
fi

# ── 10. R360 sibling L3 still 13/13 green ───────────────────────────
if bash "${REPO_ROOT}/tests/nspawn/test_architecture_qa_concepts_extended.sh" >/dev/null 2>&1; then
    pass "10. R360 architecture_qa_concepts_extended L3 still 13/13 green (no regression)"
else
    fail "R360 regressed"
fi

# ── 11. R355 sibling L3 still 12/12 green ───────────────────────────
if bash "${REPO_ROOT}/tests/nspawn/test_architecture_qa.sh" >/dev/null 2>&1; then
    pass "11. R355 architecture_qa L3 still 12/12 green (no regression)"
else
    fail "R355 regressed"
fi

# ── 12. exact byte limits verbatim — operator's §18 JSON numbers ───
# These specific integer values are from operator's §18 JSON. They
# encode 21 GiB (22548578304) and 88 GiB (94489280512). If any
# operator-conversion drift happens, this catches it.
out="$(python3 "${AQ}" show C-13 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['item']
# Both byte-limit values must be the exact operator-stated integers
assert '22548578304' in c['explanation']
assert '94489280512' in c['explanation']
# Sanity: those are exactly 21 GiB and 88 GiB (operator-named via §18)
# 22548578304 / 1024 / 1024 / 1024 ≈ 21.0
# 94489280512 / 1024 / 1024 / 1024 ≈ 88.0
" || fail "byte limits"
pass "12. C-13 exact byte limits preserved verbatim (22548578304 + 94489280512 = 21 GiB + 88 GiB)"

# ── 13. tag-based discovery works for new concepts ──────────────────
out="$(python3 "${AQ}" concepts --tag 'vibe-manager' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ids = [c['id'] for c in d['concepts']]
assert 'C-11' in ids
" || fail "tag vibe-manager"
pass "13. concepts --tag vibe-manager → C-11 (tag filter on new concept)"

echo "ALL OK"
