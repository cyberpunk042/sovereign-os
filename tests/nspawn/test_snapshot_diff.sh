#!/usr/bin/env bash
# R334 (E2.M25) — snapshot-diff verb L3.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/diagnostics/snapshot-diff.py"
SNAPSHOT="${REPO_ROOT}/scripts/diagnostics/state-snapshot.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# Build synthetic R322 snapshot via direct JSON crafting.
synth_snapshot() {
    local out="$1"
    local probes_json="$2"
    cat > "${out}" <<EOF
{
  "schema_version": "1.0.0",
  "round": "R322",
  "sdd_vector": "E2.M18",
  "snapshot_at": "2026-05-17T00:00:00Z",
  "snapshot_at_epoch": 1779000000.0,
  "snapshot_duration_ms": 100,
  "max_workers": 8,
  "per_probe_timeout_sec": 10,
  "probe_count": 0,
  "available_count": 0,
  "failed_count": 0,
  "probes": ${probes_json}
}
EOF
}

# ── 1. diff --json envelope ───────────────────────────────
a=$(mktemp); b=$(mktemp)
python3 "${SNAPSHOT}" snapshot --json > "${a}"
python3 "${SNAPSHOT}" snapshot --json > "${b}"
RC=0
out="$(python3 "${SCRIPT}" diff --before "${a}" --after "${b}" --json)" || RC=$?
[[ "${RC}" == "0" || "${RC}" == "1" ]] || fail "unexpected rc: ${RC}"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R334'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E2.M25'
for k in ('before_path', 'after_path', 'before_snapshot_at',
          'after_snapshot_at', 'diff'):
    assert k in d, k
" || fail "envelope"
rm -f "${a}" "${b}"
pass "1. diff --json envelope"

# ── 2. diff schema has 6 categories ───────────────────────
a=$(mktemp); b=$(mktemp)
synth_snapshot "${a}" '[{"name":"p1","axis":"x","rc":0,"output":{"verdict":"ok"}}]'
synth_snapshot "${b}" '[{"name":"p1","axis":"x","rc":0,"output":{"verdict":"ok"}}]'
out="$(python3 "${SCRIPT}" diff --before "${a}" --after "${b}" --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
df = d['diff']
for k in ('rc_changes', 'verdict_changes', 'new_attention',
          'resolved_attention', 'new_probes', 'removed_probes'):
    assert k in df, k
    assert isinstance(df[k], list)
" || fail "schema"
rm -f "${a}" "${b}"
pass "2. diff has 6 categories (rc_changes/verdict_changes/new_attention/resolved_attention/new_probes/removed_probes)"

# ── 3. rc=0→1 detected as rc_change AND new_attention ─────
a=$(mktemp); b=$(mktemp)
synth_snapshot "${a}" '[{"name":"p1","axis":"thermal","rc":0,"output":{"verdict":"safe"}}]'
synth_snapshot "${b}" '[{"name":"p1","axis":"thermal","rc":1,"output":{"verdict":"watch"}}]'
RC=0
out="$(python3 "${SCRIPT}" diff --before "${a}" --after "${b}" --json)" || RC=$?
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
df = d['diff']
assert len(df['rc_changes']) == 1
assert df['rc_changes'][0]['rc_before'] == 0
assert df['rc_changes'][0]['rc_after'] == 1
assert len(df['new_attention']) == 1
assert df['new_attention'][0]['probe'] == 'p1'
" || fail "rc 0→1"
[[ "${RC}" == "1" ]] || fail "rc 0→1 should give rc=1 (regression); got ${RC}"
rm -f "${a}" "${b}"
pass "3. rc=0→1 detected as rc_change + new_attention + diff rc=1"

# ── 4. rc=1→0 detected as resolved_attention ──────────────
a=$(mktemp); b=$(mktemp)
synth_snapshot "${a}" '[{"name":"p1","axis":"thermal","rc":1,"output":{"verdict":"watch"}}]'
synth_snapshot "${b}" '[{"name":"p1","axis":"thermal","rc":0,"output":{"verdict":"safe"}}]'
RC=0
out="$(python3 "${SCRIPT}" diff --before "${a}" --after "${b}" --json)" || RC=$?
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
df = d['diff']
assert len(df['resolved_attention']) == 1
assert df['resolved_attention'][0]['probe'] == 'p1'
assert df['new_attention'] == []
" || fail "rc 1→0"
[[ "${RC}" == "0" ]] || fail "rc 1→0 should give rc=0 (improvement); got ${RC}"
rm -f "${a}" "${b}"
pass "4. rc=1→0 detected as resolved_attention + diff rc=0"

