#!/usr/bin/env bash
# R358 (E1.M42) — state-fabric layout / verify / scaffold L3.
# Operator-verbatim master spec §7.1 + §7.2 — /goal NO MINIMIZING /
# NO REPHRASING enforced at push-time via 11 specific phrase assertions.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SF="${REPO_ROOT}/scripts/hardware/state-fabric.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. layout returns the 4-file §7.1 matrix with full schema ───────
out="$(python3 "${SF}" layout --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert len(d['files']) == 4
names = {f['filename'] for f in d['files']}
# Exact operator-named filenames from §7.1
for must in ('IDENTITY.md', 'SOUL.md', 'AGENTS.md', 'CLAUDE.md'):
    assert must in names, f'missing §7.1 file: {must}'
for f in d['files']:
    for k in ('filename','role_verbatim','intended_mode','intent_axis',
             'writer','readers','spec_ref'):
        assert k in f, (k, f)
" || fail "layout schema"
pass "1. layout returns exact 4-file §7.1 matrix (IDENTITY/SOUL/AGENTS/CLAUDE)"

# ── 2. role_verbatim text preserves operator-VERBATIM §7.1 intent ──
out="$(python3 "${SF}" layout --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
by_name = {f['filename']: f for f in d['files']}
# §7.1 operator-verbatim role text — exact phrases MUST appear
assert 'Immutable System Persona' in by_name['IDENTITY.md']['role_verbatim']
assert 'Read-Only to Agents' in by_name['IDENTITY.md']['role_verbatim']
assert 'Core Behavioral Logic' in by_name['SOUL.md']['role_verbatim']
assert 'Dynamic Long-Term Memory' in by_name['SOUL.md']['role_verbatim']
assert 'Read-Write via Manager' in by_name['SOUL.md']['role_verbatim']
assert 'Routing Table' in by_name['AGENTS.md']['role_verbatim']
assert 'Hardware Pinning Map' in by_name['AGENTS.md']['role_verbatim']
assert 'Read-Only to Sub-Agents' in by_name['AGENTS.md']['role_verbatim']
assert 'Active Session Context' in by_name['CLAUDE.md']['role_verbatim']
assert 'Atomic Append-Only' in by_name['CLAUDE.md']['role_verbatim']
" || fail "verbatim §7.1"
pass "2. role_verbatim preserves §7.1 operator-exact phrases (10 phrases × 4 files)"

# ── 3. §7.2 ZFS properties carry verbatim values + commands ─────────
out="$(python3 "${SF}" layout --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
props = {p['property']: p for p in d['zfs_properties']}
# Operator-verbatim §7.2 values — must be exact
assert props['sync']['value'] == 'always'
assert props['primarycache']['value'] == 'all'
assert props['logbias']['value'] == 'latency'
# Operator-verbatim §7.2 commands — must be exact
assert props['sync']['command'] == 'zfs set sync=always tank/context'
assert props['primarycache']['command'] == 'zfs set primarycache=all tank/context'
assert props['logbias']['command'] == 'zfs set logbias=latency tank/context'
" || fail "§7.2 verbatim"
pass "3. §7.2 zfs_properties verbatim: sync=always / primarycache=all / logbias=latency (3 props × value + command)"

# ── 4. sync=always rationale preserves operator-verbatim phrase ─────
out="$(python3 "${SF}" layout --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
sync = next(p for p in d['zfs_properties'] if p['property'] == 'sync')
# §7.2 verbatim rationale phrases
must = [
    'synchronous writes',
    'physically committed to the NVMe',
    \"agent's state change\",
]
for phrase in must:
    assert phrase in sync['rationale'], f'missing §7.2 verbatim: {phrase!r}'
" || fail "sync rationale"
pass "4. §7.2 sync=always rationale preserves operator-verbatim physical-commit phrasing (3 phrases)"

# ── 5. verify NEVER-raises on container (no ZFS, no /mnt/vault) ─────
empty=$(mktemp -d)
rc=0; out="$(python3 "${SF}" verify --root "${empty}" --json 2>&1)" || rc=$?
[[ "${rc}" == 0 || "${rc}" == 1 ]] || fail "verify rc=${rc}"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# dataset_exists=false on container; total_drift counts missing files
assert d['zfs']['dataset_exists'] is False
assert d['files']['missing_count'] == 4  # nothing in empty dir
" || fail "verify schema"
rm -rf "${empty}"
pass "5. verify NEVER-raises on container; dataset_exists=false; 4 files missing"

