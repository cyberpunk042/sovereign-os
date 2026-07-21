# SDD-501 — Multi-plane token-law composition: gate the decoder by grammar AND policy at once

> Status: active · Mandate: **E11.M501** (control-bits band 500–599)
>
> Cross-link: closes **E11.M501** (M00117 multi-plane token-law), the second
> SDD in the control-bits band, built directly on SDD-500's per-token call site.
>
> Number band: **500–599 (control-bits session)**
>
> **v1 shipped 2026-07-21** — operator-directed ("Good, we continue, another big
> PR" → chose "Multi-plane token-law (M00117)"). The design below is realized in
> one PR: a caller can now confine a running model by a grammar constraint **and**
> a set of static policy bitsets simultaneously, AND-combined through the real
> `token_law_combine` kernel every step. See § "What shipped".

## Mission

SDD-500 gave the M002 bit-machine its first real per-token call site: a packed
token-law allow-bitset masks logits inside the in-repo decode loop, token by
token. But that path takes **one** caller-supplied bitset. The genuinely-new
capability M00117 promises is **composition** — several independent token-law
*planes* (grammar / schema / tool / safety / route) intersected per step, so one
running model is confined by all of them at once.

Grammar-constrained decoding already works standalone in this repo
(`sovereign-cfg-grammar` → `sovereign-token-grammar-mask` →
`sovereign-llm::complete_json_schema` via `generate_dynamic_mask_until`). Static
policy bitsets already combine via `token_law_combine`. **What nothing did was
run both at the same time**: a grammar plane recomputed each position AND a
fixed safety/tool plane, intersected, gating the decoder. That is this SDD.

## What was real vs the gap (grounded 2026-07-21)

- **Real — the combine kernel.** `sovereign_simd::cheats::token_law_combine(laws: &[&[u64]], combine: LawCombine) -> Vec<u64>` (`crates/sovereign-simd/src/cheats.rs:312`). Each law is a per-vocabulary allow-bitset (`⌈V/64⌉` `u64` words). `And` = intersection. Real VPTERNLOG path + scalar reference. Consumed since SDD-500 by `sovereign-token-law-mask`.
- **Real — the grammar plane.** `sovereign_token_grammar_mask::TokenGrammarMask::new(grammar, vocab)` (`crates/sovereign-token-grammar-mask`), `.mask(prefix) -> Mask { allowed: Vec<bool>, eos: bool }`, `.allowed_ids() -> Vec<usize>`. Fed by `sovereign_json_schema_grammar::compile(&Schema) -> Grammar` (Earley `allowed_next`). Tokenizer↔grammar alignment is done.
- **Real — the per-token seam.** SDD-500's `DecoderStack::generate_dynamic_token_law_until`-shaped path already applies a `Vec<u64>` allow-mask with `mask_logits` each step.
- **The gap.** The grammar crates emit `Vec<bool>` / `Vec<usize>` / a `LogitMask` (`HashSet`), **not** the packed `Vec<u64>` `token_law_combine` consumes. So there was no way to take "the grammar allows tokens {…} here" and intersect it with a static safety bitset in the bit domain. Two pieces were missing: (a) a `Vec<usize>` → `Vec<u64>` packer, and (b) a per-step recompute+AND-combine of the grammar plane with the static planes.

The integration is again **connecting real kernels to a real seam** — no new crate, no architectural upheaval. Crate count stays 722.

## The honest scope caveat (inherited from SDD-500)

This composition lands in the **in-repo decode stack** (`sovereign-decoder-stack`
+ `sovereign-llm`), the box's own sovereign inference path. It does **not**
constrain the external-proxy `/v1/messages` path — that proxies out-of-process to
llama-server / vLLM and exposes no logits, so the bit-machine cannot gate those
tokens. Composed constrained decoding is a real capability of the sovereign path,
and a production constraint if/when the box serves from its own stack; it is not
a claim over the proxy path. The `sovereign-token-law-mask` crate documents this
boundary and `tests/lint/test_multi_plane_token_law_contract.py` locks it.

## Design

Three layers, each at the level where its inputs already live.

### 1. The packer + the plane set — `sovereign-token-law-mask`

The composition primitive belongs here because the *caller* supplies grammar
allowed-ids: no grammar-crate dependency is pulled into this layer.

```rust
// Vec<usize> allow-list  ->  packed Vec<u64> allow-mask (⌈V/64⌉ words).
pub fn pack_allowed(ids: &[usize], words: usize) -> Vec<u64>;

// The M00117 "grammar / schema / tool / safety / route" planes.
pub struct TokenLawPlanes { /* words, static_planes */ }

impl TokenLawPlanes {
    pub fn new(vocab: usize) -> Self;                       // words = ⌈vocab/64⌉
    pub fn with_plane(self, allow: Vec<u64>) -> Self;       // widen/truncate to width
    pub fn with_allow_ids(self, ids: &[usize]) -> Self;     // packs here
    pub fn combine_static(&self) -> Vec<u64>;               // planes only; empty = all-allowed
    pub fn combine_with(&self, dynamic_allow_ids: &[usize]) -> Vec<u64>;  // grammar ∧ planes
}
```

- **Static planes** (safety denylist, tool/schema allow-list — fixed across a
  generation) are held in the set. A **dynamic plane** (the grammar/regex
  constraint, recomputed each position) is passed to `combine_with`, packed, and
  AND-combined with the static planes through the real `token_law_combine`
  `And` kernel — a token survives only if **every** plane allows it.
- `combine_static` with no planes returns all-`u64::MAX` (identity: grammar
  alone survives), so the zero-policy case degrades exactly to the single-grammar
  path.
- `#![forbid(unsafe_code)]`; the packer drops ids `>= words*64`.

### 2. The M002-native dynamic loop — `sovereign-decoder-stack`

```rust
pub fn generate_dynamic_token_law_until<M>(
    &mut self, prompt: &[usize], max_new: usize, seed: u64, mut law_fn: M,
) -> Result<Vec<usize>, StackError>
where M: FnMut(&[usize]) -> Option<Vec<u64>>;
```

The bit-domain twin of `generate_dynamic_mask_until`: the per-step hook returns a
packed token-law allow-mask (`None` to stop — the grammar is complete, or no
token keeps every plane satisfiable, so **never sample from an all-masked row**).
Each step applies `mask_logits` (the SDD-500 `-inf` mask) and samples. The whole
path stays in the bit domain — no round-trip back to a `HashSet`/`LogitMask`.

### 3. The production wiring — `sovereign-llm`

```rust
pub fn complete_json_schema_with_laws(
    &self, prompt: &str, schema: &Schema,
    policy_planes: &[&[u64]], max_new: usize, seed: u64,
) -> Result<String, LlmError>;
```

Compiles the schema → grammar, builds the vocab (`tokenizer.decode` per id, once),
constructs a `TokenGrammarMask` + a `TokenLawPlanes` seeded with each policy
plane, and drives `generate_dynamic_token_law_until`. The closure per position:
decode the generated prefix → `tgm.mask(prefix)` → `None` on eos / empty
grammar set / empty intersection, else `Some(planes.combine_with(allowed_ids))`.
Zero policy planes ≡ the grammar-only `complete_json_schema` output.

## Honest performance boundary (read this)

This is a **correctness** composition, not an accelerated one:

- `TokenGrammarMask::mask(prefix)` **re-parses the whole prefix** each step
  (Earley `allowed_next` over the growing prefix) — there is no incremental
  parser here. That is the dominant per-token cost, and it is inherited from the
  existing grammar path, not introduced by this SDD.
- The vocab `decode`-per-id table is `O(V)` but built **once** per call.
- The bit-domain combine is cheap — popcount/AND over `⌈V/64⌉` words — but it
  does run **per step**.

So the composition adds negligible cost on top of grammar decoding; the honest
caveat is that grammar decoding itself is not cheap here. An incremental
Earley/derivative parser and a cached per-state bitset are the tracked
acceleration (out of scope — this SDD makes the *composition* real first, exactly
as SDD-500 made the *consumer* real before deriving laws from a source).

## What shipped (2026-07-21)

- **`crates/sovereign-token-law-mask`** — `pack_allowed` + `TokenLawPlanes`
  (`new`/`with_plane`/`with_allow_ids`/`plane_count`/`combine_static`/`combine_with`),
  over the real `token_law_combine` `And` kernel; `forbid(unsafe_code)`. +5 unit
  tests (packer bit-set + out-of-range drop; grammar {2,5,6} ∧ safety-ban(5) =
  {2,6}; empty-planes identity; `with_plane` widens to the vocabulary). No new
  crate — composition lives beside the SDD-500 mask.
- **`sovereign-decoder-stack`** — `generate_dynamic_token_law_until`, applying
  `mask_logits` each step. +1 integration test: planes ban 5, per-step grammar
  allows {2,5,6}, AND → {2,6}, run confined across 5 tokens.
- **`sovereign-llm`** — `complete_json_schema_with_laws` (dep on
  `sovereign-token-law-mask` added). +2 tests: bans the byte `t` via a policy
  plane and asserts no `t` in the output while it stays grammar-alphabet-valid;
  zero-plane output equals `complete_json_schema` (grammar-only equivalence).
- **`tests/lint/test_multi_plane_token_law_contract.py`** — pins the packer, the
  `TokenLawPlanes` `And`-combine over the real kernel, the decoder-stack dynamic
  loop, the `sovereign-llm` grammar∧policy wiring, and (the honesty lock) that
  the perf caveat + the SDD-500 external-proxy boundary stay documented.

Verified: `cargo test -p sovereign-token-law-mask -p sovereign-decoder-stack -p sovereign-llm`
pass; `cargo clippy` clean; `cargo fmt --check` clean; crate-inventory unchanged
(no new crate — 722); SDD/mandate/context lints green.

## Non-goals

- Constraining the external-proxy (`/v1/messages` → llama-server/vLLM) path (SDD-500 boundary, unchanged).
- An incremental grammar parser / cached per-state bitset (the perf follow-up).
- Deriving the *static* planes from real tool/safety sources (they are caller-supplied here, mirroring SDD-500 Q4 — a tracked next step).
- The unbuilt M00130 (XGrammar per-token bitmask) / M00131 (LLGuidance CPU mask) engines — `token_law_combine` remains the substrate those would feed as additional planes.
- Any change to `LogitPipeline`, the round engine, or cross-request law state.

## References

- SDD-500 (`docs/sdd/500-per-token-token-law-bitset.md`) — the per-token call site this composes on.
- `crates/sovereign-simd/src/cheats.rs:312` (`token_law_combine`), `crates/sovereign-token-law-mask/src/lib.rs` (`pack_allowed`, `TokenLawPlanes`), `crates/sovereign-decoder-stack/src/lib.rs` (`generate_dynamic_token_law_until`), `crates/sovereign-llm/src/lib.rs` (`complete_json_schema_with_laws`).
- `crates/sovereign-token-grammar-mask` (`TokenGrammarMask`), `crates/sovereign-json-schema-grammar` (`compile`).
- Milestone spec: `backlog/milestones/M002-control-word-injected-logic.md` (M00117 token-law-bitset); unbuilt M00130/M00131.
