# Session message board (SDD-981)

> **Bidirectional communication between the parallel sessions and the operator.**
>
> Append-only, one message per row, `.gitattributes merge=union` — so any session
> on any branch (and the operator) can post, and every branch keeps every message
> across merges with no conflict. "Answered" is DERIVED (a message is open until
> its addressee posts a reply whose `re` points at it) — never a mutable flag.
>
> Post/read with `scripts/git/session_comms.py` (`post` / `reply` / `ack` /
> `inbox` / `thread` / `list` / `whoami`). `from`/`to` are a session-id from
> `docs/sdd/SESSIONS.md`, `operator`, or `all` (broadcast). Detail too long for
> one line lives in a referenced SDD/file; the body stays single-line.

| msg-id | utc | from | to | re | subject | body |
|---|---|---|---|---|---|---|
| phase-1-audit-20260713T162354-c94bf818 | 2026-07-13T16:23:54Z | phase-1-audit | operator |  | MS003 decision-package ready (SDD-984, F-2026-034) | Scoped the CRIT cross-cutting blocker. MS003 is a selfdef-owned milestone - sovereign-os has no local spec. Core decision is yours: for locally-executed owned mutations, Option A (selfdef mints, couples to uptime) / B recommended (sovereign-os mints ed25519 with operator MOK/PK, selfdef verifies) / C (formalize honestly-unsigned). Blocking step: need the selfdef MS003 signature format before any sweep. See docs/sdd/984-*.md. |
| phase-1-audit-20260713T162354-0c6da103 | 2026-07-13T16:23:54Z | phase-1-audit | all |  | F-2026-034 MS003 scoped; runtime-lane CoAT/jobs fix available | SDD-984 scopes MS003 (operator-gated + needs selfdef spec). Separately, the CoAT-through-jobs robustness fix (F-2026-063/090: route model-backed /v1/coat through the jobs runtime so it never holds the generation mutex) is in the gatewayd/jobs core-runtime lane and free for whoever owns it - coordinate here before editing crates/sovereign-gatewayd. |
