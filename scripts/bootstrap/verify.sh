#!/usr/bin/env bash
# scripts/bootstrap/verify.sh — Master Bootstrap Verification Checklist.
#
# Master spec § 22 verbatim:
#
#   "Before passing command execution over to your active development
#    workflows, the downstream agent must pass this mandatory operational
#    grid. If any check reports an anomaly, the node enters lock-state
#    until manually cleared by the Architect."
#
# 6 checks (master spec § 22 verbatim table):
#   01 — Microcode/ISA:   avx512_vnni + avx512_bf16 in /proc/cpuinfo
#   02 — Bus Geometry:    dual slots at Gen 4/5 x8 (lspci LnkSta)
#   03 — Linux Memory:    ZFS ARC max = 137438953472 bytes (128 GiB)
#   04 — Driver Fabric:   NVIDIA Open Kernel module loaded (modinfo)
#   05 — Security Core:   /var/run/tetragon/tetragon.events present
#   06 — Network Line:    enp5s0 (Marvell 10GbE) MTU 9000
#
# CLI:
#   verify.sh                        run all checks
#   verify.sh --only 01,03,06        subset
#   verify.sh --json                 machine-readable result
#
# Env vars:
#   BOOTSTRAP_VERIFY_STRICT=1        treat SKIP as FAIL (real SAIN-01 only)
#   BOOTSTRAP_VERIFY_DATA_IFACE      override the data NIC name
#                                    (default: enp5s0 per master spec § 8.1)
#   BOOTSTRAP_VERIFY_ARC_MAX_BYTES   override expected ARC max
#                                    (default: 137438953472 per master spec § 22)
#
# Layer B metrics:
#   sovereign_os_bootstrap_check_total{check,result}
#   sovereign_os_bootstrap_verify_last_run_timestamp
#
# Exit codes:
#   0 — all checks PASS (or SKIP when not in --strict mode)
#   1 — at least one FAIL → MASTER SPEC § 22 LOCK-STATE
#   2 — usage error

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/.." && pwd)"
# shellcheck source=../build/lib/common.sh
. "${__REPO_ROOT}/build/lib/common.sh" 2>/dev/null || true
# shellcheck source=../build/lib/observability.sh
. "${__REPO_ROOT}/build/lib/observability.sh" 2>/dev/null || true

type log_info >/dev/null 2>&1 || log_info() { echo "INFO  [bootstrap/verify] $*"; }
type log_warn >/dev/null 2>&1 || log_warn() { echo "WARN  [bootstrap/verify] $*"; }
type log_error >/dev/null 2>&1 || log_error() { echo "ERROR [bootstrap/verify] $*" >&2; }
type emit_metric >/dev/null 2>&1 || emit_metric() { :; }

: "${BOOTSTRAP_VERIFY_DATA_IFACE:=enp5s0}"
: "${BOOTSTRAP_VERIFY_ARC_MAX_BYTES:=137438953472}"

JSON_OUT=0
ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --json) JSON_OUT=1; shift ;;
    --only) ONLY="$2"; shift 2 ;;
    -h|--help)
      sed -n '1,30p' "${BASH_SOURCE[0]}"
      exit 0
      ;;
    *) log_error "unknown arg: $1"; exit 2 ;;
  esac
done

# ---------- check primitives ----------
declare -A RESULTS DETAILS

run_check() {
  local id="$1" target="$2" expected="$3"
  RESULTS[$id]=""
  DETAILS[$id]=""
  if [ -n "${ONLY}" ] && ! [[ ",${ONLY}," == *",${id},"* ]]; then
    RESULTS[$id]="SKIP"
    DETAILS[$id]="not in --only list"
    return
  fi
  # Caller fills RESULTS[$id] + DETAILS[$id]
  case "$id" in
    01) check_01 ;;
    02) check_02 ;;
    03) check_03 ;;
    04) check_04 ;;
    05) check_05 ;;
    06) check_06 ;;
  esac
}

# 01 — Microcode/ISA
check_01() {
  if [ ! -r /proc/cpuinfo ]; then
    RESULTS[01]="SKIP"; DETAILS[01]="no /proc/cpuinfo"; return
  fi
  local has_vnni has_bf16
  has_vnni="$(grep -m1 -E 'avx512_vnni' /proc/cpuinfo || true)"
  has_bf16="$(grep -m1 -E 'avx512_bf16' /proc/cpuinfo || true)"
  if [ -n "${has_vnni}" ] && [ -n "${has_bf16}" ]; then
    RESULTS[01]="PASS"; DETAILS[01]="avx512_vnni + avx512_bf16 present"
  else
    RESULTS[01]="FAIL"
    DETAILS[01]="missing: vnni=$([ -n "${has_vnni}" ] && echo yes || echo no), bf16=$([ -n "${has_bf16}" ] && echo yes || echo no)"
  fi
}

