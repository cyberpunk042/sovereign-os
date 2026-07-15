#!/usr/bin/env bash
# scripts/bootstrap/phases.sh — Master spec § 12 chronological pipeline surface.
#
# Master spec § 12 — Chronological Vision: The Sovereign Bootstrap Pipeline:
#
#   "This master timeline details the sequential generation of your
#    workstation node, starting from an empty NVMe block device on the
#    ASUS ProArt X870E-Creator up to a fully optimized, multi-GPU state
#    engine. Each phase must be completed and validated before the
#    downstream phase is initiated."
#
# 5 phases verbatim:
#   I   — Minimal Trixie Base
#   II  — Zen 5 Kernel Compilation
#   III — Storage Layer + DKMS (ZFS)
#   IV  — Container + Network Edge Isolation (Podman, VFIO, asymmetric net)
#   V   — Tetragon eBPF + Guardian + State Fabric Mount
#
# This script:
#   1. Enumerates the 5 phases with their constituent artifacts
#   2. Reports ✅/✗ presence-status for every artifact in-repo
#   3. Supports `--phase N` to filter to one phase
#   4. Supports `--json` for fleet tooling
#
# Distinct from `scripts/bootstrap/verify.sh` (R159): that one runs the
# master spec § 22 6-check operational grid on a LIVE node. This one
# inventories the AUTHORING-time artifacts that drive Phase I-V.
#
# CLI:
#   phases.sh                  list all 5 phases
#   phases.sh --phase N        show only phase N (1-5 or I-V)
#   phases.sh --json           machine-readable
#
# Exit codes:
#   0 — all artifacts present
#   1 — at least one artifact missing
#   2 — usage error

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/.." && pwd)"
__REPO_ROOT="$(cd "${__REPO_ROOT}/.." && pwd)"

# ---------- python3 resolver ----------
# Some environments (linuxbrew) ship a python3 without PyYAML. Pick the
# first python3 in PATH that can import yaml; fall back to /usr/bin/python3.
PYTHON3="${PYTHON3:-python3}"
if ! "${PYTHON3}" -c "import yaml" >/dev/null 2>&1; then
  if /usr/bin/python3 -c "import yaml" >/dev/null 2>&1; then
    PYTHON3="/usr/bin/python3"
  fi
fi

JSON_OUT=0
PHASE_FILTER=""
while [ $# -gt 0 ]; do
  case "$1" in
    --json) JSON_OUT=1; shift ;;
    --phase) PHASE_FILTER="$2"; shift 2 ;;
    -h|--help)
      sed -n '1,30p' "${BASH_SOURCE[0]}"
      exit 0
      ;;
    *) echo "ERROR unknown arg: $1" >&2; exit 2 ;;
  esac
done

# Normalize phase filter: accept "1" / "I" / "i" → "1"
case "${PHASE_FILTER}" in
  I|i|1) PHASE_FILTER=1 ;;
  II|ii|2) PHASE_FILTER=2 ;;
  III|iii|3) PHASE_FILTER=3 ;;
  IV|iv|4) PHASE_FILTER=4 ;;
  V|v|5) PHASE_FILTER=5 ;;
  "") ;;
  *) echo "ERROR --phase must be 1-5 or I-V (got '${PHASE_FILTER}')" >&2; exit 2 ;;
esac

# ---------- phase definitions ----------
# R202: canonical phase table lives in config/bootstrap/phases.yaml.
# Format emitted by load-phases.py: id|name|description|artifact...
mapfile -t PHASES < <("${PYTHON3}" "${__REPO_ROOT}/scripts/bootstrap/lib/load-phases.py")
if [ "${#PHASES[@]}" -eq 0 ]; then
  echo "ERROR phases.yaml loader returned empty table" >&2
  exit 2
fi

# ---------- emit ----------
overall_missing=0

if [ "${JSON_OUT}" -eq 1 ]; then
  echo "{"
  echo "  \"phases\": ["
fi

phase_idx=0
for phase_def in "${PHASES[@]}"; do
  phase_idx=$((phase_idx + 1))
  IFS='|' read -r -a parts <<< "${phase_def}"
  # R202: yaml format is id|name|description|artifact...
  name="${parts[0]}"
  desc="${parts[1]} (${parts[2]})"
  artifacts=("${parts[@]:3}")

  if [ -n "${PHASE_FILTER}" ] && [ "${PHASE_FILTER}" != "${phase_idx}" ]; then
    continue
  fi

  phase_missing=0
  phase_present=0
  artifact_lines=()
  for a in "${artifacts[@]}"; do
    if [ -e "${__REPO_ROOT}/${a}" ]; then
      artifact_lines+=("  ✓ ${a}")
      phase_present=$((phase_present + 1))
    else
      artifact_lines+=("  ✗ ${a}")
      phase_missing=$((phase_missing + 1))
      overall_missing=$((overall_missing + 1))
    fi
  done

  if [ "${JSON_OUT}" -eq 1 ]; then
    # Build JSON entry
    if [ "${phase_idx}" -gt 1 ] && [ -z "${PHASE_FILTER}" ]; then
      echo "    ,"
    fi
    echo "    {"
    echo "      \"phase\": \"${name}\","
    echo "      \"description\": $(python3 -c "import json,sys; print(json.dumps('''${desc}'''))"),"
    echo "      \"artifacts_present\": ${phase_present},"
    echo "      \"artifacts_missing\": ${phase_missing},"
    echo "      \"artifacts\": ["
    for ((i=0;i<${#artifacts[@]};i++)); do
      a="${artifacts[$i]}"
      status="$([ -e "${__REPO_ROOT}/${a}" ] && echo "present" || echo "missing")"
      sep=$([ $i -lt $((${#artifacts[@]} - 1)) ] && echo "," || echo "")
      echo "        {\"path\": \"${a}\", \"status\": \"${status}\"}${sep}"
    done
    echo "      ]"
    echo "    }"
  else
    echo
    echo "═══ Phase ${name} ═══"
    echo "  ${desc}"
    echo
    for line in "${artifact_lines[@]}"; do
      echo "${line}"
    done
    echo
    if [ "${phase_missing}" -eq 0 ]; then
      echo "  Phase ${name}: ✓ all ${phase_present} artifacts present"
    else
      echo "  Phase ${name}: ${phase_present} present, ${phase_missing} MISSING"
    fi
  fi
done

if [ "${JSON_OUT}" -eq 1 ]; then
  echo "  ],"
  echo "  \"overall_missing\": ${overall_missing}"
  echo "}"
fi

if [ "${overall_missing}" -gt 0 ]; then
  [ "${JSON_OUT}" -eq 0 ] && echo
  [ "${JSON_OUT}" -eq 0 ] && echo "OVERALL: ${overall_missing} artifact(s) missing — pipeline incomplete"
  exit 1
fi

[ "${JSON_OUT}" -eq 0 ] && echo
[ "${JSON_OUT}" -eq 0 ] && echo "OVERALL: ✓ all 5 phases fully populated (master spec § 12 surface complete)"
exit 0
