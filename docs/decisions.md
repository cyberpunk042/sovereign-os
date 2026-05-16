# Decisions log

Chronological audit trail of design-question resolutions. Each `D-NNN`
entry corresponds to an answered question from one of the SDDs (or a
similar source doc — operator directive, handoff, audit ledger, RFC).
Entries are **append-only** — never edit a past entry; if a decision is
revisited, append a new entry that references the prior one.

The two-artifact pattern (decisions + open questions) mirrors selfdef's
`docs/decisions.md`. When an open question resolves:

1. The SDD's `Q-X` row gets annotated **in place** with
   `**answered (D-NNN, YYYY-MM-DD)**`.
2. A new `D-NNN` entry is appended here.
3. The two together form the audit trail: the SDD stays the canonical
   source of truth; this log gives the chronological view.

## Format (per entry)

```markdown
## D-NNN — YYYY-MM-DD — <one-line summary>

**Decision**: <what was decided — operator-verbatim if free-text>
**Question**: <full question, copied from source doc>
**Source**: `docs/sdd/<n>-<title>.md`:<line> (Q-X row)
**Rationale**: <why this option beats the alternatives — synthesis + any operator commentary>
**Affected items**: <files / future SDDs / scripts touched>
**Reversibility**: fully-reversible | partial | locked
**Linked**: PR #<n>
```

`Reversibility` legend:

- **fully-reversible** — the decision can be revisited at any time with
  no migration cost.
- **partial** — revisiting requires some refactor / migration but no
  data loss or compat break.
- **locked** — revisiting requires a breaking change.

---

## Decisions

### D-001 — 2026-05-16 — Repository created; AGPL-3.0-or-later; public; mirrors selfdef rhythm

**Decision**: `cyberpunk042/sovereign-os` exists as a new public repo
licensed AGPL-3.0-or-later (mirroring selfdef per the operator's framing
answer "match selfdef"). Workflow conventions mirror selfdef:
numbered SDDs in `docs/sdd/`, append-only `docs/decisions.md`, dated
handoff anchors in `docs/handoff/`, audit phases in `docs/review/`,
mdbook publishing pipeline (Stage 3+).
**Question**: Where does the OS-build pipeline arc live; under what
license; with what conventions?
**Source**: operator `/goal` 2026-05-16 (info-hub
`raw/notes/2026-05-16-user-directive-sovereign-os-arc-opening.md`);
selfdef `D-026` (in `cyberpunk042/selfdef/docs/decisions.md`).
**Rationale**: A new fourth repo respects the cleanest separation
principle (sovereign-os BUILDS, selfdef RUNS, info-hub SYNTHESIZES).
AGPL-3.0-or-later mirrors selfdef's license posture verbatim per
operator answer. Selfdef rhythm is operator-fluent; reusing it costs
zero context-switch.
**Affected items**: this repo's existence; `LICENSE`; `README.md`;
`docs/sdd/000-charter.md`; `docs/sdd/INDEX.md`; `docs/decisions.md`
(this file); `docs/handoff/INDEX.md`; `docs/review/INDEX.md`.
**Reversibility**: partial — license is reversible with consent of
contributors; conventions are reversible at any time.
**Linked**: PR #1.

### D-002 — 2026-05-16 — Plan-agent 10-PR macro-arc adopted; SFIF mapping; 5 stage gates

**Decision**: Adopt the Plan-agent's 10-PR foundation-phase macro-arc
(preserved verbatim at info-hub `raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md`).
SFIF tier mapping: Scaffold = PRs 1–3; Foundation = PRs 4–8;
Infrastructure (start) = PRs 9–10; Features = Stage 2+. Five stage
gates: Gate 1 after PR 3 (structural); Gate 2 after PR 4 (substrate);
Gate 3 after PR 6 (schema lock); Gate 4 after PR 8 (whitelabel + legal);
Gate 5 after PR 10 (foundation-complete; authorizes Stage 2).
**Question**: How is the foundation phase decomposed into PRs and
operator review checkpoints?
**Source**: Plan-agent macro-arc output authorized by operator
2026-05-16; selfdef `D-026`.
**Rationale**: The Plan-agent's decomposition respects all three
parallelism axes the operator surfaced (whitelabel independent of
substrate; profile schema independent of substrate; ~70 % of work is
hardware-free), respects the SFIF lifecycle, and lands explicit
operator-review checkpoints at every tier transition. Adopting it
verbatim preserves the "we think before we act" discipline.
**Affected items**: all future PR scopes; `docs/sdd/INDEX.md` (slots
000–010 reserved per the plan); `docs/handoff/INDEX.md` (gate-tied
handoffs); `docs/review/INDEX.md` (gate-tied audit phases).
**Reversibility**: fully-reversible — the plan is the agent's
execution scaffold; operator can re-scope any PR at any gate.
**Linked**: PR #1.

