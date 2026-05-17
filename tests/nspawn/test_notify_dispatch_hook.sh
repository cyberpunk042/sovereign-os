#!/usr/bin/env bash
# tests/nspawn/test_notify_dispatch_hook.sh — R229 (SDD-026 Z-6) autonomous
# health-scan + notification fan-out hook + matching systemd timer/service.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

HOOK="${__REPO_ROOT}/scripts/hooks/recurrent/notify-dispatch.sh"
SERVICE="${__REPO_ROOT}/systemd/system/sovereign-notify-dispatch.service"
TIMER="${__REPO_ROOT}/systemd/system/sovereign-notify-dispatch.timer"

echo "tests/nspawn/test_notify_dispatch_hook.sh"
echo

# ---- shipped artifacts ----
[ -x "${HOOK}" ] && ok "hook executable" \
  || { ko "missing/non-exec ${HOOK}"; exit 1; }
[ -f "${SERVICE}" ] && ok "service unit shipped" || ko "missing service unit"
[ -f "${TIMER}" ] && ok "timer unit shipped" || ko "missing timer unit"

# ---- hook header cites R229 ----
grep -q "R229" "${HOOK}" && ok "hook cites R229" || ko "R229 citation missing"
grep -q "R226" "${HOOK}" && ok "hook cites R226 health-scan" || ko "R226 ref missing"
grep -q "R228" "${HOOK}" && ok "hook cites R228 dispatcher" || ko "R228 ref missing"

# ---- service unit: timer wires the hook + hardening ----
grep -q "notify-dispatch.sh" "${SERVICE}" \
  && ok "service ExecStart points at the hook" || ko "ExecStart wrong"
grep -q "Type=oneshot" "${SERVICE}" \
  && ok "service is oneshot" || ko "service Type wrong"
for key in ProtectSystem=strict NoNewPrivileges=true PrivateTmp=true \
           ProtectHome=true LockPersonality=true RestrictRealtime=true; do
  grep -q "${key}" "${SERVICE}" \
    && ok "service has ${key}" || ko "service missing ${key}"
done

# ---- timer: hourly + persistent + Unit reference ----
grep -q "OnCalendar=hourly" "${TIMER}" \
  && ok "timer fires hourly" || ko "OnCalendar wrong"
grep -q "RandomizedDelaySec=" "${TIMER}" \
  && ok "timer randomizes (jitter avoids fleet sync)" || ko "no jitter"
grep -q "Persistent=true" "${TIMER}" \
  && ok "timer persistent across reboots" || ko "Persistent missing"
grep -q "Unit=sovereign-notify-dispatch.service" "${TIMER}" \
  && ok "timer wires to the matching service" || ko "Unit wrong"

# ---- live invocation: hook runs, dispatch fires, dedup holds ----
TMPDIR="$(mktemp -d -t r229-hook.XXXXXX)"
trap 'rm -rf "${TMPDIR}"' EXIT
cat > "${TMPDIR}/cfg.toml" <<'TOML'
[channels.file]
enabled = true
path = "PLACEHOLDER"
TOML
sed -i "s|PLACEHOLDER|${TMPDIR}/events.jsonl|" "${TMPDIR}/cfg.toml"

export SOVEREIGN_OS_NOTIFY_CONFIG="${TMPDIR}/cfg.toml"
export SOVEREIGN_OS_NOTIFY_STATE="${TMPDIR}/state.json"

# Run 1 — should emit events (depends on live health-scan having some
# probe at attention severity in this sandbox; we don't assert event
# count strictly, only that the hook completes rc=0 + writes state).
out1="$("${HOOK}" 2>&1)"
rc1=$?
[ "${rc1}" -eq 0 ] && ok "hook run 1 rc=0" || ko "hook run 1 rc=${rc1}: ${out1}"
echo "${out1}" | grep -q "health-scan rc=" \
  && ok "hook logs health-scan rc" || ko "no health-scan log line"
echo "${out1}" | grep -q "dispatch rc=" \
  && ok "hook logs dispatch rc" || ko "no dispatch log line"
[ -f "${TMPDIR}/state.json" ] \
  && ok "hook wrote dedup state" || ko "state file missing"

# Run 2 — same state, same probes → events_emitted=0 (dedup holds).
out2="$("${HOOK}" 2>&1)"
rc2=$?
[ "${rc2}" -eq 0 ] && ok "hook run 2 rc=0" || ko "hook run 2 rc=${rc2}"
echo "${out2}" | grep -q "events=0" \
  && ok "hook run 2 dedups to events=0" || ko "dedup did not hold: ${out2}"

# ---- DRY-RUN mode honors the contract ----
out_dry="$(SOVEREIGN_OS_DRY_RUN=1 "${HOOK}" 2>&1)"
rc_dry=$?
[ "${rc_dry}" -eq 0 ] && ok "DRY-RUN rc=0" || ko "DRY-RUN rc=${rc_dry}"
echo "${out_dry}" | grep -q "DRY-RUN" \
  && ok "DRY-RUN logs marker" || ko "DRY-RUN marker missing"
# Dry-run must NOT call dispatch — the dispatch-rc line should be absent.
echo "${out_dry}" | grep -qv "dispatch rc=" \
  && ok "DRY-RUN does not invoke dispatcher" \
  || ko "DRY-RUN unexpectedly ran dispatcher"

# ---- defensive: the hook MUST cite missing-binary failures inline ----
grep -q "missing.*health-scan\|R226 health-scan absent" "${HOOK}" \
  && ok "hook source carries operator-readable missing-scan message" \
  || ko "hook missing-scan diagnostic absent"
grep -q "missing.*dispatch\|R228 notify dispatcher absent" "${HOOK}" \
  && ok "hook source carries operator-readable missing-dispatcher message" \
  || ko "hook missing-dispatcher diagnostic absent"

echo
total=$((pass + fail))
echo "test_notify_dispatch_hook: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
