#!/usr/bin/env bash
# R325 (E2.M21) — operator-overlay drift detector L3.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/diagnostics/overlay-drift-detector.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

mk_overlay_dir() {
    local dir
    dir=$(mktemp -d)
    cat > "${dir}/sample-a.toml" <<'TOML'
key1 = 42
key2 = "hello"
[nested]
deep = true
[nested.deeper]
val = 100
TOML
    cat > "${dir}/sample-b.toml" <<'TOML'
flag = false
TOML
    echo "BAD TOML [[[" > "${dir}/bad.toml"
    echo "${dir}"
}

# ── 1. list --json envelope ────────────────────────────────
dir=$(mk_overlay_dir)
out="$(python3 "${SCRIPT}" list --overlay-dir "${dir}" --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R325'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E2.M21'
assert d['exists'] is True
assert d['overlay_count'] == 3
" || fail "envelope"
rm -rf "${dir}"
pass "1. list --json envelope + 3 overlays counted"

# ── 2. Every overlay has full schema ──────────────────────
dir=$(mk_overlay_dir)
out="$(python3 "${SCRIPT}" list --overlay-dir "${dir}" --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for o in d['overlays']:
    for k in ('overlay_file', 'overlay_path', 'size_bytes',
              'parse_error', 'keys', 'key_count', 'table_count',
              'inferred_consumer_script_basename'):
        assert k in o, (k, o)
" || fail "schema"
rm -rf "${dir}"
pass "2. every overlay carries full schema (file/path/size/parse_error/keys/...)"

# ── 3. Key flattening produces dotted-path keys ────────────
dir=$(mk_overlay_dir)
out="$(python3 "${SCRIPT}" show sample-a --overlay-dir "${dir}" --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
o = d['overlay']
keys = set(o['keys'])
# sample-a has: key1, key2, nested.deep, nested.deeper.val
assert keys == {'key1', 'key2', 'nested.deep', 'nested.deeper.val'}, keys
" || fail "flatten"
rm -rf "${dir}"
pass "3. key flattening produces dotted-path keys (nested.deeper.val)"

# ── 4. Malformed TOML → parse_error set, not crashed ──────
dir=$(mk_overlay_dir)
out="$(python3 "${SCRIPT}" show bad --overlay-dir "${dir}" --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
o = d['overlay']
assert o['parse_error'] is not None
assert o['key_count'] == 0
" || fail "parse error"
rm -rf "${dir}"
pass "4. malformed TOML → parse_error set + key_count=0 (no crash)"

# ── 5. show accepts both 'sample-a' and 'sample-a.toml' ──
dir=$(mk_overlay_dir)
out1="$(python3 "${SCRIPT}" show sample-a --overlay-dir "${dir}" --json)"
out2="$(python3 "${SCRIPT}" show sample-a.toml --overlay-dir "${dir}" --json)"
python3 -c "
import json
o1 = json.loads('''${out1}''')['overlay']['overlay_file']
o2 = json.loads('''${out2}''')['overlay']['overlay_file']
assert o1 == o2 == 'sample-a.toml'
" || fail "show normalize"
rm -rf "${dir}"
pass "5. show accepts both 'sample-a' and 'sample-a.toml' inputs"

# ── 6. Unknown overlay → rc=1 + structured error ──────────
dir=$(mk_overlay_dir)
RC=0
python3 "${SCRIPT}" show no-such-overlay --overlay-dir "${dir}" --json 2>/dev/null || RC=$?
[[ "${RC}" == "1" ]] || fail "show unknown rc expected 1; got ${RC}"
rm -rf "${dir}"
pass "6. show unknown overlay → rc=1 + structured error"

# ── 7. audit returns rollup counts ─────────────────────────
dir=$(mk_overlay_dir)
out="$(python3 "${SCRIPT}" audit --overlay-dir "${dir}" --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
a = d['audit']
assert a['overlay_count'] == 3
assert a['parsed_ok'] == 2
assert a['parse_errors'] == 1
# total_keys = 4 (sample-a) + 1 (sample-b) = 5
assert a['total_keys_overridden'] == 5, a
" || fail "audit"
rm -rf "${dir}"
pass "7. audit returns rollup (3 overlays, 2 parsed OK, 1 error, 5 keys)"

# ── 8. Nonexistent overlay_dir → rc=1 + structured response ──
RC=0
python3 "${SCRIPT}" list --overlay-dir /no/such/dir --json >/dev/null 2>&1 || RC=$?
[[ "${RC}" == "1" ]] || fail "no-dir rc expected 1; got ${RC}"
pass "8. nonexistent overlay_dir → rc=1"

# ── 9. inferred_consumer_script_basename mirrors filename ──
dir=$(mk_overlay_dir)
out="$(python3 "${SCRIPT}" show sample-a --overlay-dir "${dir}" --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
o = d['overlay']
assert o['inferred_consumer_script_basename'] == 'sample-a.py', o
" || fail "inferred"
rm -rf "${dir}"
pass "9. inferred_consumer_script_basename maps 'sample-a.toml' → 'sample-a.py'"

# ── 10. sovereign-osctl overlay-drift dispatch ────────────
dir=$(mk_overlay_dir)
out_disp="$(bash "${OSCTL}" overlay-drift audit --overlay-dir "${dir}" --json 2>/dev/null)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R325'
" || fail "osctl dispatch"
rm -rf "${dir}"
pass "10. sovereign-osctl overlay-drift dispatches"

echo "ALL OK"
