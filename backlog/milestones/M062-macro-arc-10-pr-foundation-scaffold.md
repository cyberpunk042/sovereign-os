# M062 — Macro-Arc 10-PR Foundation Scaffold (Stage 1)

**Parent**: sovereign-os runtime — foundation governance layer
**Source**: `~/infohub/raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md` (29KB, 405 lines)
- Macro-Arc Summary (lines 3-17)
- PR 1 Repo Genesis & Charter Stub (lines 19-44)
- PR 2 ARCHITECTURE.md & Cross-Repo Reference Map (lines 46-63)
- PR 3 mdbook Layout & MCP Config Template (lines 65-82)
- PR 4 Substrate Survey SDD (lines 84-117)
- PR 5 Profile Schema SDD (lines 119-141)
- PR 6 SAIN-01 & old-workstation Profile Stubs (lines 143-168)
- PR 7 Whitelabel Audit SDD (lines 170-197)
- PR 8 Whitelabel Mechanism SDD (lines 199-218)
- PR 9 TDD Harness SDD (lines 220-256)
- PR 10 TDD Harness Scaffold + First Passing Tests (lines 258-282)
- Critical-Decisions Surface (lines 284-300)
- Trade-Off Analysis Table (lines 302-319)
- Stage-Gate Placement (lines 321-330)
**Operator standing direction** (verbatim, 2026-05-19): *"following the proper workflow and respect of SFIF and second-brain knowledge"* — SFIF discipline catalogued at M063 layers ON TOP OF this 10-PR scaffold.

## Doctrinal anchors

> "The `sovereign-os` repo's first 6-10 PRs deliver a **disciplined foundation for an SDD/TDD-governed OS-build pipeline** — not a working build." (dump 5-6)
> "...mechanisms are specified before scripts are written, and tests are scaffolded before mechanisms are executed." (dump 7)
> "Each gate is an `ExitPlanMode`-style checkpoint where execution pauses, operator reviews, and explicitly authorizes the next phase. No PR opens past a gate without operator sign-off." (dump 329-330)

## Epics (E0598-E0607)

| epic | name | source |
|---|---|---|
| E0598 | PR 1 — Repo genesis + charter stub (no build code) | dump 19-44 |
| E0599 | PR 2 — ARCHITECTURE.md + cross-repo reference map | dump 46-63 |
| E0600 | PR 3 — mdbook layout + MCP config template | dump 65-82 |
| E0601 | PR 4 — Substrate survey SDD (research-only) | dump 84-117 |
| E0602 | PR 5 — Profile schema SDD | dump 119-141 |
| E0603 | PR 6 — SAIN-01 + old-workstation schema-conformant profile stubs | dump 143-168 |
| E0604 | PR 7 — Whitelabel audit SDD | dump 170-197 |
| E0605 | PR 8 — Whitelabel mechanism SDD | dump 199-218 |
| E0606 | PR 9 — TDD harness SDD | dump 220-256 |
| E0607 | PR 10 — TDD harness scaffold + first passing tests + Stage Gate 5 | dump 258-282 |

## Modules (M01037-M01053)

| module | name | source |
|---|---|---|
| M01037 | sovereign-pr1-repo-genesis | dump 19-44 |
| M01038 | sovereign-pr2-architecture-doc | dump 46-63 |
| M01039 | sovereign-pr3-mdbook-mcp-template | dump 65-82 |
| M01040 | sovereign-pr4-substrate-survey | dump 84-117 |
| M01041 | sovereign-pr5-profile-schema | dump 119-141 |
| M01042 | sovereign-pr6-profile-instances | dump 143-168 |
| M01043 | sovereign-pr7-whitelabel-audit | dump 170-197 |
| M01044 | sovereign-pr8-whitelabel-mechanism | dump 199-218 |
| M01045 | sovereign-pr9-tdd-harness-spec | dump 220-256 |
| M01046 | sovereign-pr10-tdd-harness-scaffold | dump 258-282 |
| M01047 | sovereign-stage-gate-1-coordinator | dump 82 |
| M01048 | sovereign-stage-gate-2-coordinator | dump 117 |
| M01049 | sovereign-stage-gate-3-coordinator | dump 168 |
| M01050 | sovereign-stage-gate-4-coordinator | dump 218 |
| M01051 | sovereign-stage-gate-5-coordinator | dump 282 |
| M01052 | sovereign-critical-decisions-surface | dump 284-300 |
| M01053 | sovereign-trade-off-analysis-engine | dump 302-319 |

## Features (F05186-F05270)

