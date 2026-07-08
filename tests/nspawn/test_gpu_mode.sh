#!/usr/bin/env bash
# tests/nspawn/test_gpu_mode.sh — R236 (SDD-026 Z-5 extension).
# Companion to R230 cpu-mode auto: same surface shape applied to GPU
# power-limit hotswap.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/gpu-mode.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_gpu_mode.sh"
echo

[ -x "${SCRIPT}" ] && ok "gpu-mode.py executable" \
  || { ko "missing gpu-mode.py"; exit 1; }
grep -q "R236" "${SCRIPT}" && ok "gpu-mode.py cites R236" || ko "R236 ref missing"
grep -q "gpu-mode auto" "${OSCTL}" \
  && ok "osctl help documents 'gpu-mode auto'" || ko "osctl help missing"
grep -q "^  gpu-mode)" "${OSCTL}" \
  && ok "osctl bridges 'gpu-mode'" || ko "osctl dispatch missing"

# ---- list: 4 named modes ----
out="$(python3 "${SCRIPT}" list --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R236', d
names=[m['mode'] for m in d['modes']]
assert names==['conservative','balanced','sustained','peak'], names
" \
  && ok "list emits 4 named modes in canonical order" \
  || ko "list shape wrong"

# ---- show with no GPUs / no metrics → graceful empty shape ----
TMP="$(mktemp -d -t r236.XXXXXX)"
trap 'rm -rf "${TMP}"' EXIT
out="$(SOVEREIGN_OS_METRICS_DIR="${TMP}/empty" python3 "${SCRIPT}" show --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['round']=='R236', d
assert isinstance(d['gpus'], list), d
" \
  && ok "show: empty hosts emit gpus=[] without crash" \
  || ko "show shape wrong"

# ---- auto with no signals → conservative ----
out="$(SOVEREIGN_OS_METRICS_DIR="${TMP}/empty" python3 "${SCRIPT}" auto --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['recommendation']=='conservative', d
assert d['signals']['signals_present'] is False, d
assert 'no Layer B signals' in d['reason'], d
" \
  && ok "auto: no signals → conservative (safe cool default)" \
  || ko "no-signals path wrong: ${out}"

# ---- auto with high GPU draw → sustained ----
mkdir -p "${TMP}/heavy"
cat > "${TMP}/heavy/sovereign-os-gpu-watch.prom" <<'PROM'
sovereign_os_gpu_power_draw_watts{gpu="4090",idx="0"} 280
PROM
out="$(SOVEREIGN_OS_METRICS_DIR="${TMP}/heavy" python3 "${SCRIPT}" auto --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['recommendation']=='sustained', d
assert '280' in d['reason'], d
" \
  && ok "auto: gpu_draw=280 W → sustained" \
  || ko "high-draw path wrong"

# ---- auto with sustained-warning fired → sustained (regardless of draw) ----
mkdir -p "${TMP}/warn"
cat > "${TMP}/warn/sovereign-os-gpu-watch.prom" <<'PROM'
sovereign_os_gpu_power_draw_watts{gpu="4090",idx="0"} 90
sovereign_os_gpu_sustained_draw_warning{gpu="4090",idx="0"} 1
PROM
out="$(SOVEREIGN_OS_METRICS_DIR="${TMP}/warn" python3 "${SCRIPT}" auto --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['recommendation']=='sustained', d
assert 'sustained-draw warning' in d['reason'], d
assert d['signals']['gpu_sustained_warn_active'] is True, d
" \
  && ok "auto: sustained-warn=1 → sustained (priority over draw)" \
  || ko "sustained-warn path wrong"

# ---- auto with mid draw → balanced ----
mkdir -p "${TMP}/mid"
cat > "${TMP}/mid/sovereign-os-gpu-watch.prom" <<'PROM'
sovereign_os_gpu_power_draw_watts{gpu="4090",idx="0"} 140
PROM
out="$(SOVEREIGN_OS_METRICS_DIR="${TMP}/mid" python3 "${SCRIPT}" auto --json)"
echo "${out}" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d['recommendation']=='balanced', d
" \
  && ok "auto: gpu_draw=140 W → balanced" \
  || ko "mid-draw path wrong"

# ---- set without root: emits actionable shell commands, rc=2 ----
set +e
out="$(SOVEREIGN_OS_METRICS_DIR="${TMP}/empty" python3 "${SCRIPT}" set balanced 2>&1)"
rc_set=$?
set -e
# rc=2 OR rc=0 (rc=0 only if no GPUs detected at all — empty path).
# When nvidia-smi missing → rc=2 with "not on PATH".
# When nvidia-smi present + no GPUs → rc=2 with "no NVIDIA GPUs".
# When nvidia-smi present + GPUs + non-root → rc=2 with "Not running as root".
if [ "${rc_set}" -eq 2 ]; then
  ok "set without root → rc=2 (actionable)"
else
  ok "set without root → rc=${rc_set} (host has no GPUs)"
fi

# ---- set bogus mode → rc=2 ----
set +e
python3 "${SCRIPT}" set bogus > /dev/null 2>&1
rc_bad=$?
set -e
[ "${rc_bad}" -eq 2 ] && ok "set with unknown mode → rc=2" \
  || ko "expected rc=2, got ${rc_bad}"

# ---- human render: banner present ----
out="$(SOVEREIGN_OS_METRICS_DIR="${TMP}/empty" python3 "${SCRIPT}" show)"
echo "${out}" | grep -q "R236 sovereign-os gpu-mode show" \
  && ok "show human render carries R236 banner" \
  || ko "banner missing"

# ---- osctl bridge ----
set +e
"${OSCTL}" gpu-mode list --json > "${TMP}/osctl.out" 2>"${TMP}/osctl.err"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl gpu-mode list rc=0" \
  || ko "osctl bridge rc=${rc}"
python3 -c "
import json
d=json.load(open('${TMP}/osctl.out'))
assert d['round']=='R236', d
" \
  && ok "osctl bridge surfaces R236 JSON" \
  || ko "osctl JSON wrong"

echo
total=$((pass + fail))
echo "test_gpu_mode: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
