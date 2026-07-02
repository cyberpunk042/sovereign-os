# M026 — SLM swarm + RLM engine + RM/PRM judges

> Parent: `backlog/milestones/INDEX.md` row M026 (dump 7378–7731).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 7378–7731.
> All entries below are extracted from the dump line range. No invention.

## Epics (E0238–E0247)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0238 | SLM and RLM are central — RLM ties REPL/context/recursion/workflow/intelligence | 7395–7397 |
| E0239 | Research substrate — NVIDIA SLM-future-of-agentic-AI / 2025-2026 SLM survey / Microsoft Fara-7B / TinyLLM / RLM Alex-Zhang / Context-folding / FoldAct / SRLM / RM-R1 / rLLM | 7399–7419 |
| E0240 | Three-model-class architecture — LLM (oracle/synthesis/hard-reasoning) / SLM (cheap repeated agentic / routing / tool calls / classification / reflexes) / RLM (recursive context processor / long-horizon decomposer / self-calling REPL worker) | 7421–7434 |
| E0241 | Judge class — RM/RRM/PRM (reward / process scoring / candidate ranking / branch value estimation) | 7436–7441 |
| E0242 | SLMs are microservices of intelligence — 11-role SLM swarm + "big model is your judge not your janitor" | 7445–7465 |
| E0243 | RLM is the context operating system — RLM loop (read task / inspect external context via code / spawn sub-call on relevant slice / aggregate / repeat / return) vs RAG | 7467–7504 |
| E0244 | Hardware mapping — Blackwell=parent-RLM+oracle / 4090=child-RLM+SLM-scouts+tool-use / Ryzen-AVX-512=context-index+branch-scheduler+recursion-budget / RAM-ZFS=external-context-environment | 7506–7535 |
| E0245 | RLM + AVX-512 — per-subcall 8-field control word + 7-question bulk-law per subcall + "RLM without control can explode; RLM with AVX-512 scheduling becomes disciplined recursion" | 7537–7567 |
| E0246 | Reward Models As Value Functions — 4-reward-source taxonomy (rule / process / model / system) + 8-field reward vector + profiles-become-reward-policies (careful_research vs fast_local example) | 7569–7642 |
| E0247 | RLM+SLM combination + adaptation + new architecture components (SLM Swarm + RLM Engine + Reward Plane + Profile Optimizer) + closing 8-clause key-line | 7644–7729 |

## Modules (M00423–M00440)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00423 | LLM role — big oracle / synthesis / hard reasoning / final judgment | 7427–7428 | E0240 |
| M00424 | SLM role — cheap repeated agentic actions / routing / tool calls / classification / local reflexes | 7429–7430 | E0240 |
| M00425 | RLM role — recursive context processor / long-horizon decomposer / self-calling REPL worker | 7432–7433 | E0240 |
| M00426 | Judge class — RM / RRM / PRM (reward, process scoring, candidate ranking, branch value estimation) | 7439–7440 | E0241 |
| M00427 | SLM swarm — 11 named roles (intent classifier / tool-call planner / JSON fixer / schema selector / risk tagger / memory router / branch summarizer / patch scout / GUI perception helper / query reformulator / test failure classifier) | 7449–7461 | E0242 |
| M00428 | RLM loop — 6-step (read task / inspect external context via code / spawn sub-call on relevant slice / aggregate result / repeat / return answer) | 7491–7499 | E0243 |
| M00429 | RLM vs RAG distinction — RAG retrieves for the model; RLM lets the model navigate context as an environment | 7503–7504 | E0243 |
| M00430 | Hardware mapping — Blackwell parent-RLM + oracle synthesis + hard recursive calls + final verification | 7509–7512 | E0244 |
| M00431 | Hardware mapping — 4090 child RLM calls + SLM scouts + tool-use agents + perception+rerankers | 7514–7518 | E0244 |
| M00432 | Hardware mapping — Ryzen AVX-512 context index + branch scheduler + recursion budget + duplicate detection + uncertainty routing + reward/vector scoring | 7520–7526 | E0244 |
| M00433 | Hardware mapping — RAM/ZFS external context environment (variables / files / logs / memory chunks / replay) | 7528–7531 | E0244 |
| M00434 | RLM subcall 8-field control word — parent_id / depth / context_slice_ref / question_ref / budget / uncertainty / reward_score / visited_hash | 7543–7552 | E0245 |
| M00435 | RLM AVX-512 bulk-law — 7-question scan (duplicate / exceeded-depth / need-oracle / SLM-answerable / slices-overlap / results-agree / branch-fold-into-parent) | 7554–7564 | E0245 |
| M00436 | 4-reward-source taxonomy — rule reward (schema valid / tests pass / citation exists) / process reward (reasoning step quality / tool plan quality) / model reward (RRM judge score) / system reward (latency / cost / cache reuse / risk) | 7575–7587 | E0246 |
| M00437 | Reward vector 8-field — correctness / evidence / risk / cost / latency / novelty / reuse / user_preference | 7592–7601 | E0246 |
| M00438 | Profile reward-weights map — per-profile weight assignment (careful_research / fast_local examples) | 7618–7640 | E0246 |
| M00439 | RLM+SLM combination — Parent RLM commands / Child SLMs inspect+classify+extract+summarize / Reward model scores / CPU aggregates+dedupes+routes / Oracle synthesizes | 7648–7663 | E0247 |
| M00440 | 4 new architecture components — SLM Swarm / RLM Engine / Reward Plane / Profile Optimizer | 7689–7701 | E0247 |

