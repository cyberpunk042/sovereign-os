# M019 — Intelligence creation — composable cognitive operators

> Parent: `backlog/milestones/INDEX.md` row M019 (dump 4992–5369).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 4992–5369.
> All entries below are extracted from the dump line range. No invention.

## Epics (E0167–E0177)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0167 | Substrate for creating intelligence from many imperfect parts | 5009–5025 |
| E0168 | Intelligence-creation research families — RouteLLM cascades / FrugalGPT / Multi-Agent Debate / Mixture-of-Agents / Tree+Graph of Thoughts / Self-Consistency | 5027–5043 |
| E0169 | Do Not Lock Profiles — use composable cognitive operators | 5045–5098 |
| E0170 | Intelligence As Search — sample many / score cheaply / prune deterministically / verify expensively / remember outcomes | 5100–5132 |
| E0171 | Router As Brainstem — first-class model router with 11-input / 8-output contract; rules first, learns from traces | 5134–5169 |
| E0172 | Multiple Intelligence Recipes — Fast Executor / Careful Oracle / Debate / Tree Search / Cascade / Perception Loop / Code Repair | 5171–5198 |
| E0173 | Avoiding Fake Intelligence — anti-delusion law (diversity / evidence / independent-model / external-tool / source-citation / test-execution / schema / oracle-final) | 5200–5224 |
| E0174 | Bit-Level Implementation — per-candidate 10-field record + AVX-512 bulk processing + `accept_mask` formula | 5225–5263 |
| E0175 | Model Diversity — heterogeneous cognition (different failure modes intentionally) | 5265–5292 |
| E0176 | Creating Intelligence Locally — 6 layers (model / runtime / memory / tool / deterministic / human) | 5293–5317 |
| E0177 | Core Design — intelligence foundry shape + Final Shape Deterministic Cortex Runtime + closing law "The station creates intelligence by orchestrating uncertainty under deterministic law" | 5319–5367 |

## Modules (M00302–M00319)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00302 | Cognitive-operator registry — 12 operators (route / draft / debate / verify / decompose / retrieve / simulate / reflect / vote / merge / compress / commit) | 5058–5070 | E0169 |
| M00303 | Recipe — coding-bug graph (decompose → retrieve repo context → scout patch x4 → verify with oracle → run tests → reflect → commit) | 5075–5078 | E0169 |
| M00304 | Recipe — research graph (decompose → retrieve/search → summarize shards → debate claims → verify citations → synthesize) | 5081–5084 | E0169 |
| M00305 | Recipe — UI automation graph (perceive screen → propose actions → policy gate → sandbox action → observe → update state) | 5087–5090 | E0169 |
| M00306 | Recipe — hard reasoning graph (generate tree → score nodes → expand frontier → debate top paths → oracle verify → final) | 5093–5096 | E0169 |
| M00307 | Hardware-mapping for intelligence-as-search — 3090 generate-many / AVX-512 score+filter+pack+dedupe+route / RTX PRO 6000 verify+synthesize+resolve-conflicts / RAM+ZFS remember+replay+learn | 5120–5132 | E0170 |
| M00308 | Router inputs — task_type / risk / latency target / required modality / context size / tool requirement / estimated difficulty / privacy level / cache state / current GPU load / past success stats | 5141–5152 | E0171 |
| M00309 | Router outputs — model choice / precision / backend / speculation depth / debate width / oracle threshold / human gate threshold / cache policy | 5156–5164 | E0171 |
| M00310 | Recipe — Fast Executor (scout → deterministic checks → answer) | 5176–5178 | E0172 |
| M00311 | Recipe — Careful Oracle (retrieve → oracle → verifier → answer) | 5180–5182 | E0172 |
| M00312 | Recipe — Debate (scout A + scout B + oracle critic → merge) | 5184–5186 | E0172 |
| M00313 | Recipe — Tree Search (expand N → score → expand top K → verify) | 5188–5190 | E0172 |
| M00314 | Recipe — Cascade (small model first → escalate only if confidence/risk demands) | 5192–5194 | E0172 |
| M00315 | Recipe — Perception Loop (Nano Omni → state extractor → action planner → tool gate) | 5196–5197 | E0172 |
| M00316 | Recipe — Code Repair (test failure → retrieve symbols → patch candidates → test → reflect) | 5198 | E0172 |
| M00317 | Anti-delusion law — 8 requirements (diversity / evidence / independent-model / external-tool / source-citation / test-execution / schema / oracle-final) | 5207–5215 | E0173 |
| M00318 | Candidate/branch fields — source_model / recipe_id / evidence_mask / agreement_mask / disagreement_mask / verification_state / risk / cost / latency / score | 5229–5240 | E0174 |
| M00319 | Final Shape Deterministic Cortex Runtime — Model Registry / Router-Cascade / Branch Graph / Debate-Ensemble / Tree Search / Tool Gate / Memory+KV / Replay Ledger / Skill Library / Observability Feedback / Human Gate | 5346–5357 | E0177 |

