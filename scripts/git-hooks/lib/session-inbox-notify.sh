#!/usr/bin/env bash
# scripts/git-hooks/lib/session-inbox-notify.sh — after a pull/merge, nudge the
# current session if it has unread messages on the board (SDD-981). SOURCED, not
# executed (under lib/, never symlinked as a hook).
#
# Why: a message board only works if people SEE their mail. This surfaces the
# open-message count the instant new messages arrive via a merge, with the one
# command to read them. Silent when the inbox is empty or the session can't be
# resolved from the branch — so it only ever speaks up when there's real mail.
#
# session_inbox_notify: resolve whoami from the branch; if there are open
# messages, print a one-line nudge to stderr. Never fails the hook.

session_inbox_notify() {
  local root script who count ylw rst
  root="$(git rev-parse --show-toplevel 2>/dev/null)" || return 0
  script="${root}/scripts/git/session_comms.py"
  [ -f "${script}" ] || return 0
  command -v python3 >/dev/null 2>&1 || return 0

  who="$(python3 "${script}" whoami 2>/dev/null)" || return 0
  [ -n "${who}" ] && [ "${who}" != "unknown" ] || return 0

  # inbox exits 1 when there are OPEN messages; capture the count from its header.
  count="$(python3 "${script}" inbox --for "${who}" 2>/dev/null | sed -n '1s/.*— \([0-9]*\) open.*/\1/p')"
  [ -n "${count}" ] && [ "${count}" -gt 0 ] 2>/dev/null || return 0

  ylw=$'\033[33m'; rst=$'\033[0m'
  {
    echo ""
    echo "${ylw}✉  sovereign-os · you (${who}) have ${count} open message(s) on the board.${rst}"
    echo "${ylw}   Read: python3 scripts/git/session_comms.py inbox${rst}"
    echo ""
  } >&2
  return 0
}
