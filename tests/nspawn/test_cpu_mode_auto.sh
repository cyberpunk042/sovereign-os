#!/usr/bin/env bash
# tests/nspawn/test_cpu_mode_auto.sh — R230 (SDD-026 Z-4) workload-aware
# CPU mode auto recommendation. Reads R215 inference + R219 GPU watt
# .prom files and decides which mode to recommend (optionally apply).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/cpu-mode.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_cpu_mode_auto.sh"
echo

[ -x "${SCRIPT}" ] && ok "cpu-mode.py executable" \
  || { ko "missing cpu-mode.py"; exit 1; }
grep -q "R230" "${SCRIPT}" && ok "cpu-mode.py cites R230" || ko "no R230 ref"
grep -q "cpu-mode auto" "${OSCTL}" \
  && ok "osctl help documents 'cpu-mode auto'" || ko "osctl help missing"

# ---- no signals → recommend balanced (safe default) ----
TMP="$(mktemp -d -t r230.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
out="$(SOVEREIGN_OS_METRICS_DIR="${TMP}/empty" python3 "${SCRIPT}" auto --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R230', d
assert d['signals']['signals_present'] is False, d
assert d['recommendation']=='balanced', d
assert 'no Layer B signals' in d['reason'], d
" \
  && ok "no signals → recommend balanced + reason cites missing signals" \
  || ko "no-signals path wrong: ${out}"

# ---- high GPU draw → peak-inference ----
mkdir -p "${TMP}/peak"
cat > "${TMP}/peak/sovereign-os-gpu-watch.prom" <<'PROM'
# HELP
# TYPE sovereign_os_gpu_power_draw_watts gauge
sovereign_os_gpu_power_draw_watts{gpu="3090",idx="0"} 240
sovereign_os_gpu_power_draw_watts{gpu="6000",idx="1"} 80
PROM
out="$(SOVEREIGN_OS_METRICS_DIR="${TMP}/peak" python3 "${SCRIPT}" auto --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['recommendation']=='peak-inference', d
assert d['target_governor']=='performance', d
assert d['signals']['gpu_draw_max_watts']==240.0, d
assert '200' in d['reason'], d
" \
  && ok "gpu_draw_max=240 W → recommend peak-inference" \
  || ko "peak-inference path wrong: ${out}"

# ---- mid GPU draw → sustained-burst ----
mkdir -p "${TMP}/mid"
cat > "${TMP}/mid/sovereign-os-gpu-watch.prom" <<'PROM'
sovereign_os_gpu_power_draw_watts{gpu="3090",idx="0"} 150
PROM
out="$(SOVEREIGN_OS_METRICS_DIR="${TMP}/mid" python3 "${SCRIPT}" auto --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['recommendation']=='sustained-burst', d
assert d['signals']['gpu_draw_max_watts']==150.0, d
" \
  && ok "gpu_draw_max=150 W → recommend sustained-burst" \
  || ko "sustained-burst path wrong: ${out}"

# ---- inference routes > 0, cold GPU → balanced (active but light) ----
mkdir -p "${TMP}/active"
cat > "${TMP}/active/sovereign-os-inference-router.prom" <<'PROM'
sovereign_os_inference_router_class_total{class="llm"} 42
sovereign_os_inference_router_class_total{class="slm"} 17
PROM
cat > "${TMP}/active/sovereign-os-gpu-watch.prom" <<'PROM'
sovereign_os_gpu_power_draw_watts{gpu="3090",idx="0"} 25
PROM
out="$(SOVEREIGN_OS_METRICS_DIR="${TMP}/active" python3 "${SCRIPT}" auto --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['recommendation']=='balanced', d
assert d['signals']['inference_router_total']==59.0, d
assert 'inference router served 59' in d['reason'], d
" \
  && ok "active inference + cold GPU → recommend balanced" \
  || ko "active-cold path wrong: ${out}"

# ---- --aggressive with no signals drops to ultra-low-power ----
out="$(SOVEREIGN_OS_METRICS_DIR="${TMP}/empty" python3 "${SCRIPT}" auto --aggressive --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['recommendation']=='ultra-low-power', d
assert '--aggressive' in d['reason'], d
" \
  && ok "--aggressive + no signals → ultra-low-power" \
  || ko "aggressive path wrong: ${out}"

# ---- --aggressive does NOT downgrade when signals exist ----
# (active inference should stay at balanced even with --aggressive,
# because aggressive only kicks in when signals_present is False)
out="$(SOVEREIGN_OS_METRICS_DIR="${TMP}/active" python3 "${SCRIPT}" auto --aggressive --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['recommendation']=='balanced', d
assert d['aggressive'] is True, d
" \
  && ok "--aggressive does not override real signals" \
  || ko "aggressive over-rode signals: ${out}"

# ---- human render carries banner + signals + reason ----
out="$(SOVEREIGN_OS_METRICS_DIR="${TMP}/peak" python3 "${SCRIPT}" auto)"
echo "${out}" | grep -q "R230 sovereign-os cpu-mode auto" \
  && ok "human render carries R230 banner" || ko "no banner"
echo "${out}" | grep -q "recommendation: peak-inference" \
  && ok "human render shows recommendation" || ko "no recommendation line"
echo "${out}" | grep -q "advisory" \
  && ok "human render notes advisory mode (no --apply)" \
  || ko "advisory note missing"

# ---- --apply WITHOUT root prints the actionable command + rc!=0 ----
# (this host runs as non-root in CI; cmd_set returns 2 with a shell-cmd hint)
set +e
out_apply="$(SOVEREIGN_OS_METRICS_DIR="${TMP}/peak" python3 "${SCRIPT}" auto --apply 2>&1)"
rc_apply=$?
set -e
# rc may be 2 (root needed) or 0 (already-on-target). Both are valid.
if echo "${out_apply}" | grep -qE "Not running as root|APPLIED|no change needed|cpufreq subsystem unavailable|FAILED"; then
  ok "--apply path emits operator-readable status (rc=${rc_apply})"
else
  ko "--apply output unexpected: ${out_apply}"
fi

# ---- osctl bridge: cpu-mode auto ----
set +e
"${OSCTL}" cpu-mode auto --json > "${TMP}/osctl.out" 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl cpu-mode auto rc=0" \
  || ko "osctl bridge rc=${rc}: $(cat "${TMP}/osctl.out")"
python3 -c "
import json
d=json.load(open('${TMP}/osctl.out'))
assert d['round']=='R230', d
" \
  && ok "osctl bridge surfaces R230 JSON" \
  || ko "osctl JSON wrong"

echo
total=$((pass + fail))
echo "test_cpu_mode_auto: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