## Features (F01531–F01615)

| F ID | Phrase | Dump line | Parent module | Category | Opt-in |
|---|---|---|---|---|---|
| F01531 | Cognitive operator — route | 5059 | M00302 | composite | false |
| F01532 | Cognitive operator — draft | 5060 | M00302 | composite | false |
| F01533 | Cognitive operator — debate | 5061 | M00302 | composite | false |
| F01534 | Cognitive operator — verify | 5062 | M00302 | composite | false |
| F01535 | Cognitive operator — decompose | 5063 | M00302 | composite | false |
| F01536 | Cognitive operator — retrieve | 5064 | M00302 | composite | false |
| F01537 | Cognitive operator — simulate | 5065 | M00302 | composite | false |
| F01538 | Cognitive operator — reflect | 5066 | M00302 | composite | false |
| F01539 | Cognitive operator — vote | 5067 | M00302 | composite | false |
| F01540 | Cognitive operator — merge | 5068 | M00302 | composite | false |
| F01541 | Cognitive operator — compress | 5069 | M00302 | composite | false |
| F01542 | Cognitive operator — commit | 5070 | M00302 | composite | false |
| F01543 | Recipe loader — read recipe DAG from `recipes/<name>.yaml` | 5072 | M00302 | composite | false |
| F01544 | Recipe — coding-bug graph (M00303) | 5075–5078 | M00303 | composite | true |
| F01545 | Recipe — research graph (M00304) | 5081–5084 | M00304 | composite | true |
| F01546 | Recipe — UI automation graph (M00305) | 5087–5090 | M00305 | composite | true |
| F01547 | Recipe — hard reasoning graph (M00306) | 5093–5096 | M00306 | composite | true |
| F01548 | Hardware-mapping — 3090 generates many cheap candidates | 5122 | M00307 | composite | false |
| F01549 | Hardware-mapping — AVX-512 CPU scores, filters, packs, dedupes, routes | 5125 | M00307 | composite | false |
| F01550 | Hardware-mapping — RTX PRO 6000 verifies, synthesizes, resolves conflicts | 5128 | M00307 | composite | false |
| F01551 | Hardware-mapping — RAM/ZFS remembers, replays, learns from traces | 5131 | M00307 | composite | false |
| F01552 | Router input — `task_type` | 5142 | M00308 | data_model | false |
| F01553 | Router input — `risk` | 5143 | M00308 | data_model | false |
| F01554 | Router input — `latency target` | 5144 | M00308 | data_model | false |
| F01555 | Router input — `required modality` | 5145 | M00308 | data_model | false |
| F01556 | Router input — `context size` | 5146 | M00308 | data_model | false |
| F01557 | Router input — `tool requirement` | 5147 | M00308 | data_model | false |
| F01558 | Router input — `estimated difficulty` | 5148 | M00308 | data_model | false |
| F01559 | Router input — `privacy level` | 5149 | M00308 | data_model | false |
| F01560 | Router input — `cache state` | 5150 | M00308 | data_model | false |
| F01561 | Router input — `current GPU load` | 5151 | M00308 | data_model | false |
| F01562 | Router input — `past success stats` | 5152 | M00308 | data_model | false |
| F01563 | Router output — `model choice` | 5157 | M00309 | data_model | false |
| F01564 | Router output — `precision` | 5158 | M00309 | data_model | false |
| F01565 | Router output — `backend` | 5159 | M00309 | data_model | false |
| F01566 | Router output — `speculation depth` | 5160 | M00309 | data_model | false |
| F01567 | Router output — `debate width` | 5161 | M00309 | data_model | false |
| F01568 | Router output — `oracle threshold` | 5162 | M00309 | data_model | false |
| F01569 | Router output — `human gate threshold` | 5163 | M00309 | data_model | false |
| F01570 | Router output — `cache policy` | 5164 | M00309 | data_model | false |
| F01571 | Router lifecycle — starts as rules, learns from traces, remains inspectable | 5167–5169 | M00308 | composite | false |
| F01572 | Recipe — Fast Executor | 5176–5178 | M00310 | composite | true |
| F01573 | Recipe — Careful Oracle | 5180–5182 | M00311 | composite | true |
| F01574 | Recipe — Debate | 5184–5186 | M00312 | composite | true |
| F01575 | Recipe — Tree Search | 5188–5190 | M00313 | composite | true |
| F01576 | Recipe — Cascade | 5192–5194 | M00314 | composite | true |
| F01577 | Recipe — Perception Loop | 5196–5197 | M00315 | composite | true |
| F01578 | Recipe — Code Repair | 5198 | M00316 | composite | true |
| F01579 | Anti-delusion requirement — diversity requirement | 5207 | M00317 | composite | false |
| F01580 | Anti-delusion requirement — evidence requirement | 5208 | M00317 | composite | false |
| F01581 | Anti-delusion requirement — independent model requirement for high-risk claims | 5209 | M00317 | composite | false |
| F01582 | Anti-delusion requirement — external tool verification when possible | 5210 | M00317 | composite | false |
| F01583 | Anti-delusion requirement — source/citation validation | 5211 | M00317 | composite | false |
| F01584 | Anti-delusion requirement — test execution for code | 5212 | M00317 | composite | false |
| F01585 | Anti-delusion requirement — schema validation for structured output | 5213 | M00317 | composite | false |
| F01586 | Anti-delusion requirement — oracle final check for commits | 5214 | M00317 | composite | false |
| F01587 | Anti-delusion outcome — "five agents agree" means "candidate confidence increased, pending verification", not truth | 5217–5222 | M00317 | composite | false |
| F01588 | Candidate field — `source_model` | 5230 | M00318 | data_model | false |
| F01589 | Candidate field — `recipe_id` | 5231 | M00318 | data_model | false |
| F01590 | Candidate field — `evidence_mask` | 5232 | M00318 | data_model | false |
| F01591 | Candidate field — `agreement_mask` | 5233 | M00318 | data_model | false |
| F01592 | Candidate field — `disagreement_mask` | 5234 | M00318 | data_model | false |
| F01593 | Candidate field — `verification_state` | 5235 | M00318 | data_model | false |
| F01594 | Candidate field — `risk` | 5236 | M00318 | data_model | false |
| F01595 | Candidate field — `cost` | 5237 | M00318 | data_model | false |
| F01596 | Candidate field — `latency` | 5238 | M00318 | data_model | false |
| F01597 | Candidate field — `score` | 5239 | M00318 | data_model | false |
| F01598 | AVX-512 candidate bulk — "which candidates agree?" | 5245 | M00318 | composite | false |
| F01599 | AVX-512 candidate bulk — "which have independent evidence?" | 5246 | M00318 | composite | false |
| F01600 | AVX-512 candidate bulk — "which are duplicates?" | 5247 | M00318 | composite | false |
| F01601 | AVX-512 candidate bulk — "which lack verification?" | 5248 | M00318 | composite | false |
| F01602 | AVX-512 candidate bulk — "which deserve oracle?" | 5249 | M00318 | composite | false |
| F01603 | AVX-512 candidate bulk — "which should be merged?" | 5250 | M00318 | composite | false |
| F01604 | Accept-mask formula — `accept_mask = grammar_ok & policy_ok & evidence_ok & (oracle_ok \| low_risk_consensus)` | 5255–5261 | M00318 | composite | false |
| F01605 | Six-layer intelligence composition — Model intelligence (learned weights) | 5298–5299 | E0176 | composite | false |
| F01606 | Six-layer intelligence composition — Runtime intelligence (routing, search, debate, verification) | 5301–5302 | E0176 | composite | false |
| F01607 | Six-layer intelligence composition — Memory intelligence (experience, skills, reflections, traces) | 5304–5305 | E0176 | composite | false |
| F01608 | Six-layer intelligence composition — Tool intelligence (calculators, compilers, browsers, file systems, tests) | 5307–5308 | E0176 | composite | false |
| F01609 | Six-layer intelligence composition — Deterministic intelligence (constraints, policies, automata, bitsets, replay) | 5310–5311 | E0176 | composite | false |
| F01610 | Six-layer intelligence composition — Human intelligence (approval, correction, preference, taste, goals) | 5313–5314 | E0176 | composite | false |
| F01611 | Foundry output shape — fast local assistant / coding agent / research analyst / document intelligence worker / computer-use agent / simulation controller / DevOps copilot / autonomous experiment runner | 5328–5338 | E0177 | composite | true |
| F01612 | API `POST /v1/recipes/{name}/start` | 5072 | M00302 | api_endpoint | true |
| F01613 | API `POST /v1/router/decide` (input + output records) | 5141–5164 | M00308 | api_endpoint | true |
| F01614 | Dashboard — cognitive operator graph builder + Dashboard — recipe library + Dashboard — router-decision inspector + Dashboard — anti-delusion law monitor | 5058–5263 | E0169 | dashboard | true |
| F01615 | Composite — "Models provide sparks. The architecture makes fire." closing law | 5364–5367 | E0177 | composite | false |

