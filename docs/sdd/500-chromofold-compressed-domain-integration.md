# SDD-500 — ChromoFold compressed-domain integration (DESIGN / positioning)

> Status: **design — positioning only** (no binding code this session; the build is TODO behind operator approval of the Q-rows)
> Owner: operator-directed 2026-07-20 (verbatim: *"Lets look to start integrating chromoFold coming from : ../warp-solar-system-shaders"* → *"continue, and as usual this is an opt-in feature, its not even on by default"* → *"../chromoFold is the C++ version which we will be allowed to test to if we dont chose to port it differently. Maybe it will be a choice in the config card"*).
> Mandate module: **E11.M500**.
> Number band: **500–599** per SDD-100 (first SDD in the new `chromofold-integration` session band; registered in `docs/sdd/SESSIONS.md`).
> Stage: **implement** (positioning locked; **Lane A / FM-index-first** phase-2 scaffolding landed 2026-07-20 — see Build status).
> Opt-in: **true — OFF BY DEFAULT.** Per the operator's standing opt-in directive and the verbatim above, ChromoFold is never on unless explicitly enabled; a box with no ChromoFold checkout, and every default profile, behaves exactly as today.

## Mission

Position **ChromoFold** — the GPU-resident, random-access, *searchable* entropy+index layer for the token- and
tensor-shaped data an LLM runs on (KV cache, weights, MoE experts, LoRA adapters, prompt caches, token streams) —
as an **opt-in, complementary** capability in sovereign-os, bound via its **native C ABI (`libchromofold`)**, and
lay out the phased way-forward so the actual binding lands deliberately, one subsystem at a time, without
duplicating the runtime's existing KV/quant/compression reference controllers.

ChromoFold is **two repositories, one system** (its own `chromoFold/docs/PROJECT_SYNC.md`):

- **`../warp-solar-system-shaders`** (`chromofold/`, `warp_compress/`) — the **Python + NVIDIA Warp prototype**:
  the **correctness oracle + performance floor** (341 tests), every stratum end-to-end. This is the repo SDD-300
  already integrated as the `warp-solar-system-shaders` catalog + Warp management panel — **not deprecated**; it
  is where ideas are validated cheaply and the honest end-to-end measurements live.
- **`../chromoFold`** — the **native C++20 / CUDA C++ engine** carrying the **stable C ABI**
  (`include/chromofold/chromofold.h`), the *production hot path* the operator chose to bind (verbatim: *"the C++
  version which we will be allowed to test to"*). **Status today: specified, pre-implementation** (M0/M1
  roadmap; `src/cuda/*.cu` + benchmarks are the skeleton). It ports the *proven, hot* prototype primitives and
  **must reproduce the prototype's output bit-for-bit** against frozen Warp golden vectors (`.cfwv`/`.cfrr`) —
  the prototype is the oracle, the porting map (`specs/05-porting-map.md`) the ledger, the format versions the
  shared truth.

This SDD reuses SDD-300's cross-repo pattern (committed metadata + a runtime checkout via an env root,
honest-degrade when absent) for both, rather than re-opening it.

## Problem — what ChromoFold is, and why it is *net-new* here

ChromoFold is **not** a `gzip`/`xz`/`zstd` competitor (those win bytes and lose navigation). It competes with a
raw KV cache / raw weight tensor / a separate index: it spends the GPU's cheap compute to buy back scarce **VRAM
and bandwidth**, and it stays **navigable in VRAM** — O(1)/O(log) random access and search (FM-index
`count`/`locate`/`predict`) *in the compressed domain*, decoded only where consumed. It composes **on top of**
quantization (it is the lossless entropy + random-access layer, not the quantizer). Core = numpy + NVIDIA Warp,
**no network I/O at import or use**; a native **C++20 / CUDA C++ engine with a stable C ABI** (`libchromofold`,
`cf_access_async` / `cf_rank_async` / …) is developed alongside it; portable `.cfold` container as interchange.
MIT, no telemetry, no license server — its own `INTEGRATION.md` has a "sovereign / on-prem (air-gapped)" section
aimed squarely at a deployment like this one.

