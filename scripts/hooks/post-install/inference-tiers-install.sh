#!/usr/bin/env bash
# scripts/hooks/post-install/inference-tiers-install.sh
#
# Install the inference tier systemd units so they survive a reboot, and make the
# model-storage mount persistent. Idempotent.
#
# Written after bringing the Oracle Core up by hand on 2026-07-28 hit five separate
# defects in sequence. Four are now fixed in the unit itself; this hook handles the
# HOST-SIDE prerequisites that a unit cannot express:
#
#   - the cache dirs ProtectSystem=strict leaves nowhere writable
#   - /opt/sovereign-os, which ExecStart hardcodes (the image's layout)
#   - the model-storage fstab entry, so weights are not on the root+swap device
#
# DRY-RUN BY DEFAULT. Nothing changes without --apply.
#
#   inference-tiers-install.sh                    # show the plan
#   sudo inference-tiers-install.sh --apply       # do it
#   inference-tiers-install.sh --verify           # post-install check (no root)
#
# Options:
#   --tier oracle|logic|both   which tier(s) to install (default: both)
#   --models-dir DIR           where weights live (default: /home/jfortin/models)
#   --storage-dev DEV          block device to persist in fstab (default: autodetect
#                              the largest unmounted-or-/mnt ext4 partition)
#   --no-fstab                 skip the storage step
#   --apply / --verify

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

STEP_ID="inference-tiers-install"
APPLY=0
VERIFY=0
TIER="both"
MODELS_DIR="/home/jfortin/models"
STORAGE_DEV=""
DO_FSTAB=1

while [ $# -gt 0 ]; do
  case "$1" in
    --apply)       APPLY=1 ;;
    --verify)      VERIFY=1 ;;
    --tier)        TIER="$2"; shift ;;
    --models-dir)  MODELS_DIR="$2"; shift ;;
    --storage-dev) STORAGE_DEV="$2"; shift ;;
    --no-fstab)    DO_FSTAB=0 ;;
    -h|--help)     sed -n '2,28p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)             echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

run() {
  if [ "${APPLY}" -eq 1 ]; then log_info "  + $*"; "$@"
  else log_info "  [dry-run] $*"; fi
}

# ------------------------------------------------------------------ verify
if [ "${VERIFY}" -eq 1 ]; then
  log_step_header "${STEP_ID}" "verify inference tiers"
  rc=0
  for u in sovereign-oracle-core sovereign-logic-engine; do
    st="$(systemctl is-active "${u}" 2>/dev/null || true)"
    en="$(systemctl is-enabled "${u}" 2>/dev/null || true)"
    if [ "${st}" = "active" ]; then log_info "  ${u}: active, ${en}"
    else log_warn "  ${u}: ${st:-absent} (${en:-not enabled})"; rc=1; fi
  done
  for p in 8083 8082; do
    if curl -fsS --max-time 4 "http://127.0.0.1:${p}/v1/models" >/dev/null 2>&1; then
      log_info "  port ${p}: serving"
    else log_warn "  port ${p}: not answering"; rc=1; fi
  done
  if findmnt -no TARGET /mnt/nvme0 >/dev/null 2>&1; then
    grep -q "/mnt/nvme0" /etc/fstab 2>/dev/null \
      && log_info "  /mnt/nvme0: mounted + in fstab" \
      || { log_warn "  /mnt/nvme0: mounted but NOT in fstab — lost on reboot"; rc=1; }
  fi
  emit_metric sovereign_os_post_install_inference_tiers_verify_total 1 \
    "result=\"$([ ${rc} -eq 0 ] && echo pass || echo fail)\""
  exit "${rc}"
fi

log_step_header "${STEP_ID}" "install inference tier units (tier=${TIER})"

# ------------------------------------------------------------------ preflight
FATAL=0
[ -d "${MODELS_DIR}" ] || { log_warn "  models dir ${MODELS_DIR} absent"; FATAL=1; }
command -v systemctl >/dev/null 2>&1 || { log_warn "  systemctl not found"; FATAL=1; }
if ! command -v nvidia-smi >/dev/null 2>&1; then
  log_warn "  nvidia-smi absent — run post-install/nvidia-blackwell-driver-install.sh first"
  FATAL=1
else
  log_info "  GPUs: $(nvidia-smi --query-gpu=name --format=csv,noheader | paste -sd'; ')"
fi
if [ "${FATAL}" -ne 0 ]; then
  log_warn "${STEP_ID}: preflight failed; not proceeding"
  emit_metric sovereign_os_post_install_inference_tiers_total 1 "result=\"preflight_failed\""
  exit 1
fi

