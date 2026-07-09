# SDD-063 — D-12 networking read model (the selfdef rules-mirror consumer: wire /api/d-12/snapshot to real state)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-09
> Closes findings: none (the unwired D-12 networking producer — the panel is static/demo seed data)
> Derived from: operator directive 2026-07-09 (chose the D-12 networking read-model wiring after SDD-062's functional chat merged in PR #40; confirmed the target = wire the standalone d-12-networking rules-mirror panel, the D-13 grants-mirror pattern); M060 D-12; MS007 typed-mirror crates; R10113 + R10212.

## Mission

Make the **D-12 networking panel show real state** instead of inline `seed` mock
data — by wiring its referenced `/api/d-12/snapshot` endpoint to a **read-only
selfdef rules-mirror consumer**, exactly mirroring the D-13 grants-mirror pattern.

## Problem

- `webapp/d-12-networking/index.html` renders from an inline `const seed` (nftables
  Ring-0-4 traffic + summaries + rules + denied-egress) — a `RulesMirrorSnapshot
  1.0.0` shape. Its banner says *"data source: mock … no `/api/d-12/snapshot`
  publisher wired yet … Live producer is the next D-12 increment."* Nothing fetches
  `/api/d-12/snapshot`; there is no core/daemon producing it.
- The D-12 view is a **selfdef/firewall MIRROR** (Ring-0-4 zero-trust nftables), NOT
  interfaces/routes (that's the separate, already-shipped network-edge stack). Per
  R10113 + R10212 the nftables ruleset is **selfdef-owned**; sovereign-os observes it
  **read-only** (rules change only via `selfdefctl` + MS003 on the IPS side).

## Grounded design — reuse the existing canonical core + align the webapp

**Discovery (2026-07-09):** `scripts/mirror/selfdef-rules-mirror.py` **already exists +
is canonical and tested** (the M060 mirror suite — mcp-aggregate, m060-smoke, the osctl
`rules-mirror` arm, the m060 cross-repo/mirror contracts). It reads the selfdef mirror
(`SOVEREIGN_OS_SELFDEF_RULES_MIRROR`, default `/run/sovereign-os/selfdef-mirror/rules.json`)
and `snapshot()` projects the CANONICAL schema: named MS039 rings (`sovereign_kernel /
trusted_local / sandboxed / experimental / cloud_external`, R10246-R10250) + nft
`dispositions` (accept/drop/reject/jump/continue/return) + `summaries[{ring,rule_count,
total_bytes,total_packets,pending_l3}]` + `rules[{handle,rule_id,ring,table,chain,
match_expr,disposition,priority,packets,bytes,installed_at,installed_by,signature}]` +
`mirror_status(online/offline)`. Absent artifact → `offline` + empty (SB-077).

BUT it has **no API daemon** (never served to any webapp), and the d-12-networking webapp
renders a DIVERGENT inline `seed` (numeric `ring0-4`, `allow/deny` verdicts, `ringTraffic`
bars, `denied`-egress, `fqdn/cidr` counts). Operator decision (2026-07-09): **reuse the
canonical core + build the API daemon + align the webapp to the canonical schema** (do
NOT fork the tested core's shape).

So this increment does NOT author the core (it exists). It:
- **reuses** `scripts/mirror/selfdef-rules-mirror.py` (canonical, unchanged);
- **builds** the API daemon + **aligns** the d-12 webapp render to the canonical schema
  (named rings, dispositions, per-ring `summaries` rows, the canonical `rules` fields —
  dropping the divergent ringTraffic/denied/fqdn/cidr seed shape).

### `scripts/operator/rules-mirror-api.py` — the read-only daemon (port 8133)

- importlib-loads the core; serves `GET /api/d-12/snapshot` → `_core.snapshot()`,
  `GET /api/d-12/stream` (SSE poll-push for live refresh), `/version`, `/healthz`,
  `/webapp/`, `/control-systems`. **405 on all POST/PUT/DELETE** (read-only — R10212).
- systemd unit `sovereign-rules-mirror-api.service` (loopback 127.0.0.1:8133 + R171
  hardening), mirroring `sovereign-grants-mirror-api.service`.

### Wiring

- `sovereign-osctl rules-mirror {snapshot,summaries}` → the core (read-only).
- `config/dashboard-catalog.yaml` d-12 `api:` → `sovereign-rules-mirror-api`;
  `scripts/operator/master-dashboard.py` gains the d-12 port route (8133) + webapp map.
- `webapp/d-12-networking/index.html`: fetch `/api/d-12/snapshot` + refactor the
  render into functions consuming the snapshot; the inline `seed` stays as the
  offline fallback; the banner flips mock → online/offline from `mirror_status`; the
  `emit()` clipboard `selfdefctl` actions stay (R10212 — rules mutate on the IPS side
  only). Optional SSE refresh via `/api/d-12/stream`.

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-063-A | D-12 target (rules-mirror vs VLAN/interfaces vs network-edge split). | **answered (operator, 2026-07-09): wire the standalone d-12-networking rules-mirror panel — the D-13 grants-mirror pattern.** |
| Q-063-B | Read-only vs any mutation. | **answered: read-only mirror consumer; sovereign-os NEVER runs nft; rules mutate only via selfdefctl + MS003 (R10113/R10212). 405 on POST.** |
| Q-063-C | Mirror artifact path. | **proposed: `/run/sovereign-os/selfdef-mirror/rules.json` (parallel to grants' `grants.json`); env-overridable.** |
| Q-063-D | SSE live refresh. | **proposed: add `/api/d-12/stream` (poll-push, like hardware-pressure) so the panel refreshes; the webapp keeps a same-origin fetch fallback.** |
| Q-063-E | The selfdef-side rules-mirror crate publishing the artifact. | **proposed: cross-repo selfdef work (Stage N); the consumer degrades to offline until it publishes (SB-077).** |

## Goals

- A tested, read-only rules-mirror core + daemon that wires the D-12 panel to real
  selfdef state, degrading honestly to offline when the mirror isn't published.
- Exact reuse of the D-13 grants-mirror template (core/api/systemd/osctl/contract).

## Non-goals (Stage N)

- The selfdef-side rules-mirror publisher crate (cross-repo).
- Any nft mutation from sovereign-os (forbidden — R10113/R10212).
- Consolidating d-12 with the network-edge / edge-firewall panels (the surface-map's
  D-12a/D-12b split) — a separate restructuring decision.

## Way forward

- **Stage 0 (this commit):** this SDD + INDEX + mandate E11.M30. The canonical core
  already exists (M060 mirror suite) — reused, not re-authored.
- **Stage 1 (the wiring):** `scripts/operator/rules-mirror-api.py` (serves the canonical
  core at `/api/d-12/snapshot` + `/stream`) + `sovereign-rules-mirror-api.service` +
  catalog/master-dashboard registration + `tests/lint/test_rules_mirror_api_contract.py`.
  (osctl `rules-mirror` already routes to the core — unchanged.)
- **Stage 2 (align the webapp):** rewrite `webapp/d-12-networking/index.html` render to the
  canonical schema (named rings / dispositions / per-ring summaries / canonical rule
  fields), fetch `/api/d-12/snapshot`, banner mock→online/offline, `emit()` clipboard
  `selfdefctl` actions stay.
- **Stage N:** the selfdef-side publisher crate.

## Safety invariants

Read-only mirror consumer (405 on all POST/PUT/DELETE); sovereign-os NEVER runs nft or
mutates IPS state (rules change via selfdefctl + MS003 only — R10113/R10212); the core
degrades to `offline` + empty when the artifact is absent (SB-077 — never fabricates
rules); stdlib-only; loopback-bound daemon + R171 hardening; the d-12 `emit()` actions
stay clipboard-copy of `selfdefctl` verbs (never web mutations); selfdef/perimeter
untouched; the mirror artifact path is free of any sovereign-os write (read-only).

## Cross-references

- `scripts/mirror/selfdef-grants-mirror.py` (D-13) — the read-core template.
- `scripts/operator/grants-mirror-api.py` + `sovereign-grants-mirror-api.service` — the
  daemon + unit template.
- `tests/lint/test_grants_mirror_api_contract.py` — the contract template.
- `webapp/d-12-networking/index.html` — the panel (its `RulesMirrorSnapshot` render code).
- M060 D-12, MS007 typed-mirror crates, R10113 (IPS read-only) + R10212 (web never mutates).
