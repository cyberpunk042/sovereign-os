# SDD-511 — Token-law mask-coverage heatmap: the cockpit dashboard (F00796)

> Status: active · Mandate: **E11.M511** (control-bits band 500–599)
>
> Cross-link: closes the **M00155 Expose arc** (`backlog/milestones/M010-deterministic-data-plane.md`, F00796) over the M00117 engine. The tenth SDD in the control-bits band, and the **third/last of the Expose arc** (SDD-507 route, SDD-510 osctl verb + profile/env, this dashboard).
>
> Number band: **500–599 (control-bits session)**
>
> **v1 shipped 2026-07-23** — operator-directed (*"continue"* → the token-law Expose fork). SDD-507 exposed the fusion route; SDD-510 made the layer selection operator-configurable; this gives the coverage a **visual home in the cockpit** — the last of the three Expose surfaces (crate+route → CLI+config → dashboard).

## Mission

The token-law engine's per-step decision — the fused allow-mask — is a pure,
checkpoint-free function of the layer sources + the vocabulary. SDD-507 exposed
it over HTTP; SDD-510 gave the operator a knob on *which layers* are active.
F00796 completes the Expose arc: a **read-only cockpit panel** that renders, per
named law (`grammar` / `regex` / `denylist` / `regex_denylist` / `policy`), how
much of the vocabulary that law permits — a **coverage heatmap**. It makes the
otherwise-invisible engine decision legible at a glance.

## The honesty insight (unchanged from SDD-507)

Coverage is a pure function of the sources + vocab — no model, no logits. So the
panel is **exact without a trained checkpoint**: it POSTs sample fuse requests to
the same `/v1/data-plane/token-law/fuse` route the CLI drives, and reads the
per-layer allowed counts. The dashboard is the visual mirror of
`sovereign-osctl token-law fuse`.

## Design

### 1. The panel — `webapp/token-law-coverage/index.html`

A standard cockpit panel (app-shell chrome + the inlined control-surface,
adopted like every other) rendering:
- a **per-layer coverage heatmap**: one bar per canonical layer, filled to
  `allowed / vocab` and colored on a continuous permitted-fraction scale
  (`hsl(120·frac, …)` — green = permissive, red = restrictive);
- stat tiles (gateway up/down, sample vocab size, fused-allowed intersection,
  cumulative fusions served);
- an **honest offline degrade** — when `sovereign-gatewayd` is unreachable it
  renders "offline" and never fabricates coverage.

### 2. The daemon — `scripts/operator/token-law-coverage-api.py` (port 8148)

A read-only, stdlib-only per-panel daemon that, on
`GET /api/token-law-coverage/coverage`, derives coverage by POSTing a built-in
**sample scenario** — a fixed sample vocab + one representative source per layer
(a `{"type":"string"}` schema, a `[a-z]+` regex, a literal denylist, a
`[0-9]{2,}` negated-regex, a policy bitset) — to the gateway's checkpoint-free
fuse route, once per layer (isolated coverage) plus one combined fuse (the fused
intersection). It POSTs **only** to the sanctioned fuse route (a read-compute,
never a state mutation — the same server-side pattern `brain-api` uses); a
browser write is 405. It reads the cumulative
`sovereign_data_plane_token_law_mask_layers` counter off `/metrics` for the
"fusions served" tile (that metric is a counter, **not** per-layer coverage —
coverage must be derived from the fuse responses).

### 3. Registration

Full dashboard chain: `config/dashboard-catalog.yaml` entry (category `models`,
`api: sovereign-token-law-coverage-api`, status live); the `token-law` verb's
`feature-coverage.yaml` **cli-only waiver is converted to a real
`coverage:` mapping** (`token-law-coverage: [token-law]`) now that it has a
dashboard home; a reserved-free port 8148 + the systemd unit
`sovereign-token-law-coverage-api.service` (full R171 hardening, loopback
default); regenerated `panel-api-routes.yaml` + `dashboard-routes.yaml`; the
panel adopted into the app-shell + control-surface inline set.

## What shipped

- **`webapp/token-law-coverage/index.html`** — the heatmap panel (adopted).
- **`scripts/operator/token-law-coverage-api.py`** (:8148) — the read-only
  coverage daemon (sample scenario → fuse route → per-layer coverage; honest
  offline degrade).
- **`systemd/system/sovereign-token-law-coverage-api.service`** — the unit.
- **`config/dashboard-catalog.yaml`** + **`config/feature-coverage.yaml`** (waiver
  → coverage) + regenerated `panel-api-routes.yaml` / `dashboard-routes.yaml`.
- **App-shell + control-surface** adoption; `context.md` panel count 63→64.
- **`tests/lint/test_token_law_heatmap_webapp_contract.py`** (9) — panel fetches
  the coverage feed same-origin, renders the heatmap, degrades honestly, inlines
  the control-surface; the daemon's sample scenario covers the five canonical
  layers, is read-only (405 on writes), and **live-spawns to prove the offline
  degrade** (up:false when the gateway is down); the catalog entry + systemd
  unit + port are pinned.

## Non-goals / roadmap

- Operator-supplied sources/vocab (a v2 input form) — this ships the built-in
  sample scenario; the CLI (`token-law fuse`) already accepts custom sources.
- With F00796 shipped, the **Expose arc is complete**. The fork continues with
  **Connect** (constrain real `/v1/messages` traffic — the no-logit-access
  serving boundary) and **Deepen** (the route plane as a real source, a
  text→token safety projection, SIMD).

## References

- Milestone row: `backlog/milestones/M010-deterministic-data-plane.md` F00796 (M00155).
- Arc: `docs/sdd/507-token-law-fusion-data-plane.md` (route), `docs/sdd/510-token-law-mask-layer-selection.md` (osctl verb + profile/env).
- Route + metric: `crates/sovereign-gatewayd/src/http.rs` (`token_law_fuse`, `/metrics`).
- Panel model: `webapp/chromofold/index.html` + `scripts/operator/chromofold-api.py`.
