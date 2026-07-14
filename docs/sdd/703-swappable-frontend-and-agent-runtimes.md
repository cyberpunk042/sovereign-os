# SDD-703 — swappable AI frontends + agent runtimes: GNOME / open-computer / OpenClaw, hotswappable (DESIGN)

> Status: draft (DESIGN / decision-package — no implementation in this SDD)
> Owner: operator-directed 2026-07-14 (*"how much had we customized Gnome … open-computer … hotswap … include OpenClaw in the options of the build … lets discuss"* → *"address everything sequentially … big round, big iteration"*); agent-authored.
> Addresses: **F-2026-113** (frontend not selectable/hotswappable), **F-2026-114** (no AI-sandbox frontend), **F-2026-115** (OpenClaw not a build option).
> Mandate module: **E11.M703**.
> Number band: **700–799 (phase-1 audit continuation — build-and-flash readiness)** per SDD-100.
> Stage: **design** — this scopes + designs the arc; implementation lands in subsequent SDDs (SDD-704+), one component per big round.

## The directive

> "how much had we customized Gnome? I see there is this [open-computer] interesting
> alternative that I might wanna be able to hotswap if possible? to integrate in the
> build and be able to chose at any point to start in one or another or even disable
> both, is that possible? … we also want to include OpenClaw in the options of the
> build and we can even add the preconfiguration options … address everything
> sequentially … do not minimize or compromise on quality … big round."

## Grounding research (done — do not re-derive)

### GNOME customization today = almost none
`scripts/install/install-gui-dashboards.sh` installs `gnome-core gdm3 firefox-esr xdg-utils`
(a lean GNOME), sets `graphical.target`, deploys the dashboard tree, and drops ONE launcher:
`share/applications/sovereign-dashboards.desktop` = `Exec=xdg-open http://127.0.0.1:8100/`
into the app menu + `/etc/skel/.config/autostart` + `/etc/skel/Desktop`. **No extensions, no
dconf, no theming, no kiosk.** So there is essentially nothing to unwind.

### open-computer (Mintplex anything-llm) = a QEMU AI-VM sandbox, NOT a desktop shell
Per its README: a **QEMU virtual machine** running a **Debian 13.5 guest** (XFCE + Chromium
pre-installed) with an HTTP/WebSocket service so an **AI agent can operate it**; a
browser-served UI. It **requires an external OpenAI-compatible LLM** ("any provider that
supports the OpenAI API can power Open Computer"). Base image `base.qcow2` ~2.9 GB + ~100 MB
per agent overlay; no GPU required. Pre-built QEMU binaries are shipped for macOS-ARM64 /
Windows-x64 only → on our Debian host we use **system `qemu-system-x86_64` + KVM**. **Correction
to the operator's initial framing**: it is not "GNOME vs open-computer as the desktop"; it is
an *AI-operated VM sandbox you run as a service*, whose web UI can be shown fullscreen (kiosk).
It aligns with sovereign-os's existing VFIO/`/mnt/vault` sandbox-perimeter ethos.

### OpenClaw = a Node gateway daemon, follows the selfdef installed-off shape
Peter Steinberger's OpenClaw (github.com/openclaw/openclaw, MIT; lineage Warelay→Moltbot→
OpenClaw; NOT Anthropic; the upstream OpenArms forks — same :18789 gateway). A **Node.js daemon**
(gateway port **18789**), `npm install -g openclaw@latest` + `openclaw onboard --install-daemon`,
Node **24.15+** (so NodeSource/nvm on Debian). Config `~/.openclaw/openclaw.json` (JSON5) +
`~/.openclaw/.env`. Points at a **local OpenAI-compatible endpoint** via a custom provider under
`models.providers` + an allowlist under `agents.defaults.models` (both required):
```json5
models: { mode: "merge", providers: { vllm: {
  baseUrl: "http://127.0.0.1:8000/v1", apiKey: "${VLLM_API_KEY}",
  api: "openai-completions", models: [{ id: "…", name: "Local vLLM", contextWindow: 128000 }] } } },
agents: { defaults: { models: { "vllm/*": {} } } }
```
A loopback/private baseUrl accepts a non-secret placeholder key. Runs as a systemd user service.

### The exact build seams (from the seam map — cite these when implementing)
- `install-gui-dashboards.sh:44-69` — the 3-way `SOVEREIGN_OS_DESKTOP=gnome|minimal|none` `case`;
  `:64` the ONLY `systemctl set-default graphical.target`; `:53/:56` the two apt package sets.
- `share/applications/sovereign-dashboards.desktop:11` — `xdg-open http://127.0.0.1:8100/`
  (plain browser hand-off; **no** `--kiosk`/`--app=`/fullscreen anywhere in the repo).
- `provision-bake.sh:201-215` §5b — `bake.gui` gate; `mkosi-emit.sh:59,420-447` translates
  `provisioning.bake.*` → `SOVEREIGN_OS_BAKE_*` env; **GAP: no `SOVEREIGN_OS_DESKTOP` passthrough
  and no profile field for desktop flavor** — `gnome|minimal|none` is env-only, unreachable from
  `profiles/*.yaml` on the image path.
