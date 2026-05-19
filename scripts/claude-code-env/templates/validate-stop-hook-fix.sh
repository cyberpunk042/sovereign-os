#!/usr/bin/env bash
# ~/.claude/validate-stop-hook-fix.sh
#
# Validation mechanism for the env-runner stop-hook-restage fix +
# the other operator-tunable long-session caps.
# Info-hub lesson:
#  wiki/lessons/01_drafts/claude-code-env-runner-restages-stop-hook-script-
#  from-baked-template-at-every-session-start.md
#
# Checks performed:
#   1. ~/.claude/settings.json has explicit empty Stop + SubagentStop arrays
#      ("hooks": { "Stop": [], "SubagentStop": [] }) — defeats template merge.
#   2. ~/.claude/stop-hook-git-check.sh is neutralized (script body emits
#      exit 0 on synthetic input AND source has no `exit 2` paths).
#   3. CLAUDE_CODE_STOP_HOOK_BLOCK_CAP is ≥1000 in settings.json.
#   4. CLAUDE_CODE_MAX_TURNS is set (≥10000 recommended) — prevents
#      `max_turns` stop-reason cutting long sessions short.
#   5. DISABLE_AUTOCOMPACT=1 is set — auto-compact is DISABLED per
#      operator directive (verbatim, recurring): auto-compact must be
#      off, not throttled. Setting CLAUDE_CODE_AUTO_COMPACT_WINDOW to a
#      large value only delays compaction; the correct posture is
#      disable.
#
# Note on `rapid_refill_breaker` stop-reason: service-side rate limit;
# `CLAUDE_CODE_RATE_LIMIT_TIER` is observation-only, not client-tunable.
# This validator does NOT check it.
#
# Exit codes:
#   0 — all checks pass
#   1 — at least one check failed (full report on stderr)
#   2 — settings.json unreadable / jq unavailable / structural error
#
# Usage:
#   ~/.claude/validate-stop-hook-fix.sh                   # human report
#   ~/.claude/validate-stop-hook-fix.sh --json            # JSON report
#   ~/.claude/validate-stop-hook-fix.sh --quiet           # exit-code only
#
# Suggested SessionStart hook wiring (in ~/.claude/settings.json):
#   "SessionStart": [{ "hooks": [{ "type": "command",
#       "command": "$HOME/.claude/validate-stop-hook-fix.sh --quiet" }] }]

set -uo pipefail

readonly SETTINGS="${HOME}/.claude/settings.json"
readonly ORPHAN="${HOME}/.claude/stop-hook-git-check.sh"
readonly REQUIRED_CAP=1000
readonly RECOMMENDED_MAX_TURNS=10000

mode="human"
quiet=false
for arg in "$@"; do
  case "${arg}" in
    --json) mode="json" ;;
    --quiet) quiet=true ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "unknown arg: ${arg}" >&2; exit 2 ;;
  esac
done

# Pre-flight: jq required for settings.json structural check.
if ! command -v jq >/dev/null 2>&1; then
  echo "FATAL: jq not in PATH — required for settings.json structural check" >&2
  exit 2
fi

# Pre-flight: settings.json must exist + be valid JSON.
if [ ! -r "${SETTINGS}" ]; then
  echo "FATAL: ${SETTINGS} not readable" >&2
  exit 2
fi
if ! jq -e . "${SETTINGS}" >/dev/null 2>&1; then
  echo "FATAL: ${SETTINGS} is not valid JSON" >&2
  exit 2
fi

# --- Check 1: settings.json has explicit empty Stop + SubagentStop arrays ---
check1_pass=false
check1_detail=""
if jq -e '.hooks.Stop == [] and .hooks.SubagentStop == []' \
       "${SETTINGS}" >/dev/null 2>&1; then
  check1_pass=true
  check1_detail="explicit empty arrays defeat any template merge"
