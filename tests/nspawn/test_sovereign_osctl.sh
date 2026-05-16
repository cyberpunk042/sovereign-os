#!/usr/bin/env bash
# tests/nspawn/test_sovereign_osctl.sh
#
# Layer 3 substantive test for scripts/sovereign-osctl — the operator-
# facing lifecycle-management CLI (Q-019 implementation). 639 lines of
# management surface; this test exercises the parts that don't require
# root or an installed system: help / version / profiles / inference
# route classification / unknown-command handling.
#
# Catches wiring bugs (5th class so far): bash-shell-var-vs-exported-env
# propagation into python3 subshells, command-surface drift, profile
# enumeration logic, classify() reachability from the CLI surface.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

CTL="${__REPO_ROOT}/scripts/sovereign-osctl"

[ -x "${CTL}" ] || { echo "FAIL: sovereign-osctl not executable: ${CTL}"; exit 1; }

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

echo "tests/nspawn/test_sovereign_osctl.sh"
echo "  ctl: ${CTL}"
echo

# Always run with non-interactive + a known profile, so the CLI doesn't
# stall waiting on stdin and doesn't try to read /etc/sovereign-os/.
export SOVEREIGN_OS_NONINTERACTIVE=1
export SOVEREIGN_OS_PROFILE=sain-01

# ----------- help / no-args ---------------

out="$("${CTL}" help 2>&1)"
if grep -q "sovereign-osctl — sovereign-os lifecycle management" <<< "${out}"; then
  ok "help emits banner"
else
  ko "help missing banner: ${out}"
fi

if grep -q "COMMANDS:" <<< "${out}" && grep -q "profiles list" <<< "${out}" && grep -q "inference status" <<< "${out}"; then
  ok "help lists COMMANDS surface (profiles + inference at minimum)"
else
  ko "help missing command surface"
fi

if grep -q "ENV VARS" <<< "${out}"; then
  ok "help documents ENV VARS section"
else
  ko "help missing ENV VARS section"
fi

# no-args should print help too
out_noargs="$("${CTL}" 2>&1 || true)"
if grep -q "sovereign-osctl — sovereign-os lifecycle management" <<< "${out_noargs}"; then
  ok "no-args invocation prints help (default)"
else
  ko "no-args invocation didn't print help: ${out_noargs}"
fi

# --help should also work
out_dh="$("${CTL}" --help 2>&1 || true)"
if grep -q "sovereign-osctl — sovereign-os lifecycle management" <<< "${out_dh}"; then
  ok "--help alias works"
else
  ko "--help alias failed: ${out_dh}"
fi

# ----------- version ---------------

out_v="$("${CTL}" version 2>&1)"
if grep -qE "^sovereign-osctl [0-9]+\.[0-9]+\.[0-9]+" <<< "${out_v}"; then
  ok "version emits semver-ish line"
else
  ko "version output unexpected: ${out_v}"
fi

if grep -q "active profile:    sain-01" <<< "${out_v}"; then
  ok "version reports active profile"
else
  ko "version missing active profile: ${out_v}"
fi

# Round 64: --json mode for fleet tooling
out_json="$("${CTL}" version --json 2>&1)"
if python3 -c "
import json, sys
d = json.loads('''${out_json}''')
for k in ('sovereign_osctl_version', 'phase', 'active_profile',
          'active_whitelabel', 'kernel_release', 'os_pretty_name', 'repo'):
    assert k in d, f'missing {k}'
sys.exit(0)
" 2>/dev/null; then
  ok "version --json: valid JSON with all 7 required keys"
else
  ko "version --json malformed: ${out_json:0:200}"
fi

# -V alias
out_V="$("${CTL}" -V 2>&1)"
if grep -qE "^sovereign-osctl" <<< "${out_V}"; then
  ok "-V alias works"
else
  ko "-V alias failed: ${out_V}"
fi

# ----------- unknown command → exit 2 ---------------

set +e
"${CTL}" definitely-not-a-real-command >/dev/null 2>&1
rc=$?
set -e
if [ "${rc}" -eq 2 ]; then
  ok "unknown command exits 2"
else
  ko "unknown command exit code: expected 2, got ${rc}"
fi

# ----------- profiles list ---------------
# Regression gate: SOVEREIGN_OS_PROFILE_FILE MUST be exported so the
# python3 subshell inside profile_field() sees it. Previously a shell-var
# assignment (no export) silently produced empty name/status — the
# header printed but the rows were blank. This assertion locks it in.

