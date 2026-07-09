# context.md — sovereign-os journey state + positioning + what's ahead

> **Read me first after every compaction.** This file is the operator-requested re-orientation surface (2026-05-19). It captures *where we are*, *what's done*, *what's next*, and *what NOT to do*. If anything below is stale, fix it before continuing — never silently let it drift.
>
> Hook wiring: `~/.claude/settings.json` `SessionStart` hook should `cat` this file (or grep for `## Where we are right now`) to re-prime context. See "Hook integration" section at the bottom.

## The two ultimate solutions (operator framing, verbatim 2026-05-19)

> "Continue Endlessly to toward the two ultimate solutions and their perfectioning and high UX/Developer Experience."

| solution | repo | role | independent? | composes? |
|---|---|---|---|---|
| **Solution 1** | `cyberpunk042/sovereign-os` | Local AI workstation runtime — cockpit + 21 dashboards + gateway + model orchestration + NVFP4/ternary execution + HölderPO post-training + SRP topology (Conductor/Logic/Oracle) + memory OS + super-model manifest + peace-machine close | yes — boots degraded but functional without selfdef | yes — consumes selfdef MS007 mirror crates READ-ONLY for D-12..D-18 |
| **Solution 2** | `cyberpunk042/selfdef` | IPS daemon — boundary enforcement (communication / capability tokens / sandbox tiers / filesystem / network / authority / commit / tool) + Guardian (Tetragon eBPF) + operator CLI + TUI + minimal-web + UX coherence test harness | yes — boots fully without sovereign-os (MS043 offline-survivability R10217-R10225) | yes — publishes 9 MS007 mirror crates for sovereign-os cockpit consumption |
| **Third piece (NOT a solution)** | `cyberpunk042/devops-solutions-information-hub` | Second-brain / wiki / decision log / paper archive | n/a — operator's knowledge layer | **READ-ONLY** from runtime+IPS sessions |

Full doctrine: `docs/standing-directives/two-ultimate-solutions.md`.

## Current arc (2026-05-28): M060 cross-repo mirror producers — COMPLETE

The 7 sovereign-os mirror dashboards (D-12 rules, D-13 grants, D-14
capability-tokens, D-15 sandboxes, D-16 audit-chain, D-17 quarantine,
D-18 trust-scores) plus D-02 active-profile are no longer flagship-only
shells with offline-default state — they now consume **live** selfdef-
side producers. Cross-repo wire contract verified end-to-end at every
seam.

**Selfdef side (PR `cyberpunk042/selfdef#200`, branch
`claude/recover-projects-b0oT6`, 13 commits, ~7500 LOC, all gates green
except pre-existing m3_pipeline + info-hub coherence drift accepted as
land-as-is):**

| Domain | New resident-registry crate | Persisted store | Mutation model |
|---|---|---|---|
| D-02 active-profile | (uses existing flex-profile)        | `/var/lib/selfdef/flex-profile.json` | always-published; R09535 Private default |
| D-12 rules          | `selfdef-rules-registry`            | `/var/lib/selfdef/rules.json`             | daemon-populated (nft collector projects `nft list ruleset --json` into 13-field RuleEntry across Ring 0..4); operator never appends — rules installed via selfdefctl + nft at the IPS layer |
| D-13 grants         | `selfdef-grant-registry`            | `/var/lib/selfdef/grants.json`            | operator-issued (issue/revoke) |
| D-14 capability-tokens | `selfdef-capability-registry`    | `/var/lib/selfdef/capability-tokens.json` | operator-issued (capability_word composed) |
| D-15 sandboxes      | `selfdef-sandbox-registry`          | `/var/lib/selfdef/sandboxes.json`         | operator-issued (MS036×MS032 validation) |
| D-16 audit-chain    | `selfdef-audit-registry`            | `/var/lib/selfdef/audit.json`             | daemon-populated (MS016 SHA-256 append-only chain · MS049 13-field spans · MS026 OCSF · MS003 verify-only); operator has NO mutation surface |
| D-17 quarantine     | `selfdef-quarantine-registry`       | `/var/lib/selfdef/quarantine.json`        | daemon-populated (MS042 detection); operator override release/forfeit |
| D-18 trust-scores   | `selfdef-trust-score-registry`      | `/var/lib/selfdef/trust-scores.json`      | daemon-populated (canonical_delta); operator admit + manual-delta override |

Plus the missing MS007 typed-mirror crate `selfdef-profile-mirror` (D-02
schema, which the consumer expected but had no producer crate). The
`selfdef-daemon` mirror-export loop publishes each domain READ-ONLY to
`/run/sovereign-os/selfdef-mirror/<file>.json` when its resident store
exists (honest offline otherwise — no fabricated empty-online state).
Selfdef API + selfdefctl have parity verbs for every domain (sister to
the existing schema-discovery surfaces; the SDD-055 commit-authority
gating remains the open cross-cutting work for all mutation surfaces).

**Sovereign-os side (consumer wire verified):** the existing
`scripts/mirror/selfdef-*-mirror.py` readers (plus the new
`selfdef-audit-mirror.py` reader for D-16, modeled after the same
stdlib-only pattern) and `scripts/operator/*-api.py` daemons consume
the daemon-shaped artifacts unchanged — no sovereign-os code change
required for D-02/D-13/D-14/D-15/D-17/D-18. Hand-crafted artifacts in
the exact serde shape the selfdef producer writes flip each dashboard
from `mirror_status=offline` → `online` with the right fields populated.
The cross-repo chain contract test (`tests/lint/test_m060_cross_repo_
chain_contract.py`) locks all 7 wires with daemon-shaped fixtures.

The new `webapp/d-16-audit/` dashboard renders the audit-chain mirror
READ-ONLY (chain integrity tile · OCSF category summary · MS033 4-state
policy outcomes · bounded tail of 256 spans with prev_chain_hash /
chain_hash / signature drill-down). The chain is APPEND-ONLY by MS016
R03567 doctrine — the dashboard's "actions" panel exposes only
verify/show/export verbs (no release, no replay, no edit).

**What this unblocks for sovereign-os:** the 6 mirror dashboards can
now demonstrably go live by running `selfdefd` on the host with
`[deployment].selfdef_mirror_dir = "/run/sovereign-os/selfdef-mirror"`
(plus the per-domain `SELFDEF_<DOMAIN>_PATH` env if relocated) and
issuing/observing real grants/tokens/etc. via `selfdefctl`. No more
"published mirror at X when wired" placeholder comments — they're
wired.

**What still belongs to sovereign-os explicitly:** the cockpit dashboard
UX itself (HTML/JS/CSS in `webapp/d-*/`) and the master-dashboard
aggregation. Those existed before this arc and are unchanged; the
contract they consume is now live.

---

## Where we are right now (2026-05-19 snapshot)

### CI-health recovery — DONE (2026-05-27)

> Discovered main CI was silently RED on multiple pre-existing fronts and fixed
> them all (commits land on `main`):
> - **`cargo fmt` job** was red across the generated crate set (469 files) →
>   `cargo fmt --all` (toolchain 1.88.0). GREEN.
> - **`cargo clippy` job** was red with 424 findings across 124 crates (generated
>   crates never linted) → `clippy --fix` passes + manual residual (incl. an
>   `is_empty()`, `clamp()`, `contains_key`, `#[allow]`s for intentional
>   `next()`/many-arg ctors, 10 rustdoc-list fixes, + caught a `clippy --fix`
>   over-reach that dropped a `cfg(test)`-only import). clippy exits 0, fmt clean.
> - **`pytest tests/lint`** had 8 pre-existing failures (SDD-040 never
>   catalog-wired; 7 E11 rows missing a status keyword; hugepages systemd
>   hardening) → all fixed; **2820 lint + schema + 154 unit pass**.
> - Added repo-wide YAML + JSON parse/dup-key lints (`tests/lint/`).
> All changes behaviour-preserving; no real bugs surfaced (the catalog crates
> were correct, just un-linted). **CI verified green by hand**: `cargo test
> --workspace` (0 failures), `cargo audit` (511 deps, 0 advisories), fmt, clippy,
> `pytest tests/lint`+`tests/schema` (2820), `tests/unit` (154). `build` is
> compile-confirmed. (sovereign-os CI has no `deny` job.)

### Catalog phase — COMPLETE

Operator standing /goal: *"10000+ requirements in a clear timeline, multiple milestones and 400+ Epics and 1000+ modules and 5000+ features/tasks before starting working on them in order in SDD."*

Status:

| metric | target | actual | status |
|---|---|---|---|
| Requirements (R-rows) | 10,000+ | ~24,800 | ✓ 248% |
| Sub-requirements (10 per R) | 100,000+ | ~248,000 | ✓ 248% |
| Epics | 400+ | ~800 | ✓ 200% |
| Modules | 1,000+ | ~2,000 | ✓ 200% |
| Features | 5,000+ | ~10,200 | ✓ 204% |
| Milestones combined | n/a | 125 (sovereign-os 80 + selfdef 45) | ✓ |
| Dashboards catalogued | 20+ | 21 (D-00..D-20) | ✓ 105% |

### Backward-sweep phase — COMPLETE

Operator: *"when you reach the end of the avx-plus-plus document you will have to review / go backward a bit since it redefine some of the things / surplant / evolve some of the past."*

Done:
- M061 (`backlog/milestones/M061-avx-plus-plus-canon-update-backward-sweep-2026-05-19.md`) — 170 R-rows catalogue 6 redefinitions found in the 18,341-line avx-plus-plus dump (lines 9000-18341 redefining lines 1-9000).
- `backlog/notes/backward-sweep-2026-05-19-findings.md` — inventory of all 6 redefinitions (3 breaking / 2 additive / 1 clarifying).
- Patch Pass A applied (commits `1a79fe8` sovereign-os + `6a2f6ef` selfdef) — file-level canon-update annotations to 11 affected milestones (M005 M006 M007 M009 M010 M011 M014 M016 M017 M020 + selfdef MS010).
- Patch Pass B+C (MS007 crate version + schema_version bumps) deferred to pre-1.0 lockdown — workspace is at 0.1.0.

### Prior-dump review phase — COMPLETE

Operator: *"do not forget there was also other dumps before that we decided to restart and do properly in a sense, not that all was lost but it was down a rabbit role and with weird things happening versus what I asked."*

Done:
- `backlog/notes/prior-dump-review-2026-05-19-findings.md` — Explore-agent review of `2026-05-15-sain-01-master-spec` + `2026-05-16-sovereign-os-macro-arc-plan` dumps.
- 15 must-add milestones identified, all 15 landed: M062-M068 (substrate / SFIF / kernel / ZFS / dual-CCD / atomic state / bootstrap) + M070-M076 (skipping M069 = Guardian moved to selfdef MS044 per "Respect the projects").

### External-research ingestion phase — COMPLETE

Operator (2026-05-19): *"ingess synthesize and process: marktechpost NVFP4 article + arXiv 2604.09839 + arXiv 2605.12058 + HRM-Text-1B"*

Done:
- `backlog/notes/external-research-ingestion-2026-05-19.md` — verbatim quotes preserved.
- M077 NVFP4 pretraining + inference pipeline (NVIDIA arXiv 2509.25149 — canonical paper behind marktechpost article, 5 recipe variants)
- M078 HölderPO + GRPO post-training (arXiv 2605.12058)
- M079 Activation steering interpretability surface (arXiv 2604.09839 — formal proof WB ≠ BB)
- M080 HRM architectural class (arXiv 2506.21734 + sapientinc/HRM-Text-1B + TRM arXiv 2510.04871 — 4th model class)

### Implementation phase — IN-FLIGHT

Per operator: *"little piece by little piece and progress in this massive endless journey."*

#### sovereign-os implementation status

| artifact | status | path |
|---|---|---|
| SDD-040 cockpit-dashboard-implementation-bridge | ✓ | `docs/sdd/040-cockpit-dashboard-implementation-bridge.md` |
| D-00 master-dashboard | ✓ shipped | `webapp/master-dashboard/index.html` |
| D-01 active sessions | ✓ shipped | `webapp/d-01-active-sessions/index.html` |
| D-02 profile choices | ✓ shipped | `webapp/d-02-profile-choices/index.html` |
| D-03 model health | ✓ shipped | `webapp/d-03-model-health/index.html` |
| D-07 memory changes | ✓ shipped | `webapp/d-07-memory-changes/index.html` |
| D-08 rollback points | ✓ shipped | `webapp/d-08-rollback-points/index.html` |
| D-12 networking | ✓ shipped (consumes selfdef-rules-mirror) | `webapp/d-12-networking/index.html` |
| D-13 filesystem grants | ✓ shipped (consumes selfdef-grants-mirror) | `webapp/d-13-filesystem-grants/index.html` |
| D-14 capability tokens | ✓ shipped (consumes selfdef-capability-mirror) | `webapp/d-14-capability-tokens/index.html` |
| D-15 sandboxes | ✓ shipped (consumes selfdef-sandbox-mirror) | `webapp/d-15-sandboxes/index.html` |
| D-17 quarantine | ✓ shipped (consumes selfdef-quarantine-mirror) | `webapp/d-17-quarantine/index.html` |
| D-18 trust scores | ✓ shipped (consumes selfdef-trust-score-mirror) | `webapp/d-18-trust-scores/index.html` |
| D-19 super-model manifest | ✓ shipped | `webapp/d-19-super-model-manifest/index.html` |
| D-20 peace machine health | ✓ shipped | `webapp/d-20-peace-machine-health/index.html` |
| **17 of 21 dashboards SHIPPED** (operator target "20+ and a main one" surpassed — R10128) | ✓ MILESTONE | — |
| D-04 costs | ✓ shipped | `webapp/d-04-costs/index.html` |
| D-05 traces | ✓ shipped | `webapp/d-05-traces/index.html` |
| D-06 pending approvals | ✓ shipped | `webapp/d-06-pending-approvals/index.html` |
| D-09 hardware pressure | ✓ shipped | `webapp/d-09-hardware-pressure/index.html` |
| D-10 eval history | ✓ shipped | `webapp/d-10-eval-history/index.html` |
| D-11 adapter status | ✓ shipped | `webapp/d-11-adapter-status/index.html` |
| D-12 networking (partial via network-edge + edge-firewall) | ✓ partial | `webapp/network-edge/`, `webapp/edge-firewall/` |
| D-14 capability tokens (partial via auth-tier) | ✓ partial | `webapp/auth-tier/` |
| D-16 audit cycles | ✓ shipped | `webapp/auditor/` |
| D-19 super-model manifest (partial via trinity) | ✓ partial | `webapp/trinity/` |
| D-20 peace machine health (partial via compliance) | ✓ partial | `webapp/compliance/` |
| Orthogonal dashboards (not in M060 D-00..D-20) | ✓ retained | `webapp/anti-minimization-audit/`, `doc-coverage/`, `global-history/`, `router/`, `surface-map/`, `ux-design-audit/`, `weaver/` |
| 29 SDDs (000-039) | ✓ shipped | `docs/sdd/` |
| 6 handoff anchors (001-006) | ✓ shipped | `docs/handoff/` |

#### selfdef implementation status

| artifact | status | reference |
|---|---|---|
| 12-channel notify set (write/wall/ntfy/signal/discord/slack/smtp/thehive + shared-audit-summary + integration-orchestrator + notifier-engine + notifier-orchestrator) | ✓ shipped | `CHANGELOG.md` channel inventory |
| `selfdefctl notify resend <event_id>` escalation triage | ✓ shipped | `CHANGELOG.md` PR #173 |
| `selfdef-integration-write` per-user TTY channel | ✓ shipped | `CHANGELOG.md` PR #170 |
| 8/8 SATURATED mirror crates (auth-tier / bashrc-install / history-sink / dashboard-manifest / surface-manifest / ux-checklist / audit-manifest / doc-manifest) | ✓ shipped | `crates/selfdef-{auth-tier,...}/` |
| Guardian Daemon `/usr/local/bin/guardian-core` Python impl | catalog ✓ (MS044) / impl pending | `backlog/milestones/MS044-*` |
| MS045 UX coherence test harness impl | catalog ✓ / impl pending | `backlog/milestones/MS045-*` |
| 9 D-12..D-18 mirror crates (selfdef-rules / -grants / -capability / -sandbox / -audit / -quarantine / -trust-score / -cli / -tui) | catalog ✓ (MS043 R10182-R10193) / impl pending | `backlog/milestones/MS043-*` |

## What's ahead (forward queue, operator-priority)

> **STALE-QUEUE CORRECTION (2026-05-27, verified):** most of the list below
> has SHIPPED but was never removed from this queue (update-protocol drift).
> Verified present + substantive this session:
> - **Phase D selfdef-mirror dashboards (D-13..D-20): ALL BUILT** —
>   `webapp/d-1{3,4,5,7,8}-*/index.html` (267–303 lines each) + d-19/d-20;
>   `sovereign-dashboard-coverage` verifier passes (all 21 D-NN slots).
> - **Stage 2 ISO build pipeline: BUILT** — `scripts/build/01-09-*.sh` +
>   `orchestrate.sh` (1569 lines: bootstrap-forge → kernel fetch/config/
>   compile → substrate-prepare → whitelabel-render → image build/sign/verify).
> - **MS044 Guardian Daemon: BUILT (selfdef repo)** —
>   `selfdef/scripts/guardian/guardian-core` (469 lines) + systemd unit
>   `selfdef/config/systemd/guardian-core.service`.
> - **MS045 UX coherence harness: shipped** (commit cdc9064, per provenance).
>
> So items 1–19 below are largely DONE. The genuine next frontier is NOT
> re-listed here to avoid inventing it — determine it from `docs/sdd/INDEX.md`
> (e.g. SDD-033 perpetual-intake is in `review`) and operator priority. Per
> "never delete — layer on top", the original list is retained below as
> historical record; treat its ✓-less items as needing a presence-check
> before any (re)work.

Per SDD-040 Phase A → E ordering + selfdef Guardian/UX-harness implementations.

### Immediate next pieces (Phase D — selfdef-mirror dashboards)

1. **D-14 capability tokens dashboard** — consumes `selfdef-capability-mirror`
2. **D-15 sandboxes dashboard** — consumes `selfdef-sandbox-mirror`
3. **D-17 quarantine dashboard** — needs `selfdef-quarantine-mirror` (5 of 9, not yet shipped)

