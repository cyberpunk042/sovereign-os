#!/usr/bin/env bash
# tests/nspawn/test_fs_insights.sh — R222 (SDD-026 Z-10) fs + log
# insights. Read-only; uses a fixture log dir + a 0% threshold for
# deterministic flagged-state assertions.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/fs-insights.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_fs_insights.sh"
echo

[ -x "${SCRIPT}" ] && ok "fs-insights.py executable" \
  || { ko "missing fs-insights.py"; exit 1; }
grep -q "^  fs)" "${OSCTL}" \
  && ok "osctl bridges 'fs'" || ko "osctl bridge missing"
grep -q "R222" "${OSCTL}" \
  && ok "osctl cites R222" || ko "R222 citation missing"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

# ---- usage: human banner + global summary ----
set +e
python3 "${SCRIPT}" usage --threshold-pct 100 > "${WORK}/usage.txt" 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "usage rc=0 with high threshold (no flagging)" \
  || ko "usage rc=${rc} unexpected"
grep -q "R222 sovereign-os fs-insights: usage" "${WORK}/usage.txt" \
  && ok "usage banner cites R222" || ko "no R222 banner"
grep -q "global:" "${WORK}/usage.txt" \
  && ok "usage emits global summary line" || ko "no global summary"
grep -qE "use% +used +total +mount" "${WORK}/usage.txt" \
  && ok "usage table header correct" || ko "header missing"

# ---- usage: forces flagging via threshold=0 → rc=1 ----
set +e
python3 "${SCRIPT}" usage --threshold-pct 0 > "${WORK}/usage-flag.txt" 2>&1
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "usage rc=1 when threshold flags partition" \
  || ko "expected rc=1 on flagged, got ${rc}"
grep -q "partition(s) ≥ 0%" "${WORK}/usage-flag.txt" \
  && ok "flagged-count banner present" || ko "no flagged-count banner"

# ---- usage --json shape ----
set +e
python3 "${SCRIPT}" usage --threshold-pct 100 --json > "${WORK}/usage.json" 2>&1
set -e
python3 - "${WORK}/usage.json" <<'PY' 2>/dev/null \
  && ok "usage --json shape: partitions[] + global_* fields" \
  || ko "usage --json shape wrong"
import json, sys
d = json.load(open(sys.argv[1]))
assert isinstance(d["partitions"], list)
assert "global_total_bytes" in d
assert "global_used_bytes" in d
assert "global_use_pct" in d
assert d["threshold_pct"] == 100
PY

# ---- log-audit: fixture dir with controlled files ----
mkdir -p "${WORK}/logs"
# 100 B file — under default threshold but used for flagging at small thresh
dd if=/dev/zero of="${WORK}/logs/small.log" bs=1 count=100 2>/dev/null
# 1 MiB file — large enough to flag at small thresholds
dd if=/dev/zero of="${WORK}/logs/big.log" bs=1024 count=1024 2>/dev/null

set +e
python3 "${SCRIPT}" log-audit --root "${WORK}/logs" \
  --threshold-bytes 1024 > "${WORK}/audit.txt" 2>&1
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "log-audit rc=1 when oversized file flagged" \
  || ko "expected rc=1, got ${rc}"
grep -q "R222 sovereign-os fs-insights: log-audit" "${WORK}/audit.txt" \
  && ok "log-audit banner cites R222" || ko "no banner"
grep -q "big.log" "${WORK}/audit.txt" \
  && ok "big.log enumerated" || ko "big.log missing"
grep -q "small.log" "${WORK}/audit.txt" \
  && ok "small.log also enumerated (informational)" || ko "small.log missing"
grep -q "add to /etc/logrotate.d/" "${WORK}/audit.txt" \
  && ok "operator-actionable logrotate hint surfaced" \
  || ko "logrotate hint missing"

# ---- log-audit: empty dir is clean ----
mkdir -p "${WORK}/empty-logs"
set +e
python3 "${SCRIPT}" log-audit --root "${WORK}/empty-logs" > "${WORK}/empty.txt" 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "log-audit rc=0 on empty dir" \
  || ko "empty-dir log-audit rc=${rc}"
grep -q "no log files found" "${WORK}/empty.txt" \
  && ok "empty-dir banner cites no files" \
  || ko "empty-dir banner wrong"

# ---- log-audit --json shape ----
set +e
python3 "${SCRIPT}" log-audit --root "${WORK}/logs" --threshold-bytes 1024 \
  --json > "${WORK}/audit.json" 2>&1
set -e
python3 - "${WORK}/audit.json" <<'PY' 2>/dev/null \
  && ok "log-audit --json shape: files[] + flagged_count + log_roots" \
  || ko "log-audit --json shape wrong"
import json, sys
d = json.load(open(sys.argv[1]))
assert isinstance(d["files"], list)
assert d["flagged_count"] >= 1
assert d["threshold_bytes"] == 1024
assert len(d["log_roots"]) == 1
PY

# ---- osctl bridges ----
set +e
"${OSCTL}" fs usage --threshold-pct 100 > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl fs usage rc=0" || ko "osctl bridge fs usage rc=${rc}"
set +e
"${OSCTL}" fs log-audit --root "${WORK}/logs" --threshold-bytes 1024 > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "osctl fs log-audit propagates rc=1" \
  || ko "osctl bridge fs log-audit rc=${rc}"

echo
total=$((pass + fail))
echo "test_fs_insights: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
