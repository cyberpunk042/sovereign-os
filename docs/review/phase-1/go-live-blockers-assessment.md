# Go-live blockers assessment — a prioritized decision package (2026-07-24)

> **Purpose.** The token-law / serving-completeness arc is essentially closed (M00117 planes; both OpenAI + Anthropic dialects at full sampling/stop/format/agentic parity; the `response_format` translator complete). What remains between here and go-live is a set of **operator-gated** items spread across two registries. This doc consolidates them into one prioritized read so the sequencing is a single decision, not a rediscovery each pass.
>
> **This is an assessment, not a re-spec** — each item's authoritative definition stays in its cited source (`docs/src/lifecycle/first-run-pending.md` §A–G, and `docs/review/phase-1/deferred-work-register.md` items 1–10). Nothing here is a code change. It exists to help the operator pick what to unblock next.

## The landscape in one table

| Class | Items | Who can close it | Agent-buildable? |
|---|---|---|---|
| **Physical / hardware-gated** | first-run §A (notifications channel test), §B (exec-rail sudoers flip), §C (big-MoE oracle benches), §D (compat-gate calibration on the box), §F (wikiops registry from example); register #3 (Layer-4/5 conformance — KVM/hardware), #5 (TPM2 PCR binding) | Operator, on the SAIN-01 box | No — needs the physical machine |
| **Operator decision (no hardware)** | first-run §E (AGENTS.md/CLAUDE.md v2 promotion) | Operator, a review call | No — a judgment/sign-off |
| **Software-only, agent-buildable** | register #1 (telemetry sink + Grafana dashboards), #2 (SDD-016 Layer-B Prometheus emission — *verify: may be substantially built already*), #4 (SDD-019 apt-snapshot + `SOURCE_DATE_EPOCH` + in-toto provenance) | An agent session | **Yes** — these are the real autonomous frontier |
| **Cross-repo (selfdef)** | register #7 (MS043 mirror-crate impls), #8 (selfdef CLI/TUI mirror + SG7/SG8) | Needs the selfdef tree in scope | Partially — cross-repo |
| **Question backlogs** | register #9 (SDD-046 Q-046-*, root Q-A..D, Q4..Q25), #10 (Q-067-A..F — partially overtaken) | Operator answers; agent can draft | Draft-only |

## Recommended sequencing

The physical + decision items (§A–F, register #3/#5) are the true go-live gates but **cannot** be closed from an agent session — they wait on the box or an operator call. So the highest-leverage *agent* work between now and then is the **software-only foundation** (register #1/#2/#4), which hardens observability + reproducibility so that when the box is available, go-live is a clean flip rather than a scramble.

**P1 — software-only foundation (agent-buildable now):**
1. **register #2 first** — but *verify before scoping*: the scout notes `scripts/build/lib/observability.sh` + `emit_metric` are already wired into many hooks, so SDD-016 Layer-B may be substantially done. A read-only audit closes it or resizes it cheaply.
2. **register #1** — pick the telemetry sink + ship the Grafana dashboard JSONs (the observability foundation §A's channel test will lean on).
3. **register #4** — reproducibility: apt-snapshot enforcement + `SOURCE_DATE_EPOCH` in step-04 + in-toto provenance (a security/trust gate independent of hardware).

**P2 — operator decision that unblocks the agent layer:**
4. **first-run §E** — promote (or strike) the AGENTS.md/CLAUDE.md v2. Low effort, and it's the doc the agent sessions run on; leaving it in DRAFT is a standing minor drag.

**P3 — physical, when the box is available (operator):** §A → §B → §D → §F, then §C benches; register #3 (KVM runner) + #5 (TPM) alongside.

**P4 — cross-repo + questions:** register #7/#8 (selfdef in scope), then the Q-backlogs (#9/#10), agent can draft answers for operator ratification.

## What I'd take next, autonomously

If the direction is "keep the agent productive toward go-live without the box," the cleanest next pick is **register #2's read-only audit** (confirm what SDD-016 Layer-B already emits) → then **register #1** (telemetry sink + Grafana JSONs). Both are software-only, self-contained, and directly de-risk the §A notifications go-live. I will **not** start any of these without your nod — this doc is the decision surface, and the sequence above is a recommendation, not an action.

## Cross-references

- `docs/src/lifecycle/first-run-pending.md` — §A–G (the physical / decision gates; authoritative).
- `docs/review/phase-1/deferred-work-register.md` — items 1–10 (the deferred-work index; authoritative, with owners `operator-to-assign`).
- `docs/review/phase-1/99-findings-ledger.md` — the closed findings this arc drew from.
- `AGENTS.md` / `CLAUDE.md` — the "Pending operator decisions (blocking go-live)" tables these consolidate.
