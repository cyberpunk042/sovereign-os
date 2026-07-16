# Test Performance Audit & Plan — 2026-07-16

> Read this if you are looking at "the tests take too long" — locally
> or in CI. Prompted by the operator's question:
> "The tests are taking too long, lets investigate what is happening
> and what we could do, as much for local as for CI. maybe we can do
> better, or test more focused or listen to what has actually changed,
> or all this and more."
>
> Supersedes: (companion to 008 — a focused CI/test-throughput audit,
> not a session arc)

## TL;DR — where things are

CI wall-clock is **~8 min on every push and every PR** (warm cache). The
surface is genuinely large — **718 crates / 7,881 Rust `#[test]`,
~4,970 Python layer-1 tests, 234 nspawn shell tests** — but the time is
not spent where "large workspace" would suggest. It is spent on
**duplicated work, zero change-awareness, and no intra-job parallelism**.
The 718-crate Rust build is *not* the bottleneck (warm `cargo test` = 3m43s,
release = 1m56s). The critical path is the nspawn job, and ~half of it is
the layer-1 pytest suite running a **second** time.

## Measured picture (warm-cache `main` run #29523253442, 8.0 min wall)

Jobs run in parallel → wall-clock = slowest job.

| Job | Duration | Inside it |
|---|---|---|
| **layer 3 — nspawn** | **7m 55s** ← critical path | 234 tests; one step = **4m 08s** |
| cargo — fmt + clippy + test | 5m 09s | test 3m43s · clippy 63s · fmt 2s |
| layer 1 — schema + lint | 4m 27s | pytest 4m09s (single process) |
| cargo — release build | 1m 56s (warm) | 30-min budget for cold cache |
| shellcheck | 1m 04s | |
| cross-repo / unit / ruff | 13–22s each | |

## Root causes (not symptoms)

- **P1 — Layer-1 pytest runs twice, and the second run is the wall-clock
  tail.** `tests/nspawn/test_makefile_execution.sh` (the 4m08s nspawn step)
  invokes `make lint` (= the whole layer-1 pytest, ~4 min) **and**
  `make l3-fast` (re-runs nspawn tests that already run standalone in the
  same job). Layer-1 already has its own 4m27s job. It is paid for twice,
  and the duplicate is what makes nspawn the longest job.

