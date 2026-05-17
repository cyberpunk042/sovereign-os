#!/usr/bin/env bash
# R332 (E2.M23) — config snapshot for backup/migration L3.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/diagnostics/config-snapshot.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

mk_overlay_dir() {
    local dir
    dir=$(mktemp -d)
    cat > "${dir}/sample-a.toml" <<'TOML'
key1 = 42
key2 = "hello"
TOML
    cat > "${dir}/sample-b.toml" <<'TOML'
flag = false
TOML
    echo "${dir}"
}

# ── 1. audit --json envelope ───────────────────────────────
dir=$(mk_overlay_dir)
out_a="$(python3 "${SCRIPT}" audit --overlay-dir "${dir}" --json)"
echo "${out_a}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R332'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E2.M23'
for k in ('overlay_count', 'overlay_bytes', 'helper_library_modules',
          'audit_tail_planned'):
    assert k in d, k
" || fail "audit envelope"
rm -rf "${dir}"
pass "1. audit --json envelope"

# ── 2. capture --json envelope + per-overlay body+sha256 ──
dir=$(mk_overlay_dir)
out_c="$(python3 "${SCRIPT}" capture --overlay-dir "${dir}" --json)"
echo "${out_c}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R332'
assert d['overlay_count'] == 2
for o in d['overlays']:
    for k in ('overlay_file', 'overlay_path', 'size_bytes',
              'sha256', 'body_b64'):
        assert k in o, (k, o)
    # sha256 is 64 hex chars
    assert len(o['sha256']) == 64
" || fail "capture envelope"
rm -rf "${dir}"
pass "2. capture --json envelope + per-overlay (file/size/sha256/body_b64)"

# ── 3. body_b64 round-trips to original bytes ──────────────
dir=$(mk_overlay_dir)
out_c="$(python3 "${SCRIPT}" capture --overlay-dir "${dir}" --json)"
python3 -c "
import json, base64, hashlib, pathlib
d = json.loads('''${out_c}''')
for o in d['overlays']:
    decoded = base64.b64decode(o['body_b64'])
    assert len(decoded) == o['size_bytes']
    assert hashlib.sha256(decoded).hexdigest() == o['sha256']
    # Compare to original file.
    original = pathlib.Path(o['overlay_path']).read_bytes()
    assert decoded == original
print('PASS')
" || fail "round-trip"
rm -rf "${dir}"
pass "3. body_b64 round-trips to original bytes (sha256 + content match)"

# ── 4. helper_library manifest captures lib/*.py ───────────
dir=$(mk_overlay_dir)
out_c="$(python3 "${SCRIPT}" capture --overlay-dir "${dir}" --json)"
echo "${out_c}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
hl = d['helper_library']
assert hl['module_count'] >= 3
modules = {m['module'] for m in hl['modules']}
# All three SDD-032 helpers must appear.
for must in ('operator_overlay.py', 'apply_audit.py', 'safe_apply.py'):
    assert must in modules, modules
for m in hl['modules']:
    assert len(m['sha256']) == 64
" || fail "helper-library manifest"
rm -rf "${dir}"
pass "4. helper-library manifest captures 3 SDD-032 helpers + sha256s"

# ── 5. include_inventory toggle ─────────────────────────
dir=$(mk_overlay_dir)
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
overlay_dir = "${dir}"
include_inventory = false
include_windows = false
include_audit = false
TOML
out_c="$(python3 "${SCRIPT}" capture --config "${cfg}" --json)"
echo "${out_c}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'inventory' not in d
assert 'maintenance_windows' not in d
assert 'audit_tail' not in d
" || fail "toggle"
rm -rf "${dir}"
rm -f "${cfg}"
pass "5. include_inventory/include_windows/include_audit toggles work"

# ── 6. Empty overlay dir → overlay_count=0, capture succeeds ──
dir=$(mktemp -d)
out_c="$(python3 "${SCRIPT}" capture --overlay-dir "${dir}" --json)"
echo "${out_c}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['overlay_count'] == 0
assert d['overlays'] == []
" || fail "empty overlay"
rm -rf "${dir}"
pass "6. empty overlay dir → overlay_count=0, capture still succeeds"

# ── 7. Nonexistent overlay dir → overlay_count=0 (graceful) ──
out_c="$(python3 "${SCRIPT}" capture --overlay-dir /no/such/dir --json)"
echo "${out_c}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['overlay_count'] == 0
" || fail "nonexistent"
pass "7. nonexistent overlay dir → graceful overlay_count=0"

# ── 8. captured_at is ISO-8601 UTC ─────────────────────────
dir=$(mk_overlay_dir)
out_c="$(python3 "${SCRIPT}" capture --overlay-dir "${dir}" --json)"
echo "${out_c}" | python3 -c "
import json, sys, re
d = json.loads(sys.stdin.read())
assert re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$', d['captured_at']), d['captured_at']
assert isinstance(d['captured_at_epoch'], (int, float))
assert 'host' in d
" || fail "captured_at format"
rm -rf "${dir}"
pass "8. captured_at is ISO-8601 UTC + epoch + host fields present"

# ── 9. --audit-tail flag overrides config ───────────────
dir=$(mk_overlay_dir)
out_a="$(python3 "${SCRIPT}" audit --overlay-dir "${dir}" --json)"
echo "${out_a}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['audit_tail_planned'] == 100, d
" || fail "default audit tail"
rm -rf "${dir}"
pass "9. audit_tail defaults to 100"

# ── 10. sovereign-osctl config-snapshot dispatch ──────────
dir=$(mk_overlay_dir)
out_disp="$(bash "${OSCTL}" config-snapshot audit --overlay-dir "${dir}" --json 2>/dev/null)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R332'
" || fail "osctl dispatch"
rm -rf "${dir}"
pass "10. sovereign-osctl config-snapshot dispatches"

echo "ALL OK"
