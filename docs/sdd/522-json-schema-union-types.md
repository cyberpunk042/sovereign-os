# SDD-522 — Union types in the JSON-Schema→`Schema` translator (`anyOf` / `oneOf` / nullable)

> Status: active · Mandate: **E11.M522** (control-bits band 500–599)
>
> Cross-link: the v3 of SDD-520's JSON-Schema translator — the *union* half of SDD-520's named roadmap (*"optional-property objects and union types … the natural v3"*). The twenty-first SDD in the control-bits band, extending SDD-519/520.
>
> Number band: **500–599 (control-bits session)**
>
> **v1 shipped 2026-07-24** — operator-directed (*"go"*). `response_format: {json_schema}` now enforces the two most common union shapes — `anyOf`/`oneOf` and the nullable-field `type` array — that SDD-520 degraded to `Schema::Any`.

## Mission

SDD-520 translated the standard JSON-Schema dialect into the token-law `Schema` subset, but its honest scope left **unions** unenforced: a `type` array (`{"type":["string","null"]}` — the ubiquitous nullable-field idiom) and the `anyOf`/`oneOf` keywords all degraded to `Schema::Any` (valid JSON, shape free). Nullable fields and small `anyOf` unions are pervasive in real structured-output schemas, so that gap left a lot of shape unenforced. This SDD closes the union half: the translator now maps those to a first-class union grammar, so a `response_format` request that says "a string or null" is actually confined to a string or null per decode step.

## Design

### The new grammar — `Schema::OneOf` (in `sovereign-json-schema-grammar`)

The `Schema` enum gains `OneOf(Vec<Schema>)` — a value conforming to **any one** of the listed alternatives. It compiles to plain **alternation**: one grammar rule per alternative on a shared non-terminal (the exact primitive `Schema::Enum` and the `Any` value-grammar already use), so it composes with the existing incremental parser unchanged. `oneOf`'s *exactly-one* semantics can't be enforced by a context-free grammar (a CFG can't reject a value that matches two branches), so `oneOf` is treated as `anyOf` — an honest under-constraint, consistent with the translator's "never over-constrain" contract.

### The translator mapping — `from_json_schema`

- `{"anyOf":[…]}` / `{"oneOf":[…]}` → `union_of(each translated)`. Checked first (before `type`), since a co-present `type` would mean an intersection the subset can't express — the union takes precedence (under-constraint).
- a **`type` array** `{"type":["string","null"]}` → `union_of` of each type name mapped via `type_name_to_schema` (scalars map exactly; a structural `object`/`array` name in a type array has no accompanying `properties`/`items`, so it maps to `Any`).
- `allOf` (intersection) stays degraded to `Schema::Any` — not expressible by a CFG.

`union_of` carries the simplifications: a union that **contains `Any`** *is* `Any` (`Any` accepts every JSON value, so it subsumes the union — keeping a `OneOf` would be redundant and over-list); a **single** alternative is that alternative (no wrapper); an **empty** union degrades to `Any`. Translation still recurses, so a union nested as an object property (`{"v": {"type":["integer","null"]}}`) is enforced at that field.

### The serving boundary — `sovereign-gatewayd`

**Unchanged.** `parse_response_format` already routes `json_schema.schema` through `from_json_schema` (SDD-520); the richer output is transparent to it, the serving law, and the cache gate.

### Honest scope

- `oneOf` is enforced as `anyOf` (see above) — the mutual-exclusivity is not checked.
- A `type` array (or `anyOf`) that mixes a scalar with an unstructured `object`/`array` collapses to `Any` — the union is only as tight as its loosest member.
- **Optional-property objects** — the *other* half of SDD-520's v3 roadmap — are **still** deferred: expressing "any subset of the optional keys, comma-separated, in canonical order" needs a different object-grammar construction (variable comma placement) whose correctness is subtle enough to warrant its own increment. They continue to degrade to `Any`.
- JSON-Schema **value** constraints (`minimum`/`pattern`/`format`/…) remain unenforced (SDD-520 scope — the grammar has no bounded/patterned terminals).

## What shipped

- **`sovereign-json-schema-grammar`** — `Schema::OneOf` variant + its alternation `compile` arm; `union_of` + `type_name_to_schema` helpers; `from_json_schema` maps `anyOf`/`oneOf` + `type` arrays. +1 union test (nullable `type` array, `anyOf`, `oneOf`-as-`anyOf`, single-member collapse, empty→`Any`, nested-in-object) + the SDD-520 degrade test updated (the union cases moved from `Any` to `OneOf`; new still-degrading cases: type-array with a structural member, `allOf`, a union with an unrepresentable member). Grammar-crate tests 19 → 20.
- **`sovereign-gatewayd`** — no change (transparent through `parse_response_format`).
- **`tests/lint/test_gateway_generation_contract.py`** — SDD-522 assertions (the `OneOf` variant, `union_of`/`type_name_to_schema`, `anyOf`/`oneOf` mapped not degraded).
- Registration: SDD-522 + INDEX row 522 + mandate **E11.M522** + catalog regen + context `sdd files` 232→233.

## Non-goals / roadmap

- **Optional-property objects** — the remaining half of SDD-520's v3 roadmap (needs the variable-comma object grammar); still degrades to `Any`.
- **`oneOf` exactly-one enforcement** — a CFG can't reject a value matching two branches; would need a post-parse check, not a grammar.
- **JSON-Schema value constraints** (`minimum`/`maximum`/`pattern`/`format`/length bounds) — SDD-520 carry-over; need bounded/regex terminals.

## References

- The predecessors: `docs/sdd/519-openai-shim-response-format-json-mode.md` (`Schema::Any` + the wiring), `docs/sdd/520-openai-response-format-json-schema-translation.md` (the translator; its roadmap named this union work).
- The finding: `docs/review/phase-1/99-findings-ledger.md` (F-2026-086, the `response_format` follow-up chain).
- The grammar + translator: `crates/sovereign-json-schema-grammar/src/lib.rs` (`Schema::OneOf`, `union_of`, `type_name_to_schema`, `from_json_schema`).
- The guard: `tests/lint/test_gateway_generation_contract.py`.
