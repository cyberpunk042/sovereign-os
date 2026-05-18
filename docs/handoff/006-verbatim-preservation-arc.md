# Handoff 006 — Verbatim-preservation arc (R355-R440)

> **Status**: structurally mature (perpetual mandate continues)
> **Last updated**: 2026-05-18 (R440 milestone — extends R430 to cover R431-R439; +10 more rounds, +9 lints, +159 assertions, +1 bidirectional-consistency lint; cumulative since R400: +40 rounds, +27 lints, +559 assertions, +14 bidirectional-consistency lints)
> **Owner**: sovereign-os core
> **Predecessor handoff**: 005-master-spec-materialization-arc.md

## What this arc was

Operator issued the perpetual `/goal` directive on 2026-05-18:

> **"continue till you meet ALL MY REQUIREMENTS without MINIMIZING or
> rephrasing or compressing or conflating.. RETURN REREAD ALL THE RAW
> DUMP AND REPROCESS IF YOU NEED or JUST ask me question if you are
> lost"**

This arc (40 rounds, R355 through R394) mechanized that contract at
push-time across the entire operator-verbatim content surface from
both raw dumps:
- `info-hub/raw/dumps/2026-05-15-sain-01-master-spec-other-conversation-transposition.md` (1139 lines)
- `info-hub/raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md` (404 lines)

Plus operator-stated content from the 2026-05-17 hook drop and the
`/goal` directive itself.

## What got built

### 7 operator-pull discoverable verbs

Each verb surfaces operator-verbatim content as queryable / verifiable
state. Built incrementally across R355-R366:

| Verb | Round | Purpose |
|------|-------|---------|
| `architecture-qa questions/gotchas/concepts/show/search` | R355/R357/R360/R361/R362/R363/R364/R375/R379 | §13 Q&A + §14 Gotchas + 27 concepts across 19 master spec sections |
| `ccd-pinning show/verify/recommend` | R356 | §19.2 dual-CCD topology + live PID drift check |
| `state-fabric layout/verify/scaffold` | R358 | §7.1 file-state matrix + §7.2 ZFS optimizations |
| `network-topology show/verify/scaffold` | R359 | §8 ASCII diagram + §8.1 NIC configs |
| `coverage axes/show/audit/search` | R365 | 32 operator-stated demand axes mapped to verbs |
| `repl modes/show/exec/shell` | R366 | 4-level (Python/System/GPU/LLM) operator-pull REPL |
| `verbatim-render render/summary/manifest` | R369 | Consolidated render of entire 82-item catalog |

### 2 meta-verbs

| Verb | Round | Purpose |
|------|-------|---------|
| `doctrine-status status/tally/run` | R376 | SDD-037 lint family health at a glance |
| `quarterly-review snapshot/grade/recent` | R377 | Composed coverage + doctrine + verbatim + mandate audit |

### 1 static published doc

`docs/src/verbatim-surface.md` (770+ lines) — mdbook-published
operator-readable render of the entire 82-item catalog with drift
detection (R370).

### 1 codified doctrine

`docs/sdd/037-verbatim-preservation-doctrine.md` (R367) — 7-section
SDD codifying the verbatim-preservation pattern future agents follow.
Lists the 3 named failure modes (silent paraphrase / silent compression
/ silent conflation) + 7-step contract for every verbatim round +
implementation deviation documentation requirement.

### 6 fabrication-catch L1 lints

The "fabrication-catch sextet" — 6 cross-reference validators catching
agent fabrication across 6 distinct citation surfaces:

| Surface | Round | Catch direction |
|---------|-------|-----------------|
| `master spec §N` section refs | R368 | catalog → spec |
| `E.M` mandate row refs | R371 | catalog → mandate (caught 2 bugs) |
| `sovereign-osctl <verb>` + SDD refs | R372 | catalog → osctl + SDD (caught 16 bugs) |
| Cross-catalog phrases | R373 | catalog ↔ catalog (caught 2 bugs) |
| `R<N>` round numbers + git history | R374 | catalog → git history |
| SDD reachability | R380 | SDD → catalog (inverse of R372) |

R368+R371+R372+R373+R374+R380 collectively caught **20 real bugs** at
ship time (E2.M21 mandate-row duplicate + A-06 fabricated row +
16 fabricated verb refs + C-16 missing 2 hardware SKUs).

### 4 supporting L1 lints

