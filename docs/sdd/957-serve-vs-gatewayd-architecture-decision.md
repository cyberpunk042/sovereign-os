# SDD-957 — serve-vs-gatewayd architecture: decision package (awaiting operator decision)

> Status: **draft — decision package, operator decision pending** (Q-957-A below)
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-12
> Number band: **950–999 (general / audit session)** per SDD-100.
> Scopes finding: **F-2026-089** ("`sovereign-serve` is the safer path but is dead relative to the daemon"). This SDD **scopes and recommends**; it does not implement. Ledger F-2026-089 stays open until the operator picks an option.
> Mandate module: **E11.M957** (operator-mandate cross-link).
> Derived from: a dependency-graph + code comparison of `crates/sovereign-serve` vs `crates/sovereign-gatewayd`, post-SDD-206.

## Why this is a decision, not a fix

F-2026-089 says "decide the architecture — either fold serve's filter chain into gatewayd or promote serve to be the daemon." That's an architectural choice with a downstream blast radius (it touches `generate_chat`, which the parallel Anthropic-Messages-API workstream owns), so it needs an operator decision, not a unilateral edit. This SDD lays out the real picture and recommends.

## Two corrections to the finding's premise (both material)

The finding was written before SDD-206 and reads serve's **Cargo.toml dependency list** as if it were serve's **runtime pipeline**. Precisely:

1. **serve's actual library pipeline is only cache → complexity → budget.** `Server::serve()` (`sovereign-serve/src/lib.rs:126-200`) composes three stages: exact+semantic **cache** (`sovereign-completion-cache`), a text-derived **complexity** tier (`sovereign-complexity`), and a **token-budget** meter that refuses *before* generating (`sovereign-token-meter`). The `pii-redact` / `secret-scan` / `toxicity` / `context-budget` the finding credits to serve are wired **only in serve's demo binary** (`main.rs`), each behind an opt-in CLI flag (`--redact` / `--screen`), **not** in the composable pipeline.

2. **gatewayd is no longer guard-less — SDD-206 already put the safety filters in it, default-on.** `generate_chat` (`gatewayd/src/lib.rs:1187-1307`) applies injection screening (input) + secret/PII redaction + toxicity scoring (output) via `GuardConfig`/`StreamGuard` — *more* wired than serve's opt-in-binary versions.

So the "richer, safer serve vs bare daemon" framing is stale. After SDD-206 the **only capabilities serve's pipeline has that the daemon still lacks** are:

| Capability | serve (library) | gatewayd (post-206) | Notes |
|---|---|---|---|
| **Completion cache** (exact + semantic) | ✅ `sovereign-completion-cache` | ❌ absent | a repeated/paraphrased request costs $0 in serve; the daemon re-generates every time |
| **Token-budget refusal** | ✅ `sovereign-token-meter` (`can_spend_output` before generating) | ❌ only a per-request `max_tokens` clamp (1..4096), no cumulative meter | |
| **Blocking toxicity** | ✅ `--screen` can refuse | ⚠️ flag-only by design (never censors) | gatewayd's is a deliberate choice, not a gap |
| Complexity tier | ✅ `sovereign-complexity::estimate(prompt)` | ⟳ **superseded** — gatewayd's `sovereign-router-7axis` has complexity as 1 of 7 routing axes (a superset), driving hardware-role routing via the learning `Cortex` | not a real gap |
| pii / secret / injection / toxicity-scoring | ⚠️ opt-in binary flags only | ✅ default-on in `generate_chat` | daemon is *ahead* here |

## The critical feasibility fact

**`sovereign-serve` cannot "be" the daemon.** It has **no network interface at all** — no HTTP/TCP/axum/hyper crate anywhere (grep: zero matches); `Server::serve(prompt, max_new, seed, count_fn, gen_fn)` is an in-process synchronous library function, driven by a CLI demo binary that prints to stdout and generates with a **toy sine-filler model**. gatewayd speaks real HTTP and both the Anthropic and OpenAI shapes, generates from real safetensors weights, and is the systemd-managed daemon (`sovereign-gatewayd.service`; no `sovereign-serve.service` exists). serve is **dead**: zero non-test consumers workspace-wide; gatewayd's own code comment calls it "dead in the parallel `sovereign-serve` orchestrator."

So "promote serve to be the daemon" (finding option 2) is **infeasible** — it would mean rebuilding the HTTP layer, the API shapes, the real-model generation, the routing brain, and the safety spine that gatewayd already has.

