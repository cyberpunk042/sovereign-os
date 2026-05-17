# SDD-028 — Canonical-YAML source + auto-rendered consumer surfaces

> Status: **review**
> Owner: sovereign-os core
> Last updated: 2026-05-17
> Closes findings: none (pattern codification, no F-findings)
> Derived from: R202 (phases.yaml canonical source) + R203 (auto-rendered operator doc)

## Mission

Codify the pattern adopted in R202/R203 — *single canonical
YAML source consumed by multiple parallel surfaces (shell inventory,
shell dry-run executor, markdown operator doc, schema lint, freshness
gate)* — so future work that introduces new operator-facing data
follows the same shape and reaps the same drift-elimination
properties.

## Problem

Rounds R160 (phases.sh) and R201 (run.sh) each carried an inline
PHASES array describing the master spec § 12 5-phase pipeline.
Duplicated tables across multiple files imply two failure modes:

1. **Authoring drift.** When a phase changes, the author must
   remember every consumer. The R201 L3 test caught this with a
   count-match drift guard, but a count-match check only catches
   shape drift, not content drift (e.g. renaming an artifact in one
   file but not the other).
2. **Documentation drift.** The operator-readable master spec doc
   (`docs/src/sain-01-master-spec.md`) hand-rendered each phase's
   description; when a phase artifact set changed, the doc had to
   be manually re-edited. CI couldn't catch the gap because there
   was no shared source the doc was derived from.

The same shape exists in many places in this repo: profile YAML +
profile docs, model catalog + model doc, hardening drop-in sets +
the hardening-posture SDD-024 explanation, etc.

## Required coverage

The pattern must:

1. Provide ONE canonical machine-readable source (YAML; could be
   JSON or TOML where idiomatic, but YAML matches the rest of the
   repo).
2. Provide a single parser/loader (Python; `pyyaml` is already a
   build-time dep) that consumers invoke; consumers never reach into
   the YAML directly with `grep`/`yq` (avoids inline-format coupling).
3. Provide a schema lint at Layer 1 enforcing the canonical source's
   invariants (so authoring drift fails CI before it ships).
4. Provide a freshness gate at Layer 3 for rendered artifacts — a
   `--check` mode that diffs the rendered file against what the
   renderer would emit fresh; CI fails if the file is stale.
5. Provide a `GENERATED` banner in every rendered artifact (so
   readers know not to edit it directly).

## Goals

- Eliminate drift between data tables and their rendered consumer
  surfaces by making drift structurally impossible (every consumer
  re-reads the canonical source on each invocation).
- Lower the cost of changing a multi-surface concept: edit the
  canonical YAML, re-run the renderer, the shell scripts auto-pick-up
  the new shape.
- Preserve operator readability: the rendered doc is committed to
  the repo (not generated at CI time only), so an operator browsing
  GitHub or a local clone sees the doc without invoking anything.

## Non-goals

- We are NOT advocating dataclass / pydantic models for every YAML
  in the repo. Keep the schema lint lightweight (positional
  assertions in unittest).
- We are NOT migrating every existing duplicated table to this
  pattern eagerly. R202 + R203 migrated the bootstrap-phase surface
  because it had three consumers (shell + shell + doc); single-
  consumer tables stay inline.
- We are NOT generating shell scripts from YAML. The shell scripts
  remain authored by hand; only the *data tables they consume* live
  in YAML.

## Reference implementation (R202 + R203)

| Layer | Artifact | Role |
|-------|----------|------|
| Source | `config/bootstrap/phases.yaml` | Canonical machine-readable phase table |
| Loader | `scripts/bootstrap/lib/load-phases.py` | Emits `id\|name\|description\|artifact...` stream for shell |
| Inventory consumer | `scripts/bootstrap/phases.sh` | Reads loader output; reports artifact presence |
| Executor consumer | `scripts/bootstrap/run.sh` | Reads loader output; emits DRY-RUN plan |
| Doc consumer | `scripts/bootstrap/lib/render-phases-md.py` | Reads YAML directly; emits `docs/src/bootstrap-phases.md` |
| Schema lint (L1) | `tests/lint/test_bootstrap_phases_yaml.py` | Asserts YAML invariants (count, IDs, no pipe chars, all paths exist, pre/post lists non-empty) |
| Freshness gate (L3) | `tests/nspawn/test_bootstrap_docs.sh` | `--check` rc=1 if rendered doc is stale |

## When to apply this pattern

Apply when ALL of the following hold:

1. The same data table is consumed by ≥2 surfaces (script + doc, or
   ≥2 scripts).
2. The data table is operator-relevant enough that the rendered
   surface needs to be committed (not built at CI time).
3. The table's row count is small enough that hand-authoring the
   YAML is faster than building a code generator (rule of thumb:
   <50 rows).

Do NOT apply when:

- The data lives in only one consumer (no drift risk).
- The data is computed dynamically (e.g. resident-model list — read
  from disk, not authored).
- The data IS the rendered output (e.g. a man page authored in
  markdown is itself the source).

## Future candidate migrations

These tables fit the criteria above and may migrate in future rounds:

- **Profile metadata** (`profiles/*.yaml` + `docs/src/per-profile-*.md`)
  — profile properties surface in 5 docs + the wizard + osctl
  `profiles show`.
- **Model catalog** (`models/catalog.yaml` already canonical; doc
  rendering could be auto-generated to eliminate hand-written
  per-model description drift).
- **Verify-grid checks** (`scripts/bootstrap/verify.sh` enumerates
  6 checks inline; the SDD-019 § 22 doc + the trajectory doc both
  describe the 6 checks separately).

Migrations are opportunistic — they happen when a round naturally
touches the affected table, not as a dedicated cleanup arc.

## Cross-references

- SDD-019 — Reproducibility target (drives the `--check` posture for
  rendered artifacts — same shape as `09-image-verify.sh` sha256sums
  verification)
- SDD-025 — Observability CLI architecture (parallel-verb contract
  pattern; canonical-source pattern complements it on the data side)
- R202 commit — phases.yaml + load-phases.py
- R203 commit — render-phases-md.py + bootstrap-phases.md

## How operators ratify

The pattern is in use at HEAD. Future tables that meet the migration
criteria above should land with:

1. The YAML source under `config/<area>/` (or analog location).
2. A Python loader if shell-consumed; direct YAML read if Python-
   consumed.
3. A Layer 1 schema lint (unittest, runs under the existing pytest
   sweep).
4. A Layer 3 freshness gate (shell test calling `--check`) IF the
   pattern renders to a committed artifact.
5. A `GENERATED` banner in every rendered file.
