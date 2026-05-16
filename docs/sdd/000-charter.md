# SDD-000 — Project charter

> Status: **accepted** (foundational charter, locked by PR 1 + operator-verbatim quality bar)
> Owner: operator-supervised; agent-authored
> Last updated: 2026-05-16
> Closes findings: none (foundational document)
> Derived from: operator `/goal` 2026-05-16 + selfdef SDD-011 + info-hub
> `raw/notes/2026-05-16-user-directive-sovereign-os-arc-opening.md`
> + Plan-agent macro-arc output (info-hub `raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md`).

## Mission

`sovereign-os` produces a **custom-built, multi-profile, whitelabel-able
Linux operating system** for the SAIN-01 AI Workstation (default) and
other deliberately-declared hardware profiles. The pipeline covers the
full lifecycle of an OS — pre-install image generation, during-install
experience, post-install / first-boot activation, and ongoing
post-install management — every stage **specified before built** (SDD)
and **tested before run on real hardware** (TDD).

The OS is **sovereign**: operator-owned, operator-evolvable, transparent
in every component, free of phone-home defaults, and able to run without
external dependencies once installed. "Sovereign" is the load-bearing
adjective. Every design decision is filtered through the question *"does
this preserve the operator's ability to evolve, observe, operate, and
own this system end-to-end?"* The answer must be yes.

## Scope boundaries (what sovereign-os IS — and ISN'T)

### `sovereign-os` IS

- The **build pipeline** that generates installable OS images
  (`.iso` / `.img` / equivalent) for declared profiles.
- The **schema** that defines what an OS profile is (identity, hardware
  target, kernel config, package sets, lifecycle hooks, whitelabel
  binding, observability binding).
- The **whitelabel mechanism** that rebrands the OS away from the
  upstream substrate (default substrate hypothesis: Debian 13, subject
  to Q-001 + Q-016).
- The **lifecycle management surface** for the installed OS — tools,
  commands, services that let the operator evolve the system after
  install (add modules, swap profiles, rotate models, re-audit
  perimeter, manage state).
- The **TDD harness** (chroot · systemd-nspawn · QEMU · hardware-gated)
  for hardware-free validation.
- The **first-login assistant flow** — post-install guided customization
  ready to be pre-added or auto-launched on first login.

### `sovereign-os` IS NOT

- A **runtime application** on the OS. selfdef does that.
- A **knowledge wiki** about the OS or its components. info-hub does that.
- A **kernel project**. We compile + tune kernels from upstream stable
  (Linux 6.12+ at this time); we do not maintain a kernel fork.
- A **distribution**. We produce profile-specific custom images on top
  of an upstream substrate (most likely Debian 13 per Q-001 + Q-016).
- A **fleet orchestrator**. Multi-host coordination is a future concern
  layered on top of single-host sovereign-os; not in this repo's
  primary scope.
- A **model registry**. Model weight management is referenced (the OS
  ships with hooks for inference backends) but model curation belongs
  to info-hub + the eventual model-catalog tooling.
- An **AI-agent runtime**. Agents may run on the installed OS; the OS
  does not embed an agent runtime as a sovereign-os concern (though
  pre-installed inference backends are a profile-level option).

## SDD + TDD discipline (verbatim operator directive)

> "all in Spec Driven Development and Test Driven Development"

Every code-bearing PR in this repo MUST cite an accepted SDD. The SDD
defines what the code does, what tests verify, and what invariants must
hold. No code lands without:

1. **An SDD** in `docs/sdd/NNN-*.md` at status `accepted` (or higher),
   numbered three-digit zero-padded, never recycled.
2. **Test assertions** authored *before* the implementation
   (`tests/<layer>/<name>.{sh,py,yaml}` — schema, lint, chroot, nspawn,
   qemu, hardware tier as appropriate).
3. **Invariants per lifecycle stage** — pre-install / during-install /
   post-install-first-boot / post-install-recurrent / decommission —
   declared as named assertions executable against the test harness.
4. **A decisions log entry** (`docs/decisions.md` `D-NNN`) if the PR
   resolves an open `Q-X` question.

SDD numbering reserved at PR 1:

| Slot | Working title |
|---|---|
| 000 | This charter |
| 001 | Cross-repo boundaries (PR 2) |
| 002 | Documentation pipeline + mdbook + MCP template (PR 3) |
| 003 | Substrate survey + Q-001 + Q-016 (PR 4) |
| 004 | Profile schema (PR 5) |
| 005 | Initial profile stubs (sain-01 + old-workstation) (PR 6) |
| 006 | Debian (or successor) surface audit for whitelabel (PR 7) |
| 007 | Whitelabel mechanism (PR 8) |
| 008 | TDD harness specification (PR 9) |
| 009 | TDD harness bootstrap (PR 10) |
| 010 | Stage-2 first-build-scripts stub (PR 10 reserves the slot) |