- **P2 — Nothing is change-aware.** `test.yml` has no `paths:` filter
  (though `mdbook-build.yml` and `release.yml` *do* — the mechanism is
  known, just not applied here). A docs-only or backlog-only PR triggers
  the full 718-crate clippy + test + release build + all 234 nspawn +
  ~4,970 pytest. Recent commit history: `tests/lint` and `docs/**`
  dominate; `crates/**` is touched rarely. SDD-008 §Layer-3 **already
  specified** path-scoped triggers ("every PR that touches
  scripts/profiles/whitelabel/schemas") — the implementation never
  honored it.

- **P3 — No intra-job parallelism.** Layer-1 pytest is single-process over
  ~4,970 tests (no `pytest-xdist`). The nspawn runner is a serial `for`
  loop. `cargo test` uses default threading but there is no `cargo-nextest`.

- **P4 — No modern Rust test tooling.** No `nextest` (2–3× faster + native
  sharding), no `sccache`, no `mold`, no `.cargo/config.toml`. `fmt` +
  `clippy` + `test` are one monolithic job, so a fmt typo reports only
  after a 5-min build.

- **P5 — No `concurrency` cancel on `test.yml`.** Push 3 commits in a row →
  3 full 8-min runs execute to completion; superseded runs keep burning.

- **P6 — Thin local story.** `make test` = lint + unit + **l3-fast only** —
  it skips the Rust workspace entirely. A dev changing a crate has no fast
  "test what I touched" path.

## What to do FIRST — the tiered plan

### Tier 0 — pure wins, low risk (cuts ~8 min → ~5 min)
1. **`concurrency` cancel** on `test.yml` (PR runs only; never cancel
   `main` so each merged commit keeps its green record — mirrors
   `release.yml`'s deliberate `cancel-in-progress: false`). **Shipped in
   this PR** — provably safe by inspection.
2. **De-duplicate the nspawn makefile test** — assert `make lint` /
   `make l3-fast` *wiring* (e.g. `make -n lint` dispatches to
   `pytest tests/schema tests/lint`) without re-executing the full
   suites; the real coverage stays in the dedicated layer-1 / l3 jobs.
   Removes ~4 min from the critical path. **Needs an operator judgment
   call**: is the nested full `make lint` execution load-bearing coverage
   or pure duplication? (I read it as duplication — coverage is already in
   the standalone layer-1 job.)
3. **Split `fmt` + `clippy` into a fast job ahead of `test`** so lint
   failures report in ~1 min instead of behind the 5-min build. (Guard:
   `tests/lint/test_ci_cargo_timeout.py` asserts a `cargo-workspace` job
   exists — keep that name or update the guard in lockstep.)

### Tier 1 — "listen to what changed" (the biggest structural win)
4. **Path filters** (`dorny/paths-filter` or native `paths:`): cargo jobs
   run only when `crates/**` / `Cargo.toml` / `Cargo.lock` change; nspawn
   only when `scripts/**` / `profiles/**` / `whitelabel/**` / `schemas/**`
   / `tests/nspawn/**` change — exactly SDD-008 §Layer-3's original intent.
   Docs-only PR → seconds. (Mind required-status-check plumbing: a skipped
   required job must resolve to "pass" — use a gate job or matrix `if`.)
5. **Affected-crate testing** for Rust: diff → changed crates + reverse
   dependents → `cargo nextest run -p <those>` instead of `--workspace`.

### Tier 2 — throughput when the full suite does run
6. **`cargo-nextest`** — faster, better isolation, native sharding
   (`--partition count:1/N`) across a matrix.
7. **Shard nspawn across a matrix** (e.g. 4 shards) — trivially safe, each
   test is independent.
8. **`mold` linker + `sccache`** (or tuned `Swatinem/rust-cache`).

### Tier 3 — governance so change-aware testing stays safe
9. **Nightly `cron` "full everything"** as the safety net behind the
   affected-only PR path (SDD-008 already envisioned nightly Layer-4; not
   yet wired).
10. **Merge queue** so `main` runs the full suite while PRs run only the
    affected subset.

## Verification gates each risky item needs (do NOT ship blind)

Per the repo's "do not hack / do not flake / verify before claiming" bar:

- **`pytest-xdist -n auto`** is NOT a Tier-0 drop-in. The lint suite has
  **48 tests using `socket`** (bind ports) and **21 tests that write into
  the repo tree** — `-n auto` would race across workers. It requires a
  hardening pass (tmp_path isolation, per-worker ports, repeated `-n auto`
  runs proving determinism) in the full runnable environment before it can
  ship. Staged, not shipped here.
- **De-dup + path-filters** change *what runs when*; each must be paired
  with a merge-queue / nightly full run so the affected-only lane can't
  hide a cross-cutting break.

## The vision — restore SDD-008's own three-tier pyramid

The doctrine (SDD-008) already describes a change-triggered, layered
pyramid with a nightly safety net. Reality drifted into "run everything,
always, serially, twice." The vision is to make the implementation match
the spec:

```
PR fast lane  (<2 min)   → lint(xdist) + unit + AFFECTED crates + AFFECTED nspawn,
                            path-filtered, parallel, concurrency-cancelled
main / merge-queue       → whole workspace via nextest-sharded matrix, all nspawn shards
nightly cron + release   → cold-cache full + reproducibility + QEMU Layer-4 (not yet wired)
```

**The one trade-off, named honestly:** change-aware ("focused") testing
risks missing a cross-cutting break a full run would catch — and this
repo's cross-repo contract gates + "do not minimize" bar mean the affected
subset can't be trusted alone. The mitigation is non-negotiable: the
affected-only PR lane MUST be backed by a full nightly run + a merge-queue
full run. With that net, focused PR testing is both faster and faithful to
the project's own doctrine.

## Repo signposts (file:line pointers)

- CI workflow: `.github/workflows/test.yml` (8 jobs; layer-3 nspawn is the
  114-step critical-path job).
- The duplicated pytest: `tests/nspawn/test_makefile_execution.sh:88`
  (`make lint`) + `:106` (`make l3-fast`).
- Local targets: `Makefile` — `test` (lint + unit + l3-fast, no Rust),
  `ci` (lint + unit + l3), `l3` / `l3-fast`.
- Timeout floor guard: `tests/lint/test_ci_cargo_timeout.py`.
- Dev-deps single-source guard (constrains CI pip installs):
  `tests/lint/test_dev_deps_single_source.py`.
- Original harness doctrine: `docs/sdd/008-test-harness.md` (path-scoped
  Layer-3 trigger + nightly Layer-4 already specified).

## Open items (deferred-by-design)

- xdist hardening pass (needs full runnable env; sibling `selfdef`
  checkout for the cross-repo gates).
- Affected-crate dependency-graph design (coarse path-gate first; precise
  reverse-dep selection second).
- QEMU Layer-4 wiring (SDD-008 §Layer-4 — never implemented).
