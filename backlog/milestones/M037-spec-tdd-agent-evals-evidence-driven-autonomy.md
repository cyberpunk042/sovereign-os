# M037 — Spec / TDD / agent evals as evidence-driven autonomy

> Parent: `backlog/milestones/INDEX.md` row M037 (dump 10712–10964).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 10712–10964.
> All entries below are extracted from the dump line range. No invention.

## Epics (E0348–E0357)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0348 | "Spec as an intelligence interface, not Spec as a prison"; mistake = "Everything must start with a rigid SPEC.md"; better architecture = "Spec is one of several control artifacts the runtime can use" | 10730–10742 |
| E0349 | 7 truth anchors — SPEC.md (intended behavior) / TESTS (executable behavior) / WORKFLOW.md (process behavior) / EVALS.yaml (quality behavior) / PROFILE.yaml (operating behavior) / MAP.json (environment behavior) / TRACE.log (observed behavior); "not locked into spec-driven development; building artifact-driven intelligence" | 10744–10756 |
| E0350 | Big Connection — 8-step clean pipeline (MAP understand env / SPEC define intended / TDD turn behavior into executable checks / Agent Evals measure trajectory + outcome / Symphony orchestrate isolated runs / Routing choose model+profile+cost / Compression make local portfolio practical / Sandboxes isolate execution + preserve sessions); methodology = Map → Specify → Test → Act → Evaluate → Commit → Learn; each phase skippable / lightenable / intensifiable by profile | 10758–10794 |
| E0351 | Goldilocks Profiles — 5 named profiles where adaptive Goldilocks becomes real (Reflex: light map / no full spec / local model / fast answer / minimal tests; Careful: map repo+env / write+update spec / generate tests / implement / run validation / oracle review; Experimental: wide branches / sandbox only / no commit / high novelty / save learnings; Production: strict spec / TDD required / property tests / security checks / human gate / rollback plan; Autonomous: issue/task driven / isolated workspace / persistent session / retry+recover / report packet) — "gives options without chaos" | 10796–10839 |
| E0352 | Why Tests Matter More Than Benchmarks — SWE-bench Verified increasingly contaminated; OpenAI recommends SWE-bench Pro for frontier measurement; SWE-bench page shows many agent scaffolds matter (not just raw model quality); lesson "Do not trust public benchmark scores as your main truth. Build local evals from your own workflows."; station needs 8 project-specific tests (unit / integration / property / snapshot / lint+type / security / performance / agent trajectory) — "that is how your system becomes yours" | 10841–10865 |
| E0353 | Spec + TDD + Agent Evals — good generated task produces 7 outputs (1 Map / 2 Spec / 3 Tests / 4 Plan / 5 Patch / 6 Eval / 7 Review Packet); matches Cameron Wolfe agent-evals framing (evaluate task trials through traces/trajectories + tool calls + environment outcomes + graders, NOT just final text) | 10867–10894 |
| E0354 | WorkItem core artifact — YAML schema (goal / profile / map_refs / spec_refs / test_refs / workflow / constraints / allowed_tools / model_policy / eval_policy / commit_policy); every client can feed it (Claude Code / OpenCode / Cline / Linear-GitHub issues / CLI / local dashboard / Anthropic-compatible API / OpenAI-compatible API); "this is how you avoid tying the system to one frontend" | 10896–10928 |
| E0355 | Where Symphony Fits — relevant because treats issue tracker as state machine + each issue as isolated workspace with restart/retry/observability; "for your system, Symphony should be a pattern, not the ceiling"; you want Symphony-style orchestration + MAP-style pre-understanding + Spec/TDD contract + adaptive profiles + local model portfolio + AVX-512 control plane + Anthropic-first gateway → "much stronger than a plain agent runner" | 10930–10946 |
| E0356 | New Design Law — 5-line law (Spec tells agent what correct means / Tests prove whether it happened / Evals judge whole trajectory / Profiles decide how much intelligence to spend / Memory learns which recipe works); "that is the proper weave" | 10948–10958 |
| E0357 | Closing — "the revolution is not 'spec-driven' alone. It is evidence-driven autonomy. Spec is one kind of evidence. Tests are another. Traces are another. Human review is another. Runtime telemetry is another. Your station should learn to combine them." | 10960–10962 |

