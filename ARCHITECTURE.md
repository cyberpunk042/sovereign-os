# Architecture

> Reference document. This file is **not** a design — the design lives
> in the architectural baseline owned by
> [`devops-solutions-information-hub`](https://github.com/cyberpunk042/devops-solutions-information-hub)
> (SAIN-01 milestone + 11 epics + L1-L3 syntheses). This document
> **names** the baseline, sketches the boundaries, and points the
> reader to the authoritative artifacts.
> Last updated: 2026-07-13 (Stage-2 refresh — profiles realised, intelligence
> layer added; the info-hub-owned baseline below is unchanged). Original
> arc-opening draft: 2026-05-16.
> Lock contract: `docs/sdd/001-cross-repo-boundaries.md`.

## The four-repo ecosystem

```
   ┌───────────────────────┐                 ┌───────────────────────┐
   │  sovereign-os         │   produces ───▶ │  SAIN-01 (or other    │
   │  (this repo)          │   .iso / .img   │  hardware profile)    │
   │                       │                 │                       │
   │  BUILDS the OS        │                 │  the operator's       │
   │  pre-install +        │                 │  running workstation  │
   │  during-install +     │                 │                       │
   │  post-install +       │                 │                       │
   │  lifecycle tools      │                 │                       │
   └───────────┬───────────┘                 └───────────┬───────────┘
               │                                          │
   architectural baseline                       daemon + agent target
               │                                          │
               ▼                                          ▼
   ┌───────────────────────┐                 ┌───────────────────────┐
   │  info-hub             │                 │  selfdef              │
   │  (research wiki /     │   referenced ──▶│  (security daemon +   │
   │  second brain)        │   by both       │  agent-guard +        │
   │                       │                 │  notifier channels +  │
   │  SYNTHESIZES          │                 │  escalation engine)   │
   │  knowledge:           │                 │                       │
   │  - SAIN-01 milestone  │                 │  RUNS on the OS that  │
   │  - 11 epics           │                 │  sovereign-os         │
   │  - L1 syntheses       │                 │  produces             │
   │  - L2 concepts        │                 │                       │
   │  - L3 comparisons     │                 │                       │
   └───────────────────────┘                 └───────────────────────┘

   Fourth repo:
   ┌───────────────────────┐
   │  root-ghostproxy      │   active (endpoint mode; SDD-046)
   └───────────────────────┘
```

### Boundary contract (one-line summaries)

| Repo | One-line responsibility |
|---|---|
| **`cyberpunk042/sovereign-os`** (this) | Builds the OS image; specifies profile schema; provides lifecycle-management tools. |
| **`cyberpunk042/devops-solutions-information-hub`** | Synthesizes the knowledge baseline; owns the SAIN-01 milestone + 11 epics + L1–L3 layers. Authoritative for architectural design decisions ABOUT the OS. |
| **`cyberpunk042/selfdef`** | Provides the security daemon that RUNS on the produced OS (agent-guard Tetragon module + 12 notifier channels + persistent escalations). Authoritative for runtime-defense decisions. |
| **`cyberpunk042/root-ghostproxy`** | Active as an endpoint-mode consumption dependency (SDD-046, since 2026-07-03): supplies the AI-agent safety envelope (Claude Code + opencode machine-level hooks + integrity sentinel) installed on SAIN-01 nodes via its own `install.sh --profile base --mode endpoint`. Proxy/IPS half (L2 bridge, Suricata/PolarProxy) stays DISABLED per operator directive. Authoritative for the AI-agent tool-call safety policy. Previously dormant (received /view + /questions skill installs in a prior arc). |

Full boundary semantics — what flows, what doesn't, what cross-references
are allowed — live in [`docs/sdd/001-cross-repo-boundaries.md`](docs/sdd/001-cross-repo-boundaries.md).

## The 11 SAIN-01 epics (architectural baseline, info-hub-owned)

The architectural design is locked in info-hub's SAIN-01 milestone at
[`wiki/backlog/milestones/sain-01-sovereign-node.md`](https://github.com/cyberpunk042/devops-solutions-information-hub/blob/main/wiki/backlog/milestones/sain-01-sovereign-node.md).
Each epic owns one operational domain (Single Responsibility Principle):

| Epic | Domain | What it delivers | Sovereign-os tier |
|---|---|---|---|
| **E100** Hardware Foundation | physical iron + PCIe topology | 9900X / ProArt X870E / Blackwell 96 GB / 4090 24 GB / 256 GB DDR5 / dual NVMe / 10 GbE + 2.5 GbE assembled and `friction-audit`-clean | (operator-side procurement) |
| **E101** Sovereign OS Build | custom Zen-5-tuned kernel + Debian 13 image | Bootable `.iso` with `-march=znver5` kernel; identity injected; ZFS-DKMS + NVIDIA 560+ drivers | Foundation + Infrastructure |
| **E102** ZFS Storage Layout | three-dataset stratification on RAID 0 NVMe | `tank/models` (1M lz4) · `tank/context` (16k zstd-9 copies=2 `sync=always`) · `tank/agents` (128k zstd-3); ARC clamped 128 GB | Foundation + Features |
| **E103** VFIO Isolation | RTX 4090 → `vfio-pci`; Blackwell host-resident | GRUB `vfio-pci.ids=10de:2684,10de:22ba`; AMD IOMMU pass-through; clean group separation | Foundation + Features |
| **E104** Tetragon + Guardian | kernel eBPF perimeter + Python supervisor | `TracingPolicy` (~4-binary `sys_execve` allowlist); `guardian-core` daemon; ZFS audit log | Foundation + Features |
| **E105** Network Segregation | dual-NIC split + VLAN 100/200 | Intel 2.5 GbE → mgmt VLAN 100; Marvell 10 GbE → data VLAN 200 (MTU 9000, no default GW) | Foundation + Features |
| **E106** Pulse Vector Runtime | bitnet.cpp ternary inference pinned CCD 0 | Pulse module runs `microsoft/bitnet-b1.58-2B-4T` (or 3B) on cores 0-5; ≥5 tok/sec | Features |
| **E107** Weaver State Fabric | atomic-state-write + 4 context files + gRPC | Race-free state transitions on `IDENTITY.md` / `SOUL.md` / `AGENTS.md` / `CLAUDE.md`; Podman sub-agents reach Weaver via gRPC | Features |
| **E108** Load-Balancing Profiles | three runtime profiles | Ultra-Sovereign Efficiency · Asymmetric-Burst · Deep-Context-Synthesis; profile-switch via documented mechanism | Features |
| **E109** DFlash Integration | block-diffusion speculative decoding on Blackwell + 4090 | vLLM v0.20.1+ with DFlash drafts; ≥3× speedup on code/math | Features |
| **E110** Model Catalog | resident-deploy on Blackwell 96 GB | Ling-2.6-flash (MIT, MoE 107B) and/or Nemotron-3-Nano-Omni (33B Mamba-Transformer multimodal) | Features |

Dependency graph + critical path are documented in the milestone file.
The short version: **E100 → E101** is the critical entry; **E102 + E103
+ E105 + E106** parallelize after E101; **E107 → E108 → E110** is the
final-assembly chain; **E104** straddles (depends on E102 for audit log
+ E103 for VFIO sandboxes).

## Four lifecycle stages (sovereign-os surfaces)

The OS's lifecycle is **specified** before built (SDD) and **tested**
before run (TDD via chroot / nspawn / QEMU / hardware-gated). Each
stage has its own concerns, scripts, configs, tests:

### 1. Pre-install
- Substrate selection (live-build / mkosi / debootstrap / ostree / Nix; Q-001 + Q-016)
- Custom-kernel compilation (`-march=znver5`) per **E101**
- Identity injection (`/etc/os-release` `ID=sovereign`; motd; whitelabel surfaces)
- Pre-baked driver layers (ZFS-DKMS + NVIDIA 560+ open-kernel-dkms)
- Pre-baked package set per profile (`profiles/<name>.yaml`'s `packages` section)
- Image assembly (`.iso` / `.img` via the chosen substrate)
- Reproducibility target (Q-015)

### 2. During-install
- Installer experience (debian-installer derivative / Calamares / custom TUI / image-only; Q-008)
- Hardware probing + the `friction-audit` script (per **E100** Done When: x8/x8 lanes verified, M.2_2 empty, IOMMU groups separated)
- Partitioning + ZFS layout creation (per **E102**)
- Secure-boot enrollment (Q-006) + MOK
- Profile selection (operator picks `sain-01` / `old-workstation` / future profile)

### 3. Post-install (first boot)
- Service activation (systemd ordering: ZFS → Tetragon → guardian-core → podman → application services)
- GPU driver binding (host driver for Blackwell; vfio-pci for RTX 4090 per **E103**)
- Network split activation (per **E105**)
- ZFS dataset bring-up + first-boot health check (per **E102**)
- Tetragon `TracingPolicy` load + guardian-core start (per **E104**)
- **First-login assistant flow** (Q-018): auto-launched or operator-invoked; TUI or CLI; idempotent; pre-add-friendly
- State-fabric initialization (per **E107**)
- Model catalog activation (per **E110**) — pull weights to `tank/models`; vLLM serve from Blackwell

### 4. Ongoing management (post-first-boot, lifelong)
- **Lifecycle-management surface** (Q-019): operator can evolve the OS in place
  - Add/remove modules
  - Swap profiles (e.g. add a `developer` profile rendering)
  - Rotate models in the catalog (per **E110**)
  - Re-apply whitelabel (rotate brand identity)
  - Re-audit perimeter (re-load Tetragon policies)
  - Re-shape network split (re-VLAN-config)
- Profile switching (per **E108**)
- Observability + operator dashboards (Q-013)
- Decommission / wipe (per **Q-014**)

## Four cross-cutting concerns

Threading through every lifecycle stage:

### 1. Profiles
The OS is **multi-profile from day 1**. All five profiles now exist as full,
schema-conformant `profiles/*.yaml` bodies (no longer reserved stubs):
- `sain-01` — the info-hub milestone target (default).
- `old-workstation` — 11 GB RAM + 8 GB GPU.
- `minimal` · `developer` · `headless` — realised profiles (were Q-012 reserved slots).

Profiles are schema-conformant against SDD-004; the schema + mixin/runtime/orchestration
families are validated in CI (`make validate`, `scripts/validate-profiles.sh`). The schema
covers: identity, hardware target, kernel config, package sets, activation hooks per
lifecycle phase, whitelabel binding, observability binding.

### 2. Whitelabel
The OS rebrands away from its upstream substrate (Debian 13 working hypothesis). Every Debian identity surface (per PR 7 audit) gets routed through the whitelabel mechanism (PR 8). Legal-obligation minimum stays (DFSG + Debian trademark).

### 3. Observability
- Structured logs per lifecycle phase (`~/.sovereign-os/log/...` or analog).
- Build-pipeline progress (per the IaC bar's "observable" requirement).
- Per-service exposing metrics (Prometheus / Grafana / OpenTelemetry; Q-013).
- Audit logs (Tetragon → guardian-core → `tank/context/security_audit.log` per **E104**).

### 4. Evolvability ("everything being able to evolve, before and after")
- Pipeline-level: profiles / substrates / whitelabel / lifecycle hooks add cleanly.
- Image-level: build is resumable + state-aware (IaC bar's restart-from-state).
- Installed-OS level: lifecycle-management tools (Q-019) let the operator add tools / services / models in place.

## The intelligence layer (Stage-2)

Beyond the foundation IaC, sovereign-os grew a **Rust intelligence layer** under
`crates/` — the box's own local-AI backend, so it can drive tools (VS Code, Claude
Code) against a model it runs itself rather than a remote API.

- **`sovereign-gatewayd`** is the one persistent daemon (`sovereign-gatewayd.service`,
  loopback `127.0.0.1:8787`). It speaks the **Anthropic Messages API** (`/v1/messages`,
  SDD-205) + an OpenAI shim over the local model, with the safety spine (injection
  screen + secret/PII redaction + auth/timeouts, SDD-206) in front and durable memory
  behind it.
- The **generation stack** runs inside the daemon: `safetensors-loader → quant-model`
  with real RoPE / precision-selectable load / sampler (SDD-953/950), and the
  `sovereign-cortex` routing/reasoning brain (the CoAT engine + job runtime).
- The **binaries** — one daemon, a periodic telemetry emitter, control/test helpers,
  and a set of dev/demo + config-generator CLIs — are mapped in
  [`docs/src/binaries.md`](docs/src/binaries.md); the AI-backend usage is in
  [`docs/src/ai-backend.md`](docs/src/ai-backend.md).

This layer is Stage-2 work (it postdates the foundation Gate 5); the foundation IaC
(profiles, whitelabel, observability, evolvability) remains the substrate it runs on.

## SFIF mapping (this arc itself)

Per the operator's Scaffold → Foundation → Infrastructure → Features
discipline:

| Tier | sovereign-os PRs | What lands |
|---|---|---|
| **Scaffold** | PRs 1–3 | Charter (PR 1) · ARCHITECTURE.md + SDD-001 (PR 2, this PR) · mdbook + MCP template (PR 3) |
| **Foundation** | PRs 4–8 | Substrate survey (Q-001 + Q-016) · profile schema · profile stubs · whitelabel surface audit · whitelabel mechanism |
| **Infrastructure** | PRs 9–10 (start), Stage 2+ (continues) | TDD harness (chroot · nspawn · QEMU) · first build scripts (Stage 2 post-Gate-5) |
| **Features** | Stage 2+ | Image generation · interactive build · lifecycle management · first-login assistant · model catalog · post-install evolution |

Five stage gates: Gate 1 after PR 3 · Gate 2 after PR 4 (substrate) ·
Gate 3 after PR 6 (schema) · Gate 4 after PR 8 (whitelabel + legal) ·
Gate 5 after PR 10 (foundation-complete; authorizes Stage 2).

> **Current state (2026-07 — post-Gate-5, Stage-2 underway):** the table above is the
> original arc plan. The foundation landed (5 realised profiles · whitelabel · the
> observability + build/orchestration families · the nspawn TDD tier), Gate 5 passed,
> and Stage-2 is underway — the build/orchestration scripts, the operator control-plane
> (`scripts/operator/` + the systemd fleet, see [`systemd/system/README.md`](systemd/system/README.md)),
> and the Rust **intelligence layer** above are live. The QEMU/chroot TDD tiers remain
> scaffolds (F-2026-052). See [`context.md`](context.md) for the current-arc detail.

## Authoritative references (cross-repo)

| Topic | Path |
|---|---|
| **SAIN-01 milestone (architectural baseline)** | info-hub `wiki/backlog/milestones/sain-01-sovereign-node.md` |
| 11 epics (E100–E110) | info-hub `wiki/backlog/epics/milestone-sain01/e1??-*.md` |
| L1 source-synthesis (BitNet · DFlash · Zen 5 · SAIN-01 master spec) | info-hub `wiki/sources/src-{bitnet-b158-ternary-llm,dflash-block-diffusion-spec-dec,zen5-avx512-single-cycle,sain-01-sovereign-node-spec}.md` |
| L2 concepts (1-bit ternary · spec-dec block-diffusion · SRP Trinity · ZFS tiered · VFIO isolation · dual-CCD) | info-hub `wiki/domains/{ai-models,ai-agents,devops}/concept-*.md` |
| L3 comparisons (4 head-to-heads incl. Ling vs Nemotron · BitNet vs FP16 · DFlash vs EAGLE-3/MEDUSA · wall vs write vs Tetragon) | info-hub `wiki/comparisons/cmp-*.md` |
| Operator directive verbatim (sovereign-os arc opening) | info-hub `raw/notes/2026-05-16-user-directive-sovereign-os-arc-opening.md` + `…-limit-continuation.md` |
| Plan-agent macro-arc (authoritative scaffold for PRs 1–10) | info-hub `raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md` |
| Selfdef cross-repo bridge | selfdef `docs/sdd/011-sovereign-os-arc-opening.md` |
| Selfdef decisions log (D-026 sovereign-os arc opening) | selfdef `docs/decisions.md` |
| Selfdef Stage-2 stub (selfdef-on-SAIN-01) | selfdef `docs/sdd/010-selfdef-on-sain01.md` |
| Selfdef cold-start handoff | selfdef `docs/handoff/2026-05-16-sovereign-os-arc-opening.md` |

## Reference shape

When sovereign-os references the info-hub or selfdef artifacts above,
the reference is **symbolic by default** (path-only, no commit pin)
with a CI guard verifying the referenced path resolves. Hard pinning
is reserved for cases where reproducibility requires it (release-tag
inclusion). Hybrid posture documented in
[`docs/sdd/001-cross-repo-boundaries.md`](docs/sdd/001-cross-repo-boundaries.md)
§ Q-011.

## What this architecture does NOT decide

Per the charter's non-goals (`docs/sdd/000-charter.md`):

- Substrate (Q-001 + Q-016 — PR 4)
- Brand identity (Q-003 — deferrable)
- Build script contents (Stage 2+)
- ZFS root layout details (Q-005 — Stage 2+)
- Secure-boot posture (Q-006 — Stage 2+)
- Kernel choice details (Q-007 — Stage 2+)
- Installer experience (Q-008 — Stage 2+)
- Inference backend stack (Q-017 — Stage 2+)
- First-login assistant shape (Q-018 — Stage 2+)
- Lifecycle-management surface shape (Q-019 — Stage 2+)
