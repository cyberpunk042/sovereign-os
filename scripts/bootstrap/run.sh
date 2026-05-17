#!/usr/bin/env bash
# scripts/bootstrap/run.sh — Master spec § 12 phase executor (R201).
#
# Sister to phases.sh (R160). phases.sh INVENTORIES the 5-phase pipeline
# (presence-check at authoring time); run.sh DRIVES it (enumerates the
# execution plan operators would invoke on real hardware).
#
# Per master spec § 12: "Each phase must be completed and validated
# before the downstream phase is initiated." run.sh enforces that
# sequencing constraint by phase-at-a-time invocation + by surfacing
# the execution kind of every artifact (build-step / installer-hook /
# post-install-hook / systemd-unit / recurrent-hook / tooling) so the
# operator knows WHERE each artifact runs.
#
# Safety posture:
#   - DRY-RUN ONLY in this round. Phase III-V artifacts are destructive
#     (zfs-pool-create wipes NVMe, vfio-bind detaches the GPU,
#     tetragon-policy-load loads kernel BPF). Real --apply requires a
#     follow-up round with SOVEREIGN_OS_CONFIRM_DESTROY=YES + interactive
#     confirmation + Layer 5 hardware integration. Until then, run.sh
#     emits the EXECUTION PLAN and exits.
#
# CLI:
#   run.sh --phase N [--json]    enumerate phase N's plan (N: 1-5 or I-V)
#   run.sh --phase all [--json]  enumerate ALL phases (default)
#
# Exit codes:
#   0 — execution plan emitted, all artifacts present
#   1 — at least one artifact missing (plan incomplete)
#   2 — usage error

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/.." && pwd)"
__REPO_ROOT="$(cd "${__REPO_ROOT}/.." && pwd)"

JSON_OUT=0
PHASE_FILTER="all"
while [ $# -gt 0 ]; do
  case "$1" in
    --json) JSON_OUT=1; shift ;;
    --phase) PHASE_FILTER="$2"; shift 2 ;;
    -h|--help)
      sed -n '1,32p' "${BASH_SOURCE[0]}"
      exit 0
      ;;
    *) echo "ERROR unknown arg: $1" >&2; exit 2 ;;
  esac
done

case "${PHASE_FILTER}" in
  all) ;;
  I|i|1) PHASE_FILTER=1 ;;
  II|ii|2) PHASE_FILTER=2 ;;
  III|iii|3) PHASE_FILTER=3 ;;
  IV|iv|4) PHASE_FILTER=4 ;;
  V|v|5) PHASE_FILTER=5 ;;
  *) echo "ERROR --phase must be 1-5, I-V, or 'all' (got '${PHASE_FILTER}')" >&2; exit 2 ;;
esac

# ---------- phase definitions ----------
# Drift guard: phase count + names must match scripts/bootstrap/phases.sh
# exactly. The L3 test asserts this by diffing the phase headers.
PHASES=(
"I|Minimal Trixie Base|scripts/build/01-bootstrap-forge.sh|config/preseed/sain-01.preseed.example.cfg|config/cloud-init/sain-01.user-data.example.yaml"
"II|Zen 5 Kernel Compilation|scripts/build/02-kernel-fetch.sh|scripts/build/03-kernel-config.sh|scripts/build/04-kernel-compile.sh"
"III|Storage Layer + DKMS (ZFS)|scripts/hooks/during-install/zfs-pool-create.sh|scripts/hooks/during-install/zfs-datasets-create.sh|scripts/hooks/post-install/zfs-arc-clamp.sh|scripts/hooks/recurrent/zfs-scrub.sh|systemd/system/sovereign-zfs-arc-clamp.service|systemd/system/sovereign-zfs-scrub.service|systemd/system/sovereign-zfs-scrub.timer"
"IV|Container + Network Edge Isolation|scripts/hooks/post-install/vfio-bind-3090.sh|scripts/hooks/post-install/network-vlan-config.sh|scripts/network/render-asymmetric.sh|systemd/system/sovereign-vfio-bind.service|systemd/system/sovereign-network-vlan.service|systemd/system/sovereign-nvidia-driver-bind.service"
"V|Tetragon eBPF + Guardian + State Fabric Mount|scripts/hooks/post-install/tetragon-policy-load.sh|scripts/hooks/recurrent/tetragon-policy-verify.sh|scripts/auditor/guardian-core.py|systemd/system/sovereign-guardian-core.service|systemd/system/sovereign-tetragon-policy-load.service|scripts/weaver/atomic-state.py"
)

