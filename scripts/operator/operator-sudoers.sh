#!/usr/bin/env bash
# scripts/operator/operator-sudoers.sh — install a SCOPED, reviewable NOPASSWD
# sudoers drop-in so the operator (and the panel APIs + the AI agent, which all
# run as the operator user) can run the SPECIFIC privileged commands the
# sovereign-os build / verify / diagnose workflows need — without a password
# prompt. This is deliberately an allow-list, never `ALL`.
#
#   ⚡ Review first (writes nothing):   scripts/operator/operator-sudoers.sh --print
#   Install:                            sudo scripts/operator/operator-sudoers.sh   (or: make operator-sudo)
#   Remove:                             sudo scripts/operator/operator-sudoers.sh --uninstall
#   Verify current state:               scripts/operator/operator-sudoers.sh --check
#
# SECURITY: NOPASSWD on any command is a real grant. The commands here are
# scoped to two buckets:
#   • diagnostics — read-only hardware/system probes (low risk)
#   • image       — loop-mount + inspect a built image (losetup/mount/umount:
#                   powerful, but needed to VERIFY an image before flashing)
# Raw `dd` and blanket `systemctl start/stop` are intentionally NOT granted —
# flashing stays the gated `sovereign-osctl install image` path you run
# deliberately. Comment out any line below you don't want. Enroll a different
# user with SOVEREIGN_OS_OPERATOR_USER=<name>.
set -euo pipefail

DEST="/etc/sudoers.d/sovereign-os-operator"
OPERATOR="${SOVEREIGN_OS_OPERATOR_USER:-${SUDO_USER:-$(id -un)}}"
# Granting NOPASSWD to root is meaningless (root already has everything). When
# the script is run DIRECTLY as root (no SUDO_USER), target the repo owner
# instead — the operator who actually runs the panels + the agent. Override
# with SOVEREIGN_OS_OPERATOR_USER=<name>.
if [ "${OPERATOR}" = "root" ] && [ -z "${SOVEREIGN_OS_OPERATOR_USER:-}" ]; then
  __repo_owner="$(stat -c '%U' "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)" 2>/dev/null || true)"
  [ -n "${__repo_owner}" ] && [ "${__repo_owner}" != "root" ] && OPERATOR="${__repo_owner}"
fi
# visudo lives in /usr/sbin — often absent from a login PATH.
VISUDO="$(command -v visudo 2>/dev/null || true)"; [ -n "${VISUDO}" ] || VISUDO="/usr/sbin/visudo"

# ── the allow-list: command name → resolved full path (absent tools skipped) ──
# diagnostics (read-only): the hardware/system probes the panels + doctor want
DIAG=(dmidecode lshw lspci lsusb lsblk nvme smartctl sensors nvidia-smi zpool zfs)
# journalctl is its OWN tier (SOVEREIGN_OS_JOURNAL) because a bare NOPASSWD
# journalctl is a GTFOBins root escape: on a tty it spawns a pager (less), and
# `!sh` in less yields a root shell. The grant forces `--no-pager` as the first
# argument so no pager is ever launched (env_reset already drops $PAGER), closing
# the escape while keeping passwordless log reads. Callers MUST pass --no-pager
# first (nothing in-repo uses `sudo journalctl`; interactive use adapts).
JOURNAL=(journalctl)
# image inspection: loop-mount a built .raw to verify it (shadow / os-release /
# boot chain) BEFORE flashing. HIGH-RISK primitives — enabled because image
# verification is the whole point; drop them if you'd rather verify only in QEMU.
IMAGE=(losetup mount umount)
# process control: panel.sh reclaims a prior (root-owned) panel server's port with
# `sudo -n kill <pid>` when an earlier `sudo` run left a server behind.
PROC=(kill)

# The cockpit CONTROL SURFACE (config/control-systems.yaml → _action_exec.py)
# executes each privileged action as `sudo -n sovereign-osctl <verb>`. Rather than
# grant sovereign-osctl WHOLESALE (which would be both too broad AND breach the
# R10212 selfdef boundary by granting `selfdef`/`perimeter`), the design (SDD-047
# Q-047-A/C) folds a SECOND, PER-VERB scoped alias — SOVEREIGN_OS_COCKPIT — for
# exactly the sovereign-os-OWNED control verbs. Its reviewed, test-verified source
# is config/sudoers.d/sovereign-os-cockpit (kept in lockstep with the registry by
# tests/lint/test_cockpit_action_exec_sudoers.py, which also proves selfdef +
# perimeter are NEVER present). We read that alias in verbatim so there is ONE
# source of truth, and grant it to the resolved operator user below.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COCKPIT_DRAFT="${REPO_ROOT}/config/sudoers.d/sovereign-os-cockpit"

