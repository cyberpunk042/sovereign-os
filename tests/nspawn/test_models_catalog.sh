#!/usr/bin/env bash
# tests/nspawn/test_models_catalog.sh
#
# Layer 3 test for R156 — models/catalog.yaml + scripts/models/{pull,verify}.sh
# (real model catalog manifest materialized from master spec § 17 + § 18).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

# python3 resolver — some CI envs lack PyYAML in the first python3.
PYTHON3="${PYTHON3:-python3}"
if ! "${PYTHON3}" -c "import yaml" >/dev/null 2>&1; then
  if /usr/bin/python3 -c "import yaml" >/dev/null 2>&1; then
    PYTHON3="/usr/bin/python3"
  fi
fi

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

CATALOG="${__REPO_ROOT}/models/catalog.yaml"
SCHEMA="${__REPO_ROOT}/schemas/model-catalog.schema.yaml"
PULL="${__REPO_ROOT}/scripts/models/pull.sh"
VERIFY="${__REPO_ROOT}/scripts/models/verify.sh"

echo "tests/nspawn/test_models_catalog.sh"
echo

# ---------- artifacts present ----------
[ -f "${CATALOG}" ] && ok "models/catalog.yaml present" || { ko "missing"; exit 1; }
[ -f "${SCHEMA}" ]  && ok "schemas/model-catalog.schema.yaml present" || ko "schema missing"
[ -x "${PULL}" ]    && ok "scripts/models/pull.sh executable"   || ko "pull.sh missing/not exec"
[ -x "${VERIFY}" ]  && ok "scripts/models/verify.sh executable" || ko "verify.sh missing/not exec"

# ---------- catalog parses as YAML ----------
if "${PYTHON3}" -c "import yaml; yaml.safe_load(open('${CATALOG}'))" 2>/dev/null; then
  ok "catalog.yaml is valid YAML"
else
  ko "catalog.yaml YAML parse error"
fi

# ---------- catalog cites master spec ----------
if grep -q "master spec § 17" "${CATALOG}"; then
  ok "catalog cites master spec § 17 (Genesis Trinity)"
else
  ko "master spec § 17 citation missing"
fi

# ---------- verified-real entries — operator-confirmable HF repos ----------
for repo in \
    "microsoft/bitnet-b1.58-2B-4T" \
    "deepseek-ai/DeepSeek-R1-Distill-Llama-70B" \
    "deepseek-ai/DeepSeek-V3" \
    "inclusionAI/Ling-2.6-flash" \
    "nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16"; do
  if grep -q "${repo}" "${CATALOG}"; then
    ok "catalog declares HF repo: ${repo}"
  else
    ko "catalog missing repo: ${repo}"
  fi
done

# ---------- aspirational entries (master-spec-named) ----------
for aspir in "BitNet-b1.58-3B" "BitNet-b1.58-13B" "Qwen-32B-Ternary-Quant"; do
  if grep -q "id: ${aspir}" "${CATALOG}"; then
    ok "catalog declares aspirational entry: ${aspir}"
  else
    ko "catalog missing aspirational: ${aspir}"
  fi
done

# ---------- pull.sh list ----------
set +e
out="$(bash "${PULL}" list 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "pull.sh list exit 0"
else
  ko "pull.sh list rc=${rc}"
fi
if grep -q "BitNet-b1.58-2B-4T" <<< "${out}" && grep -q "DeepSeek-V3-Quant" <<< "${out}"; then
  ok "pull.sh list surfaces catalog entries"
else
  ko "pull.sh list output incomplete"
fi
if grep -q "master spec § 17" <<< "${out}"; then
  ok "pull.sh list cites master spec § 17"
else
  ko "pull.sh list missing master spec citation"
fi

# ---------- pull.sh DRY-RUN on verified-real entry ----------
set +e
out="$(SOVEREIGN_OS_DRY_RUN=1 bash "${PULL}" BitNet-b1.58-2B-4T 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "DRY-RUN" <<< "${out}" && grep -q "microsoft/bitnet" <<< "${out}"; then
  ok "pull.sh DRY-RUN verified-real exit 0 + surfaces repo"
else
  ko "pull.sh DRY-RUN broken (rc=${rc} out=${out:0:200})"