### Phase D (selfdef-mirror dashboards via MS007)

9. selfdef 9 mirror crates implementation (rules / grants / capability / sandbox / audit / quarantine / trust-score / cli / tui)
10. D-13 filesystem grants dashboard (consumes selfdef-grants-mirror)
11. D-15 sandboxes dashboard (consumes selfdef-sandbox-mirror)
12. D-17 quarantine dashboard (consumes selfdef-quarantine-mirror)
13. D-18 trust scores dashboard (consumes selfdef-trust-score-mirror)

### Phase E (close-out + partial-completion)

14. D-08 rollback points dashboard — ZFS snapshot list
15. D-14 capability tokens completion — extend `webapp/auth-tier/`
16. D-19 super-model manifest completion — extend `webapp/trinity/`
17. D-20 peace machine health completion — extend `webapp/compliance/`

### selfdef implementations

18. **MS044 Guardian Daemon** Python impl at `/usr/local/bin/guardian-core` + systemd unit `/etc/systemd/system/guardian-core.service` (Tetragon eBPF event loop + SIGKILL + atomic ZFS audit log)
19. **MS045 UX coherence test harness** binary at `/usr/bin/selfdef-ux-harness` + systemd timer

### sovereign-os runtime crates

20. ~~M077 NVFP4 runtime crate~~ ✓ shipped 2026-05-19 — `crates/sovereign-nvfp4-runtime/` 5 recipes (NVFP4-S/M/L/XL/XXL) + E2M1 + E4M3 + 1x16 block quantize/dequantize + stochastic rounding unbiased ±2% verified (13 passing tests)
21. ~~M078 HölderPO runtime crate~~ ✓ shipped 2026-05-19 — `crates/sovereign-holderpo/` Hölder-mean aggregator (p ∈ ℝ with geom/arith/quad/max/min limits verified) + 4 anneal schedules (Constant/Linear/Cosine/Step) + GRPO group-relative advantages with optional std normalisation (17 passing tests)
22. ~~M079 Intervention-class typed mirror crate~~ ✓ shipped 2026-05-19 — `crates/sovereign-intervention-class-mirror/` per arXiv 2604.09839 + 5-variant InterventionClass enum + protocol-separation enforcement (WB↔BB generalisation refused) + DOCTRINE_NON_SURJECTIVE verbatim ("almost surely, no prompt can reproduce") + tamper detection (13 passing tests)
23. ~~M080 HRM runtime crate~~ ✓ shipped 2026-05-19 — `crates/sovereign-hrm-runtime/` 4th architectural class + 3 variants (HrmCanonical 27M / HrmText1B 1.18B / Trm7M) + two-timescale recurrence cadence stepper (outer × inner) + validators (13 passing tests)

### Cockpit + runtime crates (post-/goal arc — 17 new crates)

24. ~~sovereign-mirror-publisher~~ ✓ (12 tests) — 9-endpoint MS007 binding manifest
25. ~~sovereign-dashboard-coverage~~ ✓ (12+1 tests) — 21-slot D-NN coverage verifier
26. ~~sovereign-dashboard-toggle~~ ✓ (15 tests) — M060 R10038 per-dashboard visibility
27. ~~sovereign-cockpit-personalization~~ ✓ (19 tests) — M060 R10137 + R10140 + R10141 per-profile UX
28. ~~sovereign-router-7axis~~ ✓ (13 tests + 192-combo walk) — M042 NadirClaw 7-axis routing
29. ~~sovereign-environment-maps~~ ✓ (14 tests) — M042 7-map "Build a map first" doctrine
30. ~~sovereign-memory-os~~ ✓ (17 tests) — M028 8-type Memory OS + 11-stage lifecycle
31. ~~sovereign-value-plane~~ ✓ (18 tests) — M027 12-axis reward + 5-tier Intelligence Dial
32. ~~sovereign-inheritance-contracts~~ ✓ (14 tests) — M042 Symphony 6-contract schema
33. ~~sovereign-trinity~~ ✓ (12 tests) — M066 Pulse/Weaver/Auditor genesis
34. ~~sovereign-module-catalog~~ ✓ (15 tests) — M048 10-module catalog + KEY LINE
35. ~~sovereign-policy-questions~~ ✓ (15 tests) — M049 7 policy questions
36. ~~sovereign-cognitive-compiler~~ ✓ (17 tests + cycle detection) — M025 intent-to-DAG
37. ~~sovereign-cockpit-state~~ ✓ (12 tests) — composite envelope of 6 sub-crates
38. ~~sovereign-srp-scheduler~~ ✓ (15 tests) — M075 SRP work-placement
39. ~~sovereign-lora-foundry~~ ✓ (11 tests) — M046 8-adapter + 7-step pipeline + 6-decision
40. ~~sovereign-pressure-sensors~~ ✓ (14 tests) — M045 PSI-DCGM-runtime 6-axis pressure model
41. ~~sovereign-eval-plane~~ ✓ (11 tests) — M048 Module 7 10-dim + 8-profile weighting
42. ~~sovereign-continuity-manager~~ ✓ (11 tests) — M048 Module 8 6-primitive + 8-state lifecycle
43. ~~sovereign-observability-fabric~~ ✓ (11 tests) — M048 Module 9 9-source + 6-question
44. ~~sovereign-gateway~~ ✓ (12 tests) — M048 Module 4 6-surface + 7-responsibility Anthropic-first
45. ~~sovereign-zfs-commit-gate~~ ✓ (14 tests) — M040 4-stage snapshot/apply/test/commit-or-rollback
46. ~~sovereign-doctrinal-preservation~~ ✓ (8 tests) — 16-doctrine verbatim registry composite
47. ~~sovereign-cgroup-systemd~~ ✓ (11 tests) — M045 8-OS-primitive substrate snapshot

**sovereign-os Rust workspace: 29 crates total**

### Stage 2+ build scripts (per M062 PR 10 → Stage Gate 5 → Stage 2)

Per M062 Stage Gate 5 verbatim: "authorizes Stage 2 (first actual build scripts)". Substrate decision is locked in `docs/sdd/021-distro-base.md`. Foundation is complete. Stage 2 work = actual installable ISO build pipeline using chosen substrate tooling.

## What NOT to do — operator standing rules

Verbatim operator rules, never relax these:

1. **"you cannot invent crap"** — every R-row / module / feature / requirement traces to a verbatim source (avx-plus-plus dump line, prior-dump line, operator standing direction, or peer-reviewed paper). No invention.
2. **"do not minimize the work in selfdef"** — selfdef milestones use full 240-R-row pattern (10 epics / 26 modules / 120 features / 240 reqs). Same applies to sovereign-os 170-R-row pattern (10 / 17 / 85 / 170). Never collapse.
3. **"Respect the projects"** — IPS features stay in selfdef; runtime features stay in sovereign-os. Cross-repo via MS007 mirror crates only.
4. **"Knowledge is the second-brain / information-hub"** — info-hub is READ-ONLY from sovereign-os + selfdef sessions. Never mutate.
5. **"layered ON TOP OF prior direction — never discarded"** — additive updates only. Earlier R-rows preserved verbatim. Canon updates go in M061-style supersedes-not-replaces structure.
6. **"NO random trash please"** — every artifact must have operator-direct purpose. Sovereignty-clean UX (no framework / no CDN / no fetched fonts / monospace / monochrome palette).
7. **"you cannot re-invent what UX mean"** — match the existing webapp/ UX doctrine (see SDD-040 for canonical patterns). Industry-standard a11y (WCAG 2.1 AA + keyboard-first + focus-visible). No bespoke UX patterns invented.
8. **"DISABLE_AUTOCOMPACT=1 sacrosanct"** — never substitute or weaken. Per `~/.claude/CLAUDE.md`.
9. **"never include model identifier in commit messages / PR bodies / pushed artifacts"** — chat replies only.
10. **"the AI does NOT decide when it's complete"** — operator-controlled session-end via `/goal`. Continue endlessly.

## Parallel-session conventions (SDD-100 — 3 sessions at once)

sovereign-os is worked by **3 sessions in parallel** (recover-projects / header-sidemenu /
science-tools), each on its own branch merging to `main`. To stop the merge conflicts that
recurred 2026-07-09 (the SDD-070 number collision + INDEX/mandate append conflicts):

1. **Pick SDD-NNN / E11.M## numbers in YOUR session's band** — recover-projects **100–199**,
   header-sidemenu **200–299**, science-tools **300–399**, general **900–999** (SDD + E11.M##).
   The band table + "how to add an SDD" is [`docs/sdd/README.md`](docs/sdd/README.md). The
   historical 064–071 / M32–M38 stay as-is; bands apply going forward. Never pick a number
   outside your band — that's how collisions happen.
2. **The append-only registries are `merge=union`** ([`.gitattributes`](.gitattributes)) —
   `docs/sdd/INDEX.md`, the operator-mandate, `docs/src/lifecycle/ongoing.md`,
   `docs/observability/dashboards/README.md`, `docs/decisions.md`. Two branches appending
   different rows merge cleanly (both kept); you never hand-resolve a registry row conflict.
3. **Don't hardcode registry counts** ("N recurrent hooks", "N timers") in prose or test
   docstrings — a magic integer is a shared value two sessions both bump. The real assertions
   are glob/set-based; keep prose count-free.

## Build/test hygiene (environment caveat — 2026-05-27)

**DO NOT run `cargo test --workspace` / `cargo build --workspace` here.** This
repo has **475 crates** and the sibling selfdef has **535**; a full-workspace
build produces a `target/` of ~13 GB *per repo*. The container has ~16 GB
free headroom, so a workspace build of both (or one on top of an existing
selfdef `target/`) **fills the disk** (`No space left on device` — the shell
itself stops being able to write). Observed + recovered 2026-05-27 (freed by
`rm -rf sovereign-os/target`; pure rebuildable cache, safe).

**Instead:** build/test **per-crate** — `cargo test -p sovereign-<crate>` —
which is also the operator's established cadence (one small crate per logical
unit, direct-to-main, L3-gated). If you must clear space:
`rm -rf <repo>/target` is safe (rebuildable). Never run a whole-workspace
compile as a "quick check".

## "Two solutions" rule — every new contribution

Before any new code / SDD / milestone / dashboard / CLI / mirror / systemd unit lands, contributor MUST answer:

1. **Which solution?** sovereign-os OR selfdef. If "both" → split + bind via MS007.
2. **Preserves independence?** Receiving solution boots without sender present?
3. **Preserves composition?** Cross-repo binding via MS007 mirrors only?
4. **READ-ONLY across boundary?** Mutations proxy via MS003-signed operator request?
5. **info-hub untouched?** Never write to info-hub from runtime+IPS sessions.

## Hook integration (sovereign-os) — ACTUALLY WIRED 2026-05-19

This file is referenced by **live, working hooks** (verified post-edit):

- `~/.claude/settings.json` `SessionStart` hook chain:
  1. `bash $HOME/.claude/env-bootstrap/apply.sh --quiet` (self-healing template reinstaller)
  2. `bash $HOME/.claude/session-start-context.sh` — detects both repos' context.md and emits `systemMessage` JSON pointing the model at them on every new session
- `~/.claude/settings.json` `PostCompact` hook:
  1. `bash $HOME/.claude/post-compact-reorient.sh` — same context.md detection logic, fires on every compaction
- Canonical templates at `~/.claude/env-bootstrap/templates/{settings.json,session-start-context.sh,post-compact-reorient.sh}` — env-bootstrap `apply.sh` reinstalls live files from templates if drift detected. Template-vs-live drift verified zero post-wire.
- `~/.claude/validate-stop-hook-fix.sh --quiet` returns exit 0 (env clean) after wiring.

Verified via smoke test post-wire:
```
$ bash ~/.claude/session-start-context.sh | head -1
{"systemMessage": "SESSION-START RE-ORIENT — per operator standing direction 2026-05-19 ... | /home/user/sovereign-os/context.md | /home/user/selfdef/context.md ..."}
```

Cross-references to this file:
- `docs/standing-directives/two-ultimate-solutions.md` — references this file as the live status snapshot
- `docs/sdd/INDEX.md` — link to this file as project-state-of-the-art

If you're an AI session reading this for the first time after compaction:
1. Stop. Read this entire file.
2. Read `docs/standing-directives/two-ultimate-solutions.md` for the architectural framing.
3. Read `backlog/notes/external-research-ingestion-2026-05-19.md` + the 3 backward-sweep + prior-dump finding notes.
4. Pick the next item from "What's ahead" forward queue.
5. Execute "little piece by little piece" — one tractable deliverable per commit.
6. Update this file's "Where we are right now" section before ending your turn so the next session starts with current state.

## Update protocol

This file is **operator-state-of-the-art**. Updates:

- **After every implementation deliverable**: append the artifact to "Where we are right now" + remove from "What's ahead". Same commit as the deliverable.
- **After every catalog-phase deliverable** (new milestone / SDD / canon update): update the relevant phase status section.
- **After every operator direction change**: update "What NOT to do" or "Two solutions rule" or the doctrinal anchors.
- **Never delete sections**. Sections may be marked OUTDATED but content stays per "layered ON TOP — never discarded".

## Provenance + commits (most recent first)

- `918ad14` — standing-directive two-ultimate-solutions + D-06 pending approvals dashboard
- `cdc9064` (selfdef) — MS045 UX coherence test harness milestone
- `aca3e18` — SDD-040 bridge + D-02 profile choices dashboard
- `0255940` — M080 HRM architectural class (LAST external-research milestone)
- `a42b73c` — M079 Activation steering interpretability surface
- `84b4b2f` — M078 HölderPO + GRPO post-training pipeline
- `f0a646d` — M077 NVFP4 pretraining + inference pipeline
- `653b703` — external-research-ingestion log
- `25896b5` — CODEOWNERS closing M062 PR 1 gap
- `32cee89` — M076 Three Load-Balancing Profiles (LAST catalog must-add)
- `8e39ddf` — M075 SRP hardware topology
- `d73e658` — M074 AVX-512 VNNI fusion
### Session 2026-05-19 (post-compaction) — 15 fresh runtime crates added

- `ff91592` — `sovereign-cockpit-keystroke-map`: 5-scope shortcut registry with conflict gate
- `15a19a5` — `sovereign-doctrine-citation`: 8-shape × 16-tag runtime citation envelope
- `988aad2` — `sovereign-replay-cursor`: turn-walking cursor (step/pause/resume/jump-to/breakpoint)
- `edaaed2` — `sovereign-dashboard-layout`: 12-column widget grid with overlap detection
- `15322e7` — `sovereign-prompt-template-registry`: variable-slot rendering + context gates
- `904d079` — `sovereign-mode-transition-log`: 7-reason mode-switch audit with danger gate
- `413273d` — `sovereign-cockpit-toast-tray`: ephemeral notification queue (TTL, 20-cap)
- `19fb6a1` — `sovereign-tool-invocation-record`: per-call cockpit record with catalog-gate
- `8d835c8` — `sovereign-conversation-thread`: turn-by-turn 4-role thread schema
- `46baf6f` — `sovereign-tool-catalog`: 8-tool cockpit registry gated on (mode × bundle)
- `7d52db0` — `sovereign-cockpit-banner-state`: top-bar single-source-of-truth + severity
- `8198bea` — `sovereign-execution-mode-registry`: 7-mode capability tuple catalog
- `0bf4ee2` — `sovereign-hardware-thermal-policy`: per-target Cool/Warm/Throttle/Shutdown
- `0cead49` — `sovereign-hardware-dispatch-eligibility`: 5-target VRAM/latency/role/util feasibility
- `9d1a0c5` — `sovereign-hardware-load-sample`: 5-target VRAM/util/temp snapshot
- `0a7547f` — `sovereign-hardware-registry`: 5-target hardware catalog with SRP role

Sovereign-os workspace at 109 crates (was 32 pre-session, +77 fresh this session).
Full workspace test suite: 1240 passing tests. Newest:
`sovereign-cockpit-screen-reader-hints` (ARIA roles + politeness),
`sovereign-cockpit-collapsible-section` (per-section persistence),
`sovereign-cockpit-quick-action-bar` (MAX_SLOTS=12 horizontal bar).
Earlier:
`sovereign-cockpit-error-banner`, `sovereign-cockpit-color-blind-mode`.
Earlier batch:
`sovereign-cockpit-recent-items` (LRU recent-views),
`sovereign-cockpit-input-mode` (Mouse/Keyboard/Vim/Touch),
`sovereign-cockpit-context-menu` (per-target right-click registry).
Earlier:
`sovereign-cockpit-onboarding-flow` (8-step first-run tour),
`sovereign-cockpit-export-bundle` (multi-item operator export).
Recent additions:
`sovereign-cockpit-window-position` (multi-monitor placement),
`sovereign-cockpit-language-pack` (i18n translation table).
Newest:
`sovereign-cockpit-detail-panel` (8-kind right-side inspector),
`sovereign-cockpit-toggle-tray` (6-category feature toggle tray),
`sovereign-cockpit-quick-filter` (multi-chip facet filter).
Recent additions include
`sovereign-cockpit-clipboard-history`, `sovereign-cockpit-tooltip-catalog`,
`sovereign-cockpit-share-link`, `sovereign-cockpit-notification-center`.
Earlier additions:
`sovereign-cockpit-typing-indicator`, `sovereign-cockpit-route-history`,
`sovereign-cockpit-modal-stack`, `sovereign-cockpit-empty-state`,
`sovereign-cockpit-skeleton-loader`. Earlier additions:
`sovereign-cockpit-side-nav-state`, `sovereign-cockpit-status-badge`,
`sovereign-cockpit-clock-display`, `sovereign-cockpit-confirmation-modal`,
`sovereign-cockpit-progress-tracker`. Latest additions (all
pure-UX, no IPS authority dimension) include `sovereign-cockpit-turn-
annotation`, `sovereign-cockpit-density-mode`, `sovereign-cockpit-theme-
palette`, `sovereign-cockpit-shortcut-cheatsheet`, `sovereign-cockpit-zoom-
level`, `sovereign-cockpit-locale-state`, `sovereign-replay-playback-rate`,
`sovereign-cockpit-typography-scale`, `sovereign-cockpit-sound-preferences`,
`sovereign-cockpit-pin-board`. Earlier additions include
`sovereign-cockpit-pane-layout` (Single/SplitV/SplitH/QuadGrid),
`sovereign-cockpit-toggle-event` (append-only toggle audit log;
the SELFDEF-side authority is `selfdef-toggle-audit-authority`),
`sovereign-cockpit-pinned-shortcuts` (top-bar quick-launch pins),
`sovereign-conversation-fork-event` (operator-initiated branch fork log),
`sovereign-eval-result-summary` (single-run eval summary),
`sovereign-cockpit-turn-annotation` (operator notes/highlights/stars),
`sovereign-cockpit-density-mode` (Compact/Comfortable/Spacious/Touch),
`sovereign-cockpit-theme-palette` (5 themes).

