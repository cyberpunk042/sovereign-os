# M024 — Adaptive programming — profiles as reward weights

> Parent: `backlog/milestones/INDEX.md` row M024 (dump 6672–7000).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 6672–7000.
> All entries below are extracted from the dump line range. No invention.

## Epics (E0218–E0227)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0218 | Adaptive programming — system learns which recipe/model/workflow/tool strategy fits the moment | 6687 |
| E0219 | Research substrate — DSPy programs+optimizers / MIPRO-style optimizers / LangSmith evals / Promptfoo / OpenAI evals frame as turning workflow objectives into measured behavior | 6691–6695 |
| E0220 | Principle — Options without evals are chaos; profiles without adaptation are presets; flexibility becomes intelligence only when measured | 6697–6703 |
| E0221 | Adaptive Profiles — parameterized recipes (code_repair example: scout_width / oracle_threshold / test_required / human_gate_risk / retrieval_depth / speculation_depth / grammar_strictness) | 6705–6723 |
| E0222 | Profile registry — 10 named living-policy profiles (fast / careful / cheap / private / risky-sandbox / research-heavy / code-safe / creative / deterministic / long-context) | 6725–6738 |
| E0223 | Internal weighting set — 9 weighting axes (latency / quality / cost-energy / risk / oracle-usage / tool-freedom / memory-aggressiveness / branch-width / verification-depth) | 6740–6752 |
| E0224 | The Intelligence Knob — 6-tier intelligence budget per task (reflex / normal / deliberate / research / autonomous / scientific) | 6754–6789 |
| E0225 | Compiler mental model — 9-stage pipeline (user intent → task classifier → constraints → recipe selection → model routing → workflow graph → capability plan → execution → eval → memory update) | 6791–6816 |
| E0226 | 5 named Registries — Model / Tool / Recipe / Memory / Eval | 6817–6838 |
| E0227 | Adaptive router + evals-as-fitness + AVX-512 plan selector + programming interface + self-improvement loop + principle (Profiles are choices / Recipes are programs / Evals are reality / Telemetry is sensation / Memory is experience / Policy is character / Routing is intelligence) | 6840–6998 |

## Modules (M00389–M00405)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00389 | Adaptive recipe schema — parameters block (e.g. `code_repair` with 7 tunable parameters) | 6712–6721 | E0221 |
| M00390 | Profile registry — 10 living-policy entries | 6727–6738 | E0222 |
| M00391 | 9-axis weighting set per profile | 6743–6752 | E0223 |
| M00392 | Intelligence budget tier — reflex | 6759–6761 | E0224 |
| M00393 | Intelligence budget tier — normal | 6762–6764 | E0224 |
| M00394 | Intelligence budget tier — deliberate | 6765–6767 | E0224 |
| M00395 | Intelligence budget tier — research | 6768–6770 | E0224 |
| M00396 | Intelligence budget tier — autonomous | 6771–6773 | E0224 |
| M00397 | Intelligence budget tier — scientific | 6774–6776 | E0224 |
| M00398 | Compiler pipeline 9-stage — user-intent → task-classifier → constraints → recipe → routing → workflow-graph → capability-plan → execution → eval → memory-update | 6795–6806 | E0225 |
| M00399 | Model Registry — name / size / modality / context / speed / quality / memory cost / backend / trust | 6822–6824 | E0226 |
| M00400 | Tool Registry — schema / capabilities / side effects / sandbox tier / success stats | 6825–6827 | E0226 |
| M00401 | Recipe Registry — workflow graph / defaults / tunable parameters / eval suite | 6828–6830 | E0226 |
| M00402 | Memory Registry — sources / freshness / trust / embeddings / bitsets / replay refs | 6831–6833 | E0226 |
| M00403 | Eval Registry — test sets / assertions / metrics / failure cases / regression baselines | 6834–6836 | E0226 |
| M00404 | Adaptive router 11-input / 7-output contract | 6842–6868 | E0227 |
| M00405 | AVX-512 vectorized plan selector — 9-field candidate plan + 5-field eligibility mask + 6-term utility score formula | 6895–6935 | E0227 |

## Features (F01956–F02040)

