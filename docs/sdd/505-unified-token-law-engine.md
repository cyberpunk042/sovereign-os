# SDD-505 — The unified token-law engine: one declarative spec composing all M00117 planes

> Status: active · Mandate: **E11.M505** (control-bits band 500–599)
>
> Cross-link: closes **E11.M505** (unified token-law engine), the sixth SDD in
> the control-bits band — the capstone that folds the five plane classes built in
> SDD-500…504 into one declarative entry point.
>
> Number band: **500–599 (control-bits session)**
>
> **v1 shipped 2026-07-21** — operator-directed ("Good, we continue, another big
> PR"). A single `TokenLawSpec` + `complete_with_token_law` now composes grammar,
> regex, tool, safety-denylist and policy planes — any subset, all at once — per
> decode step. See § "What shipped".

## Mission

SDD-500…504 built the M00117 five-plane vision plane-by-plane: the per-token mask
(500), multi-plane composition (501), the incremental parser (502), real positive
sources — regex + tool (503), and the negative safety source (504). But the LLM
surface accreted as **five pairwise methods** —
`complete_json_schema_with_laws`, `complete_regex_with_laws`,
`complete_json_schema_and_regex_with_laws`, `complete_with_safety_denylist`,
`complete_regex_with_safety_denylist` — a combinatorial explosion that still could
**not** express "grammar ∧ regex ∧ safety ∧ policy all at once."

This SDD unifies them into **one declarative engine**: a `TokenLawSpec` names which
planes are active, and `complete_with_token_law` AND-composes every active plane
per step through the real `token_law_combine` kernel. It is the genuinely-new
"all planes at once" capability **and** the clean substrate the spec'd M00155
`--token-law-mask-layers` operator surface needs (the CSV layer list maps directly
onto the spec's fields).

## What was real vs the gap (grounded 2026-07-21)

- **Real — every plane source + the composition primitive.** `TokenGrammarMask::mask` (grammar, 501/502), `RegexConstraint::allowed_token_ids` (regex/tool, 503), `DenyConstraint::safe_token_ids` (safety, 504), `TokenLawPlanes::combine_with_dynamics` (the N-way AND, 503), all driving `generate_dynamic_token_law_until` (501).
- **The gap.** No single call composed **more than two** dynamic sources. The five methods hard-code specific pairs; there is no "grammar AND regex AND denylist AND policy," and no declarative way to select the active set (what M00155's `token_law_engine_mask_layers = grammar,schema,tool,safety` describes).

## Design

### `TokenLawSpec` — the declarative plane set

```rust
pub struct TokenLawSpec<'a> {
    pub schema:        Option<&'a Schema>,   // grammar plane (stop on completion)
    pub regex:         Option<&'a str>,      // regex plane (tool-name = alternation)
    pub denylist:      &'a [&'a str],        // negative safety plane
    pub policy_planes: &'a [&'a [u64]],      // static allow-bitsets (route/tool/safety)
}
```

`Default` is the empty (unconstrained) spec; a struct literal with `..Default::default()`
selects any subset. `is_empty()` reports whether any plane is active.

### `complete_with_token_law` — compose every active plane per step

Builds each active constraint once (compile grammar, compile regex, build the
deny automaton, pack the static planes), then per decode step collects the
allow-list of **every active dynamic plane** and calls
`TokenLawPlanes::combine_with_dynamics(&[…])` — the real `token_law_combine` `And`
over all dynamics **and** the static policy planes. A token survives only if every
plane allows it. Generation stops on grammar completion (`eos`), an empty plane,
or an empty intersection; an empty spec runs unconstrained to `max_new`.

### Faithful generalization (parity is the proof)

Because `combine_with(x)` ≡ `combine_with_dynamics(&[x])` (SDD-503), a spec with a
**single** plane produces the *bit-for-bit identical* mask — and therefore the
identical output — as the corresponding dedicated method. The five pairwise
methods are retained (back-compat); the engine is a superset, verified by parity
tests, not a replacement that risks drift.

## What shipped (2026-07-21)

- **`crates/sovereign-llm`** — `TokenLawSpec<'a>` (`Debug + Clone + Default`, `is_empty`) and `SovereignLlm::complete_with_token_law(prompt, spec, max_new, seed)`. No new crate (723 unchanged); no new dependency (all plane crates already in `sovereign-llm`). The five pairwise methods are unchanged.
- **+5 tests**: three parity tests (regex-only ≡ `complete_regex_with_laws`; schema-only ≡ `complete_json_schema_with_laws`; denylist-only ≡ `complete_with_safety_denylist` — each byte-for-byte); the all-planes composition (JSON-string grammar ∧ regex `"[a-z]+"` ∧ denylist `"bad"` ∧ policy ban byte `q` → quoted, lowercase, no `q`, never `"bad"` — a constraint no single method expresses); and the empty-spec unconstrained run.

Verified: `cargo test -p sovereign-llm` (91 lib + 28 runtime pass); `cargo clippy -D warnings` + `cargo fmt --check` clean; `tests/lint/test_unified_token_law_engine_contract.py` locks the spec's plane fields, the compose-all wiring, and the faithful-generalization framing.

## Non-goals

- Removing the pairwise `complete_*_with_laws` methods (kept for back-compat; the engine is a superset).
- The M00155 operator surface (`--token-law-mask-layers`, `POST /v1/data-plane/token-law/fuse`, dashboard) — this is its *code* substrate; the CLI/HTTP/config exposure is a separate SDD.
- New plane classes (grammar/regex/tool/safety/policy are the built set; a negated-regex denial is SDD-504's tracked future).
- The external-proxy `/v1/messages` path (the SDD-500 boundary — no logit access).

## References

- SDD-500…504 — the five plane classes this unifies.
- `crates/sovereign-llm/src/lib.rs` (`TokenLawSpec`, `complete_with_token_law`), `crates/sovereign-token-law-mask` (`combine_with_dynamics`), `crates/sovereign-token-grammar-mask`, `crates/sovereign-regex-constrain`, `crates/sovereign-token-law-deny`.
- Milestone spec: `backlog/milestones/M010-deterministic-data-plane.md` (M00155 "Token Law Engine" — this is its runtime substrate).
