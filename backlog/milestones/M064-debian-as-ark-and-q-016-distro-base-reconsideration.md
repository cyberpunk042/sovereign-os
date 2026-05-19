# M064 — "Debian as Ark" framing + Q-016 distro-base reconsideration

**Parent**: sovereign-os runtime — substrate philosophy + open-question gate
**Source**: `~/infohub/raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md` lines 396-399 (Post-Plan Operator Refinements items 3 + 4)
**Operator standing direction** (verbatim, 2026-05-16): *"'Debian as Ark' framing: Debian 13 is the starting boat, not the destination. The substrate survey (PR 4) must include Q-016 — distro-base reconsideration: would switching from Debian 13 to another base unlock material new potential that we'd lose by staying? Working hypothesis: stay on Debian + customize the boat. Alternatives evaluated honestly; trade-offs documented either way."*
**Cross-references**: M044 (substrate Debian 13 / Ubuntu 24) + M062 PR 4 (substrate survey SDD) + M063 SFIF Foundation phase

## Doctrinal anchors

> "Debian 13 is the starting boat, not the destination." (dump 396)
> "Working hypothesis: stay on Debian + customize the boat. Alternatives evaluated honestly; trade-offs documented either way." (dump 397-398)
> "Q-016 added to seed list: substrate-base reconsideration. Stays open through PR 4 survey; resolved at Stage Gate 2 alongside Q-001 (substrate tooling)." (dump 398-399)

## Epics (E0618-E0627)

| epic | name | source |
|---|---|---|
| E0618 | "Debian as Ark" doctrinal frame — Debian 13 is starting boat, not destination | dump 396 |
| E0619 | Working hypothesis — stay on Debian + customize the boat | dump 397 |
| E0620 | Honest alternative evaluation — every alternative substrate compared without bias | dump 397-398 |
| E0621 | Trade-off documentation — both stay + switch paths documented either way | dump 398 |
| E0622 | Q-016 open question — distro-base reconsideration | dump 398-399 |
| E0623 | Q-016 timeline — open through PR 4 substrate survey | dump 399 |
| E0624 | Q-016 resolution — at Stage Gate 2 alongside Q-001 (substrate tooling) | dump 399 |
| E0625 | Substrate evaluation criteria — what "material new potential" means | dump 396 + architecture |
| E0626 | Substrate evaluation criteria — what "lose by staying" means | dump 396 + architecture |
| E0627 | Operator decision authority — operator picks, never SDD | M062 PR 4 dump 96 |

## Modules (M01071-M01087)

| module | name | source |
|---|---|---|
| M01071 | sovereign-debian-as-ark-doctrine | dump 396 |
| M01072 | sovereign-debian-13-baseline-binder | dump 396 + cross-ref M044 |
| M01073 | sovereign-customization-the-boat | dump 397 |
| M01074 | sovereign-alternative-substrate-survey-engine | dump 397-398 + M062 PR 4 |
| M01075 | sovereign-trade-off-bidirectional-documenter | dump 398 |
| M01076 | sovereign-q-016-tracker | dump 398-399 |
| M01077 | sovereign-q-016-timeline-pr-4-gate | dump 399 + M062 PR 4 |
| M01078 | sovereign-q-016-resolver-stage-gate-2 | dump 399 + M062 dump 113-117 |
| M01079 | sovereign-q-001-coordinator (substrate tooling adjacent) | dump 399 |
| M01080 | sovereign-material-new-potential-evaluator | dump 396 |
| M01081 | sovereign-loss-by-staying-evaluator | dump 396 |
| M01082 | sovereign-substrate-decision-recorder | M062 dump 99 |
| M01083 | sovereign-debian-as-ark-replay-validator | cross-ref selfdef MS009 |
| M01084 | sovereign-debian-as-ark-typed-mirror | cross-ref selfdef MS007 |
| M01085 | sovereign-debian-as-ark-event-emitter | cross-ref M049 + cross-ref selfdef MS026 |
| M01086 | sovereign-substrate-evolution-roadmap | dump 396 + architecture |
| M01087 | sovereign-substrate-doctrine-publisher | architecture + operator standing direction |

## Features (F05356-F05440)

