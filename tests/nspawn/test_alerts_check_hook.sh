#!/usr/bin/env bash
# tests/nspawn/test_alerts_check_hook.sh
#
# Layer 3 test for the alerts-check recurrent hook (Round 90).
# Verifies it:
#   - emits meta-counters to .prom
#   - persists payload to alerts.json
#   - tallies ALERT/WARN correctly against synthetic input
#   - honors DRY_RUN
#   - is wired into `sovereign-osctl maintenance alerts-check`

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

HOOK="${__REPO_ROOT}/scripts/hooks/recurrent/alerts-check.sh"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_alerts_check_hook.sh"
echo

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

mdir="${tmp}/textfile_collector"
mkdir -p "${mdir}"
state_dir="${tmp}/state"
mkdir -p "${state_dir}"

# Seed .prom files representing real alert-triggering conditions
cat > "${mdir}/sovereign-os-fail.prom" <<'EOF'
sovereign_os_build_step_sign_total{profile="sain-01",posture="signed",result="fail"} 1
EOF
cat > "${mdir}/sovereign-os-peri.prom" <<'EOF'
sovereign_os_perimeter_status 0
EOF
cat > "${mdir}/sovereign-os-sec.prom" <<'EOF'
sovereign_os_security_updates_available 5
EOF

# ----- DRY-RUN path ----------
set +e
out="$(SOVEREIGN_OS_METRICS_DIR="${mdir}" \
       SOVEREIGN_OS_ALERTS_STATE_FILE="${state_dir}/alerts.json" \
       SOVEREIGN_OS_DRY_RUN=1 "${HOOK}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "DRY-RUN — would run" <<< "${out}"; then
  ok "DRY-RUN exits 0 with explanatory output"
else
  ko "DRY-RUN gate broken (rc=${rc})"
fi
if [ ! -f "${state_dir}/alerts.json" ]; then
  ok "DRY-RUN does NOT write alerts.json"
else
  ko "DRY-RUN incorrectly persisted state"
fi

# ----- live path with seeded alerts ----------
set +e
out="$(SOVEREIGN_OS_METRICS_DIR="${mdir}" \
       SOVEREIGN_OS_ALERTS_STATE_FILE="${state_dir}/alerts.json" \
       SOVEREIGN_OS_OSCTL="${OSCTL}" \
       "${HOOK}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ]; then
  ok "live run exits 0 (hook never fails on alert presence)"
else
  ko "live run exit broken (rc=${rc})"
fi
if grep -q "ALERT count: 2" <<< "${out}"; then
  ok "tallies 2 ALERTs (failing build step + Tetragon inactive)"
else
  ko "ALERT count wrong; output: ${out}"
fi
if grep -q "WARN  count: 1" <<< "${out}"; then
  ok "tallies 1 WARN (pending security updates)"
else
  ko "WARN count wrong"
fi

# Check .prom was written
prom="${mdir}/sovereign-os-alerts-check.prom"
if [ -f "${prom}" ]; then
  ok ".prom emitted: $(basename "${prom}")"
else
  ko ".prom NOT emitted"
fi
if [ -f "${prom}" ] && grep -q 'sovereign_os_meta_alert_count{level="ALERT"} 2' "${prom}"; then
  ok ".prom contains correct ALERT counter (2)"
else
  ko ".prom ALERT line wrong"
fi
if [ -f "${prom}" ] && grep -q 'sovereign_os_meta_alert_count{level="WARN"} 1' "${prom}"; then
  ok ".prom contains correct WARN counter (1)"
else
  ko ".prom WARN line wrong"
fi
if [ -f "${prom}" ] && grep -q 'sovereign_os_meta_alerts_check_last_run_timestamp' "${prom}"; then
  ok ".prom contains last_run_timestamp"
else
  ko "timestamp metric missing"
fi

# alerts.json was persisted
if [ -f "${state_dir}/alerts.json" ]; then
  ok "alerts.json persisted to state dir"
else
  ko "alerts.json NOT persisted"
fi
# It's valid JSON array with entries
if [ -f "${state_dir}/alerts.json" ] && python3 -c "import json,sys; a=json.load(sys.stdin); assert isinstance(a,list) and len(a) == 3" < "${state_dir}/alerts.json"; then
  ok "alerts.json is valid JSON with 3 entries (2 ALERT + 1 WARN)"
else
  ko "alerts.json malformed"
fi

# ----- live path with NO triggering conditions → 0/0 ----------
clean_mdir="${tmp}/clean_mdir"; mkdir -p "${clean_mdir}"
cat > "${clean_mdir}/sovereign-os-clean.prom" <<'EOF'
sovereign_os_build_step_render_total{profile="sain-01",result="success"} 1
sovereign_os_perimeter_status 1
EOF

clean_state="${tmp}/clean_state"; mkdir -p "${clean_state}"

set +e
out="$(SOVEREIGN_OS_METRICS_DIR="${clean_mdir}" \
       SOVEREIGN_OS_ALERTS_STATE_FILE="${clean_state}/alerts.json" \
       SOVEREIGN_OS_OSCTL="${OSCTL}" \
       "${HOOK}" 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "ALERT count: 0" <<< "${out}" && grep -q "WARN  count: 0" <<< "${out}"; then
  ok "clean .prom dir → 0/0 counters (zero is emitted, not omitted)"