## Requirements (R03061–R03230)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R03061 | We should not lock into one profile | 5009 | E0167 | non-negotiable | false | 10 |
| R03062 | Ultimate station is NOT "one best model" | 5013 | E0167 | non-negotiable | false | 10 |
| R03063 | Ultimate station is NOT "one best framework" | 5014 | E0167 | non-negotiable | false | 10 |
| R03064 | Ultimate station is NOT "one best workflow" | 5015 | E0167 | non-negotiable | false | 10 |
| R03065 | Ultimate station IS a substrate for creating intelligence from many imperfect parts | 5021–5023 | E0167 | non-negotiable | false | 10 |
| R03066 | RouteLLM reports large cost reductions while preserving most quality using preference-trained routers | 5031 | E0168 | non-negotiable | false | 10 |
| R03067 | FrugalGPT showed LLM cascades can match or improve top-model performance at much lower cost | 5031 | E0168 | non-negotiable | false | 10 |
| R03068 | Multi-Agent Debate — multiple model instances propose, critique, revise → improves factuality/reasoning in some tasks | 5032 | E0168 | non-negotiable | false | 10 |
| R03069 | Mixture-of-Agents — multiple LLMs/layers + aggregate outputs → strong gains from model collaboration | 5033 | E0168 | non-negotiable | false | 10 |
| R03070 | Tree of Thoughts — explore multiple reasoning paths, backtrack, merge, score, select | 5034 | E0168 | non-negotiable | false | 10 |
| R03071 | Graph of Thoughts extends Tree of Thoughts | 5034 | E0168 | non-negotiable | false | 10 |
| R03072 | Self-Consistency — sample multiple reasoning paths and aggregate, not greedy | 5035 | E0168 | non-negotiable | false | 10 |
| R03073 | Intelligence can be created at inference time by search, routing, critique, verification, memory, composition | 5040 | E0168 | non-negotiable | false | 10 |
| R03074 | Instead of fixed profiles, use composable cognitive operators | 5055 | E0169 | non-negotiable | false | 10 |
| R03075 | Cognitive operator — route | 5059 | M00302 | non-negotiable | false | 10 |
| R03076 | Cognitive operator — draft | 5060 | M00302 | non-negotiable | false | 10 |
| R03077 | Cognitive operator — debate | 5061 | M00302 | non-negotiable | false | 10 |
| R03078 | Cognitive operator — verify | 5062 | M00302 | non-negotiable | false | 10 |
| R03079 | Cognitive operator — decompose | 5063 | M00302 | non-negotiable | false | 10 |
| R03080 | Cognitive operator — retrieve | 5064 | M00302 | non-negotiable | false | 10 |
| R03081 | Cognitive operator — simulate | 5065 | M00302 | non-negotiable | false | 10 |
| R03082 | Cognitive operator — reflect | 5066 | M00302 | non-negotiable | false | 10 |
| R03083 | Cognitive operator — vote | 5067 | M00302 | non-negotiable | false | 10 |
| R03084 | Cognitive operator — merge | 5068 | M00302 | non-negotiable | false | 10 |
| R03085 | Cognitive operator — compress | 5069 | M00302 | non-negotiable | false | 10 |
| R03086 | Cognitive operator — commit | 5070 | M00302 | non-negotiable | false | 10 |
| R03087 | Each task builds a graph from operators | 5072 | M00302 | non-negotiable | false | 10 |
| R03088 | Recipe — coding-bug graph: decompose → retrieve repo context → scout patch x4 → verify with oracle → run tests → reflect → commit | 5075–5078 | M00303 | non-negotiable | true | 10 |
| R03089 | Recipe — research graph: decompose → retrieve/search → summarize shards → debate claims → verify citations → synthesize | 5081–5084 | M00304 | non-negotiable | true | 10 |
| R03090 | Recipe — UI automation graph: perceive screen → propose actions → policy gate → sandbox action → observe → update state | 5087–5090 | M00305 | non-negotiable | true | 10 |
| R03091 | Recipe — hard reasoning graph: generate tree → score nodes → expand frontier → debate top paths → oracle verify → final | 5093–5096 | M00306 | non-negotiable | true | 10 |
| R03092 | Same substrate, different graph | 5098 | E0169 | non-negotiable | false | 10 |
| R03093 | Workstation creates intelligence by spending compute deliberately | 5102 | E0170 | non-negotiable | false | 10 |
| R03094 | A single model answer is one sample | 5104 | E0170 | non-negotiable | false | 10 |
| R03095 | Smarter runtime — sample many | 5109 | E0170 | non-negotiable | false | 10 |
| R03096 | Smarter runtime — score cheaply | 5110 | E0170 | non-negotiable | false | 10 |
| R03097 | Smarter runtime — prune deterministically | 5111 | E0170 | non-negotiable | false | 10 |
| R03098 | Smarter runtime — verify expensively | 5112 | E0170 | non-negotiable | false | 10 |
| R03099 | Smarter runtime — remember outcomes | 5113 | E0170 | non-negotiable | false | 10 |
| R03100 | This is intelligence amplification | 5116 | E0170 | non-negotiable | false | 10 |
| R03101 | Hardware map — 3090 generate many cheap candidates | 5122 | M00307 | non-negotiable | false | 10 |
| R03102 | Hardware map — AVX-512 CPU score, filter, pack, dedupe, route | 5125 | M00307 | non-negotiable | false | 10 |
| R03103 | Hardware map — RTX PRO 6000 verify, synthesize, resolve conflicts | 5128 | M00307 | non-negotiable | false | 10 |
| R03104 | Hardware map — RAM/ZFS remember, replay, learn from traces | 5131 | M00307 | non-negotiable | false | 10 |
| R03105 | A model router should become first-class | 5136 | E0171 | non-negotiable | false | 10 |
| R03106 | Router input — task type | 5142 | M00308 | non-negotiable | false | 10 |
| R03107 | Router input — risk | 5143 | M00308 | non-negotiable | false | 10 |
| R03108 | Router input — latency target | 5144 | M00308 | non-negotiable | false | 10 |
| R03109 | Router input — required modality | 5145 | M00308 | non-negotiable | false | 10 |
| R03110 | Router input — context size | 5146 | M00308 | non-negotiable | false | 10 |
| R03111 | Router input — tool requirement | 5147 | M00308 | non-negotiable | false | 10 |
| R03112 | Router input — estimated difficulty | 5148 | M00308 | non-negotiable | false | 10 |
| R03113 | Router input — privacy level | 5149 | M00308 | non-negotiable | false | 10 |
| R03114 | Router input — cache state | 5150 | M00308 | non-negotiable | false | 10 |
| R03115 | Router input — current GPU load | 5151 | M00308 | non-negotiable | false | 10 |
| R03116 | Router input — past success stats | 5152 | M00308 | non-negotiable | false | 10 |
| R03117 | Router output — model choice | 5157 | M00309 | non-negotiable | false | 10 |
| R03118 | Router output — precision | 5158 | M00309 | non-negotiable | false | 10 |
| R03119 | Router output — backend | 5159 | M00309 | non-negotiable | false | 10 |
| R03120 | Router output — speculation depth | 5160 | M00309 | non-negotiable | false | 10 |
| R03121 | Router output — debate width | 5161 | M00309 | non-negotiable | false | 10 |
| R03122 | Router output — oracle threshold | 5162 | M00309 | non-negotiable | false | 10 |
| R03123 | Router output — human gate threshold | 5163 | M00309 | non-negotiable | false | 10 |
| R03124 | Router output — cache policy | 5164 | M00309 | non-negotiable | false | 10 |
| R03125 | Router starts as rules | 5167 | M00308 | non-negotiable | false | 10 |
| R03126 | Router learns from traces | 5167 | M00308 | non-negotiable | false | 10 |
| R03127 | Router remains inspectable | 5169 | M00308 | non-negotiable | false | 10 |
| R03128 | Define recipes, not profiles | 5173 | E0172 | non-negotiable | false | 10 |
| R03129 | Recipe Fast Executor — scout → deterministic checks → answer | 5176–5178 | M00310 | non-negotiable | true | 10 |
| R03130 | Recipe Careful Oracle — retrieve → oracle → verifier → answer | 5180–5182 | M00311 | non-negotiable | true | 10 |
| R03131 | Recipe Debate — scout A + scout B + oracle critic → merge | 5184–5186 | M00312 | non-negotiable | true | 10 |
| R03132 | Recipe Tree Search — expand N → score → expand top K → verify | 5188–5190 | M00313 | non-negotiable | true | 10 |
| R03133 | Recipe Cascade — small model first → escalate if confidence/risk demands | 5192–5194 | M00314 | non-negotiable | true | 10 |
| R03134 | Recipe Perception Loop — Nano Omni → state extractor → action planner → tool gate | 5196–5197 | M00315 | non-negotiable | true | 10 |
| R03135 | Recipe Code Repair — test failure → retrieve symbols → patch candidates → test → reflect | 5198 | M00316 | non-negotiable | true | 10 |
| R03136 | Runtime chooses a recipe dynamically | 5199 | E0172 | non-negotiable | false | 10 |
| R03137 | Multi-agent systems can create noise | 5202 | E0173 | non-negotiable | false | 10 |
| R03138 | Debate can amplify errors if agents share the same blind spot | 5202 | E0173 | non-negotiable | false | 10 |
| R03139 | Tree search can waste compute | 5202 | E0173 | non-negotiable | false | 10 |
| R03140 | Self-consistency can vote for a common mistake | 5202 | E0173 | non-negotiable | false | 10 |
| R03141 | Anti-delusion — diversity requirement | 5207 | M00317 | non-negotiable | false | 10 |
| R03142 | Anti-delusion — evidence requirement | 5208 | M00317 | non-negotiable | false | 10 |
| R03143 | Anti-delusion — independent model requirement for high-risk claims | 5209 | M00317 | non-negotiable | false | 10 |
| R03144 | Anti-delusion — external tool verification when possible | 5210 | M00317 | non-negotiable | false | 10 |
| R03145 | Anti-delusion — source/citation validation | 5211 | M00317 | non-negotiable | false | 10 |
| R03146 | Anti-delusion — test execution for code | 5212 | M00317 | non-negotiable | false | 10 |
| R03147 | Anti-delusion — schema validation for structured output | 5213 | M00317 | non-negotiable | false | 10 |
| R03148 | Anti-delusion — oracle final check for commits | 5214 | M00317 | non-negotiable | false | 10 |
| R03149 | Do not let "five agents agree" mean truth | 5217 | M00317 | non-negotiable | false | 10 |
| R03150 | "Five agents agree" means "candidate confidence increased, pending verification" | 5221–5222 | M00317 | non-negotiable | false | 10 |
| R03151 | Each candidate/branch carries `source_model` | 5230 | M00318 | non-negotiable | false | 10 |
| R03152 | Each candidate/branch carries `recipe_id` | 5231 | M00318 | non-negotiable | false | 10 |
| R03153 | Each candidate/branch carries `evidence_mask` | 5232 | M00318 | non-negotiable | false | 10 |
| R03154 | Each candidate/branch carries `agreement_mask` | 5233 | M00318 | non-negotiable | false | 10 |
| R03155 | Each candidate/branch carries `disagreement_mask` | 5234 | M00318 | non-negotiable | false | 10 |
| R03156 | Each candidate/branch carries `verification_state` | 5235 | M00318 | non-negotiable | false | 10 |
| R03157 | Each candidate/branch carries `risk` | 5236 | M00318 | non-negotiable | false | 10 |
| R03158 | Each candidate/branch carries `cost` | 5237 | M00318 | non-negotiable | false | 10 |
| R03159 | Each candidate/branch carries `latency` | 5238 | M00318 | non-negotiable | false | 10 |
| R03160 | Each candidate/branch carries `score` | 5239 | M00318 | non-negotiable | false | 10 |
| R03161 | AVX-512 bulk-process — which candidates agree? | 5245 | M00318 | non-negotiable | false | 10 |
| R03162 | AVX-512 bulk-process — which have independent evidence? | 5246 | M00318 | non-negotiable | false | 10 |
| R03163 | AVX-512 bulk-process — which are duplicates? | 5247 | M00318 | non-negotiable | false | 10 |
| R03164 | AVX-512 bulk-process — which lack verification? | 5248 | M00318 | non-negotiable | false | 10 |
| R03165 | AVX-512 bulk-process — which deserve oracle? | 5249 | M00318 | non-negotiable | false | 10 |
| R03166 | AVX-512 bulk-process — which should be merged? | 5250 | M00318 | non-negotiable | false | 10 |
| R03167 | `accept_mask = grammar_ok & policy_ok & evidence_ok & (oracle_ok \| low_risk_consensus)` | 5255–5261 | M00318 | non-negotiable | false | 10 |
| R03168 | "Created intelligence" becomes governed by accept_mask | 5263 | M00318 | non-negotiable | false | 10 |
| R03169 | Model portfolio intentionally includes different failure modes | 5267 | E0175 | non-negotiable | false | 10 |
| R03170 | Diversity — Ling-2.6-flash token-efficient agent executor | 5270–5271 | E0175 | non-negotiable | false | 10 |
| R03171 | Diversity — Nemotron 3 Nano fast scout / long-context efficient agent | 5273–5274 | E0175 | non-negotiable | false | 10 |
| R03172 | Diversity — Nemotron 3 Nano Omni perception / document / GUI / audio-video | 5276–5277 | E0175 | non-negotiable | false | 10 |
| R03173 | Diversity — Qwen/Kimi/DeepSeek variants for coding, reasoning, long-context, MoE diversity | 5279–5280 | E0175 | non-negotiable | false | 10 |
| R03174 | Diversity — Small CPU/3090 models for classifiers, routers, embedding, quick critics | 5282–5283 | E0175 | non-negotiable | false | 10 |
| R03175 | Diversity — Blackwell oracle for strongest local final synthesis | 5285–5286 | E0175 | non-negotiable | false | 10 |
| R03176 | Heterogeneous cognition is required | 5289 | E0175 | non-negotiable | false | 10 |
| R03177 | Different models fail differently | 5291 | E0175 | non-negotiable | false | 10 |
| R03178 | Intelligence is created by 6 layers | 5295 | E0176 | non-negotiable | false | 10 |
| R03179 | Layer 1 — Model intelligence (learned weights) | 5298–5299 | E0176 | non-negotiable | false | 10 |
| R03180 | Layer 2 — Runtime intelligence (routing, search, debate, verification) | 5301–5302 | E0176 | non-negotiable | false | 10 |
| R03181 | Layer 3 — Memory intelligence (experience, skills, reflections, traces) | 5304–5305 | E0176 | non-negotiable | false | 10 |
| R03182 | Layer 4 — Tool intelligence (calculators, compilers, browsers, file systems, tests) | 5307–5308 | E0176 | non-negotiable | false | 10 |
| R03183 | Layer 5 — Deterministic intelligence (constraints, policies, automata, bitsets, replay) | 5310–5311 | E0176 | non-negotiable | false | 10 |
| R03184 | Layer 6 — Human intelligence (approval, correction, preference, taste, goals) | 5313–5314 | E0176 | non-negotiable | false | 10 |
| R03185 | Ultimate station composes all 6 layers | 5317 | E0176 | non-negotiable | false | 10 |
| R03186 | Do NOT build "an assistant" | 5322 | E0177 | non-negotiable | false | 10 |
| R03187 | Build an intelligence foundry | 5323 | E0177 | non-negotiable | false | 10 |
| R03188 | Foundry can make — fast local assistant | 5329 | E0177 | non-negotiable | true | 10 |
| R03189 | Foundry can make — coding agent | 5330 | E0177 | non-negotiable | true | 10 |
| R03190 | Foundry can make — research analyst | 5331 | E0177 | non-negotiable | true | 10 |
| R03191 | Foundry can make — document intelligence worker | 5332 | E0177 | non-negotiable | true | 10 |
| R03192 | Foundry can make — computer-use agent | 5333 | E0177 | non-negotiable | true | 10 |
| R03193 | Foundry can make — simulation controller | 5334 | E0177 | non-negotiable | true | 10 |
| R03194 | Foundry can make — DevOps copilot | 5335 | E0177 | non-negotiable | true | 10 |
| R03195 | Foundry can make — autonomous experiment runner | 5336 | E0177 | non-negotiable | true | 10 |
| R03196 | Same hardware, same substrate, different recipes | 5339 | E0177 | non-negotiable | false | 10 |
| R03197 | Final shape DCR — Model Registry | 5346 | M00319 | non-negotiable | false | 10 |
| R03198 | Final shape DCR — Router / Cascade Engine | 5347 | M00319 | non-negotiable | false | 10 |
| R03199 | Final shape DCR — Branch Graph Engine | 5348 | M00319 | non-negotiable | false | 10 |
| R03200 | Final shape DCR — Debate / Ensemble Engine | 5349 | M00319 | non-negotiable | false | 10 |
| R03201 | Final shape DCR — Tree Search Engine | 5350 | M00319 | non-negotiable | false | 10 |
| R03202 | Final shape DCR — Tool Gate | 5351 | M00319 | non-negotiable | false | 10 |
| R03203 | Final shape DCR — Memory + KV Controller | 5352 | M00319 | non-negotiable | false | 10 |
| R03204 | Final shape DCR — Replay Ledger | 5353 | M00319 | non-negotiable | false | 10 |
| R03205 | Final shape DCR — Skill Library | 5354 | M00319 | non-negotiable | false | 10 |
| R03206 | Final shape DCR — Observability Feedback | 5355 | M00319 | non-negotiable | false | 10 |
| R03207 | Final shape DCR — Human Gate | 5356 | M00319 | non-negotiable | false | 10 |
| R03208 | This avoids locking into a model, a backend, or a workflow | 5359 | E0177 | non-negotiable | false | 10 |
| R03209 | The station creates intelligence by orchestrating uncertainty under deterministic law | 5364 | E0177 | non-negotiable | false | 10 |
| R03210 | The models provide sparks; the architecture makes fire | 5367 | E0177 | non-negotiable | false | 10 |
| R03211 | Recipe library operator-overrideable (yaml in `recipes/`) | 5072 | F01543 | non-negotiable | true | 10 |
| R03212 | Profile knob — `recipe_default = fast_executor \| careful_oracle \| debate \| tree_search \| cascade \| perception_loop \| code_repair` | 5172–5198 | E0172 | non-negotiable | true | 10 |
| R03213 | Env var `SOVEREIGN_DEFAULT_RECIPE` | 5172–5198 | E0172 | non-negotiable | true | 10 |
| R03214 | CLI `--recipe <name>` | 5172–5198 | E0172 | non-negotiable | true | 10 |
| R03215 | API `POST /v1/recipes/{name}/start` | 5072 | F01612 | non-negotiable | true | 10 |
| R03216 | API `POST /v1/router/decide` returns 8-output router record | 5141–5164 | F01613 | non-negotiable | true | 10 |
| R03217 | Dashboard — cognitive operator graph builder | 5058–5072 | F01614 | non-negotiable | true | 10 |
| R03218 | Dashboard — recipe library | 5171–5198 | F01614 | non-negotiable | true | 10 |
| R03219 | Dashboard — router-decision inspector | 5141–5164 | F01614 | non-negotiable | true | 10 |
| R03220 | Dashboard — anti-delusion law monitor | 5204–5224 | F01614 | non-negotiable | true | 10 |
| R03221 | Test — 12-operator catalog closed; new operator requires explicit registration | 5058–5070 | M00302 | non-negotiable | false | 10 |
| R03222 | Test — each of 4 named recipe graphs (coding-bug / research / UI / hard-reasoning) round-trips through operator graph engine | 5075–5096 | E0169 | non-negotiable | false | 10 |
| R03223 | Test — router input/output records (11/8 fields) round-trip via API | 5141–5164 | M00308 | non-negotiable | false | 10 |
| R03224 | Test — each of 7 named recipes (Fast Executor / Careful Oracle / Debate / Tree Search / Cascade / Perception Loop / Code Repair) runs end-to-end on sample task | 5172–5198 | E0172 | non-negotiable | false | 10 |
| R03225 | Test — anti-delusion 8-axis enforcement on synthetic 5-agents-agree-but-wrong scenario | 5204–5224 | M00317 | non-negotiable | false | 10 |
| R03226 | Test — candidate 10-field record round-trip | 5229–5240 | M00318 | non-negotiable | false | 10 |
| R03227 | Test — accept_mask formula matches scalar reference across truth-table of inputs | 5255–5261 | M00318 | non-negotiable | false | 10 |
| R03228 | Test — Final-shape DCR 11-subsystem rollup enumerates all 11 components by name | 5346–5357 | M00319 | non-negotiable | false | 10 |
| R03229 | Composite — Intelligence creation integrates with M015 programming plane (operators are nodes), M017 model registry (recipe → router → model), M013 observability (telemetry feeds router), M016 learning (recipes promote via skill library) | 5346–5367 | M00319 | non-negotiable | false | 10 |
| R03230 | Composite — Intelligence Foundry shape is the meta-product of all 8 planes (Inference / Control / Memory / Storage / Tool / Observability / Programming / Learning) | 5319–5339 | E0177 | non-negotiable | false | 10 |

— End of M019 milestone file.
