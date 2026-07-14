# SDD-710 — enforce the `unsafe` ban at compile time across all 202 cockpit crates (IMPLEMENTATION)

> Status: draft (implementation — closes F-2026-096)
> Owner: operator-directed 2026-07-14 (*"lets do a big round"* — phase-1 audit continuation).
> Addresses: **F-2026-096** (MED) — the workspace `unsafe_code = "forbid"` ban was only grep-enforced on
> the 202 `sovereign-cockpit-*` crates, not compile-enforced. Makes **F-2026-004**'s "all inherit workspace
> lints" claim fully true.
> Mandate module: **E11.M710**.
> Number band: **700–799** per SDD-100.
> Stage: **implement**.

## The gap this closes

`sovereign-os` treats "no `unsafe` outside the one sanctioned AVX-512 carve-out (`sovereign-simd`)" as a
core sovereignty/safety invariant (F-2026-004/057/067). The root `[workspace.lints.rust]` declares
`unsafe_code = "forbid"` — but a crate only inherits that lint if its manifest declares `[lints] workspace =
true`. The audit (SDD-974) found **202 of 717 crates** — the entire `sovereign-cockpit-*` family — declared
**no `[lints]` table at all**, so the compiler would **not** stop a future `unsafe` block added to any of
them. The ban's repo-wide guarantee rested entirely on a **CI grep** (`test_workspace_hygiene_baseline.py`
invariant 6). The durable fix was deferred at the time only because a parallel session was actively growing
that crate family (714→717 during the audit) — editing those hot manifests would have collided. That
crate-growth has since settled at 717.

## What this SDD delivers

1. **Swept `[lints] workspace = true` into all 202 cockpit manifests** (a parse-verified sweep: each
   manifest is `tomllib`-parsed before and after; the block is only appended to a `sovereign-cockpit-*`
   crate that has no `[lints]` table). Result: **716/717 crates now inherit the compile-time ban**;
   `sovereign-simd` correctly keeps its own `[lints.rust] unsafe_code = "allow"` carve-out (the one crate
   the operator permits `unsafe` in). `cargo metadata` resolves the workspace; a representative swept crate
   (`sovereign-cockpit-accent-color-policy`) `cargo check`s clean under the inherited lints.
2. **Strengthened `tests/lint/test_workspace_hygiene_baseline.py`** with two new invariants (7):
   - **every** member crate declares `[lints] workspace = true` (parsed, not grepped) except the sanctioned
     carve-out — so a **new** crate that forgets the inherit line (the exact F-2026-096 gap) fails CI here;
   - the carve-out (`sovereign-simd`) must declare its `unsafe_code = "allow"` **explicitly** in its
     manifest, so the exception is auditable rather than an omitted `[lints]` table.
   Invariant 6 (the grep) is **retained as defence-in-depth**, no longer merely a compensating control.

## Why this is safe (no build/clippy risk)

Inheriting the workspace lints into the 202 crates cannot break the build or `cargo clippy`:
- `unsafe_code = "forbid"` — inert: a repo-wide grep confirms none of the 202 uses `unsafe` (only
  `sovereign-simd` does, and it's excluded).
- `missing_docs = "warn"` — WARN, never an error; cannot fail a build.
- `[workspace.lints.clippy]` contains **only `allow`-level** lints (`field_reassign_with_default`,
  `needless_range_loop`, `collapsible_if`) — inheriting them can only *relax* clippy for these crates, never
  tighten it. So `cargo clippy` can pass more, never fail more.

## Verification

- Manifest census: **716 inherit + 1 carve-out + 0 unexpected = 717**; every swept manifest re-parses.
- `cargo metadata --no-deps` — OK (workspace resolves).
- `cargo check -p sovereign-cockpit-accent-color-policy` — clean under the inherited lints.
- `tests/lint/test_workspace_hygiene_baseline.py` — 8 cases green (6 prior + 2 new invariant-7).
- Full `tests/` + all 5 profiles + ruff (real-bug gate) green.

A full-workspace `cargo build`/`clippy` across all 717 crates runs in CI (the `cargo workspace` job, SDD-970
timeout); locally the change is proven inert by the above + the all-`allow` clippy table.

## Non-goals

- The cockpit-crate **consolidation** question (F-2026-001 — the 413-crate fate) — an architectural
  operator decision, untouched here; this SDD only closes the safety-lint gap.
- Widening or narrowing the `sovereign-simd` `unsafe` carve-out — unchanged.