**The catch this SDD resolves: heavy conceptual overlap with the existing native reference controllers.**
sovereign-os already ships CPU, deterministic, `#![forbid(unsafe_code)]`, dashboard-mirrored primitives in this
domain. ChromoFold must land as *net-new value only*, leaving those untouched:

| ChromoFold concept | Existing sovereign-os crate(s) — **untouched** | ChromoFold net-new value |
|---|---|---|
| KV cache / long context | `sovereign-kv-cache`, `sovereign-kv-window`, `sovereign-paged-kv`, `sovereign-kv-budget` | GPU-resident compressed KV with **attended-only decode**; asymptotic ~8.9× vs fp16 (grows with context) |
| Prompt / prefix compression | `sovereign-prompt-compress`, `sovereign-prefix-cache` | O(1) **span recovery** over a shared compressed prefix (30× store), N-seed multi-prefix |
| Quantization | `sovereign-quant-llm`, `sovereign-quant-block`, `sovereign-binary-quant`, `sovereign-nvfp4-runtime` | the **lossless entropy + random-access layer *on top of*** the quantizer — not a competing quantizer |
| MoE experts | `sovereign-moe-gate` | compressed expert bank, **decode only the routed** expert (~15×) |
| — (no analogue today) | — | **Search in the compressed domain** (FM-index `count`/`locate`/`predict`), a **`.cfold` portable container**, and an on-GPU **n-gram draft model** for speculative decoding |

Positioning rule (operator-selected): **new complementary capability.** Land only the net-new column — the
GPU entropy+random-access layer, compressed-domain FM-index search, and the `.cfold` container — as a distinct,
opt-in subsystem. The existing reference controllers keep their contracts and dashboards; ChromoFold is a
*sibling* GPU capability, **not** a replacement backend for them (that would be a much larger, deeper change and
is an explicit non-goal here).

## Engine provenance — a config-card choice (operator-floated)

The binding *mechanism* is settled (native C ABI, Rust FFI). What is **not** settled is *which engine
implementation backs it*, and the operator floated surfacing that as a build-time **config-card choice**
(verbatim: *"Maybe it will be a choice in the config card"* — the SDD-709 build-configurator pattern, like the
frontend/agent-runtime bake toggles). Because `../chromoFold` is **pre-implementation**, this choice is real and
time-dependent, not academic:

| Provenance option | What it means | Trade |
|---|---|---|
| **A · test/link `../chromoFold` (C++/CUDA)** | Bind the native C ABI `libchromofold` once its M1 lands; the operator's stated default (*"allowed to test to it"*). | device-native hot path; but external CUDA/C++ build dep + `unsafe` FFI + gated on the engine reaching M1 |
| **B · port it differently** | Reimplement the chosen primitive **natively in the Rust workspace** (no `unsafe` FFI, no external CUDA build; verified against the *same* Warp golden vectors) — or fall back to the Python/Warp prototype path. | fits the `#![forbid(unsafe_code)]` 721-crate core + air-gap build; but re-treads work chromoFold is already doing, and Rust-side CUDA is its own lift |

Whichever provenance wins, the **PROJECT_SYNC contract binds sovereign-os too**: any binding must reproduce the
Warp prototype oracle **bit-for-bit** against the frozen golden vectors (`.cfwv`/`.cfrr`) before any timing
number is trusted — the prototype is the floor, not an optional reference. This is the safety rail that makes a
provenance *choice* honest: the operator can swap engines behind one config-card control precisely because they
share one correctness oracle. Surfacing it is proposed (Q-500-F), gated on the pre-implementation timing
(Q-500-G); nothing is locked here.

## Required coverage (what the eventual build must satisfy — not built this session)

