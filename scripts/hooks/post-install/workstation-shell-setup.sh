#!/usr/bin/env bash
# scripts/hooks/post-install/workstation-shell-setup.sh
#
# Lightweight workstation shell sweetening. Mixin: role-workstation.
# Operator-uncontroversial defaults: bash-completion enabled,
# /etc/skel touch-ups, common dotfile baselines. Idempotent.

__SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
__REPO_ROOT="$(cd "${__SCRIPT_DIR}/../../.." && pwd)"
# shellcheck source=../../build/lib/common.sh
. "${__REPO_ROOT}/scripts/build/lib/common.sh"
# shellcheck source=../../build/lib/observability.sh
. "${__REPO_ROOT}/scripts/build/lib/observability.sh"

STEP_ID="workstation-shell-setup"

log_step_header "${STEP_ID}" "workstation shell defaults"

require_root

# Enable bash-completion globally if installed
if [ -f /etc/bash_completion ] && ! grep -q "bash_completion" /etc/profile 2>/dev/null; then
  cat >> /etc/profile.d/30-sovereign-bashcompletion.sh <<'EOF'
# sovereign-os: enable bash-completion globally for workstation profiles
if ! shopt -oq posix; then
  if [ -f /usr/share/bash-completion/bash_completion ]; then
    . /usr/share/bash-completion/bash_completion
  elif [ -f /etc/bash_completion ]; then
    . /etc/bash_completion
  fi
fi
EOF
  log_info "  bash-completion enabled via /etc/profile.d/"
fi

# /etc/skel baselines (only writes if file absent — never overwrites)
mkdir -p /etc/skel

if [ ! -f /etc/skel/.bash_aliases ]; then
  cat > /etc/skel/.bash_aliases <<'EOF'
# sovereign-os workstation default aliases
alias ll='ls -lhF'
alias la='ls -lAhF'
alias gs='git status'
alias gd='git diff'
alias gl='git log --oneline -20'
EOF
  log_info "  installed /etc/skel/.bash_aliases"
fi

if [ ! -f /etc/skel/.inputrc ]; then
  cat > /etc/skel/.inputrc <<'EOF'
# sovereign-os workstation default readline config
set completion-ignore-case on
set show-all-if-ambiguous on
set colored-stats on
EOF
  log_info "  installed /etc/skel/.inputrc"
fi

emit_metric sovereign_os_post_install_shell_setup_total 1 \
  "result=\"configured\""
log_info "${STEP_ID} complete"