# 02 — Bus Geometry (dual slots Gen 4/5 x8)
check_02() {
  if ! command -v lspci >/dev/null 2>&1; then
    RESULTS[02]="SKIP"; DETAILS[02]="lspci not installed"; return
  fi
  local lnksta_lines slot_count_at_x8
  lnksta_lines="$(lspci -vvv 2>/dev/null | grep -i "LnkSta:" || true)"
  if [ -z "${lnksta_lines}" ]; then
    RESULTS[02]="SKIP"; DETAILS[02]="lspci returned no LnkSta (needs root on real hw)"; return
  fi
  slot_count_at_x8="$(grep -cE 'Width x8' <<< "${lnksta_lines}" || true)"
  if [ "${slot_count_at_x8}" -ge 2 ]; then
    local gen_lines
    gen_lines="$(grep -cE 'Speed (16|32)\.?[0-9]*GT/s' <<< "${lnksta_lines}" || true)"
    if [ "${gen_lines}" -ge 2 ]; then
      RESULTS[02]="PASS"; DETAILS[02]="${slot_count_at_x8}× x8 slots at Gen 4/5"
    else
      RESULTS[02]="FAIL"; DETAILS[02]="${slot_count_at_x8}× x8 slots but only ${gen_lines} at Gen 4/5"
    fi
  else
    RESULTS[02]="FAIL"; DETAILS[02]="only ${slot_count_at_x8} x8-width slots (master spec § 1.2 requires 2)"
  fi
}

# 03 — Linux Memory: ZFS ARC max
check_03() {
  if ! command -v arcstat >/dev/null 2>&1 && [ ! -r /proc/spl/kstat/zfs/arcstats ]; then
    RESULTS[03]="SKIP"; DETAILS[03]="ZFS not loaded (no arcstat + no arcstats)"
    return
  fi
  local arc_max=""
  if [ -r /proc/spl/kstat/zfs/arcstats ]; then
    arc_max="$(awk '$1 == "c_max" { print $3 }' /proc/spl/kstat/zfs/arcstats)"
  fi
  if [ -z "${arc_max}" ] && command -v arcstat >/dev/null 2>&1; then
    arc_max="$(arcstat -s c 2>/dev/null | tail -1 | awk '{print $1}')"
  fi
  if [ -z "${arc_max}" ]; then
    RESULTS[03]="SKIP"; DETAILS[03]="could not read arc c_max"; return
  fi
  if [ "${arc_max}" = "${BOOTSTRAP_VERIFY_ARC_MAX_BYTES}" ]; then
    RESULTS[03]="PASS"; DETAILS[03]="arc c_max = ${arc_max} (= 128 GiB target)"
  else
    RESULTS[03]="FAIL"; DETAILS[03]="arc c_max = ${arc_max}, expected ${BOOTSTRAP_VERIFY_ARC_MAX_BYTES}"
  fi
}

# 04 — NVIDIA open-kernel module
check_04() {
  if ! command -v modinfo >/dev/null 2>&1; then
    RESULTS[04]="SKIP"; DETAILS[04]="modinfo not installed"; return
  fi
  if ! modinfo nvidia >/dev/null 2>&1; then
    RESULTS[04]="SKIP"; DETAILS[04]="nvidia kernel module not loaded"; return
  fi
  local license version
  license="$(modinfo nvidia 2>/dev/null | awk -F: '/^license:/ {gsub(/^ +/,"",$2); print $2; exit}')"
  version="$(modinfo nvidia 2>/dev/null | awk -F: '/^version:/ {gsub(/^ +/,"",$2); print $2; exit}')"
  # Master spec § 22 calls for the OPEN module (license: "MIT" or "GPL") not the proprietary closed binary.
  case "${license}" in
    MIT|GPL*|"Dual MIT/GPL")
      RESULTS[04]="PASS"; DETAILS[04]="nvidia ${version} (license=${license})"
      ;;
    NVIDIA*)
      RESULTS[04]="FAIL"; DETAILS[04]="nvidia ${version} but license='${license}' — master spec § 22 calls for OPEN kernel modules"
      ;;
    *)
      RESULTS[04]="FAIL"; DETAILS[04]="nvidia ${version} license='${license}' — expected MIT/GPL (open)"
      ;;
  esac
}

# 05 — Security core: Tetragon event stream
check_05() {
  if [ -S /var/run/tetragon/tetragon.events ] || \
     [ -p /var/run/tetragon/tetragon.events ] || \
     [ -f /var/run/tetragon/tetragon.events ]; then
    RESULTS[05]="PASS"; DETAILS[05]="/var/run/tetragon/tetragon.events present"
  else
    if [ ! -d /var/run/tetragon ]; then
      RESULTS[05]="SKIP"; DETAILS[05]="tetragon not installed (no /var/run/tetragon)"
    else
      RESULTS[05]="FAIL"; DETAILS[05]="tetragon dir exists but event stream missing"
    fi
  fi
}

# 06 — Network: enp5s0 MTU 9000
check_06() {
  if ! command -v ip >/dev/null 2>&1; then
    RESULTS[06]="SKIP"; DETAILS[06]="ip(8) not installed"; return
  fi
  local iface="${BOOTSTRAP_VERIFY_DATA_IFACE}"
  if ! ip link show "${iface}" >/dev/null 2>&1; then
    RESULTS[06]="SKIP"; DETAILS[06]="${iface} not present on this host"; return
  fi
  local mtu
  mtu="$(ip link show "${iface}" 2>/dev/null | awk '/mtu / {for(i=1;i<=NF;i++) if($i=="mtu") print $(i+1); exit}')"
  if [ "${mtu}" = "9000" ]; then
    RESULTS[06]="PASS"; DETAILS[06]="${iface} MTU=9000"
  else
    RESULTS[06]="FAIL"; DETAILS[06]="${iface} MTU=${mtu} (expected 9000)"
  fi
}