- **Binding mechanism = native C ABI (Rust FFI), operator-selected; the C-ABI source is `../chromoFold`'s
  `libchromofold`** (`include/chromofold/chromofold.h`), *not* the Warp prototype. The workspace is
  `#![forbid(unsafe_code)]`, so all `unsafe extern "C"` FFI MUST be quarantined in **one dedicated, audited
  `-sys` crate** (e.g. `sovereign-chromofold-sys`) with a thin **safe wrapper** (`sovereign-chromofold`) exposing
  only safe Rust. No `unsafe` leaks past the wrapper; the rest of the workspace never sees a raw C pointer.
  (Provenance option B — a native-Rust port — would replace the `-sys` crate with a safe-Rust primitive but keep
  the same wrapper surface and the same golden-vector contract; see Engine provenance above.)
- **Golden-vector correctness contract (PROJECT_SYNC).** Whichever engine backs the binding, its output MUST be
  **bit-for-bit** identical to the Warp prototype's frozen golden vectors (`.cfwv`/`.cfrr`) before any timing
  claim — the prototype (341 tests) is the oracle + floor. The `.cfold`/reference binary formats are the shared
  interchange; format-version bumps are shared truth across all three repos.
- **Cross-repo pattern = SDD-300's, reused.** ChromoFold is not host-resident. Commit any *metadata* (capability
  descriptor / `.cfold` fixtures) as the source of truth; do real work only when a checkout is resident via an
  env root; **honest-degrade** (exit-3 / offline, never fabricated success) when absent — exactly the
  `WARP_SHADERS_ROOT` + committed-catalog discipline SDD-300 chose (Q-300-B answered).
- **Opt-in, off by default** end to end: no default profile enables it; no always-on daemon; the sovereign-os
  build with no ChromoFold present is byte-identical in behaviour to today.
- **R10212 / SB-077 preserved:** any web surface is read-only; execution (compress/decode/search) reaches the
  operator only through the existing exec-rail (dry-run default, type-to-confirm, sudoers allowlist, OCSF span) —
  never a new arbitrary web-mutation path.
- **Air-gap honesty:** the offline guarantee (no network I/O in the core) is a *contract to test*, not a claim to
  print — the eventual `-sys`/wrapper CI asserts no network syscalls in the compress→access→save round-trip.

## Goals

- A single, agreed **positioning** (this doc): complementary, opt-in, C-ABI-bound, SDD-300-patterned.
- A registered **feature id** (`F-2026-119`, OPP) so the work is trackable and SDD-referenceable.
- A **phased plan** small enough that each phase is independently reviewable and gate-able.

## Non-goals

- **Any binding code this session** — no `-sys` crate, no wrapper, no dashboard, no osctl verb, no
  `feature-coverage.yaml` / `control-systems.yaml` / man-page changes. Those are later phases.
- **Replacing the existing kv/quant/compress/moe reference controllers** with a ChromoFold backend — explicitly
  out of scope (operator chose *complementary*, not *GPU backend for existing crates*).
- **Vendoring the repo as a git submodule** now — deferred to a later stage, mirroring SDD-300's Q-300-D
  (proposed, Stage N).
- **The Python `transformers` `ChromoFoldCache` path** as the primary binding — the C ABI is the chosen path for
  the Rust runtime; the Python drop-in cache is noted only as an alternative evaluated and set aside (see Q-500-A).

## Open questions (operator decisions before any build)

