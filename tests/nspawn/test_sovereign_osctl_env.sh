#!/usr/bin/env bash
# tests/nspawn/test_sovereign_osctl_env.sh
#
# Layer 3 test for sovereign-osctl env (Round 137; F-03 HIGH closure).
# Verifies env-var discovery (list + show + filter).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_sovereign_osctl_env.sh"
echo

# ---------- env list ----------
set +e
out="$("${OSCTL}" env list 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -qE "total: [0-9]+ env var" <<< "${out}"; then
  ok "env list → exit 0 + totals line"
else
  ko "env list broken (rc=${rc})"
fi

# Header row present
if grep -q "NAME.*DEFAULT.*CONSUMERS" <<< "${out}"; then
  ok "list emits header row"
else
  ko "list header missing"
fi

# Has well-known SOVEREIGN_OS_PROFILE
if grep -q "SOVEREIGN_OS_PROFILE\b" <<< "${out}"; then
  ok "list contains SOVEREIGN_OS_PROFILE (canonical env var)"
else
  ko "PROFILE missing from list"
fi

# Has SOVEREIGN_OS_HARDENING_DEST_PREFIX (R102 / R134)
if grep -q "SOVEREIGN_OS_HARDENING_DEST_PREFIX" <<< "${out}"; then
  ok "list contains SOVEREIGN_OS_HARDENING_DEST_PREFIX (R102)"
else
  ko "HARDENING_DEST_PREFIX missing"
fi

# At least 50 env vars discovered (sanity)
if grep -qE "total: ([5-9][0-9]|[1-9][0-9]{2,})" <<< "${out}"; then
  ok "discovered ≥50 env vars (substantive coverage)"
else
  ko "discovered too few env vars"
fi

# ---------- env list --filter ----------
set +e
out="$("${OSCTL}" env list --filter HARDENING 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "filter: /HARDENING/" <<< "${out}" \
                     && grep -q "SOVEREIGN_OS_HARDENING" <<< "${out}"; then
  ok "--filter narrows to matching vars + shows filter in summary"
else
  ko "--filter broken (rc=${rc})"
fi

# Filter with no match
set +e
out="$("${OSCTL}" env list --filter NOSUCHTHINGSORRY 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "total: 0 env var" <<< "${out}"; then
  ok "--filter with no match → exit 0 + 'total: 0'"
else
  ko "--filter no-match broken (rc=${rc})"
fi

# ---------- env show ----------
set +e
out="$("${OSCTL}" env show SOVEREIGN_OS_PROFILE 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "env show SOVEREIGN_OS_PROFILE → exit 0"
else
  ko "show broken (rc=${rc})"
fi
for kw in "name:" "default:" "currently set:" "consumed by:"; do
  if grep -q "${kw}" <<< "${out}"; then
    ok "show emits field: ${kw}"
  else
    ko "show field missing: ${kw}"
  fi
done

# show on a var that doesn't exist
set +e
out="$("${OSCTL}" env show SOVEREIGN_OS_GENUINELY_NONEXISTENT_XYZ 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ] && grep -q "not found" <<< "${out}"; then
  ok "show on nonexistent var → exit 1 + 'not found'"
else
  ko "show nonexistent-var gate broken (rc=${rc})"
fi

# show currently-set value reflects environment
set +e
out="$(SOVEREIGN_OS_PROFILE=minimal "${OSCTL}" env show SOVEREIGN_OS_PROFILE 2>&1)"
set -e
if grep -q "currently set:  minimal" <<< "${out}"; then
  ok "show 'currently set' reflects shell env"
else
  ko "show currently-set lookup broken"
fi

# show with no arg
set +e
out="$("${OSCTL}" env show 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "usage:" <<< "${out}"; then
  ok "show without arg → exit 2 + usage"
else
  ko "show no-arg gate broken (rc=${rc})"
fi

# unknown env subverb
set +e
out="$("${OSCTL}" env bogus 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "unknown env subcommand: bogus" <<< "${out}"; then
  ok "unknown env subverb → exit 2"
else
  ko "unknown-subverb gate broken (rc=${rc})"
fi

# unknown flag
set +e
out="$("${OSCTL}" env list --bogus 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "unknown env list flag" <<< "${out}"; then
  ok "unknown list flag → exit 2"
else
  ko "unknown-flag gate broken (rc=${rc})"
fi

# help mentions env
help_out="$("${OSCTL}" help 2>&1)"
for kw in "env list" "env show"; do
  if grep -q "${kw}" <<< "${help_out}"; then
    ok "help documents: ${kw}"
  else
    ko "help missing: ${kw}"
  fi
done

# ---------- result ----------
echo
total=$((pass + fail))
echo "test_sovereign_osctl_env: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
