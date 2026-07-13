# Island register — pure-library `sovereign-*` crates with zero reverse-dependencies

> Phase-1 audit, finding **F-2026-093** ("wire the island"), closed by **SDD-955**.
> Machine-verified by `tests/lint/test_island_register.py`.

## What this is

The audit's dominant theme is **built-but-unwired islands**: real, tested crates that nothing which runs depends on. The sharpest, most objective signal is a **pure-library crate (`src/lib.rs`, no `main.rs`/`bin/`) that appears in NO other crate's `Cargo.toml`** — it is depended on by nothing at all, not even a demo or a test.

There are **0** such crates today — the register is **fully drained** (excluding the 418 `sovereign-cockpit-*` leaf UI widgets, a known family consumed by the webapp, not by other crates; and excluding binaries, whose lack of reverse-deps is expected). *(Was **35** at the audit. Every one has since been given a real consumer — either **wired** crate-to-crate into a running path, or **de-islanded** by gaining a genuine runnable `main.rs` (a validate / emit / compute CLI doing real work over real input, each documented in [`docs/src/binaries.md`](../../src/binaries.md)). The first five to leave were wired or gained a dedicated consumer binary: `sovereign-rate-limit` → `sovereign-gatewayd` generation admission control; `sovereign-observability-events` → the gateway `GET /v1/events` span stream; `sovereign-hardware-dispatch-eligibility` → `sovereign-telemetry`'s eligibility tableau; `sovereign-cpu-topology` → the `sovereign-cpu-pinning` binary (systemd `AllowedCPUs=` drop-ins for the Trinity CPU agents); `sovereign-pcie-topology` → the `sovereign-pcie-advisor` binary (emits + validates the X870E-Creator PCIe layout against the E0027 lane-sharing trap). The remaining **30** were de-islanded across five parallel "big bite" batches — each crate proven to carry a real checkable / emittable / computable model exercisable without the live subsystem, none forced or thin.)* The register now sits at its terminal state — **everything is either wired or de-islanded, nothing left parked** — and the lint keeps it there (below).

The lint keeps this honest **both directions**: add a new pure-library crate with no consumer and CI fails until it is registered here (wire it, or record its trigger); wire an existing island (give it a consumer) and CI fails until its row is removed. The register can only drift toward "everything is either wired or consciously parked."

## Correction to the audit (F-2026-093 as written)

The finding flagged `sovereign-world-model` and `sovereign-hrm-runtime` as under-exposed islands. **They are not islands — both are run-reachable**: `sovereign-cortex` (a direct dependency of the `sovereign-gatewayd` daemon) depends on both (`sovereign-cortex/Cargo.toml`), so they execute inside the daemon. They are removed from the island framing. The audit's other named crates (`sovereign-holderpo`, `sovereign-save-state`, `sovereign-worker-fleet`) were confirmed zero-consumer and have since been de-islanded — each gained a genuine runnable `main.rs` (see [`docs/src/binaries.md`](../../src/binaries.md)); `sovereign-checkpoint` / `sovereign-continuous-batch` / `sovereign-load-balance` / `sovereign-paged-kv` are demo-consumed (not zero-consumer), so they are islands in the broader sense but out of this register's strict "zero reverse-dep" scope (tracked in the summary below, not the enforced table).

## Structural root cause

There are **two parallel generation stacks**. The *wired* one in `gatewayd` runs real weights (`safetensors-loader` → `quant-model` → `quant-llm` → `stream-decode` → `logit-mask` → `hf-tokenizer`). The *island* one funnels ~150 crates through the hub crate `sovereign-llm`, consumed only by the demo/dev binaries (`inference-demo`, `chat`, `serve`, `agent-runtime`) and the island hub `sovereign-retrieval`. Most "wireable" islands light up transitively the day `cortex`/`gateway` gains a real consumer of `sovereign-llm` or `sovereign-retrieval` — that single wiring is the highest-leverage move, tracked as its own follow-up (relates to F-2026-083/088/089).

## Inventory summary (non-cockpit core islands)

Per the dependency closure from the three production binaries (`sovereign-gatewayd`, `sovereign-telemetry`, `sovereign-resource-control`): **53 crates run**; the rest are islands — **418 cockpit-\*** (a family, not enumerated) **+ ~241 non-cockpit** library crates, of which **the enforced zero-reverse-dependency set is now empty** — every former island has a real consumer. The remaining ~206 non-cockpit islands are reachable today only through the `sovereign-llm` / `sovereign-retrieval` hubs (demo/island-only) — a softer signal, not enforced here.

<!-- ISLAND-REGISTER: pure-library sovereign-* crates (src/lib.rs, no main.rs/bin) with ZERO
     reverse-dependencies across all crates/*/Cargo.toml. Verified by
     tests/lint/test_island_register.py. Keep it honest: WIRE one (add a real consumer) and
     remove its row; when a NEW orphan appears, add a row with a disposition
     (wireable|aspirational) + a concrete trigger. Do NOT rename the markers. -->

_(No rows — the register is **fully drained**: zero pure-library `sovereign-*`
crates with zero reverse-dependencies remain. Every former island now has a real
consumer. The empty table below stays so a future orphan gets a home; the lint
flags any new zero-reverse-dep pure library until a row is added here or a
consumer is wired.)_

| crate | disposition | trigger — what would wire it |
|---|---|---|

<!-- END ISLAND-REGISTER -->

## How to use it

- **Adding a crate?** If it is a pure library with no consumer yet, add it here with a disposition + trigger (or wire a consumer in the same change). CI enforces it.
- **Wiring an island?** Add the real consumer, then delete its row here. CI enforces that too.
- **Disposition is a judgment, not enforced by value** — the lint requires each row to declare `wireable` or `aspirational`; whether a given crate is truly wireable is for the author/operator to decide. The trigger is the accountability: it names what "wired" would mean.
