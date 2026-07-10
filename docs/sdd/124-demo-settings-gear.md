# SDD-124 — header settings gear + DEMO on/off pane (every page)

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-10
> Closes findings: operator directive 2026-07-10 — *"we should be able to dissable DEMO on any page, we should have a settings gear on the right of 'assist' in the header with a non invasible pane that contain this first setting. I dont want demo by default / in prod"* + *"obviously stored to localstorage and live update."* Recover band (SDD-124 / E11.M124 per SDD-100).
> Derived from / extends: SDD-116 (DEMO opt-in + always-badged), SDD-123 (tooling). §1g.

## Mission

Add a **settings gear (⚙)** to the shared app-shell header, immediately right of the **✦ Assist**
button, opening a **non-invasive popover** whose first (and, today, only) setting is a **DEMO mode on/off
switch**. Available on **every** cockpit page (the app-shell ships to all 52 panels), so DEMO can be
turned off anywhere — DEMO is **OFF by default** (never demo in prod). The switch is **localStorage-backed**
(`sovereign-os.demo`, schema-guarded — the same key the per-panel DEMO treatment reads) and **live-updates**
on toggle.

## Grounded design (no new product behaviour, no web mutation)

- **Gear button** `#so-settings-toggle` in `webapp/_shared/app-shell-snippet.html` header, after
  `#so-assist-toggle`. `aria-haspopup` + `aria-expanded`.
- **Popover** `#so-settings-pane` — `position:fixed` under the header on the right, `hidden` by default,
  non-modal; click-outside / `Esc` closes. Row: **DEMO mode** label + a `role="switch"` toggle
  (`#so-demo-switch`), an honest sub-label ("badged sample data, never real telemetry"), and a
  "not for production · saved on this device" footer.
- **State** — `demoOn()` reads `sovereign-os.demo` (schema `1`, default **off**); `demoSet(on)` writes it,
  dispatches a `sovereign-os:demo-change` event, then **live-updates**: calls `window.soDemoApply()` if a
  panel exposes it (flash-free) else `location.reload()`. Self-contained in the app-shell (works on every
  page, including panels with no DEMO treatment — there it just persists the flag, fabricating nothing).
- The **badge + sample data still come from each panel's own DEMO treatment** (SB-077) — the gear only
  flips the shared flag. On a non-demo page, turning DEMO on shows no badge and no fabricated data
  (verified: `master-dashboard` badge stays absent).
- Distributed to all panels via `scripts/webapp/sync-app-shell.py --apply` (the canonical M067 block).
  R10212/SB-077 untouched — presentation-only; no fetch, no mutation.

## Way forward

- **This SDD** — the gear + pane + toggle in the app-shell snippet, synced to all 52 panels, + a contract
  lint (`tests/lint/test_settings_gear_contract.py`).
- **Verify** — `sync-app-shell.py --check` in sync; Playwright: gear present on a demo panel AND a
  non-demo page, pane opens, switch off by default, toggle writes `{schema:1,on:true}` + reloads +
  (on a demo panel) the badge appears; zero page errors. Full `make test`.
- **Next** — the DEMO rollout continues (selfdef mirror family d-12..d-17, then the rest). A later
  enhancement can register `window.soDemoApply` in each panel for flash-free (no-reload) live update.

## Cross-references

- SDD-116 (DEMO + shared helper + the personalization global toggle, which shares the same
  `sovereign-os.demo` key); SDD-123 (tooling). SDD-100 — band scheme.