| Q | Question | Status |
|---|---|---|
| Q-500-A | Confirm **native C ABI (Rust FFI)** as the binding, with `unsafe` quarantined in one `-sys` crate + safe wrapper — over the Python `chromofold[torch]` drop-in cache in the gateway loop? | **answered** (operator chose native C ABI, 2026-07-20) — recorded for the record; the Python path is the documented alternative if `libchromofold` is not build-available on SAIN-01 |
| Q-500-B | Which subsystem binds **first**? KV cache (long-context VRAM win) · weights/MoE bank · or **FM-index compressed-domain search** (the one capability with *no* existing analogue)? | **answered** (2026-07-20) — **Lane A, FM-index-search-first**, confirmed by both this session and the native-engine session (which is landing `cf_count`/`cf_locate`/`cf_predict` in the stable C ABI) |
| Q-500-C | **CI posture** with no GPU / no SAIN-01 box present: keep the C-ABI/GPU steps hardware-gated and CI-test only the pure seams? | **answered** (2026-07-20) — yes, the SDD-724 split. The native `chromofold_capability.json` declares `conformance_requires_gpu: false` + a `null_arg_contract` (every entry point returns `CF_ERR_INVALID_ARGUMENT` on a NULL pointer *before any CUDA call*), so a linked box validates the real `.so` ABI without a GPU; the sovereign side ships a pure-Rust no-GPU header-seam conformance + a `#[cfg(feature=linked)]` null-arg seam test |
| Q-500-D | Cross-repo root: `WARP_SHADERS_ROOT` or a distinct `CHROMOFOLD_ROOT`? | **answered** (2026-07-20) — the native `chromofold_capability.json` sets `root_env: CHROMOFOLD_ROOT`, `root_default_env: WARP_SHADERS_ROOT`; the wrapper's `engine_root()` resolves exactly that order |
| Q-500-E | Vendor the repo(s) as submodule(s) for host-resident builds (SDD-300 Q-300-D analogue)? | proposed (Stage N) |
| Q-500-F | Surface **engine provenance** (A: link `../chromoFold` C++/CUDA C ABI · B: port differently in-workspace) as a **build-configurator config-card** control (SDD-709 pattern), so the operator picks the backend at build/config time? | proposed — operator-floated (*"Maybe it will be a choice in the config card"*) |
| Q-500-G | `../chromoFold` is **pre-implementation** (M0/M1 roadmap). Gate the C-ABI binding (provenance A) on its M1 landing, and use the Warp prototype (341-test oracle) as the interim floor + the fixture/golden-vector source for CI until then? | proposed (recommend yes) |

## Way forward (phased — each phase its own PR + gate)

1. **This SDD (positioning)** — design-lock; `F-2026-119` registered; no code. *(this session)*
2. **`sovereign-chromofold-sys`** — the `unsafe`-isolated FFI crate over `../chromoFold`'s `libchromofold` C ABI
   (build-gated on `libchromofold` presence + the engine reaching M1, Q-500-G; pure-Rust FFI-signature +
   `.cfold`-header contract tests in CI; golden-vector round-trip against the Warp oracle). *Provenance B swaps
   this for a safe-Rust primitive verified against the same goldens.*
3. **`sovereign-chromofold`** — the safe wrapper (no `unsafe` past this line); the chosen first subsystem
   (Q-500-B) exercised end-to-end behind the checkout root, honest-degrade when absent. **If Q-500-F lands:** an
   engine-provenance config-card control (build-configurator, SDD-709 pattern) selecting the backend behind this
   one wrapper surface.
4. **Cockpit surface** — a read-only panel/section surfacing ratio / resident-VRAM-saved / search availability
   (R10212 read-only; the d-nn dashboard pattern).
5. **osctl verb + the full chain** — `sovereign-osctl chromofold …` with dispatch + help + `feature-coverage.yaml`
   accounting + man-topic ownership + (if exec-rail-wired) `control-systems.yaml` + `EXPECTED_IDS` + sudoers
   preview line. Only here does the CLAUDE.md "new osctl verb carries a chain" obligation attach.

Every phase inherits the opt-in / off-by-default and R10212 / SB-077 discipline from this positioning.

## Build status (2026-07-20 — Lane A phase-2 landed)

Coordinated with the native-engine session's **Lane A** (FM-index-search-first). Shipped this session:

