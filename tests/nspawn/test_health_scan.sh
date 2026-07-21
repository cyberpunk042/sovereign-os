#!/usr/bin/env bash
# tests/nspawn/test_health_scan.sh — R226 (SDD-026 Z-6) composite
# health-scan over every shipped Z-vector card.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/health-scan.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_health_scan.sh"
echo

[ -x "${SCRIPT}" ] && ok "health-scan.py executable" \
  || { ko "missing health-scan.py"; exit 1; }
grep -q "^  health)" "${OSCTL}" \
  && ok "osctl bridges 'health'" || ko "osctl bridge missing"
grep -q "R226" "${OSCTL}" \
  && ok "osctl cites R226" || ko "R226 citation missing"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

# ---- full scan (banner + structural assertions) ----
set +e
python3 "${SCRIPT}" > "${WORK}/scan.txt" 2>&1
rc=$?
set -e
# rc is 0 or 1 depending on which probes flag — we just check it's
# in the expected set (not 2 = usage error).
{ [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; } \
  && ok "scan rc in {0,1} (${rc})" || ko "scan unexpected rc=${rc}"
grep -q "R226 sovereign-os health scan" "${WORK}/scan.txt" \
  && ok "R226 banner present" || ko "no R226 banner"
# All 8 probes must be enumerated
for probe in gpu network cpu_mode fs_usage raid flex compat avx_mode; do
  grep -qE " ${probe} +\[" "${WORK}/scan.txt" \
    && ok "probe enumerated: ${probe}" \
    || ko "missing probe: ${probe}"
done
# Summary line
grep -qE "probes: 8" "${WORK}/scan.txt" \
  && ok "summary cites 8 probes" || ko "summary count wrong"

# ---- --json shape ----
set +e
python3 "${SCRIPT}" --json > "${WORK}/scan.json" 2>&1
set -e
python3 - "${WORK}/scan.json" <<'PY' 2>/dev/null \
  && ok "JSON shape: probes[8] + summary + needs_attention + round" \
  || ko "JSON shape wrong"
import json, sys
d = json.load(open(sys.argv[1]))
assert d["round"] == "R226"
assert d["vector"].startswith("SDD-026 Z-6")
assert isinstance(d["probes"], list)
assert len(d["probes"]) == 8
ids = {p["probe"] for p in d["probes"]}
assert ids == {"gpu", "network", "cpu_mode", "fs_usage", "raid", "flex", "compat", "avx_mode"}, ids
for p in d["probes"]:
    assert p["severity"] in {"ok", "attention", "informational"}, p
    assert "vector" in p and "round" in p and "detail" in p
assert "total" in d["summary"] and d["summary"]["total"] == 8
assert isinstance(d["needs_attention"], bool)
PY

# ---- --probe filter ----
set +e
python3 "${SCRIPT}" --probe gpu > "${WORK}/probe-gpu.txt" 2>&1
rc=$?
set -e
{ [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; } \
  && ok "--probe gpu rc in {0,1}" || ko "probe rc wrong"
grep -qE " gpu +\[" "${WORK}/probe-gpu.txt" \
  && ok "--probe gpu emits gpu card" || ko "single-probe gpu missing"
! grep -qE " raid +\[" "${WORK}/probe-gpu.txt" \
  && ok "--probe gpu excludes other probes" || ko "single-probe leaked"
grep -qE "probes: 1" "${WORK}/probe-gpu.txt" \
  && ok "--probe single → summary total=1" || ko "single-probe summary wrong"

# ---- bad --probe → rc=2 ----
set +e
python3 "${SCRIPT}" --probe bogus > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown probe → rc=2" \
  || ko "expected rc=2 on bad probe, got ${rc}"

# ---- osctl bridge ----
set +e
"${OSCTL}" health scan --probe flex > "${WORK}/osctl.txt" 2>&1
rc=$?
set -e
{ [ "${rc}" -eq 0 ] || [ "${rc}" -eq 1 ]; } \
  && ok "osctl health scan --probe flex rc in {0,1}" \
  || ko "osctl bridge rc wrong (${rc})"
grep -q "R226" "${WORK}/osctl.txt" \
  && ok "osctl bridge surfaces R226 banner" || ko "osctl banner missing"

# ---- osctl unknown subverb → rc=2 ----
set +e
"${OSCTL}" health unknown > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "unknown health subverb → rc=2" \
  || ko "expected rc=2 on unknown subverb, got ${rc}"

echo
total=$((pass + fail))
echo "test_health_scan: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
