# SDD-051 — Adapter promotion authority (functional promote / demote / rollback for D-11)

> Status: draft
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-08
> Closes findings: none (write half atop the D-11 read model + SDD-047 control surface)
> Derived from: operator directive 2026-07-08 (chose the D-11 adapter-status engine after SDD-050's snapshot/rollback merged in PR #28); SDD-048 (approval authority — this engine's structural twin: registry-overlay read model + decision-writer + gate enforcement + MS003-deferred signature); SDD-047 (cockpit functional execution / R10274 control-exec-api); M046 LoRA Foundry; MS041 high-risk triple-gate (R09697-R09711); M060 R10109-R10111 (D-11 read model).

## Mission

Make the D-11 adapter-status panel's LoRA-adapter lifecycle actions — **promote**,
**demote**, **rollback** — functional as a sanctioned cockpit control on the
SDD-047 R10274 rail. Today they are neutralized (`alert('planned')`); the D-11
read path (`adapter-foundry.py` + `adapters-api.py`) is complete, but the write
half — the promotion authority that transitions adapter status, enforces the
MS041 triple-gate, and records a durable audited decision — is greenfield.

## Problem

The D-11 per-row promote / demote / rollback buttons (+ train + export) emit
nothing (`sovereign adapter` is not a real verb). Structurally identical to the
pre-SDD-048 D-06 approvals gap:

- **Read side complete.** `sovereign-osctl adapters {inventory,list,history}` →
  `scripts/inference/adapter-foundry.py` overlays the model catalog's
  `class=lora-adapter` entries with a promotion registry
  (`/var/lib/sovereign-os/adapters/registry.json`: per-adapter `status` + MS041
  `gates` + `history`). `adapters-api.py` serves `/api/adapters/inventory` +
  `/history` + `/stream`; POST/PUT/DELETE → 405.
- **Write side greenfield.** Nothing transitions `status`, enforces the MS041
  triple-gate, or writes a decision. Adapter promotion (L6 Persist) is
  **MS041-triple-gated**: `snapshot` + `test/eval` + (`oracle` OR `human`) must
  be `passed` (R09697-R09711).

## Required coverage

### Promote / demote / rollback (write, sovereign-os-owned)

- **promote** — `pending → active`, **refuse-by-default** unless the MS041
  triple-gate is met. There is **no panel override** (operator decision Q-051-A):
  a forced promotion is a manual registry edit, keeping the high-risk gate
  meaningful. Refusal is a structured error naming the unmet gate(s).
- **demote** — `active → pending` (status guard).
- **rollback** — `→ rolled-back`.
- Each transition appends a `history` entry and records `signature:
  "unsigned-pending-MS003"`. **R10212 ownership**: the LoRA-Foundry adapter
  lifecycle is sovereign-os-owned (consistent with approvals-decide /
  rollback-apply); `adapters-api.py` stays read-only (405); the write methods are
  CLI-dispatch-only.

### Decision-writer + producer

The writer lives in a NEW `scripts/inference/adapter-decide.py` (keeps
`adapter-foundry.py` a pure reader — the API imports it and calls only
`inventory()`), importing the reader's `ADAPTER_REGISTRY` / `_VALID_STATUS` /
`_read_json` / `list_adapters`. Atomic `os.replace` registry write; durable
`/var/log/sovereign-os/adapter-decisions.jsonl` ledger; OCSF-5001 M049 span (D-05
/ D-16). A minimal `register <id>` producer mints a `pending` adapter with empty
gates (the real M046 training + eval/oracle/human gate-producers are Stage 4).

### MS003 signing (deferred, per the SDD-048 precedent)

Signing is delegated to selfdef; this first cut records `unsigned-pending-MS003`
(no signing crypto in sovereign-os — R10212). Presence-gated + type-to-confirm at
the exec daemon.

### The control (mirrors approvals-decide — one control, verb enum)

A single `adapter-decide` control — `sovereign-osctl adapters
{promote|demote|rollback} <id> --confirm`, privileged, `applies_to:
[d-11-adapter-status]` — exactly as SDD-048 shipped ONE `approvals-decide`
control for approve/deny/defer. Registry 24→25, local 19→20. `<id>` is a free
`_SAFE_ID` arg (catalog ids are `_SAFE_VALUE`-clean, no `/`).

