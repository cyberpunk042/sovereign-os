#!/usr/bin/env bash
# scripts/hooks/post-install/nvidia-blackwell-driver-install.sh
#
# Install the NVIDIA open kernel driver + CUDA toolkit for the SAIN-01 Blackwell tier.
# Closes the TODO(SDD-blackwell) gap in profiles/sain-01.yaml: nvidia-driver-bind.sh
# blacklists nouveau but installs nothing, and Debian trixie's own nvidia-driver is
# 550.163.01 — which PREDATES Blackwell (GB202 needs >= 570). Without this the
# RTX PRO 6000 (96 GB) and RTX 5090 (32 GB) stay on nouveau and are unusable for compute.
#
# DRY-RUN BY DEFAULT. Nothing is changed without --apply.
#
#   nvidia-blackwell-driver-install.sh                 # preflight + plan only
#   sudo nvidia-blackwell-driver-install.sh --apply    # do it (reboot required after)
#   nvidia-blackwell-driver-install.sh --verify        # post-reboot check (no root needed)
#
# Options:
#   --branch N     driver branch to pin (default 590; 570 is the Blackwell floor)
#   --no-cuda      driver only, skip the CUDA toolkit
#   --apply        actually make changes
#   --verify       post-reboot verification only
#
# Reversal (if the box comes back headless):
#   boot the previous kernel entry / a rescue shell, then
#     apt-get purge -y 'nvidia-*' 'cuda-*' && rm -f /etc/modprobe.d/blacklist-nouveau.conf
#     sed -i 's/ *nvidia-drm.modeset=1//' /etc/default/grub && update-grub && update-initramfs -u

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

STEP_ID="nvidia-blackwell-driver-install"

APPLY=0
VERIFY_ONLY=0
WANT_CUDA=1
BRANCH=590
MIN_BRANCH=570
NV_REPO="https://developer.download.nvidia.com/compute/cuda/repos/debian13/x86_64"
KEYRING_DEB="cuda-keyring_1.1-1_all.deb"

while [ $# -gt 0 ]; do
  case "$1" in
    --apply)    APPLY=1 ;;
    --verify)   VERIFY_ONLY=1 ;;
    --no-cuda)  WANT_CUDA=0 ;;
    --branch)   BRANCH="$2"; shift ;;
    -h|--help)  sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)          echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

run() {
  if [ "${APPLY}" -eq 1 ]; then
    log_info "  + $*"
    "$@"
  else
    log_info "  [dry-run] $*"
  fi
}

# --------------------------------------------------------------------- verify
verify() {
  local rc=0
  log_step_header "${STEP_ID}" "post-reboot verification"

  if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
    log_info "  nvidia-smi OK"
    nvidia-smi --query-gpu=index,name,memory.total,driver_version \
               --format=csv,noheader 2>/dev/null | sed 's/^/    /'
    local n
    n="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | wc -l)"
    [ "${n}" -ge 2 ] && log_info "  ${n} GPUs visible" \
                     || log_warn "  only ${n} GPU visible — expected >=2 (PRO 6000 + 5090)"
  else
    log_warn "  nvidia-smi missing or failing — driver not active"
    rc=1
  fi

  # Read /proc/modules directly: lsmod lives in /sbin and is often off a non-root PATH,
  # which would silently turn "loaded" into a false "not loaded".
  if grep -q '^nouveau ' /proc/modules 2>/dev/null; then
    log_warn "  nouveau STILL LOADED — blacklist did not take effect"
    rc=1
  else
    log_info "  nouveau not loaded"
  fi

  if command -v nvcc >/dev/null 2>&1; then
    log_info "  nvcc: $(nvcc --version 2>/dev/null | tail -1)"
  else
    log_warn "  nvcc not on PATH (add /usr/local/cuda/bin; harmless if --no-cuda)"
  fi

  grep -q nomodeset /proc/cmdline 2>/dev/null \
    && { log_warn "  'nomodeset' still on the running cmdline — GRUB not updated or not rebooted"; rc=1; } \
    || log_info "  nomodeset cleared"

  emit_metric sovereign_os_post_install_nvidia_driver_verify_total 1 \
    "result=\"$([ ${rc} -eq 0 ] && echo pass || echo fail)\""
  if [ "${rc}" -eq 0 ]; then
    log_info "  verification PASSED"
  else
    log_warn "  verification FAILED — the driver is not usable yet (details above)"
  fi
  VERIFY_RC="${rc}"
}