- R367 SDD-037 doctrine + catalog floors (12 assertions)
- R370 static-doc drift detection (9 assertions)
- Bidirectional Tetragon 4-binary allowlist consistency (within R367)

## Final state (updated through R440 — 86-round milestone)

```
Coverage:  32 ✓ shipped, 0 partial, 0 TODO (of 32 total)
Doctrine:  61 lints / 941 assertions / 30 bugs caught
Verbatim:  82 catalogued items / ~537 operator-exact phrases
           mechanized at push-time across 19 master spec sections
Operational artifacts pinned: 45+ files (R387-R439)
Systemd Descriptions pinned: 4 (Trinity-side identity, R397)
Trinity-side pinning: COMPLETE (Pulse + Weaver + Auditor scripts +
                                  Descriptions + ZFS + VFIO + Tetragon)
Catalogue-source pinning: COMPLETE (architecture-qa concepts +
                                     coverage-map axes + selfdef bridge)
Doc-family pinning: COMPLETE (handoffs + SDDs + decisions + mandate)
Bidirectional-consistency lints: 18
  R367 (Tetragon writer↔allowlist)
  R373 (cross-catalog)
  R384 (handoff INDEX)
  R399 (ZFS ARC writer↔verify-grid)
  R403 (router TIER_ENDPOINTS↔start-*.sh ports)
  R410 (verify.sh check_NN↔verify-grid.yaml ids + name fallback)
  R412 (timer↔hook↔service triangle)
  R417 (mixin.id↔filename + R415-hardening↔role-server packages)
  R419 (Tetragon policy LOAD↔VERIFY name+dir)
  R420 (Weaver atomic-state↔tank/context dataset)
  R421 (Guardian service ReadWritePaths↔script write paths)
  R422 (runtime_profile.id↔filename + engines↔R404 adapters)
  R424 (schema↔conformance test↔data files triangle)
  R425 (phases.yaml↔phases.sh↔render-md.py↔artifact paths)
  R426 (whitelabel legal_floor↔render.py LEGAL_FLOOR_PATTERNS)
  R427 (catalog tiers↔Trinity set + verified-real↔hf_repo_id)
  R428 (4-way default-model ring: build↔backend↔catalog↔start)
  R433 (selfdef-tune lib exports↔build-bitnet consumer reads)
Test count: 1450 (all green)
Mandate:   217+ rows / ~178KB
Grade:     A (stable across 86 rounds)
```

## R431-R439 extensions (after R430 handoff refresh)

After R430 milestone consolidation, R431-R439 added 9 more rounds
pivoting from build/runtime infrastructure to CATALOG SOURCES,
INTELLIGENCE VERBS, and DOC-FAMILY pinning:

| Round | Surface | Lint count |
|-------|---------|------------|
| R431 | architecture-qa.py catalog (27 C-NN concepts + Q-NN + gotchas) | 21 |
| R432 | coverage-map.py 32-axis demand-coverage catalog | 18 |
| R433 | selfdef-tune.sh cross-repo bridge detailed contract + bidir #18 | 22 |
| R434 | operator-pull intelligence verbs (doctrine-status + quarterly-review + morning-brief + next-action-advisor) | 17 |
| R435 | handoff document content contract (R384 extension) | 16 |
| R436 | operator-mandate doc structural invariants (meta-pinning) | 15 |
| R437 | selfdef cross-repo bridge surface (SD-R<N> integration) | 17 |
| R438 | SDD content + INDEX extended invariants (60-lint MILESTONE) | 15 |
| R439 | decisions.md audit-trail content + format | 18 |

R431-R439 added 9 new L1 lints + 159 assertions + 1 new bidirectional-
consistency lint (R433 selfdef-tune↔build-bitnet). Crossed 60-lint +
900-assertion thresholds.



## R401-R429 extensions (after R400 handoff refresh)

After R400 milestone consolidation, R401-R429 added 30 more rounds
extending operational-artifact pinning across the entire build pipeline,
inference Trinity, lifecycle hooks, runtime profiles, and bidirectional
ring closures. 13 new bidirectional-consistency lints (R403-R428).

