#!/usr/bin/env bash
# tests/nspawn/test_raid_status.sh — R223 (SDD-026 Z-9) software RAID
# read-only surface. Drives the script with synthetic /proc/mdstat
# fixtures because CI runners have no md arrays.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/hardware/raid-status.py"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_raid_status.sh"
echo

[ -x "${SCRIPT}" ] && ok "raid-status.py executable" \
  || { ko "missing raid-status.py"; exit 1; }
grep -q "^  raid)" "${OSCTL}" \
  && ok "osctl bridges 'raid'" || ko "osctl bridge missing"
grep -q "R223" "${OSCTL}" \
  && ok "osctl cites R223" || ko "R223 citation missing"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

# ---- Empty /proc/mdstat (no arrays present) ----
cat > "${WORK}/mdstat-empty" <<'EOF'
Personalities :
unused devices: <none>
EOF
set +e
python3 "${SCRIPT}" status --mdstat-path "${WORK}/mdstat-empty" > "${WORK}/empty.txt" 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "empty mdstat → rc=0 (no arrays = healthy)" \
  || ko "empty rc=${rc}"
grep -q "no md arrays present" "${WORK}/empty.txt" \
  && ok "empty banner cites 'no arrays'" || ko "wrong empty banner"

# ---- All-healthy 2-array fixture ----
cat > "${WORK}/mdstat-healthy" <<'EOF'
Personalities : [raid1] [raid0] [linear]
md0 : active raid1 sda1[0] sdb1[1]
      487168 blocks super 1.2 [2/2] [UU]

md1 : active raid0 sdc1[0] sdd1[1]
      1953382400 blocks super 1.2

unused devices: <none>
EOF
set +e
python3 "${SCRIPT}" status --mdstat-path "${WORK}/mdstat-healthy" > "${WORK}/healthy.txt" 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "all-healthy fixture → rc=0" \
  || ko "expected rc=0 on healthy, got ${rc}"
grep -q "R223 sovereign-os raid status" "${WORK}/healthy.txt" \
  && ok "R223 banner emitted" || ko "no R223 banner"
grep -q "md0" "${WORK}/healthy.txt" \
  && ok "md0 array enumerated" || ko "md0 missing"
grep -q "md1" "${WORK}/healthy.txt" \
  && ok "md1 array enumerated" || ko "md1 missing"
grep -q "health=ok" "${WORK}/healthy.txt" \
  && ok "healthy array marked ok" || ko "health line wrong"

# ---- Degraded fixture (slot map carries _) ----
cat > "${WORK}/mdstat-degraded" <<'EOF'
Personalities : [raid1]
md0 : active raid1 sda1[0] sdb1[1]
      1953382400 blocks super 1.2 [2/1] [_U]
      bitmap: 12/15 pages [48KB], 65536KB chunk

unused devices: <none>
EOF
set +e
python3 "${SCRIPT}" status --mdstat-path "${WORK}/mdstat-degraded" > "${WORK}/degraded.txt" 2>&1
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "degraded fixture → rc=1" \
  || ko "expected rc=1 on degraded, got ${rc}"
grep -q "health=degraded" "${WORK}/degraded.txt" \
  && ok "array marked degraded" || ko "degraded marker missing"

# ---- Failed-disk fixture (member tagged F) ----
cat > "${WORK}/mdstat-failed" <<'EOF'
Personalities : [raid1]
md0 : active raid1 sda1[0] sdb1[1](F)
      1953382400 blocks super 1.2 [2/1] [U_]

unused devices: <none>
EOF
set +e
python3 "${SCRIPT}" status --mdstat-path "${WORK}/mdstat-failed" > "${WORK}/failed.txt" 2>&1
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "failed-member fixture → rc=1" \
  || ko "expected rc=1 on failed, got ${rc}"
grep -q "health=failed" "${WORK}/failed.txt" \
  && ok "array marked failed" || ko "failed marker missing"
grep -q "sdb1(F)" "${WORK}/failed.txt" \
  && ok "failed member rendered with (F) flag" || ko "(F) member missing"

# ---- Rebuilding fixture (recovery line) ----
cat > "${WORK}/mdstat-rebuild" <<'EOF'
Personalities : [raid1]
md0 : active raid1 sda1[2] sdb1[1]
      1953382400 blocks super 1.2 [2/1] [_U]
      [===>.................]  recovery = 18.5% (361580160/1953382400) finish=20.0min speed=120000K/sec

unused devices: <none>
EOF
set +e
python3 "${SCRIPT}" status --mdstat-path "${WORK}/mdstat-rebuild" > "${WORK}/rebuild.txt" 2>&1
rc=$?
set -e
[ "${rc}" -eq 1 ] && ok "rebuilding fixture → rc=1" \
  || ko "expected rc=1 on rebuilding, got ${rc}"
grep -q "health=rebuilding" "${WORK}/rebuild.txt" \
  && ok "rebuilding state surfaced" || ko "rebuilding state missing"
grep -q "recovery: 18.5% complete" "${WORK}/rebuild.txt" \
  && ok "rebuild percent line cited" || ko "rebuild progress missing"

# ---- JSON shape on degraded fixture ----
set +e
python3 "${SCRIPT}" status --mdstat-path "${WORK}/mdstat-degraded" --json > "${WORK}/degraded.json" 2>&1
set -e
python3 - "${WORK}/degraded.json" <<'PY' 2>/dev/null \
  && ok "JSON: arrays[] + count + attention_needed + per-array health" \
  || ko "JSON shape wrong"
import json, sys
d = json.load(open(sys.argv[1]))
assert d["count"] == 1
assert d["attention_needed"] is True
assert d["arrays"][0]["name"] == "md0"
assert d["arrays"][0]["health"] == "degraded"
assert d["arrays"][0]["level"] == "raid1"
PY

# ---- detail: unknown array → rc=2 ----
set +e
python3 "${SCRIPT}" detail nonexistent --mdstat-path "${WORK}/mdstat-healthy" >/dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 2 ] && ok "detail on unknown array → rc=2" \
  || ko "expected rc=2 on unknown array, got ${rc}"

# ---- detail: empty fixture → rc=0 with note ----
set +e
python3 "${SCRIPT}" detail --all --mdstat-path "${WORK}/mdstat-empty" > "${WORK}/detail-empty.txt" 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "detail --all on empty fixture → rc=0" \
  || ko "detail empty rc=${rc}"

# ---- osctl bridge status default ----
set +e
"${OSCTL}" raid status > /dev/null 2>&1
rc=$?
set -e
[ "${rc}" -eq 0 ] && ok "osctl raid status (no fixture) → rc=0" \
  || ko "osctl bridge rc=${rc}"

echo
total=$((pass + fail))
echo "test_raid_status: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
