# SDD-955 — wire-the-island register: turn built-but-unwired surprises into an enforced register

> Status: draft
> Owner: operator-directed ("continue" — Phase-1 audit); agent-authored
> Last updated: 2026-07-12
> Number band: **950–999 (general / audit session)** per SDD-100.
> Closes findings: **F-2026-093**. From `docs/review/phase-1/99-findings-ledger.md`.
> Derived from / extends: the counts-as-contract discipline of SDD-952.

## Mission

The audit's #1 recurring pattern is **built-but-unwired islands**: real, tested crates that nothing which runs depends on (security crates, agent loop, worker-fleet/load-balance, HölderPO, save-state/checkpoint, and a long tail). "We recently rediscovered the crates" is the operator's own framing — the failure mode is that these get re-discovered by surprise instead of being *owned*. F-2026-093 asks for a "wire the island" register that, per crate, either wires it or marks it aspirational with a tracked trigger.

This SDD delivers that as a **machine-enforced register** (the SDD-952 counts-contract pattern applied to dead crates), plus a correction to the audit's own mischaracterization of two crates.

## What this SDD builds

### 1. The register — `docs/review/phase-1/island-register.md`

Enumerates the **35 pure-library `sovereign-*` crates** (`src/lib.rs`, no `main.rs` / `bin/`) that appear in **no other crate's `Cargo.toml`** — depended on by nothing, not even a demo or test. This is the sharpest, most objective "island" signal (vs the softer "reachable only via a demo hub"). Each row carries a **disposition** (`wireable` — a plausible in-repo consumer could pull it in crate-to-crate with no new gateway HTTP surface; or `aspirational` — needs a real model / GPU / system-level integration like ZFS/CRIU/VM/network, or an operator decision) and a **trigger** (the concrete thing that would activate it). 14 are aspirational, 21 wireable.

The register also records the **inventory summary** (53 run-reachable crates from the 3 production binaries; ~241 non-cockpit islands + 418 cockpit-* leaf widgets) and the **two-parallel-stacks root cause**: the wired generation stack (`safetensors-loader` → `quant-model` → …) vs the island stack funneling ~150 crates through the demo-only `sovereign-llm` hub — so the single highest-leverage move is giving `cortex`/`gateway` a real consumer of that hub (relates to F-2026-083/088/089), at which point most wireable islands light up transitively.

### 2. The enforcing lint — `tests/lint/test_island_register.py`

Recomputes the 35-crate set from the workspace Cargo.tomls and asserts it equals the register **both directions**:
- a **new** pure-library crate with zero consumers → CI fails until it is registered (wire it, or record disposition + trigger);
- **wiring** an island (adding a real consumer) → CI fails until its row is removed.

Plus: every row must declare a valid disposition, and no duplicates. So the register can only drift toward "everything is either wired or consciously parked" — the same self-maintaining guarantee SDD-952 gave `context.md`.

### 3. Correction to the audit (F-2026-093 as written)

The finding flagged `sovereign-world-model` and `sovereign-hrm-runtime` as under-exposed islands. **They are run-reachable** — `sovereign-cortex` (a direct dependency of `sovereign-gatewayd`) depends on both, so they execute inside the daemon. The ledger entry is annotated with this correction. (The audit's other named crates — `holderpo`, `save-state`, `worker-fleet` — are confirmed zero-consumer and appear in the register.)

## Scope — and what is OUT

- **In:** the objective, enforceable "zero reverse-dependency" set (35) + the summary inventory + the correction.
- **Out (softer signal, not enforced):** the ~206 non-cockpit crates reachable only through the `sovereign-llm` / `sovereign-retrieval` demo/island hubs — a real but softer island signal; enumerating all of them in an enforced list would be noisy (many are legitimately generic primitives). They are described in the register's summary, not the enforced table.
- **Out (the actual wiring):** this SDD does not wire any island — wiring the `sovereign-llm` hub into a real cortex/gateway consumer is the highest-leverage follow-up (F-2026-083/088/089) and touches the generation path a parallel session owns. This SDD makes the islands *owned and tracked* so that work is a conscious backlog choice, not a rediscovery.

## Verification

- `python3 -m pytest tests/lint/test_island_register.py` — 4 passed: the register block parses; every row has a valid disposition; the register equals the computed zero-reverse-dep set both directions; no duplicates.
- The computed set (35) was cross-checked against an independent dependency-graph analysis of all 714 crate manifests (run roots: the 3 production binaries `sovereign-gatewayd` / `sovereign-telemetry` / `sovereign-resource-control`).
- `ruff check tests/lint/test_island_register.py` clean; full `tests/lint` + `tests/schema` green.

## Way forward

- **Wire the hub** (F-2026-083/088/089): a real cortex/gateway consumer of `sovereign-llm` lights up most wireable islands transitively — the single biggest de-islanding move.
- **Aspirational triggers**: the ZFS/VM/CRIU/network islands are gated on real system integration (SDD-207 phases, F-2026-081 sandbox); HölderPO on a post-training loop. Each has its trigger recorded.
- **Extend the signal**: a future lint could also flag the demo-hub-only islands once the generic-primitive noise is curated out.

## Safety invariants

Docs + lint only — no crate code, no execution path, no gateway touch. The lint is read-only over Cargo.tomls. Purely additive. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `docs/review/phase-1/island-register.md` — the enforced register (this SDD's deliverable)
- `tests/lint/test_island_register.py` — the enforcing lint
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-093 (source) + the world-model/hrm correction; F-2026-083/088/089 (the wiring follow-ups)
- SDD-952 — the counts-as-contract pattern this reuses
- SDD-100 — the per-session number-band convention (this SDD is in the phase-1-audit 950–999 sub-band)
