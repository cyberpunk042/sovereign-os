#!/usr/bin/env bash
# R356 (E1.M41) — CCD pinning verifier L3.
# Operator-named master spec §19.2 verbatim: Pulse cores 0-5 mask 0xfff
# / Weaver+Auditor cores 6-9 mask 0xff000 / Host cores 10-11 mask 0xf00000.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CP="${REPO_ROOT}/scripts/hardware/ccd-pinning.py"
OSCTL="${REPO_ROOT}/scripts/sovereign-osctl"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── 1. show prints all 3 §19.2 layers with operator-verbatim masks ──
out="$(python3 "${CP}" show --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['layer_count'] == 3
layers = {l['layer']: l for l in d['layers']}
# Exact operator-named layer titles from master spec §19.2
assert 'Pulse Core' in layers
assert 'Weaver & Auditor' in layers
assert 'System Host / OS Base' in layers
" || fail "show 3 layers"
pass "1. show lists exactly 3 §19.2-named layers (Pulse / Weaver & Auditor / Host)"

# ── 2. verbatim mask values match operator's §19.2 table ────────────
out="$(python3 "${CP}" show --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
by_name = {l['layer']: l for l in d['layers']}
# Operator-verbatim mask values — MUST be exact
assert by_name['Pulse Core']['thread_mask_hex'] == '0xfff'
assert by_name['Pulse Core']['thread_mask_int'] == 0xfff
assert by_name['Pulse Core']['core_range'] == '0-5'
assert by_name['Pulse Core']['thread_range'] == '0-11'
assert by_name['Pulse Core']['ccd'] == 0
assert by_name['Weaver & Auditor']['thread_mask_hex'] == '0xff000'
assert by_name['Weaver & Auditor']['thread_mask_int'] == 0xff000
assert by_name['Weaver & Auditor']['core_range'] == '6-9'
assert by_name['Weaver & Auditor']['ccd'] == 1
assert by_name['System Host / OS Base']['thread_mask_hex'] == '0xf00000'
assert by_name['System Host / OS Base']['thread_mask_int'] == 0xf00000
assert by_name['System Host / OS Base']['core_range'] == '10-11'
" || fail "masks"
pass "2. operator-VERBATIM masks preserved: 0xfff / 0xff000 / 0xf00000 (§19.2)"

# ── 3. responsibility text preserves operator phrasing ──────────────
out="$(python3 "${CP}" show --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
by_name = {l['layer']: l for l in d['layers']}
# Operator-verbatim phrases from §17 + §19.2
assert 'AVX-512' in by_name['Pulse Core']['responsibility']
assert 'bitnet.cpp' in by_name['Pulse Core']['responsibility']
assert 'state engine' in by_name['Weaver & Auditor']['responsibility']
assert 'Tetragon' in by_name['Weaver & Auditor']['responsibility']
assert 'Marvell 10GbE' in by_name['System Host / OS Base']['responsibility']
assert 'ZFS' in by_name['System Host / OS Base']['responsibility'].upper() or 'zfs' in by_name['System Host / OS Base']['responsibility'].lower()
" || fail "responsibility verbatim"
pass "3. responsibility text preserves operator §17+§19.2 verbatim phrases"

# ── 4. verify NEVER-raises on a container (no systemd PIDs) ─────────
rc=0; out="$(python3 "${CP}" verify --json 2>&1)" || rc=$?
[[ "${rc}" == 0 || "${rc}" == 1 ]] || fail "verify rc=${rc}"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# Container has no systemd → all probed=false; drift_count=0
assert d['probed_count'] == 0
assert d['drift_count'] == 0
assert d['row_count'] >= 3  # 3 layers × ≥1 row each
# Every row has the schema
for r in d['rows']:
    for k in ('layer','service_unit','pid','intended_mask_hex',
             'intended_mask_int','actual_mask_int','actual_mask_hex',
             'probed','drifted'):
        assert k in r, (k, r)
