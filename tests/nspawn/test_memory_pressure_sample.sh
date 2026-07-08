#!/usr/bin/env bash
# tests/nspawn/test_memory_pressure_sample.sh — E1.M15 Layer B sampler L3.
#
# The memory-pressure-sample recurrent hook must run on ANY host (CI runners
# / containers often lack /proc/pressure pre-4.20 PSI and cgroup v2
# memory.events) and STILL emit its full Layer B metric set — with the -1
# sentinel for the PSI series when PSI is unavailable, rather than dropping
# the series. This is the runtime complement to the lint-layer
# recurrent-hooks contract (which only checks structure).

set -euo pipefail

__REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HOOK="${__REPO_ROOT}/scripts/hooks/recurrent/memory-pressure-sample.sh"

pass=0
total=0
ok() { pass=$((pass + 1)); total=$((total + 1)); echo "  PASS: $*"; }
ko() { total=$((total + 1)); echo "  FAIL: $*" >&2; }

echo "tests/nspawn/test_memory_pressure_sample.sh"

[ -x "${HOOK}" ] || { echo "FAIL: hook missing/not executable: ${HOOK}" >&2; exit 1; }

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
export SOVEREIGN_OS_LOG_DIR="${tmp}/log"
export SOVEREIGN_OS_METRICS_DIR="${tmp}/metrics"

# ── 1. DRY-RUN honored ──────────────────────────────────────────────
dry_out="$(SOVEREIGN_OS_DRY_RUN=1 "${HOOK}" 2>&1)"
if grep -q "would emit" <<< "${dry_out}"; then
  ok "honors SOVEREIGN_OS_DRY_RUN=1 (no file written)"
else
  ko "missing dry-run 'would emit' line"
fi
[ -f "${SOVEREIGN_OS_METRICS_DIR}/sovereign-os-memory-pressure-sample.prom" ] \
  && ko "dry-run wrote a .prom file (should not)" \
  || ok "dry-run wrote no .prom file"

# ── 2. real run exits 0 + writes the .prom ──────────────────────────
set +e
out="$("${HOOK}" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "real run exits 0" || ko "real run rc=${rc}: ${out:0:200}"

prom="${SOVEREIGN_OS_METRICS_DIR}/sovereign-os-memory-pressure-sample.prom"
[ -f "${prom}" ] && ok "emitted sovereign-os-memory-pressure-sample.prom" \
  || ko "metrics file missing"

# ── 3. all 7 Layer B series present (even when PSI unavailable) ──────
for key in \
  sovereign_os_memory_available_pct \
  sovereign_os_memory_swap_used_pct \
  sovereign_os_memory_psi_some_avg60_pct \
  sovereign_os_memory_psi_full_avg10_pct \
  sovereign_os_memory_oom_kill_count \
  sovereign_os_memory_pressure_verdict \
  sovereign_os_memory_sample_last_run_timestamp; do
  if grep -qE "^${key} " "${prom}" 2>/dev/null; then
    ok "metric ${key} emitted"
  else
    ko "metric ${key} missing from ${prom}"
  fi
done

# ── 4. verdict is one of the documented codes {0,1,2,-1} ────────────
verdict_line="$(grep -E '^sovereign_os_memory_pressure_verdict ' "${prom}" 2>/dev/null || true)"
verdict_val="${verdict_line##* }"
case "${verdict_val}" in
  0|1|2|-1) ok "pressure_verdict is a documented code (${verdict_val})" ;;
  *) ko "pressure_verdict unexpected value: ${verdict_val}" ;;
esac

echo "test_memory_pressure_sample: ${pass}/${total} passed"
[ "${pass}" -eq "${total}" ] || exit 1
echo "ALL OK"
