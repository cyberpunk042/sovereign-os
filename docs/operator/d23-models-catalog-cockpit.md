# D-23 — Model Catalog (cockpit panel)

> Operator-facing cockpit panel. Read-only mirror. Operator §1g standing rule
> (sacrosanct): **We do not minimize anything.**

## What it is

D-23 is the **browse-the-portfolio** view of the canonical model registry
(`models/catalog.yaml`) — every model grouped by SRP tier (Pulse / Logic /
Oracle / Router) with its class, engine, precision, parameter count, context
window, license, purpose, and verification status. It flips the
dashboard-catalog's `models-catalog` **planned** surface to **live**.

Distinct from **D-03 model-health** (which shows the *live serving health* of
the currently-bound models) — D-23 shows the *full catalog* an operator can
choose from.

Data source: **reuses** `scripts/inference/model-health.py` `load_catalog()`
(the same reader the D-03 core + `sovereign-osctl models` use) — no new data
model, no drift.

## Surfaces (§1g ladder)

| Surface | Path |
|---------|------|
| core | reused: `scripts/inference/model-health.py` `load_catalog` |
| api | `scripts/operator/models-catalog-api.py` — `GET /api/models-catalog/{catalog,stream}` |
| webapp | `webapp/d-23-models-catalog/index.html` (`/webapp/`) |
| service | `systemd/system/sovereign-models-catalog-api.service` (loopback `127.0.0.1:8123`) |

Registered in `surface-map.py` (`models-catalog`, 4/8 at structural ceiling) +
`nav-snippet.html` (D-23) + `config/dashboard-catalog.yaml`. Inlines the SDD-045
control surface; SDD-040 palette compliant.

## Read-only boundary (R10212)

Never mutates. The daemon fail-closes on POST/PUT/DELETE (`405`). Model
lifecycle stays on the signed CLI: `sovereign-osctl models {list,pull,verify,
info,eval,remove}`.

## Run it

```sh
python3 scripts/operator/models-catalog-api.py    # http://127.0.0.1:8123/webapp/
systemctl enable --now sovereign-models-catalog-api.service
```

`--self-check` prints one catalog view and exits 0 (CI smoke).

## Related

- **D-03 model-health** — live serving health (the runtime counterpart).
- **D-21 LM Orchestration** — profiles + model→hardware assignment.
- **M017** model portfolio · **M075** SRP tiers.
