# Re-arming `/goal` autopilot — root cause + the fix

> **Discovered:** 2026-05-17. Symptom: operator perceived Claude
> "stopping after a single iteration" after previously running on
> /goal-driven autopilot.

## Root cause

The Claude Code harness `/goal` command has THREE layers — the
break point in this arc was layer 3:

1. **Global Stop hook** (`~/.claude/settings.json` →
   `~/.claude/stop-hook-git-check.sh`). Blocks turn-end ONLY when
   git has uncommitted/unpushed changes. Returns exit-0 once git is
   clean → turn ends. **This is a safety net, not the autopilot.**

2. **Session-scoped /goal Stop hook.** When `/goal <text>` is set,
   the harness layers an ADDITIONAL Stop hook with the goal text as
   the "condition". After each turn the harness evaluates whether
   the condition is met; if not it injects a `Stop hook feedback`
   message forcing Claude to keep working. **This is the autopilot.**

3. **The harness char limit.** `/goal` rejects strings >4000
   characters. The operator's full mandate is ~6967 chars. Attempts
   to re-set the goal silently failed with
   `Goal condition is limited to 4000 characters (got 6967)`.

When (3) fires, the result is that NO new goal-Stop-hook registers.
Any previously-set goal that auto-cleared (the harness may consider
the condition satisfied after large progress) is not replaced. Only
(1) remains. Once git is clean (commits pushed), (1) returns exit-0
and the turn ends — no autopilot, hence "stops after a single
iteration".

## The fix — three layers

### Layer A: operator-side, re-arm now

Use the compact pointer goal-text emitted by
`tools/claude/rearm-goal-from-mandate.sh`. It's ~1130 characters —
well under the 4000-char limit — and it POINTERS at the durable
mandate file rather than inlining the verbatim text. Paste the
script's output into `/goal`.

```
$ tools/claude/rearm-goal-from-mandate.sh
Continue work toward the standing operator mandate recorded at
docs/standing-directives/2026-05-17-operator-mandate.md.

Read that file at the start of each session. Pick the next TODO
Module from any Epic. Ship one round per turn (CLI + L3 test +
commit + push), cite the Epic/Module ID in the commit message,
mark the Module ✓ in the mandate file when shipped.
[...]
```

This survives the char limit. The verbatim operator text stays
intact in the mandate file (sacrosanct §1).

### Layer B: SessionStart hook (operator opt-in)

Operators can add a `SessionStart` hook to
`~/.claude/settings.json` that prints the goal-text on every new
session so Claude reads it without `/goal` needing to register:

```json
{
  "hooks": {
    "SessionStart": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "test -x ./tools/claude/rearm-goal-from-mandate.sh && ./tools/claude/rearm-goal-from-mandate.sh || true"
      }]
    }]
  }
}
```

The hook output is injected as additional context into the session.
Claude reads it alongside the user prompt + treats the standing
mandate as authoritative even when /goal has cleared / never armed.

### Layer C: Claude-side discipline

Even with neither /goal nor SessionStart, when the operator says
"Continue from where you left off" / "keep going" / similar, Claude
should chain MULTIPLE rounds in a single response — not just
acknowledge and stop. The mandate file is the authoritative source
of "what's next" regardless of /goal state.

## Why "/goal" auto-cleared earlier

Hypothesis (not confirmed from harness source): the /goal evaluator
considers the condition "met" when the assistant's output text
strongly addresses a substantial portion of the condition. After
~40 rounds shipping the operator-mandate axes + the directive-
decomposition commit (R264) likely tripped that heuristic. The
operator's attempt to RE-set with the same 6967-char text then
failed (char limit). Net: no active goal hook → only the git-check
hook remained → "stops after a single iteration".

## Anti-recurrence

- `tools/claude/rearm-goal-from-mandate.sh` exists + ships in repo.
- Operators paste its output into `/goal` (or wire SessionStart).
- The mandate file (`2026-05-17-operator-mandate.md`) is the
  durable record — survives any harness behavior change.
- Future rounds keep citing Epic/Module IDs (E9.M2) so the
  decomposition stays visible in git log even outside the file.
