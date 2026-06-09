#!/usr/bin/env bash
# tests/nspawn/test_osctl_thermals.sh
#
# Layer 3 test for R175 — `sovereign-osctl thermals` operator UX
# surface on top of the R172 thermal-watch hook.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_osctl_thermals.sh"
echo

[ -x "${OSCTL}" ] && ok "sovereign-osctl exists + executable" \
  || { ko "missing"; exit 1; }

grep -q "cmd_thermals" "${OSCTL}" \
  && ok "cmd_thermals dispatch present" \
  || ko "cmd_thermals function missing"
grep -q "R175\|R172" "${OSCTL}" \
  && ok "cites R175 / R172 (cross-round provenance)" \
  || ko "round citations missing"
grep -q "thermals \[--json|--probe\]" "${OSCTL}" \
  && ok "cmd_help lists the thermals verb" \
  || ko "help line missing"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

# ---------- missing .prom: rc=3 + actionable message ----------
set +e
out="$(SOVEREIGN_OS_METRICS_DIR="${WORK}/empty" "${OSCTL}" thermals 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 3 ] && ok "rc=3 when no cached .prom (thermal-watch not yet run)" \
  || ko "expected rc=3, got ${rc}"
grep -q "no cached thermal readings" <<< "${out}" \
  && ok "missing-prom path prints actionable hint" \
  || ko "missing-prom message wrong"
grep -q -- "--probe" <<< "${out}" \
  && ok "actionable hint mentions --probe" \
  || ko "hint should mention --probe"

# ---------- ALL OK fixture: rc=0 ----------
mkdir -p "${WORK}/all-ok"
cat > "${WORK}/all-ok/sovereign-os-thermal-watch.prom" <<'PROM'
# HELP x x
# TYPE sovereign_os_thermal_celsius gauge
sovereign_os_thermal_celsius{sensor="k10temp/Tctl"} 58
sovereign_os_thermal_celsius{sensor="nvme/temp1"} 38
# TYPE sovereign_os_thermal_severity gauge
sovereign_os_thermal_severity{sensor="k10temp/Tctl",level="ok"} 1
sovereign_os_thermal_severity{sensor="k10temp/Tctl",level="warn"} 0
sovereign_os_thermal_severity{sensor="k10temp/Tctl",level="critical"} 0
sovereign_os_thermal_severity{sensor="nvme/temp1",level="ok"} 1
PROM
set +e
out_ok="$(SOVEREIGN_OS_METRICS_DIR="${WORK}/all-ok" "${OSCTL}" thermals 2>&1)"
rc_ok=$?
set -e
[ "${rc_ok}" -eq 0 ] && ok "rc=0 when every sensor is ok" \
  || ko "expected rc=0, got ${rc_ok}"
grep -q "ALL OK" <<< "${out_ok}" \
  && ok "human output: ALL OK banner" \
  || ko "ALL OK banner missing"
grep -q "k10temp/Tctl.*58" <<< "${out_ok}" \
  && ok "sensor table includes k10temp/Tctl=58" \
  || ko "sensor row missing"
grep -q "✓ ok" <<< "${out_ok}" \
  && ok "ok status marker rendered" \
  || ko "ok marker missing"

# ---------- WARN fixture: rc=1 ----------
mkdir -p "${WORK}/warn"
cat > "${WORK}/warn/sovereign-os-thermal-watch.prom" <<'PROM'
# TYPE sovereign_os_thermal_celsius gauge
sovereign_os_thermal_celsius{sensor="k10temp/Tctl"} 88
sovereign_os_thermal_celsius{sensor="nvme/temp1"} 38
# TYPE sovereign_os_thermal_severity gauge
sovereign_os_thermal_severity{sensor="k10temp/Tctl",level="warn"} 1
sovereign_os_thermal_severity{sensor="k10temp/Tctl",level="ok"} 0
sovereign_os_thermal_severity{sensor="nvme/temp1",level="ok"} 1
PROM
set +e
out_w="$(SOVEREIGN_OS_METRICS_DIR="${WORK}/warn" "${OSCTL}" thermals 2>&1)"
rc_w=$?
set -e
[ "${rc_w}" -eq 1 ] && ok "rc=1 when any sensor at WARN" \
  || ko "expected rc=1, got ${rc_w}"
grep -q "WARN" <<< "${out_w}" \
  && ok "WARN banner rendered" || ko "WARN banner missing"
grep -q "! warn" <<< "${out_w}" \
  && ok "warn marker rendered (!)" || ko "warn marker missing"

# ---------- CRITICAL fixture: rc=2 + worst severity wins ----------
mkdir -p "${WORK}/crit"
cat > "${WORK}/crit/sovereign-os-thermal-watch.prom" <<'PROM'
# TYPE sovereign_os_thermal_celsius gauge
sovereign_os_thermal_celsius{sensor="k10temp/Tctl"} 88
sovereign_os_thermal_celsius{sensor="nvidia-gpu-0"} 97
# TYPE sovereign_os_thermal_severity gauge
sovereign_os_thermal_severity{sensor="k10temp/Tctl",level="warn"} 1
sovereign_os_thermal_severity{sensor="nvidia-gpu-0",level="critical"} 1
PROM
set +e
out_c="$(SOVEREIGN_OS_METRICS_DIR="${WORK}/crit" "${OSCTL}" thermals 2>&1)"
rc_c=$?
set -e
[ "${rc_c}" -eq 2 ] && ok "rc=2 when any sensor at CRITICAL (worst wins)" \
  || ko "expected rc=2, got ${rc_c}"
grep -q "CRITICAL" <<< "${out_c}" \
  && ok "CRITICAL banner rendered" || ko "CRITICAL banner missing"
grep -q "✗ critical" <<< "${out_c}" \
  && ok "critical marker rendered (✗)" || ko "critical marker missing"
grep -q "nvidia-gpu-0.*97" <<< "${out_c}" \
  && ok "GPU sensor surfaced" || ko "GPU sensor missing"

# ---------- --help works ----------
set +e
out_h="$("${OSCTL}" thermals --help 2>&1)"
hrc=$?
set -e
[ "${hrc}" -eq 0 ] && ok "--help rc=0" || ko "--help rc=${hrc}"
grep -q "R175" <<< "${out_h}" \
  && ok "--help references R175" || ko "R175 missing from help"

# ---------- --json without thermal-watch.py installed → rc=3 ----------
# (CI sandboxes have the script at scripts/hardware/thermal-watch.py
# so this should succeed even with no sensors; just assert rc ∈ {0,1,2,3}.)
set +e
"${OSCTL}" thermals --json >/dev/null 2>&1
jr=$?
set -e
case "${jr}" in
  0|1|2|3) ok "--json mode returns operator-meaningful rc (${jr})" ;;
  *) ko "--json mode rc=${jr} not in expected set" ;;
esac

echo
total=$((pass + fail))
echo "test_osctl_thermals: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
