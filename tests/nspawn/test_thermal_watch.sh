#!/usr/bin/env bash
# tests/nspawn/test_thermal_watch.sh
#
# Layer 3 test for R172 — sovereign-os thermal-watch hook +
# scripts/hardware/thermal-watch.py.
#
# Mirror surface: selfdef SD-R17 ships ThermalReading + per-sensor
# probe. Sovereign-os adds the THRESHOLD + classification + Layer B
# + JSONL event layer on top.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/thermal-watch.py"
HOOK="${__REPO_ROOT}/scripts/hooks/recurrent/thermal-watch.sh"
SVC="${__REPO_ROOT}/systemd/system/sovereign-thermal-watch.service"
TIMER="${__REPO_ROOT}/systemd/system/sovereign-thermal-watch.timer"

echo "tests/nspawn/test_thermal_watch.sh"
echo

[ -x "${SCRIPT}" ] && ok "thermal-watch.py executable" || { ko "missing"; exit 1; }
[ -x "${HOOK}" ] && ok "thermal-watch.sh hook executable" || ko "hook missing"
[ -f "${SVC}" ] && ok "service unit exists" || ko "service unit missing"
[ -f "${TIMER}" ] && ok "timer unit exists" || ko "timer unit missing"

grep -q "selfdef SD-R17\|SD-R17" "${SCRIPT}" \
  && ok "cites selfdef SD-R17 (cross-repo mirror provenance)" \
  || ko "SD-R17 citation missing"
grep -q "OnUnitActiveSec=5min" "${TIMER}" \
  && ok "timer cadence: 5 minutes (operator-visible)" \
  || ko "timer cadence missing"

# ---------- fixture: 3 sensors, one >= critical, one >= warn ----------
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT
mkdir -p "${WORK}/hwmon/hwmon0" "${WORK}/hwmon/hwmon1" \
         "${WORK}/metrics" "${WORK}/events"

# hwmon0 — k10temp with Tctl at 92°C (warn on sain-01: 85/95) +
# secondary die at 78°C (ok).
echo "k10temp" > "${WORK}/hwmon/hwmon0/name"
echo "92500" > "${WORK}/hwmon/hwmon0/temp1_input"
echo "Tctl"   > "${WORK}/hwmon/hwmon0/temp1_label"
echo "78000" > "${WORK}/hwmon/hwmon0/temp2_input"
# hwmon1 — nvme at 45°C (ok).
echo "nvme"   > "${WORK}/hwmon/hwmon1/name"
echo "45000" > "${WORK}/hwmon/hwmon1/temp1_input"

CMD=(python3 "${SCRIPT}"
     --hwmon-dir "${WORK}/hwmon"
     --no-nvidia-smi
     --dry-run-events
     --profile sain-01)

# ---------- human-readable: warn severity, rc=1 ----------
set +e
out="$("${CMD[@]}" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "rc=1 when sensor at WARN" || ko "expected rc=1, got ${rc}"
grep -q "k10temp/Tctl" <<< "${out}" \
  && grep -q "warn" <<< "${out}" \
  && ok "human output flags Tctl as warn" \
  || ko "warn classification missing: ${out}"
grep -q "k10temp/temp2" <<< "${out}" \
  && grep -q "ok" <<< "${out}" \
  && ok "human output flags temp2 as ok" \
  || ko "ok classification missing"

# ---------- --json output schema ----------
set +e
out_json="$("${CMD[@]}" --json 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "--json exits 1 at WARN" || ko "json rc=${rc}"
if python3 -c "
import json, sys
d = json.loads('''${out_json}''')
assert d['profile'] == 'sain-01'
assert d['warn_threshold'] == 85
assert d['critical_threshold'] == 95
sensors = {r['source']: r for r in d['readings']}
assert 'k10temp/Tctl' in sensors
assert sensors['k10temp/Tctl']['severity'] == 'warn'
assert sensors['k10temp/Tctl']['celsius'] == 93  # round 92500 → 93
assert sensors['k10temp/temp2']['severity'] == 'ok'
assert sensors['nvme/temp1']['severity'] == 'ok'
assert d['breach_count'] == 1
" 2>/dev/null; then
  ok "--json: profile + thresholds + per-sensor severity correct"
else
  ko "--json shape wrong: ${out_json}"
fi

# ---------- escalate to CRITICAL (96°C >= 95) ----------
echo "96000" > "${WORK}/hwmon/hwmon0/temp1_input"
set +e
"${CMD[@]}" > "${WORK}/critical.txt"
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "rc=2 when sensor at CRITICAL" || ko "expected rc=2, got ${rc}"
grep -q "critical" "${WORK}/critical.txt" \
  && ok "critical severity printed" || ko "critical missing"

# ---------- emit-metrics: writes textfile collector .prom ----------
METRICS="${WORK}/metrics/sovereign-os-thermal-watch.prom"
set +e
python3 "${SCRIPT}" \
  --hwmon-dir "${WORK}/hwmon" \
  --no-nvidia-smi --dry-run-events \
  --profile sain-01 \
  --emit-metrics \
  --metrics-path "${METRICS}" >/dev/null
