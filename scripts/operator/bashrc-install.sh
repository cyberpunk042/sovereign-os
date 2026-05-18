#!/usr/bin/env bash
# scripts/operator/bashrc-install.sh — operator-discoverable bashrc
# integration (autocompletes + aliases + helper menus) per E11.M6
# (operator §1g verbatim: "the bashrc we can offer to configure it too
# and we can add our autocompletes and aliases and manual / helps and
# menus").
#
# Idempotent + reversible:
#   sovereign-osctl bashrc install   — writes a self-contained block
#                                       to ~/.bashrc bounded by sentinel
#                                       comments; idempotent re-run
#                                       updates the block in place
#   sovereign-osctl bashrc uninstall — removes the sentinel-bounded block
#   sovereign-osctl bashrc status    — reports whether the block is
#                                       present + which version
#   sovereign-osctl bashrc dump      — print the block contents to stdout
#                                       (operator-discoverable; pipe to
#                                        a different shell rc file)
#
# Env vars (all overridable):
#   SOVEREIGN_OS_BASHRC_PATH    Target rc file (default: ~/.bashrc)
#                                Set to ~/.zshrc for zsh integration.
#   SOVEREIGN_OS_BASHRC_VERSION Pin version (default: matches block VERSION below)
#   SOVEREIGN_OS_DRY_RUN        Logs intent; doesn't mutate rc file
#
# Layer B metric (SDD-016):
#   sovereign_os_operator_bashrc_install_total{action,result}
#
# Anti-corruption: the sentinel pattern lets the operator extend the
# block manually OUTSIDE the sentinels — those edits survive every
# install/uninstall cycle.

set -euo pipefail

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh" 2>/dev/null || true
# shellcheck source=../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh" 2>/dev/null || true

# Fallback log helpers if lib not sourceable
type log_info >/dev/null 2>&1 || log_info() { echo "INFO  [bashrc] $*"; }
type log_warn >/dev/null 2>&1 || log_warn() { echo "WARN  [bashrc] $*"; }
type log_error >/dev/null 2>&1 || log_error() { echo "ERROR [bashrc] $*" >&2; }
type emit_metric >/dev/null 2>&1 || emit_metric() { :; }

: "${SOVEREIGN_OS_BASHRC_PATH:=${HOME}/.bashrc}"
: "${SOVEREIGN_OS_BASHRC_VERSION:=1}"

# Sentinels — bound the operator-mutable block
SENTINEL_BEGIN="# >>> sovereign-os bashrc-integration BEGIN (managed by sovereign-osctl bashrc) >>>"
SENTINEL_END="# <<< sovereign-os bashrc-integration END (managed by sovereign-osctl bashrc) <<<"

emit_bashrc_metric() {
  emit_metric sovereign_os_operator_bashrc_install_total 1 \
    "action=\"$1\",result=\"$2\""
}