## Features (F02126–F02210)

| F ID | Phrase | Dump line | Parent module | Category | Opt-in |
|---|---|---|---|---|---|
| F02126 | Toggle three-model-class architecture (LLM-only / LLM+SLM / LLM+SLM+RLM / full-stack) | 7421–7441 | E0240 | mode | true |
| F02127 | Profile knob — `model_class_stack = llm \| llm_slm \| llm_slm_rlm \| full` | 7421–7441 | E0240 | profile | true |
| F02128 | Env var `SOVEREIGN_MODEL_CLASS_STACK` | 7421–7441 | E0240 | env_var | true |
| F02129 | CLI `--model-class-stack <mode>` | 7421–7441 | E0240 | cli_verb | true |
| F02130 | NVIDIA SLM-as-future-of-agentic substrate — SLMs sufficient + economical + better for repeated agentic invocations | 7403 | E0239 | composite | true |
| F02131 | 2025/2026 SLM survey substrate — schema/API/tool use + guided decoding + function registries + confidence scoring + verifier rollups + LoRA/QLoRA adaptation | 7404 | E0239 | composite | true |
| F02132 | Microsoft Fara-7B substrate — agentic SLM for computer use | 7405 | E0239 | composite | true |
| F02133 | TinyLLM substrate — medium-small models (1-3B+) for tool/API tasks on edge | 7406 | E0239 | composite | true |
| F02134 | RLM substrate — inputs up to two orders of magnitude beyond context windows; outperforms long-context scaffolds at comparable or lower cost | 7410 | E0239 | composite | false |
| F02135 | Context Folding substrate — keep active context small while preserving useful state | 7411 | E0239 | composite | true |
| F02136 | FoldAct substrate — context-folding extension | 7411 | E0239 | composite | true |
| F02137 | SRLM substrate — uncertainty-aware self-reflective program search on top of RLM | 7412 | E0239 | composite | true |
| F02138 | Reasoning Language Model substrate — inference-time compute + RL for multi-step reasoning | 7416 | E0239 | composite | true |
| F02139 | Reward Reasoning Model substrate — reward models reason before assigning reward | 7417 | E0239 | composite | true |
| F02140 | RM-R1 substrate — reward modeling itself as reasoning (generated rubrics + reasoning traces) | 7418 | E0239 | composite | true |
| F02141 | rLLM substrate — RL framework for training agents from episodes/trajectories/steps | 7419 | E0239 | composite | true |
| F02142 | LLM role binding — big oracle / synthesis / hard reasoning / final judgment | 7427–7428 | M00423 | composite | false |
| F02143 | SLM role binding — cheap repeated agentic actions / routing / tool calls / classification / local reflexes | 7429–7430 | M00424 | composite | false |
| F02144 | RLM role binding — recursive context processor / long-horizon decomposer / self-calling REPL worker | 7432–7433 | M00425 | composite | false |
| F02145 | Judge class binding — RM (reward) | 7439 | M00426 | composite | false |
| F02146 | Judge class binding — RRM (reasoning-reward model) | 7439 | M00426 | composite | false |
| F02147 | Judge class binding — PRM (process reward model) | 7439 | M00426 | composite | false |
| F02148 | SLM swarm role — intent classifier | 7450 | M00427 | composite | true |
| F02149 | SLM swarm role — tool-call planner | 7451 | M00427 | composite | true |
| F02150 | SLM swarm role — JSON fixer | 7452 | M00427 | composite | true |
| F02151 | SLM swarm role — schema selector | 7453 | M00427 | composite | true |
| F02152 | SLM swarm role — risk tagger | 7454 | M00427 | composite | true |
| F02153 | SLM swarm role — memory router | 7455 | M00427 | composite | true |
| F02154 | SLM swarm role — branch summarizer | 7456 | M00427 | composite | true |
| F02155 | SLM swarm role — patch scout | 7457 | M00427 | composite | true |
| F02156 | SLM swarm role — GUI perception helper | 7458 | M00427 | composite | true |
| F02157 | SLM swarm role — query reformulator | 7459 | M00427 | composite | true |
| F02158 | SLM swarm role — test failure classifier | 7460 | M00427 | composite | true |
| F02159 | SLM principle — big model is your judge, not your janitor | 7465 | M00424 | composite | false |
| F02160 | RLM loop step — read task | 7493 | M00428 | composite | false |
| F02161 | RLM loop step — inspect external context via code | 7494 | M00428 | composite | false |
| F02162 | RLM loop step — spawn sub-call on relevant slice | 7495 | M00428 | composite | false |
| F02163 | RLM loop step — aggregate result | 7496 | M00428 | composite | false |
| F02164 | RLM loop step — repeat | 7497 | M00428 | composite | false |
| F02165 | RLM loop step — return answer | 7498 | M00428 | composite | false |
| F02166 | RLM vs RAG — RAG retrieves for the model | 7503 | M00429 | composite | false |
| F02167 | RLM vs RAG — RLM lets the model navigate context as an environment | 7504 | M00429 | composite | false |
| F02168 | Hardware binding — Blackwell hosts parent RLM | 7510 | M00430 | composite | false |
| F02169 | Hardware binding — Blackwell handles hard recursive calls | 7511 | M00430 | composite | false |
| F02170 | Hardware binding — 4090 hosts child RLM calls | 7515 | M00431 | composite | false |
| F02171 | Hardware binding — 4090 hosts SLM scouts | 7516 | M00431 | composite | false |
| F02172 | Hardware binding — 4090 hosts tool-use agents | 7517 | M00431 | composite | false |
| F02173 | Hardware binding — 4090 hosts perception+rerankers | 7518 | M00431 | composite | false |
| F02174 | Hardware binding — Ryzen AVX-512 context index | 7521 | M00432 | composite | false |
| F02175 | Hardware binding — Ryzen AVX-512 branch scheduler | 7522 | M00432 | composite | false |
| F02176 | Hardware binding — Ryzen AVX-512 recursion budget | 7523 | M00432 | composite | false |
| F02177 | Hardware binding — Ryzen AVX-512 duplicate detection | 7524 | M00432 | composite | false |
| F02178 | Hardware binding — Ryzen AVX-512 uncertainty routing | 7525 | M00432 | composite | false |
| F02179 | Hardware binding — Ryzen AVX-512 reward/vector scoring | 7526 | M00432 | composite | false |
| F02180 | Hardware binding — RAM/ZFS external context environment | 7529–7531 | M00433 | composite | false |
| F02181 | RLM subcall field — `parent_id` | 7544 | M00434 | data_model | false |
| F02182 | RLM subcall field — `depth` | 7545 | M00434 | data_model | false |
| F02183 | RLM subcall field — `context_slice_ref` | 7546 | M00434 | data_model | false |
| F02184 | RLM subcall field — `question_ref` | 7547 | M00434 | data_model | false |
| F02185 | RLM subcall field — `budget` | 7548 | M00434 | data_model | false |
| F02186 | RLM subcall field — `uncertainty` | 7549 | M00434 | data_model | false |
| F02187 | RLM subcall field — `reward_score` | 7550 | M00434 | data_model | false |
| F02188 | RLM subcall field — `visited_hash` | 7551 | M00434 | data_model | false |
| F02189 | AVX-512 bulk law — which subcalls are duplicate? | 7557 | M00435 | composite | false |
| F02190 | AVX-512 bulk law — which exceeded depth? | 7558 | M00435 | composite | false |
| F02191 | AVX-512 bulk law — which need oracle? | 7559 | M00435 | composite | false |
| F02192 | AVX-512 bulk law — which can be answered by SLM? | 7560 | M00435 | composite | false |
| F02193 | AVX-512 bulk law — which slices overlap? | 7561 | M00435 | composite | false |
| F02194 | AVX-512 bulk law — which results agree? | 7562 | M00435 | composite | false |
| F02195 | AVX-512 bulk law — which branch should fold into parent? | 7563 | M00435 | composite | false |
| F02196 | Reward source — rule reward (schema valid / tests pass / citation exists) | 7576–7577 | M00436 | composite | false |
| F02197 | Reward source — process reward (reasoning step quality / tool plan quality) | 7579–7580 | M00436 | composite | false |
| F02198 | Reward source — model reward (RRM/judge score) | 7582–7583 | M00436 | composite | false |
| F02199 | Reward source — system reward (latency / cost / cache reuse / risk) | 7585–7586 | M00436 | composite | false |
| F02200 | Reward vector — `correctness` field | 7593 | M00437 | data_model | false |
| F02201 | Reward vector — `evidence` field | 7594 | M00437 | data_model | false |
| F02202 | Reward vector — `risk` field | 7595 | M00437 | data_model | false |
| F02203 | Reward vector — `cost` field | 7596 | M00437 | data_model | false |
| F02204 | Reward vector — `latency` field | 7597 | M00437 | data_model | false |
| F02205 | Reward vector — `novelty` field | 7598 | M00437 | data_model | false |
| F02206 | Reward vector — `reuse` field | 7599 | M00437 | data_model | false |
| F02207 | Reward vector — `user_preference` field | 7600 | M00437 | data_model | false |
| F02208 | Profile reward-weights example — `careful_research` (correctness 0.35 / evidence 0.30 / risk 0.15 / latency 0.05 / cost 0.05 / novelty 0.05 / user_style 0.05) | 7618–7627 | M00438 | profile | true |
| F02209 | Profile reward-weights example — `fast_local` (latency 0.40 / locality 0.20 / correctness 0.20 / cost 0.10 / risk 0.10) | 7632–7640 | M00438 | profile | true |
| F02210 | 4 new architecture components — SLM Swarm / RLM Engine / Reward Plane / Profile Optimizer | 7689–7701 | M00440 | composite | false |

