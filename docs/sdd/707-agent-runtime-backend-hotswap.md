# SDD-707 — agent-runtime backend hotswap: local model ↔ hosted Claude (IMPLEMENTATION)

> Status: draft (implementation — the preconfiguration + hotswap the operator asked for on the SDD-703 arc)
> Owner: operator-directed 2026-07-14 (verbatim): *"I already talked about preconfiguration, and there
> should be a hotswap for [the] anthropic local ai API vs the claude ai anthropic API for both. and it
> should be clear and easy how to swap this and the Desktop"*.
> Addresses: **F-2026-116** (runtimes pinned to raw vLLM, no local↔cloud hotswap) — CLOSED here.
> Corrects: SDD-705 / SDD-706 (they pointed the runtimes at the raw vLLM `:8000`, bypassing the gateway).
> Mandate module: **E11.M707**.
> Number band: **700–799 (phase-1 audit continuation)** per SDD-100.
> Stage: **implement**.

## What the double-check found

The operator asked to double-check the arc + add a **local-AI ↔ Claude/Anthropic hotswap** for both agent
runtimes. Reviewing *from the project* surfaced a real issue: the repo is **Anthropic-first**.
`sovereign-gatewayd --http` serves, on **`127.0.0.1:8787`**, an **Anthropic `/v1/messages`** API **and** an
OpenAI `/v1/chat/completions` shim — through the **SDD-206 safety spine** (auth + timeouts + injection/
secret/PII/toxicity). `sovereign-provider-catalog` already declares `CloudAnthropic`
(`https://api.anthropic.com`) alongside `LocalVllm`. But **SDD-705/706 preconfigured the runtimes at the raw
vLLM `:8000`** — bypassing the gateway and its safety spine, and with no way to reach hosted Claude. This SDD
**corrects the local endpoint to the `:8787` gateway** and **adds the hotswap**.

## Grounding (verified against each runtime's source)

- **OpenClaw** speaks Anthropic natively. Two providers coexist in `~/.openclaw/openclaw.json`: a `local`
  one (`api: "anthropic-messages"`, `baseUrl: http://127.0.0.1:8787`) and `anthropic`
  (`https://api.anthropic.com`, key from `ANTHROPIC_API_KEY`). The swap is purely
  `agents.defaults.model.primary` → `local/<model>` ↔ `anthropic/<model>`.
- **open-computer** is OpenAI-format only (`OPENAI_BASE_URL`/`OPENAI_MODEL`/`OPENAI_API_KEY`). The swap flips
  `OPENAI_BASE_URL` between the local gateway shim (`:8787/v1`) and **Anthropic's verified OpenAI-compat
  endpoint** `https://api.anthropic.com/v1/` (+ a real key + a Claude model id).
- **Keys**: the local side uses a non-secret placeholder; the **hosted Claude key is a real secret and is
  NEVER baked** — it lives in a root-only `/etc/sovereign-os/anthropic-key.env` the operator supplies, and
  both runtime units `EnvironmentFile` it.

## The design — clear + easy, parallel to the Desktop swap

```
sovereign-osctl openclaw       backend {local|anthropic|show} [--key K]
sovereign-osctl open-computer  backend {local|anthropic|show} [--key K]
sovereign-osctl frontend       set {gnome|dashboards-kiosk|open-computer-kiosk|none}   ← the Desktop (SDD-704)
```
`backend show` (and each `doctor`) reports the active backend + endpoint + whether the cloud key is present.
Swapping to `anthropic` without a key succeeds but warns (cloud calls 401 until `--key` is given).

## Components

1. **Profile + schema** — each of `provisioning.openclaw` / `provisioning.open_computer` gains
   `backend` (local|anthropic, default **local**), `anthropic_endpoint`, `anthropic_model`; the existing
   `endpoint` is **repointed to the `:8787` gateway** (Anthropic base for OpenClaw, `/v1` shim for
   open-computer). sain-01 sets `anthropic_model: claude-sonnet-4-6` (operator can set any current Claude).
2. **`scripts/operator/agent-backend.py`** — the single renderer + swap engine for both runtimes. `provision`
   (from the install hooks) persists a backend descriptor + renders the active config; `local`/`anthropic`
   flip it + `systemctl try-restart` the runtime; `show` reports; `--key` writes the root-only key file. It
   renders OpenClaw's two-provider `openclaw.json` and open-computer's `OPENAI_*` env. Dry-run seam
   (`SOVEREIGN_OS_BACKEND_DRYRUN`) for CI/rehearsal.
3. **Install hooks** — `openclaw-install.sh` + `open-computer-install.sh` now **delegate** config rendering to
   `agent-backend.py provision` (no more inline `:8000` config), passing the profile's local + anthropic
   params.
4. **osctl** — `cmd_openclaw` + `cmd_open_computer` gain a `backend)` sub-verb delegating to the engine; help
   + each `doctor` shows the active backend.
5. **Runtime units** — both `EnvironmentFile=-/etc/sovereign-os/anthropic-key.env` so the cloud key is
   injected when present (harmless when absent / backend=local).

## Verification

- `tests/lint/test_agent_backend_hotswap_contract.py` — **10 cases**: schema/profile (local = `:8787`, not
  `:8000`) · engine shape + no-baked-key · hooks delegate + drop `:8000` · osctl verbs · units EnvironmentFile
  the key · **behaviour** (OpenClaw primary flips local↔anthropic; open-computer `OPENAI_BASE_URL` flips +
  key injected only via `--key`; anthropic-without-key warns).
- SDD-705/706 contract lints updated to pin the new delegation (config-shape coverage moved to the SDD-707
  lint) — additive, not dropped.
- Full `tests/` + all 5 profiles + ruff + `bash -n` green.
- **NOT verified on hardware / live**: two upstream-behaviour items flagged by the source research —
  OpenClaw's exact `/v1` path-append for a *local* `anthropic-messages` `baseUrl` (host-root vs `/v1`), and
  Pi/open-computer's tolerance of Anthropic's OpenAI-compat limitations (system-message hoisting, no prompt
  caching, `temperature`≤1). Both are one-request smoke-tests on the box; the swap *mechanism* is correct.

## Non-goals

- Changing the gateway itself (it already serves both surfaces through the safety spine — SDD-206).
- Baking any Claude API key (operator-supplied at runtime).
- A GUI backend toggle (the CLI is the clear/easy surface, matching `frontend set`).
- Cloud providers other than Anthropic (OpenAI/Google are in the provider-catalog but out of scope here).

## Cross-references

- `docs/sdd/703-swappable-frontend-and-agent-runtimes.md` — the arc; `704` (Desktop swap) · `705`/`706`
  (the runtimes this repoints).
- `docs/sdd/206-gateway-safety-spine.md` — the `:8787` gateway + spine the local backend now routes through.
- `crates/sovereign-gatewayd/src/main.rs` (`/v1/messages` + `/v1/chat/completions`) ·
  `crates/sovereign-provider-catalog` (CloudAnthropic / LocalVllm).
- `scripts/operator/agent-backend.py` · the two install hooks · `sovereign-osctl` `cmd_openclaw` /
  `cmd_open_computer` · the two runtime units.
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-116 (closed here).
