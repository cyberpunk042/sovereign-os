#!/usr/bin/env bash
# tests/nspawn/test_hooks.sh
#
# Layer 3 test for sovereign-osctl hooks (Round 141; F-09 MED closure).
# Verifies list/add/remove with full round-trip + gates.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_hooks.sh"
echo

# Back up minimal.yaml — we mutate it then restore
PROFILE=minimal
PFILE="${__REPO_ROOT}/profiles/${PROFILE}.yaml"
PBACKUP="$(mktemp)"
cp "${PFILE}" "${PBACKUP}"
trap '
  cp "${PBACKUP}" "${PFILE}"
  rm -f "${PBACKUP}"
' EXIT

HOOK_ID="test-hook-$$"
SCRIPT="scripts/hooks/recurrent/alerts-check.sh"  # already executable

# ---------- list ----------
set +e
out="$("${OSCTL}" hooks list ${PROFILE} 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "total:" <<< "${out}"; then
  ok "hooks list ${PROFILE} → exit 0 + totals line"
else
  ko "list broken (rc=${rc})"
fi
if grep -q "post_install_first_boot:" <<< "${out}"; then
  ok "list emits stage headers"
else
  ko "list stage headers missing"
fi

# list on nonexistent profile
set +e
out="$("${OSCTL}" hooks list no-such-profile 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ] && grep -q "no such profile" <<< "${out}"; then
  ok "list on missing profile → exit 1"
else
  ko "list missing-profile gate broken (rc=${rc})"
fi

# ---------- add (happy path) ----------
set +e
out="$(SOVEREIGN_OS_PROFILE=${PROFILE} "${OSCTL}" hooks add post_install_first_boot "${SCRIPT}" --id "${HOOK_ID}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "hook added:" <<< "${out}"; then
  ok "hooks add → exit 0 + 'hook added' marker"
else
  ko "add broken (rc=${rc}): ${out:0:200}"
fi

# Hook appears in profile
if grep -q "id: ${HOOK_ID}" "${PFILE}"; then
  ok "hook id present in profile YAML after add"
else
  ko "hook id NOT in profile after add"
fi

# Profile still validates
set +e
"${__REPO_ROOT}/scripts/validate-profiles.sh" >/dev/null 2>&1
val_rc=$?
set -e
if [ "${val_rc}" -eq 0 ]; then
  ok "profile still schema-validates after add"
else
  ko "profile broken after add (validate rc=${val_rc})"
fi

# Subsequent list shows the new hook
set +e
out="$("${OSCTL}" hooks list ${PROFILE} 2>&1)"
set -e
if grep -q "${HOOK_ID}" <<< "${out}"; then
  ok "list shows the just-added hook"
else
  ko "list didn't show new hook"
fi

# ---------- add idempotency: duplicate refused ----------
set +e
out="$(SOVEREIGN_OS_PROFILE=${PROFILE} "${OSCTL}" hooks add post_install_first_boot "${SCRIPT}" --id "${HOOK_ID}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -ne 0 ] && grep -q "already exists" <<< "${out}"; then
  ok "duplicate id → refused with 'already exists'"
else
  ko "duplicate gate broken (rc=${rc})"
fi

# ---------- remove ----------
set +e
out="$(SOVEREIGN_OS_PROFILE=${PROFILE} "${OSCTL}" hooks remove "${HOOK_ID}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "removed 1 hook" <<< "${out}"; then
  ok "remove → exit 0 + 'removed N hook' marker"
else
  ko "remove broken (rc=${rc})"
fi

# Hook gone
if ! grep -q "id: ${HOOK_ID}" "${PFILE}"; then
  ok "hook id removed from profile YAML"
else
  ko "hook id STILL in profile after remove"
fi

# Profile still validates after round-trip
set +e
"${__REPO_ROOT}/scripts/validate-profiles.sh" >/dev/null 2>&1
val_rc=$?
set -e
if [ "${val_rc}" -eq 0 ]; then
  ok "profile schema-validates after add+remove round-trip"
else
  ko "round-trip broke profile"
fi

# remove of nonexistent hook
set +e
out="$(SOVEREIGN_OS_PROFILE=${PROFILE} "${OSCTL}" hooks remove no-such-hook-xyz 2>&1)"
rc=$?
set -e
if [ "${rc}" -ne 0 ] && grep -q "no hook with id" <<< "${out}"; then
  ok "remove nonexistent → non-zero + 'no hook with id'"
else
  ko "remove nonexistent gate broken (rc=${rc})"
fi

# ---------- add gates ----------
# Invalid stage
set +e
out="$(SOVEREIGN_OS_PROFILE=${PROFILE} "${OSCTL}" hooks add not-a-stage "${SCRIPT}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "invalid stage" <<< "${out}"; then
  ok "invalid stage → exit 2"
else
  ko "stage gate broken (rc=${rc})"
fi

# Missing script path
set +e
out="$(SOVEREIGN_OS_PROFILE=${PROFILE} "${OSCTL}" hooks add post_install_first_boot scripts/hooks/no-such-script.sh 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ] && grep -q "script not found" <<< "${out}"; then
  ok "missing script → exit 1"
else
  ko "missing-script gate broken (rc=${rc})"
fi

# Non-executable script
non_exec="${__REPO_ROOT}/profiles/INDEX.md"
set +e
out="$(SOVEREIGN_OS_PROFILE=${PROFILE} "${OSCTL}" hooks add post_install_first_boot profiles/INDEX.md 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ] && grep -q "not executable" <<< "${out}"; then
  ok "non-executable script → exit 1 + 'not executable'"
else
  ko "executability gate broken (rc=${rc})"
fi

# No args
set +e
out="$("${OSCTL}" hooks add 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "usage:" <<< "${out}"; then
  ok "no-args → exit 2 + usage"
else
  ko "no-args gate broken (rc=${rc})"
fi

# Unknown flag
set +e
out="$(SOVEREIGN_OS_PROFILE=${PROFILE} "${OSCTL}" hooks add post_install_first_boot "${SCRIPT}" --bogus 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "unknown hooks add flag" <<< "${out}"; then
  ok "unknown flag → exit 2"
else
  ko "unknown-flag gate broken (rc=${rc})"
fi

# Unknown subverb
set +e
out="$("${OSCTL}" hooks bogus 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "unknown hooks subcommand" <<< "${out}"; then
  ok "unknown subverb → exit 2"
else
  ko "unknown-subverb gate broken (rc=${rc})"
fi

# Help mentions hooks
help_out="$("${OSCTL}" help 2>&1)"
for kw in "hooks list" "hooks add" "hooks remove"; do
  if grep -q "${kw}" <<< "${help_out}"; then
    ok "help documents: ${kw}"
  else
    ko "help missing: ${kw}"
  fi
done

# ---------- result ----------
echo
total=$((pass + fail))
echo "test_hooks: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
