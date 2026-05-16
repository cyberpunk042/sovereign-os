#!/usr/bin/env bash
# tests/nspawn/test_sovereign_osctl_dispatch_surface.sh
#
# Layer 3 catch-all test for the sovereign-osctl dispatcher surface.
# Goal: enumerate every top-level verb + every subverb that's safe
# to invoke read-only, and verify the dispatcher reaches them.
#
# Catches a regression class: refactor to the case-statement in the
# main dispatcher accidentally drops or renames a verb; this test
# fails before a broken release lands.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

CTL="${__REPO_ROOT}/scripts/sovereign-osctl"
[ -x "${CTL}" ] || { echo "FAIL: sovereign-osctl not executable"; exit 1; }

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_sovereign_osctl_dispatch_surface.sh"
echo

export SOVEREIGN_OS_NONINTERACTIVE=1
export SOVEREIGN_OS_PROFILE=sain-01
export SOVEREIGN_OS_LOG_DIR="$(mktemp -d)"
export SOVEREIGN_OS_METRICS_DIR="$(mktemp -d)"

# Read-only / safe top-level verbs (no root, no state mutation)
SAFE_VERBS=(help status doctor version)

for v in "${SAFE_VERBS[@]}"; do
  set +e
  "${CTL}" "${v}" >/dev/null 2>&1
  rc=$?
  set -e
  # Doctor exits 1 when tooling missing (CI) — that's a valid behavior
  if [ "${rc}" -le 1 ]; then
    ok "top-level verb reachable: ${v} (rc=${rc})"
  else
    ko "top-level verb broken: ${v} rc=${rc}"
  fi
done

# Aliases
for alias in --help -h --version -V; do
  set +e
  "${CTL}" "${alias}" >/dev/null 2>&1
  rc=$?
  set -e
  if [ "${rc}" -eq 0 ]; then
    ok "alias reachable: ${alias}"
  else
    ko "alias broken: ${alias} rc=${rc}"
  fi
done

# Subverb surfaces — invoke 'list' or no-arg-default of each command-
# group and verify exit + non-empty output
declare -A SUBVERB_PROBE=(
  [profiles]=list
  [whitelabel]=list
  [perimeter]=status
  [models]=list
  [audit]=storage
  [maintenance]=list
  [inference]=status
  [assistant]=list
  [metrics]=list
  [journal]=list
  [history]=list
)

for cmd in "${!SUBVERB_PROBE[@]}"; do
  sub="${SUBVERB_PROBE[$cmd]}"
  set +e
  out="$("${CTL}" "${cmd}" "${sub}" 2>&1)"
  rc=$?
  set -e
  if [ "${rc}" -le 1 ] && [ -n "${out}" ]; then
    ok "subverb reachable: ${cmd} ${sub} (rc=${rc})"
  else
    ko "subverb broken: ${cmd} ${sub} rc=${rc} empty=$([ -z "${out}" ] && echo yes || echo no)"
  fi
done

# Every cmd_<name> function in the source has a dispatcher entry
mapfile -t functions < <(grep -oE "^cmd_[a-z_]+" "${CTL}" | sort -u)
for fn in "${functions[@]}"; do
  verb="${fn#cmd_}"
  # cmd_help is reachable via 'help' / '--help' / '-h' / no-args
  if grep -qE "^\s+${verb}[\)\|]" "${CTL}" \
     || grep -qE "${verb}\|" "${CTL}" \
     || [ "${verb}" = "help" ]; then
    ok "dispatcher has entry for: ${verb}"
  else
    ko "function ${fn}() defined but no dispatcher entry"
  fi
done

# Unknown top-level command → exit 2
set +e
"${CTL}" totally-bogus-verb >/dev/null 2>&1
rc=$?
set -e
if [ "${rc}" -eq 2 ]; then
  ok "unknown top-level verb exits 2"
else
  ko "unknown verb exit ${rc}"
fi

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_sovereign_osctl_dispatch_surface: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
