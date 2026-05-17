#!/usr/bin/env bash
# R335 (E2.M26) — config-snapshot-diff verb L3.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/diagnostics/config-snapshot-diff.py"
SNAPSHOT="${REPO_ROOT}/scripts/diagnostics/config-snapshot.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# Helper: capture two snapshots from src1, src2 → echo "snap_a|snap_b".
make_pair() {
    local src1="$1"
    local src2="$2"
    local a b
    a=$(mktemp --suffix=.json)
    b=$(mktemp --suffix=.json)
    python3 "${SNAPSHOT}" capture --overlay-dir "${src1}" --json > "${a}"
    python3 "${SNAPSHOT}" capture --overlay-dir "${src2}" --json > "${b}"
    echo "${a}|${b}"
}

# ── 1. diff --json envelope ───────────────────────────────
src1=$(mktemp -d); src2=$(mktemp -d)
echo 'k = 1' > "${src1}/x.toml"
echo 'k = 1' > "${src2}/x.toml"
pair=$(make_pair "${src1}" "${src2}"); a="${pair%|*}"; b="${pair##*|}"
RC=0
out="$(python3 "${SCRIPT}" diff --before "${a}" --after "${b}" --json)" || RC=$?
[[ "${RC}" == "0" || "${RC}" == "1" ]] || fail "unexpected rc: ${RC}"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R335'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E2.M26'
for k in ('before_path', 'after_path', 'before_captured_at',
          'after_captured_at', 'diff'):
    assert k in d, k
" || fail "envelope"
rm -rf "${src1}" "${src2}" "${a}" "${b}"
pass "1. diff --json envelope"

# ── 2. Identical overlays → rc=0 + identical_overlays populated ──
src1=$(mktemp -d); src2=$(mktemp -d)
echo 'k = 1' > "${src1}/same.toml"
echo 'k = 1' > "${src2}/same.toml"
pair=$(make_pair "${src1}" "${src2}"); a="${pair%|*}"; b="${pair##*|}"
RC=0
out="$(python3 "${SCRIPT}" diff --before "${a}" --after "${b}" --json)" || RC=$?
[[ "${RC}" == "0" ]] || fail "identical should give rc=0; got ${RC}"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
df = d['diff']
assert df['identical_overlays'] == ['same.toml'], df
assert df['added_overlays'] == []
assert df['removed_overlays'] == []
assert df['changed_overlays'] == []
" || fail "identical shape"
rm -rf "${src1}" "${src2}" "${a}" "${b}"
pass "2. identical overlays → rc=0 + identical_overlays populated"

# ── 3. Added overlay detected ─────────────────────────────
src1=$(mktemp -d); src2=$(mktemp -d)
echo 'k = 1' > "${src2}/new.toml"
pair=$(make_pair "${src1}" "${src2}"); a="${pair%|*}"; b="${pair##*|}"
RC=0
out="$(python3 "${SCRIPT}" diff --before "${a}" --after "${b}" --json)" || RC=$?
[[ "${RC}" == "1" ]] || fail "added should give rc=1; got ${RC}"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
df = d['diff']
assert len(df['added_overlays']) == 1
assert df['added_overlays'][0]['overlay_file'] == 'new.toml'
" || fail "added shape"
rm -rf "${src1}" "${src2}" "${a}" "${b}"
pass "3. added overlay detected + rc=1"

# ── 4. Removed overlay detected ───────────────────────────
src1=$(mktemp -d); src2=$(mktemp -d)
echo 'k = 1' > "${src1}/gone.toml"
pair=$(make_pair "${src1}" "${src2}"); a="${pair%|*}"; b="${pair##*|}"
out="$(python3 "${SCRIPT}" diff --before "${a}" --after "${b}" --json)" || true
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
df = d['diff']
assert len(df['removed_overlays']) == 1
assert df['removed_overlays'][0]['overlay_file'] == 'gone.toml'
" || fail "removed shape"
rm -rf "${src1}" "${src2}" "${a}" "${b}"
pass "4. removed overlay detected"

# ── 5. Changed overlay detects sha256 mismatch ─────────
src1=$(mktemp -d); src2=$(mktemp -d)
echo 'k = 1' > "${src1}/m.toml"
echo 'k = 2' > "${src2}/m.toml"
pair=$(make_pair "${src1}" "${src2}"); a="${pair%|*}"; b="${pair##*|}"
out="$(python3 "${SCRIPT}" diff --before "${a}" --after "${b}" --json)" || true
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
df = d['diff']
assert len(df['changed_overlays']) == 1
c = df['changed_overlays'][0]
assert c['overlay_file'] == 'm.toml'
assert c['sha256_before'] != c['sha256_after']
" || fail "changed shape"
rm -rf "${src1}" "${src2}" "${a}" "${b}"
pass "5. changed overlay detects sha256 mismatch"

