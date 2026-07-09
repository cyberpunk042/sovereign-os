# SDD-104 — web-expose the request *producers* (no-manual-commands) — D-06 approvals + D-07 memory-changes

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-09
> Closes findings: SDD-048 Q ("producer not web-exposed"), SDD-052 Q ("producer not web-exposed")
> Derived from: operator goal "continue on the no manual commands needed and the beautiful dashboard … god tier"; chosen after two groundings closed the remaining "make-functional" leads as hardware-gated (M046 adapter lifecycle = pivot; 30/31 exec-rail controls already built). Recover-projects band (SDD-104 / E11.M104).

## Mission

Deliver the last honest sliver of the goal's **"no manual commands needed"** half. Today the
operator one-clicks **approve/deny/defer** (D-06) and **promote/pin/forget** (D-07) from the web
through the sanctioned exec-rail, but **getting an item into either queue** still requires a
hand-authored terminal command — the two queue *producers* (`approvals request`, `memory-changes
request`) exist and dispatch through osctl but are explicitly **not web-exposed**. Web-expose both
through the **already-sanctioned exec-rail** (R10274) so the operator can enqueue a pending intent
from the panel, while the privileged **decision** that signs it stays exactly as gated. This is
**wiring, not building** — no new write path, no producer logic change.

## Problem

- `scripts/lifecycle/approval-decide.py::request(*, title, severity, gate, …)` mints an
  `APR-<8hex>` pending item; dispatched at `scripts/sovereign-osctl:8291` (`approvals request`).
  Its docstring: *"NOT privileged, NOT a control, NOT web-exposed."*
- `scripts/intelligence/memory-decide.py::request(op, *, mtype, scope, …)` mints an `mc-<8hex>`
  pending change; dispatched at `scripts/sovereign-osctl:8331` (`memory-changes request`),
  `op ∈ {promote,pin,forget}` (`_VALID_PENDING_OP`). Same *"NOT a control, NOT web-exposed"* note.
- So the *decision* is one-click from the web (`approvals-decide` / `memory-decide` controls) but
  *enqueuing* still needs the CLI — the residual "manual command" on D-06/D-07.

## Grounded design — two symmetric request controls, rail-safe by the enum vocabulary

The exec-rail (`scripts/operator/_action_exec.py`) validates every placeholder: enum placeholders
`{a|b|c}` must match `[a-z0-9|_-]` and be keyed `verb`/`verb1`/…; free `<name>` values must be in
the control's `options` list OR match the strict `_SAFE_VALUE` regex (bans `/`, whitespace,
arrows). The vocabularies are chosen to pass the rail **and** stay semantically correct:

- **`approvals-request`** (`applies_to: [d-06-pending-approvals]`)
  `change_cli: "sovereign-osctl approvals request --gate <gate> --severity {low|medium|high|critical} --title <title>"`
  - `gate` (free `<gate>`, options datalist **SG1..SG5**) → the M065 `STAGE_GATES` keys, the ONLY
    gates `approval-decide.decide()` can later gate-sign (`gate in STAGE_GATES`). SG-keys are
    **uppercase**, and the rail's enum placeholder is **lowercase-only** (`[a-z0-9|_-]`), so gate
    is a *free* placeholder — uppercase `SG3` passes `_SAFE_VALUE`, is stored verbatim, and stays
    signable. (The producer's `L4→L5` default is a non-signable arrow label the rail can't carry —
    SG-keys are both rail-safe **and** more correct than L-labels.)
  - `severity` (enum, keyed `verb`) → `low|medium|high|critical` (`_VALID_SEVERITY`) — lowercase,
    a real rail enum (segmented buttons).
  - `title` (free `<title>`) → the same `options` datalist (safe slugs `operator-request`,
    `cloud-spend`, `model-swap`, `policy-change`, `capability-grant`, `resource-scale`).
    **Accepted caveat:** rich human-readable titles stay CLI — `_SAFE_VALUE` bans spaces and
    **must not be widened**.
- **`memory-request`** (`applies_to: [d-07-memory-changes]`)
  `change_cli: "sovereign-osctl memory-changes request {promote|pin|forget} --mtype <mtype>"`
  - `op` (enum) → `promote|pin|forget` (`_VALID_PENDING_OP`).
  - `mtype` (free `<mtype>`) → the `_MEMORY_TYPES` datalist (`semantic`, `episodic`,
    `procedural`, `working`, …).

Both: `kind: lifecycle`, `scope: scoped`, `privileged: false` (a low-stakes intent-enqueue,
deliberately distinct from the privileged **decision** that signs it). Full field set. **No
producer logic change** — only the two docstrings are corrected from *"NOT a control, NOT
web-exposed"* to *"web-exposed via the sanctioned R10274 exec-rail (dry-run default); rich
free-text titles/scopes stay CLI."*

## Grounded reality — why R10212 holds by construction

