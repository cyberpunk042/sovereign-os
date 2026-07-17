# shellcheck shell=bash
# scripts/osctl.d/assistant.sh — sovereign-osctl `assistant` verb module (F-2026-025).
# Sourced by the main sovereign-osctl dispatcher; do not run directly.
#
# operator assistant helper.
# Extracted verbatim from the sovereign-osctl monolith — behavior is
# byte-identical (same shell, same globals: __REPO_ROOT / PYTHON3 /
# log_* / common.sh helpers are all resident before dispatch sources this).

cmd_assistant() {
  local sub="${1:-full}"
  shift || true
  case "${sub}" in
    full)
      # Re-run the entire first-login-assistant flow
      SOVEREIGN_OS_ASSISTANT_FORCE=1 "${__REPO_ROOT}/scripts/hooks/post-install/first-login-assistant.sh"
      ;;
    status)
      # Read the persisted assistant state if present
      local state_file="${SOVEREIGN_OS_ASSISTANT_STATE_DIR:-/var/lib/sovereign-os/assistant}/state.yaml"
      if [ -r "${state_file}" ]; then
        echo "Assistant state at ${state_file}:"
        echo
        cat "${state_file}"
      else
        echo "Assistant has not been run yet (no state at ${state_file})"
      fi
      ;;
    reset)
      local state_file="${SOVEREIGN_OS_ASSISTANT_STATE_DIR:-/var/lib/sovereign-os/assistant}/state.yaml"
      if [ "${SOVEREIGN_OS_ASSUME_YES:-}" != "1" ]; then
        if ! confirm "Reset assistant state at ${state_file}?" default-no; then
          log_info "reset cancelled"
          return 0
        fi
      fi
      rm -f "${state_file}"
      log_info "assistant state cleared; next run will execute full flow"
      ;;
    list)
      cat <<EOF
Assistant subverbs:
  full        Re-run the complete first-login assistant flow (default)
  status      Show persisted state.yaml (when did it run? what choices?)
  reset       Clear state.yaml (next run executes full flow)
  list        This list.

Env vars (consumed by the underlying first-login-assistant.sh):
  SOVEREIGN_OS_NONINTERACTIVE    skip prompts (use defaults)
  SOVEREIGN_OS_ASSISTANT_FORCE   ignore completed:true sentinel
EOF
      ;;
    *)
      log_error "unknown assistant subcommand: ${sub}"
      log_error "  available: full / status / reset / list"
      exit 2
      ;;
  esac
}