| feature | name | source |
|---|---|---|
| F05186 | PR 1 — README.md (purpose / relationship to selfdef + info-hub / current status / 11 epics pointer) | dump 25-26 |
| F05187 | PR 1 — docs/sdd/000-charter.md stub (~200 LOC) — mission + scope + non-goals | dump 26-27 |
| F05188 | PR 1 — docs/decisions.md seeded (repo identity / substrate-undecided / schema-first / plan-tool-yes + open Q seeds) | dump 28-30 |
| F05189 | PR 1 — docs/sdd/INDEX.md (empty numbered 000-010 table) | dump 30 |
| F05190 | PR 1 — docs/handoff/INDEX.md (empty anchor table) | dump 31 |
| F05191 | PR 1 — docs/review/INDEX.md (empty audit phase table) | dump 32 |
| F05192 | PR 1 — .gitignore + LICENSE (match selfdef) + CODEOWNERS | dump 33 |
| F05193 | PR 1 — LOC estimate ~600 (markdown only) | dump 36 |
| F05194 | PR 1 — dependencies: none | dump 37 |
| F05195 | PR 2 — ARCHITECTURE.md (~400 LOC) cites 11 epics E100-E110 by info-hub citation | dump 49-52 |
| F05196 | PR 2 — three-repo boundary diagram (sovereign-os BUILDS / selfdef RUNS / info-hub SYNTHESIZES) | dump 53 |
| F05197 | PR 2 — four lifecycle stages (pre-install / during-install / post-install / ongoing-management) | dump 53 |
| F05198 | PR 2 — four cross-cutting concerns (profiles / whitelabel / observability / evolvability) | dump 53 |
| F05199 | PR 2 — docs/sdd/001-cross-repo-boundaries.md substantive SDD (~350 LOC) | dump 54-55 |
| F05200 | PR 2 — docs/handoff/001-architecture-baseline.md | dump 56 |
| F05201 | PR 2 — LOC estimate ~900 | dump 58 |
| F05202 | PR 2 — depends on PR 1 merged | dump 60 |
| F05203 | PR 3 — docs/src/SUMMARY.md (mdbook nav) | dump 68 |
| F05204 | PR 3 — docs/src/ tree mirroring docs/sdd/ + docs/handoff/ + docs/review/ | dump 69 |
| F05205 | PR 3 — book.toml mirroring selfdef | dump 70 |
| F05206 | PR 3 — .github/workflows/mdbook-publish.yml (mirror selfdef pattern) | dump 71 |
| F05207 | PR 3 — .mcp/config.template.json (placeholders for operator MCP setup) | dump 72 |
| F05208 | PR 3 — docs/sdd/002-documentation-pipeline.md (~250 LOC) | dump 73 |
| F05209 | PR 3 — LOC estimate ~500 | dump 75 |
| F05210 | PR 3 — depends on PR 2 merged | dump 77 |
| F05211 | Stage Gate 1 — operator review after PRs 1-3 | dump 79-82 + 322 |
| F05212 | Stage Gate 1 — confirms structural foundation matches selfdef rhythm | dump 82 + 322 |
| F05213 | Stage Gate 1 — authorizes substantive-SDD phase to begin | dump 82 |
| F05214 | PR 4 — docs/sdd/003-substrate-survey.md (~1200 LOC research doc) | dump 86-105 |
| F05215 | PR 4 — candidates surveyed: live-build / mkosi / debootstrap / Lorax / Kiwi / ostree / Nix / Buildroot | dump 91 |
| F05216 | PR 4 — 12 criteria matrix dimensions (Debian-13 / declarative / pluralism / whitelabel / reproducibility / CI-testability / ZFS-root / secure-boot / community / familiarity / lifecycle-tool / evolvability) | dump 93-94 |
| F05217 | PR 4 — per-candidate prose justification (not just scores) | dump 95 |
| F05218 | PR 4 — recommendation: single OR ranked A/B/C (operator chooses) | dump 96 |
| F05219 | PR 4 — reversal cost section per recommended substrate | dump 97 |
| F05220 | PR 4 — LOC estimate ~1300 | dump 102 |
| F05221 | PR 4 — depends on PR 3 + parallel with PR 5/7 | dump 104 |
| F05222 | Stage Gate 2 — operator picks substrate (or asks deeper dive on top 2) | dump 113-117 |
| F05223 | Stage Gate 2 — decision recorded in docs/decisions.md | dump 116 |
| F05224 | Stage Gate 2 — no code-bearing PR proceeds until substrate locked | dump 117 |
| F05225 | PR 5 — docs/sdd/004-profile-schema.md (~700 LOC) | dump 122-141 |
| F05226 | PR 5 — schema dimensions: identity / hardware-target / kernel-config / package-sets / activation-hooks / lifecycle-metadata / whitelabel-binding / observability-binding | dump 124-135 |
| F05227 | PR 5 — schemas/profile.schema.yaml (~250 LOC) | dump 137 |
| F05228 | PR 5 — trade-off section: inheritance vs composition / rigid vs extensible / YAML vs TOML vs HCL | dump 138 |
| F05229 | PR 5 — LOC estimate ~1000 | dump 140 |
| F05230 | PR 5 — depends on PR 3 + parallel with PR 4/7 | dump 142 |
| F05231 | PR 6 — profiles/sain-01.yaml (~200 LOC) — full hardware target (Ryzen 9 9900X / Blackwell + 3090 VFIO / 256GB / ZFS RAID 0 / 10GbE+2.5GbE / ProArt X870E) | dump 147-149 |
| F05232 | PR 6 — profiles/old-workstation.yaml (~100 LOC) — older hardware (11GB RAM, 8GB GPU) | dump 150 |
| F05233 | PR 6 — profiles/INDEX.md catalog of declared profiles | dump 151 |
| F05234 | PR 6 — docs/sdd/005-initial-profiles.md (~300 LOC) — justifies seed set + reserves minimal/developer/headless | dump 152 |
| F05235 | PR 6 — scripts/validate-profiles.sh (~80 LOC) — first test-bearing artifact | dump 153 |
| F05236 | PR 6 — LOC estimate ~700 | dump 158 |
| F05237 | PR 6 — depends on PR 5 | dump 160 |
| F05238 | Stage Gate 3 — schema lock-in (may be revised once instances reveal gaps; locked thereafter) | dump 167-168 |
| F05239 | PR 7 — docs/sdd/006-debian-surface-audit.md (~900 LOC) | dump 173-189 |
| F05240 | PR 7 — filesystem surfaces (/etc/issue / os-release / lsb-release / debian_version / motd) | dump 175-178 |
| F05241 | PR 7 — package-manager surfaces (DPKG vendor / APT sources / dpkg-vendor / lsb_release) | dump 179 |
| F05242 | PR 7 — boot surfaces (GRUB / Plymouth / kernel boot logo / systemd boot banner) | dump 180 |
| F05243 | PR 7 — installer surfaces (debian-installer / Calamares / preseed banner) | dump 181 |
| F05244 | PR 7 — desktop surfaces (GDM/SDDM/LightDM theming / wallpaper / about-system dialogs) | dump 182 |
| F05245 | PR 7 — kernel surfaces (/proc/version / uname-a / package naming) | dump 183 |
| F05246 | PR 7 — documentation + network + telemetry surfaces | dump 184-186 |
| F05247 | PR 7 — surface categorization (must-rebrand / should-rebrand / may-leave / must-not-touch) | dump 187 |
| F05248 | PR 7 — legal-obligation section (Debian trademark + DFSG + GPL attribution) | dump 188 |
| F05249 | PR 7 — LOC estimate ~950 | dump 191 |
| F05250 | PR 7 — depends on PR 3 + parallel with PR 4/5 | dump 193 |
| F05251 | PR 8 — docs/sdd/007-whitelabel-mechanism.md (~600 LOC) | dump 202-214 |
| F05252 | PR 8 — declarative whitelabel-profile YAML + rendering engine | dump 203 |
| F05253 | PR 8 — per-surface strategy (template-substitution / file-overlay / package-replacement / build-time-flag) | dump 204 |
| F05254 | PR 8 — pre/during/post split (pre-build patches / install-time substitutions / first-boot scripts) | dump 205 |
| F05255 | PR 8 — evolvability (whitelabel swap without full image rebuild) | dump 206 |
| F05256 | PR 8 — legal compliance binding (enforce PR 7 must-not-touch at validation time) | dump 207 |
| F05257 | PR 8 — schemas/whitelabel.schema.yaml (~200 LOC) | dump 208 |
| F05258 | PR 8 — whitelabel/default.yaml placeholder | dump 209 |
| F05259 | PR 8 — LOC estimate ~900 | dump 213 |
| F05260 | Stage Gate 4 — operator reviews whitelabel audit + mechanism; legal posture confirmed | dump 217-218 |
| F05261 | PR 9 — docs/sdd/008-test-harness.md (~800 LOC) | dump 223-250 |
| F05262 | PR 9 — five test layers (schema-lint / unit / stage-acceptance / integration / hardware-conformance) | dump 224-228 |
| F05263 | PR 9 — virtualization stack (chroot / systemd-nspawn / QEMU-system / qemu-user) | dump 229-233 |
| F05264 | PR 9 — invariants per stage (hostname / whitelabel surfaces / ZFS pool / systemd units) | dump 234 |
| F05265 | PR 9 — test discovery + naming + CI execution model + flake policy | dump 235 |
| F05266 | PR 9 — depends on PR 4 + PR 6 + PR 8 | dump 252-254 |
| F05267 | PR 10 — tests/schema/ + tests/lint/ + tests/chroot/scaffold.sh + tests/nspawn/scaffold.sh + tests/qemu/scaffold.sh | dump 263-268 |
| F05268 | PR 10 — .github/workflows/test.yml (CI workflow) | dump 269 |
| F05269 | PR 10 — docs/sdd/009-test-harness-bootstrap.md + docs/sdd/010-stage-2-stub.md | dump 270-271 |
| F05270 | Stage Gate 5 — foundation-complete gate; authorizes Stage 2 (first actual build scripts) | dump 281-282 |

