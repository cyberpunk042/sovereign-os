# SDD-070 — Science-tools catalog + NVIDIA Warp particle-sim integration & panel

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-09
> Derived from: operator directive 2026-07-09 ("There should be somewhere something about Science experiment, tools of such type, we will add to it Nvidia Warp / warp-lang and we will start coding it, its integration and panel" → "the full job, planned properly"). Materialises the operator's Image-2 "scientific / merge / specialist catalog" (info-hub `raw/notes/2026-07-02-operator-model-routing-catalog-handwritten-verbatim.md`, encoded in the wiki `config/model-catalog/{models.yaml,profiles.yaml}` as the `dna`/`protein`/`particles` profiles). Anchors to the `simulation` REPL kind in `config/execution/m023-execution-substrate.yaml` (M00374, Tiers 3-5). R558. Mandate cross-link: E11.M37.

## Mission

Bring the operator's **science / domain compute-tools catalog** into sovereign-os
and ship the first tool — **NVIDIA Warp** (`warp-lang`, the `particles` entry) —
end-to-end on the §1g surface ladder: a schema-validated catalog, a GPU-or-CPU
differentiable particle-sim runner, and a read-only dashboard panel.

## Problem

The science catalog lives only in the info-hub wiki (the SAIN-01 master spec).
Nothing in sovereign-os materialises it: `models/catalog.yaml` is LLM-only, and
there is no home for **non-LLM** tools. NVIDIA Warp is explicitly *"not an LLM"* —
a Python + CUDA library for high-performance / differentiable simulation — so it
must not go in the model catalog. Without a science-tools surface the operator
cannot see, install, or run these tools from the cockpit.

## Grounded reality (SB-077)

- Warp is `pip install warp-lang` (v1.15.0, Apache-2.0, Py≥3.10, sole hard dep
  numpy). The wheel **bundles the CUDA 12 runtime**, so GPU works with just the
  NVIDIA driver (sain-01 ships it); **it also runs on CPU** when no CUDA GPU is
  present. Verified: the runner ran a 50k-particle sim on CPU in an isolated venv
  (`cuda_available:false → device:cpu`).
- On SAIN-01 the host targets the **RTX PRO 6000 (`cuda:0`)** — the RTX 4090 is
  VFIO-isolated (`profiles/sain-01.yaml`).
- The dev/CI box has neither warp nor CUDA — so every operator-facing surface must
  degrade to **exit 0 + honest banner** (gpu-watch precedent), never a failure.
- Runtime scripts are stdlib-only by convention; only the runner subprocess and
  the install hook may `import warp`.

## Required coverage

### config/science-tools.yaml + schemas/science-tools.schema.yaml (NEW)
Schema-validated catalog of the 7 tools by domain (DNA / protein / particles).
`warp-lang` = `integrated`; the other six = `cataloged` (data only, future rounds).
Conformance: `tests/schema/test_science_tools_schema_conformance.py`.

### scripts/science/warp-runner.py — the runner (NEW; the ONLY warp-importing script)
Device-select (`cuda:0` if `wp.is_cuda_available()` else `cpu`), run a raw-kernel
particle drop-and-bounce sim (`warp.sim`-class, version-stable), report the device
+ observables. `run`/`status`, `--json`/`--emit-metrics`, exit 0 (clean incl. CPU
and warp-absent) / 1 (sim raised) / 2 (usage). Config: `config/science/warp.toml`.

### scripts/science/science.py — core+cli (NEW, stdlib-only)
`list` / `status` / `run` / `install` / `info <id>`. Reads the catalog; delegates
all Warp work to the runner. The stdlib-only operator surface.

### scripts/operator/science-api.py — api (NEW, stdlib-only, read-only)
`GET /healthz /version /science.json /control-systems /` + static; POST → 405.
Port 8134. Shells `science.py`; NEVER imports warp, NEVER runs a sim.

### webapp/science/index.html — webapp (NEW)
Single-file, zero-dep, canonical monochrome palette. Warp status + catalog by
domain; a "run sample sim" copy-command control (execution stays the gated CLI).

### scripts/hooks/post-install/warp-setup.sh — first-boot install (NEW)
Idempotent `pip install warp-lang` (`--break-system-packages` on trixie/PEP-668);
emits `sovereign_os_post_install_warp_setup_total`. Unit:
`systemd/system/sovereign-warp-setup.service` (ConditionFirstBoot, in `FB_UNITS`).

## Wiring

- CLI: `sovereign-osctl science …` bridge (delegates to `science.py`).
- Service: `sovereign-science-api.service` (R171-hardened, loopback) — enabled at
  bake (`provision-bake.sh §5`) and on live hosts (`install-gui-dashboards.sh`,
  read-only so `enable_unit`, not deploy-only).
- Catalog: `config/dashboard-catalog.yaml` — new `science` category + entry.
- Surface ladder: `scripts/operator/surface-map.py` `MODULE_COVERAGE["science"]` =
  {core, cli, api, service, webapp}; tui / mcp / dashboard waived to a follow-up.
- Deps: `warp-lang` added to `config/operator-deps.toml.example [pip]`.
- Test: `tests/nspawn/test_science_panel.sh` (+ CI layer-3 step). Metrics documented
  in `docs/observability/dashboards/README.md`.

## Open questions

| Q | question | status |
|---|---|---|
| Q-065-A | Catalog home = a new `config/science-tools.yaml` + schema (vs extend the model catalog)? | **answered** (operator chose the new science-tools catalog + schema, 2026-07-09) |
| Q-065-B | Scope = the full job (catalog + runner-service + panel), not a minimal slice? | **answered** (operator: "the full job", 2026-07-09) |
| Q-065-C | The other 6 science tools (DNA/protein) runners + a GPU-path CI stage on SAIN-01 hardware. | proposed (Stage N) |
| Q-065-D | The tui / mcp / Grafana-dashboard rungs for the science module (currently waived). | proposed (Stage N) |
| Q-065-E | Flip the wiki `warp-lang` status → integrated (cross-repo; SDD-001 boundary — operator's call). | proposed (Stage N) |
