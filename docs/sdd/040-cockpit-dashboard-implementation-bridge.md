# SDD-040 — Cockpit dashboard implementation bridge (M060 catalog → webapp pages)

**Status**: ACTIVE
**Owner**: @cyberpunk042 (Architect)
**Created**: 2026-05-19
**Source milestone**: `backlog/milestones/M060-cockpit-and-dashboards-ux-surface.md` (21 catalogued dashboards D-00..D-20)
**Implementation surface**: `/webapp/` (single-file sovereignty-clean HTML+CSS+JS dashboards, no framework, no CDN)

> Closes findings: none (bridges the M060 cockpit-dashboard catalog — 21 dashboards D-00..D-20 — to their `/webapp/` implementations; sister to the §1g Dashboard surface tracked at E11.M2 / E11.M3)

## Mission

M060 catalogs **21 dashboards (D-00..D-20)** with 170 requirements. The webapp directory already ships **14 single-file dashboards** built under the established sovereignty-clean UX doctrine (monochrome palette, monospace font, no framework, no CDN, no external fonts). This SDD is the **bridge artifact**: maps each catalogued dashboard to its webapp implementation (where one exists), identifies coverage gaps, and orders the implementation backlog.

Per operator standing direction: *"there is over 20 dashboards and a main one and everything can be turned on and off and there are also a tons of modes and profiles"* + *"you cannot re-invent what UX mean... obviously i expect dashboards and a good UX"*. The implementation discipline is established and operator-validated (existing 14 dashboards). This SDD does NOT redesign — it materializes the M060 catalog into ordered implementation work.

## UX doctrine (preserved from existing dashboards)

Lifted verbatim from `/webapp/master-dashboard/index.html` line 11-13:

> "Operator-§1g UX: readable in 30 seconds, monochrome palette, no JS framework, no CDN, no fonts fetched from elsewhere — sovereignty-clean single-file webapp."

Color palette (verbatim from `:root` block):
- `--bg: #0e0e0e` (background)
- `--fg: #e6e6e6` (foreground)
- `--muted: #888` (muted text)
- `--accent: #9bd1ff` (section headings)
- `--good: #7ad17a` (positive state)
- `--bad: #ff7676` (negative state)
- `--warn: #e6c062` (warning state)
- `--panel: #171717` (panel background)
- `--border: #262626` (panel borders)
- `--mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`

Component vocabulary: `.panel` (container), `.row` (flex row), `.stat` (single-metric card), `.pill` (status chip), `.ok`/`.bad`/`.warn`/`.muted` (state colors), table with `th`/`td` (data tables).

Meta requirements (every dashboard):
- `<meta name="x-sovereign-module" content="<dashboard-id>-webapp">`
- `<meta name="x-sovereign-shipped-in" content="R<ID>">`
- `<meta name="x-sovereign-standing-rule" content="We do not minimize anything.">`

## M060 → webapp coverage map