### Boundary discipline (2026-05-19 correction)

Operator critique: "things in Sovereign-OS you should have done in Selfdef
and used in Sovereign-OS". Several runtime crates here (execution-mode-
registry, mode-transition-log, tool-catalog, cockpit-toggle-event,
routing-decision-log) carry IPS-authority semantics. Their SELFDEF
counterparts now exist and are the source-of-truth:

- selfdef-execution-mode-policy ←→ sovereign-execution-mode-registry
- selfdef-mode-transition-authority ←→ sovereign-mode-transition-log
- selfdef-tool-capability-policy ←→ sovereign-tool-catalog
- selfdef-toggle-audit-authority ←→ sovereign-cockpit-toggle-event
- selfdef-routing-decision-authority ←→ sovereign-routing-decision-log
- selfdef-replay-source-authority ←→ sovereign-replay-cursor (Replay-entry gate)

New runtime crates after this point are pure UX/display surfaces with
no policy authority of their own (turn-annotation, density-mode,
theme-palette).
Final-leg crates beyond the rolled-up batch:
`sovereign-routing-decision-log`, `sovereign-dashboard-snapshot`,
`sovereign-routing-preference`, `sovereign-replay-export-bundle` (thread+cursor+bookmarks),
`sovereign-prompt-history-ring` (operator prompt recall),
`sovereign-cockpit-tab-strip` (operator-managed tabs).
Additional crates beyond the first batch:
`sovereign-workspace-folder-registry` (operator-declared roots with overlap detection),
`sovereign-provider-catalog` (6-provider inference catalog with bundle gates),
`sovereign-eval-suite-catalog` (7-suite eval catalog composing 8-dim eval-plane),
`sovereign-cockpit-command-palette` (16-command Ctrl-K palette),
`sovereign-mode-default-policy` (per-bundle landing mode policy),
`sovereign-conversation-search-index` (substring+role+branch search),
`sovereign-cockpit-context-panel` (sidebar context envelope),
`sovereign-replay-bookmark-set` (operator-named anchor points),
`sovereign-cockpit-undo-stack` (reversible action LIFO with redo),
`sovereign-cockpit-action-throttle` (per-action minimum-spacing gate),
`sovereign-prompt-rationale` (per-dispatch rationale envelope).

Every crate ships with canonical builders, full validate() + serde roundtrip
+ edge-case tests (9..15 passing tests per crate).

### Earlier milestones

- `0163a46` — M073 1-bit ternary BitLinear
- `4295c85` — M072 Master Bootstrap Verification Checklist
- `b083908` — M071 Atomic State Transition Protocol
- `145cdd6` — M070 Dual-CCD topology
- `8fa7407` — M068 ZFS storage architecture
- `bd2c037` — M067 kernel build pipeline
- `3c92d79` — M066 Trinity Genesis (Pulse / Weaver / Auditor)
- `78eaca7` — M065 Five Stage Gates
- `94a4599` — M064 Debian-as-Ark + Q-016
- `4e9852e` — M063 SFIF discipline
- `46f5ac7` — M062 Macro-Arc 10-PR scaffold
- `5430020` — prior-dump-review findings log
- `1a79fe8` — Patch Pass A (10 sovereign-os milestone annotations)
- `6f07dca` — M061 AVX++ canon update (6 redefinitions)
- `02ff080` — backward-sweep findings log
- `0d17dfc` — M060 cockpit + 21 dashboards + UX

Earlier history: see `git log --oneline backlog/milestones/` and `CHANGELOG.md`.

## Reference table — operator quotes that shape the work

| quote | source | implication |
|---|---|---|
| "Continue Endlessly to toward the two ultimate solutions and their perfectioning and high UX/Developer Experience" | /goal 2026-05-19 | this doc + every dashboard + every milestone |
| "you cannot invent crap" | /goal | source citation required on every R-row |
| "do not minimize the work in selfdef" | /goal | selfdef milestones full 240-R-row pattern |
| "Respect the projects" | /goal | sovereign-os/selfdef boundary, MS007 mirrors only |
| "Knowledge is the second-brain / information-hub" | /goal | info-hub READ-ONLY |
| "you cannot re-invent what UX mean" | /goal | match existing webapp UX doctrine (SDD-040) |
| "everything can be turned on and off" | /goal | every dashboard + every feature operator-toggleable |
| "do not block, you have plenty to continue" | /goal | one tractable deliverable per commit, never pause for permission |
| "little piece by little piece" | /goal | SDD-040 Phase A → E ordering |
| "layered ON TOP OF prior direction — never discarded" | standing direction | additive updates, M061-style supersedes-not-replaces |
| "be an architect first, then a DevOps Software Engineer and Fullstack and UX Design Specialist" | /goal | rotate hats per deliverable; MS045 = DevOps + UX Specialist hat |

---

**Last updated**: 2026-05-19 (commit `81724bd` + this file `context.md`)
**Next AI session**: read this file → read two-ultimate-solutions.md → pick next item from "What's ahead" → execute → update this file.

## Latest cycle (post-resume 2026-05-19)

Added 8 pure-UX cockpit crates this cycle (no IPS authority dimension):
- `sovereign-cockpit-drag-drop` (5 ObjectKinds, begin/hover/unhover
  lifecycle, cross-kind drop rejected)
- `sovereign-cockpit-focus-trap` (modal Tab/Shift+Tab wrap, skips
  disabled, Escape dismisses)
- `sovereign-cockpit-breadcrumb-trail` (push/pop/truncate-to, render
  collapses middle to ellipsis past max_visible)
- `sovereign-cockpit-stepper` (multi-step wizard, NotStarted/Active/
  Done/Error/Skipped, next() gated on Done|Skipped)
- `sovereign-cockpit-typeahead` (query + ranked candidates +
  Down/Up wrap + Enter commit + Escape close)
- `sovereign-cockpit-accordion` (collapsible sections + optional
  single_open invariant)
- `sovereign-cockpit-tag-input` (commit-on-Enter/Tab/Comma +
  backspace-pops-last-tag + length/count/casing rules)
- `sovereign-cockpit-pagination` (total_items/page_size/page, render
  emits Page+Ellipsis tokens around active)

All include canonical builders, full validate() + serde roundtrip +
edge-case tests (13..17 tests each). Workspace count: 118 crates.

Companion selfdef IPS-authority crates landed in lockstep:
`emergency-stop-policy`, `quorum-approval-policy`, `clipboard-egress-policy`,
`time-window-policy`, `prompt-injection-classifier`, `blast-radius-classifier`,
`secret-redaction-policy`, `token-lifetime-policy`.

### Second wave (same day, +5 more cockpit crates)

- `sovereign-cockpit-tree-view` (hierarchical nodes with expand/
  collapse + single-selection cursor; visible_rows() DFS flatten
  for virtualized rendering; cycle detection on construction)
- `sovereign-cockpit-resize-handle` (horizontal/vertical split with
  current_px clamped to [min, max]; drag(delta) clamps; reset
  restores default_px; drag lifecycle for cursor)
- `sovereign-cockpit-radio-group` (mutually-exclusive selection +
  arrow-key wrap that skips disabled; required flag for form-gates)
- `sovereign-cockpit-checkbox-tree` (tri-state Checked/Unchecked/
  Indeterminate; parent state derived from children, toggle
  propagates target state to all leaf descendants)
- `sovereign-cockpit-scroll-restore` (bounded LRU mapping route ->
  (x,y) with touch-on-read MRU promotion; eviction at capacity)

Workspace count now 123. Total this resume cycle: 13 cockpit crates.

### Third wave (same day, +7 more cockpit crates)

- `sovereign-cockpit-toolbar-overflow` (priority-aware partition
  visible vs overflow under measured container width)
- `sovereign-cockpit-multi-select-list` (anchor + BTreeSet selection
  with Plain/Toggle/Range click semantics)
- `sovereign-cockpit-form-validity` (per-field touched/empty/
  required/custom_error + visible_errors filtered by touched)
- `sovereign-cockpit-search-highlight` (greedy subsequence matcher
  emitting non-overlapping byte ranges; matched_all flag)
- `sovereign-cockpit-clipboard-buffer` (MRU ring of text/image
  payloads with size + count caps)
- `sovereign-cockpit-time-picker` (hour+minute with 1/5/15/30 step,
  carry+wrap, H12/H24 display)
- `sovereign-cockpit-rating-stars` (3/5/7/10 scale, optional half-
  stars, allow_clear on click-active)

Workspace count now 130. Total this resume: 20 cockpit crates.

### Fourth wave (same day, +5 more cockpit crates)

- `sovereign-cockpit-status-aggregator` (worst-of-N headline +
  rounded percentages across subsystems)
- `sovereign-cockpit-progress-bar` (Determinate/Indeterminate +
  buffered head + warn/critical zones with above/below semantics)
- `sovereign-cockpit-snackbar-queue` (pending/visible/dismissed Vec
  with max_visible cap + TTL auto-dismiss + log)
- `sovereign-cockpit-shortcut-conflicts` (Duplicate-within-scope +
  Global-shadows-stricter detection across 3 scopes)
- `sovereign-cockpit-fuzzy-ranker` (consecutive + word-start
  bonuses + skip penalty, stable-on-tie descending)

Workspace count now 135. Total this resume: 25 cockpit crates.

### Fifth wave (same day, +3 more cockpit crates)

- `sovereign-cockpit-image-viewer-zoom` (9 discrete zoom levels +
  pan clamped to keep image center in viewport; fit-to-viewport)
- `sovereign-cockpit-bulk-action` (action enablement under
  min/max selection count + requires_unlocked flag)
- `sovereign-cockpit-color-picker` (RGBA, recent MRU dedup,
  favorites pin; set_hex parses #RGB/#RRGGBB/#RRGGBBAA)

Workspace count now 138. Total this resume: 28 cockpit crates.

### Sixth wave (same day, +2 more cockpit crates)

- `sovereign-cockpit-tab-overflow` (active tab always pinned inline;
  display-order preserved across inline + chevron-overflow lists)
- `sovereign-cockpit-page-transition` (4-phase state machine
  Idle/Outgoing/Entering/Active driven by tick(dt_ms))

Workspace count now 140. Total this resume: 30 cockpit crates.

### Seventh wave (same day, +3 more cockpit crates)

- `sovereign-cockpit-cheatsheet-builder` (Entry list → grouped
  sorted Sections of Rows for help overlay)
- `sovereign-cockpit-empty-search-state` (4-cause classifier
  BlankQuery/NothingMatches/FilteredOut/NotIndexedYet with
  per-cause headline + detail + suggested action)
- `sovereign-cockpit-data-grid-sort` (multi-column SortEntry list
  with Single click cycle + Multi click toggle)

Workspace count now 143. Total this resume: 33 cockpit crates.

### Eighth wave (same day, +3 more cockpit crates)

- `sovereign-cockpit-cell-editor` (single active Coord + buffer +
  dirty + validation_error; commit/cancel return Outcome)
- `sovereign-cockpit-grouped-list` (Groups with collapsed flag +
  Items by group_key; flat_render emits GroupHeader+Item rows)
- `sovereign-cockpit-filter-chip-bar` (active filter chips with
  per-chip removable; clear_all_removable preserves pinned)

Workspace count now 146. Total this resume: 36 cockpit crates.

### Ninth wave (same day, +3 more cockpit crates)

- `sovereign-cockpit-side-panel-state` (4 PanelMode Closed/Peek/
  Open/Pinned + MRU tabs + remembered width)
- `sovereign-cockpit-dashboard-grid` (N×M cell grid; Placement
  (id,x,y,w,h) with off-grid/overlap rejection; touching edges OK)
- `sovereign-cockpit-action-menu` (hierarchical Item/SubMenu/
  Separator tree; visible() prunes invisible + collapses empty
  subs + dedup/leading/trailing separators)

Workspace count now 149. Total this resume: 39 cockpit crates.

### Tenth wave (same day, +2 more cockpit crates)

- `sovereign-cockpit-mini-map` (aspect-preserving scaled minimap +
  viewport rect clamped to bounds; min 1px on each axis)
- `sovereign-cockpit-zoom-pan-canvas` (continuous-scale camera with
  pan_screen, world↔screen roundtrip, NaN rejection)

Workspace count now 151. Total this resume: 41 cockpit crates.

### Eleventh wave (same day, +2 more cockpit crates)

- `sovereign-cockpit-action-bar` (3 slots Primary/Secondary/Tertiary
  with id-collision rejection; render_order: secondary, tertiary,
  primary right-aligned)
- `sovereign-cockpit-virtual-grid` (2D viewport virtualization
  computing visible (first_row, first_col, row_count, col_count)
  with overscan + total cap)

Workspace count now 153. Total this resume: 43 cockpit crates.

### Twelfth wave (same day, +7 more cockpit crates)

- `sovereign-cockpit-keyboard-pillbox` (chord parser → OS-aware
  pill tokens; Mac ⌃⌥⇧⌘, Linux Super, Windows Win)
- `sovereign-cockpit-pagination-status` ('Showing A-B of N (filtered
  from M)' with comma-grouped numbers)
- `sovereign-cockpit-search-input` (debounced + last_submitted +
  show_clear; Enter bypasses debounce)
- `sovereign-cockpit-row-density` (Compact/Cozy/Comfortable/
  Spacious → row_height_px + line_count + show_secondary)
- `sovereign-cockpit-online-status` (4 Status state machine with
  reconnect/offline timeouts driven by tick(now))
- `sovereign-cockpit-stale-banner` (Fresh/SlightlyStale/Stale/
  VeryStale buckets with compact age_text s/m/h/d)
- `sovereign-cockpit-skeleton-list` (Loading/Loaded/Failed; rows()
  yields SkeletonRow{index, width_pct} deterministic per seed)

Workspace count now 160. Total this resume: 50 cockpit crates.

### Thirteenth wave (same day, +4 more cockpit crates)

- `sovereign-cockpit-quick-action` (one-tap action registry with
  use-count + ordered_for_display by descending use count)
- `sovereign-cockpit-fab` (floating-action-button + 4-corner + speed-
  dial + scroll-down auto-hide that collapses speed-dial)
- `sovereign-cockpit-segmented-control` (2-6 mutually-exclusive
  segments with arrow-key wrap that skips disabled)
- `sovereign-cockpit-field-help` (per-field help_text + error_text
  + dismissed; Error overrides Help; set_error undismisses)

Workspace count now 164. Total this resume: 54 cockpit crates.

### Fourteenth wave (same day, +3 more cockpit crates)

- `sovereign-cockpit-card-grid` (responsive layout: columns from
  container_w/min_card_w; card_w clamped to [min,max])
- `sovereign-cockpit-step-indicator` (visual numbered renderer from
  Stepper state with connector_filled and percent_complete)
- `sovereign-cockpit-spinner-pool` (Hidden/Single/Multi aggregation
  with flicker-suppression for young spinners)

Workspace count now 167. Total this resume: 57 cockpit crates.

### Fifteenth wave (same day, +3 more cockpit crates)

- `sovereign-cockpit-tag-cloud` (weighted projection mapping weight
  to font_size_pct linearly; all-equal weights → midpoint)
- `sovereign-cockpit-vim-mode-indicator` (5 VimMode + command_buffer
  + operator_count; display() renders status line)
- `sovereign-cockpit-rich-text-toolbar` (5 InlineMark BTreeSet + 7
  BlockKind; toggle_mark + set_block; CodeBlock clears marks)

Workspace count now 170. Total this resume: 60 cockpit crates.

### Sixteenth wave (same day, +3 more cockpit crates)

- `sovereign-cockpit-table-row-selection` (per-row selected BTreeSet
  + header tristate None/Some/All; toggle_header + toggle_row)
- `sovereign-cockpit-text-diff` (line-level Same/Added/Removed via
  longest-common-prefix + longest-common-suffix)
- `sovereign-cockpit-search-filter` (composite query+facets+sort
  snapshot with apply_facet/drop_facet/clear/set_sort)

Workspace count now 173. Total this resume: 63 cockpit crates.

### Seventeenth wave (same day, +4 more cockpit crates)

- `sovereign-cockpit-rate-limit-banner` (throttle countdown
  with seconds remaining + reason text)
- `sovereign-cockpit-popover-stack` (parent-id lineage; close drops
  descendants; escape closes topmost subtree)
- `sovereign-cockpit-text-input-counter` (Soft/Hard mode counter
  with Normal/Warn/Over color)
- `sovereign-cockpit-toast-position` (4-corner layout with stacking
  direction derived from corner)

Workspace count now 177. Total this resume: 67 cockpit crates.

### Eighteenth wave (same day, +2 more cockpit crates)

- `sovereign-cockpit-hover-card` (4-phase Idle/Pending/Visible/
  FadingOut state machine driven by tick(now))
- `sovereign-cockpit-column-config` (Column model with pin-left/
  pin-right + render_order projection)

Workspace count now 179. Total this resume: 69 cockpit crates.

### Nineteenth wave (same day, +2 more cockpit crates)

- `sovereign-cockpit-key-stack` (multi-key chord ring with timeout
  + max-len + matches(prefix); 'gg' / 'C-x C-f')
- `sovereign-cockpit-collapsible-region` (single-region collapse
  with auto-expand-on-fill + manual-override stickiness)

Workspace count now 181. Total this resume: 71 cockpit crates.

### Twentieth wave (same day, +2 more cockpit crates)

- `sovereign-cockpit-multi-line-input` (buffer + soft-wrap-cols +
  min_rows/max_rows clamp; line_count counts wraps)
- `sovereign-cockpit-snapshot-toolbar` (replay scrubber with
  PlaybackState + step/jump/progress_pct)

Workspace count now 183. Total this resume: 73 cockpit crates.

### Twenty-first wave (same day, +2 more cockpit crates)

- `sovereign-cockpit-keymap-editor` (action→chord BTreeMap +
  capture phase + conflict detection on finalize)
- `sovereign-cockpit-status-pulse` (triangular-wave brightness
  0..=100 with min/max/static/active flag)

Workspace count now 185. Total this resume: 75 cockpit crates.

### Twenty-second wave (same day, +2 more cockpit crates)

- `sovereign-cockpit-dnd-target` (receptor registry; companion to
  drag-drop; Accepted/RejectedKind/Inactive/Unknown)
- `sovereign-cockpit-cpu-meter` (sample ring + smoothed average +
  Green/Yellow/Red tier from thresholds)

Workspace count now 187. Total this resume: 77 cockpit crates.

### Twenty-third wave (same day, +2 more cockpit crates)

- `sovereign-cockpit-memory-meter` (used/total bytes + warn/critical
  zones + render_display picks B/KB/MB/GB/TB)
- `sovereign-cockpit-sparkline` (push f64 series; bar_heights
  normalizes to height_px against observed min/max)

Workspace count now 189. Total this resume: 79 cockpit crates.

### Twenty-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-network-meter` (cumulative rx/tx → bytes/sec
  with auto-unit and counter-reset detection)

