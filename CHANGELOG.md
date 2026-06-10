# Changelog

All notable changes to sovereign-os land here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
sovereign-os uses date-based phase markers rather than SemVer
until Stage 3+ when a public-distributable artifact lands.

Cross-references:
- Decisions: `docs/decisions.md` (every D-NNN entry)
- SDDs: `docs/sdd/INDEX.md` (every spec)
- Handoffs: `docs/handoff/` (cold-start anchors)

## [Unreleased] — Stage-2 onset (post-Gate-5)

### Added — ternary BitLinear MLP: the engine composes a real FFN block (M073) (2026-06-10)

The bitlinear-core crate had a real single-layer ternary projection
(`BitLinearLayer`) but the engine only ever ran it as a one-layer
self-check. `BitLinearMlp` (new `crates/sovereign-bitlinear-core/src/mlp.rs`)
composes the primitive into the transformer **feed-forward block** — the
dominant ternary compute — with a ReLU between layers and the standard
`d_model → d_ff → d_model` `ffn()` constructor. It preserves both core
invariants *across the stack*: every layer's inner products stay
multiplication-free (summed `OpCount`), and the stacked forward is
bit-for-bit identical to a dense multiply-based reference (ReLU + ±1 muls
are exact) — proven by `forward_matches_dense_reference` over `Base3` +
`TwoBit` packings, plus deep-stack (3-layer), ReLU-gating, op-accounting,
dim-chain-validation, and serde tests (7 new, all green on
`cargo +1.88.0`). The cortex's Conductor self-check
(`compute.rs::ternary_kernel_live`) now runs a real two-layer FFN block
instead of one layer, asserting mul-free composition end-to-end — so
`kernel_verified` means "a real multi-layer ternary FFN ran
multiplication-free," a strictly stronger guarantee. Moves the runtime a
concrete step from "single kernel callable" toward "a network block that
runs." Additive: two new `BitLinearError` variants (`EmptyStack`,
`StackShapeMismatch`); no existing API changed.

`BitLinearMlp::forward_residual` then completes the block into a real
transformer **FFN sublayer** (`y = x + block(x)`, the residual-wrapped
shape a decoder uses), guarded to `input_dim == output_dim`. Tests prove
the residual is exactly `x + block(x)`, that an all-zero block is the
residual *identity* (the trainability property deep stacks rely on), and
that a non-square block is rejected — the missing piece to drop the
multiplication-free ternary FFN into the residual stream where the quant
decoder block today still runs a float SwiGLU. Additive variant
`ResidualShapeMismatch`.

### Added — guardian dropout metrics + flap alert (M084 R14127–R14133) (2026-06-10)

A single Tetragon-stream EOF is self-healing (BindsTo + Restart=always close
the blind window in ~1–2s); what must page is **churn**. The guardian now
emits `sovereign_os_auditor_stream_eof_total` on the EOF fall-through
(inventoried), and `sovereign-os-auditor.rules.yml` pages
`SovereignOsAuditorStreamEofChurn` (warning) at ≥3 dropouts in 30m — the
dump's flapping OPNsense/SD-WAN management-path scenario — with a runbook
section routing the operator to the firewall/lease behavior, not the
guardian (which is recovering itself).

### Added — M084: OPNsense/SD-WAN boundary contract catalogued + guardian dropout prevention built (audit gap #3 closed) (2026-06-10)

The audit's gap #3: "the VLAN concept is catalogued (M003) but the firewall
interface + Tetragon-socket-dropout gotcha isn't." Two-part closure:

- **Built first**: the transposition dump's prevention (lines 761–765,
  verbatim) was only half-implemented — `sovereign-guardian-core.service`
  gains the required `BindsTo=tetragon.service`, and guardian-core.py's
  read-loop EOF fall-through (which silently returned 0, hiding the
  "blinding your real-time exploit containment system" event) now logs
  `[EOF] … perimeter blind` + exits nonzero so the `Restart=always` recovery
  is a journal-recorded failure-restart.
- **Catalogued**: `M084-opnsense-sdwan-boundary-contract-tetragon-dropout-resilience.md`
  — 170 R-rows decomposing the dual-NIC Zero-Trust topology (VLAN 100
  management/telemetry on the Intel 2.5GbE; VLAN 200 model-ingestion with NO
  outbound WAN on the Marvell 10GbE), the firewall observation surface
  (E11.M8 reachability ladder), and the gotcha/prevention pair; the
  reconfig-detector, dropout metrics, and flap alert are catalogued as
  explicitly pending. Catalog totals: 82 milestones / 14,080 R-rows
  (lockstep across INDEX, MASTER-PLAN, SHIPPED + gate literal); SHIPPED
  gains an M084 section citing the prevention commit.

### Added — M083: DFlash speculative decoding catalogued (audit gap #2 closed) (2026-06-10)

The 2026-06 catalog audit named DFlash as under-catalogued — "survives only as
one incidental clause; no dedicated epic, unlike Ling-2.6 / Nemotron-3 which
got full treatment." `backlog/milestones/M083-dflash-speculative-decoding-fast-path.md`
closes it: 10 epics / 17 modules / 85 features / 170 R-rows decomposing the
operator's verbatim dump-tail addition (transposition dump 1115–1131: "3 times
faster" on code, "does not work on creative tasks in general") + the SDD-026
design (task-type gating table, ENABLE/DISABLE override knobs with
DISABLE-wins, vllm/llama_cpp/transformers argv shaping, disabled-no-install
graceful fallback, `sovereign_os_dflash_*` Layer-B metrics) + the R161 router
task-type closure. Layer-5 benchmarking + draft-model tuning catalogued as
explicitly pending. Catalog totals updated in lockstep: 81 sovereign-os
milestones / 13,910 R-rows (INDEX, MASTER-PLAN, SHIPPED roll-up, and the
SHIPPED-gate literal).

### Added — gateway Grafana dashboard: the sovereignty tripwire is now visual (2026-06-10)

`docs/observability/dashboards/sovereign-os-gatewayd.json` completes the
gateway observability triad (metrics → alerts → dashboard): headline
never-cloud-spill tripwire stat (HOLDS/BROKEN, pairs with the
SovereignGatewayCloudSpill alerts), cloud-spill counter, live surfaces,
request + dry-run rates, decisions by disposition, routing per SRP role, M030
World-Model prior-agreement ratio, and the force_local doctrine panel. The
json-valid gate's sanctioned metric-family list gains `sovereign_gateway_*`
(the daemon's own `GET /metrics` namespace, scraped directly over HTTP — same
dedicated-binary precedent as `sovereign_telemetry_*`).