| M060 catalog ID | M060 purpose | webapp implementation | status | implementation R-range |
|---|---|---|---|---|
| D-00 | main index + global health + active-session count + quick-action bar + Cmd-K palette | `/webapp/master-dashboard/index.html` | **✓ shipped** | M060 R10050-R10058 |
| D-01 | active sessions (per-task M057 lifecycle step + profile + ETA + hibernate/resume/kill) | `/webapp/d-01-active-sessions/` + `scripts/operator/sessions-api.py` (+ core `scripts/lifecycle/session-registry.py`, CLI `sovereign-osctl sessions`, service `sovereign-sessions-api.service`) | **✓ shipped (full stack → prod)** | M060 R10059-R10062 |
| D-02 | profile choices (six-profile selector + L0..L6 envelope + Ring 0..4 highlights + history + predeclared-gate editor) | `/webapp/d-02-profile-choices/` + `scripts/operator/profile-mirror-api.py` (+ READ-ONLY mirror core `scripts/mirror/selfdef-profile-mirror.py`, CLI `sovereign-osctl profile-mirror`, service `sovereign-profile-mirror-api.service`) | **✓ shipped (full stack → prod, read-only selfdef MS040 mirror)** | M060 R10063-R10068 |
| D-03 | model health (Blackwell/3090/CPU + VRAM + KV cache + p50/p95/p99 latency + heatmap) | `/webapp/d-03-model-health/` + `scripts/operator/model-health-api.py` (+ core `scripts/inference/model-health.py`, CLI `sovereign-osctl model-health`, service `sovereign-model-health-api.service`) | **✓ shipped (full stack → prod)** | M060 R10069-R10074 |
| D-04 | costs (daily budget + per-request + project/profile/model breakdowns + forecast + alert thresholds) | `/webapp/d-04-costs/` + `scripts/operator/costs-api.py` (+ core `scripts/observability/cost-tracker.py`, CLI `sovereign-osctl costs`, service `sovereign-costs-api.service`) | **✓ shipped (full stack → prod)** | M060 R10075-R10082 |
| D-05 | traces (M049 13-field span search/filter + span tree + replay + OCSF detail panel) | `/webapp/d-05-traces/` + `scripts/operator/traces-api.py` (+ core `scripts/observability/trace-store.py`, CLI `sovereign-osctl traces`, service `sovereign-traces-api.service`) | **✓ shipped (full stack → prod)** | M060 R10083-R10087 |
| D-06 | pending approvals (operator queue + context + approve/deny/defer + batch-approve) | `/webapp/d-06-pending-approvals/` + `scripts/operator/approvals-api.py` (+ core `scripts/lifecycle/approval-queue.py`, CLI `sovereign-osctl approvals`, service `sovereign-approvals-api.service`) | **✓ shipped (full stack → prod)** | M060 R10088-R10092 |
| D-07 | memory changes (graph diff + promote/forget/pin + 7-dimension trust filters) | `/webapp/d-07-memory-changes/` (fetch-rewired) + `scripts/operator/memory-changes-api.py` (+ core `scripts/intelligence/memory-changes.py`, CLI `sovereign-osctl memory-changes`, service `sovereign-memory-changes-api.service`) | **✓ shipped (full stack → prod)** | M060 R10093-R10096 |
| D-08 | rollback points (ZFS snapshot list + commit history + dry-run + apply) | `/webapp/d-08-rollback-points/` (fetch-rewired) + `scripts/operator/rollback-api.py` (+ core `scripts/lifecycle/rollback-points.py`, CLI `sovereign-osctl rollback`, service `sovereign-rollback-api.service`) | **✓ shipped (full stack → prod)** | M060 R10097-R10101 |
| D-09 | hardware pressure (PSI gauges + DCGM gauges + backpressure indicators) | `/webapp/d-09-hardware-pressure/` + `scripts/operator/hardware-pressure-api.py` (+ core `scripts/hardware/hardware-pressure.py`, CLI `sovereign-osctl hardware-pressure`, service `sovereign-hardware-pressure-api.service`) | **✓ shipped (full stack → prod)** | M060 R10102-R10105 |
| D-10 | eval history (per-task pass/fail + per-model score + adapter-promotion candidates) | `/webapp/d-10-eval-history/` + `scripts/operator/evals-api.py` (+ core `scripts/observability/eval-tracker.py`, CLI `sovereign-osctl evals`, service `sovereign-evals-api.service`) | **✓ shipped (full stack → prod)** | M060 R10106-R10108 |
| D-11 | adapter status (LoRA inventory + promotion gates + audit trail + rollback) | `/webapp/d-11-adapter-status/` + `scripts/operator/adapters-api.py` (+ core `scripts/inference/adapter-foundry.py`, CLI `sovereign-osctl adapters`, service `sovereign-adapters-api.service`) | **✓ shipped (full stack → prod)** | M060 R10109-R10111 |
| D-12 | networking (Ring 0-4 traffic via MS007 mirror) | `/webapp/network-edge/index.html` + `/webapp/edge-firewall/index.html` | **✓ shipped (split)** | M060 R10112-R10113 |
| D-13 | filesystem grants (selfdef MS037 mirror) | `/webapp/d-13-filesystem-grants/` (fetch-rewired) + `scripts/operator/grants-mirror-api.py` (+ READ-ONLY mirror core `scripts/mirror/selfdef-grants-mirror.py`, CLI `sovereign-osctl grants-mirror`, service `sovereign-grants-mirror-api.service`) | **✓ shipped (full stack → prod, read-only selfdef mirror)** | M060 R10114-R10115 |
| D-14 | capability tokens (active capability_word grants) | `/webapp/d-14-capability-tokens/` (fetch-rewired) + `scripts/operator/capability-mirror-api.py` (+ READ-ONLY mirror core `scripts/mirror/selfdef-capability-mirror.py`, CLI `sovereign-osctl capability-mirror`, service `sovereign-capability-mirror-api.service`) — dedicated D-14 surface; the auth-tier dashboard remains the orthogonal tier view | **✓ shipped (full stack → prod, read-only selfdef MS035 mirror)** | M060 R10116-R10117 |
| D-15 | sandboxes (MS036 tier A/B/C/D allocation) | `/webapp/d-15-sandboxes/` (fetch-rewired) + `scripts/operator/sandbox-mirror-api.py` (+ READ-ONLY mirror core `scripts/mirror/selfdef-sandbox-mirror.py`, CLI `sovereign-osctl sandbox-mirror`, service `sovereign-sandbox-mirror-api.service`) | **✓ shipped (full stack → prod, read-only selfdef MS032/MS036 mirror)** | M060 R10118-R10119 |
| D-16 | audit cycles (MS009 results + replay validator) | `/webapp/auditor/index.html` | **✓ shipped** | M060 R10120 |
| D-17 | quarantine (MS042 tool-quarantine archive) | `/webapp/d-17-quarantine/` (fetch-rewired) + `scripts/operator/quarantine-mirror-api.py` (+ READ-ONLY mirror core `scripts/mirror/selfdef-quarantine-mirror.py`, CLI `sovereign-osctl quarantine-mirror`, service `sovereign-quarantine-mirror-api.service`) | **✓ shipped (full stack → prod, read-only selfdef MS042 mirror)** | M060 R10121-R10122 |
| D-18 | trust scores (per-tool trust score history) | `/webapp/d-18-trust-scores/` (fetch-rewired) + `scripts/operator/trust-mirror-api.py` (+ READ-ONLY mirror core `scripts/mirror/selfdef-trust-score-mirror.py`, CLI `sovereign-osctl trust-mirror`, service `sovereign-trust-mirror-api.service`) | **✓ shipped (full stack → prod, read-only selfdef MS042 mirror)** | M060 R10123 |
| D-19 | super-model manifest (version + module-version table) | `/webapp/d-19-super-model-manifest/` (fetch-rewired) + `scripts/operator/super-model-api.py` (+ native core `scripts/manifest/super-model-manifest.py` — live git version + M001..M080 catalog table, CLI `sovereign-osctl super-model`, service `sovereign-super-model-api.service`, editorial config `config/super-model-manifest.toml`); Trinity stays the orthogonal narrative/lineage view | **✓ shipped (full stack → prod)** | M060 R10124-R10125 |
| D-20 | peace machine health (5 properties live status) | `/webapp/d-20-peace-machine-health/` (fetch-rewired) + `scripts/operator/peace-machine-api.py` (+ native core `scripts/manifest/peace-machine.py` — 5 M059 properties + sovereign-os-peace-check verdict, CLI `sovereign-osctl peace-machine`, service `sovereign-peace-machine-api.service`); compliance stays the orthogonal §1g/§1h compliance view | **✓ shipped (full stack → prod)** | M060 R10126-R10128 |