# ------------------------------------------------------------------ plan / apply
# ExecStart hardcodes /opt/sovereign-os (the image layout). A symlink satisfies it
# without relocating a developer checkout; ProtectHome=read-only still permits reads.
if [ ! -e /opt/sovereign-os ]; then
  run ln -s "${__REPO_ROOT}" /opt/sovereign-os
else
  log_info "  /opt/sovereign-os already present"
fi

# ProtectSystem=strict + ReadWritePaths leaves the JIT caches nowhere to write, and
# FlashInfer uses HOME/.cache (XDG_CACHE_HOME does not cover it).
for d in /var/log/sovereign-os /var/lib/sovereign-os/oracle-cache/triton \
         /var/lib/sovereign-os/oracle-cache/inductor \
         /var/lib/sovereign-os/logic-cache/triton \
         /var/lib/sovereign-os/logic-cache/inductor; do
  [ -d "${d}" ] || run mkdir -p "${d}"
done
[ -d /etc/sovereign-os ] || run mkdir -p /etc/sovereign-os

install_tier() {
  local unit="$1" env_example="$2" env_target="$3"
  run install -m 0644 "${__REPO_ROOT}/systemd/system/${unit}" "/etc/systemd/system/${unit}"
  if [ -f "${env_target}" ]; then
    log_info "  ${env_target} exists — left alone (operator-owned)"
  else
    run install -m 0644 "${__REPO_ROOT}/systemd/env.examples/${env_example}" "${env_target}"
    log_warn "  EDIT ${env_target} before starting: uncomment the model block"
  fi
}

case "${TIER}" in
  oracle|both) install_tier sovereign-oracle-core.service inference-oracle-core.env \
                            /etc/sovereign-os/inference-oracle-core.env ;;
esac
case "${TIER}" in
  logic|both)  install_tier sovereign-logic-engine.service inference-logic-engine.env \
                            /etc/sovereign-os/inference-logic-engine.env ;;
esac

# ------------------------------------------------------------------ storage
if [ "${DO_FSTAB}" -eq 1 ]; then
  if [ -z "${STORAGE_DEV}" ]; then
    STORAGE_DEV="$(lsblk -rno NAME,FSTYPE,MOUNTPOINT,SIZE | awk '$2=="ext4" && ($3=="" || $3 ~ /^\/mnt\//) {print $1, $4}' \
                   | sort -k2 -hr | head -1 | cut -d' ' -f1)"
    [ -n "${STORAGE_DEV}" ] && STORAGE_DEV="/dev/${STORAGE_DEV}"
  fi
  if [ -n "${STORAGE_DEV}" ] && [ -b "${STORAGE_DEV}" ]; then
    uuid="$(lsblk -no UUID "${STORAGE_DEV}" | head -1)"
    tgt="$(findmnt -no TARGET "${STORAGE_DEV}" 2>/dev/null || echo /mnt/nvme0)"
    if [ -n "${uuid}" ] && ! grep -q "${uuid}" /etc/fstab 2>/dev/null; then
      log_info "  fstab: ${STORAGE_DEV} (${uuid}) -> ${tgt}"
      if [ "${APPLY}" -eq 1 ]; then
        cp -a /etc/fstab "/etc/fstab.bak-${STEP_ID}"
        printf 'UUID=%s  %s  ext4  defaults,noatime  0  2\n' "${uuid}" "${tgt}" >> /etc/fstab
        mkdir -p "${tgt}"
        log_info "  appended (backup: /etc/fstab.bak-${STEP_ID})"
      else
        log_info "  [dry-run] would append the UUID line above to /etc/fstab"
      fi
    else
      log_info "  fstab: ${STORAGE_DEV} already present or no UUID — skipping"
    fi
  else
    log_info "  no spare ext4 partition detected — skipping fstab"
  fi
fi

if [ "${APPLY}" -eq 0 ]; then
  log_info ""
  log_info "  DRY RUN — re-run with --apply (as root) to execute, then:"
  log_info "    edit /etc/sovereign-os/inference-*.env  (uncomment the model block)"
  log_info "    systemctl enable --now sovereign-oracle-core"
  log_info "    ${BASH_SOURCE[0]} --verify"
  emit_metric sovereign_os_post_install_inference_tiers_total 1 "result=\"dry_run\""
  exit 0
fi

require_root
run systemctl daemon-reload
emit_metric sovereign_os_post_install_inference_tiers_total 1 "result=\"installed\",tier=\"${TIER}\""
log_info ""
log_info "  ${STEP_ID} complete. Next:"
log_info "    1. edit /etc/sovereign-os/inference-*.env — uncomment the model block"
log_info "    2. systemctl enable --now sovereign-oracle-core sovereign-logic-engine"
log_info "    3. ${BASH_SOURCE[0]} --verify"
