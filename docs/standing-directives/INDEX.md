# Standing operator directives

Long-running operator mandates that survive `/goal` Stop-hook
auto-clearing. Future sessions read THIS index (not the ephemeral
hook) as the source of truth for "what is the operator asking us to
work on?".

| Date | File | Status | Epics |
|------|------|--------|-------|
| 2026-05-17 | [operator-mandate.md](./2026-05-17-operator-mandate.md) | active | E1 (Hardware-stack), E2 (Software-stack), E3 (Network), E4 (Dashboard/UX), E5 (AI/LLM), E6 (Health/Doctor), E7 (Interop/MCP), E8 (REPL tiers), E9 (Process) |
| 2026-Q2 | [mandate-review-2026-Q2.md](./mandate-review-2026-Q2.md) | review-record | quarterly snapshot + new-axis intake process (R285 closes E9.M3) |

## Re-arming /goal autopilot

See [`goal-rearming.md`](./goal-rearming.md) for the root-cause
analysis + paste-ready snippet. Short version:

- The harness `/goal` rejects strings >4000 chars; the operator's
  full mandate is ~6967 chars.
- Use `tools/claude/rearm-goal-from-mandate.sh` to emit a compact
  pointer goal-text (~1130 chars) and paste it into `/goal`.
- Layer-B option: wire SessionStart hook so it's auto-emitted.
- L1 lint at `tests/lint/test_rearm_goal_script.py` guards the
  char-limit + structural anti-recurrence contract.

## Rules

- Active directives stay active until the operator explicitly clears them.
- Each round's commit message SHOULD cite the Epic + Module ID it advances.
- New axes the operator names get added under existing Epics (or new
  Epics under an active directive) with a verbatim source quote.
- The `/goal` Stop hook is convenient for short pulses but does NOT
  replace this file. Treat `/goal` as ephemeral; treat this file as
  durable.