else
  ko "clean-dir tally broken"
fi
# zero counters STILL emitted to .prom
if [ -f "${clean_mdir}/sovereign-os-alerts-check.prom" ] && \
   grep -q 'sovereign_os_meta_alert_count{level="ALERT"} 0' "${clean_mdir}/sovereign-os-alerts-check.prom"; then
  ok "zero-alert state still emits explicit 0 (no Prometheus blind-spot)"
else
  ko "zero-state emission broken"
fi

# ----- malformed alerts --json payloads must NOT break metric emission ----
# The hook promises "Empty or malformed → treat as no alerts (still emit
# zero counters ... never just disappears)". A valid-JSON non-list, or a
# list carrying a null/scalar element, must not crash the tally and leave a
# VALUELESS `sovereign_os_meta_alert_count{...} ` line — that is invalid
# Prometheus exposition and node_exporter rejects the whole textfile.
fake_osctl="${tmp}/fake-osctl"
cat > "${fake_osctl}" <<'EOF'
#!/usr/bin/env bash
case "$*" in
  *"alerts --json"*) printf '%s' "${MALFORMED_PAYLOAD}" ;;
  *) exit 0 ;;
esac
EOF
chmod +x "${fake_osctl}"

# Case 1: valid-JSON OBJECT (not a list) → 0/0, well-formed.
mdir_obj="${tmp}/mdir_obj"; mkdir -p "${mdir_obj}"
set +e
out="$(MALFORMED_PAYLOAD='{"alerts":[]}' \
       SOVEREIGN_OS_METRICS_DIR="${mdir_obj}" \
       SOVEREIGN_OS_ALERTS_STATE_FILE="${tmp}/obj.json" \
       SOVEREIGN_OS_OSCTL="${fake_osctl}" \
       "${HOOK}" 2>&1)"
rc=$?
set -e
prom_obj="${mdir_obj}/sovereign-os-alerts-check.prom"
if [ "${rc}" -eq 0 ] \
   && grep -q 'sovereign_os_meta_alert_count{level="ALERT"} 0' "${prom_obj}" \
   && grep -q 'sovereign_os_meta_alert_count{level="WARN"} 0' "${prom_obj}"; then
  ok "non-list payload → well-formed 0/0 counters (no crash)"
else
  ko "non-list payload broke emission (rc=${rc}); out: ${out}"
fi
# No valueless gauge line (the bug signature: a count line ending in '} ').
if grep -nE 'sovereign_os_meta_alert_count\{[^}]*\} *$' "${prom_obj}"; then
  ko "emitted a VALUELESS alert_count line (invalid Prometheus exposition)"
else
  ok "no valueless alert_count line emitted (valid exposition)"
fi

# Case 2: list with a null + a scalar alongside one real ALERT → counts 1/0.
mdir_junk="${tmp}/mdir_junk"; mkdir -p "${mdir_junk}"
set +e
out="$(MALFORMED_PAYLOAD='[{"level":"ALERT","metric":"cpu"}, null, 5]' \
       SOVEREIGN_OS_METRICS_DIR="${mdir_junk}" \
       SOVEREIGN_OS_ALERTS_STATE_FILE="${tmp}/junk.json" \
       SOVEREIGN_OS_OSCTL="${fake_osctl}" \
       "${HOOK}" 2>&1)"
rc=$?
set -e
prom_junk="${mdir_junk}/sovereign-os-alerts-check.prom"
if [ "${rc}" -eq 0 ] \
   && grep -q 'sovereign_os_meta_alert_count{level="ALERT"} 1' "${prom_junk}" \
   && grep -q 'sovereign_os_meta_alert_count{level="WARN"} 0' "${prom_junk}"; then
  ok "list with null/scalar elements → counts the real dict (1/0), skips junk"
else
  ko "list-with-junk tally broke (rc=${rc}); out: ${out}"
fi

# ----- sovereign-osctl maintenance alerts-check dispatches ----------
# Use the in-repo path via SOVEREIGN_OS_OSCTL — the subcommand dispatch
# should invoke the hook. We use DRY-RUN so we don't actually emit.
set +e
out="$(SOVEREIGN_OS_DRY_RUN=1 \
       SOVEREIGN_OS_METRICS_DIR="${mdir}" \
       "${OSCTL}" maintenance alerts-check 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "DRY-RUN — would run" <<< "${out}"; then
  ok "sovereign-osctl maintenance alerts-check dispatches to hook"
else
  ko "maintenance dispatch broken (rc=${rc})"
fi

# Help text includes the new subverb
help_out="$("${OSCTL}" help 2>&1)"
if grep -q "maintenance alerts-check" <<< "${help_out}"; then
  ok "help documents 'maintenance alerts-check'"
else
  ko "help missing maintenance alerts-check"
fi

# ----- result ----------
echo
total=$((pass + fail))
echo "test_alerts_check_hook: ${pass}/${total} passed"
if [ "${fail}" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
