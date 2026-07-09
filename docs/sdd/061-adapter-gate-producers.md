# SDD-061 — M046 adapter gate-producers (advance the MS041 triple-gate from real evidence; make D-11 promote functional end-to-end)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-09
> Closes findings: none (SDD-051 Stage 4 — the deferred real gate-producers, Q-051-E)
> Derived from: operator directive 2026-07-09 (chose the M046 adapter gate-producers after SDD-060's memory list-view/purge merged in PR #38); SDD-051 (adapter promotion authority — the promote/demote/rollback consumer + the MS041 gate check; gate-producers were deferred); M056 Commit Authority (the MS041 triple-gate, R09697-R09711); M046 LoRA Foundry; R10212.

## Mission

Build the **gate-producers** that advance an adapter's MS041 gates so `adapter-decide
promote` becomes reachable and the D-11 readiness pill goes green — advancing gates
**only from real evidence** (SB-077: never fabricate a pass).

## Problem

- `adapter-decide.register()` mints an adapter with all four gates `"pending"`; `decide()`
  transitions `status` but **never touches `gates`**. So **no producer sets any gate to
  `"passed"`** — the MS041 triple-gate (`snapshot` + `test_eval` + (`oracle` OR `human`))
  can never be satisfied except by a manual registry edit, and `promote` is unreachable.
- The D-11 readiness pill is stuck at "not yet"; D-20 reports "M046 LoRA Foundry promote
  pipeline: partial (eval harness deferred)".
- Grounded reality: the eval harness (`models eval run`) is DRY-RUN-until-hardware and the
  oracle vLLM backend (:8083) needs hardware, so **eval-run + oracle honest-defer today**.
  The producible-today path to a real promote is **snapshot** (a real ZFS rollback-point) +
  **test_eval** (read a real passing eval record) + **human** (operator sign-off — the
  oracle-OR-human third gate).

## Required coverage

### The gate-producer (`scripts/inference/adapter-gate.py`)

A NEW module separate from `adapter-decide.py` (the promote/demote/rollback *consumer*),
mirroring the memory-store↔memory-decide split. Imports the `adapter-foundry.py` reader
for `ADAPTER_REGISTRY` / `list_adapters` / `_read_json`; carries its own `_atomic_write` /
`_emit_span` / `_SAFE_ID` / `_now` (mirrors adapter-decide). `_advance_gate(adapter_id,
gate, *, evidence, confirm, actor)` sets `gates[gate]="passed"` + records provenance in a
parallel `gate_evidence[gate]` sub-record + atomic-writes the registry + appends the ledger
+ an OCSF-5001 span. DRY-RUN default. The existing `gates.<gate>="passed"` string contract
is untouched, so `_gate_unmet`, the reader's `oracle_or_human` merge, and the D-11 pill all
keep working.

The four verbs — each SB-077-safe (its evidence-gatherer returns `{ok, evidence}` or
`{ok:False, reason}`; on `ok:False` the gate STAYS pending and the verb honest-defers with
a CLI remediation, NEVER setting `"passed"` without proof):

- **`gate human <id> --confirm [--rationale]`** — the `--confirm` IS the operator's
  attestation → evidence `{attested_by:actor, rationale}`. Always producible. This is the
  new cockpit control (below).
- **`gate snapshot <id> --confirm [--dataset models]`** — importlib-call
  `rollback-points.create(dataset_key, tag, confirm)` (reuse SDD-050; `tag = gate-<tag-safe
  (id)>` sanitized to `_SAFE_TAG`). Live `ok` → evidence `{target:"<dataset>@<tag>"}`;
  dry/zfs-absent → honest-defer.
- **`gate eval <id> --confirm`** — import the `eval-tracker` reader; `load_runs()` filtered
  to `adapter_id==id`; latest record with `_passed()` → evidence `{score, trace_id, ts}`;
  none → honest-defer ("no passing eval on record — run `sovereign-osctl models eval run
  <id>` first").
- **`gate oracle <id> --confirm`** — probe the oracle backend (`SOVEREIGN_OS_ORACLE_URL`,
  default `http://127.0.0.1:8083`, short timeout); unreachable → honest-defer ("oracle
  backend unreachable — start-oracle-core"); reachable → minimal judge request + verdict
  parse. Isolated `_oracle_evidence()` for testability. (Honest-defers today — backend
  hardware-gated.)

### The one new control (`adapter-gate-human`)

Only the human gate is a cockpit control — the operator signs off from D-11 via the R10274
exec rail (operator-key + type-to-confirm + DRY-RUN default). `change_cli: "sovereign-osctl
adapters gate human <id> --confirm"`, privileged, `applies_to: [d-11-adapter-status]`.
Registry 30→31, local 28→29. eval/snapshot/oracle stay CLI-only non-privileged producers
(heavy / host-gated — mirror `register()`'s "NOT a control, NOT web-exposed").

### End-to-end (the pill-green path)

`register` → `gate snapshot` (real rollback-point) + `gate eval` (real passing record) +
`gate human` (operator sign-off) → `_gate_unmet()` empty → `adapter-decide promote`
succeeds → D-11 pill green. Oracle joins the OR-branch when hardware lands.

## Goals

- Real, testable gate-producers that advance the MS041 gates from evidence, never
  fabricating a pass; a real promote reachable today via snapshot + eval-record + human.
- Reuse the SDD-050 `rollback-points.create` + the D-10 `eval-tracker` reader + the
  adapter-decide writer patterns; keep `adapter-foundry.py` pure + `adapters-api.py` 405.
- The human sign-off as a functional D-11 cockpit control (the standing `/goal`).

## Non-goals (Stage N / follow-up)

- The M046 **training pipeline** (`train` — heavy LoRA Foundry job, SDD-051 Stage 3).
- The **real oracle judge-prompt tuning** (this ships the probe + a minimal judge; the
  full judge is hardware-gated + iterative).
- A **snapshot/eval scheduler** or auto-gate-advance on training completion.
- **MS003 signing** (stays delegated to selfdef — `unsigned-pending-MS003`).

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-061-A | Gate-producer scope. | **answered (operator, 2026-07-09): the full honest 4-gate set (human + snapshot + eval + oracle), each advancing from real evidence + honest-deferring when the harness/backend is absent.** |
| Q-061-B | Human-gate surface. | **answered (operator, 2026-07-09): a new cockpit control `adapter-gate-human` (operator signs off from D-11 via the exec rail); eval/snapshot/oracle stay CLI-only.** |
| Q-061-C | Eval evidence source. | **answered (operator, 2026-07-09): read a real passing record from `evals.jsonl` (the Eval-Value fabric log the D-10 tracker consumes) — do NOT run the heavy benchmark inline.** |
| Q-061-D | Oracle judge. | **proposed: probe the backend + issue a minimal judge when reachable; honest-defer when unreachable. Full judge-prompt tuning is a hardware-gated follow-up.** |
| Q-061-E | Snapshot-gate dataset default. | **proposed: `models` (tank/models — where adapters live); operator may extend the `_DATASETS` enum.** |

## Way forward

- **Stage 0 (this commit):** this SDD + INDEX + mandate E11.M28; flip SDD-051 Q-051-E.
- **Stage 1:** `scripts/inference/adapter-gate.py` (the 4 gate-producers) +
  `tests/unit/test_adapter_gate.py` (incl. the end-to-end register→3-gate→promote proof).
- **Stage 2:** the `adapter-gate-human` control + the `adapters gate)` osctl routing +
  sudoers + lint bumps (30→31) + the d-11 sign-off button + the d-20 check-row update.
- **Stage N (follow-up):** the training pipeline; the full oracle judge; a gate scheduler.

## Safety invariants

Never fabricate a gate pass (SB-077 — real evidence or honest-defer); gate-producers are
CLI-only + DRY-RUN default (only `adapter-gate-human` is a control, exec-rail gated:
operator-key + type-to-confirm); `adapter-foundry.py` stays a pure reader +
`adapters-api.py` stays read-only (405 — NO new API mutation path); `adapter-decide.py`
untouched (the sole gate *consumer*); ids `_SAFE_ID`-validated + snapshot tags `_SAFE_TAG`;
atomic registry write + append-only ledger + OCSF-5001 span; registry gate state under
`/var/lib/sovereign-os/adapters/` + evidence logs under `/var/log/sovereign-os/` — all free
of selfdef/tetragon; selfdef/perimeter untouched; MS003 `unsigned-pending-MS003` (never
build signing crypto here); registry 30→31 (one new control — the human gate only).

## Cross-references

- `scripts/inference/adapter-decide.py` (SDD-051) — the gate CONSUMER (`_gate_unmet`,
  promote refuse-by-default); untouched by this SDD.
- `scripts/inference/adapter-foundry.py` — the pure reader (`ADAPTER_REGISTRY`,
  `list_adapters`, the `oracle_or_human` gate merge).
- `scripts/lifecycle/rollback-points.py` (SDD-050) `create()` — the snapshot-gate evidence.
- `scripts/observability/eval-tracker.py` (SDD-054, D-10) `load_runs`/`_passed` — the
  eval-gate evidence (the `evals.jsonl` fabric log; record schema `adapter_id·score·passed·
  baseline_score·trace_id`).
- `config/control-systems.yaml` — the `adapter-decide` control (mirror for
  `adapter-gate-human`). SDD-051 (parent), M056 Commit Authority (MS041), R09697-R09711.