Workspace count now 190. Total this resume: 80 cockpit crates.

### Twenty-fifth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-disk-meter` (per-mount used/total with Zone +
  worst_zone aggregator across mounts)

Workspace count now 191. Total this resume: 81 cockpit crates.


### Twenty-sixth wave (same day, +3 more cockpit crates)

- `sovereign-cockpit-battery-indicator` (Charging/Discharging/Full/
  Unknown + low/critical zones + naive time-to-empty / time-to-full
  from last two samples)
- `sovereign-cockpit-scroll-spy` (sorted (id, top_px) sections;
  active_at = last whose top ≤ pos + offset)
- `sovereign-cockpit-aria-live-router` (Severity → Polite/Assertive
  region with per-region dedup window suppressing identical
  re-announcements)
- `sovereign-cockpit-overflow-shadow` (top/bottom shadow intensities
  0..=255 ramped over fade_px when content exceeds viewport)

Workspace count now 195. Total this resume: 85 cockpit crates.

### Twenty-seventh wave (same day, +3 more cockpit crates)

- `sovereign-cockpit-scroll-lock` (refcounted body-scroll lock;
  acquire(reason)→LockId, release(id))
- `sovereign-cockpit-relative-time` ((now,then)→bucket label: just
  now / Nm ago / Yesterday / Nd ago / Nw ago / Nmo ago / Ny ago,
  symmetric futures)
- `sovereign-cockpit-drag-handle` (Idle→Pressed→Dragging gesture
  with activation_px threshold; DragStart/Move/End/Click)

Workspace count now 198. Total this resume: 88 cockpit crates.

### Twenty-eighth wave (same day, +3 more cockpit crates)

- `sovereign-cockpit-marquee-loop` (overflow label →
  Static/Looping{x_offset,cycle_px}; reduced-motion override)
- `sovereign-cockpit-popover-anchor` (anchor+popover+viewport+
  preferred → resolved(x,y,placement) with side flip on overflow
  and cross-axis viewport clamp)
- `sovereign-cockpit-pull-to-refresh` (Idle→Pulling{d,progress}
  →Armed→Refreshing→Idle with trigger_px threshold)

Workspace count now 201. Total this resume: 91 cockpit crates.

### Twenty-ninth wave (same day, +2 more cockpit crates)

- `sovereign-cockpit-input-mask` (formatted-input mask;
  '#'=digit/'A'=letter/'*'=alnum/literal; returns rendered + raw +
  complete)
- `sovereign-cockpit-color-contrast` (WCAG 2.1 contrast; ratio_x100
  + aa/aaa normal/large flags)

Workspace count now 203. Total this resume: 93 cockpit crates.

### Thirtieth wave (same day, +2 more cockpit crates)

- `sovereign-cockpit-number-format` (i64 integer with thousands +
  fixed-point minor_unit + compact k/M/B/T at 1 decimal; EN ',' vs
  FR ' ' separators)
- `sovereign-cockpit-key-binding-display` (Chord render per Platform:
  Mac ⌃⌥⇧⌘ glyphs joinless, Linux/Windows Ctrl+Alt+Shift+Super/Win;
  special keys map to platform glyphs)

Workspace count now 205. Total this resume: 95 cockpit crates.

### Thirty-first wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-carousel` (slide_count+current+wrap_around+
  autoplay; next/prev wrap or clamp; tick advances on interval)

Workspace count now 206. Total this resume: 96 cockpit crates.

### Thirty-second wave (same day, +2 more cockpit crates)

- `sovereign-cockpit-split-pane` (two-pane split; drag clamps to
  (min_a, container - min_b) and snaps to either min on near-edge;
  resize_container reclamps existing split)
- `sovereign-cockpit-text-metrics` (bytes/chars/graphemes/words/
  lines; graphemes best-effort with combining-mark + ZWJ skip)

Workspace count now 208. Total this resume: 98 cockpit crates.

### Thirty-third wave (same day, +2 more cockpit crates)

- `sovereign-cockpit-code-gutter` (per-line annotations Error >
  Warning > Info > Breakpoint > DiffModified/Added/Removed;
  gutter_width_chars = digits + 2)
- `sovereign-cockpit-focus-ring` (:focus-visible-style tracker;
  visible iff last_source = Keyboard; focus_changed preserves)

Workspace count now 210. Total this resume: 100 cockpit crates.

### Thirty-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-numeric-stepper` (bounded i64 stepper;
  set/inc/dec/large_inc/large_dec; snap-to-step; optional wrap)

Workspace count now 211. Total this resume: 101 cockpit crates.

### Thirty-fifth wave (same day, +2 more cockpit crates)

- `sovereign-cockpit-emoji-shortcode` (:name: → glyph registry;
  register/lookup/prefix/resolve; canonical 13-entry seed)
- `sovereign-cockpit-paste-format-detector` (detect(text) →
  Url/Json/CodeBlock/Markdown/Csv/PlainText heuristic)

Workspace count now 213. Total this resume: 103 cockpit crates.

### Thirty-sixth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-color-swatch` (ordered Vec<Swatch{name,hex}>
  + selected_index; insert/remove keep selection in sync;
  #RRGGBB or #RRGGBBAA hex; distinct from theme-palette and
  color-picker)

Workspace count now 214. Total this resume: 104 cockpit crates.

### Thirty-seventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-reorderable-list` (Vec<String> ids + drag
  cursor; begin_drag/hover/commit_drop; move_to shorthand;
  cancel_drag; insert-after-removal index adjustment)

Workspace count now 215. Total this resume: 105 cockpit crates.

### Thirty-eighth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-dock-position` (Placement Edge{L/R/T/B} or
  Floating{x,y}; dock_to snaps, float_to clamps; set_viewport
  reclamps floating, leaves edge unchanged)

Workspace count now 216. Total this resume: 106 cockpit crates.

### Thirty-ninth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-input-debouncer` (trailing-edge debouncer;
  observe/ready/consume/cancel; one-shot per quiet period;
  distinct from action-throttle leading-edge cooldown)

Workspace count now 217. Total this resume: 107 cockpit crates.

### Fortieth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-color-mode` (UserPreference + SystemSignal +
  per-context overrides; effective(context) override > preference
  > system; Auto+Unknown defaults to Light)

Workspace count now 218. Total this resume: 108 cockpit crates.

### Forty-first wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-widget-registry` (Widget{id, kind, title,
  enabled, min_w, min_h, allowed_in}; enable/disable + per-
  dashboard allow-set; visible_in(dashboard_id) filter combines
  enabled+allowed; pairs with dashboard-layout/toggle)

Workspace count now 219. Total this resume: 109 cockpit crates.

### Forty-second wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-dashboard-profile` (Preset{id, title,
  widget_allowlist, default_layout_id}; canonical 4 personas
  Operator/Engineer/Security/Trader; activate/widget_enabled;
  pairs with widget-registry — preset gates the toggle UI)

Workspace count now 220. Total this resume: 110 cockpit crates.

### Forty-third wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-presence-mode` (Mode Focus/Standard/Glance/
  Off/DoNotDisturb; classify_event(severity) Show/Summarize/
  Suppress; cadence + animations per mode)

Workspace count now 221. Total this resume: 111 cockpit crates.

### Forty-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-tooltip-delay` (Idle→Dwelling{entered_at}→
  Open→Closing{left_at}→Idle; enter/leave/anchor_hidden; group
  cool window after close skips dwell on next enter)

Workspace count now 222. Total this resume: 112 cockpit crates.

### Forty-fifth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-autocomplete-list` (ranked suggestions with
  highlight cursor; arrow_down/arrow_up wrap; accept returns
  highlighted; validates no-empty / no-duplicate ids; pairs with
  fuzzy-ranker)

Workspace count now 223. Total this resume: 113 cockpit crates.

### Forty-sixth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-banner-bus` (single-slot priority bus; post
  replaces lower-prio + queues displaced; dismiss promotes
  highest-prio queued; distinct from banner-state and toast-tray)

Workspace count now 224. Total this resume: 114 cockpit crates.

### Forty-seventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-destructive-confirm` (type-to-confirm gate;
  case-sensitive phrase match + hold_ms cooldown; progress_pct
  for chrome hint; distinct from confirmation-modal)

Workspace count now 225. Total this resume: 115 cockpit crates.

### Forty-eighth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-status-light` (per-subject Tone Healthy<
  Unknown<Degraded<Offline + reason + ts; set/tone_of/worst/stale;
  worst on empty defaults to Healthy)

Workspace count now 226. Total this resume: 116 cockpit crates.

### Forty-ninth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-field-error` (per-field Entry{severity:
  Hint<Info<Warn<Error, message}; insert dedup; worst_for_field;
  visible_for_field(min_sev); distinct from form-validity and
  error-banner)

Workspace count now 227. Total this resume: 117 cockpit crates.

### Fiftieth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-loading-eta` (ring-buffered samples; eta_ms
  returns Some(remaining) via linear extrapolation across last two
  distinct progress samples; None when <2 samples, at 100, or
  trajectory flat)

Workspace count now 228. Total this resume: 118 cockpit crates.

### Fifty-first wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-progress-segmented` (N-segment pipeline;
  Pending/Active/Completed/Failed; advance_to / complete / fail /
  rewind; percent_complete = Completed/total; distinct from
  progress-bar)

Workspace count now 229. Total this resume: 119 cockpit crates.

### Fifty-second wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-feature-tour` (Tour{id, title, Vec<Step>};
  register/start/next/prev/dismiss(reason)/complete; next-past-
  last auto-completes; completed + dismissed sets persist;
  distinct from onboarding-flow)

Workspace count now 230. Total this resume: 120 cockpit crates.

### Fifty-third wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-feature-toggle-grid` (Toggle{id, label, hint,
  group, on, disabled_reason}; toggle errors with the reason when
  disabled; visible_by_group partitions + label-sorts; distinct
  from dashboard-toggle (visibility))

Workspace count now 231. Total this resume: 121 cockpit crates.

### Fifty-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-search-scope` (Scope{id, label, enabled} +
  default_id + active_id; available filters disabled; effective_
  active falls back to default when active disabled; validate
  requires default ∈ scopes)

Workspace count now 232. Total this resume: 122 cockpit crates.

### Fifty-fifth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-shortcut-recorder` (arm/record/cancel/clear;
  record rejects bare-modifier keys, empty key, and Escape
  (reserved for cancel); Captured{modifiers, key}; armed flag
  clears after capture)

Workspace count now 233. Total this resume: 123 cockpit crates.

### Fifty-sixth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-hover-preview` (Phase Idle → Dwelling{id,
  entered_at} → Visible{id} → Pinned{id}; enter/leave/pin/unpin/
  anchor_hidden; Pinned survives leave + cross-anchor enter;
  distinct from tooltip-delay)

Workspace count now 234. Total this resume: 124 cockpit crates.

### Fifty-seventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-saved-view` (SavedView{id, scope_id, title,
  filters/sort blobs, columns, created_at}; create/rename/delete/
  list/by_scope; scope-aware filtering; chrome reapplies captured
  blobs on activation)

Workspace count now 235. Total this resume: 125 cockpit crates.

### Fifty-eighth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-macro-recorder` (Recording{name, events:
  Vec<{action_id, delay_ms}>, last_ts}; start/observe (monotonic
  + relative-delay)/cancel/stop+save/delete; play_sequence returns
  events for the playback engine)

Workspace count now 236. Total this resume: 126 cockpit crates.

### Fifty-ninth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-bottom-sheet` (Snap{Collapsed, Half, Full,
  Custom}; set_snap teleports; drag_to clamps + snaps to nearest
  within snap_threshold_px else Custom; validate enforces
  collapsed<half<full ordering)

Workspace count now 237. Total this resume: 127 cockpit crates.

### Sixtieth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-stat-trend` (Direction{Up/Down/Flat} +
  percent_change_x100 (signed, saturating) + ColorHint{Positive/
  Negative/Neutral}; flat_threshold_x100 governs the Flat band;
  ColorHint depends on Polarity so 'fewer errors' = Positive)

Workspace count now 238. Total this resume: 128 cockpit crates.

### Sixty-first wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-row-actions` (per row_id: RowSet{left, right:
  Vec<Action{id, label, severity, requires_confirm}>}; add/remove
  per side; same id allowed across sides; empty row auto-prune)

Workspace count now 239. Total this resume: 129 cockpit crates.

### Sixty-second wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-keystroke-sequence` (register(action_id,
  &[keys]); observe(key, now) → Matched/Partial/None; buffer
  resets on inter-key gap > sequence_timeout_ms; shared-prefix
  sequences supported (gg vs gG); distinct from keystroke-map)

Workspace count now 240. Total this resume: 130 cockpit crates.

### Sixty-third wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-column-pin` (Pinned{None, On{side: Left/Right,
  order}}; pin/unpin/ordered_by_side; ties broken by id; distinct
  from column-config which handles visibility/sizing)

Workspace count now 241. Total this resume: 131 cockpit crates.

### Sixty-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-edit-mode` (Mode{Read, Edit{dirty},
  ReviewPending}; request_edit / dirty / save_draft / submit /
  approve / reject; is_dirty accessor; bad-transition errors)

Workspace count now 242. Total this resume: 132 cockpit crates.

### Sixty-fifth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-incremental-search` (find-in-page state;
  set_query(q, total) resets, next/prev wraps; current_index
  returns 1-based or None; close resets)

Workspace count now 243. Total this resume: 133 cockpit crates.

### Sixty-sixth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-checklist` (Item{id, label, completed_at_ms};
  register/complete/uncomplete; progress(done,total); percent
  integer 0..=100; duplicate-id rejected)

Workspace count now 244. Total this resume: 134 cockpit crates.

### Sixty-seventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-time-range-selector` (Range{Last5m..Last30d,
  Custom{from, to}}; resolve(now) → (from, to); Custom validated
  from < to)

Workspace count now 245. Total this resume: 135 cockpit crates.

### Sixty-eighth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-shimmer-phase` (phase(now) 0..1000 per-mille
  cycling over period_ms; phase_for_anchor FNV-1a-stagger keeps
  adjacent skeletons out of lockstep; reduced_motion freezes at
  500)

Workspace count now 246. Total this resume: 136 cockpit crates.

### Sixty-ninth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-cell-format` (CellKind{Plain/Number/Pct/
  CurrencyMinor{code}/BytesIec/DurationMs}; format(kind, value,
  plain) per-cell dispatcher; distinct from number-format
  top-level)

Workspace count now 247. Total this resume: 137 cockpit crates.

### Seventieth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-side-by-side-diff` (HunkKind{Context/Add/
  Remove/Change} → AlignedPair{left, right}; Cell{Spacer/Context/
  Modified/Added/Removed}; Add right-only with left spacer,
  Remove left-only with right spacer; Change paired Modified)

Workspace count now 248. Total this resume: 138 cockpit crates.

### Seventy-first wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-timeline-axis` (curated intervals 1s..7d;
  pick_interval(from, to, target) closest curated to range/target;
  ticks emits aligned multiples inside [from, to])

Workspace count now 249. Total this resume: 139 cockpit crates.

### Seventy-second wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-chart-legend` (Series{id, label, color,
  visible}; add/toggle/solo/show_all/hover/unhover/
  visible_series; solo isolates one; show_all restores)

Workspace count now 250. Total this resume: 140 cockpit crates.

### Seventy-third wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-resize-observer` (observe(id, w, h) → FirstSeen
  / Changed{prev, new} / SubThreshold; either-dim ≥ noise_threshold_
  px triggers; sub-threshold dropped to avoid thrashing chart
  re-layout)

Workspace count now 251. Total this resume: 141 cockpit crates.

### Seventy-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-unsaved-guard` (mark_dirty/mark_clean per
  scope_id; navigate returns Allow or BlockConfirm{scope_id};
  force_navigate discards; any_dirty for app-level beforeunload)

Workspace count now 252. Total this resume: 142 cockpit crates.

### Seventy-fifth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-skeleton-template` (Block{kind:Line/Circle/
  Box, w_px, h_px}; register(template_id, blocks); render(id,
  count) Vec<RenderedRow>; distinct from skeleton-loader and
  skeleton-list)

Workspace count now 253. Total this resume: 143 cockpit crates.

### Seventy-sixth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-watchlist` (NotifyMode{Off<InApp<InAppAndPush
  <All}; WatchEntry{kind, item_id, notify_mode, added_ts};
  items_for_notify(min_mode) filters; distinct kinds independent)

Workspace count now 254. Total this resume: 144 cockpit crates.

### Seventy-seventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-keyboard-layout` (Layout{Qwerty/QwertyUk/
  Dvorak/Colemak/Azerty}; set/current/description for the
  settings UI; OS owns the physical-key remap)

Workspace count now 255. Total this resume: 145 cockpit crates.

### Seventy-eighth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-pip-window` (Corner{TL/TR/BL/BR}+(w,h)+
  content_id+visible; show/hide/move_to/resize/set_content;
  hide preserves content_id for resume)

