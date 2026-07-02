#!/usr/bin/env bash
# tests/nspawn/test_gpu_watch.sh — R219 (SDD-026 Z-5) GPU watt
# deviance watcher. Uses a fake nvidia-smi shim in PATH so the test
# runs on CI hosts without real NVIDIA GPUs.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/gpu-watch.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"
POLICY="${__REPO_ROOT}/config/gpu-policy.toml.example"

echo "tests/nspawn/test_gpu_watch.sh"
echo

[ -x "${SCRIPT}" ] && ok "gpu-watch.py executable" \
  || { ko "missing gpu-watch.py"; exit 1; }
[ -f "${POLICY}" ] && ok "gpu-policy.toml.example committed" \
  || ko "policy example missing"
grep -q "gpu-watch)" "${OSCTL}" \
  && ok "osctl bridges 'gpu-watch'" \
  || ko "osctl bridge missing"
grep -q "R219" "${OSCTL}" \
  && ok "osctl cites R219" || ko "R219 citation missing"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

# ---- Fake nvidia-smi shim that emits the canonical CSV format ----
# 3 GPUs:
#   idx=0  RTX PRO 6000 Blackwell  draw=275 limit=600  → within policy
#   idx=1  RTX 4090                 draw=180 limit=350  → DEVIANCE
#                                                        (policy wants 280)
#   idx=2  Tesla T4                 draw=15  limit=70   → unpoliced (no
#                                                        policy match)
SHIM_DIR="${WORK}/bin"
mkdir -p "${SHIM_DIR}"
cat > "${SHIM_DIR}/nvidia-smi" <<'EOF'
#!/usr/bin/env bash
# fake nvidia-smi for R219 L3 test
case "$*" in
  *"--query-gpu=index,name,power.draw,power.limit"*)
    cat <<CSV
0, NVIDIA RTX PRO 6000 Blackwell, 275, 600
1, NVIDIA GeForce RTX 4090, 180, 350
2, Tesla T4, 15, 70
CSV
    ;;
  *) echo "fake nvidia-smi: unknown args $*" >&2; exit 2 ;;
esac
EOF
chmod +x "${SHIM_DIR}/nvidia-smi"

# ---- Case 1: SAIN-01 shape (4090 deviant) → rc=1 ----
set +e
PATH="${SHIM_DIR}:${PATH}" python3 "${SCRIPT}" --policy "${POLICY}" \
  > "${WORK}/banner.txt" 2>&1
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "deviance detected → rc=1" \
  || ko "expected rc=1 on deviance, got ${rc}"

grep -q "R219 sovereign-os gpu-watch" "${WORK}/banner.txt" \
  && ok "R219 banner present" || ko "no R219 banner"

# RTX PRO 6000 should pass (within 10 W tolerance of 600 W).
grep -qE "✓ NVIDIA RTX PRO 6000.*draw=275W.*limit=600W" "${WORK}/banner.txt" \
  && ok "RTX PRO 6000 passes (draw=275 limit=600 within policy)" \
  || ko "RTX PRO 6000 line wrong: $(grep -F PRO ${WORK}/banner.txt)"

# RTX 4090 should DEVIATE (350 > 280 + 10 tolerance).
grep -qE "⚠ NVIDIA GeForce RTX 4090.*draw=180W.*limit=350W" "${WORK}/banner.txt" \
  && ok "RTX 4090 flagged with banner emoji" \
  || ko "RTX 4090 deviance line missing"
grep -q "350W is above operator-set safe_limit 280W" "${WORK}/banner.txt" \
  && ok "deviance reason cites actual + safe + direction" \
  || ko "deviance reason wrong"
grep -q "nvidia-smi -i 1 -pl 280" "${WORK}/banner.txt" \
  && ok "actionable fix command cited" || ko "fix command missing"

# Tesla T4 should be unpoliced (no model_hint match).
grep -qE "◌ Tesla T4.*no policy match" "${WORK}/banner.txt" \
  && ok "unpoliced GPU rendered with operator-readable marker" \
  || ko "Tesla T4 unpoliced line wrong"