# ── 6. Changed overlay → per-key dotted-path diff ─────────
src1=$(mktemp -d); src2=$(mktemp -d)
cat > "${src1}/m.toml" <<'TOML'
key_a = 1
key_b = "old"
[nested]
deep = 100
TOML
cat > "${src2}/m.toml" <<'TOML'
key_a = 2
key_c = true
[nested]
deep = 100
extra = "added"
TOML
pair=$(make_pair "${src1}" "${src2}"); a="${pair%|*}"; b="${pair##*|}"
out="$(python3 "${SCRIPT}" diff --before "${a}" --after "${b}" --json)" || true
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
kd = d['diff']['changed_overlays'][0]['key_diff']
assert kd['parsable'] is True
added_keys = {k['key'] for k in kd['added']}
removed_keys = {k['key'] for k in kd['removed']}
changed_keys = {k['key'] for k in kd['changed']}
assert 'key_c' in added_keys, added_keys
assert 'nested.extra' in added_keys, added_keys
assert 'key_b' in removed_keys, removed_keys
assert 'key_a' in changed_keys, changed_keys
" || fail "key diff"
rm -rf "${src1}" "${src2}" "${a}" "${b}"
pass "6. changed overlay emits per-key dotted-path diff (added/removed/changed)"

# ── 7. Multi-overlay diff (add + remove + change in one pair) ──
src1=$(mktemp -d); src2=$(mktemp -d)
echo 'k = 1' > "${src1}/same.toml"
echo 'k = 1' > "${src2}/same.toml"
echo 'k = 1' > "${src1}/changed.toml"
echo 'k = 2' > "${src2}/changed.toml"
echo 'k = 1' > "${src1}/removed.toml"
echo 'k = 1' > "${src2}/added.toml"
pair=$(make_pair "${src1}" "${src2}"); a="${pair%|*}"; b="${pair##*|}"
out="$(python3 "${SCRIPT}" diff --before "${a}" --after "${b}" --json)" || true
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
df = d['diff']
assert df['identical_overlays'] == ['same.toml']
assert [a['overlay_file'] for a in df['added_overlays']] == ['added.toml']
assert [r['overlay_file'] for r in df['removed_overlays']] == ['removed.toml']
assert [c['overlay_file'] for c in df['changed_overlays']] == ['changed.toml']
" || fail "multi diff"
rm -rf "${src1}" "${src2}" "${a}" "${b}"
pass "7. multi-overlay diff (add + remove + change + identical in one pair)"

# ── 8. Non-R332 snapshot rejected with rc=2 ───────────────
bad=$(mktemp)
echo '{"round": "not-R332"}' > "${bad}"
src=$(mktemp -d); echo 'k=1' > "${src}/x.toml"
b=$(mktemp --suffix=.json)
python3 "${SNAPSHOT}" capture --overlay-dir "${src}" --json > "${b}"
RC=0
python3 "${SCRIPT}" diff --before "${bad}" --after "${b}" --json 2>/dev/null || RC=$?
[[ "${RC}" == "2" ]] || fail "expected rc=2 for non-R332; got ${RC}"
rm -rf "${bad}" "${src}" "${b}"
pass "8. non-R332 snapshot rejected with rc=2 (round mismatch)"

# ── 9. Nonexistent snapshot file → rc=2 ──────────────────
src=$(mktemp -d); echo 'k=1' > "${src}/x.toml"
b=$(mktemp --suffix=.json)
python3 "${SNAPSHOT}" capture --overlay-dir "${src}" --json > "${b}"
RC=0
python3 "${SCRIPT}" diff --before /no/such/file --after "${b}" --json 2>/dev/null || RC=$?
[[ "${RC}" == "2" ]] || fail "expected rc=2 for missing file; got ${RC}"
rm -rf "${src}" "${b}"
pass "9. nonexistent snapshot file → rc=2"

# ── 10. sovereign-osctl config-snapshot-diff dispatch ──
src1=$(mktemp -d); src2=$(mktemp -d)
echo 'k = 1' > "${src1}/x.toml"
echo 'k = 1' > "${src2}/x.toml"
pair=$(make_pair "${src1}" "${src2}"); a="${pair%|*}"; b="${pair##*|}"
RC=0
out_disp="$(bash "${OSCTL}" config-snapshot-diff diff --before "${a}" --after "${b}" --json 2>/dev/null)" || RC=$?
[[ "${RC}" == "0" || "${RC}" == "1" ]] || fail "osctl rc unexpected: ${RC}"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R335'
" || fail "osctl dispatch"
rm -rf "${src1}" "${src2}" "${a}" "${b}"
pass "10. sovereign-osctl config-snapshot-diff dispatches"

echo "ALL OK"
