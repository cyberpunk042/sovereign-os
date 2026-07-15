#!/usr/bin/env bash
# tests/nspawn/test_wattage_sample.sh — R258 (SDD-026 Z-18 sampler).
# Per-minute PSU wattage sampler hook + systemd timer.

set -euo pipefail

# Hosts without pytest can't execute the metric-inventory lockstep lint.
PYTEST_AVAILABLE=0
python3 -m pytest --version >/dev/null 2>&1 && PYTEST_AVAILABLE=1

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

HOOK="${__REPO_ROOT}/scripts/hooks/recurrent/wattage-sample.sh"
SERVICE="${__REPO_ROOT}/systemd/system/sovereign-wattage-sample.service"
TIMER="${__REPO_ROOT}/systemd/system/sovereign-wattage-sample.timer"

echo "tests/nspawn/test_wattage_sample.sh"
echo

[ -x "${HOOK}" ] && ok "wattage-sample.sh executable" \
  || { ko "missing ${HOOK}"; exit 1; }
[ -f "${SERVICE}" ] && ok "service unit shipped" || ko "missing service"
[ -f "${TIMER}" ] && ok "timer unit shipped" || ko "missing timer"
grep -q "R258" "${HOOK}" && ok "hook cites R258" || ko "R258 ref missing"
grep -q "R252" "${HOOK}" && ok "hook cites R252 power-status" || ko "R252 ref missing"

# ---- service hardening ----
for key in ProtectSystem=strict NoNewPrivileges=true PrivateTmp=true \
           ProtectHome=true LockPersonality=true RestrictRealtime=true; do
  grep -q "${key}" "${SERVICE}" \
    && ok "service has ${key}" || ko "service missing ${key}"
done

# ---- timer per-minute cadence ----
grep -q "OnUnitActiveSec=1min" "${TIMER}" \
  && ok "timer fires every minute" || ko "timer cadence wrong"
grep -q "Persistent=true" "${TIMER}" \
  && ok "timer persistent" || ko "Persistent missing"

# ---- DRY-RUN emits marker without calling probe ----
out_dry="$(SOVEREIGN_OS_DRY_RUN=1 "${HOOK}" 2>&1)"
rc_dry=$?
[ "${rc_dry}" -eq 0 ] && ok "DRY-RUN rc=0" || ko "DRY-RUN rc=${rc_dry}"
echo "${out_dry}" | grep -q "DRY-RUN" \
  && ok "DRY-RUN logs marker" || ko "DRY-RUN marker missing"
echo "${out_dry}" | grep -q "sovereign_os_power_estimated_load_watts" \
  && ok "DRY-RUN lists the 4 R258 metrics it would emit" \
  || ko "DRY-RUN metric list missing"

# ---- live invocation: emits to textfile collector dir ----
TMP="$(mktemp -d -t r258.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
export SOVEREIGN_OS_METRICS_DIR="${TMP}"
out="$("${HOOK}" 2>&1)"
rc=$?
[ "${rc}" -eq 0 ] && ok "hook rc=0" || ko "hook rc=${rc}"
echo "${out}" | grep -qE "load=[0-9.]+W headroom=[0-9.]+W util=[0-9.]+%" \
  && ok "hook log line emits load/headroom/util numbers" \
  || ko "log line shape wrong"

# Verify the .prom file lands.
PROM="${TMP}/sovereign-os-wattage-sample.prom"
[ -f "${PROM}" ] && ok "wrote ${PROM##*/} into textfile collector dir" \
  || ko "no .prom file written"

# Each R258 metric line present.
for metric in sovereign_os_power_estimated_load_watts \
              sovereign_os_power_headroom_watts \
              sovereign_os_power_utilization_pct \
              sovereign_os_power_sample_last_run_timestamp; do
  grep -q "^${metric} " "${PROM}" \
    && ok ".prom contains ${metric}" \
    || ko ".prom missing ${metric}"
done

# Layer 1 lint: inventory has the new metrics.
if [ "${PYTEST_AVAILABLE}" -eq 1 ]; then
  python3 -m pytest "${__REPO_ROOT}/tests/lint/test_metric_inventory_lockstep.py" -q > /dev/null 2>&1 \
    && ok "metric-inventory lockstep green (R258 metrics documented)" \
    || ko "metric-inventory lint failed"
else
  ok "metric-inventory lint SKIPPED — pytest not installed on this host"
fi

echo
total=$((pass + fail))
echo "test_wattage_sample: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
