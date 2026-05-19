# SDD-039 — Operator §1g 8-surface delivery contract

> Status: review
> Owner: operator
> Last updated: 2026-05-19
> Closes findings: none (formalizes R453-R547 implementation lattice)
> Derived from: operator-§1g standing rule (verbatim) +
>   operator-§1g STANDING RULE (verbatim, sacrosanct, R456-anchored)

## Mission

Capture the operator's §1g 8-surface delivery contract as a single
canonical SDD so the doctrine that has shaped 95+ rounds (R453-R547)
is discoverable, citable, and lint-enforceable without grep-walking
the round log. The contract is the load-bearing rule under which
EVERY operator-facing module on sovereign-os ships:

> "everything is not just core, not just cli, not just TUI, not just
>  API, not just tool and MCP but also Dashboards and Web Apps and
>  Services" (operator §1g, R453 anchor, sacrosanct)

The supporting STANDING RULE (R456-anchored, also sacrosanct) is:

> "If you think something is really already done, ask yourself if
>  you covered all angles and levels and layers and even if then
>  improve it. Do not minimize or settle for less." (operator §1g)

The two together produce the lattice formalized here.

## Problem

Pre-R453 sovereign-os modules shipped on inconsistent surface sets.
Some had a CLI verb but no API; some had a dashboard but no MCP
exposure; some had a `service:` waiver labeled "not applicable" with
no operator-stated rationale. Without a single explicit contract:

- "Done" was author-defined, not contract-defined. An author who
  shipped core+cli could believe the module was complete; the
  operator could not see that 5 of 8 surfaces were missing.
- Cross-module symmetry was impossible to enforce. compliance had
  status/worst/history but no MCP surface; doc-coverage had a
  dashboard but no API; surface-map (the §1g coverage instrument!)
  itself had api:FUTURE + webapp:FUTURE + service:not-applicable
  waivers on its own row — a literal hypocrisy.
- Operator-§1g UX rule "every operator-facing module is reachable
  from every operator-facing surface" had no mechanized check.

The §1g 8-surface delivery contract resolves all three by:

1. **Enumerating** the 8 surfaces operator-verbatim (R453).
2. **Auditing** every module's coverage via `surface-map.py`'s
   MODULE_COVERAGE registry — the SAME instrument operators query
   via `sovereign-osctl surface-map coverage`.
3. **Distinguishing** structural ceiling from FUTURE work (R478) so
   "at-ceiling" modules with operator-justified `not applicable —
   <reason>` waivers don't trigger anti-minimization patterns.

## The 8-surface delivery ladder

Operator-verbatim, R453 anchor (sacrosanct):