### D-003 — 2026-05-16 — SAIN-01 is the default profile; old-workstation is the alternate (schema-first, multi-profile from day 1)

**Decision**: The default OS profile is `sain-01` (Ryzen 9 9900X + RTX
PRO 6000 Blackwell + RTX 3090 + 256 GB DDR5 + dual PCIe 5 NVMe + Marvell
10 GbE + Intel 2.5 GbE on ASUS ProArt X870E-Creator). The alternate
declared-from-day-1 profile is `old-workstation` (11 GB RAM + 8 GB GPU
class). Future profiles (`minimal`, `developer`, `headless`) are
reserved-but-unwritten until a concrete operator need surfaces. Profile
schema is declared **before** any profile body (PR 5 SDD-004 → PR 6
schema-conformant stubs).
**Question**: What is the default profile and how does multi-profile
shape decisions from day 1?
**Source**: operator `/goal` 2026-05-16 framing answer ("Schema-first,
multi-profile from day 1; default = SAIN-01 / RTX Pro 6000"); SAIN-01
milestone (info-hub `wiki/backlog/milestones/sain-01-sovereign-node.md`).
**Rationale**: Schema-first means the schema constrains both default
and alternate profiles. Declaring two profiles from day 1 forces the
schema to handle real variance before any single profile's body is
implementation-locked. The `old-workstation` profile keeps the
operator's "11 GB + 8 GB card" deployment honest as a real target, not
an aspirational variant.
**Affected items**: future `docs/sdd/004-profile-schema.md`;
`profiles/sain-01.yaml`; `profiles/old-workstation.yaml`;
`profiles/INDEX.md`.
**Reversibility**: fully-reversible — schema can be revised at Gate 3;
profile bodies can be extended at any time.
**Linked**: PR #1 (charter); PRs #5 + #6 (substantive).

---

## Open questions seeded at PR 1

These are the open design questions reserved for future SDDs to resolve.
Each is **enumerated** rather than answered. When resolution lands, a
`D-NNN` entry above will reference back to the relevant `Q-X` here.

### Q-001 — Final substrate selection
**Where it lands**: PR 4 SDD-003 substrate survey → Gate 2.
**Question**: Which image-build substrate does sovereign-os use? Candidates:
live-build (Debian native) · mkosi (systemd) · debootstrap (low-level) ·
Lorax (Fedora) · Kiwi (SUSE) · ostree (atomic) · Nix/NixOS-style
declarative · Buildroot (embedded reference for contrast).
**Working hypothesis**: live-build or mkosi on Debian 13 (per
Debian-as-Ark framing); decided honestly via PR 4 survey.

### Q-002 — Profile inheritance model
**Where it lands**: PR 5 SDD-004 profile schema → Gate 3.
**Question**: Single-parent inheritance · multiple-inheritance ·
composition (mixins)? Trade-off: single-parent is simpler to validate;
composition is more powerful for cross-cutting concerns (whitelabel,
observability tier) but harder to reason about.
**Working hypothesis**: single-parent inheritance + named mixins for
cross-cutting (whitelabel, observability), surfaced in PR 5's SDD.

### Q-003 — Whitelabel brand identity (name, palette, logo)
**Where it lands**: deferrable past PR 8; whitelabel mechanism lands
without brand committed.
**Question**: What is the brand name, color palette, logo asset for the
default whitelabel? Operator may defer this past the mechanism PR.

### Q-004 — Legal scope of whitelabel
**Where it lands**: PR 7 SDD-006 + PR 8 SDD-007 (whitelabel) → Gate 4.
**Question**: Public-distribution whitelabel (high legal bar — Debian
trademark + DFSG compliance fully enforced) vs internal-use whitelabel
(lower bar)?

### Q-005 — ZFS root layout details
**Where it lands**: Stage 2+ (deferred).
**Question**: Pool topology, dataset hierarchy beyond the three
SAIN-01 datasets (`tank/models` · `tank/context` · `tank/agents`),
encryption choice (LUKS-under-ZFS · native ZFS encryption · neither).

### Q-006 — Secure-boot posture
**Where it lands**: Stage 2+ (deferred).
**Question**: Own keys (MOK enrollment) · Microsoft-signed shim ·
secure-boot disabled?

### Q-007 — Kernel choice
**Where it lands**: Stage 2+ (deferred).
**Question**: Debian stock kernel · custom-compiled `-march=znver5`
kernel (per E101) · xanmod / liquorix / other tuned variant?

### Q-008 — Installer experience
**Where it lands**: Stage 2+ (substrate decision in PR 4 constrains
this).
**Question**: debian-installer derivative · Calamares · custom TUI ·
custom GUI · image-only (no installer; image is dd'd)?

### Q-009 — Hardware procurement timeline (SAIN-01)
**Where it lands**: operator-side decision; gates when hardware-tier
tests come online in TDD harness.
**Question**: When does SAIN-01 hardware reach assembly + ready-to-test?

### Q-010 — CI infrastructure
**Where it lands**: PR 3 (mdbook + MCP template) + PR 10 (CI workflow).
**Question**: GitHub Actions runners (KVM-enabled?) · self-hosted
runners · hybrid?

### Q-011 — Cross-repo commit-pin level
**Where it lands**: PR 2 (cross-repo boundaries) → SDD-001.
**Question**: How does sovereign-os reference specific selfdef / info-hub
commits — symbolic refs · hard-pinned commit SHAs · hybrid? Plan-agent's
trade-off table recommends hybrid (symbolic + CI verifying refs exist).

### Q-012 — Future-profile timeline (`minimal`, `developer`, `headless`)
**Where it lands**: Stage 2+ (deferred until concrete operator need).
**Question**: When do these reserved profile slots get substantive
bodies?

### Q-013 — Observability binding details
**Where it lands**: Stage 2+ (deferred).
**Question**: Telemetry sink (Prometheus · Grafana · OpenTelemetry · custom),
log retention policy, audit log shape, metrics-exposure model.

### Q-014 — Decommission / wipe profile testing
**Where it lands**: PR 9 SDD-008 (TDD harness) decides scope.
**Question**: Does the schema's decommission hook get exercised in
foundation-phase tests, or deferred until a real hardware-decommission
event?

### Q-015 — Reproducibility target
**Where it lands**: PR 4 SDD-003 (substrate decision constrains this).
**Question**: Bit-for-bit reproducible builds · content-equivalent
builds · best-effort?

### Q-016 — Distro-base reconsideration (operator-added 2026-05-16)
**Where it lands**: PR 4 SDD-003 substrate survey → Gate 2.
**Question**: Does staying on Debian 13 cost us material potential? Are
there features / capabilities / ecosystem advantages we'd unlock by
switching to Fedora · openSUSE · Arch · Nix / NixOS · other? Survey
honestly; if staying on Debian costs us something, document the loss +
the equivalent we'd build ourselves; if switching costs us more,
document the why.
**Working hypothesis**: stay on Debian 13 + customize heavily ("Debian
as Ark"). Decision at Gate 2 alongside Q-001.

### Q-017 — Inference-backend stack (operator-added 2026-05-16)
**Where it lands**: dedicated future SDD (target slot reserved
post-PR-10; likely Stage 2+ once profile bodies are concrete).
**Question**: Which inference backend(s) does the OS pre-install /
pre-configure in the `sain-01` profile (and others)?
Candidates: **LocalAI** (operator-flagged as potentially limiting) ·
**vLLM** (CUDA-first, datacenter-grade) · **llama.cpp** (CPU + GPU,
sovereignty-friendly) · **OpenLLM** · **Triton Inference Server** ·
**SGLang** · **Ollama** (Go, simple) · **custom stack** (bitnet.cpp +
vLLM + Mamba kernels assembled directly per the SRP Trinity).
**Working hypothesis**: profile-conditional. For `sain-01`: vLLM +
bitnet.cpp + (DFlash where applicable) directly per the SRP Trinity,
not via a unifying abstraction layer. Operator concern: "I dont even
know if we can stick with LocalAI I think would limite us" — verbatim.
The SDD must evaluate honestly: what does LocalAI's abstraction cost
us in expressiveness / direct-hardware exploitation, vs what does it
save us in operational uniformity?

### Q-018 — First-login post-install assistant (operator-added 2026-05-16)
**Where it lands**: Stage 2+ — dedicated SDD when the install
experience PR (Q-008) is in scope.
**Question**: How does the post-install assistant flow work?
- **Triggering**: auto-launch on first login · operator-invoked via
  `sovereign-osctl init` · both modes (auto + opt-out)?
- **Interface**: interactive TUI (whiptail / dialog / textual) ·
  CLI-only scripted prompts · GUI (only if installer is GUI) ·
  TUI-first with CLI fallback?
- **Scope**: which post-install customizations are surfaced (hostname,
  user accounts, locale, GPU driver enable, model catalog pick, profile
  refinement, network config, secure-boot enrollment, …)?
- **Idempotency**: re-running must be safe + state-aware.
- **Pre-add path**: how does an unattended-install scenario pre-supply
  the assistant's answers (cloud-init / preseed / sovereign-os-specific
  answer file)?

### Q-019 — Lifecycle-management surface for post-install (operator-added 2026-05-16)
**Where it lands**: Stage 2+ — dedicated SDD when the installed-OS
management story is in scope.
**Question**: What is the ongoing-management surface shape?
- **Dedicated CLI** (e.g. `sovereign-osctl modules apply` / `profiles switch`
  / `whitelabel rotate` / `services add` — mirrors selfdef's `selfdefctl`
  pattern)?
- **systemd-units + scripts** (no central CLI; each capability is a
  unit + manpage)?
- **Hybrid** (CLI for the cross-cutting verbs, units for the
  capability-specific concerns)?
- **Web UI** (operator-stated dashboard for observable + operable)?
- **Operator's existing AICP (devops-expert-local-ai) integration** —
  does the lifecycle surface plug into AICP's MCP / agent server, or
  stay standalone?
- **Evolution semantics**: adding a new tool / service post-install is
  the load-bearing case ("even if we need to add such an additional tool
  and even service possibly or even multiple adapted if need be" —
  verbatim). The surface MUST make this graceful.

---

### D-004 — 2026-05-16 — Installer experience: image-only (mkosi-built) + cloud-init/preseed pre-supplied answers; no installer UI

**Decision**: sovereign-os ships **bootable disk images** built by
mkosi (per SDD-003 substrate choice) and reads pre-supplied answers
from **cloud-init** (NoCloud datasource) and/or **debian-installer
preseed**. **No interactive installer UI** — no d-i Q&A flow, no
Calamares, no custom TUI. The post-install `first-login-assistant`
covers interactive operator decisions.
**Question**: Q-008 — Which installer experience: debian-installer
preseed · Calamares · custom TUI · image-only with no installer?
**Source**: `docs/sdd/013-installer-experience.md`; existing artifacts
in `config/cloud-init/` + `config/preseed/`.
**Rationale**: image-only minimizes installer surface (no Q&A UI to
maintain), is reproducible (image bits + answer file = deterministic),
matches the IaC bar (cloud-init = declarative pre-config), and aligns
with the sovereignty principle (no install-time phone-home, no third-
party UI surface, no network dep for first boot). The d-i preseed
path stays available for operators who prefer it. Calamares pulls in
Qt5 (wrong shape for headless / sain-01). Custom TUI would reinvent
the installer — wrong investment.
**Affected items**: `docs/sdd/013-installer-experience.md` (this SDD);
`config/cloud-init/{sain-01,old-workstation,minimal}.user-data.example.yaml`;
`config/preseed/sain-01.preseed.example.cfg`;
`scripts/hooks/post-install/first-login-assistant.sh`;
`tests/nspawn/test_install_configs.sh` (CI gate).
**Reversibility**: fully-reversible — if the operator later wants a
TUI installer, it lands as additive (image-only path stays). The
configs are operator-edited examples, not enforced policy.
**Linked**: direct-to-main commit on 2026-05-16.

### D-005 — 2026-05-16 — Brand identity: placeholder strategy with promotion criteria (Q-003 deferred-with-criteria)

**Decision**: Q-003 (whitelabel brand identity) stays **deferred** —
no permanent name, palette, or logo yet — but with explicit criteria
for when a "real" brand becomes required (public distribution per
Q-004 · second public-facing UI surface · operator rebrand) AND with
an explicit promotion mechanism (`whitelabel/<brand>/` + `<brand>.yaml`
drop-in, no render-engine code change). Until then, the placeholder
in `whitelabel/default.yaml` ships. Legal floor (`/etc/debian_version`
+ `/usr/share/doc/*/copyright` + `ID_LIKE=debian`) is preserved
regardless of brand choice — verified by Layer 3 tests.
**Question**: Q-003 — Whitelabel brand identity: name · palette · logo.
**Source**: `docs/sdd/012-brand-identity-placeholder.md`; existing
artifacts in `whitelabel/default/`.
**Rationale**: Operator's focus is technical sovereignty, not branding.
A premature brand decision would either (a) ship aesthetically weak
artifacts that get replaced or (b) consume design budget the project
doesn't have yet. Placeholder-with-promotion-mechanism keeps the
image shippable without committing to a brand. The legal-floor
contract is unaffected by Q-003 resolution timing — that's already
locked at SDD-006/007.
**Affected items**: `docs/sdd/012-brand-identity-placeholder.md`;
`whitelabel/default.yaml` (placeholder values stay);
`tests/nspawn/test_whitelabel_render_live_build.sh` (placeholder-leak
gate guards against unsubstituted `${var}` sigils in production builds).
**Reversibility**: fully-reversible — a real brand promotes any time
by adding `whitelabel/<id>/` content + flipping `active-whitelabel`.
**Linked**: direct-to-main commit on 2026-05-16.

### D-006 — 2026-05-16 — Decommission testing scope: gates in CI, destruction only on real hardware (Q-014 resolved)

**Decision**: Decommission scripts are inherently destructive — CI
tests their **gates** (require_root + SOVEREIGN_OS_CONFIRM_DESTROY
env-gate + interactive confirm + idempotency + operator-observable
refusals), NOT their destructive happy paths. End-to-end destruction
is exercised on real hardware by the operator (Layer 5), never in CI.
A potential Layer 4 destructive-loop test inside QEMU is acknowledged
but deferred until the hardware arrives.
**Question**: Q-014 — what is the testing scope for decommission?
**Source**: `docs/sdd/014-decommission-testing-scope.md`;
`scripts/hooks/decommission/`; `tests/nspawn/test_decommission_gates.sh`.
**Rationale**: Real-pool / real-disk destruction has no value in CI
(it would require provisioning destroyable state per run). Gate
correctness, however, is exactly where regressions cost the operator
real data. The 12-assertion Layer 3 gate covers every refusal path
the operator depends on. Honest scope > false confidence.
**Affected items**: `docs/sdd/014-decommission-testing-scope.md`;
`tests/nspawn/test_decommission_gates.sh`;
`.github/workflows/test.yml` (14th Layer 3 step).
**Reversibility**: fully-reversible — a QEMU destructive-loop test can
land later as additive coverage.
**Linked**: direct-to-main commit on 2026-05-16.

### D-007 — 2026-05-16 — Secure-boot posture: 3-level enum (none/shim/signed) per-profile; operator-supplied keys (Q-006 resolved)

**Decision**: secure_boot is a per-profile enum with three values:
**none** (UEFI off / unsigned, dev VMs), **shim** (Microsoft-signed
shim → operator MOK → kernel; constrained / legacy hardware),
**signed** (direct sbsign with operator's Platform Key, no shim;
production sovereign hardware). Operator supplies signing keys at
build time via SOVEREIGN_OS_{MOK,PK}_{KEY,CERT} env vars — keys are
NEVER stored in-repo. preflight-tpm.sh gates install-time TPM2
readiness for posture=shim/signed. step 08-image-sign.sh is the only
script that signs.
**Question**: Q-006 — Secure-boot posture for sovereign-os.
**Source**: `docs/sdd/015-secure-boot-posture.md`;
`profiles/{sain-01,old-workstation,minimal}.yaml` § kernel.cmdline.
secure_boot; existing `preflight-tpm.sh` + `08-image-sign.sh`.
**Rationale**: 3-level posture matches the substrate's natural
capabilities (mkosi supports SecureBoot=yes), allows constrained
profiles (old-workstation = shim) without forcing them through PK
enrollment, and keeps production sain-01 on the operator-owned chain
(direct PK, no Microsoft-CA dep). Operator-supplied keys preserve
sovereignty — sovereign-os ships zero shared secrets. Q15-A..Q15-C
sub-questions tracked in SDD-015.
**Affected items**: `docs/sdd/015-secure-boot-posture.md`;
`profiles/*.yaml` (no changes — posture values already declared
per-profile); `scripts/hooks/pre-install/preflight-tpm.sh`;
`scripts/build/08-image-sign.sh`.
**Reversibility**: partial — adding new enum values is additive,
removing is breaking. Switching a profile from signed→shim is a
build-time decision with no migration cost; the reverse requires
operator PK enrollment.
**Linked**: direct-to-main commit on 2026-05-16.

---

## Cross-references

- Charter: `docs/sdd/000-charter.md`
- SDD index: `docs/sdd/INDEX.md`
- Selfdef decision D-026 (sovereign-os arc-opening): `cyberpunk042/selfdef/docs/decisions.md`
- Selfdef SDD-011 (cross-repo bridge): `cyberpunk042/selfdef/docs/sdd/011-sovereign-os-arc-opening.md`
- Info-hub operator directive verbatim: `cyberpunk042/devops-solutions-information-hub/raw/notes/2026-05-16-user-directive-sovereign-os-arc-opening.md`
- Info-hub Plan-agent macro-arc: `cyberpunk042/devops-solutions-information-hub/raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md`
- SAIN-01 milestone: `cyberpunk042/devops-solutions-information-hub/wiki/backlog/milestones/sain-01-sovereign-node.md`