if [ "${VERIFY_ONLY}" -eq 1 ]; then
  VERIFY_RC=0
  verify
  exit "${VERIFY_RC}"
fi

# ------------------------------------------------------------------ preflight
log_step_header "${STEP_ID}" "install NVIDIA open driver (branch ${BRANCH}) + CUDA for Blackwell"

FATAL=0
warn_or_fail() { log_warn "  $1"; FATAL=1; }

# 1. Blackwell present?
GPUS="$(lspci -nn 2>/dev/null | grep -iE 'VGA|3D' | grep -i nvidia || true)"
if [ -z "${GPUS}" ]; then
  warn_or_fail "no NVIDIA GPU on the PCIe bus — nothing to install for"
else
  echo "${GPUS}" | sed 's/^/    /'
  echo "${GPUS}" | grep -qiE 'GB20[0-9]|Blackwell|RTX (PRO )?(50|60)[0-9][0-9]' \
    && log_info "  Blackwell-class GPU detected (needs driver >= ${MIN_BRANCH})" \
    || log_warn "  no Blackwell GPU matched — branch ${BRANCH} is still fine for older cards"
fi

# 2. branch sanity
if [ "${BRANCH}" -lt "${MIN_BRANCH}" ]; then
  warn_or_fail "branch ${BRANCH} < ${MIN_BRANCH}: Blackwell GB20x is NOT supported below ${MIN_BRANCH}"
fi

# 3. distro
. /etc/os-release 2>/dev/null || true
if [ "${VERSION_ID:-}" != "13" ]; then
  log_warn "  this hook targets Debian 13 (found '${PRETTY_NAME:-unknown}') — repo path may differ"
fi

# 4. Debian's own nvidia-driver is too old — make sure we do not get it by accident
DEB_NV="$(apt-cache policy nvidia-driver 2>/dev/null | awk '/Candidate:/{print $2}')"
[ -n "${DEB_NV}" ] && log_info "  Debian's nvidia-driver candidate is ${DEB_NV} (too old for Blackwell — we bypass it)"

# 5. Secure Boot — open modules are unsigned by DKMS; SB on means MOK enrolment
SB="$(mokutil --sb-state 2>/dev/null | head -1 || echo 'unknown')"
case "${SB}" in
  *disabled*) log_info "  Secure Boot disabled — DKMS modules load unsigned, no MOK enrolment needed" ;;
  *enabled*)  warn_or_fail "Secure Boot ENABLED — you must enrol a MOK key or the module will not load" ;;
  *)          log_warn "  Secure Boot state unknown (${SB}) — check before rebooting" ;;
esac

# 6. headers for DKMS
if [ -d "/lib/modules/$(uname -r)/build" ]; then
  log_info "  kernel headers present for $(uname -r)"
else
  log_warn "  kernel headers MISSING for $(uname -r) — will install linux-headers"
fi

# 7. space
FREE_MB="$(df -Pm /usr | awk 'NR==2{print $4}')"
[ "${FREE_MB:-0}" -lt 8000 ] \
  && warn_or_fail "only ${FREE_MB} MB free on /usr — CUDA toolkit needs ~6-8 GB" \
  || log_info "  ${FREE_MB} MB free on /usr"

# 8. network to NVIDIA
if curl -fsI --max-time 20 "${NV_REPO}/" >/dev/null 2>&1; then
  log_info "  ${NV_REPO} reachable"
else
  warn_or_fail "cannot reach ${NV_REPO} — this hook needs network (air-gapped boxes: mirror the repo first)"
fi

if [ "${FATAL}" -ne 0 ]; then
  log_warn "${STEP_ID}: preflight found blocking issues (above). Not proceeding."
  emit_metric sovereign_os_post_install_nvidia_driver_total 1 "result=\"preflight_failed\""
  exit 1
fi