# ── 6. verify detects file presence + mode drift via --root ─────────
tmp=$(mktemp -d)
touch "${tmp}/IDENTITY.md" "${tmp}/SOUL.md" "${tmp}/AGENTS.md" "${tmp}/CLAUDE.md"
chmod 0400 "${tmp}/IDENTITY.md" "${tmp}/AGENTS.md"
chmod 0644 "${tmp}/SOUL.md" "${tmp}/CLAUDE.md"
out="$(python3 "${SF}" verify --root "${tmp}" --json 2>&1 || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# All 4 files present with correct modes → no file drift
assert d['files']['missing_count'] == 0
assert d['files']['mode_drift_count'] == 0
" || fail "verify happy path"
# Now drift IDENTITY.md mode
chmod 0644 "${tmp}/IDENTITY.md"
out="$(python3 "${SF}" verify --root "${tmp}" --json 2>&1 || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# IDENTITY.md should now be drifted (0o644 != 0o400)
identity = next(r for r in d['files']['file_rows'] if r['filename'] == 'IDENTITY.md')
assert identity['drifted'] is True
assert identity['actual_mode'] == '0o644'
assert identity['intended_mode'] == '0o400'
assert 'chmod 400' in identity['remediation']
" || fail "verify drift"
rm -rf "${tmp}"
pass "6. verify detects mode drift (IDENTITY.md 0o644 → drifted; remediation = chmod 400)"

# ── 7. scaffold emits operator-runnable bootstrap commands ──────────
out="$(python3 "${SF}" scaffold --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
cmds = d['commands']
assert d['command_count'] >= 12  # 2 dataset + 3 zfs + 8 file (4×touch + 4×chmod)
joined = ' | '.join(cmds)
assert 'zfs create tank/context' in joined
assert 'zfs set sync=always tank/context' in joined
assert 'zfs set primarycache=all tank/context' in joined
assert 'zfs set logbias=latency tank/context' in joined
for f in ('IDENTITY.md','SOUL.md','AGENTS.md','CLAUDE.md'):
    assert f'touch /mnt/vault/context/{f}' in joined
" || fail "scaffold"
pass "7. scaffold emits ≥12 operator-runnable cmds (zfs create + 3 §7.2 props + 4×touch + 4×chmod)"

# ── 8. scaffold note warns it does NOT execute ──────────────────────
out="$(python3 "${SF}" scaffold --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'does NOT execute' in d['note']
assert 'SOVEREIGN_OS_CONFIRM_DESTROY' in d['note']
" || fail "scaffold note"
pass "8. scaffold note documents 'does NOT execute' + triple-gate confirmation"

# ── 9. operator-overlay replaces dataset + mountpoint + files ───────
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
dataset = "alt/state-pool"
mountpoint = "/srv/alt/context"
[[files]]
filename = "CUSTOM.md"
role_verbatim = "operator overlay test file"
intended_mode = "0o600"
intent_axis = "test-only"
writer = "tests"
readers = "operator"
spec_ref = "overlay 2026-05-18"
TOML
out="$(python3 "${SF}" layout --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['dataset'] == 'alt/state-pool'
assert d['mountpoint'] == '/srv/alt/context'
assert len(d['files']) == 1  # lists-replace per SDD-030
assert d['files'][0]['filename'] == 'CUSTOM.md'
" || fail "overlay"
rm -f "${cfg}"
pass "9. operator-overlay replaces dataset + mountpoint + files (R283/SDD-030)"

# ── 10. sovereign-osctl state-fabric dispatches all 3 subverbs ──────
"${OSCTL}" state-fabric layout --json >/dev/null 2>&1 || fail "osctl layout"
"${OSCTL}" state-fabric verify --json >/dev/null 2>&1 && true  # rc 0 or 1 OK
"${OSCTL}" state-fabric scaffold --json >/dev/null 2>&1 || fail "osctl scaffold"
pass "10. sovereign-osctl state-fabric dispatches layout/verify/scaffold"

# ── 11. each §7.1 file's spec_ref points back to master spec §7.1 ──
out="$(python3 "${SF}" layout --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for f in d['files']:
    assert 'master spec §7.1' in f['spec_ref'], f
for p in d['zfs_properties']:
    assert 'master spec §7.2' in p['spec_ref'], p
" || fail "spec_ref"
pass "11. all 4 files + 3 props cite master spec §7.1 / §7.2 in spec_ref"

# ── 12. atomic-state.py reference preserved for CLAUDE.md / SOUL.md
out="$(python3 "${SF}" layout --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
by_name = {f['filename']: f for f in d['files']}
# CLAUDE.md writer is the Weaver atomic writer (R154 → scripts/weaver/atomic-state.py)
assert 'atomic-state.py' in by_name['CLAUDE.md']['writer']
# SOUL.md writer references §21 atomic-state path
assert '§21' in by_name['SOUL.md']['writer'] or 'atomic-state' in by_name['SOUL.md']['writer']
" || fail "atomic-state link"
pass "12. CLAUDE.md / SOUL.md writers reference Weaver atomic-state.py (R154 / §21 cross-ref)"

echo "ALL OK"