- **`crates/sovereign-chromofold-sys`** (steps 2) — the sanctioned-unsafe FFI carve-out mirroring the
  **committed** `chromofold.h` ABI v0 (`cf_status`, `cf_wavelet_view`, `cf_access_async`, `cf_rank_async` — the
  header's *"FM-index primitive"* —, `cf_embedding_gather_async`; `ABI_VERSION=0`, `CF_WAVELET_SB=8`). The
  `extern "C"` block + `unsafe {}` wrappers are behind the OFF-by-default `linked` feature, so the default build
  needs no `libchromofold` (which is still pre-implementation, Q-500-G) and the box behaves as today. Registered
  as the **second** sanctioned-unsafe crate (after `sovereign-simd`) in the workspace-hygiene allowlist + root
  Cargo.toml.
- **`crates/sovereign-chromofold`** (step 3) — the safe wrapper (`unsafe`-forbidden), the `CapabilityDescriptor`
  honest-degrade source-of-truth, and a `chromofold` **`info`/`selftest` binary** (the upstream CLI analogue +
  the precursor to step 5's osctl verb). FM-index `count`/`locate`/`predict` are present as
  **`AbiPending`** honest-degrade stubs — deliberately **not** bound until the native session commits their
  stable C ABI (the divergence this SDD forbids).
- **Committed fixture + conformance seam** (steps 4–5) — `tests/fixtures/wavelet_view_v0.json` + a pure-Rust,
  no-GPU, no-link conformance test asserting the bound ABI constants match the header and the fixture satisfies
  every `cf_wavelet_view` layout invariant. This is the sovereign-os side of the native session's "C-link
  conformance test", minus the link (which is hardware-gated, step 7).

**Search ABI bound (step 6, 2026-07-20)** — the native session shipped the handshake explicitly for us
(`chromofold_search.h`, `packaging/chromofold_capability.json`, committed `.cfwv/.cfrr/.cfrw/.cffm` fixtures,
`seam_check.c`/`conformance.c`), so binding is no longer a guess:

- **`sovereign-chromofold-sys`** now mirrors **both** committed headers — `chromofold.h` (v0 wavelet) **and
  `chromofold_search.h`**: `cf_rrrw_view`/`cf_fm_view` (`#[repr(C)]`, `c_int`-correct) + `cf_rrrw_access`/`rank`
  and the Lane-A **`cf_fm_count`/`cf_fm_ranges`/`cf_fm_locate`** — all behind the OFF-by-default `linked` feature.
  There is **no `cf_predict`** in the ABI — n-gram prediction is a *derived* capability, corrected accordingly.
- **`sovereign-chromofold`** resolves the engine root (`CHROMOFOLD_ROOT` → `WARP_SHADERS_ROOT`, Q-500-D) and its
  `CapabilityDescriptor` is now a faithful sovereign-side **mirror of the native `chromofold_capability.json`**
  (schema/library/headers/roots + the 8 capabilities, `fm_count` flagged `sovereign_os_first`). `count`/`ranges`/
  `locate` honest-degrade `Unavailable` (unlinked) / `NotImplemented` (linked; host→device marshalling is step 7);
  `predict` is derived + `NotImplemented`.
- **Header-seam conformance** — a committed `reference_formats.json` mirroring the native `reference_fixtures`,
  plus a no-GPU test that, when an engine root is resident, validates the **real** `.cfwv/.cfrr/.cfrw` magic +
  `u32`-LE version against the manifest (the sovereign side of `seam_check.c`). **Verified green against the real
  native fixtures** at `CHROMOFOLD_ROOT=../chromoFold`; honest-degrades (skips) when absent.

**osctl verb bound (step 5, 2026-07-20)** — `sovereign-osctl chromofold info|selftest`: a read-only bash
dispatch shelling `scripts/inference/chromofold.py`, which reads the native `chromofold_capability.json` from the
resident checkout (`CHROMOFOLD_ROOT`→`WARP_SHADERS_ROOT`) and **honestly reports the offline state (exit 0)** when
absent — a diagnostic, never a mutation (R10212/SB-077). `selftest` runs the no-GPU header-seam check against the
resident fixtures. Full §1g chain landed: dispatch + help text + `feature-coverage.yaml` cli_only waiver (the
cockpit panel is step 4, deferred) + `models` man-topic (`## chromofold` source + `.SS chromofold` roff) +
`test_chromofold_cli_contract.py` (8 cases). No exec-rail/`control-systems.yaml`/sudoers — the verb is read-only.

**Cockpit panel landed (step 4, 2026-07-20)** — the read-only ChromoFold status panel: `webapp/chromofold/index.html`
(app-shell-adopted; availability tile + the 8-capability map with the Lane-A `fm_count` badge + an honest offline
banner; fetches `/chromofold.json`, never fabricates), a read-only API daemon `scripts/operator/chromofold-api.py`
(:8147, shells the `chromofold.py` helper, `POST`→405) + `sovereign-chromofold-api.service` (R171-hardened,
loopback), a `dashboard-catalog.yaml` `science`-category entry, the generated `dashboard-routes.yaml` route
(port auto-parsed from the daemon), the app-shell **GROUPS** entry (re-synced into all 63 adopted panels), and
the `feature-coverage.yaml` move from a cli_only waiver to `coverage: chromofold → [chromofold]` (the verb now has
a dashboard home). Read-only end to end (R10212/SB-077); the panel shows "offline" until step 7 gives it live data.

> Note: `sovereign-osctl master-dashboard render` is currently blocked by a **pre-existing** port collision from
> the just-merged F-2026-070 (the networking triplet `d-12-networking`/`edge-firewall`/`network-edge` all share
> :8139 in `dashboard-routes.yaml` at HEAD). ChromoFold's route (:8147) is unique and not involved; the collision
> reproduces on HEAD without any ChromoFold change. Left for the networking workstream — out of SDD-500 scope.

**Remaining:** only step 7 (real link + host→device marshalling + bit-for-bit golden-vector round-trip vs the
Warp oracle — hardware-gated). Provenance option B (native-Rust port) and the config-card (Q-500-F) remain open
operator calls.

## Cross-references

- **SDD-300** (`docs/sdd/300-warp-management-panel.md`) — the prior integration of the *same repo*
  (`warp-solar-system-shaders`); source of the committed-metadata + `WARP_SHADERS_ROOT` + honest-degrade pattern
  and the submodule-deferral precedent (Q-300-B / Q-300-D).
- **SDD-724** (`docs/sdd/724-adapter-eval-gate-producer.md`) — the "only the hardware step is gated; the pure
  seams are CI-tested via an injected stand-in" split reused in Q-500-C.
- **Existing reference controllers (untouched):** `crates/sovereign-kv-cache`, `-kv-window`, `-paged-kv`,
  `-kv-budget`, `-prompt-compress`, `-prefix-cache`, `-quant-llm`, `-quant-block`, `-binary-quant`,
  `-nvfp4-runtime`, `-moe-gate`.
- **Source repos:** `../warp-solar-system-shaders` (Python/Warp prototype — oracle/floor): `INTEGRATION.md`
  (HF + sovereign/on-prem), `chromofold/README.md`, `docs/chromofold_positioning.md`. **`../chromoFold`** (native
  C++20/CUDA engine — the C-ABI binding target): `README.md`, `include/chromofold/chromofold.h` (the stable C
  ABI), `specs/` (00-constitution … 05-porting-map), `docs/PROJECT_SYNC.md` (the two-repos-one-system contract +
  golden-vector oracle discipline).
- **SDD-709** (`docs/sdd/709-agent-layer-wizard-and-build-configurator.md`) — the build-configurator config-card
  pattern reused in Q-500-F for the engine-provenance choice.
- **F-2026-119** — the findings-ledger entry this SDD graduates from (`docs/review/phase-1/99-findings-ledger.md`).
- Hard rules: R10212 (web never arbitrarily mutates), SB-077 (never fabricate), the opt-in-by-default standing
  directive.
