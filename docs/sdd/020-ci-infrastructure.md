# SDD-020 — CI infrastructure (Q-010 resolution)

> Status: **review**
> Owner: cyberpunk042
> Last updated: 2026-05-16
> Closes findings: Q-010 (CI infrastructure: GHA vs self-hosted)
> Derived from: `.github/workflows/test.yml`, `.github/workflows/mdbook-build.yml`,
> running CI state (19 Layer-3 steps + Layer 1 + Layer 2 + shellcheck).

## Problem

Q-010 ("CI infrastructure — GHA vs self-hosted") has been open since
PR 1. CI now exists substantively (`.github/workflows/test.yml` runs
on every push to main + every PR), but no SDD formalizes the choice
or specifies what's deferred.

## Decision: **GitHub Actions only for the foundation phase; self-hosted deferred**

Foundation phase (PRs 1-10 + this session's Stage-2 onset) runs all
CI on GitHub-hosted runners (`runs-on: ubuntu-latest`). No self-hosted
runners, no operator-machine CI, no third-party services.

## Current CI surface

`.github/workflows/test.yml` (every push + PR to `main`):

| Job | Layer | What it runs |
|---|---|---|
| `schema-lint` | Layer 1 | pytest tests/schema + tests/lint (~25 cases) |
| `cross-repo-lint` | Layer 1b | checks out `cyberpunk042/selfdef` as a sibling and runs the `$SELFDEF_REPO_ROOT`-gated contract tests against it |
| `unit` | Layer 2 | pytest tests/unit (~51 cases) |
| `layer3-stage-acceptance` | Layer 3 | 19 nspawn-style bash test scripts (~250+ assertions) |
| `shellcheck` | static analysis | shellcheck against scripts/ (warning-only currently) |

### Cross-repo contract enforcement (`cross-repo-lint`)

The cockpit consumes selfdef's `/metrics` series + scheduler decisions, so
a set of `tests/lint/test_selfdef_*` and `*_lockstep_contract` gates assert
that every `selfdef_*` series our dashboards/alerts reference is really
emitted by selfdef, and that threshold/schema values stay in lockstep.
Those gates **skip** unless `$SELFDEF_REPO_ROOT` points at a selfdef
checkout — so before this job existed they skipped in every CI run (false
confidence: a selfdef rename could flat-line a cockpit panel and CI stayed
green). The `cross-repo-lint` job checks selfdef out read-only (no token —
public-ish, like selfdef's own info-hub checkout) and runs exactly the
`$SELFDEF_REPO_ROOT`-gated files, selected dynamically so new gates
auto-enrol. The checkout is `continue-on-error`: if it fails (token /
visibility), the gates fall back to their skip path — no regression. The
mirror direction (selfdef asserting *it* emits what our cockpit references,
plus runbook-binding) lives symmetrically in selfdef's `coherence` job.

`.github/workflows/mdbook-build.yml` (every push + PR):
- builds mdbook (validation only — no publish step; SDD-002 keeps
  publishing operator-controlled)

## Why GHA-only

1. **Cost**: $0 for public repos
2. **Latency**: green CI in ~3-5 minutes; operator gets fast feedback
3. **Reproducibility**: ubuntu-latest is well-known; CI builds run in
   the same environment as any operator's dev box (mostly)
4. **No infrastructure to maintain**: no self-hosted runner host,
   no token rotation, no security perimeter for the runner
5. **Operator-pullable**: anyone can reproduce the CI run by running
   the test scripts directly on Ubuntu 24.04

## Why NOT self-hosted (yet)

Self-hosted runners would only be needed if:
- **Hardware-conformance Layer 5 tests** need to run on SAIN-01
  hardware. Operator-driven; not CI-gated until much later.
- **Builds need >5min** (large kernel compile, full mkosi image
  build). Currently dry-run-tested only; full builds are operator-
  driven.
- **Sensitive signing operations** need real keys. By SDD-015
  posture-signed-with-PK contract, sovereign-os signing keys NEVER
  live in CI. So even self-hosted wouldn't help here.

## What CI does NOT cover (intentional)

| Layer | Why not in CI |
|---|---|
| Layer 4 (QEMU boot smoke) | requires KVM in CI; operator-driven for now (qemu/ scaffolds exist; gate Stage 2+) <!-- anti-min-waiver: R480 L4-CI-deferral-anchored-to-Stage-2-KVM-CI-runner-acquisition-per-SDD-008-test-harness --> |
| Layer 5 (hardware conformance) | requires SAIN-01 hardware; operator-only |
| Real builds (mkosi build → .raw image) | requires extensive substrate dependencies + ~10-30min CI time; operator-driven via `orchestrate.sh run` |
| Real decommission paths | destructive; SDD-014 testing-scope decision |
| Real install runs | hardware-bound |

## Failure mode + reproducibility

Every L3 test is a self-contained bash script runnable locally:

```sh
tests/nspawn/test_<name>.sh sain-01
```

CI failures reproduce 1:1 on operator's Ubuntu 24.04 box. No
"works on my machine" gap.

## Stage 2+ deferred (Q10-X tracked)

- **Q10-A** — Add a QEMU boot-smoke job using KVM? Recommend yes
  when the build-output `mkosi.raw` is small enough to fit in
  ubuntu-latest's 7GB free disk. Probably Stage 2+ with size-trimmed
  test image.
- **Q10-B** — Self-host CI on SAIN-01 hardware (post-procurement)?
  Recommend: opportunistic — adds a Layer-5 hardware-conformance
  matrix. Until hardware arrives, GHA-only.
- **Q10-C** — Run CI on a Debian Sid runner for trixie-soon validation?
  Recommend: defer — Debian trixie is already stable; the substrate
  is pinned per SDD-019. Adds complexity without value yet.

## Goals

1. **Cheap fast CI** — every push gets full coverage in <5 min.
2. **Operator-reproducible** — every CI step runs locally on Ubuntu
   24.04 with no special setup.
3. **No CI-resident secrets** — signing keys, deploy tokens stay
   operator-side per SDD-015.
4. **Layer 3 is the load-bearing tier** — schema (L1) + unit (L2)
   are fast filters; L3 substantive tests catch real wiring bugs
   (8 caught + fixed via this session's L3 discipline).

## Non-goals

- Does NOT prescribe a CI provider beyond "starts with GitHub
  Actions". Operator can self-host or migrate to GitLab CI later
  if sovereignty pressure rises — CI scripts are GHA-agnostic
  (pure bash + python; no GHA-specific magic).
- Does NOT integrate with proprietary code-scanning / dependency-
  bot services.
- Does NOT deploy artifacts from CI — release publishing stays
  operator-driven.

## Cross-references

- `.github/workflows/test.yml` (the load-bearing CI)
- `.github/workflows/mdbook-build.yml` (docs build validation)
- SDD-008 (5-layer test pyramid — where CI fits)
- SDD-009 (TDD harness bootstrap — Layer 1+2 ship)
- SDD-014 (decommission testing scope — destruction NOT in CI)
- SDD-019 (reproducibility target — sha256sum verification model)