## Requirements (R04251–R04420)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R04251 | SLM and RLM are absolutely central | 7395 | E0238 | non-negotiable | false | 10 |
| R04252 | RLM especially — ties together REPL, context, recursion, workflow, and intelligence in a very clean way | 7397 | E0238 | non-negotiable | false | 10 |
| R04253 | NVIDIA research argues SLMs are sufficiently capable + more economical + better suited for repeated agentic invocations than large models | 7403 | F02130 | non-negotiable | false | 10 |
| R04254 | 2025/2026 SLM survey argues SLMs effective for schema/API/tool use with guided decoding + function registries + confidence scoring + verifier rollups + LoRA/QLoRA adaptation | 7404 | F02131 | non-negotiable | false | 10 |
| R04255 | Microsoft Fara-7B is explicitly an agentic SLM for computer use | 7405 | F02132 | non-negotiable | false | 10 |
| R04256 | TinyLLM work shows medium-small models (1-3B+) can perform tool/API tasks on edge with optimization | 7406 | F02133 | non-negotiable | false | 10 |
| R04257 | RLMs treat long prompts as an external environment | 7410 | M00428 | non-negotiable | false | 10 |
| R04258 | RLMs let the model programmatically inspect, decompose, and recursively call itself over snippets | 7410 | M00428 | non-negotiable | false | 10 |
| R04259 | RLM paper reports handling inputs up to two orders of magnitude beyond context windows | 7410 | F02134 | non-negotiable | false | 10 |
| R04260 | RLM outperforms base long-context scaffolds at comparable or lower cost | 7410 | F02134 | non-negotiable | false | 10 |
| R04261 | Context-folding work attacks the same long-horizon problem | 7411 | F02135 | non-negotiable | false | 10 |
| R04262 | Context-folding keeps active context small while preserving useful state | 7411 | F02135 | non-negotiable | false | 10 |
| R04263 | SRLM adds uncertainty-aware self-reflective program search on top of RLM | 7412 | F02137 | non-negotiable | false | 10 |
| R04264 | Recursion can hurt when used blindly | 7412 | F02137 | non-negotiable | false | 10 |
| R04265 | Reasoning Language Models are increasingly RL-shaped | 7416 | F02138 | non-negotiable | false | 10 |
| R04266 | Inference-time compute plus reinforcement learning for multi-step reasoning | 7416 | F02138 | non-negotiable | false | 10 |
| R04267 | Reward Reasoning Models deliberately reason before assigning reward | 7417 | F02139 | non-negotiable | false | 10 |
| R04268 | Reward models move from "score output" to "judge through reasoning" | 7417 | F02139 | non-negotiable | false | 10 |
| R04269 | RM-R1 frames reward modeling itself as reasoning, with generated rubrics and reasoning traces before scoring | 7418 | F02140 | non-negotiable | false | 10 |
| R04270 | rLLM provides RL framework for training language agents from episodes, trajectories, and steps | 7419 | F02141 | non-negotiable | false | 10 |
| R04271 | Ultimate station needs three model classes | 7423 | E0240 | non-negotiable | false | 10 |
| R04272 | LLM role — big oracle, synthesis, hard reasoning, final judgment | 7427–7428 | M00423 | non-negotiable | false | 10 |
| R04273 | SLM role — cheap repeated agentic actions, routing, tool calls, classification, local reflexes | 7429–7430 | M00424 | non-negotiable | false | 10 |
| R04274 | RLM role — recursive context processor, long-horizon decomposer, self-calling REPL worker | 7432–7433 | M00425 | non-negotiable | false | 10 |
| R04275 | One judge class — RM/RRM/PRM (reward, process scoring, candidate ranking, branch value estimation) | 7439–7440 | M00426 | non-negotiable | false | 10 |
| R04276 | That gives a real intelligence stack | 7443 | E0240 | non-negotiable | false | 10 |
| R04277 | SLMs should be everywhere | 7447 | E0242 | non-negotiable | false | 10 |
| R04278 | SLM role — intent classifier | 7450 | F02148 | non-negotiable | true | 10 |
| R04279 | SLM role — tool-call planner | 7451 | F02149 | non-negotiable | true | 10 |
| R04280 | SLM role — JSON fixer | 7452 | F02150 | non-negotiable | true | 10 |
| R04281 | SLM role — schema selector | 7453 | F02151 | non-negotiable | true | 10 |
| R04282 | SLM role — risk tagger | 7454 | F02152 | non-negotiable | true | 10 |
| R04283 | SLM role — memory router | 7455 | F02153 | non-negotiable | true | 10 |
| R04284 | SLM role — branch summarizer | 7456 | F02154 | non-negotiable | true | 10 |
| R04285 | SLM role — patch scout | 7457 | F02155 | non-negotiable | true | 10 |
| R04286 | SLM role — GUI perception helper | 7458 | F02156 | non-negotiable | true | 10 |
| R04287 | SLM role — query reformulator | 7459 | F02157 | non-negotiable | true | 10 |
| R04288 | SLM role — test failure classifier | 7460 | F02158 | non-negotiable | true | 10 |
| R04289 | Do not send small decisions to the Blackwell oracle unless needed | 7463 | M00424 | non-negotiable | false | 10 |
| R04290 | A 1B-8B SLM on 4090 or CPU handles thousands of little decisions | 7465 | M00424 | non-negotiable | false | 10 |
| R04291 | The big model should be your judge, not your janitor | 7465 | F02159 | non-negotiable | false | 10 |
| R04292 | RLM changes the long-context problem | 7469 | E0243 | non-negotiable | false | 10 |
| R04293 | RLM replaces "stuff everything into context + hope attention finds the right facts" | 7473–7476 | E0243 | non-negotiable | false | 10 |
| R04294 | RLM loads corpus/repo/logs into environment | 7481 | M00428 | non-negotiable | false | 10 |
| R04295 | RLM model writes code/searches/slices | 7482 | M00428 | non-negotiable | false | 10 |
| R04296 | RLM model recursively delegates subquestions | 7483 | M00428 | non-negotiable | false | 10 |
| R04297 | RLM subresults return | 7484 | M00428 | non-negotiable | false | 10 |
| R04298 | RLM parent synthesizes | 7485 | M00428 | non-negotiable | false | 10 |
| R04299 | RLM aligns with REPL idea | 7488 | E0243 | non-negotiable | false | 10 |
| R04300 | RLM loop step — read task | 7493 | F02160 | non-negotiable | false | 10 |
| R04301 | RLM loop step — inspect external context via code | 7494 | F02161 | non-negotiable | false | 10 |
| R04302 | RLM loop step — spawn sub-call on relevant slice | 7495 | F02162 | non-negotiable | false | 10 |
| R04303 | RLM loop step — aggregate result | 7496 | F02163 | non-negotiable | false | 10 |
| R04304 | RLM loop step — repeat | 7497 | F02164 | non-negotiable | false | 10 |
| R04305 | RLM loop step — return answer | 7498 | F02165 | non-negotiable | false | 10 |
| R04306 | This is active context management, not just RAG | 7501 | M00429 | non-negotiable | false | 10 |
| R04307 | RAG retrieves for the model | 7503 | F02166 | non-negotiable | false | 10 |
| R04308 | RLM lets the model navigate context as an environment | 7504 | F02167 | non-negotiable | false | 10 |
| R04309 | Hardware binding — Blackwell parent RLM | 7510 | F02168 | non-negotiable | false | 10 |
| R04310 | Hardware binding — Blackwell oracle synthesis | 7511 | F02168 | non-negotiable | false | 10 |
| R04311 | Hardware binding — Blackwell hard recursive calls | 7511 | F02169 | non-negotiable | false | 10 |
| R04312 | Hardware binding — Blackwell final verification | 7512 | F02168 | non-negotiable | false | 10 |
| R04313 | Hardware binding — 4090 child RLM calls | 7515 | F02170 | non-negotiable | false | 10 |
| R04314 | Hardware binding — 4090 SLM scouts | 7516 | F02171 | non-negotiable | false | 10 |
| R04315 | Hardware binding — 4090 tool-use agents | 7517 | F02172 | non-negotiable | false | 10 |
| R04316 | Hardware binding — 4090 perception+rerankers | 7518 | F02173 | non-negotiable | false | 10 |
| R04317 | Hardware binding — Ryzen AVX-512 context index | 7521 | F02174 | non-negotiable | false | 10 |
| R04318 | Hardware binding — Ryzen AVX-512 branch scheduler | 7522 | F02175 | non-negotiable | false | 10 |
| R04319 | Hardware binding — Ryzen AVX-512 recursion budget | 7523 | F02176 | non-negotiable | false | 10 |
| R04320 | Hardware binding — Ryzen AVX-512 duplicate detection | 7524 | F02177 | non-negotiable | false | 10 |
| R04321 | Hardware binding — Ryzen AVX-512 uncertainty routing | 7525 | F02178 | non-negotiable | false | 10 |
| R04322 | Hardware binding — Ryzen AVX-512 reward/vector scoring | 7526 | F02179 | non-negotiable | false | 10 |
| R04323 | Hardware binding — RAM/ZFS external context environment (variables / files / logs / memory chunks / replay) | 7529–7531 | F02180 | non-negotiable | false | 10 |
| R04324 | Workstation is excellent for RLM because RLM wants an environment and the workstation has one | 7533–7535 | E0244 | non-negotiable | false | 10 |
| R04325 | RLM creates many subcalls — CPU must keep them sane | 7539 | E0245 | non-negotiable | false | 10 |
| R04326 | Recursive call field — `parent_id` | 7544 | F02181 | non-negotiable | false | 10 |
| R04327 | Recursive call field — `depth` | 7545 | F02182 | non-negotiable | false | 10 |
| R04328 | Recursive call field — `context_slice_ref` | 7546 | F02183 | non-negotiable | false | 10 |
| R04329 | Recursive call field — `question_ref` | 7547 | F02184 | non-negotiable | false | 10 |
| R04330 | Recursive call field — `budget` | 7548 | F02185 | non-negotiable | false | 10 |
| R04331 | Recursive call field — `uncertainty` | 7549 | F02186 | non-negotiable | false | 10 |
| R04332 | Recursive call field — `reward_score` | 7550 | F02187 | non-negotiable | false | 10 |
| R04333 | Recursive call field — `visited_hash` | 7551 | F02188 | non-negotiable | false | 10 |
| R04334 | AVX-512 bulk law — which subcalls are duplicate? | 7557 | F02189 | non-negotiable | false | 10 |
| R04335 | AVX-512 bulk law — which exceeded depth? | 7558 | F02190 | non-negotiable | false | 10 |
| R04336 | AVX-512 bulk law — which need oracle? | 7559 | F02191 | non-negotiable | false | 10 |
| R04337 | AVX-512 bulk law — which can be answered by SLM? | 7560 | F02192 | non-negotiable | false | 10 |
| R04338 | AVX-512 bulk law — which slices overlap? | 7561 | F02193 | non-negotiable | false | 10 |
| R04339 | AVX-512 bulk law — which results agree? | 7562 | F02194 | non-negotiable | false | 10 |
| R04340 | AVX-512 bulk law — which branch should fold into parent? | 7563 | F02195 | non-negotiable | false | 10 |
| R04341 | RLM without control can explode | 7566 | E0245 | non-negotiable | false | 10 |
| R04342 | RLM with AVX-512 scheduling becomes disciplined recursion | 7567 | E0245 | non-negotiable | false | 10 |
| R04343 | Add a value layer | 7571 | E0246 | non-negotiable | false | 10 |
| R04344 | Every branch/subcall/tool plan can be scored | 7573 | M00436 | non-negotiable | false | 10 |
| R04345 | Reward source — rule reward (schema valid / tests pass / citation exists) | 7576–7577 | F02196 | non-negotiable | false | 10 |
| R04346 | Reward source — process reward (reasoning step quality / tool plan quality) | 7579–7580 | F02197 | non-negotiable | false | 10 |
| R04347 | Reward source — model reward (RRM/judge score) | 7582–7583 | F02198 | non-negotiable | false | 10 |
| R04348 | Reward source — system reward (latency / cost / cache reuse / risk) | 7585–7586 | F02199 | non-negotiable | false | 10 |
| R04349 | Reward vector field — `correctness` | 7593 | F02200 | non-negotiable | false | 10 |
| R04350 | Reward vector field — `evidence` | 7594 | F02201 | non-negotiable | false | 10 |
| R04351 | Reward vector field — `risk` | 7595 | F02202 | non-negotiable | false | 10 |
| R04352 | Reward vector field — `cost` | 7596 | F02203 | non-negotiable | false | 10 |
| R04353 | Reward vector field — `latency` | 7597 | F02204 | non-negotiable | false | 10 |
| R04354 | Reward vector field — `novelty` | 7598 | F02205 | non-negotiable | false | 10 |
| R04355 | Reward vector field — `reuse` | 7599 | F02206 | non-negotiable | false | 10 |
| R04356 | Reward vector field — `user_preference` | 7600 | F02207 | non-negotiable | false | 10 |
| R04357 | Do not collapse reward vector too early into one number | 7603 | M00437 | non-negotiable | false | 10 |
| R04358 | Keep the reward vector — different profiles weight it differently | 7604 | M00437 | non-negotiable | false | 10 |
| R04359 | Fast profile weights latency | 7607 | M00438 | non-negotiable | true | 10 |
| R04360 | Careful profile weights correctness/evidence | 7608 | M00438 | non-negotiable | true | 10 |
| R04361 | Private profile weights locality | 7609 | M00438 | non-negotiable | true | 10 |
| R04362 | Creative profile weights novelty | 7610 | M00438 | non-negotiable | true | 10 |
| R04363 | Autonomous profile weights reliability | 7611 | M00438 | non-negotiable | true | 10 |
| R04364 | That is adaptive intelligence | 7614 | M00438 | non-negotiable | false | 10 |
| R04365 | Profile reward-weights example — `careful_research` (correctness 0.35) | 7621 | F02208 | non-negotiable | true | 10 |
| R04366 | Profile reward-weights example — `careful_research` (evidence 0.30) | 7622 | F02208 | non-negotiable | true | 10 |
| R04367 | Profile reward-weights example — `careful_research` (risk 0.15) | 7623 | F02208 | non-negotiable | true | 10 |
| R04368 | Profile reward-weights example — `careful_research` (latency 0.05) | 7624 | F02208 | non-negotiable | true | 10 |
| R04369 | Profile reward-weights example — `careful_research` (cost 0.05) | 7625 | F02208 | non-negotiable | true | 10 |
| R04370 | Profile reward-weights example — `careful_research` (novelty 0.05) | 7626 | F02208 | non-negotiable | true | 10 |
| R04371 | Profile reward-weights example — `careful_research` (user_style 0.05) | 7627 | F02208 | non-negotiable | true | 10 |
| R04372 | Profile reward-weights example — `fast_local` (latency 0.40) | 7635 | F02209 | non-negotiable | true | 10 |
| R04373 | Profile reward-weights example — `fast_local` (locality 0.20) | 7636 | F02209 | non-negotiable | true | 10 |
| R04374 | Profile reward-weights example — `fast_local` (correctness 0.20) | 7637 | F02209 | non-negotiable | true | 10 |
| R04375 | Profile reward-weights example — `fast_local` (cost 0.10) | 7638 | F02209 | non-negotiable | true | 10 |
| R04376 | Profile reward-weights example — `fast_local` (risk 0.10) | 7639 | F02209 | non-negotiable | true | 10 |
| R04377 | Same system, different intelligence character | 7642 | M00438 | non-negotiable | false | 10 |
| R04378 | RLM+SLM combination — parent RLM (big model asks what needs to be known) | 7649–7650 | M00439 | non-negotiable | false | 10 |
| R04379 | RLM+SLM combination — child SLMs inspect slices, classify chunks, extract facts, summarize local evidence | 7652–7653 | M00439 | non-negotiable | false | 10 |
| R04380 | RLM+SLM combination — reward model scores child outputs | 7655–7656 | M00439 | non-negotiable | false | 10 |
| R04381 | RLM+SLM combination — CPU aggregates, dedupes, routes uncertainty | 7658–7659 | M00439 | non-negotiable | false | 10 |
| R04382 | RLM+SLM combination — oracle final synthesis | 7661–7662 | M00439 | non-negotiable | false | 10 |
| R04383 | RLM+SLM gives scalable intelligence | 7665 | M00439 | non-negotiable | false | 10 |
| R04384 | Big model does not read 10 million tokens — it commands a context expedition | 7667 | M00439 | non-negotiable | false | 10 |
| R04385 | Station should learn — which SLM is good at tool calls | 7674 | E0247 | non-negotiable | true | 10 |
| R04386 | Station should learn — which SLM hallucinates APIs | 7675 | E0247 | non-negotiable | true | 10 |
| R04387 | Station should learn — which RLM recursion depth works | 7676 | E0247 | non-negotiable | true | 10 |
| R04388 | Station should learn — which reward model agrees with tests | 7677 | E0247 | non-negotiable | true | 10 |
| R04389 | Station should learn — which profile satisfies you | 7678 | E0247 | non-negotiable | true | 10 |
| R04390 | Station should learn — which context-folding strategy loses facts | 7679 | E0247 | non-negotiable | true | 10 |
| R04391 | Station should learn — which memory source is trustworthy | 7680 | E0247 | non-negotiable | true | 10 |
| R04392 | Stored as routing statistics and eval cases | 7683 | E0247 | non-negotiable | false | 10 |
| R04393 | New architecture component — SLM Swarm (small specialized local workers) | 7690–7691 | M00440 | non-negotiable | false | 10 |
| R04394 | New architecture component — RLM Engine (recursive context decomposition and self-call orchestration) | 7693–7694 | M00440 | non-negotiable | false | 10 |
| R04395 | New architecture component — Reward Plane (RM/RRM/PRM/process scoring/value estimation) | 7696–7697 | M00440 | non-negotiable | false | 10 |
| R04396 | New architecture component — Profile Optimizer (maps user intent to reward weights and recipes) | 7699–7700 | M00440 | non-negotiable | false | 10 |
| R04397 | Whole station becomes — Oracle LLM | 7706 | E0247 | non-negotiable | false | 10 |
| R04398 | Whole station becomes — + SLM swarm | 7707 | E0247 | non-negotiable | false | 10 |
| R04399 | Whole station becomes — + RLM context engine | 7708 | E0247 | non-negotiable | false | 10 |
| R04400 | Whole station becomes — + reward/value models | 7709 | E0247 | non-negotiable | false | 10 |
| R04401 | Whole station becomes — + AVX-512 deterministic scheduler | 7710 | E0247 | non-negotiable | false | 10 |
| R04402 | Whole station becomes — + REPL/tools | 7711 | E0247 | non-negotiable | false | 10 |
| R04403 | Whole station becomes — + memory/replay | 7712 | E0247 | non-negotiable | false | 10 |
| R04404 | Whole station becomes — = adaptive local intelligence | 7713 | E0247 | non-negotiable | false | 10 |
| R04405 | Key line — SLMs give reflexes | 7719 | E0247 | non-negotiable | false | 10 |
| R04406 | Key line — RLMs give long-horizon context navigation | 7720 | E0247 | non-negotiable | false | 10 |
| R04407 | Key line — RMs/RRMs give value judgment | 7721 | E0247 | non-negotiable | false | 10 |
| R04408 | Key line — LLMs give deep synthesis | 7722 | E0247 | non-negotiable | false | 10 |
| R04409 | Key line — AVX-512 gives law and scheduling | 7723 | E0247 | non-negotiable | false | 10 |
| R04410 | Key line — Workflows give durability | 7724 | E0247 | non-negotiable | false | 10 |
| R04411 | Key line — Profiles give choice | 7725 | E0247 | non-negotiable | false | 10 |
| R04412 | Key line — Evals give evolution | 7726 | E0247 | non-negotiable | false | 10 |
| R04413 | Not one mind — a programmable ecology of minds under deterministic control | 7729 | E0247 | non-negotiable | false | 10 |
| R04414 | Model-class stack operator-overrideable (llm / llm_slm / llm_slm_rlm / full) | 7421–7441 | F02126 | non-negotiable | true | 10 |
| R04415 | Env var `SOVEREIGN_MODEL_CLASS_STACK` | 7421–7441 | F02128 | non-negotiable | true | 10 |
| R04416 | CLI `--model-class-stack <mode>` | 7421–7441 | F02129 | non-negotiable | true | 10 |
| R04417 | Test — 11-role SLM swarm catalog round-trips through API | 7449–7461 | M00427 | non-negotiable | false | 10 |
| R04418 | Test — RLM 6-step loop runs end-to-end on synthetic long-context input | 7491–7499 | M00428 | non-negotiable | false | 10 |
| R04419 | Test — RLM subcall 8-field control word round-trips through encode/decode | 7543–7552 | M00434 | non-negotiable | false | 10 |
| R04420 | Composite — SLM Swarm + RLM Engine + Reward Plane + Profile Optimizer integrate with M015 programming plane / M016 learning / M017 model registry / M019 cognitive operators / M024 adaptive programming / M025 cognitive compiler — full intelligence stack | 7689–7729 | M00440 | non-negotiable | false | 10 |

— End of M026 milestone file.