else
  stop=$(jq -r '.hooks.Stop // "MISSING"' "${SETTINGS}" 2>&1)
  sub=$(jq -r '.hooks.SubagentStop // "MISSING"'  "${SETTINGS}" 2>&1)
  check1_detail="Stop=${stop} SubagentStop=${sub} (expected [] for both)"
fi

# --- Check 2: stop-hook-git-check.sh is neutralized ---
check2_pass=false
check2_detail=""
if [ ! -e "${ORPHAN}" ]; then
  check2_pass=true
  check2_detail="script absent (env-runner will re-stage on next session start; OK)"
elif ! [ -x "${ORPHAN}" ]; then
  check2_pass=true
  check2_detail="script present but not executable — inert"
else
  # Run with synthetic input; capture exit code WITHOUT using if-condition
  # (which clobbers $? to the if-condition's value, not the actual exit).
  set +e
  echo '{"stop_hook_active": false}' | "${ORPHAN}" >/dev/null 2>&1
  actual_exit=$?
  set -e
  set +u  # next operations are safe; -u re-enabled at exit
  if [ "${actual_exit}" != "0" ]; then
    check2_pass=false
    check2_detail="script returned exit=${actual_exit} on synthetic input — would block Stop"
  else
    # Source-scan for `exit 2` lines (the original template's pattern).
    if grep -qE "^[[:space:]]*exit 2\b" "${ORPHAN}" 2>/dev/null; then
      check2_pass=false
      check2_detail="script returned 0 on synthetic input BUT body contains 'exit 2' — would fire on real dirty git state"
    else
      check2_pass=true
      check2_detail="script returns 0 + body has no 'exit 2' code paths"
    fi
  fi
  set -u
fi

# --- Check 3: CLAUDE_CODE_STOP_HOOK_BLOCK_CAP ≥1000 ---
check3_pass=false
check3_detail=""
configured_cap=$(jq -r '.env.CLAUDE_CODE_STOP_HOOK_BLOCK_CAP // ""' \
                  "${SETTINGS}" 2>&1)
live_cap="${CLAUDE_CODE_STOP_HOOK_BLOCK_CAP:-}"
if [ -n "${configured_cap}" ] && \
   [ "${configured_cap}" -ge "${REQUIRED_CAP}" ] 2>/dev/null; then
  check3_pass=true
  check3_detail="configured=${configured_cap} (≥${REQUIRED_CAP})"
  if [ -n "${live_cap}" ] && [ "${live_cap}" != "${configured_cap}" ]; then
    check3_detail="${check3_detail}; WARN live env=${live_cap} differs — settings cached from earlier"
  fi
else
  check3_detail="configured=${configured_cap:-MISSING}; live=${live_cap:-unset}; expected ≥${REQUIRED_CAP}"
fi

# --- Check 4: CLAUDE_CODE_MAX_TURNS set ≥10000 ---
check4_pass=false
check4_detail=""
configured_turns=$(jq -r '.env.CLAUDE_CODE_MAX_TURNS // ""' \
                   "${SETTINGS}" 2>&1)
live_turns="${CLAUDE_CODE_MAX_TURNS:-}"
if [ -n "${configured_turns}" ] && \
   [ "${configured_turns}" -ge "${RECOMMENDED_MAX_TURNS}" ] 2>/dev/null; then
  check4_pass=true
  check4_detail="configured=${configured_turns} (≥${RECOMMENDED_MAX_TURNS})"
  if [ -n "${live_turns}" ] && [ "${live_turns}" != "${configured_turns}" ]; then
    check4_detail="${check4_detail}; WARN live env=${live_turns} differs — settings cached"
  fi
else
  check4_detail="configured=${configured_turns:-MISSING}; live=${live_turns:-unset}; expected ≥${RECOMMENDED_MAX_TURNS}"
fi

