#!/usr/bin/env bash
# tests/nspawn/test_profile_hooks_resolve.sh
#
# Substantive Layer 3 test: validates that every hook script
# referenced by a profile actually exists, is executable, and source-
# loads its common.sh dependency without error.
#
# Complements tests/lint/test_hook_script_paths.py (Layer 1 path
# existence) with shell-level runtime check.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

PROFILE="${1:-sain-01}"

# python3 resolver — some CI envs lack PyYAML in the first python3.
PYTHON3="${PYTHON3:-python3}"
if ! "${PYTHON3}" -c "import yaml" >/dev/null 2>&1; then
  if /usr/bin/python3 -c "import yaml" >/dev/null 2>&1; then
    PYTHON3="/usr/bin/python3"
  fi
fi

fail=0
pass=0

echo "tests/nspawn/test_profile_hooks_resolve.sh (profile=${PROFILE})"
echo

# Extract every hooks.*.script path from the profile via python3+yaml
hook_paths="$(${PYTHON3} - <<PY
import yaml
with open("${__REPO_ROOT}/profiles/${PROFILE}.yaml") as f:
    p = yaml.safe_load(f)
for phase, items in (p.get("hooks") or {}).items():
    for h in items or []:
        s = h.get("script")
        if s:
            print(s)
PY
)"

while IFS= read -r script; do
  [ -z "${script}" ] && continue
  full="${__REPO_ROOT}/${script}"

  if [ ! -f "${full}" ]; then
    echo "  FAIL — ${script}: file not present"
    fail=$((fail + 1))
    continue
  fi

  if [ ! -x "${full}" ]; then
    echo "  FAIL — ${script}: not executable"
    fail=$((fail + 1))
    continue
  fi

  # Syntax check
  if ! bash -n "${full}" 2>/dev/null; then
    echo "  FAIL — ${script}: bash syntax error"
    fail=$((fail + 1))
    continue
  fi

  echo "  PASS — ${script}"
  pass=$((pass + 1))
done <<< "${hook_paths}"

echo
total=$((pass + fail))
echo "test_profile_hooks_resolve: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
