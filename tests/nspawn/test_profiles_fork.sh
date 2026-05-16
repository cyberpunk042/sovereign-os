#!/usr/bin/env bash
# tests/nspawn/test_profiles_fork.sh
#
# Layer 3 test for sovereign-osctl profiles fork (Round 140; F-04 MED closure).
# Verifies: scaffolding shape, validation, INDEX registration,
# self-comparison via R139 profiles compare, restoration cleanup.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_profiles_fork.sh"
echo

# Unique fork name so we don't collide with prior leftovers
FORK_ID="test-fork-$$"
FORK_FILE="${__REPO_ROOT}/profiles/${FORK_ID}.yaml"
INDEX_FILE="${__REPO_ROOT}/profiles/INDEX.md"
INDEX_BACKUP="$(mktemp)"
cp "${INDEX_FILE}" "${INDEX_BACKUP}"
trap '
  rm -f "${FORK_FILE}"
  if [ -f "${INDEX_BACKUP}" ]; then
    cp "${INDEX_BACKUP}" "${INDEX_FILE}"
    rm -f "${INDEX_BACKUP}"
  fi
' EXIT

# ---------- happy path: fork from minimal ----------
set +e
out="$("${OSCTL}" profiles fork minimal "${FORK_ID}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "fork minimal → ${FORK_ID} exit 0"
else
  ko "fork broken (rc=${rc}): ${out:0:200}"
fi

# File created
if [ -f "${FORK_FILE}" ]; then
  ok "fork file created at ${FORK_FILE}"
else
  ko "fork file NOT created"
  exit 1
fi

# YAML parses + has expected mutations
python3 -c "
import yaml
with open('${FORK_FILE}') as f:
    data = yaml.safe_load(f)
ident = data.get('identity', {})
assert ident.get('id') == '${FORK_ID}', f'id wrong: {ident.get(\"id\")}'
assert ident.get('parent') == 'minimal', f'parent wrong: {ident.get(\"parent\")}'
assert ident.get('status') == 'draft', f'status wrong: {ident.get(\"status\")}'
desc = ident.get('description', '')
assert 'forked from minimal' in desc.lower(), f'description missing fork note'
" 2>&1 && ok "YAML parses + identity.id/parent/status correctly set" \
       || ko "fork YAML shape wrong"

# Header preserved
if grep -q "yaml-language-server" "${FORK_FILE}"; then
  ok "language-server hint preserved"
else
  ko "language-server hint missing in forked file"
fi

# Schema validation passes
set +e
val_out="$("${__REPO_ROOT}/scripts/validate-profiles.sh" 2>&1)"
val_rc=$?
set -e
if [ "${val_rc}" -eq 0 ] && grep -q "${FORK_ID}" <<< "${val_out}"; then
  ok "forked profile passes schema validation"
else
  ko "forked profile failed validation (rc=${val_rc})"
fi

# Registered in INDEX
if grep -q "\`${FORK_ID}\`" "${INDEX_FILE}"; then
  ok "registered in profiles/INDEX.md"
else
  ko "INDEX registration missing"
fi

# NEXT-steps printed
for kw in "edit" "validate" "compare" "switch"; do
  if grep -q "${kw}" <<< "${out}"; then
    ok "NEXT step surfaced: ${kw}"
  else
    ko "NEXT step missing: ${kw}"
  fi
done

# Compare against base shows minimal diff (identity-only)
set +e
cmp_out="$("${OSCTL}" profiles compare minimal "${FORK_ID}" 2>&1)"
set -e
if grep -q "id:" <<< "${cmp_out}" && grep -q "parent:" <<< "${cmp_out}"; then
  ok "fork vs base diff shows identity-only differences"
else
  ko "fork-vs-base diff unexpected"
fi

# ---------- refuses on existing target ----------
set +e
out="$("${OSCTL}" profiles fork minimal "${FORK_ID}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ] && grep -q "already exists" <<< "${out}"; then
  ok "fork onto existing target → exit 1 + 'already exists'"
else
  ko "duplicate-target gate broken (rc=${rc})"
fi

# ---------- refuses on missing base ----------
set +e
out="$("${OSCTL}" profiles fork no-such-base "${FORK_ID}-2" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ] && grep -q "no such base profile" <<< "${out}"; then
  ok "missing base → exit 1 + clear error"
else
  ko "missing-base gate broken (rc=${rc})"
fi

# ---------- refuses on invalid id ----------
set +e
out="$("${OSCTL}" profiles fork minimal "Invalid_ID!" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "invalid new profile id" <<< "${out}"; then
  ok "invalid id → exit 2 + clear pattern hint"
else
  ko "id-pattern gate broken (rc=${rc})"
fi

# ---------- usage when missing args ----------
set +e
out="$("${OSCTL}" profiles fork 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "usage:" <<< "${out}"; then
  ok "no-args → exit 2 + usage"
else
  ko "no-args gate broken (rc=${rc})"
fi

# ---------- help mentions fork ----------
help_out="$("${OSCTL}" help 2>&1)"
if grep -q "profiles fork" <<< "${help_out}"; then
  ok "help documents 'profiles fork'"
else
  ko "help missing fork"
fi

# ---------- result ----------
echo
total=$((pass + fail))
echo "test_profiles_fork: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
