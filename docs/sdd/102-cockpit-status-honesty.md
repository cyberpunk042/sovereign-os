# SDD-102 — cockpit status honesty (promote D-05 Traces to live; confirm D-04 Costs correctly-$0)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-09
> Closes findings: the stale `d-05-traces` catalog `status: snapshot` label (drift — the traces daemon is live); records the SB-077 finding that D-04 Costs is correctly-$0 for local inference and must NOT get a fabricating producer
> Derived from: operator goal "make the dashboards functional and god-tier"; a cockpit-panel survey (2026-07-09) + empirical grounding that corrected two of the survey's stub assessments. Recover-projects band (SDD-102 / E11.M102).

## Mission

A truthful accounting of which cockpit panels are functional, correcting one stale label and
one mis-assessment surfaced while looking for the next "make it functional" increment. The
net finding: **the hardware-free "make a stubbed panel functional" thread is complete** — the
remaining stubs are hardware-blocked or cross-repo, not wireable-now.

## Problem

Hunting the next panel to wire end-to-end (after this session wired D-07 Memory + D-01/D-08
sessions/rollback), a survey flagged D-05 Traces and D-04 Costs as "stubbed." Empirical
grounding **disproved both** as build targets:

- **D-05 Traces** — the catalog labels it `status: snapshot`, but per the catalog's own legend
  (`live` = backed by a running `sovereign-*-api`; `snapshot` = baked/localStorage-only) it is
  **live**: `scripts/operator/traces-api.py` (`sovereign-traces-api.service`, loopback,
  R171-hardened, auto-start) serves real spans from the M049 span log via `trace-store.py`;
  `tests/lint/test_traces_api_contract.py` already locks the 13-field schema + per-trace
  assembly + daemon/systemd; the webapp fetches `/api/traces/*` with an online/offline banner.
  The `snapshot` label is **stale drift** — set before the daemon was wired, and now
  especially wrong since this session's 8 governance producers (memory admit/advance/forget +
  decision, adapter gate, approval/session decisions) continuously feed its store.

- **D-04 Costs** — already `status: live`; renders **$0**. This is **correct, not a stub**:
  sovereign-os inference is **loopback-local** (`prompt.py` → 127.0.0.1:8080) and therefore
  **free**; the cost policy (`cost-tracker.load_policy`, `POLICY_DEFAULTS`) is about
  cloud-enablement + budgets (`cloud_enabled: False` by default), carrying **no per-token
  rate**. `cost-tracker.py` sums the per-span `attributes.cost` and shows "$0 / no activity"
  on an empty store. A "cost producer" that emitted `tokens × invented-rate` would
  **fabricate spend that does not exist** — a direct **SB-077 violation** ("you cannot invent
  crap"). Real cost accrues only from a **cloud fallback** (disabled by default); a
  cloud-cost producer is a separate, genuinely-honest Stage-N item **only if/when the operator
  enables cloud**.

## Grounded design

- **Promote `config/dashboard-catalog.yaml` `d-05-traces` `status: snapshot → live`.** A pure
  correctness fix — the panel meets the `live` definition (running api serving real data).
  `personalization` remains the only `snapshot` (correct — localStorage-only, no daemon).
- **No D-04 change** — it is already `live` and honestly $0; explicitly record that a
  fabricating cost producer must NOT be built (SB-077); a cloud-cost producer is Stage-N,
  gated on the operator enabling cloud.
- **No code, no contract, no runtime change** — a catalog label + this record.

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-102-A | D-05 status. | **answered: `live` — it has a running `sovereign-traces-api` daemon serving real spans (the `snapshot` label was stale drift).** |
| Q-102-B | D-04 cost producer. | **answered: do NOT build one — local loopback inference is free; a tokens×rate span would fabricate spend (SB-077). D-04's $0 is honest.** |
| Q-102-C | Cloud-cost producer. | **proposed: Stage-N, gated on the operator enabling cloud (`cloud_enabled: true`) — only then is there real spend to attribute.** |

## Non-goals (Stage N)

- A local-inference cost producer (would fabricate — forbidden).
- A cloud-cost producer (only meaningful once `cloud_enabled` + a cloud backend is used).
- Wiring the hardware-blocked panels (D-03/D-10/D-11/D-20/D-22 — need a running model/GPU) or
  the cross-repo selfdef mirrors (D-12–D-18 — need `$SELFDEF_REPO_ROOT`).

## Way forward

- **This commit:** this SDD + INDEX row 102 + mandate E11.M102; the D-05 catalog promotion.
- **Next (operator-steered):** the hardware-free make-functional thread being complete, the
  next substantial direction is one of — a hardware-blocked panel's producer (honest-defer
  until hardware, e.g. M046 adapter training / eval harness), a depth feature on a working
  panel (D-22 multi-turn chat), the conflict-avoidance Stage-N (union/fragment the `.py` lint
  lists), or a fresh operator-named thrust.

## Safety invariants

Catalog-label + documentation only — no code, no contract, no runtime/lifecycle/security
change. The D-05 promotion is truthful (the panel meets the `live` definition). The core
principle recorded here is **SB-077**: D-04's $0 is real (local = free); never fabricate a
cost. MS003 `unsigned-pending-MS003`.

## Cross-references

- `config/dashboard-catalog.yaml` (the status legend + the d-05/d-04 entries) +
  `tests/lint/test_dashboard_catalog_complete.py` (the catalog lint).
- `scripts/observability/cost-tracker.py` (`load_policy` / `_span_cost` — the honest $0 core).
- `scripts/operator/traces-api.py` + `tests/lint/test_traces_api_contract.py` (D-05 live proof).
- `scripts/inference/prompt.py` (loopback-local inference — the free-by-design source).
