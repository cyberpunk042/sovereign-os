#!/usr/bin/env bash
# R301 (E1.M26) — PCIe lane split detection L3.
#
# Operator-named (§1b mandate row): "pci lane splits and whatever
# like virtualization or what we find relevant via search online
# and such".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="${REPO_ROOT}/scripts/hardware/pcie-lane-detect.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. status --json envelope (graceful when lspci absent) ──
out="$(python3 "${SCRIPT}" status --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R301'
assert d['schema_version'] == '1.0.0'
assert d['sdd_vector'] == 'E1.M26'
assert d['filter'] == 'all'
# Either lspci ran (devices populated) OR error reported.
if d.get('lspci_error'):
    assert d['device_count'] == 0
    assert d['rc'] == 2
else:
    assert d['device_count'] >= 0
" || fail "envelope"
pass "1. status --json envelope (graceful lspci-absent fallback)"

# ── 2. Parser handles synthetic lspci -vv output correctly ──
python3 -c "
import sys, pathlib
sys.path.insert(0, str(pathlib.Path('scripts/hardware').resolve()))
import importlib.util
spec = importlib.util.spec_from_file_location('plane', 'scripts/hardware/pcie-lane-detect.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# Synthetic lspci -vv block: an x16 Gen4 GPU running at x8 Gen4 (split).
fixture = '''01:00.0 VGA compatible controller [0300]: NVIDIA RTX 4090 [10de:2684]
\tCapabilities: [a0] Express (v2) Endpoint, MSI 00
\t\tLnkCap:\tPort #0, Speed 16GT/s, Width x16, ASPM not supported
\t\tLnkSta:\tSpeed 16GT/s, Width x8, ClockPM- Suprise- LLActRep- BWNot-
02:00.0 VGA compatible controller [0300]: NVIDIA RTX PRO 6000 [10de:2eba]
\tCapabilities: [a0] Express (v2) Endpoint
\t\tLnkCap:\tPort #0, Speed 32GT/s, Width x16
\t\tLnkSta:\tSpeed 32GT/s, Width x16
'''
devs = m.parse_devices(fixture)
assert len(devs) == 2, devs
assert devs[0]['bdf'] == '01:00.0', devs[0]
assert devs[0]['lnk_cap_width'] == 16
assert devs[0]['lnk_sta_width'] == 8
assert devs[0]['lnk_cap_speed'] == '16'
assert devs[1]['lnk_sta_width'] == 16
# Classify.
deg0 = m.classify_degradation(devs[0])
deg1 = m.classify_degradation(devs[1])
assert deg0['verdict'] == 'width-degraded', deg0
assert deg1['verdict'] == 'full-lnk-cap', deg1
# is_gpu classifier.
assert m.is_gpu(devs[0]) is True
assert m.is_gpu(devs[1]) is True
print('PASS')
" || fail "parser unit"
pass "2. parser handles synthetic lspci output + classifies degradation"

# ── 3. gen-label maps GT/s → Gen{N} ───────────────────────────
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('plane', 'scripts/hardware/pcie-lane-detect.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert m._gen_label('2.5') == 'Gen1'
assert m._gen_label('5') == 'Gen2'
assert m._gen_label('8') == 'Gen3'
assert m._gen_label('16') == 'Gen4'
assert m._gen_label('32') == 'Gen5'
# Unknown speed = pass-through.
assert m._gen_label('64') == 'Gen6'
assert m._gen_label('999') == '999GT/s'
print('PASS')
" || fail "gen-label"
pass "3. gen-label correctly maps PCIe Gen1 through Gen6"

# ── 4. is_gpu classifier covers VGA + 3D controller ─────────
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('plane', 'scripts/hardware/pcie-lane-detect.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert m.is_gpu({'class': 'VGA compatible controller'}) is True
assert m.is_gpu({'class': '3D controller'}) is True
assert m.is_gpu({'class': 'Display controller'}) is True
assert m.is_gpu({'class': 'Ethernet controller'}) is False
assert m.is_gpu({'class': ''}) is False
print('PASS')
" || fail "is_gpu"
pass "4. is_gpu classifies VGA / 3D / Display controller as GPU"

# ── 5. degraded verb filters correctly when both modes ───────
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('plane', 'scripts/hardware/pcie-lane-detect.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
# Both width + speed degraded.
d = {'lnk_cap_width': 16, 'lnk_sta_width': 8,
     'lnk_cap_speed': '32', 'lnk_sta_speed': '8'}
assert m.classify_degradation(d)['verdict'] == 'both', m.classify_degradation(d)
# Speed only.
d = {'lnk_cap_width': 16, 'lnk_sta_width': 16,
     'lnk_cap_speed': '32', 'lnk_sta_speed': '16'}
assert m.classify_degradation(d)['verdict'] == 'speed-degraded'
# Width only.
d = {'lnk_cap_width': 16, 'lnk_sta_width': 8,
     'lnk_cap_speed': '32', 'lnk_sta_speed': '32'}
assert m.classify_degradation(d)['verdict'] == 'width-degraded'
# Neither.
d = {'lnk_cap_width': 16, 'lnk_sta_width': 16,
     'lnk_cap_speed': '32', 'lnk_sta_speed': '32'}
assert m.classify_degradation(d)['verdict'] == 'full-lnk-cap'
print('PASS')
" || fail "classify_degradation"
pass "5. classify_degradation: width-only / speed-only / both / full-lnk-cap"

# ── 6. no-link-data verdict when lspci doesn't report a link ──
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('plane', 'scripts/hardware/pcie-lane-detect.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
d = {'lnk_cap_width': None, 'lnk_sta_width': None}
assert m.classify_degradation(d)['verdict'] == 'no-link-data'
print('PASS')
" || fail "no-link-data"
pass "6. no-link-data verdict when lspci reports no link"

# ── 7. sovereign-osctl pcie-lane-detect dispatch ─────────────
out_disp="$(bash "${OSCTL}" pcie-lane-detect status --json 2>/dev/null || true)"
echo "${out_disp}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R301'
" || fail "sovereign-osctl dispatch"
pass "7. sovereign-osctl pcie-lane-detect dispatches"

# ── 8. gpu / degraded verbs both work ────────────────────────
for v in gpu degraded; do
    out_v="$(python3 "${SCRIPT}" ${v} --json || true)"
    echo "${out_v}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['round'] == 'R301'
assert d['filter'] in ('gpu', 'degraded'), d['filter']
" || fail "${v} verb shape"
done
pass "8. gpu + degraded verbs both produce valid envelopes"

echo "ALL OK"
