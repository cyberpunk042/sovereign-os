# M065 — Five Stage Gates SG1-SG5 + ExitPlanMode checkpoint ritual

**Parent**: sovereign-os runtime — foundation governance layer
**Source**: `~/infohub/raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md` lines 321-330 (Stage-Gate Placement) + lines 79-82 (SG1 detail) + lines 113-117 (SG2 detail) + lines 167-168 (SG3 detail) + lines 217-218 (SG4 detail) + lines 281-282 (SG5 detail)
**Cross-references**: M062 (Macro-Arc 10-PR scaffold) + M063 (SFIF discipline) + M064 (Debian-as-Ark / Q-016 resolves at SG2)

## Doctrinal anchor

> "Each gate is an `ExitPlanMode`-style checkpoint where execution pauses, operator reviews, and explicitly authorizes the next phase. **No PR opens past a gate without operator sign-off.**" (dump 329-330)

## Epics (E0628-E0637)

| epic | name | source |
|---|---|---|
| E0628 | SG1 — after PR 3: structural foundation review (operator confirms repo rhythm matches selfdef) | dump 79-82, 322 |
| E0629 | SG2 — after PR 4: substrate decision (operator picks tooling + resolves Q-016 + Q-001) | dump 113-117, 323 |
| E0630 | SG3 — after PR 6: schema lock-in (schema may be revised once instances reveal gaps; locked thereafter) | dump 167-168, 324 |
| E0631 | SG4 — after PR 8: whitelabel mechanism + legal posture confirmed (optional brand identity supply) | dump 217-218, 325 |
| E0632 | SG5 — after PR 10: foundation-complete gate (authorizes Stage 2 — first actual build scripts) | dump 281-282, 326 |
| E0633 | ExitPlanMode-style checkpoint ritual — execution pauses, operator reviews, explicitly authorizes | dump 328-329 |
| E0634 | Hard rule — no PR opens past a gate without operator sign-off | dump 330 |
| E0635 | Sign-off audit trail — every gate decision recorded with timestamp + actor + rationale | architecture + M062 dump 99 |
| E0636 | Sign-off transport — signed via selfdef MS003 chain-of-trust | cross-ref selfdef MS003 |
| E0637 | Gate-blocked work — alternative work CAN proceed in parallel (per M062 parallelism axes) where dependency-permitting | M062 dump 8 |

## Modules (M01088-M01104)

| module | name | source |
|---|---|---|
| M01088 | sovereign-stage-gate-sg1 | dump 79-82, 322 |
| M01089 | sovereign-stage-gate-sg2 | dump 113-117, 323 |
| M01090 | sovereign-stage-gate-sg3 | dump 167-168, 324 |
| M01091 | sovereign-stage-gate-sg4 | dump 217-218, 325 |
| M01092 | sovereign-stage-gate-sg5 | dump 281-282, 326 |
| M01093 | sovereign-checkpoint-ritual-coordinator | dump 328-329 |
| M01094 | sovereign-gate-pre-condition-checker | architecture + M062 |
| M01095 | sovereign-gate-pause-orchestrator | dump 328 |
| M01096 | sovereign-gate-operator-review-presenter | dump 329 + cross-ref M060 |
| M01097 | sovereign-gate-authorization-collector | dump 329 + cross-ref selfdef MS003 |
| M01098 | sovereign-gate-sign-off-recorder | architecture + M062 dump 99 |
| M01099 | sovereign-gate-block-enforcer (no PR past unsigned gate) | dump 330 |
| M01100 | sovereign-gate-parallel-work-router | M062 dump 8 |
| M01101 | sovereign-gate-replay-validator | cross-ref selfdef MS009 |
| M01102 | sovereign-gate-typed-mirror | cross-ref selfdef MS007 |
| M01103 | sovereign-gate-event-emitter | cross-ref M049 + cross-ref selfdef MS026 |
| M01104 | sovereign-gate-dashboard-binding (D-00 surfaces current gate state) | cross-ref M060 |

## Features (F05441-F05525)