resolve() {  # print full path(s) for the command: the PATH hit + its symlink target
  local c="$1" p d found=""
  # Require an ABSOLUTE path — `command -v kill` returns the shell builtin name
  # "kill" (not a path); accepting it would emit an invalid, cwd-relative rule.
  if p="$(command -v "$c" 2>/dev/null)" && [ "${p#/}" != "$p" ]; then found="$p"; fi
  if [ -z "${found}" ]; then
    # sudo-relevant tools (losetup/dmidecode/nvme…) + the operator CLIs live in
    # sbin / /usr/local/bin, often absent from a login PATH — search explicitly.
    for d in /usr/local/bin /usr/local/sbin /usr/bin /bin /usr/sbin /sbin; do
      [ -x "$d/$c" ] && { found="$d/$c"; break; }
    done
  fi
  [ -n "${found}" ] || return 0   # not found → empty output (caller skips empties)
  echo "${found}"
  # ALSO emit the canonical target: sovereign-osctl is a symlink into the repo,
  # and sudo may compare either the symlink or the resolved path — list both so
  # the rule matches regardless.
  local real; real="$(readlink -f "${found}" 2>/dev/null || true)"
  [ -n "${real}" ] && [ "${real}" != "${found}" ] && echo "${real}"
}

# Extract the reviewed SOVEREIGN_OS_COCKPIT Cmnd_Alias from the draft verbatim
# (its verb set stays in lockstep with the control registry via the lint). Emits
# nothing if the draft is absent (partial checkout) — the OPS bucket still installs.
cockpit_alias() {
  [ -f "${COCKPIT_DRAFT}" ] || return 0
  # print from the 'Cmnd_Alias SOVEREIGN_OS_COCKPIT' header through the first line
  # that does NOT end in a backslash (the alias' last continued line).
  awk '
    /^Cmnd_Alias SOVEREIGN_OS_COCKPIT/ { inblk=1 }
    inblk { print }
    inblk && !/\\[[:space:]]*$/ { exit }
  ' "${COCKPIT_DRAFT}"
}

# Resolve a bucket of command NAMES → a deduped list of absolute paths (one per
# line). resolve() may emit two lines (path + symlink target); absent tools emit
# nothing (caller skips them). Kept separate per bucket so each risk tier gets its
# own Cmnd_Alias — the /etc/sudoers.d file then self-documents what is low-risk
# (read-only probes) vs HIGH-RISK (loop-mount) vs process-control.
_resolve_bucket() {
  local c p p2 dup out=()
  for c in "$@"; do
    while IFS= read -r p; do
      [ -n "$p" ] || continue
      dup=0; for p2 in "${out[@]:-}"; do [ "$p" = "$p2" ] && { dup=1; break; }; done
      [ "$dup" = 0 ] && out+=("$p")
    done < <(resolve "$c")
  done
  [ "${#out[@]}" -eq 0 ] || printf '%s\n' "${out[@]}"
}

