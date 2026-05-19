#!/usr/bin/env bash
# ~/.claude/post-compact-reorient.sh
#
# Fires on PostCompact hook event. Emits a systemMessage that re-injects
# the operator's standing directives + the perpetual-mandate semantics
# into the active session, so behavioral state lost during context
# compaction is restored rather than silently dropped.
#
# Mechanism: PostCompact hooks can return JSON with a top-level
# "systemMessage" field which Claude Code surfaces back to the model.
# We emit a compact, structured reminder pointing at the canonical
# files (CLAUDE.md, sovereign-os operator-mandate, info-hub directives).
#
# Why this exists: Claude Code compaction can summarize-away the
# operator's verbatim standing directives, the perpetual /goal
# semantics, and the "never stop because AI thinks it's done/blocked"
# discipline. After compaction the model has only the harness system
# prompt + CLAUDE.md auto-load + the summary — without a re-orient,
# behavioral drift is the default.
#
# This script is deliberately stateless and idempotent. It emits the
# same systemMessage on every compaction; Claude Code dedups display.

set -uo pipefail

# Compose the systemMessage. Keep tight — every char costs context.
cat <<'EOF'
{
  "systemMessage": "POST-COMPACT RE-ORIENT — standing directives survive compaction. Re-read on first action this turn: (1) ~/.claude/CLAUDE.md — user-global overrides (PR draft policy, multi-hour cycle discipline, SDD+TDD methodology, 'never stop because AI thinks done/blocked/should-stop' anti-patterns). (2) Operator perpetual mandate: /goal is OPERATOR-CONTROLLED — AI does not decide when it's complete. AI completion-self-assessment is NOT a stop trigger. (3) Operator words are SACROSANCT — quote verbatim. (4) Direct-push to main only for cyberpunk042/sovereign-os; all other ecosystem repos use branch claude/general-session-Wk97z + normal (not draft) PR when ready. (5) Never include model identifier in pushed artifacts. (6) If config drift suspected, run: bash ~/.claude/env-bootstrap/apply.sh --dry-run to inspect, then drop --dry-run to auto-heal."
}
EOF
