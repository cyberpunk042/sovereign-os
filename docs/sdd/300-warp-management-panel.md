# SDD-300 — Warp management panel (warp-solar-system-shaders: catalog, relations & execution)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-16
> Closes findings: E11.M300 (mandate decomposition — science-tools band)
> Derived from: operator directive 2026-07-16 ("There is a visual/panel that might be missing and its a real warp management that fits well with a project like warp-solar-system … we have an example project with libs and examples and modules and such and we should be able to see the relations and even execute from the panel" → `/goal` "achieve both phases into a single PR. do not minimize"). First SDD in the **science-tools band (300–399)** per SDD-100. Builds ON SDD-070 (which catalogs `warp-lang` as a science tool + ships a stub particle-sim) and SDD-045 (the control-systems registry / exec-rail) + SDD-047 (R10274 functional-cockpit execution).

## Mission

Turn the cockpit's **stub Warp integration into real Warp management.** SDD-070
catalogs `warp-lang` and ships a single toy particle-sim (copy-only). This SDD
surfaces the **`warp-solar-system-shaders`** project — a real NVIDIA-Warp
procedural rendering engine (217 auto-discovered scenes, 20 lib packages, four
example runners) — as a first-class cockpit panel that lets the operator **see
the relations** (the scene→lib / lib→lib import graph) and **execute** a scene
(render / bench) through the sanctioned exec-rail. Both phases ship together.

## Problem

The `warp-solar-system-shaders` engine is rich and well-structured (a scene
registry, distinct lib packages, clean runner CLIs), but sovereign-os has no
window onto it: the science panel is a flat 7-tool catalog whose Warp entry is a
particle-sim stub. Nothing shows the *shape* of the engine (which scenes use
which libs, how the libs depend on each other) and nothing lets the operator run
a scene from the cockpit. The operator named the gap: *"a real warp management …
no real management and that is a lack."*

## Grounded reality

- The shaders project is a **separate repo**, not resident on the sovereign-os
  host. So — exactly like SDD-070's science catalog — its catalog is **generated
  and committed**: `config/warp-catalog.yaml` (217 scenes + 20 libs + edges) is
  produced by `scripts/warp/gen_catalog.py` from a checkout (pure `ast` parsing,
  no warp/CUDA import), and is the panel's source of truth. Byte-identical /
  reproducible for a given checkout (`--check`).
- The **relations are real data**, not hand-drawn: a scene's libs are its Python
  imports (`from ..engine import post`), extracted statically. Empirically:
  engine→139 scenes, procedural→108, subatomic→35, lod→28, … (all 217 scenes map
  to ≥1 lib).
- The dev/CI box has neither the checkout nor a GPU, so every surface must
  **degrade to an honest exit-0/exit-3 banner** (SDD-070 doctrine), never a
  failure. `render`/`bench` no-op with guidance when no checkout is resident.

## Phase A — catalog + relations (read-only)

### config/warp-catalog.yaml + schemas/warp-catalog.schema.yaml (NEW)
The generated, schema-validated catalog: `scenes[]` (name, file, summary, libs),
`libs[]` (id, kind, summary, scene_count, depends_on), `counts`, `runners`.
`scenes[].libs` + `libs[].depends_on` ARE the relation graph. Conformance:
`tests/schema/test_warp_catalog_schema_conformance.py` (validates the schema +
pins counts-match-arrays, edges-reference-declared-libs, unique names, render/bench
runners present).

### scripts/warp/gen_catalog.py — the generator (NEW, stdlib-only)
`WARP_SHADERS_ROOT=<checkout> python3 scripts/warp/gen_catalog.py` → writes the
catalog; `--check` fails if stale; `--stdout` previews. Never imports warp.

### scripts/warp/warp_manage.py — core+cli (NEW, stdlib-only)
`list [--lib L] [--search Q]` / `libs` / `relations [--scene S] [--lib L]` /
`info <scene>` / `status`. Reads the catalog; the read surface for the panel.

