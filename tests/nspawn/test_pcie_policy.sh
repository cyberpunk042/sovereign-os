#!/usr/bin/env bash
# tests/nspawn/test_pcie_policy.sh — R270 (E1.M12).
# PCIe lane-allocation policy advisor.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/pcie-policy.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_pcie_policy.sh"
echo

[ -x "${SCRIPT}" ] && ok "pcie-policy.py executable" \
  || { ko "missing"; exit 1; }
grep -q "R270\|E1.M12" "${SCRIPT}" && ok "script cites R270/E1.M12" \
  || ko "R270 missing"
grep -q "ProArt X870E-CREATOR WIFI" "${SCRIPT}" \
  && ok "X870E-CREATOR WIFI present in BOARD_LANE_RULES" \
  || ko "X870E rules missing"
grep -q "^  pcie-policy)" "${OSCTL}" \
  && ok "osctl bridges 'pcie-policy'" || ko "osctl dispatch missing"

# ---- status --json: shape ----
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
assert d['round'] == 'R270', d
for f in ('verdict','summary','devices','lspci_available'):
    assert f in d, f'missing {f}'
assert d['verdict'] in ('ok','attention','critical','unavailable'), d
" \
  && ok "status --json: required fields + verdict enum" \
  || ko "status shape wrong"

# ---- share --json: stable shape + rule_count >= 0 ----
out="$(python3 "${SCRIPT}" share --json 2>/dev/null)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R270', d
for f in ('baseboard_product','matched_board','rule_count','rules'):
    assert f in d, f'missing {f}'
" \
  && ok "share --json: stable shape (matched_board/rule_count/rules)" \
  || ko "share shape wrong"

# ---- X870E lane-share rules: 3 cycle-8 rules with required keys ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('pp','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
b = m.BOARD_LANE_RULES['ProArt X870E-CREATOR WIFI']
rules = b['rules']
assert len(rules) >= 3, rules
for r in rules:
    for k in ('trigger','effect','operator_hint'):
        assert k in r, f'rule missing {k}: {r}'
# X870E-specific named slots must surface in rules.
joined = ' '.join(r['trigger'] + ' ' + r['effect'] + ' ' + r['operator_hint'] for r in rules)
assert 'M2_2' in joined, 'M2_2 lane-share rule missing'
assert 'PCIEX16_1' in joined or 'PCIEX16_2' in joined, 'PCIEX16 split rule missing'
" \
  && ok "X870E rules: 3+ rules covering M2_2 + PCIEX16 contention" \
  || ko "X870E rules incomplete"

# ---- parse_lnk_field: handles both LnkSta + LnkCap formats ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('pp','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# LnkSta format: 'Speed 32GT/s, Width x16'
sta = m.parse_lnk_field('Speed 32GT/s, Width x16')
assert sta['speed'] == '32GT/s', sta
assert sta['width'] == 'x16', sta
# LnkCap format: 'Port #1, Speed 32GT/s, Width x16, ASPM L1, ...'
cap = m.parse_lnk_field('Port #1, Speed 32GT/s, Width x16, ASPM L1')
assert cap['speed'] == '32GT/s', cap
assert cap['width'] == 'x16', cap
" \
  && ok "parse_lnk_field: handles LnkSta + LnkCap formats" \
  || ko "parse_lnk_field broken"

# ---- speed_to_pcie_gen: 32GT/s → PCIe5.0, etc ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('pp','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert m.speed_to_pcie_gen('32GT/s') == 'PCIe5.0'
assert m.speed_to_pcie_gen('16GT/s') == 'PCIe4.0'
assert m.speed_to_pcie_gen('8GT/s')  == 'PCIe3.0'
assert m.speed_to_pcie_gen('64GT/s') == 'PCIe6.0'
assert m.speed_to_pcie_gen('') == '?'
" \
  && ok "speed_to_pcie_gen: 8/16/32/64 GT/s → PCIe3/4/5/6.0 mapping" \
  || ko "speed mapping wrong"

# ---- classify_device: degradation severity ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('pp','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# Healthy GPU
d = {'bdf':'01:00.0','name':'NVIDIA VGA',
     'lnk_sta_raw':'Speed 32GT/s, Width x16',
     'lnk_cap_raw':'Port #1, Speed 32GT/s, Width x16'}
c = m.classify_device(d)
assert c['degradation'] == 'ok', c
assert c['severity'] == 'ok', c

# Width-degraded GPU (x8 vs capable x16) → attention
d = {'bdf':'01:00.0','name':'NVIDIA VGA',
     'lnk_sta_raw':'Speed 32GT/s, Width x8',
     'lnk_cap_raw':'Port #1, Speed 32GT/s, Width x16'}
c = m.classify_device(d)
assert c['degradation'] == 'width-degraded', c
assert c['severity'] == 'attention', c

# x1 GPU with capable x16 → critical
d = {'bdf':'01:00.0','name':'NVIDIA VGA',
     'lnk_sta_raw':'Speed 16GT/s, Width x1',
     'lnk_cap_raw':'Port #1, Speed 32GT/s, Width x16'}
c = m.classify_device(d)
assert c['degradation'] == 'both', c  # both width AND speed degraded
assert c['severity'] == 'critical', c

# x4 GPU with capable x16 → critical
d = {'bdf':'01:00.0','name':'NVIDIA VGA',
     'lnk_sta_raw':'Speed 32GT/s, Width x4',
     'lnk_cap_raw':'Port #1, Speed 32GT/s, Width x16'}
c = m.classify_device(d)
assert c['severity'] == 'critical', c
" \
  && ok "classify_device: 4 cases (healthy/width-deg/x1-crit/x4-crit)" \
  || ko "classify_device wrong"

# ---- is_interesting: filters to GPU/NVMe/NIC ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('pp','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert m.is_interesting('NVIDIA VGA compatible controller') is True
assert m.is_interesting('3D controller')                   is True
assert m.is_interesting('Non-Volatile memory controller: ... NVM Express') is True
assert m.is_interesting('Ethernet controller')             is True
assert m.is_interesting('USB controller')                  is False
assert m.is_interesting('Audio device')                    is False
" \
  && ok "is_interesting: GPU/NVMe/NIC pass, USB/Audio fail" \
  || ko "is_interesting wrong"

# ---- human render: banner ----
out_h="$(python3 "${SCRIPT}" status 2>&1 || true)"
echo "${out_h}" | grep -q "R270 sovereign-os pcie-policy" \
  && ok "status human banner present" || ko "banner missing"

# ---- osctl bridge ----
TMP="$(mktemp -d -t r270.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
set +e
"${OSCTL}" pcie-policy share --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl pcie-policy share rc=0" \
  || ko "osctl bridge rc=${rc}"
python3 -c "
import json
d = json.load(open('${TMP}/osctl.out'))
assert d['round'] == 'R270', d
" \
  && ok "osctl bridge surfaces R270 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" pcie-policy nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown pcie-policy subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

echo
total=$((pass + fail))
echo "test_pcie_policy: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
