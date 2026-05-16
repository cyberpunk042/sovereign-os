#!/usr/bin/env bash
# tests/nspawn/test_pulse_build_bitnet.sh
#
# Layer 3 test for R152 — scripts/pulse/build-bitnet.sh.
# Verifies DRY-RUN behavior, env-var honoring, master spec citations,
# AVX-512 awareness, and the script doesn't actually clone/build/install
# under DRY-RUN.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/pulse/build-bitnet.sh"

echo "tests/nspawn/test_pulse_build_bitnet.sh"
echo

# ---------- script present + executable ----------
if [ -x "${SCRIPT}" ]; then
  ok "scripts/pulse/build-bitnet.sh present + executable"
else
  ko "script missing or not executable"
  exit 1
fi

# ---------- DRY-RUN ----------
set +e
out="$(SOVEREIGN_OS_DRY_RUN=1 bash "${SCRIPT}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "DRY-RUN → exit 0"
else
  ko "DRY-RUN broken (rc=${rc})"
fi
for kw in "Pulse runtime" "BitNet" "znver5" "/usr/local/bin/bitnet-cli" "DRY-RUN: would"; do
  if grep -q "${kw}" <<< "${out}"; then
    ok "DRY-RUN surfaces: ${kw}"
  else
    ko "DRY-RUN missing: ${kw}"
  fi
done

# ---------- env vars honored ----------
set +e
out="$(BITNET_REPO=https://example.org/fake-bitnet \
       BITNET_TAG=v1.2.3 \
       BITNET_BUILD_DIR=/tmp/fake-build \
       SOVEREIGN_OS_DRY_RUN=1 \
       bash "${SCRIPT}" 2>&1)"
set -e
if grep -q "example.org/fake-bitnet" <<< "${out}"; then
  ok "BITNET_REPO env var honored in log header"
else
  ko "BITNET_REPO override not surfaced"
fi
if grep -q "v1.2.3" <<< "${out}"; then
  ok "BITNET_TAG env var honored"
else
  ko "BITNET_TAG override not surfaced"
fi
if grep -q "/tmp/fake-build" <<< "${out}"; then
  ok "BITNET_BUILD_DIR env var honored"
else
  ko "BITNET_BUILD_DIR override not surfaced"
fi

# ---------- master spec citation in script header ----------
if grep -qi "master spec § 15-16\|master spec § 17" "${SCRIPT}"; then
  ok "script header cites master spec § 15-16 or § 17 (the Pulse module)"
else
  ko "master spec citation missing from script header"
fi

# Verbatim master spec compile flags present
if grep -q "march=znver5" "${SCRIPT}"; then
  ok "compile flag -march=znver5 present (master spec § 16 verbatim)"
else
  ko "znver5 compile flag missing"
fi
for flag in mavx512f mavx512dq mavx512bw mavx512vl mavx512bf16 mavx512fp16; do
  if grep -q "${flag}" "${SCRIPT}"; then
    ok "AVX-512 flag present: -${flag}"
  else
    ko "AVX-512 flag missing: -${flag}"
  fi
done

# GGML_AVX512* env per master spec § 9.1 docker snippet
for env in GGML_AVX512 GGML_AVX512_VBMI GGML_AVX512_VNNI; do
  if grep -q "${env}=1" "${SCRIPT}"; then
    ok "GGML compile env exported: ${env}=1"
  else
    ko "GGML env missing: ${env}"
  fi
done

# ---------- BITNET_SKIP_MODEL honored ----------
set +e
out="$(BITNET_SKIP_MODEL=1 SOVEREIGN_OS_DRY_RUN=1 bash "${SCRIPT}" 2>&1)"
set -e
if grep -q "DRY-RUN: would" <<< "${out}"; then
  ok "BITNET_SKIP_MODEL doesn't break DRY-RUN path"
else
  ko "DRY-RUN + skip-model broken"
fi

# ---------- Layer B metric emission noted ----------
if grep -q "sovereign_os_pulse_build_total" <<< "${out}"; then
  ok "Layer B metric emitted under DRY-RUN ('would emit' line)"
else
  ko "Layer B metric pointer missing"
fi

# ---------- script documents env vars in header ----------
for var in BITNET_REPO BITNET_TAG BITNET_BUILD_DIR BITNET_MODEL_DIR BITNET_SKIP_MODEL SOVEREIGN_OS_DRY_RUN; do
  if head -30 "${SCRIPT}" | grep -q "${var}"; then
    ok "header documents: ${var}"
  else
    ko "header doesn't document: ${var}"
  fi
done

# ---------- result ----------
echo
total=$((pass + fail))
echo "test_pulse_build_bitnet: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