**Coverage summary** (refreshed 2026-05-27 — full-stack §1g 8-surface delivery):
- **Shipped (full stack → prod)**: D-00, D-01, D-02, D-03, D-04, D-05, D-06, D-07, D-08, D-09, D-10, D-11, D-13, D-14, D-15, D-16, D-17, D-18, D-19, D-20 (20 dashboards)
- **Shipped (split)**: D-12 (network-edge + edge-firewall — networking surface split into two operator-validated dashboards by design) (1 dashboard)

## 🎉 CATALOG COMPLETE — all 21 M060 cockpit dashboards reach production

Every dashboard D-00..D-20 now ships its full §1g 8-surface stack (core + cli +
api + webapp + service + contract test). The 6 selfdef-domain surfaces (D-02 /
D-13 / D-14 / D-15 / D-17 / D-18) are cross-repo READ-ONLY mirrors that never
mutate IPS state (`scripts/mirror/selfdef-*-mirror.py`); the 2 meta surfaces
(D-19 super-model manifest, D-20 peace-machine health) compute live from the
repo/validator; the rest are sovereign-os-native runtime/observability. D-12 is
intentionally split across two dashboards. No backend remains stubbed or mocked.
- **Backend API pending**: NONE. Every one of the 21 M060 cockpit dashboards now has a working backend + webapp. The 6 selfdef-domain surfaces (D-02 profiles + D-13/D-14/D-15/D-17/D-18) ship as cross-repo READ-ONLY mirrors (`scripts/mirror/selfdef-*-mirror.py`, never mutate IPS state), correctly placed per the operator project-boundary directive. Remaining work is the Phase E **partial-completions** of D-19 (super-model manifest table on trinity) + D-20 (5-property peace-machine live view on compliance) — extensions of surfaces that already ship — plus D-12 (already split across network-edge + edge-firewall).