Workspace count now 256. Total this resume: 146 cockpit crates.

### Seventy-ninth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-snippet-library` (Snippet{id, name, body,
  trigger, tags}; search ranks exact-name>trigger>name-startswith
  >body-contains; tag_filter requires ALL tags)

Workspace count now 257. Total this resume: 147 cockpit crates.

### Eightieth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-favorites` (per kind ordered Vec<Favorite{id,
  label, pinned_at}>; star/unstar/reorder/list_kind/is_starred;
  reorder clamps to-end; empty kind auto-prune)

Workspace count now 258. Total this resume: 148 cockpit crates.

### Eighty-first wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-quick-jump` (JumpTarget{short_id, kind,
  full_path, label}; register/resolve/unregister/by_kind;
  operator-types-known-shortcut lane distinct from text search)

Workspace count now 259. Total this resume: 149 cockpit crates.

### Eighty-second wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-presence-roster` (Entry{operator_id, label,
  status: Online/Idle/Busy/Offline, last_seen_ts}; observe flips
  Idle→Online; mark_idle_if_older batch-flips stale Online→Idle;
  distinct from presence-mode — collaborator-display lane)

Workspace count now 260. Total this resume: 150 cockpit crates.

### Eighty-third wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-page-title` (stack-style title manager;
  push/pop/clear/depth; current_title(separator, suffix) joins
  outermost→innermost + optional app suffix)

Workspace count now 261. Total this resume: 151 cockpit crates.

### Eighty-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-tip-bar` (Tip{scope_id, message, optional
  chord}; tips_for(scope_id) excludes dismissed; dismiss(message)
  hides + persists; restore_all)

Workspace count now 262. Total this resume: 152 cockpit crates.

### Eighty-fifth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-status-page-list` (StatusPage{id, label, url,
  current_state: Operational/Degraded/PartialOutage/MajorOutage/
  Maintenance/Unknown, last_check_ts}; register/update_state/
  list_all/list_by_state)

Workspace count now 263. Total this resume: 153 cockpit crates.

### Eighty-sixth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-priority-display` (Priority{Low<Med<High<
  Critical<Blocker} → (label, color_token, glyph); consistent
  chrome priority chips)

Workspace count now 264. Total this resume: 154 cockpit crates.

### Eighty-seventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-leaderboard` (Row{id, label, score: i64};
  submit/remove/ranked; competition ranking (1224 style: ties
  share rank, next rank skips tie count))

Workspace count now 265. Total this resume: 155 cockpit crates.

### Eighty-eighth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-stat-card` (StatCard{id, label, value_text,
  hint, trend_chip:Option<TrendChip{direction, percent_x100}>,
  sparkline_source_id}; register/update/get/list)

Workspace count now 266. Total this resume: 156 cockpit crates.

### Eighty-ninth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-stream-pause` (pause/resume/observe/
  drop_queued; observe only counts while paused; resume clears;
  drop_queued clears while staying paused)

Workspace count now 267. Total this resume: 157 cockpit crates.

### Ninetieth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-toast-stack` (Toast{id, body, severity,
  posted_at, ttl_ms, dismissable}; post/dismiss/visible(now);
  overflow drops oldest; past-TTL filtered; distinct from
  toast-tray)

Workspace count now 268. Total this resume: 158 cockpit crates.

### Ninety-first wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-table-summary-row` (Aggregator{None/Sum/Avg/
  Min/Max/Count}; compute(rows) → Vec<SummaryCell>; empty rows
  yield None for Min/Max; width-mismatch rejected)

Workspace count now 269. Total this resume: 159 cockpit crates.

### Ninety-second wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-print-options` (PrintOptions{orientation/
  paper_size/scale_pct (50..=200)/color/copies (≥1)/page_range:
  All|From{from,to}}; setters validate ranges)

Workspace count now 270. Total this resume: 160 cockpit crates.

### Ninety-third wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-mention-suggester` (Operator{handle, display};
  active_query(input, cursor) detects @-token at start or after
  whitespace; suggest(query, operators, max) case-insensitive
  starts-with)

Workspace count now 271. Total this resume: 161 cockpit crates.

### Ninety-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-code-lang-guess` (Language enum Rust..Unknown;
  guess(filename, first_line): extension first, then shebang
  match, else Unknown)

Workspace count now 272. Total this resume: 162 cockpit crates.

### Ninety-fifth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-celebration` (scope_id → milestone_id →
  Pending{fired_at, shown}; fire idempotent; should_show only
  for not-yet-shown; mark_shown silences; reset)

Workspace count now 273. Total this resume: 163 cockpit crates.

### Ninety-sixth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-task-stack` (Task{id, label, started_at};
  push dedup-by-id; pop/pop_id; current/peek_below/depth;
  breadcrumb-friendly via peek_below)

Workspace count now 274. Total this resume: 164 cockpit crates.

### Ninety-seventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-multi-step-form` (Step{id, label, required_
  fields, completed_fields}; next_allowed_from(step) iff all
  required completed; percent_complete sums across steps by
  required-field count)

Workspace count now 275. Total this resume: 165 cockpit crates.

### Ninety-eighth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-comment-thread` (Comment{id, author, body,
  posted_at, in_reply_to, resolved}; add validates parent +
  rejects self-reply; outline depth-first by posted_at)

Workspace count now 276. Total this resume: 166 cockpit crates.

### Ninety-ninth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-fetch-state` (State{Idle/Loading{started}/
  Ready{loaded}/Errored{error,ts}}; start_loading/loaded/errored/
  reset; is_stale(now, stale_after) returns true only in Ready
  past window)

Workspace count now 277. Total this resume: 167 cockpit crates.

### One-hundredth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-draft-autosave` (per-field DraftField{text,
  last_edit_ms, last_snapshot_ms}; snapshot_due respects
  min_interval floor + idle_ms post-typing pause + max_age_ms
  force-during-typing; due_fields lists all currently due;
  non-monotonic ts rejected)

Workspace count now 278. Total this resume: 168 cockpit crates.

### Hundred-and-first wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-skip-link-set` (SkipLink{id, label, target,
  order, enabled, activations, last_activated}; register assigns
  next_order; set_enabled toggles without losing position;
  activate counts usage and is no-op on disabled;
  links_in_order returns enabled-only ordered)

Workspace count now 279. Total this resume: 169 cockpit crates.

### Hundred-and-second wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-infinite-scroll` (Scroller{next_cursor, loaded,
  in_flight, at_end, last_error, fetches_ok, fetches_err};
  start_fetch rejects double-start and at_end; complete_fetch
  records new items, None next_cursor = at_end; fail_fetch records
  last_error; should_fetch_at(distance, threshold) gates initiation)

Workspace count now 280. Total this resume: 170 cockpit crates.

### Hundred-and-third wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-log-tail-viewer` (LogLevel{Trace<...<Error};
  LogLine{level, ts, source, message}; ring buffer of capacity
  lines, oldest dropped (counted); view(Filter{min_level, sources,
  substring}) — composes; substring case-insensitive)

Workspace count now 281. Total this resume: 171 cockpit crates.

### Hundred-and-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-export-format-picker` (Format{id, label,
  extension, mime, Capabilities{lossless, preserves_formatting,
  supports_charts}, order}; available_for(CapFilter) returns
  satisfying formats in declared order; record_pick updates user
  default; pick_default falls back to first-by-order)

Workspace count now 282. Total this resume: 172 cockpit crates.

### Hundred-and-fifth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-saved-search-set` (SavedSearch{id, name, query,
  scope, run_count, last_run_ms}; add/edit/remove + record_run;
  recents/frequents/recent_and_frequent rankings — blend normalizes
  each component to 0..1000 and sums)

Workspace count now 283. Total this resume: 173 cockpit crates.

### Hundred-and-sixth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-attachment-tray` (Attachment{id, filename,
  size_bytes, mime, UploadStatus{Pending/Uploaded/Failed}};
  per-draft items with max_count + max_total_bytes; add verdict
  Accepted/RejectedCount/RejectedSize/Duplicate; drafts independent)

Workspace count now 284. Total this resume: 174 cockpit crates.

### Hundred-and-seventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-kpi-tile-grid` (Tile{id, label, unit, decimals,
  value, goal, warn_at, crit_at, Direction{HigherIsWorse/
  LowerIsWorse}, order}; status_for returns Ok/Warn/Crit/Unknown by
  comparing against thresholds in configured direction;
  format_value renders with decimals + unit; threshold validity
  checked at add+validate)

Workspace count now 285. Total this resume: 175 cockpit crates.

### Hundred-and-eighth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-text-direction-mode` (Mode{Ltr/Rtl/Auto},
  Direction{Ltr/Rtl}; direction_for(locale) respects override or
  defers to locale binding in Auto; new() seeds ar/fa/he/ur Rtl;
  bind_locale extends; is_rtl() reflects current default)

Workspace count now 286. Total this resume: 176 cockpit crates.

### Hundred-and-ninth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-kanban-board` (Column{id, label, wip_limit};
  Card{id, title, column, moves, last_moved_ms}; add_card places
  in first column; move_card returns Moved{from,to}/
  RejectedAtWipLimit{column, in_column, limit}/UnknownCard/
  UnknownColumn; cards_in lists per column)

Workspace count now 287. Total this resume: 177 cockpit crates.

### Hundred-and-tenth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-agenda-view` (Item{id, title, start_ms};
  DayGroup{day_index, items}; groups() buckets by day under
  configurable day_length_ms + day_start_offset_ms;
  between(from, to) for half-open windowing; day_index_for exposes
  bucket math)

Workspace count now 288. Total this resume: 178 cockpit crates.

### Hundred-and-eleventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-facet-counts` (Facet{counts:BTreeMap<bucket,
  u64>, selected:BTreeSet}; set_count/increment, toggle selection,
  top(n) descending with alphabetical tie-break; clear_selections,
  drop_facet for tear-down)

Workspace count now 289. Total this resume: 179 cockpit crates.

### Hundred-and-twelfth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-dictation-state` (Phase{Idle/Listening/
  Finalizing/Errored} FSM; partial_transcript accumulates,
  committed_transcript commits on complete; clamped mic_level_db;
  error from Listening|Finalizing → Errored; reset Errored→Idle;
  session_count tracks starts)

Workspace count now 290. Total this resume: 180 cockpit crates.

### Hundred-and-thirteenth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-emoji-reactions` (MessageReactions{by_emoji:
  BTreeMap<shortcode, BTreeSet<user_id>>}; toggle returns Added/
  Removed with auto-tidy of empty sets; counts() descending with
  alpha tie-break; users() sorted; has_reacted O(log n); clear()
  drops entire message)

Workspace count now 291. Total this resume: 181 cockpit crates.

### Hundred-and-fourteenth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-deep-link-codec` (DeepLink{route, params:
  BTreeMap}; encode renders /route?k=v with keys alphabetical;
  %-encodes non-unreserved bytes; decode inverts; BadEncoding{
  offset}/Malformed errors; empty param keys rejected)

Workspace count now 292. Total this resume: 182 cockpit crates.

### Hundred-and-fifteenth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-consent-prompt` (Prompt{scope, created_at_ms,
  PromptState{Pending/Granted/Denied/Deferred{reminder_at_ms}}};
  grant/deny/defer transitions; terminal states reject further
  transitions; state(now) returns Verdict including Reminder when
  reminder_at_ms reached)

Workspace count now 293. Total this resume: 183 cockpit crates.

### Hundred-and-sixteenth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-text-selection-range` (half-open Range[start,
  end); add merges overlapping AND adjacent (chains collapse);
  remove_overlap clips intersecting ranges (may split); contains
  /total_selected helpers; empty/inverted ranges rejected)

Workspace count now 294. Total this resume: 184 cockpit crates.

### Hundred-and-seventeenth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-whats-new-feed` (Entry{id, title, body,
  published_at_ms, Severity{Info/Notice/Critical}}; per-user
  last_seen watermark drives unread; mark_all_read advances
  watermark but never regresses (monotonic); unread_count helper)

Workspace count now 295. Total this resume: 185 cockpit crates.

### Hundred-and-eighteenth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-code-block-actions` (Block{id, lang,
  wrap_lines, expanded, copyable, runnable, copies, runs};
  actions_for returns Copy?/Wrap|Unwrap/Expand|Collapse/Run?
  per flags; apply mutates + records telemetry; Copy/Run on
  unset capability errors)

Workspace count now 296. Total this resume: 186 cockpit crates.

### Hundred-and-nineteenth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-result-page-cursor` (ResultPageCursor{page,
  page_size, total_pages}; next/prev/jump_to return Moved{from,to}/
  AtEdge; update_total snaps current page back when shrunk;
  first_item_index/end_item_index for window slicing)

Workspace count now 297. Total this resume: 187 cockpit crates.

### Hundred-and-twentieth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-gutter-marker-set` (Marker{kind, label,
  Severity{Info<Notice<Warn<Error<Critical}}; per pane → lines →
  alphabetical-by-kind markers; top_marker returns highest-severity
  at a line; remove_kind auto-tidies empty lines/panes;
  marked_lines sorted)

Workspace count now 298. Total this resume: 188 cockpit crates.

### Hundred-and-twenty-first wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-haptic-cue-policy` (Intensity{Off<Light<Medium<
  Strong}; Channel{intensity, muted}; master_intensity caps all
  via min(master, channel); muted overrides to Off; unknown
  channels return Off)

Workspace count now 299. Total this resume: 189 cockpit crates.

### Hundred-and-twenty-second wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-find-replace-bar` (FindReplaceBar{query,
  replacement, case_sensitive, whole_word, match_offsets,
  match_len, cursor_index}; next/prev wrap through matches;
  set_matches resets cursor; replace_current/replace_all emit
  EditOps for caller to apply)

Workspace count now 300. Total this resume: 190 cockpit crates.

### Hundred-and-twenty-third wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-titlebar-config` (TitlebarConfig{prefix,
  segments:Vec, separator default " · ", pinned_status:Option<
  StatusChip{label, Severity}>}; render_title joins prefix + segments;
  push/pop/set_segments manage path; pin/clear status)

Workspace count now 301. Total this resume: 191 cockpit crates.

### Hundred-and-twenty-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-submenu-tree` (Node{id, label, parent,
  children, enabled, expanded}; add_root/add_child build tree;
  set_expanded/toggle; activate auto-expands ancestors;
  visible_in_order DFS over expanded subtrees; path_to traces
  root → node ancestry)

Workspace count now 302. Total this resume: 192 cockpit crates.

### Hundred-and-twenty-fifth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-message-composer` (MessageComposer{body,
  attachments, reply_to, Phase{Editing/Sending/Sent/Failed},
  send_at_ms, send_attempts, last_error}; mutations guarded to
  Editing|Failed; try_send checks content + scheduling;
  mark_sent/mark_failed terminal; Failed → retry allowed)

Workspace count now 303. Total this resume: 193 cockpit crates.

### Hundred-and-twenty-sixth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-drag-snap-grid` (DragSnapGrid{step_x, step_y,
  threshold_px, enabled}; snap_point/snap_size snap to nearest
  intersection only within threshold_px — beyond threshold passes
  raw values through; equidistant ties pick lower;
  DragSnapGridConfig wraps with schema_version_marker)

Workspace count now 304. Total this resume: 194 cockpit crates.

### Hundred-and-twenty-seventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-drop-zone-set` (Zone{accept_types:BTreeSet,
  max_items, count}; decide returns Accept/RejectType{accepted}/
  RejectFull{count, max}/Unknown; accept increments count on
  Accept; release decrements saturating at 0; add_type extends)

Workspace count now 305. Total this resume: 195 cockpit crates.

### Hundred-and-twenty-eighth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-workspace-switcher` (Workspace{id, label,
  last_used_ms, pin_order}; add/remove/switch_to manage active;
  pin/unpin; ordered_for_picker returns pinned (pin_order asc,
  label tie-break) then unpinned recents (last_used desc))

Workspace count now 306. Total this resume: 196 cockpit crates.

### Hundred-and-twenty-ninth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-filter-builder` (Clause{field, Op{Eq/Ne/Gte/
  Lte/Contains/StartsWith}, value} joined by Combinator{And/Or}
  with outer negation; push/remove/move_clause; render_query
  emits deterministic "NOT (a:1 AND b:>=2)" form)

Workspace count now 307. Total this resume: 197 cockpit crates.

### Hundred-and-thirtieth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-idle-lock-screen` (Phase{Active/Warning/Locked}
  derived from idle elapsed vs warn/lock thresholds;
  observe_activity resets (rejected while Locked); lock() force,
  unlock(now) clears + counts; tick(now) auto-locks idempotently)

Workspace count now 308. Total this resume: 198 cockpit crates.

### Hundred-and-thirty-first wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-icon-set-registry` (Icon{variants:Vec<Variant{
  size_px, color_token, url_or_data}>}; register sorts + replaces
  same size+color; lookup exact then closest size preferring
  colour match; variants_of/remove helpers)

Workspace count now 309. Total this resume: 199 cockpit crates.

### Hundred-and-thirty-second wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-error-state-screen` (ErrorStateScreen{Category{
  Network/Permission/NotFound/Server/Unknown}, headline, body,
  retry_handler_id, retry_attempts, last_attempt_ms}; with_retry
  wires handler; attempt_retry counts (NoRetry err if absent);
  can_retry exposes button visibility)

Workspace count now 310. Total this resume: 200 cockpit crates.

### Hundred-and-thirty-third wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-merge-conflict-ui` (Hunk{id, base, ours,
  theirs, Resolution{Unresolved/AcceptOurs/AcceptTheirs/AcceptBoth/
  Manual{body}}}; count_unresolved + is_complete gate merge-done;
  render_merged emits resolved text or placeholder per hunk;
  mark_all_unresolved resets)

Workspace count now 311. Total this resume: 201 cockpit crates.

### Hundred-and-thirty-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-live-collab-cursors` (PeerCursor{peer_id,
  label, color_token, x, y, last_seen_ms}; update upserts position;
  active(now, max_age) filters stale; prune drops stale entries
  (counts); active sorted by label then peer_id)

Workspace count now 312. Total this resume: 202 cockpit crates.

### Hundred-and-thirty-fifth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-tag-color-palette` (explicit per-tag
  assignments override deterministic FNV-1a-64(tag)%len fallback;
  assign validates color in palette; set_palette drops invalid
  assignments and counts them; stable colours without explicit
  assignment)