| Round | Surface | Bugs caught |
|-------|---------|-------------|
| R401 | network-vlan-config §8.1 Zero-Trust dual-NIC | — |
| R402 | Trinity start scripts (start-pulse/logic-engine/oracle-core) | — |
| R403 | router classify + TIER_ENDPOINTS + bidir w/ start scripts | — |
| R404 | backend adapters (bitnet.py/vllm.py/llama_cpp.py) | — |
| R405 | 9-step build pipeline contract | 3 (#23-#25 DRY_RUN gaps) |
| R406 | substrate adapters (mkosi-emit / live-build-emit) | — |
| R407 | whitelabel render engine SDD-007 + SDD-006 § Legal floor | — |
| R408 | image-sign secure-boot SDD-015 + operator-key-mandate | — |
| R409 | image-build (step 07) + image-verify (step 09) SDD-019 | — |
| R410 | verify.sh ↔ verify-grid.yaml § 22 implementation bidir | — |
| R411 | lifecycle hooks (pre/during/decommission) | 3 (#26-#28 incl 2 mandate-grade) |
| R412 | recurrent hooks + timer↔hook↔service triangle | — |
| R413 | sovereign-osctl Q-019 sacrosanct + 25-subcommand dispatch | — |
| R414 | cloud-init user-data templates Q-018 + ZT | 1 (#30 active-whitelabel) |
| R415 | server + workstation hardening hooks SDD-023 + § 8 ZT | — |
| R416 | systemd fleet defense-in-depth R171 (24 service units) | — |
| R417 | profile mixins + R415-hardening↔role-server bidir | — |
| R418 | build/lib/* infrastructure contract (foundation R397-R417) | — |
| R419 | Tetragon policy LOAD ↔ VERIFY bidirectional | — |
| R420 | Weaver atomic-state ↔ tank/context dataset bidir + § 21 | — |
| R421 | Guardian Loop service↔script + § 10/§ 17 + bidir | — |
| R422 | runtime profiles § 18 + 3-way bidir (id+engine+hw) | — |
| R423 | verbatim-render aggregator R369 doctrine | — |
| R424 | JSON-schema set consistency + schema↔test↔data triangle | — |
| R425 | bootstrap phases.yaml § 12 + 4-way artifact bidir | — |
| R426 | whitelabel/default.yaml + legal_floor↔render.py bidir | — |
| R427 | model catalog content + Trinity-tier bidir | — |
| R428 | Pulse build-bitnet.sh § 15-16 + 4-way model bidir | — |
| R429 | Debian preseed + cloud-init R414 bidirectional | — |

R401-R429 added 29 new L1 lints + 572 assertions + 7 new bugs caught
+ 13 new bidirectional-consistency lints. Operator-mandate-grade
safety violation #27 (secure-wipe-context.sh missing SOVEREIGN_OS_
CONFIRM_DESTROY) was the highest-impact catch.

## R395-R399 extensions (after R381 handoff)

After R381 handoff and R395 doc refresh, R396-R399 extended
operational-artifact pinning by 4 more rounds:

| Round | Surface | Bugs caught |
|-------|---------|-------------|
| R396 | ZFS dataset §4.1 spec (3 datasets × recordsize+compression+copies) | — |
| R397 | Trinity systemd unit Descriptions (4 .service files) | — |
| R398 | VFIO-bind §4.3 GRUB cmdline (amd_iommu=on + iommu=pt + PCI IDs) | — |
| R399 | ZFS ARC clamp §4.2 (128 GiB = 137438953472 bytes, bidirectional) | — |

R396-R399 added 4 new L1 lints + 43 assertions + 1 new bidirectional-
consistency lint (R399 ZFS ARC writer ↔ verify-grid verifier).

## Post-R381 extensions (R382-R394)

After the initial R355-R380 verbatim-preservation arc, R381 shipped
this handoff doc. R382-R394 extended the lint/pinning surface
substantially:

| Round | Surface | Bugs caught |
|-------|---------|-------------|
| R382 | `layers` verb (11 operator-verbatim layers + typo discoverability) | — |
| R383 | osctl --help R-arc verb discoverability lint | 1 |
| R384 | handoff INDEX consistency lint | 1 |
| R385 | config/*.toml.example quality lint | — |
| R386 | unified `search` verb across 3 catalog taxonomies | — |
| R387 | profiles/sain-01.yaml verbatim pin (§2.2 KCFLAGS + §1.1 SKUs) | — |
| R388 | whitelabel/default.yaml verbatim pin (§3.2 motd) | — |
| R389 | bootstrap YAML verbatim pin (§22 verify-grid + §12 phases) | — |
| R390 | Tetragon policy verbatim pin (§4.1 TracingPolicy) | — |
| R391 | friction-audit verbatim pin (§5.1) | 1 (ZFS pool check missing) |
| R392 | guardian-core.py pin (§10.1 Trinity Auditor) | — |
| R393 | atomic-state.py pin (§21.1 Trinity Weaver) | — |
| R394 | build-bitnet.sh pin (§16+§9.1+§15 Trinity Pulse) | — |

R382-R394 added 11 new L1 lints + 100 assertions + closed Trinity-
side operational pinning (3-of-3 Trinity scripts now pinned at L0
artifact layer).

## 14 enforcement layers (updated through R394)

The /goal contract is mechanized across 14 layers:

1. **L0 catalog data** — operator-verbatim text in Python catalog files
2. **L0 build profile data** — profiles/sain-01.yaml KCFLAGS+SKUs (R387)
3. **L0 whitelabel render data** — whitelabel/default.yaml motd (R388)
4. **L0 bootstrap YAML data** — verify-grid + phases (R389)
5. **L0 Trinity-side scripts** — Pulse + Weaver + Auditor (R392-R394)
6. **L1 doctrine** — SDD-037 structure pinned (7 required sections)
7. **L1 catalog hygiene** — IDs / floors / status enum / monotonic
8. **L1 format** — spec_ref / mandate / verb / round format patterns
9. **L1 cross-reference outbound** — catalog cites real §N / E.M /
   verb / phrase / R<N>
10. **L1 cross-reference inbound** — SDDs reachable from catalogs
11. **L1 bidirectional** — Tetragon allowlist C-14 ↔ shipped script
12. **L1 cross-catalog** — 11 phrase consistency pairs
13. **L1 git-history** — R350+ rounds need backing commits
14. **L1 discoverability** — R-arc verbs visible in --help (R383)
15. **L3 phrase layer** — per-entry operator-exact phrase preservation
16. **Static doc layer** — mdbook-published, drift-protected

## Catalog state

### Master spec sections covered as concepts (19 distinct)

§1, §1.1, §1.2 (Hardware Infrastructure)
§2, §2.1, §2.2 (Sovereign Forge Stage 1 Kernel)
§3 (Storage Architecture)
§3.2 (Sovereign Forge Package List)
§4, §4.1 (Security Perimeter Tetragon)
§5 (Operational Logic / Vibe Manager)
§6 (Implementation Ledger)
§7.1, §7.2 (State Fabric + ZFS Optimizations)
§9, §9.1 (Container Build AVX-512)
§10 (Native Guardian Event Loop)
§11 (Consolidated Execution Strategy)
§15-16, §15.1, §16.1 (1-Bit Paradigm + Hardware Fusion)
§17.1 (Layered Responsibility Mapping)
§18 (Load Balancing × 3 profiles)
§19, §19.1 (Dual-CCD Topology)
§20, §20.1, §20.2 (Wasm-to-AVX-512 AOT)
§21, §21.1 (Atomic State Transition Protocol)
§23 (Summary of System Cohesion)
Block 6 (Trinity Genesis Modules 1/2/3)
+ dump-tail (DFlash + 2 HF model candidates)
+ macro-arc plan post-Plan refinements #1/#2/#3/#4

Separately covered via dedicated verifier verbs:
§8, §8.1 (network-topology verbatim)
§19.2 (ccd-pinning verbatim)
§22 (bootstrap-verify-grid verbatim)
§13, §14 (architecture-qa questions/gotchas)

### Coverage-map axes (32 catalogued)

Every operator-stated demand from the hook drop has ≥1 implementing
verb. Including operator-stated CONTRACT axes:
- A-31: Senior Architect mindset / workflow / quality bar
- A-32: Operator delegation of break-down + planify + SDD+TDD

## How to extend

Future operator hook drops with new content follow this pattern:

1. **Identify** operator-verbatim content (raw dump section / hook
   drop / mandate row)
2. **Surface** as discoverable operator-pull verb (pick the right home
   per shape: architecture-qa for explanatory, coverage-map for
   demand axes, dedicated verifier verb for executable state)
3. **Preserve** operator-exact text (typos / punctuation / exact
   numbers / list order + cardinality)
4. **L3 verbatim phrase assertions** (≥5 specific phrases per entry)
5. **Bidirectional consistency** for code-bearing entries (operator
   text in BOTH catalog AND shipped script)
6. **Implementation deviation documentation** when shipped refines
   operator's exact text
7. **Coverage-map back-link** via A-NN entry

SDD-037 codifies this 7-step contract.

## What this arc explicitly does NOT do

- Does not ship Stage 2+ build implementations (out-of-scope per
  macro-arc plan)
- Does not modify operator's raw dump files (sacrosanct L0)
- Does not promise "complete" — the perpetual mandate continues by
  design (operator's "continue endlessly" / "DO not stop")
- Does not capture verbatim text that's stylistic-only ("I guess",
  "honestly" hedges without semantic weight)

## Critical files

| Path | Purpose |
|------|---------|
| `scripts/intelligence/architecture-qa.py` | 27 concepts + 4 Q-NN + 3 G-NN |
| `scripts/intelligence/coverage-map.py` | 32 A-NN operator demand axes |
| `scripts/intelligence/verbatim-render.py` | meta-render across 9 catalogs |
| `scripts/intelligence/doctrine-status.py` | lint family health verb |
| `scripts/intelligence/quarterly-review.py` | composed meta-audit |
| `scripts/hardware/ccd-pinning.py` | §19.2 verifier |
| `scripts/hardware/state-fabric.py` | §7.1 + §7.2 verifier |
| `scripts/network/topology.py` | §8 + §8.1 verifier |
| `scripts/intelligence/repl.py` | 4-mode REPL |
| `docs/sdd/037-verbatim-preservation-doctrine.md` | Doctrine |
| `docs/src/verbatim-surface.md` | Static published render |
| `tests/lint/test_verbatim_preservation_doctrine.py` | R367 lint (12) |
| `tests/lint/test_verbatim_spec_ref_format.py` | R368 lint (7) |
| `tests/lint/test_verbatim_surface_doc_drift.py` | R370 lint (9) |
| `tests/lint/test_mandate_row_refs.py` | R371 lint (7) |
| `tests/lint/test_verb_dispatch_refs.py` | R372 lint (8) |
| `tests/lint/test_cross_catalog_phrase_consistency.py` | R373 lint (12) |
| `tests/lint/test_round_refs.py` | R374 lint (6) |
| `tests/lint/test_sdd_reachability.py` | R380 lint (6) |

## Operator-pull entry points

```bash
# Highest-level audit (one command):
sovereign-osctl quarterly-review snapshot --human

# Lint family health:
sovereign-osctl doctrine-status status --human

# Full catalog render (consolidated mdbook doc):
sovereign-osctl verbatim-render render

# Operator demand coverage:
sovereign-osctl coverage audit --human

# Drill into a specific verbatim concept:
sovereign-osctl architecture-qa show C-04   # dual-CCD penalty
sovereign-osctl architecture-qa show C-14   # Tetragon TracingPolicy
sovereign-osctl architecture-qa show C-22   # Debian-as-Ark framing

# Drill into specific operator-demand axis:
sovereign-osctl coverage show A-31  # operator mindset/workflow contract
sovereign-osctl coverage show A-04  # GPU details RTX 3090/Pro 6000/AVX512
```

## Open questions for next arc

The verbatim-preservation surface is mature. Future arc candidates
(no commitment, just discoverable):

1. **Cross-repo verbatim consistency** — sovereign-os ↔ info-hub
   raw dump drift detection
2. **Substantive Stage 2+ build implementations** — operator-driven,
   per macro-arc plan
3. **Operator-pull HISTORICAL bug-catch trend tracking** —
   per-round historical lint catches
4. **Per-section L4 hardware-conformance tests** — gated on real
   SAIN-01 procurement

All deferred to operator decision.

## Acknowledgments

This arc is a direct response to the operator's `/goal` directive
of 2026-05-18. The 20 real bugs caught by cross-reference validation
demonstrate that the contract has real operational value (catalog
drift catches that humans missed). The catalog growth from ~0 to 82
verbatim items + 32 demand axes spans the entire master spec L0 dump
breadth + macro-arc plan post-Plan refinements + operator hook drop
+ /goal directive.

The work continues per the operator's perpetual mandate
("continue endlessly", "DO not stop"). This handoff doc preserves
state for the next session/operator picking it up — they can resume
from here without re-deriving the pattern.
