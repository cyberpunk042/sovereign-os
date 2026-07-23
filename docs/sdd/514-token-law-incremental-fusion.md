# SDD-514 — Incremental fusion: the per-step token-law decision goes O(n²) → O(n) (M00155 DEEPEN)

> Status: active · Mandate: **E11.M514** (control-bits band 500–599)
>
> Cross-link: the **second Deepen slice** (`backlog/milestones/M010-deterministic-data-plane.md`) over the M00117 engine — the perf half. The thirteenth SDD in the control-bits band, after the Expose arc (SDD-507/510/511), the Connect fork (SDD-512), and the entropy plane (SDD-513).
>
> Number band: **500–599 (control-bits session)**
>
> **v1 shipped 2026-07-23** — operator-directed (*"continue"* → the Deepen perf work). SDD-512 flagged the serving hot path as O(n²) whole-prefix re-decode + re-fuse every token; this removes it, non-breaking, behind a proven parity invariant.

## Mission

`CompiledFuse::fused_mask(generated: &str)` is **stateless**: every decode step it re-walks each plane from the start of the whole prefix — the denylist re-runs the Aho-Corasick automaton from `start()` over all of `generated`, the regex planes re-advance the NFA over the whole prefix, the grammar re-parses it, and (a naive impl) the entropy plane re-copied the whole prefix per candidate. Over a decode of `n` tokens that is **O(n²)**. SDD-512 called this out as the real serving-path cost (bigger than the SIMD-of-the-AND item). This SDD makes the per-step decision **incremental** — carry each plane's committed automaton state and advance it by only the newly-committed token — so a decode is O(n), with **zero behavioral change**.

## The parity invariant (load-bearing)

The whole design rests on one guarantee: **`FuseSession::mask()` is bit-for-bit `CompiledFuse::fused_mask(prefix)` at every prefix.** The stateless `fused_mask` and the session share the exact same composition tail (`compose()` → `TokenLawPlanes::combine_with_dynamics`), the same plane order, and the same stop conditions; only *how each plane's allow-list is gathered* changes (from a full re-walk to an incremental advance). A parity test walks a token sequence through all five planes plus the two trickiest states — a positive regex that goes **off-pattern** and a grammar that reaches **eos** — asserting full `FusedMask` equality (`mask` / `allowed` / `per_layer` / `stop`) at every step. Because equality is proven, migrating a consumer from `fused_mask` to a session is a pure performance change.

## Design

### The engine — `FuseSession` (new, in `sovereign-token-law-fuse`)

`CompiledFuse::session()` opens a `FuseSession` carrying, per active plane, its incremental committed state: an `IncrementalGrammarMask` (grammar), the anchored regex live-set (`Some(None)` once off-pattern — sticky dead), the denylist `AcState`, one unanchored live-set per negated-regex, and a truncated entropy tail (kept to the plane's `window`, so entropy too is per-step-bounded). `mask()` reads the current per-plane allow-lists and runs the shared `compose()`. `advance_token(id)` / `advance_str(delta)` commit the delta into each plane's state (grammar `advance`, regex `advance_state`, deny `advance_state`, unanchored `advance_state`, entropy tail push+truncate) and return the next mask. `fused_mask` is **untouched** — the stateless path stays for the inspection route / CLI where a one-shot fuse at a prefix is wanted.

### The plane primitives (small, additive)

Two plane crates gained `*_from` helpers so a session keeps committed state behind the crate boundary; each is a pure refactor — the existing `safe_token_ids` / `allowed_token_ids` now **delegate** through them, so the existing parity tests already cover them:
- **`sovereign-token-law-deny`**: `start_state()` / `advance_state()` / `safe_token_ids_from()` + re-export `AcState`.
- **`sovereign-regex-constrain`**: `RegexConstraint::{start_state, advance_state (→ Option, None = off-pattern), allowed_token_ids_from}` + `RegexDenyConstraint::{start_state, advance_state, safe_token_ids_from}` (unanchored).
- grammar / entropy / aho-corasick / mask: **zero change** — the session reuses `IncrementalGrammarMask` and feeds entropy its running tail.

### The consumers

Both decode loops migrate to a session, dropping the per-step whole-prefix `tokenizer.decode` + `fused_mask`:
- **`sovereign-gatewayd`** — a `FuseStepper` adapter (session + a consumed-count) replaces the stateless `token_law_step` at both `/v1/messages` decode sites; it advances the session by the newly-arrived ids each step. No tokenizer at runtime.
- **`sovereign-llm`** — `complete_with_token_law` advances a session per token instead of re-decoding `so_far` + re-fusing.

## What shipped

- **`sovereign-token-law-fuse`** — `FuseSession` + `CompiledFuse::session()`; `fused_mask`/`FuseSession::mask` share a new private `compose()`; +2 parity tests (all-five-planes; off-pattern + eos).
- **`sovereign-token-law-deny`** — `start_state`/`advance_state`/`safe_token_ids_from` + `AcState` re-export; `safe_token_ids` delegates.
- **`sovereign-regex-constrain`** — the incremental `*_state`/`*_from` helpers on both constraints; existing methods delegate.
- **`sovereign-gatewayd`** — `FuseStepper` replaces `token_law_step` at both serving decode sites.
- **`sovereign-llm`** — `complete_with_token_law` drives a session.
- Registration: SDD-514 + INDEX + mandate E11.M514 + catalog regen + context sdd 224→225 + `tests/lint/test_token_law_incremental_fusion_contract.py`.

## Non-goals / roadmap

- **SIMD `fused_mask` AND-kernel** — still scalar; a smaller win now that the O(n²) re-walk is gone, tracked as the remaining Deepen perf item.
- **The route plane as a real source** — still blocked on a semantics decision (the 7-axis router outputs an `SrpRole` model choice, not a vocab subset; there is no defined `SrpRole → allow-bitset` mapping). Operator decision required before it can be built.

## References

- Milestone: `backlog/milestones/M010-deterministic-data-plane.md` (M00155 Deepen).
- The O(n²) call-out: `docs/sdd/512-token-law-serving-boundary.md` (Non-goals).
- Engine: `crates/sovereign-token-law-fuse/src/lib.rs` (`FuseSession`, `compose`, `session`).
- Plane primitives: `crates/sovereign-token-law-deny/src/lib.rs`, `crates/sovereign-regex-constrain/src/lib.rs`; incremental grammar reused from `crates/sovereign-token-grammar-mask/src/lib.rs` (`IncrementalGrammarMask`).
- Consumers: `crates/sovereign-gatewayd/src/lib.rs` (`FuseStepper`), `crates/sovereign-llm/src/lib.rs` (`complete_with_token_law`).