# ── 5. verdict change detected when rc unchanged ──────────
a=$(mktemp); b=$(mktemp)
synth_snapshot "${a}" '[{"name":"p1","axis":"x","rc":1,"output":{"verdict":"watch"}}]'
synth_snapshot "${b}" '[{"name":"p1","axis":"x","rc":1,"output":{"verdict":"drift"}}]'
out="$(python3 "${SCRIPT}" diff --before "${a}" --after "${b}" --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
df = d['diff']
assert len(df['rc_changes']) == 0
assert len(df['verdict_changes']) == 1
assert df['verdict_changes'][0]['verdict_before'] == 'watch'
assert df['verdict_changes'][0]['verdict_after'] == 'drift'
" || fail "verdict change"
rm -f "${a}" "${b}"
pass "5. verdict change detected when rc unchanged"

# ── 6. new_probes / removed_probes catalog change ──────────
a=$(mktemp); b=$(mktemp)
synth_snapshot "${a}" '[{"name":"old","axis":"x","rc":0,"output":{"verdict":"ok"}}]'
synth_snapshot "${b}" '[{"name":"new","axis":"x","rc":0,"output":{"verdict":"ok"}}]'
out="$(python3 "${SCRIPT}" diff --before "${a}" --after "${b}" --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
df = d['diff']
assert df['new_probes'] == ['new']
assert df['removed_probes'] == ['old']
" || fail "catalog change"
rm -f "${a}" "${b}"
pass "6. new_probes/removed_probes correctly identified"

# ── 7. Identical snapshots → empty diff + rc=0 ────────────
a=$(mktemp); b=$(mktemp)
synth_snapshot "${a}" '[{"name":"p1","axis":"x","rc":0,"output":{"verdict":"ok"}}]'
synth_snapshot "${b}" '[{"name":"p1","axis":"x","rc":0,"output":{"verdict":"ok"}}]'
RC=0
out="$(python3 "${SCRIPT}" diff --before "${a}" --after "${b}" --json)" || RC=$?
[[ "${RC}" == "0" ]] || fail "identical snapshots should give rc=0; got ${RC}"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
df = d['diff']
for k in ('rc_changes', 'verdict_changes', 'new_attention',
          'resolved_attention', 'new_probes', 'removed_probes'):
    assert df[k] == [], (k, df[k])
" || fail "identical empty"
rm -f "${a}" "${b}"
pass "7. identical snapshots → empty diff + rc=0"

# ── 8. Non-R322 snapshot rejected with rc=2 ───────────────
bad=$(mktemp)
echo '{"round": "not-R322"}' > "${bad}"
b=$(mktemp)
synth_snapshot "${b}" '[]'
RC=0
python3 "${SCRIPT}" diff --before "${bad}" --after "${b}" --json 2>/dev/null || RC=$?
[[ "${RC}" == "2" ]] || fail "expected rc=2 for non-R322; got ${RC}"
rm -f "${bad}" "${b}"
pass "8. non-R322 snapshot rejected with rc=2 (round mismatch)"

# ── 9. Nonexistent snapshot file → rc=2 ──────────────────
b=$(mktemp); synth_snapshot "${b}" '[]'
RC=0
python3 "${SCRIPT}" diff --before /no/such/file --after "${b}" --json 2>/dev/null || RC=$?
[[ "${RC}" == "2" ]] || fail "expected rc=2 for missing file; got ${RC}"
rm -f "${b}"
pass "9. nonexistent snapshot file → rc=2"

# ── 10. sovereign-osctl snapshot-diff dispatch ────────────
a=$(mktemp); b=$(mktemp)
python3 "${SNAPSHOT}" snapshot --json > "${a}"
python3 "${SNAPSHOT}" snapshot --json > "${b}"
RC=0
out_disp="$(bash "${OSCTL}" snapshot-diff diff --before "${a}" --after "${b}" --json 2>/dev/null)" || RC=$?
[[ "${RC}" == "0" || "${RC}" == "1" ]] || fail "osctl rc unexpected: ${RC}"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R334'
" || fail "osctl dispatch"
rm -f "${a}" "${b}"
pass "10. sovereign-osctl snapshot-diff dispatches"

echo "ALL OK"