## Modules (M00612–M00628)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00612 | Truth anchor — SPEC.md (intended behavior) | 10747 | E0349 |
| M00613 | Truth anchor — TESTS (executable behavior) | 10748 | E0349 |
| M00614 | Truth anchor — WORKFLOW.md (process behavior) | 10749 | E0349 |
| M00615 | Truth anchor — EVALS.yaml (quality behavior) | 10750 | E0349 |
| M00616 | Truth anchor — PROFILE.yaml (operating behavior) | 10751 | E0349 |
| M00617 | Truth anchor — MAP.json (environment behavior) | 10752 | E0349 |
| M00618 | Truth anchor — TRACE.log (observed behavior) | 10753 | E0349 |
| M00619 | Methodology Map → Specify → Test → Act → Evaluate → Commit → Learn (variant of M036 10-step adapted for evidence-driven autonomy) | 10791 | E0350 |
| M00620 | Goldilocks Profile — Reflex (light map / no full spec / local model / fast answer / minimal tests) | 10801–10806 | E0351 |
| M00621 | Goldilocks Profile — Careful (map repo+env / write+update spec / generate tests / implement / run validation / oracle review) | 10808–10814 | E0351 |
| M00622 | Goldilocks Profile — Experimental (wide branches / sandbox only / no commit / high novelty / save learnings) | 10816–10821 | E0351 |
| M00623 | Goldilocks Profile — Production (strict spec / TDD required / property tests / security checks / human gate / rollback plan) | 10823–10829 | E0351 |
| M00624 | Goldilocks Profile — Autonomous (issue/task driven / isolated workspace / persistent session / retry+recover / report packet) | 10831–10836 | E0351 |
| M00625 | Project-specific tests catalog — unit / integration / property / snapshot / lint+type / security / performance / agent trajectory | 10855–10862 | E0352 |
| M00626 | Generated-task output 7-step — Map / Spec / Tests / Plan / Patch / Eval / Review Packet | 10872–10891 | E0353 |
| M00627 | WorkItem schema — goal / profile / map_refs / spec_refs / test_refs / workflow / constraints / allowed_tools / model_policy / eval_policy / commit_policy | 10901–10912 | E0354 |
| M00628 | WorkItem clients — Claude Code / OpenCode / Cline / Linear-GitHub issues / CLI / local dashboard / Anthropic-compatible API / OpenAI-compatible API | 10918–10925 | E0354 |

## Features (F03061–F03145)

