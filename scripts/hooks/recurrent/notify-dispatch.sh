#!/usr/bin/env bash
# scripts/hooks/recurrent/notify-dispatch.sh — R229 (SDD-026 Z-6).
#
# Autonomous notification fan-out: run R226 health-scan, pipe its
# --json output into R228 dispatch.py, fan to operator-configured
# channels (file / webhook / ntfy). Dedup is enforced by R228 so a
# probe that stays at the same severity does NOT re-fire.
#
# R226 ships the SCAN, R228 ships the FAN-OUT, R229 closes the loop:
# this hook + the matching systemd timer make the autohealth +
# notification cycle ENTIRELY autonomous — operators are notified
# without ever touching the CLI.
#
# Operator-named (verbatim, 2026-05-17 expansion): "With scans too.
# with autohealth and doctor and analysis and event and notification
# and messaging."
#
# Honors SOVEREIGN_OS_DRY_RUN=1.
# Honors SOVEREIGN_OS_NOTIFY_CONFIG (override config path).
# Honors SOVEREIGN_OS_NOTIFY_STATE  (override dedup state path).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

STEP_ID="notify-dispatch"

log_step_header "${STEP_ID}" "R229: run R226 health-scan + fan to R228 notify channels"

if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_info "DRY-RUN — would invoke health-scan + dispatch.py and report:"
  log_info "  events_emitted   <count>    (R228 dedup applied)"
  log_info "  deliveries       <per-channel ok/fail>"
  exit 0
fi

scan_bin="${__REPO_ROOT}/scripts/hardware/health-scan.py"
dispatch_bin="${__REPO_ROOT}/scripts/notify/dispatch.py"

if [ ! -x "${scan_bin}" ]; then
  log_error "missing ${scan_bin} — R226 health-scan absent"
  exit 1
fi
if [ ! -x "${dispatch_bin}" ]; then
  log_error "missing ${dispatch_bin} — R228 notify dispatcher absent"
  exit 1
fi

# Capture the scan JSON to a tempfile + hand it to dispatch via
# --from-file so we run health-scan exactly ONCE per cycle (the
# dispatcher could shell out itself, but we want one canonical
# payload + audit trail).
scan_json="$(mktemp -t r229-scan.XXXXXX.json)"
trap 'rm -f "${scan_json}"' EXIT

# health-scan exits 1 when needs_attention=true — that's a signal,
# not a failure. Suppress both `set -e` AND the common.sh ERR trap
# by wrapping in `|| rc=...` (the ERR trap only fires on uncaught
# non-zero, so this pattern is silent for the signal case).
scan_rc=0
python3 "${scan_bin}" --json > "${scan_json}" 2>/dev/null || scan_rc=$?

if [ "${scan_rc}" -ne 0 ] && [ "${scan_rc}" -ne 1 ]; then
  log_error "health-scan failed rc=${scan_rc} — aborting fan-out"
  exit 1
fi

log_info "  health-scan rc=${scan_rc} (0=ok, 1=needs_attention)"

# dispatch returns 0 when delivery succeeded (or was a no-op);
# 1 when at least one channel failed. Same suppression trick.
dispatch_rc=0
dispatch_out="$(python3 "${dispatch_bin}" dispatch \
  --from-file "${scan_json}" --json 2>&1)" || dispatch_rc=$?

if ! python3 -c "import json,sys; json.loads(sys.stdin.read())" \
     <<< "${dispatch_out}" >/dev/null 2>&1; then
  log_error "dispatch did not emit JSON (rc=${dispatch_rc}): ${dispatch_out}"
  exit 1
fi

# Extract operator-readable summary from dispatch JSON.
summary="$(DISPATCH_JSON="${dispatch_out}" python3 -c '
import json, os
d = json.loads(os.environ["DISPATCH_JSON"])
events = d.get("events_emitted", 0)
deliveries = d.get("deliveries", []) or []
ok = sum(1 for x in deliveries if x.get("ok"))
fail = sum(1 for x in deliveries if not x.get("ok"))
chans = ",".join(x["channel"] for x in deliveries) or "(none)"
print(f"events={events} channels={chans} delivered_ok={ok} delivered_fail={fail}")
')"

log_info "  dispatch rc=${dispatch_rc} ${summary}"

# SDD-016 Layer B metric emission — fleet-aggregate "how chatty are
# my notifications" + "do channels deliver". Reads back from the
# dispatch JSON so we get the same numbers the operator sees.
events_count="$(DISPATCH_JSON="${dispatch_out}" python3 -c '
import json, os
print(json.loads(os.environ["DISPATCH_JSON"]).get("events_emitted", 0))
')"
delivered_ok="$(DISPATCH_JSON="${dispatch_out}" python3 -c '
import json, os
d = json.loads(os.environ["DISPATCH_JSON"]).get("deliveries", []) or []
print(sum(1 for x in d if x.get("ok")))
')"
delivered_fail="$(DISPATCH_JSON="${dispatch_out}" python3 -c '
import json, os
d = json.loads(os.environ["DISPATCH_JSON"]).get("deliveries", []) or []
print(sum(1 for x in d if not x.get("ok")))
')"

emit_metric_set notify-dispatch \
  "sovereign_os_notify_events_emitted_total ${events_count}" \
  "sovereign_os_notify_deliveries_ok_total ${delivered_ok}" \
  "sovereign_os_notify_deliveries_fail_total ${delivered_fail}" \
  "sovereign_os_notify_last_run_timestamp $(date +%s)"

if [ "${dispatch_rc}" -ne 0 ]; then
  log_warn "at least one channel failed delivery (rc=${dispatch_rc})"
  # Exit 0 anyway — a single failing channel should NOT take the timer
  # down. The failure is visible in the dispatch JSON + journal logs +
  # the Layer B `sovereign_os_notify_deliveries_fail_total` counter.
fi

exit 0