| # | Surface     | What it is                                                      |
|---|-------------|-----------------------------------------------------------------|
| 1 | `core`      | substrate logic (library / config / data-model)                  |
| 2 | `cli`       | `sovereign-osctl` verb (operator's primary terminal surface)     |
| 3 | `tui`       | interactive refresh-loop surface (operator-watched dashboard)    |
| 4 | `api`       | REST / gRPC endpoint (machine-to-machine access)                 |
| 5 | `mcp`       | Model Context Protocol surface (agent-accessible)                |
| 6 | `dashboard` | Grafana / Prometheus visualization (operator-watched chart)     |
| 7 | `webapp`    | master-dashboard subpath (browser-discoverable surface)          |
| 8 | `service`   | systemd unit / daemon (long-running execution)                   |

The vocabulary is encoded verbatim in
`scripts/operator/surface-map.py::SURFACE_IDS`. Cross-repo siblings
(selfdef) consume the same vocabulary via the
`selfdef-surface-manifest` crate (SD-R-MULTI-SURFACE-AUDIT-1 binding,
SDD-038); R462 closed the cross-repo loop.

## Threshold + waiver semantics

- **Default threshold**: 3 of 8 surfaces. A module below threshold
  fires the `surface-gap` anti-minimization pattern (loud, regression-
  shaped).
- **Per-surface waiver**: a module may declare an explicit
  `<surface>: not applicable — <operator rationale>` waiver. This is
  **structural** and counts toward the structural ceiling (NOT toward
  the surface-count below threshold).
- **FUTURE waiver** (R478 precision): `<surface>: FUTURE — <gap
  description>` declares a real gap operator intends to close.
  FUTURE waivers DO fire the `surface-gap` anti-min pattern.
- **Structural ceiling**: a module where `surface_count +
  structural_waiver_count == 8`. The operator's named "I cannot ship
  this surface for THIS module because <reason>" is correctly-shaped
  work, NOT minimized work (R478 ruling).
- **Full 8/8**: surface_count == 8, structural_waiver_count == 0,
  FUTURE_waiver_count == 0 — every surface actually shipped.

## Required coverage

The 4-instrument compliance suite (R458) enforces this contract:

1. `surface-map` (R453) — direct enumeration; THE §1g coverage
   instrument.
2. `doc-coverage` (R454) — every shipped surface must have its doc
   surface (readme/sdd/helptext/metric-inventory/mandate-row/man-page).
3. `anti-minimization-audit` (R456) — surface-gap pattern fails
   on FUTURE-waivered or below-threshold modules.
4. `ux-design-audit` (R457) — every shipped surface must score
   well on the 6 UX dimensions.

The 4-instrument rollup `sovereign-osctl compliance status` returns
the §1g/§1h aggregate. The compliance webapp (R521) visualizes it.

## Goals

- **G1**: Every operator-facing module declares its surface coverage
  in MODULE_COVERAGE (or carries a per-surface waiver with operator-
  authored rationale).
- **G2**: Each shipped surface is BOTH built AND test-gated. An
  asserted `mcp:shipped` row MUST have a corresponding fixed-argv
  entry in `scripts/interop/mcp-aggregate.py::LOCAL_TOOLS` (R286)
  AND a contract lint asserting that entry exists.
- **G3**: The `surface-map` module participates in its own audit
  ("inspector inspects the inspector"). MODULE_COVERAGE has a
  `surface-map` row (R493).
- **G4**: Cross-repo siblings emit/consume SurfaceManifests through
  the same vocabulary (R462 / SDD-038).
- **G5**: Every parameterless verb exposed via MCP has a
  corresponding dashboard stat card (R546 verb-coverage symmetry
  closure — the dashboard is operator-§1g surface #6, so its panel
  inventory must mirror the MCP family).

## Non-goals

- Forcing 8/8 on every module. Structural ceilings (R478) are
  correct-shape; bashrc 2/8 is legitimately a CLI-shaped tool, not
  a daemon — the 6 surface waivers are operator-justified.
- Stopping at threshold=3. The default threshold is the *minimum*;
  the operator-§1g STANDING RULE drives modules upward beyond
  threshold whenever a surface materially improves operator-UX.
- A single rotation schedule. Modules ascend the ladder
  asynchronously as each surface lands; R539 was the historic
  milestone where ALL §1g-named modules reached structural ceiling
  simultaneously.

## Historic milestones

| Round | What landed |
|---|---|
| R453 | 8-surface vocabulary + initial MODULE_COVERAGE + surface-map.py + 6 verbs (surfaces / modules / coverage / gaps / waivers / selfdef) |
| R462 | Cross-repo SurfaceManifest discovery (R462; selfdef side ships TOML manifests under `/etc/selfdef/surfaces`, sovereign-os discovers them via `surface-map selfdef`) |
| R478 | Structural-vs-FUTURE waiver precision (anti-min pattern only fires on FUTURE-class waivers) |
| R493 | Grafana dashboard (sovereign-os-surface-map.json) — closes the dashboard-surface waiver on surface-map itself |
| R506 | edge-firewall first §1g module at full 8/8 |
| R509 | network-edge §1g module at full 8/8 |
| R512 | global-history §1g module at full 8/8 |
| R515 | trinity §1g module at full 8/8 |
| R518 | router §1g module at full 8/8 |
| R521 | compliance §1g module at full 8/8 |
| R524 | anti-minimization-audit §1g module at full 8/8 |
| R527 | doc-coverage §1g module at full 8/8 |
| R530 | ux-design-audit §1g module at full 8/8 |
| R531-R533 | surface-map closes its own ladder — eating-our-own-dogfood (tui R531 + mcp R532 + api+webapp+service R533) |
| R536 | weaver §1g module at full 8/8 |
| R539 | **Historic milestone**: auditor reaches structural ceiling — TWELFTH and FINAL §1g-named module; rotation pool exhausted (15/15 at structural ceiling, 12/15 at full 8/8, ZERO FUTURE waivers) |
| R540 | First-class `milestone` rollup verb — surfaces the R539 state across CLI / TUI / API / MCP / webapp / dashboard |
| R541-R547 | `milestone` + `selfdef` + `gaps` surface promotions to MCP (R541-R545); dashboard verb-row symmetry closure (R546 + R547) |

The R539 anchor is operator-§1g sacrosanct:

> "TWELFTH §1g-named module to reach structural ceiling, closing
>  the §1g 8-surface delivery contract across the ENTIRE set of
>  §1g-named modules. The rotation pool is exhausted: ALL twelve
>  §1g instruments plus auth-tier / bashrc / master-dashboard
>  (fifteen total) are at structural ceiling with ZERO FUTURE
>  waivers remaining."

## Way forward

Three vectors remain open after R547:

1. **Quality of existing surfaces, not new ones.** Per R478 + R539,
   the "rotation pool" of §1g-named modules at structural ceiling is
   exhausted. Subsequent rounds improve the surfaces themselves —
   richer dashboards, more substantive API payloads, tighter MCP
   summaries, deeper L3 test coverage — NOT new surface promotions.
2. **Cross-repo binding completeness.** Sibling repos (selfdef,
   info-hub, devops-expert-local-ai) emit SurfaceManifests via the
   SD-R-MULTI-SURFACE-AUDIT-1 contract. Adding more cross-repo
   bindings (per SDD-038) extends the §1g lattice horizontally.
3. **Defense in depth.** Every new module landing on sovereign-os
   MUST declare its surface coverage (or operator-rationalized
   waivers) on day 1; the surface-gap anti-min pattern catches
   silent omissions in CI.

## Open questions

- **Q-039-A**: Should the structural-ceiling threshold be lifted
  from 3 → 4 (or 5)? Argues against: would force surface promotion
  on modules where structural waivers correctly apply. Argues for:
  raises the operator-§1g floor system-wide.  *(deferred — operator
  decision)*
- **Q-039-B**: Should `tui` (refresh-loop) be split into
  `tui:read-only` vs `tui:interactive-prompt`? R531-R537 watch-loops
  are all read-only; an interactive prompt-driven TUI (e.g. menu-
  driven `sovereign-osctl --interactive`) would shape differently.
  *(deferred — no current consumer)*
- **Q-039-C**: Does the §1g contract extend to operator-supplied
  modules (e.g. operator-authored ml-finetune scripts that aren't
  in the sovereign-os tree)?  Currently MODULE_COVERAGE is closed —
  operator-supplied scripts don't participate. *(deferred — operator
  decision; cross-repo SurfaceManifests partially address this)*

