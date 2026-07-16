# SDD-600 — Cockpit hotswap controls (frontend · provider/origin · AVX modes)

> Status: **draft — design-lock, awaiting operator approval before build**
> Owner: operator-supervised; agent-authored
> Last updated: 2026-07-16
> Number band: **cockpit-hotswaps 600–699** (per SDD-100 per-session banding). First SDD in the band.
> Closes findings: E11.M600 (mandate decomposition — cockpit-hotswaps band)
> Derived from: operator directive 2026-07-16 (verbatim below). Builds ON SDD-704 (frontend selector), SDD-707 (agent-runtime backend hotswap), SDD-045 (control-systems registry / exec-rail), SDD-067 (app-shell settings pane), and the AVX++ milestone family M002 / M007 / M008 / M039 / M061.

## Operator directive (verbatim — sacrosanct)

> "In the cockpit there is a common header, it should have the hotswap flags, like the with-GUI and non-GUI vs Open Computer if relevant and then in the CLI interface we say the command to turn back on the GUI / Gnome after a login.
>
> There should also be one for the provider / origin for the anthropic API endpoints config, like hotswapping from the official servers to local and vice versa. *OpenClaw, Claude Code, VSCode, Open Computer. all respectively and it should open a model if you want to edit one individually, like only Open Computer local or it being official claude for example. if it even support it, otherwise its OpenAI and we will need to develop another API enpoint and adapt what I just said to support other type of hotswap.
>
> Both can be in the settings pane that is at the top most right.
>
> [...] is thre a mode in the crate or somewhere where we use the AVX bits ? where we make sure to have room for using the bits for various reason in order to achieve a bunch of features [...] maybe its not compatible with every mode so maybe we need a hotswap for this tool, Custom-AVX vs BuiltIn-Features-AVX vs Hybrid-AVX ? I remember using the bits for various purpose but I can't find it back and the whole why and why its superpower. If there is more mode you put them all in a select."

Earlier design-lock answers (operator, same session): **lock design first (SDD, approve, then build)**; AVX surface = **functional Custom/BuiltIn/Hybrid swap**; provider swap = **all four consumers**.

## Mission

Give the cockpit's top-right **settings pane** three operator hotswaps that today have CLI machinery (or a full spec) but **no cockpit surface**:

1. **Frontend / GUI mode** — with-GUI (GNOME) · kiosk dashboards · Open-Computer kiosk · headless — plus the surfaced "restore GNOME after a console login" command.
2. **Provider / origin** — per-consumer swap of each of **OpenClaw · Claude Code · VSCode · Open Computer** between its official cloud endpoint and the local gateway, with a **drill-in modal** to edit one consumer individually.
3. **AVX mode** — a `<select>` of every AVX execution mode (Custom / BuiltIn-Features / Hybrid / Off, plus the sub-mode inventory), surfacing the M002/M007/M008 "bits-for-various-purposes" bit-machine that has no panel today.

The three parts are **separate concerns** (operator kept them distinct) that share one surface — the settings pane. Each Part below is independently buildable and can split into its own PR (600 / 601 / 602) at build time.

## Grounded reality (research findings, 2026-07-16)

| Topic | CLI/spec today | Cockpit surface today | The gap |
|---|---|---|---|
| **Frontend** | `frontend.py` (SDD-704): `sovereign-osctl frontend {status,list,set}`; state `/etc/sovereign-os/frontend.active`; 4 values | none — `control-systems.yaml` has **no `frontend` entry** | no exec-rail control; no pane row; "restore GNOME" needs `systemctl isolate graphical.target` note (undocumented) |
| **Provider** | `agent-backend.py` (SDD-707): swap wired for **OpenClaw + open-computer only** | none — no `provider`/`backend` control in registry; sudoers allowlist lacks the verbs | Claude Code + VSCode renderers **don't exist**; no pane; no controls; no sudoers lines |
| **AVX** | M002 `sovereign-control-word` (u64), M007 `sovereign-branch-tree` (scalar), M008 bit-cheats (spec-only, 13 toggle modes), M061 canon | **none for the custom bit-machine.** `cpu-features` panel surfaces only the *BuiltIn hardware* AVX (VNNI/BF16/AVX-512 detection) | the Custom-AVX policy-becomes-bits machine is invisible; kernels are u64/scalar/spec |

### The gateway is genuinely dual-protocol (enables all four consumers going local)
`sovereign-gatewayd` on `127.0.0.1:8787` serves **both** `/v1/messages` (Anthropic Messages, SDD-205) **and** `/v1/chat/completions` (OpenAI shim, SDD-062/103), with two-way translation. So every consumer can point local; the split is which protocol each speaks (below).

