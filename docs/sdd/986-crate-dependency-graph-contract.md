# SDD-986 — crate dependency-graph contract: orphan discovery becomes a CI signal (F-2026-009)

> Status: draft
> Owner: operator-directed 2026-07-13 ("we continue"); agent-authored.
> Closes: **F-2026-009** (OPP) — dependency-graph guard.
> Mandate module: **E11.M986**.
> Number band: **950–999 (phase-1 audit session)** per SDD-100.

## Mission

The Phase-1 audit found — by ad-hoc archaeology — that **413 of the 717 workspace
crates are consumed by nothing** (the whole `sovereign-cockpit-*` family, F-2026-001).
That was a one-time discovery with no standing guard: a *new* orphan (a crate
wired into nothing, shipped by accident) would only surface in the next manual
audit. This turns the discovery into a **CI signal** — a contract lint that fails
the instant a new non-sanctioned orphan lands.

## The invariant (empirically established, 2026-07-13)

Built by parsing every `crates/*/Cargo.toml` (the repo's convention — the pytest
lint job has no `cargo`; `test_workspace_hygiene_baseline.py` / `_metadata.py`
parse TOML directly, so does this). A crate is **reachable** if another workspace
crate depends on it (normal / build / dev) **or** it is a binary (`[[bin]]` or
`src/main.rs`); an **orphan** is neither. On `main`:

- **717** crates · **41** binaries · **265** consumed-by-another · **413 orphans**
- **all 413 orphans are `sovereign-cockpit-*`** · **0 non-cockpit orphans**

The cockpit family is orphan-by-design: it is bridged to the webapp as **wasm via
codegen** (SDD-800 / F-2026-001), not via Cargo dependency edges, so it carries no
`crates/*` consumer — a graph-orphan, but not dead code. Every OTHER crate is
reachable (SDD-962 wired the last non-cockpit orphans, closing F-2026-002).

So the contract is one clean rule: **every orphan must be in the cockpit family.**

## What this SDD builds

**`tests/lint/test_crate_graph_contract.py`** (stdlib + pytest):
- `test_graph_is_nontrivial` — a sanity floor (>500 crates seen, reachable set
  non-empty) so the real assertion can't silently pass on a failed walk.
- `test_no_orphan_outside_the_cockpit_family` — the contract: any orphan whose
  name is not `sovereign-cockpit-*` fails, listing the stray crate(s) with the
  remediation (wire it into a consumer/binary, or — if it's a new wasm-bridged
  UX-state crate — name it in the family). A malformed manifest is its own hard
  failure.

## Verification (real, observed)

- `python3 -m pytest tests/lint/test_crate_graph_contract.py` — **2 passed**;
  the graph walk sees 717 crates, computes 413 orphans, all cockpit, **0 stray**.
- `ruff check` clean.
- Corroborates SDD-962 (F-2026-002 closure): there are genuinely no non-cockpit
  orphans left on `main`.

## Non-goals

- Auditing the cockpit family's wasm-bridge coverage (that's SDD-800's lint).
- Asserting dependency *direction* (core-doesn't-depend-on-infra) — a possible
  future extension; this guard is the reachability half F-2026-009 named.
- Shelling `cargo metadata` — deliberately TOML-parsed for lint-job portability.

## Safety invariants

One new `tests/lint/` file + this SDD + registries. No gatewayd/cockpit/`unsafe`/
crate edits (the Cargo.toml tree is read, never written); collision-safe.
R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `tests/lint/test_crate_graph_contract.py` — the guard
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-009 (closed here), F-2026-001 (the 413-orphan discovery), F-2026-002 (non-cockpit triage, SDD-962)
- `docs/sdd/800-cockpit-wasm-bridge.md` — why the cockpit family is orphan-by-design (wasm-bridged)
- `tests/lint/test_workspace_hygiene_baseline.py` / `test_workspace_metadata.py` — the TOML-parsing convention this follows
