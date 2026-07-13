# SDD-960 — real workspace metadata + kill the dead docs.rs links

> Status: draft
> Owner: operator-directed ("we continue" — Phase-1 audit); agent-authored
> Last updated: 2026-07-12
> Closes findings: **F-2026-003**. From `docs/review/phase-1/99-findings-ledger.md`.
> Mandate module: **E11.M960** (operator-mandate cross-link).
> Number band: **950–999 (general / audit session)** per SDD-100.

## Mission

Two template-leftover defects, both inherited widely:

1. **Placeholder workspace metadata.** Root `Cargo.toml` `[workspace.package]` shipped `repository = "https://example.org/you/sovereign-os"` and `authors = ["You <you@example.org>"]` — inherited by **all 714 crates** via `repository.workspace = true` / `authors.workspace = true`. Every crate's package metadata pointed at `example.org`.
2. **Dead docs.rs links.** 23 crate `lib.rs` headers carried intra-doc reference links to `https://docs.rs/sovereign-*`, which **can never resolve**: the workspace is `publish = false`, so nothing is on docs.rs.

Neither breaks a build, but both are exactly the kind of "looks-real, is-fake" surface the audit flags — and both are one-edit-fixable at the root plus a small sweep.

## What this SDD builds

### 1. Real metadata (root `Cargo.toml`)

`repository` → `https://github.com/cyberpunk042/sovereign-os` and `authors` → `["cyberpunk042"]` — the already-public identity the mdbook's `book.toml` uses (`git-repository-url` + author). One edit; all 714 crates inherit it. (Private contact details are deliberately **not** used — the public GitHub identity is the correct package-metadata value.)

### 2. The docs.rs sweep (23 crates)

Each dead `[`sovereign-x`]: https://docs.rs/sovereign-x` reference definition is repointed to the real source `https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-x`. The link text is unchanged; only the (dead) target becomes a live one. Doc comments only — no code, no signatures.

### 3. `tests/lint/test_workspace_metadata.py` — the contract

Asserts the root `[workspace.package]` has no template placeholders (`example.org` / `You <you@` / `you@example`), that `repository` is a real https URL, that `authors` aren't placeholder, and that **no crate `lib.rs` links `docs.rs/sovereign-*`** (a dead link under `publish = false` — this stops a reintroduction). So the metadata can't silently regress to template values.

## Verification

- `cargo metadata --no-deps` parses (714 packages); `cargo build -p sovereign-quant-model -p sovereign-rope` clean (doc-comment + metadata edits don't touch compilation).
- 23 files swept; `grep -rc docs.rs/sovereign crates/*/src/lib.rs` → 0.
- `python3 -m pytest tests/lint/test_workspace_metadata.py` — 4 passed; `ruff` clean; full `tests/lint` + `tests/schema` green.

## Non-goals

- **Building + publishing local rustdoc as a cockpit panel** (the F-2026-003 alternative + the F-2026-093 "rustdoc-as-panel" opportunity) — a larger feature; repointing the dead links to the source is the load-bearing fix now.
- **Changing `publish = false`** — the workspace is deliberately unpublished; that stays.

## Safety invariants

Metadata + doc-comment + lint only — no crate logic, no runtime behavior, no gateway touch, no dependency change (so no build-graph change). The metadata values are the already-public GitHub identity; no private contact detail is introduced. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `Cargo.toml` — the `[workspace.package]` metadata
- `tests/lint/test_workspace_metadata.py` — the enforcing lint
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-003 (source); F-2026-093 (rustdoc-as-panel opportunity)
- SDD-100 — the per-session number-band convention (this SDD is in the phase-1-audit 950–999 sub-band)