| feature | name | source |
|---|---|---|
| F05356 | "Debian as Ark" frame — Debian 13 is starting baseline | dump 396 |
| F05357 | "Debian as Ark" frame — Debian 13 is NOT the destination | dump 396 |
| F05358 | "Debian as Ark" frame — destination is "AI workstation OS" (sovereign-os) | dump 396 + cross-ref M044 |
| F05359 | "Debian as Ark" frame — Debian provides starting kernel/userland/package-manager | cross-ref M044 + dump 396 |
| F05360 | "Debian as Ark" frame — substrate evolves over time without losing sovereignty | dump 396 + cross-ref M059 |
| F05361 | Working hypothesis — stay on Debian | dump 397 |
| F05362 | Working hypothesis — customize the boat (sovereign-os-specific kernel + userland) | dump 397 |
| F05363 | Working hypothesis — customization includes -march=znver5 kernel build (M067 forthcoming) | dump 397 + prior-dump 2026-05-15 |
| F05364 | Working hypothesis — customization includes ZFS-root (M068 forthcoming) | dump 397 + prior-dump 2026-05-15 |
| F05365 | Working hypothesis — customization includes Tetragon eBPF + guardian (MS044 forthcoming) | dump 397 + prior-dump 2026-05-15 |
| F05366 | Working hypothesis — customization driven by SFIF Infrastructure phase | cross-ref M063 |
| F05367 | Alternative survey — Ubuntu 24 LTS | M062 PR 4 + cross-ref M044 |
| F05368 | Alternative survey — Fedora Workstation / Silverblue | M062 PR 4 |
| F05369 | Alternative survey — NixOS (declarative, atomic) | M062 PR 4 |
| F05370 | Alternative survey — Arch Linux (rolling, customizable) | M062 PR 4 |
| F05371 | Alternative survey — Gentoo (source-based, AVX-512 tuning native) | M062 PR 4 |
| F05372 | Alternative survey — openSUSE Tumbleweed (rolling with snapshot rollback) | M062 PR 4 |
| F05373 | Alternative survey — Alpine (minimal, musl-based) | M062 PR 4 |
| F05374 | Alternative survey — Void Linux (runit init, alternative to systemd) | M062 PR 4 |
| F05375 | Alternative survey — bespoke buildroot-based custom distro | M062 PR 4 |
| F05376 | Honest evaluation — no incumbency bias toward Debian | dump 397-398 |
| F05377 | Honest evaluation — no rejection bias against alternatives | dump 397-398 |
| F05378 | Honest evaluation — material new potential measured (not assumed) | dump 396 |
| F05379 | Honest evaluation — loss by staying measured (not assumed) | dump 396 |
| F05380 | Material new potential — evaluation dimension: kernel build velocity | architecture |
| F05381 | Material new potential — evaluation dimension: AVX-512 native tuning | prior-dump 2026-05-15 + architecture |
| F05382 | Material new potential — evaluation dimension: ZFS-root maturity | prior-dump 2026-05-15 |
| F05383 | Material new potential — evaluation dimension: container/podman alignment | M062 PR 4 dump 93 |
| F05384 | Material new potential — evaluation dimension: declarative-vs-imperative substrate | M062 PR 4 dump 93 |
| F05385 | Material new potential — evaluation dimension: secure-boot ergonomics | M062 PR 4 dump 93 |
| F05386 | Material new potential — evaluation dimension: package availability + freshness | architecture |
| F05387 | Material new potential — evaluation dimension: long-term reproducibility | M062 PR 4 dump 93-94 |
| F05388 | Loss by staying — evaluation dimension: AVX-512 compiler defaults conservatism | prior-dump 2026-05-15 |
| F05389 | Loss by staying — evaluation dimension: ZFS DKMS friction | architecture |
| F05390 | Loss by staying — evaluation dimension: kernel update cadence | architecture |
| F05391 | Loss by staying — evaluation dimension: systemd ecosystem lock-in | architecture |
| F05392 | Loss by staying — evaluation dimension: package-manager flexibility | architecture |
| F05393 | Loss by staying — evaluation dimension: trademark/whitelabel friction | M062 PR 7 dump 188 |
| F05394 | Trade-off documentation — stay path documented fully | dump 398 |
| F05395 | Trade-off documentation — switch path documented fully | dump 398 |
| F05396 | Trade-off documentation — written in docs/sdd/003-substrate-survey.md | M062 PR 4 |
| F05397 | Trade-off documentation — bidirectional reversal cost analysis | M062 PR 4 dump 97 |
| F05398 | Trade-off documentation — operator chooses based on data, never assumption | M062 PR 4 dump 96 |
| F05399 | Q-016 — title: distro-base reconsideration | dump 398 |
| F05400 | Q-016 — added to docs/decisions.md open-question seed list | dump 398 |
| F05401 | Q-016 — open through M062 PR 4 substrate survey | dump 399 + M062 PR 4 |
| F05402 | Q-016 — resolved at M062 Stage Gate 2 | dump 399 + M062 dump 113-117 |
| F05403 | Q-016 — resolved alongside Q-001 (substrate tooling) | dump 399 |
| F05404 | Q-016 — resolution recorded in docs/decisions.md with timestamp + actor | M062 dump 99 |
| F05405 | Q-016 — resolution signed via selfdef MS003 | cross-ref selfdef MS003 |
| F05406 | Q-016 — resolution emits M049 trace + OCSF Configuration Change class 5001 | cross-ref M049 + selfdef MS026 |
| F05407 | Q-001 — substrate tooling adjacent question | dump 399 |
| F05408 | Q-001 — also resolved at Stage Gate 2 | dump 399 + M062 |
| F05409 | Q-001 — substrate tooling = live-build / mkosi / debootstrap / Lorax / Kiwi / ostree / Nix / Buildroot | M062 PR 4 dump 91 |
| F05410 | Q-001 — operator pick recorded alongside Q-016 result | M062 dump 116 |
| F05411 | Q-016 timeline — opens at M062 PR 1 (decisions.md seeded with seed list) | M062 dump 30 |
| F05412 | Q-016 timeline — stays open through PRs 2-3 (no early resolution) | dump 399 |
| F05413 | Q-016 timeline — research happens in PR 4 substrate survey SDD | dump 399 + M062 PR 4 |
| F05414 | Q-016 timeline — resolution happens at Stage Gate 2 (operator review) | dump 399 |
| F05415 | Q-016 timeline — locks substrate decision for downstream PRs 5-10 | M062 dump 117 |
| F05416 | Substrate doctrine publisher — publishes "Debian as Ark" + working hypothesis as docs/sdd/ doc | architecture |
| F05417 | Substrate doctrine publisher — readable summary at /etc/sovereign-os/substrate-doctrine.txt | architecture |
| F05418 | Substrate doctrine publisher — signed via selfdef MS003 | cross-ref selfdef MS003 |
| F05419 | Substrate doctrine publisher — exposed via MS007 sovereign-substrate-doctrine-mirror | cross-ref selfdef MS007 |
| F05420 | Substrate doctrine publisher — version bumps on doctrine change | cross-ref selfdef MS007 |
| F05421 | Substrate doctrine publisher — change emits M049 trace + OCSF Configuration Change class 5001 | cross-ref M049 + selfdef MS026 |
| F05422 | Substrate evolution roadmap — short-term: stay on Debian, customize kernel + userland | dump 397 + prior-dump 2026-05-15 |
| F05423 | Substrate evolution roadmap — mid-term: progressively replace components if customization friction exceeds threshold | dump 396 + architecture |
| F05424 | Substrate evolution roadmap — long-term: ability to swap base if "material new potential" emerges | dump 396 + M062 PR 4 dump 97 |
| F05425 | Substrate evolution roadmap — every swap candidate documented + scored at SFIF Foundation gate reviews | cross-ref M063 |
| F05426 | Material new potential evaluator — scores each alternative against 8+ dimensions | architecture + M062 PR 4 dump 93-94 |
| F05427 | Material new potential evaluator — emits numerical + prose justification (per M062 PR 4 mandate) | M062 PR 4 dump 95 |
| F05428 | Material new potential evaluator — failure mode: discounting an alternative without measurement | dump 397-398 |
| F05429 | Material new potential evaluator — output retained 365 days under /var/lib/sovereign-os/substrate-evaluations/ | architecture |
| F05430 | Loss by staying evaluator — scores each "stay" path against 8+ dimensions | architecture + M062 PR 4 dump 93-94 |
| F05431 | Loss by staying evaluator — emits opportunity-cost analysis | dump 396 |
| F05432 | Loss by staying evaluator — emits friction-cost analysis (DKMS / patch / build velocity) | architecture |
| F05433 | Substrate decision recorder — records operator choice in docs/decisions.md | M062 dump 99 |
| F05434 | Substrate decision recorder — records rationale (operator-authored sentence) | M062 dump 99 + architecture |
| F05435 | Substrate decision recorder — records evaluation digests + signatures | cross-ref selfdef MS003 |
| F05436 | Substrate decision recorder — recorded decision treated as L6 Persist | cross-ref selfdef MS039 |
| F05437 | Substrate replay validator — verifies historical substrate-decision chain | cross-ref selfdef MS009 |
| F05438 | Substrate replay validator — detects unauthorized substrate change | cross-ref selfdef MS009 + MS003 |
| F05439 | Substrate replay validator — emits OCSF Detection Finding class 2004 on chain break | cross-ref selfdef MS026 |
| F05440 | Closing — Debian as Ark + Q-016 covers dump 396-399 verbatim | dump 396-399 |