| F ID | Phrase | Dump line | Parent module | Category | Opt-in |
|---|---|---|---|---|---|
| F01956 | Adaptive recipe — `code_repair` parameter `scout_width` | 6714 | M00389 | profile | true |
| F01957 | Adaptive recipe — `code_repair` parameter `oracle_threshold` | 6715 | M00389 | profile | true |
| F01958 | Adaptive recipe — `code_repair` parameter `test_required` | 6716 | M00389 | profile | true |
| F01959 | Adaptive recipe — `code_repair` parameter `human_gate_risk` | 6717 | M00389 | profile | true |
| F01960 | Adaptive recipe — `code_repair` parameter `retrieval_depth` | 6718 | M00389 | profile | true |
| F01961 | Adaptive recipe — `code_repair` parameter `speculation_depth` | 6719 | M00389 | profile | true |
| F01962 | Adaptive recipe — `code_repair` parameter `grammar_strictness` | 6720 | M00389 | profile | true |
| F01963 | Profile — `fast` | 6728 | M00390 | mode | true |
| F01964 | Profile — `careful` | 6729 | M00390 | mode | true |
| F01965 | Profile — `cheap` | 6730 | M00390 | mode | true |
| F01966 | Profile — `private` | 6731 | M00390 | mode | true |
| F01967 | Profile — `risky-sandbox` | 6732 | M00390 | mode | true |
| F01968 | Profile — `research-heavy` | 6733 | M00390 | mode | true |
| F01969 | Profile — `code-safe` | 6734 | M00390 | mode | true |
| F01970 | Profile — `creative` | 6735 | M00390 | mode | true |
| F01971 | Profile — `deterministic` | 6736 | M00390 | mode | true |
| F01972 | Profile — `long-context` | 6737 | M00390 | mode | true |
| F01973 | Weighting axis — `latency_weight` | 6744 | M00391 | profile | true |
| F01974 | Weighting axis — `quality_weight` | 6745 | M00391 | profile | true |
| F01975 | Weighting axis — `cost_energy_weight` | 6746 | M00391 | profile | true |
| F01976 | Weighting axis — `risk_weight` | 6747 | M00391 | profile | true |
| F01977 | Weighting axis — `oracle_usage_weight` | 6748 | M00391 | profile | true |
| F01978 | Weighting axis — `tool_freedom` | 6749 | M00391 | profile | true |
| F01979 | Weighting axis — `memory_aggressiveness` | 6750 | M00391 | profile | true |
| F01980 | Weighting axis — `branch_width` | 6751 | M00391 | profile | true |
| F01981 | Weighting axis — `verification_depth` | 6752 | M00391 | profile | true |
| F01982 | Intelligence budget — `reflex` (one model, little search, low latency) | 6759–6761 | M00392 | mode | true |
| F01983 | Intelligence budget — `normal` (retrieve + one generation + validation) | 6762–6764 | M00393 | mode | true |
| F01984 | Intelligence budget — `deliberate` (multiple drafts + oracle verify + tool checks) | 6765–6767 | M00394 | mode | true |
| F01985 | Intelligence budget — `research` (branch/debate/search + citation verification) | 6768–6770 | M00395 | mode | true |
| F01986 | Intelligence budget — `autonomous` (workflow graph + tools + memory + checkpoints) | 6771–6773 | M00396 | mode | true |
| F01987 | Intelligence budget — `scientific` (hypothesis → experiment → measurement → reflection) | 6774–6776 | M00397 | mode | true |
| F01988 | Intelligence-budget UX surface — answer-fast | 6781 | E0224 | composite | true |
| F01989 | Intelligence-budget UX surface — answer-carefully | 6782 | E0224 | composite | true |
| F01990 | Intelligence-budget UX surface — explore-options | 6783 | E0224 | composite | true |
| F01991 | Intelligence-budget UX surface — prove-it | 6784 | E0224 | composite | true |
| F01992 | Intelligence-budget UX surface — try-in-sandbox | 6785 | E0224 | composite | true |
| F01993 | Intelligence-budget UX surface — run-experiment | 6786 | E0224 | composite | true |
| F01994 | Compiler-pipeline stage — user intent | 6796 | M00398 | composite | false |
| F01995 | Compiler-pipeline stage — task classifier | 6797 | M00398 | composite | false |
| F01996 | Compiler-pipeline stage — constraints | 6798 | M00398 | composite | false |
| F01997 | Compiler-pipeline stage — recipe selection | 6799 | M00398 | composite | false |
| F01998 | Compiler-pipeline stage — model routing | 6800 | M00398 | composite | false |
| F01999 | Compiler-pipeline stage — workflow graph | 6801 | M00398 | composite | false |
| F02000 | Compiler-pipeline stage — capability plan | 6802 | M00398 | composite | false |
| F02001 | Compiler-pipeline stage — execution | 6803 | M00398 | composite | false |
| F02002 | Compiler-pipeline stage — eval | 6804 | M00398 | composite | false |
| F02003 | Compiler-pipeline stage — memory update | 6805 | M00398 | composite | false |
| F02004 | AI programming analogy — prompt is source-code-ish | 6810 | E0225 | composite | false |
| F02005 | AI programming analogy — recipe is a program | 6811 | E0225 | composite | false |
| F02006 | AI programming analogy — workflow is compiled execution | 6812 | E0225 | composite | false |
| F02007 | AI programming analogy — trace is runtime telemetry | 6813 | E0225 | composite | false |
| F02008 | AI programming analogy — eval is a test suite | 6814 | E0225 | composite | false |
| F02009 | AI programming analogy — policy update is optimization | 6815 | E0225 | composite | false |
| F02010 | Model Registry schema — 9 fields | 6822–6824 | M00399 | data_model | false |
| F02011 | Tool Registry schema — 5 fields | 6825–6827 | M00400 | data_model | false |
| F02012 | Recipe Registry schema — 4 fields | 6828–6830 | M00401 | data_model | false |
| F02013 | Memory Registry schema — 6 fields | 6831–6833 | M00402 | data_model | false |
| F02014 | Eval Registry schema — 5 fields | 6834–6836 | M00403 | data_model | false |
| F02015 | Adaptive router input — task type | 6845 | M00404 | composite | false |
| F02016 | Adaptive router input — risk | 6846 | M00404 | composite | false |
| F02017 | Adaptive router input — latency target | 6847 | M00404 | composite | false |
| F02018 | Adaptive router input — quality target | 6848 | M00404 | composite | false |
| F02019 | Adaptive router input — modality | 6849 | M00404 | composite | false |
| F02020 | Adaptive router input — current GPU load | 6850 | M00404 | composite | false |
| F02021 | Adaptive router input — KV cache state | 6851 | M00404 | composite | false |
| F02022 | Adaptive router input — past success stats | 6852 | M00404 | composite | false |
| F02023 | Adaptive router input — tool availability | 6853 | M00404 | composite | false |
| F02024 | Adaptive router input — privacy constraints | 6854 | M00404 | composite | false |
| F02025 | Adaptive router input — user profile | 6855 | M00404 | composite | false |
| F02026 | Adaptive router output — which model / backend / precision / recipe / sandbox tier / verification path / memory policy | 6861–6867 | M00404 | composite | false |
| F02027 | AVX-512 candidate plan field — recipe_id / model_id / tool_mask / risk / cost_bucket / latency_bucket / expected_quality / cache_hit_prob / eval_score_bucket | 6902–6910 | M00405 | data_model | false |
| F02028 | AVX-512 eligibility mask — `eligible = capabilities_ok & risk_ok & budget_ok & model_available & cache_affinity_ok` | 6915–6920 | M00405 | composite | false |
| F02029 | AVX-512 utility score — `utility = quality_weight*quality - latency_weight*latency - risk_weight*risk - cost_weight*cost + cache_bonus + past_success_bonus` | 6926–6933 | M00405 | composite | false |
| F02030 | Programming interface — `@recipe("careful_code_repair")` Python decorator | 6942 | E0227 | composite | true |
| F02031 | Programming interface — `retrieve(project=True, depth="adaptive")` | 6944 | E0227 | composite | true |
| F02032 | Programming interface — `draft.parallel(model="scout", n=adaptive("scout_width"))` | 6945 | E0227 | composite | true |
| F02033 | Programming interface — `verify.oracle(patches, threshold=adaptive("oracle_threshold"))` | 6946 | E0227 | composite | true |
| F02034 | Programming interface — `tools.test(reviewed, sandbox=True)` | 6947 | E0227 | composite | true |
| F02035 | Programming interface — `commit.if_passes(result)` | 6948 | E0227 | composite | true |
| F02036 | Declarative policy — `writes: gated` | 6955 | E0227 | profile | true |
| F02037 | Declarative policy — `network: ask` | 6956 | E0227 | profile | true |
| F02038 | Declarative policy — `shell: sandbox_first` | 6957 | E0227 | profile | true |
| F02039 | Declarative policy — `oracle_required_for: [file_write, external_claim, high_risk]` | 6958–6961 | E0227 | profile | true |
| F02040 | Self-improvement loop — 8-step (Run / Record / Score / Attribute / Add-eval-if-useful / Tune-params / Promote-if-passes / Keep-rollback) | 6969–6977 | E0227 | composite | true |