### The header settings pane is deliberately pure-static chrome
Per SDD-067 + R10212: the app-shell chrome navigates/explains and **does not mutate server state** — the ONLY sanctioned POST in the whole shell is the Assistant "Ask" footer. Every control in the cockpit today follows the registry doctrine (control-systems.yaml §"the web surface NEVER mutates privileged state … every control copies the exact `change_cli`"). Panels (not the shell) may mount `SovereignControlSurface` and execute via the exec-rail — the warp panel (SDD-300) is the precedent.

---

## Part 1 — Frontend / GUI hotswap

### 1.1 The control (NEW registry entry)
`config/control-systems.yaml` gains `frontend`:
```yaml
- id: frontend
  kind: mode
  scope: global
  label: "Frontend / GUI"
  description: >-
    Boot frontend — GNOME desktop (with-GUI), dashboards kiosk,
    Open-Computer kiosk, or headless (non-GUI). Restore GUI after a
    console login with the copied command.
  options: [gnome, dashboards-kiosk, open-computer-kiosk, none]
  options_cli: "sovereign-osctl frontend list"
  state_cli:   "sovereign-osctl frontend status --json"
  change_cli:  "sovereign-osctl frontend set <mode>"
  state_path:  "/etc/sovereign-os/frontend.active"
  privileged: true
  applies_to: [runtime-modes, settings-pane]
  refs: [scripts/operator/frontend.py, docs/sdd/704-frontend-selector.md]
```

### 1.2 The settings-pane row (NEW)
A third `.so-set-row` in `#so-settings-pane` (beside DEMO + course):
- Reads current mode from `sovereign-osctl frontend status --json` (rendered as a badge — `with-GUI` / `kiosk` / `headless`).
- A native `<select>` of the four modes + an **Apply** button that EXECUTES `frontend set <mode>` through the control-exec-api (`/api/control/execute`) — dry-run until the box is live; privileged → Confirm. (Operator directive: a hotswap that swaps, not a copied command.)
- A `.so-set-sub` "restore after console login" line that DISPLAYS the **two-step** recovery command as selectable text (this case has no GUI to click — the operator reads it at the tty):
  ```
  sudo sovereign-osctl frontend set gnome && sudo systemctl isolate graphical.target
  ```
  (`set gnome` sets `graphical.target` as default + enables gdm3; `isolate` brings the desktop up **in the current session** — the missing piece today.)

### 1.3 CLI parity note surfaced
The pane's help text names the exact restore command so an operator who logged into a console/tty can read it off the cockpit (or off the printed help) and get back to GNOME.

---

## Part 2 — Provider / origin hotswap (four consumers)

### 2.1 Per-consumer protocol map (grounded)
| Consumer | Protocol | Local endpoint | Cloud endpoint | Config the swap writes | Wired today? |
|---|---|---|---|---|---|
| **OpenClaw** | Anthropic | `http://127.0.0.1:8787` | `https://api.anthropic.com` | `openclaw.json` `primary` local↔anthropic | ✅ SDD-707 |
| **Open Computer** | OpenAI shim | `http://127.0.0.1:8787/v1` | `https://api.anthropic.com/v1/` (Anthropic OpenAI-compat) | `open-computer.env` `OPENAI_BASE_URL` | ✅ SDD-707 |
| **Claude Code** | Anthropic | `http://127.0.0.1:8787` | `https://api.anthropic.com` | `ANTHROPIC_BASE_URL` env / `~/.claude/settings.json` | ❌ **NEW renderer** |
| **VSCode** (Cline / Claude Dev) | Anthropic | `http://127.0.0.1:8787` | provider default | extension settings (`cline`/`claude-dev`) | ❌ **NEW renderer** |

### 2.2 Two new renderers in `agent-backend.py` (extend SDD-707)
Extend `RUNTIMES = ("openclaw", "open-computer")` → add `"claude-code"`, `"vscode"`:
- `render_claude_code(backend)` — local: write `ANTHROPIC_BASE_URL=http://127.0.0.1:8787` (+ `ANTHROPIC_API_KEY=sovereign-local`) into a managed env file / `~/.claude/settings.json`; anthropic: unset base URL (cloud default) + use the shared `/etc/sovereign-os/anthropic-key.env`.
- `render_vscode(backend)` — target the Anthropic-protocol Cline / Claude Dev extension settings (Base URL + key). Descriptor `/etc/sovereign-os/vscode-backends.json`.
- Each keeps the SDD-707 descriptor pattern (`{runtime}-backends.json`) + `show --json` so the modal reads current state.