> Core-reuse clusters (one source-of-truth, multiple dashboards, zero schema drift):
> - **observability** — `scripts/observability/trace-store.py` reads the M049 span log; `cost-tracker.py` (D-04) + `eval-tracker.py` (D-10) reuse its loaders / patterns.
> - **inference/model** — `scripts/inference/model-health.py` (D-03) is the catalog parser; `adapter-foundry.py` (D-11) reuses it; `eval-tracker.py` (D-10) reuses adapter-foundry for promotion candidates. Chain: model-health ← adapter-foundry ← eval-tracker.

> Delivery doctrine (D-03/D-09 proved): a dashboard "reaches prod" only when ALL of {core, cli, api, webapp, service} ship + a contract test locks the live fetch shape + the master-dashboard aggregator route is registered. A webapp HTML file alone is a scaffold, not prod. Status tracked here (the M060 bridge) + commit history; we do not maintain a competing status board.

**Existing webapp dashboards NOT in M060 catalog** (orthogonal surfaces, retained):
- `/webapp/anti-minimization-audit/` — audits operator's "do not minimize" doctrine
- `/webapp/doc-coverage/` — docs surface
- `/webapp/global-history/` — cross-cutting history view
- `/webapp/router/` — routing inspector
- `/webapp/surface-map/` — surface inventory
- `/webapp/ux-design-audit/` — UX consistency audit
- `/webapp/weaver/` — Trinity Weaver visualization

These pre-date M060 and serve operator-facing surfaces beyond the 21-dashboard catalog. They remain shipped; M060 does not deprecate them.

## Implementation ordering (operator-priority)

Phase A (high operator-UX value, low cross-dependency):
1. **D-02 profile choices** — six-profile selector + envelope visualization. Operator names profiles in /goal explicitly. Implementing NOW alongside this SDD.
2. **D-06 pending approvals** — operator queue. Critical for "operator-controlled" axiom (M065 Stage Gates).
3. **D-01 active sessions** — M057 lifecycle view. Operator visibility into running work.

Phase B (observability + cost):
4. **D-05 traces** — M049 13-field span surface. Required for all post-shipping debugging.
5. **D-04 costs** — daily budget surface. Required for "fast/careful/private profile cost-awareness" per MS040.
6. **D-09 hardware pressure** — PSI + DCGM gauges. Required for M058 scheduler visibility.

