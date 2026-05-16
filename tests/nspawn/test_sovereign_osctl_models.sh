#!/usr/bin/env bash
# tests/nspawn/test_sovereign_osctl_models.sh
#
# Layer 3 test for sovereign-osctl models verbs (Round 62).
# Validates list / size / remove against a fake SOVEREIGN_OS_MODELS_DIR.
# Doesn't exercise 'pull' (needs huggingface-cli + network).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

CTL="${__REPO_ROOT}/scripts/sovereign-osctl"
[ -x "${CTL}" ] || { echo "FAIL: sovereign-osctl not executable"; exit 1; }

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_sovereign_osctl_models.sh"
echo

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
export SOVEREIGN_OS_NONINTERACTIVE=1
export SOVEREIGN_OS_PROFILE=sain-01

models_dir="${tmp}/models"
mkdir -p "${models_dir}/fake-org__model-a" "${models_dir}/fake-org__model-b"
# Pad with bytes so du shows non-zero
head -c 1024 /dev/urandom > "${models_dir}/fake-org__model-a/weights.bin"
head -c 2048 /dev/urandom > "${models_dir}/fake-org__model-b/weights.bin"

export SOVEREIGN_OS_MODELS_DIR="${models_dir}"

# ----------- list ---------------

out="$("${CTL}" models list 2>&1)"
if grep -q "fake-org__model-a" <<< "${out}" && grep -q "fake-org__model-b" <<< "${out}"; then
  ok "models list enumerates both resident models"
else
  ko "models list missing one or both: ${out:0:200}"
fi

# ----------- size ---------------

out="$("${CTL}" models size 2>&1)"
if grep -q "Per-model breakdown" <<< "${out}"; then
  ok "models size emits per-model breakdown"
else
  ko "models size output unexpected: ${out:0:200}"
fi

if grep -qE "[0-9]+(\.[0-9]+)?[KMG]" <<< "${out}"; then
  ok "models size reports du-readable sizes"
else
  ko "models size: no du-readable size value"
fi

# ----------- remove (ASSUME_YES bypass) ---------------

set +e
out="$(SOVEREIGN_OS_ASSUME_YES=1 "${CTL}" models remove fake-org__model-a 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && [ ! -d "${models_dir}/fake-org__model-a" ]; then
  ok "models remove (ASSUME_YES=1) deletes resident model"
else
  ko "models remove failed: rc=${rc} out=${out:0:200}"
fi

# Other model still there
if [ -d "${models_dir}/fake-org__model-b" ]; then
  ok "models remove only touched the named model"
else
  ko "models remove also deleted unrelated model"
fi

# ----------- remove without ASSUME_YES → default-no refuses ---------------

set +e
out="$("${CTL}" models remove fake-org__model-b 2>&1)"
rc=$?
set -e
# NONINTERACTIVE + default-no → confirm returns false → 'cancelled'
if [ "${rc}" -eq 0 ] && grep -q "remove cancelled" <<< "${out}"; then
  ok "models remove default-no path refuses under NONINTERACTIVE"
else
  ko "models remove no-confirm path broken: rc=${rc} out=${out:0:200}"
fi

# Model b should still be there
[ -d "${models_dir}/fake-org__model-b" ] \
  && ok "models remove refusal didn't touch the target" \
  || ko "model deleted despite refusal"

# ----------- remove nonexistent → error ---------------

set +e
out="$("${CTL}" models remove totally-bogus-model 2>&1)"
rc=$?
set -e
if [ "${rc}" -ne 0 ] && grep -q "model not resident" <<< "${out}"; then
  ok "models remove rejects nonexistent target"
else
  ko "models remove bogus-target gate broken: rc=${rc}"
fi

# ----------- help documents new subcommands ---------------

help_out="$("${CTL}" help 2>&1)"
if grep -q "models size" <<< "${help_out}" && grep -q "models remove" <<< "${help_out}"; then
  ok "help documents 'models size' + 'models remove'"
else
  ko "help missing new models subverbs"
fi

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_sovereign_osctl_models: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