- **selfdef is the reusable optional-component template** (`mkosi-emit.sh:375-410` posture-gated
  unit install + `sovereign-osctl` `cmd_selfdef()` `:1917-2015` full `status|install-units|on|off|
  start|stop|logs|sync|doctor` lifecycle). root-ghostproxy is the *weaker* template (build-time
  only, no CLI). **OpenClaw follows the selfdef shape.**
- The dashboard hub (`sovereign-dashboards.service` → `build-configurator-api.py`, **:8100**)
  already serves every `webapp/<panel>/index.html`; a kiosk browser at `http://127.0.0.1:8100/`
  gets exactly what the launcher opens — the reusable "web UI shown fullscreen" seed.
- No `frontend`/`gui`/`desktop` `sovereign-osctl` verb exists — clean new territory. (Beware the
  3-way "master-dashboard" name collision: panel vs `-api` :8090 vs the nginx generator :8000 —
  none is the :8100 hub.)
- Only `sain-01.yaml` has a `provisioning:` block; the root-reflash path
  (`install-sovereign-root.sh`, `INSTALL_GUI=1` default) is the profile-agnostic seam.

## The unifying insight

All three "frontends" are **installed-off components that consume our local OpenAI endpoint**
(the vLLM Oracle tier / gateway from SDD-702). So this arc is two orthogonal axes:

1. **The presentation axis** — *what the box shows at boot / on the display*: a **frontend
   selector** with values `gnome` · `open-computer` (kiosk to the sandbox UI) · `dashboards`
   (kiosk to the :8100 hub) · `none` (headless). Build-time default + runtime-switchable.
2. **The service axis** — *which AI runtimes are installed + on*: `open-computer` (QEMU sandbox
   service) and `openclaw` (gateway daemon), each a posture-gated `bake.*` toggle with a
   `sovereign-osctl <name> {status,install-units,on,off,…}` lifecycle (selfdef shape).

The selector picks a *presentation*; the services can be on regardless of what's presented
(e.g. OpenClaw running headless while GNOME is shown; open-computer's VM running while the box
kiosks its UI). This cleanly answers "one or the other or both or disable both."

## Design — component by component

### A. Frontend selector (fills the profile-flavor gap + adds the runtime switch)

**Build-time**: add `provisioning.frontend` to the profile + schema, and plumb it through
`mkosi-emit.sh` into a new `SOVEREIGN_OS_FRONTEND` env the install script reads:
```yaml
provisioning:
  frontend:
    default: gnome            # gnome | dashboards-kiosk | open-computer-kiosk | none
    install: [gnome]          # which frontends to bake in (so a later switch can pick among them)
```
`install-gui-dashboards.sh`'s `case` extends from `gnome|minimal|none` to also handle the kiosk
values (a kiosk = `cage` or `gnome-kiosk` compositor + a getty-autologin unit launching a
fullscreen browser at a URL). `graphical.target` vs `multi-user.target` is set per the chosen
default.

**Runtime switch** — a NEW `sovereign-osctl frontend {status|set <value>|list}` verb:
- `set gnome` → ensure gdm3 enabled, `set-default graphical.target`, disable any kiosk unit.
- `set dashboards-kiosk` → enable a `sovereign-frontend-kiosk.service` (cage + fullscreen browser
  → `http://127.0.0.1:8100/`), `set-default graphical.target`.
- `set open-computer-kiosk` → kiosk browser → the open-computer web UI URL (requires the
  open-computer service on; the verb checks + hints).
- `set none` → `set-default multi-user.target`, disable kiosk + gdm.
- `status` → what's installed, what's default, what's active (selfdef-style verdict line).
This is the "choose at any point" the operator asked for — live, no reflash.

**New units**: `sovereign-frontend-kiosk.service` (parameterised by a `FRONTEND_KIOSK_URL` env
file), possibly a `sovereign-frontend-kiosk@.service` template so one unit serves both kiosk
targets. Full R171 sandbox where a browser+compositor allows it.

### B. open-computer (QEMU AI-sandbox service)

- `provisioning.bake.open_computer: true` (selfdef shape): stage the open-computer tree to
  `/opt/open-computer`, ensure **system QEMU/KVM** + Node, provision the `base.qcow2` (a
  first-boot download to `/mnt/vault/open-computer/` — same gated/resumable/non-fatal pattern as
  SDD-702's model pull, since it's ~2.9 GB), and **preconfigure its LLM backend to our endpoint**
  (the vLLM Oracle `:8000/v1` or the gateway). Posture: installed-off.
- `sovereign-osctl open-computer {status,install,on,off,url,…}` — start/stop the QEMU sandbox +
  its node service; `url` prints the web-UI address the kiosk/selector points at.