| feature | name | source |
|---|---|---|
| F05441 | SG1 — placement: after PR 3 merged | dump 79-82, 322 |
| F05442 | SG1 — scope: structural foundation review | dump 322 |
| F05443 | SG1 — confirms repo rhythm matches selfdef | dump 322 |
| F05444 | SG1 — authorizes substantive-SDD phase to begin (PRs 4-8) | dump 82 |
| F05445 | SG1 — sign-off recorded with timestamp + actor + rationale | architecture + M062 dump 99 |
| F05446 | SG1 — sign-off signed via selfdef MS003 | cross-ref selfdef MS003 |
| F05447 | SG1 — sign-off emits OCSF Configuration Change class 5001 + M049 trace | cross-ref M049 + selfdef MS026 |
| F05448 | SG2 — placement: after PR 4 merged | dump 113-117, 323 |
| F05449 | SG2 — scope: substrate decision (operator picks tooling) | dump 113-117, 323 |
| F05450 | SG2 — resolves Q-016 distro-base reconsideration | cross-ref M064 + dump 399 |
| F05451 | SG2 — resolves Q-001 substrate tooling | cross-ref M064 + dump 399 |
| F05452 | SG2 — no code-bearing PR proceeds until substrate locked | dump 117 |
| F05453 | SG2 — decision recorded in docs/decisions.md | dump 116 + M062 dump 99 |
| F05454 | SG2 — sign-off signed via selfdef MS003 | cross-ref selfdef MS003 |
| F05455 | SG2 — emits OCSF Configuration Change class 5001 + M049 trace | cross-ref M049 + selfdef MS026 |
| F05456 | SG3 — placement: after PR 6 merged | dump 167-168, 324 |
| F05457 | SG3 — scope: schema lock-in moment | dump 168 |
| F05458 | SG3 — schema may be revised once instances reveal gaps | dump 167 |
| F05459 | SG3 — schema locked thereafter (no further revision without operator override) | dump 168 |
| F05460 | SG3 — schema-revision policy after lock: operator-signed override only | architecture + cross-ref selfdef MS003 |
| F05461 | SG3 — sign-off emits OCSF Configuration Change class 5001 + M049 trace | cross-ref M049 + selfdef MS026 |
| F05462 | SG4 — placement: after PR 8 merged | dump 217-218, 325 |
| F05463 | SG4 — scope: whitelabel mechanism + legal posture confirmed | dump 217-218 |
| F05464 | SG4 — operator OPTIONALLY supplies actual brand identity (name + palette + logo) | dump 218 |
| F05465 | SG4 — operator MAY defer brand commit to a later PR | dump 218 |
| F05466 | SG4 — legal-obligation review (Debian trademark + DFSG + GPL attribution) | M062 PR 7 dump 188 |
| F05467 | SG4 — sign-off signed via selfdef MS003 | cross-ref selfdef MS003 |
| F05468 | SG4 — sign-off emits OCSF Configuration Change class 5001 + M049 trace | cross-ref M049 + selfdef MS026 |
| F05469 | SG5 — placement: after PR 10 merged | dump 281-282, 326 |
| F05470 | SG5 — scope: foundation-complete gate (operator reviews full 10-PR arc holistically) | dump 281 |
| F05471 | SG5 — authorizes Stage 2 (first actual build scripts) | dump 282 |
| F05472 | SG5 — confirms charter set + substrate chosen + profile schema locked with 2 conformant instances + whitelabel mechanism specified + hardware-free test harness operational | dump 281 |
| F05473 | SG5 — Stage 2 (build-script) work NEVER begins without SG5 sign-off | dump 282 |
| F05474 | SG5 — sign-off signed via selfdef MS003 | cross-ref selfdef MS003 |
| F05475 | SG5 — sign-off emits OCSF Configuration Change class 5001 + M049 trace | cross-ref M049 + selfdef MS026 |
| F05476 | Checkpoint ritual — execution pauses (CI / agents / automation all halt) | dump 328 |
| F05477 | Checkpoint ritual — operator review window opens | dump 329 |
| F05478 | Checkpoint ritual — operator either authorizes next phase or returns to ask deeper dive | dump 329 + M062 dump 115 |
| F05479 | Checkpoint ritual — "ExitPlanMode-style" semantic (per Claude Code naming convention) | dump 328 |
| F05480 | Checkpoint ritual — modeled on operator's planning-pause discipline | dump 328-329 |
| F05481 | Hard rule — no PR opens past a gate without operator sign-off | dump 330 |
| F05482 | Hard rule — automation MUST refuse to advance past unsigned gate | dump 330 + architecture |
| F05483 | Hard rule — bypassing a gate emits OCSF Detection Finding class 2004 + halts daemon | cross-ref selfdef MS026 + cross-ref M055 |
| F05484 | Hard rule — bypass attempt requires audit + remediation before continuing | cross-ref selfdef MS009 |
| F05485 | Sign-off audit — every gate decision recorded with timestamp | architecture + M062 dump 99 |
| F05486 | Sign-off audit — every gate decision recorded with actor (operator key fingerprint) | cross-ref selfdef MS003 |
| F05487 | Sign-off audit — every gate decision recorded with rationale (operator-authored string) | architecture |
| F05488 | Sign-off audit — recorded in docs/decisions.md | M062 dump 99 |
| F05489 | Sign-off audit — additional record in /var/lib/sovereign-os/stage-gates/<sg>-<ts>.json | architecture |
| F05490 | Sign-off audit — retained 365 days minimum | cross-ref selfdef MS037 + architecture |
| F05491 | Sign-off audit — retained INDEFINITELY for SG5 (foundation-complete is permanent record) | architecture + dump 281-282 |
| F05492 | Sign-off transport — signature via selfdef MS003 chain-of-trust | cross-ref selfdef MS003 |
| F05493 | Sign-off transport — operator key may be hardware-token-derived (YubiKey/TPM/smartcard) | cross-ref selfdef MS003 + cross-ref selfdef MS043 F05127 |
| F05494 | Sign-off transport — operator key rotation policy: optional, per M041 commit authority | cross-ref selfdef MS041 |
| F05495 | Sign-off transport — operator can delegate signing to deputy via signed delegation token | architecture + cross-ref selfdef MS003 |
| F05496 | Sign-off transport — delegation token TTL `<=` 24h | cross-ref selfdef MS038 |
| F05497 | Parallel work routing — per M062 parallelism axes (whitelabel / profile-schema / hardware-free) | M062 dump 8 |
| F05498 | Parallel work routing — PR 5 can proceed while PR 4 pending SG2 | M062 dump 142 |
| F05499 | Parallel work routing — PR 7 can proceed while PR 4 pending SG2 | M062 dump 193 |
| F05500 | Parallel work routing — non-dependent work continues per M058 hardware-aware scheduler | cross-ref M058 |
| F05501 | Parallel work routing — gate-blocked work transparently surfaces in D-00 main dashboard | cross-ref M060 |
| F05502 | Gate replay validator — verifies historical gate-decision chain integrity | cross-ref selfdef MS009 |
| F05503 | Gate replay validator — detects unauthorized gate skip | cross-ref selfdef MS009 + MS003 |
| F05504 | Gate replay validator — detects sign-off forgery (signature mismatch) | cross-ref selfdef MS003 |
| F05505 | Gate replay validator — emits OCSF Detection Finding class 2004 on chain break | cross-ref selfdef MS026 |
| F05506 | Gate replay validator — runs daily as systemd timer | cross-ref selfdef MS009 |
| F05507 | Gate replay validator — failures halt all new gate-affecting work | architecture |
| F05508 | Typed mirror — sovereign-stage-gates-mirror crate published under MS007 8/8 SATURATED | cross-ref selfdef MS007 |
| F05509 | Typed mirror — StageGateId enum (SG1 / SG2 / SG3 / SG4 / SG5) | cross-ref selfdef MS007 |
| F05510 | Typed mirror — StageGateState enum (Pending / OperatorReviewing / SignedOff / Bypassed) | cross-ref selfdef MS007 |
| F05511 | Typed mirror — StageGateRecord struct {gate-id, state, ts, actor, rationale, signature} | cross-ref selfdef MS007 |
| F05512 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 |
| F05513 | Typed mirror — signed via MS003 | cross-ref selfdef MS003 |
| F05514 | Event emitter — every gate state transition emits M049 13-field span | cross-ref M049 |
| F05515 | Event emitter — span includes from-state + to-state + gate-id + actor | cross-ref M049 |
| F05516 | Event emitter — span deterministic for MS009 replay | cross-ref selfdef MS009 |
| F05517 | Event emitter — every gate state transition emits OCSF Configuration Change class 5001 | cross-ref selfdef MS026 |
| F05518 | Event emitter — bypass attempts additionally emit OCSF Detection Finding class 2004 | cross-ref selfdef MS026 |
| F05519 | Dashboard binding — D-00 main dashboard surfaces current SFIF phase + active gate | cross-ref M060 + M063 |
| F05520 | Dashboard binding — D-00 main dashboard shows last SG1..SG5 sign-offs (timeline) | cross-ref M060 |
| F05521 | Dashboard binding — D-06 pending approvals surfaces pending gate sign-offs | cross-ref M060 + dump 16457 |
| F05522 | Dashboard binding — D-06 approve action signs via operator key (MS003) | cross-ref M060 + selfdef MS003 |
| F05523 | Dashboard binding — D-08 rollback points surfaces SG5 + Stage 2 commits separately | cross-ref M060 |
| F05524 | CLI binding — `sovereign stage-gate show` returns current gate state | architecture + cross-ref M060 |
| F05525 | CLI binding — `sovereign stage-gate sign-off <gate> --rationale <text>` records operator decision | architecture + cross-ref selfdef MS003 |