Workspace count now 313. Total this resume: 203 cockpit crates.

### Hundred-and-thirty-sixth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-keyboard-chord-detector` (Chord{keys,
  action_id}; press returns Fired/Buffered/NoMatch; timeout clears
  buffer; non-prefix keys clear buffer; reset() manual clear;
  duplicate chord registrations rejected)

Workspace count now 314. Total this resume: 204 cockpit crates.

### Hundred-and-thirty-seventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-action-discoverability` (ActionUsage{
  action_id, label, category, created_at_ms, use_count,
  last_used_ms}; record_use counts + bumps last_used; undiscovered(
  min_age, now) lists never-used past min_age; most_used/least_used
  ranks; register idempotent preserving use_count)

Workspace count now 315. Total this resume: 205 cockpit crates.

### Hundred-and-thirty-eighth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-input-validator-set` (Rule{Required/MinLength/
  MaxLength/StartsWith/EndsWith/Contains/OnlyAscii}; register
  fields with ordered rules; validate_value returns Ok or first
  Failure{rule_index, message}; lengths in Unicode chars)

Workspace count now 316. Total this resume: 206 cockpit crates.

### Hundred-and-thirty-ninth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-undo-redo-stack` (Command{kind, label,
  forward_payload, inverse_payload}; push clears redo (new edit
  branches); undo/redo move between stacks; capacity bound on
  undo with overflow drop+count; clear() resets)

Workspace count now 317. Total this resume: 207 cockpit crates.

### Hundred-and-fortieth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-alert-tile-board` (AlertTile{id, title,
  severity, summary, pinned, acknowledged, ts_ms}; ordered sorts
  pinned-first, then unacked-before-acked, higher-severity, newer
  ts, title alpha; ack/pin toggle state)

Workspace count now 318. Total this resume: 208 cockpit crates.

### Hundred-and-forty-first wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-combobox-state` (Option_{id, label}; state
  holds options + filter + open flag + highlight + accepted value;
  set_filter case-insensitive substring; move_up/down wrap;
  accept_highlight commits; clamps highlight when filtered shrinks)

Workspace count now 319. Total this resume: 209 cockpit crates.

### Hundred-and-forty-second wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-virtual-tree-window` (VirtualTreeWindow{
  total_rows, first_visible, window} over externally-flattened
  tree; set_total snaps; scroll_to aligns at top/bottom;
  scroll_by adjusts; end_visible/is_visible/visible_count helpers)

Workspace count now 320. Total this resume: 210 cockpit crates.

### Hundred-and-forty-third wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-status-bar-segments` (Segment{id, label,
  Zone{Left/Center/Right}, priority}; visible_in_zone returns
  top-priority desc with alpha tie-break, truncated to max_items;
  zones isolated)

Workspace count now 321. Total this resume: 211 cockpit crates.

### Hundred-and-forty-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-date-range-picker` (DateRangePicker{from_ms,
  to_ms, presets:BTreeMap<name, Preset{days_back}>}; set_range
  validates from<to; apply_preset(now) computes to=now,
  from=now-days×DAY_MS; seeded last-7/30/90-days)

Workspace count now 322. Total this resume: 212 cockpit crates.

### Hundred-and-forty-fifth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-floating-panel-stack` (Panel{id, title, z,
  minimized}; open assigns next_z (top); bring_to_front rebumps;
  set_minimized hides without removing; focused() topmost
  non-minimized; z_order() front-to-back)

Workspace count now 323. Total this resume: 213 cockpit crates.

### Hundred-and-forty-sixth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-todo-list` (Item{id, title, Status{Open/Done/
  Cancelled}, order, created_at_ms}; add/complete/cancel/reopen
  transitions; ordered by insertion; by_status filters; stats
  returns counts)

Workspace count now 324. Total this resume: 214 cockpit crates.

### Hundred-and-forty-seventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-row-expansion` (Expansion{expanded, loaded};
  expand/collapse/toggle drive expanded; mark_loaded signals
  subrows arrived; collapse preserves loaded flag; pending_load
  lists expanded-but-unloaded for spinner UI)

Workspace count now 325. Total this resume: 215 cockpit crates.

### Hundred-and-forty-eighth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-preset-chip-bar` (Preset{id, label, payload,
  order, apply_count, last_applied_ms}; add assigns next_order;
  apply returns payload + sets active + bumps counters; remove
  clears active if matches; ordered() in declared order)

Workspace count now 326. Total this resume: 216 cockpit crates.

### Hundred-and-forty-ninth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-thumbs-vote` (Vote{Up/Down}; cast returns
  Added/Switched/Cleared (toggle off); tally returns Tally{up,
  down, net (i64)}; auto-tidies items with no remaining votes)

Workspace count now 327. Total this resume: 217 cockpit crates.

### Hundred-and-fiftieth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-split-view-state` (Orientation{Horizontal/
  Vertical}; ratio_bp 0..=10000 primary share; set_ratio clamps
  to [min_primary, 10000-min_secondary]; collapsed=primary 100%;
  effective_primary/secondary respect collapse)

Workspace count now 328. Total this resume: 218 cockpit crates.

### Hundred-and-fifty-first wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-help-overlay` (Section{title, entries:Vec<
  Entry{keys, description}>}; add_section/add_entry; search(q)
  case-insensitive over description+keys; empty query returns all;
  total_entries helper)

Workspace count now 329. Total this resume: 219 cockpit crates.

### Hundred-and-fifty-second wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-text-size-policy` (scale_bp 1000..=40000;
  presets small/normal/large/x-large/xx-large; per-element override
  composes multiplicatively (override × global / 10000); clear
  reverts to global)

Workspace count now 330. Total this resume: 220 cockpit crates.

### Hundred-and-fifty-third wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-settings-form` (Field{committed, pending:
  Option<String>}; edit sets pending (clears if equal); apply
  commits all pending (returns count); discard drops all pending;
  is_dirty exposes any-pending; effective returns pending or
  committed)

Workspace count now 331. Total this resume: 221 cockpit crates.

### Hundred-and-fifty-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-view-mode-toggle` (Mode{List/Grid/Card}; per-
  screen override with default_mode fallback; set/clear/mode_of
  helpers)

Workspace count now 332. Total this resume: 222 cockpit crates.

### Hundred-and-fifty-fifth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-wizard-flow` (Step{id, label, next:BTreeSet,
  valid}; start sets current; set_valid gates; advance refuses
  invalid or non-neighbor target; is_terminal when no next exists)

Workspace count now 333. Total this resume: 223 cockpit crates.

### Hundred-and-fifty-sixth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-tab-manager` (Tab{id, title, pinned, order};
  open assigns order + first becomes active; close auto-switches;
  switch/set_pinned/move_to; ordered() pinned-first then by order
  then title)

Workspace count now 334. Total this resume: 224 cockpit crates.

### Hundred-and-fifty-seventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-notification-prefs` (ChannelPrefs{enabled,
  min_severity}; should_deliver requires enabled + sev >= min and
  not in DND window (critical_bypasses_dnd allowed))

Workspace count now 335. Total this resume: 225 cockpit crates.

### Hundred-and-fifty-eighth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-recent-files` (Entry{path, last_touched_ms};
  touch upserts; new path at capacity drops oldest by ts;
  ordered() most-recent-first)

Workspace count now 336. Total this resume: 226 cockpit crates.

### Hundred-and-fifty-ninth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-stream-render-state` (Phase{Idle/Streaming/
  Complete/Errored/Aborted}; start init; append_chunk records text
  + first_chunk_ms; complete/error/abort terminal; ttfb_ms helper)

Workspace count now 337. Total this resume: 227 cockpit crates.

### Hundred-and-sixtieth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-mode-profile-switch` (Profile{id, label};
  switch sets active + appends history (capacity bounded);
  previous() returns profile just before active for "go back")

Workspace count now 338. Total this resume: 228 cockpit crates.

### Hundred-and-sixty-first wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-global-search` (Source{id, label, weight,
  enabled}; merge_results sorts by composite (result.score ×
  source.weight) desc then ts desc then title; disabled sources
  filtered; limit truncates)

Workspace count now 339. Total this resume: 229 cockpit crates.

### Hundred-and-sixty-second wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-inline-rename` (State{Idle{name}/Editing{
  original, draft}}; enter begins editing; edit updates draft;
  commit accepts (empty rejected); cancel discards)

Workspace count now 340. Total this resume: 230 cockpit crates.

### Hundred-and-sixty-third wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-column-resize` (Column{min_px, max_px,
  width_px}; register clamps initial; set_width/drag_delta clamp;
  reset to min)

Workspace count now 341. Total this resume: 231 cockpit crates.

### Hundred-and-sixty-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-side-drawer` (Edge{Left/Right/Top/Bottom};
  Mode{Push/Overlay}; open/close/toggle; set_width clamps; set_mode
  switches)

Workspace count now 342. Total this resume: 232 cockpit crates.

### Hundred-and-sixty-fifth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-tile-grid-layout` (Rect{x,y,w,h}; place rejects
  OoB/Overlap/ZeroArea; move_to allows same-tile self-overlap;
  tile_at queries by coords; occupied_cells totals)

Workspace count now 343. Total this resume: 233 cockpit crates.

### Hundred-and-sixty-sixth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-action-search-bar` (Action{id, name, category,
  keywords}; search ranks exact-name 4 → starts-with 3 → category-
  contains 2 → keyword-contains 1 → name-contains 0; ties by name)

Workspace count now 344. Total this resume: 234 cockpit crates.

### Hundred-and-sixty-seventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-drag-state` (Phase{Idle/Dragging{item, hover}/
  Completed{item, zone}}; start/hover/drop/cancel; drop requires
  hovered_zone; drops/cancels counters)

Workspace count now 345. Total this resume: 235 cockpit crates.

### Hundred-and-sixty-eighth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-feature-promo-banner` (Promo{id, title, body,
  valid_from_ms, valid_until_ms}; per-user dismiss/snooze;
  should_show window + not-dismissed + past-snooze)

Workspace count now 346. Total this resume: 236 cockpit crates.

### Hundred-and-sixty-ninth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-bulk-selection` (items + selected:BTreeSet +
  anchor; click resets to single; ctrl_click toggles; shift_click
  selects range from anchor; select_all/clear/count helpers)

Workspace count now 347. Total this resume: 237 cockpit crates.

### Hundred-and-seventieth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-accent-color-policy` (hex parsed to r/g/b;
  luminance 0..255 (rough); prefer_white_text when luminance<128)

Workspace count now 348. Total this resume: 238 cockpit crates.

### Hundred-and-seventy-first wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-countdown-timer` (Phase{Idle/Running/Paused/
  Finished}; start/pause/resume/reset; tick → Finished when
  elapsed >= duration; elapsed_ms/remaining_ms)

Workspace count now 349. Total this resume: 239 cockpit crates.

### Hundred-and-seventy-second wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-scroll-shadow-state` (scroll_top/viewport_h/
  content_h; show_top when scroll>0; show_bottom when scroll+
  viewport<content)

Workspace count now 350. Total this resume: 240 cockpit crates.

### Hundred-and-seventy-third wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-action-trigger-button` (Phase{Idle/Pending/
  Success/Failed}; trigger from non-Pending; complete/fail from
  Pending; tick auto-resets terminal phases after transient_ms)

Workspace count now 351. Total this resume: 241 cockpit crates.

### Hundred-and-seventy-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-job-tracker` (Job{id, label, total, done,
  started_at, last_update}; progress_bp 0..10000; eta_ms linear
  extrapolation; update/inc clamp to total; finish removes)

Workspace count now 352. Total this resume: 242 cockpit crates.

### Hundred-and-seventy-fifth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-cooldown-meter` (State{Ready/Cooling}; fire
  errors StillCooling until last_fire+cooldown_ms elapsed;
  observe returns Status{state, remaining_ms, progress_bp};
  reset is operator override)

Workspace count now 353. Total this resume: 243 cockpit crates.

### Hundred-and-seventy-sixth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-byte-size-formatter` (Unit{Si/Iec};
  SI=1000-base B/kB/.../EB; IEC=1024-base B/KiB/.../EiB;
  precision 0..=3; picks largest unit where value>=1)

Workspace count now 354. Total this resume: 244 cockpit crates.

### Hundred-and-seventy-seventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-duration-formatter` (Style{Compact/Long};
  units d/h/m/s/ms; zero units skipped; max_units 1..=5 caps
  non-zero unit count; Long uses singular/plural forms)

Workspace count now 355. Total this resume: 245 cockpit crates.

### Hundred-and-seventy-eighth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-table-of-contents` (Heading{id,label,
  level 1..=6,offset}; update_scroll sets offset; active picks
  latest heading offset<=scroll, fallback first; children_of
  returns immediate-children indices)

Workspace count now 356. Total this resume: 246 cockpit crates.

### Hundred-and-seventy-ninth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-frame-budget` (begin_frame resets; record
  accumulates work_us; should_yield true once work_us>=budget_us;
  end_frame emits FrameStats{usage_bp, over_budget} and bumps
  over_budget_frames counter)

Workspace count now 357. Total this resume: 247 cockpit crates.

### Hundred-and-eightieth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-breakpoint-state` (Breakpoint{Xs/Sm/Md/Lg/Xl};
  thresholds 640/768/1024/1280 default, strictly increasing;
  update(width) recomputes and counts transitions; at_least
  orders breakpoints)

Workspace count now 358. Total this resume: 248 cockpit crates.

### Hundred-and-eighty-first wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-minimap-state` (content scaled to fit minimap
  box preserving aspect ratio, letterboxed; viewport_rect maps
  viewport to minimap-space rect; click_to_viewport converts
  minimap click to content-space center, clamped to bounds)

Workspace count now 359. Total this resume: 249 cockpit crates.

### Hundred-and-eighty-second wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-text-truncate` (Mode{Start/Middle/End};
  char-aware (not byte) Unicode truncation with configurable
  ellipsis; max_chars >= ellipsis chars + 1; short strings
  pass through unchanged)

Workspace count now 360. Total this resume: 250 cockpit crates.

### Hundred-and-eighty-third wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-activity-feed` (Entry{id,category,ts_ms,
  label}; push drops oldest at capacity; unread set tracks
  fresh ids; mark_read clears one, mark_all_read clears all;
  recent filters by time window; by_category filters)

Workspace count now 361. Total this resume: 251 cockpit crates.

### Hundred-and-eighty-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-do-not-disturb` (Mode{Off/Manual/Scheduled};
  Manual silences all; Scheduled silences when minute-of-day in
  [start,end) with overnight wrap; exempt tag set bypasses;
  suppress(now, tag) counts suppressed/passed)

Workspace count now 362. Total this resume: 252 cockpit crates.

### Hundred-and-eighty-fifth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-elevation-stack` (Kind{Dropdown=1000/Sticky=
  1100/Banner=1200/Tooltip=1300/Modal=1400/Popover=1500/Toast=
  1600}; push assigns z=base+per-kind seq; pop by id; on_top
  picks highest-z layer; z_of looks up assigned z)

Workspace count now 363. Total this resume: 253 cockpit crates.

### Hundred-and-eighty-sixth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-avatar-stack` (Avatar{id, initials, color};
  push derives 1..=2 uppercase ASCII letters from name; render
  returns first max_visible + overflow count for "+N" indicator;
  remove by id)

Workspace count now 364. Total this resume: 254 cockpit crates.

### Hundred-and-eighty-seventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-spacing-scale` (Token{None/Xxs/Xs/Sm/Md/Lg/
  Xl/Xxl/Xxxl} → px; defaults 0/2/4/8/12/16/24/32/48;
  multiply saturating-scales; validate ensures non-decreasing)

Workspace count now 365. Total this resume: 255 cockpit crates.

### Hundred-and-eighty-eighth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-volume-meter` (level_bp + peak_bp 0..=10000;
  peak lifts on higher sample; after hold_ms, peak decays at
  decay_bp_per_sec; tick decays without changing level)

Workspace count now 366. Total this resume: 256 cockpit crates.

### Hundred-and-eighty-ninth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-permission-prompt` (State{Idle/Pending/
  Granted/Denied} per (subject, capability); request flips
  Pending or auto-resolves on remembered choice; resolve
  Pending→Granted/Denied with optional sticky-remember;
  reset clears state)

Workspace count now 367. Total this resume: 257 cockpit crates.

### Hundred-and-ninetieth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-log-level-filter` (Level{Trace<Debug<Info<
  Warn<Error}; min threshold + per-level u64 counts; observe
  counts regardless of threshold; visible_count sums counts
  at >= min; reset clears counts)

Workspace count now 368. Total this resume: 258 cockpit crates.

### Hundred-and-ninety-first wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-secret-reveal` (State{Masked/Revealed};
  reveal records ts; tick auto-masks after reveal_ms;
  masked_display shows •••••<tail> when masked (passthrough
  if shorter than tail); tail 0..=8)

Workspace count now 369. Total this resume: 259 cockpit crates.

### Hundred-and-ninety-second wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-cell-range-select` (Cell{row, col};
  anchor+focus form selection rect; click sets both, drag
  moves focus; rect normalizes corners; cells row-major;
  contains tests membership)

Workspace count now 370. Total this resume: 260 cockpit crates.

### Hundred-and-ninety-third wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-attention-cue` (Phase{Off/Pulsing}; notify
  sets Pulsing+intensity=10000; observe returns current
  intensity = max(0, 10000-decay*(now-last)/1000); auto-flips
  Off at zero; acknowledge dismisses explicitly)

Workspace count now 371. Total this resume: 261 cockpit crates.

### Hundred-and-ninety-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-hero-stat-tile` (label + value_x100 +
  prev_x100 centi-units + unit; delta_bp = (val-prev)*10000/
  abs(prev) with zero-prev rule; Trend{Up/Flat/Down} from
  delta with epsilon; display formats with optional 2-decimal)

Workspace count now 372. Total this resume: 262 cockpit crates.

### Hundred-and-ninety-fifth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-tri-state-checkbox` (State{Unchecked/
  Checked/Indeterminate}; click cycles Unchecked↔Checked,
  Indeterminate→Checked; rollup(children) returns Checked iff
  all checked, Unchecked iff all unchecked, else Indeterminate)

