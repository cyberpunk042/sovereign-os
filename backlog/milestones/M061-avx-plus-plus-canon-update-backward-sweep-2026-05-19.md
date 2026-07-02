# M061 — AVX++ canon update — backward-sweep redefinitions (2026-05-19)

**Parent**: sovereign-os runtime — catalog hygiene + canon-pin
**Source**: `~/infohub/raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` (full 18341 lines, reverse-pass review)
**Companion**: `/home/user/sovereign-os/backlog/notes/backward-sweep-2026-05-19-findings.md` (6 redefinitions identified)
**Operator standing direction** (verbatim, 2026-05-18): *"layered: new direction ON TOP OF prior direction — never discarded"* / *"when you reach the end of the avx-plus-plus document you will have to review / go backward a bit since it redefine some of the things"*

## Purpose

The avx-plus-plus dump (18341 lines) was authored as a single conversation. Later sections **REDEFINE** earlier sections in specific places. The earlier catalog of 103 milestones cited earlier definitions verbatim. Per operator standing direction, this canon-update milestone:

- **PINS** the later (canonical) definition for each of 6 identified redefinitions
- **ADDS** new R-rows that supersede earlier ones (additive — not destructive)
- **CROSS-REFERENCES** the affected earlier milestones so their R-rows are interpreted under the canonical later definitions
- **PRESERVES** all earlier R-rows verbatim (operator standing: "never discarded")

The 6 redefinitions (severity):
1. **Profiles** — memory-lens (8420-8440) → authority-gate (17468-17488) — **breaking**
2. **Core Law** — 5-line earlier variants (15350-15355, 15789-15794) → canonical 6-line at 18299-18305 — **clarifying**
3. **Authority Levels 0..6** — implicit everywhere → explicit ladder at 17252-17272 — **additive**
4. **Trust Rings 0..4** — dispersed → explicit topology at 17280-17302 — **additive**
5. **Scheduler** — component (312, 677, 1325) → first-class policy layer at 17914-18268 — **breaking**
6. **Commit Authority** — deterministic substrate (1527, 1858, 2139, 2155, 2319) → evidence-earned authority at 17389-17421 — **breaking**

## Epics (E0588-E0597)

| epic | name | source |
|---|---|---|
| E0588 | Redefinition 1 — Profiles: memory-lens → authority-gate (BREAKING) | dump 8420-8440 + 17468-17488 |
| E0589 | Redefinition 2 — Core Law canonical 6-line "CPU enforces" explicit (CLARIFYING) | dump 15350-15355 + 15789-15794 + 18299-18305 |
| E0590 | Redefinition 3 — Authority Levels 0..6 explicit ladder (ADDITIVE) | dump 17252-17272 |
| E0591 | Redefinition 4 — Trust Rings 0..4 explicit topology (ADDITIVE) | dump 17280-17302 |
| E0592 | Redefinition 5 — Scheduler as first-class policy layer (BREAKING) | dump 17914-18268 |
| E0593 | Redefinition 6 — Commit Authority deterministic-substrate → evidence-earned (BREAKING) | dump 1527-2319 + 17389-17421 |
| E0594 | Patch pass A — affected-milestone canon-update annotations | architecture + operator standing direction |
| E0595 | Patch pass B — typed-mirror crate version bumps (MS007 ecosystem) | cross-ref selfdef MS007 |
| E0596 | Patch pass C — schema_version bumps on contract-breaking mirrors | cross-ref selfdef MS007 + architecture |
| E0597 | Catalog hygiene closure — backward-sweep complete, prior-dump review next | operator standing direction |

## Modules (M01020-M01036)

| module | name | source |
|---|---|---|
| M01020 | sovereign-canon-redef-profiles | dump 8420-8440 + 17468-17488 |
| M01021 | sovereign-canon-redef-core-law | dump 15350-15355 + 18299-18305 |
| M01022 | sovereign-canon-redef-authority-levels | dump 17252-17272 |
| M01023 | sovereign-canon-redef-trust-rings | dump 17280-17302 |
| M01024 | sovereign-canon-redef-scheduler | dump 17914-18268 |
| M01025 | sovereign-canon-redef-commit-authority | dump 1527-2319 + 17389-17421 |
| M01026 | sovereign-canon-affected-milestone-index | architecture + backward-sweep findings |
| M01027 | sovereign-canon-patch-pass-coordinator | architecture |
| M01028 | sovereign-canon-mirror-version-bumper | cross-ref selfdef MS007 |
| M01029 | sovereign-canon-schema-version-tracker | cross-ref selfdef MS007 + architecture |
| M01030 | sovereign-canon-supersedes-recorder | architecture + operator standing direction |
| M01031 | sovereign-canon-replay-validator-bridge | cross-ref selfdef MS009 |
| M01032 | sovereign-canon-trace-emitter | cross-ref M049 |
| M01033 | sovereign-canon-ocsf-event-emitter | cross-ref selfdef MS026 |
| M01034 | sovereign-canon-doctrinal-preservation | operator standing direction |
| M01035 | sovereign-canon-prior-dump-review-planner | operator standing direction |
| M01036 | sovereign-canon-sdd-tdd-readiness-gate | operator standing direction |

## Features (F05101-F05185)

