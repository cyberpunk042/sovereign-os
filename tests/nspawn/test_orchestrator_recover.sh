#!/usr/bin/env bash
# tests/nspawn/test_orchestrator_recover.sh
#
# Layer 3 test for orchestrate.sh recover (Round 135; F-13 CRIT closure).
# Verifies recovery guidance is produced for: empty state, failed state,
# completed state, partial state with first-pending step.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

ORCH="${__REPO_ROOT}/scripts/build/orchestrate.sh"

echo "tests/nspawn/test_orchestrator_recover.sh"
echo

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

# Isolate state dir per-test
export SOVEREIGN_OS_STATE_DIR="${tmp}/build-state"
export SOVEREIGN_OS_STATE_FILE="${SOVEREIGN_OS_STATE_DIR}/state.yaml"
mkdir -p "${SOVEREIGN_OS_STATE_DIR}"
export SOVEREIGN_OS_PROFILE=sain-01

# ---------- fresh state (state_init creates 'steps: {}') → suggest run ----------
# After state_init the file exists but no step has run yet; recover
# treats every step as 'pending' → "no failure recorded / next pending step: 01-..."
set +e
out="$("${ORCH}" recover 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "no failure recorded" <<< "${out}" \
                     && grep -q "next pending step:" <<< "${out}" \
                     && grep -q "orchestrate.sh run" <<< "${out}"; then
  ok "fresh state → 'no failure' + 'next pending step' + 'run' recommendation"
else
  ko "fresh-state recovery broken (rc=${rc}): ${out:0:200}"
fi

# ---------- seeded state: one failed step ----------
cat > "${SOVEREIGN_OS_STATE_FILE}" <<EOF
build_id: "test-recover"
created_at: "2026-01-01T00:00:00+00:00"
steps:
  01-bootstrap-forge:
    status: completed
    started_at: "2026-01-01T00:00:01+00:00"
    inputs_hash: "abc"
    completed_at: "2026-01-01T00:01:00+00:00"
  02-kernel-fetch:
    status: failed
    started_at: "2026-01-01T00:01:01+00:00"
    inputs_hash: "def"
    fail_reason: "network-timeout-fetching-kernel-tag"
EOF

set +e
out="$("${ORCH}" recover 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "FAILED step: 02-kernel-fetch" <<< "${out}"; then
  ok "failed state → identifies the failed step"
else
  ko "failed-state detection broken (rc=${rc})"
fi
if grep -q "network-timeout-fetching-kernel-tag" <<< "${out}"; then
  ok "fail_reason surfaced from state.yaml"
else
  ko "fail_reason not surfaced"
fi
if grep -q "RECOMMENDED NEXT ACTIONS" <<< "${out}"; then
  ok "recovery guidance section present"
else
  ko "recommended-actions header missing"
fi
# 4 options (a/b/c/d) presented
for opt in '(a)' '(b)' '(c)' '(d)'; do
  if grep -q "${opt}" <<< "${out}"; then
    ok "option ${opt} presented"
  else
    ko "option ${opt} missing"
  fi
done
# Each option points at a specific orchestrate.sh subverb
for verb in "orchestrate.sh run" "orchestrate.sh rewind 02-kernel-fetch" \
            "orchestrate.sh skip 02-kernel-fetch" "orchestrate.sh reset"; do
  if grep -q "${verb}" <<< "${out}"; then
    ok "guidance suggests: ${verb}"
  else
    ko "guidance missing: ${verb}"
  fi
done
# Cross-reference to journal verb (Phase G)
if grep -q "sovereign-osctl journal" <<< "${out}"; then
  ok "recovery cross-references sovereign-osctl journal for log inspection"
else
  ko "journal cross-reference missing"
fi

# ---------- partial state: one completed, no failure ----------
cat > "${SOVEREIGN_OS_STATE_FILE}" <<EOF
build_id: "test-recover-partial"
created_at: "2026-01-01T00:00:00+00:00"
steps:
  01-bootstrap-forge:
    status: completed
    started_at: "2026-01-01T00:00:01+00:00"
    inputs_hash: "abc"
    completed_at: "2026-01-01T00:01:00+00:00"
EOF

set +e
out="$("${ORCH}" recover 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "no failure recorded" <<< "${out}" \
                     && grep -q "next pending step:" <<< "${out}"; then
  ok "partial state (no failure) → 'no failure' + next pending step"
else
  ko "partial-state recovery broken (rc=${rc})"
fi

# ---------- all-completed state → install image suggestion ----------
{
  cat <<EOF
build_id: "test-recover-done"
created_at: "2026-01-01T00:00:00+00:00"
steps:
EOF
  for s in 01-bootstrap-forge 02-kernel-fetch 03-kernel-config 04-kernel-compile \
           05-substrate-prepare 06-whitelabel-render 07-image-build \
           08-image-sign 09-image-verify; do
    cat <<EOF
  ${s}:
    status: completed
    started_at: "2026-01-01T00:00:01+00:00"
    inputs_hash: "x"
    completed_at: "2026-01-01T00:01:00+00:00"
EOF
  done
} > "${SOVEREIGN_OS_STATE_FILE}"

set +e
out="$("${ORCH}" recover 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "all steps completed" <<< "${out}" \
                     && grep -q "install image" <<< "${out}"; then
  ok "all-completed state → 'all steps completed' + install-image cross-ref"
else
  ko "all-completed gate broken (rc=${rc})"
fi

# ---------- help mentions recover ----------
help_out="$("${ORCH}" help 2>&1)"
if grep -q "recover" <<< "${help_out}"; then
  ok "help documents 'recover' subverb"
else
  ko "help missing 'recover'"
fi

# ---------- unknown subverb still 2 ----------
set +e
out="$("${ORCH}" not-a-real-command 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "unknown command:" <<< "${out}"; then
  ok "unknown subverb → exit 2"
else
  ko "unknown-subverb gate broken (rc=${rc})"
fi

# ---------- result ----------
echo
total=$((pass + fail))
echo "test_orchestrator_recover: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