## Options

| # | Option | What it means | Verdict |
|---|---|---|---|
| **A** | **Fold serve's 2 real stages into gatewayd; retire serve** | Add `sovereign-completion-cache` + `sovereign-token-meter` to `generate_chat` via the same `GuardConfig`-as-struct-field pattern SDD-206 established (cache lookup right after the injection screen, before `resolve_model`; a `TokenMeter` field checked on cache-miss). Skip `sovereign-complexity` (router-7axis supersets it). Then retire `sovereign-serve` (delete, or park it in the island register with a trigger). | **Recommended** |
| B | Promote serve to be the daemon | Rebuild HTTP + API shapes + real-model generation + routing + safety in/around serve | **Rejected — infeasible** (serve has no network interface; toy model) |
| C | Keep both (status quo) | Two parallel orchestrators, one dead | **Rejected** — this *is* the drift the audit flags |
| D | Retire serve without folding | Delete serve; don't add cache/budget | Viable only if cache + budget are explicitly unwanted; loses two real cost-control capabilities |

## Recommendation — Option A

Fold the **two genuinely-missing capabilities** into the live daemon and retire the dead orchestrator:

1. **Completion cache** — `sovereign-completion-cache` as a `GatewayServer` field; an exact-key (`model, prompt, max_new`) lookup returns early on hit, a `put` after a successful generate. Biggest bang: repeated tool/agent calls stop re-paying full generation. (Semantic cache optional, second step.)
2. **Token-budget** — `sovereign-token-meter` as a field; refuse (honest 429-style) when a request would exceed a configured cumulative output budget, mirroring the `GuardConfig` env-resolution shape (`SOVEREIGN_GATEWAY_*`).
3. **Complexity** — do **not** port `sovereign-complexity`; gatewayd's router-7axis already carries complexity as a routing axis. (If a text-*derived* complexity is wanted for logging, that's a separate small enhancement, not a serve port.)
4. **Blocking toxicity** — leave gatewayd's flag-only default (it's a deliberate "never censor" posture); optionally add an opt-in `SOVEREIGN_GATEWAY_GUARD_BLOCK_TOXICITY` later, consistent with the existing `BLOCK_INJECTION` knob.
5. **Retire `sovereign-serve`** — after the fold, delete it, or move it to the island register (SDD-955) with the trigger "superseded by gatewayd cache+budget." One live serving path, not two.

**Why A over D:** the cache alone is a real cost win for the "local sovereign" premise (agent loops re-issue near-identical prompts constantly), and both stages drop into the established insertion point with no `generate_chat` restructuring — low risk, high value.

**Sequencing / coordination:** the fold edits `generate_chat` + the `GatewayServer` struct — the same surface the **Anthropic-Messages-API session and the compute-plane multi-model session actively touch**. So the implementation must be **sequenced with those sessions** (or taken by one of them), not landed blind. That is the main cost of Option A, and the reason this is a decision for the operator rather than an immediate PR.

## Open question (operator decision)

| Q | Question | Options |
|---|---|---|
| **Q-957-A** | Adopt **Option A** (fold completion-cache + token-budget into `generate_chat`, skip complexity, retire `sovereign-serve`)? | **A** (recommended) · D (retire serve, skip cache/budget) · defer (park until the parallel `generate_chat` work settles) |

Until answered, `sovereign-serve` stays as-is (it is inert — nothing runs it, so it is not a live risk), and F-2026-089 remains **open (scoped)** in the ledger.

## Safety invariants

This SDD is a **decision document only** — no code, no crate change, no route change, nothing wired. It changes no runtime behavior. `sovereign-serve` remains dead-but-present exactly as today. R10212/SB-077 untouched. MS003 `unsigned-pending-MS003`.

## Cross-references

- `crates/sovereign-serve/src/lib.rs` — `Server::serve` (the real cache→complexity→budget pipeline)
- `crates/sovereign-gatewayd/src/lib.rs` — `generate_chat` + `GuardConfig` (the SDD-206 insertion-point pattern the fold would reuse)
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-089 (source); F-2026-081/086 (the work this decision gates)
- SDD-206 — the gateway safety spine (already moved serve's *safety* filters into the daemon)
- SDD-955 — the island register (where `sovereign-serve` would land if retired-not-deleted)
- SDD-100 — the per-session number-band convention (this SDD is in the phase-1-audit 950–999 sub-band)
