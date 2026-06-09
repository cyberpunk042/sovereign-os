# Sovereign substrate — the observability / control / data-flow contract layer

> The crates below are the **substrate**: the typed contracts, schemas, state
> machines, and observability the runtime *engine* (router / scheduler / memory
> / eval cortex) plugs into. They are deliberately engine-agnostic — the engine
> emits/decides/schedules **against** these types; it does not live inside them.
> Every crate is `#![forbid(unsafe_code)]`, serde-typed, unit-tested, and
> auto-included via the `crates/*` workspace glob.

## The task data-flow (M057), step by step

A task moves through 12 lifecycle steps; each step has a substrate crate that
fixes its contract:

| Step | Crate | What it fixes |
|---|---|---|
| 1. Intake | `sovereign-intake` | 10 task sources + the 6 gateway fields (request_id / **trace_id** / client_id / profile_hint / privacy_context / budget_hint) |
| 3. Profile | `sovereign-config-resolver` | 7 config layers + 5 conflict-resolution rules (hard-policy > profile, project > generic, …) |
| 4. Map | `sovereign-task-map` | 4 domain maps (code/research/gui/os-admin) + `missing_components()` blind-spots |
| 5. Plan/Compile | `sovereign-workflow-graph` | 8 node types + a DAG with cycle detection + topological order |
| 7. Execute | `sovereign-execution-env` | 9 bounded environments + isolation levels |
| 8. Observe | `sovereign-observability-events` | 15-event taxonomy + 13-field span (`branch_id`/`trace_id` = the trace types) |
| 9–10. Evaluate/Commit | `sovereign-zfs-commit-gate` | 4-stage gate, test-score ≥ 80 to commit, else rollback |
| 11. Learn | `sovereign-learning-signals` | 7 immediate signals + 4 deferred LoRA steps, outcome-driven |
| 1–12. lifecycle | `sovereign-task-lifecycle` | 12 steps + the 9 task states with a validated state machine |
| (the law) | `sovereign-typed-state` | "Text is payload inside typed state" — the 8 typed components |

The **trace** is the spine: `sovereign-trace-context` (trace_id / span_id /
branch_id / commit_id + reconstructable `committed_path()`) is reused by
`intake`, `typed-state`, and `observability-events`, so a task is locatable end
to end.

## Cross-cutting substrate

- **Sense → decide → enforce (M045/M013)**: `sovereign-pressure-sensors` +
  `sovereign-hardware-load-sample` ingest real PSI / nvidia-smi / `/proc/stat` /
  sysfs-thermal → `sovereign-pressure-reactions` (OS) + `sovereign-runtime-reactions`
  (E0472 telemetry-as-control) prescribe actions → `sovereign-resource-control`
  emits the systemd cgroup boundaries. The `sovereign-telemetry` **binary** runs
  the whole chain and exposes `--prometheus` (→ alerts + Grafana dashboard via
  the systemd timer).
- **Bit-level worker state**: `sovereign-worker-status-word` (M00212, 8 byte
  fields) + `sovereign-worker-fleet` (fleet summary); `sovereign-control-word`
  (M00013, variable-width fields + a branchless rule-word LUT).
- **Hardware topology**: `sovereign-cpu-topology` (dual-CCD + Trinity core
  pinning + cpuset emission) and `sovereign-pcie-topology` (slot map + the
  lane-sharing trap detector).
- **Governance**: `sovereign-policy-input` (7 questions, 10-field intent-based
  input, 9 sensitivity classes), `sovereign-trust-boundaries` (4 zones + the
  A/B/C/D tool ladder with `is_placement_safe`), `sovereign-module-facets` (the
  uniform 6-facet module contract), `sovereign-codegen-pipeline` (the 7-step
  generated-code path + 5-rung promotion ladder).

## How the engine plugs in

- **Consume** the telemetry (`PressureSnapshot` / `LoadSnapshot`) and the
  hardware topology to schedule; the reactions crates turn pressure into
  prescribed actions.
- **Emit** `ObservabilitySpan`s (one per event) carrying the trace coordinates;
  write `WorkerStatusWord`s the fleet view aggregates.
- **Decide** through `PolicyInput` / `TrustZone` placement before acting.
- **Resolve** config per action via `LayeredConfig`; record the typed state.

None of these crates schedules, infers, or routes — that is the engine's job.
They are the legible, typed surface that makes the engine's actions
observable, governable, and reversible.