if [ "${APPLY}" -eq 0 ]; then
  log_info ""
  log_info "  DRY RUN — plan:"
  log_info "    1. apt install linux-headers-amd64 dkms build-essential"
  log_info "    2. add NVIDIA CUDA repo (${KEYRING_DEB})"
  log_info "    3. apt install nvidia-driver-pinning-${BRANCH} then nvidia-open"
  [ "${WANT_CUDA}" -eq 1 ] && log_info "    4. apt install cuda-toolkit"
  log_info "    5. blacklist nouveau + drop 'nomodeset' + add nvidia-drm.modeset=1"
  log_info "    6. update-initramfs + update-grub"
  log_info "    7. REBOOT, then: $0 --verify"
  log_info ""
  log_info "  re-run with --apply (as root) to execute."
  emit_metric sovereign_os_post_install_nvidia_driver_total 1 "result=\"dry_run\""
  exit 0
fi

require_root

# ---------------------------------------------------------------------- apply
export DEBIAN_FRONTEND=noninteractive

log_info "  [1/6] build prerequisites"
run apt-get update
run apt-get install -y linux-headers-amd64 dkms build-essential curl ca-certificates

log_info "  [2/6] NVIDIA CUDA repository"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT
run curl -fsSL -o "${TMP}/${KEYRING_DEB}" "${NV_REPO}/${KEYRING_DEB}"
run dpkg -i "${TMP}/${KEYRING_DEB}"
run apt-get update

log_info "  [3/6] pin driver branch ${BRANCH} + install the OPEN kernel module"
# Blackwell GB20x is supported ONLY by the open kernel modules — not the legacy proprietary one.
run apt-get install -y "nvidia-driver-pinning-${BRANCH}"
run apt-get update
run apt-get install -y nvidia-open

if [ "${WANT_CUDA}" -eq 1 ]; then
  log_info "  [4/6] CUDA toolkit (nvcc — needed to build Colibri CUDA=1 and ChromoFold)"
  run apt-get install -y cuda-toolkit
  if [ "${APPLY}" -eq 1 ] && [ ! -f /etc/profile.d/cuda.sh ]; then
    printf 'export PATH=/usr/local/cuda/bin:$PATH\nexport LD_LIBRARY_PATH=/usr/local/cuda/lib64:${LD_LIBRARY_PATH:-}\n' \
      > /etc/profile.d/cuda.sh
    log_info "  wrote /etc/profile.d/cuda.sh"
  fi
else
  log_info "  [4/6] skipped (--no-cuda)"
fi

log_info "  [5/6] nouveau blacklist + kernel cmdline"
if [ ! -f /etc/modprobe.d/blacklist-nouveau.conf ]; then
  if [ "${APPLY}" -eq 1 ]; then
    cat > /etc/modprobe.d/blacklist-nouveau.conf <<'EOF'
# sovereign-os: nouveau replaced by the NVIDIA open kernel driver
blacklist nouveau
options nouveau modeset=0
EOF
  fi
  log_info "  blacklisted nouveau"
else
  log_info "  nouveau already blacklisted"
fi

# 'nomodeset' and the NVIDIA DRM driver are mutually exclusive (profiles/sain-01.yaml
# TODO(SDD-blackwell)). Drop it and enable KMS.
if grep -q 'nomodeset' /etc/default/grub 2>/dev/null; then
  run cp -a /etc/default/grub "/etc/default/grub.bak-${STEP_ID}"
  run sed -i 's/\bnomodeset\b//g' /etc/default/grub
  log_info "  removed 'nomodeset' (backup: /etc/default/grub.bak-${STEP_ID})"
fi
if ! grep -q 'nvidia-drm.modeset=1' /etc/default/grub 2>/dev/null; then
  run sed -i 's/^\(GRUB_CMDLINE_LINUX_DEFAULT="\)/\1nvidia-drm.modeset=1 /' /etc/default/grub
  log_info "  added nvidia-drm.modeset=1"
fi

log_info "  [6/6] regenerate boot artefacts"
command -v update-initramfs >/dev/null 2>&1 && run boot_regen update-initramfs -u
command -v update-grub      >/dev/null 2>&1 && run update-grub

emit_metric sovereign_os_post_install_nvidia_driver_total 1 \
  "result=\"installed\",branch=\"${BRANCH}\""

log_info ""
log_info "  ${STEP_ID} complete — REBOOT REQUIRED."
log_info "    sudo reboot"
log_info "  then verify:"
log_info "    $0 --verify"
log_info ""
log_info "  if the box comes back headless, see the reversal recipe in this script's header."
