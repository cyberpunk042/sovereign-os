# SDD-025 — Observability CLI architecture (Rounds 88-91, 107 codification)

> Status: **review**
> Owner: cyberpunk042
> Last updated: 2026-05-16
> Derived from: SDD-016 (observability bindings — Layer A/B/C),
> SDD-023 (alerts contract), `scripts/sovereign-osctl` cmd_metrics +
> cmd_alerts + cmd_journal + cmd_history (Rounds 88, 89, 91, 107),
> operator verbatim "observable and operable, at all stages of
> lifecycle" + "Reach our ultimate sovereignty".

## Problem

Rounds 88-91 + 107 added four sovereign-osctl verbs that surface
observability data: `metrics`, `alerts`, `journal`, `history`. Their
implementations share substantial structural patterns:

- Log-/metrics-dir resolution (`SOVEREIGN_OS_*_DIR` env > installed-
  system path > per-operator path > clear error)
- `list` / `show <name>` / `tail [N]` / domain-specific verbs
- Bare-name resolution (`show build` resolves to `sovereign-os-build.prom`
  or `build-<ts>.jsonl`)
- Pretty-print + `--json` mode where applicable
- Specific exit codes for distinct error classes

These were grown organically. Future additions (a `drift` verb that
takes both .prom + .json + JSONL inputs? a `summary` verb that fuses
all three? operator-contributed verbs?) need a written contract or
they will diverge.

## Decision: codify the 4-verb shape + the patterns they share

### Verbs in scope

| Verb | Layer | Source of truth | Aggregation | Output formats |
|---|---|---|---|---|
| `metrics` | B | `${SOVEREIGN_OS_METRICS_DIR}/sovereign-os-*.prom` | per-file | text |
| `alerts` | B (derived) | `${SOVEREIGN_OS_METRICS_DIR}/sovereign-os-*.prom` | rule-engine | text + JSON |
| `journal` | A | `${SOVEREIGN_OS_LOG_DIR}/*.jsonl` | per-file | text |
| `history` | A (derived) | `${SOVEREIGN_OS_LOG_DIR}/*.jsonl` | per-run | text |

Symmetry: 2 Layer-A verbs + 2 Layer-B verbs; one raw + one derived
per layer. Future Layer C (operator dashboard) verbs would parallel
the same shape if added.

### Required subverb pattern

Each verb MUST implement subverbs `list` and `show <id>` (or
equivalent — `metrics` uses `show <basename>`; `alerts` is single-shot
so the list/show distinction collapses into the one invocation).

Additional subverbs are verb-specific:
- `metrics` — `tail [N]` + `health`
- `alerts` — `--json` flag (not a subverb)
- `journal` — `tail [N]` + `errors`
- `history` — (currently just list + show; `compare <a> <b>` deferred)

### Dir resolution contract

All four verbs use the same `dir resolution` pattern (codified at the
top of each `cmd_*` function):

```
1. $SOVEREIGN_OS_<VERB>_DIR env override
2. /var/<log|lib>/<sovereign|node_exporter>/... (installed system)
3. ${HOME}/.sovereign-os/...                   (per-operator dev host)
4. clear error: "no <kind> dir found; checked: [list]"
```

Adding a new verb in the same family MUST follow this resolution
pattern. The error message MUST list all candidates tried (operator-
actionable; not a black-box "directory missing" failure).

### Bare-name resolution contract

`show <name>` in any verb MUST accept:
- Exact filename match
- `<name>` (bare) — auto-prefixes/suffixes attempted
- Absolute path (where applicable)

The candidate-search order MUST be deterministic and documented in
the function comment.

### Exit-code contract

| Code | Meaning |
|---|---|
| 0 | Success / no issues found |
| 1 | Substantive non-error signal (e.g., alerts present; drift detected; missing file in show) |
| 2 | Usage error (no-arg subverb, unknown subverb, bad N for tail) |
| 3 | (Reserved for `audit provenance --deep` digest mismatch — SDD-019) |

Verbs MUST use `exit` (not `return`) when signalling non-zero
deliberately, to bypass the common.sh ERR trap (which would otherwise
log "command failed: return 1" — confusing noise for an intentional
signalling exit).

### --json mode contract

