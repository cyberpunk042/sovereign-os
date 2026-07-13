# SDD-962 — runtime binaries reference + close the orphan-crate triage

> Status: draft
> Owner: operator-directed ("we continue" — Phase-1 audit); agent-authored
> Last updated: 2026-07-13
> Closes findings: **F-2026-005** (binaries doc); **F-2026-002** (orphan triage — subsumed by SDD-955).
> Mandate module: **E11.M962** (operator-mandate cross-link).
> Number band: **950–999 (general / audit session)** per SDD-100.

## Mission

Two "what actually runs" findings, both about seeing the real surface through the 714-crate fog:

- **F-2026-005** — the **9 Rust binary crates** (`crates/*/src/main.rs`) are the executable runtime surface, but no single doc said "these are the executables, here's what each is for, here's how they compose." A reader couldn't tell the one production daemon from the demo CLIs.
- **F-2026-002** — the 35 non-cockpit zero-consumer crates needed a per-crate "entry-point-or-dead" triage. That triage **already shipped** as the island register (SDD-955): every one carries a `wireable`/`aspirational` disposition + a concrete trigger, machine-enforced. This SDD closes F-2026-002 by pointing at it.

## What this SDD builds

### 1. `docs/src/binaries.md` — the runtime-binary map

Each of the 9 binaries mapped to **role → invocation → purpose**, split honestly into **production** and **dev/demo**:

- **Production**: `gatewayd` (the one persistent daemon — `sovereign-gatewayd.service`), `telemetry` (periodic Prometheus textfile emitter via the telemetry-textfile timer), `resource-control` (cgroup/compute-plane helper), `feature-selftest` (the feature-test-lab runner).
- **Dev/demo CLIs** (manual or via the `brain-api` catalog, none persistent): `cortex` (routing-brain driver — the *library* runs in gatewayd), `agent-runtime` (ReAct demo, F-2026-088), `inference-demo` (synthetic-weights composition proof, F-2026-006), `chat` (chat CLI), `serve` (the dead parallel orchestrator, F-2026-089/SDD-957).

Plus a "how they compose" diagram: **one daemon** + a periodic emitter + control/test helpers; the rest are developer tools. Wired into `SUMMARY.md` under "Using the box" so it's in the published book (the SDD-958 catalog surfaces it too).

### 2. `tests/lint/test_binaries_doc.py` — the completeness contract

Every crate that produces a binary (`src/main.rs` or `src/bin/`) must appear in `binaries.md`; the doc must not name a crate that doesn't exist; and `SUMMARY.md` must link the page. So a new binary can't ship undocumented, and the runtime-surface map can't drift. Same self-maintaining discipline as the island register (SDD-955) and the route-parity contract (SDD-956).

### 3. F-2026-002 closure (ledger)

Annotated closed-by-SDD-955: the island register **is** the per-crate disposition table F-2026-002 asked for (now 33 crates — a parallel session wired `rate-limit` + `observability-events` since, which the register's lint enforced). The two headline crates F-2026-002 called out — `sovereign-holderpo` and `sovereign-worker-fleet` — are both in the register as `aspirational` with their triggers.

## Verification

- `python3 -m pytest tests/lint/test_binaries_doc.py` — 3 passed (doc exists + linked; all 9 binary crates documented; no ghost names).
- All 9 `crates/*/src/main.rs` crates present in the doc; `ruff` clean; full `tests/lint` + `tests/schema` green.

## Non-goals

- **Per-binary systemd-unit exhaustiveness** — the doc names the primary invocation of each; the ~90 Python operator-API units are a different surface (out of scope).
- **Wiring the demo binaries into production** — `agent-runtime` (F-2026-088), `serve` (F-2026-089), `inference-demo`'s real-model upgrade (F-2026-006) are their own findings.

## Safety invariants

Docs + read-only lint only — no crate code, no runtime behavior, no gateway touch. The doc describes verifiable invocation (systemd units + script references that exist); it invents nothing. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `docs/src/binaries.md` — the runtime-binary map
- `tests/lint/test_binaries_doc.py` — the completeness contract
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-005, F-2026-002 (sources); F-2026-006/088/089 (the demo-binary follow-ups)
- `docs/review/phase-1/island-register.md` — the orphan triage F-2026-002 asked for (SDD-955)
- SDD-955 / SDD-956 / SDD-958 — the same self-maintaining-contract pattern
- SDD-100 — the per-session number-band convention (this SDD is in the phase-1-audit 950–999 sub-band)