## Requirements (R10711-R10880)

| req | description | source | feature | priority | exception | sub-reqs |
|---|---|---|---|---|---|---|
| R10711 | Doctrinal — "Debian 13 is the starting boat, not the destination" | dump 396 | F05356 | non-negotiable | false | 10 |
| R10712 | Doctrinal — substrate survey (PR 4) must include Q-016 distro-base reconsideration | dump 398 | F05399 | non-negotiable | false | 10 |
| R10713 | Doctrinal — would switching from Debian 13 unlock material new potential? | dump 396 | F05378 | non-negotiable | false | 10 |
| R10714 | Doctrinal — would switching lose something material by staying? | dump 396 | F05379 | non-negotiable | false | 10 |
| R10715 | Doctrinal — Working hypothesis: stay on Debian + customize the boat | dump 397 | F05361 | non-negotiable | false | 10 |
| R10716 | Doctrinal — Alternatives evaluated honestly | dump 397-398 | F05376 | non-negotiable | false | 10 |
| R10717 | Doctrinal — trade-offs documented either way | dump 398 | F05394 | non-negotiable | false | 10 |
| R10718 | Doctrinal — Q-016 added to seed list: substrate-base reconsideration | dump 398 | F05400 | non-negotiable | false | 10 |
| R10719 | Doctrinal — Q-016 stays open through PR 4 survey | dump 399 | F05401 | non-negotiable | false | 10 |
| R10720 | Doctrinal — Q-016 resolved at Stage Gate 2 alongside Q-001 (substrate tooling) | dump 399 | F05402 | non-negotiable | false | 10 |
| R10721 | Ark frame — Debian 13 is starting baseline | dump 396 | F05356 | non-negotiable | false | 10 |
| R10722 | Ark frame — destination = sovereign-os AI workstation | dump 396 + cross-ref M044 | F05358 | non-negotiable | false | 10 |
| R10723 | Ark frame — Debian provides starting kernel | cross-ref M044 + dump 396 | F05359 | non-negotiable | false | 10 |
| R10724 | Ark frame — Debian provides starting userland | cross-ref M044 + dump 396 | F05359 | non-negotiable | false | 10 |
| R10725 | Ark frame — Debian provides starting package-manager (dpkg + apt) | cross-ref M044 + dump 396 | F05359 | non-negotiable | false | 10 |
| R10726 | Ark frame — substrate evolves over time without losing sovereignty | dump 396 + cross-ref M059 | F05360 | non-negotiable | false | 10 |
| R10727 | Ark frame — sovereignty preserved across substrate evolution (peace machine axiom) | cross-ref M059 + operator standing direction | F05360 | non-negotiable | false | 10 |
| R10728 | Hypothesis — stay on Debian | dump 397 | F05361 | non-negotiable | false | 10 |
| R10729 | Hypothesis — customize the boat | dump 397 | F05362 | non-negotiable | false | 10 |
| R10730 | Hypothesis — customization includes -march=znver5 kernel build (M067 forthcoming) | dump 397 + prior-dump 2026-05-15 | F05363 | non-negotiable | false | 10 |
| R10731 | Hypothesis — customization includes ZFS-root (M068 forthcoming) | dump 397 + prior-dump 2026-05-15 | F05364 | non-negotiable | false | 10 |
| R10732 | Hypothesis — customization includes Tetragon eBPF + guardian daemon (MS044 forthcoming) | dump 397 + prior-dump 2026-05-15 | F05365 | non-negotiable | false | 10 |
| R10733 | Hypothesis — customization driven by SFIF Infrastructure phase | cross-ref M063 | F05366 | non-negotiable | false | 10 |
| R10734 | Hypothesis — customization respects M063 IaC quality bar | cross-ref M063 + dump 392-393 | F05366 | non-negotiable | false | 10 |
| R10735 | Hypothesis — customization signed via selfdef MS003 chain-of-trust | cross-ref selfdef MS003 | F05366 | non-negotiable | false | 10 |
| R10736 | Alternatives surveyed — Ubuntu 24 LTS | M062 PR 4 + cross-ref M044 | F05367 | non-negotiable | false | 10 |
| R10737 | Alternatives surveyed — Fedora Workstation / Silverblue | M062 PR 4 | F05368 | non-negotiable | false | 10 |
| R10738 | Alternatives surveyed — NixOS (declarative atomic) | M062 PR 4 | F05369 | non-negotiable | false | 10 |
| R10739 | Alternatives surveyed — Arch Linux (rolling customizable) | M062 PR 4 | F05370 | non-negotiable | false | 10 |
| R10740 | Alternatives surveyed — Gentoo (source-based AVX-512 tuning native) | M062 PR 4 | F05371 | non-negotiable | false | 10 |
| R10741 | Alternatives surveyed — openSUSE Tumbleweed (rolling snapshot rollback) | M062 PR 4 | F05372 | non-negotiable | false | 10 |
| R10742 | Alternatives surveyed — Alpine (minimal musl-based) | M062 PR 4 | F05373 | non-negotiable | false | 10 |
| R10743 | Alternatives surveyed — Void Linux (runit init, alternative to systemd) | M062 PR 4 | F05374 | non-negotiable | false | 10 |
| R10744 | Alternatives surveyed — bespoke buildroot-based custom distro | M062 PR 4 | F05375 | non-negotiable | false | 10 |
| R10745 | Honest evaluation — no incumbency bias toward Debian | dump 397-398 | F05376 | non-negotiable | false | 10 |
| R10746 | Honest evaluation — no rejection bias against alternatives | dump 397-398 | F05377 | non-negotiable | false | 10 |
| R10747 | Honest evaluation — material new potential measured, not assumed | dump 396 | F05378 | non-negotiable | false | 10 |
| R10748 | Honest evaluation — loss by staying measured, not assumed | dump 396 | F05379 | non-negotiable | false | 10 |
| R10749 | Honest evaluation — evaluator output signed via MS003 | cross-ref selfdef MS003 | F05429 | non-negotiable | false | 10 |
| R10750 | Honest evaluation — failure mode (discounting without measurement) blocks merge of PR 4 | dump 397-398 + architecture | F05428 | non-negotiable | false | 10 |
| R10751 | Material new potential — dimension: kernel build velocity | architecture | F05380 | non-negotiable | false | 10 |
| R10752 | Material new potential — dimension: AVX-512 native tuning | prior-dump 2026-05-15 + architecture | F05381 | non-negotiable | false | 10 |
| R10753 | Material new potential — dimension: ZFS-root maturity | prior-dump 2026-05-15 | F05382 | non-negotiable | false | 10 |
| R10754 | Material new potential — dimension: container/podman alignment | M062 PR 4 dump 93 | F05383 | non-negotiable | false | 10 |
| R10755 | Material new potential — dimension: declarative-vs-imperative substrate | M062 PR 4 dump 93 | F05384 | non-negotiable | false | 10 |
| R10756 | Material new potential — dimension: secure-boot ergonomics | M062 PR 4 dump 93 | F05385 | non-negotiable | false | 10 |
| R10757 | Material new potential — dimension: package availability + freshness | architecture | F05386 | non-negotiable | false | 10 |
| R10758 | Material new potential — dimension: long-term reproducibility | M062 PR 4 dump 93-94 | F05387 | non-negotiable | false | 10 |
| R10759 | Loss by staying — dimension: AVX-512 compiler defaults conservatism | prior-dump 2026-05-15 | F05388 | non-negotiable | false | 10 |
| R10760 | Loss by staying — dimension: ZFS DKMS friction | architecture | F05389 | non-negotiable | false | 10 |
| R10761 | Loss by staying — dimension: kernel update cadence | architecture | F05390 | non-negotiable | false | 10 |
| R10762 | Loss by staying — dimension: systemd ecosystem lock-in | architecture | F05391 | non-negotiable | false | 10 |
| R10763 | Loss by staying — dimension: package-manager flexibility | architecture | F05392 | non-negotiable | false | 10 |
| R10764 | Loss by staying — dimension: trademark / whitelabel friction | M062 PR 7 dump 188 | F05393 | non-negotiable | false | 10 |
| R10765 | Trade-off doc — stay path documented fully | dump 398 | F05394 | non-negotiable | false | 10 |
| R10766 | Trade-off doc — switch path documented fully | dump 398 | F05395 | non-negotiable | false | 10 |
| R10767 | Trade-off doc — written in docs/sdd/003-substrate-survey.md | M062 PR 4 | F05396 | non-negotiable | false | 10 |
| R10768 | Trade-off doc — bidirectional reversal cost analysis | M062 PR 4 dump 97 | F05397 | non-negotiable | false | 10 |
| R10769 | Trade-off doc — operator chooses based on data, never assumption | M062 PR 4 dump 96 | F05398 | non-negotiable | false | 10 |
| R10770 | Q-016 — title: distro-base reconsideration | dump 398 | F05399 | non-negotiable | false | 10 |
| R10771 | Q-016 — added to docs/decisions.md open-question seed list | dump 398 | F05400 | non-negotiable | false | 10 |
| R10772 | Q-016 — open through M062 PR 4 substrate survey | dump 399 | F05401 | non-negotiable | false | 10 |
| R10773 | Q-016 — resolved at M062 Stage Gate 2 | dump 399 | F05402 | non-negotiable | false | 10 |
| R10774 | Q-016 — resolved alongside Q-001 substrate tooling | dump 399 | F05403 | non-negotiable | false | 10 |
| R10775 | Q-016 — resolution recorded in docs/decisions.md with timestamp + actor | M062 dump 99 | F05404 | non-negotiable | false | 10 |
| R10776 | Q-016 — resolution signed via selfdef MS003 | cross-ref selfdef MS003 | F05405 | non-negotiable | false | 10 |
| R10777 | Q-016 — resolution emits M049 trace | cross-ref M049 | F05406 | non-negotiable | false | 10 |
| R10778 | Q-016 — resolution emits OCSF Configuration Change class 5001 | cross-ref selfdef MS026 | F05406 | non-negotiable | false | 10 |
| R10779 | Q-001 — substrate tooling adjacent question | dump 399 | F05407 | non-negotiable | false | 10 |
| R10780 | Q-001 — also resolved at Stage Gate 2 | dump 399 + M062 | F05408 | non-negotiable | false | 10 |
| R10781 | Q-001 — substrate tooling candidates: live-build / mkosi / debootstrap / Lorax / Kiwi / ostree / Nix / Buildroot | M062 PR 4 dump 91 | F05409 | non-negotiable | false | 10 |
| R10782 | Q-001 — operator pick recorded alongside Q-016 result | M062 dump 116 | F05410 | non-negotiable | false | 10 |
| R10783 | Q-016 timeline — opens at M062 PR 1 (decisions.md seeded) | M062 dump 30 | F05411 | non-negotiable | false | 10 |
| R10784 | Q-016 timeline — stays open through PRs 2-3 (no early resolution) | dump 399 | F05412 | non-negotiable | false | 10 |
| R10785 | Q-016 timeline — research happens in PR 4 substrate survey SDD | dump 399 + M062 PR 4 | F05413 | non-negotiable | false | 10 |
| R10786 | Q-016 timeline — resolution at Stage Gate 2 (operator review) | dump 399 | F05414 | non-negotiable | false | 10 |
| R10787 | Q-016 timeline — locks substrate decision for downstream PRs 5-10 | M062 dump 117 | F05415 | non-negotiable | false | 10 |
| R10788 | Doctrine publisher — publishes "Debian as Ark" + working hypothesis as docs/sdd/ doc | architecture | F05416 | non-negotiable | false | 10 |
| R10789 | Doctrine publisher — readable summary at /etc/sovereign-os/substrate-doctrine.txt | architecture | F05417 | non-negotiable | false | 10 |
| R10790 | Doctrine publisher — signed via selfdef MS003 | cross-ref selfdef MS003 | F05418 | non-negotiable | false | 10 |
| R10791 | Doctrine publisher — exposed via MS007 sovereign-substrate-doctrine-mirror | cross-ref selfdef MS007 | F05419 | non-negotiable | false | 10 |
| R10792 | Doctrine publisher — version bumps on doctrine change | cross-ref selfdef MS007 | F05420 | non-negotiable | false | 10 |
| R10793 | Doctrine publisher — change emits M049 trace | cross-ref M049 | F05421 | non-negotiable | false | 10 |
| R10794 | Doctrine publisher — change emits OCSF Configuration Change class 5001 | cross-ref selfdef MS026 | F05421 | non-negotiable | false | 10 |
| R10795 | Evolution roadmap — short-term: stay on Debian, customize kernel + userland | dump 397 + prior-dump 2026-05-15 | F05422 | non-negotiable | false | 10 |
| R10796 | Evolution roadmap — mid-term: progressively replace components if friction exceeds threshold | dump 396 + architecture | F05423 | non-negotiable | false | 10 |
| R10797 | Evolution roadmap — long-term: ability to swap base if material new potential emerges | dump 396 + M062 PR 4 dump 97 | F05424 | non-negotiable | false | 10 |
| R10798 | Evolution roadmap — every swap candidate documented + scored at SFIF Foundation gate reviews | cross-ref M063 | F05425 | non-negotiable | false | 10 |
| R10799 | Evolution roadmap — friction threshold operator-defined, retained in docs/decisions.md | architecture + M062 dump 99 | F05423 | non-negotiable | false | 10 |
| R10800 | Material new potential evaluator — scores each alternative against 8+ dimensions | architecture + M062 PR 4 | F05426 | non-negotiable | false | 10 |
| R10801 | Material new potential evaluator — emits numerical + prose justification | M062 PR 4 dump 95 | F05427 | non-negotiable | false | 10 |
| R10802 | Material new potential evaluator — failure mode: discounting without measurement = invalid | dump 397-398 | F05428 | non-negotiable | false | 10 |
| R10803 | Material new potential evaluator — output retained 365 days under /var/lib/sovereign-os/substrate-evaluations/ | architecture | F05429 | non-negotiable | false | 10 |
| R10804 | Loss by staying evaluator — scores each "stay" path against 8+ dimensions | architecture + M062 PR 4 | F05430 | non-negotiable | false | 10 |
| R10805 | Loss by staying evaluator — emits opportunity-cost analysis | dump 396 | F05431 | non-negotiable | false | 10 |
| R10806 | Loss by staying evaluator — emits friction-cost analysis (DKMS / patch / build velocity) | architecture | F05432 | non-negotiable | false | 10 |
| R10807 | Decision recorder — records operator choice in docs/decisions.md | M062 dump 99 | F05433 | non-negotiable | false | 10 |
| R10808 | Decision recorder — records rationale (operator-authored sentence) | M062 dump 99 + architecture | F05434 | non-negotiable | false | 10 |
| R10809 | Decision recorder — records evaluation digests + signatures | cross-ref selfdef MS003 | F05435 | non-negotiable | false | 10 |
| R10810 | Decision recorder — recorded decision treated as L6 Persist | cross-ref selfdef MS039 | F05436 | non-negotiable | false | 10 |
| R10811 | Decision recorder — high-risk gates (snapshot + test/eval + oracle-or-human) required per MS041 | cross-ref selfdef MS041 | F05436 | non-negotiable | false | 10 |
| R10812 | Replay validator — verifies historical substrate-decision chain | cross-ref selfdef MS009 | F05437 | non-negotiable | false | 10 |
| R10813 | Replay validator — detects unauthorized substrate change | cross-ref selfdef MS009 + MS003 | F05438 | non-negotiable | false | 10 |
| R10814 | Replay validator — emits OCSF Detection Finding class 2004 on chain break | cross-ref selfdef MS026 | F05439 | non-negotiable | false | 10 |
| R10815 | Replay validator — runs daily as cron unit | cross-ref selfdef MS009 | F05437 | non-negotiable | false | 10 |
| R10816 | Replay validator — failures halt new substrate-related commits until resolved | architecture | F05437 | non-negotiable | false | 10 |
| R10817 | Boundary — IPS (selfdef) NOT affected by substrate choice mechanism (only ENFORCES policy on it) | operator standing direction "Respect the projects" | F05357 | non-negotiable | false | 10 |
| R10818 | Boundary — info-hub knowledge layer surfaces substrate doctrine as read-only context | operator standing direction "second-brain" | F05417 | non-negotiable | false | 10 |
| R10819 | Boundary — cross-repo substrate coordination ONLY through MS007 mirror | cross-ref selfdef MS007 | F05419 | non-negotiable | false | 10 |
| R10820 | Boundary — substrate decision is sovereign-os runtime concern (M044 substrate cataloged here) | cross-ref M044 + operator standing direction | F05357 | non-negotiable | false | 10 |
| R10821 | Composition — substrate doctrine composable with SFIF Foundation phase | cross-ref M063 | F05366 | non-negotiable | false | 10 |
| R10822 | Composition — substrate doctrine composable with M042 choice architecture | cross-ref M042 | F05425 | non-negotiable | false | 10 |
| R10823 | Composition — substrate doctrine composable with selfdef MS040 production-profile gates | cross-ref selfdef MS040 | F05436 | non-negotiable | false | 10 |
| R10824 | Composition — substrate doctrine retained across SFIF phase transitions | cross-ref M063 | F05425 | non-negotiable | false | 10 |
| R10825 | Composition — substrate evolution emits cumulative metric via M049 (years-on-Debian / years-on-alt) | cross-ref M049 + architecture | F05423 | non-negotiable | false | 10 |
| R10826 | Telemetry — substrate evaluation count emitted via M049 | cross-ref M049 | F05426 | non-negotiable | false | 10 |
| R10827 | Telemetry — Q-016 lifecycle (open / researching / resolved) emitted via M049 | cross-ref M049 | F05399 | non-negotiable | false | 10 |
| R10828 | Telemetry — substrate decision recorder write count emitted via M049 | cross-ref M049 | F05433 | non-negotiable | false | 10 |
| R10829 | Telemetry — substrate doctrine version emitted via M049 | cross-ref M049 + cross-ref selfdef MS007 | F05420 | non-negotiable | false | 10 |
| R10830 | Telemetry — substrate replay validator pass/fail rate emitted via M049 | cross-ref M049 | F05437 | non-negotiable | false | 10 |
| R10831 | Operational — substrate doctrine publisher runs as systemd unit sovereign-substrate-doctrine.service | architecture | F05416 | non-negotiable | false | 10 |
| R10832 | Operational — substrate doctrine publisher honors SIGHUP for doctrine reload | architecture | F05416 | non-negotiable | false | 10 |
| R10833 | Operational — substrate replay validator runs as systemd timer (daily) | architecture + cross-ref selfdef MS009 | F05437 | non-negotiable | false | 10 |
| R10834 | Operational — substrate decision recorder emits readiness probe at /run/sovereign-substrate-doctrine/ready | architecture | F05433 | non-negotiable | false | 10 |
| R10835 | Operational — substrate evaluation evaluator dispatched via on-demand CLI `sovereign substrate evaluate <alt>` | architecture | F05426 | non-negotiable | false | 10 |
| R10836 | Operational — `sovereign substrate evaluate` emits M049 trace | cross-ref M049 | F05426 | non-negotiable | false | 10 |
| R10837 | Operational — `sovereign substrate evaluate` signs results via MS003 | cross-ref selfdef MS003 | F05427 | non-negotiable | false | 10 |
| R10838 | Operational — `sovereign substrate evaluate` writes to /var/lib/sovereign-os/substrate-evaluations/<alt>-<ts>.json | architecture | F05429 | non-negotiable | false | 10 |
| R10839 | Operational — `sovereign substrate doctrine show` returns current doctrine | architecture | F05417 | non-negotiable | false | 10 |
| R10840 | Operational — `sovereign substrate doctrine history` returns prior doctrine versions | architecture | F05420 | non-negotiable | false | 10 |
| R10841 | Doctrinal preservation — operator words "Debian as Ark" verbatim in M064 doc | dump 396 + operator standing direction | F05356 | non-negotiable | false | 10 |
| R10842 | Doctrinal preservation — operator words "Debian 13 is the starting boat, not the destination" verbatim | dump 396 | F05356 | non-negotiable | false | 10 |
| R10843 | Doctrinal preservation — operator words "stay on Debian + customize the boat" verbatim | dump 397 | F05361 | non-negotiable | false | 10 |
| R10844 | Doctrinal preservation — operator words "Alternatives evaluated honestly" verbatim | dump 397 | F05376 | non-negotiable | false | 10 |
| R10845 | Doctrinal preservation — operator words "trade-offs documented either way" verbatim | dump 398 | F05394 | non-negotiable | false | 10 |
| R10846 | Doctrinal preservation — operator words "Q-016 added to seed list" verbatim | dump 398 | F05400 | non-negotiable | false | 10 |
| R10847 | Doctrinal preservation — operator words "Stays open through PR 4 survey" verbatim | dump 399 | F05401 | non-negotiable | false | 10 |
| R10848 | Doctrinal preservation — operator words "resolved at Stage Gate 2 alongside Q-001" verbatim | dump 399 | F05402 | non-negotiable | false | 10 |
| R10849 | Doctrinal preservation — verbatim quotes never paraphrased in any artifact | operator standing direction | F05417 | non-negotiable | false | 10 |
| R10850 | Doctrinal preservation — verbatim quotes layered (additive) when new dump material arrives | operator standing direction | F05425 | non-negotiable | false | 10 |
| R10851 | Doctrinal preservation — info-hub knowledge graph indexes "Debian as Ark" as second-brain entry | operator standing direction "second-brain" | F05418 | non-negotiable | false | 10 |
| R10852 | Schema — sovereign-substrate-doctrine-mirror crate schema_version "1.0.0" | cross-ref selfdef MS007 | F05419 | non-negotiable | false | 10 |
| R10853 | Schema — sovereign-substrate-doctrine-mirror crate fields: doctrine_text + alternatives_list + working_hypothesis + q016_status + decision_history | cross-ref selfdef MS007 | F05419 | non-negotiable | false | 10 |
| R10854 | Schema — mirror crate breaking change requires schema_version bump | cross-ref selfdef MS007 | F05420 | non-negotiable | false | 10 |
| R10855 | Schema — mirror crate signed via MS003 | cross-ref selfdef MS003 | F05419 | non-negotiable | false | 10 |
| R10856 | Schema — mirror crate re-exported via sovereign-os cargo workspace | cross-ref selfdef MS007 | F05419 | non-negotiable | false | 10 |
| R10857 | Performance — substrate doctrine publisher startup `<` 100ms | architecture | F05416 | non-negotiable | false | 10 |
| R10858 | Performance — substrate evaluate CLI runtime `<` 30s per alternative | architecture | F05426 | non-negotiable | false | 10 |
| R10859 | Performance — substrate doctrine show CLI `<` 50ms p95 | architecture | F05839 | non-negotiable | false | 10 |
| R10860 | Performance — substrate replay validator daily run `<` 5min on full chain | architecture | F05437 | non-negotiable | false | 10 |
| R10861 | Performance — mirror crate publication latency `<` 100ms p95 | cross-ref selfdef MS007 | F05419 | non-negotiable | false | 10 |
| R10862 | Cross-ref — M064 supplements M044 (substrate Debian 13 / Ubuntu 24) with framing + Q-016 | cross-ref M044 | F05356 | non-negotiable | false | 10 |
| R10863 | Cross-ref — M064 supplements M062 PR 4 (substrate survey SDD) with operator-stated working hypothesis | cross-ref M062 | F05366 | non-negotiable | false | 10 |
| R10864 | Cross-ref — M064 informs M063 SFIF Foundation phase (PR 4 is Foundation) | cross-ref M063 | F05366 | non-negotiable | false | 10 |
| R10865 | Cross-ref — M064 informs forthcoming M067 kernel build pipeline (customization) | cross-ref M067 (pending) | F05363 | non-negotiable | false | 10 |
| R10866 | Cross-ref — M064 informs forthcoming M068 ZFS storage architecture (customization) | cross-ref M068 (pending) | F05364 | non-negotiable | false | 10 |
| R10867 | Cross-ref — M064 informs forthcoming selfdef MS044 guardian daemon (customization) | cross-ref selfdef MS044 (pending) | F05365 | non-negotiable | false | 10 |
| R10868 | Cross-ref — M064 informs M065 Five Stage Gates (Stage Gate 2 resolves Q-016) | cross-ref M065 (pending) | F05402 | non-negotiable | false | 10 |
| R10869 | Cross-ref — M064 informs M066 Trinity Framework Genesis (hardware-SRP topology atop substrate) | cross-ref M066 (pending) | F05422 | non-negotiable | false | 10 |
| R10870 | Closing — "Debian as Ark" frame covers dump 396 verbatim | dump 396 | F05356 | non-negotiable | false | 10 |
| R10871 | Closing — working hypothesis covers dump 397 verbatim | dump 397 | F05361 | non-negotiable | false | 10 |
| R10872 | Closing — honest evaluation covers dump 397-398 verbatim | dump 397-398 | F05376 | non-negotiable | false | 10 |
| R10873 | Closing — trade-off documentation covers dump 398 verbatim | dump 398 | F05394 | non-negotiable | false | 10 |
| R10874 | Closing — Q-016 + Q-001 cover dump 398-399 verbatim | dump 398-399 | F05399 | non-negotiable | false | 10 |
| R10875 | Closing — sovereign-os catalog at 64/64 milestones | architecture | F05440 | non-negotiable | false | 10 |
| R10876 | Closing — combined ecosystem 107 milestones | architecture | F05440 | non-negotiable | false | 10 |
| R10877 | Closing — combined R-rows ~21200 | architecture | F05440 | non-negotiable | false | 10 |
| R10878 | Closing — combined enforced sub-reqs ~212000 | architecture | F05440 | non-negotiable | false | 10 |
| R10879 | Closing — every R-row carries 10 hard non-negotiable sub-requirements | operator standing direction | F05356 | non-negotiable | false | 10 |
| R10880 | Closing — M064 covers dump 396-399 verbatim; M065 (Five Stage Gates) drafting next | dump 396-399 + operator standing direction | F05440 | non-negotiable | false | 10 |

