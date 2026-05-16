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
# Format: name|description|artifact1|artifact2|...
# Each artifact is a path relative to the repo root.
PHASES=(
"I|Minimal Trixie Base (master spec § 12 Phase I)|scripts/build/01-bootstrap-forge.sh|config/preseed/sain-01.preseed.example.cfg|config/cloud-init/sain-01.user-data.example.yaml"
"II|Zen 5 Kernel Compilation (master spec § 12 Phase II + § 2)|scripts/build/02-kernel-fetch.sh|scripts/build/03-kernel-config.sh|scripts/build/04-kernel-compile.sh"
"III|Storage Layer + DKMS — ZFS native (master spec § 12 Phase III + § 3, 4.1)|scripts/hooks/during-install/zfs-pool-create.sh|scripts/hooks/during-install/zfs-datasets-create.sh|scripts/hooks/post-install/zfs-arc-clamp.sh|scripts/hooks/recurrent/zfs-scrub.sh|systemd/system/sovereign-zfs-arc-clamp.service|systemd/system/sovereign-zfs-scrub.service|systemd/system/sovereign-zfs-scrub.timer"
"IV|Container + Network Edge Isolation — Podman, VFIO, asymmetric net (master spec § 12 Phase IV + § 4.3, 8)|scripts/hooks/post-install/vfio-bind-3090.sh|scripts/hooks/post-install/network-vlan-config.sh|scripts/network/render-asymmetric.sh|systemd/system/sovereign-vfio-bind.service|systemd/system/sovereign-network-vlan.service|systemd/system/sovereign-nvidia-driver-bind.service"
"V|Tetragon eBPF + Guardian + State Fabric Mount (master spec § 12 Phase V + § 5, 6, 10, 21)|scripts/hooks/post-install/tetragon-policy-load.sh|scripts/hooks/recurrent/tetragon-policy-verify.sh|scripts/auditor/guardian-core.py|systemd/system/sovereign-guardian-core.service|systemd/system/sovereign-tetragon-policy-load.service|scripts/weaver/atomic-state.py"
)

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
  name="${parts[0]}"
  desc="${parts[1]}"
  artifacts=("${parts[@]:2}")

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