## Requirements (R10371-R10540)

| req | description | source | feature | priority | exception | sub-reqs |
|---|---|---|---|---|---|---|
| R10371 | Doctrinal — first 6-10 PRs deliver a "disciplined foundation for an SDD/TDD-governed OS-build pipeline — not a working build" | dump 5-6 | F05186 | non-negotiable | false | 10 |
| R10372 | Doctrinal — mechanisms specified before scripts written, tests scaffolded before mechanisms executed | dump 7 | F05186 | non-negotiable | false | 10 |
| R10373 | Doctrinal — "we think before we act always" principle | dump 7 + operator standing direction | F05186 | non-negotiable | false | 10 |
| R10374 | Doctrinal — 3 parallelism axes: whitelabel-survey / profile-schema / ~70% hardware-free work | dump 8 | F05221 | non-negotiable | false | 10 |
| R10375 | Doctrinal — mirror selfdef workflow conventions exactly (SDD numbering / decisions log / audit phase / mdbook / MCP) | dump 9 | F05186 | non-negotiable | false | 10 |
| R10376 | Doctrinal — cross-repo references are explicit citations, never duplications | dump 9 | F05195 | non-negotiable | false | 10 |
| R10377 | Doctrinal — no PR opens past a gate without operator sign-off | dump 329-330 | F05211 | non-negotiable | false | 10 |
| R10378 | PR 1 — title: chore: bootstrap sovereign-os repo skeleton and charter stub | dump 22 | F05186 | non-negotiable | false | 10 |
| R10379 | PR 1 — scope: empty-repo scaffolding, no build code, no scripts | dump 24 | F05186 | non-negotiable | false | 10 |
| R10380 | PR 1 — README.md states current status "foundation phase, no buildable artifact yet" | dump 26 | F05186 | non-negotiable | false | 10 |
| R10381 | PR 1 — README.md points to 11 epics in info-hub as architectural baseline | dump 26 | F05186 | non-negotiable | false | 10 |
| R10382 | PR 1 — docs/sdd/000-charter.md stubs the mission | dump 27 | F05187 | non-negotiable | false | 10 |
| R10383 | PR 1 — docs/sdd/000-charter.md stubs scope boundaries (BUILDS / does not RUN / does not SYNTHESIZE) | dump 27 | F05187 | non-negotiable | false | 10 |
| R10384 | PR 1 — docs/sdd/000-charter.md commits to SDD+TDD discipline | dump 28 | F05187 | non-negotiable | false | 10 |
| R10385 | PR 1 — docs/sdd/000-charter.md enumerates explicit non-goals | dump 28 | F05187 | non-negotiable | false | 10 |
| R10386 | PR 1 — docs/decisions.md seeded with locked decisions (repo identity / substrate-undecided / schema-first / plan-tool-yes) | dump 29 | F05188 | non-negotiable | false | 10 |
| R10387 | PR 1 — docs/decisions.md seeded with open-question seed list | dump 30 | F05188 | non-negotiable | false | 10 |
| R10388 | PR 1 — docs/sdd/INDEX.md reserves 000-010 slots | dump 30 | F05189 | non-negotiable | false | 10 |
| R10389 | PR 1 — docs/handoff/INDEX.md empty anchor table | dump 31 | F05190 | non-negotiable | false | 10 |
| R10390 | PR 1 — docs/review/INDEX.md empty audit phase table | dump 32 | F05191 | non-negotiable | false | 10 |
| R10391 | PR 1 — .gitignore + LICENSE (match selfdef) + CODEOWNERS | dump 33 | F05192 | non-negotiable | false | 10 |
| R10392 | PR 1 — critical files: docs/sdd/000-charter.md (~200 LOC) + README.md (~150 LOC) + docs/decisions.md (~120 LOC) | dump 35 | F05193 | non-negotiable | false | 10 |
| R10393 | PR 1 — LOC estimate ~600 total (mostly markdown) | dump 36 | F05193 | non-negotiable | false | 10 |
| R10394 | PR 1 — dependencies: none | dump 37 | F05194 | non-negotiable | false | 10 |
| R10395 | PR 2 — title: docs: add ARCHITECTURE.md referencing info-hub epics and selfdef workflow | dump 47 | F05195 | non-negotiable | false | 10 |
| R10396 | PR 2 — scope: document architectural baseline without re-deriving | dump 49 | F05195 | non-negotiable | false | 10 |
| R10397 | PR 2 — ARCHITECTURE.md cites 11 epics E100-E110 by info-hub backlog milestone path | dump 51-52 | F05195 | non-negotiable | false | 10 |
| R10398 | PR 2 — three-repo boundary diagram (sovereign-os BUILDS / selfdef RUNS / info-hub SYNTHESIZES) | dump 53 | F05196 | non-negotiable | false | 10 |
| R10399 | PR 2 — four lifecycle stages: pre-install / during-install / post-install / ongoing-management | dump 53 | F05197 | non-negotiable | false | 10 |
| R10400 | PR 2 — four cross-cutting concerns: profiles / whitelabel / observability / evolvability | dump 53 | F05198 | non-negotiable | false | 10 |
| R10401 | PR 2 — docs/sdd/001-cross-repo-boundaries.md substantive SDD | dump 54 | F05199 | non-negotiable | false | 10 |
| R10402 | PR 2 — docs/sdd/001 defines what flows across repos and what does not | dump 55 | F05199 | non-negotiable | false | 10 |
| R10403 | PR 2 — docs/sdd/001 references info-hub epics by ID | dump 55 | F05199 | non-negotiable | false | 10 |
| R10404 | PR 2 — docs/handoff/001-architecture-baseline.md captures assumptions at checkpoint | dump 56 | F05200 | non-negotiable | false | 10 |
| R10405 | PR 2 — critical files ~400 + ~350 LOC | dump 58 | F05201 | non-negotiable | false | 10 |
| R10406 | PR 2 — LOC estimate ~900 | dump 58 | F05201 | non-negotiable | false | 10 |
| R10407 | PR 2 — depends on PR 1 merged | dump 60 | F05202 | non-negotiable | false | 10 |
| R10408 | PR 3 — title: docs: scaffold mdbook publishing pipeline and MCP config template | dump 66 | F05203 | non-negotiable | false | 10 |
| R10409 | PR 3 — scope: wire up documentation publishing + MCP template | dump 68 | F05203 | non-negotiable | false | 10 |
| R10410 | PR 3 — docs/src/SUMMARY.md seeded with charter + architecture + SDD index + decisions + handoff | dump 68 | F05203 | non-negotiable | false | 10 |
| R10411 | PR 3 — docs/src/ tree mirrors docs/sdd/ + docs/handoff/ + docs/review/ | dump 69 | F05204 | non-negotiable | false | 10 |
| R10412 | PR 3 — book.toml mirrors selfdef settings | dump 70 | F05205 | non-negotiable | false | 10 |
| R10413 | PR 3 — .github/workflows/mdbook-publish.yml (mirror selfdef pattern) | dump 71 | F05206 | non-negotiable | false | 10 |
| R10414 | PR 3 — .mcp/config.template.json (placeholders, not real config) | dump 72 | F05207 | non-negotiable | false | 10 |
| R10415 | PR 3 — docs/sdd/002-documentation-pipeline.md (~250 LOC) | dump 73 | F05208 | non-negotiable | false | 10 |
| R10416 | PR 3 — LOC estimate ~500 | dump 75 | F05209 | non-negotiable | false | 10 |
| R10417 | PR 3 — depends on PR 2 merged | dump 77 | F05210 | non-negotiable | false | 10 |
| R10418 | Stage Gate 1 — operator reviews PRs 1-3 holistically | dump 79 + 322 | F05211 | non-negotiable | false | 10 |
| R10419 | Stage Gate 1 — confirms structural foundation matches selfdef rhythm | dump 82 + 322 | F05212 | non-negotiable | false | 10 |
| R10420 | Stage Gate 1 — authorizes substantive-SDD phase to begin | dump 82 | F05213 | non-negotiable | false | 10 |
| R10421 | PR 4 — title: sdd: 003 substrate survey and image-build tooling selection | dump 100 | F05214 | non-negotiable | false | 10 |
| R10422 | PR 4 — scope: research-only SDD, no code | dump 102 | F05214 | non-negotiable | false | 10 |
| R10423 | PR 4 — candidates surveyed: live-build, mkosi, debootstrap, Lorax, Kiwi, ostree, Nix, Buildroot | dump 91 | F05215 | non-negotiable | false | 10 |
| R10424 | PR 4 — criteria matrix dimension: Debian-13 native support | dump 93 | F05216 | non-negotiable | false | 10 |
| R10425 | PR 4 — criteria matrix dimension: declarative-vs-imperative | dump 93 | F05216 | non-negotiable | false | 10 |
| R10426 | PR 4 — criteria matrix dimension: profile/variant pluralism | dump 93 | F05216 | non-negotiable | false | 10 |
| R10427 | PR 4 — criteria matrix dimension: whitelabel surface accessibility | dump 93 | F05216 | non-negotiable | false | 10 |
| R10428 | PR 4 — criteria matrix dimension: reproducibility | dump 93 | F05216 | non-negotiable | false | 10 |
| R10429 | PR 4 — criteria matrix dimension: CI testability without hardware | dump 93 | F05216 | non-negotiable | false | 10 |
| R10430 | PR 4 — criteria matrix dimension: ZFS-root support | dump 93 | F05216 | non-negotiable | false | 10 |
| R10431 | PR 4 — criteria matrix dimension: secure-boot support | dump 93 | F05216 | non-negotiable | false | 10 |
| R10432 | PR 4 — criteria matrix dimension: community + longevity | dump 94 | F05216 | non-negotiable | false | 10 |
| R10433 | PR 4 — criteria matrix dimension: operator-familiarity cost | dump 94 | F05216 | non-negotiable | false | 10 |
| R10434 | PR 4 — criteria matrix dimension: lifecycle-tool surface | dump 94 | F05216 | non-negotiable | false | 10 |
| R10435 | PR 4 — criteria matrix dimension: evolvability (swap substrates in 2 years?) | dump 94 | F05216 | non-negotiable | false | 10 |
| R10436 | PR 4 — per-candidate prose justification (not just scores) | dump 95 | F05217 | non-negotiable | false | 10 |
| R10437 | PR 4 — recommendation = single OR ranked A/B/C (operator chooses, not SDD) | dump 96 | F05218 | non-negotiable | false | 10 |
| R10438 | PR 4 — reversal cost section (evolvability principle) | dump 97 | F05219 | non-negotiable | false | 10 |
| R10439 | PR 4 — docs/decisions.md updated with substrate question elevated to pending operator review | dump 99 | F05214 | non-negotiable | false | 10 |
| R10440 | PR 4 — critical file docs/sdd/003-substrate-survey.md (~1200 LOC) | dump 101 | F05214 | non-negotiable | false | 10 |
| R10441 | PR 4 — LOC estimate ~1300 (heavy research doc) | dump 102 | F05220 | non-negotiable | false | 10 |
| R10442 | PR 4 — depends on PR 3 + parallel with PR 5/7 | dump 104 | F05221 | non-negotiable | false | 10 |
| R10443 | Stage Gate 2 — operator reviews PR 4 in isolation | dump 113 | F05222 | non-negotiable | false | 10 |
| R10444 | Stage Gate 2 — operator picks substrate or asks deeper dive on top 2 | dump 115 | F05222 | non-negotiable | false | 10 |
| R10445 | Stage Gate 2 — decision recorded in docs/decisions.md | dump 116 | F05223 | non-negotiable | false | 10 |
| R10446 | Stage Gate 2 — no code-bearing PR proceeds until substrate locked | dump 117 | F05224 | non-negotiable | false | 10 |
| R10447 | PR 5 — title: sdd: 004 profile schema design | dump 120 | F05225 | non-negotiable | false | 10 |
| R10448 | PR 5 — scope: schema-first profile definition (before any profile body exists) | dump 122 | F05225 | non-negotiable | false | 10 |
| R10449 | PR 5 — schema dimension: identity (name / id / version / parent / status) | dump 124 | F05226 | non-negotiable | false | 10 |
| R10450 | PR 5 — schema dimension: hardware target (CPU + features + GPU + memory + storage + network) | dump 125-126 | F05226 | non-negotiable | false | 10 |
| R10451 | PR 5 — schema dimension: kernel config (flavor / required / blacklisted / cmdline / microcode) | dump 127 | F05226 | non-negotiable | false | 10 |
| R10452 | PR 5 — schema dimension: package sets (layered base / role / profile + explicit deny lists) | dump 128 | F05226 | non-negotiable | false | 10 |
| R10453 | PR 5 — schema dimension: activation hooks (pre-install / during-install / first-boot / recurrent / decommission) | dump 129 | F05226 | non-negotiable | false | 10 |
| R10454 | PR 5 — schema dimension: lifecycle metadata (maintainer / evolution policy / substrate range) | dump 130 | F05226 | non-negotiable | false | 10 |
| R10455 | PR 5 — schema dimension: whitelabel binding (forward reference to PR 7) | dump 131 | F05226 | non-negotiable | false | 10 |
| R10456 | PR 5 — schema dimension: observability binding (telemetry tier / log retention / audit hooks) | dump 132 | F05226 | non-negotiable | false | 10 |
| R10457 | PR 5 — schemas/profile.schema.yaml (~250 LOC) | dump 137 | F05227 | non-negotiable | false | 10 |
| R10458 | PR 5 — trade-off: inheritance vs composition | dump 138 | F05228 | non-negotiable | false | 10 |
| R10459 | PR 5 — trade-off: rigid vs extensible schema | dump 138 | F05228 | non-negotiable | false | 10 |
| R10460 | PR 5 — trade-off: YAML vs TOML vs HCL | dump 138 | F05228 | non-negotiable | false | 10 |
| R10461 | PR 5 — LOC estimate ~1000 | dump 140 | F05229 | non-negotiable | false | 10 |
| R10462 | PR 5 — depends on PR 3 + parallel with PR 4/7 | dump 142 | F05230 | non-negotiable | false | 10 |
| R10463 | PR 6 — title: profiles: declare sain-01 and old-workstation as schema-conformant stubs | dump 144 | F05231 | non-negotiable | false | 10 |
| R10464 | PR 6 — scope: first two profile instances, schema-conformant, body placeholder | dump 146 | F05231 | non-negotiable | false | 10 |
| R10465 | PR 6 — profiles/sain-01.yaml hardware: Ryzen 9 9900X | dump 147 | F05231 | non-negotiable | false | 10 |
| R10466 | PR 6 — profiles/sain-01.yaml hardware: RTX PRO 6000 + RTX 3090 VFIO | dump 148 | F05231 | non-negotiable | false | 10 |
| R10467 | PR 6 — profiles/sain-01.yaml hardware: 256 GB DDR5 | dump 148 | F05231 | non-negotiable | false | 10 |
| R10468 | PR 6 — profiles/sain-01.yaml hardware: dual PCIe 5 NVMe ZFS RAID 0 | dump 148 | F05231 | non-negotiable | false | 10 |
| R10469 | PR 6 — profiles/sain-01.yaml hardware: Marvell 10GbE + Intel 2.5GbE | dump 149 | F05231 | non-negotiable | false | 10 |
| R10470 | PR 6 — profiles/sain-01.yaml hardware: ASUS ProArt X870E-Creator | dump 149 | F05231 | non-negotiable | false | 10 |
| R10471 | PR 6 — profiles/old-workstation.yaml hardware: 11 GB RAM + 8 GB GPU | dump 150 | F05232 | non-negotiable | false | 10 |
| R10472 | PR 6 — profiles/INDEX.md catalog of declared profiles with status | dump 151 | F05233 | non-negotiable | false | 10 |
| R10473 | PR 6 — docs/sdd/005-initial-profiles.md justifies seed set | dump 152 | F05234 | non-negotiable | false | 10 |
| R10474 | PR 6 — docs/sdd/005 reserves minimal/developer/headless for future PRs | dump 152 | F05234 | non-negotiable | false | 10 |
| R10475 | PR 6 — scripts/validate-profiles.sh lints profiles against schema | dump 153 | F05235 | non-negotiable | false | 10 |
| R10476 | PR 6 — scripts/validate-profiles.sh is first test-bearing artifact | dump 153 | F05235 | non-negotiable | false | 10 |
| R10477 | PR 6 — LOC estimate ~700 | dump 158 | F05236 | non-negotiable | false | 10 |
| R10478 | PR 6 — depends on PR 5 merged | dump 160 | F05237 | non-negotiable | false | 10 |
| R10479 | Stage Gate 3 — operator reviews schema + 2 instances together | dump 167 | F05238 | non-negotiable | false | 10 |
| R10480 | Stage Gate 3 — schema may be revised once instances reveal gaps | dump 167 | F05238 | non-negotiable | false | 10 |
| R10481 | Stage Gate 3 — schema locked thereafter | dump 168 | F05238 | non-negotiable | false | 10 |
| R10482 | PR 7 — title: sdd: 006 debian surface audit and whitelabel target inventory | dump 171 | F05239 | non-negotiable | false | 10 |
| R10483 | PR 7 — scope: survey/audit only, identifies every place "Debian" surfaces, no rebranding mechanism | dump 173 | F05239 | non-negotiable | false | 10 |
| R10484 | PR 7 — filesystem surfaces (/etc/issue / /etc/issue.net / /etc/os-release / /etc/lsb-release / /etc/debian_version / /etc/motd / /usr/lib/os-release) | dump 176 | F05240 | non-negotiable | false | 10 |
| R10485 | PR 7 — package-manager surfaces (DPKG vendor + APT sources + dpkg-vendor + lsb_release) | dump 177 | F05241 | non-negotiable | false | 10 |
| R10486 | PR 7 — boot surfaces (GRUB theme + menu + Plymouth + kernel boot logo + systemd boot banner) | dump 180 | F05242 | non-negotiable | false | 10 |
| R10487 | PR 7 — installer surfaces (debian-installer + Calamares + preseed banner) | dump 181 | F05243 | non-negotiable | false | 10 |
| R10488 | PR 7 — desktop surfaces (GDM/SDDM/LightDM + wallpaper + about-system) | dump 182 | F05244 | non-negotiable | false | 10 |
| R10489 | PR 7 — kernel surfaces (/proc/version + uname-a + kernel package naming) | dump 183 | F05245 | non-negotiable | false | 10 |
| R10490 | PR 7 — documentation + network + telemetry surfaces inventoried | dump 184-186 | F05246 | non-negotiable | false | 10 |
| R10491 | PR 7 — categorization: must-rebrand / should-rebrand / may-leave / must-not-touch | dump 187 | F05247 | non-negotiable | false | 10 |
| R10492 | PR 7 — legal-obligation section (Debian trademark + DFSG + GPL attribution) | dump 188 | F05248 | non-negotiable | false | 10 |
| R10493 | PR 7 — citation-grade legal section | dump 188 | F05248 | non-negotiable | false | 10 |
| R10494 | PR 7 — critical file docs/sdd/006-debian-surface-audit.md (~900 LOC) | dump 190 | F05239 | non-negotiable | false | 10 |
| R10495 | PR 7 — LOC estimate ~950 | dump 191 | F05249 | non-negotiable | false | 10 |
| R10496 | PR 7 — depends on PR 3 + parallel with PR 4/5 | dump 193 | F05250 | non-negotiable | false | 10 |
| R10497 | PR 8 — title: sdd: 007 whitelabel mechanism specification | dump 200 | F05251 | non-negotiable | false | 10 |
| R10498 | PR 8 — scope: how rebranding is applied — declaratively, per-profile, evolvable | dump 202 | F05251 | non-negotiable | false | 10 |
| R10499 | PR 8 — mechanism shape: declarative whitelabel-profile YAML + rendering engine | dump 203 | F05252 | non-negotiable | false | 10 |
| R10500 | PR 8 — per-surface strategy: template-substitution / file-overlay / package-replacement / build-time-flag | dump 204 | F05253 | non-negotiable | false | 10 |
| R10501 | PR 8 — pre/during/post split: pre-build patches / install-time substitutions / first-boot scripts | dump 205 | F05254 | non-negotiable | false | 10 |
| R10502 | PR 8 — evolvability: whitelabel swap without full image rebuild (where possible) | dump 206 | F05255 | non-negotiable | false | 10 |
| R10503 | PR 8 — legal compliance binding: enforce PR 7 must-not-touch list at validation time | dump 207 | F05256 | non-negotiable | false | 10 |
| R10504 | PR 8 — schemas/whitelabel.schema.yaml (~200 LOC) | dump 208 | F05257 | non-negotiable | false | 10 |
| R10505 | PR 8 — whitelabel/default.yaml placeholder (no brand committed yet) | dump 209 | F05258 | non-negotiable | false | 10 |
| R10506 | PR 8 — whitelabel/INDEX.md | dump 210 | F05257 | non-negotiable | false | 10 |
| R10507 | PR 8 — critical files: 007.md (~600 LOC) + schema (~200 LOC) | dump 212 | F05251 | non-negotiable | false | 10 |
| R10508 | PR 8 — LOC estimate ~900 | dump 213 | F05259 | non-negotiable | false | 10 |
| R10509 | PR 8 — depends on PR 7 (substrate decision helpful but not strictly blocking) | dump 215 | F05251 | non-negotiable | false | 10 |
| R10510 | Stage Gate 4 — operator reviews whitelabel audit + mechanism together | dump 217 | F05260 | non-negotiable | false | 10 |
| R10511 | Stage Gate 4 — confirms legal posture | dump 217 | F05260 | non-negotiable | false | 10 |
| R10512 | Stage Gate 4 — optionally supplies actual brand identity (name, palette, logo) or defers | dump 218 | F05260 | non-negotiable | false | 10 |
| R10513 | PR 9 — title: sdd: 008 test harness specification for hardware-free validation | dump 221 | F05261 | non-negotiable | false | 10 |
| R10514 | PR 9 — test layer 1: schema/lint (profile + whitelabel YAML against schemas, pure CI) | dump 224 | F05262 | non-negotiable | false | 10 |
| R10515 | PR 9 — test layer 2: unit (mocked filesystem / apt / dpkg) | dump 225 | F05262 | non-negotiable | false | 10 |
| R10516 | PR 9 — test layer 3: stage acceptance (each lifecycle stage in controlled env) | dump 226 | F05262 | non-negotiable | false | 10 |
| R10517 | PR 9 — test layer 4: integration (full image built + booted in QEMU + smoke tests) | dump 227 | F05262 | non-negotiable | false | 10 |
| R10518 | PR 9 — test layer 5: hardware-conformance (gated; SAIN-01 hardware when procured) | dump 228 | F05262 | non-negotiable | false | 10 |
| R10519 | PR 9 — virtualization stack: chroot (package-level assertions) | dump 230 | F05263 | non-negotiable | false | 10 |
| R10520 | PR 9 — virtualization stack: systemd-nspawn (service-startup assertions) | dump 231 | F05263 | non-negotiable | false | 10 |
| R10521 | PR 9 — virtualization stack: QEMU system (boot + initramfs + GRUB + UEFI + secure-boot + VFIO emulation) | dump 232 | F05263 | non-negotiable | false | 10 |
| R10522 | PR 9 — virtualization stack: qemu-user (cross-arch validation) | dump 233 | F05263 | non-negotiable | false | 10 |
| R10523 | PR 9 — invariants per stage (hostname / whitelabel surfaces / ZFS pool / systemd units) | dump 234 | F05264 | non-negotiable | false | 10 |
| R10524 | PR 9 — test discovery + naming convention + CI execution model + flake policy | dump 235 | F05265 | non-negotiable | false | 10 |
| R10525 | PR 9 — LOC estimate ~850 | dump 250 | F05261 | non-negotiable | false | 10 |
| R10526 | PR 9 — depends on PR 4 + PR 6 + PR 8 | dump 252-254 | F05266 | non-negotiable | false | 10 |
| R10527 | PR 10 — title: test: scaffold test harness and land first lifecycle-invariant tests | dump 259 | F05267 | non-negotiable | false | 10 |
| R10528 | PR 10 — tests/schema/ wired into CI | dump 263 | F05267 | non-negotiable | false | 10 |
| R10529 | PR 10 — tests/lint/ markdown + decisions-log + SDD index consistency | dump 264 | F05267 | non-negotiable | false | 10 |
| R10530 | PR 10 — tests/chroot/scaffold.sh substrate-aware | dump 265 | F05267 | non-negotiable | false | 10 |
| R10531 | PR 10 — tests/nspawn/scaffold.sh | dump 266 | F05267 | non-negotiable | false | 10 |
| R10532 | PR 10 — tests/qemu/scaffold.sh with stubbed boot test | dump 267 | F05267 | non-negotiable | false | 10 |
| R10533 | PR 10 — .github/workflows/test.yml CI workflow | dump 269 | F05268 | non-negotiable | false | 10 |
| R10534 | PR 10 — docs/sdd/009-test-harness-bootstrap.md documents what scaffold delivers + does not | dump 270 | F05269 | non-negotiable | false | 10 |
| R10535 | PR 10 — docs/sdd/010-stage-2-stub.md placeholder for Stage 2 (mirrors selfdef pattern) | dump 271 | F05269 | non-negotiable | false | 10 |
| R10536 | PR 10 — LOC estimate ~1200 | dump 274 | F05267 | non-negotiable | false | 10 |
| R10537 | PR 10 — depends on PR 9 merged | dump 277 | F05267 | non-negotiable | false | 10 |
| R10538 | Stage Gate 5 — foundation-complete gate; operator reviews full 10-PR arc holistically | dump 281 | F05270 | non-negotiable | false | 10 |
| R10539 | Stage Gate 5 — authorizes Stage 2 (first actual build scripts) | dump 282 | F05270 | non-negotiable | false | 10 |
| R10540 | Closing — every R-row carries 10 hard non-negotiable sub-requirements | operator standing direction | F05186 | non-negotiable | false | 10 |

