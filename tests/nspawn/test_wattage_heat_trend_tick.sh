#!/usr/bin/env bash
# tests/nspawn/test_wattage_heat_trend_tick.sh — E1.M36 trend driver L3.
#
# The wattage-heat-trend-tick hook must run on any host, advance the rolling
# window (tick), and emit its 5 Layer B trend series — with the -1 sentinel
# for signals that have insufficient data / unavailable probes, rather than
# dropping the series. Runtime complement to the lint-layer hooks contract.

set -euo pipefail

__REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HOOK="${__REPO_ROOT}/scripts/hooks/recurrent/wattage-heat-trend-tick.sh"

pass=0; total=0
ok() { pass=$((pass + 1)); total=$((total + 1)); echo "  PASS: $*"; }
ko() { total=$((total + 1)); echo "  FAIL: $*" >&2; }

echo "tests/nspawn/test_wattage_heat_trend_tick.sh"
[ -x "${HOOK}" ] || { echo "FAIL: hook missing/not executable: ${HOOK}" >&2; exit 1; }

tmp="$(mktemp -d)"; trap 'rm -rf "${tmp}"' EXIT
export SOVEREIGN_OS_LOG_DIR="${tmp}/log"
export SOVEREIGN_OS_METRICS_DIR="${tmp}/metrics"

dry_out="$(SOVEREIGN_OS_DRY_RUN=1 "${HOOK}" 2>&1)"
grep -q "would emit" <<< "${dry_out}" && ok "honors SOVEREIGN_OS_DRY_RUN=1" || ko "missing dry-run line"
[ -f "${SOVEREIGN_OS_METRICS_DIR}/sovereign-os-wattage-heat-trend.prom" ] \
  && ko "dry-run wrote a .prom (should not)" || ok "dry-run wrote no .prom"

set +e; out="$("${HOOK}" 2>&1)"; rc=$?; set -e
[ "${rc}" -eq 0 ] && ok "real run exits 0" || ko "real run rc=${rc}: ${out:0:200}"

prom="${SOVEREIGN_OS_METRICS_DIR}/sovereign-os-wattage-heat-trend.prom"
[ -f "${prom}" ] && ok "emitted sovereign-os-wattage-heat-trend.prom" || ko "metrics file missing"

for key in \
  sovereign_os_wattage_heat_trend_verdict \
  sovereign_os_wattage_heat_trend_wattage \
  sovereign_os_wattage_heat_trend_cpu_temp \
  sovereign_os_wattage_heat_trend_gpu_temp \
  sovereign_os_wattage_heat_trend_last_run_timestamp; do
  grep -qE "^${key} " "${prom}" 2>/dev/null && ok "metric ${key} emitted" || ko "metric ${key} missing"
done

vline="$(grep -E '^sovereign_os_wattage_heat_trend_verdict ' "${prom}" 2>/dev/null || true)"
vval="${vline##* }"
case "${vval}" in
  0|1|2|-1) ok "verdict is a documented code (${vval})" ;;
  *) ko "verdict unexpected value: ${vval}" ;;
esac

echo "test_wattage_heat_trend_tick: ${pass}/${total} passed"
[ "${pass}" -eq "${total}" ] || exit 1
echo "ALL OK"
