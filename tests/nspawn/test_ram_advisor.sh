#!/usr/bin/env bash
# tests/nspawn/test_ram_advisor.sh — R279 (E1.M16).
# 256 GB DDR5 RAM advisor with master-spec ZFS ARC clamp +
# GGUF context budget.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/ram-advisor.py"
EXAMPLE="${__REPO_ROOT}/config/ram.toml.example"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_ram_advisor.sh"
echo

[ -x "${SCRIPT}" ] && ok "ram-advisor.py executable" \
  || { ko "missing"; exit 1; }
[ -f "${EXAMPLE}" ] && ok "config/ram.toml.example shipped" \
  || ko "example missing"
grep -q "R279\|E1.M16" "${SCRIPT}" && ok "script cites R279/E1.M16" \
  || ko "R279 missing"
grep -q "^  ram-advisor)" "${OSCTL}" \
  && ok "osctl bridges 'ram-advisor'" || ko "osctl dispatch missing"

# Example config carries operator-named master-spec defaults.
grep -q "expected_total_gib = 256" "${EXAMPLE}" \
  && ok "example: expected_total_gib=256" || ko "256 missing"
grep -q "arc_max_gib = 128" "${EXAMPLE}" \
  && ok "example: arc_max_gib=128 (master-spec §19 clamp)" || ko "ARC clamp missing"
grep -q "gguf_context_max_gib = 64" "${EXAMPLE}" \
  && ok "example: gguf_context_max_gib=64" || ko "GGUF ceiling missing"

TMP="$(mktemp -d -t r279.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT

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
assert d['round'] == 'R279', d
assert d['vector'].startswith('E1.M16'), d
for f in ('verdict','advisories','metrics','config_source'):
    assert f in d, f'missing {f}'
assert d['verdict'] in ('ok','attention','critical'), d
m = d['metrics']
for k in ('expected_total_gib','live_total_gib','arc_max_gib_cfg',
         'gguf_context_max_gib','non_ai_headroom_gib'):
    assert k in m, f'missing metric {k}'
" \
  && ok "status --json: required fields + verdict enum + 5 metric keys" \
  || ko "status shape wrong"

# ---- budget --json ----
out="$(python3 "${SCRIPT}" budget --json 2>/dev/null || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R279', d
m = d['metrics']
assert m['non_ai_headroom_gib'] >= 0, m
" \
  && ok "budget --json: non_ai_headroom_gib >= 0" \
  || ko "budget shape wrong"

# ---- advisory --json ----
out="$(python3 "${SCRIPT}" advisory --json 2>/dev/null || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R279', d
assert d['verdict'] in ('ok','attention','critical'), d
assert isinstance(d['advisories'], list)
" \
  && ok "advisory --json shape" \
  || ko "advisory shape wrong"

# ---- in-process: verdict transitions ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('ra','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

KB_PER_GIB = 1024 * 1024

# Healthy: 256 GiB total, ZFS not loaded, no GGUF over-commit.
cfg = {'expected_total_gib': 256, 'arc_max_gib': 128, 'gguf_context_max_gib': 64}
mi = {'MemTotal': 256 * KB_PER_GIB, 'MemAvailable': 200 * KB_PER_GIB}
arc = {'arc_module_loaded': False, 'arc_max_bytes': None, 'arc_size_bytes': None}
r = m.derive_verdict(cfg, mi, arc)
# 'attention' OR 'ok' (advisory mentions ZFS not loaded but not critical).
assert r['verdict'] in ('ok','attention'), r
# Non-AI headroom = 256 - 128 - 64 = 64
assert r['metrics']['non_ai_headroom_gib'] == 64.0, r

# Critical: live 200 GiB (22% below 256) → critical (DIMM-fail)
mi_low = {'MemTotal': 200 * KB_PER_GIB, 'MemAvailable': 100 * KB_PER_GIB}
r = m.derive_verdict(cfg, mi_low, arc)
assert r['verdict'] == 'critical', r
assert any('BELOW' in a or 'failed DIMM' in a for a in r['advisories']), r

# Attention: live 250 GiB (2.3% below 256) → attention
mi_mid = {'MemTotal': 250 * KB_PER_GIB, 'MemAvailable': 180 * KB_PER_GIB}
r = m.derive_verdict(cfg, mi_mid, arc)
assert r['verdict'] == 'attention', r

# ARC ceiling exceeded → attention
GIB = 1024**3
arc_over_max = {'arc_module_loaded': True, 'arc_max_bytes': int(150 * GIB), 'arc_size_bytes': int(50 * GIB)}
r = m.derive_verdict(cfg, mi, arc_over_max)
assert any('EXCEEDS' in a for a in r['advisories']), r

# ARC LIVE size exceeded → critical
arc_live_over = {'arc_module_loaded': True, 'arc_max_bytes': int(128 * GIB), 'arc_size_bytes': int(135 * GIB)}
r = m.derive_verdict(cfg, mi, arc_live_over)
assert r['verdict'] == 'critical', r

# GGUF + ARC over total → attention
cfg_over = {'expected_total_gib': 256, 'arc_max_gib': 128, 'gguf_context_max_gib': 150}
r = m.derive_verdict(cfg_over, mi, arc)
assert r['verdict'] == 'attention', r
assert any('exceeds' in a.lower() for a in r['advisories']), r
" \
  && ok "derive_verdict: 6 cases (healthy / -22% DIMM fail / -2.3% / ARC max-over / ARC live-over / GGUF over)" \
  || ko "verdict logic wrong"

# ---- example config parses + matches in-script default ----
python3 -c "
import tomllib
with open('${EXAMPLE}', 'rb') as f:
    doc = tomllib.load(f)
assert doc['expected_total_gib'] == 256, doc
assert doc['arc_max_gib'] == 128, doc
assert doc['gguf_context_max_gib'] == 64, doc
" \
  && ok "example config TOML parses + carries 256/128/64 master-spec defaults" \
  || ko "example malformed"

# ---- human render: banner ----
out_h="$(python3 "${SCRIPT}" status 2>&1 || true)"
echo "${out_h}" | grep -q "R279 sovereign-os ram-advisor status" \
  && ok "status human banner present" || ko "banner missing"
echo "${out_h}" | grep -q "ZFS ARC ceiling" \
  && ok "status human shows ZFS ARC ceiling line" || ko "ARC ceiling line missing"

# ---- osctl bridge ----
set +e
"${OSCTL}" ram-advisor status --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "osctl ram-advisor status rc ∈ {0,1}"
else
  ko "osctl bridge rc=${rc}"
fi
python3 -c "
import json
d = json.load(open('${TMP}/osctl.out'))
assert d['round'] == 'R279', d
" \
  && ok "osctl bridge surfaces R279 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" ram-advisor nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown ram-advisor subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

echo
total=$((pass + fail))
echo "test_ram_advisor: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