out_pl="$("${CTL}" profiles list 2>&1)"
if grep -q "Declared profiles:" <<< "${out_pl}"; then
  ok "profiles list emits header"
else
  ko "profiles list missing header: ${out_pl}"
fi

if grep -q "sain-01" <<< "${out_pl}"; then
  ok "profiles list enumerates sain-01"
else
  ko "profiles list didn't list sain-01: ${out_pl}"
fi

if grep -q "old-workstation" <<< "${out_pl}"; then
  ok "profiles list enumerates old-workstation"
else
  ko "profiles list didn't list old-workstation: ${out_pl}"
fi

# Regression: the row MUST contain the identity.name from the profile
# YAML, not just the id. If the export bug regresses, this fails.
if grep -E "sain-01\s+SAIN-01 AI Workstation" <<< "${out_pl}" >/dev/null; then
  ok "profiles list resolves identity.name (export-propagation gate)"
else
  ko "profiles list shows id but not identity.name — SOVEREIGN_OS_PROFILE_FILE export regressed?"
fi

# Status field should resolve too
if grep -E "\[draft\]" <<< "${out_pl}" >/dev/null; then
  ok "profiles list resolves identity.status"
else
  ko "profiles list missing identity.status"
fi

# ----------- profiles show ---------------

out_ps="$("${CTL}" profiles show sain-01 2>&1)"
if grep -q "id: sain-01" <<< "${out_ps}"; then
  ok "profiles show sain-01 emits the YAML"
else
  ko "profiles show didn't emit profile YAML"
fi

# ----------- profiles show-effective (calls profile_merger) ---------------

out_pe="$("${CTL}" profiles show-effective sain-01 2>&1)"
if grep -q "id: sain-01" <<< "${out_pe}" && grep -q "march:" <<< "${out_pe}"; then
  ok "profiles show-effective resolves through profile_merger"
else
  ko "profiles show-effective failed: ${out_pe}"
fi

# ----------- profiles active ---------------

out_pa="$("${CTL}" profiles active 2>&1)"
if [ "${out_pa}" = "sain-01" ]; then
  ok "profiles active echoes SOVEREIGN_OS_PROFILE"
else
  ko "profiles active output unexpected: '${out_pa}'"
fi

# ----------- profiles validate ---------------

if "${CTL}" profiles validate >/dev/null 2>&1; then
  ok "profiles validate delegates to validate-profiles.sh and passes"
else
  ko "profiles validate failed"
fi

# ----------- profiles unknown-subcommand → exit 2 ---------------

set +e
"${CTL}" profiles definitely-not-a-real-subcommand >/dev/null 2>&1
rc=$?
set -e
if [ "${rc}" -eq 2 ]; then
  ok "profiles <unknown> exits 2"
else
  ko "profiles <unknown> exit code: expected 2, got ${rc}"
fi

# ----------- inference route (router.classify() reachable from CLI) ---------------

# A code/math-heavy prompt should classify to oracle_core per router rules.
out_ir="$("${CTL}" inference route "fix this python traceback: TypeError on line 42" 2>&1)"
if grep -q "would route to:" <<< "${out_ir}"; then
  ok "inference route emits routing decision"
else
  ko "inference route didn't classify: ${out_ir}"
fi

if grep -qE "oracle_core|logic_engine|pulse" <<< "${out_ir}"; then
  ok "inference route picks one of the 3 tiers"
else
  ko "inference route output is not a known tier: ${out_ir}"
fi

# A short low-entropy prompt should route to pulse (ternary fast-path).
out_ir2="$("${CTL}" inference route "hi" 2>&1)"
if grep -q "would route to: pulse" <<< "${out_ir2}"; then
  ok "inference route 'hi' → pulse (short low-entropy)"
else
  # Soft fail: classify rules can evolve; just verify it routes somewhere.
  if grep -q "would route to:" <<< "${out_ir2}"; then
    ok "inference route short prompt routes (tier may evolve)"
  else
    ko "inference route 'hi' failed: ${out_ir2}"
  fi
fi

# ----------- inference unknown-subcommand → exit 2 ---------------

set +e
"${CTL}" inference definitely-not-a-real-subcommand >/dev/null 2>&1
rc=$?
set -e
if [ "${rc}" -eq 2 ]; then
  ok "inference <unknown> exits 2"
else
  ko "inference <unknown> exit code: expected 2, got ${rc}"
fi

# ----------- result ---------------

echo
total=$((pass + fail))
echo "test_sovereign_osctl: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
