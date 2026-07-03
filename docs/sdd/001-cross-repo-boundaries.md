# SDD-001 — Cross-repo boundaries: contract between sovereign-os, info-hub, selfdef

> Status: **accepted** (boundary contract; locked by PR 2)
> Owner: operator-supervised; agent-authored
> Last updated: 2026-05-16
> Closes findings: none (foundational)
> Derived from: charter (`docs/sdd/000-charter.md`); Plan-agent macro-arc (info-hub `raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md`); selfdef SDD-011

## Problem

Four repos collaborate on the sovereign-OS arc — `sovereign-os` (this
repo) BUILDS the OS, `selfdef` RUNS on the OS, `devops-solutions-information-hub`
SYNTHESIZES the knowledge baseline, `root-ghostproxy` is dormant. Their
responsibilities overlap only where the architecture explicitly chooses;
silent overlap is scope creep. Cross-references between them are
inevitable but can rot, conflict, or duplicate authority if not
disciplined.

This SDD locks the **boundary contract**: what flows across repos, what
doesn't, what reference shapes are allowed, what's forbidden, and how
the contract is verified.

## Required coverage

### 1. Per-repo responsibility surface (canonical)

| Repo | Authoritative for | Non-authoritative |
|---|---|---|
| **sovereign-os** | OS-image generation pipeline; profile schema; whitelabel mechanism; TDD harness; lifecycle-management tools | Architectural design ABOUT the OS (that's info-hub); runtime security policy (selfdef) |
| **info-hub** | Architectural design + L0/L1/L2/L3 knowledge; SAIN-01 milestone + 11 epics; operator-directive verbatim; comparison + recommendation matrices | Implementation artifacts (scripts / configs / build tooling — those live in sovereign-os) |
| **selfdef** | Security daemon + agent-guard module + 12 notifier channels + persistent escalation engine; security threat model; runtime-defense decisions | OS-image construction; profile schema (sovereign-os owns); architectural baseline (info-hub owns) |
| **root-ghostproxy** | (dormant at the time this contract locked; received /view + /questions skill installs in a prior arc. **Re-activated 2026-07-03 as an endpoint-mode consumption dependency — see SDD-046**, which decides the re-activation this SDD scoped out) | — |

### 2. Cross-repo verbs (what "flows" between repos)

Three verbs lock the dependency direction:

#### `sovereign-os` **CONSUMES FROM** `info-hub`
- Architectural baseline (SAIN-01 milestone, 11 epics, L1–L3 syntheses) is the design sovereign-os materializes.
- Operator-directive verbatim provenance is L0 evidence sovereign-os SDDs cite.
- Plan-agent macro-arc output is the authoritative scaffold for the 10-PR foundation phase.

#### `selfdef` **CONSUMES FROM** `info-hub` + `sovereign-os`
- From info-hub: the SAIN-01 architectural baseline (constrains the Stage-2 integration design in selfdef's SDD-010).
- From sovereign-os: the deployable OS images selfdef runs on (Stage-2 integration is gated on sovereign-os producing artifacts).

#### `info-hub` **OBSERVES** `sovereign-os` + `selfdef`
- info-hub's L4 lessons distill cross-cutting findings from sovereign-os + selfdef + AICP observations.
- info-hub does NOT directly drive implementation in either repo.

**Reverse flows are forbidden by default.** sovereign-os does not author
info-hub knowledge; selfdef does not author OS-image construction.
Exceptions go through info-hub's L0 directive log and a dedicated
boundary-violation note.

### 3. Allowed reference shapes

When sovereign-os references info-hub or selfdef artifacts:

| Shape | When | Example |
|---|---|---|
| **Path-only symbolic** | Default — references by relative path within the upstream repo | `info-hub wiki/backlog/milestones/sain-01-sovereign-node.md` |
| **Path + commit-pin** | When reproducibility matters (release-tag inclusions; SDD that depends on specific epic phrasing at the time of authoring) | `info-hub@1f2a3b4 wiki/sources/src-bitnet-b158-ternary-llm.md` |
| **Permalink (GitHub blob URL)** | When the document is operator-facing and a stable URL is preferable to a path that may move | `https://github.com/cyberpunk042/devops-solutions-information-hub/blob/main/wiki/...` |

Forbidden shapes:
- **Verbatim copy** of more than a few sentences from another repo (use a citation + short quote; if more is needed, the artifact belongs in the source-of-truth repo).
- **Cross-repo edits** without operator authorization (no agent-driven PRs that touch info-hub + sovereign-os in the same change without explicit operator direction).

### 4. Reference rot — CI guard

A CI workflow in this repo (PR 3 or PR 10 lands the workflow file)
validates that:

- Every reference to `info-hub <path>` resolves against a known-good
  commit of `cyberpunk042/devops-solutions-information-hub` (HEAD of
  `main`, or the pinned SHA if one is specified).
- Every reference to `selfdef <path>` resolves similarly.
- Broken references fail the build with a precise error: file + line +
  reference shape + what's missing.

The guard's scope: `*.md` files in `docs/sdd/`, `docs/handoff/`,
`docs/review/`, `docs/decisions.md`, plus `README.md` and
`ARCHITECTURE.md` at root.

### 5. Commit-pinning posture (Q-011 — partial resolution)

Q-011 from PR 1 asks: how does sovereign-os reference specific selfdef
/ info-hub commits — symbolic refs, hard-pinned SHAs, or hybrid?

**Working resolution (locked at Gate 1)**: **hybrid**, with explicit
rules per artifact-type.

- **SDDs** (`docs/sdd/*.md`): symbolic references by default. CI guard
  verifies path existence at HEAD. Hard-pin only when the SDD depends
  on specific phrasing at the time of authoring (rare; e.g., quoting
  a milestone's exact text).
- **Decisions log** (`docs/decisions.md`): symbolic references; decision
  text quotes the source phrase verbatim, so the reference rotting
  doesn't change the decision's interpretation.
- **Handoffs** (`docs/handoff/*.md`): symbolic; handoffs are
  point-in-time and acknowledge upstream evolution.
- **Review ledgers** (`docs/review/phase-N/`): hard-pin to the commit
  the audit ran against. Audits are forensic; reference stability
  matters.
- **Release tags**: hard-pin all cross-repo references at tag time
  (release notes capture the upstream SHA explicitly).

Trade-off context (Plan-agent's table on this):

| Approach | Pro | Con |
|---|---|---|
| Hard-pin everything | Reproducible | References stale; manual upkeep |
| Symbolic everything | Always fresh | Can rot silently; CI must guard |
| **Hybrid (chosen)** | Fresh where evolution is desired; stable where audit / release demands it | Requires the discipline to apply the right shape per artifact-type |

This resolution **partially** answers Q-011 (the per-artifact rule).
The full Q-011 closure happens when the CI guard ships (PR 3 or PR 10
per the workflow-file PR) — at which point Q-011 marks
**answered (D-NNN, YYYY-MM-DD)** and the decisions log appends the
D-NNN entry.

## Goals

1. **No silent overlap**: each repo's authoritative surface is named
   explicitly; sovereign-os SDDs do not re-derive info-hub knowledge.
2. **Direction-of-dependency honesty**: the CONSUMES-FROM / OBSERVES
   verbs are explicit; reverse flows are forbidden by default.
3. **Reference shape discipline**: path-only, path+pin, or permalink —
   per the per-artifact rule.
4. **CI-verified references**: broken references fail the build;
   reference rot doesn't accumulate silently.
5. **Operator-friendly cross-navigation**: README + ARCHITECTURE link to
   the canonical info-hub and selfdef artifacts; a fresh reader can
   trace the dependency chain in one click.

## Non-goals (this SDD)

- Does NOT pick a commit-pinning automation (CI workflow YAML); that
  lands in PR 3 (mdbook + MCP template + CI) or PR 10 (TDD harness's
  schema/lint stage).
- Does NOT define info-hub's or selfdef's internal organization; each
  repo owns its own conventions.
- Does NOT decide how root-ghostproxy re-activates (out of scope).
  *(Decided later by SDD-046 — endpoint-mode binding, 2026-07-03.)*
- Does NOT preempt the LocalAI reconsideration (Q-017) — that's a
  separate inference-backend-stack SDD, not a boundary concern.

## Open questions

- **Q-A** — Should the CI guard run on every PR (mandatory gate), or
  only on release-tag PRs (advisory elsewhere)? Plan-agent recommends
  every PR; trade-off is build-time cost vs reference freshness.
- **Q-B** — Where does the CI workflow file live (`.github/workflows/`)?
  Naming convention?
- **Q-C** — How are info-hub URLs/paths configured (env var? CI
  config? hardcoded in workflow)? Trade-off is portability vs
  explicit-ness.
- **Q-D** — Should sovereign-os SDDs explicitly version-pin to a
  selfdef SDD when describing a selfdef-on-SAIN-01 boundary? (e.g.,
  "selfdef SDD-010 v1.2 covers this"). Helps audit trail; adds
  upkeep cost.

These get resolved before Stage Gate 1 (after PR 3) OR at PR 10 (TDD
harness scope).

## Way forward

1. PR 2 (this PR): document the contract via this SDD + ARCHITECTURE.md
   + handoff anchor 001.
2. PR 3 (next): mdbook layout consumes the references; MCP config
   template includes the info-hub + selfdef paths.
3. Stage Gate 1 (after PR 3): operator reviews PRs 1–3 holistically;
   confirms repo rhythm matches selfdef; locks the boundary contract.
4. PR 10 (TDD harness bootstrap): ships the CI reference-guard
   workflow (schemas + lint + cross-repo refs).
5. Q-011 final closure happens at the CI-guard PR, with a D-NNN entry
   in `docs/decisions.md`.

## Cross-references

- Charter: `docs/sdd/000-charter.md`
- Architecture: `ARCHITECTURE.md` (PR 2, this PR)
- Decisions log: `docs/decisions.md` D-001 / D-002 / D-003 (PR 1) +
  future D-NNN closing Q-011
- Plan-agent macro-arc (PR 2 spec): info-hub `raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md` § PR 2
- Selfdef SDD-011 (cross-repo bridge from selfdef side):
  `cyberpunk042/selfdef/docs/sdd/011-sovereign-os-arc-opening.md`
- Selfdef SDD-010 (selfdef-on-SAIN-01 stub; downstream of
  sovereign-os producing images):
  `cyberpunk042/selfdef/docs/sdd/010-selfdef-on-sain01.md`
- SAIN-01 milestone (info-hub authoritative baseline):
  `cyberpunk042/devops-solutions-information-hub/wiki/backlog/milestones/sain-01-sovereign-node.md`
