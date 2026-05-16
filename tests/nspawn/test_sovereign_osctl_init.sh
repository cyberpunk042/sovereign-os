#!/usr/bin/env bash
# tests/nspawn/test_sovereign_osctl_init.sh
#
# Layer 3 test for sovereign-osctl init (Round 136; F-02 HIGH closure).
# Verifies --non-interactive mode + state file shape + next-steps output.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_sovereign_osctl_init.sh"
echo

# Save + restore in-repo state file (don't pollute the working tree)
state_file="${__REPO_ROOT}/.sovereign-os/init-state.yaml"
state_backup=""
if [ -f "${state_file}" ]; then
  state_backup="$(mktemp)"
  cp "${state_file}" "${state_backup}"
fi
trap '
  if [ -n "${state_backup}" ] && [ -f "${state_backup}" ]; then
    cp "${state_backup}" "${state_file}"
    rm -f "${state_backup}"
  else
    rm -f "${state_file}"
  fi
' EXIT

# ---------- --non-interactive accepts defaults ----------
rm -f "${state_file}"
set +e
out="$("${OSCTL}" init --non-interactive 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "--non-interactive → exit 0"
else
  ko "--non-interactive broken (rc=${rc})"
fi

# 5 decisions present in output
for n in "1/5" "2/5" "3/5" "4/5" "5/5"; do
  if grep -q "\[${n}\]" <<< "${out}"; then
    ok "decision ${n} presented"
  else
    ko "decision ${n} missing"
  fi
done

# All decision categories surfaced
for kw in PROFILE SUBSTRATE SECURE-BOOT "DISK ENCRYPTION" WHITELABEL; do
  if grep -q "${kw}" <<< "${out}"; then
    ok "category: ${kw}"
  else
    ko "category missing: ${kw}"
  fi
done

# Each profile shown
for p in sain-01 old-workstation minimal developer headless; do
  if grep -q "${p}" <<< "${out}"; then
    ok "profile listed: ${p}"
  else
    ko "profile missing from menu: ${p}"
  fi
done

# Recommendation lines (operator decision-support)
if grep -c "recommendation:" <<< "${out}" | grep -qE "^[3-9]"; then
  ok "≥3 recommendation lines (decision-support content)"
else
  ko "recommendation lines too few"
fi

# Next-steps block
for next in "preflight" "orchestrate.sh run --dry-run" "install image --plan"; do
  if grep -q "${next}" <<< "${out}"; then
    ok "next-step: ${next}"
  else
    ko "next-step missing: ${next}"
  fi
done

# ---------- State file written ----------
if [ -f "${state_file}" ]; then
  ok "state file written: .sovereign-os/init-state.yaml"
else
  ko "state file NOT written"
fi

# State file is valid YAML with the 5 decisions
if python3 -c "
import yaml
with open('${state_file}') as f:
    data = yaml.safe_load(f)
d = data.get('decisions', {})
assert d.get('profile') == 'sain-01', f'profile wrong: {d.get(\"profile\")}'
assert d.get('substrate') == 'mkosi', f'substrate wrong: {d.get(\"substrate\")}'
assert d.get('secure_boot') == 'signed', f'secure_boot wrong: {d.get(\"secure_boot\")}'
assert d.get('encrypt') == 'yes', f'encrypt wrong: {d.get(\"encrypt\")}'
assert d.get('whitelabel') == 'default', f'whitelabel wrong: {d.get(\"whitelabel\")}'
assert 'init_completed_at' in data, 'timestamp missing'
" 2>&1; then
  ok "state file has all 5 decisions with sain-01 defaults"
else
  ko "state file shape wrong"
fi

# ---------- Idempotency: re-run overwrites ----------
old_ts="$(grep init_completed_at "${state_file}")"
sleep 1
set +e
"${OSCTL}" init --non-interactive >/dev/null 2>&1
rc=$?
set -e
new_ts="$(grep init_completed_at "${state_file}")"
if [ "${rc}" -eq 0 ] && [ "${old_ts}" != "${new_ts}" ]; then
  ok "re-running init updates the state file (idempotent overwrite)"
else
  ko "re-run idempotency broken"
fi

# ---------- Unknown flag ----------
set +e
out="$("${OSCTL}" init --bogus-flag 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 2 ] && grep -q "unknown init flag" <<< "${out}"; then
  ok "unknown flag → exit 2"
else
  ko "unknown-flag gate broken (rc=${rc})"
fi

# ---------- SOVEREIGN_OS_NONINTERACTIVE env honored ----------
rm -f "${state_file}"
set +e
out="$(SOVEREIGN_OS_NONINTERACTIVE=1 "${OSCTL}" init 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && [ -f "${state_file}" ]; then
  ok "SOVEREIGN_OS_NONINTERACTIVE=1 env triggers non-interactive mode"
else
  ko "NONINTERACTIVE env not honored"
fi

# ---------- top-level help mentions init ----------
help_out="$("${OSCTL}" help 2>&1)"
if grep -q "init \[--non-interactive\]\|init " <<< "${help_out}"; then
  ok "top-level help documents 'init'"
else
  ko "help missing init"
fi

# ---------- Dispatcher routes init → cmd_init ----------
if grep -qE "init\)\s+cmd_init" "${OSCTL}"; then
  ok "dispatcher routes 'init' → cmd_init"
else
  ko "dispatch entry missing for init"
fi

# ---------- result ----------
echo
total=$((pass + fail))
echo "test_sovereign_osctl_init: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