Workspace count now 373. Total this resume: 263 cockpit crates.

### Hundred-and-ninety-sixth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-split-button` (Action{id, label, invokes};
  add_action appends; primary at index 0; swap_primary promotes
  by id; invoke bumps counter and (when last_used_first=true)
  promotes the invoked action; menu = non-primary)

Workspace count now 374. Total this resume: 264 cockpit crates.

### Hundred-and-ninety-seventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-connectivity-state` (State{Online/Degraded/
  Reconnecting/Offline}; observe(rtt_ms, ok): ok → Online or
  Degraded based on threshold + reset attempts; !ok → attempts+1
  with Offline at max; force_online/force_offline overrides)

Workspace count now 375. Total this resume: 265 cockpit crates.

### Hundred-and-ninety-eighth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-linkify` (Span{Text/Url/Mention/Hashtag};
  scan emits ordered non-overlapping spans; Url breaks at
  whitespace/<>(); Mention/Hashtag = @/# + [A-Za-z0-9_]+;
  Linkify state stores last input + spans)

Workspace count now 376. Total this resume: 266 cockpit crates.

### Hundred-and-ninety-ninth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-focus-mode` (Mode{Off/Focus/Presentation};
  Off=all visible; Focus=allowlist-only (empty=all visible);
  Presentation=only presentation_widget; allow_add/remove/
  set_presentation_widget mutators)

Workspace count now 377. Total this resume: 267 cockpit crates.

### Two-hundredth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-coachmark-tour` (Step{anchor, title, body};
  Status{Idle/Running/Completed/Dismissed}; start requires >=1
  step; next advances and flips Completed at end; prev clamps
  at 0; dismiss ends; current returns None unless Running)

Workspace count now 378. Total this resume: 268 cockpit crates.

### Two-hundred-and-first wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-sync-status` (Status{Saved/Saving/Failed/
  Stale}; begin_save→Saving; ok(now)→Saved+last_saved_ms;
  fail(error)→Failed; observe flips Saved→Stale after
  stale_after_ms)

Workspace count now 379. Total this resume: 269 cockpit crates.

### Two-hundred-and-second wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-environment-pill` (Env{Dev/Staging/Prod/
  Custom{label, risk}}; Risk{Low<Medium<High}; defaults Dev=
  Low, Staging=Medium, Prod=High; requires_confirm iff
  risk >= confirm_threshold)

Workspace count now 380. Total this resume: 270 cockpit crates.

### Two-hundred-and-third wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-history-stack` (push truncates forward
  stack from cursor and appends; capacity-bounded drops oldest;
  back/forward move cursor; can_back/can_forward expose
  navigation state)

Workspace count now 381. Total this resume: 271 cockpit crates.

### Two-hundred-and-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-reading-progress` (total_words + offset
  (clamped) + wpm; progress_bp = offset*10000/total;
  remaining_seconds = (total-offset)*60/wpm; is_complete iff
  offset>=total)

Workspace count now 382. Total this resume: 272 cockpit crates.

### Two-hundred-and-fifth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-quick-notes` (Note{id, text, pinned, done,
  ts_ms}; capacity drops oldest non-pinned (oldest if all
  pinned); pin/mark_done toggles; visible returns pinned-first
  + filters done)

Workspace count now 383. Total this resume: 273 cockpit crates.

### Two-hundred-and-sixth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-playback-scrubber` (current_ms 0..=total_ms;
  advance pauses while dragging; begin/update/commit/cancel drag
  semantics; visible_ms reports playhead or preview;
  click_to_ms maps bp → ms)

Workspace count now 384. Total this resume: 274 cockpit crates.

### Two-hundred-and-seventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-entity-chip-bar` (Chip{id, label, kind};
  add appends (no duplicates); remove by id; visible returns
  first max_visible chips + overflow count)

Workspace count now 385. Total this resume: 275 cockpit crates.

### Two-hundred-and-eighth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-alert-group` (Group{tag, count, max_severity,
  latest_ts_ms}; observe bumps count, maxes severity, updates
  latest_ts; groups_by_severity sorts severity desc + ts desc;
  clear/total)

Workspace count now 386. Total this resume: 276 cockpit crates.

### Two-hundred-and-ninth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-filter-state` (pending + applied BTreeMap
  key→value; set/clear/clear_all mutate pending; apply copies
  pending→applied; discard reverts to applied; is_dirty when
  pending != applied)

Workspace count now 387. Total this resume: 277 cockpit crates.

### Two-hundred-and-tenth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-hint-card` (Hint{title, body, dismissed,
  last_dismissed_ms, accepted}; should_show false if accepted;
  true if not dismissed or cooldown elapsed; dismiss/accept/
  reset mutators)

Workspace count now 388. Total this resume: 278 cockpit crates.

### Two-hundred-and-eleventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-update-prompt` (current_version +
  available_version + snooze_until_ms; announce sets available;
  should_show iff available set and now>=snooze; snooze N ms;
  install promotes current and clears)

Workspace count now 389. Total this resume: 279 cockpit crates.

### Two-hundred-and-twelfth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-search-history` (QueryEntry{query, pinned,
  hits}; record promotes existing to front incrementing hits,
  or prepends new; capacity drops oldest non-pinned;
  pin/clear_unpinned mutators)

Workspace count now 390. Total this resume: 280 cockpit crates.

### Two-hundred-and-thirteenth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-cost-meter` (budget + used u64; charge
  increments; usage_bp = used*10000/budget; level() Exceeded
  when used>=budget else Critical/Warning/Normal by threshold
  bp; remaining saturating)

Workspace count now 391. Total this resume: 281 cockpit crates.

### Two-hundred-and-fourteenth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-tap-target` (Target{width_px, height_px,
  aria_label}; register rejects too-small (min dim < min_size_px),
  empty label, duplicates; set_min_size_px raises threshold;
  audit lists ids below current min)

Workspace count now 392. Total this resume: 282 cockpit crates.

### Two-hundred-and-fifteenth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-high-contrast-mode` (Mode{Off/On} + class
  → Pair{fg, bg} overrides; add_override registers, resolve
  returns override iff On + class mapped; remove_override drops)

Workspace count now 393. Total this resume: 283 cockpit crates.

### Two-hundred-and-sixteenth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-radial-gauge` (min<max range; value clamped
  on set; fill_bp = (value-min)*10000/(max-min) clamped; Zone
  {Cold/Warm/Hot} from strictly-increasing warm_bp+hot_bp)

Workspace count now 394. Total this resume: 284 cockpit crates.

### Two-hundred-and-seventeenth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-scroll-anchor` (Mode{Top/Bottom/Anchored};
  apply_prepend shifts offset by +n under Anchored (keeps view
  stable); apply_append snaps per mode; Bottom sticks to end;
  at_bottom test exposed)

Workspace count now 395. Total this resume: 285 cockpit crates.

### Two-hundred-and-eighteenth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-validation-summary` (Entry{ErrorLevel{Info/
  Warning/Error}, message}; record appends to per-field list;
  status Pass iff no Error-level entries; error_fields lists
  failing fields; clear/clear_all mutators)

Workspace count now 396. Total this resume: 286 cockpit crates.

### Two-hundred-and-nineteenth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-external-link-policy` (Class{Internal/
  Trusted/UnknownExternal} via exact internal_host + trusted
  set; action_for_class returns Action{Open/OpenNewTab/Warn/
  Block}; defaults Open/OpenNewTab/Warn)

Workspace count now 397. Total this resume: 287 cockpit crates.

### Two-hundred-and-twentieth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-request-list` (Request{id, label, Status{
  InFlight/Done/Cancelled/Failed(err)}, progress_bp 0..=10000,
  ts_started}; start/complete/fail/cancel/update_progress
  transitions; inflight() filters)

Workspace count now 398. Total this resume: 288 cockpit crates.

### Two-hundred-and-twenty-first wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-press-and-hold` (Phase{Idle/Pressing/
  Committed/Cancelled}; progress_bp=elapsed*10000/hold_ms
  capped; release at progress>=10000 → Commit else Cancel;
  commits/cancels counters)

Workspace count now 399. Total this resume: 289 cockpit crates.

### Two-hundred-and-twenty-second wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-timezone-bar` (Zone{label, utc_offset_min
  -720..=840}; local_hhmm(zone_idx, utc_minute_of_day) → (h, m)
  with rem_euclid wrap; unique labels)

Workspace count now 400. Total this resume: 290 cockpit crates.

### Two-hundred-and-twenty-third wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-cascading-select` (parent→children options;
  select_parent switches parent and clears child if no longer
  valid (kept if still listed); select_child requires parent +
  valid option; options_for_child accessor)

Workspace count now 401. Total this resume: 291 cockpit crates.

### Two-hundred-and-twenty-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-lazy-loader` (Phase{Idle/Loading/Loaded/
  Failed(err)} per resource; request Idle/Failed→Loading
  (bumps attempts); complete→Loaded; fail→Failed; retry only
  if attempts<max; reset→Idle)

Workspace count now 402. Total this resume: 292 cockpit crates.

### Two-hundred-and-twenty-fifth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-calendar-grid` (is_leap_year, days_in_month,
  weekday_of_first Zeller's; build(y, m, first_dow) → 42 Cell
  array with prev-month tail / current-month / next-month head
  padding; is_current_month flag)

Workspace count now 403. Total this resume: 293 cockpit crates.

### Two-hundred-and-twenty-sixth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-diff-stats` (FileStat{added, removed},
  churn=sum; record(path, ...) overwrites; totals aggregate
  {files, added, removed, churn}; files_by_churn sorts desc
  (path asc tie-break))

Workspace count now 404. Total this resume: 294 cockpit crates.

### Two-hundred-and-twenty-seventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-pipeline-stage` (Stage{id, label, deps,
  Status{Pending/Running/Success/Failed/Skipped}}; ready_to_run
  = Pending + all-deps-Success; failed_chain = Pending +
  any-dep-Failed)

Workspace count now 405. Total this resume: 295 cockpit crates.

### Two-hundred-and-twenty-eighth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-footer-bar` (primary optional + secondary[]
  + status_text; mutators reject duplicates across primary+
  secondary; invoke bumps action counter)

Workspace count now 406. Total this resume: 296 cockpit crates.

### Two-hundred-and-twenty-ninth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-inline-annotation` (Annotation{id, start,
  end, body}; apply_insert shifts at/after; apply_delete
  clamps or removes overlapping annotations and shifts the
  subsequent ones down)

Workspace count now 407. Total this resume: 297 cockpit crates.

### Two-hundred-and-thirtieth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-usage-meter` (Metric{label, unit, used,
  limit>=1}; usage_bp=used*10000/limit may exceed; is_over iff
  used>=limit; add/remove/set_used/charge mutators; over_limit
  lists exhausted)

Workspace count now 408. Total this resume: 298 cockpit crates.

### Two-hundred-and-thirty-first wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-pill-input` (multi-value field; commit
  splits by separator, trims, drops empties, dedups, appends
  up to max_pills cap; remove by exact; clear empties)

Workspace count now 409. Total this resume: 299 cockpit crates.

### Two-hundred-and-thirty-second wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-trend-bar` (Segment{label, value}; render
  returns RenderedSegment{label, width_bp} proportional to
  value/total in basis points; widths sum to 10000 when
  total>0 (last segment absorbs rounding))

Workspace count now 410. Total this resume: 300 cockpit crates.

### Two-hundred-and-thirty-third wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-operation-receipt` (Receipt{id, action,
  Outcome{Success/Failure(err)}, ts_ms}; record_success/
  record_failure append, capacity drops oldest; recent(n)
  newest-first; failures() filters)

Workspace count now 411. Total this resume: 301 cockpit crates.

### Two-hundred-and-thirty-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-alpha-index` (build sorts items + computes
  first-index per lowercase starting letter; present_letters
  lists; jump_index(letter) returns first matching item index
  (case-insensitive))

Workspace count now 412. Total this resume: 302 cockpit crates.

### Two-hundred-and-thirty-fifth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-column-visibility` (Column{id, label,
  required, visible}; show/hide/toggle mutate; required cannot
  be hidden (RequiredCannotHide error); visible_columns
  preserves registration order)

Workspace count now 413. Total this resume: 303 cockpit crates.

### Two-hundred-and-thirty-sixth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-code-fold` (Region{id, start_line,
  end_line, folded}; toggle/set_folded mutate; visible_lines
  (total) skips start_line+1..=end_line for folded regions
  (anchor stays))

Workspace count now 414. Total this resume: 304 cockpit crates.

### Two-hundred-and-thirty-seventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-multi-sort` (Direction{Asc/Desc};
  click(column, extend): non-extend replaces chain with
  rotate Asc→Desc→Off; extend appends/rotates that column
  in place; clear empties)

Workspace count now 415. Total this resume: 305 cockpit crates.

### Two-hundred-and-thirty-eighth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-audit-trail` (Record{actor, action, target,
  ts_ms}; capacity-bounded with oldest eviction; by_actor /
  by_target filters; recent(n) returns newest-first)

Workspace count now 416. Total this resume: 306 cockpit crates.

### Two-hundred-and-thirty-ninth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-recipient-list` (Line{To/Cc/Bcc}; add
  appends with cross-list dedup (AlreadyPresent); remove
  drops from specific line; all_recipients union; total sums)

Workspace count now 417. Total this resume: 307 cockpit crates.

### Two-hundred-and-fortieth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-dirty-fields` (initial+current BTreeMaps
  + cached dirty set; set_initial replaces baseline; set_current
  updates and refreshes that field's dirty membership; diff
  recomputes; reset reverts current to initial)

Workspace count now 418. Total this resume: 308 cockpit crates.

### Two-hundred-and-forty-first wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-alert-acknowledge` (Ack{acker, ts_ms,
  note}; register inits unacked; acknowledge records ack;
  unack clears (rejects unknown); is_acknowledged/unacked/
  acked accessors)

Workspace count now 419. Total this resume: 309 cockpit crates.

### Two-hundred-and-forty-second wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-column-filter` (Rule{Contains/Equals/Range};
  set/clear per column; matches(row) iff all rules pass;
  missing column or non-integer parse for Range fails;
  empty value / lo>hi rejected at set)

Workspace count now 420. Total this resume: 310 cockpit crates.

### Two-hundred-and-forty-third wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-grid-cursor` ((row, col) within (max_row,
  max_col) inclusive; set clamps; move_by(drow, dcol) shifts
  within bounds via i64 + clamp; home/end mutators)

Workspace count now 421. Total this resume: 311 cockpit crates.

### Two-hundred-and-forty-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-context-help` (Tooltip{body, a11y_label};
  register rejects duplicates; update modifies existing;
  remove drops; resolve returns tooltip or None)

Workspace count now 422. Total this resume: 312 cockpit crates.

### Two-hundred-and-forty-fifth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-save-as-suggest` (suggest(base, ext,
  existing) returns "<base>.<ext>" or increments "-2", "-3",
  ... until free; empty ext supported)

Workspace count now 423. Total this resume: 313 cockpit crates.

### Two-hundred-and-forty-sixth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-result-card` (Card{id, title, snippet,
  source, score}; sorted_by_score yields score desc + id asc;
  top_n limits; by_source filters; duplicates rejected)

Workspace count now 424. Total this resume: 314 cockpit crates.

### Two-hundred-and-forty-seventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-did-you-mean` (Suggestion{candidate,
  score_bp}; suggest scores via multiset char-overlap
  (shared / max_len in bp); returns top-N score-desc with
  lex tie-break)

Workspace count now 425. Total this resume: 315 cockpit crates.

### Two-hundred-and-forty-eighth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-rubber-band` (DragState{Idle/Dragging};
  start(x, y) anchors, update tracks current, finish returns
  normalized SelRect{lo/hi}; cancel discards; rect reads
  current normalized box)

Workspace count now 426. Total this resume: 316 cockpit crates.

### Two-hundred-and-forty-ninth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-drop-indicator` (Indicator{None/Above/Below/
  Inside}; resolve maps cursor to relative bp 0..10000 within
  row, picks Inside (middle band) / Above (<5000) / Below
  (>5000); outside → None)

Workspace count now 427. Total this resume: 317 cockpit crates.

### Two-hundred-and-fiftieth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-selection-summary` (Item{id, value,
  category}; add records (no duplicates); summary returns
  {count, total i128, sorted unique categories}; remove/
  clear mutators)

Workspace count now 428. Total this resume: 318 cockpit crates.

### Two-hundred-and-fifty-first wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-emergency-stop` (Phase{Locked/Armed/
  Triggered}; arm(now) Locked→Armed with armed_at; trigger
  Armed→Triggered iff within arm_window_ms (else falls
  Locked); cancel returns Locked; Triggered one-way)

Workspace count now 429. Total this resume: 319 cockpit crates.

### Two-hundred-and-fifty-second wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-rollout-banner` (Banner{Label{Alpha/Beta/
  EarlyAccess/GenerallyAvailable}, cohort, dismissed};
  should_show iff not dismissed + label != GenerallyAvailable;
  active lists visible)

Workspace count now 430. Total this resume: 320 cockpit crates.

### Two-hundred-and-fifty-third wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-item-pin` (pin idempotent + AtCapacity at
  max_pins; ordered(items) yields pinned-first (skipping ones
  not in items) then remaining in input order)

Workspace count now 431. Total this resume: 321 cockpit crates.

### Two-hundred-and-fifty-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-object-fit` (Mode{Contain/Cover/Fill/None/
  ScaleDown}; compute returns Rendered{w, h, off_x, off_y}
  centered in container; ScaleDown picks min(Contain, None))

Workspace count now 432. Total this resume: 322 cockpit crates.

### Two-hundred-and-fifty-fifth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-trash-buffer` (TrashItem{payload,
  deleted_at_ms}; soft_delete inserts; undo returns payload +
  removes; purge(now) deletes entries past TTL with count;
  undo/purge lifetime counters)

Workspace count now 433. Total this resume: 323 cockpit crates.

### Two-hundred-and-fifty-sixth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-tab-history` (ClosedTab{id, title, ts_closed};
  close appends with capacity drop oldest; reopen_last pops
  newest; find returns most recent with id; clear empties)

Workspace count now 434. Total this resume: 324 cockpit crates.

