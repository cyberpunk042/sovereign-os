#!/usr/bin/env bash
# R319 (E3.M7) — network runtime-stack advisor L3.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/network/runtime-stack-advisor.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. list --json envelope + 5 default services ──────────
out="$(python3 "${SCRIPT}" list --json)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R319'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E3.M7'
assert d['total_count'] == 5
" || fail "envelope"
pass "1. list --json envelope + 5 default services"

# ── 2. All 5 operator-named services present ──────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
names = {s['name'] for s in d['services']}
must = {'tailscale', 'cloudflared', 'traefik', 'systemd-resolved', 'suricata'}
assert names == must, names
" || fail "anchors"
pass "2. all 5 operator-named services (tailscale/cloudflared/traefik/systemd-resolved/suricata)"

# ── 3. Every service has full schema ────────────────────────
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
for s in d['services']:
    for k in ('name', 'axis', 'unit', 'binary', 'config_path',
              'troubleshoot'):
        assert k in s, (k, s['name'])
    assert isinstance(s['troubleshoot'], list)
    assert len(s['troubleshoot']) >= 4
" || fail "schema"
pass "3. every service has full schema (axis/unit/binary/config_path/troubleshoot≥4 steps)"

# ── 4. --axis filter narrows ───────────────────────────────
out_t="$(python3 "${SCRIPT}" list --axis tunnel --json)"
echo "${out_t}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert all(s['axis'] == 'tunnel' for s in d['services'])
assert d['filtered_count'] == 2  # tailscale + cloudflared
" || fail "axis filter"
pass "4. --axis tunnel filter narrows (tailscale + cloudflared)"

# ── 5. status verb probes every service ────────────────────
RC=0
out_s="$(python3 "${SCRIPT}" status --json)" || RC=$?
echo "${out_s}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R319'
assert len(d['probes']) == 5
for p in d['probes']:
    for k in ('name', 'axis', 'unit', 'installed', 'running',
              'healthy', 'detail'):
        assert k in p
" || fail "status shape"
pass "5. status verb probes all 5 services + per-probe shape"

# ── 6. probe_service handles missing binary gracefully ──
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('n', 'scripts/network/runtime-stack-advisor.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
synthetic = {
    'name': 'nonexistent-svc',
    'unit': 'nonexistent.service',
    'binary': 'definitely-not-a-binary-xyz',
}
r = m.probe_service(synthetic)
# Binary not found → installed = False
assert r['installed'] is False
# Healthy = installed AND running; either False → healthy = False
assert r['healthy'] is False
print('PASS')
" || fail "probe missing"
pass "6. probe_service gracefully handles missing binary + service"

# ── 7. aggregate verdict matrix ────────────────────────────
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('n', 'scripts/network/runtime-stack-advisor.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# All healthy → ok
probes_ok = [
    {'healthy': True}, {'healthy': True}, {'healthy': True},
]
v, rc, c = m.aggregate(probes_ok)
assert v == 'ok' and rc == 0, (v, rc)
assert c['healthy'] == 3
# Any unhealthy → degraded
probes_mix = [
    {'healthy': True}, {'healthy': False}, {'healthy': None},
]
v, rc, c = m.aggregate(probes_mix)
assert v == 'degraded' and rc == 1
assert c['healthy'] == 1 and c['unhealthy'] == 1 and c['unprobed'] == 1
print('PASS')
" || fail "aggregate"
pass "7. aggregate verdict: all-healthy=ok / any-unhealthy=degraded"

# ── 8. troubleshoot <service> renders 4-7 diagnostic steps ──
out_tb="$(python3 "${SCRIPT}" troubleshoot tailscale --json)"
echo "${out_tb}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
s = d['service']
assert s['name'] == 'tailscale'
assert s['axis'] == 'tunnel'
assert len(s['troubleshoot']) >= 4
# Operator-runnable: contains 'systemctl' + 'tailscale'.
joined = ' '.join(s['troubleshoot'])
assert 'systemctl' in joined
assert 'tailscale' in joined
" || fail "troubleshoot shape"
pass "8. troubleshoot tailscale renders ≥4 operator-runnable steps"

# ── 9. Unknown service → rc=1 + structured error ──────────
RC=0
python3 "${SCRIPT}" troubleshoot no-such-svc --json 2>/dev/null || RC=$?
[[ "${RC}" == "1" ]] || fail "unknown service rc expected 1; got ${RC}"
pass "9. troubleshoot unknown service → rc=1 + structured error"

# ── 10. sovereign-osctl network-stack dispatch ─────────────
out_disp="$(bash "${OSCTL}" network-stack list --json 2>/dev/null)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R319'
assert d['total_count'] == 5
" || fail "sovereign-osctl dispatch"
pass "10. sovereign-osctl network-stack dispatches"

echo "ALL OK"
