#!/usr/bin/env bash
# tests/nspawn/test_sovereign_osctl_lib_paths.sh
#
# Layer 3 test for sovereign-osctl's lib-path detection (Round 81).
# Verifies the 5-candidate ordered lookup behaves correctly across:
#   - in-repo (sibling lib)
#   - make install layout (/usr/local/lib/sovereign-os via tmpdir)
#   - SOVEREIGN_OS_LIB env override
#   - all-candidates-missing → clear error + remediation hint

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_sovereign_osctl_lib_paths.sh"
echo

# ----------- in-repo (sibling lib) ---------------

set +e
out="$("${__REPO_ROOT}/scripts/sovereign-osctl" version 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "sovereign-osctl 0\." <<< "${out}"; then
  ok "in-repo run finds sibling lib (no SOVEREIGN_OS_LIB needed)"
else
  ko "in-repo run failed: rc=${rc}"
fi

# ----------- orphan script: no lib anywhere → clean error ---------------

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
cp "${__REPO_ROOT}/scripts/sovereign-osctl" "${tmp}/sovereign-osctl"
chmod +x "${tmp}/sovereign-osctl"

set +e
out="$("${tmp}/sovereign-osctl" version 2>&1)"
rc=$?
set -e
if [ "${rc}" -ne 0 ] && grep -q "can't locate its lib" <<< "${out}"; then
  ok "orphan script (no lib found) → clear error message"
else
  ko "orphan run gate broken: rc=${rc}"
fi

# Remediation hint
if grep -q "Set SOVEREIGN_OS_LIB=<dir> to override" <<< "${out}"; then
  ok "error message includes SOVEREIGN_OS_LIB env override hint"
else
  ko "remediation hint missing"
fi

# Candidate list visible
for path in "/usr/local/lib/sovereign-os/lib/common.sh" "/usr/lib/sovereign-os/lib/common.sh" "/opt/sovereign-os/lib/common.sh"; do
  if grep -qF "${path}" <<< "${out}"; then
    ok "error message lists candidate: ${path}"
  else
    ko "candidate path missing from error: ${path}"
  fi
done

# ----------- SOVEREIGN_OS_LIB override (valid) ---------------

# Build a tmpdir that LOOKS like an installed-system layout
inst="${tmp}/sovereign-os-install"
mkdir -p "${inst}/lib"
cp "${__REPO_ROOT}/scripts/build/lib/common.sh" "${inst}/lib/common.sh"
cp "${__REPO_ROOT}/scripts/build/lib/state.sh"  "${inst}/lib/state.sh"
cp "${__REPO_ROOT}/scripts/build/lib/logging.sh" "${inst}/lib/logging.sh"
# Profiles + whitelabel are needed for some sovereign-osctl verbs but
# not for 'version' — just verify lib lookup succeeds.

set +e
out="$(SOVEREIGN_OS_LIB="${inst}" "${tmp}/sovereign-osctl" version 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "sovereign-osctl 0\." <<< "${out}"; then
  ok "SOVEREIGN_OS_LIB env override loads from tmpdir layout"
else
  ko "SOVEREIGN_OS_LIB override broken: rc=${rc} out=${out:0:200}"
fi

# ----------- SOVEREIGN_OS_LIB pointing at non-existent path → falls through ---------------
# The env override is a HINT, not absolute; if the path doesn't have
# the lib, the script keeps looking. Verify against an in-repo script
# (so the in-repo fallback wins).

set +e
out="$(SOVEREIGN_OS_LIB="/nonexistent/path/$$" "${__REPO_ROOT}/scripts/sovereign-osctl" version 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "sovereign-osctl 0\." <<< "${out}"; then
  ok "SOVEREIGN_OS_LIB pointing at junk → falls through to in-repo successfully"
else
  ko "fallthrough broken: rc=${rc}"
fi

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_sovereign_osctl_lib_paths: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
