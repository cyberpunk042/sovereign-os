# SDD-502 — Incremental Earley parser: per-token grammar masking without re-parsing the prefix

> Status: active · Mandate: **E11.M502** (control-bits band 500–599)
>
> Cross-link: closes **E11.M502** (incremental grammar parser), the third SDD in
> the control-bits band, closing the honest-perf caveat SDD-500/501 both flagged.
>
> Number band: **500–599 (control-bits session)**
>
> **v1 shipped 2026-07-21** — operator-directed ("Good, we continue, another big
> PR" → chose "Incremental grammar parser"). The design below is realized: the
> grammar mask no longer re-parses the whole prefix each token, with **bit-for-bit
> identical** output. See § "What shipped".

## Mission

SDD-501 shipped composed constrained decoding and stated its honest performance
boundary verbatim: *"`TokenGrammarMask::mask` re-parses the whole prefix each
step … that is the dominant per-token cost."* This SDD closes that — the single
biggest cost in every grammar-constrained decode path (`complete_json_schema`,
`complete_regex`, and SDD-501's `complete_json_schema_with_laws`).

The fix is an **incremental Earley parser**: parse the committed prefix once into
a persistent chart, and validate each candidate token by feeding its characters
onto that chart and rolling back — cost proportional to the *token's* length, not
the prefix's. Output is provably identical to the from-scratch recognizer.

## What was real vs the gap (grounded 2026-07-21)

- **Real — a correct Earley recognizer.** `sovereign_cfg_grammar::Grammar` (`crates/sovereign-cfg-grammar/src/lib.rs`) with `allowed_next` / `is_live_prefix` / `accepts`, all routed through `parse_chart(input)` — predict/scan/complete over a dotted-rule chart. Correct, prefiltered, `forbid(unsafe_code)`.
- **Real — the token mask.** `sovereign_token_grammar_mask::TokenGrammarMask::mask(prefix)` (`crates/sovereign-token-grammar-mask/src/lib.rs`): one `allowed_next(prefix)` for a first-character prefilter, then `is_live_prefix(prefix + token)` for every surviving token.
- **The gap — every call rebuilds the chart from scratch.** `parse_chart` (`cfg-grammar/src/lib.rs`) allocates a fresh chart/`seen` over `0..=n` and re-seeds `S[0]` **every call** — zero cached or incremental state. So `mask(prefix)` costs one full parse of `prefix` (for `allowed_next`) **plus one full re-parse of `prefix + token` for every prefilter survivor**. With `S` survivors and prefix length `L`, that is ≈ `O(S · L · G)` per step (`G` = grammar work per position); across a generation where `L` grows to `N`, ≈ `O(N² · S · G)` — quadratic in sequence length.

## The key property that makes it incremental (and exact)

The Earley chart is a **pure function of the prefix**: building the state for
position `k+1` only ever *appends* it — SCAN reads `S[k]`, predict/complete write
only the new state, and `S[0..=k]` are never mutated. Two consequences:

1. A committed prefix's chart can be **extended** one character at a time instead
   of rebuilt.
2. A candidate continuation can be fed and then **rolled back** by simply
   truncating the appended states — restoring the committed chart exactly.

Because the operations are the *same* predict/scan/complete in the *same* order,
the incremental chart's state at position `L` is byte-identical to
`parse_chart(prefix)`'s — so `next_set` / `is_live` / `accepts` off the
incremental chart equal `allowed_next` / `is_live_prefix` / `accepts` exactly.
Parity is not approximate; it is the same computation, persisted.

## Design

### 1. The incremental substrate — `sovereign-cfg-grammar`

A new public `EarleyChart` (opaque handle over the chart + `seen` sets) plus
`Grammar::start_chart()`:

```
let mut ec = grammar.start_chart();     // seed + close S[0]
ec.feed(&grammar, c);                    // SCAN + close one position; -> still parseable?
ec.feed_str(&grammar, prefix);           // feed many chars
let base = ec.chars_consumed();
ec.feed_str(&grammar, token);            // speculative continuation
let live = ec.is_live(&grammar);         // == grammar.is_live_prefix(prefix+token)
ec.rollback_to(base);                    // exact restore — O(token length)
ec.next_set(&grammar);                   // == grammar.allowed_next(prefix)
ec.accepts(&grammar);                    // == grammar.accepts(prefix)
```

`feed` appends exactly one state; `rollback_to` truncates back. The from-scratch
`allowed_next` / `is_live_prefix` / `accepts` stay **unchanged** — they are the
parity oracle the incremental path is tested against.

### 2. Within-call incremental mask — `TokenGrammarMask::mask` (drop-in)

`mask(prefix)` now parses the prefix **once** into an `EarleyChart`, then
validates each surviving token by `feed`-then-`rollback_to` on that committed
chart — no per-token full re-parse. The signature and output are unchanged, so
**every existing caller inherits the speedup with zero code change**
(`complete_json_schema`, `complete_regex`, `complete_json_schema_with_laws`).
Per-step cost drops from ≈ `O(S · L · G)` to ≈ `O(L · G + S · t · G)` (`t` =
token length), removing the survivors × prefix-length blow-up.

### 3. Fully-incremental stateful mask — `IncrementalGrammarMask`

`mask` still re-parses the prefix once per step. `IncrementalGrammarMask` holds
the committed `EarleyChart` across steps and `advance`s it by the newly-accepted
characters, so the per-step prefix cost is only the *new* characters:
≈ `O(new_chars · G + S · t · G)` per step → **linear** across a generation. API:
`new` · `mask(&mut self)` (feed-then-rollback off the committed chart, leaving it
unchanged) · `advance(text)` / `advance_token(id)` (permanent commit) ·
`eos_allowed()`.

## Honest boundaries

- **Parity is exact, and it is the acceptance test.** The unchanged
  `prefilter_matches_full_check` + `serde_round_trip` (`mask == mask`) tests, plus
  new `EarleyChart`-vs-from-scratch parity tests over several grammars and dead
  ends, pin bit-for-bit equality. The incremental path is a *speed* change, never
  a *behaviour* change.
- **The stateful path is character-domain, and deliberately not auto-wired.**
  `IncrementalGrammarMask` operates in the grammar's character domain. A
  token-driven loop may use it only when the tokenizer is *char-concatenative*
  (`decode(a) + decode(b) == decode([a, b])`) — feed each accepted token's decoded
  text. The byte-level BPE path satisfies this; a merge-BPE tokenizer generally
  does not. So it ships as a **substrate** for callers that can guarantee that
  property; the LLM wiring keeps the stateless, drop-in `TokenGrammarMask::mask`
  (also incremental, per-call — no concatenation assumption). This mirrors the
  SDD-500/501 doctrine of shipping the capability behind an honest boundary rather
  than making an unsafe assumption.
- **This is complexity, not micro-optimization.** No SIMD, no `unsafe`; the win is
  algorithmic (`forbid(unsafe_code)` holds in both crates).

## What shipped (2026-07-21)

- **`crates/sovereign-cfg-grammar`** — `EarleyChart` + `Grammar::start_chart` /
  `feed` / `feed_str` / `rollback_to` / `next_set` / `is_live` / `accepts` /
  `chars_consumed`. +3 tests: `incremental_chart_matches_from_scratch` (parity vs
  `allowed_next`/`is_live_prefix`/`accepts` across growing prefixes on
  balanced/number/expr grammars incl. dead ends), `feed_then_rollback_restores_state`
  (speculative feed + exact restore), `incremental_commit_tracks_stepwise` (+ deep
  nesting). `forbid(unsafe_code)`.
- **`crates/sovereign-token-grammar-mask`** — `mask()` rewired to the within-call
  incremental path (drop-in, exact parity); new stateful `IncrementalGrammarMask`.
  +3 tests: `incremental_masker_matches_stateless` (stateful ≡ stateless at every
  step), `incremental_masker_advance_token_tracks_eos`, `stateless_mask_large_prefix_matches_brute`.
- **No new crate** (722 unchanged); no change to any caller's signature.
- **`tests/lint/test_incremental_grammar_parser_contract.py`** — pins the
  `EarleyChart` API, the `feed`/`rollback` append-only contract, the drop-in
  incremental `mask()` (no per-token `is_live_prefix`), and the honest
  char-concatenative caveat on the stateful masker.

Verified: `cargo test -p sovereign-cfg-grammar -p sovereign-token-grammar-mask`
(14 + 14 pass) + every downstream consumer green (`sovereign-llm` 79 lib + 28
runtime, `sovereign-json-schema-grammar` 13, `sovereign-token-law-mask` 9,
`sovereign-decoder-stack` 37 — exact parity inherited); `cargo clippy -D warnings`
+ `cargo fmt --check` clean.

## Non-goals

- Changing any observable grammar/mask behaviour — this is a speed change with bit-for-bit-identical output.
- Auto-wiring the stateful masker into the byte-BPE LLM path (the char-concatenative caveat; offered as a substrate).
- SIMD / `unsafe` acceleration of the chart (the win here is algorithmic; a bitset-per-state representation is a separate future).
- Grammar features (the recognizer's language coverage is unchanged).

## References

- SDD-501 (`docs/sdd/501-multi-plane-token-law-composition.md`) § "Honest performance boundary" — the caveat this closes.
- `crates/sovereign-cfg-grammar/src/lib.rs` (`EarleyChart`, `start_chart`, `parse_chart`, `allowed_next`), `crates/sovereign-token-grammar-mask/src/lib.rs` (`TokenGrammarMask::mask`, `IncrementalGrammarMask`).
- Downstream: `crates/sovereign-llm/src/lib.rs` (`complete_json_schema*`, `complete_regex`), `crates/sovereign-token-law-mask` (SDD-500/501 planes).
