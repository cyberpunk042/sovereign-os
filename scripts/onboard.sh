#!/usr/bin/env bash
# scripts/onboard.sh — fresh-machine operator onboarding (R138 / F-08 closure)
#
# What this does (in order):
#   1. Run setup.sh — installs git pre-commit hook + verifies python +
#      shellcheck + runs L1 smoke
#   2. Run `sovereign-osctl init` — interactive wizard for the 5
#      decisions (profile · substrate · secure-boot · encrypt · whitelabel)
#   3. Run `orchestrate.sh preflight` against the chosen profile to
#      verify the build host is ready
#   4. Print the EXACT next command (`orchestrate.sh run --dry-run`)
#
# Operator runs this ONCE per fresh-clone-on-a-new-machine.
# Idempotent — re-running re-validates + re-prompts.
#
# Env:
#   SOVEREIGN_OS_NONINTERACTIVE=1  skip every interactive prompt
#                                  (accepts defaults; suitable for CI)
#   SOVEREIGN_OS_ONBOARD_SKIP_PREFLIGHT=1  skip step 3 (operator already
#                                          ran it; speeds re-runs)

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/.." && pwd)"
cd "${__REPO_ROOT}"

bold='\033[1m'; green='\033[32m'; yellow='\033[33m'; reset='\033[0m'

echo -e "${bold}sovereign-os fresh-machine onboarding${reset}"
echo "Walks you from clone → ready-to-build in 3 steps."
echo
echo "Steps:"
echo "  1/3  dev-env setup (scripts/setup.sh)"
echo "  2/3  decision wizard (sovereign-osctl init)"
echo "  3/3  build-host preflight (orchestrate.sh preflight)"
echo

# ---- 1/3 — dev-env setup ----
echo -e "${bold}[1/3] dev-environment setup${reset}"
if [ -x "${__REPO_ROOT}/scripts/setup.sh" ]; then
  if ! "${__REPO_ROOT}/scripts/setup.sh"; then
    echo -e "${yellow}  warn: setup.sh exited non-zero; continuing${reset}"
  fi
else
  echo "  skipped — scripts/setup.sh missing"
fi
echo

# ---- 2/3 — decision wizard ----
echo -e "${bold}[2/3] decision wizard${reset}"
if ! "${__REPO_ROOT}/scripts/sovereign-osctl" init ${SOVEREIGN_OS_NONINTERACTIVE:+--non-interactive}; then
  echo -e "${yellow}  warn: init exited non-zero${reset}"
  exit 1
fi

# Read the chosen profile from the state file
profile="sain-01"
state_file="${__REPO_ROOT}/.sovereign-os/init-state.yaml"
if [ -f "${state_file}" ]; then
  parsed_profile="$(python3 -c "
import yaml, sys
try:
    with open('${state_file}') as f:
        data = yaml.safe_load(f)
    print(data.get('decisions', {}).get('profile', 'sain-01'))
except: print('sain-01')
" 2>/dev/null)"
  [ -n "${parsed_profile}" ] && profile="${parsed_profile}"
fi
echo

# ---- 3/3 — build-host preflight ----
if [ -n "${SOVEREIGN_OS_ONBOARD_SKIP_PREFLIGHT:-}" ]; then
  echo -e "${bold}[3/3] preflight${reset} — SKIPPED (SOVEREIGN_OS_ONBOARD_SKIP_PREFLIGHT=1)"
else
  echo -e "${bold}[3/3] build-host preflight (profile=${profile})${reset}"
  if SOVEREIGN_OS_PROFILE="${profile}" "${__REPO_ROOT}/scripts/build/orchestrate.sh" preflight; then
    echo -e "  ${green}✓ preflight passed${reset}"
  else
    echo -e "  ${yellow}preflight reported issues — review the output above${reset}"
    echo "  you can still continue to dry-run; some checks (TPM, network) may"
    echo "  not apply to a build host."
  fi
fi
echo

# ---- Next steps ----
echo -e "${bold}onboarding complete${reset}"
echo
echo -e "  ${green}NEXT:${reset}"
echo
echo "    # 1. Validate the pipeline plan without building (always safe)"
echo "    SOVEREIGN_OS_PROFILE=${profile} scripts/build/orchestrate.sh run --dry-run"
echo
echo "    # 2. When ready, drop --dry-run to actually build:"
echo "    SOVEREIGN_OS_PROFILE=${profile} scripts/build/orchestrate.sh run"
echo
echo "    # 3. After build succeeds, dump to target device (safety-gated):"
echo "    sovereign-osctl install image --plan build/${profile}/output/${profile} --to /dev/<target>"
echo
echo "  USEFUL OPERATOR VERBS:"
echo "    sovereign-osctl env list           — every SOVEREIGN_OS_* env var (R137)"
echo "    sovereign-osctl status             — system overview"
echo "    sovereign-osctl doctor             — profile-conditioned sanity check"
echo "    sovereign-osctl alerts             — rule-derived alerts (no Alertmanager)"
echo "    sovereign-osctl audit drift        — hardening drift detection"
echo "    scripts/build/orchestrate.sh recover  — if build fails mid-pipeline (R135)"
echo
echo "  Re-run onboarding any time: scripts/onboard.sh"
