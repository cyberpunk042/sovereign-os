#!/usr/bin/env bash
# tests/nspawn/test_git_hooks.sh
#
# Layer 3 test for Round 52 — sovereign-os git pre-commit hook + installer.
#
# Asserts:
#   - install.sh symlinks the hook into .git/hooks/
#   - install.sh is idempotent
#   - install.sh rejects unknown hook names
#   - pre-commit hook is well-formed bash (passes bash -n)
#   - pre-commit hook references the L1 lint + profile validation
#   - README documents env var bypass paths

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_git_hooks.sh"
echo

# ----------- presence + syntax ---------------

[ -f "${__REPO_ROOT}/scripts/git-hooks/pre-commit" ] \
  && ok "pre-commit script present" \
  || ko "pre-commit script missing"

[ -f "${__REPO_ROOT}/scripts/git-hooks/install.sh" ] \
  && ok "install.sh present" \
  || ko "install.sh missing"

[ -f "${__REPO_ROOT}/scripts/git-hooks/README.md" ] \
  && ok "README.md present" \
  || ko "README.md missing"

bash -n "${__REPO_ROOT}/scripts/git-hooks/pre-commit" \
  && ok "pre-commit passes bash -n syntax check" \
  || ko "pre-commit has syntax errors"

bash -n "${__REPO_ROOT}/scripts/git-hooks/install.sh" \
  && ok "install.sh passes bash -n syntax check" \
  || ko "install.sh has syntax errors"

# ----------- pre-commit content ---------------

if grep -q "pytest tests/schema tests/lint" "${__REPO_ROOT}/scripts/git-hooks/pre-commit"; then
  ok "pre-commit runs L1 schema + lint pytest"
else
  ko "pre-commit doesn't run L1 pytest"
fi

if grep -q "validate-profiles.sh" "${__REPO_ROOT}/scripts/git-hooks/pre-commit"; then
  ok "pre-commit runs validate-profiles.sh"
else
  ko "pre-commit doesn't validate profiles"
fi

if grep -q "shellcheck" "${__REPO_ROOT}/scripts/git-hooks/pre-commit"; then
  ok "pre-commit runs shellcheck (warning-only)"
else
  ko "pre-commit doesn't run shellcheck"
fi

if grep -q "SOVEREIGN_OS_PRECOMMIT_SKIP_L3\|SOVEREIGN_OS_PRECOMMIT_FULL" "${__REPO_ROOT}/scripts/git-hooks/pre-commit"; then
  ok "pre-commit honors SKIP_L3 / FULL env vars"
else
  ko "pre-commit missing env-var bypass"
fi

# ----------- install.sh idempotency + rejection ---------------

# Use a throwaway git repo to avoid touching the real .git/hooks
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
(
  cd "${tmp}"
  git init -q
  git config commit.gpgsign false 2>/dev/null
  mkdir -p scripts/git-hooks
  cp "${__REPO_ROOT}/scripts/git-hooks/pre-commit" scripts/git-hooks/
  cp "${__REPO_ROOT}/scripts/git-hooks/install.sh" scripts/git-hooks/
  cp "${__REPO_ROOT}/scripts/git-hooks/README.md" scripts/git-hooks/
  chmod +x scripts/git-hooks/install.sh scripts/git-hooks/pre-commit
  bash scripts/git-hooks/install.sh pre-commit >/dev/null 2>&1
)
if [ -L "${tmp}/.git/hooks/pre-commit" ]; then
  ok "install.sh creates pre-commit symlink in .git/hooks/"
else
  ko "install.sh did not create symlink"
fi

# Idempotency — re-run, must succeed cleanly
(cd "${tmp}" && bash scripts/git-hooks/install.sh pre-commit >/dev/null 2>&1) \
  && ok "install.sh idempotent (re-run succeeds)" \
  || ko "install.sh second run failed"

# Reject unknown hook
set +e
(cd "${tmp}" && bash scripts/git-hooks/install.sh totally-bogus-hook >/dev/null 2>&1)
rc=$?
set -e
if [ "${rc}" -ne 0 ]; then
  ok "install.sh rejects unknown hook name with non-zero exit"
else
  ko "install.sh accepted bogus hook"
fi

# ----------- README content ---------------

if grep -q "git commit --no-verify" "${__REPO_ROOT}/scripts/git-hooks/README.md"; then
  ok "README documents --no-verify bypass"
else
  ko "README missing --no-verify reference"
fi

if grep -q "direct-push-to-main" "${__REPO_ROOT}/scripts/git-hooks/README.md"; then
  ok "README mentions direct-push-to-main rationale"
else
  ko "README missing operator workflow rationale"
fi

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_git_hooks: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
