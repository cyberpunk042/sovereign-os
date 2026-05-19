# M057 — Data flow and lifecycle — 12-step task lifecycle

> Parent: `backlog/milestones/INDEX.md` row M057 (dump 17532–17914).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 17532–17914. Operator directive 17532: "continue" + closing 17914: "continue".
> All entries below extract verbatim. No invention.

## Epics (E0548–E0557)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0548 | Data flow + lifecycle framing — "Next layer: data flow and lifecycle. We need to describe how a real task moves through the station from user intent to durable learning"; 12-step Task Lifecycle: 1. Intake / 2. Normalize / 3. Profile Resolve / 4. Map / 5. Plan / Compile / 6. Route / 7. Execute / 8. Observe / 9. Evaluate / 10. Commit / Rollback / 11. Learn / 12. Resume / Archive | 17536–17564 |
| E0549 | Step 1 Intake — 10 task sources (Claude Code / Cline / OpenCode / local dashboard / CLI / MCP / API / scheduled automation / file watcher / human voice-text later); gateway creates 6 fields (request_id / trace_id / client_id / profile_hint / privacy_context / budget_hint) | 17568–17598 |
| E0550 | Step 2 Normalize + Step 3 Profile Resolve — Normalize converts 5 external formats (Anthropic message / OpenAI chat / MCP tool call / CLI task / GUI action) all become RuntimeRequest; "This keeps clients replaceable"; Profile Resolve determines 8 operating postures (fast / careful / private / offline / research / autonomous / experimental / production); profile resolves into 7 fields (cost limit / cloud permission / sandbox level / memory depth / oracle requirement / test requirement / human gate threshold) | 17602–17648 |
| E0551 | Step 4 Map — 4 domain-specific maps; "MAP prevents blind action"; for code: repo structure + language/framework + test commands + dependency graph + recent failures + relevant files + project policy; for research: source landscape + claim types + freshness requirements + citation needs; for GUI: screen elements + state machine + allowed actions + risk zones; for OS/admin: service state + logs + hardware pressure + rollback points + permissions | 17652–17698 |
| E0552 | Step 5 Plan/Compile + Step 6 Route — Plan/Compile produces workflow graph with 8 node types (model call / tool call / memory read / test run / policy gate / human gate / eval / commit); "Edges define dependency and order"; "The plan is not fixed forever. It can recompile after observations"; Route maps each node to hardware/model — 6 examples (draft patch→3090 scout / hard diagnosis→Blackwell oracle / memory filter→AVX cortex / file read→tool sandbox / test run→container / private final answer→local-only model / high-stakes external claim→cloud optional only if approved); routing considers 8 factors (profile + cost + latency + risk + hardware pressure + cache/KV state + model eval history + privacy) | 17702–17758 |
| E0553 | Step 7 Execute + Step 8 Observe — Execute occurs in 9 bounded environments (model server / REPL / shell / container / VM / browser / memory service / symbolic planner / policy engine); "Every execution emits trace events"; Observe captures 10 categories (stdout/stderr / exit code / files changed / network touched / tokens used / latency / GPU/CPU pressure / model output / tool output / test results); "Observation is ground truth for the workflow" | 17762–17794 |
| E0554 | Step 9 Evaluate + Step 10 Commit/Rollback — Evaluate combines 8 axes (tests / schema validation / policy compliance / trajectory quality / cost / risk / user satisfaction / oracle/verifier score); "This determines whether to continue, retry, escalate, rollback, or commit"; Commit requires evidence — for code: diff valid / tests pass or failure understood / snapshot exists / policy allows write / review gate satisfied; if not: rollback / archive branch / store failure / replan; "ZFS snapshots make this practical" | 17798–17832 |
| E0555 | Step 11 Learn — without changing weights first: store trace / update memory / update route statistics / add eval case / promote skill / adjust profile defaults / tag model failure; later: curate dataset / train LoRA / evaluate adapter / promote adapter | 17836–17858 |
| E0556 | Step 12 Resume/Archive — 9 task states (active / paused / waiting_user / waiting_tool / hibernated / completed / failed / rolled_back / archived); Resume requires 5 things (trace summary / current state / open risks / next action / staleness check) | 17862–17878 |
| E0557 | Critical Data Flow Law + End-to-End Example + closing — Law: "Text is not the system state. Text is payload inside typed state"; real state is 8 things (frames / routes / policies / memory refs / tool observations / eval results / commits / traces); "This is what makes the system programmable and continuous"; End-to-end example: User "fix failing parser test" → Intake (Claude Code → gateway) → Profile (careful_code) → Map (inspect repo, detect test runner, find parser files) → Compile (read files → run targeted test → draft patch → verify → apply → retest) → Route (3090 drafts patch, AVX filters risk/policy, Blackwell reviews patch, container runs tests) → Observe (test output, diff, changed files) → Evaluate (tests pass, no forbidden files, cost acceptable) → Commit (snapshot + apply diff + trace record) → Learn (store command, failure pattern, useful files); "That is the practical flow" | 17882–17912 |

