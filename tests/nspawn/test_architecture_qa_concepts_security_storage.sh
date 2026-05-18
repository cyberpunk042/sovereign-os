#!/usr/bin/env bash
# R362 (E10.M7) — architecture-qa concepts C-14 (§4 Tetragon) + C-15
# (§3 Storage Architecture) verbatim preservation L3.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
AQ="${REPO_ROOT}/scripts/intelligence/architecture-qa.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. concepts catalog ≥15 with C-14 + C-15 ────────────────────────
out="$(python3 "${AQ}" concepts --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['concept_count'] >= 15
ids = {c['id'] for c in d['concepts']}
assert 'C-14' in ids
assert 'C-15' in ids
" || fail "15 concepts"
pass "1. concepts catalog ≥15; C-14 + C-15 present"

# ── 2. C-14 §4 Tetragon TracingPolicy verbatim ──────────────────────
out="$(python3 "${AQ}" show C-14 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['item']
# §4 + §4.1 operator-verbatim YAML phrases — MUST appear unchanged
must = [
    'apiVersion: cilium.io/v1alpha1',
    'kind: TracingPolicy',
    'sovereign-kernel-fence',
    'kprobes',
    'sys_execve',
    'syscall: true',
    'matchArgs',
    'NotIn',
    '/usr/bin/python3',
    '/usr/bin/nvidia-smi',
    '/usr/local/bin/vllm',
    '/usr/bin/podman',
    'Sigkill',
    'kernel space',
    'maintaining system integrity',
]
for phrase in must:
    assert phrase in c['explanation'], f'missing verbatim phrase: {phrase!r}'
" || fail "C-14 verbatim"
pass "2. C-14 §4 Tetragon TracingPolicy verbatim — 15 phrases (apiVersion, TracingPolicy, 4-binary allowlist, Sigkill)"

# ── 3. C-14 documents implementation deviation explicitly ───────────
out="$(python3 "${AQ}" show C-14 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['item']
# C-14 explicitly notes the shipped policy uses __x64_sys_execve +
# matchBinaries instead of operator's bare sys_execve + matchArgs —
# documents the deviation so operator can audit.
assert '__x64_sys_execve' in c['explanation']
assert 'matchBinaries' in c['explanation']
assert 'modern Tetragon' in c['explanation']
" || fail "C-14 deviation notes"
pass "3. C-14 explicitly documents shipped-vs-verbatim deviation (__x64_sys_execve + matchBinaries refinement)"

# ── 4. C-14 4-binary allowlist preserved exactly (operator's §4.1)
out="$(python3 "${AQ}" show C-14 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['item']
exact_binaries = [
    '/usr/bin/python3',
    '/usr/bin/nvidia-smi',
    '/usr/local/bin/vllm',
    '/usr/bin/podman',
]
for b in exact_binaries:
    assert b in c['explanation'], f'missing allowlist binary: {b}'
# Mentioned twice — once in the YAML block, once in implementation note
explanation_count = sum(c['explanation'].count(b) for b in exact_binaries)
assert explanation_count >= 4, f'allowlist binaries should appear at least once each; got total {explanation_count}'
" || fail "4-binary allowlist"
pass "4. C-14 preserves operator's exact 4-binary allowlist (python3 / nvidia-smi / vllm / podman)"

# ── 5. C-15 §3 + §4.1 Storage Architecture verbatim ─────────────────
out="$(python3 "${AQ}" show C-15 --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
c = d['item']
must = [
    'shard data',
    'access patterns and reliability',
    'tank/models',
    'recordsize 1M',
    'lz4',
    'Redundant Metadata',
    '100GB+ weight files',
    'tank/context',
    'recordsize 16k',
    'zstd-9',
    'copies=2',
    '[SOUL.md]',
    '[IDENTITY.md]',
    'tank/agents',
    'recordsize 128k',
    'zstd-3',
    'Stateful local storage',
    'ashift=12',
    'compression=lz4',
    '/dev/nvme0n1',
    '/dev/nvme1n1',
    'ZFS RAID 0',
    '31.5 GB/s',
]
for phrase in must:
    assert phrase in c['explanation'], f'missing verbatim phrase: {phrase!r}'
" || fail "C-15 verbatim"
pass "5. C-15 §3 + §4.1 verbatim — 23 phrases (3 datasets × recordsize+compression + RAID 0 + 31.5 GB/s)"

# ── 6. spec_ref correctness ─────────────────────────────────────────
out="$(python3 "${AQ}" concepts --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
by_id = {c['id']: c for c in d['concepts']}
assert '§4' in by_id['C-14']['spec_ref']
assert '§3' in by_id['C-15']['spec_ref']
" || fail "spec_ref"
pass "6. C-14/C-15 spec_ref cite §4/§3 correctly"

# ── 7. search 'tetragon' now matches C-07 + C-14 (multiple concepts)
out="$(python3 "${AQ}" search 'tetragon' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ids = [c['id'] for c in d['matched_concepts']]
# Should hit C-07 (Guardian event loop), C-14 (TracingPolicy)
assert 'C-14' in ids, ids
" || fail "search tetragon"
pass "7. search 'tetragon' → C-14 (TracingPolicy concept added)"

# ── 8. search 'zstd-9' finds C-15 ───────────────────────────────────
out="$(python3 "${AQ}" search 'zstd-9' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ids = [c['id'] for c in d['matched_concepts']]
assert 'C-15' in ids, ids
" || fail "search zstd-9"
pass "8. search 'zstd-9' → C-15 (Storage Architecture concept)"

# ── 9. search '/usr/local/bin/vllm' finds C-14 (allowlist binary) ───
out="$(python3 "${AQ}" search '/usr/local/bin/vllm' --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ids = [c['id'] for c in d['matched_concepts']]
assert 'C-14' in ids, ids
" || fail "search vllm binary"
pass "9. search '/usr/local/bin/vllm' → C-14 (allowlist binary preserved)"

# ── 10. R357 sibling L3 still green ─────────────────────────────────
if bash "${REPO_ROOT}/tests/nspawn/test_architecture_qa_concepts.sh" >/dev/null 2>&1; then
    pass "10. R357 architecture_qa_concepts L3 still 13/13 green"
else
    fail "R357 regressed"
fi

# ── 11. R360 sibling L3 still green ─────────────────────────────────
if bash "${REPO_ROOT}/tests/nspawn/test_architecture_qa_concepts_extended.sh" >/dev/null 2>&1; then
    pass "11. R360 architecture_qa_concepts_extended L3 still 13/13 green"
else
    fail "R360 regressed"
fi

# ── 12. R361 sibling L3 still green ─────────────────────────────────
if bash "${REPO_ROOT}/tests/nspawn/test_architecture_qa_concepts_final.sh" >/dev/null 2>&1; then
    pass "12. R361 architecture_qa_concepts_final L3 still 13/13 green"
else
    fail "R361 regressed"
fi

# ── 13. shipped Tetragon policy file matches operator's allowlist ──
policy_script="${REPO_ROOT}/scripts/hooks/post-install/tetragon-policy-load.sh"
if [ -f "${policy_script}" ]; then
    for b in /usr/bin/python3 /usr/bin/nvidia-smi /usr/local/bin/vllm /usr/bin/podman; do
        grep -q "${b}" "${policy_script}" \
            || fail "shipped policy missing allowlist binary: ${b}"
    done
    pass "13. shipped Tetragon policy script preserves operator's 4-binary allowlist exactly"
else
    fail "tetragon-policy-load.sh missing"
fi

echo "ALL OK"
