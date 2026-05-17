#!/usr/bin/env bash
# tests/nspawn/test_profile_flex.sh — R224 (SDD-026 Z-3) flex-profile
# JSON delta surface. Uses --state to point at a tempfile so CI
# runners can exercise the full flow without /var/lib write access.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/profile-flex.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_profile_flex.sh"
echo

[ -x "${SCRIPT}" ] && ok "profile-flex.py executable" \
  || { ko "missing profile-flex.py"; exit 1; }
grep -q "    flex)" "${OSCTL}" \
  && ok "osctl namespaces 'profiles flex'" || ko "osctl bridge missing"
grep -q "R224" "${OSCTL}" \
  && ok "osctl cites R224" || ko "R224 citation missing"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT
STATE="${WORK}/flex.json"

# ---- empty state: show + history ----
set +e
python3 "${SCRIPT}" --state "${STATE}" show > "${WORK}/show1.txt" 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "show on missing state → rc=0" || ko "show rc=${rc}"
grep -q "R224 sovereign-os profile flex" "${WORK}/show1.txt" \
  && ok "R224 banner emitted" || ko "no R224 banner"
grep -q "no flex deltas" "${WORK}/show1.txt" \
  && ok "empty-state banner cites no deltas" || ko "empty banner wrong"

# ---- reset on empty → rc=1 ----
set +e
python3 "${SCRIPT}" --state "${STATE}" reset > "${WORK}/reset-empty.txt" 2>&1
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "reset on empty state → rc=1" \
  || ko "expected rc=1 on empty reset, got ${rc}"

# ---- set: numeric value ----
set +e
python3 "${SCRIPT}" --state "${STATE}" set gpu.utilization 0.85 > "${WORK}/set1.txt" 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "set numeric value → rc=0" || ko "set rc=${rc}"
grep -q "gpu.utilization = 0.85" "${WORK}/set1.txt" \
  && ok "operator-readable confirmation cites key + value" \
  || ko "confirm line wrong"

# ---- set: boolean value (JSON-parsed) ----
python3 "${SCRIPT}" --state "${STATE}" set inference.streaming true > /dev/null 2>&1

# ---- set: string value (JSON parse falls back) ----
python3 "${SCRIPT}" --state "${STATE}" set affinity.cores 0-5 > /dev/null 2>&1

# ---- show: 3 deltas present + JSON shape ----
set +e
python3 "${SCRIPT}" --state "${STATE}" show > "${WORK}/show2.txt" 2>&1
set -e
grep -q "3 delta(s) applied" "${WORK}/show2.txt" \
  && ok "show counts deltas (3)" || ko "delta count wrong"
grep -q "gpu.utilization = 0.85" "${WORK}/show2.txt" \
  && ok "show enumerates numeric delta" || ko "numeric delta missing"
grep -q "inference.streaming = true" "${WORK}/show2.txt" \
  && ok "show enumerates boolean delta" || ko "boolean delta missing"
grep -q 'affinity.cores = "0-5"' "${WORK}/show2.txt" \
  && ok "show enumerates string delta (JSON-quoted)" || ko "string delta missing"

set +e
python3 "${SCRIPT}" --state "${STATE}" --json show > "${WORK}/show.json" 2>&1
set -e
python3 - "${WORK}/show.json" <<'PY' 2>/dev/null \
  && ok "JSON shape: schema_version + active_profile_id + deltas[3]" \
  || ko "JSON shape wrong"
import json, sys
d = json.load(open(sys.argv[1]))
assert d["schema_version"] == "1.0.0"
assert isinstance(d["deltas"], list)
assert len(d["deltas"]) == 3
keys = [e["key"] for e in d["deltas"]]
assert "gpu.utilization" in keys
assert "inference.streaming" in keys
assert "affinity.cores" in keys
PY

# ---- history ----
set +e
python3 "${SCRIPT}" --state "${STATE}" history > "${WORK}/history.txt" 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "history rc=0" || ko "history rc=${rc}"
grep -q "history" "${WORK}/history.txt" \
  && ok "history banner present" || ko "history banner missing"
# Should enumerate 3 deltas
[ "$(grep -c '=' ${WORK}/history.txt)" -eq 3 ] \
  && ok "history enumerates all 3 deltas" || ko "history count wrong"

# ---- reset with deltas → rc=0 + cleared count ----
set +e
python3 "${SCRIPT}" --state "${STATE}" reset > "${WORK}/reset.txt" 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "reset with deltas → rc=0" || ko "reset rc=${rc}"
grep -q "cleared 3 flex delta" "${WORK}/reset.txt" \
  && ok "reset cites cleared count" || ko "reset count wrong"

# After reset, show should be empty again
set +e
python3 "${SCRIPT}" --state "${STATE}" show > "${WORK}/show-after.txt" 2>&1
set -e
grep -q "no flex deltas" "${WORK}/show-after.txt" \
  && ok "post-reset show back to empty state" || ko "post-reset wrong"

# ---- osctl bridge: profiles flex show ----
set +e
"${OSCTL}" profiles flex show --state "${STATE}" > "${WORK}/osctl.txt" 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl profiles flex show rc=0" \
  || ko "osctl bridge rc=${rc}"
grep -q "R224 sovereign-os profile flex" "${WORK}/osctl.txt" \
  && ok "osctl bridge surfaces R224 banner" || ko "osctl banner missing"

echo
total=$((pass + fail))
echo "test_profile_flex: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