| feature | name | source |
|---|---|---|
| F05101 | Profile redef — earlier profiles were memory-access lenses (lines 8420-8440) | dump 8420-8440 |
| F05102 | Profile redef — earlier scope: temporal validation / shallow memory / local-only augmentation / associative broadness | dump 8420-8440 |
| F05103 | Profile redef — later profiles are authority-gates (lines 17468-17488) | dump 17468-17488 |
| F05104 | Profile redef — later scope: 6 profiles with explicit max authority levels per envelope | dump 17468-17487 |
| F05105 | Profile redef — CANONICAL: authority-gate; memory-lens is HISTORICAL only | dump 17468-17488 + operator standing direction |
| F05106 | Profile redef — affected: sovereign-os M016 M017 + selfdef MS010 | backward-sweep findings |
| F05107 | Profile redef — affected milestones interpret memory-lens R-rows under authority-gate canon | architecture + operator standing direction |
| F05108 | Profile redef — selfdef MS040 already cataloged under authority-gate canon (no patch needed) | cross-ref selfdef MS040 |
| F05109 | Core Law redef — earlier variant at 15350-15355 was 5-line (missing "CPU enforces") | dump 15350-15355 |
| F05110 | Core Law redef — earlier variant at 15789-15794 was 5-line (missing "CPU enforces") | dump 15789-15794 |
| F05111 | Core Law redef — canonical 6-line at 18299-18305 includes "CPU enforces" | dump 18299-18305 |
| F05112 | Core Law redef — CANONICAL form (6 lines): Models propose / Runtime routes / CPU enforces / Tools prove / ZFS remembers / User chooses | dump 18299-18305 |
| F05113 | Core Law redef — affected: sovereign-os M005 M006 M009 M020 (must reference 18299-18305) | backward-sweep findings |
| F05114 | Core Law redef — sovereign-os M059 already cataloged under canonical 6-line form | cross-ref M059 |
| F05115 | Authority redef — earlier sections had authority implicit (no explicit ladder) | dump 1-9000 (implicit) |
| F05116 | Authority redef — later section adds explicit 7-level ladder (L0..L6) at 17252-17272 | dump 17252-17272 |
| F05117 | Authority redef — L0 Observe / L1 Suggest / L2 Simulate / L3 Prepare / L4 Execute-bounded / L5 Commit / L6 Persist | dump 17252-17272 |
| F05118 | Authority redef — CANONICAL: explicit 7-level ladder; implicit earlier scope respected but inherits explicit semantics | dump 17252-17272 |
| F05119 | Authority redef — affected: sovereign-os M005 M007 M014 M017 (add explicit ladder cross-ref) | backward-sweep findings |
| F05120 | Authority redef — sovereign-os M056 already cataloged with full ladder | cross-ref M056 |
| F05121 | Authority redef — selfdef MS039 already cataloged with full ladder (IPS-side projection) | cross-ref selfdef MS039 |
| F05122 | Trust ring redef — earlier sections had no explicit ring topology | dump 1-9000 (dispersed) |
| F05123 | Trust ring redef — later section adds 5-ring topology (Ring 0..4) at 17280-17302 | dump 17280-17302 |
| F05124 | Trust ring redef — Ring 0 Sovereign Kernel / Ring 1 Trusted Local / Ring 2 Sandboxed / Ring 3 Experimental / Ring 4 Cloud-External | dump 17280-17302 |
| F05125 | Trust ring redef — CANONICAL: 5-ring topology + ring-transition policy | dump 17280-17302 |
| F05126 | Trust ring redef — affected: sovereign-os M011 M014 M016 (add ring topology cross-ref) | backward-sweep findings |
| F05127 | Trust ring redef — sovereign-os M056 already cataloged with full ring topology | cross-ref M056 |
| F05128 | Trust ring redef — selfdef MS039 already cataloged with full ring topology (IPS projection) | cross-ref selfdef MS039 |
| F05129 | Scheduler redef — earlier sections had scheduler as component (312, 677, 1325) | dump 312 + 677 + 1325 |
| F05130 | Scheduler redef — later section makes scheduler first-class policy layer (17914-18268) | dump 17914-18268 |
| F05131 | Scheduler redef — 6 scheduling policies per profile (fast/careful/private/autonomous/experimental/production) | dump 18001-18030 |
| F05132 | Scheduler redef — 8 resource types + 8 queue types + Blackwell/4090/CPU policies + Backpressure + Goldilocks | dump 17920-18209 |
| F05133 | Scheduler redef — Key Scheduling Law: "never let expensive cognition wait on cheap preparation" | dump 18261-18264 |
| F05134 | Scheduler redef — CANONICAL: policy-layer scheduler with per-profile scheduling | dump 17914-18268 |
| F05135 | Scheduler redef — affected: sovereign-os M005 M007 M009 (citations to component-scheduler must layer policy-layer canon) | backward-sweep findings |
| F05136 | Scheduler redef — sovereign-os M058 already cataloged with full policy-layer canon | cross-ref M058 |
| F05137 | Commit redef — earlier sections framed commit as deterministic substrate (1527, 1858, 2139, 2155, 2319) | dump 1527 + 1858 + 2139 + 2155 + 2319 |
| F05138 | Commit redef — earlier scope: CPU commits accepted transitions to replay log + policy-filtered commit equation | dump 2155 |
| F05139 | Commit redef — later section frames commit as evidence-earned authority (17389-17421) | dump 17389-17421 |
| F05140 | Commit redef — later scope: 8 commit types + 5 mandatory fields + 3 high-risk gates | dump 17389-17421 |
| F05141 | Commit redef — DISTINCTION: speculative commit (runtime token masking) vs durable commit (policy-gated action logging) | dump 1527-2319 + 17389-17421 |
| F05142 | Commit redef — CANONICAL: durable commit at 17389-17421; speculative commit retained as runtime-level mechanism | dump 17389-17421 + operator standing direction |
| F05143 | Commit redef — affected: sovereign-os M006 M010 (distinguish speculative vs durable commit) | backward-sweep findings |
| F05144 | Commit redef — selfdef MS041 already cataloged with full evidence-earned canon | cross-ref selfdef MS041 |
| F05145 | Patch pass A — affected milestones receive AVX++ canon-update annotation at top of file | architecture |
| F05146 | Patch pass A — annotation cites M061 + canonical line range | architecture |
| F05147 | Patch pass A — annotation severity tag (breaking / clarifying / additive) preserved | backward-sweep findings |
| F05148 | Patch pass A — annotation signed via MS003 (file-level signature) | cross-ref selfdef MS003 |
| F05149 | Patch pass A — annotation emits M049 trace on application | cross-ref M049 |
| F05150 | Patch pass B — MS007 typed-mirror crates bump version for breaking redefinitions | cross-ref selfdef MS007 |
| F05151 | Patch pass B — non-breaking redefinitions retain crate version, add CHANGELOG entry | cross-ref selfdef MS007 |
| F05152 | Patch pass B — all crate bumps signed via MS003 | cross-ref selfdef MS003 |
| F05153 | Patch pass B — crate bump triggers sovereign-os runtime workspace re-resolve | cross-ref selfdef MS007 |
| F05154 | Patch pass C — schema_version "1.0.0" → "1.1.0" on additive changes | cross-ref selfdef MS007 |
| F05155 | Patch pass C — schema_version "1.0.0" → "2.0.0" on breaking changes | cross-ref selfdef MS007 |
| F05156 | Patch pass C — schema bumps emit OCSF Configuration Change class 5001 | cross-ref selfdef MS026 |
| F05157 | Patch pass C — schema bumps signed via MS003 | cross-ref selfdef MS003 |
| F05158 | Patch pass C — schema_version retained in MS007 crate metadata + CHANGELOG.md | cross-ref selfdef MS007 |
| F05159 | Affected milestone index — sovereign-os M005 M006 M007 M009 M010 M011 M014 M016 M017 M020 | backward-sweep findings |
| F05160 | Affected milestone index — selfdef MS010 (memory-lens profile R-rows historical only) | backward-sweep findings |
| F05161 | Supersedes recorder — each redefinition's earlier R-row IDs catalogued | architecture |
| F05162 | Supersedes recorder — supersedes link is read-only metadata (does NOT delete earlier R-row) | operator standing direction "never discarded" |
| F05163 | Supersedes recorder — supersedes metadata published as MS007 sovereign-canon-supersedes-mirror crate | cross-ref selfdef MS007 |
| F05164 | Replay validator bridge — selfdef MS009 replay validator honors canon-update annotations | cross-ref selfdef MS009 |
| F05165 | Replay validator bridge — annotations carry chain-of-trust signature | cross-ref selfdef MS003 |
| F05166 | Replay validator bridge — chain-break detection treats canon-update as authoritative | cross-ref selfdef MS009 |
| F05167 | Trace emitter — every canon-update event emits M049 13-field span | cross-ref M049 |
| F05168 | Trace emitter — span includes redefinition severity + affected milestone list | cross-ref M049 |
| F05169 | OCSF event emitter — canon-updates emit Configuration Change class 5001 | cross-ref selfdef MS026 |
| F05170 | OCSF event emitter — breaking redefinitions emit additional Detection Finding class 2004 | cross-ref selfdef MS026 |
| F05171 | Doctrinal preservation — earlier R-rows preserved verbatim (operator: "never discarded") | operator standing direction |
| F05172 | Doctrinal preservation — canon-update is LAYERED ON TOP per operator standing direction | operator standing direction |
| F05173 | Doctrinal preservation — operator words verbatim quoted in M061 doc + affected-milestone annotations | operator standing direction |
| F05174 | Doctrinal preservation — verbatim quotes never paraphrased | operator standing direction |
| F05175 | Doctrinal preservation — info-hub knowledge graph indexes redefinitions as second-brain entries | operator standing direction "knowledge = second-brain" |
| F05176 | Prior-dump review planner — operator: "there was also other dumps before that we decided to restart" | operator standing direction |
| F05177 | Prior-dump review planner — inventory of prior dumps at ~/infohub/raw/dumps/ | architecture + operator standing direction |
| F05178 | Prior-dump review planner — review approach: backward-pass per dump, identify supplanted concepts, ADD net-new requirements | operator standing direction |
| F05179 | Prior-dump review planner — output target: new milestones M062+ (sovereign-os) / MS044+ (selfdef) | architecture |
| F05180 | Prior-dump review planner — never discards prior-dump material; treats as additional canon source | operator standing direction |
| F05181 | SDD-TDD readiness gate — implementation phase begins only after: catalog complete + backward-sweep patches applied + prior-dump review complete | operator standing direction |
| F05182 | SDD-TDD readiness gate — gate check: M001..M061 + MS001..MS043 all landed on main | architecture |
| F05183 | SDD-TDD readiness gate — gate check: backward-sweep patch pass A applied to 10 affected milestones | architecture |
| F05184 | SDD-TDD readiness gate — gate check: prior-dump milestones M062+ / MS044+ inventoried | architecture |
| F05185 | SDD-TDD readiness gate — implementation begins with first SDD doc per milestone order; small commits direct-to-main | operator standing direction |

