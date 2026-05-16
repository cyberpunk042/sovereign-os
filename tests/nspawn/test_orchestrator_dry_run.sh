#!/usr/bin/env bash
# tests/nspawn/test_orchestrator_dry_run.sh
#
# Layer 3 end-to-end test for scripts/build/orchestrate.sh in --dry-run
# mode. Validates the full 9-step pipeline can be planned + validated
# without root, without chroot, without kernel sources, without mutating
# any state — purely a plan-and-prerequisite-check pass.
#
# This is the operator-facing "what would happen if I built now"
# affordance (Q-019-style observability of the build pipeline itself)
# and the strongest single Layer-3 gate for orchestrator regressions:
# it exercises the dispatch, the flag parser, profile load, step
# enumeration, and per-step existence/executable check, all in one
# invocation.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

ORCH="${__REPO_ROOT}/scripts/build/orchestrate.sh"
[ -x "${ORCH}" ] || { echo "FAIL: orchestrator not executable"; exit 1; }

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

# Isolate state + log dirs (so no global state is touched).
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
export SOVEREIGN_OS_STATE_DIR="${tmp}/state"
export SOVEREIGN_OS_LOG_DIR="${tmp}/log"
export SOVEREIGN_OS_NONINTERACTIVE=1
export SOVEREIGN_OS_PROFILE="${1:-sain-01}"

echo "tests/nspawn/test_orchestrator_dry_run.sh (profile=${SOVEREIGN_OS_PROFILE})"
echo "  state: ${SOVEREIGN_OS_STATE_DIR}"
echo "  log:   ${SOVEREIGN_OS_LOG_DIR}"
echo

# ----------- dry-run via flag ---------------

out="$("${ORCH}" run --dry-run 2>&1)"
rc=$?

if [ "${rc}" -eq 0 ]; then
  ok "run --dry-run exit code 0"
else
  ko "run --dry-run exit code: ${rc}"
  echo "${out}" | tail -20
fi

if grep -q "DRY-RUN mode" <<< "${out}"; then
  ok "output declares DRY-RUN mode"
else
  ko "output missing DRY-RUN mode banner"
fi

if grep -q "loaded profile: ${SOVEREIGN_OS_PROFILE}" <<< "${out}"; then
  ok "profile loaded: ${SOVEREIGN_OS_PROFILE}"
else
  ko "profile not loaded"
fi

# All 9 steps must be enumerated in order
expected_steps=(
  "01-bootstrap-forge"
  "02-kernel-fetch"
  "03-kernel-config"
  "04-kernel-compile"
  "05-substrate-prepare"
  "06-whitelabel-render"
  "07-image-build"
  "08-image-sign"
  "09-image-verify"
)
for step in "${expected_steps[@]}"; do
  if grep -q "${step}" <<< "${out}"; then
    ok "step enumerated: ${step}"
  else
    ko "step missing from plan: ${step}"
  fi
done

# Plan-complete sentinel
if grep -q "DRY-RUN complete: all 9 steps present + executable" <<< "${out}"; then
  ok "all 9 steps validated present + executable"
else
  ko "completion sentinel missing — plan may be incomplete"
fi

# ----------- IaC bar: dry-run must NOT touch state ---------------
# Operator directive: "easily tweakable and configurable... local
# tracking of the progress of a build... that can only ever re-happen
# locally". Dry-run is an inspection mode — it must not mutate state,
# or rerunning a real build would think the steps are already complete.

if [ ! -e "${SOVEREIGN_OS_STATE_DIR}/state.yaml" ]; then
  ok "dry-run did NOT create state.yaml (state preserved)"
else
  ko "dry-run created state.yaml — would corrupt real-build resume"
fi

# But the log file is fine to create (it's the dry-run output itself).
# log_init writes build-<timestamp>.jsonl
if find "${SOVEREIGN_OS_LOG_DIR}" -name 'build-*.jsonl' -type f 2>/dev/null | grep -q .; then
  ok "log file created (build-*.jsonl) — observability path live"
else
  ko "log file not created — observability gap"
fi

# ----------- env-var equivalent: SOVEREIGN_OS_DRY_RUN=1 ---------------

# Wipe state dir between runs
rm -rf "${SOVEREIGN_OS_STATE_DIR}" "${SOVEREIGN_OS_LOG_DIR}"

out2="$(SOVEREIGN_OS_DRY_RUN=1 "${ORCH}" run 2>&1)"
rc2=$?
if [ "${rc2}" -eq 0 ] && grep -q "DRY-RUN mode" <<< "${out2}"; then
  ok "env SOVEREIGN_OS_DRY_RUN=1 enables dry-run (CLI-flag equivalence)"
else
  ko "env-var dry-run failed: rc=${rc2}"
fi

# ----------- --profile flag override ---------------

rm -rf "${SOVEREIGN_OS_STATE_DIR}" "${SOVEREIGN_OS_LOG_DIR}"
out3="$("${ORCH}" run --dry-run --profile old-workstation 2>&1)"
rc3=$?
if [ "${rc3}" -eq 0 ] && grep -q "loaded profile: old-workstation" <<< "${out3}"; then
  ok "--profile flag overrides env profile"
else
  ko "--profile flag override failed: rc=${rc3}"
fi

# ----------- unknown flag → exit 2 ---------------

set +e
rm -rf "${SOVEREIGN_OS_STATE_DIR}" "${SOVEREIGN_OS_LOG_DIR}"
"${ORCH}" run --definitely-bogus-flag >/dev/null 2>&1
rc4=$?
set -e
if [ "${rc4}" -eq 2 ]; then
  ok "unknown run flag exits 2"
else
  ko "unknown run flag exit code: expected 2, got ${rc4}"
fi

# ----------- list / status / help still functional (regression gate) ---------------
# Capture-then-grep to avoid SIGPIPE-on-upstream under set -o pipefail
# (grep -q closes the pipe as soon as it matches, killing the producer).

list_out="$("${ORCH}" list 2>&1)"
if grep -q "01-bootstrap-forge" <<< "${list_out}"; then
  ok "'list' command still emits step IDs"
else
  ko "'list' command regressed"
fi

help_out="$("${ORCH}" help 2>&1)"
if grep -q "sovereign-os build pipeline driver" <<< "${help_out}"; then
  ok "'help' command still emits banner"
else
  ko "'help' command regressed"
fi

# Help should document the new --dry-run flag (so operators discover it)
if grep -q -- "--dry-run" <<< "${help_out}"; then
  ok "'help' documents --dry-run flag"
else
  ko "'help' missing --dry-run documentation"
fi

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_orchestrator_dry_run: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