Verbs emitting `--json` MUST:
- Emit `[]` (or `{"summary":{...},"entries":[]}` for objects) on empty state.
  NEVER `null`, NEVER an error string. Fleet aggregation tools depend
  on parseable output.
- Have a stable schema: fields are additive only. Removing a field
  requires an SDD revision + version bump in the verb itself (e.g.,
  Round 64 added `version --json` at 0.2.0 in part because `version`
  schema was first-class).
- Document the schema in the verb's docstring/comment.

Currently `--json` mode is locked at the schema level for:
- `version` (SDD-019 + Round 64) — 7-key contract
- `status` (Round 83) — 8-key contract
- `alerts` (SDD-023 + Round 89) — array of {level, metric, value, labels, remediation}
- `audit drift` (Round 111) — {summary, entries[]}

### Test gate contract

Every new observability-family verb MUST ship with:
- Layer 3 nspawn test (synthetic input dir + assertions on each subverb)
- Help text entry (the dispatch surface lint catches missing dispatcher
  entries — `test_sovereign_osctl_dispatch_surface.sh`)
- Layer 1 lint entries where applicable (e.g., the L2 alerts schema
  test pins SDD-023's JSON contract)

### Sovereignty posture

- "observable and operable, at all stages of lifecycle" — the four
  verbs cover both axes (build/install/operate) and both layers (A/B).
- "Reach our ultimate sovereignty" — every verb reads ONLY local files
  (no network), reads no journal that isn't operator-readable, and emits
  no telemetry. Operators audit their fleet using only what sovereign-os
  ships.
- "we always deliver IaC" — the dir resolution is env-overridable, so
  these surfaces run unchanged in containers / chroots / build trees.

## Out of scope

- A `tui` (terminal-UI) layer that wraps the 4 verbs — operators who
  want one can use `watch sovereign-osctl alerts` or similar. Sovereign-
  os ships the data, not the chrome.
- A REST/gRPC server in front of the verbs — Stage 4+ if operator
  demand surfaces. The CLI is the authoritative interface for now. <!-- anti-min-waiver: R480 CLI-authoritative-is-architectural-choice-anchored-to-Stage-4-operator-demand-not-minimization-debt -->
- Multi-host aggregation (fleet view across many machines) — that's
  the Grafana + node_exporter scrape path; sovereign-os ships the
  metrics + dashboard templates, not a fleet manager.

## Cross-references

- SDD-016 — Layer A/B/C foundation
- SDD-023 — Alerts contract (verb #2)
- `scripts/sovereign-osctl` cmd_metrics (Round 88), cmd_alerts
  (Round 89), cmd_journal (Round 91), cmd_history (Round 107)
- `tests/nspawn/test_sovereign_osctl_{metrics,alerts,journal,history}.sh`
- `tests/unit/test_alerts_json_schema.py` — L2 contract for verb #2
- `docs/observability/dashboards/README.md` — 55-metric inventory
- `docs/src/install-runbook.md` § 5b — operator walkthrough
- Operator verbatim (sacrosanct): "observable and operable, at all
  stages of lifecycle", "Reach our ultimate sovereignty"

## Open sub-questions (Q25-X tracked)

- **Q25-A** — Should `journal` and `history` get `--json` mode?
  Recommend: YES, but only when an external operator-script use case
  drives it. Currently the JSONL files themselves are the JSON; bash
  scripts wrap with `jq`.
- **Q25-B** — Should a `summary` (or `dashboard`) verb fuse all four
  into a single screen? Recommend: NO at foundation — `status` already
  gives an at-a-glance overview; adding another aggregator dilutes
  the surface. Operators chain verbs in scripts when needed.
- **Q25-C** — Should every new top-level verb in sovereign-osctl
  follow the same 4 patterns (dir resolution, bare-name show, exit
  codes, --json schema)? Recommend: YES for any observability-family
  verb; NO for fundamentally different verb classes (e.g., `decommission`
  is destructive + interactive; `inference start` spawns daemons).
- **Q25-D** — Should `metrics show --json` and `journal show --json`
  emit parsed metric/event objects instead of raw .prom/.jsonl content?
  Recommend: NO at foundation — `metrics show` is meant for human
  reading; the JSON output of `alerts` already provides the structured
  rule-derived view.
