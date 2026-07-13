# SDD-983 — cold-start signpost for the July intelligence-layer arc (handoff 008 + the gateway /v1 API reference)

> Status: draft
> Owner: operator-directed 2026-07-13 ("lets go then" — take the recommended next collision-safe audit item); agent-authored.
> Closes: **F-2026-060** (CRIT) + **F-2026-036** (HIGH) + **F-2026-064** (LOW).
> Mandate module: **E11.M983**.
> Number band: **950–999 (phase-1 audit session)** per SDD-100.

## Mission

The Phase-1 audit's highest-severity *still-open* finding was documentation, not
code: the **July 11–12 intelligence-layer arc** (Brain observatory, CoAT engine,
background-jobs runtime, Anthropic Messages API, Plan-mode/AUQ/classifier, HF-BPE
tokenizer, durable Cortex memory) — the box's whole reasoning layer — shipped and
merged with **no cold-start signpost**: the handoff INDEX topped out at 007, no
decisions entry existed past D-019, and the `/v1` deliberation endpoints were
documented only in code comments. A fresh or post-compaction session had no way
to learn the biggest recent arc exists. This closes that gap, entirely in docs.

## What this SDD writes

| Artifact | Closes | What |
|---|---|---|
| **`docs/handoff/008-july-intelligence-layer-arc.md`** | F-2026-060 / F-2026-036 | The cold-start anchor: what the arc is, what shipped (with evidence paths — `sovereign-coat`, `jobs_store.py`, `brain-api.py`, `http.rs`), the ports (brain 8141 / jobs 8142 / gateway 8787, loopback), the verified-good properties to preserve (F-2026-067), the open follow-up findings, and a recommended next-work order. Supersedes handoff 007. |
| **`docs/src/gateway-api-reference.md`** | F-2026-064 | Every `/v1` route from `crates/sovereign-gatewayd/src/http.rs`: the deliberation ladder (`infer`→`simple`→`explain`/`simple-explain`→`deliberate`→`coat`), the Anthropic surface (`messages`/`models`/`count_tokens`, SDD-205), model-management, observability. Explicitly delineates `/v1/deliberate` (flat best-of-N) vs `/v1/coat` (tree/ladder) per the finding, and carries the F-2026-082 (loopback-only) + F-2026-063 (coat-holds-the-mutex) caveats. Linked from `SUMMARY.md` so it's in the book. |
| **`docs/decisions.md` D-020** | F-2026-036 | A retroactive architecture record for the arc (clearly marked as documenting shipped state, not new policy), naming the open sub-decision F-2026-034 (MS003 signing). |
| `context.md` + `docs/handoff/INDEX.md` + the findings ledger | all three | The intelligence-layer bullet now points at handoff 008 + the API reference; the INDEX gains the 008 row; F-2026-060/036/064 are back-annotated as closed. |

## Accuracy discipline

The `/v1` reference was written from the **actual route table** in
`crates/sovereign-gatewayd/src/http.rs` (module doc-comment lines 16–23 + the
match arms), not paraphrased from the finding — read-only (no gatewayd edit).
The arc inventory is sourced from the findings ledger (F-2026-060/067/090/091)
+ the standing-directives + `context.md`.

## Verification (real, observed)

- `test_context_md_counts.py` green (prose-only + the `sdd files` count bumped for
  this file); `test_mdbook_catalog_sync.py` + `test_sdd_reachability.py` +
  `test_sdd_numbers_unique.py` + `test_session_registry.py` green.
- `mdbook build` job: the new `gateway-api-reference.md` is linked from
  `SUMMARY.md` (no orphan page).
- No code/behaviour change; every path cited in the docs was verified to exist.

## Non-goals

- Fixing any of the arc's open findings (F-2026-034/061/062/063/083/087/090/091) —
  those are the *next* work, named in handoff 008; this SDD only makes the arc
  discoverable.
- Creating a `SHIPPED.md` — none exists in this repo; the CHANGELOG + handoff 008
  + D-020 carry the "shipped" record (noted in the F-2026-036 back-annotation).

## Safety invariants

Docs only (`docs/handoff/`, `docs/src/`, `context.md`, `docs/decisions.md`, the
findings ledger, this SDD + registries). No gatewayd/cockpit/`unsafe`/crate
edits — `http.rs` was read, never written; collision-safe with the core-runtime
sessions. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `docs/handoff/008-july-intelligence-layer-arc.md` — the anchor this SDD authors
- `docs/src/gateway-api-reference.md` — the `/v1` reference this SDD authors
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-060 / F-2026-036 / F-2026-064 (closed here) + F-2026-067 (verified-good)
- `crates/sovereign-gatewayd/src/http.rs` — the authoritative route table (read-only source)
- SDD-205 (Anthropic Messages API) · SDD-957 (serve-vs-gatewayd) · SDD-982 (the session-protocol brain wiring — same docs-onboarding discipline)
