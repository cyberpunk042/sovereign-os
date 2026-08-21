# SDD-903 — Profile-driven inference reconciler: make the runtime/orchestration profile the real source of truth for model→card placement (N models per card)

> The runtime/orchestration profile is *partly* the operator's control surface for *which model runs on which card*. Switching a profile and restarting a tier **does** swap that tier's model — the launchers honor the active profile via `runtime_profile_override` (proven by `test_runtime_profile_honoring.sh`). But it stops there: it **cannot** put **multiple models on one card** or add a tier (the tier→unit mapping and the gatewayd tier list are hardcoded), and `trinity profile switch` also renders an `active-runtime-profile-env.sh` that **nothing consumes** — a dead env that masquerades as the apply path while the real path reads the profile YAML directly. This SDD unifies placement into ONE reconciler so a profile that declares a new layout (including **multiple models per card**) takes effect end to end: env the units consume, tier units that exist, and gatewayd routing that matches.

> Status: draft — design for review; no implementation yet.
> Owner: operator-directed 2026-08-21 ("we will need to solve this… it would make no sense otherwise"); agent-authored from a live code + running-state trace.
> Derivation: follow-on to [SDD-902](902-compute-plane-phase2-multi-model.md) (gateway-level multi-model registry) and [SDD-993](993-sain-gpu-topology-5090-primary-4090-oculink-egpu.md) (the three-card topology). This SDD is the **declarative placement layer** above 902's mechanism.
> Mandate module: **E11.M903**.
> Number band: **900–949 (compute-plane — multi-model / GPU)** per SDD-100.
> Decision record: pending — allocate a `D-0##` in `docs/decisions.md` on acceptance.

## Problem — per-tier model swap works, but not N-per-card, and one path is dead code

Model→card placement is split across two mechanisms; one works within narrow limits, the other is partly dead. Traced live on the SAIN-01 desktop (2026-08-21):

1. **IaC converge — the substrate that provisions the tiers.** Modules `72-vllm-host`, `76-oracle-tier`, `84-gpu-route` generate `/etc/sovereign-os/inference-*.env`, register a **hardcoded** GPU tier list with `sovereign-gatewayd` (`84-gpu-route.sh:64` — `_TIERS="gpu-logic@…,gpu-oracle@…"`), and restart the tier units on config change. The units load these env files via `EnvironmentFile`.

2. **Runtime-orchestration profiles (SDD-043 / E108) — partly real.** `sovereign-osctl trinity profile switch <id>` writes `/etc/sovereign-os/active-runtime-profile`, renders `active-runtime-profile-env.sh`, restarts `sovereign-{pulse,logic-engine,oracle-core}`, and applies GPU power states. Crucially the launchers **do** honor the active profile: `start-logic-engine.sh` / `start-oracle-core.sh` / `start-pulse.sh` call `runtime_profile_override <VAR> <tier> model`, which reads that tier's `model` (or `tier_intent` → VRAM-aware `select-by-intent.py`) straight from the active-profile YAML. So on restart a tier **does** pick up the profile's model — proven by `tests/nspawn/test_runtime_profile_honoring.sh` (pulse → `BitNet-b1.58-3B`, core_mask `0-7`).

What works vs. what doesn't:

