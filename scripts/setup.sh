#!/usr/bin/env bash
# scripts/setup.sh — one-command operator dev-environment setup.
#
# What it does:
#   1. Installs the git pre-commit hook (Round 52)
#   2. Verifies python3 + required Python modules (pyyaml + jsonschema)
#   3. Verifies shellcheck (optional but recommended)
#   4. Sets the active profile via SOVEREIGN_OS_PROFILE or interactive pick
#   5. Runs the Layer 1 lint suite as a smoke test
#
# Idempotent — re-running is safe. Operator runs this once after a
# fresh clone to get to a known-working dev state.
#
# Tunable env:
#   SOVEREIGN_OS_PROFILE             default profile (skips interactive pick)
#   SOVEREIGN_OS_SETUP_SKIP_HOOKS=1  skip git hooks install
#   SOVEREIGN_OS_SETUP_SKIP_SMOKE=1  skip the smoke test

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/.." && pwd)"
cd "${__REPO_ROOT}"

bold='\033[1m'; red='\033[31m'; green='\033[32m'; yellow='\033[33m'; reset='\033[0m'

echo -e "${bold}sovereign-os operator dev-environment setup${reset}"
echo

failed=0

# ----------- (1) git pre-commit hook ---------------

if [ -z "${SOVEREIGN_OS_SETUP_SKIP_HOOKS:-}" ]; then
  echo -e "${bold}[1/5] git hooks (pre-commit gate + post-merge/rebase warnings)${reset}"
  if [ -x "${__REPO_ROOT}/scripts/git-hooks/install.sh" ]; then
    # all hooks: pre-commit (gate) + post-merge/post-rewrite (root-ownership warn)
    "${__REPO_ROOT}/scripts/git-hooks/install.sh"
  else
    echo -e "  ${yellow}!${reset} scripts/git-hooks/install.sh not present — skipping"
  fi
  echo
fi

# ----------- (2) Python dependencies ---------------

echo -e "${bold}[2/5] python3 dependencies${reset}"
for mod in yaml jsonschema; do
  if python3 -c "import ${mod}" 2>/dev/null; then
    echo -e "  ${green}✓${reset} python3 has ${mod}"
  else
    echo -e "  ${red}✗${reset} python3 missing ${mod} (try: apt install python3-${mod} OR pip install ${mod})"
    failed=1
  fi
done
echo

# ----------- (3) shellcheck (optional) ---------------

echo -e "${bold}[3/5] shellcheck${reset}"
if command -v shellcheck >/dev/null 2>&1; then
  echo -e "  ${green}✓${reset} shellcheck $(shellcheck --version 2>/dev/null | grep version | head -1 | awk '{print $2}') installed"
else
  echo -e "  ${yellow}!${reset} shellcheck not installed (optional; CI runs it — local convenience only)"
fi
echo

# ----------- (4) active profile ---------------

echo -e "${bold}[4/5] active profile${reset}"
mapfile -t available_profiles < <(find "${__REPO_ROOT}/profiles" -maxdepth 1 -name '*.yaml' -type f | xargs -n1 basename | sed 's/\.yaml$//' | sort)

if [ -n "${SOVEREIGN_OS_PROFILE:-}" ]; then
  profile="${SOVEREIGN_OS_PROFILE}"
elif [ -t 0 ] && [ -z "${SOVEREIGN_OS_NONINTERACTIVE:-}" ]; then
  echo "  available profiles: ${available_profiles[*]}"
  read -rp "  pick a profile (default: sain-01): " profile
  profile="${profile:-sain-01}"
else
  profile="sain-01"
fi

if printf '%s\n' "${available_profiles[@]}" | grep -qx "${profile}"; then
  echo -e "  ${green}✓${reset} active profile: ${profile}"
  # Persist to a local-only file (not committed)
  mkdir -p .sovereign-os
  echo "${profile}" > .sovereign-os/active-profile
  echo -e "  ${green}✓${reset} persisted to .sovereign-os/active-profile"
else
  echo -e "  ${red}✗${reset} unknown profile: ${profile}"
  failed=1
fi
echo

# ----------- (5) smoke test ---------------

if [ -z "${SOVEREIGN_OS_SETUP_SKIP_SMOKE:-}" ]; then
  echo -e "${bold}[5/5] L1 smoke test${reset}"
  if python3 -m pytest tests/schema tests/lint -q >/dev/null 2>&1; then
    echo -e "  ${green}✓${reset} Layer 1 lint passes (schema + lint)"
  else
    echo -e "  ${red}✗${reset} Layer 1 lint failed — run \`python3 -m pytest tests/schema tests/lint -v\` to see"
    failed=1
  fi
  echo
fi

# ----------- result ---------------

if [ "${failed}" -ne 0 ]; then
  echo -e "${bold}${red}setup gate FAILED${reset} — fix issues above + re-run"
  exit 1
fi

echo -e "${bold}${green}setup complete${reset}"
echo
echo "Next steps:"
echo "  scripts/install/bootstrap-host.sh             # ONE-TIME: enable apt components + install ALL build-host deps (zfs, mkosi, qemu…)"
echo "  scripts/build/orchestrate.sh run --dry-run    # validate build plan"
echo "  scripts/build/orchestrate.sh preflight        # run pre-install hooks"
echo "  sudo scripts/build/orchestrate.sh run         # actual build (operator-only)"
echo
echo "Operator handbook: docs/src/ops/manage.md"
echo "Install runbook:   docs/src/install-runbook.md"
echo "Handoff state:     docs/handoff/002-foundation-substantive-buildout.md"