## Requirements (R10881-R11050)

| req | description | source | feature | priority | exception | sub-reqs |
|---|---|---|---|---|---|---|
| R10881 | Doctrinal — "Each gate is an `ExitPlanMode`-style checkpoint where execution pauses, operator reviews, and explicitly authorizes the next phase" | dump 328-329 | F05476 | non-negotiable | false | 10 |
| R10882 | Doctrinal — "No PR opens past a gate without operator sign-off" | dump 330 | F05481 | non-negotiable | false | 10 |
| R10883 | Doctrinal — 5 stage gates total: SG1, SG2, SG3, SG4, SG5 | dump 321-326 | F05441 | non-negotiable | false | 10 |
| R10884 | Doctrinal — SG1..SG5 are CHECKPOINTS (not optional bumps) | dump 328-330 | F05476 | non-negotiable | false | 10 |
| R10885 | Doctrinal — operator authority is non-delegable for primary sign-off | dump 329 + operator standing direction | F05495 | non-negotiable | false | 10 |
| R10886 | SG1 — placement: after PR 3 merged | dump 79, 322 | F05441 | non-negotiable | false | 10 |
| R10887 | SG1 — scope: structural foundation review | dump 322 | F05442 | non-negotiable | false | 10 |
| R10888 | SG1 — confirms repo rhythm matches selfdef | dump 322 | F05443 | non-negotiable | false | 10 |
| R10889 | SG1 — authorizes substantive-SDD phase (PRs 4-8) | dump 82 | F05444 | non-negotiable | false | 10 |
| R10890 | SG1 — sign-off recorded with timestamp | architecture + M062 dump 99 | F05445 | non-negotiable | false | 10 |
| R10891 | SG1 — sign-off recorded with actor (operator key fingerprint) | cross-ref selfdef MS003 | F05486 | non-negotiable | false | 10 |
| R10892 | SG1 — sign-off recorded with rationale (operator-authored string non-empty) | architecture | F05487 | non-negotiable | false | 10 |
| R10893 | SG1 — sign-off signed via selfdef MS003 | cross-ref selfdef MS003 | F05446 | non-negotiable | false | 10 |
| R10894 | SG1 — emits OCSF Configuration Change class 5001 | cross-ref selfdef MS026 | F05447 | non-negotiable | false | 10 |
| R10895 | SG1 — emits M049 trace span | cross-ref M049 | F05447 | non-negotiable | false | 10 |
| R10896 | SG2 — placement: after PR 4 merged | dump 113, 323 | F05448 | non-negotiable | false | 10 |
| R10897 | SG2 — scope: substrate decision (operator picks tooling) | dump 113-117, 323 | F05449 | non-negotiable | false | 10 |
| R10898 | SG2 — resolves Q-016 distro-base reconsideration | cross-ref M064 + dump 399 | F05450 | non-negotiable | false | 10 |
| R10899 | SG2 — resolves Q-001 substrate tooling | cross-ref M064 + dump 399 | F05451 | non-negotiable | false | 10 |
| R10900 | SG2 — no code-bearing PR proceeds until substrate locked | dump 117 | F05452 | non-negotiable | false | 10 |
| R10901 | SG2 — decision recorded in docs/decisions.md | dump 116 + M062 dump 99 | F05453 | non-negotiable | false | 10 |
| R10902 | SG2 — sign-off signed via selfdef MS003 | cross-ref selfdef MS003 | F05454 | non-negotiable | false | 10 |
| R10903 | SG2 — emits OCSF Configuration Change class 5001 | cross-ref selfdef MS026 | F05455 | non-negotiable | false | 10 |
| R10904 | SG2 — emits M049 trace span | cross-ref M049 | F05455 | non-negotiable | false | 10 |
| R10905 | SG2 — operator may ask deeper dive on top 2 instead of immediate pick | dump 115 + M062 dump 115 | F05478 | non-negotiable | false | 10 |
| R10906 | SG3 — placement: after PR 6 merged | dump 167, 324 | F05456 | non-negotiable | false | 10 |
| R10907 | SG3 — scope: schema lock-in | dump 168 | F05457 | non-negotiable | false | 10 |
| R10908 | SG3 — schema may be revised once instances reveal gaps | dump 167 | F05458 | non-negotiable | false | 10 |
| R10909 | SG3 — schema locked thereafter (no further revision without operator override) | dump 168 | F05459 | non-negotiable | false | 10 |
| R10910 | SG3 — schema-revision policy after lock: operator-signed override only | architecture + cross-ref selfdef MS003 | F05460 | non-negotiable | false | 10 |
| R10911 | SG3 — sign-off signed via selfdef MS003 | cross-ref selfdef MS003 | F05461 | non-negotiable | false | 10 |
| R10912 | SG3 — emits OCSF Configuration Change class 5001 + M049 trace | cross-ref selfdef MS026 + M049 | F05461 | non-negotiable | false | 10 |
| R10913 | SG4 — placement: after PR 8 merged | dump 217, 325 | F05462 | non-negotiable | false | 10 |
| R10914 | SG4 — scope: whitelabel mechanism + legal posture confirmed | dump 217 | F05463 | non-negotiable | false | 10 |
| R10915 | SG4 — operator OPTIONALLY supplies actual brand identity | dump 218 | F05464 | non-negotiable | false | 10 |
| R10916 | SG4 — operator MAY defer brand commit to later PR | dump 218 | F05465 | non-negotiable | false | 10 |
| R10917 | SG4 — legal-obligation review (Debian trademark + DFSG + GPL attribution) | M062 PR 7 dump 188 | F05466 | non-negotiable | false | 10 |
| R10918 | SG4 — sign-off signed via selfdef MS003 | cross-ref selfdef MS003 | F05467 | non-negotiable | false | 10 |
| R10919 | SG4 — emits OCSF Configuration Change class 5001 + M049 trace | cross-ref selfdef MS026 + M049 | F05468 | non-negotiable | false | 10 |
| R10920 | SG5 — placement: after PR 10 merged | dump 281, 326 | F05469 | non-negotiable | false | 10 |
| R10921 | SG5 — scope: foundation-complete gate (operator reviews full 10-PR arc holistically) | dump 281 | F05470 | non-negotiable | false | 10 |
| R10922 | SG5 — authorizes Stage 2 (first actual build scripts) | dump 282 | F05471 | non-negotiable | false | 10 |
| R10923 | SG5 — confirms charter set | dump 281 | F05472 | non-negotiable | false | 10 |
| R10924 | SG5 — confirms substrate chosen | dump 281 | F05472 | non-negotiable | false | 10 |
| R10925 | SG5 — confirms profile schema locked with 2 conformant instances | dump 281 | F05472 | non-negotiable | false | 10 |
| R10926 | SG5 — confirms whitelabel mechanism specified | dump 281 | F05472 | non-negotiable | false | 10 |
| R10927 | SG5 — confirms hardware-free test harness operational | dump 281 | F05472 | non-negotiable | false | 10 |
| R10928 | SG5 — Stage 2 NEVER begins without SG5 sign-off | dump 282 | F05473 | non-negotiable | false | 10 |
| R10929 | SG5 — sign-off signed via selfdef MS003 | cross-ref selfdef MS003 | F05474 | non-negotiable | false | 10 |
| R10930 | SG5 — emits OCSF Configuration Change class 5001 + M049 trace | cross-ref selfdef MS026 + M049 | F05475 | non-negotiable | false | 10 |
| R10931 | SG5 — record retained INDEFINITELY (foundation-complete is permanent record) | architecture + dump 281-282 | F05491 | non-negotiable | false | 10 |
| R10932 | Ritual — execution pauses (CI / agents / automation all halt) | dump 328 | F05476 | non-negotiable | false | 10 |
| R10933 | Ritual — operator review window opens | dump 329 | F05477 | non-negotiable | false | 10 |
| R10934 | Ritual — operator either authorizes next phase OR returns to ask deeper dive | dump 329 + M062 dump 115 | F05478 | non-negotiable | false | 10 |
| R10935 | Ritual — "ExitPlanMode-style" semantic (per Claude Code naming convention) | dump 328 | F05479 | non-negotiable | false | 10 |
| R10936 | Ritual — modeled on operator's planning-pause discipline | dump 328-329 | F05480 | non-negotiable | false | 10 |
| R10937 | Ritual — pause duration is operator-controlled (no implicit timeout) | dump 329 + operator standing direction | F05477 | non-negotiable | false | 10 |
| R10938 | Ritual — pause MUST be detectable by automation (CI halts on gate-pending state) | architecture | F05482 | non-negotiable | false | 10 |
| R10939 | Ritual — D-06 pending approvals dashboard surfaces gate-pending state | cross-ref M060 | F05521 | non-negotiable | false | 10 |
| R10940 | Hard rule — no PR opens past a gate without operator sign-off | dump 330 | F05481 | non-negotiable | false | 10 |
| R10941 | Hard rule — automation MUST refuse to advance past unsigned gate | dump 330 + architecture | F05482 | non-negotiable | false | 10 |
| R10942 | Hard rule — bypassing a gate emits OCSF Detection Finding class 2004 | cross-ref selfdef MS026 | F05483 | non-negotiable | false | 10 |
| R10943 | Hard rule — bypass attempt halts the daemon | cross-ref M055 + architecture | F05483 | non-negotiable | false | 10 |
| R10944 | Hard rule — bypass attempt requires audit + remediation before continuing | cross-ref selfdef MS009 | F05484 | non-negotiable | false | 10 |
| R10945 | Hard rule — bypass attempt logged separately at /var/log/sovereign-os/gate-bypass/ | architecture | F05484 | non-negotiable | false | 10 |
| R10946 | Audit — every gate decision recorded with timestamp | architecture | F05485 | non-negotiable | false | 10 |
| R10947 | Audit — every gate decision recorded with actor (operator key fingerprint) | cross-ref selfdef MS003 | F05486 | non-negotiable | false | 10 |
| R10948 | Audit — every gate decision recorded with rationale (operator-authored non-empty string) | architecture | F05487 | non-negotiable | false | 10 |
| R10949 | Audit — recorded in docs/decisions.md | M062 dump 99 | F05488 | non-negotiable | false | 10 |
| R10950 | Audit — additional record in /var/lib/sovereign-os/stage-gates/<sg>-<ts>.json | architecture | F05489 | non-negotiable | false | 10 |
| R10951 | Audit — retained 365 days minimum for SG1..SG4 | cross-ref selfdef MS037 + architecture | F05490 | non-negotiable | false | 10 |
| R10952 | Audit — retained INDEFINITELY for SG5 (foundation-complete) | architecture | F05491 | non-negotiable | false | 10 |
| R10953 | Audit — operator can query gate history via `sovereign stage-gate history` | architecture | F05524 | non-negotiable | false | 10 |
| R10954 | Audit — gate history exposed via MS007 sovereign-stage-gates-mirror | cross-ref selfdef MS007 | F05508 | non-negotiable | false | 10 |
| R10955 | Audit — gate-history immutable (append-only) | cross-ref selfdef MS009 + architecture | F05485 | non-negotiable | false | 10 |
| R10956 | Sign-off transport — signature via selfdef MS003 chain-of-trust | cross-ref selfdef MS003 | F05492 | non-negotiable | false | 10 |
| R10957 | Sign-off transport — operator key may be hardware-token-derived (YubiKey/TPM/smartcard) | cross-ref selfdef MS003 + cross-ref selfdef MS043 F05127 | F05493 | non-negotiable | false | 10 |
| R10958 | Sign-off transport — operator key rotation policy per M041 commit authority | cross-ref selfdef MS041 | F05494 | non-negotiable | false | 10 |
| R10959 | Sign-off transport — operator can delegate signing to deputy via signed delegation token | architecture + cross-ref selfdef MS003 | F05495 | non-negotiable | false | 10 |
| R10960 | Sign-off transport — delegation token TTL `<=` 24h | cross-ref selfdef MS038 | F05496 | non-negotiable | false | 10 |
| R10961 | Sign-off transport — delegation token records original operator + deputy + scope | architecture + cross-ref selfdef MS003 | F05495 | non-negotiable | false | 10 |
| R10962 | Sign-off transport — delegation token revocable | cross-ref selfdef MS035 + MS038 | F05495 | non-negotiable | false | 10 |
| R10963 | Sign-off transport — delegation emits OCSF Audit Activity class 1003 | cross-ref selfdef MS026 | F05495 | non-negotiable | false | 10 |
| R10964 | Sign-off transport — SG5 sign-off NEVER delegable (operator-only) | architecture + operator standing direction | F05495 | non-negotiable | false | 10 |
| R10965 | Sign-off transport — SG4 sign-off requires operator OR oracle-or-human gate per MS041 | cross-ref selfdef MS041 | F05495 | non-negotiable | false | 10 |
| R10966 | Parallel work — per M062 parallelism axes (whitelabel / profile-schema / hardware-free) | M062 dump 8 | F05497 | non-negotiable | false | 10 |
| R10967 | Parallel work — PR 5 can proceed while PR 4 pending SG2 | M062 dump 142 | F05498 | non-negotiable | false | 10 |
| R10968 | Parallel work — PR 7 can proceed while PR 4 pending SG2 | M062 dump 193 | F05499 | non-negotiable | false | 10 |
| R10969 | Parallel work — non-dependent work continues per M058 hardware-aware scheduler | cross-ref M058 | F05500 | non-negotiable | false | 10 |
| R10970 | Parallel work — gate-blocked work transparently surfaces in D-00 main dashboard | cross-ref M060 | F05501 | non-negotiable | false | 10 |
| R10971 | Parallel work — operator can see which work is gate-blocked vs gate-independent | cross-ref M060 | F05501 | non-negotiable | false | 10 |
| R10972 | Parallel work — gate-blocked PRs labeled with `gate-blocked:<sg>` GitHub label | architecture | F05501 | non-negotiable | false | 10 |
| R10973 | Parallel work — gate-independent PRs proceed through normal review | architecture | F05500 | non-negotiable | false | 10 |
| R10974 | Parallel work — gate-blocked PR auto-merges on gate sign-off if all other approvals present | architecture | F05500 | non-negotiable | false | 10 |
| R10975 | Replay validator — verifies historical gate-decision chain integrity | cross-ref selfdef MS009 | F05502 | non-negotiable | false | 10 |
| R10976 | Replay validator — detects unauthorized gate skip | cross-ref selfdef MS009 + MS003 | F05503 | non-negotiable | false | 10 |
| R10977 | Replay validator — detects sign-off forgery (signature mismatch) | cross-ref selfdef MS003 | F05504 | non-negotiable | false | 10 |
| R10978 | Replay validator — emits OCSF Detection Finding class 2004 on chain break | cross-ref selfdef MS026 | F05505 | non-negotiable | false | 10 |
| R10979 | Replay validator — runs daily as systemd timer | cross-ref selfdef MS009 | F05506 | non-negotiable | false | 10 |
| R10980 | Replay validator — failures halt all new gate-affecting work | architecture | F05507 | non-negotiable | false | 10 |
| R10981 | Typed mirror — sovereign-stage-gates-mirror published under MS007 8/8 SATURATED | cross-ref selfdef MS007 | F05508 | non-negotiable | false | 10 |
| R10982 | Typed mirror — StageGateId enum (SG1 / SG2 / SG3 / SG4 / SG5) | cross-ref selfdef MS007 | F05509 | non-negotiable | false | 10 |
| R10983 | Typed mirror — StageGateState enum (Pending / OperatorReviewing / SignedOff / Bypassed) | cross-ref selfdef MS007 | F05510 | non-negotiable | false | 10 |
| R10984 | Typed mirror — StageGateRecord struct {gate-id, state, ts, actor, rationale, signature} | cross-ref selfdef MS007 | F05511 | non-negotiable | false | 10 |
| R10985 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 | F05512 | non-negotiable | false | 10 |
| R10986 | Typed mirror — signed via MS003 | cross-ref selfdef MS003 | F05513 | non-negotiable | false | 10 |
| R10987 | Typed mirror — re-exported via sovereign-os cargo workspace | cross-ref selfdef MS007 | F05508 | non-negotiable | false | 10 |
| R10988 | Typed mirror — no_std friendly | architecture | F05508 | non-negotiable | false | 10 |
| R10989 | Typed mirror — serde + bincode derives present | architecture | F05508 | non-negotiable | false | 10 |
| R10990 | Typed mirror — schema-breaking changes require schema_version bump | architecture + cross-ref selfdef MS007 | F05512 | non-negotiable | false | 10 |
| R10991 | Event emitter — every gate state transition emits M049 13-field span | cross-ref M049 | F05514 | non-negotiable | false | 10 |
| R10992 | Event emitter — span includes from-state + to-state + gate-id + actor | cross-ref M049 | F05515 | non-negotiable | false | 10 |
| R10993 | Event emitter — span deterministic for MS009 replay | cross-ref selfdef MS009 | F05516 | non-negotiable | false | 10 |
| R10994 | Event emitter — every gate state transition emits OCSF Configuration Change class 5001 | cross-ref selfdef MS026 | F05517 | non-negotiable | false | 10 |
| R10995 | Event emitter — bypass attempts additionally emit OCSF Detection Finding class 2004 | cross-ref selfdef MS026 | F05518 | non-negotiable | false | 10 |
| R10996 | Dashboard — D-00 main dashboard surfaces current SFIF phase + active gate | cross-ref M060 + M063 | F05519 | non-negotiable | false | 10 |
| R10997 | Dashboard — D-00 main dashboard shows last SG1..SG5 sign-offs (timeline) | cross-ref M060 | F05520 | non-negotiable | false | 10 |
| R10998 | Dashboard — D-06 pending approvals surfaces pending gate sign-offs | cross-ref M060 | F05521 | non-negotiable | false | 10 |
| R10999 | Dashboard — D-06 approve action signs via operator key (MS003) | cross-ref M060 + selfdef MS003 | F05522 | non-negotiable | false | 10 |
| R11000 | Dashboard — D-08 rollback points surfaces SG5 + Stage 2 commits separately | cross-ref M060 | F05523 | non-negotiable | false | 10 |
| R11001 | CLI — `sovereign stage-gate show` returns current gate state + history | architecture + cross-ref M060 | F05524 | non-negotiable | false | 10 |
| R11002 | CLI — `sovereign stage-gate sign-off <gate> --rationale <text>` records operator decision | architecture + cross-ref selfdef MS003 | F05525 | non-negotiable | false | 10 |
| R11003 | CLI — `sovereign stage-gate sign-off` requires operator MS003 signature | cross-ref selfdef MS003 | F05525 | non-negotiable | false | 10 |
| R11004 | CLI — `sovereign stage-gate sign-off` emits M049 trace + OCSF Configuration Change | cross-ref M049 + selfdef MS026 | F05514 | non-negotiable | false | 10 |
| R11005 | CLI — `sovereign stage-gate history --gate <sg>` returns gate decision history | architecture | F05524 | non-negotiable | false | 10 |
| R11006 | CLI — `sovereign stage-gate delegate <gate> --to <deputy>` issues delegation token | architecture + cross-ref selfdef MS003 | F05495 | non-negotiable | false | 10 |
| R11007 | CLI — `sovereign stage-gate revoke-delegation <token-id>` revokes delegation | architecture + cross-ref selfdef MS035 | F05496 | non-negotiable | false | 10 |
| R11008 | CLI — `sovereign stage-gate replay-verify` runs replay validator on demand | cross-ref selfdef MS009 | F05502 | non-negotiable | false | 10 |
| R11009 | CLI — all stage-gate subcommands emit M049 trace | cross-ref M049 | F05514 | non-negotiable | false | 10 |
| R11010 | CLI — all stage-gate subcommands available with --json flag | architecture | F05524 | non-negotiable | false | 10 |
| R11011 | Performance — gate state transition latency `<` 100ms p95 | architecture | F05485 | non-negotiable | false | 10 |
| R11012 | Performance — gate replay validator daily run `<` 10s | cross-ref selfdef MS009 | F05502 | non-negotiable | false | 10 |
| R11013 | Performance — gate dashboard render `<` 200ms p95 | cross-ref M060 | F05519 | non-negotiable | false | 10 |
| R11014 | Performance — mirror crate publication latency `<` 100ms p95 | cross-ref selfdef MS007 | F05508 | non-negotiable | false | 10 |
| R11015 | Telemetry — gate sign-off count emitted via M049 | cross-ref M049 | F05485 | non-negotiable | false | 10 |
| R11016 | Telemetry — gate pause duration (operator review time) histograms via M049 | cross-ref M049 | F05477 | non-negotiable | false | 10 |
| R11017 | Telemetry — gate bypass attempt count emitted via M049 (high-priority alert) | cross-ref M049 + selfdef MS026 | F05483 | non-negotiable | false | 10 |
| R11018 | Telemetry — gate delegation count emitted via M049 | cross-ref M049 | F05495 | non-negotiable | false | 10 |
| R11019 | Telemetry — gate replay validator pass-rate emitted via M049 | cross-ref M049 | F05502 | non-negotiable | false | 10 |
| R11020 | Boundary — sovereign-os owns gate enforcement | architecture + operator standing direction | F05481 | non-negotiable | false | 10 |
| R11021 | Boundary — selfdef MS007 mirror exports gate state read-only to dashboards | cross-ref selfdef MS007 | F05508 | non-negotiable | false | 10 |
| R11022 | Boundary — info-hub knowledge layer treats gate state as read-only context | operator standing direction | F05519 | non-negotiable | false | 10 |
| R11023 | Boundary — gate enforcement never mutates selfdef directly | operator standing direction | F05481 | non-negotiable | false | 10 |
| R11024 | Boundary — gate enforcement never mutates info-hub directly | operator standing direction | F05481 | non-negotiable | false | 10 |
| R11025 | Composition — gates compose with M063 SFIF phase transitions (SG1=>Foundation, SG4=>Infra-begin, SG5=>Infra-continue) | cross-ref M063 | F05519 | non-negotiable | false | 10 |
| R11026 | Composition — gates compose with selfdef MS040 production-profile L5 Commit gating | cross-ref selfdef MS040 | F05525 | non-negotiable | false | 10 |
| R11027 | Composition — gates compose with selfdef MS041 high-risk commit triple-gate (snapshot + test/eval + oracle-or-human) | cross-ref selfdef MS041 | F05525 | non-negotiable | false | 10 |
| R11028 | Composition — gates compose with M064 Q-016 (SG2 resolves Q-016 + Q-001) | cross-ref M064 | F05450 | non-negotiable | false | 10 |
| R11029 | Operational — gate coordinator runs as systemd unit sovereign-stage-gates.service | architecture | F05493 | non-negotiable | false | 10 |
| R11030 | Operational — gate coordinator emits readiness probe at /run/sovereign-stage-gates/ready | architecture | F05485 | non-negotiable | false | 10 |
| R11031 | Operational — gate coordinator honors SIGHUP for config reload | architecture | F05485 | non-negotiable | false | 10 |
| R11032 | Operational — gate coordinator graceful drain on shutdown | architecture | F05485 | non-negotiable | false | 10 |
| R11033 | Operational — gate coordinator refuses to start with chain-break detected | cross-ref selfdef MS009 | F05507 | non-negotiable | false | 10 |
| R11034 | Operational — gate coordinator refuses to start with missing MS003 keys | cross-ref selfdef MS003 | F05492 | non-negotiable | false | 10 |
| R11035 | Doctrinal preservation — operator words "No PR opens past a gate without operator sign-off" verbatim | dump 330 | F05481 | non-negotiable | false | 10 |
| R11036 | Doctrinal preservation — operator words "ExitPlanMode-style checkpoint" verbatim | dump 328 | F05479 | non-negotiable | false | 10 |
| R11037 | Doctrinal preservation — operator words "execution pauses, operator reviews, and explicitly authorizes" verbatim | dump 329 | F05476 | non-negotiable | false | 10 |
| R11038 | Doctrinal preservation — verbatim quotes never paraphrased | operator standing direction | F05481 | non-negotiable | false | 10 |
| R11039 | Doctrinal preservation — info-hub knowledge graph indexes stage gates as second-brain entries | operator standing direction "second-brain" | F05519 | non-negotiable | false | 10 |
| R11040 | Closing — 5 gates SG1..SG5 cover dump 321-330 verbatim | dump 321-330 | F05441 | non-negotiable | false | 10 |
| R11041 | Closing — checkpoint ritual covers dump 328-329 verbatim | dump 328-329 | F05476 | non-negotiable | false | 10 |
| R11042 | Closing — hard rule covers dump 330 verbatim | dump 330 | F05481 | non-negotiable | false | 10 |
| R11043 | Closing — SG5 indefinitely-retained foundation-complete record | dump 281-282 + architecture | F05491 | non-negotiable | false | 10 |
| R11044 | Closing — sovereign-os catalog at 65/65 milestones | architecture | F05441 | non-negotiable | false | 10 |
| R11045 | Closing — combined ecosystem 108 milestones | architecture | F05441 | non-negotiable | false | 10 |
| R11046 | Closing — combined R-rows ~21370 | architecture | F05441 | non-negotiable | false | 10 |
| R11047 | Closing — combined enforced sub-reqs ~213700 | architecture | F05441 | non-negotiable | false | 10 |
| R11048 | Closing — every R-row carries 10 hard non-negotiable sub-requirements | operator standing direction | F05441 | non-negotiable | false | 10 |
| R11049 | Closing — sovereignty preserved (peace machine axiom retained throughout gate model) | cross-ref M059 + operator standing direction | F05441 | non-negotiable | false | 10 |
| R11050 | Closing — M065 covers dump 321-330 verbatim; M066 Trinity Framework Genesis next | dump 321-330 + operator standing direction | F05441 | non-negotiable | false | 10 |