- ✅ **Per-tier model swap works.** A runtime profile naming a different `model` for an existing tier + a restart → the tier serves the new model (via `runtime_profile_override`, tested). Earlier drafts of this SDD called the whole thing a facade — that was wrong; this path is real.
- ❌ **`active-runtime-profile-env.sh` is dead code.** `trinity profile switch` generates it, but no unit's `EnvironmentFiles` and no launcher sources it — the real consumption is `runtime_profile_override` reading the YAML directly. It masquerades as the apply path; it isn't one.
- ❌ **No N-models-per-card and no new tiers.** `runtime_profile_override` maps a **fixed** tier→unit set (`pulse`/`logic`/`oracle`, + `embed`/`rerank`) 1:1 to a model. Nothing lets a profile put two models on one card or add a tier — the units and the gatewayd `_TIERS` list are hardcoded (the 4090's embed+rerank two-per-card came from two hand-authored units + modules, not the profile).
- ❌ **gatewayd registration isn't profile-derived** (`_TIERS` hardcoded), so a profile-declared *new* tier wouldn't be routable even if a unit existed.
- On this box there is **no `active-runtime-profile`** set, so even the working per-tier-swap path is dormant — placement is the module/env defaults today.

Net: the profile can **swap a model on an existing tier** (real, tested), but it **cannot express or apply the thing the operator actually asked for — multiple models per card / new tiers** — and it ships a dead env file that looks like the apply path. That is the "makes no sense otherwise."

## Goal

One reconciler makes the runtime/orchestration profile the **single source of truth** for model→card placement, such that `trinity profile switch <id>` (or `converge --only inference`) causes the running stack — tier processes, the env they read, and gatewayd routing — to match the profile's `allocations[]`, **including multiple models per card**, or fails loudly with a reason (e.g. VRAM overcommit) and changes nothing.

Non-goals: replacing SDD-902's in-gateway registry/proxy (this drives it); changing the OS-profile/build path (`profiles switch` stays hardware/build); training/tensor-parallel across cards (the 4090 eGPU is x4 — inference only, per SDD-993).

## Design — the reconciler

The profile's `allocations[]` (agent_id, tier, target_hardware, engine, model, `vram_limit_bytes`, `runtime_invocation`, core_mask — already emitted by `profiles generate-runtime`, SDD-043) is the desired state. Reconcile = make live state equal it:

1. **Validate before touching anything.** Sum `vram_limit_bytes` per `target_hardware` ≤ that card's VRAM; refuse the whole switch on overcommit (never OOM a card). Reuse `generate-runtime`'s sizing, or better, the SDD-207 shared-VRAM plane so model residents and GPU jobs claim from one view.
2. **Render the env the units actually consume.** Emit one `inference-<tier>.env` per allocation (the files the units already `EnvironmentFile`), or repoint the units at the runtime-profile env — either way, close the dead-env gap. A lint asserts every generated env file has a consumer.
3. **Materialize tier units dynamically.** Replace the fixed `pulse/logic/oracle/embed/rerank` units with a hardened **systemd instanced template** `sovereign-tier@<alloc-id>.service`, so *N models per card = N instances* (the 4090 already proves this works — it runs `bge-m3` + `bge-reranker-v2-m3` as two units on one card, sharing via `nvidia-mps.yaml` / `gpu-policy.toml`). Each instance pins `CUDA_VISIBLE_DEVICES` + its MPS VRAM fraction. Units inherit the SDD-036 sandbox.
4. **Derive gatewayd registration from the profile.** `84-gpu-route` enumerates the active allocations instead of hardcoding `_TIERS`, so new tiers are routable and the `/v1/embeddings` allow-list stays correct.
5. **Diff + converge idempotently.** Start/stop/restart only changed instances; re-register only changed tiers; a no-op switch is a clean no-op.
6. **One owner, two entry points.** `trinity profile switch` (runtime) is the live model-placement command and invokes the reconciler; `profiles switch` (OS profile) stays build/hardware. No two writers of the same env.

## Open decisions (forks for the review)

- **F1 — tier units.** Dynamic templated instanced units (`sovereign-tier@.service`, flexible, more moving parts) **vs** a fixed max-N tier pool (pre-created units toggled, simpler, capped). *Lean: templated* — it's the only shape that honestly supports arbitrary N-per-card.
- **F2 — engine.** Fold runtime-apply into `converge --only inference` (one reconcile engine, heavier) **vs** keep `trinity profile switch` as a fast dedicated path sharing the validate/register libraries. *Lean: shared libraries, fast path stays.*
- **F3 — env ownership.** Migrate `inference-*.env` to be reconciler-owned (single writer) **vs** keep modules 72/76/84 as writer and feed them from the profile (two writers → drift risk). *Lean: single writer.*
- **F4 — VRAM authority.** SDD-207 live shared-VRAM plane **vs** `generate-runtime` static sizing. *Lean: the live plane* (consistent with SDD-902/207).

## Prerequisite — the profile schema can't express the goal yet (blocks Phase 1)

Traced 2026-08-21: a runtime/orchestration allocation is `{agent_id, tier, role, target_hardware, core_mask, engine, model, active}` (e.g. `profiles/orchestration/coding-focus.yaml`). Two hard gaps make N-per-card *inexpressible* today, so no reconciler can act on it until the schema grows:

- **No serving endpoint/port.** `84-gpu-route`'s tier record is `<proxy-id>@<endpoint>@<device>@<vram_gb>`; the endpoint exists only as the module's hardcoded per-tier port (logic→8082, oracle→8083). An allocation carries no endpoint, so tiers **cannot** be enumerated from allocations without one. → add `endpoint`/`port` (or a deterministic port-allocation convention keyed by tier-instance).
- **`tier` is a fixed set `{pulse, logic, oracle, router}`** (pinned by `test_runtime_profiles_verbatim.py` + `test_orchestration_profiles.py`), one model per tier. There is no way to declare a second model on a card or a new tier. → relax to allow ≥2 allocations sharing a `target_hardware`, each with its own endpoint + `vram_limit_bytes`, and give instances stable ids.

This is a coordinated **schema + verbatim-lint** change (the profile schema is lint-pinned), and it is **F5** below — the foundational decision the rest depends on. It also means **Phase 1 splits**: a schema step (1a) precedes the `84-gpu-route` enumeration (1b).

> **Verification constraint.** `84-gpu-route` is the module whose tier misregistration caused the week-long 256-wedge total-inference outage (its own header documents it). Changes here **must** be validated on the nspawn/qemu integration harness and a live gatewayd apply — not by unit tests alone. Treat any change to it as integration-gated.

## Open decisions (forks for the review)

- **F1 — tier units.** Dynamic templated instanced units (`sovereign-tier@.service`, flexible, more moving parts) **vs** a fixed max-N tier pool (pre-created units toggled, simpler, capped). *Lean: templated* — it's the only shape that honestly supports arbitrary N-per-card.
- **F2 — engine.** Fold runtime-apply into `converge --only inference` (one reconcile engine, heavier) **vs** keep `trinity profile switch` as a fast dedicated path sharing the validate/register libraries. *Lean: shared libraries, fast path stays.*
- **F3 — env ownership.** Migrate `inference-*.env` to be reconciler-owned (single writer) **vs** keep modules 72/76/84 as writer and feed them from the profile (two writers → drift risk). *Lean: single writer.*
- **F4 — VRAM authority.** SDD-207 live shared-VRAM plane **vs** `generate-runtime` static sizing. *Lean: the live plane* (consistent with SDD-902/207).
- **F5 — allocation schema (the prerequisite above).** Add `endpoint`/`port` + allow ≥2 allocations per `target_hardware` with instance ids **vs** keep the fixed 4-tier / one-model-per-tier schema and cap the feature at model-swap only. *Lean: extend the schema* — without it, "multiple models per card" cannot even be written down.

## Migration (incremental, each shippable)

- **Phase 0 — remove the dead env + make the switch honest (smallest fix). ✅ landed.** The `trinity profile switch` env generator no longer emits the dead per-tier exports (only the consumed GPU power-state ones; allocations→comments); honest messaging; `test_runtime_profile_env_no_dead_exports.py` guards it.
- **Phase 1a — schema (F5).** Extend the allocation schema (endpoint/port + ≥2-per-card instance ids) + its verbatim lints. Pure config/lint; no live infra. **This is the real start of N-per-card and must precede 1b.**
- **Phase 1b — reconciler renders `inference-*.env` from `allocations[]`; `84-gpu-route` enumerates allocations for gatewayd.** Integration-gated (see the verification constraint).
- **Phase 2** — hardened `sovereign-tier@.service` template; N-per-card via MPS + `vram_limit_bytes`.
- **Phase 3** — `trinity profile switch` → validate → reconcile → verify.

## Acceptance

A capstone (mirrors `perimeter-capstone.sh` discipline): `trinity profile switch <profile-that-puts-2-models-on-the-4090>` → gatewayd `/v1/models` lists **both**, both serve a real request, per-card VRAM stays within limits, the two big cards are untouched; switching back removes the extra instance and its route. An overcommitted profile is **refused** with the offending card named, changing nothing. A lint blocks any generated env file with no consumer (the dead-env class of bug that motivated this SDD).

## Relationship to prior SDDs

- **SDD-902** — gateway-level multi-model registry + GPU serve-process proxy: the *mechanism* a served model registers through. SDD-903 makes the *profile* decide which models 902 hosts. Complementary layers.
- **SDD-993** — the three-card topology this must respect (PRO 6000 + 5090 internal x8, 4090 OcuLink eGPU x4): keep bandwidth-sensitive models internal; the eGPU is for small/aux models (today: embeddings + reranker).
- **SDD-036** — inference-service-hardening doctrine: the templated tier unit inherits the same sandbox.
- **SDD-207** — shared VRAM authority: the validation/claim source (F4).
- **SDD-043** — runtime-profile generation: `generate-runtime` is the allocation producer and the first sizing gate.

## Status / roadmap

- [ ] Review + pick F1–F4.
- [x] Phase 0 — removed the dead per-tier env exports from `trinity profile switch` (kept the consumed GPU power-state exports; allocations now comments), honest switch messaging (applies per-tier swap; NOT N-per-card/new-tiers), + `test_runtime_profile_env_no_dead_exports.py` regression lint. Landed 2026-08-21.
- [x] Phase 1a — allocation schema (F5): added `port` + `vram_limit_bytes` to the orchestration allocation schema, `embed`/`rerank` tiers+roles, a per-card port-uniqueness lint + an N-per-card-expressible acceptance lint, and a grounded seed profile `profiles/orchestration/dense-4090.yaml` (the live 4090 embed+rerank, 2-on-one-card). Pure config/lint, no live infra. Landed 2026-08-21.
- [x] Phase 1b (core) — `scripts/inference/derive-gpu-tiers.py`: PURE derivation of `GPU_ROUTE_TIERS` + embed/rerank endpoints + SSRF allowlist from `allocations[]`, with port/VRAM `validate()`. 7 unit tests; round-trips **byte-identical** to today's hardcoded `_TIERS`. Landed 2026-08-21. NOT wired.
- [x] Phase 1b (wiring) — `84-gpu-route` derives `_TIERS` + the embed endpoint from the active profile behind a **default-off** knob (`IAC_GPU_ROUTE_FROM_PROFILE`), with a hard fallback to the hardcoded tiers that can never blank them; guard lint `test_gpu_route_profile_wiring.py`. Landed 2026-08-21 — default off, so this box (no active profile) is byte-for-byte unchanged. **ENABLING it live** (flag on + an active profile) stays integration-gated (nspawn/qemu + a live gatewayd apply). Profile-derived `inference-*.env` (per-tier launcher env) rolls into Phase 2.
- [ ] Phase 2 — `sovereign-tier@.service` template + MPS N-per-card.
- [ ] Phase 3 — switch → validate → reconcile → verify + acceptance capstone.