### scripts/operator/warp-api.py — api (NEW, stdlib-only, read-only)
`GET /healthz /version /warp.json /warp/{scenes,libs,relations} /control-systems /`
+ static; **POST → 405**. Port **8138**. Shells `warp_manage.py`; NEVER imports warp.

### webapp/warp/index.html — the panel (NEW)
Single-file, zero-dep, same-origin. A status strip, an inline-SVG **lib
dependency graph** (nodes sized by scene-usage, lib→lib edges, click-to-filter),
and a searchable/filterable scene table with per-scene lib chips. Inlines the
shared control-surface verbatim (SDD-045 lockstep).

## Phase B — execution (the exec-rail)

No new write path is invented — execution reuses the R10274 control-exec rail:

### config/control-systems.yaml — two controls (NEW)
`warp-render` (`change_cli: sovereign-osctl warp render <scene>`) and `warp-bench`
(`… warp bench <scene>`), `kind: lifecycle`, `applies_to: [warp]`,
`privileged: true` (real GPU/CPU compute → operator-key + type-to-confirm). The
free `<scene>` is validated by `_action_exec._SAFE_VALUE` (all 217 names pass);
`options` seeds a hero-scene datalist.

### config/sudoers.d/sovereign-os-cockpit — allowlist (EXTENDED)
`sovereign-osctl warp render *` + `warp bench *` added to `SOVEREIGN_OS_COCKPIT`
(kept in lockstep with the registry by `test_cockpit_action_exec_sudoers.py`;
selfdef/perimeter still absent — R10212).

### sovereign-osctl warp — the gated verb (EXTENDED)
`warp )` dispatches to `warp_manage.py`; `render`/`bench` shell the project's own
`render.py` / `bench.py` when a checkout is resident, else the honest no-op.
Validates the scene against the catalog AND a strict token before executing.

### the panel Execute path
`SovereignControlSurface.load(…, {filterSlug:'warp'})` renders the render/bench
cards; each per-scene Render/Bench button fills the card's `<scene>` input and
scrolls to it (the shared component's Execute is the only mutating path — it POSTs
to the same-origin control-exec-api, copying the command where not fronted by it).
Privileged actions inherit dry-run-by-default + type-to-confirm + single-flight +
Prometheus counter + OCSF-5001 audit span for free.

## Wiring

- Catalog: `config/dashboard-catalog.yaml` — `warp` entry under the `science`
  category, `status: live`, `api: sovereign-warp-api`.
- Service: `systemd/system/sovereign-warp-api.service` (R171-hardened, loopback,
  port 8138). Auto-discovered by `panel.sh`.
- Registry lint: `warp-render` + `warp-bench` added to
  `tests/lint/test_control_systems_registry.py` `EXPECTED_IDS`.

## Open questions

| Q | question | status |
|---|---|---|
| Q-300-A | Both phases (catalog+relations AND execution) in a single PR? | **answered** (operator `/goal`, 2026-07-16) |
| Q-300-B | Cross-repo dependency = a committed generated catalog + runtime checkout via `WARP_SHADERS_ROOT` (vs submodule / hard pip dep)? | **answered** (chose the SDD-070 committed-catalog pattern — no host residency required, CI-safe) |
| Q-300-C | Dedicated `webapp/warp/` panel (vs extending the science panel)? | **answered** (dedicated panel — "real management" surface distinct from the 7-tool science catalog) |
| Q-300-D | Vendor the shaders project (submodule) so the host can render without a manual checkout. | proposed (Stage N) |
| Q-300-E | The tui / mcp rungs + a per-scene thumbnail gallery (render output served back). | proposed (Stage N) |
| Q-300-F | Flip the SDD-070 wiki `warp-lang` entry to reference this management surface (cross-repo; SDD-001 boundary). | proposed (Stage N) |
