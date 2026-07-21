# SDD-503 — Real constraint-source planes: regex as a token-law plane + multi-source composition

> Status: active · Mandate: **E11.M503** (control-bits band 500–599)
>
> Cross-link: closes **E11.M503** (real constraint-source planes), the fourth SDD
> in the control-bits band, discharging the "real sources" step SDD-500 (Q4) and
> SDD-501 (Non-goal) both parked.
>
> Number band: **500–599 (control-bits session)**
>
> **v1 shipped 2026-07-21** — operator-directed ("Good, we continue, another big
> PR"). The design below is realized: a running model can now be confined by
> **grammar ∧ regex ∧ policy at once**, with the regex plane derived from a real
> constraint source (not a hand-built bitset). See § "What shipped".

## Mission

SDD-501 made policy planes *compose* (grammar ∧ static policy), but the policy
planes were **caller-supplied bitsets** — hand-built, not derived from any real
constraint. Both prior SDDs parked the same next step verbatim: SDD-500 Q4
("derive laws from a real grammar/tool source") and SDD-501's Non-goals
("deriving the static planes from real tool/safety sources — a tracked next
step"). This SDD closes it for the sources that already emit the right shape.

The genuinely-new capability: **compose multiple independent real constraint
sources per step** — a JSON-schema grammar plane *and* a regular-expression plane
*and* static policy planes, all AND-combined through the real `token_law_combine`
kernel, so the model is confined by every one of them simultaneously. Nothing in
the repo could express "grammar ∧ regex ∧ policy" before.

## What was real vs the gap (grounded 2026-07-21)

- **Real — the regex source already emits the plane shape.** `sovereign_regex_constrain::RegexConstraint::allowed_token_ids(generated, vocab) -> Vec<usize>` (`crates/sovereign-regex-constrain/src/lib.rs:76`) advances an NFA over the prefix once, then returns the ids of tokens that keep the pattern satisfiable — **exactly** the `Vec<usize>` that `TokenLawPlanes::combine_with` / `pack_allowed` consume. It reported this only as a `LogitMask` (`:106`) — the same domain-mismatch SDD-501 solved for grammar.
- **Real — the grammar source.** `sovereign_token_grammar_mask::TokenGrammarMask` (SDD-501/502) reports `allowed_ids()` + `eos`.
- **Real — the composition primitive.** `TokenLawPlanes` (SDD-501) with `combine_with(one_dynamic)` over `token_law_combine`.
- **The gap.** `complete_json_schema_with_laws` (`crates/sovereign-llm/src/lib.rs`, SDD-501) hard-codes grammar as the *only* dynamic source and takes policy planes as caller-supplied bitsets. There was (a) no way to make **regex** a composable plane, and (b) no way to intersect **two** dynamic sources (grammar ∧ regex) in one step — `combine_with` takes a single dynamic allow-list.

## Honest scope (what is and isn't a plane)

- **Regex is a genuine dynamic source** — a per-position allow-list, just like grammar. A **tool-name allow-list** is a special case: a `(name_a|name_b|…)` alternation *is* a regex, so it needs no new code — `complete_regex_with_laws(prompt, "(get_weather|search_web)", …)` confines output to the allowed tool names.
- **Safety scanners are deliberately excluded.** `sovereign-secret-scan` / `-pii-redact` / `-toxicity` / `-injection-detect` operate on *finished text* (substring/entropy/term matches) and expose no token-level ban set. A secret/toxicity ban is a **substring** property, not a per-token one, so it does not cleanly become a static allow-bitset — making it a plane needs a genuinely new text→token-span projection layer, which is out of scope here (it would be a design SDD of its own, not a wiring). This SDD ships only sources that already are per-token.

## Design

### 1. Multi-dynamic composition — `TokenLawPlanes::combine_with_dynamics`

`combine_with` takes one dynamic allow-list. The new primitive takes **N**:

```
pub fn combine_with_dynamics(&self, dynamic_allow_id_lists: &[&[usize]]) -> Vec<u64>
```

Each dynamic list (grammar's `allowed_ids`, regex's `allowed_token_ids`, a
tool-name enum) is packed and AND-combined with every static policy plane through
the real `token_law_combine` — a token survives only if **every** source and
plane allows it. `combine_with` becomes the single-source case (delegates), so
SDD-501's behaviour is unchanged. No planes at all ⇒ identity (all allowed).

### 2. Regex as a composable plane — `complete_regex_with_laws`

The regex sibling of SDD-501's `complete_json_schema_with_laws`: the regex plane
(`RegexConstraint::allowed_token_ids`, recomputed per position) is AND-combined
with static `policy_planes` each step via `combine_with`. A real constraint
source feeding a token-law plane — the SDD-500-Q4 / SDD-501 tracked step, closed.

### 3. Two dynamic sources at once — `complete_json_schema_and_regex_with_laws`

Drives `generate_dynamic_token_law_until` with a closure that computes **both**
the grammar plane (`TokenGrammarMask::mask(...).allowed_ids()`) **and** the regex
plane (`RegexConstraint::allowed_token_ids(...)`) each step, and
`combine_with_dynamics([grammar_ids, regex_ids])` ∩ static planes. Stops on
grammar completion, an empty source, or an empty intersection. This is the
multi-source composition — e.g. a JSON string whose *content* the regex further
restricts beyond what the grammar allows.

## What shipped (2026-07-21)

- **`crates/sovereign-token-law-mask`** — `TokenLawPlanes::combine_with_dynamics`
  (N dynamic sources ∧ statics); `combine_with` delegates to it. `forbid(unsafe_code)`.
  +3 unit tests: `multiple_dynamic_planes_all_intersect_with_policy` (grammar {2,5,6}
  ∧ regex {5,6,7} ∧ safety-ban(6) = {5} — the rigorous multi-source AND),
  `combine_with_is_the_single_dynamic_case_of_combine_with_dynamics`,
  `no_planes_at_all_is_identity`.
- **`crates/sovereign-llm`** — `complete_regex_with_laws` (regex ∧ policy) and
  `complete_json_schema_and_regex_with_laws` (grammar ∧ regex ∧ policy). +4 tests:
  `regex_with_laws_composes_pattern_and_policy` (`[0-9]+` ∧ ban `5` → digits, no `5`),
  `regex_with_laws_zero_planes_still_matches_the_pattern`,
  `tool_name_allow_list_via_regex_alternation` (`(get_weather|search_web)` → output
  is a prefix of an allowed name), and `json_schema_and_regex_compose_all_three`
  (JSON-string grammar ∧ regex `"[a-z]+"` ∧ ban `z` → quoted, lowercase, no `z`;
  the regex forbids the uppercase/digits/empty-string the grammar allows — a
  constraint no single source expresses).
- **No new crate** (722 unchanged); no external dependency; `complete_json_schema_with_laws`
  (SDD-501) unchanged (`combine_with` still the one-source path).

Verified: `cargo test -p sovereign-token-law-mask -p sovereign-llm` (12 + 83 lib +
28 runtime pass) + the grammar/regex/decoder family green
(`sovereign-token-grammar-mask` 14, `sovereign-cfg-grammar` 14,
`sovereign-regex-constrain` 8, `sovereign-json-schema-grammar` 13,
`sovereign-decoder-stack` 37); `cargo clippy -D warnings` + `cargo fmt --check`
clean; `tests/lint/test_real_constraint_source_planes_contract.py` locks the
multi-dynamic primitive, the regex-source wiring, and the honest
safety-not-a-plane boundary.

## Non-goals

- A safety-denylist plane (substring bans are not per-token — needs a new text→token projection, a separate design).
- New grammar/regex features (the sources' languages are unchanged).
- Wiring these into the external-proxy `/v1/messages` path (the SDD-500 boundary — no logit access there).
- The M00155 operator surface (`--token-law-mask-layers`, `/v1/data-plane/token-law/fuse`) — that exposes these planes through config/HTTP; a separate SDD once the sources are real (they now are).

## References

- SDD-500 § Q4, SDD-501 § Non-goals ("derive the static planes from real … sources") — the tracked step this closes.
- `crates/sovereign-regex-constrain/src/lib.rs:76` (`allowed_token_ids`), `crates/sovereign-token-law-mask/src/lib.rs` (`combine_with_dynamics`), `crates/sovereign-llm/src/lib.rs` (`complete_regex_with_laws`, `complete_json_schema_and_regex_with_laws`).
- `crates/sovereign-simd/src/cheats.rs` (`token_law_combine`), `crates/sovereign-token-grammar-mask` (grammar plane), `crates/sovereign-json-schema-grammar` (`compile`).
