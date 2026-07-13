# Runtime binaries

> The **33 Rust binary crates** (`crates/*/src/main.rs`) are the executable runtime surface of
> sovereign-os. Everything else in `crates/` is a library consumed by these (or an island —
> see the phase-1 audit's island register). This page maps each binary to its **role**, how it
> is **invoked**, and what it **does**. Enforced complete by `tests/lint/test_binaries_doc.py`.

Most of the box's ~90 systemd services are the **Python operator APIs** (`scripts/operator/*.py`);
the Rust binaries below are the compute/runtime core.

## Production

| Binary | Invoked by | Role |
|---|---|---|
| **`sovereign-gatewayd`** | `sovereign-gatewayd.service` (persistent) | The one AI-backend daemon — loopback `127.0.0.1:8787`, speaks the Anthropic Messages API + OpenAI shim over the local model, plus the sovereign routing/reasoning surfaces. The `sovereign-cortex` routing engine + the `safetensors → quant-model` generation stack run **inside** it. See [Use the box as your AI backend](./ai-backend.md). |
| **`sovereign-telemetry`** | `sovereign-telemetry-textfile.timer` → `scripts/hooks/recurrent/sovereign-telemetry-textfile.sh` (periodic) | Probes host state and emits Prometheus **textfile** metrics (M045/M013) for node-exporter to scrape. |
| **`sovereign-resource-control`** | `Makefile` (`bins`) + `scripts/operator/brain-api.py` | Resource / cgroup control helper for the compute plane. |
| **`sovereign-feature-selftest`** | `sovereign-feature-test-lab-api.service` + `scripts/operator/feature-test-lab-api.py` | The feature self-test runner behind the feature-test-lab surface. |
| **`sovereign-cpu-pinning`** | operator / provisioning (emits config) | Emits systemd `AllowedCPUs=` drop-ins pinning the Trinity CPU agents (Pulse / Weaver+Auditor / System-Host) to their CCD cores, from the `sovereign-cpu-topology` source of truth — the CPU-affinity counterpart to `sovereign-resource-control`. |
| **`sovereign-pcie-advisor`** | operator / provisioning (emits + validates config) | Prints the recommended ProArt X870E-Creator PCIe layout and validates a proposed one against the E0027 lane-sharing trap, from the `sovereign-pcie-topology` source of truth. `--check FILE` exits non-zero on a lane-sharing / duplicate-slot conflict. |
| **`sovereign-inheritance-check`** | operator / governance (verify) | Prints the canonical M042 8-artifact durable-inheritance manifest (VISION/ARCHITECTURE/METHODOLOGY/PROFILES/POLICY/MODEL_REGISTRY/HARDWARE_PROFILES/EVALS) and `--check ROOT` verifies the files exist, from the `sovereign-inheritance-artifacts` source of truth. |
| **`sovereign-execution-env`** | operator / reference | Lists the E0553 execution-environment taxonomy — the 9 environments (ModelServer / Repl / Shell / Container / VM / Browser / …) each mapped to its isolation level, + the 10 observation categories a run is watched by. A discoverable reference over the model crate. |
| **`sovereign-module-facets`** | operator / reference + validate | Lists the E0477 uniform module interface — the 6 facets every module must expose (state / events / policy-hooks / profile-knobs / rollback / learning-signal); `--check FILE` validates a ModuleDescriptor JSON against the canonical set. |
| **`sovereign-mode-transition-log`** | operator / audit | Renders an example append-only ExecutionMode transition record and `--validate FILE` validates a transition log JSON (legal mode shifts), exiting non-zero on an invalid log. |
| **`sovereign-cgroup-systemd`** | operator / reference + validate | Lists the 8 M045 OS primitives (cgroupv2 / systemd / psi / ebpf / apparmor / namespaces / zfs / luks-tpm-fido2); `--check FILE` validates a PrimitiveSnapshot JSON + reports available_count. |
| **`sovereign-continuity-manager`** | operator / reference + validate | Lists the continuity lifecycle states/primitives + the allowed-transition matrix; `--check FILE` validates signed (MS003) lifecycle transitions, exit != 0 on an illegal/unsigned move. |
| **`sovereign-harness-layers`** | operator / reference + validate | Lists the M082 5-layer TDD test pyramid (virtualization / CI trigger / retries per layer); `--check FILE` classifies test directories to their layer, flagging unrecognized ones. |
| **`sovereign-replay-export-bundle`** | operator / validate | Builds an example replay ExportBundle (thread + cursor + bookmarks); `--validate FILE` validates a bundle JSON's cross-references, exit != 0 on a mismatch. |
| **`sovereign-dashboard-layout`** | operator / reference + validate | The 12-column dashboard widget grid + 8 widget kinds; `--check FILE` validates a DashboardLayout / LayoutManifest against the grid bounds + slot coverage. |
| **`sovereign-whitelabel`** | operator / reference + validate | The M081 rebrand model (4 categories / 4 strategies / 3 lifecycle stages); `--check FILE` enforces the E0785 legal-compliance rule (must-not-touch never modified, must-rebrand always) on a rebrand plan. |
| **`sovereign-continuity-levels`** | operator / reference + validate | The E0456 8-level continuity ladder (depth + cloud-typical / station-owned per level); `--check FILE` validates a continuity level value. |
| **`sovereign-cpu-dispatch`** | operator / query + validate | The 4 ranked dispatch paths (scalar → avx2 → avx512 → zen5-avx512); `--select FILE` runs the real `select_best()` on CpuFeatures, `--check FILE` gates the chosen path against an expected one. |
| **`sovereign-dashboard-snapshot`** | operator / validate | Builds an example cockpit DashboardSnapshot (banner + context + toasts) and `--validate FILE` validates a snapshot JSON, exit != 0 on schema/consistency failure. |
| **`sovereign-data-plane`** | operator / set algebra | Exact RoaringBitmap set operations over JSON id arrays — `--union` / `--intersect` / `--cardinality` / `--contains` (the integer-set analogue of comm/sort -u). |
| **`sovereign-intake`** | operator / reference + validate | The intake model (10 task sources / 3 privacy contexts / the gateway-stamped fields); `--check FILE` validates an IntakeRequest's identity (request_id + client_id). |
| **`sovereign-replay-playback-rate`** | operator / query + validate | The 6 replay speeds (0.25x…8x) with wall-time factors; `--interval MS` computes each rate's advance interval, `--rate NAME` reports one, `--check FILE` validates a rate state. |
| **`sovereign-zfs-snapshot-policy`** | operator / emit + validate | Emits the canonical ZFS snapshot systemd units (a .timer + oneshot .service per daily/weekly/monthly cadence) from the retention model; `--check FILE` runs `plan_pruning()` on a snapshot inventory and prints the `zfs destroy` plan. |
| **`sovereign-zfs-provisioning-plan`** | operator / emit + validate | Emits a REVIEW-ONLY `zpool create` / `zfs create` / `zfs set` script from the provisioning model (never executes, device-safety checked); `--check FILE` validates a plan (shell-safe tokens, target device). |
| **`sovereign-zfs-commit-gate`** | operator / reference + validate | The 4-stage ZFS commit gate (commit permitted only at test_score ≥ 80; rollback always); `--check FILE` runs the real gate decision on a GateCycle, flagging violations. |
| **`sovereign-fs-boundary`** | operator / classify + validate | The `/ai-exchange/{inbox,outbox,artifacts}` filesystem boundary; classifies paths (allowed/denied, `..`-escape safe) and `--check FILE` validates a boundary-query config. |
| **`sovereign-sandbox-profile`** | operator / reference + validate | The 8 sandbox profiles by dimension (fs / network / gpu / isolation); `--check FILE` resolves a profile set + flags a dimension constrained by two profiles. |
| **`sovereign-network-boundary`** | operator / reference + validate | The 5-rung network profile ladder (offline → authenticated-browser); `--check FILE` decides allow/deny per tool intent via `is_within_allowance`. |

## Dev / demo CLIs

Invoked manually or surfaced through the `brain-api` catalog (`scripts/operator/brain-api.py`);
none is a persistent service.

| Binary | Role |
|---|---|
| **`sovereign-cortex`** | CLI/demo over the routing brain. NOTE the cortex **library** is the routing engine wired into `gatewayd`; this binary is a standalone driver, not the production path. |
| **`sovereign-agent-runtime`** | ReAct agent-loop demo (LlmResponder). Built + tested; not wired into the daemon (F-2026-088). |
| **`sovereign-inference-demo`** | End-to-end quantized-inference composition demo on **synthetic** weights (a plumbing proof, not a real model run — F-2026-006). |
| **`sovereign-chat`** | Interactive chat CLI over the local model. |
| **`sovereign-serve`** | The parallel serving orchestrator (cache → complexity → budget). Currently **dead relative to the daemon** — see the SDD-957 decision package (F-2026-089). |

## Operator config generators

Deterministic CLIs that **emit systemd/host configuration** from a Rust source-of-truth
model, for an operator (or the build) to review and place. Not services — they print and exit.

| Binary | Role |
|---|---|
| **`sovereign-cpu-pinning`** | Emits the `AllowedCPUs=` resource-control drop-ins that pin the Trinity CPU agents (Pulse / Weaver+Auditor / System-Host) to their CCD cores, from the single-source-of-truth `sovereign-cpu-topology` partition (E0672-E0674). Default prints every unit's drop-in preceded by its `/etc/systemd/system/<unit>.d/…` path; `--unit <name>` restricts to one. The CPU-affinity counterpart to `sovereign-resource-control`'s weight/limit drop-ins; replaces the hardcoded ranges once duplicated in `scripts/hardware/ccd-pinning.py`. |

## How they compose

```
sovereign-gatewayd (daemon)                     ← the only always-on Rust service
  ├─ sovereign-cortex (lib)   routing / decision brain
  └─ safetensors-loader → quant-model → …        text generation

sovereign-telemetry (periodic)   → node-exporter textfiles
sovereign-resource-control       → cgroup / compute-plane control
sovereign-cpu-pinning            → systemd AllowedCPUs= drop-ins (Trinity core pinning)
sovereign-pcie-advisor           → recommended/validated PCIe layout (lane-sharing trap)
sovereign-inheritance-check      → verify the box's 8 durable inheritance artifacts
sovereign-execution-env          → reference the 9 execution envs + isolation levels
sovereign-module-facets          → the 6-facet module interface (list + validate)
sovereign-mode-transition-log    → example transition record + validate a log
sovereign-cgroup-systemd         → the 8 OS primitives (list + validate a snapshot)
sovereign-continuity-manager     → lifecycle states + validate signed transitions
sovereign-harness-layers         → the 5-layer test pyramid (classify test dirs)
sovereign-replay-export-bundle   → build/validate a replay export bundle
sovereign-dashboard-layout       → 12-col widget grid (validate layouts)
sovereign-whitelabel             → M081 rebrand model (validate a rebrand plan)
sovereign-continuity-levels      → the 8-level continuity ladder (validate a level)
sovereign-cpu-dispatch           → the 4 CPU dispatch paths (select_best + gate)
sovereign-dashboard-snapshot     → build/validate a cockpit snapshot
sovereign-data-plane             → RoaringBitmap set algebra (union/intersect/…)
sovereign-intake                 → intake model (validate request identity)
sovereign-replay-playback-rate   → the 6 replay speeds (interval/rate/validate)
sovereign-zfs-snapshot-policy    → emit snapshot systemd units + prune plan
sovereign-zfs-provisioning-plan  → emit review-only zpool/zfs commands + validate
sovereign-zfs-commit-gate        → the commit gate (test_score>=80) decision
sovereign-fs-boundary            → /ai-exchange path classification
sovereign-sandbox-profile        → 8 sandbox profiles by dimension
sovereign-network-boundary       → the 5-rung network profile ladder
sovereign-feature-selftest       → feature-test-lab

dev/demo: cortex · agent-runtime · inference-demo · chat · serve   (manual / brain-api)
config-gen: cpu-pinning   → systemd AllowedCPUs= drop-ins (from sovereign-cpu-topology)
```

The production runtime is **one daemon** (`gatewayd`) plus a periodic metrics emitter and a
couple of control/test helpers; the rest are developer tools. Do not conflate the demo binaries
(`inference-demo` on synthetic weights, `serve` the dead orchestrator) with the real path.
