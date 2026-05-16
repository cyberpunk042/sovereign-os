#!/usr/bin/env bash
# scripts/hooks/post-install/first-login-assistant.sh
#
# Operator-stated requirement (verbatim, sacrosanct):
#   "post install script ready to be pre-added or even automatically
#    launch on first login and such. based on what is chosen by the
#    user."
#
# Q-018 implementation: interactive TUI flow surfacing post-install
# choices. Honors SOVEREIGN_OS_NONINTERACTIVE for unattended installs
# (skips prompts; uses defaults). Idempotent — running a second time
# detects already-applied state.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"

STEP_ID="first-login-assistant"

: "${SOVEREIGN_OS_PROFILE:=sain-01}"
load_profile "${SOVEREIGN_OS_PROFILE}"

: "${SOVEREIGN_OS_ASSISTANT_STATE_DIR:=/var/lib/sovereign-os/assistant}"
mkdir -p "${SOVEREIGN_OS_ASSISTANT_STATE_DIR}"

log_step_header "${STEP_ID}" "first-login assistant"

state_file="${SOVEREIGN_OS_ASSISTANT_STATE_DIR}/state.yaml"

# Skip if already-completed and not forced
if [ -f "${state_file}" ] && grep -q "completed: true" "${state_file}" && [ -z "${SOVEREIGN_OS_ASSISTANT_FORCE:-}" ]; then
  log_info "first-login assistant already completed (state at ${state_file})"
  log_info "  re-run with SOVEREIGN_OS_ASSISTANT_FORCE=1 to repeat"
  exit 0
fi

# ---- welcome ----
cat <<EOF

╔════════════════════════════════════════════════════════════════════╗
║                                                                    ║
║   Welcome to sovereign-os — first-login assistant                  ║
║                                                                    ║
║   Profile: ${SOVEREIGN_OS_PROFILE}
║                                                                    ║
║   This assistant walks through post-install customization. Each   ║
║   step is opt-in; you can skip anything and re-run later via       ║
║   'sovereign-osctl assistant'.                                     ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝

EOF

# ---- track choices ----
declare -A choices=()

# Hostname
default_hostname="${SOVEREIGN_OS_PROFILE}"
current_hostname="$(hostnamectl hostname 2>/dev/null || hostname)"
if [ "${current_hostname}" != "${default_hostname}" ] && [ "${current_hostname}" != "localhost" ]; then
  default_hostname="${current_hostname}"
fi

if confirm "Set hostname to '${default_hostname}'?" default-yes; then
  if [ -n "${SOVEREIGN_OS_NONINTERACTIVE:-}" ]; then
    new_hostname="${default_hostname}"
  else
    read -rp "Hostname [${default_hostname}]: " new_hostname
    new_hostname="${new_hostname:-${default_hostname}}"
  fi
  if [ "$(id -u)" -eq 0 ]; then
    # hostnamectl requires systemd as PID 1; containers / chroots
    # don't have that — fall back to /etc/hostname write in that case.
    if command -v hostnamectl >/dev/null 2>&1 && hostnamectl set-hostname "${new_hostname}" 2>/dev/null; then
      choices[hostname]="${new_hostname}"
      log_info "  hostname set to ${new_hostname} (via hostnamectl)"
    elif [ -w /etc/hostname ] || [ -w /etc ]; then
      echo "${new_hostname}" > /etc/hostname
      choices[hostname]="${new_hostname}"
      log_info "  hostname written to /etc/hostname (hostnamectl unavailable — container/chroot?)"
    else
      log_warn "  could not set hostname (no hostnamectl + /etc not writable)"
      choices[hostname]="unchanged"
    fi
  else
    log_warn "  not root — hostname change skipped (re-run with sudo)"
    choices[hostname]="skipped-no-root"
  fi
fi

# GPU driver enable
if profile_field hardware.gpu | grep -q nvidia; then
  if confirm "Enable NVIDIA driver for primary GPU?" default-yes; then
    if command -v nvidia-modprobe >/dev/null 2>&1; then
      nvidia-modprobe || log_warn "nvidia-modprobe failed"
    fi
    choices[nvidia_driver]="enabled"
  fi
fi

# Model catalog pick (placeholder; full Q-017 + E110 integration is Stage 2+)
if confirm "Pre-pull a default LLM model into tank/models?" default-no; then
  log_info "  → model catalog sync would run here (Stage 2+ integration)"
  log_info "  → for now, run 'sovereign-osctl models pull <id>' manually"
  choices[model_pull]="deferred"
fi

# Tetragon policy verify
if confirm "Verify Tetragon sovereign-kernel-fence policy is loaded?" default-yes; then
  if command -v tetragon >/dev/null 2>&1 && systemctl is-active --quiet tetragon; then
    log_info "  ✓ tetragon active"
    choices[tetragon]="active"
  else
    log_warn "  ✗ tetragon not active; run 'sovereign-osctl perimeter verify' to diagnose"
    choices[tetragon]="inactive"
  fi
fi

# Whitelabel surfaces sanity check
if confirm "Verify whitelabel surfaces (e.g. /etc/os-release matches profile)?" default-yes; then
  if [ -r /etc/os-release ] && grep -q "sovereign" /etc/os-release; then
    log_info "  ✓ /etc/os-release contains sovereign-os branding"
    choices[whitelabel]="applied"
  else
    log_warn "  ✗ /etc/os-release does NOT contain sovereign-os branding; whitelabel may not be applied"
    choices[whitelabel]="missing"
  fi
fi

# ---- write state ----
cat > "${state_file}" <<EOF
# auto-generated by sovereign-os first-login assistant
completed: true
completed_at: "$(date -u --iso-8601=seconds)"
profile: "${SOVEREIGN_OS_PROFILE}"
choices:
EOF
for k in "${!choices[@]}"; do
  printf '  %s: "%s"\n' "${k}" "${choices[$k]}" >> "${state_file}"
done

log_info "state written: ${state_file}"

cat <<EOF

╔════════════════════════════════════════════════════════════════════╗
║                                                                    ║
║   Assistant complete. Next steps:                                  ║
║                                                                    ║
║     sovereign-osctl status         — see system state              ║
║     sovereign-osctl models list    — manage model catalog          ║
║     sovereign-osctl perimeter      — manage Tetragon policy        ║
║     sovereign-osctl whitelabel     — manage whitelabel             ║
║                                                                    ║
║   Run 'sovereign-osctl assistant' anytime to revisit.              ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝

EOF

log_info "${STEP_ID} complete"