## Modules (M00952–M00968)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00952 | 12-step lifecycle preamble — "describe how a real task moves through the station from user intent to durable learning" | 17538 | E0548 |
| M00953 | Step 1 Intake — 10 task sources + 6 gateway-created fields | 17570–17598 | E0549 |
| M00954 | Step 2 Normalize — 5 external formats → RuntimeRequest + "keeps clients replaceable" | 17602–17626 | E0550 |
| M00955 | Step 3 Profile Resolve — 8 operating postures + 7 resolved fields | 17630–17648 | E0550 |
| M00956 | Step 4 Map — 4 domain-specific maps (code/research/GUI/OS-admin) + "MAP prevents blind action" | 17652–17698 | E0551 |
| M00957 | Step 5 Plan/Compile — 8 node types + recompile-after-observations | 17702–17726 | E0552 |
| M00958 | Step 6 Route — 6 routing examples + 8 routing factors | 17730–17758 | E0552 |
| M00959 | Step 7 Execute — 9 bounded environments + "every execution emits trace events" | 17762–17776 | E0553 |
| M00960 | Step 8 Observe — 10 observation categories + "observation is ground truth" | 17780–17794 | E0553 |
| M00961 | Step 9 Evaluate — 8 evaluation axes + 5 outcome decisions | 17798–17816 | E0554 |
| M00962 | Step 10 Commit/Rollback — 5 commit-required evidence + 4 rollback steps + "ZFS snapshots make this practical" | 17820–17832 | E0554 |
| M00963 | Step 11 Learn — 7 before-weights + 4 later-with-weights | 17836–17858 | E0555 |
| M00964 | Step 12 Resume/Archive — 9 task states + 5 resume requirements | 17862–17878 | E0556 |
| M00965 | Critical Data Flow Law — "Text is not the system state. Text is payload inside typed state" | 17882 | E0557 |
| M00966 | 8 real-state elements — frames / routes / policies / memory refs / tool observations / eval results / commits / traces | 17886–17896 | E0557 |
| M00967 | End-to-end example — User "fix failing parser test" 8-step practical flow | 17900–17912 | E0557 |
| M00968 | "That is the practical flow" | 17912 | E0557 |

## Features (F04761–F04845)