### Export / train (operator decision: export now, train deferred)

`export inventory CSV` becomes a real client-side CSV built from the live
`/api/adapters/inventory` (a read, no host mutation). `train new adapter` (the
heavy M046 LoRA training pipeline — a poor synchronous-control fit) is honestly
relabeled + deferred to Stage 3.

## Goals

- Functional promote/demote/rollback via the sanctioned control-exec-api rail;
  one control auto-rendered on d-11.
- Reuse `adapter-foundry.py` (pure reader) + mirror `approval-decide.py`.
- R10212 preserved: selfdef/perimeter untouched; `state_path` free of
  selfdef/tetragon; `adapters-api.py` stays read-only (405).

## Non-goals (Stage 3 / follow-up)

- Wire the M046 LoRA **training pipeline** (`train`).
- Real MS003 **signing** (selfdef) + real **gate-producers** (eval/oracle/human
  advancing the MS041 gates).
- NVFP4 promotion path (M077); quarantine transitions.

## Open questions

| Q | Question | Resolution |
|---|---|---|
| Q-051-A | Promote-gate strictness. | **answered (operator, 2026-07-08): refuse-by-default unless the MS041 triple-gate is met; NO panel override (a forced promotion is a manual registry edit).** |
| Q-051-B | `train new adapter` scope. | **answered (operator, 2026-07-08): deferred to Stage 3 (heavy M046 pipeline); export-CSV wired client-side now.** |
| Q-051-C | Target status names for demote / rollback. | **proposed: demote→`pending`, rollback→`rolled-back` (both in `_VALID_STATUS`). Operator may prefer a distinct `demoted` status.** |
| Q-051-D | Adapter-id `/` fallback. | **proposed: `<id>` free `_SAFE_ID` arg now (catalog ids are clean). If a real id ever carries `/`, resolve it internally like model-load (SDD-049).** |
| Q-051-E | Real MS003 signing + real gate-producers. | **proposed: Stage 4 — signature `unsigned-pending-MS003` until selfdef signs; gates stay operator/registry-advanced until the training pipeline feeds them.** |

## Way forward

- **Stage 0 (this commit):** this SDD.
- **Stage 1:** `scripts/inference/adapter-decide.py` (promote/demote/rollback +
  register) + `tests/unit/test_adapter_decide.py`.
- **Stage 2:** the `adapter-decide` control + the `adapters)` osctl read/write
  sub-case routing + sudoers + lint bumps (24→25) + honest d-11 button re-wire.
- **Stage 3 (follow-up):** train pipeline, real signing, real gate-producers.

## Safety invariants (every stage)

Privileged + operator-key + type-to-confirm + DRY-RUN-default; promote
refuse-by-default unless the MS041 triple-gate passed (no panel override);
selfdef/perimeter untouched + `state_path` free of selfdef/tetragon;
`adapters-api.py` stays read-only (405); ids `_SAFE_ID`-validated; atomic registry
write + durable ledger + OCSF-5001 span; MS003 `unsigned-pending-MS003` (real
signing deferred to selfdef). The registry write is the only host mutation, gated
by the exec rail + sudoers.

## Cross-references

- `scripts/inference/adapter-foundry.py` — the D-11 reader (import its helpers;
  keep it a pure reader).
- `scripts/lifecycle/approval-decide.py` — the writer template (this engine's twin).
- `scripts/operator/adapters-api.py` — read-only daemon (imported `_core`; stays 405).
- `scripts/sovereign-osctl` — the `adapters)` arm → read/write sub-case routing,
  mirroring `approvals)`.
- `scripts/operator/_action_exec.py` — the exec rail (`state_path` must avoid
  selfdef/tetragon; `_SAFE_VALUE` forbids `/`); `control-exec-api.py` — R10274 daemon.
- `config/control-systems.yaml` — the 24 controls (model the new one on approvals-decide).
- SDD-048 (approval authority — the structural twin), SDD-047 (cockpit functional
  execution), SDD-050 (snapshot/rollback — the prior greenfield engine).