fi

# ---------- pull.sh on aspirational entry (no real repo) ----------
set +e
out="$(SOVEREIGN_OS_DRY_RUN=1 bash "${PULL}" BitNet-b1.58-3B 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "aspirational" <<< "${out}"; then
  ok "pull.sh aspirational entry warns + exits 0 (no pull, no crash)"
else
  ko "pull.sh aspirational path broken (rc=${rc} out=${out:0:200})"
fi

# ---------- pull.sh unknown model ----------
set +e
out="$(bash "${PULL}" NoSuchModel-9999 2>&1)"
rc=$?
set -e
if [ "${rc}" -ne 0 ] && grep -q "not found in catalog" <<< "${out}"; then
  ok "pull.sh unknown model → rc≠0 + clear error"
else
  ko "pull.sh unknown model path broken (rc=${rc})"
fi

# ---------- verify.sh on empty dir → rc=2 + tier breakdown ----------
TMP_EMPTY="$(mktemp -d)"
set +e
out="$(SOVEREIGN_OS_MODELS_DIR="${TMP_EMPTY}" bash "${VERIFY}" 2>&1)"
rc=$?
set -e
rm -rf "${TMP_EMPTY}"
if [ "${rc}" -eq 2 ]; then
  ok "verify.sh on empty dir → rc=2 (absent detected)"
else
  ko "verify.sh rc wrong on empty dir: ${rc}"
fi
for tier in "tier=pulse" "tier=logic" "tier=oracle"; do
  if grep -q "${tier}" <<< "${out}"; then
    ok "verify.sh surfaces ${tier}"
  else
    ko "verify.sh missing ${tier}"
  fi
done
if grep -q "ABSENT" <<< "${out}"; then
  ok "verify.sh lists ABSENT entries"
else
  ko "verify.sh missing ABSENT section"
fi

# ---------- verify.sh on fully-resident dir → rc=0 ----------
# E110 defines resident as a model directory containing at least one file.
# Compute the resident-dir set + expected count from models/catalog.yaml
# directly — the verified-real model count has grown from 5 (Round 156
# initial) to 15+ as the master-spec § 17 model catalog expanded. The
# "5/5" lock was a 1:1 snapshot of the initial 5; per Hard Rule 4a
# (Adding ≠ discarding) we now derive the count dynamically so future
# catalog growth doesn't require a test edit.
TMP_FULL="$(mktemp -d)"
mapfile -t VERIFIED_REAL_IDS < <("${PYTHON3}" -c "
import yaml
with open('${__REPO_ROOT}/models/catalog.yaml') as f:
    doc = yaml.safe_load(f)
for m in doc['catalog']['models']:
    if m['status'] == 'verified-real':
        print(m['id'])
")
for d in "${VERIFIED_REAL_IDS[@]}"; do
  mkdir -p "${TMP_FULL}/${d}"
  printf 'fixture for %s\n' "${d}" > "${TMP_FULL}/${d}/weights.fixture"
done
EXPECTED_N=${#VERIFIED_REAL_IDS[@]}
set +e
out="$(SOVEREIGN_OS_MODELS_DIR="${TMP_FULL}" bash "${VERIFY}" 2>&1)"
rc=$?
set -e
rm -rf "${TMP_FULL}"
if [ "${rc}" -eq 0 ]; then
  ok "verify.sh on fully-resident dir → rc=0"
else
  ko "verify.sh rc wrong on resident dir: ${rc}"
fi
if grep -qE "RESIDENT \(verified-real\):     ${EXPECTED_N}/${EXPECTED_N}" <<< "${out}"; then
  ok "verify.sh reports ${EXPECTED_N}/${EXPECTED_N} verified-real resident"
else
  ko "verify.sh count wrong"
fi

# ---------- verify.sh DRY-RUN ----------
set +e
out="$(SOVEREIGN_OS_DRY_RUN=1 bash "${VERIFY}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "DRY-RUN" <<< "${out}"; then
  ok "verify.sh DRY-RUN exit 0 + surfaces intent"
else
  ko "verify.sh DRY-RUN broken (rc=${rc})"
fi

echo
total=$((pass + fail))
echo "test_models_catalog: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
