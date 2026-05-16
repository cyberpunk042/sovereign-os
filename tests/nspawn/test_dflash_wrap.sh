#!/usr/bin/env bash
# tests/nspawn/test_dflash_wrap.sh
#
# Layer 3 test for R157 — scripts/inference/dflash-wrap.sh
# (DFlash speculative decoding wrapper per master spec Block 7).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/inference/dflash-wrap.sh"
SDD="${__REPO_ROOT}/docs/sdd/026-dflash-speculative-decoding.md"

echo "tests/nspawn/test_dflash_wrap.sh"
echo

[ -x "${SCRIPT}" ] && ok "dflash-wrap.sh executable" || { ko "missing"; exit 1; }
[ -f "${SDD}" ]    && ok "SDD-026 present"           || ko "SDD missing"

# ---------- master spec citations ----------
if grep -qi "master spec" "${SCRIPT}" && grep -q "Block 7" "${SCRIPT}"; then
  ok "script cites master spec Block 7"
else
  ko "script missing master spec Block 7 citation"
fi
# Verbatim operator phrase encoded in the script
if grep -q "does not work on creative tasks in general" "${SCRIPT}"; then
  ok "script preserves operator's verbatim phrase 'does not work on creative...'"
else
  ko "operator's verbatim phrase missing"
fi
# DFlash paper + repo provenance
if grep -q "arXiv:2602.06036" "${SCRIPT}" && grep -q "z-lab/dflash" "${SCRIPT}"; then
  ok "script cites paper + repo (L0 provenance)"
else
  ko "script missing DFlash paper/repo citation"
fi

# ---------- help screen ----------
set +e
out="$(bash "${SCRIPT}" --help 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "Gating policy" <<< "${out}"; then
  ok "--help exit 0 + describes gating policy"
else
  ko "--help broken (rc=${rc})"
fi

# ---------- gating decisions per task_type ----------
for t_decision in "code:enabled" "math:enabled" "conversational:disabled" "creative:disabled"; do
  t="${t_decision%:*}"
  expected="${t_decision#*:}"
  set +e
  out="$(SOVEREIGN_OS_DRY_RUN=1 bash "${SCRIPT}" \
         --task-type "${t}" --backend vllm -- /bin/true 2>&1)"
  rc=$?
  set -e
  if [ "${rc}" -eq 0 ] && grep -q "decision:   ${expected}" <<< "${out}"; then
    ok "task=${t} → decision=${expected}"
  else
    ko "task=${t} expected ${expected}: rc=${rc} out=${out:0:200}"
  fi
done

# ---------- operator override: force-disable on a normally-enabled task ----------
set +e
out="$(DFLASH_DISABLE_OVERRIDE=1 SOVEREIGN_OS_DRY_RUN=1 \
       bash "${SCRIPT}" --task-type code --backend vllm -- /bin/true 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "decision:   disabled" <<< "${out}" && \
   grep -q "operator-override" <<< "${out}"; then
  ok "DFLASH_DISABLE_OVERRIDE wins over task-type=code"
else
  ko "disable override broken"
fi

# ---------- operator override: force-enable on creative ----------
set +e
out="$(DFLASH_ENABLE_OVERRIDE=1 SOVEREIGN_OS_DRY_RUN=1 \
       bash "${SCRIPT}" --task-type creative --backend vllm -- /bin/true 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "decision:   enabled" <<< "${out}"; then
  ok "DFLASH_ENABLE_OVERRIDE wins over task-type=creative"
else
  ko "enable override broken"
fi

# ---------- override precedence: DISABLE wins over ENABLE ----------
set +e
out="$(DFLASH_DISABLE_OVERRIDE=1 DFLASH_ENABLE_OVERRIDE=1 SOVEREIGN_OS_DRY_RUN=1 \
       bash "${SCRIPT}" --task-type math --backend vllm -- /bin/true 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "decision:   disabled" <<< "${out}"; then
  ok "DISABLE override wins over ENABLE override (safe default)"
else
  ko "override precedence wrong"
fi

# ---------- bad task_type ----------
set +e
out="$(bash "${SCRIPT}" --task-type evil --backend vllm -- /bin/true 2>&1)"
rc=$?
set -e
if [ "${rc}" -ne 0 ] && grep -q "unknown --task-type" <<< "${out}"; then
  ok "bad --task-type → rc≠0 + clear error"
else
  ko "bad task-type path broken (rc=${rc})"
fi

# ---------- bad backend ----------
set +e
out="$(bash "${SCRIPT}" --task-type code --backend tensorflow -- /bin/true 2>&1)"
rc=$?
set -e
if [ "${rc}" -ne 0 ] && grep -q "unknown --backend" <<< "${out}"; then
  ok "bad --backend → rc≠0 + clear error"
else
  ko "bad backend path broken (rc=${rc})"
fi

# ---------- missing required args ----------
set +e
bash "${SCRIPT}" 2>&1 > /dev/null
rc=$?
set -e
if [ "${rc}" -ne 0 ]; then
  ok "missing required args → rc≠0"
else
  ko "missing args did not fail"
fi

# ---------- DFlash install absence handled gracefully ----------
set +e
out="$(DFLASH_PATH=/tmp/no-such-dflash-$$ SOVEREIGN_OS_DRY_RUN=1 \
       bash "${SCRIPT}" --task-type code --backend vllm -- /bin/true 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "DFlash not installed" <<< "${out}" && \
   grep -q "falling back to vanilla" <<< "${out}"; then
  ok "missing DFlash install → graceful WARN + fallback (no hard fail)"
else
  ko "missing-install path broken (rc=${rc})"
fi

# ---------- per-backend argv shaping (DFlash install present) ----------
DFLASH_FAKE="$(mktemp -d)"
# vllm: should append --speculative-config
set +e
out="$(DFLASH_PATH="${DFLASH_FAKE}" SOVEREIGN_OS_DRY_RUN=1 \
       bash "${SCRIPT}" --task-type code --backend vllm \
       -- /usr/bin/vllm serve foo 2>&1)"
set -e
if grep -q -- "--speculative-config" <<< "${out}"; then
  ok "vllm backend → argv gains --speculative-config when enabled"
else
  ko "vllm argv shaping missing"
fi

# llama_cpp: should append --draft-model
set +e
out="$(DFLASH_PATH="${DFLASH_FAKE}" SOVEREIGN_OS_DRY_RUN=1 \
       bash "${SCRIPT}" --task-type code --backend llama_cpp \
       -- /usr/bin/llama-server -m foo 2>&1)"
set -e
if grep -q -- "--draft-model" <<< "${out}"; then
  ok "llama_cpp backend → argv gains --draft-model when enabled"
else
  ko "llama_cpp argv shaping missing"
fi
rm -rf "${DFLASH_FAKE}"

# ---------- disabled decision does NOT mutate argv ----------
set +e
out="$(SOVEREIGN_OS_DRY_RUN=1 bash "${SCRIPT}" \
       --task-type creative --backend vllm \
       -- /usr/bin/vllm serve foo 2>&1)"
set -e
if ! grep -q -- "--speculative-config" <<< "${out}"; then
  ok "creative (disabled) → argv unchanged (no --speculative-config)"
else
  ko "disabled decision still mutated argv"
fi

# ---------- SDD content ----------
if grep -q "task_type" "${SDD}" && grep -q "verbatim" "${SDD}"; then
  ok "SDD-026 codifies gating + operator-verbatim discipline"
else
  ko "SDD-026 missing key content"
fi

echo
total=$((pass + fail))
echo "test_dflash_wrap: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