## SFIF discipline (verbatim operator directive)

> "we remember the SFIF, Skaffold, Fundation, Infrastructure, Features"

The Scaffold → Foundation → Infrastructure → Features lifecycle pattern
applies to this arc itself:

| Tier | PRs | Deliverables |
|---|---|---|
| **Scaffold** | 1 (this PR) — 3 | Repo skeleton · charter (this doc) · ARCHITECTURE.md · cross-repo refs · mdbook · MCP template |
| **Foundation** | 4 — 8 | Substrate survey (Q-001 + Q-016) · profile schema · profile stubs · whitelabel surface audit · whitelabel mechanism. **Decisions land in this tier.** |
| **Infrastructure** | 9 — 10 (start), Stage 2 (continues) | TDD harness (hardware-free chroot + nspawn + QEMU) · first build scripts (Stage 2) |
| **Features** | Stage 2+ onwards | Image generation · interactive build modes · lifecycle management commands · first-login assistant · profile selection UX · model-catalog integration · post-install evolution tools |

Each tier closes with a **stage gate**: explicit operator review before
the next tier opens. No PR opens past a gate without sign-off.

## IaC quality bar (verbatim operator directive — sacrosanct)

> "we always deliver IaC, high quality scripts and libs and configuration
> and easily tweakable and configurable and customisation and even via
> env vars when needed, or other pre-existing config or temporary file
> detected and restarting from there such as if there is has to be a
> local tracking of the progress of a build in multi-steps that can only
> ever re-happen locally"

Every script / lib / config in this repo MUST satisfy:

| Requirement | Concrete obligation |
|---|---|
| **IaC** | Every operational pattern as reproducible tooling. No manual infrastructure. Declarative where the substrate supports it. |
| **High quality** | Lint clean (shellcheck for bash; ruff/mypy for Python; yamllint for YAML). Sealed deps. Drift-guard tests where applicable. No `set -e` without `set -o pipefail` + explicit error handling. |
| **Tweakable** | Every operational knob exposed via config file (YAML/TOML preferred) AND env-var override AND CLI flag. Three layers of override, documented precedence. |
| **Restart-from-state** | Any multi-step build operation persists per-step state under `.sovereign-os-build/` (or equivalent) and resumes from the last completed step on re-run. The state file is human-readable; operator can inspect, force-rewind, or skip-step manually. |
| **Pre-existing config detection** | Scripts probe for existing config / temp / state before clobbering. Prompt or fail loudly; never overwrite silently. |
| **Observable** | Every long-running operation emits structured progress (stdout + log file in `~/.sovereign-os/log/` or equivalent). Exit codes are meaningful. Timing + step-completion metrics captured. |
| **Operable** | Operator can intervene mid-flight: pause (Ctrl-Z safe), inspect state, resume, rewind to a prior step, skip a step with documented consequences. |

This bar is **load-bearing**. A script that ships without restart-from-state
is incomplete, not a v1 deliverable. A config without env-var override is
incomplete. The bar is non-negotiable.

## "Debian as Ark" framing (verbatim operator directive)

> "I think Debian is a bit like saying we have our Arc but we start from
> there, kind of thing ?"

Debian 13 is the **starting boat, not the destination**. The working
hypothesis is: stay on Debian 13 + customize the boat so heavily that
the result is recognizable-only-on-paper as Debian. The whitelabel
mechanism (SDD-007, PR 8) is what makes this real — every Debian
identity surface gets rebranded; what stays is the legal-obligation
minimum (per DFSG + trademark).

Q-016 (substrate-base reconsideration) keeps the question open through
PR 4's substrate survey: would switching to Fedora / openSUSE / Arch /
Nix unlock material new potential? The survey evaluates honestly. If
staying on Debian costs us potential, document the loss. If alternatives
cost us more, document why we stayed.

## Evolution discipline (verbatim operator directive)

> "Everything being able to evolve, before and after"

> "even once installed and configured it will be possible to manage the
> OS like we need to even if we need to add such an additional tool and
> even service possibly or even multiple adapted if need be"

Three implications baked into every SDD:

1. **Pre-install evolution** — the build pipeline itself is versioned,
   forward-compatible, and operator-evolvable. Adding a profile, a
   substrate, a whitelabel target, or a lifecycle hook does not require
   a rewrite.
