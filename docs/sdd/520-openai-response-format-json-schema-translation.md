# SDD-520 — Full JSON-Schema → token-law `Schema` translation (`response_format` json_schema v2)

> Status: active · Mandate: **E11.M520** (control-bits band 500–599)
>
> Cross-link: the v2 of SDD-519's `json_schema` mode — completing the OpenAI chat shim's `response_format` support (F-2026-086) against the M00117 **grammar plane** (SDD-503/512). The nineteenth SDD in the control-bits band, directly extending SDD-519.
>
> Number band: **500–599 (control-bits session)**
>
> **v1 shipped 2026-07-24** — operator-directed (*"we continue"*). SDD-519's own named roadmap item: `json_schema` mode now translates the **standard JSON-Schema dialect** the client actually sends, not just the project's internal `Schema` serde representation.

## Mission

SDD-519 wired `response_format` into the grammar plane so JSON mode is *enforced per token*, not merely prompted. But its `json_schema` path had a real gap in its honest scope: it accepted a schema only when the caller's JSON `serde_json::from_value::<Schema>` deserialized into the project's **own** tagged `Schema` representation (e.g. `{"Object":[["ok","Boolean"]]}`) — a shape no real OpenAI client emits. Clients send the **standard JSON-Schema dialect**:

```json
{"type":"object","properties":{"ok":{"type":"boolean"}},"required":["ok"]}
```

which never matched the internal repr and so **silently degraded to `Schema::Any`** — valid JSON enforced, but the client's *shape* unenforced. This SDD closes that: a total translator maps the standard dialect into the token-law `Schema` subset, so a real client's `json_schema` request is confined to its shape per decode step.

## Design

### The translator — `from_json_schema` (in `sovereign-json-schema-grammar`)

`pub fn from_json_schema(value: &serde_json::Value) -> Schema` — a **total** mapping (it never fails; it always returns *some* `Schema`). The contract is: any construct the token-law subset cannot faithfully express degrades to `Schema::Any` (enforce *valid JSON*, shape unconstrained) rather than erroring or over-constraining. **Under-constraining is the safe direction** — the output is still valid JSON the client can parse; over-constraining (e.g. dropping a schema's optional keys, then rejecting output that includes them) would mask output the client's own schema permits, breaking the client.

Mapped faithfully:

- `{"type":"string"}` → `Schema::StringType`; with a string `enum` → `Schema::Enum`;
- `{"type":"integer"}` → `Schema::Integer`; `{"type":"number"}` → `Schema::Number`;
- `{"type":"boolean"}` → `Schema::Boolean`; `{"type":"null"}` → `Schema::Null`;
- `{"type":"array","items":S}` → `Schema::Array` of the translated item (absent `items` → array of `Schema::Any`);
- `{"type":"object","properties":{…},"required":[…]}` → `Schema::Object` **iff** `required` is a duplicate-free bijection with the property keys (the subset's object is *all-required, fixed key order, no extras*); key order follows the client's `required` array;
- a bare `{"enum":[strings…]}` with no `type` → `Schema::Enum`.

Degraded to `Schema::Any` (honest under-constraint):

- a `type` that is an array (union / nullable — `["string","null"]`) or absent / unknown;
- an object with **optional** properties (`required ⊊ properties`), a duplicated `required`, a `required` entry with no matching property, or a non-object `properties`;
- `$ref`, `anyOf` / `allOf` / `oneOf`, tuple `items` (an array of schemas), a boolean sub-schema, or a non-string `enum`.

Translation **recurses**, so degradation is *localized*: an untranslatable leaf inside an otherwise-faithful object becomes `Schema::Any` at that field only, not the whole object.

### The rewire — `sovereign-gatewayd`

`parse_response_format` drops the `serde_json::from_value::<Schema>(…)` attempt and instead maps the client's `json_schema.schema` through `from_json_schema(…)`. `json_object` → `Schema::Any` and `text`/absent → `None` are unchanged; a `json_schema` with no `schema` field → `Schema::Any`. Everything downstream (the `ServingTokenLaw` law object, the `generate_chat_cached` `law.is_none()` cache gate, both decode sites) is unchanged — this SDD only improves *which* `Schema` the shape maps to.

### Honest scope

- Enforcement stays **local-only** (proxies forward `response_format` upstream, no logit access claimed) — unchanged from SDD-519.
- The token-law subset is *structural*: it has no bounded-integer, ranged-number, string-`pattern`, `format`, or `minItems`/`maxItems` terminals, so JSON-Schema value constraints (`minimum`, `maxLength`, `pattern`, `format`, array length bounds) are **not** enforced — a schema that carries them still maps by its `type`, and the extra constraints are simply not masked. This is faithful to the grammar's expressive power, not a silent drop of a shape it *could* enforce.
- **Optional-property** objects and **union** types are the two common shapes that degrade to `Schema::Any`; expressing them faithfully needs new `Schema` variants (an object grammar with optional keys; an alternation variant) — the natural v3.

## What shipped

- **`sovereign-json-schema-grammar`** — `pub fn from_json_schema` + the `string_enum` / `object_from_json_schema` helpers; +5 tests (scalars+enums, arrays, all-required objects in `required` order, unrepresentable→`Any` degradation, nested recursion). Grammar-crate tests 14 → 19.
- **`sovereign-gatewayd`** — `parse_response_format` translates via `from_json_schema` (the internal-repr `from_value::<Schema>` deserialize is gone); the `parse_response_format` unit test now uses standard JSON-Schema input (all-required object → typed `Object`; an optional-property object → `Schema::Any`; a `json_schema` with no `schema` → `Schema::Any`).
- **`tests/lint/test_gateway_generation_contract.py`** — SDD-520 assertions: the grammar crate exposes `from_json_schema` (+ the `object_from_json_schema` / `string_enum` helpers), `parse_response_format` uses it, and the internal-repr `serde_json::from_value::<Schema>` deserialize is gone.
- Registration: SDD-520 + INDEX row 520 + mandate **E11.M520** + catalog regen + context `sdd files` 230→231.

## Non-goals / roadmap

- **JSON-Schema value constraints** — `minimum`/`maximum`, `minLength`/`maxLength`, `pattern`, `format`, `minItems`/`maxItems`: the grammar has no bounded/patterned terminals, so these are not enforced. Enforcing them needs new grammar primitives (bounded repetition, a regex-string terminal — the latter could ride the existing `sovereign-regex-*` plane).
- **Optional-property objects** — need a `Schema::Object` variant that marks per-key optionality (and an object grammar that permits any subset of the optional keys, in a canonical order); today they degrade to `Schema::Any`.
- **Union types** (`anyOf` / `["string","null"]`) — need an alternation `Schema` variant; today they degrade to `Schema::Any`.
- **`response_format` + tools composition** — still deferred (SDD-519 carry-over).

## References

- The predecessor: `docs/sdd/519-openai-shim-response-format-json-mode.md` (the `response_format` wiring + `Schema::Any`; its roadmap named this translator).
- The finding: `docs/review/phase-1/99-findings-ledger.md` (F-2026-086, the `response_format` follow-up).
- The translator: `crates/sovereign-json-schema-grammar/src/lib.rs` (`from_json_schema`, `object_from_json_schema`, `string_enum`).
- The wiring: `crates/sovereign-gatewayd/src/main.rs` (`parse_response_format`).
- The guard: `tests/lint/test_gateway_generation_contract.py`.