### Fixed — small operational symmetry + diagnosability gaps (2026-06-10)

- **`make uninstall` now removes what `make bins` installs.** It removed
  sovereign-osctl + lib + manpage but left the three Rust binaries behind in
  `PREFIX/bin`. Verified symmetric via a DESTDIR sandbox.
- **Layer-3 `make lint` failures now show WHICH tests broke.** The
  makefile-execution harness captured the 4644-test pytest output and then
  printed only `FAIL — make lint failed`; a CI flake on 2026-06-10 was
  diagnosable only by inference from the sibling layer-1 job. On failure the
  harness now prints the FAILED/ERROR lines + the summary tail.

### Added — the never-cloud-spill invariant now pages (2026-06-10)

The gateway daemon has tracked its sovereignty tripwire since birth
(`sovereign_gateway_never_cloud_spill_holds` on `GET /metrics`), but nothing
*paged* on it — a spill would sit unread in a ledger until someone looked at a
dashboard. New `config/prometheus/alerts/sovereign-gatewayd.rules.yml`:

- **SovereignGatewayCloudSpill** (critical, deliberately `for:`-less — one
  confirmed scrape pages): the holds-gauge dropped to 0, meaning a decision
  routed to the cloud plane despite `force_local`. An incident, never tuning.
- **SovereignGatewayTripwireUnmonitored** (warning, 10m): `absent()` on the
  gauge — an invariant nobody can see is not enforced from the operator's
  seat (daemon down / scrape job broken / bind moved).

Runbook sections (meaning → diagnosis → fix, with the scrape-job snippet —
the daemon serves `/metrics` itself, no textfile collector) added to
`docs/operator/m060-deployment-guide.md`; per-file contract gate
`tests/lint/test_sovereign_gatewayd_alerts_contract.py` reads the emitted
metric set straight out of `lib.rs` so an exporter rename kills the alert
file in CI instead of leaving a dead alert.

### Added — gateway `simple` op: a client need not build a full CortexRequest (2026-06-09)

`POST /v1/messages` required a full `CortexRequest` (7 axes + workload +
pressures + 12-axis reward). The new `simple` op lets a client send only the
task `axes` + an explicit `expected_quality` dial (+ optional `query_topic` /
`profile`); the gateway fills the engine-internal fields and runs it like
`infer`. Additive — the full `CortexRequest` path is unchanged.

- NDJSON `{"op":"simple-infer","request":{"axes":{…},"expected_quality":0.8}}`
  and HTTP `POST /v1/simple` → `{"kind":"decision",…}`. Verified live (minimal
  `{axes, quality}` → a real conductor/commit decision).

