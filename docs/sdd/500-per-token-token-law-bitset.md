# SDD-500 — Per-token token-law bitset: wiring the M002 bit-machine into the in-repo decode loop

> Status: draft · Mandate: **E11.M500** (control-bits band 500–599)
>
> Design pass (no code). Operator-directed 2026-07-21 ("still on the control
> bits, lets explore what we should do" → "Design the per-token hook"). This is
> the DOCUMENT/DESIGN stage artifact for the one genuine remaining M002 gap;
> implementation is gated on operator greenlight of the open questions below.

## Mission

M002 ("control-word injected logic") is real from the `u64` up: the control
word, the AVX-512 round engine (scalar-parity-proven), the 8-branch scheduler,
the M008 cheats, the service layer, and the gatewayd inspection routes are all
implemented, `unsafe`-audited, and tested. **The one true gap is the doc's own
admission** (`docs/src/avx-mode-bit-machine.md` § Honest boundaries): the
bit-machine has **zero call sites inside real token generation**. "Policy
becomes bits" is proven as a library and over standalone HTTP routes, but no
running model is actually *gated* by it.

This SDD scopes the first real per-token integration: use the existing
`token_law_combine` kernel to mask logits inside the in-repo decode loop, so a
packed **token-law allow-bitset actually constrains what a model may emit,
token by token**.

## What is real vs the gap (grounded)

Per the crate-reality map (2026-07-21):

- **Real kernel** — `sovereign_simd::cheats::token_law_combine(laws: &[&[u64]], combine: LawCombine) -> Vec<u64>` (`crates/sovereign-simd/src/cheats.rs:312`) + `allowed_token_count` (`:336`). Each *law* is a per-vocabulary **allow-bitset** (`⌈V/64⌉` `u64` words; bit `t` set = token `t` allowed). `And` = every law must allow (intersection); `Or` = union. Real VPTERNLOG path with a scalar reference. Exposed read-only at `POST /v1/token-law/allowed-mask` (`crates/sovereign-gatewayd/src/http.rs`).
- **Real seam** — `sovereign_logit_pipeline::LogitProcessor` is a trait `fn process(&self, history: &[usize], logits: &mut [f32])` (`crates/sovereign-logit-pipeline/src/lib.rs:37`); `LogitPipeline::apply` (`:98`) runs every processor over the logit row before sampling. The in-repo decode loops already call it: `sovereign-decode-loop::decode_next` samples right after `head.project(&context)` (`crates/sovereign-decode-loop/src/lib.rs:181→183`), and `sovereign-decoder-stack::generate_with` applies `LogitMask` per position then samples (`crates/sovereign-decoder-stack/src/lib.rs:396,416`).
- **The gap** — none of the decode crates import any M002 crate. `token_law_combine` is never invoked in a decode loop; the token-law route is inspection-only.

So the integration is not an architectural upheaval — it is **connecting one real kernel to one real seam** via a new `LogitProcessor`.

## The honest scope caveat (read this first)

Production serving (`POST /v1/messages`) **proxies out-of-process** to an
external engine (llama-server / vLLM) — the gateway translates to
`/v1/chat/completions` and forwards. Token generation happens outside this repo,
so the bit-machine **cannot** gate those tokens. This integration therefore
lands in the **in-repo decode stack** (`sovereign-decoder-stack`), the box's own
sovereign inference path. That is the honest, correct target because it:

1. makes "policy becomes bits" **true end-to-end for a running model** (the first real per-token call site), not just a library claim;
2. becomes a **production** constraint if/when the box serves from its own stack (the sovereignty direction — not proxying to llama-server); and
3. is fully testable today without external infrastructure.

It does **not** claim to constrain the external-proxy path. That would require
logit-level access the OpenAI proxy protocol does not provide, and is explicitly
out of scope here.

## Design

### The `TokenLawMask` logit processor

A new `LogitProcessor` in `sovereign-logit-pipeline` (or a small sibling crate
`sovereign-token-law-mask` depending on Q2):

```
struct TokenLawMask { allow: Vec<u64> }   // the combined allow-mask (⌈V/64⌉ words)

impl LogitProcessor for TokenLawMask {
    fn process(&self, _history: &[usize], logits: &mut [f32]) {
        for (t, l) in logits.iter_mut().enumerate() {
            let word = t >> 6;              // t / 64
            let bit  = t & 63;              // t % 64
            let allowed = self.allow.get(word).map_or(false, |w| (w >> bit) & 1 == 1);
            if !allowed { *l = f32::NEG_INFINITY; }
        }
    }
}
```

- The `allow` mask is produced upstream by `token_law_combine(&laws, And)` — the caller supplies one bitset per active *law* (grammar / tool / safety / schema / route — the M00117 classes), and the kernel intersects them.
- Plugs into the existing pipeline unchanged: `pipeline.with(Box::new(TokenLawMask::new(mask)))`. No change to `LogitPipeline` itself.
- Consumed by `sovereign-decoder-stack::generate_with` (and optionally `decode-loop::decode_next` — Q3) exactly where `LogitMask` is applied today.

### Where the laws come from (v1 vs later)

- **v1 (this SDD's build):** the law set is **caller-supplied** — the decode entry point accepts `laws: Vec<Vec<u64>>` (mirroring the `/v1/token-law/allowed-mask` request shape), combines them once per position (or once per request if static), and installs the `TokenLawMask`. This proves the mechanism with a concrete, testable law (e.g. "only these 10 tokens are legal").
- **Later (out of scope, tracked):** derive laws from a real constraint source — grammar (`sovereign-cfg-grammar` / `sovereign-json-schema-grammar`), tool schemas, or the unbuilt **M00130 (XGrammar per-token bitmask)** / **M00131 (LLGuidance CPU mask)** spec rows. `token_law_combine` is the natural substrate those would feed; this SDD makes the consumer real first.

### Determinism + parity

The mask op is exact scalar (`f32::NEG_INFINITY`), no AVX needed for
correctness — a masked token has zero sampling probability deterministically.
The AVX-512 acceleration (VPTERNLOG) applies only to the *law combine* step
(`token_law_combine`), which already carries a scalar reference. A golden test
pins: given a known allow-mask, exactly the disallowed tokens go to `-inf` and
`allowed_token_count` matches the survivors.

### avx-mode interaction (Q1)

The round engine is gated on `avx-mode` custom/hybrid (it is an *acceleration*
path). The token-law **mask is correctness policy, not acceleration** — a legal
token set should hold regardless of how AVX is configured. Proposed default:
**the mask always applies when a law set is present**; only the AVX-accelerated
combine chooses the VPTERNLOG vs scalar path per `avx-mode`. Flagged for operator
confirmation because it differs from the round-engine's gating.

## Staging plan (methodology stage gates)

| Stage | Deliverable | Gate |
|---|---|---|
| **document** | *this SDD* — problem, seam, contract, caveat, open questions | operator reviews; open questions answered |
| **design** | SDD moves to `accepted` with the Q1–Q5 decisions folded in | trade-offs settled |
| **scaffold** | `TokenLawMask` struct + trait impl signature + test stubs; the decode entry-point parameter; no behavior | compiles; stubs only |
| **implement** | the `process()` body + wiring into `decoder-stack::generate_with` + a cockpit/CLI demo | a banned-token bitset provably masks generation |
| **test** | golden mask test + a real generate() run showing disallowed tokens never emitted + `token_law_combine` parity | full pass; no regression |

## Tests (planned)

1. **Unit** — `TokenLawMask::process` sets exactly the disallowed logits to `-inf`; boundary words (V not a multiple of 64) handled; empty mask = all masked / full mask = no-op.
2. **Integration** — `decoder-stack::generate_with` given a mask that allows only token set S never emits a token outside S across N positions.
3. **Parity** — the combined mask equals `token_law_combine` scalar-ref output.
4. **Honesty** — a doc/contract test asserting the external-proxy path is documented as out of scope (so no future reader over-claims coverage).

## Open questions (operator decisions before design→scaffold)

- **Q1 — avx-mode gating:** mask always-on when laws present (proposed), or gate the whole stage on custom/hybrid like the round engine?
- **Q2 — crate home:** add `TokenLawMask` inside `sovereign-logit-pipeline`, or a dedicated `sovereign-token-law-mask` crate it depends on? (Pipeline already depends on `logit-mask` + `no-repeat-ngram`; a sibling keeps M002 deps out of the generic pipeline.)
- **Q3 — targets:** wire `decoder-stack` only, or also `decode-loop::decode_next`?
- **Q4 — law source for v1:** caller-supplied bitset (proposed), or make the first real law a grammar/tool constraint now?
- **Q5 — M00130/M00131 relationship:** treat this as the substrate the future XGrammar/LLGuidance masks feed, or a parallel path?

## Non-goals

- Constraining the external-proxy (`/v1/messages` → llama-server/vLLM) generation path.
- Building a grammar/tool constraint engine (XGrammar/LLGuidance — separate M008 spec rows).
- Any change to `LogitPipeline`'s existing processors or the round engine.
- Distributed / cross-request law state.

## References

- Crate-reality map (2026-07-21) — real kernels, per-token gap confirmed, exact seam.
- `docs/src/avx-mode-bit-machine.md` § Honest boundaries (the admission this closes).
- `crates/sovereign-simd/src/cheats.rs:312` (`token_law_combine`), `crates/sovereign-logit-pipeline/src/lib.rs:37,98`, `crates/sovereign-decoder-stack/src/lib.rs:396,416`, `crates/sovereign-decode-loop/src/lib.rs:181`.
- Milestone spec: `backlog/milestones/M002-control-word-injected-logic.md` (M00117 token-law-bitset); unbuilt M00130/M00131 (`backlog/modules/INDEX.md:191`).