Phase C (model + memory ops):
7. **D-03 model health** — Blackwell + 3090 + CPU + VRAM + KV cache.
8. **D-10 eval history** — adapter-promotion candidate surface for M046 LoRA Foundry.
9. **D-11 adapter status** — LoRA inventory + promotion gates + rollback.
10. **D-07 memory changes** — memory graph diff + promote/forget/pin.

Phase D (selfdef-mirror dashboards):
11. **D-13 filesystem grants** — selfdef MS037 mirror via MS007.
12. **D-15 sandboxes** — selfdef MS036 tier allocation visualization.
13. **D-17 quarantine** — selfdef MS042 tool-quarantine archive viewer.
14. **D-18 trust scores** — selfdef MS042 per-tool trust history.

Phase E (close-out + partial-completion):
15. **D-08 rollback points** — ZFS snapshot list (M068).
16. **D-14 capability tokens completion** — extend existing auth-tier with capability_word grant list.
17. **D-19 super-model manifest completion** — add module-version table to existing trinity dashboard.
18. **D-20 peace machine health completion** — add 5-property live status to existing compliance dashboard.

15 missing dashboards + 4 completions = **19 implementation work items**, each a single-file webapp page following the established UX doctrine.

## Decisions locked here

- D-040.1 — UX doctrine preserved from existing webapp; no framework introduction.
- D-040.2 — Each dashboard = single-file (`/webapp/<dashboard-id>/index.html`).
- D-040.3 — Meta tags `x-sovereign-module` + `x-sovereign-shipped-in` + `x-sovereign-standing-rule` mandatory.
- D-040.4 — Color palette + component vocabulary canonical (this SDD).
- D-040.5 — Operator-disable-able per M060 R10129 — **✓ SHIPPED**: `scripts/manifest/dashboard-toggles.py` is the toggle core (catalog = real `webapp/*/` dirs; state in `/etc/sovereign-os/dashboards.toml` per R10130, default-enabled; `set_enabled` is the operator CLI path per R10131 and emits an M049 trace + OCSF 5001 Configuration Change into the D-05 span log per R10132). Surfaced via `sovereign-osctl dashboards {list,status,enable,disable}` + `master-dashboard.py toggles`. (Per-daemon render-time refusal is a thin follow-up — the toggle mechanism + state + trace + operator CLI are complete and operator-usable now.)
- D-040.6 — D-12..D-18 dashboards READ-ONLY mirror of selfdef state per M060 R10112-R10123; mutation proxies via MS003-signed request per MS043 R10274.
- D-040.7 — Implementation order Phase A → E as enumerated above; operator may reorder per /goal direction.
- D-040.8 — Cross-repo binding: selfdef-mirror dashboards (D-12..D-18) consume MS007 typed mirror crates only.

## Open questions (Q-040)

- **Q-040.1** — Should partial-completion dashboards (D-14, D-19, D-20) be split into separate pages OR extended in place? Recommendation: extend in place (operator already familiar with the existing URL).
- **Q-040.2** — Live data source: WebSocket per dashboard, OR SSE single-stream multiplexed, OR polling? Recommendation: SSE single-stream per M060 minimal-web pattern (selfdef MS043 R10173 already chose SSE for minimal-web).
- **Q-040.3** — Should dashboard URLs map to keyboard shortcuts Cmd-0..Cmd-9 per M060 R10055-R10105? Recommendation: yes — already partially in M060 catalog, just needs implementation.

## Closing

This SDD does NOT add new catalog requirements (M060 covers them). It MATERIALIZES the catalog into ordered implementation work that respects the operator's "you cannot invent crap" + "do not minimize" directives. Phase A item 1 (D-02 profile choices) lands alongside this commit.

Sources:
- `backlog/milestones/M060-cockpit-and-dashboards-ux-surface.md`
- `/webapp/master-dashboard/index.html` (UX doctrine reference)
- `/webapp/auditor/index.html` (UX doctrine reference)
- Operator standing /goal direction 2026-05-19 (UX dashboards + toggleable)