## Sub-requirements accounting

Every R-row carries 10 hard non-negotiable sub-requirements. Total enforced sub-reqs = 170 R × 10 = **1,700 sub-requirements** for M064.

## Cross-references

- **M042** — choice architecture (substrate doctrine composes with profile envelope)
- **M044** — sovereign-os substrate (Debian 13 / Ubuntu 24 — M064 supplements with framing)
- **M048** — modules map (substrate informs Base OS module)
- **M049** — observability + trace pipeline
- **M058** — hardware-aware scheduler (substrate affects kernel + scheduler integration)
- **M059** — peace machine close (sovereignty preserved across substrate evolution)
- **M062** — Macro-Arc 10-PR scaffold (M064 informs PR 4 + Stage Gate 2)
- **M063** — SFIF discipline (M064 lives in Foundation phase)
- **M065** — Five Stage Gates (pending; Stage Gate 2 resolves Q-016)
- **M067** — Custom Kernel Build Pipeline (pending; customization per working hypothesis)
- **M068** — ZFS Storage Architecture (pending; customization per working hypothesis)
- **selfdef MS003** — selfdef-signing (signs every substrate decision + doctrine version)
- **selfdef MS007** — typed-mirror crate scheme (sovereign-substrate-doctrine-mirror)
- **selfdef MS009** — replay validator (verifies substrate-decision chain integrity)
- **selfdef MS026** — observability + OCSF event emission
- **selfdef MS039** — authority levels (substrate decision is L6 Persist)
- **selfdef MS040** — six-profile authority matrix (production-profile gates for substrate change)
- **selfdef MS041** — commit authority (high-risk gates for substrate change)
- **selfdef MS044** — Guardian Daemon (pending; customization per working hypothesis)

## Schema

```
schema_version: "1.0.0"
milestone_id: M064
parent: sovereign-os
epics: 10
modules: 17
features: 85
requirements: 170
sub_requirements_per_requirement: 10
total_sub_requirements: 1700
source_dump_lines: 396-399
operator_doctrine_verbatim:
  ark_frame: "Debian 13 is the starting boat, not the destination."
  working_hypothesis: "stay on Debian + customize the boat. Alternatives evaluated honestly; trade-offs documented either way."
  q016: "distro-base reconsideration. Stays open through PR 4 survey; resolved at Stage Gate 2 alongside Q-001 (substrate tooling)."
typed_mirror_crate: sovereign-substrate-doctrine-mirror
catalog_status:
  sovereign_os: 64/64 milestones
  selfdef: 43/43 milestones
  combined: 107 milestones
```
