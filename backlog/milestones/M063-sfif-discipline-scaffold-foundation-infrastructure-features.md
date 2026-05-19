# M063 — SFIF discipline — Scaffold → Foundation → Infrastructure → Features

**Parent**: sovereign-os runtime — foundation governance layer
**Source**: `~/infohub/raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md` lines 389-396 (Post-Plan Operator Refinements: "SFIF discipline" + "IaC quality bar" + "Debian as Ark" + Q-016)
**Operator standing direction** (verbatim, 2026-05-19): *"following the proper workflow and respect of SFIF and second-brain knowledge"* — SFIF named explicitly in /goal as required discipline.

## Doctrinal anchor

> "**SFIF discipline**: the arc itself follows Scaffold → Foundation → Infrastructure → Features. PRs 1-3 = Scaffold; PRs 4-8 = Foundation; PRs 9-10 begin Infrastructure; Stage 2 onwards delivers Infrastructure + Features." (dump 390-391)

> "**IaC quality bar**: every PR must deliver high-quality scripts + libs + configuration + easily tweakable + customisable + env-var-driven + restart-from-state. Build pipeline is resumable + observable, not one-shot." (dump 392-393)

## Epics (E0608-E0617)

| epic | name | source |
|---|---|---|
| E0608 | SFIF Phase 1 — Scaffold (PRs 1-3): repo genesis / architecture / docs pipeline | dump 390-391 + M062 PRs 1-3 |
| E0609 | SFIF Phase 2 — Foundation (PRs 4-8): substrate / profile schema / instances / whitelabel audit / whitelabel mechanism | dump 390-391 + M062 PRs 4-8 |
| E0610 | SFIF Phase 3 — Infrastructure begins (PRs 9-10): TDD harness spec + scaffold | dump 390-391 + M062 PRs 9-10 |
| E0611 | SFIF Phase 4 — Infrastructure continues (Stage 2+ PRs): build scripts / image generation / first installable artifact | dump 390-391 + M062 Stage 2 stub |
| E0612 | SFIF Phase 5 — Features (Stage 3+ PRs): actual OS features layer on infrastructure | dump 390-391 (implied) |
| E0613 | IaC Quality Bar — every PR meets: scripts + libs + config + tweakable + customisable + env-var-driven + restart-from-state | dump 392-393 |
| E0614 | IaC Quality Bar — build pipeline resumable + observable, not one-shot | dump 393 |
| E0615 | SFIF transition gates — phase-to-phase transitions are operator-acknowledged | dump 390-391 + operator standing direction |
| E0616 | SFIF cross-repo applicability — discipline applies to selfdef + sovereign-os + info-hub (per "second-brain knowledge") | operator standing direction 2026-05-19 |
| E0617 | SFIF audit trail — every PR labeled with SFIF phase + IaC quality bar checklist passed | architecture + operator standing direction |

## Modules (M01054-M01070)

| module | name | source |
|---|---|---|
| M01054 | sovereign-sfif-phase-1-scaffold | dump 390-391 |
| M01055 | sovereign-sfif-phase-2-foundation | dump 390-391 |
| M01056 | sovereign-sfif-phase-3-infrastructure-begin | dump 390-391 |
| M01057 | sovereign-sfif-phase-4-infrastructure-continue | dump 390-391 |
| M01058 | sovereign-sfif-phase-5-features | dump 390-391 |
| M01059 | sovereign-sfif-phase-transition-coordinator | dump 390-391 + operator standing direction |
| M01060 | sovereign-iac-quality-bar-validator | dump 392-393 |
| M01061 | sovereign-iac-quality-bar-scripts-checker | dump 392 |
| M01062 | sovereign-iac-quality-bar-libs-checker | dump 392 |
| M01063 | sovereign-iac-quality-bar-config-checker | dump 392 |
| M01064 | sovereign-iac-quality-bar-tweakable-checker | dump 392 |
| M01065 | sovereign-iac-quality-bar-env-var-checker | dump 392 |
| M01066 | sovereign-iac-quality-bar-restart-from-state-checker | dump 392 |
| M01067 | sovereign-iac-pipeline-resumability-checker | dump 393 |
| M01068 | sovereign-iac-pipeline-observability-checker | dump 393 |
| M01069 | sovereign-sfif-cross-repo-projector | operator standing direction |
| M01070 | sovereign-sfif-audit-trail-emitter | cross-ref M049 + cross-ref selfdef MS026 |

## Features (F05271-F05355)