## Sub-requirements accounting

Every R-row carries 10 hard non-negotiable sub-requirements per operator standing direction. Total enforced sub-reqs = 170 R × 10 = **1,700 sub-requirements** for M062.

## Cross-references

- **All M001..M061** — this macro-arc is the IMPLEMENTATION ROADMAP for the catalog (the 104 milestones describe the destination; the 10-PR scaffold + Stage 2..N work below is the path)
- **M063** — SFIF discipline (Scaffold → Foundation → Infrastructure → Features) categorizes the 10-PR scaffold + Stage 2+ work
- **M064** — "Debian as Ark" framing + Q-016 distro-base reconsideration (informs PR 4)
- **M065** — Five Stage Gates SG1-SG5 (operationalizes the gates above)
- **info-hub** — 11 epics E100-E110 cited as architectural baseline (read-only)
- **selfdef** — workflow conventions mirrored exactly (SDD numbering, decisions log, audit phase, mdbook, MCP)

## Schema

```
schema_version: "1.0.0"
milestone_id: M062
parent: sovereign-os
epics: 10
modules: 17
features: 85
requirements: 170
sub_requirements_per_requirement: 10
total_sub_requirements: 1700
source_dump: 2026-05-16-sovereign-os-macro-arc-plan.md
prs_total: 10
stage_gates: 5
stage_gate_placement:
  SG1: after PR 3 (structural foundation review)
  SG2: after PR 4 (substrate decision)
  SG3: after PR 6 (schema lock-in)
  SG4: after PR 8 (whitelabel mechanism + legal posture)
  SG5: after PR 10 (foundation-complete; authorizes Stage 2)
```
