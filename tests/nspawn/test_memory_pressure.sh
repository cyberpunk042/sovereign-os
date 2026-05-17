#!/usr/bin/env bash
# tests/nspawn/test_memory_pressure.sh — R269 (E1.M15).
# Memory pressure + OOM watcher.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/memory-pressure.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_memory_pressure.sh"
echo

[ -x "${SCRIPT}" ] && ok "memory-pressure.py executable" \
  || { ko "missing"; exit 1; }
grep -q "R269\|E1.M15" "${SCRIPT}" && ok "script cites R269/E1.M15" \
  || ko "R269 missing"
grep -q "^  memory-pressure)" "${OSCTL}" \
  && ok "osctl bridges 'memory-pressure'" || ko "osctl dispatch missing"
grep -q "memory-pressure status" "${OSCTL}" \
  && ok "osctl help documents 'memory-pressure'" || ko "osctl help missing"

# ---- status --json: shape contract ----
set +e
out="$(python3 "${SCRIPT}" status --json 2>/dev/null)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "status --json rc ∈ {0,1} (got ${rc})"
else
  ko "rc unexpected ${rc}"
fi
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R269', d
assert d['vector'].startswith('E1.M15'), d
for f in ('psi_available','cgroup_v2_present','verdict','advisories','metrics','oom_journal_scan'):
    assert f in d, f'missing {f}'
assert d['verdict'] in ('ok','attention','critical','unavailable'), d
" \
  && ok "status --json: required fields + verdict enum constrained" \
  || ko "status shape wrong"

# ---- metrics include all the right keys ----
out="$(python3 "${SCRIPT}" status --json 2>/dev/null)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
m = d['metrics']
for k in ('mem_total_mb','mem_available_mb','mem_available_pct',
         'swap_total_mb','swap_used_mb','swap_used_pct',
         'psi_some_avg60_pct','psi_full_avg10_pct',
         'cgroup_oom_kill_count','journal_oom_event_count'):
    assert k in m, f'missing metric {k}'
" \
  && ok "metrics: 10 keys including mem/swap/PSI/cgroup_oom/journal" \
  || ko "metrics shape wrong"

# ---- psi --json: shape ----
set +e
out="$(python3 "${SCRIPT}" psi --json 2>/dev/null)"
set -e
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R269', d
assert 'available' in d
assert isinstance(d['psi'], dict)
" \
  && ok "psi --json: stable shape regardless of kernel version" \
  || ko "psi shape wrong"

# ---- oom-events --json: shape + count ----
set +e
out="$(python3 "${SCRIPT}" oom-events --json --lines 50 2>/dev/null)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "oom-events rc ∈ {0,1}"
else
  ko "oom-events rc unexpected ${rc}"
fi
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R269', d
assert 'available' in d and 'events' in d
" \
  && ok "oom-events --json: stable shape" \
  || ko "oom-events shape wrong"

# ---- verdict logic: in-process unit checks ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('mp','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# 4% available → critical
mi = {'MemTotal': 1024*1024, 'MemAvailable': 1024*40, 'SwapTotal': 0, 'SwapFree': 0}
r = m.derive_verdict(mi, None, {}, {'event_count':0})
assert r['verdict'] == 'critical', r

# 12% available → attention
mi = {'MemTotal': 1024*1024, 'MemAvailable': 1024*120, 'SwapTotal': 0, 'SwapFree': 0}
r = m.derive_verdict(mi, None, {}, {'event_count':0})
assert r['verdict'] == 'attention', r

# Healthy → ok
mi = {'MemTotal': 1024*1024, 'MemAvailable': 1024*800, 'SwapTotal': 0, 'SwapFree': 0}
r = m.derive_verdict(mi, None, {}, {'event_count':0})
assert r['verdict'] == 'ok', r

# PSI full.avg10 > 5 → critical
mi = {'MemTotal': 1024*1024, 'MemAvailable': 1024*800, 'SwapTotal': 0, 'SwapFree': 0}
psi = {'some': {'avg10':0,'avg60':0,'avg300':0,'total':0},
       'full': {'avg10':10.0,'avg60':2.0,'avg300':0.5,'total':100}}
r = m.derive_verdict(mi, psi, {}, {'event_count':0})
assert r['verdict'] == 'critical', r
assert any('PSI full.avg10' in a for a in r['advisories']), r

# Recent OOM kill (journalctl) → critical regardless of memory
r = m.derive_verdict(mi, None, {}, {'event_count':3})
assert r['verdict'] == 'critical', r
assert any('OOM-killer' in a for a in r['advisories']), r

# cgroup oom_kill > 0 → critical
r = m.derive_verdict(mi, None, {'events':{'oom_kill':1}}, {'event_count':0})
assert r['verdict'] == 'critical', r

# Swap >50% used → attention
mi_swap = {'MemTotal': 1024*1024, 'MemAvailable': 1024*800,
           'SwapTotal': 1024*1024, 'SwapFree': 1024*400}
r = m.derive_verdict(mi_swap, None, {}, {'event_count':0})
assert r['verdict'] == 'attention', r
assert any('swap' in a.lower() for a in r['advisories']), r
" \
  && ok "derive_verdict: 7 transition cases (critical/attention/ok/PSI/oom/cgroup/swap)" \
  || ko "verdict logic wrong"

# ---- parse_meminfo handles real /proc/meminfo ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('mp','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
mi = m.parse_meminfo()
assert 'MemTotal' in mi, mi
assert mi['MemTotal'] > 0
" \
  && ok "parse_meminfo: live /proc/meminfo extraction" \
  || ko "parse_meminfo broken"

# ---- human render: banner + verdict ----
out_h="$(python3 "${SCRIPT}" status 2>&1 || true)"
echo "${out_h}" | grep -q "R269 sovereign-os memory-pressure" \
  && ok "status human banner present" || ko "banner missing"
echo "${out_h}" | grep -q "verdict:" \
  && ok "status human shows verdict line" || ko "verdict line missing"

# ---- osctl bridge ----
TMP="$(mktemp -d -t r269.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
set +e
"${OSCTL}" memory-pressure status --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "osctl memory-pressure status rc ∈ {0,1}"
else
  ko "osctl rc=${rc}"
fi
python3 -c "
import json
d = json.load(open('${TMP}/osctl.out'))
assert d['round'] == 'R269', d
" \
  && ok "osctl bridge surfaces R269 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" memory-pressure nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown memory-pressure subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

echo
total=$((pass + fail))
echo "test_memory_pressure: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