| F ID | Phrase | Dump line | Parent | Category | Opt-in |
|---|---|---|---|---|---|
| F03061 | Continuation framing — "Spec as an intelligence interface, not Spec as a prison" | 10730 | E0348 | composite | false |
| F03062 | Mistake to avoid — "Everything must start with a rigid SPEC.md" | 10734 | E0348 | composite | false |
| F03063 | Better architecture — "Spec is one of several control artifacts the runtime can use" | 10741 | E0348 | composite | false |
| F03064 | 7 truth anchors enumerated | 10744 | E0349 | composite | false |
| F03065 | Truth anchor — SPEC.md (intended behavior) | 10747 | M00612 | composite | true |
| F03066 | Truth anchor — TESTS (executable behavior) | 10748 | M00613 | composite | true |
| F03067 | Truth anchor — WORKFLOW.md (process behavior) | 10749 | M00614 | composite | true |
| F03068 | Truth anchor — EVALS.yaml (quality behavior) | 10750 | M00615 | composite | true |
| F03069 | Truth anchor — PROFILE.yaml (operating behavior) | 10751 | M00616 | composite | true |
| F03070 | Truth anchor — MAP.json (environment behavior) | 10752 | M00617 | composite | true |
| F03071 | Truth anchor — TRACE.log (observed behavior) | 10753 | M00618 | composite | true |
| F03072 | "Not locked into spec-driven development; building artifact-driven intelligence" | 10756 | E0349 | composite | false |
| F03073 | Pipeline source — MAP (understand environment before acting) | 10763 | E0350 | composite | false |
| F03074 | Pipeline source — SPEC (define intended behavior before building) | 10766 | E0350 | composite | false |
| F03075 | Pipeline source — TDD (turn desired behavior into executable checks) | 10769 | E0350 | composite | false |
| F03076 | Pipeline source — Agent Evals (measure trajectory and final outcome) | 10772 | E0350 | composite | false |
| F03077 | Pipeline source — Symphony (orchestrate many isolated agent runs) | 10775 | E0350 | composite | false |
| F03078 | Pipeline source — Routing (choose model/profile/cost level) | 10778 | E0350 | composite | false |
| F03079 | Pipeline source — Compression (make model portfolio practical locally) | 10781 | E0350 | composite | false |
| F03080 | Pipeline source — Sandboxes (isolate execution and preserve sessions) | 10784 | E0350 | composite | false |
| F03081 | Methodology — Map → Specify → Test → Act → Evaluate → Commit → Learn | 10791 | M00619 | composite | false |
| F03082 | Each phase can be skipped / lightened / intensified by profile | 10794 | M00619 | composite | false |
| F03083 | Goldilocks Profiles header — "where 'adaptive Goldilocks' idea becomes real" | 10798 | E0351 | composite | false |
| F03084 | Goldilocks Profile — Reflex | 10801 | M00620 | composite | true |
| F03085 | Reflex profile detail — light map | 10802 | M00620 | composite | false |
| F03086 | Reflex profile detail — no full spec | 10803 | M00620 | composite | false |
| F03087 | Reflex profile detail — local model | 10804 | M00620 | composite | false |
| F03088 | Reflex profile detail — fast answer | 10805 | M00620 | composite | false |
| F03089 | Reflex profile detail — minimal tests | 10806 | M00620 | composite | false |
| F03090 | Goldilocks Profile — Careful | 10808 | M00621 | composite | true |
| F03091 | Careful profile detail — map repo/environment | 10809 | M00621 | composite | false |
| F03092 | Careful profile detail — write/update spec | 10810 | M00621 | composite | false |
| F03093 | Careful profile detail — generate tests | 10811 | M00621 | composite | false |
| F03094 | Careful profile detail — implement | 10812 | M00621 | composite | false |
| F03095 | Careful profile detail — run validation | 10813 | M00621 | composite | false |
| F03096 | Careful profile detail — oracle review | 10814 | M00621 | composite | false |
| F03097 | Goldilocks Profile — Experimental | 10816 | M00622 | composite | true |
| F03098 | Experimental profile detail — wide branches | 10817 | M00622 | composite | false |
| F03099 | Experimental profile detail — sandbox only | 10818 | M00622 | composite | false |
| F03100 | Experimental profile detail — no commit | 10819 | M00622 | composite | false |
| F03101 | Experimental profile detail — high novelty | 10820 | M00622 | composite | false |
| F03102 | Experimental profile detail — save learnings | 10821 | M00622 | composite | false |
| F03103 | Goldilocks Profile — Production | 10823 | M00623 | composite | true |
| F03104 | Production profile detail — strict spec | 10824 | M00623 | composite | false |
| F03105 | Production profile detail — TDD required | 10825 | M00623 | composite | false |
| F03106 | Production profile detail — property tests | 10826 | M00623 | composite | false |
| F03107 | Production profile detail — security checks | 10827 | M00623 | composite | false |
| F03108 | Production profile detail — human gate | 10828 | M00623 | composite | false |
| F03109 | Production profile detail — rollback plan | 10829 | M00623 | composite | false |
| F03110 | Goldilocks Profile — Autonomous | 10831 | M00624 | composite | true |
| F03111 | Autonomous profile detail — issue/task driven | 10832 | M00624 | composite | false |
| F03112 | Autonomous profile detail — isolated workspace | 10833 | M00624 | composite | false |
| F03113 | Autonomous profile detail — persistent session | 10834 | M00624 | composite | false |
| F03114 | Autonomous profile detail — retry/recover | 10835 | M00624 | composite | false |
| F03115 | Autonomous profile detail — report packet | 10836 | M00624 | composite | false |
| F03116 | "This gives options without chaos" | 10839 | E0351 | composite | false |
| F03117 | SWE-bench Verified is increasingly contaminated (OpenAI recommendation) | 10843 | E0352 | composite | false |
| F03118 | SWE-bench Pro is recommended for frontier measurement (OpenAI) | 10843 | E0352 | composite | false |
| F03119 | Many agent scaffolds matter, not just raw model quality (SWE-bench Verified page) | 10843 | E0352 | composite | false |
| F03120 | Lesson — "Do not trust public benchmark scores as your main truth" | 10848 | E0352 | composite | false |
| F03121 | Lesson — "Build local evals from your own workflows" | 10849 | E0352 | composite | false |
| F03122 | Project-specific test — unit tests | 10855 | M00625 | composite | true |
| F03123 | Project-specific test — integration tests | 10856 | M00625 | composite | true |
| F03124 | Project-specific test — property tests | 10857 | M00625 | composite | true |
| F03125 | Project-specific test — snapshot tests | 10858 | M00625 | composite | true |
| F03126 | Project-specific test — lint/type checks | 10859 | M00625 | composite | true |
| F03127 | Project-specific test — security checks | 10860 | M00625 | composite | true |
| F03128 | Project-specific test — performance checks | 10861 | M00625 | composite | true |
| F03129 | Project-specific test — agent trajectory checks | 10862 | M00625 | composite | true |
| F03130 | "That is how your system becomes yours" | 10865 | E0352 | composite | false |
| F03131 | Generated-task output 1 — Map (What exists? What constraints? What tools? What risks?) | 10872–10873 | M00626 | composite | false |
| F03132 | Generated-task output 2 — Spec (What should be true?) | 10875–10876 | M00626 | composite | false |
| F03133 | Generated-task output 3 — Tests (How do we know it is true?) | 10878–10879 | M00626 | composite | false |
| F03134 | Generated-task output 4 — Plan (What changes are needed?) | 10881–10882 | M00626 | composite | false |
| F03135 | Generated-task output 5 — Patch (What changed?) | 10884–10885 | M00626 | composite | false |
| F03136 | Generated-task output 6 — Eval (Did it work? How expensive? What failed? What was learned?) | 10887–10888 | M00626 | composite | false |
| F03137 | Generated-task output 7 — Review Packet (Human-readable summary, diff, tests, risks, rollback) | 10890–10891 | M00626 | composite | false |
| F03138 | Matches Cameron Wolfe agent-evals framing — evaluate task trials through traces/trajectories + tool calls + environment outcomes + graders, NOT just final text | 10894 | E0353 | composite | false |
| F03139 | WorkItem schema field — goal / profile / map_refs / spec_refs / test_refs / workflow / constraints / allowed_tools / model_policy / eval_policy / commit_policy | 10901–10912 | M00627 | composite | false |
| F03140 | WorkItem consumer — Claude Code | 10918 | M00628 | composite | true |
| F03141 | WorkItem consumer — OpenCode / Cline / Linear-GitHub issues / CLI / local dashboard / Anthropic-compatible API / OpenAI-compatible API | 10919–10925 | M00628 | composite | true |
| F03142 | "How you avoid tying the system to one frontend" | 10928 | E0354 | composite | false |
| F03143 | Symphony-style + MAP + Spec/TDD + adaptive profiles + local model portfolio + AVX-512 control plane + Anthropic-first gateway = "much stronger than a plain agent runner" | 10936–10946 | E0355 | composite | false |
| F03144 | New Design Law — 5-line weave (Spec tells correct / Tests prove happen / Evals judge trajectory / Profiles decide intelligence / Memory learns recipe) | 10950–10956 | E0356 | composite | false |
| F03145 | Composite — Closing "the revolution is not 'spec-driven' alone. It is evidence-driven autonomy. Spec is one kind of evidence. Tests are another. Traces are another. Human review is another. Runtime telemetry is another. Your station should learn to combine them." | 10960–10962 | E0357 | composite | false |