" || fail "verify schema"
pass "4. verify NEVER-raises on container (probed=0, drift=0, valid schema)"

# ── 5. recommend = no drift on container → rc=0 + empty list ────────
rc=0; out="$(python3 "${CP}" recommend --json 2>&1)" || rc=$?
[[ "${rc}" == 0 ]] || fail "recommend rc=${rc}"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
assert d['drift_count'] == 0
assert d['drifted_services'] == []
assert d['remediation_commands'] == []
" || fail "recommend empty"
pass "5. recommend on un-probed container → rc=0 + empty drift list"

# ── 6. each layer has a remediation command pointing at AllowedCPUs ─
out="$(python3 "${CP}" verify --json 2>&1 || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
remediations = [r['remediation'] for r in d['rows']
                 if r.get('remediation')]
# At least 2 layers (Pulse, Weaver+Auditor) have remediation commands
assert len(remediations) >= 2
for rem in remediations:
    assert 'systemctl set-property' in rem
    assert 'AllowedCPUs=' in rem
" || fail "remediation"
pass "6. remediation commands use 'systemctl set-property … AllowedCPUs=…' shape"

# ── 7. operator-overlay can replace service_units per host ──────────
cfg=$(mktemp --suffix=.toml)
cat > "${cfg}" <<TOML
[[layers]]
layer = "Test-Layer"
ccd = 0
core_range = "0-1"
thread_range = "0-3"
thread_mask_hex = "0xf"
thread_mask_int = 15
responsibility = "test overlay"
service_units = ["overlay-test.service"]
TOML
out="$(python3 "${CP}" show --config "${cfg}" --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
# Lists replace per SDD-030
assert d['layer_count'] == 1
assert d['layers'][0]['layer'] == 'Test-Layer'
" || fail "overlay"
rm -f "${cfg}"
pass "7. operator-overlay replaces layers list (R283/SDD-030 lists-replace)"

# ── 8. CCD0 / CCD1 boundary preserved (operator's structural concern)
out="$(python3 "${CP}" show --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
ccd0 = [l for l in d['layers'] if l['ccd'] == 0]
ccd1 = [l for l in d['layers'] if l['ccd'] == 1]
# §19.2: Pulse is the SOLE CCD0 layer; Weaver+Auditor and Host both CCD1
assert len(ccd0) == 1
assert ccd0[0]['layer'] == 'Pulse Core'
assert len(ccd1) == 2
# §19.1 verbatim — eliminates Infinity Fabric latency
" || fail "ccd boundary"
pass "8. CCD0 = Pulse only; CCD1 = Weaver+Auditor + Host (master spec §19.1 boundary)"

# ── 9. sovereign-osctl ccd-pinning dispatches all 3 subverbs ────────
"${OSCTL}" ccd-pinning show --json >/dev/null 2>&1 || fail "osctl show"
"${OSCTL}" ccd-pinning verify --json >/dev/null 2>&1 || fail "osctl verify"
"${OSCTL}" ccd-pinning recommend --json >/dev/null 2>&1 || fail "osctl recommend"
pass "9. sovereign-osctl ccd-pinning dispatches show/verify/recommend"

# ── 10. Service unit mapping matches operator §19.2 + Trinity naming
out="$(python3 "${CP}" show --json || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
by_name = {l['layer']: l for l in d['layers']}
# Pulse layer ↔ sovereign-pulse.service (Trinity naming)
units = by_name['Pulse Core']['service_units']
assert 'sovereign-pulse.service' in units
# Auditor ↔ sovereign-guardian-core.service (per master spec §10 Native Guardian)
units = by_name['Weaver & Auditor']['service_units']
assert 'sovereign-guardian-core.service' in units
" || fail "unit mapping"
pass "10. service_units map: Pulse→sovereign-pulse; Auditor→sovereign-guardian-core (Trinity naming preserved)"

echo "ALL OK"