set -e
[ -f "${METRICS}" ] && ok ".prom file written" || ko ".prom missing"
grep -q "sovereign_os_thermal_celsius" "${METRICS}" \
  && ok ".prom: thermal_celsius gauge present" \
  || ko "thermal_celsius gauge missing"
grep -q "sovereign_os_thermal_severity" "${METRICS}" \
  && ok ".prom: thermal_severity gauge present" \
  || ko "thermal_severity gauge missing"
grep -q "sovereign_os_thermal_breach_total 1" "${METRICS}" \
  && ok ".prom: breach_total = 1 (one CRITICAL sensor)" \
  || ko "breach_total wrong"
grep -q 'severity{sensor="k10temp/Tctl",level="critical"} 1' "${METRICS}" \
  && ok ".prom: per-sensor critical flag set correctly" \
  || ko "per-sensor critical flag missing"

# ---------- JSONL event emission on CRITICAL ----------
EVENTS="${WORK}/events/thermal.jsonl"
set +e
python3 "${SCRIPT}" \
  --hwmon-dir "${WORK}/hwmon" \
  --no-nvidia-smi \
  --events-jsonl "${EVENTS}" \
  --profile sain-01 >/dev/null
set -e
[ -f "${EVENTS}" ] && ok "JSONL event file written" || ko "JSONL event file missing"
if python3 -c "
import json
with open('${EVENTS}') as f:
    line = next(f, '').strip()
ev = json.loads(line)
assert ev['class_uid'] == 2004
assert ev['category_uid'] == 2
assert ev['severity_id'] == 5
assert ev['unmapped']['sensor'] == 'k10temp/Tctl'
assert ev['unmapped']['celsius'] == 96
assert ev['unmapped']['critical_threshold'] == 95
" 2>/dev/null; then
  ok "OCSF event well-formed (class_uid 2004, sensor + celsius + threshold)"
else
  ko "OCSF event malformed"
fi

# ---------- profile differentiation: headless has tighter thresholds ----------
echo "82000" > "${WORK}/hwmon/hwmon0/temp1_input"
set +e
python3 "${SCRIPT}" \
  --hwmon-dir "${WORK}/hwmon" \
  --no-nvidia-smi --dry-run-events \
  --profile headless --json > "${WORK}/headless.json"
hr=$?
set -e
# headless: warn=75, critical=85 → 82°C is warn
[ "${hr}" -eq 1 ] && ok "headless profile: 82°C → warn (rc=1)" \
  || ko "headless threshold differentiation broken (rc=${hr})"

# ---------- override path: per-sensor threshold tightening ----------
set +e
python3 "${SCRIPT}" \
  --hwmon-dir "${WORK}/hwmon" \
  --no-nvidia-smi --dry-run-events \
  --profile sain-01 \
  --override "k10temp/Tctl=warn:70,crit:80" \
  --json > "${WORK}/override.json"
or=$?
set -e
# Override makes 82°C critical (>= 80), so rc=2.
[ "${or}" -eq 2 ] && ok "--override tightens threshold (Tctl 82°C → critical)" \
  || ko "override path broken (rc=${or})"
python3 -c "
import json
d=json.load(open('${WORK}/override.json'))
tctl = next(r for r in d['readings'] if r['source']=='k10temp/Tctl')
assert tctl['warn_threshold']==70
assert tctl['critical_threshold']==80
assert tctl['severity']=='critical'
" && ok "--override JSON reflects per-sensor thresholds" \
  || ko "override JSON broken"

# ---------- empty hwmon: rc=0, no crash ----------
EMPTY="${WORK}/empty-hwmon"
mkdir -p "${EMPTY}"
set +e
python3 "${SCRIPT}" \
  --hwmon-dir "${EMPTY}" \
  --no-nvidia-smi --dry-run-events \
  --profile sain-01 --json > "${WORK}/empty.json"
er=$?
set -e
[ "${er}" -eq 0 ] && ok "empty hwmon → rc=0" || ko "empty hwmon rc=${er}"
python3 -c "
import json
d = json.load(open('${WORK}/empty.json'))
assert d['readings'] == []
assert d['breach_count'] == 0
" && ok "empty hwmon: zero readings, zero breaches" || ko "empty hwmon shape wrong"

# ---------- hook script honors DRY-RUN ----------
set +e
SOVEREIGN_OS_DRY_RUN=1 "${HOOK}" > "${WORK}/hook.log" 2>&1
hr=$?
set -e
[ "${hr}" -eq 0 ] && ok "hook DRY-RUN exits 0" || ko "hook DRY-RUN rc=${hr}"
grep -q "DRY-RUN" "${WORK}/hook.log" \
  && ok "hook DRY-RUN logged" || ko "hook DRY-RUN log missing"

echo
total=$((pass + fail))
echo "test_thermal_watch: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
