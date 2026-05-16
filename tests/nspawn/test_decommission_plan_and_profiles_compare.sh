#!/usr/bin/env bash
# tests/nspawn/test_decommission_plan_and_profiles_compare.sh
#
# Layer 3 test for R139 — closes F-11 (decommission --plan) + F-12
# (profiles compare). Both shipped in the same round.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_decommission_plan_and_profiles_compare.sh"
echo

# ---------- decommission --plan ----------
set +e
out="$("${OSCTL}" decommission --plan 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "decommission --plan → exit 0 (non-destructive)"
else
  ko "decommission --plan broken (rc=${rc})"
fi
for kw in "Phase 1" "Phase 2" "Phase 3" "NOTHING WAS WRITTEN"; do
  if grep -q "${kw}" <<< "${out}"; then
    ok "plan surfaces: ${kw}"
  else
    ko "plan missing: ${kw}"
  fi
done
# Each phase names the underlying hook
for hook in secure-wipe-context.sh zfs-pool-destroy.sh secure-wipe.sh; do
  if grep -q "${hook}" <<< "${out}"; then
    ok "plan names hook: ${hook}"
  else
    ko "hook missing from plan: ${hook}"
  fi
done
# Each phase shows the invoke command
for invoke in "decommission start" "decommission pool" "decommission wipe"; do
  if grep -q "${invoke}" <<< "${out}"; then
    ok "plan shows invoke: ${invoke}"
  else
    ko "invoke missing: ${invoke}"
  fi
done
# SOVEREIGN_OS_CONFIRM_DESTROY env-gate explicitly mentioned
if grep -q "SOVEREIGN_OS_CONFIRM_DESTROY" <<< "${out}"; then
  ok "plan mentions SOVEREIGN_OS_CONFIRM_DESTROY env-gate"
else
  ko "env-gate not surfaced"
fi
# alias: plan (without --)
set +e
out="$("${OSCTL}" decommission plan 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "Phase 1" <<< "${out}"; then
  ok "'decommission plan' (no --) accepted as alias"
else
  ko "plan alias broken (rc=${rc})"
fi

# ---------- WIPE_DEVICES surfaced when set ----------
set +e
out="$(SOVEREIGN_OS_WIPE_DEVICES="/dev/zero" "${OSCTL}" decommission --plan 2>&1)"
set -e
if grep -q "/dev/zero" <<< "${out}"; then
  ok "WIPE_DEVICES env reflected in plan"
else
  ko "WIPE_DEVICES not surfaced when set"
fi
if grep -q "NOT A BLOCK DEVICE" <<< "${out}"; then
  ok "plan flags non-block-device WIPE_DEVICES targets"
else
  ko "non-block-device check missing"
fi

# ---------- profiles compare ----------
set +e
out="$("${OSCTL}" profiles compare minimal headless 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "profiles compare minimal headless → exit 0"
else
  ko "compare broken (rc=${rc})"
fi
# Unified-diff headers present
if grep -qE "^--- minimal" <<< "${out}" && grep -qE "^\+\+\+ headless" <<< "${out}"; then
  ok "compare emits unified-diff headers"
else
  ko "diff headers missing"
fi
# Substantive differences shown (auditd / fail2ban only in headless)
if grep -q "auditd" <<< "${out}" || grep -q "fail2ban" <<< "${out}"; then
  ok "compare surfaces substantive diff (role-server packages)"
else
  ko "compare didn't surface known differences"
fi

# ---------- missing args ----------
set +e
out="$("${OSCTL}" profiles compare minimal 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "usage:" <<< "${out}"; then
  ok "compare with one arg → exit 2 + usage"
else
  ko "compare 1-arg gate broken (rc=${rc})"
fi

# ---------- nonexistent profile ----------
set +e
out="$("${OSCTL}" profiles compare minimal no-such-profile 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ] && grep -q "no such profile" <<< "${out}"; then
  ok "compare with nonexistent profile → exit 1"
else
  ko "compare nonexistent gate broken (rc=${rc})"
fi

# ---------- self-compare (identical → no diff body) ----------
set +e
out="$("${OSCTL}" profiles compare sain-01 sain-01 2>&1)"
rc=$?
set -e
# diff exit code 0 = no differences; the wrapper returns 0 in either case
if [ "${rc}" -eq 0 ]; then
  ok "compare profile-to-itself → exit 0"
else
  ko "self-compare broken (rc=${rc})"
fi

# ---------- help mentions both ----------
help_out="$("${OSCTL}" help 2>&1)"
if grep -q "decommission --plan" <<< "${help_out}"; then
  ok "help documents 'decommission --plan'"
else
  ko "help missing decommission --plan"
fi
if grep -q "profiles compare" <<< "${help_out}"; then
  ok "help documents 'profiles compare'"
else
  ko "help missing profiles compare"
fi

# ---------- result ----------
echo
total=$((pass + fail))
echo "test_decommission_plan_and_profiles_compare: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