# --- Check 5: DISABLE_AUTOCOMPACT=1 (auto-compact DISABLED, not throttled) ---
check5_pass=false
check5_detail=""
configured_disable=$(jq -r '.env.DISABLE_AUTOCOMPACT // ""' \
                     "${SETTINGS}" 2>&1)
live_disable="${DISABLE_AUTOCOMPACT:-}"
legacy_window=$(jq -r '.env.CLAUDE_CODE_AUTO_COMPACT_WINDOW // ""' \
                "${SETTINGS}" 2>&1)
if [ -n "${legacy_window}" ]; then
  check5_detail="CLAUDE_CODE_AUTO_COMPACT_WINDOW=${legacy_window} present \
— that only throttles compaction; operator directive is DISABLE_AUTOCOMPACT=1. \
Remove the legacy key."
elif [ "${configured_disable}" = "1" ] || [ "${configured_disable}" = "true" ]; then
  check5_pass=true
  check5_detail="DISABLE_AUTOCOMPACT=${configured_disable} (auto-compact disabled)"
  if [ -n "${live_disable}" ] && [ "${live_disable}" != "${configured_disable}" ]; then
    check5_detail="${check5_detail}; WARN live env=${live_disable} differs — settings cached"
  fi
else
  check5_detail="DISABLE_AUTOCOMPACT=${configured_disable:-MISSING}; live=${live_disable:-unset}; expected =1"
fi

# --- Check 6: SessionStart hook wired (auto-heal on every session) ---
check6_pass=false
check6_detail=""
ss_cmd=$(jq -r '.hooks.SessionStart[0].hooks[0].command // ""' \
         "${SETTINGS}" 2>&1)
if echo "${ss_cmd}" | grep -q "env-bootstrap/apply.sh"; then
  check6_pass=true
  check6_detail="SessionStart → env-bootstrap/apply.sh (auto-heal on session start)"
else
  check6_detail="SessionStart hook missing or doesn't call env-bootstrap/apply.sh (got: ${ss_cmd:-MISSING})"
fi

# --- Check 7: PostCompact hook wired (re-orient after compaction) ---
check7_pass=false
check7_detail=""
pc_cmd=$(jq -r '.hooks.PostCompact[0].hooks[0].command // ""' \
         "${SETTINGS}" 2>&1)
if echo "${pc_cmd}" | grep -q "post-compact-reorient.sh"; then
  check7_pass=true
  check7_detail="PostCompact → post-compact-reorient.sh (anti-amnesia)"
else
  check7_detail="PostCompact hook missing or doesn't call post-compact-reorient.sh (got: ${pc_cmd:-MISSING})"
fi

# --- Check 8: env-bootstrap mirror present + executable ---
check8_pass=false
check8_detail=""
BOOTSTRAP_APPLY="${HOME}/.claude/env-bootstrap/apply.sh"
REORIENT="${HOME}/.claude/post-compact-reorient.sh"
if [ -x "${BOOTSTRAP_APPLY}" ] && [ -d "${HOME}/.claude/env-bootstrap/templates" ] && [ -x "${REORIENT}" ]; then
  check8_pass=true
  check8_detail="env-bootstrap/{apply.sh,templates/} + post-compact-reorient.sh installed + executable"
else
  missing=""
  [ ! -x "${BOOTSTRAP_APPLY}" ] && missing="${missing} env-bootstrap/apply.sh"
  [ ! -d "${HOME}/.claude/env-bootstrap/templates" ] && missing="${missing} env-bootstrap/templates/"
  [ ! -x "${REORIENT}" ] && missing="${missing} post-compact-reorient.sh"
  check8_detail="missing/non-exec:${missing}; run 'bash scripts/claude-code-env/apply.sh' to install"
fi

# --- Report ---
overall_pass=true
[ "${check1_pass}" = "false" ] && overall_pass=false
[ "${check2_pass}" = "false" ] && overall_pass=false
[ "${check3_pass}" = "false" ] && overall_pass=false
[ "${check4_pass}" = "false" ] && overall_pass=false
[ "${check5_pass}" = "false" ] && overall_pass=false
[ "${check6_pass}" = "false" ] && overall_pass=false
[ "${check7_pass}" = "false" ] && overall_pass=false
[ "${check8_pass}" = "false" ] && overall_pass=false