## Cross-references

- **R453 anchor**: `scripts/operator/surface-map.py` (SURFACE_IDS,
  MODULE_COVERAGE, 6 verbs + R540 milestone + R531 watch)
- **R456 standing rule**: `scripts/operator/anti-minimization-audit.py`
  (surface-gap pattern, R474 waiver enumeration, R478 precision)
- **R458 4-instrument rollup**: `scripts/operator/compliance.py`
  (status/module/worst/history/snapshot)
- **R462 cross-repo**: SDD-038, `scripts/operator/surface-map.py`
  (`cmd_selfdef`, SELFDEF_SURFACE_DIR)
- **R478 precision**: `scripts/operator/anti-minimization-audit.py`
  (`_is_future_waiver`)
- **R493 dashboard**: `docs/observability/dashboards/sovereign-os-surface-map.json`
- **R539 milestone**: `surface-map.py::cmd_milestone`
- **R540-R547 promotion lattice**:
  - R540 milestone verb (CLI rollup)
  - R541 milestone API endpoint + MCP tool
  - R542 webapp milestone panel
  - R543 watch-TUI milestone banner
  - R544 selfdef MCP tool
  - R545 gaps MCP tool (regression-detection)
  - R546 dashboard milestone + selfdef stat cards
  - R547 dashboards README anchor for R546
- **Cross-references**: SDD-016 (Layer B metric contract,
  `sovereign_os_operator_surface_map_query_total`), SDD-031 (MCP
  aggregator R286 fixed-argv rule), SDD-038 (cross-repo binding)
- **Operator-mandate**: operator §1g (verbatim, sacrosanct) +
  STANDING RULE (R456-anchored, verbatim, sacrosanct)