# ---- Case 2: --json shape ----
set +e
PATH="${SHIM_DIR}:${PATH}" python3 "${SCRIPT}" --policy "${POLICY}" --json \
  > "${WORK}/out.json" 2>&1
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "--json deviance rc=1" || ko "json rc=${rc}"
python3 - "${WORK}/out.json" <<'PY' 2>/dev/null \
  && ok "JSON shape correct + deviance + fix_command surfaced" \
  || ko "JSON shape wrong"
import json, sys
d = json.load(open(sys.argv[1]))
assert d["any_deviance"] is True, d
gpus = d["gpus"]
assert len(gpus) == 3, gpus
pro6000 = next(g for g in gpus if "PRO 6000" in g["name"])
assert pro6000["policed"] is True
assert pro6000["flags"] == [], pro6000["flags"]
rtx4090 = next(g for g in gpus if "RTX 4090" in g["name"])
assert rtx4090["policed"] is True
assert len(rtx4090["flags"]) >= 1
assert "350" in rtx4090["flags"][0] and "280" in rtx4090["flags"][0]
assert rtx4090["fix_command"] == "nvidia-smi -i 1 -pl 280"
t4 = next(g for g in gpus if g["name"] == "Tesla T4")
assert t4["policed"] is False, t4
PY

# ---- Case 3: --emit-metrics writes textfile ----
metrics_path="${WORK}/sovereign-os-gpu-watch.prom"
set +e
PATH="${SHIM_DIR}:${PATH}" python3 "${SCRIPT}" --policy "${POLICY}" \
  --emit-metrics --metrics-path "${metrics_path}" > /dev/null 2>&1
set -e
[ -f "${metrics_path}" ] && ok "metrics .prom file written" \
  || ko "metrics file missing"
grep -q "^# TYPE sovereign_os_gpu_power_limit_deviance_watts gauge" "${metrics_path}" \
  && ok "deviance gauge declared" || ko "deviance gauge missing"
grep -qE '^sovereign_os_gpu_power_limit_deviance_watts\{gpu="NVIDIA GeForce RTX 4090",idx="1"\} 70' "${metrics_path}" \
  && ok "RTX 4090 deviance gauge = 70 W (350 - 280)" \
  || ko "deviance gauge wrong"
grep -qE '^sovereign_os_gpu_power_draw_watts\{gpu="NVIDIA RTX PRO 6000 Blackwell",idx="0"\} 275' "${metrics_path}" \
  && ok "RTX PRO 6000 draw gauge correct" || ko "draw gauge wrong"

# ---- Case 4: all-conformant policy → rc=0 ----
cat > "${WORK}/conformant.toml" <<'EOF'
[gpu."NVIDIA RTX PRO 6000"]
safe_limit_watts = 600
tolerance_watts  = 10

[gpu."RTX 4090"]
safe_limit_watts = 350
tolerance_watts  = 10
EOF
set +e
PATH="${SHIM_DIR}:${PATH}" python3 "${SCRIPT}" --policy "${WORK}/conformant.toml" \
  > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "all-conformant policy → rc=0" \
  || ko "expected rc=0 on conformant, got ${rc}"

# ---- Case 5: no nvidia-smi → clean empty banner, rc=0 ----
set +e
PATH="/usr/bin:/bin" python3 "${SCRIPT}" --policy "${POLICY}" \
  > "${WORK}/no-gpu.txt" 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "no-nvidia-smi host → rc=0 (clean exit)" \
  || ko "no-gpu expected rc=0, got ${rc}"
grep -q "no GPUs detected" "${WORK}/no-gpu.txt" \
  && ok "no-gpu banner cites nvidia-smi unavailable" \
  || ko "no-gpu banner wrong"

# ---- Case 6: osctl bridge ----
set +e
PATH="${SHIM_DIR}:${PATH}" "${OSCTL}" gpu-watch --policy "${POLICY}" \
  > "${WORK}/osctl.txt" 2>&1
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "osctl gpu-watch propagates rc=1" \
  || ko "osctl bridge rc wrong (${rc})"
grep -q "R219 sovereign-os gpu-watch" "${WORK}/osctl.txt" \
  && ok "osctl bridge surfaces banner" || ko "osctl banner missing"

echo
total=$((pass + fail))
echo "test_gpu_watch: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