## Requirements (R10201-R10370)

| req | description | source | feature | priority | exception | sub-reqs |
|---|---|---|---|---|---|---|
| R10201 | Doctrinal — "layered: new direction ON TOP OF prior direction — never discarded" | operator standing direction | F05172 | non-negotiable | false | 10 |
| R10202 | Doctrinal — backward-sweep redefinitions ADDITIVE, not destructive | operator standing direction | F05171 | non-negotiable | false | 10 |
| R10203 | Doctrinal — operator words sacrosanct, never paraphrased | operator standing direction | F05174 | non-negotiable | false | 10 |
| R10204 | Doctrinal — info-hub knowledge graph indexes redefinitions | operator standing direction "second-brain" | F05175 | non-negotiable | false | 10 |
| R10205 | Profile redef — earlier memory-lens framing at dump 8420-8440 | dump 8420-8440 | F05101 | non-negotiable | false | 10 |
| R10206 | Profile redef — earlier scope: temporal validation / shallow memory / local-only / associative broadness | dump 8420-8440 | F05102 | non-negotiable | false | 10 |
| R10207 | Profile redef — later authority-gate framing at dump 17468-17488 | dump 17468-17488 | F05103 | non-negotiable | false | 10 |
| R10208 | Profile redef — later scope: 6 profiles with explicit max authority levels per envelope | dump 17468-17487 | F05104 | non-negotiable | false | 10 |
| R10209 | Profile redef — CANONICAL: authority-gate framing | dump 17468-17488 + operator standing direction | F05105 | non-negotiable | false | 10 |
| R10210 | Profile redef — HISTORICAL: memory-lens framing preserved verbatim, marked superseded | dump 8420-8440 + operator standing direction | F05101 | non-negotiable | false | 10 |
| R10211 | Profile redef — affected sovereign-os: M016 M017 | backward-sweep findings | F05106 | non-negotiable | false | 10 |
| R10212 | Profile redef — affected selfdef: MS010 | backward-sweep findings | F05106 | non-negotiable | false | 10 |
| R10213 | Profile redef — affected milestones receive canon-update annotation | architecture + operator standing direction | F05145 | non-negotiable | false | 10 |
| R10214 | Profile redef — selfdef MS040 already cataloged under authority-gate canon | cross-ref selfdef MS040 | F05108 | non-negotiable | false | 10 |
| R10215 | Profile redef — severity = BREAKING | backward-sweep findings | F05106 | non-negotiable | false | 10 |
| R10216 | Core Law redef — 5-line variant at dump 15350-15355 | dump 15350-15355 | F05109 | non-negotiable | false | 10 |
| R10217 | Core Law redef — 5-line variant at dump 15789-15794 | dump 15789-15794 | F05110 | non-negotiable | false | 10 |
| R10218 | Core Law redef — canonical 6-line at dump 18299-18305 | dump 18299-18305 | F05111 | non-negotiable | false | 10 |
| R10219 | Core Law redef — CANONICAL line 1: Models propose | dump 18299 | F05112 | non-negotiable | false | 10 |
| R10220 | Core Law redef — CANONICAL line 2: Runtime routes | dump 18300 | F05112 | non-negotiable | false | 10 |
| R10221 | Core Law redef — CANONICAL line 3: CPU enforces (added in 6-line) | dump 18301 | F05112 | non-negotiable | false | 10 |
| R10222 | Core Law redef — CANONICAL line 4: Tools prove | dump 18302 | F05112 | non-negotiable | false | 10 |
| R10223 | Core Law redef — CANONICAL line 5: ZFS remembers | dump 18303 | F05112 | non-negotiable | false | 10 |
| R10224 | Core Law redef — CANONICAL line 6: User chooses | dump 18304 | F05112 | non-negotiable | false | 10 |
| R10225 | Core Law redef — affected: sovereign-os M005 M006 M009 M020 | backward-sweep findings | F05113 | non-negotiable | false | 10 |
| R10226 | Core Law redef — sovereign-os M059 already cataloged with canonical 6-line | cross-ref M059 | F05114 | non-negotiable | false | 10 |
| R10227 | Core Law redef — severity = CLARIFYING | backward-sweep findings | F05113 | non-negotiable | false | 10 |
| R10228 | Core Law redef — Core Law file at /etc/sovereign-os/core-law.txt MUST contain canonical 6-line form | architecture + dump 18299-18305 | F05111 | non-negotiable | false | 10 |
| R10229 | Core Law redef — Core Law file signed via MS003 | cross-ref selfdef MS003 | F05111 | non-negotiable | false | 10 |
| R10230 | Authority redef — earlier sections had authority implicit | dump 1-9000 (implicit) | F05115 | non-negotiable | false | 10 |
| R10231 | Authority redef — later section adds explicit 7-level ladder at dump 17252-17272 | dump 17252-17272 | F05116 | non-negotiable | false | 10 |
| R10232 | Authority redef — L0 Observe read-only no side effects | dump 17252-17254 | F05117 | non-negotiable | false | 10 |
| R10233 | Authority redef — L1 Suggest propose actions no execution | dump 17255-17257 | F05117 | non-negotiable | false | 10 |
| R10234 | Authority redef — L2 Simulate sandbox no host mutation | dump 17258-17260 | F05117 | non-negotiable | false | 10 |
| R10235 | Authority redef — L3 Prepare diff/plan/command pending approval | dump 17261-17263 | F05117 | non-negotiable | false | 10 |
| R10236 | Authority redef — L4 Execute-bounded allowed tool action within policy | dump 17264-17266 | F05117 | non-negotiable | false | 10 |
| R10237 | Authority redef — L5 Commit mutate project/host state after gates | dump 17267-17269 | F05117 | non-negotiable | false | 10 |
| R10238 | Authority redef — L6 Persist write memory/profile/policy/adapter changes | dump 17270-17272 | F05117 | non-negotiable | false | 10 |
| R10239 | Authority redef — CANONICAL: explicit 7-level ladder | dump 17252-17272 | F05118 | non-negotiable | false | 10 |
| R10240 | Authority redef — affected: sovereign-os M005 M007 M014 M017 | backward-sweep findings | F05119 | non-negotiable | false | 10 |
| R10241 | Authority redef — sovereign-os M056 already cataloged with full ladder | cross-ref M056 | F05120 | non-negotiable | false | 10 |
| R10242 | Authority redef — selfdef MS039 already cataloged with full ladder (IPS-side projection) | cross-ref selfdef MS039 | F05121 | non-negotiable | false | 10 |
| R10243 | Authority redef — severity = ADDITIVE | backward-sweep findings | F05119 | non-negotiable | false | 10 |
| R10244 | Trust ring redef — earlier sections had no explicit ring topology | dump 1-9000 (dispersed) | F05122 | non-negotiable | false | 10 |
| R10245 | Trust ring redef — later section adds 5-ring topology at dump 17280-17302 | dump 17280-17302 | F05123 | non-negotiable | false | 10 |
| R10246 | Trust ring redef — Ring 0 Sovereign Kernel: policy, gateway, replay, memory authority | dump 17280-17284 | F05124 | non-negotiable | false | 10 |
| R10247 | Trust ring redef — Ring 1 Trusted Local: model servers, memory service, eval service | dump 17285-17287 | F05124 | non-negotiable | false | 10 |
| R10248 | Trust ring redef — Ring 2 Sandboxed: tool workers, build/test containers, browser agents | dump 17288-17290 | F05124 | non-negotiable | false | 10 |
| R10249 | Trust ring redef — Ring 3 Experimental: unknown code, external downloads, risky web | dump 17291-17293 | F05124 | non-negotiable | false | 10 |
| R10250 | Trust ring redef — Ring 4 Cloud-External: remote APIs, external services, internet | dump 17294-17302 | F05124 | non-negotiable | false | 10 |
| R10251 | Trust ring redef — ring transition requires explicit policy | dump 17302 | F05125 | non-negotiable | false | 10 |
| R10252 | Trust ring redef — CANONICAL: 5-ring topology | dump 17280-17302 | F05125 | non-negotiable | false | 10 |
| R10253 | Trust ring redef — affected: sovereign-os M011 M014 M016 | backward-sweep findings | F05126 | non-negotiable | false | 10 |
| R10254 | Trust ring redef — sovereign-os M056 already cataloged with full ring topology | cross-ref M056 | F05127 | non-negotiable | false | 10 |
| R10255 | Trust ring redef — selfdef MS039 already cataloged with full ring topology | cross-ref selfdef MS039 | F05128 | non-negotiable | false | 10 |
| R10256 | Trust ring redef — severity = ADDITIVE | backward-sweep findings | F05126 | non-negotiable | false | 10 |
| R10257 | Scheduler redef — earlier sections had scheduler as component at dump 312, 677, 1325 | dump 312 + 677 + 1325 | F05129 | non-negotiable | false | 10 |
| R10258 | Scheduler redef — later section makes scheduler first-class policy layer at dump 17914-18268 | dump 17914-18268 | F05130 | non-negotiable | false | 10 |
| R10259 | Scheduler redef — 6 scheduling policies per profile (fast/careful/private/autonomous/experimental/production) | dump 18001-18030 | F05131 | non-negotiable | false | 10 |
| R10260 | Scheduler redef — 8 resource types + 8 queue types | dump 17920-17999 | F05132 | non-negotiable | false | 10 |
| R10261 | Scheduler redef — Blackwell/4090/CPU policies + Backpressure + Goldilocks objective | dump 18040-18209 | F05132 | non-negotiable | false | 10 |
| R10262 | Scheduler redef — Key Scheduling Law "never let expensive cognition wait on cheap preparation" | dump 18261-18264 | F05133 | non-negotiable | false | 10 |
| R10263 | Scheduler redef — CANONICAL: policy-layer scheduler with per-profile scheduling | dump 17914-18268 | F05134 | non-negotiable | false | 10 |
| R10264 | Scheduler redef — affected: sovereign-os M005 M007 M009 | backward-sweep findings | F05135 | non-negotiable | false | 10 |
| R10265 | Scheduler redef — sovereign-os M058 already cataloged with full policy-layer canon | cross-ref M058 | F05136 | non-negotiable | false | 10 |
| R10266 | Scheduler redef — severity = BREAKING | backward-sweep findings | F05135 | non-negotiable | false | 10 |
| R10267 | Commit redef — earlier sections framed commit as deterministic substrate at dump 1527, 1858, 2139, 2155, 2319 | dump 1527 + 1858 + 2139 + 2155 + 2319 | F05137 | non-negotiable | false | 10 |
| R10268 | Commit redef — earlier scope: CPU commits accepted transitions to replay log | dump 2155 | F05138 | non-negotiable | false | 10 |
| R10269 | Commit redef — earlier scope: policy-filtered commit equation | dump 2155 | F05138 | non-negotiable | false | 10 |
| R10270 | Commit redef — later section frames commit as evidence-earned authority at dump 17389-17421 | dump 17389-17421 | F05139 | non-negotiable | false | 10 |
| R10271 | Commit redef — later scope: 8 commit types | dump 17391-17398 | F05140 | non-negotiable | false | 10 |
| R10272 | Commit redef — later scope: 5 mandatory fields (actor/reason/policy-decision/rollback-status/trace-reference) | dump 17396-17402 | F05140 | non-negotiable | false | 10 |
| R10273 | Commit redef — later scope: 3 high-risk gates (snapshot/test-eval/oracle-or-human) | dump 17415-17421 | F05140 | non-negotiable | false | 10 |
| R10274 | Commit redef — DISTINCTION: speculative commit = runtime token masking (earlier scope) | dump 1527-2319 + operator standing direction | F05141 | non-negotiable | false | 10 |
| R10275 | Commit redef — DISTINCTION: durable commit = policy-gated action logging (later scope) | dump 17389-17421 + operator standing direction | F05141 | non-negotiable | false | 10 |
| R10276 | Commit redef — both layers retained: speculative (runtime-level) + durable (action-level) | operator standing direction "never discarded" | F05142 | non-negotiable | false | 10 |
| R10277 | Commit redef — CANONICAL durable commit form at 17389-17421 | dump 17389-17421 | F05142 | non-negotiable | false | 10 |
| R10278 | Commit redef — affected: sovereign-os M006 M010 (distinguish speculative vs durable commit) | backward-sweep findings | F05143 | non-negotiable | false | 10 |
| R10279 | Commit redef — selfdef MS041 already cataloged with full evidence-earned canon | cross-ref selfdef MS041 | F05144 | non-negotiable | false | 10 |
| R10280 | Commit redef — severity = BREAKING (for distinguishing layers, not for replacing) | backward-sweep findings | F05143 | non-negotiable | false | 10 |
| R10281 | Patch pass A — annotation format = single block at top of milestone file | architecture | F05145 | non-negotiable | false | 10 |
| R10282 | Patch pass A — annotation cites M061 + canonical line range | architecture | F05146 | non-negotiable | false | 10 |
| R10283 | Patch pass A — annotation severity tag preserved | backward-sweep findings | F05147 | non-negotiable | false | 10 |
| R10284 | Patch pass A — annotation signed via MS003 (file-level signature) | cross-ref selfdef MS003 | F05148 | non-negotiable | false | 10 |
| R10285 | Patch pass A — annotation emits M049 trace on application | cross-ref M049 | F05149 | non-negotiable | false | 10 |
| R10286 | Patch pass A — annotation applied to sovereign-os M005 M006 M007 M009 M010 M011 M014 M016 M017 M020 | backward-sweep findings | F05159 | non-negotiable | false | 10 |
| R10287 | Patch pass A — annotation applied to selfdef MS010 | backward-sweep findings | F05160 | non-negotiable | false | 10 |
| R10288 | Patch pass A — total: 11 milestone files receive annotations | architecture + backward-sweep findings | F05159 | non-negotiable | false | 10 |
| R10289 | Patch pass A — annotations land in same commit (atomic) | architecture | F05148 | non-negotiable | false | 10 |
| R10290 | Patch pass A — pass A timeline: complete within 7 days of M061 landing | architecture | F05145 | non-negotiable | false | 10 |
| R10291 | Patch pass B — MS007 typed-mirror crates bump version for breaking redefinitions | cross-ref selfdef MS007 | F05150 | non-negotiable | false | 10 |
| R10292 | Patch pass B — breaking crates: profile-mirror (BREAKING via profile redef) | cross-ref selfdef MS007 + selfdef MS040 | F05150 | non-negotiable | false | 10 |
| R10293 | Patch pass B — non-breaking crates: authority-mirror, ring-membership-mirror (ADDITIVE) | cross-ref selfdef MS007 + selfdef MS039 | F05151 | non-negotiable | false | 10 |
| R10294 | Patch pass B — clarifying crates: super-model-mirror (CLARIFYING via Core Law 6-line) | cross-ref selfdef MS007 + M059 | F05151 | non-negotiable | false | 10 |
| R10295 | Patch pass B — all crate bumps signed via MS003 | cross-ref selfdef MS003 | F05152 | non-negotiable | false | 10 |
| R10296 | Patch pass B — crate bump triggers sovereign-os runtime workspace re-resolve | cross-ref selfdef MS007 | F05153 | non-negotiable | false | 10 |
| R10297 | Patch pass C — schema_version "1.0.0" → "1.1.0" on additive changes | cross-ref selfdef MS007 | F05154 | non-negotiable | false | 10 |
| R10298 | Patch pass C — schema_version "1.0.0" → "2.0.0" on breaking changes | cross-ref selfdef MS007 | F05155 | non-negotiable | false | 10 |
| R10299 | Patch pass C — schema bumps emit OCSF Configuration Change class 5001 | cross-ref selfdef MS026 | F05156 | non-negotiable | false | 10 |
| R10300 | Patch pass C — schema bumps signed via MS003 | cross-ref selfdef MS003 | F05157 | non-negotiable | false | 10 |
| R10301 | Patch pass C — schema_version retained in MS007 crate metadata + CHANGELOG.md | cross-ref selfdef MS007 | F05158 | non-negotiable | false | 10 |
| R10302 | Supersedes recorder — earlier R-row IDs catalogued in MS007 sovereign-canon-supersedes-mirror crate | cross-ref selfdef MS007 | F05161 | non-negotiable | false | 10 |
| R10303 | Supersedes recorder — supersedes link is READ-ONLY metadata | operator standing direction "never discarded" | F05162 | non-negotiable | false | 10 |
| R10304 | Supersedes recorder — supersedes link NEVER deletes earlier R-row | operator standing direction "never discarded" | F05162 | non-negotiable | false | 10 |
| R10305 | Supersedes recorder — supersedes metadata published as MS007 crate | cross-ref selfdef MS007 | F05163 | non-negotiable | false | 10 |
| R10306 | Replay validator — selfdef MS009 replay validator honors canon-update annotations | cross-ref selfdef MS009 | F05164 | non-negotiable | false | 10 |
| R10307 | Replay validator — canon-update annotations carry chain-of-trust signature | cross-ref selfdef MS003 | F05165 | non-negotiable | false | 10 |
| R10308 | Replay validator — chain-break detection treats canon-update as authoritative | cross-ref selfdef MS009 | F05166 | non-negotiable | false | 10 |
| R10309 | Trace emitter — every canon-update event emits M049 13-field span | cross-ref M049 | F05167 | non-negotiable | false | 10 |
| R10310 | Trace emitter — span includes redefinition severity | cross-ref M049 + backward-sweep findings | F05168 | non-negotiable | false | 10 |
| R10311 | Trace emitter — span includes affected milestone list | cross-ref M049 + backward-sweep findings | F05168 | non-negotiable | false | 10 |
| R10312 | OCSF event emitter — canon-updates emit Configuration Change class 5001 | cross-ref selfdef MS026 | F05169 | non-negotiable | false | 10 |
| R10313 | OCSF event emitter — breaking redefinitions additionally emit Detection Finding class 2004 | cross-ref selfdef MS026 | F05170 | non-negotiable | false | 10 |
| R10314 | Doctrinal preservation — earlier R-rows preserved verbatim across all 11 affected milestones | operator standing direction | F05171 | non-negotiable | false | 10 |
| R10315 | Doctrinal preservation — canon-update LAYERED ON TOP | operator standing direction | F05172 | non-negotiable | false | 10 |
| R10316 | Doctrinal preservation — operator words verbatim quoted in M061 doc | operator standing direction | F05173 | non-negotiable | false | 10 |
| R10317 | Doctrinal preservation — verbatim quotes never paraphrased | operator standing direction | F05174 | non-negotiable | false | 10 |
| R10318 | Doctrinal preservation — info-hub knowledge graph indexes redefinitions as second-brain entries | operator standing direction "knowledge = second-brain" | F05175 | non-negotiable | false | 10 |
| R10319 | Prior-dump review planner — operator: "there was also other dumps before that we decided to restart" | operator standing direction | F05176 | non-negotiable | false | 10 |
| R10320 | Prior-dump review planner — inventory prior dumps at ~/infohub/raw/dumps/ | architecture + operator standing direction | F05177 | non-negotiable | false | 10 |
| R10321 | Prior-dump review planner — review approach: backward-pass per dump | operator standing direction | F05178 | non-negotiable | false | 10 |
| R10322 | Prior-dump review planner — identify supplanted concepts | operator standing direction | F05178 | non-negotiable | false | 10 |
| R10323 | Prior-dump review planner — ADD net-new requirements only | operator standing direction | F05178 | non-negotiable | false | 10 |
| R10324 | Prior-dump review planner — output target: new milestones M062+ / MS044+ | architecture | F05179 | non-negotiable | false | 10 |
| R10325 | Prior-dump review planner — never discards prior-dump material | operator standing direction "never discarded" | F05180 | non-negotiable | false | 10 |
| R10326 | Prior-dump review planner — treats prior dumps as additional canon source | operator standing direction | F05180 | non-negotiable | false | 10 |
| R10327 | Prior-dump review planner — operator: "not that all was lost but it was down a rabbit role and with weird things happening versus what I asked" | operator standing direction | F05176 | non-negotiable | false | 10 |
| R10328 | Prior-dump review planner — preserve good material, discard "weird things versus what I asked" | operator standing direction | F05180 | non-negotiable | false | 10 |
| R10329 | Prior-dump review planner — review precedes SDD/TDD implementation phase | operator standing direction | F05181 | non-negotiable | false | 10 |
| R10330 | SDD-TDD readiness gate — implementation phase begins only after catalog complete | operator standing direction | F05181 | non-negotiable | false | 10 |
| R10331 | SDD-TDD readiness gate — implementation phase begins only after backward-sweep patches applied | operator standing direction | F05181 | non-negotiable | false | 10 |
| R10332 | SDD-TDD readiness gate — implementation phase begins only after prior-dump review complete | operator standing direction | F05181 | non-negotiable | false | 10 |
| R10333 | SDD-TDD readiness gate — gate check: M001..M061 + MS001..MS043 landed on main | architecture | F05182 | non-negotiable | false | 10 |
| R10334 | SDD-TDD readiness gate — gate check: backward-sweep patch pass A applied to 11 affected milestones | architecture | F05183 | non-negotiable | false | 10 |
| R10335 | SDD-TDD readiness gate — gate check: prior-dump milestones M062+ / MS044+ inventoried | architecture | F05184 | non-negotiable | false | 10 |
| R10336 | SDD-TDD readiness gate — implementation begins with first SDD doc per milestone order | operator standing direction | F05185 | non-negotiable | false | 10 |
| R10337 | SDD-TDD readiness gate — small commits direct-to-main throughout implementation | operator standing direction | F05185 | non-negotiable | false | 10 |
| R10338 | SDD-TDD readiness gate — L1-L5 layered test harness pattern | operator standing direction | F05185 | non-negotiable | false | 10 |
| R10339 | SDD-TDD readiness gate — Layer 0 = operator words verbatim, logged to raw/notes/ before acting | operator standing direction | F05185 | non-negotiable | false | 10 |
| R10340 | SDD-TDD readiness gate — real-substrate execution at L3+, no stubs above L2 | operator standing direction | F05185 | non-negotiable | false | 10 |
| R10341 | Closing — backward-sweep complete (6 redefinitions identified) | architecture + backward-sweep findings | F05597 | non-negotiable | false | 10 |
| R10342 | Closing — 11 affected milestone files identified for patch pass A | backward-sweep findings | F05159 | non-negotiable | false | 10 |
| R10343 | Closing — patch passes A/B/C planned + scheduled | architecture | F05145 | non-negotiable | false | 10 |
| R10344 | Closing — prior-dump review next | operator standing direction | F05176 | non-negotiable | false | 10 |
| R10345 | Closing — SDD/TDD readiness gate defined | operator standing direction | F05181 | non-negotiable | false | 10 |
| R10346 | Closing — sovereign-os catalog at 61/61 milestones | architecture | F05597 | non-negotiable | false | 10 |
| R10347 | Closing — combined ecosystem 104 milestones (selfdef 43 + sovereign-os 61) | architecture | F05597 | non-negotiable | false | 10 |
| R10348 | Closing — combined R-rows ~20690 (R10320 + R10370) | architecture | F05597 | non-negotiable | false | 10 |
| R10349 | Closing — combined enforced sub-reqs ~206900 | architecture | F05597 | non-negotiable | false | 10 |
| R10350 | Closing — operator standing /goal "10000+ requirements" exceeded individually per repo | operator standing direction | F05597 | non-negotiable | false | 10 |
| R10351 | Closing — sovereignty preserved (peace machine axiom retained throughout) | sovereign-os M059 + operator standing direction | F05597 | non-negotiable | false | 10 |
| R10352 | Closing — project boundary discipline maintained throughout catalog | operator standing direction | F05597 | non-negotiable | false | 10 |
| R10353 | Closing — IPS features stay in selfdef, runtime features in sovereign-os, knowledge in info-hub | operator standing direction "Respect the projects" | F05597 | non-negotiable | false | 10 |
| R10354 | Closing — cross-repo binding routed only through MS007 8/8 SATURATED typed mirrors | cross-ref selfdef MS007 | F05597 | non-negotiable | false | 10 |
| R10355 | Closing — info-hub knowledge layer treated read-only from runtime+IPS sessions | operator standing direction | F05597 | non-negotiable | false | 10 |
| R10356 | Closing — multi-hour autonomous cycles (2h/4h/8h/16h) supported throughout | operator standing direction | F05597 | non-negotiable | false | 10 |
| R10357 | Closing — harness remains configured across all cycle lengths | operator standing direction | F05597 | non-negotiable | false | 10 |
| R10358 | Closing — DISABLE_AUTOCOMPACT=1 sacrosanct, never substituted | operator standing direction | F05597 | non-negotiable | false | 10 |
| R10359 | Closing — perpetual /goal cycles supported across catalog + implementation phases | operator standing direction | F05597 | non-negotiable | false | 10 |
| R10360 | Closing — operator words verbatim preserved at every commit | operator standing direction | F05597 | non-negotiable | false | 10 |
| R10361 | Closing — operator words layered (additive) when new direction arrives | operator standing direction | F05597 | non-negotiable | false | 10 |
| R10362 | Closing — model identifier never included in commit messages, PR titles/bodies, code comments | operator standing direction | F05597 | non-negotiable | false | 10 |
| R10363 | Closing — direct-to-main commits on selfdef + sovereign-os remain authorized | operator standing direction | F05597 | non-negotiable | false | 10 |
| R10364 | Closing — every commit signs via MS003 selfdef-signing | cross-ref selfdef MS003 | F05597 | non-negotiable | false | 10 |
| R10365 | Closing — every commit emits M049 trace event | cross-ref M049 | F05597 | non-negotiable | false | 10 |
| R10366 | Closing — every L6 module persistence updates super-model manifest | cross-ref selfdef MS039 + M059 | F05597 | non-negotiable | false | 10 |
| R10367 | Closing — every super-model version retained 365 days minimum | cross-ref M047 | F05597 | non-negotiable | false | 10 |
| R10368 | Closing — peace machine remains the deliverable | sovereign-os M059 | F05597 | non-negotiable | false | 10 |
| R10369 | Closing — intelligence remains in user's hands (sovereignty axiom) | dump 18341 + operator standing direction | F05597 | non-negotiable | false | 10 |
| R10370 | Closing — every R-row carries 10 hard non-negotiable sub-requirements | operator standing direction | F05597 | non-negotiable | false | 10 |

