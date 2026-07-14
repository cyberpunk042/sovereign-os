# SDD-705 — OpenClaw agent runtime: Node gateway daemon, preconfigured to the local model (IMPLEMENTATION)

> Status: draft (implementation — second big round of the SDD-703 frontend+runtimes arc)
> Owner: operator-directed 2026-07-14 (*"we also want to include OpenClaw in the options of the
> build and we can even add the preconfiguration options"* → *"continue, we need to make this
> ready"*); agent-authored.
> Addresses: **F-2026-115** (OpenClaw not a build option) — CLOSED here.
> Design parent: **SDD-703** (the arc's design + decision package — the *service axis*).
> Mandate module: **E11.M705**.
> Number band: **700–799 (phase-1 audit continuation — build-and-flash readiness)** per SDD-100.
> Stage: **implement**.

## What this delivers

OpenClaw — Peter Steinberger's Node gateway daemon (npm `openclaw`, MIT; lineage
Warelay→Moltbot→OpenClaw; **not** Anthropic; OpenArms is a downstream fork sharing the :18789
gateway) — is now a **build option** that ships **installed-off** and **preconfigured to the local
vLLM endpoint** (SDD-702). Flip `provisioning.bake.openclaw`, and a flashed box gets OpenClaw
provisioned at first boot, pointed at the on-box sovereign model, ready to start with
`sovereign-osctl openclaw on`.

This is the **selfdef installed-off shape** (SDD-703 D4): staged at build, provisioned at first
boot, started only by the operator.

## Grounding (verified against primary sources — npm registry + repo docs)

- npm `openclaw`, `bin: openclaw`; install `npm install -g openclaw@latest`.
- Node **engines are banded**: `>=22.22.3 <23 || >=24.15 <25 || >=25.9` — 23.x, 24.0–24.14, 25.0–25.8 are **excluded**. The profile pins NodeSource **24** (satisfies the recommended `>=24.15 <25`); the hook verifies the running node against the band and installs NodeSource only if needed.
- Gateway on **:18789**; runs foreground via `openclaw gateway` (reads bind/port from config) — so systemd is the supervisor, not OpenClaw's own user-daemon installer.
- Config `~/.openclaw/openclaw.json` (**JSON5** despite `.json`), **hot-reloaded** — a config drop-in is a supported headless path (no interactive onboard required).
- Local vLLM provider: `api: "openai-completions"` (the vLLM default), `baseUrl`, `${ENV}`-interpolated `apiKey`; a loopback baseUrl **accepts a non-secret placeholder key**; `agents.defaults.models: { "vllm/*": {} }` is an allowlist that triggers `/v1/models` **auto-discovery** — so the config doesn't need to hardcode the exact served id.

## The build seams (as implemented)

1. **Schema + profile** — `provisioning.bake.openclaw: bool` + a `provisioning.openclaw` block
   (`endpoint`, `model_id`, `gateway_port`, `node_major`). sain-01 opts in and points at
   `http://127.0.0.1:8000/v1` (the local vLLM router/Oracle), port 18789, node 24. No external
   channels (SDD-703 D5 — never bake credentials).
2. **mkosi-emit** — parses `bake.openclaw` → emits `SOVEREIGN_OS_BAKE_OPENCLAW`.
3. **provision-bake §4b** — when baked, stages the two units and enables **only** the first-boot
   installer. The runtime daemon stays installed-off. (No install at postinst: NodeSource + the
   npm registry are unreachable during the image build — the install must be first-boot.)
4. **First-boot hook** — `scripts/hooks/post-install/openclaw-install.sh`
   (`sovereign-openclaw-install.service`, `ConditionFirstBoot=yes`, **VM-tolerant** — a Node daemon
   runs on VMs, unlike the GPU hooks): ensures a band-satisfying Node (NodeSource if needed),
   `npm install -g openclaw@latest`, renders `~/.openclaw/openclaw.json` + `/etc/sovereign-os/openclaw.env`
   pointed at the local endpoint, stages the runtime unit installed-off. **Non-fatal + resumable**
   throughout (no network / no npm / a too-old Node each skip cleanly; re-run with
   `sovereign-osctl openclaw install`); idempotent.
5. **Runtime daemon** — `sovereign-openclaw.service` runs `openclaw gateway` as the operator with
   **`HOME` relocated to `/var/lib/sovereign-os/openclaw`** (set in the env file). That keeps
   OpenClaw's `~/.openclaw` config/state under a writable tree **outside `/home`**, so the daemon
   holds `ProtectHome=read-only` + `ProtectSystem=strict` + a narrow `ReadWritePaths` — fully R171
   + long-running hardened, **no waiver**.
6. **CLI** — `sovereign-osctl openclaw {status|on|off|start|stop|restart|logs|install|install-units|doctor}`
   (`cmd_openclaw`, selfdef shape): the sovereign management surface. `status`/`doctor` are read-only;
   `on`/`install` need root.

## Verification

- `tests/lint/test_openclaw_provision_contract.py` — **10 cases**: schema → profile (local
  endpoint, port, node band) → mkosi-emit → provision-bake (installer-only enable, runtime
  never enabled) → hook (local endpoint, `openai-completions`, non-fatal skips, engines-band
  check, **no external channels**) → both units (first-boot VM-tolerant installer; installed-off
  hardened runtime) → the osctl verb.
- systemd fleet lints green with both new units (hardening / posture / per-unit coverage /
  install-coverage README 120→122 / 100→102 service); `openclaw` verb `cli_only` waiver.
- `bash -n` clean on the hook + osctl; profile validates; ruff clean.
- **NOT verified on hardware**: the real Node/npm install + `openclaw gateway` boot + a live
  agent turn against vLLM — no network/registry/GPU in CI. Two load-bearing assumptions the
  operator should confirm on the box: (a) OpenClaw honours `$HOME` for its config dir (high
  confidence — it computes `~/.openclaw` from the home dir); (b) a pure config-drop-in daemon boot
  needs no one-time pairing token (the docs present `onboard --non-interactive` as the headless
  path; if a token is required it's a one-time operator step). Both are documented; the daemon
  ships **off**, so nothing runs until the operator turns it on.

## Non-goals (this round)

- The **open-computer** QEMU AI-sandbox service (the arc's remaining round — heaviest).
- Baking any external messaging channel or its credentials (SDD-703 D5).
- Replacing OpenClaw's Control UI (:18789) with a sovereign panel (it ships its own).
- Wiring OpenClaw into the frontend selector as a kiosk target (it's a headless service; the
  operator opens its Control UI from GNOME or over loopback).

## Cross-references

- `docs/sdd/703-swappable-frontend-and-agent-runtimes.md` §C — the OpenClaw design + D4/D5/D6.
- `docs/sdd/704-frontend-selector.md` — the sibling (presentation-axis) round.
- `docs/sdd/702-inference-model-provisioning.md` — the local vLLM endpoint OpenClaw consumes.
- `scripts/hooks/post-install/openclaw-install.sh` · `systemd/system/sovereign-openclaw*.service` ·
  `scripts/sovereign-osctl` `cmd_openclaw` — the new components.
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-115 (closed here).
- OpenClaw: github.com/openclaw/openclaw (MIT; :18789 gateway; vLLM provider `openai-completions`).