# Generate the block content
generate_block() {
  cat <<EOF
${SENTINEL_BEGIN}
# Version: ${SOVEREIGN_OS_BASHRC_VERSION}
# Generated: \$(date -u --iso-8601=seconds 2>/dev/null || date)
# DO NOT EDIT INSIDE THIS BLOCK — rerun \`sovereign-osctl bashrc install\`
# to refresh. Edits OUTSIDE the sentinels survive install/uninstall.
#
# E11.M6 (operator §1g verbatim — autocompletes + aliases + manual/helps).

# Aliases (operator-discoverable short-forms)
alias sosctl='sovereign-osctl'
alias soshelp='sovereign-osctl help'
alias sosstatus='sovereign-osctl status'
alias sosmodels='sovereign-osctl models list'
alias soshealth='sovereign-osctl autohealth'
alias sosdoctor='sovereign-osctl doctor'
alias sosthermal='sovereign-osctl thermals'
alias soswatt='sovereign-osctl gpu-wattage'
alias soshist='sovereign-osctl history'
alias sosmorning='sovereign-osctl morning-brief rollup'

# Quick-help menu (operator-runnable: type \`soshelp-menu\`)
soshelp-menu() {
  cat <<'MENU'
sovereign-osctl quick-help menu:

  Operator-pull intelligence:
    sosmorning          — morning brief rollup (R352)
    sosstatus           — system state overview
    sosdoctor           — sanity checks
    soshealth           — autohealth severity
    sosthermal          — thermal sample

  Models + inference:
    sosmodels           — list resident models
    sovereign-osctl trinity status
    sovereign-osctl inference router-status

  Hardware + power:
    soswatt             — GPU wattage tracking
    sovereign-osctl gpu-watch
    sovereign-osctl cpu-mode

  Modules + features:
    sovereign-osctl modules list
    sovereign-osctl features
    sovereign-osctl install

  Configuration + history:
    sovereign-osctl env
    soshist             — global history (delta/diff)
    sovereign-osctl events

  Full surface:
    soshelp             — full help text
MENU
}

# Bash completion — operator-discoverable subcommand tab-complete
_sovereign_osctl_complete() {
  local cur prev opts
  COMPREPLY=()
  cur="\${COMP_WORDS[COMP_CWORD]}"
  prev="\${COMP_WORDS[COMP_CWORD-1]}"

  # Top-level subcommands (derived from osctl dispatcher)
  if [[ \${COMP_CWORD} -eq 1 ]]; then
    opts="status overview doctor assistant profiles whitelabel \\
          perimeter models audit maintenance metrics journal \\
          history thermals alerts env init trinity wizard \\
          bootstrap secure-boot install hooks decommission \\
          inference version help bashrc autohealth dashboard \\
          guide morning-brief next-action coverage doctrine-status \\
          architecture-qa repl layers search verbatim-render \\
          quarterly-review ccd-pinning state-fabric network-topology"
    COMPREPLY=( \$(compgen -W "\${opts}" -- "\${cur}") )
    return 0
  fi

  # 2nd-level subcommands (per top-level)
  case "\${COMP_WORDS[1]}" in
    profiles)
      opts="list show show-effective compare fork active switch validate"
      COMPREPLY=( \$(compgen -W "\${opts}" -- "\${cur}") )
      ;;
    whitelabel)
      opts="show apply list diff"
      COMPREPLY=( \$(compgen -W "\${opts}" -- "\${cur}") )
      ;;
    perimeter)
      opts="status verify reload"
      COMPREPLY=( \$(compgen -W "\${opts}" -- "\${cur}") )
      ;;
    models)
      opts="list pull verify remove size info query suggest docs \\
            eval toolchains fine-tune"
      COMPREPLY=( \$(compgen -W "\${opts}" -- "\${cur}") )
      ;;
    morning-brief)
      opts="rollup status modules"
      COMPREPLY=( \$(compgen -W "\${opts}" -- "\${cur}") )
      ;;
    bashrc)
      opts="install uninstall status dump"
      COMPREPLY=( \$(compgen -W "\${opts}" -- "\${cur}") )
      ;;
  esac
}
complete -F _sovereign_osctl_complete sovereign-osctl sosctl
${SENTINEL_END}
EOF
}

