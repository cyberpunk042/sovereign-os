#!/usr/bin/env bash
# tests/nspawn/test_sovereign_osctl_maintenance.sh
#
# Layer 3 test for the expanded `sovereign-osctl maintenance` surface
# (Round 66 — 8 subverbs total, was 2).
#
# Asserts:
#   - 'maintenance list' enumerates all 8 subverbs
#   - 'maintenance arc-status' works without root (read-only)
#   - 'maintenance log-rotate' invokes the recurrent hook (DRY_RUN safe)
#   - 'maintenance security-check' invokes the hook
#   - 'maintenance models-sync' invokes the hook
#   - 'maintenance perimeter-check' invokes the hook
#   - unknown subverb → exit 2 + valid-list hint
#   - help documents all 8 subverbs

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

CTL="${__REPO_ROOT}/scripts/sovereign-osctl"
[ -x "${CTL}" ] || { echo "FAIL: sovereign-osctl not executable"; exit 1; }

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_sovereign_osctl_maintenance.sh"
echo

export SOVEREIGN_OS_NONINTERACTIVE=1
export SOVEREIGN_OS_PROFILE=sain-01
export SOVEREIGN_OS_DRY_RUN=1
export SOVEREIGN_OS_LOG_DIR="$(mktemp -d)"
export SOVEREIGN_OS_METRICS_DIR="$(mktemp -d)"

# ----------- maintenance list ---------------

out="$("${CTL}" maintenance list 2>&1)"
expected_subverbs=(list scrub arc-status log-rotate snapshot
                   security-check models-sync perimeter-check)
for v in "${expected_subverbs[@]}"; do
  if grep -qE "^\s+${v}\s" <<< "${out}"; then
    ok "maintenance list documents: ${v}"
  else
    ko "maintenance list missing: ${v}"
  fi
done

# ----------- arc-status (no root needed) ---------------

set +e
out="$("${CTL}" maintenance arc-status 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "maintenance arc-status exits 0 (gracefully degrades on non-ZFS host)"
else
  ko "maintenance arc-status rc=${rc}"
fi

# ----------- log-rotate (DRY_RUN exercises the path safely) ---------------

set +e
out="$("${CTL}" maintenance log-rotate 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "log-rotate" <<< "${out}"; then
  ok "maintenance log-rotate invokes the recurrent hook"
else
  ko "maintenance log-rotate broken: rc=${rc}"
fi

# ----------- security-check (gracefully no-op on non-apt) ---------------

set +e
out="$("${CTL}" maintenance security-check 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "security-update-check" <<< "${out}"; then
  ok "maintenance security-check invokes the recurrent hook"
else
  ko "maintenance security-check broken: rc=${rc}"
fi

# ----------- models-sync ---------------

set +e
out="$(SOVEREIGN_OS_MODELS_DIR="/tmp/nope-$$" "${CTL}" maintenance models-sync 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "model-catalog-sync" <<< "${out}"; then
  ok "maintenance models-sync invokes the recurrent hook"
else
  ko "maintenance models-sync broken: rc=${rc}"
fi

# ----------- perimeter-check ---------------

set +e
out="$("${CTL}" maintenance perimeter-check 2>&1)"
rc=$?
set -e
if grep -q "tetragon-policy-verify\|perimeter\|Tetragon" <<< "${out}"; then
  ok "maintenance perimeter-check invokes the recurrent hook"
else
  ko "maintenance perimeter-check broken: rc=${rc} out=${out:0:200}"
fi

# ----------- unknown subverb → exit 2 ---------------

set +e
"${CTL}" maintenance totally-bogus >/dev/null 2>&1
rc=$?
set -e
if [ "${rc}" -eq 2 ]; then
  ok "unknown maintenance subverb exits 2"
else
  ko "unknown subverb exit code: ${rc}"
fi

# ----------- help documents the new surface ---------------

help_out="$("${CTL}" help 2>&1)"
for v in log-rotate snapshot security-check models-sync perimeter-check; do
  if grep -q "maintenance ${v}" <<< "${help_out}"; then
    ok "help documents 'maintenance ${v}'"
  else
    ko "help missing 'maintenance ${v}'"
  fi
done

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_sovereign_osctl_maintenance: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
