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

20. M077 NVFP4 runtime crate (`crates/sovereign-nvfp4-runtime/`) — 5 recipe variants
21. M078 HölderPO runtime crate (`crates/sovereign-holderpo/`) — Hölder-mean aggregator + dynamic-p scheduler
22. M079 Intervention-class typed mirror crate
23. M080 HRM runtime crate — 3 variants (canonical-27M / text-1B / TRM-7M)

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

**Last updated**: 2026-05-19 (commit `918ad14` + this file `context.md`)
**Next AI session**: read this file → read two-ultimate-solutions.md → pick next item from "What's ahead" → execute → update this file.
