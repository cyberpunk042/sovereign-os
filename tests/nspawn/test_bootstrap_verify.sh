#!/usr/bin/env bash
# tests/nspawn/test_bootstrap_verify.sh
#
# Layer 3 test for R159 — scripts/bootstrap/verify.sh +
# sovereign-osctl bootstrap verb (master spec § 22 6-check checklist).

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"

fail=0
pass=0
ok() { echo "  PASS — $1"; pass=$((pass + 1)); }
ko() { echo "  FAIL — $1"; fail=$((fail + 1)); }

SCRIPT="${__REPO_ROOT}/scripts/bootstrap/verify.sh"
OSCTL="${__REPO_ROOT}/scripts/sovereign-osctl"

echo "tests/nspawn/test_bootstrap_verify.sh"
echo

[ -x "${SCRIPT}" ] && ok "verify.sh executable" || { ko "missing"; exit 1; }
[ -x "${OSCTL}" ]  && ok "sovereign-osctl executable" || ko "osctl missing"

# ---------- master spec citation ----------
if grep -q "master spec § 22" "${SCRIPT}"; then
  ok "verify.sh cites master spec § 22"
else
  ko "master spec § 22 citation missing"
fi

# All 6 checks named verbatim from the master spec § 22 table
for kw in "Microcode" "Bus Geometry" "ZFS ARC" "NVIDIA" "Tetragon" "MTU"; do
  if grep -q "${kw}" "${SCRIPT}"; then
    ok "check enumerates: ${kw}"
  else
    ko "check missing: ${kw}"
  fi
done
# Verbatim master spec § 22 target values
if grep -q "avx512_vnni" "${SCRIPT}" && grep -q "avx512_bf16" "${SCRIPT}"; then
  ok "check 01 references verbatim avx512_vnni + avx512_bf16"
else
  ko "check 01 ISA targets missing"
fi
if grep -q "137438953472" "${SCRIPT}"; then
  ok "check 03 references verbatim ARC max (137438953472 bytes = 128 GiB)"
else
  ko "check 03 ARC value missing"
fi
if grep -q "tetragon.events" "${SCRIPT}"; then
  ok "check 05 references verbatim /var/run/tetragon/tetragon.events"
else
  ko "check 05 socket path missing"
fi
if grep -q "enp5s0" "${SCRIPT}"; then
  ok "check 06 references verbatim enp5s0 (master spec § 8.1 data iface)"
else
  ko "check 06 iface missing"
fi

# ---------- script runs, produces 6 result lines ----------
set +e
out="$(bash "${SCRIPT}" 2>&1)"
rc=$?
set -e
for id in "01" "02" "03" "04" "05" "06"; do
  if grep -qE "^  ${id} " <<< "${out}"; then
    ok "output row for check ${id}"
  else
    ko "missing row for check ${id}"
  fi
done
if grep -q "Summary:" <<< "${out}"; then
  ok "output contains Summary line"
else
  ko "Summary line missing"
fi

# ---------- --only filter ----------
set +e
out="$(bash "${SCRIPT}" --only 02,05 2>&1)"
rc=$?
set -e
# Both 02 and 05 lines exist (run); others say "not in --only list"
if grep -qE "^  01 .*not in --only list" <<< "${out}"; then
  ok "--only excludes 01 (not in list message)"
else
  ko "--only filter broken for 01"
fi
if grep -qE "^  03 .*not in --only list" <<< "${out}"; then
  ok "--only excludes 03 (not in list message)"
else
  ko "--only filter broken for 03"
fi
if grep -qE "^  02 " <<< "${out}" && ! grep -qE "^  02 .*not in --only" <<< "${out}"; then
  ok "--only includes 02 (real result)"
else
  ko "--only didn't run check 02"
fi

# ---------- --json output ----------
set +e
out="$(bash "${SCRIPT}" --json --only 01 2>&1)"
rc=$?
set -e
if grep -q '"summary"' <<< "${out}" && grep -q '"lock_state"' <<< "${out}"; then
  ok "--json emits summary + lock_state field"
else
  ko "--json output broken"
fi
# JSON parseable
json_block="$(awk '/^{/,/^}/' <<< "${out}")"
if [ -n "${json_block}" ] && python3 -c "import json,sys; json.loads('''${json_block}''')" 2>/dev/null; then
  ok "--json output is valid JSON"
else
  ko "--json output failed JSON parse"
fi

