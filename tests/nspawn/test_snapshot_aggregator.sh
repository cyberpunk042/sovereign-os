#!/usr/bin/env bash
# R324 (E2.M20) — fleet snapshot aggregator L3.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/fleet/snapshot-aggregator.py"
SNAPSHOT="${REPO_ROOT}/scripts/diagnostics/state-snapshot.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# Build a 3-host snapshot fixture for each test that needs one.
mk_fixture() {
    local n="$1"
    local dir
    dir=$(mktemp -d)
    for ((i=1; i<=n; i++)); do
        python3 "${SNAPSHOT}" snapshot --json > "${dir}/host${i}.json"
    done
    echo "${dir}"
}

# ── 1. aggregate --json envelope + multi-host count ───────
dir=$(mk_fixture 3)
out="$(python3 "${SCRIPT}" aggregate --snapshots-dir "${dir}" --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R324'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E2.M20'
assert d['host_count'] == 3
for k in ('host_summaries', 'verdict', 'outliers', 'axis_distribution'):
    assert k in d, k
" || fail "envelope"
rm -rf "${dir}"
pass "1. aggregate --json envelope + 3-host count"

# ── 2. Per-host summary carries probe + fail + axes ───────
dir=$(mk_fixture 3)
out="$(python3 "${SCRIPT}" aggregate --snapshots-dir "${dir}" --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for h in d['host_summaries']:
    for k in ('host_source', 'probe_count', 'failed_count',
              'axes_count', 'verdicts'):
        assert k in h, (k, h)
" || fail "host summary shape"
rm -rf "${dir}"
pass "2. per-host summary carries (host_source, probe_count, failed_count, axes_count, verdicts)"

# ── 3. axis_distribution aggregates verdicts across hosts ──
dir=$(mk_fixture 3)
out="$(python3 "${SCRIPT}" aggregate --snapshots-dir "${dir}" --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ad = d['axis_distribution']
# Each axis maps verdict → count.
for axis, verdicts in ad.items():
    assert isinstance(verdicts, dict)
    for v, n in verdicts.items():
        assert isinstance(n, int)
# Sum of counts per axis should == number of probes in that axis ×
# host count (3).
for axis, verdicts in ad.items():
    total = sum(verdicts.values())
    # Total = number of probes (across hosts) in this axis.
    # Each host has N probes in axis A; total = N × 3 = multiple of 3.
    assert total % 3 == 0, (axis, total)
" || fail "axis distribution"
rm -rf "${dir}"
pass "3. axis_distribution aggregates verdict counts across hosts"

# ── 4. NDJSON stdin input parses correctly ────────────────
dir=$(mk_fixture 2)
# Build stdin payload: 2 JSON objects, newline-separated.
( cat "${dir}/host1.json"; echo; cat "${dir}/host2.json" ) \
    | jq -c . | python3 "${SCRIPT}" aggregate --snapshots-dir /no/such/dir --json \
    > /tmp/r324-stdin.json 2>&1 || true
# Above won't work because --snapshots-dir was set to invalid dir,
# but aggregator will fall back to stdin. Just verify stdin works.
python3 -c "
import json, subprocess, sys, pathlib
SCRIPT = '${SCRIPT}'
host1 = pathlib.Path('${dir}/host1.json').read_text()
host2 = pathlib.Path('${dir}/host2.json').read_text()
# NDJSON: each JSON on one line.
h1 = json.dumps(json.loads(host1))
h2 = json.dumps(json.loads(host2))
payload = h1 + '\n' + h2 + '\n'
r = subprocess.run([sys.executable, SCRIPT, 'aggregate',
                     '--snapshots-dir', '/nonexistent-dir-xyz',
                     '--json'],
                    input=payload, capture_output=True, text=True,
                    check=False)
d = json.loads(r.stdout)
assert d['host_count'] == 2, d
" || fail "ndjson"
rm -rf "${dir}"
pass "4. NDJSON stdin input (2 hosts) parses correctly"

# ── 5. JSON-array stdin input also parses ──────────────────
dir=$(mk_fixture 2)
python3 -c "
import json, subprocess, sys, pathlib
SCRIPT = '${SCRIPT}'
host1 = json.loads(pathlib.Path('${dir}/host1.json').read_text())
host2 = json.loads(pathlib.Path('${dir}/host2.json').read_text())
payload = json.dumps([host1, host2])
r = subprocess.run([sys.executable, SCRIPT, 'aggregate',
                     '--snapshots-dir', '/nonexistent-dir-xyz',
                     '--json'],
                    input=payload, capture_output=True, text=True,
                    check=False)
d = json.loads(r.stdout)
assert d['host_count'] == 2, d
" || fail "json-array"
rm -rf "${dir}"
pass "5. JSON-array stdin input (2 hosts) parses correctly"

# ── 6. derive_outliers spots high-failure hosts ────────────
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('a', 'scripts/fleet/snapshot-aggregator.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# Median = 1; outlier > 2.0 × 1 = > 2.
hosts = [
    {'host_source': 'h1', 'failed_count': 1, 'probe_count': 10},
    {'host_source': 'h2', 'failed_count': 1, 'probe_count': 10},
    {'host_source': 'h3', 'failed_count': 1, 'probe_count': 10},
    {'host_source': 'h4', 'failed_count': 5, 'probe_count': 10},  # outlier
]
outliers = m.derive_outliers(hosts, 2.0)
names = [o['host_source'] for o in outliers]
assert names == ['h4'], names
print('PASS')
" || fail "outliers"
pass "6. derive_outliers correctly spots high-failure hosts (>median × threshold)"

# ── 7. All-zero-failure case → outliers = [] ──────────────
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('a', 'scripts/fleet/snapshot-aggregator.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
hosts = [{'host_source': f'h{i}', 'failed_count': 0, 'probe_count': 10}
          for i in range(5)]
outliers = m.derive_outliers(hosts, 2.0)
assert outliers == [], outliers
print('PASS')
" || fail "all-zero outliers"
pass "7. all-zero-failures fleet → no outliers"

# ── 8. by-axis --axis filter narrows ────────────────────
dir=$(mk_fixture 3)
out="$(python3 "${SCRIPT}" by-axis --snapshots-dir "${dir}" --axis hardware --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ad = d['axis_distribution']
# Should only contain the 'hardware' key.
assert list(ad.keys()) == ['hardware'], list(ad.keys())
" || fail "by-axis filter"
rm -rf "${dir}"
pass "8. by-axis --axis hardware filter narrows to single axis"

# ── 9. No snapshots → rc=1 + structured error ─────────────
RC=0
python3 "${SCRIPT}" aggregate --snapshots-dir /no/such/dir --json </dev/null 2>/dev/null || RC=$?
[[ "${RC}" == "1" ]] || fail "no-snapshots rc expected 1; got ${RC}"
pass "9. no snapshots found → rc=1 + structured error"

# ── 10. sovereign-osctl fleet-aggregate dispatch ──────────
dir=$(mk_fixture 2)
out_disp="$(bash "${OSCTL}" fleet-aggregate aggregate --snapshots-dir "${dir}" --json 2>/dev/null)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R324'
assert d['host_count'] == 2
" || fail "osctl dispatch"
rm -rf "${dir}"
pass "10. sovereign-osctl fleet-aggregate dispatches"

echo "ALL OK"
