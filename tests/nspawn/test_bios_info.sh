#!/usr/bin/env bash
# tests/nspawn/test_bios_info.sh — R251 (SDD-026 Z-17).
# BIOS + baseboard + memory snapshot with board-specific advisories.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/bios-info.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_bios_info.sh"
echo

[ -x "${SCRIPT}" ] && ok "bios-info.py executable" \
  || { ko "missing bios-info.py"; exit 1; }
grep -q "R251" "${SCRIPT}" && ok "bios-info.py cites R251" || ko "R251 missing"
grep -q "ProArt X870E-CREATOR WIFI" "${SCRIPT}" \
  && ok "operator-named ASUS X870E-CREATOR WIFI present in KNOWN_BOARDS" \
  || ko "X870E-CREATOR WIFI missing from advisories"
grep -q "^  bios-info)" "${OSCTL}" \
  && ok "osctl bridges 'bios-info'" || ko "osctl dispatch missing"
grep -q "bios-info show" "${OSCTL}" \
  && ok "osctl help documents 'bios-info'" || ko "osctl help missing"

TMP="$(mktemp -d -t r251.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT

# ---- show --json: stable schema regardless of dmidecode availability ----
set +e
out="$(python3 "${SCRIPT}" show --json 2>/dev/null)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "show --json rc=0" || ko "show --json rc=${rc}"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R251', d
assert d['vector'].startswith('SDD-026 Z-17'), d
for k in ('bios','baseboard','memory','pci_gpus','advisories'):
    assert k in d, f'missing {k}'
for k in ('vendor','version','release_date','source'):
    assert k in d['bios'], f'bios missing {k}'
assert 'dimms' in d['memory']
assert 'matched_board' in d['advisories']
" \
  && ok "show --json carries bios+baseboard+memory+pci_gpus+advisories" \
  || ko "show shape wrong"

# ---- memory --json: dimm_count + dimms[] shape ----
set +e
out="$(python3 "${SCRIPT}" memory --json 2>/dev/null)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "memory --json rc=0" || ko "memory rc=${rc}"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R251', d
assert 'dimm_count' in d and 'dimms' in d, d
assert isinstance(d['dimms'], list)
# Each dimm row (if any) has stable shape.
for d_ in d['dimms']:
    for f in ('slot','channel','size','type','speed_rated_mts','speed_configured_mts','part_number'):
        assert f in d_, f'dimm row missing {f}: {d_}'
" \
  && ok "memory --json shape (dimm_count + per-DIMM fields)" \
  || ko "memory shape wrong"

# ---- advisories --json ----
set +e
out="$(python3 "${SCRIPT}" advisories --json 2>/dev/null)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "advisories --json rc=0" || ko "advisories rc=${rc}"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R251', d
assert 'matched_board' in d
assert 'advisories' in d
" \
  && ok "advisories --json shape" \
  || ko "advisories shape wrong"

# ---- KNOWN_BOARDS table contract: every entry has required fields ----
python3 -c "
import importlib.util, sys
spec = importlib.util.spec_from_file_location('bi','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
for bid, b in m.KNOWN_BOARDS.items():
    for k in ('vendor','chipset','socket','memory_channels',
             'memory_max_speed_jedec','memory_max_speed_exp_oc',
             'pcie_layout','advisories'):
        assert k in b, f'{bid} missing {k}'
    assert isinstance(b['advisories'], list)
    assert len(b['advisories'])>=3, f'{bid} should ship ≥3 advisories'
" \
  && ok "KNOWN_BOARDS contract: every entry has required fields + ≥3 advisories" \
  || ko "KNOWN_BOARDS table shape wrong"

# ---- advisories include operator-named optimization knobs for X870E ----
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('bi','${SCRIPT}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
adv = m.KNOWN_BOARDS['ProArt X870E-CREATOR WIFI']['advisories']
joined = ' '.join(adv).lower()
# Operator-named optimization axes must surface in the advisories.
for needle in ('expo','svm','iommu','pcie5','pciex16','firmware'):
    assert needle in joined, f'missing advisory keyword: {needle}'
" \
  && ok "X870E advisories cover EXPO + SVM + IOMMU + PCIe5 lane split + firmware" \
  || ko "X870E advisories missing operator-named knobs"

# ---- human render carries banner regardless of dmi availability ----
out_h="$(python3 "${SCRIPT}" show 2>&1)"
echo "${out_h}" | grep -q "R251 sovereign-os bios-info show" \
  && ok "human render carries R251 banner" || ko "banner missing"
echo "${out_h}" | grep -q "BIOS$" \
  && ok "human render shows BIOS section" || ko "BIOS section missing"
echo "${out_h}" | grep -q "BASEBOARD$" \
  && ok "human render shows BASEBOARD section" || ko "BASEBOARD section missing"

# ---- osctl bridge ----
set +e
"${OSCTL}" bios-info advisories --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl bios-info advisories rc=0" \
  || ko "osctl bridge rc=${rc}"
python3 -c "
import json
d=json.load(open('${TMP}/osctl.out'))
assert d['round']=='R251', d
" \
  && ok "osctl bridge surfaces R251 JSON" \
  || ko "osctl JSON wrong"

# ---- unknown osctl subverb → rc=2 ----
set +e
"${OSCTL}" bios-info nope > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown bios-info subverb → rc=2" \
  || ko "expected rc=2, got ${rc}"

echo
total=$((pass + fail))
echo "test_bios_info: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
