#!/usr/bin/env bash
# scripts/hooks/post-install/nvidia-driver-install.sh
#
# Install the pinned NVIDIA ≥570 OPEN-kernel driver at first boot (SDD-701).
# trixie ships 550.163, which predates the Blackwell GB202 (RTX PRO 6000 Max-Q +
# RTX 5090) — so the baked nvidia-open-kernel-dkms (550) is superseded here by
# the operator-chosen pinned open-kernel .run from NVIDIA's own download server.
#
# Secure boot: when the profile is secure_boot=signed the enrolled MOK lives at
# /var/lib/sovereign-os/mok (mok-enroll.sh). The .run signs the built modules
# with it (--module-signing-*), and we write /etc/dkms/nvidia.conf so a later
# kernel update re-signs on rebuild — otherwise the kernel refuses the unsigned
# nvidia/nvidia_drm/nvidia_modeset/nvidia_uvm modules and the GPUs stay dark.
#
# Idempotent (a running ≥570 driver → no-op) + VM-skipped by the unit
# (ConditionVirtualization=no). A driver install needs a reboot to bind: this
# hook drops the reboot marker the completion service surfaces on the console.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

STEP_ID="nvidia-driver-install"
MIN_MAJOR=570

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

: "${SOVEREIGN_OS_MOK_DIR:=/var/lib/sovereign-os/mok}"

log_step_header "${STEP_ID}" "install pinned NVIDIA ≥${MIN_MAJOR} open-kernel driver"

require_root

emit_install_metric() {
  emit_metric sovereign_os_post_install_nvidia_driver_install_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"$1\""
}

# ---- idempotency: a running ≥570 driver means we're done ----
if command -v nvidia-smi >/dev/null 2>&1; then
  cur="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1 | cut -d. -f1)"
  if [ -n "${cur}" ] && [ "${cur}" -ge "${MIN_MAJOR}" ] 2>/dev/null; then
    log_info "nvidia driver ${cur}.x already active (≥${MIN_MAJOR}); nothing to install"
    emit_install_metric already-current
    exit 0
  fi
  log_info "current nvidia driver reports major '${cur:-none}' (< ${MIN_MAJOR}) — installing the pinned runfile"
fi

ver="$(profile_field provisioning.nvidia.driver_runfile_version)"
url_base="$(profile_field provisioning.nvidia.runfile_url_base)"
mod_type="$(profile_field provisioning.nvidia.kernel_module_type)"
: "${mod_type:=open}"
if [ -z "${ver}" ] || [ -z "${url_base}" ]; then
  log_error "profile provisioning.nvidia.{driver_runfile_version,runfile_url_base} unset — cannot pin the driver"
  emit_install_metric no-pin
  exit 1
fi
# Refuse a pin below the Blackwell floor (a stale profile edit would ship a dark GPU).
if ! printf '%s' "${ver}" | grep -qE '^[0-9]+'; then
  log_error "driver_runfile_version '${ver}' is not a version string"
  emit_install_metric bad-pin; exit 1
fi
if [ "$(printf '%s' "${ver}" | cut -d. -f1)" -lt "${MIN_MAJOR}" ] 2>/dev/null; then
  log_error "pinned driver ${ver} is < ${MIN_MAJOR} — Blackwell needs ≥${MIN_MAJOR}; fix the profile"
  emit_install_metric pin-too-old; exit 1
fi

runfile="NVIDIA-Linux-x86_64-${ver}.run"
url="${url_base%/}/${ver}/${runfile}"
cache="/var/cache/sovereign-os/nvidia"
mkdir -p "${cache}"
dst="${cache}/${runfile}"

# ---- download the pinned runfile (fail loudly on a 404 / short file) ----
if [ ! -s "${dst}" ]; then
  log_info "downloading ${url}"
  if ! curl -fL --retry 3 --retry-delay 5 -o "${dst}.part" "${url}" 2>&1 | sed 's/^/  /'; then
    log_error "download failed: ${url} — verify provisioning.nvidia.driver_runfile_version exists on NVIDIA's server"
    rm -f "${dst}.part"; emit_install_metric download-failed; exit 1
  fi
  mv "${dst}.part" "${dst}"