# CLI dispatcher
case "${1:-status}" in
  install)
    if [ ! -f "${SOVEREIGN_OS_BASHRC_PATH}" ]; then
      log_info "creating ${SOVEREIGN_OS_BASHRC_PATH} (didn't exist)"
      if [ -z "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
        touch "${SOVEREIGN_OS_BASHRC_PATH}"
      fi
    fi

    # Remove any existing block (idempotent)
    if grep -qF "${SENTINEL_BEGIN}" "${SOVEREIGN_OS_BASHRC_PATH}" 2>/dev/null; then
      log_info "existing sovereign-os block found — replacing"
      if [ -z "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
        # Delete from BEGIN to END inclusive
        sed -i.sovereign-os-bak \
          "/$(printf '%s' "${SENTINEL_BEGIN}" | sed 's/[]\/$*.^[]/\\&/g')/,/$(printf '%s' "${SENTINEL_END}" | sed 's/[]\/$*.^[]/\\&/g')/d" \
          "${SOVEREIGN_OS_BASHRC_PATH}"
      fi
    fi

    if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
      log_info "DRY-RUN — would append block to ${SOVEREIGN_OS_BASHRC_PATH}"
      emit_bashrc_metric install dry-run
      exit 0
    fi

    # Append the new block
    echo "" >> "${SOVEREIGN_OS_BASHRC_PATH}"
    generate_block >> "${SOVEREIGN_OS_BASHRC_PATH}"
    log_info "installed bashrc integration to ${SOVEREIGN_OS_BASHRC_PATH}"
    log_info "  open a new shell OR run: source ${SOVEREIGN_OS_BASHRC_PATH}"
    log_info "  then try: soshelp-menu"
    emit_bashrc_metric install success
    ;;

  uninstall)
    if [ ! -f "${SOVEREIGN_OS_BASHRC_PATH}" ]; then
      log_warn "${SOVEREIGN_OS_BASHRC_PATH} doesn't exist; nothing to uninstall"
      emit_bashrc_metric uninstall skip-no-file
      exit 0
    fi
    if ! grep -qF "${SENTINEL_BEGIN}" "${SOVEREIGN_OS_BASHRC_PATH}"; then
      log_info "no sovereign-os block present; nothing to uninstall"
      emit_bashrc_metric uninstall skip-no-block
      exit 0
    fi

    if [ -n "${SOVEREIGN_OS_DRY_RUN:-}" ]; then
      log_info "DRY-RUN — would remove block from ${SOVEREIGN_OS_BASHRC_PATH}"
      emit_bashrc_metric uninstall dry-run
      exit 0
    fi

    sed -i.sovereign-os-bak \
      "/$(printf '%s' "${SENTINEL_BEGIN}" | sed 's/[]\/$*.^[]/\\&/g')/,/$(printf '%s' "${SENTINEL_END}" | sed 's/[]\/$*.^[]/\\&/g')/d" \
      "${SOVEREIGN_OS_BASHRC_PATH}"
    log_info "uninstalled bashrc integration from ${SOVEREIGN_OS_BASHRC_PATH}"
    log_info "  backup saved at ${SOVEREIGN_OS_BASHRC_PATH}.sovereign-os-bak"
    emit_bashrc_metric uninstall success
    ;;

  status)
    if [ ! -f "${SOVEREIGN_OS_BASHRC_PATH}" ]; then
      echo "absent (target rc file ${SOVEREIGN_OS_BASHRC_PATH} doesn't exist)"
      emit_bashrc_metric status absent
      exit 0
    fi
    if grep -qF "${SENTINEL_BEGIN}" "${SOVEREIGN_OS_BASHRC_PATH}"; then
      local_version=$(grep -A 1 "${SENTINEL_BEGIN}" "${SOVEREIGN_OS_BASHRC_PATH}" \
                       | grep "Version:" | awk '{print $NF}' || echo "?")
      echo "installed (rc=${SOVEREIGN_OS_BASHRC_PATH}, version=${local_version})"
      emit_bashrc_metric status installed
    else
      echo "absent (rc=${SOVEREIGN_OS_BASHRC_PATH}, sentinel not present)"
      emit_bashrc_metric status absent
    fi
    ;;

  dump)
    generate_block
    emit_bashrc_metric dump success
    ;;

  --help|-h|help|"")
    cat <<'HELP'
sovereign-osctl bashrc — operator-discoverable bashrc integration

USAGE:
  sovereign-osctl bashrc <subcommand> [options]

SUBCOMMANDS:
  install     Install the sovereign-os bashrc block (idempotent;
              re-running updates the block in place)
  uninstall   Remove the sovereign-os bashrc block (keeps a .sovereign-os-bak
              backup of the previous rc file)
  status      Report whether the block is installed + its version
  dump        Print the block contents to stdout (pipe to a different
              rc file like ~/.zshrc for zsh integration)
  help        Show this message

ENV VARS:
  SOVEREIGN_OS_BASHRC_PATH    target rc file (default: ~/.bashrc;
                              set to ~/.zshrc for zsh)
  SOVEREIGN_OS_BASHRC_VERSION pin version (default: matches block)
  SOVEREIGN_OS_DRY_RUN        preview only; no mutation

WHAT THE BLOCK PROVIDES:
  • 10 operator-discoverable aliases (sosctl, soshelp, sosstatus,
    sosmodels, soshealth, sosdoctor, sosthermal, soswatt, soshist,
    sosmorning)
  • Quick-help menu function: type `soshelp-menu` to see categorized
    command groupings
  • Tab-completion for sovereign-osctl + sosctl subcommands

OPERATOR-ANTI-CORRUPTION:
  The block is bounded by sentinel comments. Edits OUTSIDE the
  sentinels (your own aliases, exports, etc.) survive every
  install/uninstall cycle.

E11.M6 (operator §1g 2026-05-18 verbatim — autocompletes + aliases +
manual/helps + menus).
HELP
    ;;

  *)
    log_error "unknown bashrc subcommand: $1"
    exec "$0" help
    ;;
esac
