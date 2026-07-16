# shellcheck shell=bash
# scripts/osctl.d/version.sh — sovereign-osctl `version` verb module.
# Sourced by the main sovereign-osctl dispatcher; do not run directly.
#
# Extracted from the sovereign-osctl monolith as the first modular verb
# (F-2026-025). Depends on common.sh already being sourced and __REPO_ROOT
# being set.

_sovereign_os_version() {
  local candidate version
  local -a candidates

  if [ -n "${SOVEREIGN_OS_VERSION_FILE:-}" ]; then
    candidates=("${SOVEREIGN_OS_VERSION_FILE}")
  else
    candidates=(
      "${__REPO_ROOT}/VERSION"
      "${__REPO_ROOT}/share/VERSION"
      "/usr/local/share/sovereign-os/VERSION"
      "/usr/share/sovereign-os/VERSION"
    )
  fi

  for candidate in "${candidates[@]}"; do
    [ -r "${candidate}" ] || continue
    IFS= read -r version < "${candidate}" || {
      log_error "cannot read sovereign-os version from ${candidate}"
      return 1
    }
    if [[ "${version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$ ]]; then
      printf '%s\n' "${version}"
      return 0
    fi
    log_error "invalid sovereign-os version in ${candidate}: ${version:-<empty>}"
    return 1
  done

  log_error "sovereign-os VERSION file not found; reinstall or set SOVEREIGN_OS_VERSION_FILE"
  return 1
}

cmd_version() {
  local sovereign_version
  sovereign_version="$(_sovereign_os_version)" || return 1
  local phase="Stage-2 operator-observability + hardening complete"
  local active_profile="${SOVEREIGN_OS_PROFILE:-unknown}"
  local active_whitelabel="default"
  [ -r /etc/sovereign-os/active-whitelabel ] && \
    active_whitelabel="$(cat /etc/sovereign-os/active-whitelabel)"
  local kernel_release; kernel_release="$(uname -r)"
  local os_pretty="unknown"
  if [ -r /etc/os-release ]; then
    os_pretty="$(grep PRETTY_NAME /etc/os-release | cut -d= -f2- | tr -d '"')"
  fi

  if [ "${1:-}" = "--json" ]; then
    # Machine-readable for fleet tooling. Stable field set.
    cat <<EOF
{
  "sovereign_osctl_version": "${sovereign_version}",
  "phase": "${phase}",
  "active_profile": "${active_profile}",
  "active_whitelabel": "${active_whitelabel}",
  "kernel_release": "${kernel_release}",
  "os_pretty_name": "${os_pretty}",
  "repo": "https://github.com/cyberpunk042/sovereign-os"
}
EOF
  else
    echo "sovereign-osctl ${sovereign_version} (${phase})"
    echo "active profile:    ${active_profile}"
    echo "active whitelabel: ${active_whitelabel}"
    echo "kernel release:    ${kernel_release}"
    echo "OS:                ${os_pretty}"
  fi
}