| Feature ID | Phrase | Dump line | Parent module |
|---|---|---|---|
| F04761 | 12-step Task Lifecycle header — "Task Lifecycle" | 17542 | M00952 |
| F04762 | Step 1 — Intake | 17546 | M00953 |
| F04763 | Step 2 — Normalize | 17547 | M00954 |
| F04764 | Step 3 — Profile Resolve | 17548 | M00955 |
| F04765 | Step 4 — Map | 17549 | M00956 |
| F04766 | Step 5 — Plan / Compile | 17550 | M00957 |
| F04767 | Step 6 — Route | 17551 | M00958 |
| F04768 | Step 7 — Execute | 17552 | M00959 |
| F04769 | Step 8 — Observe | 17553 | M00960 |
| F04770 | Step 9 — Evaluate | 17554 | M00961 |
| F04771 | Step 10 — Commit / Rollback | 17555 | M00962 |
| F04772 | Step 11 — Learn | 17556 | M00963 |
| F04773 | Step 12 — Resume / Archive | 17557 | M00964 |
| F04774 | Intake source — Claude Code | 17574 | M00953 |
| F04775 | Intake source — Cline | 17575 | M00953 |
| F04776 | Intake source — OpenCode | 17576 | M00953 |
| F04777 | Intake source — local dashboard | 17577 | M00953 |
| F04778 | Intake source — CLI | 17578 | M00953 |
| F04779 | Intake source — MCP | 17579 | M00953 |
| F04780 | Intake source — API | 17580 | M00953 |
| F04781 | Intake source — scheduled automation | 17581 | M00953 |
| F04782 | Intake source — file watcher | 17582 | M00953 |
| F04783 | Intake source — human voice/text later | 17583 | M00953 |
| F04784 | Gateway-created — request_id + trace_id + client_id + profile_hint + privacy_context + budget_hint | 17590–17598 | M00953 |
| F04785 | Normalize — Anthropic message + OpenAI chat + MCP tool call + CLI task + GUI action → RuntimeRequest | 17606–17626 | M00954 |
| F04786 | "This keeps clients replaceable" | 17626 | M00954 |
| F04787 | Profile posture — fast + careful + private + offline + research + autonomous + experimental + production | 17632–17642 | M00955 |
| F04788 | Profile resolves into — cost limit + cloud permission + sandbox level + memory depth + oracle requirement + test requirement + human gate threshold | 17646–17654 | M00955 |
| F04789 | MAP for code — repo structure + language/framework + test commands + dependency graph + recent failures + relevant files + project policy | 17660–17672 | M00956 |
| F04790 | MAP for research — source landscape + claim types + freshness requirements + citation needs | 17676–17684 | M00956 |
| F04791 | MAP for GUI — screen elements + state machine + allowed actions + risk zones | 17688–17692 | M00956 |
| F04792 | MAP for OS/admin — service state + logs + hardware pressure + rollback points + permissions | 17694–17698 | M00956 |
| F04793 | "MAP prevents blind action" | 17698 | M00956 |
| F04794 | Node type — model call + tool call + memory read + test run + policy gate + human gate + eval + commit | 17708–17716 | M00957 |
| F04795 | "Edges define dependency and order" | 17720 | M00957 |
| F04796 | "The plan is not fixed forever. It can recompile after observations" | 17724 | M00957 |
| F04797 | Routing example — draft patch → 3090 scout | 17732 | M00958 |
| F04798 | Routing example — hard diagnosis → Blackwell oracle | 17734 | M00958 |
| F04799 | Routing example — memory filter → AVX cortex | 17736 | M00958 |
| F04800 | Routing example — file read → tool sandbox | 17738 | M00958 |
| F04801 | Routing example — test run → container | 17740 | M00958 |
| F04802 | Routing example — private final answer → local-only model | 17742 | M00958 |
| F04803 | Routing example — high-stakes external claim → cloud optional only if approved | 17744 | M00958 |
| F04804 | Routing factor — profile + cost + latency + risk + hardware pressure + cache/KV state + model eval history + privacy | 17750–17758 | M00958 |
| F04805 | Execute environment — model server + REPL + shell + container + VM + browser + memory service + symbolic planner + policy engine | 17766–17774 | M00959 |
| F04806 | "Every execution emits trace events" | 17776 | M00959 |
| F04807 | Observe — stdout/stderr + exit code + files changed + network touched + tokens used + latency + GPU/CPU pressure + model output + tool output + test results | 17784–17794 | M00960 |
| F04808 | "Observation is ground truth for the workflow" | 17794 | M00960 |
| F04809 | Evaluate combines — tests + schema validation + policy compliance + trajectory quality + cost + risk + user satisfaction + oracle/verifier score | 17802–17812 | M00961 |
| F04810 | Outcome decisions — continue + retry + escalate + rollback + commit | 17816 | M00961 |
| F04811 | Commit requires for code — diff valid + tests pass or failure understood + snapshot exists + policy allows write + review gate satisfied | 17822–17828 | M00962 |
| F04812 | If not (rollback) — rollback + archive branch + store failure + replan | 17832 | M00962 |
| F04813 | "ZFS snapshots make this practical" | 17832 | M00962 |
| F04814 | Learn (before weights) — store trace + update memory + update route statistics + add eval case + promote skill + adjust profile defaults + tag model failure | 17840–17852 | M00963 |
| F04815 | Learn (later, with weights) — curate dataset + train LoRA + evaluate adapter + promote adapter | 17856–17858 | M00963 |
| F04816 | Task state — active + paused + waiting_user + waiting_tool + hibernated + completed + failed + rolled_back + archived | 17866–17874 | M00964 |
| F04817 | Resume requires — trace summary + current state + open risks + next action + staleness check | 17878 | M00964 |
| F04818 | Critical Law — "Text is not the system state" | 17882 | M00965 |
| F04819 | Critical Law — "Text is payload inside typed state" | 17882 | M00965 |
| F04820 | Real state — frames + routes + policies + memory refs + tool observations + eval results + commits + traces | 17886–17894 | M00966 |
| F04821 | "This is what makes the system programmable and continuous" | 17896 | E0557 |
| F04822 | End-to-end User input — "fix failing parser test" | 17900 | M00967 |
| F04823 | End-to-end Intake — Claude Code request enters gateway | 17902 | M00967 |
| F04824 | End-to-end Profile — careful_code | 17904 | M00967 |
| F04825 | End-to-end Map — inspect repo, detect test runner, find parser files | 17906 | M00967 |
| F04826 | End-to-end Compile — read files → run targeted test → draft patch → verify → apply → retest | 17908 | M00967 |
| F04827 | End-to-end Route — 3090 drafts / AVX filters / Blackwell reviews / container tests | 17910 | M00967 |
| F04828 | End-to-end Observe — test output + diff + changed files | 17912 | M00967 |
| F04829 | End-to-end Evaluate — tests pass + no forbidden files + cost acceptable | 17912 | M00967 |
| F04830 | End-to-end Commit — snapshot + apply diff + trace record | 17912 | M00967 |
| F04831 | End-to-end Learn — store command + failure pattern + useful files | 17912 | M00967 |
| F04832 | "That is the practical flow" | 17912 | M00968 |
| F04833 | Cross-module — 12-step lifecycle realizes M054 Tool Interface ToolIntent→PolicyDecision→ToolExecution→ToolObservation 4-state pipeline + selfdef MS033 Phase 3 Policy and Trace 7-step model-call + 5-step tool-call trace templates | cross-ref M054 + MS033 | E0548 |
| F04834 | Cross-module — Step 1 Intake source list maps to M054 Gateway Interface 5 inputs + RuntimeRequest 9 fields | cross-ref M054 | M00953 |
| F04835 | Cross-module — Step 3 Profile Resolve maps to M054 Profile Resolver Interface 5 inputs + 10-field ResolvedProfile | cross-ref M054 | M00955 |
| F04836 | Cross-module — Step 4 Map realizes M036 MAP→SPEC→TEST→ACT→EVAL→COMMIT→LEARN methodology + M041 7-canonical-contracts MAP.json field | cross-ref M036 + M041 | M00956 |
| F04837 | Cross-module — Step 5 Plan/Compile realizes M025 Cognitive Compiler 7-input → 7-output | cross-ref M025 | M00957 |
| F04838 | Cross-module — Step 6 Route realizes M054 Router Interface + M043 Bridge Layer 8-bulk-eval-decision | cross-ref M054 + M043 | M00958 |
| F04839 | Cross-module — Step 7-8 Execute+Observe realize selfdef MS032 sandbox tiers + MS017 agent-guard + MS016 Tetragon + M048 Module 3 Container/Sandbox Fabric | cross-ref MS032 + MS017 + MS016 + M048 | M00959 + M00960 |
| F04840 | Cross-module — Step 9 Evaluate realizes M048 Module 7 Eval/Value Plane + M037 Spec/TDD evidence-driven autonomy + 10-field EvalResult | cross-ref M048 + M037 | M00961 |
| F04841 | Cross-module — Step 10 Commit/Rollback realizes M040 Hyper Feature 8 ZFS commit gate + M044 Storage Plane ZFS + selfdef MS037 filesystem boundary 6-step host import | cross-ref M040 + M044 + MS037 | M00962 |
| F04842 | Cross-module — Step 11 Learn realizes M046 LoRA foundry 6-before-training + 7-training-to-deployment | cross-ref M046 | M00963 |
| F04843 | Cross-module — Step 12 Resume/Archive realizes M047 Continuity Manager 6 primitives + 8 states + M048 Module 8 Continuity Manager | cross-ref M047 + M048 | M00964 |
| F04844 | Cross-repo binding — 12-step lifecycle schema published via MS007 doc-manifest + audit-manifest + surface-manifest typed-mirror crates (8/8 SATURATED) | cross-ref MS007 | E0557 |
| F04845 | Doctrine — 12-step lifecycle IS the operator-facing programmable + continuous workflow vocabulary; Critical Data Flow Law makes the entire architecture FRAGMENT-FREE | dump 17882–17896 | M00965 + M00966 |