# ---------- run + report ----------
log_info "==== sovereign-os Master Bootstrap Verification (master spec § 22) ===="
log_info "  6-check operational grid"
log_info "  --strict mode: ${BOOTSTRAP_VERIFY_STRICT:-no}"
[ -n "${ONLY}" ] && log_info "  --only:        ${ONLY}"

for id in 01 02 03 04 05 06; do
  run_check "$id" "" ""
done

# Format
printf "\n"
printf "  %-4s %-25s %-7s %s\n" "ID" "Check" "Result" "Detail"
printf "  %-4s %-25s %-7s %s\n" "──" "─────────────────────────" "──────" "──────"
# R207: check metadata is canonicalized in config/bootstrap/verify-grid.yaml
# (SDD-028 pattern). load-verify-grid.py emits id|name|spec|checks_what.
declare -A CHECK_NAMES=()
while IFS='|' read -r _id _name _spec _what; do
  [ -z "${_id}" ] && continue
  CHECK_NAMES[${_id}]="${_name}"
done < <(python3 "${__SCRIPT_DIR}/lib/load-verify-grid.py" 2>/dev/null || true)
unset _id _name _spec _what
# Fallback if YAML loader unavailable — keeps the script defensive.
if [ "${#CHECK_NAMES[@]}" -eq 0 ]; then
  CHECK_NAMES[01]="Microcode / ISA"
  CHECK_NAMES[02]="Bus Geometry"
  CHECK_NAMES[03]="Linux Memory (ZFS ARC)"
  CHECK_NAMES[04]="Driver Fabric (NVIDIA)"
  CHECK_NAMES[05]="Security Core (Tetragon)"
  CHECK_NAMES[06]="Network Line (Jumbo MTU)"
fi
fail_count=0
skip_count=0
pass_count=0
for id in 01 02 03 04 05 06; do
  res="${RESULTS[$id]}"
  case "${res}" in
    PASS) pass_count=$((pass_count + 1)); marker="✓" ;;
    FAIL) fail_count=$((fail_count + 1)); marker="✗" ;;
    SKIP) skip_count=$((skip_count + 1)); marker="—" ;;
    # An indeterminate result (a check that didn't set PASS/FAIL/SKIP — e.g. a
    # future check-function bug) is an ANOMALY. Master spec §22: "if any check
    # reports an anomaly, the node enters lock-state" — fail-safe, count it as a
    # FAIL rather than letting an unknown result silently pass the gate.
    *)    fail_count=$((fail_count + 1)); marker="?"
          DETAILS[$id]="indeterminate result '${res}' — treated as FAIL (fail-safe)" ;;
  esac
  printf "  %-4s %-25s %s %-5s %s\n" "${id}" "${CHECK_NAMES[$id]}" "${marker}" "${res}" "${DETAILS[$id]}"
  emit_metric sovereign_os_bootstrap_check_total 1 \
    "check=\"${id}\",result=\"${res}\""
done

emit_metric sovereign_os_bootstrap_verify_last_run_timestamp \
  "$(date +%s)" ""

printf "\n  Summary: %d PASS · %d SKIP · %d FAIL\n" \
  "${pass_count}" "${skip_count}" "${fail_count}"

# Strict mode promotes SKIP to FAIL
if [ -n "${BOOTSTRAP_VERIFY_STRICT:-}" ] && [ "${skip_count}" -gt 0 ]; then
  log_warn "  --strict mode: ${skip_count} SKIP(s) promoted to FAIL"
  fail_count=$((fail_count + skip_count))
fi

# JSON mode emits machine-readable summary on top of human output
if [ "${JSON_OUT}" -eq 1 ]; then
  printf "\n--- JSON ---\n"
  python3 - <<PYEOF
import json
results = {
$(for id in 01 02 03 04 05 06; do printf "  '%s': {'result': '%s', 'detail': %s},\n" "${id}" "${RESULTS[$id]}" "$(python3 -c "import json; print(json.dumps('''${DETAILS[$id]}'''))")"; done)
}
summary = {
    "pass": ${pass_count},
    "skip": ${skip_count},
    "fail": ${fail_count},
    "lock_state": ${fail_count} > 0,
}
print(json.dumps({"checks": results, "summary": summary}, indent=2))
PYEOF
fi

if [ "${fail_count}" -gt 0 ]; then
  echo
  log_error "MASTER SPEC § 22 LOCK-STATE — ${fail_count} check(s) failed"
  log_error "  The node MUST NOT pass command execution to active dev workflows"
  log_error "  Clear: investigate each FAIL line above; re-run after correction"
  exit 1
fi

log_info "✓ all checks passed — master spec § 22 grid clear"
exit 0