> **⚠ Operator review needed on the fill-in defaults.** The gateway invents no
> *hidden* quality policy — `expected_quality` is a **required** field, so the
> client always supplies the quality dial — but the convenience does choose
> conservative defaults for the remaining under-specified (mostly mechanical or
> non-decision-affecting) fields, and in a sovereign system those are a policy
> you should own. They are deliberately transparent and tunable in
> `SimpleRequest::into_cortex`:
> runtime pressures → **idle** (no live telemetry → assume capacity);
> `allow_cloud` → **false** (sovereign default); workload class + precision →
> derived from `axes.complexity` (simple → CPU/ternary, complex → GPU/fp16);
> `min_vram_gb` → 0 (don't over-constrain placement); `profile` → `careful`;
> `model_params` → 7B (footprint estimate only); reward → `expected_quality`
> spread over the competence axes with risk/latency/cost low. Adjust or reject
> these in review — the op is isolated and easy to retune or drop.

### Added — gateway best-of-N: a read-only `deliberate` op (2026-06-09)

The gateway exposed only the single-pass `tick`; the cortex's premium decision
mode — best-of-N `deliberate` (fork one branch per candidate, return the
winner + every assessment + the branch tree) — was unreachable. Added a
`deliberate` op whose inputs are all **explicit client choices** (no
product-default guessing): the shared `request`, the candidate `RewardVector`s
(the N), and the compute `tier` (`reflex` … `experimental`, the fanout dial).

- NDJSON `{"op":"deliberate","request":{…},"candidates":[…],"tier":"…"}` →
  `{"kind":"deliberation",…}`; HTTP `POST /v1/deliberate` with the same body.
- **Read-only** like `explain`: it decides but does not learn or touch the
  ledger (verified the ledger stays 0 after a deliberation), with the same
  `force_local` Privacy policy. Verified live over HTTP (best-of-3 → winner
  committed, `candidates_considered=3`).
- +4 tests (lib + http: best-of-N, read-only, bad body → 400, GET → 405). 29
  unit + 9 integration tests pass; `fmt` + `clippy -D warnings` clean on 1.88.0.

### Added — `sovereign-chat` is runnable: multi-turn conversation with bounded history (2026-06-09)

`sovereign-chat` composes `sovereign-llm` into a stateful chat session (record
the turn → render the role-tagged history → generate → append) with **bounded
history** for endless dialogue, but was lib-only. Added a `[[bin]]` + demo (the
workspace's 8th runnable binary) that runs a session on a small real
`SovereignLlm` and shows the distinct behaviour — the history grows to the cap
(system + 4 non-system messages) then **stays bounded** as the dialogue
continues, the earliest turns dropped while the system message is always kept.

The 6 model crates moved from dev-dependencies to dependencies (no new
workspace crates; Cargo.lock unchanged). `--help` supported. `fmt` +
`clippy -D warnings` clean on pinned 1.88.0; the 8 lib tests still pass. This
completes the runnable set of the four distinct decision/execution paths over
the runtime: routing (`gatewayd`), cost (`serve`), agent (`agent-runtime`),
conversation (`chat`).

### Added — `sovereign-agent-runtime` is runnable: a tool-using ReAct agent on the real engine (2026-06-09)

`sovereign-agent-runtime` bridges the real quantized inference engine
(`sovereign-llm`) into the ReAct loop (`sovereign-agent-loop`) but was lib-only.
Added a `[[bin]]` + demo (the workspace's 7th runnable binary) that drives the
agent two ways:

- **Real runtime** — a small `SovereignLlm` drives the loop end-to-end, proving
  the inference stack + agentic layer compose into one running agent. (Random
  weights → no tool call, one-step gibberish answer; the point is the real
  engine drives the control flow.)
- **Scripted ReAct** — a deterministic responder emits `[[tool:upper|sovereign]]`,
  so the run shows the full loop: generate → dispatch the tool → feed the
  observation back → final answer (`upper("sovereign") = "SOVEREIGN"`).

The 7 model crates the binary needs to build a `SovereignLlm` moved from
dev-dependencies to dependencies (no new workspace crates; Cargo.lock
unchanged). `--help` supported. `fmt` + `clippy -D warnings` clean on pinned
1.88.0; the 4 lib tests still pass.

### Added — `sovereign-serve` is runnable: the $0-aware serving assembly runs end-to-end (2026-06-09)

`sovereign-serve` composed the cache / complexity / token-meter crates into one
`serve()` call but was lib-only — the assembly never ran. Added a `[[bin]]` +
demo session (the workspace's 6th runnable binary) that drives requests through
it, showing the cost-aware behaviour the crates exist for:

- a repeated request is a **cache hit** — `$0`, the model never runs (`in=0 out=0`);
- each request's **complexity tier** is estimated for routing;
- a request that would blow the **token budget** is **refused before generating**
  (`16 + 50 > 40`), not run and charged.

The generator is a deterministic model stand-in (the point is the orchestration,
not the text), mirroring the cortex binary's demo mode. `--help` supported.
With no args it runs the demo; given `PROMPT [PROMPT…]` it serves each on an
unlimited budget (a repeated prompt resolving as a `$0` cache hit) — an actually
usable cost-aware serving tool, not just a fixed demo. `fmt` +
`clippy -D warnings` clean on pinned 1.88.0; the 6 lib tests still pass.

### Added — the World-Model prior now acts: a surprise engages deeper reasoning (2026-06-09)

The M030 prior was observe-only; now it influences compute — conservatively.
When a **confident, well-observed** prior contradicts the live verdict
(`confidence ≥ 0.75`, `observations ≥ 3`), the decision is a "surprise" (the
task is resolving against history) and the cortex engages a bounded HRM
recurrent pass (M080) — the same deeper-reasoning mechanism an uncertain verdict
already triggers.

Crucially, this **never changes the verdict** — it only adds a recurrent pass
(and the speculative control-word flag) for extra scrutiny before the Auditor
sees the branch, so it can never cause a wrong commit. Thresholds are named
constants (`WORLD_MODEL_SURPRISE_CONFIDENCE` / `_MIN_OBS`). Locked by a test:
seed a confident Prune history, then a committing request engages reasoning
while keeping its Commit verdict. Cortex suite now 56 tests; `fmt` +
`clippy -D warnings` clean on pinned 1.88.0.

### Added — cortex composes the World-Model plane (M030): learned routing-outcome priors (2026-06-09)

The cortex assembly gains a ninth real engine. `sovereign-cortex` now owns a
`sovereign-world-model` (M030) that learns `(task-topic, routing-role) →
outcome` dynamics across requests — distinct from the symbolic planner's fixed
effects (this learns from data, Dreamer-style):

- **`Cortex::learn`** observes the transition on **every** outcome (commit,
  prune, expand, need-more-compute), not just commits, so the model can predict
  prunes too. Separate from the commit-gated Memory-OS admission.
- **`Cortex::tick`** consults the model for a learned prior and annotates the
  decision with `Option<WorldModelPrediction>` — `expected_action`, `confidence`
  (modal probability), `observations` (history depth), and `agrees_with_verdict`
  (a mismatch flags a task resolving differently than history). Honest `None`
  for a cold pair — no fabrication.
- New `WorldModel::pair_observations(state, action)` (additive) backs the
  history-depth field.
- The prior is read-only in `tick` and learned only in `learn`, so there's no
  intra-request leakage: a cold pair predicts `None`, and the prediction only
  becomes informative once the pair has resolved before.
- Locked by a cortex test (cold → None; after one observation → agreeing
  prediction at confidence 1.0) + a world-model test. All 53 existing cortex
  tests still pass; `fmt` + `clippy -D warnings` clean on pinned 1.88.0; the
  gateway (which serializes `CortexDecision`) passes unchanged — the new field
  is additive.

### Added — `sovereign-gatewayd` deployable: systemd unit + Makefile install + e2e transport tests (2026-06-09)

Turns the gateway daemon from a buildable binary into a deployable managed
service:

- **`systemd/system/sovereign-gatewayd.service`** — runs `sovereign-gatewayd
  --http`, loopback-by-default (`SOVEREIGN_GATEWAY_ADDR`, with the documented
  `.d/bind.conf` override pattern), `Restart=on-failure`. Carries the full R171
  defense-in-depth posture; since the daemon is pure in-memory (reads/writes no
  files) it runs cleanly under `ProtectSystem=strict`. Passes all 245
  systemd-hardening lint assertions + the fleet/posture/timer gates.
- **Makefile `bins`** now builds + installs `sovereign-gatewayd` to
  `PREFIX/bin` alongside `sovereign-telemetry` / `sovereign-resource-control`,
  matching the `ExecStart` path.
- **End-to-end transport tests** (`tests/transports.rs`): spin the real binary
  on an ephemeral port and exercise both transports over actual sockets — NDJSON
  TCP (infer→ledger across one connection; malformed line → error, not drop) and
  HTTP (health 200, `POST /v1/messages` runs the engine, `/metrics` reflects it,
  404/400). Locks the socket plumbing the unit tests can't reach. 25 tests total.

### Added — `sovereign-gatewayd` HTTP/1.1 surface: real clients reach the engine (2026-06-09)

The gateway daemon spoke only a custom NDJSON line protocol; now it also serves
the bind paths the M048 manifest advertises over plain HTTP, so curl / an MCP
bridge / the cockpit can hit the engine directly:

- New `--http` transport (pure-std HTTP/1.1, thread-per-connection,
  `Connection: close`; request line + headers + `Content-Length` body parsed by
  hand — no async runtime, no new deps, honors `unsafe_code = forbid`).
- Routes: `GET /health`, `GET /manifest`, `GET /admin/ledger` (the CostRouteLedger
  bind path), `GET /metrics`, and `POST /v1/messages` (Anthropic surface) /
  `POST /v1/infer` / `POST /mcp` taking one JSON `CortexRequest` → the tagged
  decision. Wrong verb on a known route → 405; unknown → 404; malformed body →
  400; engine refusal → 422.
- **`GET /metrics`** renders the live ledger + health as Prometheus
  text-exposition (`sovereign_gateway_requests_total`, `…_route_total{role}`,
  `…_decisions_total{disposition}`, `…_cloud_spills_total`,
  `…_never_cloud_spill_holds`, `…_live_surfaces`, and — once the engine learns —
  `…_prediction_total` / `…_prediction_agreements_total`) so the existing
  node_exporter→Grafana cockpit can chart the daemon with no new pipeline —
  the operator-visible surface the SHIPPED bar requires. Verified live via curl.
- **Request-size caps (DoS hardening).** A `Content-Length` over 1 MiB → `413`
  *before* any buffer is allocated; an over-8 KiB request line or header line,
  or more than 100 headers → `431`; an over-1 MiB NDJSON line → error + close.
  Each is read through a fresh `take`, so a client can't exhaust the daemon's
  memory with a huge or unterminated request on either transport. Cortex
  requests are a few KB. Verified live (4 GiB body → 413; 9 KB header → 431).
- **Connection cap (flood back-pressure).** Both accept loops (now DRY'd into
  one `serve()`) bound concurrent handler threads (default 256, override
  `SOVEREIGN_GATEWAY_MAX_CONN`); over the cap a connection is accepted and
  closed immediately rather than spawning unbounded threads. Matters once the
  daemon is exposed past its loopback default. Tested with the cap at 2.
- **Survives a failed handler-spawn.** The accept loop uses
  `Thread::Builder::spawn` and, if a handler thread can't start under resource
  pressure, drops that one connection and keeps serving rather than panicking
  the accept loop and taking the whole daemon down. The `ConnGuard` drops on the
  failure path, so the active-connection counter stays correct.
- The HTTP routing (`http::respond`) is pure and routes through the same
  `GatewayServer::handle` as the line protocol, so the two transports can never
  diverge. Verified live (curl + raw-socket): `GET /health` 200,
  `POST /v1/messages` 200 with a real decision, ledger advancing, no cloud spill.
- +9 unit tests (19 total in the crate). `cargo fmt`/`clippy -D warnings` clean
  on the pinned 1.88.0 CI toolchain. The full Anthropic content-block schema
  remains a later layer; this v1 carries the typed cortex request/decision.

### Fixed — `cargo workspace` CI job green: the `sovereign-telemetry` orphan repaired (2026-06-09)

The `cargo workspace` check was RED **on `main` too** (pre-existing, not a
regression): `sovereign-telemetry`'s binary and `sovereign-pressure-reactions`'
test fixtures were written against an OLD API of three model crates
(`sovereign-pressure-sensors`, `sovereign-hardware-load-sample`,
`sovereign-observability-fabric`) that was later slimmed to pure
canonical-constructor snapshots — deleting `PressureSnapshot::{from_psi,
from_readings}`, `AxisReading::new`, `LoadSnapshot::{update_target, update_gpu}`,
`ObservabilityFabric::update_source`, and the free parsers (`parse_proc_stat_cpu`,
`parse_gpu_csv`, `parse_psi_some_avg10`, `parse_thermal_zone_temp`,
`cpu_util_pct`, `GpuTelemetry`). The two consumers were never updated.

Repaired **without touching the model crates** (they stay pure typed snapshots):
- The deleted OS-parsing helpers now live **in the `sovereign-telemetry` binary**
  — where reading `/proc`, `/sys`, and `nvidia-smi` belongs — and feed the model
  types through their public fields. The deleted mutator methods become direct
  public-field assignment on the canonical snapshots. The binary builds, runs as
  a real probe on a dev host (live PSI / `/proc/stat` CPU / thermal verdicts /
  adaptive reactions), and emits both JSON and Prometheus surfaces.
- `sovereign-pressure-reactions`' test fixtures rebuilt the same way
  (`free_canonical` + field set; a `set_util` helper for load fixtures).

`cargo check --workspace --all-targets` now exits 0; affected crates' tests green;
`cargo fmt` clean.

### Added — `sovereign-gatewayd`: the first persistent runnable service (2026-06-09)

Promotes the one-shot `sovereign-cortex` engine (PR #17) into a long-lived
**daemon** behind the M048 Module 4 `sovereign-gateway` contract — closing the
audit's "engine catalogued + assembled but nothing runs as a service" gap. New
`sovereign-gatewayd` binary crate, pure-std (no async runtime; honors the
workspace `unsafe_code = forbid`):

- **Stateful, learning engine.** The daemon owns one process-wide `Cortex`;
  every committed decision is admitted back into Memory-OS via `act_and_learn`
  (M016 learning without retraining), so recall grows across requests — verified
  live (recall 2 → 3 on a replayed request) and across *separate* TCP
  connections (a second client observes the first's accumulated ledger +
  learned memory). A CLI cannot do this.
- **NDJSON serving core** (`GatewayServer::handle_line`) shared by three
  transports in `main`: TCP (thread-per-connection, default `127.0.0.1:8787`),
  `--stdio` (MCP/Claude-Code shape), and `--selftest`. Ops: `infer` / `manifest`
  / `health` / `ledger`.
- **Gateway responsibilities made real, not decorative:** `force_local` policy
  forces `allow_cloud = false` before the router (Privacy + Routing on the
  client's behalf, per the provider-inversion doctrine); a live cost/route
  `Ledger` (surface 6: route distribution + committed/refused/learned counts);
  the **never-cloud-spill** invariant tracked as a process-level tripwire and
  asserted to HOLD across the full demo session. 4 of the 6 canonical surfaces
  marked `Live`.
- Locked by 10 unit tests (malformed input, every op, force-local override,
  cross-request learning, invariant) + an `examples/demo_request.rs` client
  payload generator. `cargo clippy` clean, `cargo fmt` clean.

### Added — MS048 scheduler observability + cross-repo consumer (Solution 1 ← Solution 2) (2026-06-05)

The runtime side of the selfdef MS048 Goldilocks Scheduler — sovereign-os
renders the scheduler READ-ONLY (boundary discipline: the decision lives in
selfdef) and now also CONSUMES it:

- **Decision observability**: 3 Grafana panels (route distribution + hibernate
  + ring-window size) + the `SelfdefSchedulerHighHibernateRate` alert (>50%
  deferral 15m) on the new `selfdef_scheduler_decisions_*` metrics; the cockpit
  `scheduler-status.py` card (40) parses + surfaces decision metrics; the 8
  scheduler alert `runbook_url`s repointed to the real selfdef runbook (were
  dangling).
- **Cross-repo consumer bridge** (`scripts/inference/scheduler-bridge.py`):
  the runtime gateway consults `selfdef-scheduler-decide` (read-only subprocess)
  per the integration contract — builds a task descriptor, parses the Decision,
  maps route → backend tier (blackwell→oracle / rtx3090→scout / cpu→cortex /
  hibernate→defer), honoring **honor-Hibernate · map-route→tier · read-only**.
  Graceful-offline: binary absent/errored → `scheduler_available=False` so the
  gateway falls back to its own SDD-011 routing (never crashes, never fabricates
  a route). Maps route → runtime service (blackwell→Oracle Core / rtx3090→Logic
  Engine / cpu→Pulse). Locked by `tests/unit/test_scheduler_bridge.py` (10
  cases, fake binary). Registered in the inference INDEX.
- **Router opt-in advisory** (`router.py`): when `SOVEREIGN_OS_CONSULT_SCHEDULER=1`
  (default OFF — routing then unchanged), the router surfaces the scheduler's
  hardware-tier advisory as the `X-Sovereign-Scheduler-Advisory` response header
  **without changing the routed tier** (the runtime's `classify()` stays
  authoritative). Fail-safe — a missing/broken scheduler never affects routing.
  Locked by `tests/unit/test_router_scheduler_advisory.py` (5 cases). Making the
  advisory authoritative remains a separate explicit operator step.

### Added — D-09 hardware-pressure cockpit dashboard driven to PRODUCTION (full 8-surface stack) (2026-05-27)

The M060 D-09 dashboard existed only as an HTML shell fetching `/api/hardware/pressure`,
`/api/hardware/zfs/datasets`, `/api/hardware/stream` — **dead endpoints, no backend** (the
"reached the shell but not prod" gap). Built the full §1g 8-surface stack, sovereign-os-native
(zero selfdef-boundary — pure runtime hardware signals), stdlib-only (sovereignty: zero deps):
- **core** `scripts/hardware/hardware-pressure.py` — unified pressure aggregator: Linux PSI
  (`/proc/pressure/{cpu,memory,io}` some/full × 10s/60s/300s, reusing the memory-pressure.py
  parser), dual-CCD topology (M070, per-core busy% from `/proc/stat`), GPU via `nvidia-smi`
  CSV, ZFS pool latency + per-dataset sync via `zpool`/`zfs`, scheduler backpressure (M058).
  Every probe degrades gracefully to `null` when a kernel iface/tool/device is absent — NEVER
  crashes (verified on this GPU-less/ZFS-less/PSI-less dev host). CLI: `status`/`psi`/`zfs --json`.
- **cli** `sovereign-osctl hardware-pressure <verb>` dispatch.
- **api** `scripts/operator/hardware-pressure-api.py` — read-only HTTP (stdlib http.server,
  loopback-default) serving the exact dashboard contract + an SSE `/api/hardware/stream` +
  hosting the webapp; mutation verbs → 405 (pressure is observed, not set).
- **webapp** the D-09 dashboard, now served by + wired to its real API.
- **service** `sovereign-hardware-pressure-api.service` (R171 defense-in-depth hardened).
- registered in the master-dashboard aggregator route table (port 8097, `/hardware-pressure/`).
- **tests** `tests/lint/test_hardware_pressure_api_contract.py` — 11 cases locking the full
  stack live (daemon spawn + the 3 dashboard endpoints + webapp serve + read-only 405 + osctl
  dispatch + R171 hardening), all green.

Verified end-to-end via live curl. SDD-040's stale D-09 row updated MISSING → shipped. This is
the first cockpit dashboard taken catalog→shell→**production** through every layer; the other
d-01…d-20 shells follow the same template.

### Fixed — repo-wide `cargo clippy` green (rust CI job no longer blocked at the clippy step) (2026-05-27)

`cargo clippy --workspace --all-targets -- -D warnings` (the rust CI job's step after
fmt) was RED with **424 findings across 124 crates** — the generated crate set was never
run through clippy (same root as the fmt gap). Resolved with clippy 0.1.88 (exact CI
toolchain): two `cargo clippy --fix` passes + one `--unsafe-fixes` pass auto-resolved the
bulk (collapsible_if ×67, manual_*/unnecessary_*/doc_* …), then the residual was fixed by
hand — 11 intentional inherent methods (`next()` widget-advance + a 10-arg / 8-arg
constructor) got targeted `#[allow]`s, `ItemPin` gained the `is_empty()` clippy expects,
three `.get(k).is_none()` → `contains_key`, an index loop → slice iterator, a
`.max().min()` → `.clamp()`, two nested `format!` flattened, two `if`-with-identical-blocks
collapsed (behaviour-preserving — verified non-bugs), and ten rustdoc list-formatting
lints fixed. One `clippy --fix` over-reach was caught + corrected: it dropped a
`cfg(test)`-only `Modifiers` import from `shortcut-cheatsheet` (correct for the lib target,
but the test used it) — re-imported inside the test module. Final state: clippy exits 0,
`cargo fmt --check` clean. 126 source files; all changes behaviour-preserving (no real
bugs surfaced — the catalog crates were correct, just un-linted).

### Fixed — repo-wide `cargo fmt` unblocks the rust CI job (2026-05-27)

`cargo fmt --all --check` (the rust job's first step in `test.yml`) was RED across
the crate set (469 source files) — crates written/generated with non-canonical
formatting that rustfmt reflows. Since `cargo fmt --check` is the first step of
the rust job, its failure blocked clippy/test/build from even running. Ran
`cargo fmt --all` (toolchain 1.88.0's rustfmt — identical to CI; no `rustfmt.toml`,
defaults match), making `--check` exit 0. Purely formatting (rustfmt preserves all
tokens/semantics; verified idempotent via the `--check` round-trip), as one
standalone style commit. Parallels the same-day selfdef fmt fix.

### Fixed — main CI green: 8 pre-existing lint failures resolved (2026-05-27)

`pytest tests/lint` had 8 failures on main (they predate this session). Root-caused
and fixed, all values determined from repo content (no fabrication):
- **SDD-040** (cockpit-dashboard bridge, authored 2026-05-19) was never catalog-wired.
  Added its `docs/sdd/INDEX.md` row (transcribed from its own header), a
  `> Closes findings: none (...)` cross-link line (same pattern as SDD-038/039), and
  a reference in the operator mandate (the dashboard-content surface note on E11.M2) —
  clearing `test_sdd_index_consistency`, `test_sdd_cross_links`, and both
  `test_sdd_reachability` tests.
- **E11.M2/M5/M6/M7/M8/M9/M10/M12** rows in the mandate's §1g decomposition lacked a
  status keyword. Appended an accurate `Status:` to each: `✓ shipped (R<n>)` for the
  six whose operator/* module file was verified present (371–857-line scripts + contract
  tests), `in-flight` for the never-ending-PR row (E11.M12). The §1g FLAGGED-UNDONE axis
  is preserved alongside — clearing `test_epic_e11_cross_repo_coverage`.
- **sovereign-hugepages-sizer.service** declared no `ProtectSystem=` and lacked
  `ProtectKernelTunables` (the author documented the intent in comments but never encoded
  the directives). Added `ProtectSystem=full` (safe: it locks /usr+/boot+/etc but not
  /proc/sys, with /etc/sysctl.d re-opened via the existing `ReadWritePaths`) +
  `ProtectKernelTunables=false` + a `# HARDENING-WAIVER:` documenting the one justified
  opt-out (the sizer must write /proc/sys/vm/nr_hugepages) — clearing both
  `test_systemd_*hardening*` tests.

The 8th failure (`test_round_refs::test_recent_rounds_in_commit_history`) was a
shallow-clone artifact, not a repo defect: R350–R475 are real commits below this clone's
shallow horizon; the test self-skips in CI's depth-1 checkout (HEAD carries no R-number),
and passes once the clone has full history. No repo change needed. Full suite:
2820 lint+schema tests pass.

### Added — repo-wide JSON parse + duplicate-key lint (2026-05-27)

The 19 Grafana cockpit dashboards under `docs/observability/dashboards/`
(plus `.mcp.json` and the env template) are imported verbatim into
Grafana, but nothing validated that the dashboard JSON parses, and
nothing guarded duplicate object keys. `json.load` silently keeps only
the LAST value for a repeated key — a duplicate panel `"id"` or a doubled
`"targets"`/`"title"` silently drops a panel or query, so the dashboard
imports fine but renders wrong with no syntax error. New
`tests/lint/test_all_json_parses_and_no_dup_keys.py` discovers every JSON
under the repo (skipping target/.git/build dirs) and asserts each parses
+ has no duplicate keys via an `object_pairs_hook` guard. Stdlib-only
(`json`); runs in the existing `pytest tests/lint` layer. All 21 files
pass; both checks negative-control-verified. Completes the
sh/py/yaml/json parse-gate matrix alongside the YAML lint added the same
day.

### Added — repo-wide YAML parse + duplicate-key lint (2026-05-27)

sovereign-os ships ~30 YAML documents (build/runtime profiles + mixins,
schema mirrors, cloud-init seeds, bootstrap phase/verify tables, the
whitelabel manifest, the model registry, GitHub workflows). A few had
content-specific lints, but most had NO gate ensuring they even parse,
and NONE guarded against duplicate mapping keys — which PyYAML accepts
silently, keeping only the last value (two `kernel:`/`runtime:` keys
quietly collapse to one). New `tests/lint/test_all_yaml_parses_and_no_dup_keys.py`
discovers every YAML under the repo (skipping target/.git/build dirs)
and asserts each parses + has no duplicate keys, via a strict PyYAML
`SafeLoader` subclass that raises on dup keys. Uses only `pyyaml` (CI
already installs it; runs in the existing `pytest tests/lint` layer). All
30 files pass; both checks negative-control-verified (injected syntax
error and duplicate key each land RED). Parallels the selfdef
`L1-yaml-parse-scan.sh` gate added the same day.

### Added — Cockpit dashboards + Rust runtime crates (2026-05-19)

Cross-repo cockpit-surface completion arc per M060 R10128 ("21 dashboards (D-00..D-20) satisfy operator '20+ dashboards and a main one' verbatim"):

- **11 new dashboards** authored under `webapp/` (D-03 model health, D-07 memory changes, D-08 rollback points, D-12 networking, D-13 filesystem grants, D-14 capability tokens, D-15 sandboxes, D-17 quarantine, D-18 trust scores, D-19 super-model manifest, D-20 peace machine health). D-12..D-18 consume selfdef MS007 mirror crates READ-ONLY per MS043 R10212; all mutation routes emit clipboard CLI for operator-signed `selfdefctl` invocation.
- **6 Rust runtime crates** (81 passing tests, cargo workspace bootstrapped):
  - `sovereign-nvfp4-runtime` (M077, arXiv 2509.25149 / 2505.19115 — E2M1 + E4M3 + 1×16 block quant + unbiased stochastic rounding ±2% verified)
  - `sovereign-holderpo` (M078, arXiv 2605.12058 — Hölder mean + GRPO + 4 anneal schedules)
  - `sovereign-hrm-runtime` (M080, arXiv 2506.21734 — 4th architectural class, 3 variants 27M/1.18B/7M)
  - `sovereign-intervention-class-mirror` (M079, arXiv 2604.09839 — WB↔BB protocol-separation invariant)
  - `sovereign-mirror-publisher` (typed manifest of the 9 selfdef-mirror HTTP/SSE endpoints with bound-lifecycle helpers)
  - `sovereign-dashboard-coverage` (verifies all 21 D-NN slots have on-disk coverage; one disk integration test against real repo tree)
- **CI extension** — new `cargo-workspace` job in `test.yml` runs fmt + clippy (-D warnings) + workspace test + release build across all 6 crates.


- 4 new SDDs (012-022): brand-identity placeholder · installer-experience
  · decommission-testing-scope · secure-boot posture · observability
  bindings · ZFS root layout · kernel choice · reproducibility target ·
  CI infrastructure · distro-base lock-in · disk-encryption posture.
- 3 new profiles + 2 new mixins: `minimal` (VM baseline) · `developer`
  (polyglot toolchain) · `headless` (bare-metal server); mixins
  `role-headless`, `role-developer`, `role-server`.
- Substrate-prepare adapter for live-build (was mkosi-only).
- `orchestrate.sh run --dry-run` / `preflight` / `rewind <step>` /
  `skip <step>` operational verbs.
- 4 new pre-install hooks: preflight-network · preflight-tpm ·
  preflight-storage (plus friction-audit-spec was already shipped).
- 2 new recurrent hooks: security-update-check · backup-snapshot.
- Substantive plymouth + GRUB whitelabel overlays — operator-verbatim
  motd ('quality over quantity · honesty over cheats and lies')
  surfaced at boot in 3 surfaces (`/etc/issue`, plymouth splash,
  GRUB menu bottom).
- `sovereign-osctl` 4 new subverbs: `audit provenance`, `inference
  health`, `inference route`, `doctor v2` (profile-conditioned
  multi-section).
- in-toto SLSA v1 build-provenance.json + sha256sums.txt emission
  at step 09; operator-side verification via `audit provenance`.
- SOURCE_DATE_EPOCH + DEBIAN_SNAPSHOT propagation through mkosi-emit;
  KBUILD_BUILD_TIMESTAMP recorded in kernel build.
- ZFS encryption (SDD-022): aes-256-gcm on tank/context + tank/agents;
  passphrase + TPM2 PCR-7+11 binding default for sain-01 + headless.
- 16 systemd service units, ALL with defense-in-depth sandboxing
  (ProtectSystem / NoNewPrivileges / PrivateTmp / narrow ReadWritePaths).
- 21 Layer-B Prometheus textfile-collector metrics emitted across
  pipeline + recurrent + inference + perimeter + log-rotation +
  ZFS-health + snapshot + security-updates + image-build + image-sign.
- 2 Grafana JSON dashboard templates (`docs/observability/dashboards/`).
- `scripts/setup.sh` — one-command fresh-clone bootstrap.
- `scripts/git-hooks/pre-commit` — operator-side L1 + profile + L3
  fast-sample gate before every commit.
- `tests/qemu/scaffold.sh` — Layer 4 QEMU integration scaffold (gated
  on KVM + qemu + built image; SKIPs gracefully when absent).

### Test coverage
- Layer 1 (schema + lint): ~25 + 6 lint suites (was 3).
  New: systemd-unit-hardening, dashboard-json-valid, dashboard-metrics-
  lockstep.
- Layer 2 (unit): ~51 (was 51); +10 provenance-manifest shape.
- Layer 3 (nspawn): 35 substantive test scripts (was 7). Coverage:
  every lifecycle stage + every operator-facing CLI verb + every
  build step's gate path + reproducibility chain + image-sign +
  whitelabel overlays + inference router + first-login-assistant +
  decommission gates + during-install gates + new recurrent hooks +
  e2e DRY-RUN smoke across all 5 profiles.
- Layer 4 (QEMU): scaffold ready; substantive run gated on
  KVM-equipped self-hosted runner (Q10-B per SDD-020).
- Layer 5 (hardware): operator-driven on real SAIN-01.

### Fixed (15 real wiring bugs caught by L1/L2/L3 discipline)
1. `whitelabel/default.yaml` template paths
2. `orchestrate.sh` cmd_help sed truncation
3. `state_step_status` empty-string default
4. `logging.sh` log_file parent dir auto-create
5. `sovereign-osctl profiles list` shell-var-vs-export propagation
6. `friction-audit-spec.sh` bash -c profile_field scope
7. `test_decisions_log_sequence.py` regex never matched its target
8. `first-login-assistant.sh` unconditional hostnamectl in containers
9. inference start scripts `${VAR:=…}` defaults not exported
10. `sovereign-osctl doctor` missing load_profile
11. `sovereign-osctl models remove` `${1:?word}` brace ambiguity (R62)
12. `sovereign-osctl` lib-path mismatch (`/usr/local/lib` vs `/usr/lib`) (R81)
13. `live-build-emit.sh` README embedded tmpdir basename → non-reproducible (R84)
14. `first-login-assistant.sh` shipped without Layer B coverage; gap closed
    + Layer 1 lint authored to prevent regression class (R86)

See `docs/src/tdd/bugs-caught.md` for the ledger + 3 distilled
cross-bug Learnings.

### Rounds 61-94 — operator-observability + Phase F + G arcs

**Phase F closer (Rounds 61-77)** — operator surface deepening:
- `sovereign-osctl models {size, remove, list, pull, verify}` complete
- `model-catalog-sync` substantive recurrent hook (replaced stub)
- `version --json` (7-key contract) + `status --json` (8-key contract)
- `whitelabel diff` operator preview verb
- `maintenance` surface expanded 2 → 8 subverbs
- `assistant` surface: full / status / reset / list
- 5-candidate lib-path detection (operator-actionable error on miss)
- Layer B parity across all during-install + post-install hooks
- 3rd Grafana dashboard: `sovereign-os-install.json`
- Root Makefile + `make install` / `make uninstall` (PREFIX/DESTDIR)
- Comprehensive dispatcher-surface L3 (33/33)

**Phase G — operator-observability arc (Rounds 78-94)**:
- Reproducibility self-test gate (`test_reproducibility_self_test.sh`):
  byte-identical mkosi + live-build emissions under pinned inputs
- 51-metric Layer B inventory (was 21) restructured into 7 labeled
  sections; two-way contract enforced (code ↔ inventory) by
  `test_metric_inventory_lockstep.py`
- Hook Layer-B coverage lint (`test_hook_layer_b_coverage.py`):
  every lifecycle hook calls `emit_metric` or carries a waiver
- `sovereign-osctl metrics {list, show, tail, health}` — read .prom
  files without third-party tooling (20-assertion L3)
- `sovereign-osctl alerts [--json]` — 6-rule in-tree engine over .prom
  files; ALERT/WARN with remediation hints (13-assertion L3)
- `sovereign-osctl journal {list, show, tail, errors}` — Layer A
  JSONL surface symmetrical with metrics (21-assertion L3)
- `alerts-check.sh` recurrent hook + `sovereign-alerts-check.timer`
  (hourly); meta-counters back into Layer B (15-assertion L3)
- SDD-023 codifies the alerts contract (6 rules, 2 levels, 5
  tunables, 4 surfaces, 5 test gates, 4 open Q23-X)
- Handoff 003 — operator-observability cold-start signpost
- Install-runbook §5b — Layer A/B/C walkthrough with sovereignty
  posture restated

### Rounds 95-114 — Phase H: contracts + hardening + audit surfaces

**Closing arcs**:
- Rounds 95-103 — closer for the observability arc: CHANGELOG R61-94
  catchup · headless hardening IaC (5 drop-ins) · SDD-024 server
  hardening posture · Handoff 003 trajectory
- Rounds 104-105 — workstation hardening parallel (sain-01 + old-workstation
  get 4 drop-ins, share auditd/pwquality/unattended with server, get
  workstation-tuned sshd, deliberately NO fail2ban) + D-017 + SDD-024
  extended
- Round 106 — in-toto verifier `--deep` mode closes the SDD-019
  triangle (manifest ↔ sums ↔ on-disk)
- Round 107 — `sovereign-osctl history` verb (per-run summary derived
  from JSONL); fourth observability-family verb completing symmetry
- Round 108 — 15th bug caught by L2 contract test: alerts engine
  reacted to `sovereign_os_meta_*` metrics → self-reinforcing loop;
  fix + 9-assertion L2 schema gate codifying SDD-023 Q23-A
- Round 109 — SDD-007 strategy 7 (must-not-touch) implementation;
  7/7 strategies now covered
- Round 110 — Handoff 003 refresh through R109
- Round 111 — `sovereign-osctl audit drift` verb: compares deployed
  hardening drop-ins vs config/{server,workstation} sources; --json mode
- Round 112 — SDD-024 Q24-C resolved: sshd Banner → /etc/issue.net
  (standard pre-auth convention); /etc/issue.net extended with
  "Authorized use only" legal-language line
- Round 113 — SDD-025 codifies the observability CLI architecture
  (4-verb shape + dir resolution + exit codes + --json contract)
- Round 114 — L2 schema test for audit drift --json (parallels alerts
  schema test)

**Operator-facing additions** (Rounds 95-114):
- 6 hardening drop-ins (5 server + 1 workstation-specific sshd)
  totaling ~250 lines of opinionated IaC with invariants pinned in
  Layer 1 lint
- 2 apply hooks (server + workstation) with DEST_PREFIX support for
  chroot/image-build flows + idempotency + drift detection
- 4 new sovereign-osctl verbs: `history` + `audit drift` + (carried
  from R88-91) `metrics`/`alerts`/`journal`
- `audit provenance --deep` flag completing the in-toto verifier
- 3 new SDDs: SDD-023 (alerts contract) · SDD-024 (server + workstation
  hardening posture) · SDD-025 (observability CLI architecture)
- 3 new decision-log entries: D-015 (alerts) · D-016 (server hardening) ·
  D-017 (workstation hardening parallel)
- 2 new L2 schema contract tests (alerts JSON + drift JSON)
- ~115 lint assertions (was ~92); ~70 unit tests (was ~62); ~55 L3
  nspawn tests (was ~52)

**Bug ledger**: now at 15 real wiring bugs caught (was 14 at start of
Phase H). #15 — alerts engine reacted to its own meta-metrics — caught
by L2 schema test within minutes of being authored, locked by an
explicit code guard + permanent test gate.

### Question closures (every PR-1-seed Q-X resolved/partial)
| Q | Status | Resolution |
|---|---|---|
| Q-001 | resolved | SDD-003 (substrate survey — mkosi primary) |
| Q-002 | resolved | SDD-004 (profile schema + mixins; merge rules pinned; fork/overlay are operator-side workflows) |
| Q-003 | deferred-with-criteria | SDD-012 (brand identity placeholder) |
| Q-004 | resolved | SDD-007 (legal scope) |
| Q-005 | resolved | SDD-017 (ZFS root layout) |
| Q-006 | resolved | SDD-015 (secure-boot 3-level posture) |
| Q-007 | resolved | SDD-018 (kernel choice — dual strategy) |
| Q-008 | resolved | SDD-013 (installer experience — image-only) |
| Q-009 | operator-side | hardware procurement |
| Q-010 | resolved | SDD-020 (CI infrastructure — GHA only) |
| Q-011 | resolved | SDD-001 (cross-repo boundaries) |
| Q-012 | resolved | minimal + developer + headless profiles landed |
| Q-013 | resolved | SDD-016 (observability bindings) |
| Q-014 | resolved | SDD-014 (decommission testing scope) |
| Q-015 | resolved | SDD-019 (reproducibility target) |
| Q-016 | resolved | SDD-021 (distro-base — Debian 13) |
| Q-017 | resolved | SDD-011 (inference backend stack) |
| Q-018 | resolved | first-login-assistant + cloud-init pre-add path + sovereign-osctl assistant surface (R67) + Layer B (R86) |
| Q-019 | resolved | sovereign-osctl 15 verb groups + 30+ subverbs + SDD-025 CLI architecture; 37-assertion dispatch L3 gate |

Plus Stage-2+ sub-questions: Q15-B (SDD-022) + Q18-A (Round 30
short-circuit) resolved; Q15-A/C, Q16-A..D, Q18-B..C, Q22-A..C tracked.

## Pre-history

Foundation-phase PRs 1–10 landed:
- PR 1 — charter + decisions log + INDEX files
- PR 2 — cross-repo boundaries (SDD-001)
- PR 3 — documentation pipeline (SDD-002) + mdbook
- PR 4 — substrate survey (SDD-003 → Gate 2)
- PR 5 — profile schema (SDD-004 → Gate 3)
- PR 6 — initial profile stubs (SDD-005)
- PR 7 — Debian surface audit (SDD-006)
- PR 8 — whitelabel mechanism (SDD-007 → Gate 4)
- PR 9 — TDD harness spec (SDD-008)
- PR 10 — TDD harness bootstrap (SDD-009 → Gate 5)

See `docs/decisions.md` § D-001..D-003 for the pre-PR-4 charter
decisions.
