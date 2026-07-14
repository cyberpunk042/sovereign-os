# SDD-706 — open-computer: a QEMU AI-sandbox service, preconfigured to the local model (IMPLEMENTATION)

> Status: draft (implementation — third + final round of the SDD-703 frontend+runtimes arc)
> Owner: operator-directed 2026-07-14 (*"I see there is this [open-computer] interesting
> alternative that I might wanna be able to hotswap … integrate in the build"* → *"continue, we
> need to make this ready"*); agent-authored.
> Addresses: **F-2026-114** (no AI-operated sandbox frontend) — CLOSED here.
> Design parent: **SDD-703** (§B — the service axis). Sibling rounds: **SDD-704** (selector), **SDD-705** (OpenClaw).
> Mandate module: **E11.M706**.
> Number band: **700–799 (phase-1 audit continuation — build-and-flash readiness)** per SDD-100.
> Stage: **implement**.

## What this delivers

**open-computer** (Mintplex-Labs, in the `anything-llm` repo; **AGPL-3.0**) — a QEMU virtual machine
(Debian 13.5 guest + XFCE + Chromium) that an AI agent lives in and drives, with a live
human-in-the-loop web UI — is now a **build option** that ships **installed-off** and
**preconfigured to the local vLLM endpoint** (SDD-702). Flip `provisioning.bake.open_computer`, and
a flashed box provisions it at first boot (QEMU/KVM + Node + a repo build + the base image), pointed
at the on-box sovereign model, ready to start with `sovereign-osctl open-computer on`. It's also the
third value the SDD-704 frontend selector already accepts — `open-computer-kiosk` — now wired to the
sandbox's real UI.

This is the arc's **heaviest** round and its **last** planned one.

## Grounding (verified against primary sources — the repo's own CLI/service code)

- **Not an npm package** — a git subdir (`open-computer/` in `Mintplex-Labs/anything-llm`, `master`).
  A TypeScript CLI (`@open-computer/cli`) you clone + build (`npm install && npm run build` →
  `cli/dist/open-computer`), driven via a `./open-computer` wrapper (`base install` / `create <name>` / `up <name>`).
- **QEMU/KVM required on Linux** — the CLI resolves `qemu-system-x86_64` from PATH (bundled QEMU is
  macOS/Windows only) and builds `-machine q35 -accel kvm -cpu host`, so **`/dev/kvm` is mandatory**
  for acceleration. Debian host needs `qemu-system-x86` + `qemu-utils` + `ovmf` (UEFI vars).
- **Base image** — a `base.qcow2` (+ `efi-vars.fd`) downloaded from
  `cdn.anythingllm.com/support/open-computer/base-images/06_08_2026/x64-base-image.tar` (~3 GB, sha256
  sidecar). Upstream's `fetch-base-image.sh` is **not resumable** — this SDD pulls the same asset with
  `curl -fL -C -` + sha256 verify so a dropped multi-GB download resumes. Per-agent overlays (~100 MB)
  are qcow2 deltas on the shared read-only base.
- **Web UI** — per-agent HTTP+WebSocket on **base port 9800** (agent 1 → `http://localhost:9800`).
  *(My initial :3000 assumption was wrong; corrected in the selector.)*
- **LLM backend = plain env** read by the interface-service: `OPENAI_BASE_URL`, `OPENAI_MODEL`,
  `OPENAI_API_KEY` (empty ok for keyless local). Crucially, open-computer **auto-rewrites a host
  `127.0.0.1`/`localhost` endpoint to `10.0.2.2`** (the QEMU user-net gateway) for the guest — so our
  host-local vLLM endpoint is reachable from inside the VM with no extra bridging.
- **Node** — no `engines` pin declared upstream; Node 20/22 LTS is the safe target (profile: 22).

## The build seams (as implemented)

1. **Schema + profile** — `provisioning.bake.open_computer: bool` + a `provisioning.open_computer`
   block (`endpoint`, `model_id`, `web_port`, `repo`, `base_image_url`, `node_major`). sain-01 opts in,
   endpoint `http://127.0.0.1:8000/v1`, web_port 9800, the Mintplex repo + the CDN base-image URL.
2. **mkosi-emit** — emits `SOVEREIGN_OS_BAKE_OPEN_COMPUTER`.
3. **provision-bake §4c** — when baked, stages the two units and enables **only** the first-boot
   installer (no install at postinst — QEMU/Node/registry/CDN are all unreachable in the image build).
4. **First-boot hook** — `scripts/hooks/post-install/open-computer-install.sh`
   (`sovereign-open-computer-install.service`, `ConditionFirstBoot`, VM-tolerant, `After=network-online`):
   installs QEMU/KVM + OVMF + Node, adds the operator to the `kvm` group, sparse-clones the
   `open-computer/` subdir + builds the CLI, downloads the base image (resumable + sha256), renders
   `/etc/sovereign-os/open-computer.env` (LLM env → the local endpoint), stages the runtime unit
   installed-off. **Non-fatal + resumable + idempotent** throughout.
5. **Runtime daemon** — `sovereign-open-computer.service` runs
   `scripts/operator/open-computer-run.sh` (creates the default agent overlay, then `open-computer up`)
   as the operator, **`/dev/kvm`-gated** (`ConditionPathExists=/dev/kvm`), `HOME` relocated to
   `/var/lib/sovereign-os/open-computer`. As a genuine **QEMU/KVM VM host** it carries a documented
   `# HARDENING-WAIVER:` (needs `/dev/kvm`; a hardened KVM host may need `RestrictNamespaces` relaxed
   for QEMU's user-net) **plus** every universally-safe clause (`ProtectSystem=strict`,
   `ProtectHome=read-only`, the 4 fleet clauses, narrow RWP).
6. **CLI** — `sovereign-osctl open-computer {status|on|off|start|stop|restart|logs|install|install-units|url|doctor}`
   (`cmd_open_computer`, selfdef shape); `url` prints `http://localhost:9800`, `doctor` checks
   qemu/kvm/node/base-image.
7. **Selector wiring** — `frontend.py`'s `open-computer-kiosk` value now points at the verified `:9800`
   (was a `:3000` guess); `sovereign-osctl frontend set open-computer-kiosk` kiosks to the sandbox UI.

## Verification

- `tests/lint/test_open_computer_provision_contract.py` — **11 cases**: schema → profile (local
  endpoint, :9800, Mintplex repo) → mkosi-emit → provision-bake (installer-only enable) → hook
  (QEMU install, **resumable** base pull + sha256, local-endpoint env, non-fatal skips, no channels)
  → both units (full-R171 installer; KVM-gated waived VM-host runtime) → the osctl verb → the
  frontend :9800 wiring.
- systemd fleet lints green with both new units (hardening / posture / per-unit coverage /
  install-coverage README 122→124 / 102→104 service); `open-computer` verb `cli_only` waiver; new
  metric documented.
- `bash -n` clean on the hook + launcher + osctl; profile validates; ruff clean.
- **NOT verified on hardware** (the arc's biggest unverified surface): the real QEMU/KVM install,
  the ~3 GB base-image download, the CLI build, and a booted sandbox VM with a live agent turn — no
  network / KVM / display in CI. Documented assumptions the operator confirms on the box: (a) the
  base-image CDN URL + sha256 layout is current (it's a dated asset — `06_08_2026`); (b) `open-computer up`
  stays foreground under systemd (else switch the unit to `Type=forking`); (c) the CLI build succeeds
  on the pinned Node. The service ships **off** and is `/dev/kvm`-gated, so nothing runs until the
  operator provisions + turns it on.

## Non-goals (this round)

- Giving the sandbox a GPU (SDD-703 D3 — the VFIO 4090 into the VM is a later, perimeter-touching SDD).
- Building the base image from the Debian ISO (the interactive VNC path) — we use the prebuilt download.
- Redistributing open-computer inside our image (AGPL) — it is **cloned at first boot** from upstream.
- Baking external channels/credentials (SDD-703 D5).

## Cross-references

- `docs/sdd/703-swappable-frontend-and-agent-runtimes.md` §B — the open-computer design + D2/D3.
- `docs/sdd/704-frontend-selector.md` — the selector whose `open-computer-kiosk` value this wires.
- `docs/sdd/705-openclaw-agent-runtime.md` — the sibling service-axis round.
- `docs/sdd/702-inference-model-provisioning.md` — the local vLLM endpoint the sandbox consumes.
- `scripts/hooks/post-install/open-computer-install.sh` · `scripts/operator/open-computer-run.sh` ·
  `systemd/system/sovereign-open-computer*.service` · `sovereign-osctl` `cmd_open_computer` — the components.
- `docs/review/phase-1/99-findings-ledger.md` — F-2026-114 (closed here).
- open-computer: github.com/Mintplex-Labs/anything-llm/tree/master/open-computer (AGPL-3.0).
