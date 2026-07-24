# SDD-519 — OpenAI `response_format` JSON mode, enforced by the token-law grammar plane

> Status: active · Mandate: **E11.M519** (control-bits band 500–599)
>
> Cross-link: connects the OpenAI chat shim (F-2026-086) to the M00117 **grammar plane** (SDD-503/512). The eighteenth SDD in the control-bits band, after the route-source pair (SDD-517/518).
>
> Number band: **500–599 (control-bits session)**
>
> **v1 shipped 2026-07-24** — operator-directed (*"1, 2, and 3 now go, one big PR"*). The `response_format` residual of F-2026-086 is closed here as a first-class capstone: OpenAI JSON mode is not merely *prompted* on this shim, it is **enforced per token** by the same checkpoint-free grammar engine the token-law route inspects.

## Mission

OpenAI's `response_format: {type: "json_object"}` asks the model to emit valid JSON; `{type: "json_schema", json_schema: {schema: …}}` asks for a specific shape. On most stacks this is a *prompt hint* the model can violate. This project already has an exact mechanism to make it a **guarantee**: the M00117 grammar plane (SDD-503) compiles a `Schema` into a grammar and, via `sovereign-token-law-fuse` + the serving boundary (SDD-512), masks the logits each decode step so only tokens that keep the output a valid prefix of a conforming JSON value survive. This SDD wires `response_format` into that plane, so a `/v1/chat/completions` request that asks for JSON **gets** JSON — the decode is confined, not hoped-for.

## Design

### The new grammar — `Schema::Any` (in `sovereign-json-schema-grammar`)

The `Schema` enum had typed variants (Boolean/Integer/Number/String/Enum/Object/Array) but no "any JSON value" — exactly what `json_object` mode needs (valid JSON of *any* shape). This adds `Schema::Any`, a **recursive** value grammar: `VALUE → OBJECT | ARRAY | STRING | NUMBER | BOOL | NULL`, with `OBJECT`/`ARRAY` referring back to `VALUE` through members/elements. The `value` non-terminal is allocated and cached **before** its rules are defined so the self-recursion resolves. It reuses the existing `string`/`number`/`boolean`/`null`/`ws` primitives, so it composes with the existing incremental parser (`sovereign-token-grammar-mask`) unchanged. +1 grammar test walks valid JSON (scalars, nested objects/arrays, whitespace) accepted and malformed JSON (unclosed, trailing comma, unquoted key, missing comma) rejected.

### The parse + serving wiring — `sovereign-gatewayd`

- `parse_response_format(req) -> Option<Schema>`: `json_object` ⇒ `Schema::Any`; `json_schema` ⇒ the caller's `schema` when it deserializes into the token-law `Schema` subset, else `Schema::Any` (still enforce valid JSON); `text` / absent ⇒ `None` (unconstrained).
- `response_format_law(req)` builds a `ServingTokenLaw { schema: Some(…), .. }` — reusing the SDD-512 serving law object, so the grammar drives the same per-step `fused_mask` the token-law engine uses.
- `generate_chat_cached` gains an `Option<&ServingTokenLaw>`: a law-carrying request is **non-cacheable** (a constrained decode differs from an unconstrained one), so the cache is gated on `law.is_none()` (alongside the SDD-penalties/logit_bias `greedy && logit_bias.is_empty()` gates) and the request routes through `generate_chat_with_sampler_law` with the grammar law. Both `/v1/chat/completions` decode sites (streaming + non-streaming) pass the response-format law.

### Honest scope

- Enforcement is **local-only** — the grammar masks the local `QuantModel`'s logits. A request routed to a proxy backend is forwarded upstream (which applies its own `response_format`); no logit access is claimed for proxies.
- `json_schema` mode maps a **token-law-shaped** `Schema` (the project's own subset), not the full JSON-Schema dialect; an unmappable schema degrades to `Schema::Any` (valid JSON, shape unenforced) rather than erroring. A full JSON-Schema → `Schema` translator is a follow-up.
- Applies on the non-tool chat path; `response_format` combined with server-side tool use is not composed in v1.

## What shipped

- **`sovereign-json-schema-grammar`** — `Schema::Any` variant + the recursive `any()` builder; +1 test.
- **`sovereign-gatewayd`** — `parse_response_format` + `response_format_law`; `generate_chat_cached` gains the `Option<&ServingTokenLaw>` param + the `law.is_none()` cache gate; both `/v1/chat/completions` decode sites drive the grammar law; +1 `parse_response_format` unit test.
- Registration: SDD-519 + INDEX + mandate E11.M519 + catalog regen + context `sdd files` 229→230 + the F-2026-086 ledger follow-up + `tests/lint/test_gateway_generation_contract.py` guards.

## Non-goals / roadmap

- **Full JSON-Schema → `Schema` translation** — v1 accepts the token-law `Schema` shape for `json_schema` mode; a standard-dialect translator is the natural v2.
- **`n` (multiple completions)** — the last remaining F-2026-086 residual (needs the worker-pool multi-decode).
- **`response_format` + tools composition** — deferred.

## References

- The finding: `docs/review/phase-1/99-findings-ledger.md` (F-2026-086, the `response_format` follow-up).
- The grammar plane: `docs/sdd/503-*` (regex/grammar), `docs/sdd/512-token-law-serving-boundary.md` (the serving law object + per-step masking).
- The new grammar: `crates/sovereign-json-schema-grammar/src/lib.rs` (`Schema::Any`, `any()`).
- The wiring: `crates/sovereign-gatewayd/src/main.rs` (`parse_response_format`, `response_format_law`), `crates/sovereign-gatewayd/src/lib.rs` (`generate_chat_cached` law gate).