2. **During-install evolution** — the installer / image-deploy path
   supports new profile options without re-spinning the build.
3. **Post-install evolution** — the running OS can be re-shaped via
   lifecycle-management tools (Q-019 — surface TBD): add a service,
   add a module, swap a model, re-audit perimeter, re-apply a profile
   partial. The OS is not a frozen snapshot; it is a state the operator
   can drive forward in place.

## Sovereignty principles

The OS is sovereign when:

1. The operator can rebuild any image from source on their own hardware.
2. No component phones home by default (popcon, apport, telemetry).
3. Every binary that ships has a documented provenance (apt-sourced,
   compiled-from-source-here, or vendored-with-checksum).
4. The operator can introspect every running service (`systemctl
   status`, `journalctl`, structured logs in known locations).
5. The operator can disable any non-essential component without
   re-installing.
6. Updates are operator-pulled, not vendor-pushed (no auto-update on
   non-security-critical packages by default).
7. The OS works **offline** for its core functions after install
   (inference, state-fabric, perimeter, network split) — internet
   reachability is enrichment, not a precondition.

## Non-goals (sovereign-os, today)

To keep scope tight and stage gates honest:

- We do NOT pick the substrate in PR 1. PR 4 surveys; Gate 2 decides.
- We do NOT commit a brand identity (name / palette / logo) in PR 1.
  Q-003 stays open through Gate 4 at least.
- We do NOT write build scripts in PRs 1–10. Stage 2 (post-Gate-5)
  authorizes that work.
- We do NOT decide ZFS layout, secure-boot posture, kernel choice,
  installer experience in the foundation phase. Those are Stage 2
  decisions informed by the substrate selection.
- We do NOT block on hardware for any of PRs 1–10. ~70 % of foundation
  work is hardware-free; the remainder is gated on E100 (info-hub).
- We do NOT duplicate the SAIN-01 architectural baseline. The 11 epics
  in info-hub are referenced, never re-derived.
- We do NOT pre-commit to LocalAI as the inference backend (Q-017 is
  open; operator-flagged concern that LocalAI may be limiting).
- We do NOT pre-commit to a single first-login assistant pattern
  (Q-018 is open).
- We do NOT decide the lifecycle-management surface shape (Q-019 is
  open).

## Standing rules (carried from selfdef + info-hub)

- **Never minimize, conflate, hack, or take shortcuts** — operator
  quality bar.
- **Verbatim quoting** of operator directives — never paraphrase the
  load-bearing ones; embed sources by file:line.
- **Additive, not destructive** — new direction layers on prior
  direction; never overwrite or drop earlier rules.
- **No `--no-verify`**; no force-push to main; no model-identifier in
  commits / PRs / public artifacts.
- **Stage gates are honest** — no PR opens past a gate without operator
  sign-off.
- **Audit findings get tracked** — `docs/review/phase-N/` ledgers when
  audits run; `docs/decisions.md` `D-NNN` when questions resolve.

## Open questions seeded at PR 1

See [`../decisions.md`](../decisions.md) for the canonical list and the
status-tracking format. The 19 open questions seeded at PR 1 are
**Q-001..Q-019** — operator-confirmed locked decisions + Plan-agent
seed + post-Plan operator additions (Q-016 distro-base reconsideration,
Q-017 inference backend, Q-018 first-login assistant, Q-019 lifecycle
management surface).

## Relationships

- DERIVED FROM: operator `/goal` directive 2026-05-16 (verbatim in info-hub `raw/notes/2026-05-16-user-directive-sovereign-os-arc-opening.md`)
- DERIVED FROM: Plan-agent macro-arc output (info-hub `raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md`)
- DERIVED FROM: selfdef `docs/sdd/011-sovereign-os-arc-opening.md` (cross-repo bridge)
- IMPLEMENTS: SAIN-01 milestone (info-hub `wiki/backlog/milestones/sain-01-sovereign-node.md`) — `sovereign-os` is the build-pipeline materialization of the 11 epics
- BUILDS ON: operator's prior 4-stage SFIF lifecycle directive (info-hub `raw/notes/2026-04-09-user-directive-raw-idea-flow-patterns-standards.md`)
- ENABLES: future `sovereign-os` PRs 2–10 (foundation phase)
- ENABLES: future Stage 2 (build scripts) post-Gate-5
- CONSTRAINS: selfdef Stage 2 (SDD-010) — selfdef-on-SAIN-01 integration is downstream of sovereign-os producing deployable images
