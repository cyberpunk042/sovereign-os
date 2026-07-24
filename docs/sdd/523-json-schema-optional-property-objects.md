# SDD-523 — Optional-property objects in the JSON-Schema→`Schema` translator

> Status: active · Mandate: **E11.M523** (control-bits band 500–599)
>
> Cross-link: the second (and final) half of SDD-520's named v3 roadmap — after unions (SDD-522), this closes optional-property objects. The twenty-second SDD in the control-bits band.
>
> Number band: **500–599 (control-bits session)**
>
> **v1 shipped 2026-07-24** — operator-directed (*"all of these, a big PR"*). With this, the `response_format` JSON-Schema translator faithfully enforces every common structured-output shape.

## Mission

SDD-520 mapped all-required objects to `Schema::Object` and degraded **optional-property** objects (`required ⊊ properties`) to `Schema::Any` — never over-constrain by dropping the optional keys. But optional fields are as common as nullable ones in real structured-output schemas, so a large class stayed shape-unenforced. This SDD closes it: an object with a mix of required + optional properties is now enforced by a grammar that accepts **any subset of the optionals**, in a pinned order, with correct comma separation and no extras.

## Design

### The new grammar — `Schema::ObjectOpt`

`Schema::ObjectOpt(Vec<(String, Schema, bool)>)` — `(key, schema, required)` in a fixed key order. Compiled with the standard **two-state (first/rest)** construction that a CFG uses for a fixed-order optional-member list:

- for each key position `i`, two tail non-terminals: `first[i]` = the tail with **nothing emitted yet** (an emitted member carries no leading comma), `rest[i]` = the tail with **something already emitted** (an emitted member is preceded by `WS , WS`);
- a **required** key at `i` has only the emit rule (it must appear); an **optional** key adds a skip rule (`first[i] → first[i+1]`, `rest[i] → rest[i+1]`);
- base: `first[n] = rest[n] = ε`; the object is `'{' WS first[0] WS '}'`.

This threads "have we emitted a member yet" through the grammar, so commas separate exactly the present members — no leading, trailing, or doubled comma — while required keys are mandatory and order is pinned. `Object` (all-required) is unchanged; `ObjectOpt` extends it.

### The translator — `object_from_json_schema`

`required` must be duplicate-free and a **subset** of the property keys (a dangling required name → `Schema::Any`). When `required` is exactly the key set → the all-required `Object` (unchanged). When some properties are optional → `ObjectOpt`, key order following the `properties` map, each field flagged with its required-ness.

### Honest scope

- **Extra properties** are still rejected (`additionalProperties:false` is the modeled default — the constrained decode never emits an unknown key), matching `Object`.
- Value constraints (`minimum`/`pattern`/…) remain unenforced (SDD-520 carry-over — the grammar has no such terminals).

## What shipped

- **`sovereign-json-schema-grammar`** — `Schema::ObjectOpt` variant + the two-state compile arm; `object_from_json_schema` routes optional-property objects to it. +3 tests (translator mapping incl. the all-required + dangling-required cases; the grammar accepting any subset in order with correct commas and rejecting order/comma/extra/type violations; an all-optional object accepting `{}`). Grammar-crate tests 20 → 23.
- **`sovereign-gatewayd`** — no change (transparent through `parse_response_format`); its `parse_response_format` unit test updated (an optional-property `json_schema` now maps to `ObjectOpt`, no longer `Any`).
- **`tests/lint/test_gateway_generation_contract.py`** — guards the `ObjectOpt` variant.
- Registration: SDD-523 + INDEX row 523 + mandate **E11.M523** + catalog regen + context `sdd files` (part of the 232→235 batch).

## Non-goals / roadmap

- **`additionalProperties: true`** (open objects with known + arbitrary extra keys) — the modeled default is closed; an open-object grammar is a further increment.
- Value constraints (`minimum`/`pattern`/`format`/length) — SDD-520 carry-over.

## References

- The predecessors: `docs/sdd/520-openai-response-format-json-schema-translation.md` (the translator; its roadmap named this), `docs/sdd/522-json-schema-union-types.md` (the union half).
- The grammar + translator: `crates/sovereign-json-schema-grammar/src/lib.rs` (`Schema::ObjectOpt`, `object_from_json_schema`).
