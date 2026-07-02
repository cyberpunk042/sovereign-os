#!/usr/bin/env bash
# tests/nspawn/test_pick_gpu.sh
#
# Layer 3 test for R178 — scripts/inference/lib/pick-gpu.py.
# Consumes the selfdef SD-R28 schedule.json and emits a
# CUDA_VISIBLE_DEVICES env-line for a requested role. Inference
# start scripts (start-pulse.sh / start-logic-engine.sh /
# start-oracle-core.sh) can source this to pin workloads on the
# largest-VRAM GPU (master spec § 17 Trinity).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/inference/lib/pick-gpu.py"

echo "tests/nspawn/test_pick_gpu.sh"
echo

[ -x "${SCRIPT}" ] && ok "pick-gpu.py executable" \
  || { ko "missing"; exit 1; }

grep -q "SD-R28" "${SCRIPT}" \
  && ok "cites selfdef SD-R28 (cross-repo provenance)" \
  || ko "SD-R28 citation missing"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

# ---------- fixture: SAIN-01 dual-GPU schedule ----------
cat > "${WORK}/schedule.json" <<'JSON'
{
  "schema_version": "1.0.0",
  "generated_at": "2026-05-16T00:00:00Z",
  "schedule": [
    {
      "gpu_index": 0,
      "role": "model_inference",
      "model_hint": "NVIDIA RTX PRO 6000 Blackwell",
      "vram_bytes": 105226698752,
      "power_limit_watts": 600
    },
    {
      "gpu_index": 1,
      "role": "auxiliary",
      "model_hint": "NVIDIA GeForce RTX 4090",
      "vram_bytes": 25769803776,
      "power_limit_watts": 350
    }
  ],
  "rationale": "ranked 2 GPU(s) by VRAM"
}
JSON

# ---------- happy path: model_inference → CUDA_VISIBLE_DEVICES=0 ----------
set +e
out="$(python3 "${SCRIPT}" model_inference --schedule "${WORK}/schedule.json" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "model_inference role exits 0" || ko "rc=${rc}"
[ "${out}" = "CUDA_VISIBLE_DEVICES=0" ] \
  && ok "model_inference → CUDA_VISIBLE_DEVICES=0 (largest-VRAM GPU)" \
  || ko "wrong gpu: '${out}'"

# ---------- happy path: auxiliary → CUDA_VISIBLE_DEVICES=1 ----------
set +e
out="$(python3 "${SCRIPT}" auxiliary --schedule "${WORK}/schedule.json" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "auxiliary role exits 0" || ko "rc=${rc}"
[ "${out}" = "CUDA_VISIBLE_DEVICES=1" ] \
  && ok "auxiliary → CUDA_VISIBLE_DEVICES=1 (RTX 4090)" \
  || ko "wrong gpu: '${out}'"

# ---------- --json mode emits full entry ----------
set +e
out="$(python3 "${SCRIPT}" model_inference --schedule "${WORK}/schedule.json" --json 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "--json exits 0" || ko "rc=${rc}"
if python3 -c "
import json
d = json.loads('''${out}''')
assert d['gpu_index'] == 0, d
assert d['model_hint'] == 'NVIDIA RTX PRO 6000 Blackwell', d
" 2>/dev/null; then
  ok "--json carries gpu_index + model_hint"
else
  ko "--json shape wrong: ${out}"
fi

# ---------- bad role rejected ----------
set +e
out="$(python3 "${SCRIPT}" not-a-role --schedule "${WORK}/schedule.json" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "bad role exits 2" || ko "expected rc=2 got ${rc}"

# ---------- missing role in schedule → rc=1 + unset line ----------
# spare isn't in the fixture schedule.
set +e
out="$(python3 "${SCRIPT}" spare --schedule "${WORK}/schedule.json" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "missing role exits 1" || ko "expected rc=1 got ${rc}"
[ "${out}" = "CUDA_VISIBLE_DEVICES=" ] \
  && ok "missing role prints unset line (clears stale state)" \
  || ko "expected unset line: '${out}'"

# ---------- absent schedule + PICK_GPU_DEFAULT fallback ----------
# Capture stdout separately from stderr — the helper logs an INFO
# line to stderr when the fallback kicks in.
set +e
out="$(PICK_GPU_DEFAULT='model_inference:0' python3 "${SCRIPT}" model_inference \
  --schedule "${WORK}/no-such.json" 2>/dev/null)"
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "fallback triggers rc=0" || ko "fallback rc=${rc}"
[ "${out}" = "CUDA_VISIBLE_DEVICES=0" ] \
  && ok "PICK_GPU_DEFAULT honored when schedule absent" \
  || ko "fallback wrong: '${out}'"

# ---------- absent schedule, no fallback → rc=1 ----------
set +e
out="$(python3 "${SCRIPT}" model_inference \
  --schedule "${WORK}/no-such.json" 2>&1)"
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "no schedule + no fallback → rc=1" || ko "rc=${rc}"

# ---------- eval-able shell consumption ----------
# The whole point: shell scripts source this via eval to pin a GPU.
set +e
eval "$(python3 "${SCRIPT}" model_inference --schedule "${WORK}/schedule.json")"
set -e
[ "${CUDA_VISIBLE_DEVICES:-}" = "0" ] \
  && ok "eval \$(pick-gpu.py model_inference) sets CUDA_VISIBLE_DEVICES" \
  || ko "eval didn't set var: '${CUDA_VISIBLE_DEVICES:-}'"

echo
total=$((pass + fail))
echo "test_pick_gpu: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
