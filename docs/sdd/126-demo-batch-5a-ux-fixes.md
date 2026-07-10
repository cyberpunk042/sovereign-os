# SDD-126 — DEMO batch 5a (edge/mgmt) + badge-position + light-theme + ups fix

> Status: draft
> Owner: operator-directed; agent-authored
> Last updated: 2026-07-10
> Closes findings: the operator-approved broad DEMO rollout (roadmap Phase 1, batch 5a) **plus two operator-flagged UX bugs** (2026-07-10): *"the demo notice btw is at the wrong place, it should be at the bottom center, not over the setting menu"* and *"when the theme is light, isn't it supposed to be light"*. Recover band (SDD-126 / E11.M126 per SDD-100).
> Derived from / extends: SDD-116/119/123..125 (DEMO + tooling + gear). §1g.

## Mission

Three things in one increment:

1. **Batch 5a DEMO** — `edge-firewall`, `network-edge`, `selfdef-management`, `ups`, `science`. Two are
   true multi-fetch aggregators (edge-firewall: 4 endpoints via `Promise.all`; network-edge: 6) → one
   merged `DEMO_<X>` object each, destructured before the `Promise.all`; the other three are single-endpoint
   `load()`s → render the const directly. Each: shared helper in `<head>` (SDD-119), `demoActive()` gate,
   badged `DEMO_<X>` with `demo/`|`demo-` ids, **zero network in the demo path**.
2. **Badge position** — the DEMO badge moved from top-right (where it covered the SDD-124 settings gear) to
   **bottom-center** (`position:fixed; bottom:14px; left:50%; transform:translateX(-50%)`). Updated in the
   canonical `webapp/_shared/demo-mode.css` + every demo panel's inlined copy.
3. **Light theme** — 10 panels lacked the `html[data-theme="light"]` var override, so the theme toggle set
   `data-theme="light"` but they stayed dark. Added the override (`--bg`/`--fg`/`--muted`/`--panel`/
   `--border` light values) to all 10, bringing coverage to **52/52**.

Plus a **pre-existing bug fix**: `ups` had `const shutMin` declared twice in `render()` — a `SyntaxError`
that broke the entire panel (live and demo). Surfaced by `make demo-capture` (page-error), fixed by
dropping the redundant second declaration.

## Grounded design (no new data, no web mutation)

- edge-firewall / network-edge: `if (demoActive()) { const {…} = DEMO_<X>; render…; return; }` at the top of
  `refresh()`'s try, before the `Promise.all`. No banner/EventSource in these.
- selfdef-management / ups / science: `if (demoActive()) { render/populate from DEMO_<X>; status = "DEMO"; return; }`
  at the top of `load()`'s try.
- All five added to `scripts/webapp/demo-panels.json`; the tool + manifest lint + bespoke guards cover them.
- Badge + light-theme are presentation-only; R10212/SB-077 untouched. New lints pin both against regression
  (`test_demo_badge_renders_bottom_center`, `test_light_theme_coverage.py`).

## Way forward

- **Verify** — `make demo-preflight`; `make demo-capture --sdd SDD-126` (5/5: badge + rows + zero data-API +
  no errors); Playwright confirms badge bottom-center + light theme renders light (bodyBg #f6f6f6);
  `pytest tests/lint/test_demo_mode_contract.py tests/lint/test_light_theme_coverage.py`; full `make test`.
- **Next** — batch 5b (trinity, weaver, auditor, router, global-history), then batch 6 (hard + badge-only).

## Cross-references

- SDD-116/119/123/124/125 (DEMO + head recipe + tooling + gear + selfdef). SDD-100 — band scheme.
