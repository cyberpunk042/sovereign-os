# Standing directive — the two ultimate solutions

**Status**: ACTIVE (operator standing direction, 2026-05-19, verbatim)
**Audience**: every Claude Code session + every downstream agent + every contributor

## Verbatim operator statement

> "Continue Endlessly to toward the two ultimate solutions and their perfectioning and high UX/Developer Experience."

> "They combine but keep in mind they are also independent... if I talk about an IPS feature its obviously not in Sovereign-OS. I feel like earlier you did a lot of things in Sovereign-OS you should have done in Selfdef and used in Sovereign-OS. Respect the projects."

> "Knowledge is the second-brain / information-hub."

## The two ultimate solutions

| solution | role | independence claim | composition contract |
|---|---|---|---|
| **Solution 1 — `sovereign-os`** | Local AI workstation runtime — cockpit, gateway, model orchestration, NVFP4 + ternary execution, HölderPO post-training, SRP topology (Conductor/Logic/Oracle), 21 dashboards, scheduler, evaluators, memory OS, super-model manifest, peace-machine close | Boots and operates without selfdef IPS present (degraded-but-functional mode); produces its own state under `tank/context` ZFS dataset; owns its own M057 12-step task lifecycle; owns its own cockpit at `/webapp/master-dashboard/` | When selfdef is present, sovereign-os consumes selfdef's MS007 typed-mirror crates READ-ONLY to surface IPS state in dashboards D-12..D-18; operator-mutation actions proxy to selfdef via MS003-signed requests per MS043 R10274 |
| **Solution 2 — `selfdef`** | IPS daemon — boundary enforcement across communication / capability tokens / sandbox tiers / filesystem / network / authority levels / commit / tool authority / Guardian (Tetragon eBPF) + operator CLI/TUI/minimal-web + UX coherence test harness (MS045) | Boots and operates without sovereign-os present per MS043 offline-survivability requirements R10217-R10225; has its own CLI + TUI + minimal-web at localhost:7575; writes audit logs to `tank/vault/context/security_audit.log` (which lives on ZFS regardless of sovereign-os runtime presence) | When sovereign-os is present, selfdef publishes 9 MS007 mirror crates (selfdef-rules-mirror / -grants-mirror / -capability-mirror / -sandbox-mirror / -audit-mirror / -quarantine-mirror / -trust-score-mirror / -cli-mirror / -tui-mirror) for sovereign-os cockpit consumption; never accepts mutation from sovereign-os except via MS003-signed operator requests |

The two solutions are **independent** (each boots without the other) AND **combining** (cross-repo mirrors via MS007 8/8 SATURATED scheme). They are NOT a single monolith.

## The third piece — info-hub (NOT a solution; it's the brain)

> "Knowledge is the second-brain / information-hub."

`cyberpunk042/devops-solutions-information-hub` is **the operator's read-only knowledge layer**. It is NOT a third solution. It is the wiki / second-brain / decision log / paper-ingestion archive. From sovereign-os + selfdef sessions, info-hub is **READ-ONLY**. Both solutions index their canonical sources, doctrinal anchors, and external research ingestion as info-hub entries.

## Status of perfectioning (2026-05-19 snapshot)

### Solution 1 — sovereign-os

| stage | scope | status |
|---|---|---|
| Catalog (10000+ requirements) | 80 milestones M001-M080, ~13,600 R-rows, ~136,000 sub-requirements | ✓ COMPLETE |
| Backward-sweep review (avx-plus-plus dump 18,341 lines, EOF-onward redefinitions) | M061 + `backlog/notes/backward-sweep-2026-05-19-findings.md` — 6 redefinitions identified (3 breaking / 2 additive / 1 clarifying) | ✓ COMPLETE |
| Backward-sweep Patch Pass A | 10 sovereign-os milestones annotated (M005 M006 M007 M009 M010 M011 M014 M016 M017 M020) | ✓ COMPLETE (commit `1a79fe8`) |
| Backward-sweep Patch Pass B+C | MS007 crate version bumps + schema_version bumps | ⚠ PENDING (workspace at 0.1.0 pre-release; deferred until pre-1.0 lockdown) |
| Prior-dump review (2026-05-15 master-spec + 2026-05-16 macro-arc) | `backlog/notes/prior-dump-review-2026-05-19-findings.md` — 15 must-add milestones identified, all 15 landed (M062-M068 + M070-M076) | ✓ COMPLETE |
| External research ingestion (operator-cited 2026-05-19) | M077 NVFP4 + M078 HölderPO + M079 Activation Steering + M080 HRM — 4 milestones, 690 R-rows | ✓ COMPLETE |
| SDD bridge (catalog → implementation) | SDD-040 cockpit-dashboard-implementation-bridge.md — 19 dashboards inventoried, Phase A-E ordering | ✓ COMPLETE |
| Implementation: D-00 master-dashboard | `/webapp/master-dashboard/index.html` | ✓ SHIPPED |
| Implementation: D-02 profile choices | `/webapp/d-02-profile-choices/index.html` — six-profile selector + L0..L6 + Ring 0..4 | ✓ SHIPPED |
| Implementation: D-06 pending approvals | `/webapp/d-06-pending-approvals/` — operator-controlled axiom for Stage Gates | shipping now |
| Implementation: D-01 D-03 D-04 D-05 D-07 D-08 D-09 D-10 D-11 D-13 D-15 D-17 D-18 + partials D-14 D-19 D-20 | 16 dashboards remaining | IN-FLIGHT |
| SDD/TDD implementation (M062 PRs 1-10 + Stage 2+ build scripts) | foundation phase substantially complete (29 SDDs landed, 6 handoffs); Stage 2 forward-implementation in-flight | IN-FLIGHT |

