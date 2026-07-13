# SDD-970 — cargo-workspace CI timeout headroom + floor guard

> Status: draft
> Owner: operator-directed ("we continue" — Phase-1 audit); agent-authored
> Last updated: 2026-07-13
> Closes findings: **F-2026-050** (cargo-workspace job: whole workspace under `timeout-minutes: 10`) — core risk.
> Mandate module: **E11.M970** (operator-mandate cross-link).
> Number band: **950–999 (general / audit session)** per SDD-100.

## Mission

The `cargo-workspace` CI job (`.github/workflows/test.yml`) runs four heavy steps over the **whole 717+ crate workspace** in a single job under **`timeout-minutes: 10`**:

- `cargo fmt --all --check`
- `cargo clippy --workspace --all-targets -- -D warnings`
- `cargo test --workspace --locked`
- `cargo build --release --workspace --locked`

`Swatinem/rust-cache` keeps warm runs to ~6–7 min — but that is already two-thirds of the 10-minute budget. Any **cold-cache** run (a toolchain bump, a `Cargo.lock` change, or a cache eviction) rebuilds every crate — clippy compiles the whole graph, then `build --release` compiles it *again* optimized — and will exceed 10 minutes, failing the PR **spuriously** on a timeout that has nothing to do with the change. The workspace only grows (it went 714 → 717 during this audit as parallel sessions de-islanded crates), so the margin shrinks over time. This affects **every** PR, not just this session's.

## What this SDD does

### 1. Raise the budget to 30 minutes

`timeout-minutes: 10 → 30` on the `cargo-workspace` job, with a comment explaining the cold-cache math. 30 min gives real headroom for a from-scratch clippy + release build of 717+ crates while still bounding a genuinely runaway job (the GitHub default is 6 h). **Zero coverage change** — every step still runs exactly as before.

### 2. `tests/lint/test_ci_cargo_timeout.py` — the floor guard

Parses the workflow and asserts the `cargo-workspace` job declares a `timeout-minutes` ≥ 20. So the budget can't be quietly lowered back toward 10 as the workspace keeps growing, and the job can't lose its bound entirely (an unbounded 6 h job hides runaway builds).

## Verification

- `python3 -c "import yaml; …"` → `cargo-workspace timeout: 30`; the workflow still parses.
- `python3 -m pytest tests/lint/test_ci_cargo_timeout.py` — **2 passed** (job exists; timeout ≥ 20).
- `ruff` clean; full `tests/lint` + `tests/schema` green.

## Non-goals — the follow-up split

- **Splitting `cargo build --release --workspace` into its own parallel job** (the finding's option 2) — this would give faster fmt/clippy/test feedback (the common failure modes) without waiting on the slow release build, each with its own budget. It's the better long-term structure but a larger, coverage-sensitive workflow change that can't be validated locally (no GitHub Actions runner here); scoped as a follow-up so the timeout risk is closed now without a risky restructure.
- **Scoping the release build to the shipping binaries** (option 3) — reduces cost but drops release-mode compile coverage for library crates; deliberately not done (coverage preserved).
- **Retiring unconsumed crates to shrink the job** (F-2026-001 relation) — a separate, larger effort; the parallel session's de-islanding is already reducing the island set.

## Safety invariants

CI-config + read-only lint only. No crate code, no runtime behavior, no gateway touch, no coverage change — the same four cargo steps run, only the timeout budget grew. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `.github/workflows/test.yml` — the `cargo-workspace` job
- `tests/lint/test_ci_cargo_timeout.py` — the floor guard
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-050 (source); F-2026-001 (unconsumed crates, the cost-reduction relation)
- SDD-963 — the sibling test.yml change (single-sourced Python deps)
- SDD-100 — the per-session number-band convention (phase-1-audit 950–999 sub-band)