build_body() {
  echo "# sovereign-os operator NOPASSWD allow-list"
  echo "# generated by scripts/operator/operator-sudoers.sh — DO NOT hand-edit"
  echo "# (re-run the script to regenerate; edit the script's allow-list instead)"
  echo "# operator: ${OPERATOR}"
  # Three RISK-TIERED Cmnd_Aliases (SDD-1000) instead of one opaque bucket, so the
  # drop-in is self-auditing: a reviewer sees exactly which grants are read-only
  # vs powerful. `tests/lint/test_operator_sudoers.py` locks the reviewed command
  # set of each tier and forbids any privilege-escalating binary from appearing.
  local diag image proc journal grants=()
  diag="$(_resolve_bucket "${DIAG[@]}")"
  image="$(_resolve_bucket "${IMAGE[@]}")"
  proc="$(_resolve_bucket "${PROC[@]}")"
  journal="$(_resolve_bucket "${JOURNAL[@]}")"
  if [ -z "${diag}${image}${proc}${journal}" ]; then
    echo "# (no allow-listed commands found on PATH)" >&2
    return 1
  fi
  _alias() {  # _alias <NAME> <comment> <newline-separated-paths>
    [ -n "$3" ] || return 0
    local joined; joined="$(printf '%s, ' $3)"; joined="${joined%, }"
    echo "# $2"
    echo "Cmnd_Alias $1 = ${joined}"
    grants+=("$1")
  }
  # journalctl: each resolved path becomes ONE sudoers Cmnd `<path> --no-pager *`
  # (forced first arg) — a dedicated emitter because the entry carries internal
  # spaces (the `_alias` join splits on space) and a literal `*` that must NOT
  # be glob-expanded. Assignments below are quoted, so the `*` stays literal.
  _journal_alias() {  # _journal_alias <newline-separated-paths>
    [ -n "$1" ] || return 0
    local line joined=""
    while IFS= read -r line; do
      [ -n "${line}" ] || continue
      joined="${joined}${line} --no-pager *, "
    done <<< "$1"
    joined="${joined%, }"
    echo "# journal reads, pager-escape-guarded (forced --no-pager)"
    echo "Cmnd_Alias SOVEREIGN_OS_JOURNAL = ${joined}"
    grants+=("SOVEREIGN_OS_JOURNAL")
  }
  _alias SOVEREIGN_OS_DIAG  "read-only hardware/system diagnostics (low risk)" "${diag}"
  _journal_alias "${journal}"
  _alias SOVEREIGN_OS_IMAGE "HIGH-RISK: loop-mount + inspect a built image before flashing" "${image}"
  _alias SOVEREIGN_OS_PROC  "process control: reclaim a prior root-owned panel server's port" "${proc}"
  # second surface: the per-verb cockpit control aliases (R10212-safe — selfdef +
  # perimeter absent by construction). Folded from the reviewed draft.
  local cockpit; cockpit="$(cockpit_alias)"
  if [ -n "${cockpit}" ]; then
    echo ""
    echo "${cockpit}"
    grants+=("SOVEREIGN_OS_COCKPIT")
  fi
  local grant_list; grant_list="$(printf '%s, ' "${grants[@]}")"; grant_list="${grant_list%, }"
  echo "${OPERATOR} ALL=(root) NOPASSWD: ${grant_list}"
}

cmd_print() { build_body; }

cmd_check() {
  if [ -f "${DEST}" ]; then
    echo "installed: ${DEST}"
    echo "  operator: $(grep -oE '^[a-zA-Z0-9_-]+ ALL=' "${DEST}" 2>/dev/null | awk '{print $1}' | head -1)"
    echo "  commands: $(grep -c ',' "${DEST}" 2>/dev/null || echo '?') allow-listed"
    sudo -n -l >/dev/null 2>&1 && echo "  ✓ NOPASSWD active for the current user" || echo "  (run as the operator to test NOPASSWD)"
  else
    echo "not installed (${DEST} absent) — run: sudo $0"
  fi
}

cmd_install() {
  [ "$(id -u)" -eq 0 ] || { echo "install needs root: sudo $0" >&2; exit 2; }
  local tmp; tmp="$(mktemp)"
  build_body > "${tmp}"
  # validate BEFORE placing it — a broken sudoers drop-in can lock out sudo
  if ! "${VISUDO}" -cf "${tmp}" >/dev/null 2>&1; then
    echo "✗ generated sudoers failed visudo validation — not installing:" >&2
    "${VISUDO}" -cf "${tmp}" >&2 || true
    rm -f "${tmp}"; exit 1
  fi
  if [ -f "${DEST}" ] && cmp -s "${tmp}" "${DEST}"; then
    echo "✓ already current: ${DEST}"; rm -f "${tmp}"; return 0
  fi
  install -m 0440 -o root -g root "${tmp}" "${DEST}"
  rm -f "${tmp}"
  # final belt-and-suspenders: validate the whole sudoers tree
  "${VISUDO}" -c >/dev/null 2>&1 && echo "✓ installed + validated: ${DEST} (operator=${OPERATOR})" \
    || { echo "✗ sudoers tree invalid after install — removing" >&2; rm -f "${DEST}"; exit 1; }
}

cmd_uninstall() {
  [ "$(id -u)" -eq 0 ] || { echo "uninstall needs root: sudo $0 --uninstall" >&2; exit 2; }
  rm -f "${DEST}" && echo "✓ removed ${DEST}"
}

case "${1:-install}" in
  --print|print)         cmd_print ;;
  --check|check)         cmd_check ;;
  --uninstall|uninstall) cmd_uninstall ;;
  ""|--install|install)  cmd_install ;;
  -h|--help)             grep '^#' "$0" | sed 's/^# \{0,1\}//' ;;
  *) echo "usage: $0 [--print|--install|--uninstall|--check]" >&2; exit 2 ;;
esac