### Solution 2 — selfdef

| stage | scope | status |
|---|---|---|
| Catalog (10000+ requirements) | 45 milestones MS001-MS045, ~11,200 R-rows, ~112,000 sub-requirements | ✓ COMPLETE |
| Backward-sweep Patch Pass A | 1 selfdef milestone annotated (MS010) | ✓ COMPLETE (commit `6a2f6ef`) |
| Boundary mirror crates (8/8 SATURATED) | crates/selfdef-auth-tier + -bashrc-install + -history-sink + -dashboard-manifest + -surface-manifest + -ux-checklist + -audit-manifest + -doc-manifest | ✓ SHIPPED |
| Guardian Daemon (MS044) | catalog complete; implementation pending | catalog ✓ / impl IN-FLIGHT |
| UX coherence test harness (MS045) | catalog complete; CLI + TUI + minimal-web validators | ✓ COMPLETE (catalog) |
| Implementation: 12 channel set (write/wall/ntfy/signal/discord/slack/smtp/thehive + shared-audit-summary + integration-orchestrator + notifier-engine + notifier-orchestrator) | per `CHANGELOG.md` "channel inventory" | ✓ SHIPPED |
| Implementation: SDD-008 channel-set + `selfdefctl notify resend` escalation | per `CHANGELOG.md` PRs #170 + #173 | ✓ SHIPPED |
| 9 MS007 mirror crates for sovereign-os D-12..D-18 dashboards | catalog (MS043 R10182-R10193); implementation pending | catalog ✓ / impl IN-FLIGHT |

## Combined ecosystem (as of 2026-05-19)

- **Milestones**: 80 (sovereign-os) + 45 (selfdef) = **125 milestones** (124 prior + this directive lands)
- **R-rows**: ~13,600 + ~11,200 = **~24,800 first-class requirements**
- **Sub-requirements**: ~248,000 enforced sub-requirements (every R-row carries 10 hard non-negotiable sub-reqs)
- **Epics**: ~800
- **Modules**: ~2,000
- **Features**: ~10,200

Per operator's standing direction (verbatim): *"10000+ requirements... 400+ Epics and 1000+ modules and 5000+ features/tasks"* — every target exceeded by ≥2x.

## "Two solutions" rule — applied to every future contribution

Before any new code, SDD, milestone, dashboard, CLI command, mirror crate, or systemd unit lands, the contributor MUST answer:

1. **Which solution does this belong to?** sovereign-os runtime OR selfdef IPS — never both. If the answer is "both", split into two artifacts, one per solution, plus the MS007 typed-mirror that binds them.
2. **Does it preserve independence?** Can the receiving solution boot and operate without the other being present? If no, the contribution violates the "independence" claim and must be refactored.
3. **Does it preserve composition?** Does the cross-repo binding route through MS007 mirror crates only? If no, the contribution violates the "Respect the projects" rule and must be refactored.
4. **Is it READ-ONLY across the boundary?** Cross-repo state mutations must proxy through MS003-signed operator requests (e.g., MS043 R10274 — sovereign-os cockpit operator-restore action proxies to selfdef via signed request).
5. **Is info-hub treated as READ-ONLY?** Sessions in sovereign-os and selfdef MUST NOT mutate the info-hub repo. Knowledge is the second-brain.

## Forward queue

Per "little piece by little piece" — next concrete deliverables:

- D-06 pending approvals dashboard (shipping with this directive) — operator-controlled axiom for M065 Five Stage Gates
- D-01 active sessions dashboard — M057 12-step lifecycle view
- D-05 traces dashboard — M049 13-field span surface
- D-09 hardware pressure dashboard — PSI + DCGM gauges
- selfdef 9 MS007 mirror crates implementation (per MS043) for sovereign-os D-12..D-18 consumption
- selfdef MS044 Guardian Daemon `/usr/local/bin/guardian-core` Python implementation
- selfdef MS045 UX coherence test harness `/usr/bin/selfdef-ux-harness` implementation
- sovereign-os M077-M080 implementation (NVFP4 + HölderPO + Activation Steering + HRM runtime crates)

Per operator standing direction *"do not block, you have plenty to continue"* — work proceeds in tractable increments. Catalog is the foundation; implementation extends from it.

## Source provenance

- Operator standing direction 2026-05-19 (verbatim quoted above)
- `backlog/notes/backward-sweep-2026-05-19-findings.md` (sovereign-os)
- `backlog/notes/prior-dump-review-2026-05-19-findings.md` (sovereign-os)
- `backlog/notes/external-research-ingestion-2026-05-19.md` (sovereign-os)
- `backlog/milestones/M061-avx-plus-plus-canon-update-backward-sweep-2026-05-19.md` (sovereign-os)
- `docs/sdd/040-cockpit-dashboard-implementation-bridge.md` (sovereign-os)
- `backlog/milestones/MS045-ux-coherence-test-harness-cli-tui-minimal-web.md` (selfdef)