## Requirements (R03911–R04080)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R03911 | Adaptive programming — system does not just run profiles, but learns which recipe / model / workflow / tool strategy fits the moment | 6687 | E0218 | non-negotiable | false | 10 |
| R03912 | DSPy treats LM systems as programs and optimizes prompts / demos / weights against metrics | 6691 | E0219 | non-negotiable | false | 10 |
| R03913 | DSPy compiles high-level code into prompts/weights aligned with the program and metrics | 6691 | E0219 | non-negotiable | false | 10 |
| R03914 | MIPRO-style optimizers explore instructions + few-shot demos for multi-stage LM programs | 6692 | E0219 | non-negotiable | false | 10 |
| R03915 | MIPRO uses task-grounded instruction proposals and evaluation to improve accuracy | 6692 | E0219 | non-negotiable | false | 10 |
| R03916 | LangSmith evaluations combine human eval + heuristic checks + LLM-as-judge + pairwise comparison + datasets + traces + prompt/model comparison | 6693 | E0219 | non-negotiable | false | 10 |
| R03917 | Promptfoo provides open-source evals/red-teaming with YAML test cases + assertions + model-graded checks + CI/CD integration | 6694 | E0219 | non-negotiable | false | 10 |
| R03918 | OpenAI evals frame evals as turning workflow objectives into consistent measured behavior, not benchmark vanity | 6695 | E0219 | non-negotiable | false | 10 |
| R03919 | Principle — Options without evals are chaos | 6700 | E0220 | non-negotiable | false | 10 |
| R03920 | Principle — Profiles without adaptation are presets | 6701 | E0220 | non-negotiable | false | 10 |
| R03921 | Principle — Flexibility becomes intelligence only when measured | 6702 | E0220 | non-negotiable | false | 10 |
| R03922 | Profiles are NOT static | 6707 | E0221 | non-negotiable | false | 10 |
| R03923 | Profiles are parameterized recipes | 6709 | M00389 | non-negotiable | false | 10 |
| R03924 | Recipe `code_repair` parameter — `scout_width` | 6714 | F01956 | non-negotiable | true | 10 |
| R03925 | Recipe `code_repair` parameter — `oracle_threshold` | 6715 | F01957 | non-negotiable | true | 10 |
| R03926 | Recipe `code_repair` parameter — `test_required` | 6716 | F01958 | non-negotiable | true | 10 |
| R03927 | Recipe `code_repair` parameter — `human_gate_risk` | 6717 | F01959 | non-negotiable | true | 10 |
| R03928 | Recipe `code_repair` parameter — `retrieval_depth` | 6718 | F01960 | non-negotiable | true | 10 |
| R03929 | Recipe `code_repair` parameter — `speculation_depth` | 6719 | F01961 | non-negotiable | true | 10 |
| R03930 | Recipe `code_repair` parameter — `grammar_strictness` | 6720 | F01962 | non-negotiable | true | 10 |
| R03931 | Runtime can tune recipe parameters | 6723 | E0221 | non-negotiable | false | 10 |
| R03932 | Profile registry — `fast` | 6728 | F01963 | non-negotiable | true | 10 |
| R03933 | Profile registry — `careful` | 6729 | F01964 | non-negotiable | true | 10 |
| R03934 | Profile registry — `cheap` | 6730 | F01965 | non-negotiable | true | 10 |
| R03935 | Profile registry — `private` | 6731 | F01966 | non-negotiable | true | 10 |
| R03936 | Profile registry — `risky-sandbox` | 6732 | F01967 | non-negotiable | true | 10 |
| R03937 | Profile registry — `research-heavy` | 6733 | F01968 | non-negotiable | true | 10 |
| R03938 | Profile registry — `code-safe` | 6734 | F01969 | non-negotiable | true | 10 |
| R03939 | Profile registry — `creative` | 6735 | F01970 | non-negotiable | true | 10 |
| R03940 | Profile registry — `deterministic` | 6736 | F01971 | non-negotiable | true | 10 |
| R03941 | Profile registry — `long-context` | 6737 | F01972 | non-negotiable | true | 10 |
| R03942 | Profiles are internally just weightings | 6740 | M00391 | non-negotiable | false | 10 |
| R03943 | Weighting — `latency weight` | 6744 | F01973 | non-negotiable | false | 10 |
| R03944 | Weighting — `quality weight` | 6745 | F01974 | non-negotiable | false | 10 |
| R03945 | Weighting — `cost/energy weight` | 6746 | F01975 | non-negotiable | false | 10 |
| R03946 | Weighting — `risk weight` | 6747 | F01976 | non-negotiable | false | 10 |
| R03947 | Weighting — `oracle usage weight` | 6748 | F01977 | non-negotiable | false | 10 |
| R03948 | Weighting — `tool freedom` | 6749 | F01978 | non-negotiable | false | 10 |
| R03949 | Weighting — `memory aggressiveness` | 6750 | F01979 | non-negotiable | false | 10 |
| R03950 | Weighting — `branch width` | 6751 | F01980 | non-negotiable | false | 10 |
| R03951 | Weighting — `verification depth` | 6752 | F01981 | non-negotiable | false | 10 |
| R03952 | Every task carries an "intelligence budget" | 6756 | E0224 | non-negotiable | false | 10 |
| R03953 | Intelligence budget — reflex (one model / little search / low latency) | 6759–6761 | M00392 | non-negotiable | true | 10 |
| R03954 | Intelligence budget — normal (retrieve + one generation + validation) | 6762–6764 | M00393 | non-negotiable | true | 10 |
| R03955 | Intelligence budget — deliberate (multiple drafts + oracle verify + tool checks) | 6765–6767 | M00394 | non-negotiable | true | 10 |
| R03956 | Intelligence budget — research (branch/debate/search + citation verification) | 6768–6770 | M00395 | non-negotiable | true | 10 |
| R03957 | Intelligence budget — autonomous (workflow graph + tools + memory + checkpoints) | 6771–6773 | M00396 | non-negotiable | true | 10 |
| R03958 | Intelligence budget — scientific (hypothesis → experiment → measurement → reflection) | 6774–6776 | M00397 | non-negotiable | true | 10 |
| R03959 | Intelligence budget gives the user real choices | 6778 | E0224 | non-negotiable | false | 10 |
| R03960 | UX surface — answer fast | 6781 | F01988 | non-negotiable | true | 10 |
| R03961 | UX surface — answer carefully | 6782 | F01989 | non-negotiable | true | 10 |
| R03962 | UX surface — explore options | 6783 | F01990 | non-negotiable | true | 10 |
| R03963 | UX surface — prove it | 6784 | F01991 | non-negotiable | true | 10 |
| R03964 | UX surface — try in sandbox | 6785 | F01992 | non-negotiable | true | 10 |
| R03965 | UX surface — run experiment | 6786 | F01993 | non-negotiable | true | 10 |
| R03966 | That is UX for intelligence | 6789 | E0224 | non-negotiable | false | 10 |
| R03967 | Runtime compiles an intent into an execution plan | 6793 | M00398 | non-negotiable | false | 10 |
| R03968 | Compiler-pipeline stage 1 — user intent | 6796 | F01994 | non-negotiable | false | 10 |
| R03969 | Compiler-pipeline stage 2 — task classifier | 6797 | F01995 | non-negotiable | false | 10 |
| R03970 | Compiler-pipeline stage 3 — constraints | 6798 | F01996 | non-negotiable | false | 10 |
| R03971 | Compiler-pipeline stage 4 — recipe selection | 6799 | F01997 | non-negotiable | false | 10 |
| R03972 | Compiler-pipeline stage 5 — model routing | 6800 | F01998 | non-negotiable | false | 10 |
| R03973 | Compiler-pipeline stage 6 — workflow graph | 6801 | F01999 | non-negotiable | false | 10 |
| R03974 | Compiler-pipeline stage 7 — capability plan | 6802 | F02000 | non-negotiable | false | 10 |
| R03975 | Compiler-pipeline stage 8 — execution | 6803 | F02001 | non-negotiable | false | 10 |
| R03976 | Compiler-pipeline stage 9 — eval | 6804 | F02002 | non-negotiable | false | 10 |
| R03977 | Compiler-pipeline stage 10 — memory update | 6805 | F02003 | non-negotiable | false | 10 |
| R03978 | This is AI programming | 6808 | E0225 | non-negotiable | false | 10 |
| R03979 | A prompt is source-code-ish | 6810 | F02004 | non-negotiable | false | 10 |
| R03980 | A recipe is a program | 6811 | F02005 | non-negotiable | false | 10 |
| R03981 | A workflow is compiled execution | 6812 | F02006 | non-negotiable | false | 10 |
| R03982 | A trace is runtime telemetry | 6813 | F02007 | non-negotiable | false | 10 |
| R03983 | An eval is a test suite | 6814 | F02008 | non-negotiable | false | 10 |
| R03984 | A policy update is optimization | 6815 | F02009 | non-negotiable | false | 10 |
| R03985 | Model Registry schema — name | 6822 | M00399 | non-negotiable | false | 10 |
| R03986 | Model Registry schema — size | 6822 | M00399 | non-negotiable | false | 10 |
| R03987 | Model Registry schema — modality | 6822 | M00399 | non-negotiable | false | 10 |
| R03988 | Model Registry schema — context | 6822 | M00399 | non-negotiable | false | 10 |
| R03989 | Model Registry schema — speed | 6823 | M00399 | non-negotiable | false | 10 |
| R03990 | Model Registry schema — quality | 6823 | M00399 | non-negotiable | false | 10 |
| R03991 | Model Registry schema — memory cost | 6823 | M00399 | non-negotiable | false | 10 |
| R03992 | Model Registry schema — backend | 6823 | M00399 | non-negotiable | false | 10 |
| R03993 | Model Registry schema — trust | 6824 | M00399 | non-negotiable | false | 10 |
| R03994 | Tool Registry schema — schema | 6826 | M00400 | non-negotiable | false | 10 |
| R03995 | Tool Registry schema — capabilities | 6826 | M00400 | non-negotiable | false | 10 |
| R03996 | Tool Registry schema — side effects | 6826 | M00400 | non-negotiable | false | 10 |
| R03997 | Tool Registry schema — sandbox tier | 6826 | M00400 | non-negotiable | false | 10 |
| R03998 | Tool Registry schema — success stats | 6826 | M00400 | non-negotiable | false | 10 |
| R03999 | Recipe Registry schema — workflow graph | 6829 | M00401 | non-negotiable | false | 10 |
| R04000 | Recipe Registry schema — defaults | 6829 | M00401 | non-negotiable | false | 10 |
| R04001 | Recipe Registry schema — tunable parameters | 6829 | M00401 | non-negotiable | false | 10 |
| R04002 | Recipe Registry schema — eval suite | 6830 | M00401 | non-negotiable | false | 10 |
| R04003 | Memory Registry schema — sources | 6832 | M00402 | non-negotiable | false | 10 |
| R04004 | Memory Registry schema — freshness | 6832 | M00402 | non-negotiable | false | 10 |
| R04005 | Memory Registry schema — trust | 6832 | M00402 | non-negotiable | false | 10 |
| R04006 | Memory Registry schema — embeddings | 6832 | M00402 | non-negotiable | false | 10 |
| R04007 | Memory Registry schema — bitsets | 6832 | M00402 | non-negotiable | false | 10 |
| R04008 | Memory Registry schema — replay refs | 6833 | M00402 | non-negotiable | false | 10 |
| R04009 | Eval Registry schema — test sets | 6835 | M00403 | non-negotiable | false | 10 |
| R04010 | Eval Registry schema — assertions | 6835 | M00403 | non-negotiable | false | 10 |
| R04011 | Eval Registry schema — metrics | 6835 | M00403 | non-negotiable | false | 10 |
| R04012 | Eval Registry schema — failure cases | 6835 | M00403 | non-negotiable | false | 10 |
| R04013 | Eval Registry schema — regression baselines | 6836 | M00403 | non-negotiable | false | 10 |
| R04014 | Everything is programmable when 5 registries exist | 6838 | E0226 | non-negotiable | false | 10 |
| R04015 | Adaptive router input — task type | 6845 | F02015 | non-negotiable | false | 10 |
| R04016 | Adaptive router input — risk | 6846 | F02016 | non-negotiable | false | 10 |
| R04017 | Adaptive router input — latency target | 6847 | F02017 | non-negotiable | false | 10 |
| R04018 | Adaptive router input — quality target | 6848 | F02018 | non-negotiable | false | 10 |
| R04019 | Adaptive router input — modality | 6849 | F02019 | non-negotiable | false | 10 |
| R04020 | Adaptive router input — current GPU load | 6850 | F02020 | non-negotiable | false | 10 |
| R04021 | Adaptive router input — KV cache state | 6851 | F02021 | non-negotiable | false | 10 |
| R04022 | Adaptive router input — past success stats | 6852 | F02022 | non-negotiable | false | 10 |
| R04023 | Adaptive router input — tool availability | 6853 | F02023 | non-negotiable | false | 10 |
| R04024 | Adaptive router input — privacy constraints | 6854 | F02024 | non-negotiable | false | 10 |
| R04025 | Adaptive router input — user profile | 6855 | F02025 | non-negotiable | false | 10 |
| R04026 | Adaptive router output — which model | 6861 | F02026 | non-negotiable | false | 10 |
| R04027 | Adaptive router output — which backend | 6862 | F02026 | non-negotiable | false | 10 |
| R04028 | Adaptive router output — which precision | 6863 | F02026 | non-negotiable | false | 10 |
| R04029 | Adaptive router output — which recipe | 6864 | F02026 | non-negotiable | false | 10 |
| R04030 | Adaptive router output — which sandbox tier | 6865 | F02026 | non-negotiable | false | 10 |
| R04031 | Adaptive router output — which verification path | 6866 | F02026 | non-negotiable | false | 10 |
| R04032 | Adaptive router output — which memory policy | 6867 | F02026 | non-negotiable | false | 10 |
| R04033 | Adaptive router is the "SMART" layer | 6870 | E0227 | non-negotiable | false | 10 |
| R04034 | System continuously creates small evals from real traces | 6874 | M00403 | non-negotiable | false | 10 |
| R04035 | Eval creation — user-corrected answer → eval case | 6877 | M00403 | non-negotiable | true | 10 |
| R04036 | Eval creation — tool failure → regression case | 6878 | M00403 | non-negotiable | true | 10 |
| R04037 | Eval creation — bad retrieval → memory eval | 6879 | M00403 | non-negotiable | true | 10 |
| R04038 | Eval creation — invalid JSON → schema eval | 6880 | M00403 | non-negotiable | true | 10 |
| R04039 | Eval creation — bad patch → code eval | 6881 | M00403 | non-negotiable | true | 10 |
| R04040 | Eval creation — slow run → performance eval | 6882 | M00403 | non-negotiable | true | 10 |
| R04041 | Every model/profile/workflow change runs against those evals | 6884 | M00403 | non-negotiable | false | 10 |
| R04042 | Local truth first, not huge academic benchmarks | 6887 | M00403 | non-negotiable | false | 10 |
| R04043 | Metric is "Does this station get better at operator's actual work?" | 6890 | M00403 | non-negotiable | false | 10 |
| R04044 | AVX-512 vectorized plan selector — candidate plan field `recipe_id` | 6902 | F02027 | non-negotiable | false | 10 |
| R04045 | AVX-512 vectorized plan selector — candidate plan field `model_id` | 6903 | F02027 | non-negotiable | false | 10 |
| R04046 | AVX-512 vectorized plan selector — candidate plan field `tool_mask` | 6904 | F02027 | non-negotiable | false | 10 |
| R04047 | AVX-512 vectorized plan selector — candidate plan field `risk` | 6905 | F02027 | non-negotiable | false | 10 |
| R04048 | AVX-512 vectorized plan selector — candidate plan field `cost_bucket` | 6906 | F02027 | non-negotiable | false | 10 |
| R04049 | AVX-512 vectorized plan selector — candidate plan field `latency_bucket` | 6907 | F02027 | non-negotiable | false | 10 |
| R04050 | AVX-512 vectorized plan selector — candidate plan field `expected_quality` | 6908 | F02027 | non-negotiable | false | 10 |
| R04051 | AVX-512 vectorized plan selector — candidate plan field `cache_hit_prob` | 6909 | F02027 | non-negotiable | false | 10 |
| R04052 | AVX-512 vectorized plan selector — candidate plan field `eval_score_bucket` | 6910 | F02027 | non-negotiable | false | 10 |
| R04053 | AVX-512 eligibility mask — `capabilities_ok` | 6916 | F02028 | non-negotiable | false | 10 |
| R04054 | AVX-512 eligibility mask — `risk_ok` | 6917 | F02028 | non-negotiable | false | 10 |
| R04055 | AVX-512 eligibility mask — `budget_ok` | 6918 | F02028 | non-negotiable | false | 10 |
| R04056 | AVX-512 eligibility mask — `model_available` | 6919 | F02028 | non-negotiable | false | 10 |
| R04057 | AVX-512 eligibility mask — `cache_affinity_ok` | 6920 | F02028 | non-negotiable | false | 10 |
| R04058 | AVX-512 utility score formula — `utility = quality_weight*quality - latency_weight*latency - risk_weight*risk - cost_weight*cost + cache_bonus + past_success_bonus` | 6926–6933 | F02029 | non-negotiable | false | 10 |
| R04059 | The CPU becomes a vectorized plan selector | 6935 | M00405 | non-negotiable | false | 10 |
| R04060 | Programming interface — `@recipe("careful_code_repair")` Python decorator | 6942 | F02030 | non-negotiable | true | 10 |
| R04061 | Programming interface — `retrieve(project=True, depth="adaptive")` | 6944 | F02031 | non-negotiable | true | 10 |
| R04062 | Programming interface — `draft.parallel(model="scout", n=adaptive("scout_width"))` | 6945 | F02032 | non-negotiable | true | 10 |
| R04063 | Programming interface — `verify.oracle(patches, threshold=adaptive("oracle_threshold"))` | 6946 | F02033 | non-negotiable | true | 10 |
| R04064 | Programming interface — `tools.test(reviewed, sandbox=True)` | 6947 | F02034 | non-negotiable | true | 10 |
| R04065 | Programming interface — `commit.if_passes(result)` | 6948 | F02035 | non-negotiable | true | 10 |
| R04066 | Declarative policy — `writes: gated` | 6955 | F02036 | non-negotiable | true | 10 |
| R04067 | Declarative policy — `network: ask` | 6956 | F02037 | non-negotiable | true | 10 |
| R04068 | Declarative policy — `shell: sandbox_first` | 6957 | F02038 | non-negotiable | true | 10 |
| R04069 | Declarative policy — `oracle_required_for: [file_write, external_claim, high_risk]` | 6958–6961 | F02039 | non-negotiable | true | 10 |
| R04070 | This gives hands-on control without hardcoding everything | 6964 | E0227 | non-negotiable | false | 10 |
| R04071 | Self-improvement loop step 1 — Run recipe | 6970 | F02040 | non-negotiable | false | 10 |
| R04072 | Self-improvement loop step 2 — Record trace | 6971 | F02040 | non-negotiable | false | 10 |
| R04073 | Self-improvement loop step 3 — Score outcome | 6972 | F02040 | non-negotiable | false | 10 |
| R04074 | Self-improvement loop step 4 — Attribute success/failure (to model / retrieval / tool / workflow / policy / prompt / cache / sandbox) | 6973–6974 | F02040 | non-negotiable | false | 10 |
| R04075 | Self-improvement loop step 5 — Add eval case if useful | 6975 | F02040 | non-negotiable | false | 10 |
| R04076 | Self-improvement loop step 6 — Tune recipe parameters | 6976 | F02040 | non-negotiable | false | 10 |
| R04077 | Self-improvement loop step 7 — Promote only if regression suite passes | 6977 | F02040 | non-negotiable | false | 10 |
| R04078 | Self-improvement loop step 8 — Keep rollback path | 6978 | F02040 | non-negotiable | false | 10 |
| R04079 | This is adaptive intelligence without losing control | 6980 | E0227 | non-negotiable | false | 10 |
| R04080 | Closing principle — Profiles are choices / Recipes are programs / Evals are reality / Telemetry is sensation / Memory is experience / Policy is character / Routing is intelligence | 6985–6991 | E0227 | non-negotiable | false | 10 |

— End of M024 milestone file.