### 2.3 Four controls + the drill-in modal
- `config/control-systems.yaml` gains four `kind: mode` controls (`openclaw-backend`, `open-computer-backend`, `claude-code-backend`, `vscode-backend`), each `options: [local, anthropic]`, `change_cli: "sovereign-osctl <runtime> backend <origin>"`, `state_cli: "sovereign-osctl <runtime> backend show --json"`, `privileged: true`, `applies_to: [settings-pane]`.
- Settings-pane **Provider** row → opens a modal listing the four consumers, each with its current origin badge + a local/official toggle. Editing one selects its origin + **Apply** EXECUTES `sovereign-osctl <consumer> backend <origin>` through the exec-rail (dry-run until live; privileged → Confirm). This is the "open a modal if you want to edit one individually" the operator asked for — a real swap, not a copied command.
- `config/sudoers.d/sovereign-os-cockpit` (via `operator-sudoers.sh`) gains `sovereign-osctl {openclaw|open-computer|claude-code|vscode} backend *`.

### 2.4 The OpenAI-only follow-on (operator-anticipated)
The operator noted: *"if it even support it, otherwise its OpenAI and we will need to develop another API enpoint."* Today the "anthropic" side for OpenAI consumers uses **Anthropic's OpenAI-compat endpoint**, not OpenAI proper (an explicit SDD-707 non-goal). A **true OpenAI cloud provider** (a consumer that can only speak OpenAI and wants a non-Anthropic origin) is scoped as **Part 2b / Stage-N**: a new provider descriptor `openai` + endpoint config, adapting the same modal to a third origin option. Flagged, not built in the first pass.

---

## Part 3 — AVX mode hotswap (the bit-machine)

### 3.1 What it is (found — the "bits for various purposes")
The operator's memory is exact and catalogued in the AVX++ milestone family (source: `~/infohub/raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md`, 18,341 lines):

- **M002 `sovereign-control-word`** — a packed per-branch bitfield ("injected logic"). Crate today: **u64** (opcode / precision / flags / operand). Spec wants 128/256/ZMM limbs (M002 E0018/E0019).
- **M007 `sovereign-branch-tree` + scheduler** — branch primitive; E0054 control word = route/task/risk/permissions/grammar/priority/spec_depth/flags; M00104 branch queries via AVX-512 masks. Crate today: **scalar HashMap**.
- **M008 bit-level cheats (the crown jewel)** — "using the bits for various purposes": bitfields-as-microcode, **64-bit inline LUT** (`decision = (rule_word >> condition) & 1`), **k-mask decision vectors**, **token-law bitset** (grammar/tool/safety/schema/route), VPCOMPRESS branch packing, "AVX-512 = accelerating *law*, not just math." Spec-only (no crate).
- **M061 AVX++ canon** — pins: profiles = **authority-gate** (not memory-lens), authority ladder L0..L6, trust rings 0..4, scheduler = per-profile policy layer. This is **why "not compatible with every mode"** — the custom bit-microcode is gated per profile/authority-level.

