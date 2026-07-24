# Go-live blockers assessment — a prioritized decision package (2026-07-24)

> **Purpose.** The token-law / serving-completeness arc is essentially closed (M00117 planes; both OpenAI + Anthropic dialects at full sampling/stop/format/agentic parity; the `response_format` translator complete). What remains between here and go-live is a set of **operator-gated** items spread across two registries. This doc consolidates them into one prioritized read so the sequencing is a single decision, not a rediscovery each pass.
>
> **This is an assessment, not a re-spec** — each item's authoritative definition stays in its cited source (`docs/src/lifecycle/first-run-pending.md` §A–G, and `docs/review/phase-1/deferred-work-register.md` items 1–10). Nothing here is a code change. It exists to help the operator pick what to unblock next.

## The landscape in one table

| Class | Items | Who can close it | Agent-buildable? |
|---|---|---|---|
| **Physical / hardware-gated** | first-run §A (notifications channel test), §B (exec-rail sudoers flip), §C (big-MoE oracle benches), §D (compat-gate calibration on the box), §F (wikiops registry from example); register #3 (Layer-4/5 conformance — KVM/hardware), #5 (TPM2 PCR binding) | Operator, on the SAIN-01 box | No — needs the physical machine |
| **Operator decision (no hardware)** | first-run §E (AGENTS.md/CLAUDE.md v2 promotion) | Operator, a review call | No — a judgment/sign-off |
| **Software-only, agent-buildable** | ~~register #1 (telemetry sink + Grafana dashboards), #2 (SDD-016 Layer-B Prometheus emission), #4 (SDD-019 apt-snapshot + `SOURCE_DATE_EPOCH` + in-toto provenance)~~ **— all three reconciled CLOSED 2026-07-24 (already built by the July arc; the register was stale, not the code — see deferred-work-register rows 1/2/4)** | An agent session | **Done** — this frontier is exhausted; the audit that verified it *was* the P1 agent work |
| **Cross-repo (selfdef)** | register #7 (MS043 mirror-crate impls), #8 (selfdef CLI/TUI mirror + SG7/SG8) | Needs the selfdef tree in scope | Partially — cross-repo |
| **Question backlogs** | register #9 (SDD-046 Q-046-*, root Q-A..D, Q4..Q25), #10 (Q-067-A..F — partially overtaken) | Operator answers; agent can draft | Draft-only |

## Recommended sequencing

The physical + decision items (§A–F, register #3/#5) are the true go-live gates but **cannot** be closed from an agent session — they wait on the box or an operator call. So the highest-leverage *agent* work between now and then is the **software-only foundation** (register #1/#2/#4), which hardens observability + reproducibility so that when the box is available, go-live is a clean flip rather than a scramble.

**P1 — software-only foundation — ✅ RECONCILED CLOSED (2026-07-24).** The read-only audit this section recommended was run and found all three already built:
1. ~~register #2~~ — **closed**: `emit_metric`/`emit_metric_set` wired into 19 recurrent hooks + `guardian-core.py` + `warp-runner.py`; pinned by `test_hook_layer_b_coverage` + `test_metric_inventory_lockstep` + `test_metric_observability_coverage` + `test_prom_read_write_binding` (all green).
2. ~~register #1~~ — **closed**: sink = `prometheus-local`; 61 Grafana dashboard JSONs shipped under `docs/observability/dashboards/`, held in lockstep by `test_dashboard_metrics_lockstep`.
3. ~~register #4~~ — **substantially closed**: `SOURCE_DATE_EPOCH` honored+propagated in step-04 + 4 more build scripts; apt-snapshot pin (`DEBIAN_SNAPSHOT`) in `mkosi-emit`; in-toto `Statement/v1`+SLSA provenance in the release-metadata generator; pinned by `test_release_contract` + `test_provenance_manifest_shape`. Residual (same-inputs→same-bytes rebuild proof) is build-host-gated, like item 3's KVM gate.

**Net: the agent-buildable software frontier for go-live is exhausted.** What remains is genuinely hardware-gated (§A–F, register #3/#5), an operator decision (§E), cross-repo selfdef (#7/#8), or draft-only question backlogs (#9/#10).

**P2 — operator decision that unblocks the agent layer:**
4. **first-run §E** — promote (or strike) the AGENTS.md/CLAUDE.md v2. Low effort, and it's the doc the agent sessions run on; leaving it in DRAFT is a standing minor drag.

**P3 — physical, when the box is available (operator):** §A → §B → §D → §F, then §C benches; register #3 (KVM runner) + #5 (TPM) alongside.

**P4 — cross-repo + questions:** register #7/#8 (selfdef in scope), then the Q-backlogs (#9/#10), agent can draft answers for operator ratification.

## What I'd take next, autonomously

**Update 2026-07-24:** the recommended next pick (register #2's read-only audit) was run, and it cascaded — #2, #1, and #4 are all already built (register rows 1/2/4 reconciled closed). With the P1 software frontier exhausted, the remaining agent-buildable candidates are the **cross-repo selfdef** items (#7/#8 — selfdef is in repo scope; verify the 9 MS043 mirror-crate impls against the M060 completion claim) and **draft-only** work on the question backlogs (#9/#10). Everything else waits on the SAIN-01 box (§A–F, register #3/#5) or an operator sign-off (§E). This doc remains the decision surface; the sequence is a recommendation, not an action.

## Cross-references

- `docs/src/lifecycle/first-run-pending.md` — §A–G (the physical / decision gates; authoritative).
- `docs/review/phase-1/deferred-work-register.md` — items 1–10 (the deferred-work index; authoritative, with owners `operator-to-assign`).
- `docs/review/phase-1/99-findings-ledger.md` — the closed findings this arc drew from.
- `AGENTS.md` / `CLAUDE.md` — the "Pending operator decisions (blocking go-live)" tables these consolidate.
