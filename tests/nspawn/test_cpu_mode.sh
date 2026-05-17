#!/usr/bin/env bash
# tests/nspawn/test_cpu_mode.sh — R221 (SDD-026 Z-4) CPU hotswap
# modes. Read-only tests + non-root set error-path. CI runners
# typically lack /sys/devices/system/cpu/cpu*/cpufreq, which the
# script handles gracefully (cpufreq unavailable → operator-readable
# banner instead of crash).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/cpu-mode.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_cpu_mode.sh"
echo

[ -x "${SCRIPT}" ] && ok "cpu-mode.py executable" \
  || { ko "missing cpu-mode.py"; exit 1; }
grep -q "cpu-mode)" "${OSCTL}" \
  && ok "osctl bridges 'cpu-mode'" || ko "osctl bridge missing"
grep -q "R221" "${OSCTL}" \
  && ok "osctl cites R221" || ko "R221 citation missing"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

# ---- list — enumerate all 4 modes ----
set +e
python3 "${SCRIPT}" list > "${WORK}/list.txt" 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "list rc=0" || ko "list rc=${rc}"
for mode in ultra-low-power balanced sustained-burst peak-inference; do
  grep -q "${mode}" "${WORK}/list.txt" \
    && ok "list includes mode: ${mode}" \
    || ko "missing mode: ${mode}"
done

# Each mode shows its governor.
grep -q "governor=powersave" "${WORK}/list.txt" \
  && ok "ultra-low-power → powersave" || ko "powersave missing"
grep -q "governor=schedutil" "${WORK}/list.txt" \
  && ok "balanced → schedutil" || ko "schedutil missing"
grep -q "governor=performance" "${WORK}/list.txt" \
  && ok "sustained-burst/peak-inference → performance" || ko "performance missing"

# ---- list --json ----
set +e
python3 "${SCRIPT}" list --json > "${WORK}/list.json" 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "list --json rc=0" || ko "list --json rc=${rc}"
python3 - "${WORK}/list.json" <<'PY' 2>/dev/null \
  && ok "list --json shape: 4 modes with governor/summary keys" \
  || ko "list --json shape wrong"
import json, sys
d = json.load(open(sys.argv[1]))
modes = d["modes"]
assert set(modes.keys()) == {"ultra-low-power", "balanced", "sustained-burst", "peak-inference"}, modes
for name, spec in modes.items():
    assert "governor" in spec, spec
    assert "summary"  in spec, spec
PY

# ---- show — works whether cpufreq present or not ----
set +e
python3 "${SCRIPT}" show > "${WORK}/show.txt" 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "show rc=0 (cpufreq absent or present)" \
  || ko "show rc=${rc}"

# When cpufreq absent (typical CI runner without /sys/devices/system/cpu
# /cpu*/cpufreq), the script emits an operator-readable banner.
if grep -q "cpufreq subsystem unavailable" "${WORK}/show.txt"; then
  ok "show on cpufreq-less host renders graceful 'unavailable' banner"
elif grep -q "R221 sovereign-os cpu-mode" "${WORK}/show.txt"; then
  # Real cpufreq host (e.g. SAIN-01) — different output shape.
  ok "show on cpufreq-present host renders R221 banner"
else
  ko "show output unexpected: $(head -3 ${WORK}/show.txt)"
fi

# ---- show --json shape ----
set +e
python3 "${SCRIPT}" show --json > "${WORK}/show.json" 2>&1
set -e
python3 - "${WORK}/show.json" <<'PY' 2>/dev/null \
  && ok "show --json shape: cpus + matched_mode keys present" \
  || ko "show --json shape wrong"
import json, sys
d = json.load(open(sys.argv[1]))
assert "cpus" in d
# matched_mode key OR note key (cpufreq absent path)
assert "matched_mode" in d or "note" in d
PY

# ---- set <mode> — non-root → rc=2 + actionable command ----
# Only run if cpufreq actually exists; otherwise rc=2 fires for the
# "subsystem unavailable" reason regardless of euid.
if [ -d /sys/devices/system/cpu/cpu0/cpufreq ] && [ "$(id -u)" -ne 0 ]; then
  set +e
  python3 "${SCRIPT}" set balanced > "${WORK}/set.out" 2>&1
  rc=$?
  set -e
  [ "${rc}" -eq 2 ] && ok "set as non-root → rc=2" \
    || ko "expected rc=2, got ${rc}"
  grep -q "Not running as root" "${WORK}/set.out" \
    && ok "non-root set prints actionable hint" \
    || ko "actionable hint missing"
  grep -q "sudo tee" "${WORK}/set.out" \
    && ok "actionable hint cites sudo tee" \
    || ko "sudo tee command missing"
else
  ok "set non-root test SKIPPED (cpufreq absent or running as root)"
  ok "set non-root test SKIPPED (cpufreq absent or running as root)"
  ok "set non-root test SKIPPED (cpufreq absent or running as root)"
fi

# ---- set unknown mode → rc=2 ----
set +e
python3 "${SCRIPT}" set bogus-mode > "${WORK}/bogus.out" 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "set with unknown mode → rc=2" \
  || ko "expected rc=2 on bogus mode, got ${rc}"

# ---- osctl bridge default to show ----
set +e
"${OSCTL}" cpu-mode > "${WORK}/osctl-default.txt" 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl cpu-mode (no subverb) rc=0 + default to show" \
  || ko "osctl default rc=${rc}"

# ---- osctl bridge list ----
set +e
"${OSCTL}" cpu-mode list > "${WORK}/osctl-list.txt" 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl cpu-mode list rc=0" \
  || ko "osctl list rc=${rc}"
grep -q "ultra-low-power" "${WORK}/osctl-list.txt" \
  && ok "osctl list surfaces named modes" \
  || ko "osctl list missing modes"

echo
total=$((pass + fail))
echo "test_cpu_mode: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