# ---------- --strict mode promotes SKIP to FAIL ----------
# Use --only 02 which will definitely be SKIP in nspawn (no lspci usually,
# or no LnkSta). Even if lspci is installed, it won't see x8 slots.
# Pick a check guaranteed to SKIP: check 04 (modinfo) is usually absent
# OR returns SKIP. Let's force via --only 05 (no tetragon).
set +e
out="$(bash "${SCRIPT}" --only 05 2>&1)"
non_strict_rc=$?
out2="$(BOOTSTRAP_VERIFY_STRICT=1 bash "${SCRIPT}" --only 05 2>&1)"
strict_rc=$?
set -e
# Check 05: tetragon dir absent → SKIP
if grep -qE "^  05 .*(SKIP|tetragon not installed)" <<< "${out}"; then
  ok "check 05 SKIPs cleanly when tetragon absent (non-strict)"
else
  ko "check 05 behavior unexpected in non-strict mode"
fi
if [ "${non_strict_rc}" -eq 0 ] && [ "${strict_rc}" -ne 0 ]; then
  ok "--strict promotes SKIP→FAIL (rc: ${non_strict_rc}→${strict_rc})"
else
  ko "--strict promotion not working (non=${non_strict_rc} strict=${strict_rc})"
fi

# ---------- network check with controllable iface ----------
# Find an actual iface on this host to test the data-iface override.
set +e
real_iface="$(ip -o link show 2>/dev/null | awk -F': ' '{print $2}' | grep -v lo | head -1 | cut -d@ -f1)"
set -e
if [ -n "${real_iface}" ]; then
  current_mtu="$(ip link show "${real_iface}" 2>/dev/null | awk '/mtu /{for(i=1;i<=NF;i++)if($i=="mtu")print $(i+1);exit}')"
  set +e
  out="$(BOOTSTRAP_VERIFY_DATA_IFACE="${real_iface}" bash "${SCRIPT}" --only 06 2>&1)"
  rc=$?
  set -e
  if [ "${current_mtu}" = "9000" ]; then
    grep -qE "^  06 .*PASS" <<< "${out}" && ok "check 06 PASS on iface=${real_iface} mtu=9000" || ko "check 06 should PASS"
  else
    grep -qE "^  06 .*FAIL" <<< "${out}" && ok "check 06 FAIL when iface MTU != 9000 (actual=${current_mtu})" || ko "check 06 should FAIL when mtu wrong"
  fi
else
  ok "skipping iface test — no usable iface present"
fi

# ---------- iface absent → SKIP ----------
set +e
out="$(BOOTSTRAP_VERIFY_DATA_IFACE=no-such-iface-9999 bash "${SCRIPT}" --only 06 2>&1)"
rc=$?
set -e
if grep -qE "^  06 .*(SKIP|not present)" <<< "${out}"; then
  ok "check 06 SKIPs when iface absent"
else
  ko "check 06 should SKIP when iface absent"
fi

# ---------- master-spec lock-state message on FAIL ----------
# Force a FAIL by setting an absurd ARC max expectation. Then run with
# only 03 — should SKIP because ZFS not loaded in container. So instead
# force a FAIL via check 01 only if avx512 missing.
# Simpler: use --strict on a definitely-skip check.
set +e
out="$(BOOTSTRAP_VERIFY_STRICT=1 bash "${SCRIPT}" --only 04 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 1 ] && grep -q "MASTER SPEC § 22 LOCK-STATE" <<< "${out}"; then
  ok "lock-state message surfaces on FAIL"
else
  ko "lock-state message missing"
fi

# ---------- sovereign-osctl bootstrap wrapper ----------
set +e
out="$("${OSCTL}" bootstrap help 2>&1)"
rc=$?
set -e
if [ "${rc}" -eq 0 ] && grep -q "master spec § 22" <<< "${out}"; then
  ok "sovereign-osctl bootstrap help cites master spec § 22"
else
  ko "osctl help broken (rc=${rc})"
fi

set +e
out="$("${OSCTL}" bootstrap verify --only 02 2>&1)"
rc=$?
set -e
if grep -qE "^  02 " <<< "${out}"; then
  ok "sovereign-osctl bootstrap verify executes the script"
else
  ko "osctl verify dispatch broken"
fi

# Unknown subverb
set +e
out="$("${OSCTL}" bootstrap nope 2>&1)"
rc=$?
set -e
if [ "${rc}" -ne 0 ]; then
  ok "osctl bootstrap unknown subverb → rc≠0"
else
  ko "osctl unknown subverb didn't fail"
fi

echo
total=$((pass + fail))
echo "test_bootstrap_verify: ${pass}/${total} passed"
[ "${fail}" -eq 0 ] && { echo "PASS"; exit 0; } || { echo "FAIL"; exit 1; }
