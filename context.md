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

## Where we are right now (2026-05-19 snapshot)

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
