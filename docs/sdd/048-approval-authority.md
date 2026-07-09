# SDD-048 — Approval authority (functional approve/deny/defer for D-06)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-08
> Closes findings: none (write-path atop the D-06 read model + SDD-047 control surface)
> Derived from: operator directive 2026-07-08 (chose "Approval authority (d-06)" as the next greenfield engine after SDD-047's feasible controls merged); SDD-047 (cockpit functional execution / R10274 control-exec-api); SDD-045 (control surface); M065 stage-gate spec (`config/agent/m065-stage-gates.yaml`); SDD-015 (MS003 / MOK signing, a selfdef-consumed service).

## Mission

Make the D-06 pending-approvals panel's **approve / deny / defer** actions
**functional** as a sanctioned cockpit control — the operator decides on a queued
approval from the dashboard, the decision transitions the M065 stage-gate state,
and the outcome is durably audited. Today those buttons are neutralized
("planned") because no write path exists.

This realizes the write half of an already-built read surface, on the SDD-047
R10274 rail (the dedicated `control-exec-api` write daemon), preserving **R10212**:
the web still never *arbitrarily* mutates — it executes only an allowlisted,
options-validated, operator-key-present, type-to-confirm, audited, DRY-RUN-default
verb.

## Problem

The **read path is fully built**; the **write path is entirely greenfield**:

1. **No producer.** Nothing writes `/run/sovereign-os/approvals.json`
   (`SOVEREIGN_OS_APPROVALS`). `approval-queue.py` is a pure reader that degrades
   to an empty queue when the file is absent. `cloud_requires_approval` is a static
   flag with no enqueuer; the M065 stage-gate coordinators are spec-only.
2. **No decision-writer.** `approval-queue.py` has verbs `pending` / `gates` /
   `key` only — all read-only. There is no `approve` / `deny` / `defer` function or
   verb; `webapp/d-06-pending-approvals/index.html:624-637` says so explicitly.
3. **No MS003 signing.** Only operator-key *presence* checks exist
   (`approval-queue.py operator_key_status`, `_action_exec.operator_key_loaded`).
   The M065 spec delegates decision signing to **selfdef** as a *consumed
   chain-of-trust service* — building signing crypto inside sovereign-os would
   breach R10212.
4. **The `/run` queue is ephemeral** (tmpfs) — a decision recorded only there does
   not survive reboot; it needs a durable ledger + the OCSF audit chain.

## Required coverage

### The approvals.json write contract (extends the read schema)

Per-record (existing read fields: `id, title, severity, gate, actor, kind,
profile, ts, trace_id, summary, context, diff_url`) gains:

| Field | Values | Meaning |
|---|---|---|
| `status` | `pending` \| `signed` \| `denied` \| `deferred` | decision outcome (default `pending`) |
| `defer_until` | ISO ts, optional | when a deferred item re-surfaces |
| `decided_by` | actor, optional | who decided |
| `decided_ts` | ISO ts, optional | when |
| `signature` | `"unsigned-pending-MS003"` (first cut) | provenance; real MS003 sig is Stage 4 |

Top-level `gates{SG1..SG5 → pending|signed|bypassed}` transitions on an approve
whose `gate` names an SGn.

### Decision semantics (fills the M065 gap — deny/defer were unspec'd)

- **approve** → record `status: signed`; if `record.gate` names an SGn,
  `gates[SGn] → signed`; drop from the active pending view; write the decision.
- **deny** → record `status: denied`; the gate stays `pending` (NOT signed); drop
  from pending; record with an optional `--rationale`.
- **defer** → keep the record in queue; set `defer_until` (default now+24h or
  `--until`); `status: deferred`; the item stays visible with a **deferred badge**
  (nothing silently disappears — §1g "we do not minimize").

### Ids, ledger, audit

- **id format** `APR-<8hex>` — `_action_exec._SAFE_VALUE`-clean (no `/`, which the
  exec allowlist forbids). The decision-writer also accepts `latest`
  (highest-severity, then oldest `ts`) as a rollback-apply-style convenience.
- **durable ledger** — append-only `/var/log/sovereign-os/approval-decisions.jsonl`
  (the eval-history precedent), because `/run` is ephemeral.
- **OCSF-5001 audit** — reuse the `_action_exec._emit_audit` 13-field M049 span
  shape (`operation: "approval_decision"`, `ocsf_class 5001`) into
  `SOVEREIGN_OS_SPAN_STORE`, so every decision auto-surfaces in the **D-05 traces**
  and **D-16 audit** dashboards via `trace-store.py`. Matches M065 E0635/E0636
  ("emit OCSF Configuration-Change class 5001 + an M049 trace").

## Goals

- A functional, **honestly-unsigned**, fully-audited approve/deny/defer loop wired
  to D-06 through the sanctioned R10274 `control-exec-api` path.
- Zero new doctrine: reuse `execute()`'s privileged + operator-key-presence +
  type-to-confirm + DRY-RUN-default gate; reuse `_emit_audit`; keep the read core
  (`approval-queue.py`) pristine (writers in a new sibling `approval-decide.py`).
- A minimal CLI **producer** (`approvals request`) so the loop is operable + testable
  end-to-end.
- R10212 preserved: selfdef/perimeter untouched; `approvals-api.py` stays read-only
  (405); the only web write path is `control-exec-api → execute()`.

## Non-goals (Stage 4 / follow-up Epic)

- **Real MS003 signature** creation/verification (the selfdef chain-of-trust
  transport). First cut writes `signature: "unsigned-pending-MS003"`.
- **Real producers** — cloud-spend gate (`cloud_requires_approval` → enqueue),
  stage-gate coordinators. First cut ships only the CLI `approvals request`
  stand-in.
- Any change to the selfdef producer or the R10212 boundary.

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-048-A | How is the decision signed given sovereign-os has no signing crypto? | **answered (operator, 2026-07-08): presence-gated + audited; `signature: "unsigned-pending-MS003"`; real selfdef MS003 signing deferred to Stage 4.** |
| Q-048-B | How much producer to build now? | **answered (operator, 2026-07-08): a minimal CLI `approvals request` stand-in only; real producers are Stage 4.** |
| Q-048-C | Spec-first cadence — SDD alone or SDD + engine? | **answered (operator, 2026-07-08): SDD as the lead commit + the engine (Stages 1-3) in the same PR.** |
| Q-048-D | Should a deferred item be hidden until `defer_until`, or shown with a badge? | **proposed: shown with a deferred badge (nothing silently disappears). Operator may revise.** |
| Q-048-E | What is the canonical approval `id` format the real (Stage-4) producers will mint? | **proposed: `APR-<8hex>` (`_SAFE_VALUE`-clean). Confirm before Stage-4 producer work.** |

## Way forward

- **Stage 0 (this commit):** this SDD.
- **Stage 1:** `scripts/lifecycle/approval-decide.py` — the decision-writer
  (`decide(id, verb, …)`): validate, resolve (exact id / `latest`), transition
  record `status` + `gates[SGn]`, atomic single-flight write to the `/run` queue,
  append to the durable JSONL, emit the OCSF-5001 span, honor `SOVEREIGN_OS_DRY_RUN`.
  Imports the shared schema from `approval-queue.py`.
- **Stage 2:** `approvals request` (same module) — the minimal CLI producer minting
  `APR-<8hex>` records. Non-privileged. (Web-exposed via the R10274 exec-rail as the
  `approvals-request` control as of **SDD-104** — was: "not a control"; the enqueue is an
  unprivileged intent, distinct from the privileged `approvals-decide` that signs it.)
- **Stage 3:** the 18th control `approvals-decide`
  (`sovereign-osctl approvals {approve|deny|defer} <id> --confirm`, privileged,
  `applies_to: [d-06-pending-approvals]`) + sudoers + lint bumps + the
  `approvals)` dispatch subverb case + re-wire D-06's `handleAction` to POST the
  control-exec-api + a `test_approval_decide.py` unit suite.
- **Stage 4 (follow-up Epic):** real producers + real selfdef MS003 signing.

## Cross-references

- `config/agent/m065-stage-gates.yaml` — SG1-SG5 gate contract (E0633-E0636).
- `scripts/lifecycle/approval-queue.py` — the read core (schema source of truth).
- `scripts/operator/_action_exec.py` — `execute()` gate + `operator_key_loaded` +
  `_emit_audit` (reused; `state_path` must not name selfdef/tetragon).
- `scripts/operator/control-exec-api.py` — the R10274 write daemon.
- `config/control-systems.yaml` — the 17 controls (model #18 on `rollback-apply`).
- SDD-047 (cockpit functional execution), SDD-045 (control surface), SDD-015 (MS003).