## Requirements (R06121–R06290)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R06121 | "Spec as an intelligence interface, not Spec as a prison" | 10730 | F03061 | non-negotiable | false | 10 |
| R06122 | Anti-pattern — "Everything must start with a rigid SPEC.md" | 10734 | F03062 | non-negotiable | false | 10 |
| R06123 | Better architecture — "Spec is one of several control artifacts the runtime can use" | 10741 | F03063 | non-negotiable | false | 10 |
| R06124 | Multiple truth anchors supported (7) | 10744 | E0349 | non-negotiable | false | 10 |
| R06125 | Truth anchor — SPEC.md (intended behavior) | 10747 | F03065 | non-negotiable | true | 10 |
| R06126 | Truth anchor — TESTS (executable behavior) | 10748 | F03066 | non-negotiable | true | 10 |
| R06127 | Truth anchor — WORKFLOW.md (process behavior) | 10749 | F03067 | non-negotiable | true | 10 |
| R06128 | Truth anchor — EVALS.yaml (quality behavior) | 10750 | F03068 | non-negotiable | true | 10 |
| R06129 | Truth anchor — PROFILE.yaml (operating behavior) | 10751 | F03069 | non-negotiable | true | 10 |
| R06130 | Truth anchor — MAP.json (environment behavior) | 10752 | F03070 | non-negotiable | true | 10 |
| R06131 | Truth anchor — TRACE.log (observed behavior) | 10753 | F03071 | non-negotiable | true | 10 |
| R06132 | "Building artifact-driven intelligence" (not locked into spec-driven development) | 10756 | F03072 | non-negotiable | false | 10 |
| R06133 | Big Connection pipeline source — MAP | 10763 | F03073 | non-negotiable | false | 10 |
| R06134 | Big Connection pipeline source — SPEC | 10766 | F03074 | non-negotiable | false | 10 |
| R06135 | Big Connection pipeline source — TDD | 10769 | F03075 | non-negotiable | false | 10 |
| R06136 | Big Connection pipeline source — Agent Evals | 10772 | F03076 | non-negotiable | false | 10 |
| R06137 | Big Connection pipeline source — Symphony | 10775 | F03077 | non-negotiable | false | 10 |
| R06138 | Big Connection pipeline source — Routing | 10778 | F03078 | non-negotiable | false | 10 |
| R06139 | Big Connection pipeline source — Compression | 10781 | F03079 | non-negotiable | false | 10 |
| R06140 | Big Connection pipeline source — Sandboxes | 10784 | F03080 | non-negotiable | false | 10 |
| R06141 | Methodology — Map → Specify → Test → Act → Evaluate → Commit → Learn | 10791 | F03081 | non-negotiable | false | 10 |
| R06142 | Methodology — each phase can be skipped, lightened, or intensified by profile | 10794 | F03082 | non-negotiable | false | 10 |
| R06143 | Goldilocks Profile — Reflex (light map / no full spec / local model / fast answer / minimal tests) | 10801–10806 | F03084 | non-negotiable | true | 10 |
| R06144 | Reflex profile detail — light map | 10802 | F03085 | non-negotiable | false | 10 |
| R06145 | Reflex profile detail — no full spec | 10803 | F03086 | non-negotiable | false | 10 |
| R06146 | Reflex profile detail — local model | 10804 | F03087 | non-negotiable | false | 10 |
| R06147 | Reflex profile detail — fast answer | 10805 | F03088 | non-negotiable | false | 10 |
| R06148 | Reflex profile detail — minimal tests | 10806 | F03089 | non-negotiable | false | 10 |
| R06149 | Goldilocks Profile — Careful | 10808 | F03090 | non-negotiable | true | 10 |
| R06150 | Careful profile detail — map repo/environment | 10809 | F03091 | non-negotiable | false | 10 |
| R06151 | Careful profile detail — write/update spec | 10810 | F03092 | non-negotiable | false | 10 |
| R06152 | Careful profile detail — generate tests | 10811 | F03093 | non-negotiable | false | 10 |
| R06153 | Careful profile detail — implement | 10812 | F03094 | non-negotiable | false | 10 |
| R06154 | Careful profile detail — run validation | 10813 | F03095 | non-negotiable | false | 10 |
| R06155 | Careful profile detail — oracle review | 10814 | F03096 | non-negotiable | false | 10 |
| R06156 | Goldilocks Profile — Experimental | 10816 | F03097 | non-negotiable | true | 10 |
| R06157 | Experimental profile detail — wide branches | 10817 | F03098 | non-negotiable | false | 10 |
| R06158 | Experimental profile detail — sandbox only | 10818 | F03099 | non-negotiable | false | 10 |
| R06159 | Experimental profile detail — no commit | 10819 | F03100 | non-negotiable | false | 10 |
| R06160 | Experimental profile detail — high novelty | 10820 | F03101 | non-negotiable | false | 10 |
| R06161 | Experimental profile detail — save learnings | 10821 | F03102 | non-negotiable | false | 10 |
| R06162 | Goldilocks Profile — Production | 10823 | F03103 | non-negotiable | true | 10 |
| R06163 | Production profile detail — strict spec | 10824 | F03104 | non-negotiable | false | 10 |
| R06164 | Production profile detail — TDD required | 10825 | F03105 | non-negotiable | false | 10 |
| R06165 | Production profile detail — property tests | 10826 | F03106 | non-negotiable | false | 10 |
| R06166 | Production profile detail — security checks | 10827 | F03107 | non-negotiable | false | 10 |
| R06167 | Production profile detail — human gate | 10828 | F03108 | non-negotiable | false | 10 |
| R06168 | Production profile detail — rollback plan | 10829 | F03109 | non-negotiable | false | 10 |
| R06169 | Goldilocks Profile — Autonomous | 10831 | F03110 | non-negotiable | true | 10 |
| R06170 | Autonomous profile detail — issue/task driven | 10832 | F03111 | non-negotiable | false | 10 |
| R06171 | Autonomous profile detail — isolated workspace | 10833 | F03112 | non-negotiable | false | 10 |
| R06172 | Autonomous profile detail — persistent session | 10834 | F03113 | non-negotiable | false | 10 |
| R06173 | Autonomous profile detail — retry/recover | 10835 | F03114 | non-negotiable | false | 10 |
| R06174 | Autonomous profile detail — report packet | 10836 | F03115 | non-negotiable | false | 10 |
| R06175 | "Gives options without chaos" | 10839 | F03116 | non-negotiable | false | 10 |
| R06176 | SWE-bench Verified is increasingly contaminated (per OpenAI) | 10843 | F03117 | non-negotiable | false | 10 |
| R06177 | SWE-bench Pro recommended for frontier measurement | 10843 | F03118 | non-negotiable | false | 10 |
| R06178 | SWE-bench Verified shows many agent scaffolds matter, not just raw model quality | 10843 | F03119 | non-negotiable | false | 10 |
| R06179 | Doctrine — "Do not trust public benchmark scores as your main truth" | 10848 | F03120 | non-negotiable | false | 10 |
| R06180 | Doctrine — "Build local evals from your own workflows" | 10849 | F03121 | non-negotiable | false | 10 |
| R06181 | Project-specific test — unit tests | 10855 | F03122 | non-negotiable | true | 10 |
| R06182 | Project-specific test — integration tests | 10856 | F03123 | non-negotiable | true | 10 |
| R06183 | Project-specific test — property tests | 10857 | F03124 | non-negotiable | true | 10 |
| R06184 | Project-specific test — snapshot tests | 10858 | F03125 | non-negotiable | true | 10 |
| R06185 | Project-specific test — lint/type checks | 10859 | F03126 | non-negotiable | true | 10 |
| R06186 | Project-specific test — security checks | 10860 | F03127 | non-negotiable | true | 10 |
| R06187 | Project-specific test — performance checks | 10861 | F03128 | non-negotiable | true | 10 |
| R06188 | Project-specific test — agent trajectory checks | 10862 | F03129 | non-negotiable | true | 10 |
| R06189 | "That is how your system becomes yours" | 10865 | F03130 | non-negotiable | false | 10 |
| R06190 | Generated-task output 1 — Map (What exists? What constraints? What tools? What risks?) | 10872–10873 | F03131 | non-negotiable | true | 10 |
| R06191 | Generated-task output 2 — Spec (What should be true?) | 10875–10876 | F03132 | non-negotiable | true | 10 |
| R06192 | Generated-task output 3 — Tests (How do we know it is true?) | 10878–10879 | F03133 | non-negotiable | true | 10 |
| R06193 | Generated-task output 4 — Plan (What changes are needed?) | 10881–10882 | F03134 | non-negotiable | true | 10 |
| R06194 | Generated-task output 5 — Patch (What changed?) | 10884–10885 | F03135 | non-negotiable | true | 10 |
| R06195 | Generated-task output 6 — Eval (Did it work? How expensive? What failed? What was learned?) | 10887–10888 | F03136 | non-negotiable | true | 10 |
| R06196 | Generated-task output 7 — Review Packet (Human-readable summary, diff, tests, risks, rollback) | 10890–10891 | F03137 | non-negotiable | true | 10 |
| R06197 | Cameron Wolfe agent-evals framing — evaluate task trials through traces/trajectories + tool calls + environment outcomes + graders | 10894 | F03138 | non-negotiable | false | 10 |
| R06198 | WorkItem schema field — goal | 10902 | M00627 | non-negotiable | true | 10 |
| R06199 | WorkItem schema field — profile | 10903 | M00627 | non-negotiable | true | 10 |
| R06200 | WorkItem schema field — map_refs | 10904 | M00627 | non-negotiable | true | 10 |
| R06201 | WorkItem schema field — spec_refs | 10905 | M00627 | non-negotiable | true | 10 |
| R06202 | WorkItem schema field — test_refs | 10906 | M00627 | non-negotiable | true | 10 |
| R06203 | WorkItem schema field — workflow | 10907 | M00627 | non-negotiable | true | 10 |
| R06204 | WorkItem schema field — constraints | 10908 | M00627 | non-negotiable | true | 10 |
| R06205 | WorkItem schema field — allowed_tools | 10909 | M00627 | non-negotiable | true | 10 |
| R06206 | WorkItem schema field — model_policy | 10910 | M00627 | non-negotiable | true | 10 |
| R06207 | WorkItem schema field — eval_policy | 10911 | M00627 | non-negotiable | true | 10 |
| R06208 | WorkItem schema field — commit_policy | 10912 | M00627 | non-negotiable | true | 10 |
| R06209 | WorkItem consumer — Claude Code | 10918 | F03140 | non-negotiable | true | 10 |
| R06210 | WorkItem consumer — OpenCode | 10919 | F03141 | non-negotiable | true | 10 |
| R06211 | WorkItem consumer — Cline | 10920 | F03141 | non-negotiable | true | 10 |
| R06212 | WorkItem consumer — Linear/GitHub issues | 10921 | F03141 | non-negotiable | true | 10 |
| R06213 | WorkItem consumer — CLI | 10922 | F03141 | non-negotiable | true | 10 |
| R06214 | WorkItem consumer — local dashboard | 10923 | F03141 | non-negotiable | true | 10 |
| R06215 | WorkItem consumer — Anthropic-compatible API | 10924 | F03141 | non-negotiable | true | 10 |
| R06216 | WorkItem consumer — OpenAI-compatible API | 10925 | F03141 | non-negotiable | true | 10 |
| R06217 | "This is how you avoid tying the system to one frontend" | 10928 | F03142 | non-negotiable | false | 10 |
| R06218 | Symphony fits — issue tracker as state machine + each issue as isolated workspace with restart/retry/observability | 10932 | E0355 | non-negotiable | false | 10 |
| R06219 | "For your system, Symphony should be a pattern, not the ceiling" | 10932 | E0355 | non-negotiable | false | 10 |
| R06220 | You want Symphony-style orchestration | 10937 | F03143 | non-negotiable | true | 10 |
| R06221 | You want + MAP-style pre-understanding | 10938 | F03143 | non-negotiable | true | 10 |
| R06222 | You want + Spec/TDD contract | 10939 | F03143 | non-negotiable | true | 10 |
| R06223 | You want + adaptive profiles | 10940 | F03143 | non-negotiable | true | 10 |
| R06224 | You want + local model portfolio | 10941 | F03143 | non-negotiable | true | 10 |
| R06225 | You want + AVX-512 control plane | 10942 | F03143 | non-negotiable | true | 10 |
| R06226 | You want + Anthropic-first gateway | 10943 | F03143 | non-negotiable | true | 10 |
| R06227 | "Much stronger than a plain agent runner" | 10946 | F03143 | non-negotiable | false | 10 |
| R06228 | New Design Law — Spec tells the agent what correct means | 10951 | F03144 | non-negotiable | false | 10 |
| R06229 | New Design Law — Tests prove whether it happened | 10952 | F03144 | non-negotiable | false | 10 |
| R06230 | New Design Law — Evals judge the whole trajectory | 10953 | F03144 | non-negotiable | false | 10 |
| R06231 | New Design Law — Profiles decide how much intelligence to spend | 10954 | F03144 | non-negotiable | false | 10 |
| R06232 | New Design Law — Memory learns which recipe works | 10955 | F03144 | non-negotiable | false | 10 |
| R06233 | "That is the proper weave" | 10958 | F03144 | non-negotiable | false | 10 |
| R06234 | Closing — "the revolution is not 'spec-driven' alone. It is evidence-driven autonomy." | 10960 | F03145 | non-negotiable | false | 10 |
| R06235 | Closing — Spec is one kind of evidence | 10960 | F03145 | non-negotiable | false | 10 |
| R06236 | Closing — Tests are another | 10960 | F03145 | non-negotiable | false | 10 |
| R06237 | Closing — Traces are another | 10960 | F03145 | non-negotiable | false | 10 |
| R06238 | Closing — Human review is another | 10960 | F03145 | non-negotiable | false | 10 |
| R06239 | Closing — Runtime telemetry is another | 10960 | F03145 | non-negotiable | false | 10 |
| R06240 | Closing — "Your station should learn to combine them" | 10962 | F03145 | non-negotiable | false | 10 |
| R06241 | M037 integrates with M025 cognitive compiler — Methodology step Specify+Test compiles to typed DAGs | cross-ref M025 | E0350 | non-negotiable | false | 10 |
| R06242 | M037 integrates with M026 SLM swarm + RLM engine — Routing pipeline source | 10778 + cross-ref M026 | F03078 | non-negotiable | false | 10 |
| R06243 | M037 integrates with M027 Value Plane — Evals layer scores trajectory + outcome + cost + risk | 10772 + cross-ref M027 | F03076 | non-negotiable | false | 10 |
| R06244 | M037 integrates with M028 Memory OS — "Memory learns which recipe works" + save-learnings (Experimental) | 10955 + 10821 + cross-ref M028 | F03102 + F03144 | non-negotiable | false | 10 |
| R06245 | M037 integrates with M029 Computer-Use Plane — sandbox-only profile (Experimental) | 10818 + cross-ref M029 | F03099 | non-negotiable | false | 10 |
| R06246 | M037 integrates with M030 World Model Plane — Map step covers "What exists? What constraints? What tools? What risks?" | 10872–10873 + cross-ref M030 | F03131 | non-negotiable | false | 10 |
| R06247 | M037 integrates with M031 Symbolic Planning Plane — property tests + formal validation in Production profile | 10826 + cross-ref M031 | F03106 | non-negotiable | false | 10 |
| R06248 | M037 integrates with M032 Cloud Expert Plane — Routing pipeline source (model-policy field) | 10778 + 10910 + cross-ref M032 | F03078 + R06206 | non-negotiable | false | 10 |
| R06249 | M037 integrates with M033 Compatibility Gateway + M034 Anthropic-first Gateway — WorkItem consumer Claude Code / OpenCode / Cline / API-compatible | 10918–10925 + cross-ref M033 + M034 | F03140 + F03141 | non-negotiable | false | 10 |
| R06250 | M037 integrates with M035 Frontier — Goldilocks Profile reflex/careful/experimental/production/autonomous maps to M035 intelligence-budget tiers | 10796–10839 + cross-ref M035 R05799–R05803 | E0351 | non-negotiable | false | 10 |
| R06251 | M037 integrates with M036 MAP — methodology Map step + Map truth anchor + Map pipeline source | 10752 + 10763 + 10791 + cross-ref M036 | M00617 + F03073 + F03081 | non-negotiable | false | 10 |
| R06252 | Project boundary — M037 covers sovereign-os runtime methodology; selfdef MS006 functional modules MAY produce WorkItem-compatible event metadata | architecture + MS006 | E0354 | non-negotiable | false | 10 |
| R06253 | Project boundary — WorkItem schema may be carried as a typed-mirror crate (MS007) for cross-repo consumers | MS007 + SDD-038 | M00627 | non-negotiable | false | 10 |
| R06254 | Project boundary — TRACE.log content may flow into selfdef-collector-eventstream (MS002) for incident correlation (metadata only, not prompt content) | architecture + MS002 | M00618 | non-negotiable | false | 10 |
| R06255 | Goldilocks-Reflex maps to claude-jean-fast (M034 alias) | 10801 + cross-ref M034 R05664 | F03084 | non-negotiable | false | 10 |
| R06256 | Goldilocks-Careful maps to claude-jean-careful (M034 alias) | 10808 + cross-ref M034 R05666 | F03090 | non-negotiable | false | 10 |
| R06257 | Goldilocks-Experimental maps to claude-jean-sandbox (M033 profile alias) | 10816 + cross-ref M033 R05480 | F03097 | non-negotiable | false | 10 |
| R06258 | Goldilocks-Production maps to claude-jean-hybrid + jean/oracle (M033/M034 aliases) | 10823 + cross-ref M033 R05498 + M034 R05669 | F03103 | non-negotiable | false | 10 |
| R06259 | Goldilocks-Autonomous maps to claude-jean-autonomous (operator-defined alias per M035 R05904) | 10831 + cross-ref M035 R05904 | F03110 | non-negotiable | false | 10 |
| R06260 | Reflex profile — minimal map + spec / local model only / fast | 10802–10806 | F03084 | non-negotiable | false | 10 |
| R06261 | Careful profile — full Spec/TDD round-trip with oracle review | 10809–10814 | F03090 | non-negotiable | false | 10 |
| R06262 | Experimental profile — sandbox-only; no commit; high novelty | 10817–10821 | F03097 | non-negotiable | false | 10 |
| R06263 | Production profile — TDD required + property tests + security + human gate + rollback | 10825–10829 | F03103 | non-negotiable | false | 10 |
| R06264 | Autonomous profile — issue/task driven + isolated workspace + persistent session + retry/recover + report packet | 10832–10836 | F03110 | non-negotiable | false | 10 |
| R06265 | Eval is mandatory step in generated-task output (output 6) | 10887 | F03136 | non-negotiable | false | 10 |
| R06266 | Eval answers — Did it work? How expensive? What failed? What was learned? | 10888 | F03136 | non-negotiable | false | 10 |
| R06267 | Review Packet is human-readable; includes summary + diff + tests + risks + rollback | 10891 | F03137 | non-negotiable | false | 10 |
| R06268 | WorkItem allows runtime to skip / lighten / intensify methodology phases per profile | 10794 | F03082 | non-negotiable | false | 10 |
| R06269 | WorkItem.profile field selects which truth anchors are mandatory | 10903 + 10744 | M00627 | non-negotiable | false | 10 |
| R06270 | WorkItem.model_policy field encodes Routing decisions (model selection per Goldilocks Profile + cost/latency policy) | 10910 + 10778 | M00627 | non-negotiable | false | 10 |
| R06271 | WorkItem.eval_policy field encodes which evals run + which graders apply | 10911 + 10894 | M00627 | non-negotiable | false | 10 |
| R06272 | WorkItem.commit_policy field encodes human-gate / rollback-plan / promote-rules | 10912 + 10828–10829 | M00627 | non-negotiable | false | 10 |
| R06273 | "Spec is one kind of evidence" — evidence-driven autonomy doctrine | 10960 | F03145 | non-negotiable | false | 10 |
| R06274 | "Tests are another" — evidence-driven autonomy doctrine | 10960 | F03145 | non-negotiable | false | 10 |
| R06275 | "Traces are another" — evidence-driven autonomy doctrine | 10960 | F03145 | non-negotiable | false | 10 |
| R06276 | "Human review is another" — evidence-driven autonomy doctrine | 10960 | F03145 | non-negotiable | false | 10 |
| R06277 | "Runtime telemetry is another" — evidence-driven autonomy doctrine | 10960 | F03145 | non-negotiable | false | 10 |
| R06278 | Station must learn to combine all 5 evidence kinds — doctrine | 10962 | F03145 | non-negotiable | false | 10 |
| R06279 | "Building artifact-driven intelligence" — top-level architectural framing | 10756 | F03072 | non-negotiable | false | 10 |
| R06280 | Methodology is NOT a fixed pipeline — each phase profile-tunable | 10794 | F03082 | non-negotiable | false | 10 |
| R06281 | Evidence sources for Eval — local project-specific tests (not public benchmark scores) | 10847–10849 | F03120 + F03121 | non-negotiable | false | 10 |
| R06282 | Public benchmark scores — NOT primary truth | 10848 | F03120 | non-negotiable | false | 10 |
| R06283 | Local evals — built from operator's own workflows | 10849 | F03121 | non-negotiable | false | 10 |
| R06284 | Project-specific test coverage — 8 categories (unit / integration / property / snapshot / lint+type / security / performance / agent trajectory) | 10855–10862 | M00625 | non-negotiable | false | 10 |
| R06285 | Composite — M037 Spec/TDD/Agent-evals = evidence-driven autonomy; 7 truth anchors; 8-step Big Connection pipeline; 7-step methodology (Map → Specify → Test → Act → Evaluate → Commit → Learn); 5 Goldilocks profiles (Reflex / Careful / Experimental / Production / Autonomous); 8 project-specific test categories; 7-output generated-task contract (Map / Spec / Tests / Plan / Patch / Eval / Review Packet); WorkItem 11-field schema + 8 frontend consumers; New Design Law 5-line weave; closing "the revolution is evidence-driven autonomy, not 'spec-driven' alone" | 10712–10962 | E0348 + E0349 + E0350 + E0351 + E0352 + E0353 + E0354 + E0355 + E0356 + E0357 | non-negotiable | false | 10 |
| R06286 | M037 maps to M027 R04590 8-plane stack — evidence-driven autonomy is the 17th plane (extending M027 + M028 + M029 + M030 + M031 + M032 + M033 + M034 + M035 + M036) | cross-ref M027 R04590 + M028 + M029 + M030 + M031 + M032 + M033 + M034 + M035 + M036 | E0357 | non-negotiable | false | 10 |
| R06287 | M037 doctrine — "Spec tells the agent what correct means" enforces Spec-Driven Development without locking | 10951 | F03144 | non-negotiable | false | 10 |
| R06288 | M037 doctrine — "Tests prove whether it happened" enforces TDD | 10952 | F03144 | non-negotiable | false | 10 |
| R06289 | M037 doctrine — "Evals judge the whole trajectory" enforces Agent Eval discipline | 10953 | F03144 | non-negotiable | false | 10 |
| R06290 | M037 doctrine — "Profiles decide how much intelligence to spend" / "Memory learns which recipe works" — completes the evidence-driven feedback loop | 10954–10955 | F03144 | non-negotiable | false | 10 |

## Cross-references

- Adjacent dump-range milestones: M036 MAP-then-act paradigm (10378–10712) / M038 Hardware-aware AIDLC (10964–11169)
- Plane integration: M025-M036 all feed into M037 evidence-driven autonomy doctrine
- Selfdef boundary: MS006 functional modules may produce WorkItem-compatible event metadata; MS007 typed mirrors may carry WorkItem schema; TRACE.log content flows into MS002 selfdef-collector-eventstream (metadata only, not prompt content)
- Profile alignment: Goldilocks-Reflex/Careful/Experimental/Production/Autonomous maps to M033/M034 claude-jean-* aliases + M035 intelligence-budget tiers
- WorkItem 11-field schema is the canonical core artifact across all frontends (Claude Code / OpenCode / Cline / Linear-GitHub / CLI / local dashboard / Anthropic-compatible API / OpenAI-compatible API)