### 3.2 Why it's a superpower
"Policy becomes bits, reasoning becomes state transitions" (M008 M00105): instead of interpreting rules as branchy code per token, the rule is a bitmask and the decision is one AVX-512 op across many branches at once — token-by-token routing at hardware speed, with the remaining bits carrying profile + route (exactly the operator's "put it in 128/256 and use the remaining bits to add profile and accelerate token-by-token routing").

### 3.3 The Custom / BuiltIn / Hybrid distinction (the hotswap axis)
| Mode | Meaning | Repo anchor | Surfaced today? |
|---|---|---|---|
| **Custom-AVX** | our own bitfield-as-microcode (policy→bits) | M002 / M007 / M008 | **no** (the gap) |
| **BuiltIn-Features-AVX** | stock AVX-512 math accel | `sovereign-simd`/`vnni`/`bitops`, `cpu-dispatch`, `precision-profile` Tiers; M085/M086 | yes (`cpu-features` panel) |
| **Hybrid-AVX** | both | — | no |
| **Off / Scalar-baseline** | no AVX (portable fallback) | `cpu-dispatch::ScalarBaseline` | partial |

### 3.4 The `<select>` — every mode (per operator "put them all in a select")
The panel's master hotswap is a `<select>` with the four modes above. The panel additionally exposes the full mode inventory it gates:
- **Custom sub-modes (M008, 13 toggles)**: bitfields-as-microcode · VPTERNLOG fused-policy · k-mask routing · VPCOMPRESS pack-dense · token-law bitset · 64-bit inline LUT · two-level rule table · speculative+deterministic-commit · branch-prediction · bloom-sketch popcount · SIMD-FSM 8-branch · token-class mini-LUT · filter-cascade · three-representation · cheat-doctrine · CPU branch-ops.
- **BuiltIn dispatch paths (`cpu-dispatch`)**: ScalarBaseline · Avx2 · Avx512Generic · Zen5Avx512.
- **BuiltIn tiers (`precision-profile`)**: T1 quant/dot · T2 bitwise/attn · T3 structure/KV.

### 3.5 The control + panel (functional swap, honest degrade)
- **Control** `avx-mode` in `config/control-systems.yaml`, `kind: mode`, `options: [custom, builtin, hybrid, off]`, `change_cli: "sovereign-osctl avx-mode set <mode>"`, `state_cli: "sovereign-osctl avx-mode show --json"`, `privileged: true`, `applies_to: [cpu-features, settings-pane]`. The swap flips the M008 profile-knob family (`bitfields_microcode_enabled` etc. / `SOVEREIGN_BITFIELDS_MICROCODE_ENABLED`) — the toggle infra is already specced (M008 F00596–F00600). The **switch is real**; what it gates is scaffold until the ZMM kernels land.
- **NEW backing script** `scripts/hardware/avx-mode.py` (stdlib-only) — `list`/`show`/`set`, persisting to `/etc/sovereign-os/avx-mode.active`, degrading exit-0 with an honest banner where a mode's kernel is not yet built (warp/science-panel doctrine).
- **NEW panel** `webapp/avx-modes/index.html` — the master `<select>`, the full mode inventory (3.4), a "why it's a superpower" explainer (3.2) with the M002/M007/M008 + M061 citations, and the shared control-surface inlined (SDD-045). Degrades honestly on a box without the crates built.
- **Settings-pane row** — a `<select>` of every master mode + **Apply** that EXECUTES `avx-mode set <mode>` through the exec-rail (dry-run until live; privileged → Confirm).

### 3.6 Honesty ledger (do-not-minimize)
control-word is **u64** (not 128/256/ZMM); branch-tree is **scalar** (not the AVX-512 masked SoA scheduler); M008 bit-cheats have **no crate**. The panel therefore surfaces **spec + a real mode switch over scaffold**, and says so — it does not claim live ZMM kernels. Building those kernels is downstream (M002 E0018/E0019, M007 M00104, M008) and out of this SDD.

---

## Wiring (all three parts — build phase, after approval)
- `config/control-systems.yaml` — +6 controls (frontend, 4× *-backend, avx-mode). Registry lint `test_control_systems_registry.py` `EXPECTED_IDS` extended; every `applies_to` slug must exist (add `settings-pane` as a recognized surface).
- `config/sudoers.d/sovereign-os-cockpit` (via `operator-sudoers.sh`) — + frontend + 4 backend + avx-mode verbs; `test_cockpit_action_exec_sudoers.py` kept in lockstep (selfdef/perimeter still excluded — R10212).
- `webapp/_shared/app-shell-snippet.html` — +3 settings-pane rows (frontend / provider-modal / avx-mode) that EXECUTE via `/api/control/execute` (the exec-rail). `test_app_shell_contract` carves out that sanctioned loopback POST alongside the chat. Re-synced by `sync-app-shell.py`.
- `scripts/operator/agent-backend.py` — +2 renderers (claude-code, vscode).
- NEW: `scripts/hardware/avx-mode.py`, `webapp/avx-modes/index.html`, `systemd/system/sovereign-avx-modes-api.service` (if the panel needs a read API like warp), `config/dashboard-catalog.yaml` entry.
- Docs/man/course/demo/INDEX lockstep re-synced (the ~8 registries the warp panel exercised).

## Open questions / operator decisions

| Q | question | proposed | status |
|---|---|---|---|
| Q-600-A | Settings-pane behavior: copy-CLI only vs **live-exec-in-pane** (contract-lint carve-out) vs hybrid. | **answered — LIVE EXEC in the pane** (operator directive: *"I will not copy and paste any commands"* / *"DO WHAT I SAID"*). The hotswaps POST to the sanctioned control-exec-api (`/api/control/execute`), the same rail the panels use — dry-run until the box's live flag is set, privileged → Confirm. `test_app_shell_contract` carves out `/api/control/execute` alongside the chat fetch. | **answered 2026-07-16** |
| Q-600-B | Provider: which config for Claude Code (env vs `~/.claude/settings.json`) and which VSCode extension (Cline / Claude Dev vs Continue/Copilot). | CC = env + settings.json; VSCode = Cline/Claude Dev (Anthropic) | proposed — **needs operator** |
| Q-600-C | True-OpenAI cloud provider (Part 2b) — build now or Stage-N. | Stage-N (matches SDD-707 non-goal) | proposed — **needs operator** |
| Q-600-D | AVX: functional switch over scaffold now (this SDD) vs defer whole AVX to SDD-601. | functional switch now; kernels downstream | proposed (operator earlier chose "functional swap") |
| Q-600-E | One PR (SDD-600, three parts) vs three PRs (600 frontend / 601 provider / 602 AVX). | three PRs for separable review (operator kept the three separate) | proposed — **needs operator** |
| Q-600-F | Split this SDD file into 600/601/602 to mirror the PR split. | keep one design doc; split at build | proposed |
