#!/usr/bin/env bash
# tests/nspawn/test_net_perf_baseline.sh — R276 (E3.M6).
# Network perf baseline + drift detection.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/network/perf-baseline.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_net_perf_baseline.sh"
echo

[ -x "${SCRIPT}" ] && ok "perf-baseline.py executable" \
  || { ko "missing"; exit 1; }
grep -q "R276\|E3.M6" "${SCRIPT}" && ok "script cites R276/E3.M6" \
  || ko "R276 missing"
grep -q "^  net-perf)" "${OSCTL}" \
  && ok "osctl bridges 'net-perf'" || ko "osctl dispatch missing"

TMP="$(mktemp -d -t r276.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
export SOVEREIGN_OS_NETWORK_BASELINE="${TMP}/state.json"

# ---- probe --json: 4 default targets + measurement shape ----
out="$(python3 "${SCRIPT}" probe --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R276', d
assert d['vector'].startswith('E3.M6'), d
assert len(d['targets']) == 4, d
for t in d['targets']:
    assert 'name' in t and 'kind' in t and 'measurement' in t
    assert t['kind'] in ('ping','dns','https'), t
" \
  && ok "probe --json: 4 default targets with kind enum" \
  || ko "probe shape wrong"

# ---- drift before any record → no-data ----
out="$(python3 "${SCRIPT}" drift --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['verdict'] == 'no-data', d
" \
  && ok "drift before record → verdict=no-data" \
  || ko "no-data path wrong"

# ---- record: persists samples + baselines ----
out="$(python3 "${SCRIPT}" record --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R276', d
assert d['sample_count'] == 1, d
# baseline_count >= 0 (depends on CI ping/dig availability).
assert d['baseline_count'] >= 0, d
" \
  && ok "record --json: persists sample to state file" \
  || ko "record shape wrong"

# State file actually exists with right shape
python3 -c "
import json
d = json.load(open('${TMP}/state.json'))
assert d['version'] == 1, d
assert len(d['samples']) == 1, d
assert isinstance(d['baselines'], dict), d
" \
  && ok "state file written with version + samples + baselines" \
  || ko "state file shape wrong"

# ---- parse_targets logic ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('pb','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# 'ping:1.1.1.1' → 1 target
r = m.parse_targets('ping:1.1.1.1')
assert r is not None and len(r) == 1
assert r[0]['kind'] == 'ping' and r[0]['target'] == '1.1.1.1'
# 'dns:9.9.9.9:example.com' → 1 dns target
r = m.parse_targets('dns:9.9.9.9:example.com')
assert r[0]['kind'] == 'dns'
assert r[0]['target'] == '9.9.9.9'
assert r[0]['host'] == 'example.com'
# 'https://...' parses to https
r = m.parse_targets('https:https://1.1.1.1')
assert r[0]['kind'] == 'https'
assert r[0]['target'] == 'https://1.1.1.1'
# Empty → None
assert m.parse_targets(None) is None
assert m.parse_targets('') is None
" \
  && ok "parse_targets: ping/dns/https syntax + empty fallback" \
  || ko "parse_targets wrong"

# ---- drift logic in-process: synthetic baseline + drifting latest ----
python3 -c "
import importlib.util, json as j, time
spec = importlib.util.spec_from_file_location('pb','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

state = {
    'version': 1,
    'baselines': {
        'sample-1': {'measured_at': '2026-05-17T00:00:00Z',
                     'avg_ms': 10.0, 'loss_pct': 0.0},
        'sample-2': {'measured_at': '2026-05-17T00:00:00Z',
                     'avg_ms': 20.0, 'loss_pct': 0.0},
    },
    'samples': [{
        'measured_at': '2026-05-17T00:00:00Z',
        'targets': [
            {'name':'sample-1','kind':'ping','target':'x',
             'measurement': {'ok':True, 'avg_ms':10.0, 'loss_pct':0.0}},
            {'name':'sample-2','kind':'ping','target':'y',
             'measurement': {'ok':True, 'avg_ms':20.0, 'loss_pct':0.0}},
        ],
    }, {
        # Latest: sample-1 went from 10 → 15 ms (+50%, drifting)
        # sample-2 stayed at 21 ms (+5%, within threshold)
        'measured_at': '2026-05-17T01:00:00Z',
        'targets': [
            {'name':'sample-1','kind':'ping','target':'x',
             'measurement': {'ok':True, 'avg_ms':15.0, 'loss_pct':0.0}},
            {'name':'sample-2','kind':'ping','target':'y',
             'measurement': {'ok':True, 'avg_ms':21.0, 'loss_pct':0.0}},
        ],
    }],
}
m.save_state(m.Path('${TMP}/synth-state.json'), state)

import os
os.environ['SOVEREIGN_OS_NETWORK_BASELINE'] = '${TMP}/synth-state.json'

import argparse
args = argparse.Namespace(threshold_pct=25.0, json=True)
import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = m.cmd_drift(args)
report = j.loads(buf.getvalue())
# rc=1 because sample-1 drifted
assert rc == 1, report
assert report['verdict'] == 'drifting', report
assert report['drift_count'] == 1, report
d = report['drifts'][0]
assert d['name'] == 'sample-1', d
assert d['direction'] == 'slower', d
assert d['delta_pct'] == 50.0, d
" \
  && ok "drift logic: sample-1 +50% triggers drift, sample-2 +5% within ±25%" \
  || ko "drift logic wrong"

# ---- threshold above delta → no drift ----
python3 -c "
import importlib.util, os, argparse, io, contextlib, json as j
os.environ['SOVEREIGN_OS_NETWORK_BASELINE'] = '${TMP}/synth-state.json'
spec = importlib.util.spec_from_file_location('pb','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
args = argparse.Namespace(threshold_pct=75.0, json=True)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = m.cmd_drift(args)
report = j.loads(buf.getvalue())
assert rc == 0, report
assert report['verdict'] == 'stable', report
" \
  && ok "threshold 75% above 50% delta → verdict=stable" \
  || ko "stable verdict wrong"

# ---- osctl bridge ----
set +e
"${OSCTL}" net-perf drift --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "osctl net-perf drift rc ∈ {0,1}"
else
  ko "osctl bridge rc=${rc}"
fi
python3 -c "
import json
d = json.load(open('${TMP}/osctl.out'))
assert d['round'] == 'R276', d
" \
  && ok "osctl bridge surfaces R276 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" net-perf nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown net-perf subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

# ---- human render: banner ----
out_h="$(python3 "${SCRIPT}" probe 2>&1)"
echo "${out_h}" | grep -q "R276 sovereign-os network-perf-baseline probe" \
  && ok "probe human banner present" || ko "banner missing"

echo
total=$((pass + fail))
echo "test_net_perf_baseline: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
