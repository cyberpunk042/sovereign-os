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

### Added — GPT-OSS real-model coherence harness (2026-07-19)

Caps the GPT-OSS decoder line (the block FFN math, the full GGUF path, and the
safetensors MXFP4 → fused-expert → clamped-α/biases/sinks assembly) with the one
check no synthetic fixture can stand in for: does a **real** gpt-oss checkpoint,
loaded by `sovereign-safetensors-loader`, produce sane autoregressive logits?

- **`crates/sovereign-safetensors-loader/tests/gpt_oss_coherence.rs`** — an
  **env-gated** integration test (`SOVEREIGN_GPT_OSS_GGUF=/path/to/gpt-oss.gguf`,
  optional `SOVEREIGN_GPT_OSS_PROMPT_IDS`). CI compiles it and **skips** cleanly
  (no multi-GB checkpoint on the runner); point it at a GGUF and run it to close
  the coherence gate. It loads via `load_gguf`, greedily rolls out ~25 tokens
  over the stateful KV cache, and at every step **asserts** the mechanical
  invariants a broken dequant/assembly would trip (logits finite, non-degenerate,
  valid argmax) while **emitting** the greedy rollout for human coherence
  judgement — the harness produces the evidence, it does not fabricate a
  coherence threshold. A GGUF is the tractable real path: k-quant experts this
  crate already dequants byte-exact + the tokenizer in metadata, so no MXFP4 and
  no vocab bridge are needed to smoke it. The **safetensors** arm
  (`openai/gpt-oss-20b`, multi-shard MXFP4) is a documented follow-up gated on the
  loader's multi-shard/index assembly. Real-model coherence stays checkpoint-gated
  until this is run against one; the GGUF path is the coherence anchor.

### Added — the goal-loop trace sink: the M046 trace source (2026-07-16)

Operator-directed (*"go"*) (SDD-723) — close the last software gap in the M046 loop after SDD-721 (train) +
SDD-722 (dataset). The curator reads a JSONL trace log but nothing wrote one (fixtures only); this ships the
producer so the loop is whole **and self-feeding**: `traces (this) → dataset (SDD-722) → train (SDD-721) →
register → gate → transport → serve --lora`.

- **`goal-driver.py` `run_loop(…, trace_sink=None)`** — the `/goal` loop now records the trajectory. It
  accumulates `messages` (user prompt + assistant reply per iteration) and, at termination, emits **one record**
  through an injected sink: `{"messages":[…], "outcome":"success"|"failure", "goal":<text>, …}` — exactly the
  shape `adapter-dataset.py` curates. The sink lives here, not in the raw daemon, because **success/failure is
  already known at the loop** (`done → success`, `paused → failure` — the same signal the curator keys on), so
  the label falls out of the terminal state with no oracle, and it stays stdlib-only + CI-testable (scripted
  responder, no daemon/GPU).
- **`append_trace()` / `file_trace_sink()`** — append to the trace log (`SOVEREIGN_OS_TRACE_LOG`, default
  `/var/lib/sovereign-os/traces/agentic.jsonl`), **bounded** (keeps the last `SOVEREIGN_OS_TRACE_MAX_LINES`,
  default 10 000, so an always-on loop can't grow it unbounded) and **atomic** (`os.replace`, like goal-ctl's
  state write). CLI `goal run` wires it by default; `--no-trace` opts out. The signature change is
  backward-compatible (`trace_sink` defaults `None` — the goal-lock tests pass unchanged).
- **`tests/lint/test_trace_sink_contract.py`** (5) — trajectory emitted with alternating roles;
  done→success / paused→failure; the record curates cleanly through `adapter-dataset.py`; `append_trace`
  bounded + atomic; `trace_sink=None` emits nothing.

Verified: trace-sink 5 + goal-lock 8 passed; **end-to-end (real, in CI)** — a scripted 2-step goal run writes a
trajectory to the log, `adapter-dataset.py curate` keeps it as one success example (sentinel stripped), and
`adapter-train.py plan … --dataset <log>` consumes it. The M046 loop now runs from a live goal pursuit all the
way to a training-ready dataset with zero fixtures; full `tests/` + ruff green. With SDD-721/722/723 the loop is
whole in CI-testable Python — a pursued goal becomes training data becomes the next adapter. Only the GPU run +
real gate scores remain, both genuinely SAIN-01-side.

### Added — the trace→dataset curator: success examples become training data (2026-07-16)

Operator-directed (*"go"*) (SDD-722) — continue the M046 loop upstream after SDD-721 landed the trainer. The
trainer assumes a `--dataset` exists; E0444 (*"trace → success/failure examples → curated dataset"*) is what
produces it. This closes the **input** hole symmetric to the training hole SDD-721 closed on the output side:
`traces → DATASET (this) → TRAIN (SDD-721) → register → MS041 gate → transport → serve --lora`.

- **`scripts/inference/adapter-dataset.py`** — a **CLI curator** (a real producer, not a planner: curation is
  pure I/O so — unlike GPU training — it **runs in CI**). `curate <id> --traces <log.jsonl> [--out <path>]
  [--label success|all] [--min-turns N]` reads a JSONL trace log (one agentic interaction per line —
  `{"messages":[…], "outcome":…, "goal":…}`) and writes a curated chat-format dataset (`{"messages":[…]}`) that
  unsloth/TRL consume as `--dataset`. **DRY-RUN by default** (reports kept/dropped + reasons + previews the
  first example); `--apply` writes to `--out` (default `/var/lib/sovereign-os/adapters/<id>/dataset/train.jsonl`).
  Stdlib-only.
- **The success label is the `/goal` loop's own completion token.** A positive example is `outcome=="success"`
  **or** its final assistant message carries `DONE_SENTINEL`, imported from `goal-driver.py` (SDD-719) — "the
  goal loop said it finished" *is* the label; no separate oracle. The sentinel is **stripped from the emitted
  target** so the model learns the behaviour, not the token.
- **Curation rails**: drop interactions shorter than `--min-turns`, drop ones with no assistant reply, **dedup**
  identical message sequences (SHA-256). `--label all` keeps failures too, tagged `label: success|failure`, for
  later contrastive/DPO datasets.
- **`tests/lint/test_adapter_dataset_contract.py`** (8) — present/executable/stdlib; reuses the goal-driver
  sentinel; success-filter + dedup + too-short drop; sentinel stripped from the target; `all` includes
  failures; DRY-RUN default vs `--apply` writes.

Verified: `pytest tests/lint/test_adapter_dataset_contract.py` 8 passed; functional (5 fixture traces → 2 kept
success-mode with dedup + sentinel-strip; `--apply` writes JSONL that `adapter-train … --dataset` consumes
unchanged); full `tests/` + ruff green. Not runtime-verified — the gateway/goal-loop doesn't yet *persist*
traces; the curator reads the shape they emit, and wiring the trace sink is the follow-up. With SDD-721 (train)
and this (dataset), the M046 loop is whole in CI-testable producers; only the runtime trace-sink + the GPU run
remain.

### Added — the adapter training producer: unsloth/QLoRA on the unpacked base (2026-07-16)

