# SDD-504 — Safety denylist as a negative-constraint token-law plane

> Status: active · Mandate: **E11.M504** (control-bits band 500–599)
>
> Cross-link: closes **E11.M504** (safety denylist plane), the fifth SDD in the
> control-bits band — the source SDD-503 explicitly deferred, completing the
> M00117 five-plane vision (grammar · schema · tool · **safety** · route).
>
> Number band: **500–599 (control-bits session)**
>
> **v1 shipped 2026-07-21** — operator-directed ("Good, we continue, another big
> PR"). The design below is realized: a running model can be **guaranteed never to
> emit** any of a set of banned substrings, composed with the positive constraints
> of 500–503. See § "What shipped".

## Mission

Every constraint the arc has built — grammar (501/502), regex, schema, tool-name
(503) — is a **positive** allow-list: "the next token must keep some pattern
reachable". Safety is the opposite: "the output must **never contain** any of
these substrings" (prompt-injection markers, banned phrases). That is a
**negative** constraint, and it is exactly the source SDD-503 deferred
(§Non-goals #1): *"A safety-denylist plane (substring bans are not per-token —
needs a new text→token projection, a separate design)."* This SDD is that design.

## The crux — why a substring ban is not a per-token property

You cannot ban "the tokens that contain a forbidden substring", because a
forbidden phrase can **span token boundaries**: with a byte-level tokenizer,
"ab" is the token `a` followed by the token `b` — neither token contains "ab".
Banning either token individually is both wrong (over-bans legitimate `a`/`b`)
and insufficient. The ban is a property of the *byte stream*, not of any single
token.

## The realization — an incremental matcher that bans the completer

Compile the denied substrings into an [`AhoCorasick`] automaton. Walk it over the
committed generation to a **scan state**, then ask of every candidate token:
*would appending its bytes drive the automaton onto a match (complete a banned
substring)?* If yes, ban it; else it is safe. `DenyConstraint::safe_token_ids`
returns the safe set — all tokens minus the completers — the same `Vec<usize>`
shape `sovereign-regex-constrain` and `TokenLawPlanes` already consume, so the
safety plane composes with grammar / regex / policy through `token_law_combine`.

**The guarantee is exact and per-step.** Starting from clean text and applying the
plane every step, the output can never contain a denied substring: the only step
at which one could appear is the byte that completes it, and that token is masked
at that step. This is a *decode-time guarantee*, not a post-hoc scanner that
flags a violation after it has already been emitted.

## What was real vs the gap (grounded 2026-07-21)

- **Real — the automaton.** `sovereign-aho-corasick` (`crates/sovereign-aho-corasick/src/lib.rs`) — a full Aho-Corasick (trie + failure links + output sets), byte-level, built for "banned phrases / prompt-injection markers". But its incremental `step(state, byte)` was **private** — only whole-haystack scans (`find_all`/`is_match`/`earliest`) were public.
- **Real — the denylist sources.** `sovereign_injection_detect::PATTERNS` (`crates/sovereign-injection-detect/src/lib.rs:38`) is a `pub const &[&str]` of 24 literal injection phrases; `sovereign-toxicity` carries a literal term-list. Both are directly compilable.
- **Real — the plane seam.** `TokenLawPlanes::combine_with` / `combine_with_dynamics` (501/503) + `generate_dynamic_token_law_until` (501) consume a `Vec<usize>` allow-list per step.
- **The gap.** No incremental scan-state API on the automaton (so a decode loop couldn't probe a candidate from a committed state without re-scanning the whole prefix), and no crate turning "denied substrings" into a per-token allow-list.

## Honest scope — which safety sources become a plane, and which don't

- **Literal-substring denylists → yes.** Injection phrases, banned terms. These are exactly what Aho-Corasick matches.
- **Structural / entropy detectors → no.** `sovereign-secret-scan` uses Shannon-entropy thresholds; `sovereign-pii-redact` uses checksums (Luhn) and shape rules. "The token that completes a high-entropy secret" is not well-defined, so these stay **post-hoc scanners**, not planes. Shipping them as planes would need a different projection (or is genuinely not a per-token property at all) — deliberately out of scope, matching SDD-503's honesty about what is and isn't a plane.

## Design

### 1. Incremental scan state — `sovereign-aho-corasick`

An opaque `AcState` (a `Copy` handle over the automaton node) + `start()` /
`advance(state, byte)` / `hits(state)` — the same goto/failure walk the
whole-haystack scans already used, exposed one byte at a time. `Copy` means a
committed state is probed with a candidate and simply discarded — no rollback.
The whole-scan methods are unchanged; this is purely additive.

### 2. The negative plane — `sovereign-token-law-deny` (new crate)

`DenyConstraint::new(patterns)` compiles the automaton;
`safe_token_ids(generated, vocab) -> Vec<usize>` walks to the committed state and
returns the tokens that do not complete a banned match. Mirrors
`RegexConstraint::allowed_token_ids` exactly, so it drops into the existing
composition. `forbid(unsafe_code)`.

### 3. Wiring — `sovereign-llm`

- `complete_with_safety_denylist(prompt, deny_patterns, …)` — the pure negative constraint.
- `complete_regex_with_safety_denylist(prompt, pattern, deny_patterns, …)` — a **positive** plane (regex) AND a **negative** plane (denylist) at once, via `combine_with_dynamics` — a composition no single constraint expresses.

## What shipped (2026-07-21)

- **`crates/sovereign-aho-corasick`** — `AcState` + `start` / `advance` / `hits` (incremental scan state). +2 tests: incremental walk agrees with `find_all`; committed-state probe hits exactly when a candidate completes a pattern.
- **`crates/sovereign-token-law-deny`** (NEW crate — 722→723) — `DenyConstraint` + `safe_token_ids` / `is_denied`. `forbid(unsafe_code)`. +8 tests, incl. the deterministic cross-token proofs (forbidden "ab": after "a", token "b" is banned; a token that itself contains "ab" is banned; single-byte ban excludes any token containing it; overlapping "he"/"she").
- **`crates/sovereign-llm`** — `complete_with_safety_denylist` and `complete_regex_with_safety_denylist`. +3 tests: banning byte `a` → no `a`; regex `[a-z]+` ∧ denylist `z` → lowercase a–y; and the denylist consuming the **real** `sovereign_injection_detect::PATTERNS` source with the output guaranteed clean.

Verified: `cargo test -p sovereign-aho-corasick -p sovereign-token-law-deny -p sovereign-llm` (12 + 8 + 86 lib + 28 runtime pass); `cargo clippy -D warnings` + `cargo fmt --check` clean; the new crate is registered (crate-inventory regenerated — non-integrated, reached via the `sovereign-llm` hub; crate-graph reachable via `sovereign-llm`; rustdoc-panel catalog 722→723; context workspace-crates 722→723); `tests/lint/test_safety_denylist_plane_contract.py` locks the incremental automaton API, the negative-plane crate, the wiring, and the honest structural-detectors-are-not-planes boundary.

## Non-goals

- Entropy/checksum detectors (secret-scan, pii-redact) as planes — not per-token; they stay post-hoc scanners.
- Regex-shaped denials (a *pattern* of forbidden text) — this ships literal-substring denials; a negated-regex plane is a separate design.
- The external-proxy `/v1/messages` path (the SDD-500 boundary — no logit access).
- The M00155 operator surface exposing these planes via CLI/HTTP (a separate SDD; the sources are now real).

## References

- SDD-503 § Non-goals #1 ("a safety-denylist plane … needs a new text→token projection, a separate design") — the future this closes.
- `crates/sovereign-aho-corasick/src/lib.rs` (`AcState`, `start`/`advance`/`hits`), `crates/sovereign-token-law-deny/src/lib.rs` (`DenyConstraint`, `safe_token_ids`), `crates/sovereign-llm/src/lib.rs` (`complete_with_safety_denylist`, `complete_regex_with_safety_denylist`).
- `crates/sovereign-injection-detect/src/lib.rs:38` (`PATTERNS`), `crates/sovereign-token-law-mask` (`TokenLawPlanes` — the plane the safe-set feeds).
