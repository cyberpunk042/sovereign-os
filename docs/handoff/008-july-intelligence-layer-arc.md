# Handoff 008 — the July 11–12 intelligence-layer arc (Brain · CoAT · Jobs · Plan-mode · Anthropic API · durable Cortex)

> **Read this first if you are starting a new session on sovereign-os.**
> **Status**: shipped + merged to `main`; the arc is live. Follow-up hardening is open (see "What's still open").
> **Last updated**: 2026-07-13
> **Owner**: sovereign-os core
> **Predecessor handoff**: [007-cockpit-functional-execution-arc.md](007-cockpit-functional-execution-arc.md)
> **Closes audit findings**: F-2026-060 (CRIT — no state surface knew this arc) + F-2026-036 (HIGH — no handoff existed). Signposted by SDD-983.

## What this arc was

Between 2026-07-11 and 2026-07-12 (a ~15-commit arc, documented at the time only
in the three standing-directives + CHANGELOG) sovereign-os grew an **intelligence
layer** on top of the local model runtime: the box can now reason with structured
deliberation, run background deliberation jobs, drive external agents (VS Code /
Claude Code) against its own local model via the Anthropic Messages API, and keep
durable memory across restarts. This handoff is the cold-start anchor the audit
found missing (the largest recent arc had no signpost in context.md / SHIPPED /
decisions / handoffs / mdbook).

## What got built (shipped, on `main`)

| Piece | Where | What it is |
|---|---|---|
| **Sovereign Brain observatory** | `scripts/operator/brain-api.py` (:8141, loopback) + the cockpit brain panel | Read-only observatory over the runtime's cognitive state; all webapp fetches map to real routes (`brain-api.py:319-371`). |
| **CoAT reasoning engine** | `crates/sovereign-coat` (1262 LOC, 14 tests) | ONE real MCTS parameterized into CoT / ToT / MCTS / C-MCTS / CoAT presets; model-gated via `ThoughtSource` + `AssociativeMemory` traits; honesty-enforced (`thought_source: heuristic\|model` in every trace). Wired live into `POST /v1/coat`, recalling from the daemon's real Cortex memory. |
| **Background-jobs runtime** | `scripts/operator/jobs_store.py` + `jobs-api.py` (:8142, loopback) | Durable atomic JSON registry (`/var/lib/sovereign-os/jobs/registry.json`, temp+rename), thread pool, per-job cancel events, orphan-resume on startup. Hosts the `/v1/coat` deliberation runner. |
| **Anthropic Messages API** | `crates/sovereign-gatewayd/src/http.rs` — `POST /v1/messages`, `GET /v1/models`, `POST /v1/messages/count_tokens` (SDD-205) | Lets the box drive VS Code / Claude Code against its own local model. `stream:true` → SSE. |
| **Plan Mode / User Approval / auto-mode safety classifier** | gatewayd + `scripts/operator/` | Structured planning + approval gating for mutating actions; the classifier flags destructive intent (SDD-954 reframed its over-claim — see F-2026-061 for the residual). |
| **QCFA + interactive AUQ clarification** | gatewayd | Ask-until-unambiguous clarification loop before acting on underspecified requests. |
| **HF-BPE tokenizer** | inference crates | Real Hugging-Face BPE tokenization (replaces the earlier ad-hoc path). |
| **Durable gateway (Cortex) memory** | `crates/sovereign-gatewayd` | Memory survives restarts; corruption-recovery + bounded growth added by SDD-951 (F-2026-084). |

**Verified-good properties to preserve** (F-2026-067): brain/code-console webapp
fetches all map to real routes; the jobs registry is durable (atomic temp+rename,
orphan-resume); ports are clean + env-overridable (brain **8141**, jobs **8142**,
gateway **8787**, all loopback-forced); units auto-install via the service glob
(R171-hardened); CoAT traces honestly flag `thought_source`.

## The runtime API surface