Operator-directed (*"what about custom training, doesn't it take unsloth ? … did we handle that already ? like a
real support for it and LoRA management and observability and operability ?"*; then *"ready"*) (SDD-721). LoRA
**management + observability + operability** were already shipped — `adapter-foundry` (inventory → D-11),
`adapter-gate` (MS041 triple-gate → D-10), `adapter-decide` (promote/demote/rollback + `register`),
`adapter-transport` (ship + ZFS, SDD-716), `--lora` serving (SDD-715), the registry — but nothing actually
**trained**: `register` only minted a *pending* adapter. This closes the last gap so the loop is whole:
`traces → dataset → TRAIN (this) → register → MS041 gate → transport → serve --lora → rollback`.

- **`scripts/inference/adapter-train.py`** — a **CLI planner** (the standalone `adapter-transport` pattern, not
  an osctl verb): `plan <id> --base <unpacked> --dataset <path> [--method qlora|lora] [--trainer unsloth|trl]
  [--epochs N]` prints the exact commands — an `adapter-decide register` step (mint the pending adapter) + the
  trainer invocation + the output layout `/var/lib/sovereign-os/adapters/<id>/train/` — **DRY-RUN by default**,
  `--apply` runs them. QLoRA defaults (r=16, α=32, lr=2e-4, 4-bit) are operator-overridable. Trainer metadata
  (install/detect/hardware-fit) is read from the existing `scripts/models/toolchains.py` registry (unsloth is
  catalogued there) — never reinvented. Stdlib-only (no trainer imported at load).
- **The ternary caveat is enforced, not just documented.** A packed ternary/GGUF `--base` **warns**: you cannot
  LoRA-train a 1.58-bit base — train the FP16 LoRA on the **unpacked** safetensors (`prism-ml/Ternary-Bonsai-*-
  unpacked`), base frozen, then serve the adapter over the ternary GGUF (SDD-715). A CUDA trainer also warns it
  belongs on **SAIN-01** (E0446: "4090 → train small LoRAs / QLoRA"), not the serving box.
- **`tests/lint/test_adapter_train_contract.py`** (7) — present/executable/stdlib; reuses toolchains +
  adapter-decide; plan shape `[register, train]` with base/dataset/output/hyperparams; the ternary warning
  fires; QLoRA=4-bit vs LoRA≠4-bit; DRY-RUN default.

Why a planner, not the trainer: GPU training (unsloth/TRL on the 4090/Blackwell) can't run in CI — no GPUs, no
weights — which is exactly why M046 deferred it. The deliverable is the **plan** (argv-tested) plus the
correctness rails; the GPU-side trainer entry point (`train/<trainer>-lora.py`) is the operator-supplied Stage-4
piece the plan invokes. Verified: `pytest tests/lint/test_adapter_train_contract.py` 7 passed + full `tests/` +
ruff green. Not GPU-verified (no CUDA/weights in CI).

### Added — `/goal`: a locked goal the agent pursues on its own (2026-07-16)

Operator-directed (*"the '/ goal' command … set a goal and have it stay locked … I don't want … to
continuously have to tell it to continue or to re-state what I want"*; then *"ready"*) (SDD-719, implementation
slice 1 — the first behavior built from the autonomy design arc). Recommended Q-719 defaults taken: one active
goal, 50 iterations / 3 no-progress → pause.

- **`sovereign-osctl goal {set,show,pause,resume,done,abandon,progress,run}`** — set one durable, operator-
  verbatim goal; it stays locked until you close it.
- **`scripts/inference/goal-ctl.py`** — the goal state at `/etc/sovereign-os/agent-state.json` (atomic write,
  stdlib-only). The goal `text` is written only by `set`; the loop only appends progress + bumps the iteration
  count, **never rewriting the objective** (sacrosanct-verbatim, enforced by a test).
- **`scripts/inference/goal-driver.py`** (`goal run`) — loop-until-goal: the SDD-718 self-loop tier realized as
  an orchestrator over the existing gateway agentic endpoint (SDD-712). While the goal is `active` it re-arms
  one agentic request per iteration (goal + recent progress fed back) and stops on **done** (the model ends a
  reply with `[[GOAL_DONE]]`), the **max-iterations** ceiling, or the **no-progress** guard — the two guards are
  goal-level (distinct from SDD-712's per-step repeat-guard) and both *pause* (not abandon) the goal, so "keep
  going until done" can never pin the box.

No daemon change (it orchestrates the endpoint that already exists). The per-iteration call is a `Responder` —
tests inject a scripted one, so the loop control + guards are proven without a model. Verified: `pytest
tests/lint/test_goal_lock_contract.py` 8 passed + full `tests/` + ruff green. Not model-verified (no weights in
CI). Slice 2 (mode-gating in the tools per SDD-720, the OpenClaw tier, an unattended systemd/cockpit runner,
Plan→lock seeding) is deferred.

### Scoped (design, no code) — local-agent autonomy: modes, /goal lock, sub-agents (2026-07-16)

Operator-directed (*"I want it like Claude Opus and able to set the Auto mode … work multiple query and launch
sub-agents and continue and do real round, real iterations … the '/ goal' command … stay locked"*). Decision:
harness = **both, tiered**; **scope both first as SDDs**. Three design SDDs (no implementation) so the operator
can review the whole arc before code:

- **SDD-718** — the architecture spine: **the model has no modes, the harness does.** vLLM/llama.cpp are token
  generators; Auto/Plan/Bypass + iteration + sub-agents + goal-lock are *harness* behaviors, pointed at the
  gateway's OpenAI endpoint instead of Anthropic's. Decision: **both-tiered** — the gatewayd self-loop (SDD-712,
  single-agent, zero-dependency) + OpenClaw (SDD-705, full harness with sub-agents), sharing one model +
  `permission-modes.yaml` + `/goal` state.
- **SDD-719** — `/goal`: a durable, sacrosanct-verbatim goal in `/etc/sovereign-os/agent-state.json` + a
  loop-until-goal control (goal-level max-iters + no-progress guard) so "set it and it stays locked, iterating
  on its own" works. Plan-approval seeds the goal ("approve the plan" = "lock the goal and go").
- **SDD-720** — wire the existing permission classifier into the agent loop's tool dispatch, so Auto mode
  actually auto-runs safe tools + blocks destructive ones *inside the iteration* ("Auto Edit On" = a preset).

What already exists (reused, not rebuilt): `config/permission-modes.yaml` (manual/auto/bypass — the operator's
own 2026-07-11 directive), `permission_classifier.py` (SDD-954), the `sovereign-agent-loop` crate, the gatewayd
agentic loop (SDD-712), and OpenClaw (SDD-705). The real enforcement boundary (sandbox) stays selfdef's;
these are the UX/workflow layer on top. No code — `scoping` status; implementation follows operator review.

### Added — vision + speculative-draft serving on the dual-Turing node (2026-07-16)

Operator-directed (*"2b and 3 now, one PR. take your time"*) (SDD-717, Slice 3). Lands the last two of the
operator's originally-named Bonsai-27B files:

- **Vision** — `llama_cpp` backend gains `mmproj_path` → `--mmproj`; a projector makes the 27B oracle
  image-capable (the operator's `…-mmproj-BF16.gguf`, Qwen3-VL lineage). Catalog: `Ternary-Bonsai-27B-vision`
  (`class: multimodal`, base 27B), bound to `dual-turing-serving`.
- **Speculative draft** — `draft_model_path` → `--model-draft`; a small draft the 27B verifies, accelerating
  decode (the operator's `…-dspark-bf16.gguf`). Catalog: `Ternary-Bonsai-27B-dspark` (`class: speculative`,
  base 27B). This is the **llama.cpp analogue** of SAIN-01's DFlash/DSpark (M083), which drafts via vLLM
  `--speculative-config`; the M083 path + `dspark-ctl.py` are untouched.

Both `operator-must-confirm`, BF16→F16 on Turing (no native BF16). The SDD-715 serving-coherence lint now covers
any base_model-carrying entry (lora / speculative / vision). Serve-only. Verified: backend verbatim pins +
`for_dual_turing` argv + full `tests/` + 5 profiles + ruff green. Not hardware-verified (no Turing GPUs / real
weights in CI).

### Added — adapter transport + ZFS lineage (2026-07-16)

Operator-directed (*"2b and 3 now, one PR. take your time"*) (SDD-716, Slice 2b). Closes the missing "ship a
promoted adapter SAIN-01 → box, versioned for rollback" link in the M046 foundry (E0444 pipeline; E0446 ZFS
"adapter versions + rollback"). Between *promote* (SDD-051 `adapter-decide`, MS041 triple-gate) and *serve*
(SDD-715 `--lora`), nothing moved or versioned the weights.

- **New `scripts/inference/adapter-transport.py`** — a stdlib-only **planner** (reuses `adapter-foundry.py`'s
  registry reader): `plan <id>` → the `rsync` pull into `/var/lib/sovereign-os/adapters/<id>/<version>/` **plus**
  a `zfs snapshot <dataset>@adapter-<id>-<version>` for lineage; `list` → local versions; `rollback <id>
  <version>` → `zfs rollback`. **DRY-RUN by default**; `--apply` executes. The ZFS dataset is profile-declared
  (not hardcoded) — the planner snapshots whatever backs the adapters path.
- **New contract lint** — present/executable/stdlib, registry reuse, plan/rollback shape, DRY-RUN default.

A planner rather than an executor because cross-box rsync/ssh + ZFS can't run in CI (one box, no pool); the
operator runs `--apply` on the real box. Verified: the lint + functional plan/list/rollback; full `tests/` +
5 profiles + ruff green.

### Added — LoRA-adapter serving on the dual-Turing node (2026-07-16)

Operator-directed (*"go"* — Slice 2 of the personal-workstation LoRA plan) (SDD-715). Closes the *serving* gap
in the M046 LoRA foundry: the inventory/governance side was already built (`adapter-foundry.py` + the MS041
triple-gate + the D-11 dashboard), but `LlamaCppBackend` had no `--lora`, so a promoted adapter had nowhere to
load, and none was bound to the SDD-714 dual-Turing node.

- **llama.cpp backend** gains `lora_path`/`lora_scale` → `--lora <path>` (or `--lora-scaled <path> <scale>`),
  plumbed through `for_dual_turing()`. The adapter overlays the frozen ternary base **unmerged** (E0443), a
  hot-swappable behavioral overlay — the argv-layer analogue of Slice 1's `--tensor-split`.
- **Catalog** registers two real E0442 candidate adapters (`class: lora-adapter`, `engine: llama.cpp`) bound to
  `dual-turing-serving`: `sovereign-os-admin-lora` (base `Ternary-Bonsai-27B`) + `coding-style-lora` (base
  `Prism-Ternary-Bonsai-8B`), both `operator-must-confirm` (real weights + MS041 promotion pending).
  `adapter-foundry.py list` inventories all three automatically.
- **New serving-coherence lint** — every lora-adapter `base_model` resolves to a real catalog model, a bound
  profile actually serves that base (E0442), and the llama.cpp adapter exposes `--lora`.

Serve-only (training on SAIN-01); bf16 adapters → F16 for Turing serving. M046 spec (E0441–E0447) untouched.
Transport (SAIN-01 → box) + E0446 ZFS versioning are Slice 2b (runtime/ops). Verified: touched-contract pytest
+ `for_dual_turing` argv + full `tests/` + 5 profiles + ruff green. Not hardware-verified (no Turing GPUs /
real adapter weights in CI).

### Added — dual-Turing workstation serving profile + Bonsai catalog (2026-07-16)

Operator-directed (*"I might wanna re-use those later with LORA customization for my personal (2080 + 2080 Ti
workstation)"* → serve base + LoRAs, training offloaded; both tiered → *"yes. pull the latest main and start"*)
(SDD-714, Slice 1). Makes the operator's personal dual-Turing workstation (RTX 2080 Ti 11 GB + RTX 2080 8 GB) a
real, catalogued llama.cpp serving target — an 8B scout + a 27B oracle, both ternary GGUF, one model per card,
serving hot-swap LoRA adapters trained on SAIN-01 (M046 E0446).

- **NEW runtime profile** `profiles/runtime/dual-turing-serving.yaml` (operator-additive § 18): `Ternary-Bonsai-27B`
  Q2_0 (oracle) on the 11 GB card, `Prism-Ternary-Bonsai-8B` (scout) on the 8 GB card — mirrors the M018
  Scout/Oracle tiering on Turing.
- **Catalog** adds HF-verified `Ternary-Bonsai-27B` (`prism-ml/Ternary-Bonsai-27B-gguf`, released 2026-07-04,
  base Qwen3.6-27B, ternary/GGUF), binds both Bonsai entries to the new profile, and corrects the stale
  2026-07-02 "largest is 8B" note (the 27B post-dates it by two days).
- **llama.cpp backend** gains `--tensor-split` + a `for_dual_turing()` constructor — llama.cpp splits UNEVEN
  VRAM by ratio (8 + 11 GB), the concrete reason it, not vLLM (symmetric tensor-parallel + Ampere+ kernels;
  Turing has no native BF16/FP8), serves this box. Ternary is not engine-bound — the catalog already runs
  `ternary-1.58bit` on vllm + llama.cpp + bitnet.cpp.

Serve-only (training offloaded, operator-chosen); M046 E0446 (sacrosanct spec) left untouched. Vision (`mmproj`)
and the `dspark` speculative-decode draft are deferred (Slice 3 — BF16→F16 on Turing). Verified: touched-contract
pytest + `for_dual_turing` argv + full `tests/` + 5 profiles + ruff green. Not hardware-verified (no Turing
GPUs/weights in CI).

### Added — a production agent tool catalog: calc + time + recall (2026-07-14)

Operator-directed (*"go. lets do everything, another big round. take your time to do this right"*) (SDD-713).
Lands the curated production tool catalog that SDD-712 named as a slice-2 non-goal — the first three real,
still-side-effect-free tools on the server-side ReAct loop (F-2026-088 stays closed; no finding re-opens):

- **`calc`** reuses `sovereign-calc::eval`, the pure dependency-free shunting-yard evaluator that was a
  demo-only island — real arithmetic (`[[tool:calc|2*(3+4)]]` → `14`); a parse error returns
  `[calc error: …]` as a recoverable observation; whole-number results render as integers.
- **`time`** returns `SystemTime::now()` as `"<n> (unix seconds, UTC)"` — the first real wall-clock read
  inside gatewayd, non-reproducible by design (a clock read is the point).
- **`recall`** queries the daemon's one process-wide learning `Cortex` (M016): the best-available text of the
  top memories whose text-sketch overlaps the query, or `[no relevant memory]`.

`recall` is registered only when a cortex handle is supplied, and `builtin_specs(include_recall)` mirrors that
so the model's advertised toolset never drifts from what the daemon dispatches (a test asserts they agree).
The one structural change: `GatewayServer.cortex` becomes `Arc<Mutex<Cortex>>` with a `cortex_handle()`
accessor (registry handlers are `'static` and can't borrow the server), and a new string-level
`Cortex::recall_text` keeps the FNV-1a sketch logic in the cortex crate. A poisoned lock degrades to
`[recall unavailable: …]` rather than a panic. The two SDD-712 sovereignty gates (per-request opt-in +
`SOVEREIGN_GATEWAY_AGENTIC` kill-switch, default OFF) are unchanged; side-effecting tools stay deferred to
selfdef. Verified: `cargo test -p sovereign-gatewayd` (9 agentic tests, was 6) + `-p sovereign-cortex` (+2);
fmt/clippy clean; gatewayd consumes `sovereign-calc` (was demo-only); no new crate; full tests + 5 profiles +
ruff green. Not model-verified (no weights in CI).

### Added — the daemon can run the agent loop itself (server-side agentic tool use) (2026-07-14)

Operator-directed (*"go with A"*) (SDD-712). Closes the multi-step half of F-2026-088 — with SDD-711
(single-turn, client-driven) this **fully closes F-2026-088**. Where SDD-711 returns `tool_calls` for the
client to execute, this runs the ReAct loop **inside** the daemon over built-in tools it executes, and
returns only the final answer.

Model-sharing is **Option A** (the operator's choice): a new `crates/sovereign-gatewayd/src/agentic.rs`
provides `GatewayResponder`, a `sovereign_agent_loop::Responder` that wraps the daemon's existing
`GatewayServer` and calls its `generate_chat` per step — the **same shared generator every request uses, with
no per-step model clone** — so the SDD-206 safety spine screens every step. The loop composes `AgentLoop`
(step cap + repeat-guard) with a **pure, side-effect-free** built-in tool set (`upper`/`lower`/`reverse`/
`wordcount`/`charcount` — no shell, fs, or network) and the SDD-711 bridge's prompt preamble.
`/v1/chat/completions` gains an agentic path: a request with `"sovereign_agentic": true` runs the loop and
returns the final answer (`finish_reason:"stop"`); without the field the existing paths are unchanged.

Sovereignty posture — the capability is gated twice: a per-request opt-in AND an env kill-switch
`SOVEREIGN_GATEWAY_AGENTIC=1` (**default OFF**, documented in the daemon USAGE), matching the installed-off
doctrine; a bounded step cap keeps a runaway loop from pinning the shared generator. A curated production
tool catalog (calc, time, local retrieval), streaming intermediate steps, and Anthropic `/v1/messages`
agentic parity are scoped as follow-ups; any side-effecting tool needs the sandbox + capability-gating story
(selfdef territory), deliberately not folded in.

### Added — `/v1/chat/completions` can use tools (OpenAI-compatible, single-turn) (2026-07-14)

Operator-directed (*"yes of course we want tools, good catch, so many things come from tools"*) (SDD-711).
Closes the single-turn half of F-2026-088. A workspace map corrected the finding: the daemon
(`sovereign-gatewayd`) has its own `QuantModel` stack (separate from the agent-loop's `SovereignLlm`),
`/v1/chat/completions` read no `tools` field, and OpenAI tool use is *client-driven* (the server returns
`tool_calls`, the client executes the tool) — so single-turn tool use needs no server-side ReAct loop and
no model-sharing change.

A new model-free crate `sovereign-tool-bridge` adapts between the bespoke `[[tool:NAME|ARGS]]` dialect
(`sovereign-tool-dispatch`) and OpenAI/Anthropic `tool_calls`/`tool_use` JSON (bridging the previously
zero-consumer `sovereign-tool-call-parse`): parse request `tools`, teach the bracket convention, extract a
call in either dialect gated on the offered tools, and shape the response blocks (18 unit tests). The
`/v1/chat/completions` handler is now tool-aware: when a request carries `tools`, it generates the reply
buffered and returns a `tool_calls` response the client executes (or plain content) — reusing `generate_chat`
with the SDD-206 safety spine intact; a request without `tools` runs the existing token-streaming path
byte-identically. The bridge is genuinely consumed by gatewayd in the same change (the workspace forbids
orphan non-cockpit crates), following the MS003 reviewed-in-isolation-then-wired pattern.

The multi-step server-side ReAct loop, streaming tool-call deltas, and `/v1/messages` tool parity are scoped
as a gated increment in SDD-711 (with the daemon model-sharing decision surfaced), not built here.

### Changed — the `unsafe` ban is now compiler-enforced across all 202 cockpit crates (2026-07-14)

Operator-directed (*"lets do a big round"*, phase-1 audit continuation) (SDD-710). Closes F-2026-096 and
makes F-2026-004's "all inherit workspace lints" claim fully true. The root `[workspace.lints.rust]`
declares `unsafe_code = "forbid"`, but a crate inherits that lint only if it declares `[lints] workspace =
true` — and the audit (SDD-974) found the whole `sovereign-cockpit-*` family (202 of 717 crates) declared
no `[lints]` table, so the compiler would not have stopped a future `unsafe` in them; the ban rested on a
CI grep alone. A parse-verified sweep appended `[lints] workspace = true` to all 202 cockpit manifests, so
**716/717 crates now enforce the ban at compile time** and `sovereign-simd` keeps its sanctioned
`unsafe_code = "allow"` carve-out. `test_workspace_hygiene_baseline.py` gains invariant 7 (every crate must
inherit except the carve-out, which must declare its `allow` explicitly), so a new crate that forgets the
inherit line now fails CI. The change is provably inert (forbid is unused by the 202, `missing_docs` is
warn-level, and the workspace clippy table is all-`allow`), verified by a clean `cargo check` of a
representative swept crate + `cargo metadata` resolving the workspace.

### Added — the agent layer reaches the setup wizard + build configurator (2026-07-14)

Operator-directed (*"I like when we have a proper IaC and scripts and integrations and setup wizard and
auto-installs and auto-configuration."* → *"continue"*, Round B) (SDD-709). Closes F-2026-118 and the
wizard/configurator half of F-2026-117. SDD-703..707 wired the agent layer IaC→CLI and SDD-708 documented
it, but its build-time knobs still reached the operator only through hand-edited profile YAML or exported
env vars — the two surfaces the operator named didn't drive them: `sovereign-osctl init` had 5 fixed
decisions (no desktop/runtime), and `webapp/build-configurator` surfaced only 3 of the bake toggles
(the frontend selector + both agent-runtime bakes were absent from the page, its POST body, and the API).

Now one chain wires that last mile: `scripts/build/adapters/mkosi-emit.sh` gains a tri-state env-override
seam (`_env_bake`) so `SOVEREIGN_OS_BAKE_OPENCLAW`/`_OPEN_COMPUTER` (`1`/`0`/unset) and `SOVEREIGN_OS_FRONTEND`
override the profile's declared bakes (the profile stays source-of-truth; the surfaces are overlays);
`scripts/operator/build-configurator-api.py` translates the run POST body's `frontend`/`bake_openclaw`/
`bake_open_computer` into those env vars (frontend validated against a canonical `FRONTEND_CHOICES` set);
`webapp/build-configurator/index.html` grows an agent-layer row (a frontend `<select>` + two bake
checkboxes) that POSTs with the run + live-previews in the build-command pane; and `sovereign-osctl init`
gains a 6th "AGENT LAYER" decision (frontend + bake each runtime, recorded in the init state file and
folded into NEXT STEPS — the API key is never collected here, runtime-only per SDD-707).
`tests/lint/test_agent_layer_build_config_contract.py` (11 cases) pins the whole chain and
`tests/nspawn/test_sovereign_osctl_init.sh` is updated to the 6-decision reality.

An honest finding is recorded rather than forced: the third Round-B item — registering
frontend/openclaw/open-computer in `surface-map.py`/`doc-coverage.py` with a `cli_only` waiver — is
**retired as mis-shaped**. Those trackers enforce a `gaps=0` structural-ceiling invariant (every surface
shipped or "not applicable"-waived), but the agent layer's unshipped api/mcp/webapp surfaces are honestly
FUTURE, not structural-NA, and the system has no `cli_only` ceiling category — so a forced entry would
either falsely mark futures "not applicable" (gaming the anti-minimization audit) or redden CI. The
trackers are left untouched; a proper fix would add a new classifier waiver-category, decided deliberately.

### Added — operator documentation for the agent layer + a drift lint (2026-07-14)

Operator-directed (*"is it even all documented and how deep does the configuration goes?"*) (SDD-708).
Closes the doc half of F-2026-117. A surface map found the agent layer (SDD-704 frontend / 705 OpenClaw /
706 open-computer / 707 backend hotswap) fully wired into the IaC + `sovereign-osctl` and contract-pinned —
but the contracts stop at CLI `--help`, so it had reached no operator-facing surface. Now `docs/src/ai-backend.md`
gains a cohesive "The desktop + the agent runtimes" section (the `frontend set` face-swap, both installed-off
runtimes, and the `backend {local|anthropic}` hotswap, with the build-time knobs + the key-never-baked
discipline); `ops/manage.md` + `profiles/sain-01.md` gain the verbs; and a new 6-case
`test_agent_layer_docs_contract.py` drift-guards it (every agent-layer verb the CLI dispatches must be
documented). Docs-only — no code/units/metrics changed. Scoped follow-ons (Round B): the setup
wizard + build-configurator webapp integration and registering the subsystems in the §1g governance trackers.

### Added — agent-runtime backend hotswap: local model ↔ hosted Claude (2026-07-14)

Operator-directed (*"there should be a hotswap for [the] anthropic local ai API vs the claude ai anthropic
API for both. and it should be clear and easy how to swap this"*) (SDD-707). Closes F-2026-116; corrects
SDD-705/706. A double-check found the repo is Anthropic-first — `sovereign-gatewayd --http` serves an
Anthropic `/v1/messages` API + an OpenAI shim on `:8787` through the SDD-206 safety spine — but SDD-705/706
had pinned both agent runtimes to the raw vLLM `:8000`, bypassing the spine with no path to hosted Claude.
Now the local backend is repointed to the `:8787` gateway, and a `backend {local|anthropic|show}` hotswap is
added for both runtimes via a new `scripts/operator/agent-backend.py` (the single config renderer + swap:
flips OpenClaw's `agents.defaults.model.primary` and open-computer's `OPENAI_BASE_URL` to Anthropic's
OpenAI-compat endpoint). The hosted-Claude key is operator-supplied in a root-only
`/etc/sovereign-os/anthropic-key.env` — **never baked** — and both runtime units `EnvironmentFile` it.
`sovereign-osctl {openclaw,open-computer} backend …` is the clear/easy surface, parallel to
`sovereign-osctl frontend set` (the Desktop, SDD-704). New 10-case `test_agent_backend_hotswap_contract.py`;
grounding verified per runtime; SDD-705/706 lints updated to pin the delegation. Two upstream-behaviour items
(OpenClaw's local `anthropic-messages` path-append; Pi's tolerance of Anthropic OpenAI-compat quirks) are
box smoke-tests — the swap mechanism itself is verified.

### Added — open-computer: a QEMU AI-sandbox service, preconfigured to the local model (2026-07-14)

Operator-directed (*"this open-computer interesting alternative … integrate in the build"*)
(SDD-706 — the service axis of the SDD-703 arc; its heaviest + final round). Closes F-2026-114 and
**closes the SDD-703 frontend+agent-runtimes arc** (SDD-704 selector + SDD-705 OpenClaw + SDD-706
open-computer). open-computer (Mintplex-Labs, AGPL-3.0) is a QEMU VM (Debian guest + XFCE + Chromium)
an AI agent drives; now a build option shipping **installed-off** + **preconfigured to the local vLLM
endpoint** (SDD-702). A `provisioning.bake.open_computer` toggle + a `provisioning.open_computer` block
is threaded through mkosi-emit → provision-bake (stages the units, enables only the first-boot
installer). A first-boot `open-computer-install.sh` hook (non-fatal, resumable) installs QEMU/KVM +
OVMF + Node, sparse-clones + builds the open-computer CLI, downloads the ~3GB `base.qcow2` (resumable
`curl -C -` + sha256), and renders the LLM env (`OPENAI_BASE_URL` → the local endpoint; open-computer
auto-rewrites host `127.0.0.1` → the QEMU gateway `10.0.2.2` for the guest). The runtime
`sovereign-open-computer.service` runs `open-computer up` installed-off, `/dev/kvm`-gated, HOME
relocated to `/var/lib/sovereign-os/open-computer` (VM-host hardening waiver + every compatible
clause); `sovereign-osctl open-computer {status|on|off|install|url|logs|doctor}` is the lifecycle. The
SDD-704 selector's `open-computer-kiosk` value is wired to the verified `:9800` UI. New 11-case
`test_open_computer_provision_contract.py`; grounding verified against the repo's CLI/service code;
systemd README count 122→124 (102→104 service). Ships OFF + `/dev/kvm`-gated; the real QEMU/KVM
install + base download + booted sandbox are unverified in CI (no network/KVM/display).

### Added — OpenClaw agent runtime: Node gateway daemon, preconfigured to the local model (2026-07-14)

Operator-directed (*"include OpenClaw in the options of the build … add the preconfiguration
options"*) (SDD-705, the service axis of the SDD-703 arc). Closes F-2026-115. OpenClaw (npm
`openclaw`, MIT; the :18789 Node gateway, NOT Anthropic) is now a build option shipping
**installed-off** + **preconfigured to the local vLLM endpoint** (SDD-702). A `provisioning.bake.openclaw`
toggle + a `provisioning.openclaw` block ({endpoint, model_id, gateway_port, node_major}) is threaded
through mkosi-emit → provision-bake (stages the units, enables only the first-boot installer — no
install at postinst since NodeSource/npm are unreachable in the image build). A first-boot
`openclaw-install.sh` hook (VM-tolerant, non-fatal, resumable) ensures a band-satisfying Node
(NodeSource 24; OpenClaw's engines exclude 24.0–24.14), `npm install -g openclaw`, and renders
`~/.openclaw/openclaw.json` (JSON5, `api: openai-completions`, `"vllm/*"` auto-discovery) pointed at
the local endpoint — no external channels (SDD-703 D5). The runtime `sovereign-openclaw.service` runs
`openclaw gateway` installed-off with HOME relocated to `/var/lib/sovereign-os/openclaw` so it stays
ProtectHome=read-only + ProtectSystem=strict (no waiver); `sovereign-osctl openclaw {status|on|off|install|logs|doctor}`
is the lifecycle. New 10-case `test_openclaw_provision_contract.py`; grounding verified against the
npm registry + repo docs; systemd README count 120→122 (100→102 service). Ships OFF — nothing runs
until `openclaw on`; the real Node/npm install + gateway boot are unverified in CI (no network/registry).
The open-computer QEMU sandbox is the arc's remaining round.

### Added — swappable boot-frontend selector: GNOME ↔ dashboards-kiosk, live (2026-07-14)

Operator-directed (*"be able to chose at any point to start in one or another or even disable both"*)
(SDD-703 design + SDD-704 implementation). Closes F-2026-113 (MED); scopes F-2026-114 (open-computer,
→ SDD-706) + F-2026-115 (OpenClaw, → SDD-705). The boot frontend was hard-wired GNOME — an env-only
`SOVEREIGN_OS_DESKTOP` knob unreachable from the profile, no runtime switch. Now a `provisioning.frontend`
block ({`default`, `install`}) + schema is threaded through mkosi-emit → the installer (restructured to
*stage each `install:` stack → activate the `default`*), a new `sovereign-frontend-kiosk.service`
(cage + fullscreen browser at a URL from an env file, seatd-seated, R171-hardened + a graphical-session
waiver), and a new `sovereign-osctl frontend {status|list|set}` verb (`scripts/operator/frontend.py`) that
flips gnome ↔ dashboards-kiosk ↔ open-computer-kiosk ↔ none live — no reflash. Default stays `gnome`
(behaviour-preserving; SDD-703 D1 adopted provisionally + overridable). New 14-case
`test_frontend_selector_contract.py`; systemd fleet README count 119→120 (99→100 service). The kiosk ships
disabled by default, so boot is unchanged for the shipping profile; a real kiosk session on hardware is
unverified (no seat/GPU/display in CI). OpenClaw (SDD-705) + open-computer sandbox service (SDD-706) are the
next big rounds of the arc.

### Added — inference model provisioning: the vLLM Oracle tier gets a real model at first boot (2026-07-14)

Operator-directed build-and-flash readiness, inference (operator upgraded the Oracle model to Llama 4 Scout)
(SDD-702). Closes F-2026-112 (HIGH). The repo has a 3-tier inference architecture (Pulse=BitNet ternary,
Logic=Qwen3-Coder, Oracle=vLLM on Blackwell) whose serve units read `/mnt/vault/models/<name>`, and vLLM is
already in operator-deps `[pip]` — but nothing downloaded any model, so the inference tier was weightless. New
first-boot `inference-model-provision.sh` hook + unit downloads the profile's `provisioning.model` (default
upgraded to `meta-llama/Llama-4-Scout-17B-16E-Instruct` — ~60GB Q4, fits the 96GB card w/ KV headroom) to
`/mnt/vault/models` via `huggingface-cli` (sharded, resumable, gated-token aware via `SOVEREIGN_OS_HF_TOKEN`),
then points `ORACLE_MODEL` at it. Fully non-fatal (missing CLI/token/space/error → clean skip; never bricks
first boot; resumable post-flash) + VM-skipped + idempotent; the unit requires the ZFS vault mount and doesn't
time out the download. Serving stays operator-launched per the installed-off posture. New
`test_inference_model_provision_contract.py` (6 cases). 1 hook + 1 unit + 1 lint + profile block + schema.

### Added — NVIDIA GPU bring-up: install the pinned ≥570 driver + apply the power caps at boot (2026-07-14)

Operator-directed build-and-flash readiness review, GPU bring-up (driver channel: CUDA-repo-pinned `.run`
≥570) (SDD-701). Closes F-2026-109 (HIGH) + F-2026-110 (MED). **F-2026-109**: trixie ships nvidia 550.163,
which predates the Blackwell GB202 (RTX PRO 6000 Max-Q + RTX 5090), and nothing installed a ≥570 driver — a
flashed box booted with both cards dark. New first-boot `nvidia-driver-install.sh` hook + unit installs the
pinned open-kernel `.run` (version from a new `provisioning.nvidia` profile block; refuses <570; fails loudly
on a bad URL), purges the conflicting distro 550, installs `--dkms --kernel-module-type=open`, and under
secure boot signs the built modules with the enrolled MOK (`/var/lib/sovereign-os/mok`) + writes
`/etc/dkms/nvidia.conf` so kernel-update rebuilds re-sign (else the kernel rejects the modules). Serialized
initramfs via SDD-998 `boot_regen`; reboot marker surfaced on the console. **F-2026-110**: each GPU's
`tdp_watts` (300W / 350W-from-575W-stock) was declared but never applied — the 5090 would run at 575W, ~225W
over intent. New every-boot `nvidia-power-limit.sh` hook + unit (multi-user.target, since `-pl` doesn't
persist) enables persistence mode + applies each card's cap via `nvidia-smi -pl`, matched by PCI device-id.
New `test_nvidia_gpu_bringup_contract.py` (8 cases) pins the MOK-signing / ≥570-floor / per-card-cap
properties. Static-verified (bash -n, lints); the real driver install + power draw need the physical machine
(no Blackwell/NVIDIA in CI). 2 hooks + 2 units + 1 lint + profile block + firstboot rewiring.

### Fixed — operator sudoers: risk-tier the OPS grants + lock them against privilege-escalation drift (2026-07-14)

Operator-directed build-and-flash readiness review ("everything that needs to be in the sudoer are there
too?") (SDD-700). Closes F-2026-107 (MED) + F-2026-108 (LOW). **F-2026-107**: `operator-sudoers.sh`'s per-verb
cockpit alias was lockstep-linted, but the OPS bucket (one opaque `SOVEREIGN_OS_OPS` alias) had no coverage
lint and no privesc guard — `test_operator_sudoers.py` only checked "not `NOPASSWD: ALL`" + absolute paths, so
adding `bash`/`dd`/`systemctl`/`tee`/`chmod` to a bucket would silently make the scoped drop-in
root-equivalent while every lint passed. Fixed by (1) splitting the opaque alias into three self-documenting
risk tiers — `SOVEREIGN_OS_DIAG` (read-only probes), `SOVEREIGN_OS_IMAGE` (HIGH-RISK loop-mount),
`SOVEREIGN_OS_PROC` (kill) — and (2) rewriting the lint to lock each tier's command set to the reviewed set and
forbid any privilege-escalating binary (shells, interpreters, `dd`/`tee`/`chmod`/`chroot`/`systemctl`/pkg
managers/pagers/`find`/`tar`/`su`/`sudo`…) from appearing in any NOPASSWD grant. Same commands granted, only
split across named aliases; `visudo`-valid. **F-2026-108**: `_action_exec.py`'s docstring pointed at a
non-existent `systemd/sudoers.d/…` path; corrected to `config/sudoers.d/…`. Band note: the 950–999 audit band
filled, so this readiness arc continues in the newly-registered 700–799 block.

### Fixed — build-pipeline safety: a missing/critical step must fail the build, not silently pass (2026-07-14)

Operator-directed build-and-flash readiness review (SDD-999). Closes F-2026-105 (HIGH) + F-2026-106 (HIGH).
**F-2026-105**: `scripts/build/orchestrate.sh` had an inconsistent contract — the dry-run (`cmd_preflight`)
treats a missing/non-executable step as failure, but the real build (`cmd_run`) silently skipped it ("will
land in subsequent PR") and still reported "pipeline complete", so a missing `08-image-sign`/`09-image-verify`
(or any step) would emit an unsigned/unverified image while succeeding. `cmd_run` now treats a missing step as
fatal (matching the dry-run); `SOVEREIGN_OS_ALLOW_MISSING_STEPS=1` keeps the old skip for deliberate partial
dev builds. **F-2026-106**: `scripts/build/provision-bake.sh` is NON-FATAL BY DESIGN (`set -uo pipefail`, every
step `|| log …`) — correct for the many optional steps — but the blanket `exit 0` made even image-bricking
steps non-fatal, so a failed operator-account create or a failed `systemctl enable sovereign-firstboot.target`
would still "succeed", yielding an image with no operator login or an inert first boot. Added a `crit` tracker:
the operator-account and first-boot-enable steps now verify (the latter checks the `multi-user.target.wants`
symlink, since an offline enable can no-op silently) and `crit` on failure, and provision-bake exits non-zero
when any critical step failed. Optional steps stay non-fatal. 2 build scripts, no crate/webapp change.

### Fixed — first-boot orchestration correctness: the flashed image must actually run its hooks (2026-07-14)

Operator-directed build-and-flash readiness review ("we need to fix everything before I build and flash
like I said … the IaC is ready through and through and will be done properly and in proper timing and
sequence?") (SDD-998). Closes F-2026-101 (CRIT) + F-2026-102 (HIGH) + F-2026-103 (MED) + F-2026-104 (LOW).
**F-2026-101 (CRIT)**: `sovereign-firstboot.target` grouped 10 first-boot oneshots, but the install path
enables only the target — and `systemctl enable <target>` never processes the members' `[Install]
WantedBy=`, while `PartOf=` propagates stop/restart only. So 10 units declared membership and 0 were
reachable: on first boot no hook ran and the flashed box came up as bare Debian (no VLAN/network, no
NVIDIA/VFIO bind, no ZFS ARC clamp, no Tetragon policy). Fixed by giving the target `Wants=` for all 10
members (each still self-gates `ConditionFirstBoot=yes`+`ConditionVirtualization=no`). **F-2026-102 (HIGH)**:
three members regenerate the initramfs on first boot with no ordering between them → parallel
`update-initramfs -u` corrupts it → unbootable. Fixed with a shared `boot_regen` helper in `common.sh`
that `flock`-serializes every `update-initramfs`/`update-grub`. **F-2026-103 (MED)**: nvidia-driver-bind
warned "may need reboot" only in the journal while vfio surfaced a console flag; the nvidia unit now writes
`.nvidia-bind-needs-reboot` and the completion service prints one `/dev/console` notice covering both GPU
markers. **F-2026-104 (LOW)**: the opt-in `sovereign-guardian-core.service` (post-deploy, not flashed) could
226/NAMESPACE crash-loop if started before `/mnt/vault` mounts — added `After=zfs.target` +
`RequiresMountsFor=/mnt/vault/context` + `-`-prefixed ReadWritePaths (ExecStart verified correct). New
`tests/lint/test_firstboot_target_membership.py` (4 cases) keeps the target's `Wants=` == the
`WantedBy=`-declaring member set both directions. 4 systemd units + `common.sh` + 3 hooks + 1 lint; no crate
or gatewayd/cockpit/webapp change; no new dependency.

### Added — per-crate `✅ integrated` flag on the crate-inventory, validated by named usage (2026-07-14)

Operator-directed (phase-1 audit continuation — "were you not suppoed to flag the crates that are done /
integrated?") (SDD-997). Closes F-2026-100 (LOW). After SDD-996 flagged done SDDs, the crate map gained the
parallel: `gen-crate-inventory.py` now renders a per-crate ✅ **integrated** badge for the 57 crates in the
production-binary closure (gatewayd/telemetry/resource-control), each with a usage note naming the concrete
consumer(s) / that it runs as a binary — the usage validates the integration. Per the operator's definition,
integrated means actually USED by a running path, not merely referenced: a cockpit crate wasm-bridged for a
panel (SDD-800, 0 wired) or a demo/hub-only crate is not in the closure and never flagged. New
`tests/lint/test_crate_inventory_integrated_flag.py` keeps the flagged set == the closure, requires a usage
note per flag, and guards the used-not-referenced boundary. Generator + regenerated inventory + 1 lint.

### Changed — SDD INDEX status completeness: merged SDDs marked `complete`, enforced by a lint (2026-07-14)

Operator-directed (phase-1 audit continuation, "continue" → "merged → complete") (SDD-996). Closes
F-2026-099 (LOW). SDD-961 gave the INDEX status hygiene (valid vocabulary + no stale branch refs) but left
the draft→complete transition unenforced — only 2 of 178 rows were `complete` while 44 declared "shipped on
branch". 42 rows flipped `draft→complete` (exactly the draft rows with a clean shipped-marker and no caveat
— the reliable in-band merged signal). Deliberately not flipped: 3 caveated shipped rows (awaiting-decision
/ stale stacked-PR), the 76 older rows carrying no shipped claim (inferring complete without evidence would
fabricate status — a per-row operator pass is the honest close), and the deliberate non-draft statuses
(40 review / 4 active / 4 accepted / 1 scoping). Now 44 complete (was 2). New
`tests/lint/test_sdd_index_status_completeness.py` enforces that a clean shipped-marker row never sits at
`draft`. No SDD content changed — only status cells that already declared shipped.

### Added — crate-inventory generator gains a `--check` freshness gate + sync lint (2026-07-14)

Operator-directed (phase-1 audit continuation, "continue") (SDD-995). Closes F-2026-098 (LOW).
`scripts/docs/gen-crate-inventory.py` (generates `docs/architecture/crate-inventory.md`, the map of every
workspace crate) was the one living-doc generator without a `--check` gate — its `main()` unconditionally
wrote the page, with no lint, so a crate added/removed/re-described could silently leave the inventory
stale. The page-building body is now factored into `render() -> str`; `main()` gains `--check` (regenerate
in-memory → compare → exit 1 on drift, else rewrite), matching `gen-sdd-catalog.py`. New
`tests/lint/test_crate_inventory_sync.py` (4 cases) fails CI if the committed page drifts from the tree.
Inventory content unchanged — staleness is now a CI failure, not a silent gap. Generator + 1 lint; no
crate/runtime/webapp change.

### Fixed — inference router bounds the request body instead of crashing / over-allocating (2026-07-14)

Operator-directed (phase-1 audit continuation, "we continue") (SDD-994). Closes F-2026-097 (LOW). The
OpenAI-compatible front door `scripts/inference/router.py` read its POST body as
`length = int(self.headers.get("Content-Length", 0)); raw = self.rfile.read(length)` — a non-numeric
`Content-Length` raised an uncaught `ValueError` (handler crash + dropped connection), and the read
trusted the client length unbounded (a huge value → memory-DoS). A pure `parse_content_length()` helper
now returns `(length, error)` — malformed/negative → 400, oversize → 413, absent/valid → the length —
and `_do_post_inner` rejects before reading. Cap is a generous 16 MiB (the router proxies inference
requests; long prompts are legitimately large). New 11-case boundary regression
`tests/unit/test_router_body_bounds.py`; 42 router tests pass; ruff clean. Router-only + 1 test — no
cockpit/webapp/crate/other-daemon change. Brings the one unguarded body-read up to the sibling operator
daemons' existing bar (`control-exec-api` `_MAX_BODY`, `code-console-api`, `brain-api`).

### Changed — SAIN GPU topology: RTX PRO 6000 primary + RTX 5090 internal secondary + RTX 4090 OcuLink eGPU; VFIO now opt-in (2026-07-13)

Operator-directed hardware change (SDD-993, decision **D-021**). All **three cards are in the build**: the **RTX PRO
6000 Blackwell 96GB (~600W)** is the **primary / main Oracle Core** (internal, PCIEX16_1 x8) — unchanged; the **RTX 4090
24GB** moves OUT of its internal slot to an **OcuLink eGPU** (OcuLink-to-M.2 adapter on a **chipset M.2 slot**, PCIe 4.0
x4 / 64 Gbps); and the new **RTX 5090 32GB (TUF-RTX5090-O32G-GAMING)**, power-limited **~350W** (Blackwell GB202,
512-bit — same FP4/NVFP4 family as the PRO 6000), takes the 4090's vacated **internal x8 slot** (PCIEX16_2). Two internal
cards ⇒ **x8/x8 bifurcation stands**, and **M.2_2 MUST remain empty** (it shares lanes with PCIEX16_2 / the 5090) — the
OcuLink adapter is on a chipset M.2 slot, NOT M.2_2. One primary + **two secondaries** (5090 internal + 4090 eGPU); no
future/missing card. Grounded in researched specs (5090 stock TGP 575W → 350/575 ≈ 61%, near the Blackwell efficiency
knee; OcuLink-M.2 ≈ 7.9 GB/s, fine for inference).

**VFIO is now opt-in** (operator: *"not in a VM by default"*): the 4090's default `role` is host-resident (bare-metal,
directly usable by the host inference stack); the VFIO-isolated sandbox is an opt-in mode (`role: vfio`), and
`vfio-bind-4090.sh` no-ops unless opted in. The isolation machinery is preserved — a default-flip, not a removal.

**Reconcile landed this session**: `profiles/sain-01.yaml` GPU block (PRO 6000 primary + 5090 secondary + 4090 egpu;
`m2_2_empty` restored) + `schemas/profile.schema.yaml` (`egpu` role) + `crates/sovereign-pcie-topology` +
`sovereign-pcie-advisor` (x8/x8 layout, M.2_2 empty) + `friction-audit-spec.sh` + pinning lints; `sain-01-master-spec.md`
+ `profiles/sain-01.md`; `config/hardware/m003` + `config/inference/m077` additive reconciles (both internal cards are
Blackwell FP4; the Oracle stays on the PRO 6000); M040 additive OcuLink note (verbatim rows untouched);
`profiles/runtime/*.yaml` + `trinity-runtime-profiles.md`; the D-21 LM-orchestration panel (three cards); `model-catalog.md`;
`docs/decisions.md` D-021. DSpark-from-DeepSeek is a separate follow-up SDD (PR 2).

### Fixed — gateway daemon survives a poisoned lock instead of cascading (2026-07-13)

Operator-directed (phase-1 audit continuation) (SDD-992). Closes F-2026-065 (LOW, daemon-path half). Every mutex access
on the gateway request path used `.lock().expect("… poisoned")`; a poisoned `Mutex` stays poisoned, so one panicking
request thread cascaded — every subsequent request that locked the same mutex panicked too, taking the daemon down one
request at a time. Fix: two guards matched to what each lock protects. `cortex_guard()` DECLINES a poisoned cortex (the
decision engine may hold torn state) — handlers return `GatewayResponse::Error` instead of panicking (`persist_memory`
maps to an I/O error; `maintain` skips the cycle). `ledger_guard()` RECOVERS a poisoned ledger via `into_inner()` (pure
counters — dropping an already-computed response over a stat lock would be wrong). 15 daemon call sites converted. The
two `sovereign-coat` `.expect()`s are pure-lib invariant guards, not lock state — kept, per the finding. New tests poison
a mutex the real way (a thread panics holding the guard) and assert the daemon declines/recovers gracefully:
`cortex_guard_declines_a_poisoned_lock_instead_of_panicking`, `infer_on_a_poisoned_cortex_returns_error_not_panic`,
`ledger_guard_recovers_a_poisoned_lock_and_keeps_serving`. Verified: `cargo test -p sovereign-gatewayd` 71 lib + 4 + 18
integration passed (+3); `cargo fmt --all --check` exit 0; clippy clean. gatewayd-crate only, no coat/cockpit/webapp/
`scripts/operator` edits.

### Fixed — CoAT no longer serializes generation: cortex lock narrowed to per-recall (2026-07-13)

Operator-directed ("CoAT-through-jobs runtime fix") (SDD-991). Advances F-2026-063 (MED) + F-2026-090 (OPP).
`GatewayServer::coat()` held the shared `self.cortex` mutex across the whole CoAT deliberation (up to 12
model-backed expansions) because `CortexRecall` borrowed `&Cortex` — and that is the same mutex `infer()`/`explain`/
`simple`/`deliberate`/every other `/v1/coat` locks, so one model-backed CoAT serialized all other generation for the
full deliberation. Fix: `CortexRecall` now borrows the mutex (`&Mutex<Cortex>`) and locks **per recall** — the brief
short-hold pattern `infer()` already uses — and `coat()` no longer pre-locks, so between expansions the cortex mutex is
free and `/v1/infer` (and every other decision surface) interleaves instead of blocking. Routing the caller through the
background-jobs runtime alone would NOT have fixed this (`_run_deliberation` issues the same synchronous `POST /v1/coat`);
the serialization had to be fixed in `coat()`. CoAT is read-only on the cortex, so per-recall locking is safe; the poison
path now degrades to empty recall instead of panicking the request thread (softer than the whole-loop `.expect()`, a nod
to F-2026-065). New tests `coat_recall_releases_the_cortex_lock_between_recalls` +
`coat_does_not_hold_the_cortex_lock_across_deliberation` prove the mutex is free after a recall and after a full
deliberation. Verified: `cargo test -p sovereign-gatewayd` 68 lib + 18 integration passed; `cargo fmt --all --check`
exit 0; clippy clean. gatewayd-crate only (private struct), no cockpit/webapp/`scripts/operator` edits. Deferred
follow-ups: async caller (webapp→jobs UI, contended surface) and a model-backed integration test (needs a loadable
model fixture, overlaps F-2026-066).

### Changed — MS003 writer sweep: real signatures on the decision-writers (Option B, PR 2) (2026-07-13)

Operator-directed ("MS003 implementation arc") (SDD-990). Advances F-2026-034 (CRIT) — PR 2 of the arc, consuming the
SDD-989 primitive. Wires `ms003.sign()` into the **eight runtime decision/mutation writers** that until now hard-coded
the `unsigned-pending-MS003` placeholder: `scripts/intelligence/{memory-store,memory-decide}.py`,
`scripts/inference/{adapter-decide,adapter-gate}.py`,
`scripts/lifecycle/{approval-decide,save-state,session-decide,session-runtime}.py`. Each gained a best-effort import +
`_sign()`/`_signed()` helpers; every record-construction site is wrapped `{...}` → `_signed({...})`. With an operator
key provisioned, every persisted mutation/decision record now carries a **real ed25519 signature** that
`ms003.verify()` accepts; **without a key the output is byte-identical to before** (`sign()` falls back to the
placeholder and never raises, so no node/CI changes until `gen-key` runs). Care taken for two site shapes: records that
gain fields after the placeholder line are signed after full assembly; the `memory-store` undo re-signs its change
record after flipping `reversed` (signatures are point-in-time). Provenance spans that borrow a decision's signature are
left as linkages (decision signed before emit). New `tests/unit/test_ms003_writer_signing.py` — 4 tests proving the
wiring end-to-end (memory-decide in-process + approval-decide subprocess): a provisioned key yields a durable ledger
record whose signature verifies and whose tampering is rejected; keyless → placeholder. Verified: writer-signing 4
passed; full tests/unit 505 passed; ruff clean. No new dependency, no gatewayd/cockpit/`unsafe`/crate edits.
F-2026-034 producer half now complete; the selfdef-side verifier remains (selfdef-owned).

### Added — MS003 ed25519 signing primitive (Option B, producer half) (2026-07-13)

Operator-directed (AskUserQuestion → "B — sovereign-os mints") (SDD-989). Advances F-2026-034 (CRIT) — the
`unsigned-pending-MS003` placeholder every SDD-142..204 record carries. Implements the operator's Option-B choice
from SDD-984: **sovereign-os mints a real ed25519 signature over each record with the operator key identity; selfdef
verifies.** Real signatures now, with no coupling to selfdef uptime (preserves MS043 offline-survivability) and the
R10212 selfdef boundary untouched (signs only records sovereign-os already authors). **PR 1 of 2 = the producer
PRIMITIVE only** (crypto reviewed in isolation; PR 2 sweeps the ~8 writers). New `scripts/lib/ms003.py`:
`sign(record)` → `ms003:ed25519:<keyid>:<sig>` when an operator key is present, else the historical placeholder —
**never raises** (a signing fault degrades to the placeholder, never breaks a mutation write); `verify()` (selfdef-side
reference), `canonical_bytes()` (record minus `signature`, sort_keys, compact, UTF-8 — the byte contract),
`is_signed()`, `keyid()`, provisioning CLI `gen-key`/`pubkey`/`status`. **No new dependency**: the `cryptography` wheel
is unimportable here, so signing shells to the system `openssl` (already a hard dep), keeping the scripts stdlib-only +
locally verifiable. **Opportunistic**: a real signature needs both an ed25519-capable openssl and a key at
`$SOVEREIGN_OS_MS003_KEY` (default `~/.sovereign-os/ms003.key`); a keyless node behaves exactly as today.
Wire format (the contract selfdef implements): keyid = first 16 of base64url(raw 32-byte pubkey), sig =
base64url(64-byte ed25519 sig), signed bytes = `canonical_bytes`. New `tests/unit/test_ms003_sign.py` — 6 tests
(no-key fallback, never-raises, canonical determinism, placeholder-never-verifies, and a skip-if-no-ed25519 full
round-trip with tamper + wrong-key rejection). Verified: pytest 6 passed; CLI gen-key→sign→verify smoke; ruff clean.
No record writer modified (PR 2), no gatewayd/cockpit/`unsafe`/crate edits. F-2026-034 stays OPEN (producer half).

### Added — panel reserved-port contract lint (2026-07-13)

Operator-directed ("we continue") (SDD-988). Closes F-2026-075 (LOW). Promotes panel.sh's runtime port-collision
guard (the 2026-07-03 ux-design-audit-api:8100 incident) into a CI contract.

- **`tests/lint/test_panel_reserved_ports.py`** — reads the reserved ports (configurator 8100 / dashboard 8443 /
  live-reload 8136) from panel.sh's own defaults (the same single source the runtime guard uses) and fails if
  any `sovereign-*-api.service` unit declares one. Read-only — no panel.sh edit; pairs with the existing
  no-two-units-share-a-port lint.
- Verified: 2 passed (53 API units, 0 collisions); ruff clean. Collision-safe.

### Added — local pre-push cargo-fmt gate (2026-07-13)

Operator-directed ("we continue") (SDD-987). Closes F-2026-095 (MED, root-cause half). The July arc landed
52 fmt violations because it lived on a long-lived branch that bypassed CI's fmt gate until the audit.

- **`scripts/git-hooks/pre-push`** — runs the CI-exact `cargo fmt --all --check` before a push reaches the
  remote; reads cargo's exit directly (no pipe masking), blocks + prints `cargo fmt --all` on violations,
  skips gracefully without the Rust toolchain, `git push --no-verify` to bypass.
- **`tests/lint/test_fmt_hook_contract.py`** — keeps the hook and CI in lockstep (both must run the same gate).
- Verified: hook `bash -n` clean + executable; `cargo fmt --all --check` exit 0 on the tree; 4 contract tests +
  hook-hygiene/scripts/shell-safety green; ruff clean. Collision-safe.

### Added — crate dependency-graph contract lint (2026-07-13)

Operator-directed ("we continue") (SDD-986). Closes F-2026-009 (OPP). Turns the audit's ad-hoc 413-orphan
discovery into a standing CI signal.

- **`tests/lint/test_crate_graph_contract.py`** — parses every `crates/*/Cargo.toml` (repo convention; the
  pytest lint job has no `cargo`), builds the internal dependency graph (reachable = depended-on by another
  workspace crate OR a binary), and asserts **every orphan is `sovereign-cockpit-*`** (orphan-by-design,
  wasm-bridged per SDD-800). Empirical: 717 crates / 41 binaries / 265 consumed / 413 orphans, all cockpit,
  0 non-cockpit — a NEW non-cockpit orphan now fails the instant it lands.
- Verified: 2 passed; ruff clean; corroborates SDD-962's F-2026-002 closure. One new lint file — collision-safe.

### Added — cockpit functional-execution close-out decision-package (2026-07-13)

Operator-directed ("scope F-2026-035") (SDD-985). The "single largest planned UX unlock" turns out to be
**~90% already shipped**: research found Phase 1 (the `control-surface.js` Execute button + type-to-confirm +
graceful degrade) done, Phase 2 done for the SDD-048..052 engines, Phase 3 partial by design. The stall was
documentation, not engineering. Docs only.

- **`docs/sdd/985-cockpit-execute-unlock-decision-package.md`** — the reconciliation: what's actually shipped
  vs the plan, the MS003 independence (Execute ships on presence+confirm, not a real signature), and the
  operator decisions (D1 close Q-047-D as obsolete — branch merged via PRs #110–#118; D2 ratify Q-047-B
  selfdef-proxy; D3 ratify the Phase-0.5 sudoers reversal; D4 add the `cockpit_action_total` alert rules).
- F-2026-035 de-escalated from "stalled HIGH" to "shipped; close-out pending" in the ledger.
- Docs only — every surface read, never written; collision-safe.

### Added — MS003 commit-authority decision-package (2026-07-13)

Operator-directed ("yes lets go, lets do it") (SDD-984). Scopes F-2026-034 (CRIT) — the cross-cutting blocker
every SDD-142..204 ships `unsigned-pending-MS003` against. A DECISION-PACKAGE, not an implementation: research
found MS003 is a **selfdef-owned milestone** (no local spec), so the core policy question — does a
locally-executed sovereign-os-owned mutation get a real signature, and who mints it — is operator-gated.

- **`docs/sdd/984-ms003-commit-authority-decision-package.md`** — current state (presence-gate + confirm +
  audit; `signature` is a placeholder; no mutation-signing crypto exists), the surfaces re-baselined (34 owned
  controls + 6 decision-writers + selfdefctl parity proxy + M065 sign-off), three options (A selfdef-mints /
  B recommended sovereign-os-mints-ed25519-selfdef-verifies / C formalize-honestly-unsigned), 6 open questions,
  and the blocking cross-repo step (the selfdef MS003 signature format).
- F-2026-034 ledger back-annotation (scoped, not closed; SDD-055→SDD-015/048 mislabel corrected).
- First real use of the SDD-981 board: coordination messages to operator + the core-runtime lane.
- Docs only — every mutation surface read, never written; collision-safe.

### Added — cold-start signpost for the July intelligence-layer arc (2026-07-13)

Operator-directed ("lets go then" — the recommended next collision-safe audit item) (SDD-983). Closes
F-2026-060 (CRIT), F-2026-036 (HIGH), F-2026-064 (LOW). The July 11–12 intelligence-layer arc (Brain
observatory, CoAT engine, background-jobs runtime, Anthropic Messages API, Plan-mode/AUQ/classifier, HF-BPE
tokenizer, durable Cortex memory) shipped + merged with no cold-start signpost. Docs only.

- **`docs/handoff/008-july-intelligence-layer-arc.md`** — the cold-start anchor (what shipped + evidence
  paths, ports brain 8141 / jobs 8142 / gateway 8787, verified-good properties, open follow-ups, next-work
  order); supersedes handoff 007.
- **`docs/src/gateway-api-reference.md`** — every `/v1` route from `crates/sovereign-gatewayd/src/http.rs`
  (deliberation ladder, Anthropic surface, model-mgmt, observability); delineates `/v1/deliberate` (best-of-N)
  vs `/v1/coat` (tree/ladder) per F-2026-064; linked from SUMMARY.md.
- **`docs/decisions.md` D-020** — retroactive architecture record (documenting shipped state; names the open
  F-2026-034 MS003 sub-decision). `context.md` + handoff INDEX + findings-ledger back-annotations.
- Verified: context.md counts + catalog-sync + reachability + uniqueness lints green; API page linked (no
  orphan); no code/behaviour change (`http.rs` read-only).

### Changed — surface the parallel-session protocol in the agent brain files (2026-07-13)

Operator-directed ("you did not even update claude and agents.md files and such") (SDD-982). SDD-980/981
shipped the machinery but a fresh/post-compaction session couldn't discover it. Wired it into the two
surfaces a session reads:

- **`context.md`** "Parallel-session conventions" grew 3→6 steps: identify yourself (SESSIONS.md +
  `session_comms.py whoami`), collisions self-heal (SDD-980 resolver), talk to sessions + operator (SDD-981
  board — inbox/post/reply/thread). The higher-up summary bullet now names all three.
- **`scripts/claude-code-env/templates/CLAUDE.md`** (the per-session CLAUDE.md the env-bootstrap installs)
  gained a methodology-table row: at session start `whoami` + check `inbox`; collisions self-heal; message
  the board. Docs only; no behaviour change.

### Added — parallel-session communication protocol: sessions ↔ sessions ↔ operator (2026-07-13)

Operator-directed ("what about the communication protocol between each sessions and me yeah, lets do, point 1.
and lets do this right and make sure its documented properly") (SDD-981). Builds on SDD-980's session identity —
turns the resolver's ledger seed into a real bidirectional channel. Docs + scripts + `.gitattributes` only.

- **`scripts/git/session_comms.py`** (stdlib; `whoami`/`post`/`reply`/`ack`/`inbox`/`thread`/`list`) — addressed,
  threaded messages between any session and between sessions and the operator. `from`/`to` are a session-id
  (from SESSIONS.md), `operator`, or `all` (broadcast).
- **`docs/sdd/MESSAGES.md`** — append-only 7-column board (`msg-id · utc · from · to · re · subject · body`),
  `merge=union`. Design: one message = one line (union-safe), ids unique without coordination, identity from
  the branch, and **derived** answered-state (open until the addressee replies — never a mutable flag).
- **Discovery**: the `post-merge` hook nudges you when a pull brings new mail (`lib/session-inbox-notify.sh`),
  silent when empty; `inbox` on demand.
- New lints: `test_session_comms.py` (9 hermetic cases) + `test_messages_board.py` (board integrity).
- Verified live: whoami→phase-1-audit; direct+broadcast+operator posts; a reply flips the message to answered;
  thread renders the chain; pipe+newline body round-trips.

### Added — self-healing parallel-session SDD conflicts: session registry + auto-resolver (2026-07-13)

Operator-directed ("we could have actually useful ones to resolves conflict, automatically and then give a
warning if we can't … we know the logic and how to resolve the conflict of numbers and lines"; aggressiveness
"Auto-apply, verify, warn on doubt"; + "a way for sessions to identify themselves … even talk to each other /
talk to me"; + "a note about what was done … and potentiel further needs") (SDD-980). Makes the SDD-100 band
convention self-healing — docs + scripts + `.gitattributes` only, collision-safe.

- **`scripts/git/sdd_conflict_resolver.py`** (stdlib; `--check`/`--dry-run`/`--apply`) — on a duplicate SDD
  number, the file whose declared `Number band:` does NOT contain the number is the intruder; it is renumbered
  into the next free slot of its own band (rename + internal refs + **surgical** INDEX/mandate row renumber,
  each row identified by its self-declaring last cell — never a blind global replace), the catalog + counts
  are regenerated, and it **verifies** with the uniqueness/contiguity/counts lints; on any doubt it **reverts
  and warns** with the exact fix. Wired into `post-merge`/`post-rewrite` (`lib/sdd-resolve.sh`) — silent on the
  happy path, changes left UNSTAGED, never auto-commits.
- **`docs/sdd/SESSIONS.md`** — the session registry (sessions identify themselves: id→band→branch→purpose).
- **`docs/sdd/RESOLUTION-LOG.md`** — append-only cross-session ledger (what was resolved + follow-ups);
  `merge=union`, the seed of the session↔session / session↔operator message board.
- Fixed `SDD-800`'s stale band declaration (`950–999`→`800–899`) — the exact drift the new
  `test_sdd_band_declaration_matches_number.py` forbids.
- Verified: live plant of a cockpit-wasm intruder at SDD-979 → `--apply` renamed to 801, renumbered both
  rows, owner kept 979, 3 lints green, ledger written; warn-on-doubt live (no-band intruder → no-op + warn);
  `test_sdd_conflict_resolver.py` 4/4, `test_session_registry.py` 3, `test_sdd_band_declaration_matches_number.py` 1.

### Added — retrieval hub decorator flags + cached-RAG serving (2026-07-13)

Operator-directed ("1 and 2 both, sequentially, big PR, do not minimize") (SDD-978 + SDD-979; advances
F-2026-093). A two-part crate-integration arc that runs the full `sovereign-retrieval` surface in shipping
binaries — entirely in the crate layer, off the shared-registry collision surface.

- **`sovereign-retrieval`** (additive): `impl Retriever for Box<R>` (a boxed retriever is a retriever) + a
  `augment_prompt(retriever, prompt, top_k)` free fn factored out of `RagResponder::augment` (ground without
  generating). No behaviour change; 63 tests pass.
- **`sovereign-chat` (SDD-978)**: `--hybrid` / `--rerank` / `--injection-filter` / `--keyphrase` flags
  (combinable, each implies `--rag`), assembled by `build_retriever` into one `Box<dyn Retriever>` with a
  labelled pipeline (`keyphrase → hybrid(BM25+embed) → rerank → dedup → diversify → injection-filter`).
- **`sovereign-serve` (SDD-979)**: `--rag` grounds each query then serves the grounded prompt through the
  cost-aware cache — a repeated grounded query is a genuine $0 exact cache hit (retrieval × the cache).
- Verified: `cargo test` chat 28 / serve 18 / retrieval 63 passed; live full chat pipeline grounds; live
  serve `--rag` shows first-serve miss then $0 exact hit on repeat; fmt --all --check + clippy clean.

### Added — deepen chat RAG with the rerank pipeline (2026-07-13)

Operator-directed ("Deepen chat RAG (reranking pipeline)") (SDD-977; advances F-2026-093, builds on SDD-976).
SDD-976's `--rag` used only the retrieval hub's base BM25 store; this exercises its decorator surface.

- **`sovereign-chat --rerank [QUERY…]`** (implies `--rag`): wraps the knowledge store in the hub's
  Reranked → Deduped → Diversified decorator chain (each a Retriever over the last) before grounding. A
  generic `drive_rag<Ret: Retriever>` helper lets the plain + reranked pipelines share one path without boxing.
- Verified: `cargo test -p sovereign-chat` 25 passed; live `--rerank` runs the full BM25 → rerank → dedup →
  diversify pipeline and grounds.

### Added — retrieval-augmented chat: wire the retrieval hub into sovereign-chat (2026-07-13)

Operator-directed ("crates integrations from the bottom to avoid collision") (SDD-976; advances ledger
F-2026-093). The full `sovereign-retrieval` RAG hub (~20 store types, RagResponder, 63 tests) was consumed
by nothing but the 152-crate mega-demo; the chat binary did plain generation. This gives the retrieval
cluster a real second consumer — entirely in the crate layer, off the shared-registry collision surface.

- **`sovereign-chat --rag [QUERY…]`**: a retrieval-augmented mode — a built-in BM25 `knowledge_store`, the
  runtime wrapped as a `Responder` via `LlmResponder`, then `RagResponder` grounding each query with top-2
  retrieval. Reports per-query whether retrieval actually grounded the prompt.
- Verified: `cargo test -p sovereign-chat` 13 passed (RAG unit + binary-integration, grounded + ungrounded
  cases); live run grounds a corpus query (BM25 hit) and correctly leaves an unmatched query ungrounded.

### Added — scripts health-baseline contract (2026-07-13)

Phase-1 audit (SDD-969; closes ledger F-2026-020). The operator-script surface was at an exemplary
baseline with no guard — the scripts-surface parallel to the crate-hygiene contract (SDD-974).

- **`tests/lint/test_scripts_health_baseline.py`**: three tree-recomputed invariants — every
  `scripts/**/*.sh` passes `bash -n` (102 files, parse-only); every `scripts/**/*.py` byte-compiles
  (299 files, never imported); `sovereign-osctl`'s 29 called `cmd_*` all resolve to definitions (a
  dispatch to a missing handler fails CI, not the operator's terminal).

### Fixed — SDD-969 cross-session number collision + band-scheme drift (2026-07-13)

The cockpit-wasm bridge session (F-2026-001) took SDD-969 inside the phase-1-audit band (950–999),
colliding with the audit session's own SDD-969 — main's `test_sdd_numbers_unique` went red on all
three surfaces (file / INDEX / mandate). The `test_sdd_numbers_unique` backstop had passed on the
cockpit PR because its branch was cut before the audit's 969 merged (a stale-green merge).

- **Resolved the live collision**: the audit session yielded its 969 → **975** (its own band; renamed
  doc + INDEX + mandate + catalog), leaving the cockpit-wasm 969 intact.
- **Fixed the band-scheme drift**: `docs/sdd/README.md` still advertised the retired "any new →
  900–999" catch-all (superseded by the 2026-07-12 SDD-100 amendment) — a session reading it grabs a
  900-number. Updated it + SDD-100 + context.md to the disjoint sub-bands and assigned the cockpit-wasm
  session its own **800–899** block.
- **Recommended prevention** (operator setting): enable branch protection "require branches up to date
  before merging" so a PR must re-run the uniqueness lint against the current tree before it can merge.

### Added — workspace-hygiene baseline contract (2026-07-13)

Phase-1 audit (SDD-974; closes ledger F-2026-004, surfaces F-2026-096). The audit found the 717-crate
workspace's hygiene exemplary and asked for a lint so "the bar never silently drops".

- **`tests/lint/test_workspace_hygiene_baseline.py`**: six invariants recomputed from the tree (drift fails
  CI both directions) — root lints forbid `unsafe`/warn `missing_docs`; every manifest has a `description`;
  per-crate tests except `{sovereign-feature-selftest}`; marker-free (`todo!()`/`unimplemented!()`/`FIXME`/
  `TODO`); no `/home`/`/Users`/`/root` paths; `unsafe` confined to `{sovereign-simd}` (the sanctioned
  AVX-512 carve-out).
- **F-2026-096 surfaced**: the finding's "all inherit workspace lints" claim doesn't fully hold — 202 cockpit
  crates don't declare `[lints] workspace=true`, so they don't inherit the compile-time `unsafe` ban (latent).
  Invariant 6 is the repo-wide compensating control; manifest-unification deferred (hot-file collision).

### Added — exotic tool-domain discoverability index (2026-07-13)

Phase-1 audit (SDD-973; closes ledger F-2026-027). Six scripts/<domain>/ trees (science/research/insights/
history/weaver/pulse) held lone specialist entry points with zero docs/index — hidden capabilities.

- **`docs/src/exotic-tools.md`**: maps the 8 top-level scripts to role + invocation + existing surface; wired
  into SUMMARY. A discoverability surface, not new osctl/panel infra.
- **`tests/lint/test_exotic_tools_doc.py`**: every exotic-domain script documented + no ghost refs + SUMMARY
  links it — completeness contract.

### Added — per-milestone backlog delivery roll-up (2026-07-13)

Phase-1 audit (SDD-972; closes ledger F-2026-038). "How done is M0xx" was only in SHIPPED.md's SAMPLED /
state-TBD snapshot. A literal shipped-÷-R-rows % misleads (SHIPPED rows are surfaces, several per R-row).

- **`scripts/backlog/gen-shipped-rollup.py`** + **`backlog/SHIPPED-ROLLUP.md`**: per milestone — catalogued
  R-rows + delivered? + shipped surfaces (depth signal, not a %). Grand roll-up: 7 of 84 milestones (8%) have
  production delivery recorded; 14,079 distinct catalogued R-rows.
- **`tests/lint/test_shipped_rollup.py`**: regen-and-compare + every-milestone-present — sync contract.

### Added — consolidated deferred-work register (2026-07-13)

Phase-1 audit (SDD-971; closes ledger F-2026-037 at the consolidation core). The ~10 docs-promised deferred
items were scattered across decisions/SDDs/context — rediscovered each pass.

- **`docs/review/phase-1/deferred-work-register.md`**: one table — each item with source-refs + one-line scope
  + proposed order + owner=`operator-to-assign` (sequencing/ownership is an operator decision-package). Pointer
  index, not a re-spec.
- **`tests/lint/test_deferred_work_register.py`**: every cited SDD + doc path resolves (dangling-reference guard).

### Changed — cargo-workspace CI timeout headroom (2026-07-13)

Phase-1 audit (SDD-970; closes ledger F-2026-050 core). The cargo-workspace job builds the whole 717+ crate
workspace (fmt + clippy + test + release build) in one job; warm runs take ~6-7 min but a cold-cache run would
exceed the 10-min budget and fail PRs spuriously.

- `.github/workflows/test.yml`: `cargo-workspace` `timeout-minutes` 10 → 30 (headroom; zero coverage change).
- **`tests/lint/test_ci_cargo_timeout.py`**: the job's timeout-minutes must stay ≥ 20 — floor guard against
  regression as the workspace grows.
- Splitting the release build into its own parallel job (faster fmt/clippy/test feedback) scoped as follow-up.

### Added — navigation companion for the 640 KB standing-directive (2026-07-13)

Phase-1 audit (SDD-969; closes ledger F-2026-039 at its "at minimum" bar). The 2026-05-17 operator-mandate
file is ~640 KB (multi-KB single mandate-table rows) — slow to open, undiffable.

- **`…-operator-mandate-NAVIGATION.md`**: a section-level map (6 sections + §1.0–§1h verbatim-paste
  subdirectives + Epics E1–E11) — reproduces no content; navigation only. Deliberately a companion, not a
  split (sacrosanct §1 byte-risk) and not a per-row index (would CI-couple the most-appended file).
- **`tests/lint/test_mandate_navigation.py`**: every `##`/`###` heading in the mandate is reflected in the
  companion — structural drift guard, checks headings only (routine `E11.M###` row appends need no update).

### Added — shell-safety-flags contract (2026-07-13)

Phase-1 audit (SDD-968; closes ledger F-2026-024). Investigation found the finding's premise didn't hold —
the "missing set -euo pipefail" candidates are deliberate (provision-bake.sh "NON-FATAL BY DESIGN"; preflight.sh
a fail-counter) or sourced libs / a neutralized template; 0 entry-points ship with zero safety flags.

- **`tests/lint/test_shell_safety_flags.py`**: every executable `scripts/**/*.sh` outside `lib/`/`templates/`
  sources `common.sh` or sets a safety flag (`set -e`/`-u`/`-o pipefail`). Requires safety present, does not
  mandate `-e` (respects the deliberate non-`-e` designs). 91 entry-points guarded, 0 violations.

### Changed — hook hygiene: dedup vfio-bind + hook contracts (2026-07-13)

Phase-1 audit (SDD-967; closes ledger F-2026-021 + F-2026-023).

- **Removed** `scripts/hooks/post-install/vfio-bind-3090.sh` — a byte-identical, profile-driven
  duplicate of `vfio-bind-4090.sh` (the build-configurator itself called it a "legacy name" that
  "binds the 4090"). Repointed the one webapp build-step referrer to the canonical `vfio-bind-4090`.
- **`tests/lint/test_hook_hygiene.py`**: `test_all_hooks_executable` (every hook keeps its +x bit —
  orchestrate.sh's `find -executable` dispatch can't silently skip one, F-2026-023) +
  `test_no_dangling_hook_path_references` (every hook path in the dispatch wiring — phases.yaml +
  systemd units — resolves to a real file, so a delete/rename can't leave a dangling wiring ref).

### Added — Cockpit wasm bridge round 3: the final 19 bespoke crates — 418/418 (2026-07-13)

Phase-1 audit (SDD-800; F-2026-001 — cockpit family COMPLETE). The 19 crates without the uniform
`validate(&self)` were bridged **by hand** over their real decision fns (the macro can't):

- **`cockpit-wasm/src/bespoke/<slug>.rs`** (NEW, 19 modules) — each a `#[wasm_bindgen]` wrapper over the
  crate's genuine surface: `color-contrast`→`verdict` (WCAG ratio + AA/AAA), `pagination`→`info`/`next`/`goto`,
  `word-count`→`count`, `day-divider`→`classify`/`group`, `relative-time`→`format`, `text-truncation`→`truncate`,
  `toast-stack`/`search-history`→functional mutations (parse→mutate copy→return new state), `views`→coverage,
  the audit panels→their pure `any_*`/`aggregate_*`/`render`. Filesystem loaders + wall-clock deliberately not
  bridged (pure fns; a clock is passed in).
- **`gen-bridges.py`** now also scans `src/bespoke/*.rs`, writes `bespoke/mod.rs`, and folds those crates'
  optional deps + feature entries into the generated blocks (auto-catching the transitive `keystroke-map`).
  The `bridges` feature = 398 generated ∪ 19 bespoke = **417 cockpit deps** (+ banner-state = 418/418).
- Fixed a latent round-2 defect: `bridges.rs` had used `#![rustfmt::skip]` (unstable inner attr, E0658) which
  broke `--features bridges`; replaced with a `cargo fmt` normalisation step.

Verified: `cargo build --features bridges` clean (465 exports); bespoke bridges execute in node
(`color_contrast_verdict(black,white)`→21:1 AA+AAA, `pagination_info`→correct range/pages, word-count/day-divider/
truncation correct, bad tokens→graceful); `cargo test --features bridges` 6 passed; clippy default+bridges + fmt
clean; committed demo still 128 KB; `pytest tests/lint/test_cockpit_wasm_bridge.py` 13 passed. **F-2026-001: 418/418.**

### Added — Cockpit wasm bridge round 2: 398 more cockpit crates, generated + feature-gated (2026-07-13)

Phase-1 audit (SDD-800; F-2026-001 continued). The family is uniform — **~399 of 418 crates** share
`Type::validate(&self) -> Result<(), E>` on a serde type — so the bridge scales **mechanically**:

- **`cockpit-wasm/gen-bridges.py`** (NEW) emits one `bridge_validate!(<slug>_validate, …::Type)` line per
  uniform crate into a generated `src/bridges.rs`, plus an optional path-dep + a `dep:` entry in a `bridges`
  feature. The **`bridge_validate!`** macro expands to a `#[wasm_bindgen]` fn running the crate's REAL
  `validate()`. 398 crates bridged this round; 19 ineligible (bespoke later).
- **Feature-gated for repo health**: the generated module is behind `#[cfg(feature = "bridges")]`. The
  committed demo build stays **banner-only, 128 KB**; the full family (all 398, ~4.4 MB, 399 `_validate`
  exports) builds only under `--features bridges` — on demand + verified (`make cockpit-wasm-all`),
  **never committed** (a lint size-ceiling enforces it).
- **`tests/lint/test_cockpit_wasm_bridge.py`**: now also pins `bridges.rs` / optional-deps / feature-list to
  the same real-crate set + a ≥300 coverage floor; a `--features bridges` native test proves a generated
  bridge reaches the crate's real `validate()` (valid→ok, schema-mismatch→its real error, garbage→parse guard).

Verified: `cargo build --features bridges` → 399 exports (18 s); `build.sh --verify-all` runs a sample in node
(item-pin valid/invalid/parse-guard OK); `cargo test --features bridges` 6 passed; clippy default + bridges
clean; `pytest tests/lint/test_cockpit_wasm_bridge.py` 12 passed. F-2026-001: 399/418 cockpit crates now bridged.

### Added — Cockpit wasm bridge: the typed cockpit crates run in the browser (2026-07-13)

Phase-1 audit (SDD-800; closes ledger **F-2026-001** partial — the #1 crate finding). **413 of 418
`sovereign-cockpit-*` crates (~58% of the workspace) are consumed by nothing that runs**: they encode the
cockpit's UX-state as typed, tested Rust, but the webapp is hand-written HTML/JS (zero `wasm-bindgen`/`cdylib`/
`wasm32`), so every panel re-implements crate logic in JS that can drift. Operator chose the audit's option (a):
**build the wasm bridge**. Shipped end-to-end on the first crate + established the repeatable pattern.

- **`cockpit-wasm/`** (NEW facade crate, wasm-bindgen over `sovereign-cockpit-banner-state`) — exports
  `banner_severity` / `banner_state` / `banner_validate` / `schema_version`, wrapping the crate's REAL
  `compute_severity` / `build` / `validate`. **Deliberately OUTSIDE the workspace** (`[workspace].exclude`):
  wasm-bindgen emits `unsafe` glue and `sovereign-simd` is the one sanctioned unsafe crate, so exclusion keeps
  that invariant true + keeps the wasm toolchain off the 714-crate CI (F-2026-050).
- **`webapp/_shared/cockpit-wasm/{cockpit_wasm.js,cockpit_wasm_bg.wasm}`** (NEW committed artifact, reproduced by
  `cockpit-wasm/build.sh`) + **`webapp/_shared/cockpit-wasm/demo.html`** (NEW served demo, co-located with the
  wasm; a demonstrator, not a nav panel — promotion is a follow-up) — computes banner severity live in-browser
  via the real Rust; tamper the stored severity and the crate's `validate()` catches it; degrades offline.
- **`scripts/operator/cockpit-bridge-api.py`** + **`sovereign-cockpit-bridge-api.service`** (NEW, loopback :8137,
  read-only) — serves the panel + wasm with the correct `application/wasm` MIME the other panel APIs lacked.
- **`tests/lint/test_cockpit_wasm_bridge.py`** (NEW, 8 cases) — facade excluded + wasm cdylib over a real crate;
  artifact is valid wasm with the 4 exports; panel imports+calls the real logic+degrades; api wasm-MIME+read-only.

Verified: `cargo test` 5 passed (facade); `build.sh --smoke` EXECUTES the exports in node — 7/7 severity cases
match the crate + tamper rejected; live serving confirmed (wasm `application/wasm`, POST 405, traversal 404);
`pytest tests/lint/test_cockpit_wasm_bridge.py` 8 passed; full `tests/lint` green. The other 412 cockpit crates
are follow-up thin wrappers on this pattern.

### Added — per-unit systemd coverage contract (2026-07-13)

Phase-1 audit (SDD-966; closes ledger F-2026-054). ~41 of 111 units had no name-specific test.

- **`tests/lint/test_systemd_unit_coverage.py`**: pytest-parametrized over every
  `systemd/system/*.{service,timer,target}` — each unit gets a `test_unit_is_reachable[<unit>]`
  (not orphaned: [Install] / same-stem .timer / a dependency of another unit / phases.yaml /
  install-referenced) + `test_unit_is_structurally_valid[<unit>]` (service→[Service]+Exec*;
  timer→[Timer]+schedule; target→[Unit]) case. 223 cases, 0 orphans, 0 malformed. New units
  are covered automatically. Complements the SDD-964 install-coverage contract.

### Changed — ARCHITECTURE.md Stage-2 refresh (2026-07-13)

Phase-1 audit (SDD-965; closes ledger F-2026-053). ARCHITECTURE.md was frozen at the arc-opening
(2026-05-16) — profiles framed as future "PR 5/6 stubs", no mention of the Stage-2 intelligence layer.

- **Profiles** section: the 5 profiles are realised, schema-conformant `profiles/*.yaml` bodies (dropped
  the reserved-stub framing).
- **New "The intelligence layer (Stage-2)" section**: the `crates/` Rust workspace — `gatewayd` daemon
  (Anthropic Messages API + safety spine + durable memory) + the in-daemon generation/reasoning stack —
  cross-linked to `binaries.md` + `ai-backend.md`.
- **SFIF mapping**: a Current-state (2026-07, post-Gate-5) note supersedes the "Stage 2+" future-tense.
- Info-hub-owned baseline (four-repo ecosystem, 11 epics) left byte-unchanged.
- **`tests/lint/test_architecture_doc_current.py`**: every profile named + gatewayd/binaries.md referenced —
  currency contract guarding against scaffold-era regression.

### Added — systemd install coverage: make install-units (2026-07-13)

Phase-1 audit (SDD-964; closes the file-side core of ledger F-2026-051). The 111 systemd units + the scripts they call
were never installed by `make`, and the unit README documented only 4 of 111.

- **`make install-units`** (+ `uninstall-units`): DESTDIR-clean staging of every `*.{service,timer,target}` →
  `/etc/systemd/system/` + the three script trees at the roots their `ExecStart` hardcodes (operator-API →
  `/usr/local/lib`, hooks/inference/hardware → `/opt`). Prints the `daemon-reload` + `enable` activation step.
- **`systemd/system/README.md`**: extended (additively) with the full 111-unit fleet + the two-prefix doctrine.
- **`tests/lint/test_systemd_install_coverage.py`**: every unit `ExecStart` script exists in-repo (88/0-missing);
  prefixes ⊆ the two documented roots; install-units stages all 3 trees; README counts match tree — coverage contract.
- Q-964-A (unify the two prefixes vs keep the split) deferred to the operator; recommendation: keep.

### Added — developer bootstrap: single-source dev deps (2026-07-13)

Phase-1 audit (SDD-963; closes ledger F-2026-022 + F-2026-056 + F-2026-026 + F-2026-055). A fresh clone couldn't
reach a working test/lint loop, and CI declared its Python deps inline in four jobs.

- **`requirements-dev.txt`**: the ONE dev-dep list (`pytest` + `pyyaml` + `jsonschema`). `make dev-deps` installs
  it; all four CI installs now `pip install -r requirements-dev.txt` (single-sourced).
- **`make clean-pyc`** (removes `__pycache__` + `*.pyc`, folded into `make clean`) closes F-2026-026.
- **`_require-pytest`** guard on `lint`/`unit`/`dashboards-lint` → "run `make dev-deps`" instead of a raw
  `ModuleNotFoundError`; `setup.sh` verifies pytest too.
- **README prerequisites**: Python line → `make dev-deps`; new Rust 1.89 paragraph names
  `scripts/install/rust-toolchain.sh` (closes F-2026-055).
- **`tests/lint/test_dev_deps_single_source.py`**: keeps local + CI deps single-sourced (no inline pytest install,
  `make dev-deps` + guard present) — drift contract.

### Added — runtime binaries reference (2026-07-13)

Phase-1 audit (SDD-962; closes ledger F-2026-005 + F-2026-002). The 9 Rust binary crates are the executable runtime
surface but had no single map.

- **`docs/src/binaries.md`**: each binary mapped to role → invocation → purpose — production (`gatewayd`,
  `telemetry`, `resource-control`, `feature-selftest`) vs dev/demo CLIs (`cortex`, `agent-runtime`,
  `inference-demo`, `chat`, `serve`) + a compose diagram; wired into SUMMARY.
- **`tests/lint/test_binaries_doc.py`**: every binary crate must stay documented (completeness contract).
- F-2026-002 (the 35-orphan triage) closed by annotation — already delivered by the island register (SDD-955),
  now 33 after a parallel session wired two islands.


### Fixed — SDD INDEX status hygiene: stale branch refs dropped + a hygiene contract (2026-07-13)

Phase-1 audit (SDD-961; closes the objective core of ledger F-2026-031). `docs/sdd/INDEX.md` had 71 rows referencing
a stale ephemeral feature branch (`on branch claude/recover-projects-b0oT6`) for a dormant, long-merged session,
and an undocumented Status vocabulary.

- **`docs/sdd/INDEX.md`**: the 71 branch refs → `(recover-projects session)` (ephemeral branch dropped, honest
  session provenance kept); a Status vocabulary legend added to the header (draft/review/scoping/accepted/active/complete).
- **`tests/lint/test_sdd_index_hygiene.py`**: blocks feature-branch references + status words outside the documented
  vocabulary from returning.
- The subjective status-value reconciliation (flip merged `draft` SDDs → accepted/complete) is left to each
  authoring session against the legend — a per-SDD judgement, not a unilateral mass-relabel of other sessions' rows.


### Fixed — real workspace metadata + dead docs.rs links removed (2026-07-13)

Phase-1 audit (SDD-960; closes ledger F-2026-003). Root `Cargo.toml` `[workspace.package]` carried template
placeholders (`repository = "https://example.org/you/sovereign-os"`, `authors = ["You <you@example.org>"]`)
inherited by all 714 crates, and 23 crate `lib.rs` headers linked `https://docs.rs/sovereign-*` — dead under
`publish = false`.

- **`Cargo.toml`**: `repository` → `https://github.com/cyberpunk042/sovereign-os`, `authors` → `["cyberpunk042"]`
  (the already-public identity; one edit, all crates inherit it).
- **23 crates**: the dead docs.rs reference-links repointed to the GitHub source (doc comments only).
- **`tests/lint/test_workspace_metadata.py`**: blocks placeholder workspace metadata and any `docs.rs/sovereign-*`
  link from returning.


### Fixed — MASTER-PLAN count reconciliation + milestone-completeness contract (2026-07-12)

Phase-1 audit (SDD-959; closes ledger F-2026-032). `docs/MASTER-PLAN.md` self-contradicted on the milestone count —
it stated both "128" and "130", its sovereign-os cell (82) trailed the file tree (84, with M085/M086 missing from
the enumeration), and the D-16/D-12 rows read "not yet wired" while the dashboards had shipped.

- **`docs/MASTER-PLAN.md`**: the count is single-valued at 132 (intro + table + header + status line reconciled);
  M085/M086 added to the enumeration (annotated as operator-note milestones, 0 R-rows); the D-16 audit-chain +
  D-12 networking rows updated to "at prod" (cited to `webapp/d-16-audit/` + `webapp/d-12-networking/` + context.md).
- **`tests/lint/test_master_plan_counts.py`**: every `backlog/milestones/M*.md` must be enumerated, no stale
  entries, the sovereign-os cell equals the file count, the combined total equals selfdef + sovereign-os, and the
  three stated totals agree — the 128-vs-130 contradiction guard. Same counts-as-contract discipline as
  `context.md` (SDD-952) and the mdbook catalog (SDD-958). The cross-repo selfdef count is checked for internal
  consistency only (selfdef isn't in this checkout).


### Added — unfreeze the mdbook: generated SDD catalog + standing-directives, enforced (2026-07-12)

Phase-1 audit (SDD-958; closes ledger F-2026-033). The published mdbook (`docs/src/SUMMARY.md`) had hand-curated SDD
links frozen at SDD-067 — the book trailed the repo by ~90 SDDs (the whole intelligence layer + the phase-1 audit
arc) with no page for the July standing-directives.

- **`scripts/docs/gen-sdd-catalog.py`**: generates `docs/src/sdd-catalog.md` (every SDD by number) +
  `docs/src/standing-directives.md` (the operator directives incl the three July ones) from the file tree. Run it
  after adding an SDD/directive.
- **`docs/src/SUMMARY.md`**: a new "Design record" section links both generated chapters (additive — the curated
  intro links are kept).
- **`tests/lint/test_mdbook_catalog_sync.py`**: re-runs the generator and fails CI if either page is stale
  (regen-and-compare + a newest-SDD anti-freeze guard + link resolution). Same self-maintaining discipline as the
  `context.md` counts-contract and the island register — the book can never freeze behind the design record again.


### Docs — serve-vs-gatewayd architecture decision package (2026-07-12)

Phase-1 audit (SDD-957; scopes ledger F-2026-089 — **open, awaiting operator decision Q-957-A**). A code comparison of
`sovereign-serve` vs `sovereign-gatewayd` (post-SDD-206) corrects the finding's premise twice: serve's real library
pipeline is only cache→complexity→budget (the pii/secret/toxicity are opt-in flags in its demo binary), and SDD-206
already put those safety filters into `gatewayd::generate_chat`. serve has no network interface (a library fn + a
CLI demo with a toy model) so it cannot be the daemon, and it is dead (0 non-test consumers). The only real delta:
a completion cache + token-budget refusal (complexity is superseded by router-7axis). Recommendation: **Option A** —
fold cache + token-meter into `generate_chat` via the SDD-206 insertion pattern, skip complexity, retire serve;
sequenced with the parallel sessions that own `generate_chat`. Decision document only — no code change.


### Added — gateway API reference: route-parity contract + routing-vs-generation clarification (2026-07-12)

Phase-1 audit (SDD-956; closes ledger F-2026-094). The gateway API reference (`docs/src/ai-backend.md`) already
enumerates every route, but nothing kept it honest against the daemon code — the pre-existing contract lint only
checked a static hand-listed subset.

- **`tests/lint/test_gateway_route_parity.py`**: extracts the served route set from the daemon dispatch
  (`sovereign-gatewayd/src/http.rs` + the `main.rs` streaming intercepts) and the documented set from
  `ai-backend.md`, and asserts they are equal **both directions** — a served-but-undocumented route fails CI, a
  documented-but-unserved route fails CI. Parity is 19==19 today. Same counts-as-contract discipline as
  `context.md` (SDD-952) and the island register (SDD-955), applied to the HTTP surface. `ai-backend.md` is left
  untouched (complete + accurate); the lint only keeps it that way.
- **Clarified (SDD-956)** the routing-vs-generation "two brains": the generation path
  (`safetensors-loader → quant-model → …`) serves `/v1/messages` + `/v1/chat/completions` and produces text; the
  routing path (`sovereign-cortex`) serves `/v1/infer`/`/v1/simple`/`/v1/explain`/`/v1/deliberate`/`/v1/coat` and
  produces a decision/rationale/trace — never text. `/v1/deliberate` (best-of-N) and `/v1/coat` (CoAT ladder trace)
  are distinct shapes, not duplicates.


### Added — wire-the-island register: built-but-unwired crates become a machine-enforced register (2026-07-12)

Phase-1 audit (SDD-955; closes ledger F-2026-093 — the audit's #1 theme). A dependency-graph pass over all 714 crate
manifests found the **35 pure-library `sovereign-*` crates** (`src/lib.rs`, no binary) that appear in **no other
crate's `Cargo.toml`** — depended on by nothing that runs.

- **`docs/review/phase-1/island-register.md`**: the 35 enumerated, each with a disposition (14 aspirational — need a
  real model / GPU / ZFS / CRIU / VM / network integration or an operator decision; 21 wireable) + a concrete
  trigger, plus the inventory summary and the two-parallel-stacks root cause (the wired `safetensors` path vs the
  demo-only `sovereign-llm` island hub).
- **`tests/lint/test_island_register.py`**: recomputes the set and asserts register == computed **both directions**
  — a new orphan fails CI until registered; a newly-wired island fails CI until its row is removed. Same
  counts-as-contract discipline as `context.md`, applied to dead crates.
- **Correction**: `sovereign-world-model` + `sovereign-hrm-runtime` were flagged as islands but are run-reachable
  via `sovereign-cortex` (a gatewayd dependency) — annotated in the ledger.


### Fixed — auto-mode permission classifier: flag normalization + honest framing (2026-07-12)

Phase-1 audit (SDD-954; closes ledger F-2026-092). The Auto-mode safety classifier
(`scripts/operator/lib/permission_classifier.py`) matched destructive `rm` via a single combined-token regex, so
split (`rm -r -f`) and uppercase (`rm -R -f`) flags escaped the `destructive` verdict and fell to `confirm` —
undercutting Auto mode's job to block the recursive-delete class.

- **`permission_classifier.py`**: the two fragile `rm` regexes are replaced by `_rm_recursive_or_force()`, which
  flag-normalizes recursive (`-r`/`-R`/`--recursive`) and force (`-f`/`--force`) across split / combined / reordered
  / uppercase / long forms (and `sudo rm …`). Tightening-only (nothing that blocked/confirmed becomes allow) and
  fail-safe (unrecognized / obfuscated mutations still land in `unknown` → confirm, never a silent allow).
- **Doctrine reframe**: the module docstring and the plan-mode/user-approval directive now state the classifier is a
  **best-effort UX heuristic, not a security boundary** — the real boundary is the allowlisted execute daemon
  (`control-exec-api`) + fs sandbox (F-2026-081); a `block` means "spared the operator a mistake", not "an attacker
  was stopped".
- Regression + framing tests in `tests/lint/test_plan_mode_contract.py`.


### Added — configurable model load: the loader stops hardcoding F32-greedy (2026-07-12)

Phase-1 audit (SDD-953; closes the self-contained halves of ledger F-2026-085 + F-2026-086). `sovereign-safetensors-loader::load`
assembled every model at a hardcoded `Precision::F32` (a 7B model needs ~28GB, undercutting the "local sovereign"
premise) with a hardcoded `Sampler::greedy()` (so temperature/top_p/top_k were unreachable at the model level) —
even though the decoder stack is already precision-heterogeneous and the sampler/quant machinery are built and tested.

- **`sovereign-safetensors-loader`**: `load` refactored into `load_configured(bytes, config, precision, sampler)` plus
  delegating wrappers `load_at_precision` (caller precision, greedy) and `load_with_sampler` (F32, caller sampler).
  `load` keeps its exact signature and defaults (F32/greedy), so all existing call sites are byte-identical. A real
  checkpoint can now load as Ternary/NVFP4/INT8/BF16 in-memory. `Precision` + `Sampler` are re-exported.
- **`sovereign-quant-model`**: new `with_sampler(Sampler)` builder + `sampler()` getter — an assembled model can be
  re-pointed at a warm sampler and introspected (the hook the gateway's future per-request sampling wiring plugs into).
- **Deferred (tracked):** GGUF/pre-quantized-checkpoint dequant (no dequant-from-disk path exists — milestone-scoped)
  and threading per-request HTTP sampling params into `generate_chat` (owned by the parallel Anthropic-Messages-API
  session; this change only provides the model-side hook).
- Also removes two zombie `docs/sdd/INDEX.md` rows (900/901) a `merge=union` re-added for SDD files that had been
  renumbered to 950/951 — the union-merge deletion hazard; the canonical rows are 950/951.


### Fixed — context.md counts-as-contract: the re-orientation surface can't silently drift again (2026-07-12)

Phase-1 audit (SDD-952; closes ledger F-2026-030). `context.md` — the operator's "read me first after every
compaction" surface — was ~6 weeks stale and self-contradictory (it stated both "29 crates" and "476 crates"
while the tree held 714; "17 of 21 dashboards"; "29 SDDs"), despite its own "never silently let it drift" banner.

- **`context.md`**: a new "Current state (2026-07-12 — counts machine-verified)" section at the top (the stale
  "Current arc" header retitled "Historical arc") with a fenced `COUNTS-CONTRACT` block (crates 714 / dashboards
  25 / panels 55 / SDDs 134 / milestones 85, each with its source path) + a recent-arcs summary. The historical
  resume-cycle log below is left intact.
- **`tests/lint/test_context_md_counts.py`**: a new lint that parses the block and asserts every count against
  the live tree — a drift now **fails CI** with a `stated -> actual` diff, so the surface can't rot silently.
- The same pattern is the fix for MASTER-PLAN / mdbook drift (F-2026-032/033), tracked separately.


### Fixed — durable memory is never silently lost: corruption recovery + bounded growth (2026-07-12)

Phase-1 audit (SDD-951; closes ledger F-2026-084 partially). The gateway daemon persists its learning Cortex's
`MemoryStore` to `SOVEREIGN_GATEWAY_MEMORY`, but the load was `from_str(&json).unwrap_or_else(seed_memory)` — any
parse failure (a torn file from a hard kill, a manual edit, a struct-shape change) **silently discarded all
learned memory** and reseeded with no signal; and the store grew unbounded.

- **`sovereign-memory-os`**: new `MemoryStore::set_capacity(Option<usize>)` (sets the bound and evicts the
  lowest-value residents down to it — value-based, needs no clock, can never over-evict) + `capacity()` getter.
- **`sovereign-gatewayd`**: new pure `load_memory_from(path)` — an unparseable store is **moved aside to
  `<path>.corrupt` (atomic rename) and reseeded loudly**, preserving the old bytes for recovery instead of
  discarding them; the store is then capped via `SOVEREIGN_GATEWAY_MEMORY_CAP` (default 4096, `0` = unbounded).
- Backward-compatible on-disk format; zero behaviour change when `SOVEREIGN_GATEWAY_MEMORY` is unset.
- Deferred (Q-901-001): the M028 decay pass stays unscheduled until the admission clock is unified — bounded
  growth already caps accumulation clock-independently. Verified: memory-os 40 tests (2 new), gatewayd lib 55
  (4 new incl. corruption-recovery), clippy `-D warnings` clean, downstream unchanged. MS003 `unsigned-pending-MS003`.


### Fixed — real RoPE: `rope_theta` + `rope_scaling` from the model config (modern models decode coherently) (2026-07-12)

Arc 1 of the Phase-1 audit (SDD-950; closes ledger F-2026-080). Every decoder block was built with a **hardcoded
RoPE base of 10000**, so Llama-3 (500000), Qwen2 (1000000), Mistral etc. decoded as garbage — the single biggest
blocker to running a real model, and it made SDD-205's Anthropic endpoint return gibberish from VS Code / Claude Code.

- **`sovereign-mha-block`**: new `MhaDecoderBlock::with_rope(theta_base, scaling)` builder (additive — existing
  callers/tests untouched) + public `RopeScalingKind` (Linear/Dynamic/Yarn/Llama3) + `RopeScaling`, mapping onto
  `sovereign-rope`'s existing (previously-unplumbed) `with_base` / `ntk_aware_base` / `with_yarn`.
- **`sovereign-safetensors-loader`**: `Config` now parses `rope_theta` (default 10000) + `rope_scaling` (both the
  newer `rope_type` and older `type` key), resolves it, and threads it into every block. Unknown scaling type ⇒
  base-theta only (never a fabricated scaling, never a parse failure — SB-077).
- Honest partial support: YaRN without a known original context, and the llama3 frequency ramp, fall back to the
  correct base theta (the dominant win) rather than fabricating a scaling.
- Verified: mha-block 28 tests (8 new, incl. "a distinct base yields distinct decode output"), loader 13 (6 new);
  clippy `-D warnings` clean; downstream quant-llm/gatewayd/decoder-layer/inference-demo build unchanged. Sampling
  params + chat template + quantized loading are the tracked next arcs. MS003 `unsigned-pending-MS003`.
### Added — Compute Plane Phase 2, increment 5: observability — the plane + registry surface on D-22 (2026-07-12)

The live state of the compute plane + model registry becomes visible where the operator already watches
per-device model status (the D-22 LM Status & Operability panel). SDD-902.

- NEW read-only `GET /api/lm-status/compute-plane` (lm-status-operability-api) joins the compute plane (jobs-api
  `/plane.json` — devices with live free VRAM + `effective_free` after claims + the outstanding claims) with the
  gateway registry (`/v1/models` — loaded primary / CPU secondaries / GPU proxies with device+VRAM + the
  `background` target) + the `model-serve` jobs. Each half degrades independently (an `offline` flag).
- A "Compute Plane & Models" section on D-22 renders it — a devices/VRAM table, the claims, the gateway models
  (background badged), serving jobs — riding D-22's existing SSE + 5s poll, with a demo fixture. The
  `model-serve start/stop/background` verbs are clipboard-copied signed CLI (R10212 — no web mutation).
- Verified: an http test asserts the endpoint joins plane + registry + serving and degrades when the upstreams
  are down; a webapp-contract test locks the section + the copyable verbs + the demo fixture. 24 D-22 contract
  tests.

### Added — de-islanding big bite #5: the last 8 islands — the register drains to ZERO (2026-07-12)

Fifth (final) parallel batch (SDD-955), clearing the enforced island register **8 → 0**. These were the
crates the register itself labelled "aspirational" (VM / hibernation / ZFS-CRIU / network / post-training /
host-provisioning) — yet on inspection every one carried a real checkable / computable / emittable model
exercisable **without** the live subsystem, so none needed a forced or thin de-islanding. Built concurrently
by 8 sub-agents, each a genuine runnable `main.rs`, each verified (test + clippy `-D warnings` + fmt) before
integration. This closes **F-2026-093** completely: the register now sits at its terminal "everything is
either wired or de-islanded, nothing parked" state.

- **`sovereign-base-os`** — the base-OS provisioning model (10 responsibilities tagged declarative/imperative
  per E0459 + 5 config modes); `--check` validates a BaseOsConfig against `is_hardware_reality()`.
- **`sovereign-hibernation`** — classifies a HibernationRecord's resumability (`is_resumable` + wait-condition);
  `--check` validates a record.
- **`sovereign-holderpo`** — the HölderPO post-training math (Hölder mean M_p, 4 anneal schedules, trajectory
  aggregation, group-relative advantages); `--compute` runs the real ops, `--check` validates a config.
- **`sovereign-network-zerotrust`** — the §8 NIC zero-trust posture model; `--check` validates a NIC policy,
  `--emit` prints the canonical config.
- **`sovereign-save-state`** — the 5-layer save-state completeness gate; `--check` validates layer coverage +
  round-trip invariants.
- **`sovereign-vm-channel`** — the E0120 Host↔4090 boundary (4 channels / 8 message types / the M00224
  "VM output is a candidate, never committed" invariant); `--check` validates a channel-message envelope.
- **`sovereign-vm-workload`** — the VM-workload appropriateness gate over 13 workloads (`is_vm_appropriate`);
  `--check` decides quarantined-VM fit.
- **`sovereign-worker-fleet`** — the N-worker fleet-health decision (`summarise()` → FleetVerdict); `--check`
  summarises a fleet snapshot.

Per-crate tests (12 + 13 + 28 + 13 + 13 + 16 + 10 + 18 = 123 across lib+bin); clippy `-D warnings` + fmt clean
across all eight. The island-register lint now accepts a **zero-row** register as the valid drained state (a new
zero-reverse-dep pure library still fails it until registered), and `docs/src/binaries.md` grows to **41**
documented binary crates.

### Added — de-islanding big bite #4: 6 aspirational config crates get validate/emit CLIs (2026-07-12)

Third parallel batch (SDD-955), into the "aspirational" tier. On inspection these 6 crates were NOT pure runtime
stubs — each has a real policy/decision model a config tool surfaces WITHOUT the live system (validate a policy /
emit deployable artifacts, exactly like `sovereign-cpu-pinning`). The full runtime integration (live ZFS host,
kernel sandbox, network enforcement) remains future work; these make the models real + checkable now. Register
14 → 8; the enforcing lint stays green.

- **`sovereign-zfs-snapshot-policy`** — emits the snapshot systemd units (timer+service per cadence) + `--check`
  runs `plan_pruning()` producing the `zfs destroy` plan.
- **`sovereign-zfs-provisioning-plan`** — emits a REVIEW-ONLY zpool/zfs script (never executes; device-safe) +
  `--check` validates a plan (shell-safe tokens, target device).
- **`sovereign-zfs-commit-gate`** — the 4-stage commit gate (commit only at test_score ≥ 80); `--check` decides.
- **`sovereign-fs-boundary`** — classifies paths against the `/ai-exchange` boundary (`..`-escape safe).
- **`sovereign-sandbox-profile`** — 8 sandbox profiles by dimension; `--check` flags a double-constrained dimension.
- **`sovereign-network-boundary`** — the 5-rung network profile ladder; `--check` decides allow/deny per intent.

Per-crate tests (17 + 11 + 27 + 19 + 13 + 11); clippy `-D warnings` + fmt clean across all six.

### Added — de-islanding big bite #3: 6 more model crates gain runnable CLIs (2026-07-12)

Second parallel batch (SDD-955) — 6 more zero-reverse-dependency crates, each a genuine runnable `main.rs` doing
REAL work over real input. Built concurrently by 6 sub-agents, verified + integrated. Register 20 → 14.

- **`sovereign-continuity-levels`** — the E0456 8-level continuity ladder; `--check` validates a level value.
- **`sovereign-cpu-dispatch`** — runs the real `select_best()` CPU-dispatch-path selector; `--check` gates it.
- **`sovereign-dashboard-snapshot`** — builds a cockpit snapshot; `--validate` checks a snapshot JSON.
- **`sovereign-data-plane`** — exact RoaringBitmap set algebra over JSON id arrays (union / intersect / …).
- **`sovereign-intake`** — validates an IntakeRequest's identity (request_id + client_id).
- **`sovereign-replay-playback-rate`** — computes replay advance intervals; `--check` validates a rate state.

Per-crate tests (10 + 13 + 12 + 18 + 14 + 21); clippy `-D warnings` + fmt clean across all six.

### Added — de-islanding big bite: 6 model crates gain runnable CLIs in one batch (2026-07-12)

A parallel batch de-islanding pass (SDD-955) — 6 zero-reverse-dependency model crates, each given a genuine
runnable `main.rs` that does REAL work (validates real input against the crate's own rules), never a thin print.
Built concurrently by 6 sub-agents, each verified + integrated. Island register 26 → 20; the enforcing lint +
binaries-doc lint (21 binary crates) stay green.

- **`sovereign-cgroup-systemd`** — lists the 8 M045 OS primitives; `--check FILE` validates a `PrimitiveSnapshot`.
- **`sovereign-continuity-manager`** — the lifecycle states + allowed-transition matrix; `--check FILE` validates
  signed (MS003) lifecycle transitions, refusing illegal/unsigned moves.
- **`sovereign-harness-layers`** — the M082 5-layer TDD test pyramid; `--check FILE` classifies test directories.
- **`sovereign-replay-export-bundle`** — builds an example replay `ExportBundle`; `--validate FILE` checks a
  bundle JSON's cross-references (thread/cursor/bookmarks).
- **`sovereign-dashboard-layout`** — the 12-column widget grid + 8 widget kinds; `--check FILE` validates a
  `DashboardLayout` / `LayoutManifest` against grid bounds + slot coverage.
- **`sovereign-whitelabel`** — the M081 rebrand model; `--check FILE` enforces the E0785 legal-compliance rule
  (must-not-touch never modified, must-rebrand always) on a rebrand plan.

Per-crate tests (18 + 20 + 18 + 13 + 21 + 13); clippy `-D warnings` + fmt clean across all six.

### Added — de-islanding big round: runnable surfaces for built-but-unwired model crates (2026-07-12)

A batch de-islanding pass (SDD-955), one PR. Each crate below was a real, tested, zero-reverse-dependency
library that nothing ran; each now has a genuine runnable consumer (validates or checks real input, never a
forced print). The enforcing island lint stays green.

- **`sovereign-inheritance-check`** (NEW binary) → de-islands `sovereign-inheritance-artifacts`. Prints the
  canonical M042 8-artifact durable-inheritance manifest (VISION / ARCHITECTURE / METHODOLOGY / PROFILES / POLICY
  / MODEL_REGISTRY / HARDWARE_PROFILES / EVALS) and `--check ROOT` verifies the files exist — "does the box carry
  its executable memory?" made checkable.
- **`sovereign-execution-env`** (added a `main.rs`) → de-islands itself. Lists the E0553 execution-environment
  taxonomy — the 9 environments each mapped to its isolation level + the 10 observation categories.
- **`sovereign-module-facets`** (added a `main.rs`) → de-islands itself. Lists the E0477 uniform module
  interface (the 6 facets every module must expose) and `--check FILE` validates a ModuleDescriptor against them.
- **`sovereign-mode-transition-log`** (added a `main.rs`) → de-islands itself. Renders an example append-only
  ExecutionMode transition record and `--validate FILE` validates a transition log (legal mode shifts only).
- Island register 30 → 26 this round; the enforcing lint + the binaries-doc lint stay green.

### Added — de-island a crate with a subsystem: `sovereign-pcie-advisor` (catch the PCIe lane-sharing trap) (2026-07-12)

De-islanding pass #5 (SDD-955). `sovereign-pcie-topology` (the ProArt X870E-Creator slot map + lane-sharing
validator) was zero-reverse-dependency — its own doc even flagged a *divergent* `board-advisor-x870e-creator.py`.
Nothing ran the validator, so the E0027 trap (populating `PCIEX16_2` + `M.2_2` together silently halves a GPU's
bandwidth) could only be caught after a benchmark came back mysteriously halved.

- NEW `sovereign-pcie-advisor` crate (lib + binary): consumes `sovereign-pcie-topology` and (default) prints the
  slot map (flagging lane-sharing pairs) + the recommended layout + its validation; `--check FILE` validates a
  proposed `[{slot, device}]` population and exits non-zero on a lane-sharing / duplicate-slot conflict — so a bad
  hardware layout is caught before it's populated. Slot ranges come from the topology crate, the source of truth.
- The island register drops `sovereign-pcie-topology` (31 → 30); enforcing lint green. 2 crate tests (advisory
  validates; the lane-sharing trap is rejected); `cargo test` / `clippy -D warnings` clean.

### Added — build a subsystem to de-island a crate: `sovereign-cpu-pinning` (Trinity CPU-agent pinning) (2026-07-12)

De-islanding pass #4 (SDD-955), the "build the subsystem" path. `sovereign-cpu-topology` (the AMD Zen5 CCD
partition — Pulse / Weaver+Auditor / System-Host core allocations) was a zero-reverse-dependency crate, yet its
exact ranges were **hardcoded** in `scripts/hardware/ccd-pinning.py` — the classic two-parallel-stacks island.

- NEW `sovereign-cpu-pinning` crate (lib + binary): consumes `sovereign-cpu-topology::allocations()` (validating
  the partition first) and emits deployable systemd **`AllowedCPUs=` drop-ins** that pin the Trinity CPU agents to
  their cores — the CPU-affinity counterpart to `sovereign-resource-control`'s `CPUWeight` drop-ins. CLI mirrors it
  (`--unit NAME` / `--help`); drop-ins land at `/etc/systemd/system/<unit>.d/50-sovereign-cpu-pinning.conf`. Pulse
  → `sovereign-pulse.service` (CPUs 0-11), Weaver+Auditor → the weaver/auditor services (12-19), System-Host →
  `system.slice` (20-23) — every range read from the topology crate, never re-hardcoded.
- `ccd-pinning.py` now names `sovereign-cpu-topology` / `sovereign-cpu-pinning` as the canonical source of truth
  (a follow-up can have it shell out so the ranges live in exactly one place).
- The island register drops `sovereign-cpu-topology` (32 → 31); the enforcing lint stays green. 3 crate tests
  (drop-in per unit, cpusets sourced from topology, section by unit kind); `cargo test`/`clippy -D warnings` clean.

### Added — wire an island crate: `sovereign-hardware-dispatch-eligibility` → telemetry eligibility tableau (2026-07-12)

De-islanding pass #3 (SDD-955 island register), crossing into the hardware domain. `sovereign-hardware-dispatch-
eligibility` (which hardware targets can take a workload, given live load) was zero-reverse-dependency — and it
needs exactly a `HardwareRegistry` + `LoadSnapshot`, which `sovereign-telemetry` already builds every sample.

- `sovereign-telemetry` depends on it; after measuring live load it computes an `EligibilityTableau` for a
  baseline (no-VRAM, any-role) workload and emits it under `derived.dispatch_eligibility` (+ an `eligible_targets`
  summary) in its JSON document — so the telemetry sample now says which hardware can take work right now.
- Fixed a latent API gap the wiring exposed: `WorkloadRequest.max_latency`'s `LatencyTier` is re-exported from
  `sovereign-hardware-registry` (telemetry imports it there); no crate change needed once the path was corrected.
- The island register drops the row (33 → 32); the enforcing lint stays green. A telemetry test asserts the
  tableau computes (5 targets) and surfaces in the JSON. `cargo test`/`clippy -D warnings` clean.

### Added — wire an island crate: `sovereign-observability-events` → `GET /v1/events` span stream (2026-07-12)

De-islanding pass #2 (SDD-955 island register). `sovereign-observability-events` (the 13-field runtime span
taxonomy — `model_call` … `cost_event`) was zero-reverse-dependency. Its register trigger named the hardware-
telemetry binary, but the natural consumer is the **gateway** — it makes the model calls the taxonomy describes.

- `sovereign-gatewayd` depends on it (+ `sovereign-trace-context` for TraceId/BranchId). The server keeps a
  bounded ring (256) of `ObservabilitySpan`s + a monotonic trace-id source; `generate_chat` records a
  `model_call` span (model, tokens, latency_ms, provider=local) on every local generation.
- NEW read-only `GET /v1/events` → `{count, events:[…]}` (newest last; the last N, a ring not a full history).
- The island register drops the row (34 → 33); the enforcing lint stays green. Both wired crates now run in prod.
- Verified: a lib test (record + snake_case kind + bounded ring + monotonic trace ids) + an http test. 66 lib+http
  + 4 bin + 18 transport tests (2 new); clippy `-D warnings` + fmt clean.

### Added — wire an island crate: `sovereign-rate-limit` → gateway generation admission control (2026-07-12)

De-islanding pass (SDD-955 island register): `sovereign-rate-limit` was a real, tested, zero-reverse-dependency
crate — built but wired into nothing. It is now the gateway's generation admission control.

- `sovereign-gatewayd` depends on `sovereign-rate-limit`; a `TokenBucket` (capacity + refill from
  `SOVEREIGN_GATEWAY_RATE_CAPACITY` / `_PER_SEC`, defaults 60 burst / 20-per-sec, 0 disables) bounds how fast the
  expensive generation endpoints (`/v1/messages`, `/v1/chat/completions`) are admitted, so a runaway/buggy client
  can't peg the box's CPU/GPU. `admit_generation()` spends one token at the HTTP boundary — BEFORE any generation
  work; a refusal is a `429` in the requested API's error shape (`rate_limit_error` / OpenAI), tallied on
  `/metrics` as `sovereign_gateway_rate_limited_total`. Fail-open on a poisoned lock (availability > strictness).
- The island register (`docs/review/phase-1/island-register.md`) drops the `sovereign-rate-limit` row (35 → 34);
  `tests/lint/test_island_register.py` enforces that a wired crate leaves the register (and stays green).
- Verified: a transport test with a 2-token no-refill bucket admits 2 requests then `429`s the 3rd and the
  refusal shows on `/metrics`. 64 lib+http + 4 bin + 18 transport tests (1 new); clippy `-D warnings` + fmt clean.

### Added — the `sovereign-osctl model-serve` verb: launch a GPU model in one command (2026-07-12)

The operability capstone for Compute Plane Phase 2 (SDD-902) — launching a GPU-hosted model no longer means
hand-crafting a `jobs submit` JSON.

- NEW `scripts/operator/lib/model_serve_cli.py` + the osctl `model-serve)` verb:
  - `start <id> --model <path> --vram N [--engine llama-server|vllm] [--port P] [--dialect openai|anthropic]
    [--device auto|logic|oracle]` — builds the serve-process argv and submits the `model-serve` job (which places
    on a device by free VRAM, launches the engine, and registers a gateway proxy).
  - `stop <id>` — cancels the serving job (→ unregister + release VRAM); `list` — serving jobs + the gateway
    registry (`GET /v1/models`); `background [<id>|--clear]` — designate the `"background"` alias.
- Stdlib-only, loopback (jobs-api :8142 + gateway :8787); degrades gracefully when either is down. Mapped to the
  Code Console in feature-coverage. Verified: a test asserts `serve_command` builds the engine argv and `start`
  submits a `model-serve` job with the right meta (endpoint/dialect/vram/command) to a mock jobs-api. 16
  jobs-runtime tests.

### Added — Compute Plane Phase 2, increment 4: the Code Console UX loop — the model registry reaches the chat (2026-07-12)

The multi-model registry + the `"background"` alias become visible and usable from the operator's actual chat
surface (the Code Console). SDD-902.

- **The OpenAI shim is now a full peer of the Anthropic surface.** The Console chat rides `prompt.py` → the
  gateway OpenAI shim (`/v1/chat/completions`), which now **expands the `"background"` alias** and **routes GPU
  proxies**: an `openai`-dialect backend's SSE is relayed verbatim (`stream_proxy_chat_completions`), an
  `anthropic`-dialect proxy is an honest error pointing at `/v1/messages`. So `"background"`-that-resolves-to-a-
  proxy no longer silently falls back to the primary. The proxy transport is factored into shared
  `open_proxy_stream` / `next_proxy_block` helpers used by both streaming paths.
- **`GET /v1/models` reports the `background` target** so a UI can show where the alias points.
- **Console wiring.** `code-console-api` gains a read-only `GET /api/code-console/models` (proxying the gateway
  registry) and threads a `model` id from the chat body into the inference runner. The webapp composer gains a
  **Model picker** (primary / secondaries / GPU proxies / the `"background"` alias / `auto`) + a live "N models
  loaded · background → …" status, and sends the chosen model on every chat; it degrades to `auto` offline.
- Verified: a transport test streams a proxy through the OpenAI shim; an http test asserts `GET /v1/models`
  reports the background target; a jobs-runtime test locks the console-api proxy + composer wiring. 16 transport +
  62 lib+http + 15 jobs-runtime tests; clippy `-D warnings` clean.

### Added — Compute Plane Phase 2, increment 2b: streaming to a GPU proxy (VS Code / Claude Code stream from GPU-hosted models) (2026-07-12)

Editors stream by default, so this is what makes a GPU-hosted model actually usable from them. SDD-902.

- A `stream:true` request for a proxy model now opens a streaming connection to the upstream serve-process and
  **transcodes its SSE into the Anthropic event sequence as tokens arrive** (`stream_proxy_message`) — replacing
  the increment-2 honest-error gate.
- An `openai` backend's `/v1/chat/completions` deltas become `content_block_delta` events (dechunking
  `Transfer-Encoding: chunked`, as llama-server / vLLM emit); an `anthropic` backend's SSE is relayed verbatim.
  A pre-stream upstream failure is an honest Anthropic error; a client hang-up mid-stream ends the relay cleanly.
- Verified end-to-end: a mock chunked OpenAI-SSE upstream registered as a proxy → `POST /v1/messages {stream:true}`
  yields `message_start → content_block_delta* → message_stop` with the transcoded text + `stop_reason:end_turn`.
  15 gateway transport tests (1 new); clippy `-D warnings` clean.

### Added — Compute Plane Phase 2, increment 3: background routing — work targets the secondary, the primary stays free (2026-07-12)

The routing that makes the two backend kinds usable as background compute. SDD-902.

- **The reserved `"background"` model alias.** A request for `model: "background"` (Anthropic `/v1/messages`, the
  OpenAI shim, or `/v1/coat`) routes to a *designated* secondary — CPU resident or GPU proxy. `set_background` /
  `background_id` / `expand_alias` on the gateway; NEW `POST /v1/models/background {id}` designates it (loopback-
  trust), seeded from `SOVEREIGN_GATEWAY_BACKGROUND_MODEL`. **Honest fallback:** a designated-but-unloaded id (or
  none) resolves to the primary, never a dead id. `expand_alias` runs at every entry point (message, streaming,
  and inside `generate_chat`), so the alias targets the same backend whichever kind it is.
- **Background deliberations run on the secondary.** `GatewayRequest::Coat` + the `/v1/coat` body carry an
  optional `model`; `ModelThoughts` expands the reasoning through it. The jobs-api deliberation runner sends
  `model: "background"` by default (override via `meta.model`), so a background CoAT job keeps the interactive
  primary responsive — falling back to the primary when nothing is designated.
- Verified: gateway lib/http tests (alias designates + falls back on unload, `POST /v1/models/background` reports
  `active`, a `model:"background"` message reaches the designated proxy end-to-end, `/v1/coat` accepts the hint) +
  a jobs-runtime test asserting the deliberation sends the `"background"` alias. 62 gateway lib+http + 14 jobs-
  runtime tests; clippy `-D warnings` clean.

### Added — Compute Plane Phase 2, increment 2: a GPU serve-process backend the gateway proxies to (2026-07-12)

The second backend kind (option c): a real large model runs on the RTX PRO 6000 / VFIO-passed 4090 while the
CPU primary keeps serving interactive chat. SDD-902.

- **Gateway proxy registry.** `ProxyBackend { endpoint, device, vram_gb, dialect }`; `register_proxy` /
  `resolve_proxy`; `unload_model` removes proxies too; `GET /v1/models` now reports each resident's `device` +
  `vram_gb`. NEW `POST /v1/models/register {id, endpoint, device?, vram_gb?, dialect?}` (loopback-trust).
- **Dialect translation.** llama-server / vLLM speak OpenAI `/v1/chat/completions`, not Anthropic — so an
  `openai`-dialect backend has the Anthropic `/v1/messages` request translated (`anthropic_to_openai_chat`) and
  the reply mapped back (`openai_to_anthropic_message`: content, stop_reason, usage); an `anthropic`-dialect
  backend (another sovereign-gatewayd) is forwarded verbatim. Two http tests (mock Anthropic + mock OpenAI
  upstreams) prove both paths. Streaming to a proxy is honestly gated (retry non-streaming), never silently
  served by the primary.
- **`model-serve` job kind** (jobs-api). A VRAM-needing job: the compute plane PLACES + CLAIMS the device, the
  runner launches the serve-process argv (`meta.command`, no shell), waits for `meta.endpoint` to accept
  connections (bounded, degrade-safe), registers the gateway proxy on the ACTUAL placed device, stays running
  until cancelled; on ANY exit it terminates the process + unregisters the proxy, and run_job's `finally`
  releases the plane claim — no leaked VRAM or stale proxy.
- Verified LIVE (mock gateway + mock serve process): place → launch → register on `gpu0` → cancel → unregister →
  the plane frees the claim. 60 gateway lib+http tests (2 new proxy tests) + 13 jobs-runtime tests (1 new
  model-serve integration test); clippy `-D warnings` clean.

### Added — Compute Plane Phase 2, increment 1: the gateway hosts a secondary model (2026-07-12)

Operator-directed (the Background Tasks "massive" pass, option c). The gateway's own generator is CPU, so
"a secondary model" is two backend kinds under one registry (in-gateway CPU + GPU serve-process proxy) over
the shared plane. Increment 1 ships the in-gateway CPU multi-model registry. SDD-902 (the shared general 900 band; renumbered from 900 to avoid a collision with a parallel general-session's SDD-900/901).

- The gateway's single `generator` becomes a **registry**: a primary + an `RwLock` map of secondaries. A
  generation clones the resident `Arc` and releases the registry, so different models run concurrently, the
  same model serialises, and load/unload never blocks an in-flight request.
- `generate_chat(model, …)` **routes** by model id (a named secondary else the primary); all four call sites
  pass it; the **safety spine** (injection screen + secret/PII redaction) is preserved on every route.
- NEW `POST /v1/models/load {id, dir}` + `POST /v1/models/unload {id}` (loopback-trust operator actions);
  `GET /v1/models` now lists the **loaded** residents. A bad dir is an honest Anthropic 422, never a fabricated
  model.
- The shared VRAM authority (SDD-207): jobs-api `POST /plane/{place,claim,release}` — so model residents and
  GPU jobs claim from ONE view and never double-book (CPU residents claim no VRAM).
- Verified LIVE with a real model: `/v1/models` → load `fast` → `[primary, fast]` → a `{"model":"fast"}` message
  routed to the secondary → unload → `[primary]`. 53 lib + 4 bin + 14 transport tests; clippy clean.
- Honest gating: increment 1 is CPU-scale; big GPU models are increment 2 (a plane-placed llama-server/vLLM
  serve process the gateway proxies to), where the shared-plane authority becomes load-bearing.

### Added — the gateway safety spine: input screening + output redaction, made real on the daemon (2026-07-12)

First chunk of the Phase-1 audit's Arc 2 (SDD-206; closes ledger F-2026-081 + F-2026-082). The running
`sovereign-gatewayd` now enforces the Privacy + Redaction responsibilities the M048 gateway declares — previously
those crates were built and tested but wired only into the non-daemon `sovereign-serve`, so the daemon did none of it.

- **Safety spine wired into `generate_chat`** (the single chokepoint behind all four generation surfaces — OpenAI
  + Anthropic, stream + non-stream): input prompts screened for injection (`sovereign-injection-detect`); generated
  output redacted for secrets (`sovereign-secret-scan`) + PII (`sovereign-pii-redact`) and scored for toxicity
  (`sovereign-toxicity`, flag-only, never censors). `GuardConfig` is env-resolved, secure-by-default; injection
  *blocking* is opt-in (fail-open) so a false positive never silently swallows a prompt.
- **`StreamGuard`** — a cross-decode-chunk-safe streaming redactor: holds back a 256-byte window and releases only
  to the last ASCII-whitespace boundary, so a secret split across two generated chunks is caught before any byte
  leaves the box. Bounded memory; guard-disabled ⇒ exact legacy passthrough.
- **Transport hardening**: bearer auth (`SOVEREIGN_GATEWAY_TOKEN`, constant-time compare, `401` else — the minimum
  gate for a non-loopback bind); per-connection read/write deadline (`SOVEREIGN_GATEWAY_TIMEOUT_SECS`, default 30s,
  bounds slow-loris); honest over-capacity back-pressure (HTTP `503` + `Retry-After` / NDJSON error line instead of
  a silent drop).
- **Observability**: `/metrics` gains `sovereign_gateway_guard_{injections,redactions,enabled}`.
- Verified: `cargo test -p sovereign-gatewayd` (lib 51 incl. 11 new spine tests, main 4, transports 14), clippy
  `-D warnings` clean, fmt clean. TLS deferred (SDD-206 non-goal). MS003 `unsigned-pending-MS003`.
### Added — the Sovereign Compute Plane, Phase 1: a GPU job never OOMs the box (2026-07-12)

Operator-directed (the Background Tasks "massive" pass — "my rtx4090 jobs or a secondary model in general …
lets discuss and plan"). Discussed + planned: ONE compute plane placing both background models and GPU jobs
across the host PRO 6000 + the VFIO-passed 4090/3090 by live VRAM. A 4-phase roadmap was approved; this is
**Phase 1** (the plane core). SDD-207.

- NEW `scripts/operator/lib/compute_plane.py` — extends the M075 SRP doctrine (Conductor=CPU, Logic=4090,
  Oracle=PRO 6000; fit by precision + VRAM) from static capacities to **live free VRAM**. Probes host GPUs via
  `nvidia-smi`, tracks **claims** (a device + VRAM held for a job's life), and `place(need_gb, role_pref)`
  returns a device whose effective free VRAM (live − claims) covers the need (prefer role, else wait); a
  no-VRAM job → the CPU. Degrade-safe (no `nvidia-smi` → CPU-only; a GPU job honestly waits, never fabricates).
- `jobs-api` (SDD-204) now **places a `meta.vram_gb>0` job before it runs** — it waits (`queued`, "waiting for
  N GB free VRAM…") until a device fits, claims it, runs, and releases on completion. So a GPU job **never OOMs
  the box**; concurrent GPU jobs serialise by VRAM. NEW `GET /plane.json` + `sovereign-osctl plane` (read-only
  devices + claims); feature-coverage maps `plane → code-console`.
- `tests/lint/test_jobs_runtime_contract.py` extended: fit-by-live-VRAM (a 40 GB model excludes the 24 GB
  Logic; a claim removes headroom → queue), the CPU-only degrade, and jobs-api queues-not-OOMs a job when VRAM
  is exhausted (and keeps it cancellable while waiting). Verified live (`/plane.json` + `sovereign-osctl plane`).
- Honest gating: the canonical rule is the Rust `sovereign-srp-scheduler::place()` (Phase 2 wires the gateway
  for model residents); the 4090 is VM-isolated so Phase 1 sees host devices only (Phase 3 adds the VM); the
  wait holds a worker (a Phase-4 admission scheduler refines it).

### Added — user documentation: "Use the box as your AI backend" + "Reasoning & operability" (2026-07-12)

Operator-directed ("we need to do the documentation too"). The session's features had design docs (SDDs) but
no user-facing guide. Two new mdBook chapters, integrated into the existing book + README (not a new system).

- NEW `docs/src/ai-backend.md` — run the gateway + load a model; wire **VS Code (Cline/Claude Dev)**, **Claude
  Code (`ANTHROPIC_BASE_URL`)**, and the **Anthropic SDK**; the OpenAI-shim alternative; a full **gateway
  endpoint reference** (`/v1/messages`, `/v1/models`, `/v1/messages/count_tokens`, `/v1/chat/completions`,
  `/v1/infer` decision, `/v1/simple`, `/v1/explain`, `/v1/deliberate`, `/v1/coat`, health/manifest/ledger/metrics)
  with curl examples; and the sovereign posture (loopback-trust, never-fabricated, no cloud spill, model-gated).
- NEW `docs/src/reasoning-operability.md` — the CoT→ToT→MCTS→C-MCTS→CoAT ladder + `/v1/coat`; the Brain
  observatory (`/brain/`); Background Tasks (the jobs runtime + `sovereign-osctl jobs` + the 4090-VM bridge);
  the Code Console (the unified questions/plans/tasks/reasoning surface); and the interaction doctrine.
- Registered both in `docs/src/SUMMARY.md` (new "Using the box" section) + linked from `README.md`'s "Where to
  read next"; cross-linked the design SDDs (205/204/112/011) + the standing directives.
- NEW `tests/lint/test_ai_backend_docs_contract.py` guards the pages exist, are registered + linked, cover the
  load-bearing content (editor wiring, the endpoint reference, the ladder, tasks, the console), and that every
  relative link in them RESOLVES (no broken cross-links).

### Added — the Anthropic Messages API on the gateway: use the box from VS Code / Claude Code (2026-07-12)

Operator-directed ("make it compatible with Anthropic Messages API structure, so I can use it in vscode and
whatever else compatible"). `sovereign-gatewayd` (:8787) now speaks the **Anthropic Messages API**, so VS Code
extensions (Cline / Claude Dev), Claude Code (`ANTHROPIC_BASE_URL`), and the Anthropic SDKs drive the box's
OWN local model on loopback. Fulfils the pre-existing M034 "Anthropic-first" spec (`/v1/messages` had been a
decision stub). SDD-205.

- **`POST /v1/messages`** is the Anthropic Messages API: accepts `{model, max_tokens, system?, messages[],
  stream?}` (content a string OR a `[{type:"text",text}]` block array), generates from the local model, and
  returns the Anthropic shape — non-stream `{type:"message", role:"assistant", content:[{type:"text",text}],
  stop_reason:"end_turn", usage:{input_tokens,output_tokens}}` OR, on `stream:true`, the SSE event sequence
  `message_start → content_block_start → content_block_delta(text_delta)* → content_block_stop → message_delta
  → message_stop` (intercepted in main.rs like the OpenAI shim; non-stream in http.rs).
- NEW **`GET /v1/models`** (Anthropic models list) + **`POST /v1/messages/count_tokens`**.
- The sovereign routing **DECISION** that `/v1/messages` used to return moved fully to **`/v1/infer`**
  (`{kind:"decision"}`); the OpenAI shim `/v1/chat/completions` stays as the secondary compat surface.
- **Loopback-trust** (`x-api-key` / `anthropic-version` accepted, not validated — no cloud auth on a sovereign
  box); **never fabricated** (no model → an honest Anthropic error envelope 503, SB-077); the requested model
  id is echoed back, the box serves its one local model.
- **Verified LIVE end-to-end with SmolLM-135M:** non-stream returned the Anthropic message shape; `stream:true`
  emitted the full Anthropic SSE token-by-token. Output *quality* is model-gated (a base model rambles; a
  stop-sequence + instruct model is a follow-up), but the *compatibility* the editors need is complete.
- NEW `docs/sdd/205-anthropic-messages-api.md` (mission + wiring how-to for VS Code / Claude Code / Cline) +
  `tests/lint/test_anthropic_messages_contract.py`; the gateway lib + transport tests were repointed.

### Changed — the Code Console, brought to a high standard: the Plan pane goes live and unifies questions / plans / tasks / reasoning (2026-07-12)

Operator-directed ("make sure the console is fully developed and proper relative to everything — questions /
plans / background tasks — aim for high standards"). The console had the pieces but they didn't cohere: the
Plan pane was a static placeholder while Plan Mode rendered plans only in chat and a background deliberation
threw its reasoning away. Now the Plan pane is the live home for "what the AI is thinking right now" (SDD-204).

- The **Plan pane is live**: it mirrors the **active Plan-Mode plan** from the conversation (summary + numbered
  steps + the four approvals, which feed back to the chat), and renders a clicked deliberation's **CoAT
  reasoning trace** (a mini observatory: per-step category, backpropagated value, ↑ recall-lifted, recalled
  memory). The header reflects its mode — plan / reasoning / artifact. Artifacts + repo chips stay honest-
  deferred (SB-077) until a producer lands.
- **Deliberation jobs now keep the full compact trace** (best_path + values + recall), not just a summary line
  — so a finished background deliberation is clickable and its reasoning renders in the pane, and can be
  **brought into the conversation** as a turn.
- Background Task rows for deliberations are clickable ("◔ reasoning"); everything stays R10212 (reads + the
  one chat POST; submit/cancel are copied osctl verbs) and DEMO-safe (a demo trace ships).
- **Fixed** a latent bug: a Plan-Mode card whose question carried raw newlines (the numbered steps) failed
  `JSON.parse` and rendered as a `<pre>` fallback instead of an interactive card. A lenient `parseAUQ` now
  escapes raw control chars in an otherwise-compact envelope, and the DEMO plan card's steps are properly
  escaped — so questions AND plans render interactively in the console. The same lenient `parseAUQ` was
  applied to the other two chat surfaces (the Sovereign Brain observatory + lm-status), so a real model
  emitting raw-newline plan cards renders interactively there too; `test_all_chat_surfaces_render_auq_interactively`
  now asserts the lenient parse + a no-stray-control-bytes guard on all three panels.
- `tests/lint/test_code_console_webapp_contract.py` gains `test_plan_pane_is_live_for_plans_and_reasoning`;
  the scaffold contract tracks `renderPlanPane()`.

### Added — Background Tasks: a job runtime + a Code Console Plan-pane split, like claude.ai/code (2026-07-12)

The box now runs long-running work OFF the request path and shows it in a supplementary pane that splits the
Code Console's right Plan pane 50/50 — a background CoAT deliberation, a model eval, a secondary-model load, a
GPU job, and jobs mirrored from the RTX-4090 passthrough VM (operator-directed; plan approved: runtime +
Plan-pane split + 4090-VM bridge). SDD-204.

- NEW `scripts/operator/lib/jobs_store.py` — a PERSISTED job registry (atomic temp+rename → survives restart)
  with create/update/list/ingest/prune + a summary.
- NEW `scripts/operator/jobs-api.py` (:8142) — the runtime: a bounded worker pool drives a job
  queued→running→(done|failed|cancelled) with live progress. Kinds: `deliberation` (calls the gateway
  `/v1/coat`), `eval`/`model-load`/`gpu-job` (a no-shell subprocess runner with PID-tracked cancellation),
  `demo`, and `vm-job` (mirrored from the VM, not host-run). Orphaned `running` jobs are marked failed on
  restart — never a zombie. Read endpoints feed the pane; submit/cancel/ingest are the runtime control surface.
- NEW `sovereign-osctl jobs list|status|submit|cancel` (`scripts/operator/lib/jobs_cli.py`). `list`/`status`
  are read-only; **submit/cancel are the ACTIONS** the cockpit routes through the sanctioned `control-exec-api`
  — the pane never POSTs a mutation (R10212), it copies the signed osctl verb.
- The **Code Console Plan pane splits 50/50** (`webapp/code-console/`): Plan/artifact on top, a live
  **Background Tasks** list below (state · progress · kind · device · cancel), fed by a read-only
  `code-console-api` proxy `/api/code-console/jobs`. A header toggle shows/hides it (persisted); "＋ deliberate"
  and per-task cancel copy the `sovereign-osctl jobs …` verb; graceful when the runtime is down; DEMO-safe
  (zero network in DEMO — SB-077).
- NEW `scripts/jobs/vm-bridge-guest.py` — the **4090-VM bridge**: runs inside the VFIO passthrough VM, probes
  its `nvidia-smi`, and POSTs entries to the host `jobs-api` `POST /jobs/ingest` (upserted as `vm-job` rows), so
  the host cockpit sees jobs on the passed-through GPU.
- NEW `systemd/system/sovereign-jobs-api.service` (R171-hardened; jobs dir read-write). feature-coverage maps
  `jobs → code-console`. `tests/lint/test_jobs_runtime_contract.py` guards the registry, the worker lifecycle,
  cancellation, graceful failure without a gateway, the surfaces, the unit, and the bridge.
- Honest gating (SB-077): runtime + pane + CLI + ingest are live and tested; the guest→host **channel** for the
  VM bridge (libvirt NAT gateway / vsock, via `SOVEREIGN_JOBS_HOST`) is the deployment step and is inert until
  wired — and says so.

### Changed — reasoning engine hardened: an adversarial review found the mechanics were presets/labels; made them real (2026-07-12)

A "push it to the limits" review (three independent adversarial reviewers + live verification) found the
search *harness* was correct but several reasoning *mechanics* were presets/labels, and the CoAT centerpiece
was inert in production (recall *lifted* values but did not *steer* which path won). Every finding is now
closed — the ladder rungs are behaviourally distinct:

- **CoAT now steers, not just lifts.** `CortexRecall` keys recall on the **per-thought** `ctx.text`
  (FNV-1a sketch OR'd with the problem sketch), not only the problem — so different thoughts recall
  different memory and recall can change which path wins. Relevance now uses an **absolute** `rel/(rel+K)`
  scale so a weak hit stays weak (the old within-batch-max faked maximal support). Recall also conditions
  thought **generation** (RAG). Proven by `coat_recall_steers_the_winning_path` + a normalization test.
- **Simulation is a real look-ahead rollout** to `max_depth` (not a one-step value relabeled "playout").
- **Backtracking is real** — a thought below `prune_below` is abandoned and its M007 branch pruned during
  the search; the trace reports `abandoned` / `branches_committed` / `branches_pruned`.
- **ToT offers real BFS and DFS** search strategies (`SearchStrategy`), not only UCT.
- **C-MCTS is load-bearing** — categories are phase-gated per depth, so constraining changes the search;
  there is a `cmcts()` preset and a "C-MCTS" rung. `rung()` is now behavioural (can't mislabel).
- **Model-backed thoughts when a model is loaded** (`ModelThoughts` via the generator); the trace's new
  `thought_source` field says `"model"` vs `"heuristic"`, and the panel shows a chip — placeholders are
  never passed off as reasoning. The `expand()` seed set is truncated to `expand_k` (protects the CoT
  chain invariant); degenerate configs are rejected.
- **Defects fixed:** brain-api now surfaces a gateway 4xx (e.g. a bad rung) as its **structured message**
  instead of "unreachable"; `now`/`half_life` are caller-supplied (not a frozen constant); the `dry_runs`
  metric/doc now names all four read-only ops; `esc()` escapes single quotes; the read-only-memory invariant
  is asserted (`learned==0`, `dry_runs>=1`). The directive's overstatements (BFS/DFS, the `value-plane`
  mapping, "external" info, C-MCTS as a rung) are corrected to match the code.

### Added — the CoAT engine: one parameterized MCTS that IS the whole reasoning ladder, recalling the live Memory-OS (2026-07-12)

Increment 2 of "both, sequenced": the runtime that makes the reasoning progression real. `sovereign-coat`
is a single iterative-MCTS engine over the M007 branch tree, and the earlier rungs fall out as presets —
CoT (`expand_k = 1`), ToT (branch, greedy), MCTS (UCT select/expand/simulate/backprop), C-MCTS (a bounded
five-category action space), and **CoAT** (the default): every expansion recalls associative memory that
modulates the thought's value. The two model-gated inputs are traits (`ThoughtSource`, `AssociativeMemory`),
so the search harness is deterministic + fully tested without a model; only the thought *content* is
model-gated.

- NEW crate `sovereign-coat` — the engine (`CoatEngine`, `CoatConfig::{cot,tot,mcts,coat}`, `ThoughtCategory`,
  `CoatTrace`). 8 unit tests prove each rung, the UCT/backprop invariants (root visits == budget; parent
  dominates child), the constrained action space, determinism, and — the centerpiece — that **recall lifts
  a memory-supported thought onto the winning path** while an equal-prior bare thought does not. Clippy
  `-D warnings` clean.
- The gateway exposes **`POST /v1/coat`** (`GatewayRequest::Coat` → `CoatTrace`), running the engine with the
  daemon's **live Cortex Memory-OS as CoAT's associative memory** (`CortexRecall` adapter over the new
  `Cortex::recall`). Read-only: it decides without learning (only the dry-run counter moves). A heuristic,
  model-free `ThoughtSource` makes the search + recall demonstrable today; a model-driven source replaces it
  when a generator is loaded. Verified live: a CoAT deliberation recalls 128 items from the seeded store and
  the recall boosts each step's value above its bare prior.
- The Sovereign Brain observatory gains a **CoAT deliberation** card (`/brain/coat` in `brain-api.py`,
  `webapp/brain/`): pick a rung, deliberate, and watch the winning reasoning chain with each step's
  backpropagated value vs prior, visit count, and the memory recalled there (↑ marks a memory-lifted thought).
- `tests/lint/test_deliberate_reasoning_contract.py` extended: the crate is the whole ladder, the gateway
  endpoint runs over the live memory, and the observatory surfaces it.

### Added — deliberate reasoning: the CoT → ToT → MCTS → C-MCTS → CoAT progression, mapped onto the box's own primitives (2026-07-12)

Third in the reasoning/interaction trilogy after QCFA (align on intent) and Plan Mode (review the plan):
this codifies how the AI *thinks* — deliberate, search-based reasoning instead of a single reactive pass.
The sovereign thesis: each rung of the ladder already maps onto a real execution primitive, not a borrowed
metaphor. Increment 1 of "both, sequenced" — the directive + scaffold posture; the `sovereign-coat` engine
follows.

- NEW standing directive `docs/standing-directives/2026-07-12-deliberate-reasoning.md` (registered in
  INDEX) — maps **CoT** → a single `Cortex::act` path, **ToT** → `sovereign-branch-tree`
  (fork/commit/prune/lineage) + `sovereign-value-plane` scoring, **MCTS** → the same tree + the value-plane
  "MCTS + PRM" critic + backprop over `lineage()`, **C-MCTS** → the cortex's bounded `NextAction` /
  constrained routing categories, and **CoAT** (the centerpiece) → `Cortex::deliberate` forking branches
  against the **recalled** context where "recalled memory modulates the reward" — the Memory-OS `retrieve()`
  IS CoAT's associative memory. Honest gating: the search harness ships + is tested today; useful thoughts
  are model-gated.
- The reasoning scaffold (`config/prompts/qcfa-system-prompt.md`) gains a **DELIBERATE REASONING** posture:
  CoT (reason step by step, show your work) for the routine, branch-and-backtrack ToT for the genuinely
  hard, and always recall before concluding (CoAT).
- `tests/lint/test_deliberate_reasoning_contract.py` guards the progression, the primitive mapping, that
  the mapped crates actually exist, and the scaffold posture.

### Added — Plan Mode presented for approval in the cockpit (2026-07-11)

Completes the plan → approve flow: the sovereign AI proposes a PLAN (summary + numbered steps) and
presents it for approval, reusing the interactive-clarification rendering already on every chat surface.

- The scaffold (`config/prompts/qcfa-system-prompt.md`) now instructs Plan Mode: for a mutating /
  consequential task, propose a plan inside the ` ```askuserquestion ` envelope with the four approvals
  as options (Approve / Reject / Approve with changes / Approve and remember), holding execution until
  approved. So the plan renders as a clickable card on code-console, the Sovereign Brain panel, and
  lm-status — no new UI. A destructive step is auto-blocked by Auto regardless.
- The AUQ question class now preserves newlines so numbered plan steps render as lines; the
  code-console DEMO thread shows a live plan card.

### Added — Plan Mode + User Approval + Auto-mode safety classifier (2026-07-11)

Companion to the QCFA framework: where QCFA aligns on intent before acting, this reviews the plan
before executing. The AI proposes a plan and holds execution; the operator Approves / Rejects /
Approves-with-changes / Approves-and-remembers; permission modes (manual/auto/bypass) control how
often it stops; and an Auto-mode safety classifier auto-blocks destructive ops. Built on
sovereign-os's existing approval gates. One framework, two homes.

- NEW standing directive `docs/standing-directives/2026-07-11-plan-mode-user-approval.md` (registered
  in INDEX) — canonical for both the local sovereign AI and external agents/operators.
- NEW `scripts/operator/lib/permission_classifier.py` — the Auto-mode safety classifier: classifies a
  command destructive / routine / unknown and decides allow / block / confirm per mode. **manual** →
  confirm mutating (destructive flagged DANGER); **auto** → BLOCK destructive, allow routine, confirm
  unknown; **bypass** → allow. Destructive families: `rm -rf`, `dd of=/dev/*`, `mkfs`/`wipefs`, `nvme
  format`, `zpool`/`zfs destroy`, force-push, `git reset --hard`, fork bomb, `curl|sh`, `poweroff`, …
  Extensible via config; stdlib-only; tested.
- NEW `config/permission-modes.yaml` — the modes + the 4 approvals + the operator-tunable
  `destructive_extra` extension point. `SOVEREIGN_OS_PERMISSION_MODE` (default manual).
- `control-exec-api` (the ONE sanctioned execute daemon) now consults the classifier under the active
  mode: **Auto BLOCKS a destructive control (403) before it reaches the primitive**; the verdict rides
  on every response. Layers onto the existing dry-run-default + operator-key + type-to-confirm gate.
- NEW osctl verb `sovereign-osctl permission [--mode …] <command>`; `tests/lint/test_plan_mode_contract.py`
  guards the directive, config, classifier decisions, and enforcement.

### Added — interactive clarification across every chat surface (2026-07-11)

Extends the QCFA/AUQ interactive rendering (first shipped on the code console) to the other chat
surfaces, so the thinking-partner behaviour is consistent everywhere.

- The **Sovereign Brain panel chat** (`/brain/`) and **lm-status (D-22)** chats now detect the fenced
  ` ```askuserquestion ` envelope and render clickable options + a free-text "Other", feeding the
  picked answer back as the next turn — graceful `<pre>` fallback if unparseable. The brain chat also
  gained a small in-page history so a clarification answer continues the thread.
- `tests/lint/test_qcfa_framework_contract.py` now asserts ALL chat surfaces (code-console, brain,
  lm-status) render AUQ interactively. The renderers are functionally verified (node); full lint green.

### Added — QCFA + interactive-clarification framework (2026-07-11)

Codifies the operator's directive to make AI an interactive thinking partner (not a typewriter):
QCFA (Task / Context / References / Framework-Evaluate) + AskUserQuestion (hold execution, interview)
+ suggestions. One framework, two homes.

- NEW standing directive `docs/standing-directives/2026-07-11-qcfa-interactive-clarification.md`
  (registered in INDEX) — the canonical interaction model for BOTH the local sovereign AI (the
  gateway model + agent-runtime + chat surfaces) AND external agents/operators working on the repo.
- NEW reusable scaffold `config/prompts/qcfa-system-prompt.md` — the QCFA/AUQ system prompt: structure
  intent; hold execution + ask 1–4 decision-shaped questions + suggest; iterate; then execute.
- `scripts/inference/prompt.py` injects the scaffold as a leading `system` turn, OPT-IN via
  `SOVEREIGN_OS_QCFA` (default off, so a base completion model's chat is never degraded; recommended
  on once a capable instruct model is loaded). Never double-injects over a caller-supplied system
  turn; every chat surface routes through it, so one switch applies everywhere. The 20 prompt tests
  stay green.
- The scaffold has the model emit questions in a machine-parseable envelope (a fenced
  ` ```askuserquestion ` JSON block), and the **code console renders it interactively**: the chat
  (`webapp/code-console/index.html`) parses the block into clickable options + a free-text "Other"
  and feeds the picked answer back as the next turn — a graceful `<pre>` fallback if unparseable, so
  a question is never raw-swallowed. The DEMO thread shows a live card. This is the difference
  between a thinking partner and raw text.
- `tests/lint/test_qcfa_framework_contract.py` guards the directive, the scaffold + its envelope, the
  opt-in wiring, and the console's interactive rendering.

### Added — Sovereign Brain refinements: second-brain browser, cross-links, memory controls (2026-07-11)

Three follow-ups closing out the brain panel's observability + operability.

- **The second brain is now browsable.** The panel showed the Rust cortex memory in full but the
  Python Memory-OS only as a summary; it now renders the operational entries (id / type / stage /
  state / summary) as a table beside the cortex store — the two brains, side by side.
- **One clear home.** The `trinity` + `d-03-model-health` "Live Gateway" strips now link to the
  Sovereign Brain observatory (framed as summaries), so there is a single detailed home.
- **Memory lifecycle from the panel.** The CLI-gated Memory-OS controls (forget / undo / decide /
  request; SDD-052/059) are surfaced on the brain panel via the control-surface — copy-able,
  refuse-by-default, mutation stays CLI (`applies_to: […, brain]`). Contract-asserted.

### Added — read-only routing probe: preview without polluting memory (2026-07-11)

The Sovereign Brain panel's routing probe sent `/v1/simple`, which LEARNS — so every probe grew the
brain's memory. This adds a read-only decide path so previewing is side-effect-free.

- NEW gateway endpoint **`POST /v1/simple-explain`** — the read-only sibling of `/v1/simple`: it
  decides via `Cortex::act` (tick + execute, both `&self`) and returns the FULL decision
  (route/device/verdict/summary) with `learned: false`. No memory admit and no request/learned ledger
  movement — only the honest `dry_runs` counter (`GatewayServer::decide` + `GatewayRequest::SimpleExplain`).
- `brain-api.py`'s routing probe now POSTs `/v1/simple-explain`, and the panel labels it a read-only
  preview. Proven: 3 probes left memory unchanged (2 → 2); a control `/v1/simple` then grew it (2 → 3);
  ledger `dry_runs 3, learned 1, total_requests 1`.
- Rust unit test `simple_explain_decides_without_learning`; the brain contract asserts the probe uses
  the no-learn endpoint.

### Added — the Sovereign Brain panel: observe + operate the intelligence layer (2026-07-11)

The earlier cockpit work bolted a status *strip* onto trinity/model-health — a tripwire, ledger
counters, and a memory *count*. That is not observing the brain, and it left the crates nebulous.
This is the dedicated observatory + console: you look INTO the brain and drive it.

- NEW `scripts/operator/brain-api.py` (port 8141) — read-only over the gateway's read surfaces + a
  non-mutating decide/chat compute; reuses `gateway_probe`. Endpoints: `/brain.json` (status +
  memory summary + daemon map), `/brain/memory` (the DECODED cortex store — every hot meta's CoALA
  type / trust / value / freshness / flags + its cold ground-truth episode·summary·facts — beside
  the Python Memory-OS operational store), `/brain/route` (a 7-axis decide probe), `POST /brain/chat`
  (streamed from the :8787 OpenAI shim), `/brain/daemons` (the 9-daemon crate map). Forget/clear stay
  CLI-gated (SDD-052).
- NEW `webapp/brain/index.html` — a full contract-compliant panel: the **memory browser** (the
  actual learned memories, not a count; both stores side by side), live gateway telemetry + the
  never-cloud-spill tripwire, a **routing probe** (pick the 7 axes → watch the brain decide, and
  learn), inline **chat** with the local model, and the **daemon/crate map** that de-nebulizes the
  layer. Demo-capable.
- Wired in: `sovereign-brain-api.service`, a `dashboard-catalog` entry + app-shell nav entry (slug
  `brain`, category trinity), the demo manifest, the app-shell/controls-audit baselines, and
  `tests/lint/test_brain_panel_contract.py`. Full lint green (5924); the panel serves live and its
  feeds decode real memory + stream real generation.

### Added — the compiled brain ships in the image: host-copy bake path (2026-07-11)

A freshly flashed SAIN-01 can boot with the sovereign brain already compiled + enabled (and
optionally a model), so it generates out of the box — no first-boot compile.

- **Host-copy staging (not in-container).** The bake has no external network (snapshot mirror only)
  and apt cargo predates the pinned 1.89, so rustup cannot fetch the toolchain there — an
  in-container build is impossible. So `scripts/build/07-image-build.sh` builds the intelligence
  layer on the BUILD HOST (rustup 1.89) and stages the daemon binaries into
  `mkosi.extra/usr/local/bin` (`stage_intelligence_binaries`) — the same "staged from the build
  host" pattern as Claude Code. The binaries link only glibc/libm/libgcc, so they run in the image
  with zero added packages.
- **Optional baked model.** `stage_intelligence_model` fetches a small real model (default
  SmolLM-135M) into `mkosi.extra/var/lib/sovereign-os/models/…` so the gateway generates on first
  boot.
- **Auto-start.** `provision-bake.sh` installs + enables `sovereign-gatewayd.service` when the
  binary was staged (guarded so a source-only image never enables a unit with no `ExecStart`).
- Gated on opt-in knobs `SOVEREIGN_OS_BAKE_INTELLIGENCE` + `SOVEREIGN_OS_BAKE_MODEL` (env, dry-run
  safe). Absent ⇒ the image ships source and builds the brain at provision time (the prior
  behaviour). Verified: `SOVEREIGN_OS_RUST_BINDIR=<stage> build-intelligence.sh` stages all 9
  daemons; the gatewayd binary is glibc-only portable.

### Added — the gateway generates: OpenAI chat shim on :8787 + the cockpit talks to the brain (2026-07-11)

`sovereign-gatewayd` stops being a pure decision surface and becomes a local generation brain: it
loads real weights + a real tokenizer at startup and serves the OpenAI chat shim, and the cockpit
chat console now talks to it.

- **Local generation in the daemon.** When `SOVEREIGN_GATEWAY_MODEL` names a model dir
  (`config.json` + `*.safetensors` + `tokenizer.json`), the gateway loads it into a `QuantModel` +
  `HfBpeTokenizer` at startup and flips the manifest's `open-ai-shim` surface **Live**. Absent /
  not-yet-fetched ⇒ it stays a pure decision surface (no error). New `GatewayServer::generate_chat`
  streams decoded UTF-8 chunks token-by-token.
- **`POST /v1/chat/completions` (OpenAI SSE).** A new streaming path in the HTTP transport emits
  `data: {chunk}` deltas + a final `finish_reason`/`usage` chunk + `data: [DONE]` — the exact shape
  `scripts/inference/prompt.py` consumes. A modelless gateway answers an honest `503`.
- **`DecoderLayer: … + Send`** — a one-line supertrait so a built model can be owned by the
  thread-per-connection daemon (every block is plain owned data, so `Send` was already satisfied;
  no call-site changes; workspace + the inference-crate tests stay green).
- **The cockpit talks to the brain.** `prompt.py` (the code-console / lm-status chat engine) now
  targets the sovereign gateway (:8787) first, falling back to the tier router (:8080) when the
  gateway is down or carries no model — chat degrades gracefully. Env-overridable; the honest-error
  contract (SB-077) is preserved. Verified end-to-end: prompt.py → gateway :8787 → *"The capital of
  France is"* → *" Paris. It is the largest city in France…"* (streamed SSE, real SmolLM-135M).
- The `sovereign-gatewayd.service` unit gains the optional `SOVEREIGN_GATEWAY_MODEL` env.

### Added — the sovereign brain does REAL inference: HF tokenizer bridge + real-model generation (2026-07-11)

The Rust intelligence layer's weight loader was real but tokenizer-crippled (a hardcoded 256-vocab
byte tokenizer, so any genuine 32k+ vocab model hit `VocabMismatch`). This closes the gap:
`sovereign-serve --model DIR` now runs a real trained checkpoint and generates COHERENT text.

- NEW crate **`sovereign-hf-tokenizer`** — a faithful loader for a HuggingFace `tokenizer.json`
  (GPT-2 byte-level BPE: explicit vocab + ranked merges + the byte↔unicode alphabet). Pure Rust +
  `serde_json` with a **hand-rolled GPT-2 pre-tokenizer** — no external `tokenizers`/`regex`/
  `sentencepiece` dependency (the workspace rolls its own; sovereignty-clean). Validated against
  SmolLM's real vocab (`the`→1195, ` the`→260, ` quick`→2365, individual-digit splitting, exact
  round-trip decode); 6 unit tests.
- **`sovereign-serve --model DIR`** now uses it when a `<dir>/tokenizer.json` is present: it loads
  the weights into a `QuantModel` (the loader carve-out), pairs them with the real tokenizer,
  prepends BOS, and generates through the engine directly — a **zero-ripple** path that touches
  neither `QuantLlm` nor its tests. Falls back to the byte tokenizer for the vocab-256 fixtures.
- **Proof (real SmolLM-135M, ~0.5 GB, CPU, 4.2 s for 3×24 tokens):**
  - *"The capital of France is"* → *" Paris. It is the largest city in France…"*
  - *"Once upon a time"* → *", there was a little girl named Lily. She loved to play with her friends…"*
  This proves the whole sovereign transformer (RoPE, GQA, SwiGLU, RMSNorm, the HF q/k permute,
  greedy sampling) is **numerically HF-Llama-compatible** — the runtime does genuine local
  inference on real downloaded weights, not just synthetic filler.
- NEW `scripts/intelligence/fetch-model.sh` — opt-in, manual-only helper to fetch a small real
  model (default SmolLM-135M). Never wired into provisioning or first-boot.

### Added — the sovereign gateway brain: durable memory + live cockpit (2026-07-11)

The dormant Rust intelligence layer's `sovereign-gatewayd` (M048 provider-inversion gateway
over the deterministic cortex engine) becomes a real, self-remembering daemon the cockpit can
watch — the durable-memory + cockpit activations of the brain arc.

- **Durable Memory-OS.** `MemoryStore` now serialises (serde); `sovereign-gatewayd` resumes
  from `SOVEREIGN_GATEWAY_MEMORY` at boot and a background thread atomically snapshots the
  learning Cortex (temp-write + rename; cadence `SOVEREIGN_GATEWAY_MEMORY_SAVE_SECS`). The unit
  points it at `/var/lib/sovereign-os/memory/cortex.json` (`StateDirectory` — the one writable
  path under `ProtectSystem=strict`). Verified end-to-end: an empty store stays empty (load
  works, no cold re-seed), a fresh seed persists to disk (save works), and learned commits
  accumulate across restarts (the store grew 3→4→5 over three daemon lifetimes). Recall no
  longer resets each boot.
- **Cockpit ↔ live gateway (read-only).** NEW `scripts/operator/lib/gateway_probe.py` — a
  stdlib server-side probe of the running gateway (:8787): `GET /health` + `/admin/ledger` +
  `/manifest` plus the persisted snapshot on disk, degrading to a structured `{up:false}` when
  the daemon is down (a browser can't cross-origin fetch :8787, so the same-origin api daemons
  proxy it). Wired into `trinity-api` (`GET /gateway`) and `model-health-api`
  (`GET /api/models/gateway`); the **trinity** and **d-03-model-health** panels render a "Live
  Sovereign Gateway" section — the never-cloud-spill sovereignty tripwire, the cost/route
  ledger (committed / learned / by-role), the live gateway surfaces, and the persisted-memory
  item count. New osctl verb `sovereign-osctl gateway [--json]` prints the same probe.
  Read-only at every surface. `tests/lint/test_gateway_cockpit_contract.py` guards the shape +
  graceful degradation; the 93 panel-contract lints stay green.

### Added — Live-reload for the dev operator panels (2026-07-11)

Operator directive (verbatim): *"couldn't there be a live-reload feature now that I think
about it that is enabled by default ? so that I dont have to redo make panel everytime. one
way that doesn't even need to kill anything if possible ? aren't those static assets ? in
the page if a panel has updated there could be a notification at the bottom center and offer
to refresh the page. and we dont reload something for nothing I guess but the reload include
the services / apis behind. no matter how complex and long we can take the time. no rush, do
this right and performant"*.

Editing a panel no longer needs a stop + rerun — in dev (`make panel`) AND on a flashed box
(the operator keeps developing on the live `/opt/sovereign-os` checkout). Shipped ON by
default; a locked build sets `bake.livereload:false`. See SDD-203.

- Round 559 — NEW `scripts/operator/lib/reload-run.py`: a **self-re-exec launcher** every
  panel daemon runs through. It `runpy`-runs the daemon in-process (same PID, owns the
  socket) and, on an edit to the daemon's OWN `.py`, `os.execv`s the **same process image**
  in place — no external kill, no `Ctrl-C` (the operator's "doesn't even need to kill
  anything"); the socket re-binds in milliseconds (`allow_reuse_address`). Lazy-import files
  appearing later are absorbed (never bounce mid-request); a crashed daemon stays recoverable
  (a non-daemon watcher re-execs on the next save). Disabled it is a transparent pass-through.
- Round 559 — NEW `scripts/operator/livereload-broker.py`: ONE loopback file-watcher on
  `:8136` for the whole fleet (performant — not one watcher per daemon) that pushes
  `event: reload` over SSE **only for paths a panel depends on** (its `webapp/<slug>/`,
  `webapp/_shared/`, its daemon source + the `scripts/…`/`config/…` that daemon shells —
  parsed once at startup, stdlib-only). Nothing reloads "for nothing". Read-only; never
  leaves 127.0.0.1; not shipped/enabled in the image.
- Round 559 — the SDD-067 app-shell block (`webapp/_shared/app-shell-snippet.html`, synced
  byte-identical to all 52 adopted panels) gains a small `EventSource` client that shows a
  **bottom-centre "This panel updated — Refresh"** toast on a relevant change. It is
  loopback-gated (inert in the image), **non-mutating** (a GET stream + a `location.reload()`
  navigation — adds no `fetch`/XHR/POST, so `test_app_shell_chrome_is_non_mutating` stays
  green), coalesces a burst into one toast, and never auto-reloads (it *offers*, per "offer
  to refresh the page"). Static HTML + shelled-script edits need NO restart (a pure refresh);
  only a daemon's own `.py` triggers the in-place re-exec ("include the services / apis
  behind").
- Round 559 — `scripts/operator/panel.sh` starts the broker first, then wraps the two main
  servers + every panel daemon in `reload-run.py`. **ON by default**; opt out
  `SOVEREIGN_OS_LIVERELOAD=0`.
- Round 559 — **installed-box wiring** (so it works on a flashed OS, no `make panel`): NEW
  `systemd/system/sovereign-livereload-broker.service` (R171-hardened, loopback :8136);
  `scripts/build/provision-bake.sh` §5c (mkosi image) + `scripts/install/install-gui-dashboards.sh`
  §3c (root-reflash) enable the broker and generate a systemd **drop-in** per enabled panel
  API + the hub that wraps `ExecStart` through `reload-run.py` and sets
  `SOVEREIGN_OS_LIVERELOAD=1` — so a daemon's own `.py` edit re-execs it in place (same PID,
  no `systemctl restart`). **Shipped unit files stay byte-identical** (the wrap lives only in
  the drop-in), so every per-unit lint is untouched. Gated on the NEW bake flag
  `SOVEREIGN_OS_BAKE_LIVERELOAD` (`profiles/*.yaml` `provisioning.bake.livereload`, default
  true; mkosi-emit + schema); `sain-01` sets it on.
- Round 559 — NEW `tests/lint/test_live_reload_contract.py` (client present + loopback-gated
  + `EventSource`-only + broker/port consistency + daemons compile + panel.sh wiring) + NEW
  `tests/nspawn/test_live_reload.sh` (broker SSE relevant-notifies / irrelevant-stays-silent
  + in-place self-re-exec proven by **same PID + fresh code**).

### Added — Science-tools catalog + NVIDIA Warp particle-sim integration & panel (2026-07-09)

Operator directive (verbatim): *"There should be somewhere something about Science
experiment, tools of such type, we will add to it Nvidia Warp / warp-lang and we
will start coding it, its integration and panel"* → *"the full job, planned properly"*.

Materialises the operator's Image-2 "scientific / merge / specialist catalog"
(info-hub `model-catalog` `dna`/`protein`/`particles`) into sovereign-os, and ships
NVIDIA Warp end-to-end. See SDD-070.

- Round 558 — NEW `config/science-tools.yaml` + `schemas/science-tools.schema.yaml`
  + `tests/schema/test_science_tools_schema_conformance.py`: a schema-validated
  catalog of 7 non-LLM domain compute tools (DNA / protein / particles), kept OUT
  of the LLM model catalog. Anchored to the `simulation` REPL kind (m023 / M00374).
- Round 558 — NEW `scripts/science/warp-runner.py` (the ONLY warp-importing script):
  device-selects `cuda:0` if `wp.is_cuda_available()` else `cpu`, runs a
  `warp.sim`-class particle drop-and-bounce sim, `--json`/`--emit-metrics`, exit-0
  clean even when warp-lang is absent or no CUDA is present. Verified on CPU
  (50k particles) in an isolated venv.
- Round 558 — NEW `scripts/science/science.py` (stdlib-only `list`/`status`/`run`/
  `install`/`info`) + the `sovereign-osctl science` bridge; read-only
  `scripts/operator/science-api.py` (:8134, POST→405) + `webapp/science/index.html`
  + `sovereign-science-api.service`; new `science` dashboard category + catalog entry;
  `surface-map` `science` module = core/cli/api/service/webapp.
- Round 558 — first-boot install: `scripts/hooks/post-install/warp-setup.sh` +
  `sovereign-warp-setup.service` (in `FB_UNITS`); `warp-lang` added to
  `operator-deps.toml [pip]`; enabled at bake (`provision-bake.sh §5`) and on live
  hosts (`install-gui-dashboards.sh`). L3 `tests/nspawn/test_science_panel.sh` (19/19)
  + a CI layer-3 step. Metrics `sovereign_os_post_install_warp_setup_total` +
  `sovereign_os_science_warp_*`.

### Added — GUI + dashboards ON by default for the root-of-machine install (2026-07-02)

Operator directive (verbatim): *"lets make with GUI by default when we install
at the root of the machine, I will keep Debian 13 GUI to explore the dashboards
and lets make sure we have them running by default and that I can easily find
them on a fresh install."* This **reverses the prior non-GUI-by-default stance**
(R225, `scripts/dashboard/serve.py`) for the root install only — headless is
still available via `SOVEREIGN_OS_INSTALL_GUI=0`.

- **New `scripts/install/install-gui-dashboards.sh`** (idempotent, root): installs
  a Debian 13 desktop (GNOME by default; `minimal`=XFCE or `none` selectable via
  `SOVEREIGN_OS_DESKTOP`) + a browser, deploys the dashboard app tree to
  `/usr/local/lib/sovereign-os`, enables the dashboard services on boot, and drops
  a discoverable **"Sovereign Dashboards"** launcher into the app menu, the
  desktop, and login autostart. Runs both in the install chroot (offline
  wants-symlink) and on a live system.
- **New `systemd/system/sovereign-dashboards.service`**: runs the panel **hub**
  (`build-configurator-api.py`) on boot, loopback-bound (`127.0.0.1:8100`), full
  R171 defense-in-depth block (passes the systemd fleet-hardening gate). The hub
  statically serves every `webapp/` panel — verified serving **37 panels**
  (master-dashboard + d-01..d-20 + siblings) with a `/panels/` discovery index.
- **New `share/applications/sovereign-dashboards.desktop`**: XDG launcher that
  `xdg-open`s `http://127.0.0.1:8100/` in the operator's browser.
- **`scripts/install/install-sovereign-root.sh`**: `SOVEREIGN_OS_INSTALL_GUI`
  (default `1`) now provisions GUI + dashboards inside the chroot before unmount;
  the closing message tells the operator exactly where to find them.
- **`scripts/hooks/post-install/first-login-assistant.sh`**: prints the dashboard
  hub URL + how to find the launcher when the GUI path is installed.

Exposure stays the operator's call: everything binds loopback; a documented
`bind.conf` drop-in opens it to LAN/tailscale for a headless box.

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

`TernarySwiGlu` (new `swiglu.rs`) then builds the *gated* FFN the decoder
actually runs — `h = SiLU(W_gate·x) ⊙ (W_up·x)`, `out = W_down·h` — with
all three projections as multiplication-free `BitLinearLayer`s. The heavy
`O(hidden·dim)` matmuls are fully ternary (every inner-product multiply
eliminated, summed `OpCount`); the only genuine multiplies left are the
`O(hidden)` elementwise SiLU-gate products — exactly the BitNet trade.
Proven bit-for-bit equal to a dense SwiGLU on the de-quantized weights
(over `Base3` + `TwoBit`), with mul-free accounting, the zero-weight
residual identity, and shape-rejection tests (6 new). This is the genuine
multiplication-free drop-in for the float SwiGLU the quant decoder block
runs today — the M073 FFN at the shape a real decoder uses.

`BitLinearLayer::forward_packed` implements the dump's still-unbuilt
F06060-F06062 ask: a forward that runs **directly on the 2-bit packed
codes** — a single pass over the packed bytes, no intermediate
`Vec<Trit>`, each weight a `01`→add / `10`→subtract / `00`→skip decision
read in place. This is the scalar form of the AVX-512 lookup-table matmul
("no de-quantization, single-pass through CPU registers") — the
correctness foundation a SIMD lane must reproduce. Gated bit-for-bit
(output *and* `OpCount`) against `forward()` over random weights;
restricted to `Packing::TwoBit` (the byte-aligned LUT target) via the new
`PackedForwardUnsupported` variant. `BitLinearMlp::forward_packed` and
`TernarySwiGlu::forward_packed` propagate it to the block level, so a
whole FFN (or gated FFN) runs single-pass on packed codes — each
bit-for-bit equal to its `forward()`.

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
  maps route → backend tier (blackwell→oracle / rtx4090→scout / cpu→cortex /
  hibernate→defer), honoring **honor-Hibernate · map-route→tier · read-only**.
  Graceful-offline: binary absent/errored → `scheduler_available=False` so the
  gateway falls back to its own SDD-011 routing (never crashes, never fabricates
  a route). Maps route → runtime service (blackwell→Oracle Core / rtx4090→Logic
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