## Sub-requirements accounting

Every R-row carries 10 hard non-negotiable sub-requirements. Total = 170 R × 10 = **1,700 sub-requirements** for M065.

## Cross-references

- **M042** — choice architecture
- **M048** — modules map
- **M049** — observability + trace pipeline (gate transitions emit traces)
- **M055** — failure modes (gate bypass triggers halt protocol)
- **M058** — hardware-aware scheduler (parallel work routing)
- **M059** — peace machine close (sovereignty preserved)
- **M060** — cockpit + dashboards (D-00 surfaces gate state; D-06 surfaces pending; D-08 rollback)
- **M062** — Macro-Arc 10-PR scaffold (defines PR placement around each gate)
- **M063** — SFIF discipline (gates transition SFIF phases)
- **M064** — Debian-as-Ark + Q-016 (SG2 resolves Q-016)
- **M066** — Trinity Framework Genesis (pending)
- **selfdef MS003** — selfdef-signing (signs every gate sign-off + delegation token)
- **selfdef MS007** — typed-mirror crate scheme (sovereign-stage-gates-mirror)
- **selfdef MS009** — replay validator
- **selfdef MS026** — observability + OCSF event emission
- **selfdef MS035** — capability tokens (delegation token revocation)
- **selfdef MS038** — network boundary (delegation token TTL)
- **selfdef MS040** — six-profile authority matrix
- **selfdef MS041** — commit authority (high-risk gate composition)
- **selfdef MS043** — IPS operator surface (CLI integration)

## Schema

```
schema_version: "1.0.0"
milestone_id: M065
parent: sovereign-os
epics: 10
modules: 17
features: 85
requirements: 170
sub_requirements_per_requirement: 10
total_sub_requirements: 1700
source_dump_lines:
  - 321-330 (placement summary)
  - 79-82 (SG1 detail)
  - 113-117 (SG2 detail)
  - 167-168 (SG3 detail)
  - 217-218 (SG4 detail)
  - 281-282 (SG5 detail)
stage_gates:
  SG1: after PR 3 (structural foundation review)
  SG2: after PR 4 (substrate decision; Q-016 + Q-001 resolved)
  SG3: after PR 6 (schema lock-in)
  SG4: after PR 8 (whitelabel mechanism + legal posture)
  SG5: after PR 10 (foundation-complete; authorizes Stage 2)
checkpoint_ritual: ExitPlanMode-style
hard_rule: "No PR opens past a gate without operator sign-off"
typed_mirror_crate: sovereign-stage-gates-mirror
catalog_status:
  sovereign_os: 65/65 milestones
  selfdef: 43/43 milestones
  combined: 108 milestones
```
