# Island register — pure-library `sovereign-*` crates with zero reverse-dependencies

> Phase-1 audit, finding **F-2026-093** ("wire the island"), closed by **SDD-955**.
> Machine-verified by `tests/lint/test_island_register.py`.

## What this is

The audit's dominant theme is **built-but-unwired islands**: real, tested crates that nothing which runs depends on. The sharpest, most objective signal is a **pure-library crate (`src/lib.rs`, no `main.rs`/`bin/`) that appears in NO other crate's `Cargo.toml`** — it is depended on by nothing at all, not even a demo or a test.

There are **30** such crates today (excluding the 418 `sovereign-cockpit-*` leaf UI widgets, which are a known family consumed by the webapp, not by other crates; and excluding binaries, whose lack of reverse-deps is expected). *(Was 35 — four crates were wired and left the register: `sovereign-rate-limit` → `sovereign-gatewayd` generation admission control; `sovereign-observability-events` → the gateway `GET /v1/events` span stream; `sovereign-hardware-dispatch-eligibility` → `sovereign-telemetry`'s eligibility tableau; `sovereign-cpu-topology` → the NEW `sovereign-cpu-pinning` binary (systemd `AllowedCPUs=` drop-ins for the Trinity CPU agents); and `sovereign-pcie-topology` → the NEW `sovereign-pcie-advisor` binary, which emits + validates the X870E-Creator PCIe layout against the E0027 lane-sharing trap.)* Each is either **wireable** (a plausible in-repo consumer could pull it in crate-to-crate, no new gateway HTTP surface) or **aspirational** (needs a real model / GPU / system-level integration like ZFS/CRIU/VM/network, or an operator decision, before it can be wired). Every one carries a **trigger** — the concrete thing that would activate it — so a rediscovery is an owned backlog item, not a surprise.

The lint keeps this honest **both directions**: add a new pure-library crate with no consumer and CI fails until it is registered here (wire it, or record its trigger); wire an existing island (give it a consumer) and CI fails until its row is removed. The register can only drift toward "everything is either wired or consciously parked."

## Correction to the audit (F-2026-093 as written)

The finding flagged `sovereign-world-model` and `sovereign-hrm-runtime` as under-exposed islands. **They are not islands — both are run-reachable**: `sovereign-cortex` (a direct dependency of the `sovereign-gatewayd` daemon) depends on both (`sovereign-cortex/Cargo.toml`), so they execute inside the daemon. They are removed from the island framing. The audit's other named crates (`sovereign-holderpo`, `sovereign-save-state`, `sovereign-worker-fleet`) are confirmed zero-consumer and appear below; `sovereign-checkpoint` / `sovereign-continuous-batch` / `sovereign-load-balance` / `sovereign-paged-kv` are demo-consumed (not zero-consumer), so they are islands in the broader sense but out of this register's strict "zero reverse-dep" scope (tracked in the summary below, not the enforced table).

## Structural root cause

There are **two parallel generation stacks**. The *wired* one in `gatewayd` runs real weights (`safetensors-loader` → `quant-model` → `quant-llm` → `stream-decode` → `logit-mask` → `hf-tokenizer`). The *island* one funnels ~150 crates through the hub crate `sovereign-llm`, consumed only by the demo/dev binaries (`inference-demo`, `chat`, `serve`, `agent-runtime`) and the island hub `sovereign-retrieval`. Most "wireable" islands light up transitively the day `cortex`/`gateway` gains a real consumer of `sovereign-llm` or `sovereign-retrieval` — that single wiring is the highest-leverage move, tracked as its own follow-up (relates to F-2026-083/088/089).

## Inventory summary (non-cockpit core islands)

Per the dependency closure from the three production binaries (`sovereign-gatewayd`, `sovereign-telemetry`, `sovereign-resource-control`): **53 crates run**; the rest are islands — **418 cockpit-\*** (a family, not enumerated) **+ ~241 non-cockpit** library crates, of which the **30 below have literally zero reverse-dependencies** (the enforced set). The remaining ~206 non-cockpit islands are reachable today only through the `sovereign-llm` / `sovereign-retrieval` hubs (demo/island-only) — a softer signal, not enforced here.

<!-- ISLAND-REGISTER: pure-library sovereign-* crates (src/lib.rs, no main.rs/bin) with ZERO
     reverse-dependencies across all crates/*/Cargo.toml. Verified by
     tests/lint/test_island_register.py. Keep it honest: WIRE one (add a real consumer) and
     remove its row; when a NEW orphan appears, add a row with a disposition
     (wireable|aspirational) + a concrete trigger. Do NOT rename the markers. -->

| crate | disposition | trigger — what would wire it |
|---|---|---|
| sovereign-base-os | aspirational | real host provisioning (install.sh / first-boot) adopts it |
| sovereign-cgroup-systemd | wireable | `sovereign-resource-control` uses it for cgroup enforcement |
| sovereign-continuity-levels | wireable | a cortex/session continuity consumer |
| sovereign-continuity-manager | wireable | a cortex/session continuity consumer |
| sovereign-cpu-dispatch | wireable | the scheduler/plane picks a dispatch path through it |
| sovereign-dashboard-layout | wireable | a cockpit/webapp layout consumer |
| sovereign-dashboard-snapshot | wireable | an observability snapshot consumer |
| sovereign-data-plane | wireable | the gateway data path routes through it |
| sovereign-execution-env | wireable | the jobs/agent execution path resolves env through it |
| sovereign-fs-boundary | aspirational | the real execution-path sandbox (F-2026-081) wires it in |
| sovereign-harness-layers | wireable | a harness/test-orchestration consumer |
| sovereign-hibernation | aspirational | real CRIU/system checkpoint integration |
| sovereign-holderpo | aspirational | a post-training / RL loop (the "post-training pillar" gains a caller) |
| sovereign-inheritance-artifacts | wireable | a config/inheritance resolution consumer |
| sovereign-intake | wireable | a retrieval/ingestion consumer (via `sovereign-retrieval` hub) |
| sovereign-mode-transition-log | wireable | a mode-manager records transitions through it |
| sovereign-module-facets | wireable | a module registry consumer |
| sovereign-network-boundary | aspirational | real network enforcement (F-2026-081 / topology) |
| sovereign-network-zerotrust | aspirational | real network policy enforcement at the bridge |
| sovereign-replay-export-bundle | wireable | an audit/replay export consumer |
| sovereign-replay-playback-rate | wireable | a replay-playback consumer |
| sovereign-sandbox-profile | aspirational | the real execution-path boundary (F-2026-081) selects a profile |
| sovereign-save-state | aspirational | real ZFS+CRIU persistence integration (replaces inline JSON) |
| sovereign-vm-channel | aspirational | the 4090-VM-as-a-device integration (SDD-207 Phase 3) |
| sovereign-vm-workload | aspirational | the VM workload integration (SDD-207 Phase 3) |
| sovereign-whitelabel | wireable | a webapp/branding consumer |
| sovereign-worker-fleet | aspirational | a real N-worker serving cluster (F-2026-083 concurrency) |
| sovereign-zfs-commit-gate | aspirational | real ZFS host integration |
| sovereign-zfs-provisioning-plan | aspirational | real ZFS provisioning integration |
| sovereign-zfs-snapshot-policy | aspirational | real ZFS snapshot integration |

<!-- END ISLAND-REGISTER -->

## How to use it

- **Adding a crate?** If it is a pure library with no consumer yet, add it here with a disposition + trigger (or wire a consumer in the same change). CI enforces it.
- **Wiring an island?** Add the real consumer, then delete its row here. CI enforces that too.
- **Disposition is a judgment, not enforced by value** — the lint requires each row to declare `wireable` or `aspirational`; whether a given crate is truly wireable is for the author/operator to decide. The trigger is the accountability: it names what "wired" would mean.
