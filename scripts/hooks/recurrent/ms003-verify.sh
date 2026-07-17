#!/usr/bin/env bash
# scripts/hooks/recurrent/ms003-verify.sh
#
# Daily MS003 ledger-integrity sweep (F-2026-034 verifier half). Walks the
# durable decision/mutation ledgers under /var/lib/sovereign-os, verifies
# every signed record against the operator trust-anchor store
# (/etc/sovereign-os/ms003-trust-anchors/), and makes the result LOUD:
# Layer-B gauges per status + a forensic security_audit.log line on any
# invalid signature / unknown signer. Mirrors tetragon-policy-verify.sh.
#
# unsigned-placeholder records are EXPECTED on a keyless node (documented
# graceful degradation, SDD-989) — they gauge as a count, and only flip
# status to 0 when an operator key IS provisioned (records should be
# signed on such a node; unsigned-with-key-present means signing failures
# or pre-key history the operator should see).

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

: "${SOVEREIGN_OS_MS003_SWEEP_ROOT:=/var/lib/sovereign-os}"
: "${SOVEREIGN_OS_AUDIT_LOG:=/mnt/vault/context/security_audit.log}"

log_step_header "ms003-verify" "verify MS003 ledger signatures"

MS003_PY="${__REPO_ROOT}/scripts/lib/ms003.py"
if [ ! -f "${MS003_PY}" ]; then
  log_error "ms003.py not found at ${MS003_PY}"
  exit 1
fi

# One python pass: sweep + emit counts as shell assignments.
eval "$(python3 - "${MS003_PY}" "${SOVEREIGN_OS_MS003_SWEEP_ROOT}" <<'PY'
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("ms003", sys.argv[1])
ms003 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ms003)
c = ms003.sweep(Path(sys.argv[2]))
key_loaded = 1 if ms003._have_key() else 0
print(f"MS003_FILES={c['files']}")
print(f"MS003_UNREADABLE={c['unreadable']}")
print(f"MS003_VERIFIED={c['verified']}")
print(f"MS003_UNSIGNED={c['unsigned-placeholder']}")
print(f"MS003_NO_SIG_FIELD={c['no-signature-field']}")
print(f"MS003_UNKNOWN_KEYID={c['unknown-keyid']}")
print(f"MS003_INVALID={c['invalid-signature']}")
print(f"MS003_KEY_LOADED={key_loaded}")
PY
)"

log_info "swept ${MS003_FILES} ledger file(s) under ${SOVEREIGN_OS_MS003_SWEEP_ROOT}"
log_info "  verified=${MS003_VERIFIED} unsigned=${MS003_UNSIGNED} unknown-keyid=${MS003_UNKNOWN_KEYID} invalid=${MS003_INVALID}"

# Healthy = no tampered records, no untrusted signers, and (when the
# operator key is provisioned) no unsigned placeholders accumulating.
healthy=1
if [ "${MS003_INVALID}" -gt 0 ] || [ "${MS003_UNKNOWN_KEYID}" -gt 0 ]; then
  healthy=0
  log_error "MS003 INTEGRITY FAILURE: invalid=${MS003_INVALID} unknown-keyid=${MS003_UNKNOWN_KEYID}"
  echo "$(date -u --iso-8601=seconds) MS003_INTEGRITY invalid=${MS003_INVALID} unknown_keyid=${MS003_UNKNOWN_KEYID} root=${SOVEREIGN_OS_MS003_SWEEP_ROOT}" \
    >> "${SOVEREIGN_OS_AUDIT_LOG}" 2>/dev/null || true
elif [ "${MS003_KEY_LOADED}" = "1" ] && [ "${MS003_UNSIGNED}" -gt 0 ]; then
  healthy=0
  log_warn "operator key loaded but ${MS003_UNSIGNED} record(s) carry the unsigned-pending-MS003 placeholder"
fi

emit_metric_set ms003 \
  '# HELP sovereign_os_ms003_ledger_status MS003 ledger integrity (1=healthy, 0=invalid/unknown-signer/unsigned-with-key)' \
  '# TYPE sovereign_os_ms003_ledger_status gauge' \
  "sovereign_os_ms003_ledger_status ${healthy}" \
  '# HELP sovereign_os_ms003_records Records seen by the last sweep, per verification status' \
  '# TYPE sovereign_os_ms003_records gauge' \
  "sovereign_os_ms003_records{status=\"verified\"} ${MS003_VERIFIED}" \
  "sovereign_os_ms003_records{status=\"unsigned-placeholder\"} ${MS003_UNSIGNED}" \
  "sovereign_os_ms003_records{status=\"unknown-keyid\"} ${MS003_UNKNOWN_KEYID}" \
  "sovereign_os_ms003_records{status=\"invalid-signature\"} ${MS003_INVALID}" \
  '# HELP sovereign_os_ms003_key_loaded Operator MS003 signing key presence (1=loaded)' \
  '# TYPE sovereign_os_ms003_key_loaded gauge' \
  "sovereign_os_ms003_key_loaded ${MS003_KEY_LOADED}" \
  '# HELP sovereign_os_ms003_verify_last_run_timestamp Unix timestamp of last verifier run' \
  '# TYPE sovereign_os_ms003_verify_last_run_timestamp gauge' \
  "sovereign_os_ms003_verify_last_run_timestamp $(date +%s)"

if [ "${healthy}" = "0" ] && { [ "${MS003_INVALID}" -gt 0 ] || [ "${MS003_UNKNOWN_KEYID}" -gt 0 ]; }; then
  exit 1
fi
log_info "ms003-verify complete (status=${healthy})"
