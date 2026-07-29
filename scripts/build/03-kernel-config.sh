#!/usr/bin/env bash
# scripts/build/03-kernel-config.sh — derive kernel .config from the
# profile's kernel.config block. Starts from the running distro's
# config (defconfig fallback), applies profile enable/disable list,
# resolves dependencies via olddefconfig.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib/common.sh
. "${__SCRIPT_DIR}/lib/common.sh"
# shellcheck source=./lib/observability.sh
. "${__SCRIPT_DIR}/lib/observability.sh"

STEP_ID="03-kernel-config"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

: "${SOVEREIGN_OS_FORGE_DIR:=/mnt/kernel_forge}"
: "${SOVEREIGN_OS_KERNEL_SRC:=${SOVEREIGN_OS_FORGE_DIR}/linux-stable}"

# Q18-A: substrate-default profiles skip kernel-build steps 02-04.
kernel_source="$(profile_field kernel.source)"
if [ "${kernel_source}" = "substrate-default" ] || [ -z "${kernel_source}" ]; then
  log_info "skipping ${STEP_ID} (kernel.source=substrate-default — no custom .config to derive)"
  exit 0
fi

inputs_hash="$(state_inputs_hash "${BASH_SOURCE[0]}" "${SOVEREIGN_OS_PROFILE_FILE}")"

if ! state_step_should_run "${STEP_ID}" "${inputs_hash}"; then
  log_info "step ${STEP_ID} already completed with matching inputs — skipping"
  exit 0
fi

log_step_header "${STEP_ID}" "derive kernel .config from profile"
state_step_start "${STEP_ID}" "${inputs_hash}"

# ---- DRY-RUN short-circuit (operator-verbatim CI/preview safety) ----
if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
  log_warn "SOVEREIGN_OS_DRY_RUN set — skipping defconfig + olddefconfig"
  emit_metric sovereign_os_build_step_kernel_config_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"dry-run\""
  # Record 'dry-run', NOT 'completed' — completing here with the real
  # inputs_hash makes the next REAL run skip this step body entirely.
  state_step_dry_run "${STEP_ID}"
  exit 0
fi

require_dir "${SOVEREIGN_OS_KERNEL_SRC}"
require_command make

cd "${SOVEREIGN_OS_KERNEL_SRC}" || exit 1

# ---- starting config: prefer running distro's; fall back to defconfig ----
# The seed decides thousands of symbols the profile never names, so WHERE it
# comes from is a real correctness question — not a detail.
#
# Order: an explicit operator seed, then the build host's running config, then
# defconfig. The host config is a good seed only when the host and the TARGET
# are the same distribution: Debian and Ubuntu ship materially different kernel
# configs (LSMs, apparmor defaults, module signing, ZFS/AppArmor toggles), and
# seeding an Ubuntu 26.04 target from a Debian 13 host quietly produces a kernel
# that is neither. Say so loudly rather than let it pass unnoticed — the
# operator can then point SOVEREIGN_OS_KERNEL_SEED_CONFIG at the right file
# (2026-07-28, when Ubuntu became a build target).
_host_distro="$( . /etc/os-release 2>/dev/null && printf '%s' "${ID:-unknown}" )"
_target_distro="${SOVEREIGN_OS_DISTRO:-debian}"

if [ -n "${SOVEREIGN_OS_KERNEL_SEED_CONFIG:-}" ]; then
  require_file "${SOVEREIGN_OS_KERNEL_SEED_CONFIG}"
  log_info "seeding .config from SOVEREIGN_OS_KERNEL_SEED_CONFIG=${SOVEREIGN_OS_KERNEL_SEED_CONFIG}"
  cp "${SOVEREIGN_OS_KERNEL_SEED_CONFIG}" .config
elif [ -r "/boot/config-$(uname -r)" ] && [ -z "${SOVEREIGN_OS_FORCE_DEFCONFIG:-}" ]; then
  if [ "${_host_distro}" != "${_target_distro}" ]; then
    log_warn "CROSS-DISTRO KERNEL SEED: build host is '${_host_distro}', target is '${_target_distro}'"
    log_warn "  seeding from /boot/config-$(uname -r) — a ${_host_distro} config for a ${_target_distro} kernel."
    log_warn "  It builds and boots, but the two distros differ on LSM/apparmor/module-signing"
    log_warn "  defaults, so the result matches NEITHER distro's stock kernel."
    log_warn "  To seed deliberately:  SOVEREIGN_OS_KERNEL_SEED_CONFIG=/path/to/${_target_distro}-config"
    log_warn "  or force a clean base:  SOVEREIGN_OS_FORCE_DEFCONFIG=1"
    emit_metric sovereign_os_build_step_kernel_seed_total 1 \
      "host=\"${_host_distro}\",target=\"${_target_distro}\",result=\"cross-distro\""
  else
    log_info "seeding .config from /boot/config-$(uname -r) (host and target are both ${_target_distro})"
    emit_metric sovereign_os_build_step_kernel_seed_total 1 \
      "host=\"${_host_distro}\",target=\"${_target_distro}\",result=\"host-config\""
  fi
  cp "/boot/config-$(uname -r)" .config