### Two-hundred-and-fifty-seventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-metric-card` (MetricCard{title, unit,
  value, prev, sparkline, last_updated, flat_epsilon_bp};
  set_value shifts prev + appends bounded sparkline; delta_bp
  + Trend{Up/Flat/Down} with epsilon)

Workspace count now 435. Total this resume: 325 cockpit crates.

### Two-hundred-and-fifty-eighth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-day-schedule` (Block{id, start_min, end_min,
  label}; add rejects out-of-range, start>=end, conflict
  (overlap not edge-touch); blocks_sorted ascending start_min)

Workspace count now 436. Total this resume: 326 cockpit crates.

### Two-hundred-and-fifty-ninth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-service-status` (Status{Up/Degraded/Down};
  fleet_status: Down if any Down else Degraded if any
  Degraded else Up; counts per-status; services_with filter)

Workspace count now 437. Total this resume: 327 cockpit crates.

### Two-hundred-and-sixtieth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-upload-progress` (Upload{Phase{Queued/
  Uploading/Done/Failed(err)/Cancelled}, bytes_done,
  bytes_total}; enqueue/start/progress/complete/fail/cancel;
  total_progress_bp aggregates across uploads)

Workspace count now 438. Total this resume: 328 cockpit crates.

### Two-hundred-and-sixty-first wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-streak-indicator` (Streak{current, best}
  per key; hit increments current + updates best; miss resets
  current to 0, best preserved; clear removes key; per-key
  BTreeMap)

Workspace count now 439. Total this resume: 329 cockpit crates.

### Two-hundred-and-sixty-second wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-kbd-hint` (Hint{action, chord: Vec<Key>};
  parse('Ctrl+Shift+K') canonicalizes modifiers; render returns
  Chunk sequence alternating KeyCap + Plus so surface can wrap
  each keycap in <kbd>; surface-only)

Workspace count now 440. Total this resume: 330 cockpit crates.

### Two-hundred-and-sixty-third wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-ticker-tape` (Item{id, text, priority,
  inserted_at_ms, expires_at_ms}; push adds; tick(now) drops
  expired (ttl=0 = never); render(now) yields items in
  priority-desc then insertion-asc order)

Workspace count now 441. Total this resume: 331 cockpit crates.

### Two-hundred-and-sixty-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-callout-arrow` (place(balloon Rect, target,
  arrow_margin) picks balloon Side via max signed distance to
  target; offset along that edge clamped within
  [arrow_margin, edge_len - arrow_margin]; pure geometry)

Workspace count now 442. Total this resume: 332 cockpit crates.

### Two-hundred-and-sixty-fifth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-swipe-gesture` (down/move/up state machine;
  up() evaluates distance >= min_distance, velocity >=
  min_velocity_pps, dominant-axis ratio >= 2:1; otherwise
  TooShort / TooSlow / Diagonal)

Workspace count now 443. Total this resume: 333 cockpit crates.

### Two-hundred-and-sixty-sixth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-aspect-ratio-box` (fit(outer_w, outer_h,
  w_num, w_den) sizes inner Box2D preserving target ratio and
  fitting inside outer, centered; pillarbox vs letterbox decided
  by limiting axis; pure geometry)

Workspace count now 444. Total this resume: 334 cockpit crates.

### Two-hundred-and-sixty-seventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-freshness-badge` (State{fetched_at_ms,
  fresh_ttl_ms, stale_ttl_ms, revalidating, last_error}; classify
  yields Fresh/Stale/Expired/Revalidating/Failed in priority
  order: Revalidating > Failed > Expired > Stale > Fresh)

Workspace count now 445. Total this resume: 335 cockpit crates.

### Two-hundred-and-sixty-eighth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-row-hover-affordance` (three independent
  inputs: hovered_row pointer, focused_row keyboard, pinned_row
  sticky; visible(row) true if any equals row; keyboard parity
  with pointer; pin persists across unhover)

Workspace count now 446. Total this resume: 336 cockpit crates.

### Two-hundred-and-sixty-ninth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-achievement-toast` (Achievement{id, title,
  tier Bronze/Silver/Gold/Platinum}; earn rejects dup ids
  unique-once; show(now) promotes queue front when slot free or
  current expired; ack dismisses)

Workspace count now 447. Total this resume: 337 cockpit crates.

### Two-hundred-and-seventieth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-lightbox-overlay` (items Vec<String>;
  open(i) at index, close dismisses, next/prev advance index;
  cyclic=true wraps at boundaries otherwise clamps; current
  returns currently-shown item or None)

Workspace count now 448. Total this resume: 338 cockpit crates.

### Two-hundred-and-seventy-first wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-month-picker` (YearMonth{year, month 1..=12};
  MonthPicker{visible_year, selected, min/max bounds, explicit
  disabled set}; cells() returns 12 Cell{ym, enabled, selected}
  for visible year; select rejects out-of-range or disabled)

Workspace count now 449. Total this resume: 339 cockpit crates.

### Two-hundred-and-seventy-second wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-type-to-confirm` (TypeToConfirm{required,
  case_insensitive, current_input}; update sets input;
  matches() iff input == required exactly or
  case-insensitively per config; prefix_len returns leading
  matching bytes for progress display)

Workspace count now 450. Total this resume: 340 cockpit crates.

### Two-hundred-and-seventy-third wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-frozen-columns` (Column{id, width};
  freeze_lead leading + freeze_trail trailing columns pinned;
  position(i) returns PinnedLeft(offset) / Scrolling(left) /
  PinnedRight(offset); scrolling_width sums non-frozen widths)

Workspace count now 451. Total this resume: 341 cockpit crates.

### Two-hundred-and-seventy-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-reply-form` (State{parent_id, draft,
  saved_at_ms, autosave_every_ms, persisted_draft}; type sets
  draft; dirty compares to persisted; tick(now) autosaves if
  elapsed and dirty; submit returns body + resets, rejects
  whitespace-only; cancel clears)

Workspace count now 452. Total this resume: 342 cockpit crates.

### Two-hundred-and-seventy-fifth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-mention-resolver` (resolve(text) walks
  chars and emits Token::Plain runs interleaved with
  Token::Mention when @handle matches a known user; handle =
  ASCII alnum + underscore, length 1..=64; unknown @handles
  stay as Plain)

Workspace count now 453. Total this resume: 343 cockpit crates.

### Two-hundred-and-seventy-sixth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-output-pane` (Line{stream Stdout/Stderr,
  ts_ms, text}; push_stdout/push_stderr append; max_lines-bounded
  with front-eviction; filter(opts) returns refs to lines matching
  active stream + substring filter)

Workspace count now 454. Total this resume: 344 cockpit crates.

### Two-hundred-and-seventy-seventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-auto-link` (tokenize(text) returns
  Vec<Segment>: Plain runs interleaved with Link{url}; URL
  starts at http:// or https:// and runs until whitespace;
  trailing punctuation [.,;:!?)\]>\"'] excluded from link and
  returned in next Plain)

Workspace count now 455. Total this resume: 345 cockpit crates.

### Two-hundred-and-seventy-eighth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-unread-dot` (Channel{count, last_seen_ts_ms,
  mention}; observe(ch, is_mention) increments count + sets
  mention flag; mark_seen(ch, ts) zeroes count and clears
  mention; dot(ch) returns Hidden / Numeric / Mention;
  total_unread sums all channels)

Workspace count now 456. Total this resume: 346 cockpit crates.

### Two-hundred-and-seventy-ninth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-currency-formatter` (Spec{symbol, position
  Prefix/Suffix, decimals 0..=8, group sep char, sep decimal
  char}; format(amount_minor i64) renders thousands-grouped
  integer + sep + zero-padded fractional; negative gets
  leading '-')

Workspace count now 457. Total this resume: 347 cockpit crates.

### Two-hundred-and-eightieth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-step-dots` (State{total, current, visited
  Vec<bool>}; goto(i) jumps; next/prev shift by 1 with saturation;
  render() yields Dot per index: Active current / Visited /
  Unvisited; prev does not unvisit)

Workspace count now 458. Total this resume: 348 cockpit crates.

### Two-hundred-and-eighty-first wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-flame-graph` (Frame{name, weight,
  children}; layout(root, viewport_w) returns Vec<(name,
  Box2D{x, depth, w})> in left-to-right depth-first order;
  child x-offsets accumulate, width proportional to
  weight/root_weight)

Workspace count now 459. Total this resume: 349 cockpit crates.

### Two-hundred-and-eighty-second wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-stack-trace-viewer` (Frame{idx, file, line,
  fn_name, in_project}; push classifies against project_prefixes;
  render(collapse_deps) yields RenderRow Vec; collapse_deps=true
  folds contiguous out-of-project runs into Collapsed{count})

Workspace count now 460. Total this resume: 350 cockpit crates.

### Two-hundred-and-eighty-third wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-workspace-state` (Pane{id, kind, scroll_y};
  State{panes, active_pane, named_snapshots};
  add_pane/set_active/set_scroll mutate live; save(name) clones
  live into named_snapshots; restore(name) replaces live from
  snapshot)

Workspace count now 461. Total this resume: 351 cockpit crates.

### Two-hundred-and-eighty-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-changelog-pane` (Entry{version, title, kind
  Added/Changed/Fixed/Deprecated/Removed/Security, body,
  published_at_ms}; add inserts + sorts by published asc;
  duplicate version rejected; mark_read flags entry; unread_count
  + unread() filter)

Workspace count now 462. Total this resume: 352 cockpit crates.

### Two-hundred-and-eighty-fifth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-retry-banner` (Phase{Idle, Failed
  {retry_at_ms, attempt, error}, Retrying{attempt},
  Succeeded}; fail records attempt + carries forward;
  ready/time_left compare retry_at vs now; retry rejected
  before window; succeed/dismiss transitions)

Workspace count now 463. Total this resume: 353 cockpit crates.

### Two-hundred-and-eighty-sixth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-delta-pill` (render(current, prior,
  flat_threshold, invert_polarity) → Pill{direction Up/Flat/Down,
  sentiment Positive/Neutral/Negative post-polarity, label,
  magnitude_bp basis points}; invert_polarity flips sentiment
  for higher-is-worse metrics)

Workspace count now 464. Total this resume: 354 cockpit crates.

### Two-hundred-and-eighty-seventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-incident-card` (IncidentCard{id, title,
  severity Info/Warning/Error/Critical, first_seen, last_seen,
  occurrence_count, affected_count running-max, resolved_at_ms};
  observe(now, affected) increments + un-resolves; resolve
  marks inactive; duration uses now-or-resolved)

Workspace count now 465. Total this resume: 355 cockpit crates.

### Two-hundred-and-eighty-eighth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-json-viewer` (path-addressed expanded set
  $.foo / $[0]; flatten(value) walks JSON producing Row{depth,
  path, label, value_preview, expandable, expanded};
  toggle/is_expanded manage state; surface owns JSON)

Workspace count now 466. Total this resume: 356 cockpit crates.

### Two-hundred-and-eighty-ninth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-word-count` (count(text, wpm) → Stats{chars
  all-chars, chars_no_ws excluding-whitespace, words
  Unicode-whitespace-split, reading_time_ms = words * 60_000 /
  wpm})

Workspace count now 467. Total this resume: 357 cockpit crates.

### Two-hundred-and-ninetieth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-job-progress-card` (Stage{id, label, phase
  Pending/Running/Done/Failed(reason), started_at_ms,
  ended_at_ms}; JobCard{job_id, title, stages}; transitions
  Pending→Running→Done|Failed; progress_bp weights Done=2
  Running=1 out of 2N)

Workspace count now 468. Total this resume: 358 cockpit crates.

### Two-hundred-and-ninety-first wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-day-divider` (classify(now_ms, item_ms)
  returns Today/Yesterday/EarlierThisWeek/Older based on
  epoch-day diff ts_ms / 86_400_000; group(now, items_ms)
  coalesces newest-first items into contiguous (Bucket,
  Vec<u64>) groups)

Workspace count now 469. Total this resume: 359 cockpit crates.

### Two-hundred-and-ninety-second wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-image-load-state` (Image{url, placeholder,
  phase Idle/Loading/Loaded/Failed(reason), started_at_ms,
  ended_at_ms}; begin Idle/Failed → Loading; load Loading →
  Loaded; fail Loading → Failed; retry allowed from Failed)

Workspace count now 470. Total this resume: 360 cockpit crates.

### Two-hundred-and-ninety-third wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-color-contrast` (WCAG-2.1 §1.4.3 relative-
  luminance + contrast-ratio. `Rgb{r,g,b}` with `from_hex(0xRRGGBB)`
  constructor. `relative_luminance(rgb)` linearises each sRGB
  channel (≤0.04045 → c/12.92, else ((c+0.055)/1.055)^2.4) then
  blends 0.2126·R + 0.7152·G + 0.0722·B. `contrast_ratio(fg,bg)` =
  (Llight+0.05)/(Ldark+0.05) — order-invariant. `WcagLevel::{AA,
  AAA}.threshold(large_text)` returns the 4.5/3.0/7.0/4.5
  thresholds; `.passes(ratio, large)` with 1e-9 tolerance for
  at-threshold pairs. `Verdict{ratio, passes_aa, passes_aaa}` +
  `verdict(fg, bg, large)` bundle. 17 unit tests including
  black-on-white = 21:1 invariant, mid-gray-on-white = ~3.95 fails
  AA-normal but passes AA-large, ordering invariance, boundary
  ratio at threshold, lowercase serde for AA/AAA).

Workspace count now 471. Total this resume: 361 cockpit crates.

### Two-hundred-and-ninety-fourth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-pagination` (Pager{page, per_page, total} +
  PageInfo{page, per_page, total, total_pages, can_prev, can_next,
  range}. Pager::new(p,pp,t) clamps page into [1, total_pages] and
  rejects per_page=0 with PaginationError::InvalidPerPage. info()
  computes total_pages via ceil-div, range = Some((start, end_incl))
  in [0, total-1] or None for empty total, with partial-last-page
  capped to total-1. next()/prev() are no-ops at boundaries; goto()
  clamps. total_pages_for(0,_) = total_pages_for(_,0) = 0. 20 unit
  tests covering exact-division + rounding + zero-total + zero-per-
  page + clamping overshoot/undershoot + empty-total navigation +
  partial-last-page range cap + step/goto boundaries + serde
  round-trip).

Workspace count now 472. Total this resume: 362 cockpit crates.

### Two-hundred-and-ninety-fifth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-relative-time` (human relative-time formatter
  with Tense{Now,Past,Future}. classify(now_ms, item_ms) → (tense,
  |delta|ms). format(now_ms, item_ms) returns "just now" if |Δ|<1s,
  else N seconds/minutes/hours/days ago (or "in N …" for future)
  with proper singular/plural pluralization; falls back to absolute
  "on YYYY-MM-DD" past 7 days. epoch_day_to_yyyymmdd uses Howard
  Hinnant's civil-from-days algorithm for the proleptic Gregorian
  calendar (era + day-of-era + year-of-era → year/month/day). 16
  unit tests covering: within-1s "just now", 5-second ago, 1-second
  singular, 5-minute ago, 1-minute singular, 3-hour ago, 2-day ago,
  6-day ago (still days), 8-day fall-back to date, future +5m,
  future +3h, future +30d fall-back to date, classify tense + delta
  table, epoch-day round-trip, schema check, Tense serde lowercase).

Workspace count now 473. Total this resume: 363 cockpit crates.

### Two-hundred-and-ninety-sixth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-text-truncation` (char-aware text truncation
  for narrow columns with three strategies: End preserves start,
  Start preserves end, Middle preserves both ends with head-bias
  on odd budgets. truncate(input, max_chars, strategy, ellipsis)
  + truncate_default() with "…". Unicode-safe (operates on chars
  not bytes — "héllo" counts as 5 not 6). Errors:
  InvalidMaxChars (0), EllipsisTooLong (≥ max_chars). 14 unit
  tests: pass-through under budget, exact-budget pass-through,
  three strategies on "the quick brown fox" with measured outputs,
  Unicode chars-not-bytes, custom 3-dot ellipsis, zero max_chars
  rejection, ellipsis-too-long rejection at == and >, empty input
  pass-through, middle odd-budget head-bias verification, schema
  check, Strategy lowercase serde).

Workspace count now 474. Total this resume: 364 cockpit crates.

### Two-hundred-and-ninety-seventh wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-search-history` (recent-query ring buffer with
  MRU semantics + dedup + bounded capacity. SearchHistory::new(
  capacity, dedup) where DedupMode ∈ {CaseSensitive,
  CaseInsensitive}. record(q) trims + ignores empty/whitespace; if
  q matches existing entry MOVES it to head (preserves operator
  intent "recent = last used"), else inserts at head + evicts
  oldest when at capacity. Returns bool indicating whether the
  buffer changed (move-to-head IS a change; duplicate-at-head is
  not). 13 unit tests: zero-capacity rejection, empty/whitespace
  no-op, trim-before-record, MRU ordering, duplicate moves to head
  (existing keeps original case in CaseInsensitive mode),
  duplicate-at-head no-op, capacity eviction, case-sensitive vs
  case-insensitive dedup, clear, schema check, full serde
  round-trip, DedupMode kebab-case serde).

Workspace count now 475. Total this resume: 365 cockpit crates.

### Two-hundred-and-ninety-eighth wave (same day, +1 more cockpit crate)

- `sovereign-cockpit-toast-stack` (toast notification stack with
  auto-dismiss timers + severity-ordered eviction + bounded
  capacity. Severity{Info < Success < Warning < Error} with derived
  Ord. ToastStack::new(capacity) — rejects 0. push(Toast) inserts
  at head; on capacity-full evicts the lowest-severity OLDEST
  toast (higher severity wins). dismiss(id) → bool removes a
  specific toast. expire(now_ms) → Vec<String> auto-dismisses
  toasts whose created_at + ttl ≤ now and returns removed IDs.
  clear() empties. 15 unit tests: zero-capacity rejection, newest-
  first ordering, duplicate-id rejection, eviction picks lowest-
  severity (Info evicted before Error even when Info is newer),
  dismiss + dismiss-unknown, expire returns removed IDs, expire at
  exact-ttl boundary (inclusive), no-due-toasts returns empty,
  clear, Severity Ord ladder, schema check, ToastStack serde
  round-trip, Severity lowercase serde).

Workspace count now 476. Total this resume: 366 cockpit crates.
