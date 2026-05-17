#!/usr/bin/env bash
# R298 (E2.M12) — unified storage health rollup L3.
#
# Operator-named (§1b mandate row): "logs, log rotate, system usage,
# partitions and global and such. insights".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/hardware/storage-health-rollup.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. status --json envelope ────────────────────────────────
out="$(python3 "${SCRIPT}" status --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R298'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E2.M12'
for k in ('axes', 'inputs', 'verdict', 'rc', 'config'):
    assert k in d, k
" || fail "envelope"
pass "1. status --json envelope"

# ── 2. All 4 axes present with verdict + detail ──────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
axes = d['axes']
for axis in ('logrotate', 'raid', 'partitions', 'journal'):
    assert axis in axes, axis
    assert 'verdict' in axes[axis]
    assert 'detail' in axes[axis]
" || fail "axes shape"
pass "2. logrotate + raid + partitions + journal axes all present"

# ── 3. Combined verdict is one of the expected outcomes ──────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['verdict'] in ('healthy', 'watch', 'degraded'), d['verdict']
assert d['rc'] in (0, 1, 2), d['rc']
" || fail "combined verdict"
pass "3. combined verdict ∈ {healthy, watch, degraded}"

# ── 4. Verdict severity matches axis severity ────────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# If any axis is 'critical', combined must be 'degraded' (rc=2).
crit = [k for k, v in d['axes'].items() if v['verdict'] == 'critical']
if crit:
    assert d['verdict'] == 'degraded', (crit, d['verdict'])
    assert d['rc'] == 2
# If no critical but ≥1 warn, must be 'watch' (rc=1).
warns = [k for k, v in d['axes'].items() if v['verdict'] == 'warn']
if not crit and warns:
    assert d['verdict'] == 'watch', (warns, d['verdict'])
" || fail "verdict-severity correspondence"
pass "4. combined verdict severity matches highest axis severity"

# ── 5. operator overlay controls thresholds ────────────────────
overlay="$(mktemp --suffix=.toml)"
cat > "${overlay}" <<'TOML'
partition_free_warn_pct      = 50
partition_free_critical_pct  = 25
journal_warn_pct             = 50
journal_critical_pct         = 70
logrotate_warn_days          = 7
logrotate_critical_days      = 14
TOML

out_ov="$(python3 "${SCRIPT}" status --config "${overlay}" --json || true)"
echo "${out_ov}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
cfg = d['config']
assert cfg['partition_free_warn_pct'] == 50
assert cfg['logrotate_warn_days'] == 7
assert cfg['journal_critical_pct'] == 70
" || fail "overlay knob takeover"
rm -f "${overlay}"
pass "5. operator overlay (R283/SDD-030) controls thresholds"

# ── 6. Malformed overlay → defaults + _parse_error ──────────
bad="$(mktemp --suffix=.toml)"
echo "this is not toml [[[[ }}}}" > "${bad}"
out_bad="$(python3 "${SCRIPT}" status --config "${bad}" --json || true)"
echo "${out_bad}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['config']['partition_free_warn_pct'] == 15
assert '_parse_error' in d['overlay']
" || fail "malformed-overlay fallback"
rm -f "${bad}"
pass "6. malformed overlay → defaults + _parse_error"

# ── 7. inputs verb surfaces raw probe data ────────────────
out_in="$(python3 "${SCRIPT}" inputs --json || true)"
echo "${out_in}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
inp = d['inputs']
for k in ('logrotate', 'raid', 'partitions', 'journal'):
    assert k in inp, k
" || fail "inputs shape"
pass "7. inputs verb surfaces all 4 raw probes"

# ── 8. advisory carries verdict + axes_summary ──────────────
out_adv="$(python3 "${SCRIPT}" advisory --json || true)"
echo "${out_adv}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R298'
assert d['verdict'] in ('healthy', 'watch', 'degraded')
assert isinstance(d['axes_summary'], dict)
assert set(d['axes_summary'].keys()) == {'logrotate', 'raid', 'partitions', 'journal'}
" || fail "advisory shape"
pass "8. advisory carries verdict + axes_summary"

# ── 9. Pseudo-fs are skipped from partitions probe ──────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
parts = d['inputs']['partitions']
for p in parts:
    assert p['fstype'] not in ('tmpfs', 'devtmpfs', 'proc', 'sysfs'), p
" || fail "pseudo-fs filtered"
pass "9. pseudo-fs (tmpfs/proc/sysfs) filtered from partitions"

# ── 10. sovereign-osctl storage-health dispatch + read-only ──
out_disp="$(bash "${OSCTL}" storage-health status --json || true)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R298'
" || fail "sovereign-osctl dispatch"
pass "10. sovereign-osctl storage-health dispatches"

echo "ALL OK"
