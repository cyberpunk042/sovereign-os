# SDD-997 — a per-crate `✅ integrated` flag on the crate-inventory, validated by named usage (F-2026-100)

> Status: draft
> Owner: operator-directed 2026-07-14 (phase-1 audit continuation); agent-authored.
> Closes: **F-2026-100** (LOW) — no positive "done / integrated" flag on crates.
> Mandate module: **E11.M997**.
> Number band: **950–999 (phase-1 audit session)** per SDD-100.

## The gap

After SDD-996 flagged which *SDDs* are done (`draft → complete`), the operator
asked the parallel question about crates:

> "were you not suppoed to flag the crates that are done / integrated ?"

The crate-connection state was tracked only *negatively* / *implicitly*: the island
register (SDD-955) drains by **removing** a crate's row when it gets wired (so there
is no positive record of what is integrated), and the crate-inventory (SDD-995)
bucketed crates by reachability but carried **no per-crate "integrated" marker**.
There was no positive, per-crate "done / integrated" flag — the direct analogue of
the SDD `complete` flag.

## The operator's definition (verbatim)

Where to put it, and what "integrated" means:

> "Flag in crate-inventory" · "Production-reachable"

> "it has to be used to be integrated, not only referenced in a panel"

> "you can explain the usage to validate the integration"

So: **integrated = actually USED by a running production binary**, not merely
*referenced*. A cockpit crate wasm-bridged for a panel (SDD-800 — 0 panels wired) is
referenced, not used. And the flag must **explain the usage** that validates the
claim.

## The flag — generated, per-crate, usage-validated

`scripts/docs/gen-crate-inventory.py`:

1. **Integrated set** = the dependency closure of the three production binaries
   (`gatewayd` / `telemetry` / `resource-control`) — a crate is integrated only if
   its code compiles and links into a process that runs. This closure was already
   computed (`prod`); the flag surfaces it per-crate. Cockpit crates (panel-bridged)
   and demo/hub-only crates are **not** in this closure, so they never get the flag —
   directly honouring "used, not merely referenced".

2. **Usage explanation** (`usage_explanation()`): for each integrated crate, a note
   naming the concrete usage that validates it — `runs as a production binary`
   and/or `used by \`<consumer>\`, …` (its direct production consumers, computed from
   the reverse dependency edges within the closure). Examples:
   - `sovereign-gatewayd` — ✅ **integrated**: runs as a production binary
   - `sovereign-cortex` — ✅ **integrated**: runs as a production binary; used by `sovereign-gatewayd`
   - `sovereign-hardware-load-sample` — ✅ **integrated**: used by `sovereign-hardware-dispatch-eligibility`, `sovereign-hardware-thermal-policy`, `sovereign-pressure-reactions`, `sovereign-telemetry`

3. **Legend** in the summary explains the badge + the used-not-referenced boundary.

**57 crates** carry the flag (the 4 production binaries + 53 production libraries) —
the honest minority: most of the 717-crate workspace is not yet integrated, and the
flag does not pretend otherwise.

## The lint

`tests/lint/test_crate_inventory_integrated_flag.py` (4 cases) keeps the flag honest
independently of the byte-equality sync lint (SDD-995):

- the ✅-flagged set in the committed doc **equals** the production closure exactly
  (no used-but-unflagged, no flagged-but-not-used);
- every flagged crate carries a **usage note** (a bare ✅ with no consumer/binary
  explanation is rejected — the usage is the validation);
- the **used ≠ referenced** boundary: `gatewayd` is flagged; no `cockpit-*` crate is
  (panel-bridged ≠ used), and none is in the closure;
- an anti-inflation floor: the flagged set stays a minority of the workspace.

## Verification (real, observed)

- `python3 scripts/docs/gen-crate-inventory.py` regenerates the page with **57**
  `✅ integrated` badges, each with a usage note.
- `python3 -m pytest tests/lint/test_crate_inventory_integrated_flag.py
  tests/lint/test_crate_inventory_sync.py` → **8 passed**. `ruff` clean. Full
  `tests/lint` green.

## Scope / safety

`scripts/docs/gen-crate-inventory.py` (a `direct_deps` refactor + `usage_explanation`
+ the badge/legend in `render()`/`emit_group`) + the regenerated
`docs/architecture/crate-inventory.md` + a new `tests/lint/` file + this SDD +
registries. No crate, runtime, or webapp change; no new dependency; collision-safe.
R10212 / MS043 untouched. MS003 `unsigned-pending-MS003`.

## Non-goals

- Call-graph "is every symbol of a linked crate actually invoked" analysis — the
  production-binary closure (compiled + linked into a running process) is the
  practical, generated bar for "used"; a declared-but-dead dependency is a separate
  concern (cargo's own unused-deps tooling).
- Flagging demo/dev-binary usage as integrated (the operator chose production-reachable).
- A positive "graduated islands" history in the island register (a different surface;
  this puts the positive flag where the operator asked — the inventory).

## Cross-references

- `scripts/docs/gen-crate-inventory.py` — `usage_explanation()` + the `✅ integrated` badge
- `tests/lint/test_crate_inventory_integrated_flag.py` — the flag ⇔ closure + usage lint
- `docs/sdd/995-crate-inventory-check-gate.md` — the `--check`/sync gate this builds on
- `docs/sdd/996-sdd-index-status-completeness.md` — the SDD `complete` flag this parallels for crates
- `docs/review/phase-1/island-register.md` (SDD-955) — the negative/removal tracking this complements
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-100 (closed here); F-2026-001 (cockpit-crate connection)