`crates/sovereign-gatewayd/src/http.rs` exposes the gateway HTTP API on
**:8787** (loopback). Full per-route reference:
[`../src/gateway-api-reference.md`](../src/gateway-api-reference.md) (SDD-983,
F-2026-064). The deliberation ladder in one line: `/v1/infer` (raw routing
decision) → `/v1/simple` (axes+quality) → `/v1/explain` / `/v1/simple-explain`
(read-only dry-runs) → `/v1/deliberate` (best-of-N) → `/v1/coat` (the CoAT ladder,
the deepest), with `/v1/messages` as the Anthropic-compatible surface.

## Current state

- The arc is **merged and live**; `context.md` "Current state" + "Recent arcs"
  reference it, and the mdbook now carries the SDD catalog (SDD-958) + this API
  reference.
- The **Phase-1 audit** (`docs/review/phase-1/99-findings-ledger.md`) reviewed the
  arc in passes E/F/G and filed the follow-ups below.

## What's still open (the arc's follow-up findings)

These are the honest gaps the audit filed against the arc — the next work on it:

| Finding | Sev | Gap |
|---|---|---|
| **F-2026-034** | CRIT | MS003 commit-authority signing — every SDD ships `unsigned-pending-MS003`; the cross-cutting gate. Operator-gated. |
| **F-2026-083** | HIGH | Generation is globally serialized behind one mutex. |
| **F-2026-063** | MED | Model-backed `/v1/coat` runs synchronously on the gateway request thread (holds the generation mutex). Route it through the jobs runtime. |
| **F-2026-061** | MED | Auto-mode classifier over-claims "auto-blocks destructive" (SDD-954 reframed; residual remains). |
| **F-2026-062** | MED | jobs-api generic runner vs the systemd `ReadWritePaths` sandbox will fail for `eval`/`model-load`/`gpu-job` kinds. |
| **F-2026-087** | MED | SSE robustness gaps. |
| **F-2026-065/066** | LOW | Daemon-path `.expect()` invariants; cross-daemon integration untested. |
| **F-2026-090** | OPP | CoAT is the most mature new piece — protect + extend (model-backed integration test; route through jobs so deliberation never blocks the request path). |
| **F-2026-091** | OPP | Jobs runtime is real + mature — grow it (per-kind ReadWritePaths, work checkpointing, resource caps). |

## What to do next (recommended order)

1. **Operator decision on F-2026-034 (MS003 signing)** — it gates the "shipped"
   status of everything; nothing is truly done until mutation surfaces are signed.
2. **F-2026-063 + F-2026-090** together — route model-backed CoAT through the
   background-jobs runtime so deliberation never holds the generation mutex, and
   add the model-backed CoAT integration test. This is the highest-leverage
   robustness fix and it composes two mature pieces already on `main`.
3. **F-2026-062** — per-kind `ReadWritePaths` for the jobs sandbox before more
   job kinds land.

> Note on session lanes (SDD-100/980/981): the gatewayd/CoAT/jobs work above lives
> in the **core runtime** lane — coordinate via the message board
> (`scripts/git/session_comms.py`) before editing `crates/sovereign-gatewayd` or
> `scripts/operator/*-api.py` so parallel sessions don't collide.

## Cross-references

- `docs/review/phase-1/99-findings-ledger.md` — findings F-2026-060/061/062/063/065/066/067/083/087/090/091
- `docs/src/gateway-api-reference.md` — the `/v1` API reference (SDD-983)
- `crates/sovereign-coat/` — the CoAT engine · `scripts/operator/jobs_store.py` — the jobs runtime
- `docs/sdd/205-*` (Anthropic Messages API) · SDD-951 (durable memory) · SDD-954 (classifier reframe)
- `docs/standing-directives/` — the 2026-07-11 / 2026-07-12 directives that were the arc's only prior record
- Predecessor: `007-cockpit-functional-execution-arc.md`