- The sandbox is a natural fit for the existing dual-GPU/VFIO perimeter — an explicit non-goal
  here is deciding whether it gets a GPU (default: CPU-only per its README; a later SDD can wire
  the VFIO 4090 into it).

### C. OpenClaw (Node gateway daemon)

- `provisioning.bake.openclaw: true` (selfdef shape): provision Node (NodeSource/nvm, pin ≥24.15),
  `npm install -g openclaw@latest`, drop a **preconfigured** `~/.openclaw/openclaw.json` +
  `~/.openclaw/.env` pointing `models.providers.vllm.baseUrl` at our OpenAI endpoint with a
  loopback placeholder key + the allowlist, and install a `sovereign-openclaw.service` (gateway
  on :18789). Posture: installed-off.
- `sovereign-osctl openclaw {status,install-units,on,off,logs,doctor}` mirroring `cmd_selfdef()`.
- Preconfiguration options (operator's ask): the profile can carry an
  `provisioning.openclaw:` block (which channels to enable, model id, bind) rendered into the
  config at provision time.

## Decisions the operator must steer (before implementation SDDs)

| # | Decision | Options | Recommendation |
|---|---|---|---|
| D1 | Default boot frontend on a fresh flash | `gnome` (today) · `dashboards-kiosk` · `open-computer-kiosk` · `none` | Keep `gnome` default; make the others opt-in — least surprise, everything still hotswappable. |
| D2 | open-computer integration depth | full kiosk-replacement session · installed service whose UI you open from GNOME · both | Both: install the service + a kiosk *option*; default to "open from GNOME/dashboards" (cheaper, still hotswap via the selector). |
| D3 | open-computer GPU | CPU-only (its default) · wire the VFIO 4090 sandbox GPU | CPU-only now; VFIO-GPU as a later SDD (it's real work + touches the perimeter). |
| D4 | OpenClaw lifecycle shape | selfdef (full osctl on/off + posture-gated) · ghostproxy (build-time only) | selfdef shape — you asked for build options + preconfig + runtime control. |
| D5 | OpenClaw channels preconfigured | none (operator adds) · a default set | Ship it configured for the LOCAL model + no external channels; operator adds WhatsApp/etc. later (avoids baking credentials). |
| D6 | Node provisioning mechanism | NodeSource apt · nvm/fnm per-user | NodeSource (system-wide, reproducible in the image) — matches the operator-deps posture. |

> **Provisional adoption (2026-07-14):** the operator gave the arc a green light
> (*"address everything sequentially … big round"*) but has NOT separately answered D1–D6.
> The implementation rounds proceed on the **recommendations above as provisional, fully
> overridable defaults** — the selector itself makes every one reversible (a profile field or a
> live `sovereign-osctl frontend set`), so shipping on them costs nothing and unblocks the
> "choose at any point" ask now. **D1 (default = gnome)** is adopted by SDD-704 (behaviour-
> preserving). **D2/D3** are deferred to SDD-706 (they don't affect the selector). **D4/D5/D6**
> are adopted by SDD-705 (OpenClaw). None is locked; the operator can revise any row and the
> corresponding profile field / bake toggle changes with it.

## Sequencing (the big rounds, in order)

1. **SDD-704** — the **frontend selector** (profile field + `mkosi-emit` plumbing + the
   `sovereign-osctl frontend` verb + the kiosk unit + `install-gui-dashboards.sh` `case`
   extension). This unblocks "choose at any point" for the frontends that already exist
   (gnome/dashboards/none) *before* the heavier VM/agent work.
2. **SDD-705** — **OpenClaw** bake option (Node provisioning + install + preconfig + unit +
   `sovereign-osctl openclaw` verb). Self-contained, no VM.
3. **SDD-706** — **open-computer** bake option (QEMU/KVM + base-image provisioning + LLM
   preconfig + service + `open-computer-kiosk` wired into the selector). Heaviest; last.

Each is its own big round + its own PR, with the full dossier + contract lints + verification
(full `tests/` + profile validation), consistent with the readiness arc.

## Non-goals (this design SDD)

- Any implementation (this is the design/decision stage — one commit, docs only).
- Wiring open-computer to a GPU (D3 — later).
- Baking external-channel credentials into OpenClaw (D5).
- Re-theming GNOME (it's intentionally near-stock).
- Replacing the dashboard hub / touching the "master-dashboard" naming collision (separate).

## Cross-references

- `scripts/install/install-gui-dashboards.sh` · `provision-bake.sh:201-215` · `mkosi-emit.sh:375-447` — the seams extended
- `sovereign-osctl` `cmd_selfdef()` `:1917-2015` — the lifecycle template
- `docs/sdd/702-inference-model-provisioning.md` — the OpenAI endpoint all three consume; the gated/resumable/non-fatal download pattern reused for base.qcow2
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-113/114/115 (scoped here, closed by SDD-704/705/706)
- open-computer: github.com/Mintplex-Labs/anything-llm/tree/master/open-computer
- OpenClaw: github.com/openclaw/openclaw (MIT; :18789 gateway; local-vLLM provider config)