## Requirements (R09521–R09690)

| Req ID | Phrase | Dump line | Parent feature | Negotiability | Layer-B metric | Priority |
|---|---|---|---|---|---|---|
| R09521 | "Next layer: data flow and lifecycle" | 17536 | E0548 | non-negotiable | false | 10 |
| R09522 | "Describe how a real task moves through the station from user intent to durable learning" | 17538 | M00952 | non-negotiable | false | 10 |
| R09523 | Lifecycle step 1 — Intake | 17546 | F04762 | non-negotiable | false | 10 |
| R09524 | Lifecycle step 2 — Normalize | 17547 | F04763 | non-negotiable | false | 10 |
| R09525 | Lifecycle step 3 — Profile Resolve | 17548 | F04764 | non-negotiable | false | 10 |
| R09526 | Lifecycle step 4 — Map | 17549 | F04765 | non-negotiable | false | 10 |
| R09527 | Lifecycle step 5 — Plan / Compile | 17550 | F04766 | non-negotiable | false | 10 |
| R09528 | Lifecycle step 6 — Route | 17551 | F04767 | non-negotiable | false | 10 |
| R09529 | Lifecycle step 7 — Execute | 17552 | F04768 | non-negotiable | false | 10 |
| R09530 | Lifecycle step 8 — Observe | 17553 | F04769 | non-negotiable | false | 10 |
| R09531 | Lifecycle step 9 — Evaluate | 17554 | F04770 | non-negotiable | false | 10 |
| R09532 | Lifecycle step 10 — Commit / Rollback | 17555 | F04771 | non-negotiable | false | 10 |
| R09533 | Lifecycle step 11 — Learn | 17556 | F04772 | non-negotiable | false | 10 |
| R09534 | Lifecycle step 12 — Resume / Archive | 17557 | F04773 | non-negotiable | false | 10 |
| R09535 | Intake source — Claude Code | 17574 | F04774 | non-negotiable | false | 10 |
| R09536 | Intake source — Cline | 17575 | F04775 | non-negotiable | false | 10 |
| R09537 | Intake source — OpenCode | 17576 | F04776 | non-negotiable | false | 10 |
| R09538 | Intake source — local dashboard | 17577 | F04777 | non-negotiable | false | 10 |
| R09539 | Intake source — CLI | 17578 | F04778 | non-negotiable | false | 10 |
| R09540 | Intake source — MCP | 17579 | F04779 | non-negotiable | false | 10 |
| R09541 | Intake source — API | 17580 | F04780 | non-negotiable | false | 10 |
| R09542 | Intake source — scheduled automation | 17581 | F04781 | non-negotiable | false | 10 |
| R09543 | Intake source — file watcher | 17582 | F04782 | non-negotiable | false | 10 |
| R09544 | Intake source — human voice/text later | 17583 | F04783 | non-negotiable | false | 10 |
| R09545 | Gateway-created — request_id | 17590 | F04784 | non-negotiable | false | 10 |
| R09546 | Gateway-created — trace_id | 17591 | F04784 | non-negotiable | false | 10 |
| R09547 | Gateway-created — client_id | 17592 | F04784 | non-negotiable | false | 10 |
| R09548 | Gateway-created — profile_hint | 17593 | F04784 | non-negotiable | false | 10 |
| R09549 | Gateway-created — privacy_context | 17594 | F04784 | non-negotiable | false | 10 |
| R09550 | Gateway-created — budget_hint | 17595 | F04784 | non-negotiable | false | 10 |
| R09551 | Normalize — Anthropic message → RuntimeRequest | 17606 | F04785 | non-negotiable | false | 10 |
| R09552 | Normalize — OpenAI chat → RuntimeRequest | 17607 | F04785 | non-negotiable | false | 10 |
| R09553 | Normalize — MCP tool call → RuntimeRequest | 17608 | F04785 | non-negotiable | false | 10 |
| R09554 | Normalize — CLI task → RuntimeRequest | 17609 | F04785 | non-negotiable | false | 10 |
| R09555 | Normalize — GUI action → RuntimeRequest | 17610 | F04785 | non-negotiable | false | 10 |
| R09556 | "This keeps clients replaceable" | 17626 | F04786 | non-negotiable | false | 10 |
| R09557 | Profile posture — fast | 17632 | F04787 | non-negotiable | false | 10 |
| R09558 | Profile posture — careful | 17633 | F04787 | non-negotiable | false | 10 |
| R09559 | Profile posture — private | 17634 | F04787 | non-negotiable | false | 10 |
| R09560 | Profile posture — offline | 17635 | F04787 | non-negotiable | false | 10 |
| R09561 | Profile posture — research | 17636 | F04787 | non-negotiable | false | 10 |
| R09562 | Profile posture — autonomous | 17637 | F04787 | non-negotiable | false | 10 |
| R09563 | Profile posture — experimental | 17638 | F04787 | non-negotiable | false | 10 |
| R09564 | Profile posture — production | 17639 | F04787 | non-negotiable | false | 10 |
| R09565 | Profile resolves — cost limit | 17646 | F04788 | non-negotiable | false | 10 |
| R09566 | Profile resolves — cloud permission | 17647 | F04788 | non-negotiable | false | 10 |
| R09567 | Profile resolves — sandbox level | 17648 | F04788 | non-negotiable | false | 10 |
| R09568 | Profile resolves — memory depth | 17649 | F04788 | non-negotiable | false | 10 |
| R09569 | Profile resolves — oracle requirement | 17650 | F04788 | non-negotiable | false | 10 |
| R09570 | Profile resolves — test requirement | 17651 | F04788 | non-negotiable | false | 10 |
| R09571 | Profile resolves — human gate threshold | 17652 | F04788 | non-negotiable | false | 10 |
| R09572 | MAP for code — repo structure | 17660 | F04789 | non-negotiable | false | 10 |
| R09573 | MAP for code — language/framework | 17661 | F04789 | non-negotiable | false | 10 |
| R09574 | MAP for code — test commands | 17662 | F04789 | non-negotiable | false | 10 |
| R09575 | MAP for code — dependency graph | 17663 | F04789 | non-negotiable | false | 10 |
| R09576 | MAP for code — recent failures | 17664 | F04789 | non-negotiable | false | 10 |
| R09577 | MAP for code — relevant files | 17665 | F04789 | non-negotiable | false | 10 |
| R09578 | MAP for code — project policy | 17666 | F04789 | non-negotiable | false | 10 |
| R09579 | MAP for research — source landscape | 17676 | F04790 | non-negotiable | false | 10 |
| R09580 | MAP for research — claim types | 17677 | F04790 | non-negotiable | false | 10 |
| R09581 | MAP for research — freshness requirements | 17678 | F04790 | non-negotiable | false | 10 |
| R09582 | MAP for research — citation needs | 17679 | F04790 | non-negotiable | false | 10 |
| R09583 | MAP for GUI — screen elements | 17688 | F04791 | non-negotiable | false | 10 |
| R09584 | MAP for GUI — state machine | 17689 | F04791 | non-negotiable | false | 10 |
| R09585 | MAP for GUI — allowed actions | 17690 | F04791 | non-negotiable | false | 10 |
| R09586 | MAP for GUI — risk zones | 17691 | F04791 | non-negotiable | false | 10 |
| R09587 | MAP for OS/admin — service state | 17694 | F04792 | non-negotiable | false | 10 |
| R09588 | MAP for OS/admin — logs | 17695 | F04792 | non-negotiable | false | 10 |
| R09589 | MAP for OS/admin — hardware pressure | 17696 | F04792 | non-negotiable | false | 10 |
| R09590 | MAP for OS/admin — rollback points | 17697 | F04792 | non-negotiable | false | 10 |
| R09591 | MAP for OS/admin — permissions | 17698 | F04792 | non-negotiable | false | 10 |
| R09592 | "MAP prevents blind action" | 17698 | F04793 | non-negotiable | false | 10 |
| R09593 | Node type — model call | 17708 | F04794 | non-negotiable | false | 10 |
| R09594 | Node type — tool call | 17709 | F04794 | non-negotiable | false | 10 |
| R09595 | Node type — memory read | 17710 | F04794 | non-negotiable | false | 10 |
| R09596 | Node type — test run | 17711 | F04794 | non-negotiable | false | 10 |
| R09597 | Node type — policy gate | 17712 | F04794 | non-negotiable | false | 10 |
| R09598 | Node type — human gate | 17713 | F04794 | non-negotiable | false | 10 |
| R09599 | Node type — eval | 17714 | F04794 | non-negotiable | false | 10 |
| R09600 | Node type — commit | 17715 | F04794 | non-negotiable | false | 10 |
| R09601 | "Edges define dependency and order" | 17720 | F04795 | non-negotiable | false | 10 |
| R09602 | "The plan is not fixed forever" | 17722 | F04796 | non-negotiable | false | 10 |
| R09603 | "It can recompile after observations" | 17724 | F04796 | non-negotiable | false | 10 |
| R09604 | Routing example — draft patch → 3090 scout | 17732 | F04797 | non-negotiable | false | 10 |
| R09605 | Routing example — hard diagnosis → Blackwell oracle | 17734 | F04798 | non-negotiable | false | 10 |
| R09606 | Routing example — memory filter → AVX cortex | 17736 | F04799 | non-negotiable | false | 10 |
| R09607 | Routing example — file read → tool sandbox | 17738 | F04800 | non-negotiable | false | 10 |
| R09608 | Routing example — test run → container | 17740 | F04801 | non-negotiable | false | 10 |
| R09609 | Routing example — private final answer → local-only model | 17742 | F04802 | non-negotiable | false | 10 |
| R09610 | Routing example — high-stakes external claim → cloud optional only if approved | 17744 | F04803 | non-negotiable | false | 10 |
| R09611 | Routing factor — profile | 17750 | F04804 | non-negotiable | false | 10 |
| R09612 | Routing factor — cost | 17751 | F04804 | non-negotiable | false | 10 |
| R09613 | Routing factor — latency | 17752 | F04804 | non-negotiable | false | 10 |
| R09614 | Routing factor — risk | 17753 | F04804 | non-negotiable | false | 10 |
| R09615 | Routing factor — hardware pressure | 17754 | F04804 | non-negotiable | false | 10 |
| R09616 | Routing factor — cache/KV state | 17755 | F04804 | non-negotiable | false | 10 |
| R09617 | Routing factor — model eval history | 17756 | F04804 | non-negotiable | false | 10 |
| R09618 | Routing factor — privacy | 17757 | F04804 | non-negotiable | false | 10 |
| R09619 | Execute env — model server | 17766 | F04805 | non-negotiable | false | 10 |
| R09620 | Execute env — REPL | 17767 | F04805 | non-negotiable | false | 10 |
| R09621 | Execute env — shell | 17768 | F04805 | non-negotiable | false | 10 |
| R09622 | Execute env — container | 17769 | F04805 | non-negotiable | false | 10 |
| R09623 | Execute env — VM | 17770 | F04805 | non-negotiable | false | 10 |
| R09624 | Execute env — browser | 17771 | F04805 | non-negotiable | false | 10 |
| R09625 | Execute env — memory service | 17772 | F04805 | non-negotiable | false | 10 |
| R09626 | Execute env — symbolic planner | 17773 | F04805 | non-negotiable | false | 10 |
| R09627 | Execute env — policy engine | 17774 | F04805 | non-negotiable | false | 10 |
| R09628 | "Every execution emits trace events" | 17776 | F04806 | non-negotiable | false | 10 |
| R09629 | Observe — stdout/stderr | 17784 | F04807 | non-negotiable | false | 10 |
| R09630 | Observe — exit code | 17785 | F04807 | non-negotiable | false | 10 |
| R09631 | Observe — files changed | 17786 | F04807 | non-negotiable | false | 10 |
| R09632 | Observe — network touched | 17787 | F04807 | non-negotiable | false | 10 |
| R09633 | Observe — tokens used | 17788 | F04807 | non-negotiable | false | 10 |
| R09634 | Observe — latency | 17789 | F04807 | non-negotiable | false | 10 |
| R09635 | Observe — GPU/CPU pressure | 17790 | F04807 | non-negotiable | false | 10 |
| R09636 | Observe — model output | 17791 | F04807 | non-negotiable | false | 10 |
| R09637 | Observe — tool output | 17792 | F04807 | non-negotiable | false | 10 |
| R09638 | Observe — test results | 17793 | F04807 | non-negotiable | false | 10 |
| R09639 | "Observation is ground truth for the workflow" | 17794 | F04808 | non-negotiable | false | 10 |
| R09640 | Evaluate — tests | 17802 | F04809 | non-negotiable | false | 10 |
| R09641 | Evaluate — schema validation | 17803 | F04809 | non-negotiable | false | 10 |
| R09642 | Evaluate — policy compliance | 17804 | F04809 | non-negotiable | false | 10 |
| R09643 | Evaluate — trajectory quality | 17805 | F04809 | non-negotiable | false | 10 |
| R09644 | Evaluate — cost | 17806 | F04809 | non-negotiable | false | 10 |
| R09645 | Evaluate — risk | 17807 | F04809 | non-negotiable | false | 10 |
| R09646 | Evaluate — user satisfaction | 17808 | F04809 | non-negotiable | false | 10 |
| R09647 | Evaluate — oracle/verifier score | 17809 | F04809 | non-negotiable | false | 10 |
| R09648 | Evaluate outcome — continue / retry / escalate / rollback / commit | 17816 | F04810 | non-negotiable | false | 10 |
| R09649 | Commit code — diff valid | 17822 | F04811 | non-negotiable | false | 10 |
| R09650 | Commit code — tests pass or failure understood | 17823 | F04811 | non-negotiable | false | 10 |
| R09651 | Commit code — snapshot exists | 17824 | F04811 | non-negotiable | false | 10 |
| R09652 | Commit code — policy allows write | 17825 | F04811 | non-negotiable | false | 10 |
| R09653 | Commit code — review gate satisfied | 17826 | F04811 | non-negotiable | false | 10 |
| R09654 | Rollback action — rollback | 17832 | F04812 | non-negotiable | false | 10 |
| R09655 | Rollback action — archive branch | 17832 | F04812 | non-negotiable | false | 10 |
| R09656 | Rollback action — store failure | 17832 | F04812 | non-negotiable | false | 10 |
| R09657 | Rollback action — replan | 17832 | F04812 | non-negotiable | false | 10 |
| R09658 | "ZFS snapshots make this practical" | 17832 | F04813 | non-negotiable | false | 10 |
| R09659 | Learn (before weights) — store trace | 17840 | F04814 | non-negotiable | false | 10 |
| R09660 | Learn (before weights) — update memory | 17841 | F04814 | non-negotiable | false | 10 |
| R09661 | Learn (before weights) — update route statistics | 17842 | F04814 | non-negotiable | false | 10 |
| R09662 | Learn (before weights) — add eval case | 17843 | F04814 | non-negotiable | false | 10 |
| R09663 | Learn (before weights) — promote skill | 17844 | F04814 | non-negotiable | false | 10 |
| R09664 | Learn (before weights) — adjust profile defaults | 17845 | F04814 | non-negotiable | false | 10 |
| R09665 | Learn (before weights) — tag model failure | 17846 | F04814 | non-negotiable | false | 10 |
| R09666 | Learn (later) — curate dataset | 17856 | F04815 | non-negotiable | false | 10 |
| R09667 | Learn (later) — train LoRA | 17857 | F04815 | non-negotiable | false | 10 |
| R09668 | Learn (later) — evaluate adapter | 17858 | F04815 | non-negotiable | false | 10 |
| R09669 | Learn (later) — promote adapter | 17858 | F04815 | non-negotiable | false | 10 |
| R09670 | Task state — active | 17866 | F04816 | non-negotiable | false | 10 |
| R09671 | Task state — paused | 17867 | F04816 | non-negotiable | false | 10 |
| R09672 | Task state — waiting_user | 17868 | F04816 | non-negotiable | false | 10 |
| R09673 | Task state — waiting_tool | 17869 | F04816 | non-negotiable | false | 10 |
| R09674 | Task state — hibernated | 17870 | F04816 | non-negotiable | false | 10 |
| R09675 | Task state — completed | 17871 | F04816 | non-negotiable | false | 10 |
| R09676 | Task state — failed | 17872 | F04816 | non-negotiable | false | 10 |
| R09677 | Task state — rolled_back | 17873 | F04816 | non-negotiable | false | 10 |
| R09678 | Task state — archived | 17874 | F04816 | non-negotiable | false | 10 |
| R09679 | Resume requires — trace summary + current state + open risks + next action + staleness check | 17878 | F04817 | non-negotiable | false | 10 |
| R09680 | Critical Data Flow Law — "Text is not the system state" | 17882 | F04818 | non-negotiable | false | 10 |
| R09681 | Critical Data Flow Law — "Text is payload inside typed state" | 17882 | F04819 | non-negotiable | false | 10 |
| R09682 | Real state — frames + routes + policies + memory refs + tool observations + eval results + commits + traces | 17886–17894 | F04820 | non-negotiable | false | 10 |
| R09683 | "This is what makes the system programmable and continuous" | 17896 | F04821 | non-negotiable | false | 10 |
| R09684 | End-to-end User — "fix failing parser test" | 17900 | F04822 | non-negotiable | false | 10 |
| R09685 | End-to-end Intake — Claude Code request enters gateway | 17902 | F04823 | non-negotiable | false | 10 |
| R09686 | End-to-end Profile — careful_code | 17904 | F04824 | non-negotiable | false | 10 |
| R09687 | End-to-end Map — inspect repo, detect test runner, find parser files | 17906 | F04825 | non-negotiable | false | 10 |
| R09688 | End-to-end Compile — read files → run targeted test → draft patch → verify → apply → retest | 17908 | F04826 | non-negotiable | false | 10 |
| R09689 | End-to-end Route + Observe + Evaluate + Commit + Learn — 3090 drafts patch / AVX filters / Blackwell reviews / container tests / observe test output diff changed files / evaluate tests pass no forbidden files cost / commit snapshot+diff+trace / learn command+pattern+files; "That is the practical flow" | 17910–17912 | F04827–F04832 | non-negotiable | false | 10 |
| R09690 | Composite — M057 (10 epics / 17 modules / 85 features / 170 reqs) catalogs 12-step Task Lifecycle (Intake / Normalize / Profile Resolve / Map / Plan-Compile / Route / Execute / Observe / Evaluate / Commit-Rollback / Learn / Resume-Archive) + Critical Data Flow Law "Text is not the system state. Text is payload inside typed state" + 8-element real state (frames + routes + policies + memory refs + tool observations + eval results + commits + traces) + 8-step End-to-End Example "fix failing parser test"; cross-module realization across all prior milestones M025/M036/M037/M040/M041/M043/M044/M046/M047/M048/M049/M054 + selfdef MS016/MS017/MS027/MS032/MS033/MS037; cross-repo binding via MS007 typed-mirror crates | dump 17532–17912 | E0548-E0557 | non-negotiable | false | 10 |

## Cross-references

- Adjacent dump-range milestones: M056 Trust boundaries (17215–17532) / M058 Hardware-aware scheduling (next; dump 17914–18268)
- 12-step lifecycle synthesizes all prior architectural milestones into the operator-facing task flow
- Critical Data Flow Law overlays M050 Design Law + M052 Vision Recap
- Selfdef integration — MS010 + MS011 + MS016 + MS017 + MS022 + MS023 + MS024 + MS025 + MS026 + MS027 + MS032 + MS033 + MS034 + MS035 + MS036 + MS037 + MS038 all realize per-step enforcement
- Cross-repo binding — MS007 surface-manifest + audit-manifest + doc-manifest typed-mirror crates publish 12-step schema across selfdef + sovereign-os
- Operator references: dump 17532–17914 (12-step lifecycle + Critical Data Flow Law + End-to-End Example)