if [ "${mode}" = "json" ]; then
  jq -n \
    --arg c1 "${check1_pass}" --arg c1d "${check1_detail}" \
    --arg c2 "${check2_pass}" --arg c2d "${check2_detail}" \
    --arg c3 "${check3_pass}" --arg c3d "${check3_detail}" \
    --arg c4 "${check4_pass}" --arg c4d "${check4_detail}" \
    --arg c5 "${check5_pass}" --arg c5d "${check5_detail}" \
    --arg c6 "${check6_pass}" --arg c6d "${check6_detail}" \
    --arg c7 "${check7_pass}" --arg c7d "${check7_detail}" \
    --arg c8 "${check8_pass}" --arg c8d "${check8_detail}" \
    --arg overall "${overall_pass}" \
    '{
       overall: ($overall == "true"),
       checks: [
         { id: "settings-explicit-empty-stop-arrays",
           passed: ($c1 == "true"), detail: $c1d },
         { id: "orphan-script-neutralized",
           passed: ($c2 == "true"), detail: $c2d },
         { id: "stop-hook-block-cap-raised",
           passed: ($c3 == "true"), detail: $c3d },
         { id: "max-turns-raised",
           passed: ($c4 == "true"), detail: $c4d },
         { id: "auto-compact-disabled",
           passed: ($c5 == "true"), detail: $c5d },
         { id: "session-start-auto-heal-wired",
           passed: ($c6 == "true"), detail: $c6d },
         { id: "post-compact-reorient-wired",
           passed: ($c7 == "true"), detail: $c7d },
         { id: "env-bootstrap-mirror-installed",
           passed: ($c8 == "true"), detail: $c8d }
       ]
     }'
elif [ "${quiet}" = "false" ]; then
  echo "── validate-stop-hook-fix ──"
  m() { [ "$1" = "true" ] && echo "✓" || echo "✗"; }
  printf "  %s  settings.json explicit empty Stop arrays — %s\n" "$(m "${check1_pass}")" "${check1_detail}"
  printf "  %s  ~/.claude/stop-hook-git-check.sh neutralized — %s\n" "$(m "${check2_pass}")" "${check2_detail}"
  printf "  %s  CLAUDE_CODE_STOP_HOOK_BLOCK_CAP ≥%d — %s\n" "$(m "${check3_pass}")" "${REQUIRED_CAP}" "${check3_detail}"
  printf "  %s  CLAUDE_CODE_MAX_TURNS ≥%d — %s\n" "$(m "${check4_pass}")" "${RECOMMENDED_MAX_TURNS}" "${check4_detail}"
  printf "  %s  DISABLE_AUTOCOMPACT=1 (auto-compact disabled) — %s\n" "$(m "${check5_pass}")" "${check5_detail}"
  printf "  %s  SessionStart auto-heal hook wired — %s\n" "$(m "${check6_pass}")" "${check6_detail}"
  printf "  %s  PostCompact re-orient hook wired — %s\n" "$(m "${check7_pass}")" "${check7_detail}"
  printf "  %s  env-bootstrap mirror installed — %s\n" "$(m "${check8_pass}")" "${check8_detail}"
  if [ "${overall_pass}" = "true" ]; then
    echo "  ✓ ALL CHECKS PASSED — harness configured + self-healing + post-compact-resilient"
  else
    echo "  ✗ AT LEAST ONE CHECK FAILED — see info-hub lesson"
    echo "    claude-code-env-runner-restages-stop-hook-script-from-baked-"
    echo "    template-at-every-session-start.md for the durable fix recipe"
  fi
fi

[ "${overall_pass}" = "true" ] && exit 0 || exit 1