D-06/D-07 already mount the shared component (`webapp/d-06-pending-approvals/index.html` +
`d-07-memory-changes/index.html` end with `SovereignControlSurface.load(…,{filterSlug:…})`;
`control-surface.js` filters the registry by `applies_to`). A control with the right `applies_to`
**auto-renders — no webapp code change.** The two controls route through the existing sanctioned
exec-rail: allowlisted `control_id`, `SELFDEF_OWNED` hard-reject (neither is selfdef-owned),
placeholder allowlist / `_SAFE_VALUE`, **DRY-RUN by default** (nothing mutates unless
`SOVEREIGN_OS_ACTION_EXEC_LIVE=1` + operator-reviewed sudoers), OCSF-5001 audit span. **No new
write path** — every other `*-api.py` daemon stays read-only 405.

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-104-A | Privileged? | **answered (operator, 2026-07-09): `privileged: false`** — enqueuing a pending intent is low-stakes and distinct from the privileged approve/decide that signs it; still dry-run-default + audited via the rail. |
| Q-104-B | Gate vocabulary for approvals-request. | **answered: SG1..SG5** (the signable `STAGE_GATES`; arrow L-labels can't cross the rail and aren't gate-signable). |
| Q-104-C | Free title/scope richness. | **answered: safe-slug only via the rail; rich text stays CLI. Do NOT widen `_SAFE_VALUE`.** |

## Non-goals (Stage N / fabrication traps explicitly out)

- Widening `_action_exec._SAFE_VALUE` to carry free text (erodes the R10212 arg allowlist).
- Adding a POST to any read-only `*-api.py` mirror daemon (breaks the one-write-path invariant).
- Shipping `SOVEREIGN_OS_ACTION_EXEC_LIVE=1` / the sudoers drop-in to "really execute" (the
  hardware/privilege boundary — operator-reviewed).
- Building MS003 signing in sovereign-os (delegated to selfdef; `unsigned-pending-MS003`).
- A real auto-producer (cost/stage-gate) that enqueues on its own — needs live cloud/cost events
  (integration-gated); fabricating enqueues violates SB-077.
- Web-triggering `sessions start` (arbitrary exec — permanently excluded).

## Way forward

- **Stage 0 (this commit):** this SDD + INDEX row 104 + mandate E11.M104; flip SDD-048 & SDD-052
  producer notes.
- **Stage 1:** the two controls in `config/control-systems.yaml` + `EXPECTED_IDS` + the two
  docstring corrections + the two verbs in the DRAFT sudoers allowlist
  (`config/sudoers.d/sovereign-os-cockpit` — `approvals request --gate *`, `memory-changes
  request *`; `test_cockpit_action_exec_sudoers.py` requires every sovereign-os-owned verb be
  allowlisted) + a request-controls test.
- **Stage 2:** verify the D-06/D-07 auto-render + e2e (`_action_exec.execute` dry-run for both) +
  full gate.

## Safety invariants

**R10212 preserved by construction** — no new write path; the two controls route through the
existing sanctioned exec-rail (allowlisted, dry-run-default, audited OCSF-5001). The web still
never *arbitrarily* mutates; in the shipped posture nothing executes without operator-enabled
LIVE. **SB-077** — an unreachable exec daemon streams the honest error / copy fallback, never
fabricates a queue write. Enqueue (unprivileged intent) stays distinct from the privileged signed
decision. No `_SAFE_VALUE` widening, no new API POST, no LIVE/sudoers ship, no MS003 crypto, no
auto-producer, `sessions start` untouched. No contract yaml change. MS003 `unsigned-pending-MS003`.

## Cross-references

- `scripts/operator/_action_exec.py` — the R10274 exec-rail (`execute` / `resolve_argv` / the
  `_SAFE_VALUE` allowlist / `SELFDEF_OWNED` boundary).
- `webapp/_shared/control-surface.js` — the shared renderer (auto-renders by `applies_to`).
- `config/control-systems.yaml` — the control registry.
- `scripts/lifecycle/approval-decide.py::request` (SDD-048) + `scripts/lifecycle/approval-queue.py`
  (`STAGE_GATES` = SG1..SG5, `_VALID_SEVERITY`).
- `scripts/intelligence/memory-decide.py::request` (SDD-052) + `_VALID_PENDING_OP` +
  `scripts/intelligence/memory-store.py::_MEMORY_TYPES`.
- `tests/lint/test_control_systems_registry.py` (`EXPECTED_IDS`), `test_control_surface_execute_boundary.py`,
  `test_cockpit_action_exec_sudoers.py` (every sovereign-os-owned verb allowlisted).
- `config/sudoers.d/sovereign-os-cockpit` (DRAFT allowlist — `approvals request --gate *`, `memory-changes request *`).
- `tests/unit/test_request_controls.py`.
- SDD-045 (control-systems registry), R10274 (exec-rail), R10212, SB-077, M065 (stage gates).
