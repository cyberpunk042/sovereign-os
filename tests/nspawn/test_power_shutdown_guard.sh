#!/usr/bin/env bash
# tests/nspawn/test_power_shutdown_guard.sh — R253 (SDD-026 Z-18 closure).
# Graceful-shutdown guard hook + systemd timer wiring.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

HOOK="${__REPO_ROOT}/scripts/hooks/recurrent/power-shutdown-guard.sh"
SERVICE="${__REPO_ROOT}/systemd/system/sovereign-power-shutdown-guard.service"
TIMER="${__REPO_ROOT}/systemd/system/sovereign-power-shutdown-guard.timer"

echo "tests/nspawn/test_power_shutdown_guard.sh"
echo

[ -x "${HOOK}" ] && ok "hook executable" \
  || { ko "missing ${HOOK}"; exit 1; }
[ -f "${SERVICE}" ] && ok "service unit shipped" || ko "missing service"
[ -f "${TIMER}" ] && ok "timer unit shipped" || ko "missing timer"

grep -q "R253" "${HOOK}" && ok "hook cites R253" || ko "R253 ref missing"
grep -q "R252" "${HOOK}" && ok "hook cites R252 power-status" || ko "R252 ref missing"

# ---- service hardening (R171 contract) ----
for key in ProtectSystem=strict NoNewPrivileges=true PrivateTmp=true \
           ProtectHome=true LockPersonality=true RestrictRealtime=true \
           ProtectKernelTunables=true; do
  grep -q "${key}" "${SERVICE}" \
    && ok "service has ${key}" || ko "service missing ${key}"
done

# ---- timer: per-minute cadence ----
grep -q "OnUnitActiveSec=1min" "${TIMER}" \
  && ok "timer fires every minute" || ko "timer cadence wrong"
grep -q "Persistent=true" "${TIMER}" \
  && ok "timer persistent across reboots" || ko "Persistent missing"
grep -q "Unit=sovereign-power-shutdown-guard.service" "${TIMER}" \
  && ok "timer wires to the matching service" || ko "Unit ref wrong"

# ---- DRY-RUN: emits marker + exits 0 without calling probe ----
out_dry="$(SOVEREIGN_OS_DRY_RUN=1 "${HOOK}" 2>&1)"
rc_dry=$?
[ "${rc_dry}" -eq 0 ] && ok "DRY-RUN rc=0" || ko "DRY-RUN rc=${rc_dry}"
echo "${out_dry}" | grep -q "DRY-RUN" \
  && ok "DRY-RUN logs marker" || ko "DRY-RUN marker missing"

# ---- live invocation: no UPS = verdict=no-ups, no shutdown attempted ----
out="$("${HOOK}" 2>&1)"
rc=$?
[ "${rc}" -eq 0 ] && ok "no-UPS path rc=0" || ko "no-UPS rc=${rc}"
echo "${out}" | grep -q "verdict=no-ups" \
  && ok "no-UPS path emits verdict=no-ups" || ko "no-ups verdict missing"
echo "${out}" | grep -qv "firing: shutdown" \
  && ok "no-UPS path does NOT attempt shutdown" \
  || ko "no-UPS path tried to shutdown"

# ---- arm gate: critical battery without arm flag is loud but no shutdown ----
# Construct a config + override the probe to return verdict=critical.
TMP="$(mktemp -d -t r253.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT

# Build a fake power-status.py that always returns critical.
mkdir -p "${TMP}/scripts/hardware"
cat > "${TMP}/scripts/hardware/power-status.py" <<'PY'
#!/usr/bin/env python3
import json, sys
print(json.dumps({
    "round": "R252",
    "verdict": "critical",
    "thresholds": {"battery_critical_pct": 15, "runtime_warn_minutes": 5,
                   "shutdown_minutes": 2, "enabled": False},
    "ups_present": True,
    "live": {"battery_charge_pct": 10, "time_left_minutes": 1.5},
    "advisories": ["battery 10% ≤ critical 15%"],
}))
sys.exit(1)  # advisories exits 1 when critical
PY
chmod +x "${TMP}/scripts/hardware/power-status.py"

# Copy the hook + adjust REPO_ROOT resolution by placing hook in
# matching path.
mkdir -p "${TMP}/scripts/hooks/recurrent" "${TMP}/scripts/build/lib"
cp "${HOOK}" "${TMP}/scripts/hooks/recurrent/power-shutdown-guard.sh"
chmod +x "${TMP}/scripts/hooks/recurrent/power-shutdown-guard.sh"
# Copy all of scripts/build/lib/ — common.sh sources its siblings.
cp -r "${__REPO_ROOT}/scripts/build/lib"/* "${TMP}/scripts/build/lib/"
# textfile collector dir for metric emission
mkdir -p "${TMP}/var/textfile"
export SOVEREIGN_OS_METRICS_DIR="${TMP}/var/textfile"

# Run hook with NO armed flag — should log WARN + exit 0.
set +e
out="$("${TMP}/scripts/hooks/recurrent/power-shutdown-guard.sh" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "critical-but-not-armed path rc=0 (no shutdown)" \
  || ko "expected rc=0, got ${rc}"
echo "${out}" | grep -qi "shutdown NOT ARMED" \
  && ok "critical-but-not-armed warns 'not armed'" || ko "not-armed warning missing"
echo "${out}" | grep -qv "firing: shutdown" \
  && ok "critical-but-not-armed does NOT call shutdown(8)" \
  || ko "tried to fire shutdown without arm"

# ---- arm gate: critical + armed + DRY-RUN env still no-op ----
out="$(SOVEREIGN_OS_DRY_RUN=1 SOVEREIGN_OS_POWER_SHUTDOWN_ARMED=YES \
  "${TMP}/scripts/hooks/recurrent/power-shutdown-guard.sh" 2>&1)"
echo "${out}" | grep -q "DRY-RUN" \
  && ok "DRY-RUN short-circuits even when armed" \
  || ko "DRY-RUN bypass failed"

echo
total=$((pass + fail))
echo "test_power_shutdown_guard: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
