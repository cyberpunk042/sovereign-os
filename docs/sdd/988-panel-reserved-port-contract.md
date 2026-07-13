# SDD-988 — panel reserved-port contract: tribal knowledge becomes a CI signal (F-2026-075)

> Status: draft
> Owner: operator-directed 2026-07-13 ("we continue"); agent-authored.
> Closes: **F-2026-075** (LOW).
> Mandate module: **E11.M988**.
> Number band: **950–999 (phase-1 audit session)** per SDD-100.

## Mission

`scripts/operator/panel.sh` starts three main servers on reserved ports — the
build configurator (`CFG_PORT`, default **8100**), the runtime dashboard
(`DASH_PORT` from `DASH_BIND`, default **8443**), and the live-reload broker
(`LR_PORT`, default **8136**) — then loops over `scripts/operator/*-api.py`,
starting each data API on its systemd-unit port. It carries a **runtime** collision
guard (skip any data API whose port equals `CFG_PORT`/`DASH_PORT`) that exists only
because of a real incident: `sovereign-ux-design-audit-api` shipped `PORT=8100 ==
CFG_PORT`, `start_server`'s takeover evicted the configurator, and every panel
404'd (2026-07-03). That guard is **load-bearing tribal knowledge in a comment** —
it protects the running launcher but nothing stops a *new* unit from re-declaring
a reserved port and only failing at runtime. This promotes it to a CI-time contract.

## What this SDD builds

**`tests/lint/test_panel_reserved_ports.py`** (stdlib + pytest):
- reads the reserved ports **from panel.sh itself** — its `VAR="${ENV:-DEFAULT}"`
  defaults, the *same single source* the runtime guard uses, so the two can't
  drift (no parallel config to maintain);
- asserts **no `sovereign-*-api.service` unit declares a reserved port**. The
  owning services (`sovereign-dashboards.service` on 8100, etc.) are not
  `*-api.service` units, so they are correctly excluded;
- a sanity test asserts all three reserved ports parse, so a panel.sh format
  change that breaks parsing fails loudly instead of silently passing.

Pairs with `test_dashboard_port_and_reference_integrity.py` (no two units share a
port); this adds the orthogonal invariant "no data-API unit sits on a reserved
main-server port."

## Why a read-only contract (not a config rewrite)

The finding suggested "a single generated source consumed by both the guard and
the lint." Investigation showed panel.sh is **already** the single source: the
runtime guard reads `CFG_PORT`/`DASH_PORT` from panel.sh's own defaults, and the
data-API ports live in the systemd units (also read by the existing lint). So the
missing piece was not a new config — it was a lint reading the *same* panel.sh
source, turning the runtime-only guard into a CI-time signal, **without editing
panel.sh** (a shared operator script — collision-safe to leave untouched).

## Verification (real, observed)

- `python3 -m pytest tests/lint/test_panel_reserved_ports.py` — **2 passed**;
  parses `{8100: configurator, 8443: runtime-dashboard, 8136: live-reload}` from
  panel.sh, checks 53 `sovereign-*-api.service` units, **0 collisions**.
- `ruff check` clean.
- The historical `ux-design-audit-api:8100` incident would fail this contract.

## Non-goals

- Editing panel.sh's runtime guard (it works; it's a shared script — read-only
  here). A future increment could have panel.sh's guard also cover `LR_PORT`
  (this lint already does), but that's a panel.sh edit for its owning session.
- A generated port-map config — unnecessary; panel.sh + the units are the source.

## Safety invariants

One new `tests/lint/` file + this SDD + registries. No gatewayd/cockpit/`unsafe`/
crate/panel.sh edits (panel.sh + the units are read, never written); collision-safe.
R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `tests/lint/test_panel_reserved_ports.py` — the contract
- `scripts/operator/panel.sh` — the reserved-port defaults + the runtime guard (the source, read-only)
- `tests/lint/test_dashboard_port_and_reference_integrity.py` — the sibling port lint (no two units share a port)
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-075 (closed here), F-2026-020 (the health baseline)