else
  log_info "seeding .config via 'make defconfig'"
  emit_metric sovereign_os_build_step_kernel_seed_total 1 \
    "host=\"${_host_distro}\",target=\"${_target_distro}\",result=\"defconfig\""
  make defconfig
fi

# ---- apply profile enable list ----
log_info "applying enable list from profile"
python3 - <<'PY'
import os, sys, yaml, subprocess
with open(os.environ["SOVEREIGN_OS_PROFILE_FILE"]) as f:
    data = yaml.safe_load(f)
cfg = (data.get("kernel") or {}).get("config") or {}
enable = cfg.get("enable") or []
disable = cfg.get("disable") or []

for sym in enable:
    subprocess.run(["scripts/config", "--enable", sym], check=False)
    print(f"  + CONFIG_{sym}=y")

for sym in disable:
    subprocess.run(["scripts/config", "--disable", sym], check=False)
    print(f"  - CONFIG_{sym} is not set")
PY

# ---- resolve dependencies / fill in missing symbols ----
log_info "running 'make olddefconfig' to resolve deps"
if ! make olddefconfig; then
  log_error "make olddefconfig failed — kernel symbol resolution broken"
  emit_metric sovereign_os_build_step_kernel_config_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"fail\""
  state_step_fail "${STEP_ID}" "olddefconfig-failed"
  exit 1
fi

# ---- verify profile-required symbols survived olddefconfig ----
# `scripts/config --enable` sets a symbol, but `make olddefconfig` silently
# DROPS any symbol whose dependencies are unmet (or whose name is wrong / has
# been removed upstream). A silently-missing VFIO_PCI / *_IOMMU / BPF_LSM / ZFS
# means a kernel that can't do GPU passthrough, run selfdef's eBPF security, or
# mount the root pool — discovered only at runtime. Surface any dropped symbols
# loudly (a warning + a metric, not a hard fail: an obsolete symbol such as
# AMD_IOMMU_V2 on a 6.12+ kernel is a benign drop that shouldn't break the
# build, but the operator must still see what's missing).
missing_syms=""
while IFS= read -r sym; do
  [ -z "${sym}" ] && continue
  if ! grep -qE "^CONFIG_${sym}=(y|m)$" .config; then
    missing_syms="${missing_syms} ${sym}"
  fi
done < <(python3 -c "
import os, yaml
with open(os.environ['SOVEREIGN_OS_PROFILE_FILE']) as f:
    d = yaml.safe_load(f)
for s in ((d.get('kernel') or {}).get('config') or {}).get('enable') or []:
    print(s)
")
if [ -n "${missing_syms}" ]; then
  log_warn "profile-required kernel symbols NOT enabled after olddefconfig:${missing_syms}"
  log_warn "  (unmet dependencies, wrong name, or removed upstream — the built kernel"
  log_warn "   would LACK these capabilities; reconcile the profile kernel.config.enable"
  log_warn "   list or the symbols' Kconfig dependencies)"
else
  log_info "verified: all profile-required kernel symbols are enabled in .config"
fi
# Count of dropped required symbols — 0 is the healthy state; alert on > 0.
missing_count="$(printf '%s' "${missing_syms}" | wc -w | tr -d ' ')"
emit_metric sovereign_os_build_step_kernel_config_missing_symbols "${missing_count}" \
  "profile=\"${SOVEREIGN_OS_PROFILE}\"" 2>/dev/null || true

# ---- record produced .config ----
config_out="${SOVEREIGN_OS_STATE_DIR}/kernel.config"
if ! cp .config "${config_out}"; then
  log_error "failed to record kernel .config to state dir"
  emit_metric sovereign_os_build_step_kernel_config_total 1 \
    "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"fail\""
  state_step_fail "${STEP_ID}" "config-record-failed"
  exit 1
fi
log_info "kernel config saved to ${config_out} (size: $(wc -l <"${config_out}") lines)"

# ---- emit env handoff with KCFLAGS/KCPPFLAGS from profile ----
kcflags="$(profile_field kernel.compile_flags.KCFLAGS)"
kcppflags="$(profile_field kernel.compile_flags.KCPPFLAGS)"
kbuild_user="$(profile_field kernel.compile_flags.KBUILD_BUILD_USER)"
kbuild_host="$(profile_field kernel.compile_flags.KBUILD_BUILD_HOST)"

env_file="${SOVEREIGN_OS_STATE_DIR}/env-kernel-config.sh"
cat > "${env_file}" <<EOF
# auto-generated by ${STEP_ID}
export KCFLAGS="${kcflags}"
export KCPPFLAGS="${kcppflags}"
export KBUILD_BUILD_USER="${kbuild_user:-sovereign-os}"
export KBUILD_BUILD_HOST="${kbuild_host:-sovereign-os}"
EOF
log_info "compile flags env: ${env_file}"
log_info "KCFLAGS=${kcflags}"

emit_metric sovereign_os_build_step_kernel_config_total 1 \
  "profile=\"${SOVEREIGN_OS_PROFILE}\",result=\"success\""
state_step_complete "${STEP_ID}"
log_info "step ${STEP_ID} complete"