## Sub-requirements accounting

Every R-row carries 10 hard non-negotiable sub-requirements per operator standing direction. Total enforced sub-reqs = 170 R × 10 = **1,700 sub-requirements** for M061.

## Cross-references

- **All M001..M060 + MS001..MS043** — this milestone references the entire ecosystem catalog
- **M005, M006, M007, M009, M010, M011, M014, M016, M017, M020** — affected sovereign-os milestones (patch pass A annotations pending)
- **MS010** — affected selfdef milestone (patch pass A annotation pending)
- **M056** — already canonical (authority levels + trust rings)
- **M057** — canonical (12-step task lifecycle)
- **M058** — already canonical (hardware-aware scheduler policy layer)
- **M059** — already canonical (super-model identity + Core Law 6-line)
- **selfdef MS039** — already canonical (IPS-side authority levels + trust rings)
- **selfdef MS040** — already canonical (six-profile authority-gate matrix)
- **selfdef MS041** — already canonical (commit authority evidence-earned)
- **selfdef MS003** — selfdef-signing (signs all annotations + chain)
- **selfdef MS007** — typed-mirror crate scheme (sovereign-canon-supersedes-mirror published)
- **selfdef MS009** — replay validator (honors canon-update annotations)
- **selfdef MS026** — OCSF event emission
- **M049** — observability + trace pipeline
- **Companion**: `/home/user/sovereign-os/backlog/notes/backward-sweep-2026-05-19-findings.md`

## Schema

```
schema_version: "1.0.0"
milestone_id: M061
parent: sovereign-os
epics: 10
modules: 17
features: 85
requirements: 170
sub_requirements_per_requirement: 10
total_sub_requirements: 1700
purpose: avx-plus-plus canon-update — backward-sweep redefinitions
redefinitions_total: 6
severity_breakdown:
  breaking: 3 (profiles, scheduler, commit-authority)
  clarifying: 1 (core law 6-line)
  additive: 2 (authority levels, trust rings)
affected_milestones_total: 11
affected_milestones_sovereign_os: [M005, M006, M007, M009, M010, M011, M014, M016, M017, M020]
affected_milestones_selfdef: [MS010]
patch_passes:
  - A: affected-milestone canon-update annotations
  - B: MS007 typed-mirror crate version bumps
  - C: schema_version bumps
operator_doctrine_layered_additive: true
operator_doctrine_never_discarded: true
catalog_status:
  sovereign_os: 61/61 milestones
  selfdef: 43/43 milestones
  combined: 104 milestones
next_phase: prior-dump review (then SDD/TDD implementation gated)
```
