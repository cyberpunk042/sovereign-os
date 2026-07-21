# SDD-506 — The negated-regex denial plane: forbid the output from matching a pattern

> Status: active · Mandate: **E11.M506** (control-bits band 500–599)
>
> Cross-link: closes **E11.M506** (negated-regex denial plane) — SDD-504's own
> tracked future, the seventh SDD in the control-bits band.
>
> Number band: **500–599 (control-bits session)**
>
> **v1 shipped 2026-07-21** — operator-directed ("ready for the next big PR"). A
> running model can now be **guaranteed never to emit text that *matches* a
> forbidden regex anywhere** (an SSN shape, a forbidden id format), composed with
> every other plane through the unified engine. See § "What shipped".

## Mission

SDD-504 added the negative *literal-substring* plane (Aho-Corasick) and named its
own next step in Non-goals: *"negated-regex denials (a forbidden pattern, not a
literal substring)."* This SDD is that plane. Where SDD-503's `regex` plane forces
output **onto** a pattern (positive), this keeps it **off** one (negative): the
output must never **match** the forbidden regex — a `\d\d\d-\d\d-\d\d\d\d` SSN
shape, a banned id format — anywhere in the stream.

## The crux — "match anywhere" needs an unanchored NFA

`sovereign-regex-nfa` is fully steppable but **anchored at both ends**
(`Regex::is_match` requires the *whole* string to match, `crates/sovereign-regex-nfa/src/lib.rs:121`).
A denylist asks the opposite, unanchored question — *does the pattern match any
**substring**?* — and, like SDD-504's substring ban, a forbidden match can span
token boundaries, so it must be detected at the character that completes it.

The standard Thompson trick: simulate the NFA with the **start state always
active** — re-seed the start closure at every position so a match may begin
there; an accepting live set then means a substring match ended at the current
character. That is the only genuinely-new engine primitive here.

## What was real vs the gap (grounded 2026-07-21)

- **Real — the steppable NFA.** `Regex::start` / `step` / `is_accepting` (`crates/sovereign-regex-nfa/src/lib.rs:169,177,197`), and the *positive* plane built on them (`RegexConstraint::allowed_token_ids`, `crates/sovereign-regex-constrain/src/lib.rs`).
- **Real — the negative-plane template.** SDD-504's `DenyConstraint::safe_token_ids` (Aho-Corasick): walk to a committed state, ban tokens whose bytes complete a match. The regex plane mirrors it exactly, with the NFA in unanchored mode instead of the substring automaton.
- **The gap.** No unanchored/substring search on the NFA (only whole-string `is_match`), and no negative-regex constraint over tokens.

## Design

### 1. Unanchored search — `sovereign-regex-nfa`

Additive: `start_unanchored()` (= the start closure), `step_unanchored(set, c)`
(step **and** re-inject the start closure — the union of two epsilon-closed sets
is itself closed, so no re-closure), and `matches_anywhere(text)` (unanchored
`is_match`). The anchored `is_match` / `step` are unchanged.

### 2. The negative plane — `RegexDenyConstraint` (in `sovereign-regex-constrain`)

Lives beside the positive `RegexConstraint` — same NFA substrate, so **no new
crate**. `new(pattern)` compiles a forbidden regex; `safe_token_ids(generated,
vocab)` walks the unanchored NFA to the committed state and returns the tokens
whose characters do **not** complete a match — the same `Vec<usize>` allow-list a
token-law plane consumes. `is_denied(text)` post-hoc-scans via `matches_anywhere`.

**The guarantee** is exact and per-step, identical in shape to SDD-504: starting
from a clean prefix, a forbidden match can only appear at the character that
completes it, and that token is masked at that step — not a post-hoc scanner.

### 3. Composition — a new plane in the unified engine (SDD-505)

`TokenLawSpec` gains `regex_denylist: &[&str]`; `complete_with_token_law` builds a
`RegexDenyConstraint` per pattern and AND-composes each one's safe-set with the
other planes via `combine_with_dynamics`. So a model can be confined by grammar ∧
positive-regex ∧ literal-denylist ∧ **negated-regex** ∧ policy simultaneously.
`TokenLawSpec::is_empty` accounts for the new field; the SDD-505 parity tests are
unaffected (the field defaults to empty).

## What shipped (2026-07-21)

- **`crates/sovereign-regex-nfa`** — `start_unanchored` / `step_unanchored` / `matches_anywhere`. `forbid(unsafe_code)`. +3 tests (substring finds; a match completing mid-stream flips `is_accepting`; alternation/classes anywhere).
- **`crates/sovereign-regex-constrain`** — `RegexDenyConstraint` (`new` / `from_regex` / `regex` / `is_denied` / `safe_token_ids`), beside the positive `RegexConstraint` (NO new crate — same NFA). +5 tests, incl. deterministic cross-token proofs (forbidden `ab`: after `a`, token `b` banned; a token whose own chars are two digits banned for `\d\d`; a cross-token digit pair; `cat|dog` matched mid-token).
- **`crates/sovereign-llm`** — `TokenLawSpec::regex_denylist` + composition in `complete_with_token_law`. +1 test: positive regex `[a-z]+` ∧ negated regex `[xyz]` → lowercase a–w only (a regex *class* forbidden, which the SDD-504 literal denylist can't express).

Verified: `cargo test -p sovereign-regex-nfa -p sovereign-regex-constrain -p sovereign-llm` (14 + 13 + 92 lib + 28 runtime pass); `cargo clippy -D warnings` + `cargo fmt --check` clean; `tests/lint/test_negated_regex_denial_plane_contract.py` locks the unanchored API, the negative-regex constraint, the engine field, and the honest empty-match caveat.

## Non-goals

- Regex features beyond the NFA's set (`* + ? | () . [] \d\w\s`) — no `{n}` bounds, backrefs, or lookaround.
- Patterns that match the empty string (they forbid everything — documented, not special-cased).
- The M00155 operator surface (a separate SDD; this deepens the engine).
- The external-proxy `/v1/messages` path (SDD-500 boundary — no logit access).

## References

- SDD-504 § Non-goals ("negated-regex denials — a forbidden pattern, not a literal substring") — the future this closes; SDD-505 (the unified engine this plane joins).
- `crates/sovereign-regex-nfa/src/lib.rs` (`start_unanchored`/`step_unanchored`/`matches_anywhere`), `crates/sovereign-regex-constrain/src/lib.rs` (`RegexDenyConstraint`), `crates/sovereign-llm/src/lib.rs` (`TokenLawSpec::regex_denylist`, `complete_with_token_law`).
