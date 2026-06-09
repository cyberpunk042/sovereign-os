#!/usr/bin/env bash
# scripts/hooks/post-install/nvidia-driver-bind.sh
#
# Ensure NVIDIA driver loads cleanly + blacklists nouveau. Idempotent.
# Used by old-workstation and any non-VFIO NVIDIA profile.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

STEP_ID="nvidia-driver-bind"

log_step_header "${STEP_ID}" "ensure nvidia driver + nouveau blacklisted"

require_root

# Blacklist nouveau
if [ ! -f /etc/modprobe.d/blacklist-nouveau.conf ]; then
  cat > /etc/modprobe.d/blacklist-nouveau.conf <<'EOF'
# sovereign-os: nouveau replaced by nvidia driver
blacklist nouveau
options nouveau modeset=0
EOF
  log_info "  blacklisted nouveau"
fi

# Update initramfs so the blacklist applies at boot
if command -v update-initramfs >/dev/null 2>&1; then
  update-initramfs -u 2>&1 | sed 's/^/  /' || log_warn "update-initramfs failed"
fi

# Check nvidia driver
if command -v nvidia-smi >/dev/null 2>&1; then
  if nvidia-smi >/dev/null 2>&1; then
    log_info "  nvidia driver active (nvidia-smi succeeds)"
  else
    log_warn "  nvidia-smi exists but doesn't run cleanly — driver may need post-install module rebuild + reboot"
  fi
fi

emit_metric sovereign_os_post_install_nvidia_bind_total 1 \
  "result=\"configured\""
log_info "${STEP_ID} complete"
