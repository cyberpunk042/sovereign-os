#!/usr/bin/env bash
# tests/nspawn/test_thermal_integration.sh — R265 (E1.M11).
# Heat integration into power-status advisories.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/power-status.py"

echo "tests/nspawn/test_thermal_integration.sh"
echo

grep -q "R265\|E1.M11" "${SCRIPT}" && ok "power-status.py cites R265 / E1.M11" \
  || ko "R265 ref missing"
grep -q "probe_thermal_breach" "${SCRIPT}" \
  && ok "probe_thermal_breach helper present" || ko "thermal probe missing"

TMP="$(mktemp -d -t r265.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
mkdir -p "${TMP}/textfile"
export SOVEREIGN_OS_METRICS_DIR="${TMP}/textfile"

# ---- baseline: no thermal data → telemetry_present=false, verdict unaffected by heat ----
out="$(python3 "${SCRIPT}" advisories --json 2>/dev/null || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
t = d['thermal']
assert t['telemetry_present'] is False, t
assert t['critical_count'] == 0, t
assert t['warn_count'] == 0, t
# No thermal data → no thermal-driven verdict escalation.
" \
  && ok "no thermal data → telemetry_present=False, no heat escalation" \
  || ko "no-data shape wrong"

# ---- synthetic CRITICAL sensor → verdict escalates to critical ----
cat > "${TMP}/textfile/sovereign-os-thermal-watch.prom" <<'PROM'
sovereign_os_thermal_severity{sensor="gpu0",level="critical"} 1
sovereign_os_thermal_severity{sensor="cpu_pkg",level="warn"} 0
sovereign_os_thermal_breach_total 1
PROM
set +e
out="$(python3 "${SCRIPT}" advisories --json 2>/dev/null)"
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "thermal CRITICAL → rc=1 (operator alert)" \
  || ko "expected rc=1, got ${rc}"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
t = d['thermal']
assert t['critical_count'] == 1, t
assert 'gpu0' in t['critical_sensors'], t
assert d['verdict'] == 'critical', d
assert any('thermal CRITICAL' in a for a in d['advisories']), d
" \
  && ok "thermal CRITICAL → verdict=critical with GPU sensor named in advisory" \
  || ko "thermal-critical escalation wrong"

# ---- synthetic WARN-only sensor → verdict=attention (no critical) ----
cat > "${TMP}/textfile/sovereign-os-thermal-watch.prom" <<'PROM'
sovereign_os_thermal_severity{sensor="gpu0",level="critical"} 0
sovereign_os_thermal_severity{sensor="cpu_pkg",level="warn"} 1
sovereign_os_thermal_severity{sensor="gpu1",level="warn"} 1
sovereign_os_thermal_breach_total 2
PROM
set +e
out="$(python3 "${SCRIPT}" advisories --json 2>/dev/null)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "thermal WARN only → rc=0 (informational)" \
  || ko "expected rc=0, got ${rc}"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
t = d['thermal']
assert t['critical_count'] == 0, t
assert t['warn_count'] == 2, t
assert d['verdict'] == 'attention', d
assert any('thermal WARN' in a for a in d['advisories']), d
" \
  && ok "thermal WARN-only → verdict=attention, no critical escalation" \
  || ko "warn-only shape wrong"

# ---- mixed: WARN + CRITICAL → CRITICAL wins ----
cat > "${TMP}/textfile/sovereign-os-thermal-watch.prom" <<'PROM'
sovereign_os_thermal_severity{sensor="gpu0",level="critical"} 1
sovereign_os_thermal_severity{sensor="cpu_pkg",level="warn"} 1
sovereign_os_thermal_breach_total 2
PROM
out="$(python3 "${SCRIPT}" advisories --json 2>/dev/null || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['verdict'] == 'critical', d
# Both advisories emitted? No — when critical present, only critical
# advisory should land (precedence). Verify our behavior either way:
" \
  && ok "mixed warn+critical: verdict=critical (precedence)" \
  || ko "mixed-thermal verdict wrong"

# ---- telemetry_present=True when prom file exists (even with zero breaches) ----
cat > "${TMP}/textfile/sovereign-os-thermal-watch.prom" <<'PROM'
sovereign_os_thermal_severity{sensor="gpu0",level="warn"} 0
sovereign_os_thermal_severity{sensor="cpu_pkg",level="warn"} 0
sovereign_os_thermal_breach_total 0
PROM
out="$(python3 "${SCRIPT}" advisories --json 2>/dev/null || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
t = d['thermal']
assert t['telemetry_present'] is True, t
assert t['critical_count'] == 0, t
assert t['warn_count'] == 0, t
" \
  && ok "telemetry present, zero breaches → no heat advisory" \
  || ko "zero-breach shape wrong"

# ---- breach_total_metric surfaced ----
cat > "${TMP}/textfile/sovereign-os-thermal-watch.prom" <<'PROM'
sovereign_os_thermal_severity{sensor="gpu0",level="critical"} 1
sovereign_os_thermal_breach_total 7
PROM
out="$(python3 "${SCRIPT}" advisories --json 2>/dev/null || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['thermal']['breach_total_metric'] == 7.0, d
" \
  && ok "breach_total_metric parsed + surfaced in JSON" \
  || ko "breach_total parsing wrong"

# ---- malformed .prom lines tolerated ----
cat > "${TMP}/textfile/sovereign-os-thermal-watch.prom" <<'PROM'
# this is a comment
sovereign_os_thermal_severity{garbled
not a metric line at all
sovereign_os_thermal_severity{sensor="gpu0",level="critical"} 1
PROM
out="$(python3 "${SCRIPT}" advisories --json 2>/dev/null || true)"
echo "${out}" | python3 -c "
import json, sys
d = json.load(sys.stdin)
# The one valid critical sensor still lands.
assert d['thermal']['critical_count'] == 1, d
" \
  && ok "malformed .prom lines tolerated (one valid critical still surfaces)" \
  || ko "malformed-tolerance wrong"

echo
total=$((pass + fail))
echo "test_thermal_integration: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
