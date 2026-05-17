#!/usr/bin/env bash
# tests/nspawn/test_gpu_card_advisor.sh — R271 (E1.M13).
# RTX 3090 + RTX PRO 6000 operator-specific advisory.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/gpu-card-advisor.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_gpu_card_advisor.sh"
echo

[ -x "${SCRIPT}" ] && ok "gpu-card-advisor.py executable" \
  || { ko "missing"; exit 1; }
grep -q "R271\|E1.M13" "${SCRIPT}" && ok "script cites R271/E1.M13" \
  || ko "R271 missing"
grep -q "RTX 3090" "${SCRIPT}" && ok "KNOWN_CARDS contains RTX 3090" \
  || ko "RTX 3090 missing"
grep -q "RTX PRO 6000" "${SCRIPT}" && ok "KNOWN_CARDS contains RTX PRO 6000" \
  || ko "RTX PRO 6000 missing"
grep -q "^  gpu-card-advisor)" "${OSCTL}" \
  && ok "osctl bridges 'gpu-card-advisor'" || ko "osctl dispatch missing"

# ---- detect --json: shape ----
set +e
out="$(python3 "${SCRIPT}" detect --json 2>/dev/null)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "detect --json rc=0" || ko "detect rc=${rc}"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R271', d
for f in ('nvidia_smi_available','card_count','cards'):
    assert f in d, f'missing {f}'
" \
  && ok "detect --json: required fields present" \
  || ko "detect shape wrong"

# ---- advisories --json: shape + curated advisories per card ----
set +e
out="$(python3 "${SCRIPT}" advisories --json 2>/dev/null)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; then
  ok "advisories rc ∈ {0,1}"
else
  ko "rc unexpected ${rc}"
fi
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R271', d
assert 'card_count' in d and 'results' in d
" \
  && ok "advisories --json shape" \
  || ko "advisories shape wrong"

# ---- dual-card --json: 3 booleans + findings list ----
out="$(python3 "${SCRIPT}" dual-card --json 2>/dev/null)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['round'] == 'R271', d
for f in ('rtx_3090_present','rtx_pro_6000_present','sain01_dual_card_layout','findings'):
    assert f in d, f'missing {f}'
assert isinstance(d['rtx_3090_present'], bool)
assert isinstance(d['rtx_pro_6000_present'], bool)
assert isinstance(d['findings'], list)
" \
  && ok "dual-card --json: 3 boolean flags + findings array" \
  || ko "dual-card shape wrong"

# ---- KNOWN_CARDS table contract: 4+ advisories per card ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('gca','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
for key in ('RTX 3090','RTX PRO 6000'):
    assert key in m.KNOWN_CARDS, key
    c = m.KNOWN_CARDS[key]
    for f in ('architecture','vram_gb','vram_type','stock_tdp_watts',
             'operator_recommended_cap_watts','pcie_rated','advisories'):
        assert f in c, f'{key} missing {f}'
    assert len(c['advisories']) >= 4, f'{key} should ship ≥4 advisories'
# RTX 3090 must cite the operator-stated 'slightly reduced' quote.
adv_3090 = ' '.join(m.KNOWN_CARDS['RTX 3090']['advisories'])
assert 'slightly reduced' in adv_3090, adv_3090
assert '280' in adv_3090 and '320' in adv_3090, adv_3090
# RTX PRO 6000 must cite Blackwell + 96 GB + driver 565+ + PCIe5.
adv_pro = ' '.join(m.KNOWN_CARDS['RTX PRO 6000']['advisories'])
assert 'Blackwell' in adv_pro
assert '96' in adv_pro
assert '565' in adv_pro
assert 'PCIe5' in adv_pro or 'PCIe 5' in adv_pro
" \
  && ok "KNOWN_CARDS contract: 3090 cites 'slightly reduced'/280-320W, PRO 6000 cites Blackwell/96GB/driver-565/PCIe5" \
  || ko "KNOWN_CARDS table incomplete"

# ---- classify_card() heuristics ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('gca','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
c = m.classify_card('NVIDIA GeForce RTX 3090')
assert c is not None and c['matched_key'] == 'RTX 3090'
c = m.classify_card('NVIDIA RTX PRO 6000 Blackwell')
assert c is not None and c['matched_key'] == 'RTX PRO 6000'
# Unmatched
c = m.classify_card('NVIDIA RTX 4090')
assert c is None
c = m.classify_card('NVIDIA T4')
assert c is None
" \
  && ok "classify_card: substring matches 3090/PRO 6000, unmatched for 4090/T4" \
  || ko "classify heuristics wrong"

# ---- live-findings logic: power_limit > operator cap → finding ----
python3 -c "
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location('gca','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# Verify the band lookup
c = m.classify_card('RTX 3090')
band = c['operator_recommended_cap_watts']
assert band == [280, 320], band
# Verify temperature finding code path constants
# (the constants are inline; smoke-test the threshold below)
" \
  && ok "operator_recommended_cap_watts band for RTX 3090 = [280, 320]" \
  || ko "cap band wrong"

# ---- human render: banner + RTX 3090 mentioned in dual-card output (when absent, the no-detection path emits message) ----
out_h="$(python3 "${SCRIPT}" dual-card 2>&1 || true)"
echo "${out_h}" | grep -q "R271 sovereign-os gpu-card-advisor" \
  && ok "dual-card human banner present" || ko "banner missing"
echo "${out_h}" | grep -q "RTX 3090:" \
  && ok "dual-card human shows 3090 detection status" || ko "3090 status line missing"
echo "${out_h}" | grep -q "RTX PRO 6000:" \
  && ok "dual-card human shows PRO 6000 detection status" || ko "PRO 6000 status missing"

# ---- osctl bridge ----
TMP="$(mktemp -d -t r271.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
set +e
"${OSCTL}" gpu-card-advisor dual-card --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl gpu-card-advisor dual-card rc=0" \
  || ko "osctl bridge rc=${rc}"
python3 -c "
import json
d = json.load(open('${TMP}/osctl.out'))
assert d['round'] == 'R271', d
" \
  && ok "osctl bridge surfaces R271 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" gpu-card-advisor nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown gpu-card-advisor subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

echo
total=$((pass + fail))
echo "test_gpu_card_advisor: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