# ---------- artifact-kind classification ----------
# Returns one of:
#   build-step          — runs in the build container (forge), authoring-time
#   installer-hook      — runs during cloud-init / preseed install
#   post-install-hook   — runs after first boot (firstboot service)
#   recurrent-hook      — runs on a systemd timer (ongoing)
#   systemd-unit        — operator enables via systemctl
#   systemd-timer       — operator enables via systemctl
#   tooling             — python/shell helper invoked manually or by hooks
#   config              — declarative config consumed by the substrate
classify_artifact() {
  local path="$1"
  case "${path}" in
    scripts/build/*.sh)                    echo "build-step" ;;
    scripts/hooks/during-install/*.sh)     echo "installer-hook" ;;
    scripts/hooks/post-install/*.sh)       echo "post-install-hook" ;;
    scripts/hooks/recurrent/*.sh)          echo "recurrent-hook" ;;
    systemd/system/*.service)              echo "systemd-unit" ;;
    systemd/system/*.timer)                echo "systemd-timer" ;;
    scripts/*.py|scripts/*/*.py)           echo "tooling" ;;
    scripts/*/*.sh)                        echo "tooling" ;;
    config/*|profiles/*|whitelabel/*)      echo "config" ;;
    *)                                     echo "other" ;;
  esac
}

# ---------- emit ----------
overall_missing=0

if [ "${JSON_OUT}" -eq 1 ]; then
  echo "{"
  echo "  \"mode\": \"dry-run\","
  echo "  \"safety_note\": \"R201 emits the execution plan only. --apply is gated to a future round + SOVEREIGN_OS_CONFIRM_DESTROY=YES + Layer 5 hardware.\","
  echo "  \"phases\": ["
fi

emitted_count=0
phase_idx=0
for phase_def in "${PHASES[@]}"; do
  phase_idx=$((phase_idx + 1))
  IFS='|' read -r -a parts <<< "${phase_def}"
  name="${parts[0]}"
  desc="${parts[1]}"
  artifacts=("${parts[@]:2}")

  if [ "${PHASE_FILTER}" != "all" ] && [ "${PHASE_FILTER}" != "${phase_idx}" ]; then
    continue
  fi

  phase_missing=0

  if [ "${JSON_OUT}" -eq 1 ]; then
    [ "${emitted_count}" -gt 0 ] && echo "    ,"
    echo "    {"
    echo "      \"phase\": \"${name}\","
    echo "      \"description\": $(python3 -c "import json,sys; print(json.dumps('''${desc}'''))"),"
    echo "      \"plan\": ["
    for ((i=0;i<${#artifacts[@]};i++)); do
      a="${artifacts[$i]}"
      kind="$(classify_artifact "${a}")"
      status="present"
      if [ ! -e "${__REPO_ROOT}/${a}" ]; then
        status="missing"
        phase_missing=$((phase_missing + 1))
        overall_missing=$((overall_missing + 1))
      fi
      sep=$([ $i -lt $((${#artifacts[@]} - 1)) ] && echo "," || echo "")
      echo "        {\"artifact\": \"${a}\", \"kind\": \"${kind}\", \"status\": \"${status}\"}${sep}"
    done
    echo "      ],"
    echo "      \"would_invoke\": ${#artifacts[@]},"
    echo "      \"artifacts_missing\": ${phase_missing}"
    echo "    }"
  else
    echo
    echo "═══ Phase ${name} — execution plan (DRY-RUN) ═══"
    echo "  ${desc}"
    echo
    for a in "${artifacts[@]}"; do
      kind="$(classify_artifact "${a}")"
      if [ -e "${__REPO_ROOT}/${a}" ]; then
        printf '  [%-18s] would invoke: %s\n' "${kind}" "${a}"
      else
        printf '  [%-18s] MISSING:      %s\n' "${kind}" "${a}"
        phase_missing=$((phase_missing + 1))
        overall_missing=$((overall_missing + 1))
      fi
    done
    echo
    if [ "${phase_missing}" -eq 0 ]; then
      echo "  Phase ${name}: ✓ ${#artifacts[@]} artifacts plotted, ready for operator-driven apply on real hardware"
    else
      echo "  Phase ${name}: ${phase_missing} missing — plan incomplete"
    fi
  fi
  emitted_count=$((emitted_count + 1))
done

if [ "${JSON_OUT}" -eq 1 ]; then
  echo "  ],"
  echo "  \"overall_missing\": ${overall_missing}"
  echo "}"
else
  echo
  echo "═══ DRY-RUN ONLY ═══"
  echo "  R201 emits the execution plan + classifies each artifact's runtime"
  echo "  surface (build-step / installer-hook / post-install-hook /"
  echo "  recurrent-hook / systemd-unit / tooling)."
  echo
  echo "  --apply is intentionally not wired this round: Phase III-V"
  echo "  artifacts are destructive (zfs-pool-create wipes NVMe, vfio-bind"
  echo "  detaches the 3090, tetragon-policy-load installs kernel BPF)."
  echo "  Real execution lives at Layer 5 on the SAIN-01 box behind"
  echo "  SOVEREIGN_OS_CONFIRM_DESTROY=YES + interactive prompt."
fi

if [ "${overall_missing}" -gt 0 ]; then
  exit 1
fi
exit 0
