# Review Phase 1 — Charter: the massive whole-repo improvement audit

> Status: **open** (findings ledger populated; items graduate to SDDs / backlog as they are picked up)
> Trigger: **operator-authored** (2026-07-12) — verbatim: *"If you had to improve sovereign-os, fix something, tap into unseen potentials, polish, and such, what would it be? you can generate a massive list of potential TODOs / Room for improvement / development. do not minimize, take your time and do this right and go big. If you find things hidden or unused or broken / that needs fixing and/or evolving this is to be included too […] By the end you should have a clear file which we may use to do future work and SDD."*
> Owner: operator + audit sessions
> Last updated: 2026-07-12

## Scope

The entire `sovereign-os` repository as of branch state 2026-07-12
(includes the unmerged intelligence-layer arc commits `234a474..7e9dea2`):

- `crates/` — 714 workspace crates (~221k LOC Rust)
- `webapp/` — ~50 cockpit panels (~138k LOC HTML/JS/CSS)
- `scripts/` — 706 files across ~40 domains (~189k LOC Python + bash, incl. the 9,081-line `sovereign-osctl`)
- `docs/` + `backlog/` — 129 SDD files, 85 milestone files (14,080 R-rows), decisions log, handoffs, standing directives
- `tests/` — 459 lint-contract tests + chroot/nspawn/qemu/schema/unit suites
- system surfaces — `config/`, `profiles/`, `schemas/`, `systemd/`, `models/`, `share/`, `whitelabel/`, `assets/`, CI workflows

## Non-goals

- The Anthropic Messages API compliance work (a parallel conversation owns it; the ledger only records *adjacent* gateway gaps, not that design).
- Fixing anything in this phase — Phase 1 produces the ledger; fixes land as future SDD-driven work.

## Deliverable

`99-findings-ledger.md` — the consolidated findings + TODO/opportunity
catalog, ID'd `F-0001-NNN`, severity-ranked, with evidence paths, intended
as the seed inventory for future SDDs and backlog items.