| feature | name | source |
|---|---|---|
| F05271 | Scaffold = empty-repo skeleton + charter + docs index + decisions log | M062 PRs 1-3 |
| F05272 | Scaffold = no build code, no scripts (pure structural seed) | M062 PR 1 dump 24 |
| F05273 | Scaffold = mirror selfdef workflow conventions exactly | M062 dump 9 |
| F05274 | Foundation = substrate decision via research-only SDD | M062 PR 4 dump 84 |
| F05275 | Foundation = schema-first profile definition before any profile body | M062 PR 5 dump 122 |
| F05276 | Foundation = first two profile instances (sain-01 + old-workstation) | M062 PR 6 dump 144 |
| F05277 | Foundation = whitelabel audit (every "Debian" surface inventoried) | M062 PR 7 dump 173 |
| F05278 | Foundation = whitelabel mechanism (declarative, per-profile, evolvable) | M062 PR 8 dump 202 |
| F05279 | Foundation = ends at Stage Gate 4 (legal posture confirmed) | M062 dump 217-218 |
| F05280 | Infrastructure begin = TDD harness specification | M062 PR 9 dump 221 |
| F05281 | Infrastructure begin = TDD harness scaffold + first passing tests | M062 PR 10 dump 259 |
| F05282 | Infrastructure begin = Stage Gate 5 (foundation-complete; Stage 2 authorized) | M062 dump 281-282 |
| F05283 | Infrastructure continue = Stage 2+ PRs deliver actual build scripts | M062 dump 281 (implied) |
| F05284 | Infrastructure continue = image generation pipeline (substrate-tooling-driven) | M062 PR 4 substrate decision |
| F05285 | Infrastructure continue = first installable artifact | architecture + dump 391 |
| F05286 | Infrastructure continue = CI-runnable end-to-end build | architecture |
| F05287 | Features = OS features layer ON TOP OF infrastructure | dump 391 (implied) |
| F05288 | Features = sovereign-os specific behaviors (cockpit / gateway / memory OS / etc) | cross-ref M048 (modules map) |
| F05289 | Features = brand identity committed (whitelabel materialized) | M062 dump 218 (Stage Gate 4 optional) |
| F05290 | Features = first SAIN-01 hardware deployment readiness | operator standing direction + M062 |
| F05291 | IaC quality bar — scripts: every PR ships executable scripts | dump 392 |
| F05292 | IaC quality bar — libs: shared libraries with reusable interfaces | dump 392 |
| F05293 | IaC quality bar — configuration: declarative config files (YAML / TOML) | dump 392 |
| F05294 | IaC quality bar — easily tweakable: configs follow predictable shape | dump 392 |
| F05295 | IaC quality bar — customisable: configs support per-profile overrides | dump 392 |
| F05296 | IaC quality bar — env-var-driven: all configurable values exposed as env-vars OR config keys | dump 392 |
| F05297 | IaC quality bar — restart-from-state: scripts resume from checkpoint, never one-shot-only | dump 392 |
| F05298 | IaC pipeline resumable — partial failure does not require full re-run | dump 393 |
| F05299 | IaC pipeline observable — every step emits M049 trace + OCSF event | dump 393 + cross-ref M049 + cross-ref selfdef MS026 |
| F05300 | IaC pipeline observable — operator dashboard surfaces pipeline progress | cross-ref M060 |
| F05301 | IaC quality bar validator — runs at every PR via CI | architecture |
| F05302 | IaC quality bar validator — failures block merge | architecture |
| F05303 | IaC quality bar validator — emits OCSF Configuration Change class 5001 on PR landing | cross-ref selfdef MS026 |
| F05304 | IaC quality bar validator — emits M049 trace per check | cross-ref M049 |
| F05305 | IaC quality bar validator — produces compliance report (passed/failed checklist) | architecture |
| F05306 | SFIF phase transition — Scaffold → Foundation requires Stage Gate 1 sign-off | M062 dump 79-82 |
| F05307 | SFIF phase transition — Foundation → Infrastructure begin requires Stage Gate 4 sign-off | M062 dump 217-218 |
| F05308 | SFIF phase transition — Infrastructure begin → Infrastructure continue requires Stage Gate 5 sign-off | M062 dump 281-282 |
| F05309 | SFIF phase transition — Infrastructure → Features requires operator-defined acceptance criteria | operator standing direction |
| F05310 | SFIF phase transition — every transition emits OCSF Configuration Change class 5001 | cross-ref selfdef MS026 |
| F05311 | SFIF phase transition — every transition signed via MS003 | cross-ref selfdef MS003 |
| F05312 | SFIF phase transition — every transition recorded in docs/decisions.md | M062 dump 28-30 + architecture |
| F05313 | SFIF cross-repo — selfdef catalog phases map to S+F+I+F: SS010-SS022 Scaffold, MS023-MS033 Foundation, MS034-MS043 Infrastructure begin | architecture + operator standing direction |
| F05314 | SFIF cross-repo — sovereign-os M001-M061 catalog phase = Scaffold (catalog written, code not yet) | architecture + operator standing direction |
| F05315 | SFIF cross-repo — info-hub follows SFIF as knowledge-layer projection (read-only from runtime+IPS) | operator standing direction "second-brain knowledge" |
| F05316 | SFIF cross-repo — sovereign-os M062 (this milestone's parent) defines the 10-PR Scaffold+Foundation+Infrastructure scope | cross-ref M062 |
| F05317 | SFIF audit trail — every PR labeled with SFIF phase tag | architecture |
| F05318 | SFIF audit trail — PR label format `sfif:scaffold` `sfif:foundation` `sfif:infra-begin` `sfif:infra-continue` `sfif:features` | architecture |
| F05319 | SFIF audit trail — IaC quality bar checklist published as PR-comment | architecture |
| F05320 | SFIF audit trail — checklist signed via MS003 by CI runner | cross-ref selfdef MS003 |
| F05321 | SFIF audit trail — checklist retained 365 days on main branch | cross-ref selfdef MS037 + architecture |
| F05322 | SFIF audit trail — annual SFIF retrospective documented at docs/sdd/SFIF-retrospective-YYYY.md | architecture |
| F05323 | IaC quality bar item — script: #!/usr/bin/env bash + set -euo pipefail header | architecture |
| F05324 | IaC quality bar item — script: trap-based error handling | architecture |
| F05325 | IaC quality bar item — script: rollback function defined where mutation occurs | cross-ref selfdef MS041 |
| F05326 | IaC quality bar item — script: idempotent (re-run safely repeats with no-op on prior success) | dump 392 |
| F05327 | IaC quality bar item — lib: documented public interface | architecture |
| F05328 | IaC quality bar item — lib: unit-tested under L1 schema/lint layer (M062 PR 10) | M062 dump 263 |
| F05329 | IaC quality bar item — config: schema-validated | M062 PR 5 + dump 392 |
| F05330 | IaC quality bar item — config: per-profile overlay via inheritance OR composition | M062 dump 138 |
| F05331 | IaC quality bar item — config: env-var fallback for every value | dump 392 |
| F05332 | IaC quality bar item — config: documented at docs/sdd/<N>-<topic>.md | architecture |
| F05333 | IaC quality bar item — env-var: namespace prefix per project (SOVEREIGN_OS_, SELFDEF_, INFOHUB_) | architecture |
| F05334 | IaC quality bar item — env-var: precedence documented (env > config > default) | architecture |
| F05335 | IaC quality bar item — restart-from-state: checkpoint file at /var/lib/<project>/state.json | architecture |
| F05336 | IaC quality bar item — restart-from-state: signed via MS003 | cross-ref selfdef MS003 |
| F05337 | IaC pipeline resumable — checkpoint per major step | dump 393 |
| F05338 | IaC pipeline resumable — `--resume <checkpoint-id>` flag on every long-running script | architecture |
| F05339 | IaC pipeline resumable — checkpoint includes timestamp + step ID + state digest | architecture + cross-ref MS003 |
| F05340 | IaC pipeline observable — progress bar OR percent for operator visibility | architecture + cross-ref M060 |
| F05341 | IaC pipeline observable — ETA estimated from prior runs | architecture |
| F05342 | IaC pipeline observable — log file at /var/log/<project>/<pipeline-id>.log | architecture |
| F05343 | IaC pipeline observable — log file emits OCSF System Activity class 1001 entries | cross-ref selfdef MS026 |
| F05344 | IaC pipeline observable — cancel via SIGTERM cleanly stops + writes resumable checkpoint | architecture |
| F05345 | SFIF transition trace — emits M049 13-field span | cross-ref M049 |
| F05346 | SFIF transition trace — span includes from-phase + to-phase | cross-ref M049 |
| F05347 | SFIF transition trace — span includes operator approval signature | cross-ref selfdef MS003 |
| F05348 | SFIF transition replay validator — verifies phase-history chain integrity | cross-ref selfdef MS009 |
| F05349 | SFIF transition replay validator — detects unauthorized phase escalations | cross-ref selfdef MS009 + MS003 |
| F05350 | SFIF transition replay validator — emits OCSF Detection Finding class 2004 on chain break | cross-ref selfdef MS026 |
| F05351 | SFIF observability surface — M060 D-00 main dashboard shows current SFIF phase | cross-ref M060 |
| F05352 | SFIF observability surface — D-00 main dashboard surfaces IaC quality bar pass-rate trend | cross-ref M060 |
| F05353 | SFIF doctrinal preservation — operator words "SFIF discipline" verbatim in M063 doc | operator standing direction |
| F05354 | SFIF doctrinal preservation — operator words "respect of SFIF and second-brain knowledge" verbatim | operator standing direction 2026-05-19 |
| F05355 | SFIF closing — discipline applies across all 3 repos (sovereign-os + selfdef + info-hub) | operator standing direction |

## Requirements (R10541-R10710)

| req | description | source | feature | priority | exception | sub-reqs |
|---|---|---|---|---|---|---|
| R10541 | Doctrinal — "SFIF discipline" (verbatim, operator standing direction 2026-05-16 and re-issued 2026-05-19) | dump 390 + operator standing direction | F05353 | non-negotiable | false | 10 |
| R10542 | Doctrinal — SFIF = Scaffold → Foundation → Infrastructure → Features | dump 390 | F05271 | non-negotiable | false | 10 |
| R10543 | Doctrinal — PRs 1-3 = Scaffold phase | dump 391 | F05271 | non-negotiable | false | 10 |
| R10544 | Doctrinal — PRs 4-8 = Foundation phase | dump 391 | F05274 | non-negotiable | false | 10 |
| R10545 | Doctrinal — PRs 9-10 begin Infrastructure phase | dump 391 | F05280 | non-negotiable | false | 10 |
| R10546 | Doctrinal — Stage 2 onwards delivers Infrastructure + Features | dump 391 | F05283 | non-negotiable | false | 10 |
| R10547 | Doctrinal — "respect of SFIF and second-brain knowledge" (operator standing /goal verbatim 2026-05-19) | operator standing direction | F05354 | non-negotiable | false | 10 |
| R10548 | Doctrinal — IaC quality bar verbatim: "high-quality scripts + libs + configuration + easily tweakable + customisable + env-var-driven + restart-from-state" | dump 392 | F05291 | non-negotiable | false | 10 |
| R10549 | Doctrinal — IaC pipeline verbatim: "resumable + observable, not one-shot" | dump 393 | F05298 | non-negotiable | false | 10 |
| R10550 | Scaffold — empty-repo skeleton + charter + docs index + decisions log | M062 PRs 1-3 | F05271 | non-negotiable | false | 10 |
| R10551 | Scaffold — no build code, no scripts (pure structural seed) | M062 PR 1 | F05272 | non-negotiable | false | 10 |
| R10552 | Scaffold — mirror selfdef workflow conventions exactly | M062 dump 9 | F05273 | non-negotiable | false | 10 |
| R10553 | Scaffold — ends at Stage Gate 1 (structural foundation review) | M062 dump 79-82 | F05306 | non-negotiable | false | 10 |
| R10554 | Foundation — substrate decision via research-only SDD (PR 4) | M062 PR 4 | F05274 | non-negotiable | false | 10 |
| R10555 | Foundation — schema-first profile definition before any profile body (PR 5) | M062 PR 5 | F05275 | non-negotiable | false | 10 |
| R10556 | Foundation — first two profile instances (sain-01 + old-workstation) (PR 6) | M062 PR 6 | F05276 | non-negotiable | false | 10 |
| R10557 | Foundation — whitelabel audit (every Debian surface inventoried) (PR 7) | M062 PR 7 | F05277 | non-negotiable | false | 10 |
| R10558 | Foundation — whitelabel mechanism (declarative, per-profile, evolvable) (PR 8) | M062 PR 8 | F05278 | non-negotiable | false | 10 |
| R10559 | Foundation — ends at Stage Gate 4 (legal posture confirmed) | M062 dump 217-218 | F05279 | non-negotiable | false | 10 |
| R10560 | Infrastructure begin — TDD harness specification (PR 9) | M062 PR 9 | F05280 | non-negotiable | false | 10 |
| R10561 | Infrastructure begin — TDD harness scaffold + first passing tests (PR 10) | M062 PR 10 | F05281 | non-negotiable | false | 10 |
| R10562 | Infrastructure begin — ends at Stage Gate 5 (foundation-complete; Stage 2 authorized) | M062 dump 281-282 | F05282 | non-negotiable | false | 10 |
| R10563 | Infrastructure continue — Stage 2+ PRs deliver actual build scripts | M062 dump 281 | F05283 | non-negotiable | false | 10 |
| R10564 | Infrastructure continue — image generation pipeline (substrate-tooling-driven) | M062 PR 4 substrate decision | F05284 | non-negotiable | false | 10 |
| R10565 | Infrastructure continue — first installable artifact | architecture + dump 391 | F05285 | non-negotiable | false | 10 |
| R10566 | Infrastructure continue — CI-runnable end-to-end build | architecture | F05286 | non-negotiable | false | 10 |
| R10567 | Features — OS features layer ON TOP OF infrastructure | dump 391 (implied) | F05287 | non-negotiable | false | 10 |
| R10568 | Features — sovereign-os specific behaviors (cockpit / gateway / memory OS / etc) | cross-ref M048 | F05288 | non-negotiable | false | 10 |
| R10569 | Features — brand identity committed (whitelabel materialized) | M062 dump 218 | F05289 | non-negotiable | false | 10 |
| R10570 | Features — first SAIN-01 hardware deployment readiness | operator standing direction + M062 | F05290 | non-negotiable | false | 10 |
| R10571 | IaC quality bar — every PR ships executable scripts | dump 392 | F05291 | non-negotiable | false | 10 |
| R10572 | IaC quality bar — shared libraries with reusable interfaces | dump 392 | F05292 | non-negotiable | false | 10 |
| R10573 | IaC quality bar — declarative config files (YAML / TOML) | dump 392 | F05293 | non-negotiable | false | 10 |
| R10574 | IaC quality bar — configs follow predictable shape (easily tweakable) | dump 392 | F05294 | non-negotiable | false | 10 |
| R10575 | IaC quality bar — configs support per-profile overrides (customisable) | dump 392 | F05295 | non-negotiable | false | 10 |
| R10576 | IaC quality bar — all configurable values exposed as env-vars OR config keys | dump 392 | F05296 | non-negotiable | false | 10 |
| R10577 | IaC quality bar — scripts resume from checkpoint, never one-shot-only | dump 392 | F05297 | non-negotiable | false | 10 |
| R10578 | IaC pipeline — partial failure does not require full re-run (resumable) | dump 393 | F05298 | non-negotiable | false | 10 |
| R10579 | IaC pipeline — every step emits M049 trace | dump 393 + cross-ref M049 | F05299 | non-negotiable | false | 10 |
| R10580 | IaC pipeline — every step emits OCSF event | dump 393 + cross-ref selfdef MS026 | F05299 | non-negotiable | false | 10 |
| R10581 | IaC pipeline — operator dashboard surfaces pipeline progress (M060 D-00) | cross-ref M060 | F05300 | non-negotiable | false | 10 |
| R10582 | IaC quality bar validator — runs at every PR via CI | architecture | F05301 | non-negotiable | false | 10 |
| R10583 | IaC quality bar validator — failures block merge | architecture | F05302 | non-negotiable | false | 10 |
| R10584 | IaC quality bar validator — emits OCSF Configuration Change class 5001 on PR landing | cross-ref selfdef MS026 | F05303 | non-negotiable | false | 10 |
| R10585 | IaC quality bar validator — emits M049 trace per check | cross-ref M049 | F05304 | non-negotiable | false | 10 |
| R10586 | IaC quality bar validator — produces compliance report (passed/failed checklist) | architecture | F05305 | non-negotiable | false | 10 |
| R10587 | SFIF transition — Scaffold → Foundation requires Stage Gate 1 sign-off | M062 dump 79-82 | F05306 | non-negotiable | false | 10 |
| R10588 | SFIF transition — Foundation → Infrastructure begin requires Stage Gate 4 sign-off | M062 dump 217-218 | F05307 | non-negotiable | false | 10 |
| R10589 | SFIF transition — Infrastructure begin → Infrastructure continue requires Stage Gate 5 sign-off | M062 dump 281-282 | F05308 | non-negotiable | false | 10 |
| R10590 | SFIF transition — Infrastructure → Features requires operator-defined acceptance criteria | operator standing direction | F05309 | non-negotiable | false | 10 |
| R10591 | SFIF transition — every transition emits OCSF Configuration Change class 5001 | cross-ref selfdef MS026 | F05310 | non-negotiable | false | 10 |
| R10592 | SFIF transition — every transition signed via MS003 | cross-ref selfdef MS003 | F05311 | non-negotiable | false | 10 |
| R10593 | SFIF transition — every transition recorded in docs/decisions.md | M062 dump 28-30 | F05312 | non-negotiable | false | 10 |
| R10594 | SFIF cross-repo — selfdef catalog phases map to S+F+I+F (MS010-22 Scaffold / MS023-33 Foundation / MS034-43 Infrastructure begin) | architecture | F05313 | non-negotiable | false | 10 |
| R10595 | SFIF cross-repo — sovereign-os M001-M061 catalog phase = Scaffold (catalog written, code not yet) | architecture | F05314 | non-negotiable | false | 10 |
| R10596 | SFIF cross-repo — info-hub follows SFIF as knowledge-layer projection (read-only from runtime+IPS) | operator standing direction | F05315 | non-negotiable | false | 10 |
| R10597 | SFIF cross-repo — M062 (this milestone's parent) defines 10-PR Scaffold+Foundation+Infrastructure scope | cross-ref M062 | F05316 | non-negotiable | false | 10 |
| R10598 | SFIF audit trail — every PR labeled with SFIF phase tag | architecture | F05317 | non-negotiable | false | 10 |
| R10599 | SFIF audit trail — PR label format `sfif:<phase>` | architecture | F05318 | non-negotiable | false | 10 |
| R10600 | SFIF audit trail — IaC quality bar checklist published as PR-comment | architecture | F05319 | non-negotiable | false | 10 |
| R10601 | SFIF audit trail — checklist signed via MS003 by CI runner | cross-ref selfdef MS003 | F05320 | non-negotiable | false | 10 |
| R10602 | SFIF audit trail — checklist retained 365 days on main branch | cross-ref selfdef MS037 | F05321 | non-negotiable | false | 10 |
| R10603 | SFIF audit trail — annual retrospective at docs/sdd/SFIF-retrospective-YYYY.md | architecture | F05322 | non-negotiable | false | 10 |
| R10604 | IaC script — #!/usr/bin/env bash + set -euo pipefail header | architecture | F05323 | non-negotiable | false | 10 |
| R10605 | IaC script — trap-based error handling | architecture | F05324 | non-negotiable | false | 10 |
| R10606 | IaC script — rollback function defined where mutation occurs | cross-ref selfdef MS041 | F05325 | non-negotiable | false | 10 |
| R10607 | IaC script — idempotent (re-run safely repeats with no-op on prior success) | dump 392 | F05326 | non-negotiable | false | 10 |
| R10608 | IaC lib — documented public interface | architecture | F05327 | non-negotiable | false | 10 |
| R10609 | IaC lib — unit-tested under L1 schema/lint layer | M062 dump 263 | F05328 | non-negotiable | false | 10 |
| R10610 | IaC config — schema-validated | M062 PR 5 + dump 392 | F05329 | non-negotiable | false | 10 |
| R10611 | IaC config — per-profile overlay via inheritance OR composition | M062 dump 138 | F05330 | non-negotiable | false | 10 |
| R10612 | IaC config — env-var fallback for every value | dump 392 | F05331 | non-negotiable | false | 10 |
| R10613 | IaC config — documented at docs/sdd/<N>-<topic>.md | architecture | F05332 | non-negotiable | false | 10 |
| R10614 | IaC env-var — namespace prefix per project (SOVEREIGN_OS_ / SELFDEF_ / INFOHUB_) | architecture | F05333 | non-negotiable | false | 10 |
| R10615 | IaC env-var — precedence documented (env > config > default) | architecture | F05334 | non-negotiable | false | 10 |
| R10616 | IaC restart-from-state — checkpoint file at /var/lib/<project>/state.json | architecture | F05335 | non-negotiable | false | 10 |
| R10617 | IaC restart-from-state — signed via MS003 | cross-ref selfdef MS003 | F05336 | non-negotiable | false | 10 |
| R10618 | IaC pipeline — checkpoint per major step | dump 393 | F05337 | non-negotiable | false | 10 |
| R10619 | IaC pipeline — `--resume <checkpoint-id>` flag on every long-running script | architecture | F05338 | non-negotiable | false | 10 |
| R10620 | IaC pipeline — checkpoint includes timestamp + step ID + state digest | architecture + cross-ref selfdef MS003 | F05339 | non-negotiable | false | 10 |
| R10621 | IaC pipeline — progress bar OR percent for operator visibility | architecture + cross-ref M060 | F05340 | non-negotiable | false | 10 |
| R10622 | IaC pipeline — ETA estimated from prior runs | architecture | F05341 | non-negotiable | false | 10 |
| R10623 | IaC pipeline — log file at /var/log/<project>/<pipeline-id>.log | architecture | F05342 | non-negotiable | false | 10 |
| R10624 | IaC pipeline — log file emits OCSF System Activity class 1001 entries | cross-ref selfdef MS026 | F05343 | non-negotiable | false | 10 |
| R10625 | IaC pipeline — cancel via SIGTERM cleanly stops + writes resumable checkpoint | architecture | F05344 | non-negotiable | false | 10 |
| R10626 | SFIF transition trace — emits M049 13-field span | cross-ref M049 | F05345 | non-negotiable | false | 10 |
| R10627 | SFIF transition trace — span includes from-phase + to-phase | cross-ref M049 | F05346 | non-negotiable | false | 10 |
| R10628 | SFIF transition trace — span includes operator approval signature | cross-ref selfdef MS003 | F05347 | non-negotiable | false | 10 |
| R10629 | SFIF transition replay — verifies phase-history chain integrity | cross-ref selfdef MS009 | F05348 | non-negotiable | false | 10 |
| R10630 | SFIF transition replay — detects unauthorized phase escalations | cross-ref selfdef MS009 + MS003 | F05349 | non-negotiable | false | 10 |
| R10631 | SFIF transition replay — emits OCSF Detection Finding class 2004 on chain break | cross-ref selfdef MS026 | F05350 | non-negotiable | false | 10 |
| R10632 | SFIF observability — M060 D-00 main dashboard shows current SFIF phase | cross-ref M060 | F05351 | non-negotiable | false | 10 |
| R10633 | SFIF observability — D-00 main dashboard surfaces IaC quality bar pass-rate trend | cross-ref M060 | F05352 | non-negotiable | false | 10 |
| R10634 | SFIF observability — operator can drill into per-phase metrics | cross-ref M060 | F05351 | non-negotiable | false | 10 |
| R10635 | SFIF observability — phase transition emits operator notification (toast / email if configured) | cross-ref M060 + architecture | F05345 | non-negotiable | false | 10 |
| R10636 | SFIF doctrinal preservation — operator words "SFIF discipline" verbatim in M063 doc | operator standing direction | F05353 | non-negotiable | false | 10 |
| R10637 | SFIF doctrinal preservation — operator words "respect of SFIF and second-brain knowledge" verbatim in M063 doc | operator standing direction 2026-05-19 | F05354 | non-negotiable | false | 10 |
| R10638 | SFIF doctrinal preservation — verbatim quotes never paraphrased | operator standing direction | F05354 | non-negotiable | false | 10 |
| R10639 | SFIF cross-repo applicability — discipline applies to selfdef + sovereign-os + info-hub | operator standing direction | F05355 | non-negotiable | false | 10 |
| R10640 | SFIF cross-repo applicability — info-hub treated as knowledge-layer projection per "second-brain" | operator standing direction | F05315 | non-negotiable | false | 10 |
| R10641 | Implementation — SFIF phase tag emitted in every commit message at footer | architecture | F05317 | non-negotiable | false | 10 |
| R10642 | Implementation — SFIF phase tag visible in `git log --oneline --decorate` | architecture | F05317 | non-negotiable | false | 10 |
| R10643 | Implementation — SFIF phase tag tracked at /etc/sovereign-os/sfif-phase.txt | architecture | F05317 | non-negotiable | false | 10 |
| R10644 | Implementation — SFIF phase signed via MS003 | cross-ref selfdef MS003 | F05311 | non-negotiable | false | 10 |
| R10645 | Implementation — SFIF phase exposed via MS007 sovereign-sfif-mirror typed crate | cross-ref selfdef MS007 | F05317 | non-negotiable | false | 10 |
| R10646 | Implementation — SFIF phase mirror crate schema_version "1.0.0" | cross-ref selfdef MS007 | F05317 | non-negotiable | false | 10 |
| R10647 | Implementation — SFIF phase mirror crate enum (Scaffold / Foundation / InfrastructureBegin / InfrastructureContinue / Features) | cross-ref selfdef MS007 | F05317 | non-negotiable | false | 10 |
| R10648 | Implementation — SFIF transition coordinator runs as systemd unit sovereign-sfif-coordinator.service | architecture | F05306 | non-negotiable | false | 10 |
| R10649 | Implementation — SFIF transition coordinator emits readiness probe at /run/sovereign-sfif/ready | architecture | F05306 | non-negotiable | false | 10 |
| R10650 | Implementation — SFIF transition coordinator honors SIGHUP for phase reload | architecture | F05306 | non-negotiable | false | 10 |
| R10651 | IaC quality bar — CI runner: `bash` validates all .sh files with shellcheck | architecture | F05323 | non-negotiable | false | 10 |
| R10652 | IaC quality bar — CI runner: shellcheck severity `error` blocks merge | architecture | F05302 | non-negotiable | false | 10 |
| R10653 | IaC quality bar — CI runner: shellcheck severity `warning` flagged in PR comment | architecture | F05319 | non-negotiable | false | 10 |
| R10654 | IaC quality bar — CI runner: YAML configs validated against schemas | M062 PR 5 | F05329 | non-negotiable | false | 10 |
| R10655 | IaC quality bar — CI runner: TOML configs validated by `taplo` (or equivalent) | architecture | F05329 | non-negotiable | false | 10 |
| R10656 | IaC quality bar — CI runner: env-var references parsed + documented in PR comment | architecture | F05333 | non-negotiable | false | 10 |
| R10657 | IaC quality bar — CI runner: checkpoint format validated (timestamp + step-id + digest) | architecture | F05339 | non-negotiable | false | 10 |
| R10658 | IaC quality bar — CI runner: report retained as PR artifact 365 days | architecture | F05321 | non-negotiable | false | 10 |
| R10659 | Performance — IaC quality bar validator runtime `<` 30s p95 (full check) | architecture | F05301 | non-negotiable | false | 10 |
| R10660 | Performance — SFIF transition coordinator response `<` 100ms p95 | architecture | F05306 | non-negotiable | false | 10 |
| R10661 | Performance — SFIF mirror crate publication latency `<` 100ms p95 | cross-ref selfdef MS007 | F05317 | non-negotiable | false | 10 |
| R10662 | Telemetry — SFIF phase duration histograms emitted via M049 | cross-ref M049 | F05346 | non-negotiable | false | 10 |
| R10663 | Telemetry — IaC quality bar pass-rate per project emitted via M049 | cross-ref M049 | F05304 | non-negotiable | false | 10 |
| R10664 | Telemetry — IaC pipeline checkpoint count per project emitted via M049 | cross-ref M049 | F05337 | non-negotiable | false | 10 |
| R10665 | Telemetry — SFIF transition count per phase emitted via M049 | cross-ref M049 | F05345 | non-negotiable | false | 10 |
| R10666 | Boundary — SFIF discipline NEVER mutates selfdef state directly | operator standing direction | F05315 | non-negotiable | false | 10 |
| R10667 | Boundary — SFIF discipline NEVER mutates info-hub state directly | operator standing direction | F05315 | non-negotiable | false | 10 |
| R10668 | Boundary — selfdef SFIF phase published via MS007 mirror, consumed by sovereign-os only | cross-ref selfdef MS007 | F05313 | non-negotiable | false | 10 |
| R10669 | Boundary — info-hub SFIF phase published via MS007 mirror, consumed by sovereign-os only | operator standing direction "second-brain" | F05315 | non-negotiable | false | 10 |
| R10670 | Boundary — cross-repo SFIF coordination ONLY through MS007 8/8 SATURATED typed mirrors | cross-ref selfdef MS007 | F05315 | non-negotiable | false | 10 |
| R10671 | Audit — SFIF retrospective emitted annually at docs/sdd/SFIF-retrospective-YYYY.md | architecture | F05322 | non-negotiable | false | 10 |
| R10672 | Audit — retrospective includes per-phase duration / IaC pass-rate / failure root-causes | architecture | F05322 | non-negotiable | false | 10 |
| R10673 | Audit — retrospective signed via MS003 | cross-ref selfdef MS003 | F05322 | non-negotiable | false | 10 |
| R10674 | Audit — retrospective retained indefinitely (operator history) | architecture | F05322 | non-negotiable | false | 10 |
| R10675 | Cumulative — SFIF discipline covers PRs 1-N (10-PR scaffold + Stage 2+ infrastructure + Stage 3+ features) | M062 + dump 391 | F05283 | non-negotiable | false | 10 |
| R10676 | Cumulative — IaC quality bar applies to every PR regardless of SFIF phase | dump 392 | F05291 | non-negotiable | false | 10 |
| R10677 | Cumulative — phase transitions emit cumulative SFIF metrics via M049 | cross-ref M049 | F05345 | non-negotiable | false | 10 |
| R10678 | Cumulative — phase transitions never skip a phase (no Scaffold → Features) | architecture + operator standing direction | F05306 | non-negotiable | false | 10 |
| R10679 | Cumulative — phase reverts allowed only via signed operator decision | cross-ref selfdef MS003 | F05311 | non-negotiable | false | 10 |
| R10680 | Cumulative — phase reverts logged in docs/decisions.md | M062 dump 28-30 | F05312 | non-negotiable | false | 10 |
| R10681 | Composition — SFIF phase composable with sovereign-os profile (M042) | cross-ref M042 + cross-ref selfdef MS040 | F05315 | non-negotiable | false | 10 |
| R10682 | Composition — SFIF phase composable with authority levels (selfdef MS039) | cross-ref selfdef MS039 | F05315 | non-negotiable | false | 10 |
| R10683 | Composition — SFIF phase composable with trust rings (selfdef MS039) | cross-ref selfdef MS039 | F05315 | non-negotiable | false | 10 |
| R10684 | Composition — Features-phase work UNLOCKED only when Infrastructure-phase Stage Gate 5 passed | dump 281-282 | F05308 | non-negotiable | false | 10 |
| R10685 | Composition — IaC quality bar enforced at MS040 production-profile L5 Commit gate | cross-ref selfdef MS040 + dump 392 | F05291 | non-negotiable | false | 10 |
| R10686 | Operational — SFIF coordinator refuses to start if sfif-phase.txt missing or unsigned | architecture + cross-ref selfdef MS003 | F05311 | non-negotiable | false | 10 |
| R10687 | Operational — SFIF coordinator refuses to skip phase | architecture | F05678 | non-negotiable | false | 10 |
| R10688 | Operational — SFIF coordinator refuses to advance phase without Stage Gate sign-off | architecture | F05306 | non-negotiable | false | 10 |
| R10689 | Operational — SFIF coordinator graceful drain on shutdown | architecture | F05306 | non-negotiable | false | 10 |
| R10690 | Operational — SFIF coordinator emits per-phase health via M049 | cross-ref M049 | F05345 | non-negotiable | false | 10 |
| R10691 | Closing — SFIF discipline is OPERATOR-NAMED in /goal 2026-05-19 verbatim | operator standing direction | F05354 | non-negotiable | false | 10 |
| R10692 | Closing — SFIF is not invented; operator-stated discipline preserved verbatim | operator standing direction | F05353 | non-negotiable | false | 10 |
| R10693 | Closing — SFIF coordination respects "Respect the projects" boundary | operator standing direction | F05315 | non-negotiable | false | 10 |
| R10694 | Closing — SFIF applies to all 3 repos (sovereign-os + selfdef + info-hub) | operator standing direction | F05355 | non-negotiable | false | 10 |
| R10695 | Closing — info-hub is read-only "second-brain / information-hub" per operator standing direction | operator standing direction | F05315 | non-negotiable | false | 10 |
| R10696 | Closing — IaC quality bar is OPERATOR-STATED verbatim (dump 392-393) | dump 392-393 | F05548 | non-negotiable | false | 10 |
| R10697 | Closing — IaC quality bar is non-negotiable, enforced at every PR | dump 392-393 + operator standing direction | F05301 | non-negotiable | false | 10 |
| R10698 | Closing — operator standing direction "do not minimize" preserved across SFIF | operator standing direction | F05291 | non-negotiable | false | 10 |
| R10699 | Closing — operator standing direction "do not invent crap" preserved across SFIF | operator standing direction | F05691 | non-negotiable | false | 10 |
| R10700 | Closing — operator words sacrosanct verbatim in every artifact | operator standing direction | F05354 | non-negotiable | false | 10 |
| R10701 | Closing — direct-to-main commits on sovereign-os + selfdef authorized | operator standing direction | F05317 | non-negotiable | false | 10 |
| R10702 | Closing — every commit signs via selfdef MS003 | cross-ref selfdef MS003 | F05320 | non-negotiable | false | 10 |
| R10703 | Closing — every commit emits M049 trace event | cross-ref M049 | F05299 | non-negotiable | false | 10 |
| R10704 | Closing — sovereignty preserved: peace machine axiom retained throughout SFIF | sovereign-os M059 + operator standing direction | F05355 | non-negotiable | false | 10 |
| R10705 | Closing — sovereign-os catalog 63/63 milestones (now extends prior 62) | architecture | F05355 | non-negotiable | false | 10 |
| R10706 | Closing — combined ecosystem 106 milestones (selfdef 43 + sovereign-os 63) | architecture | F05355 | non-negotiable | false | 10 |
| R10707 | Closing — combined R-rows ~21030 | architecture | F05355 | non-negotiable | false | 10 |
| R10708 | Closing — combined enforced sub-reqs ~210300 | architecture | F05355 | non-negotiable | false | 10 |
| R10709 | Closing — every R-row carries 10 hard non-negotiable sub-requirements | operator standing direction | F05291 | non-negotiable | false | 10 |
| R10710 | Closing — SFIF authoring complete; M064-M076 pending; SDD/TDD implementation gated behind catalog + patch passes + prior-dump milestones | operator standing direction | F05315 | non-negotiable | false | 10 |

## Sub-requirements accounting

Every R-row carries 10 hard non-negotiable sub-requirements per operator standing direction. Total enforced sub-reqs = 170 R × 10 = **1,700 sub-requirements** for M063.

## Cross-references

- **M042** — choice architecture / sovereignty-as-policy-composable (SFIF composes with profile envelope)
- **M048** — modules map (Features-phase delivers sovereign-os module set)
- **M049** — observability + trace pipeline (SFIF transitions emit traces)
- **M059** — peace machine close (SFIF preserves sovereignty axiom throughout)
- **M060** — cockpit + dashboards (D-00 surfaces SFIF phase)
- **M062** — Macro-Arc 10-PR Foundation Scaffold (SFIF labels PRs 1-3 / 4-8 / 9-10)
- **M064** — "Debian as Ark" + Q-016 (Foundation-phase substrate-survey scope)
- **M065** — Five Stage Gates SG1-SG5 (operationalizes SFIF transition checkpoints)
- **selfdef MS003** — selfdef-signing (signs every SFIF phase transition + IaC checkpoint)
- **selfdef MS007** — typed-mirror crate scheme (sovereign-sfif-mirror)
- **selfdef MS009** — replay validator (verifies SFIF phase chain integrity)
- **selfdef MS026** — observability + OCSF event emission
- **selfdef MS039** — authority levels + trust rings (SFIF composes with authority envelope)
- **selfdef MS040** — six-profile authority matrix (IaC quality bar enforced at production-profile L5 Commit)
- **selfdef MS041** — commit authority (IaC restart-from-state signed receipts)
- **info-hub** — second-brain knowledge layer (read-only, SFIF phase published via MS007 mirror)

## Schema

```
schema_version: "1.0.0"
milestone_id: M063
parent: sovereign-os
epics: 10
modules: 17
features: 85
requirements: 170
sub_requirements_per_requirement: 10
total_sub_requirements: 1700
source_dump_lines: 390-396
operator_named_explicitly: true
operator_directive_verbatim: |
  SFIF discipline: the arc itself follows Scaffold → Foundation → Infrastructure → Features.
  PRs 1-3 = Scaffold; PRs 4-8 = Foundation; PRs 9-10 begin Infrastructure;
  Stage 2 onwards delivers Infrastructure + Features.
iac_quality_bar_verbatim: |
  high-quality scripts + libs + configuration + easily tweakable + customisable +
  env-var-driven + restart-from-state. Build pipeline is resumable + observable,
  not one-shot.
sfif_phases:
  - Scaffold (PRs 1-3)
  - Foundation (PRs 4-8)
  - Infrastructure begin (PRs 9-10)
  - Infrastructure continue (Stage 2+)
  - Features (Stage 3+)
typed_mirror_crate: sovereign-sfif-mirror
catalog_status:
  sovereign_os: 63/63 milestones (now extends prior 62)
  selfdef: 43/43 milestones
  combined: 106 milestones
```
