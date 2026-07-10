# SDD-123 — DEMO tooling: reusable capture/verify utility + preflight + manifest

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-10
> Closes findings: operator directive 2026-07-10 — *"lets tool ourself, we can make the playwright screencapture more re-usable and configurable and such and other utilities like this like to avoid conflict."* Turns the throwaway `verify-batchN.mjs` scripts (used through SDD-119..122) into checked-in, configurable tooling, and adds a conflict-avoidance preflight. Recover band (SDD-123 / E11.M123 per SDD-100).
> Derived from / extends: the DEMO rollout (SDD-116..122). §1g.

## Mission

Three reusable dev utilities so every future DEMO batch (and any panel work) is verified the same way, and drift is caught before the gate:

1. **`scripts/webapp/demo-capture.mjs`** — manifest-driven Playwright capture + verify. CLI:
   `--panels a,b | --sdd SDD-1NN | --all`, `--demo on|off`, `--out DIR`, `--viewport WxH`, `--json`.
   Per panel it asserts the runtime SB-077 / R10212 contract: DEMO badge present, sample rows rendered
   (when a `rowSelector` is given), **zero calls to the panel's own data endpoint** (`apiPrefix`), zero
   page errors. Exits non-zero on any failure → a local self-validation gate. Resolves Chromium via
   `PLAYWRIGHT_BROWSERS_PATH` (fallback: the pinned `/opt/pw-browsers/chromium-*` install) and Playwright
   via `NODE_PATH` or a local install.
2. **`scripts/webapp/preflight.sh`** — the "avoid conflict" helper. One command before each increment:
   branch-behind-`origin/main` check (rebase needed?), `sync-app-shell.py --check` (app-shell drift the
   parallel header/sidemenu session churns), and the doc lints. Green/red summary; non-zero if anything
   needs attention.
3. **`scripts/webapp/demo-panels.json`** — the single source of truth for DEMO-capable panels
   (`slug` / `demoConst` / `apiPrefix` / `rowSelector` / `headInjected` / `sdd`). Consumed by
   `demo-capture.mjs` AND `tests/lint/test_demo_mode_contract.py`, so adding a panel to the rollout is a
   one-line manifest edit that the tool + lint both pick up.

Plus `make demo-capture` / `make demo-preflight` targets and a `.demo-captures/` gitignore.

## Grounded design (no new product behaviour)

- **Manifest-driven lint** — `test_manifest_covers_exactly_the_demo_capable_panels` (drift guard: manifest
  slugs == panels carrying `so-demo-badge` on disk, minus the personalization global toggle) +
  `test_manifest_panels_satisfy_the_generic_demo_contract` (helper + badge + `demoActive()` + `DEMO_<X>`
  + obvious `demo/`|`demo-` ids; helper in `<head>` unless `headInjected:false`). The bespoke per-panel
  asserts (EventSource guards / ternaries) stay as explicit cases.
- **`headInjected:false`** honestly records that the three SDD-116/117/118 panels (code-console, d-21,
  d-22) predate the SDD-119 head-injection rule and inline in `<body>` — they still pass at runtime
  (verified by `demo-capture.mjs`).
- Presentation/tooling only: no webapp behaviour change, no new data model, no web mutation
  (R10212/SB-077 untouched).

## Way forward

- **This SDD** — the three utilities + Makefile targets + gitignore + the two manifest lints. Backfills
  all 20 shipped demo panels into the manifest.
- **Verify** — `make demo-preflight` green; `make demo-capture` green (20/20 panels: badge + zero data
  API + no errors); `pytest tests/lint/test_demo_mode_contract.py`; full `make test`.
- **Next** — the next batch (selfdef mirror family d-12..d-17) uses this tooling: add the six panels to
  the manifest and verify with `make demo-capture` (no more throwaway scripts).

## Cross-references

- SDD-116 (DEMO + shared helper); SDD-119 (head-injection rule); SDD-120/121/122 (batches). SDD-100 — band scheme.
