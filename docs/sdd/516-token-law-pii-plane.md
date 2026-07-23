# SDD-516 — The PII-completion token-law plane: ban the token that *completes* a personal identifier (M00155 DEEPEN)

> Status: active · Mandate: **E11.M516** (control-bits band 500–599)
>
> Cross-link: a **Deepen** slice over the M00117 engine — the exact-shape v2 the entropy plane's own scope note named. The fifteenth SDD in the control-bits band, after the Expose arc (SDD-507/510/511), the Connect fork (SDD-512), and the Deepen slices (SDD-513 entropy, SDD-514 incremental fusion, SDD-515 SIMD).
>
> Number band: **500–599 (control-bits session)**
>
> **v1 shipped 2026-07-23** — operator-directed (*"let continue"*). SDD-513 shipped a *heuristic* entropy plane and its own non-goals named the natural v2: *"A checksum/Luhn-shaped PII projection (well-defined completion, unlike entropy) is a natural v2."* This is that v2.

## Mission

The M00117 planes turn a text constraint into a per-token allow-list. The deny plane bans the token that *completes* a forbidden substring — an **exact** per-step guarantee because "the token that completes pattern P" is well-defined. SDD-513's entropy plane is honest that a *secret* is **statistical** (a high-entropy run, not a fixed shape), so it stayed an explicitly heuristic threshold. **PII is different from a secret**: an email, a US SSN (`###-##-####`), an IPv4 address, and a Luhn-valid credit-card number are **defined shapes**. At any prefix, appending a candidate token either creates a `sovereign-pii-redact` detection that ends *within the candidate* or it does not — deterministic per step, not a statistical cutoff. This plane bans exactly those completing tokens, so a running model can be prevented from **emitting the token that completes a personal identifier**, before it is sampled — a preventive, per-step complement to the post-hoc `sovereign-pii-redact::redact` the gateway's `StreamGuard` already runs.

## The honesty framing (load-bearing)

The plane reuses `sovereign-pii-redact::detect` **wholesale**, so the plane and the post-hoc redactor can never disagree on what PII is — the same discipline the entropy plane keeps with the secret scanner. Two honesty boundaries:

1. **Completion is exact; recall is bounded.** Within the four shapes `detect` recognizes, the completion is exact (a detection deterministically fires or not at each prefix). But `detect` is itself a *high-precision heuristic over four kinds* — it will not catch a name or a novel identifier format. So, like entropy, this plane is **opt-in per request, off by default**, and the post-hoc redactor stays the exact backstop. It is a preventive complement, never a replacement.
2. **Windowed.** Only the trailing `window` characters of `generated` are scanned, so per-step cost is bounded and the stateless (`fused_mask`) and incremental (`FuseSession`) paths agree **bit-for-bit** (the SDD-514 parity invariant extends to this plane). A PII value whose start falls before the window boundary is the documented limitation of the window — the same trade the entropy plane's window makes. The default window (`DEFAULT_PII_WINDOW = 128`) covers the short shape-based kinds (card ≤19 digits + separators, SSN, IPv4) comfortably.

## Design

### The plane — `sovereign-token-law-pii` (NEW crate)

`PiiConstraint::safe_token_ids(generated, vocab) -> Vec<usize>` mirrors the deny and entropy planes verbatim: for each candidate token, window the history once, append the candidate, and ban the token iff `detect(base + tok)` yields a detection whose end falls *within the appended region* (`d.end > base_len`) — i.e. the candidate closed a PII value. An empty token and any non-completing token are safe; a `window` of `0` is an all-safe identity (the plane off). `forbid(unsafe_code)`; deps `sovereign-pii-redact` only. `ends_with_pii` is a post-hoc intent check. +9 unit tests (Luhn card completion, SSN completion, a token carrying a whole email, prior-PII-does-not-ban, empty token, disabled identity, …).

### The seventh plane wired through the fuse engine

`sovereign-token-law-fuse` gains `pii` as the **seventh** plane, first-class everywhere the other six are: `FuseLayers.pii` / `select` / `CompiledFuse` / `fused_mask` (LayerCoverage `"pii"`, stop-on-empty) / `FuseSession` (a `pii_tail` truncated to the plane's `window`, so the incremental path is per-step-bounded and bit-for-bit identical) / `FuseRequest.pii` + `PiiRequest` wire type / `MaskLayerSet` seventh bool with a **DISTINCT `pii` name** — deliberately NOT folded into the `safety` alias, so an existing `safety`-only selection is unchanged (the same discipline SDD-513 kept for `entropy`). +3 fuse tests (request path bans a card completer with `"pii"` in `layers_active`; deselection; a session-vs-stateless parity walk over a card being typed).

### First-class at the serving + engine boundaries

- **`sovereign-llm`** — `TokenLawSpec.pii` + `complete_with_token_law` passthrough, so a local decode is confined by grammar ∧ regex ∧ denylist ∧ regex_denylist ∧ policy ∧ entropy ∧ **pii** at once.
- **`sovereign-gatewayd`** — `ServingTokenLaw.pii` (the `/v1/messages` `token_law` object) + `layers_active` reporting.

## What shipped

- **NEW crate `sovereign-token-law-pii`** (727→728) — `PiiConstraint::safe_token_ids` reusing `sovereign-pii-redact::detect`, windowed, disabled-identity, `forbid(unsafe_code)`, +9 unit tests.
- **`sovereign-token-law-fuse`** — the seventh plane through `FuseLayers`/`select`/`CompiledFuse`/`fused_mask`/`FuseSession`(`pii_tail`)/`FuseRequest`/`PiiRequest`/`MaskLayerSet` (distinct `pii` name) + `layers_active`; +3 tests.
- **`sovereign-llm`** — `TokenLawSpec.pii` + passthrough.
- **`sovereign-gatewayd`** — `ServingTokenLaw.pii` + `layers_active`.
- Registration: SDD-516 + INDEX + mandate E11.M516 + catalog regen + context `sdd files` 226→227 + `workspace crates` 727→728 + crate-inventory + rustdoc-panel catalog regen + `tests/lint/test_token_law_pii_plane_contract.py`.

## Non-goals / roadmap

- **More PII kinds** — the plane rides `sovereign-pii-redact`'s four kinds; adding a kind (IBAN, phone, passport) is a change to that crate, and this plane inherits it for free.
- **The route plane as a real source** — still the one design-gated Deepen piece (the 7-axis router outputs an `SrpRole` model choice, not a vocab subset; no defined `SrpRole → allow-bitset` mapping). Operator decision required.

## References

- The non-goal that named this: `docs/sdd/513-token-law-entropy-plane.md` (Non-goals — "checksum/Luhn PII projection … the natural v2").
- The sibling planes: `crates/sovereign-token-law-deny/src/lib.rs`, `crates/sovereign-token-law-entropy/src/lib.rs`.
- The reused detector: `crates/sovereign-pii-redact/src/lib.rs` (`detect`).
- The plane: `crates/sovereign-token-law-pii/src/lib.rs` (`PiiConstraint`).
- The fuse wiring: `crates/sovereign-token-law-fuse/src/lib.rs` (`FuseLayers.pii`, `PiiRequest`, `FuseSession::pii_tail`).
- Consumers: `crates/sovereign-llm/src/lib.rs` (`TokenLawSpec.pii`), `crates/sovereign-gatewayd/src/lib.rs` (`ServingTokenLaw.pii`).