fi
# a runfile is a self-extracting shell script + a large payload — a few-KB file is an error page, not a driver
if [ "$(stat -c%s "${dst}" 2>/dev/null || echo 0)" -lt 10000000 ]; then
  log_error "downloaded runfile ${dst} is implausibly small (<10MB) — likely an error page, not the driver"
  rm -f "${dst}"; emit_install_metric bad-download; exit 1
fi
chmod +x "${dst}"

# ---- clear the conflicting distro driver (the .run refuses to coexist) ----
if command -v apt-get >/dev/null 2>&1; then
  log_info "removing the distro nvidia driver packages the .run would conflict with"
  DEBIAN_FRONTEND=noninteractive apt-get purge -y \
    'nvidia-driver*' 'nvidia-kernel*' 'nvidia-open-kernel-dkms' 'xserver-xorg-video-nvidia*' 2>&1 \
    | sed 's/^/  /' || log_warn "distro nvidia purge reported issues (continuing — the .run supersedes)"
fi

# ---- secure-boot module signing (MOK) ----
sign_args=()
dkms_conf_written=0
sb_state="$(mokutil --sb-state 2>/dev/null || true)"
if [ -f "${SOVEREIGN_OS_MOK_DIR}/MOK.priv" ] && [ -f "${SOVEREIGN_OS_MOK_DIR}/MOK.der" ]; then
  log_info "MOK present (${SOVEREIGN_OS_MOK_DIR}) — signing the built modules for secure boot"
  sign_args=(
    --module-signing-secret-key "${SOVEREIGN_OS_MOK_DIR}/MOK.priv"
    --module-signing-public-key "${SOVEREIGN_OS_MOK_DIR}/MOK.der"
  )
  # persist the signing key so a future kernel update's DKMS rebuild re-signs
  mkdir -p /etc/dkms
  cat > /etc/dkms/nvidia.conf <<EOF
# sovereign-os (SDD-701): re-sign the nvidia DKMS modules with the enrolled MOK
# on every kernel-update rebuild, else secure boot rejects them and the GPU dies.
mok_signing_key="${SOVEREIGN_OS_MOK_DIR}/MOK.priv"
mok_certificate="${SOVEREIGN_OS_MOK_DIR}/MOK.der"
sign_tool="/etc/dkms/sign_helper.sh"
EOF
  dkms_conf_written=1
elif printf '%s' "${sb_state}" | grep -qi 'enabled'; then
  log_warn "secure boot is ENABLED but no MOK at ${SOVEREIGN_OS_MOK_DIR} — the built modules will be UNSIGNED and the kernel will refuse them; run mok-enroll first"
fi

# ---- install (silent, DKMS-registered, open modules for Blackwell) ----
log_info "installing ${runfile} (--dkms --kernel-module-type=${mod_type}${sign_args:+ + MOK-signed})"
if ! "${dst}" --silent --dkms --no-questions \
      --kernel-module-type="${mod_type}" \
      "${sign_args[@]}" 2>&1 | sed 's/^/  /'; then
  log_error "NVIDIA runfile install failed — see /var/log/nvidia-installer.log; GPUs will not bind until resolved"
  [ "${dkms_conf_written}" = 1 ] && rm -f /etc/dkms/nvidia.conf
  emit_install_metric install-failed
  exit 1
fi

# rebuild initramfs (serialized — SDD-998 boot_regen — vfio/zfs/bind race on it)
if command -v update-initramfs >/dev/null 2>&1; then
  boot_regen update-initramfs -u 2>&1 | sed 's/^/  /' || log_warn "update-initramfs failed"
fi

log_info "pinned NVIDIA ${ver} (${mod_type} modules) installed — reboot required to bind the GPUs"
emit_install_metric installed
emit_metric sovereign_os_post_install_nvidia_driver_version_info 1 \
  "profile=\"${SOVEREIGN_OS_PROFILE}\",version=\"${ver}\",module_type=\"${mod_type}\""
log_info "${STEP_ID} complete"
