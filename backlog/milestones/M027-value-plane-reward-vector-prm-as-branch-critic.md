# M027 — Value plane — reward vector + PRM as branch critic

> Parent: `backlog/milestones/INDEX.md` row M027 (dump 7731–8121).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 7731–8121.
> All entries below are extracted from the dump line range. No invention.

## Epics (E0248–E0257)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0248 | Value, reward, and test-time intelligence — system that can choose better thoughts | 7746–7748 |
| E0249 | Research substrate — PRM survey / ThinkPRM / GenPRM / Best-of-N+BoNBoN+Best-of-Majority / LE-MCTS / HF search-and-learn cookbook | 7750–7757 |
| E0250 | The Value Plane — answers 7-question test (which thought to expand / which branch correct / which tool plan safe / which memory trustworthy / which answer to return / which profile / how much more compute) | 7761–7775 |
| E0251 | Reward Vector — 12-axis vector (correctness / evidence / schema_validity / tool_success / test_success / risk / latency / cost / novelty / user_preference / cache_reuse / confidence_calibration) | 7777–7816 |
| E0252 | PRM As Branch Critic — 5-input + 5-output advise-not-commit contract; "PRM proposes value, CPU applies law, Oracle verifies high-stakes commitments" | 7819–7849 |
| E0253 | Search Modes — 9-mode catalog (Greedy / Best-of-N / Self-consistency / Beam / Diverse beam / MCTS / RLM recursion / Debate / Program-of-thought) | 7851–7884 |
| E0254 | Adaptive Test-Time Compute — 5-difficulty allocation ladder + intelligence-budgeting formula (`expected_gain > compute_cost + latency_penalty + risk_penalty`) | 7886–7917 |
| E0255 | AVX-512 reward-guided scheduling — 7-array Hot SoA + bulk eligibility/expand/verify/kill masks + 4 compressed queues | 7919–7953 |
| E0256 | MCTS / RLM+PRM / SLM+Reward / Intelligence Dial — 5-tier user-facing dial (reflex / normal / deliberate / exhaustive / experimental) | 7955–8059 |
| E0257 | Value Plane architecture component + 8-plane full stack + closing rule "Intelligence is knowing which thoughts deserve more life" | 8061–8120 |

## Modules (M00441–M00458)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00441 | PRM substrate — Process Reward Models score intermediate reasoning steps (not just final answers) | 7752 | E0249 |
| M00442 | ThinkPRM substrate — reasoning-capable PRMs with best-of-N selection + reward-guided search | 7753 | E0249 |
| M00443 | GenPRM substrate — scales PRM test-time compute by having reward model reason generatively + code verification | 7754 | E0249 |
| M00444 | Best-of-N + BoNBoN + Best-of-Majority substrate — spend inference budget on multiple candidates and select better | 7755 | E0249 |
| M00445 | LE-MCTS substrate — multiple LLMs + Monte Carlo Tree Search guided by process rewards | 7756 | E0249 |
| M00446 | HF search-and-learn substrate — Best-of-N + beam search + Diverse Verifier Tree Search with PRM | 7757 | E0249 |
| M00447 | Value Plane 7-question contract — thought-expand / branch-correct / tool-plan-safe / memory-trustworthy / answer-return / profile-choose / compute-justified | 7763–7773 | E0250 |
| M00448 | Reward Vector 12-axis — correctness / evidence / schema_validity / tool_success / test_success / risk / latency / cost / novelty / user_preference / cache_reuse / confidence_calibration | 7783–7796 | E0251 |
| M00449 | Profile-weighted reward — fast / careful / autonomous / creative / private (5 profile examples with operator-readable axis weighting) | 7800–7815 | E0251 |
| M00450 | PRM branch-critic 5-input — branch_state / partial reasoning / tool observations / memory evidence / candidate next step | 7822–7829 | E0252 |
| M00451 | PRM branch-critic 5-output — step_score / risk_score / uncertainty / failure_mode / suggested_next_action | 7832–7839 | E0252 |
| M00452 | Reward-model authority law — PRM proposes value / CPU applies law / Oracle verifies high-stakes commitments | 7845–7849 | E0252 |
| M00453 | Search modes — Greedy / Best-of-N / Self-consistency / Beam / Diverse beam / MCTS / RLM recursion / Debate / Program-of-thought | 7855–7883 | E0253 |
| M00454 | Adaptive compute ladder — easy=SLM+validation / medium=scout+oracle / hard=branch-search+PRM+tools / long-context=RLM+memory+oracle / high-risk=oracle+verifier+human gate | 7894–7909 | E0254 |
| M00455 | Intelligence-budget formula — `expected_gain > compute_cost + latency_penalty + risk_penalty` | 7913–7914 | E0254 |
| M00456 | AVX-512 reward-guided 7-array Hot SoA — score_q16 / risk_u8 / uncertainty_u8 / cost_u8 / latency_u8 / depth_u8 / flags_u64 | 7925–7932 | E0255 |
| M00457 | AVX-512 bulk masks — eligible / expand / verify / kill + 4 compressed queues (expand_queue / verify_queue / kill_queue / human_gate_queue) | 7937–7950 | E0255 |
| M00458 | 8-plane full stack — Model / Control / Workflow / Execution / Memory / Value / Observability / Profile | 8076–8101 | E0257 |

## Features (F02211–F02295)

| F ID | Phrase | Dump line | Parent module | Category | Opt-in |
|---|---|---|---|---|---|
| F02211 | Toggle Value Plane backend (native / thinkprm-bridge / genprm-bridge / le-mcts-bridge) | 7752–7757 | E0249 | mode | true |
| F02212 | Profile knob — `value_plane_backend = native \| thinkprm \| genprm \| le_mcts` | 7752–7757 | E0249 | profile | true |
| F02213 | Env var `SOVEREIGN_VALUE_PLANE_BACKEND` | 7752–7757 | E0249 | env_var | true |
| F02214 | CLI `--value-plane-backend <name>` | 7752–7757 | E0249 | cli_verb | true |
| F02215 | PRM substrate — score intermediate reasoning steps not just final answers | 7752 | M00441 | composite | true |
| F02216 | ThinkPRM substrate — reasoning-capable PRMs + best-of-N selection + reward-guided search | 7753 | M00442 | composite | true |
| F02217 | GenPRM substrate — generative reward-model reasoning + code verification | 7754 | M00443 | composite | true |
| F02218 | Best-of-N substrate — sample N candidates + reward-rank | 7755 | M00444 | composite | true |
| F02219 | BoNBoN + Best-of-Majority substrate — variants of multi-candidate selection | 7755 | M00444 | composite | true |
| F02220 | LE-MCTS substrate — multiple LLMs + MCTS + process rewards | 7756 | M00445 | composite | true |
| F02221 | HF search-and-learn substrate — Best-of-N + beam + Diverse Verifier Tree Search with PRM | 7757 | M00446 | composite | true |
| F02222 | Value Plane question — Which thought is worth expanding? | 7766 | M00447 | composite | false |
| F02223 | Value Plane question — Which branch is likely correct? | 7767 | M00447 | composite | false |
| F02224 | Value Plane question — Which tool plan is safe? | 7768 | M00447 | composite | false |
| F02225 | Value Plane question — Which memory is trustworthy? | 7769 | M00447 | composite | false |
| F02226 | Value Plane question — Which answer should be returned? | 7770 | M00447 | composite | false |
| F02227 | Value Plane question — Which profile should be used? | 7771 | M00447 | composite | false |
| F02228 | Value Plane question — How much more compute is justified? | 7772 | M00447 | composite | false |
| F02229 | Reward vector axis — `correctness` | 7784 | M00448 | data_model | false |
| F02230 | Reward vector axis — `evidence` | 7785 | M00448 | data_model | false |
| F02231 | Reward vector axis — `schema_validity` | 7786 | M00448 | data_model | false |
| F02232 | Reward vector axis — `tool_success` | 7787 | M00448 | data_model | false |
| F02233 | Reward vector axis — `test_success` | 7788 | M00448 | data_model | false |
| F02234 | Reward vector axis — `risk` | 7789 | M00448 | data_model | false |
| F02235 | Reward vector axis — `latency` | 7790 | M00448 | data_model | false |
| F02236 | Reward vector axis — `cost` | 7791 | M00448 | data_model | false |
| F02237 | Reward vector axis — `novelty` | 7792 | M00448 | data_model | false |
| F02238 | Reward vector axis — `user_preference` | 7793 | M00448 | data_model | false |
| F02239 | Reward vector axis — `cache_reuse` | 7794 | M00448 | data_model | false |
| F02240 | Reward vector axis — `confidence_calibration` | 7795 | M00448 | data_model | false |
| F02241 | Profile reward-weighting — `fast` profile (latency high / correctness medium / oracle use low) | 7801–7803 | M00449 | profile | true |
| F02242 | Profile reward-weighting — `careful` profile (correctness+evidence high / latency low) | 7804–7806 | M00449 | profile | true |
| F02243 | Profile reward-weighting — `autonomous` profile (tool_success+risk+replay high) | 7807–7809 | M00449 | profile | true |
| F02244 | Profile reward-weighting — `creative` profile (novelty high / risk medium / verification late) | 7810–7812 | M00449 | profile | true |
| F02245 | Profile reward-weighting — `private` profile (locality+privacy high / network penalty huge) | 7813–7815 | M00449 | profile | true |
| F02246 | PRM branch-critic input — `branch_state` | 7824 | M00450 | data_model | false |
| F02247 | PRM branch-critic input — `partial reasoning` | 7825 | M00450 | data_model | false |
| F02248 | PRM branch-critic input — `tool observations` | 7826 | M00450 | data_model | false |
| F02249 | PRM branch-critic input — `memory evidence` | 7827 | M00450 | data_model | false |
| F02250 | PRM branch-critic input — `candidate next step` | 7828 | M00450 | data_model | false |
| F02251 | PRM branch-critic output — `step_score` | 7834 | M00451 | data_model | false |
| F02252 | PRM branch-critic output — `risk_score` | 7835 | M00451 | data_model | false |
| F02253 | PRM branch-critic output — `uncertainty` | 7836 | M00451 | data_model | false |
| F02254 | PRM branch-critic output — `failure_mode` | 7837 | M00451 | data_model | false |
| F02255 | PRM branch-critic output — `suggested_next_action` | 7838 | M00451 | data_model | false |
| F02256 | Reward-model authority — PRM proposes value | 7846 | M00452 | composite | false |
| F02257 | Reward-model authority — CPU applies law | 7847 | M00452 | composite | false |
| F02258 | Reward-model authority — Oracle verifies high-stakes commitments | 7848 | M00452 | composite | false |
| F02259 | Search mode — Greedy (one path, fastest) | 7857–7858 | M00453 | mode | true |
| F02260 | Search mode — Best-of-N (sample N candidates, reward-rank) | 7860–7861 | M00453 | mode | true |
| F02261 | Search mode — Self-consistency (sample N, vote/cluster final answers) | 7863–7864 | M00453 | mode | true |
| F02262 | Search mode — Beam (keep top K partial branches) | 7866–7867 | M00453 | mode | true |
| F02263 | Search mode — Diverse beam (keep different families of thought) | 7869–7870 | M00453 | mode | true |
| F02264 | Search mode — MCTS (expand promising branches with exploration bonus) | 7872–7873 | M00453 | mode | true |
| F02265 | Search mode — RLM recursion (decompose context and spawn child calls) | 7875–7876 | M00453 | mode | true |
| F02266 | Search mode — Debate (competing agents critique and merge) | 7878–7879 | M00453 | mode | true |
| F02267 | Search mode — Program-of-thought (generate executable check/code) | 7881–7882 | M00453 | mode | true |
| F02268 | Adaptive compute — `easy` (SLM + validation) | 7896–7897 | M00454 | mode | true |
| F02269 | Adaptive compute — `medium` (scout + oracle verify) | 7899–7900 | M00454 | mode | true |
| F02270 | Adaptive compute — `hard` (branch search + PRM + tools) | 7902–7903 | M00454 | mode | true |
| F02271 | Adaptive compute — `long-context` (RLM + memory/RAG + oracle synthesis) | 7905–7906 | M00454 | mode | true |
| F02272 | Adaptive compute — `high-risk` (oracle + verifier + human gate) | 7908–7909 | M00454 | mode | true |
| F02273 | Intelligence-budget formula — `expected_gain > compute_cost + latency_penalty + risk_penalty` | 7913–7914 | M00455 | composite | false |
| F02274 | AVX-512 Hot array — `score_q16[]` | 7926 | M00456 | data_model | false |
| F02275 | AVX-512 Hot array — `risk_u8[]` | 7927 | M00456 | data_model | false |
| F02276 | AVX-512 Hot array — `uncertainty_u8[]` | 7928 | M00456 | data_model | false |
| F02277 | AVX-512 Hot array — `cost_u8[]` | 7929 | M00456 | data_model | false |
| F02278 | AVX-512 Hot array — `latency_u8[]` | 7930 | M00456 | data_model | false |
| F02279 | AVX-512 Hot array — `depth_u8[]` | 7931 | M00456 | data_model | false |
| F02280 | AVX-512 Hot array — `flags_u64[]` | 7932 | M00456 | data_model | false |
| F02281 | AVX-512 bulk mask — `eligible = alive & policy_ok & budget_ok` | 7938 | M00457 | composite | false |
| F02282 | AVX-512 bulk mask — `expand = eligible & high_value & high_uncertainty` | 7939 | M00457 | composite | false |
| F02283 | AVX-512 bulk mask — `verify = eligible & high_risk \| final_candidate` | 7940 | M00457 | composite | false |
| F02284 | AVX-512 bulk mask — `kill = eligible & low_value & low_uncertainty` | 7941 | M00457 | composite | false |
| F02285 | Compressed queue — `expand_queue` | 7947 | M00457 | data_model | false |
| F02286 | Compressed queue — `verify_queue` | 7948 | M00457 | data_model | false |
| F02287 | Compressed queue — `kill_queue` | 7949 | M00457 | data_model | false |
| F02288 | Compressed queue — `human_gate_queue` | 7950 | M00457 | data_model | false |
| F02289 | Intelligence Dial — `reflex` (greedy / SLM-scout / low verification) | 8033, 8043–8044 | E0256 | mode | true |
| F02290 | Intelligence Dial — `normal` (retrieve + scout + oracle if uncertain) | 8034, 8046–8047 | E0256 | mode | true |
| F02291 | Intelligence Dial — `deliberate` (Best-of-N + PRM + oracle) | 8035, 8049–8050 | E0256 | mode | true |
| F02292 | Intelligence Dial — `exhaustive` (tree/MCTS + RLM + tools + multiple verifiers) | 8036, 8052–8053 | E0256 | mode | true |
| F02293 | Intelligence Dial — `experimental` (wide exploration, sandboxed, high novelty, no auto-commit) | 8037, 8055–8056 | E0256 | mode | true |
| F02294 | 8-plane full stack — Model / Control / Workflow / Execution / Memory / Value / Observability / Profile | 8076–8101 | M00458 | composite | false |
| F02295 | Composite — Closing rule "Intelligence is not just generating thoughts. Intelligence is knowing which thoughts deserve more life." | 8105–8108 | E0257 | composite | false |

## Requirements (R04421–R04590)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R04421 | Value, reward, and test-time intelligence is the next layer | 7746 | E0248 | non-negotiable | false | 10 |
| R04422 | Where SLM/RLM/LLM/workflow become a system that can choose better thoughts | 7748 | E0248 | non-negotiable | false | 10 |
| R04423 | Process Reward Models score intermediate reasoning steps, not just final answers | 7752 | M00441 | non-negotiable | false | 10 |
| R04424 | Recent PRM surveys frame PRMs as key move from outcome-only supervision to process supervision | 7752 | M00441 | non-negotiable | false | 10 |
| R04425 | ThinkPRM / "Process Reward Models That Think" uses reasoning-capable PRMs | 7753 | M00442 | non-negotiable | false | 10 |
| R04426 | ThinkPRM reports gains under best-of-N selection and reward-guided search | 7753 | M00442 | non-negotiable | false | 10 |
| R04427 | GenPRM scales PRM test-time compute by having the reward model reason generatively | 7754 | M00443 | non-negotiable | false | 10 |
| R04428 | GenPRM supports code verification | 7754 | M00443 | non-negotiable | false | 10 |
| R04429 | Best-of-N and Best-of-Majority style work explores how to spend inference budget on multiple candidates | 7755 | M00444 | non-negotiable | false | 10 |
| R04430 | LE-MCTS combines multiple LLMs with Monte Carlo Tree Search guided by process rewards | 7756 | M00445 | non-negotiable | false | 10 |
| R04431 | Hugging Face search-and-learn recipe shows Best-of-N, beam search, and Diverse Verifier Tree Search with a PRM | 7757 | M00446 | non-negotiable | false | 10 |
| R04432 | Workstation needs a Value Plane | 7759 | E0250 | non-negotiable | false | 10 |
| R04433 | Value Plane answers — Which thought is worth expanding? | 7766 | F02222 | non-negotiable | false | 10 |
| R04434 | Value Plane answers — Which branch is likely correct? | 7767 | F02223 | non-negotiable | false | 10 |
| R04435 | Value Plane answers — Which tool plan is safe? | 7768 | F02224 | non-negotiable | false | 10 |
| R04436 | Value Plane answers — Which memory is trustworthy? | 7769 | F02225 | non-negotiable | false | 10 |
| R04437 | Value Plane answers — Which answer should be returned? | 7770 | F02226 | non-negotiable | false | 10 |
| R04438 | Value Plane answers — Which profile should be used? | 7771 | F02227 | non-negotiable | false | 10 |
| R04439 | Value Plane answers — How much more compute is justified? | 7772 | F02228 | non-negotiable | false | 10 |
| R04440 | Value Plane is where intelligence becomes adaptive instead of just wide | 7775 | E0250 | non-negotiable | false | 10 |
| R04441 | Do NOT use one scalar reward too early | 7779 | M00448 | non-negotiable | false | 10 |
| R04442 | Use a reward vector | 7781 | M00448 | non-negotiable | false | 10 |
| R04443 | Reward vector axis — `correctness` | 7784 | F02229 | non-negotiable | false | 10 |
| R04444 | Reward vector axis — `evidence` | 7785 | F02230 | non-negotiable | false | 10 |
| R04445 | Reward vector axis — `schema_validity` | 7786 | F02231 | non-negotiable | false | 10 |
| R04446 | Reward vector axis — `tool_success` | 7787 | F02232 | non-negotiable | false | 10 |
| R04447 | Reward vector axis — `test_success` | 7788 | F02233 | non-negotiable | false | 10 |
| R04448 | Reward vector axis — `risk` | 7789 | F02234 | non-negotiable | false | 10 |
| R04449 | Reward vector axis — `latency` | 7790 | F02235 | non-negotiable | false | 10 |
| R04450 | Reward vector axis — `cost` | 7791 | F02236 | non-negotiable | false | 10 |
| R04451 | Reward vector axis — `novelty` | 7792 | F02237 | non-negotiable | false | 10 |
| R04452 | Reward vector axis — `user_preference` | 7793 | F02238 | non-negotiable | false | 10 |
| R04453 | Reward vector axis — `cache_reuse` | 7794 | F02239 | non-negotiable | false | 10 |
| R04454 | Reward vector axis — `confidence_calibration` | 7795 | F02240 | non-negotiable | false | 10 |
| R04455 | Profiles weight reward vector differently | 7798 | M00449 | non-negotiable | false | 10 |
| R04456 | Profile `fast` — latency high / correctness medium / oracle use low | 7801–7803 | F02241 | non-negotiable | true | 10 |
| R04457 | Profile `careful` — correctness/evidence high / latency low | 7804–7806 | F02242 | non-negotiable | true | 10 |
| R04458 | Profile `autonomous` — tool_success/risk/replay high | 7807–7809 | F02243 | non-negotiable | true | 10 |
| R04459 | Profile `creative` — novelty high / risk medium / verification late | 7810–7812 | F02244 | non-negotiable | true | 10 |
| R04460 | Profile `private` — locality/privacy high / network penalty huge | 7813–7815 | F02245 | non-negotiable | true | 10 |
| R04461 | Same system, different intelligence character | 7817 | M00449 | non-negotiable | false | 10 |
| R04462 | Every branch frame can be scored by PRM | 7821 | M00450 | non-negotiable | false | 10 |
| R04463 | PRM input — `branch_state` | 7824 | F02246 | non-negotiable | false | 10 |
| R04464 | PRM input — `partial reasoning` | 7825 | F02247 | non-negotiable | false | 10 |
| R04465 | PRM input — `tool observations` | 7826 | F02248 | non-negotiable | false | 10 |
| R04466 | PRM input — `memory evidence` | 7827 | F02249 | non-negotiable | false | 10 |
| R04467 | PRM input — `candidate next step` | 7828 | F02250 | non-negotiable | false | 10 |
| R04468 | PRM/RRM output — `step_score` | 7834 | F02251 | non-negotiable | false | 10 |
| R04469 | PRM/RRM output — `risk_score` | 7835 | F02252 | non-negotiable | false | 10 |
| R04470 | PRM/RRM output — `uncertainty` | 7836 | F02253 | non-negotiable | false | 10 |
| R04471 | PRM/RRM output — `failure_mode` | 7837 | F02254 | non-negotiable | false | 10 |
| R04472 | PRM/RRM output — `suggested_next_action` | 7838 | F02255 | non-negotiable | false | 10 |
| R04473 | Reward model does NOT commit — it advises | 7843 | M00452 | non-negotiable | false | 10 |
| R04474 | PRM proposes value | 7846 | F02256 | non-negotiable | false | 10 |
| R04475 | CPU applies law | 7847 | F02257 | non-negotiable | false | 10 |
| R04476 | Oracle verifies high-stakes commitments | 7848 | F02258 | non-negotiable | false | 10 |
| R04477 | Runtime gives multiple reasoning/search choices | 7853 | M00453 | non-negotiable | false | 10 |
| R04478 | Search mode — Greedy (one path, fastest) | 7857–7858 | F02259 | non-negotiable | true | 10 |
| R04479 | Search mode — Best-of-N (sample N candidates, reward-rank) | 7860–7861 | F02260 | non-negotiable | true | 10 |
| R04480 | Search mode — Self-consistency (sample N, vote/cluster final answers) | 7863–7864 | F02261 | non-negotiable | true | 10 |
| R04481 | Search mode — Beam (keep top K partial branches) | 7866–7867 | F02262 | non-negotiable | true | 10 |
| R04482 | Search mode — Diverse beam (keep different families of thought) | 7869–7870 | F02263 | non-negotiable | true | 10 |
| R04483 | Search mode — MCTS (expand promising branches with exploration bonus) | 7872–7873 | F02264 | non-negotiable | true | 10 |
| R04484 | Search mode — RLM recursion (decompose context and spawn child calls) | 7875–7876 | F02265 | non-negotiable | true | 10 |
| R04485 | Search mode — Debate (competing agents critique and merge) | 7878–7879 | F02266 | non-negotiable | true | 10 |
| R04486 | Search mode — Program-of-thought (generate executable check/code) | 7881–7882 | F02267 | non-negotiable | true | 10 |
| R04487 | Profiles choose among search modes | 7884 | E0253 | non-negotiable | false | 10 |
| R04488 | Adaptive test-time compute is big | 7888 | E0254 | non-negotiable | false | 10 |
| R04489 | System should NOT always think hard | 7890 | M00454 | non-negotiable | false | 10 |
| R04490 | System should estimate difficulty and allocate compute | 7892 | M00454 | non-negotiable | false | 10 |
| R04491 | Adaptive compute — `easy` (SLM answer + validation) | 7896–7897 | F02268 | non-negotiable | true | 10 |
| R04492 | Adaptive compute — `medium` (scout + oracle verify) | 7899–7900 | F02269 | non-negotiable | true | 10 |
| R04493 | Adaptive compute — `hard` (branch search + PRM + tools) | 7902–7903 | F02270 | non-negotiable | true | 10 |
| R04494 | Adaptive compute — `long-context` (RLM + memory/RAG + oracle synthesis) | 7905–7906 | F02271 | non-negotiable | true | 10 |
| R04495 | Adaptive compute — `high-risk` (oracle + verifier + human gate) | 7908–7909 | F02272 | non-negotiable | true | 10 |
| R04496 | Branch can request more compute only if value justifies it | 7911 | M00455 | non-negotiable | false | 10 |
| R04497 | Intelligence-budgeting formula — `expected_gain > compute_cost + latency_penalty + risk_penalty` | 7913–7914 | F02273 | non-negotiable | false | 10 |
| R04498 | Value Plane produces scores; CPU turns them into routing | 7921 | M00457 | non-negotiable | false | 10 |
| R04499 | Hot array — `score_q16[]` | 7926 | F02274 | non-negotiable | false | 10 |
| R04500 | Hot array — `risk_u8[]` | 7927 | F02275 | non-negotiable | false | 10 |
| R04501 | Hot array — `uncertainty_u8[]` | 7928 | F02276 | non-negotiable | false | 10 |
| R04502 | Hot array — `cost_u8[]` | 7929 | F02277 | non-negotiable | false | 10 |
| R04503 | Hot array — `latency_u8[]` | 7930 | F02278 | non-negotiable | false | 10 |
| R04504 | Hot array — `depth_u8[]` | 7931 | F02279 | non-negotiable | false | 10 |
| R04505 | Hot array — `flags_u64[]` | 7932 | F02280 | non-negotiable | false | 10 |
| R04506 | AVX-512 bulk mask — `eligible = alive & policy_ok & budget_ok` | 7938 | F02281 | non-negotiable | false | 10 |
| R04507 | AVX-512 bulk mask — `expand = eligible & high_value & high_uncertainty` | 7939 | F02282 | non-negotiable | false | 10 |
| R04508 | AVX-512 bulk mask — `verify = eligible & high_risk \| final_candidate` | 7940 | F02283 | non-negotiable | false | 10 |
| R04509 | AVX-512 bulk mask — `kill = eligible & low_value & low_uncertainty` | 7941 | F02284 | non-negotiable | false | 10 |
| R04510 | Compressed queue — `expand_queue` | 7947 | F02285 | non-negotiable | false | 10 |
| R04511 | Compressed queue — `verify_queue` | 7948 | F02286 | non-negotiable | false | 10 |
| R04512 | Compressed queue — `kill_queue` | 7949 | F02287 | non-negotiable | false | 10 |
| R04513 | Compressed queue — `human_gate_queue` | 7950 | F02288 | non-negotiable | false | 10 |
| R04514 | This is reward-guided cognition with deterministic scheduling | 7953 | E0255 | non-negotiable | false | 10 |
| R04515 | MCTS — state = branch/workflow/memory/tool state | 7960–7961 | E0256 | non-negotiable | false | 10 |
| R04516 | MCTS — action = model call / tool call / retrieve / summarize / verify / ask human | 7963–7964 | E0256 | non-negotiable | false | 10 |
| R04517 | MCTS — transition = observation result | 7966–7967 | E0256 | non-negotiable | false | 10 |
| R04518 | MCTS — reward = PRM + tests + policy + user feedback | 7969–7970 | E0256 | non-negotiable | false | 10 |
| R04519 | MCTS — selection = choose branch with best UCB-style score | 7972–7973 | E0256 | non-negotiable | false | 10 |
| R04520 | MCTS — expansion = 3090/SLM generates options | 7975–7976 | E0256 | non-negotiable | false | 10 |
| R04521 | MCTS — simulation = cheap SLM rollout or tool dry-run | 7978–7979 | E0256 | non-negotiable | false | 10 |
| R04522 | MCTS — backup = update branch value | 7981–7982 | E0256 | non-negotiable | false | 10 |
| R04523 | Blackwell oracle is not used everywhere — used at important frontier points | 7985 | E0256 | non-negotiable | false | 10 |
| R04524 | RLM can recursively decompose context, but needs value guidance | 7989 | E0256 | non-negotiable | false | 10 |
| R04525 | Otherwise RLM may inspect irrelevant slices | 7991 | E0256 | non-negotiable | false | 10 |
| R04526 | Use PRM/RM to score subquestion quality | 7996 | E0256 | non-negotiable | false | 10 |
| R04527 | Use PRM/RM to score slice relevance | 7997 | E0256 | non-negotiable | false | 10 |
| R04528 | Use PRM/RM to score child answer reliability | 7998 | E0256 | non-negotiable | false | 10 |
| R04529 | Use PRM/RM to score aggregation quality | 7999 | E0256 | non-negotiable | false | 10 |
| R04530 | Use PRM/RM to score uncertainty | 8000 | E0256 | non-negotiable | false | 10 |
| R04531 | Then recurse only where worth it | 8003 | E0256 | non-negotiable | false | 10 |
| R04532 | Gives recursive context navigation + reward-guided pruning | 8008 | E0256 | non-negotiable | false | 10 |
| R04533 | Excellent for huge repos, documents, logs, research corpora | 8011 | E0256 | non-negotiable | false | 10 |
| R04534 | SLMs become cheap policy/value workers | 8015 | E0256 | non-negotiable | false | 10 |
| R04535 | SLM worker — router | 8018 | E0256 | non-negotiable | true | 10 |
| R04536 | SLM worker — critic | 8019 | E0256 | non-negotiable | true | 10 |
| R04537 | SLM worker — schema checker | 8020 | E0256 | non-negotiable | true | 10 |
| R04538 | SLM worker — difficulty estimator | 8021 | E0256 | non-negotiable | true | 10 |
| R04539 | SLM worker — tool planner | 8022 | E0256 | non-negotiable | true | 10 |
| R04540 | SLM worker — uncertainty assessor | 8023 | E0256 | non-negotiable | true | 10 |
| R04541 | Big model does not need to inspect every branch — SLM swarm triages | 8026 | E0256 | non-negotiable | false | 10 |
| R04542 | User-facing intelligence dial choice — `reflex` | 8033 | F02289 | non-negotiable | true | 10 |
| R04543 | User-facing intelligence dial choice — `normal` | 8034 | F02290 | non-negotiable | true | 10 |
| R04544 | User-facing intelligence dial choice — `deliberate` | 8035 | F02291 | non-negotiable | true | 10 |
| R04545 | User-facing intelligence dial choice — `exhaustive` | 8036 | F02292 | non-negotiable | true | 10 |
| R04546 | User-facing intelligence dial choice — `experimental` | 8037 | F02293 | non-negotiable | true | 10 |
| R04547 | Intelligence dial `reflex` — greedy / SLM/scout / low verification | 8043–8044 | F02289 | non-negotiable | true | 10 |
| R04548 | Intelligence dial `normal` — retrieve + scout + oracle if uncertain | 8046–8047 | F02290 | non-negotiable | true | 10 |
| R04549 | Intelligence dial `deliberate` — Best-of-N + PRM + oracle | 8049–8050 | F02291 | non-negotiable | true | 10 |
| R04550 | Intelligence dial `exhaustive` — tree/MCTS + RLM + tools + multiple verifiers | 8052–8053 | F02292 | non-negotiable | true | 10 |
| R04551 | Intelligence dial `experimental` — wide exploration / sandboxed / high novelty / no auto-commit | 8055–8056 | F02293 | non-negotiable | true | 10 |
| R04552 | That is SMART, ADAPTIVE, OPTIONS | 8059 | E0256 | non-negotiable | false | 10 |
| R04553 | Value Plane architecture component — PRM/RRM/ORM models | 8067 | E0257 | non-negotiable | false | 10 |
| R04554 | Value Plane architecture component — reward vector calculator | 8068 | E0257 | non-negotiable | false | 10 |
| R04555 | Value Plane architecture component — branch value estimator | 8069 | E0257 | non-negotiable | false | 10 |
| R04556 | Value Plane architecture component — difficulty estimator | 8070 | E0257 | non-negotiable | false | 10 |
| R04557 | Value Plane architecture component — compute budget allocator | 8071 | E0257 | non-negotiable | false | 10 |
| R04558 | Value Plane architecture component — search policy selector | 8072 | E0257 | non-negotiable | false | 10 |
| R04559 | Full stack plane — Model Plane (LLM / SLM / RLM / perception / reward models) | 8079–8080 | M00458 | non-negotiable | false | 10 |
| R04560 | Full stack plane — Control Plane (AVX-512 deterministic scheduler) | 8082–8083 | M00458 | non-negotiable | false | 10 |
| R04561 | Full stack plane — Workflow Plane (compiled DAGs and futures) | 8085–8086 | M00458 | non-negotiable | false | 10 |
| R04562 | Full stack plane — Execution Plane (REPL / tools / sandboxes) | 8088–8089 | M00458 | non-negotiable | false | 10 |
| R04563 | Full stack plane — Memory Plane (RAG / KV / ZFS / replay / context folding) | 8091–8092 | M00458 | non-negotiable | false | 10 |
| R04564 | Full stack plane — Value Plane (scoring / search / compute allocation) | 8094–8095 | M00458 | non-negotiable | false | 10 |
| R04565 | Full stack plane — Observability Plane (traces / telemetry / evals / adaptation) | 8097–8098 | M00458 | non-negotiable | false | 10 |
| R04566 | Full stack plane — Profile Plane (user-selectable reward/policy personalities) | 8100–8101 | M00458 | non-negotiable | false | 10 |
| R04567 | Core insight — Intelligence is not just generating thoughts | 8106 | E0257 | non-negotiable | false | 10 |
| R04568 | Core insight — Intelligence is knowing which thoughts deserve more life | 8107 | E0257 | non-negotiable | false | 10 |
| R04569 | That is what the Value Plane gives you | 8110 | E0257 | non-negotiable | false | 10 |
| R04570 | The SLM generates cheaply | 8112 | E0257 | non-negotiable | false | 10 |
| R04571 | The RLM navigates context | 8113 | E0257 | non-negotiable | false | 10 |
| R04572 | The PRM scores process | 8114 | E0257 | non-negotiable | false | 10 |
| R04573 | The oracle judges hard cases | 8115 | E0257 | non-negotiable | false | 10 |
| R04574 | The AVX-512 scheduler allocates life to branches | 8116 | E0257 | non-negotiable | false | 10 |
| R04575 | The workflow commits only what survives law | 8117 | E0257 | non-negotiable | false | 10 |
| R04576 | That is the adaptive station | 8119 | E0257 | non-negotiable | false | 10 |
| R04577 | Value Plane backend operator-overrideable (native / thinkprm / genprm / le_mcts) | 7752–7757 | F02211 | non-negotiable | true | 10 |
| R04578 | Env var `SOVEREIGN_VALUE_PLANE_BACKEND` | 7752–7757 | F02213 | non-negotiable | true | 10 |
| R04579 | CLI `--value-plane-backend <name>` | 7752–7757 | F02214 | non-negotiable | true | 10 |
| R04580 | API `POST /v1/value/score` — submit branch + receive reward vector | 7777–7796 | M00448 | non-negotiable | true | 10 |
| R04581 | API `POST /v1/value/branch-critic` — PRM 5-in/5-out branch advise | 7822–7839 | M00450 + M00451 | non-negotiable | true | 10 |
| R04582 | API `POST /v1/value/dial` — set intelligence dial (reflex/normal/deliberate/exhaustive/experimental) | 8033–8038 | E0256 | non-negotiable | true | 10 |
| R04583 | Dashboard — Value Plane scoreboard (per-branch reward-vector heatmap) | 7777–7796 | M00448 | non-negotiable | true | 10 |
| R04584 | Dashboard — Intelligence Dial selector + active mode + 5-tier preview | 8033–8057 | E0256 | non-negotiable | true | 10 |
| R04585 | Test — 12-axis reward vector round-trips through API | 7783–7796 | M00448 | non-negotiable | false | 10 |
| R04586 | Test — PRM 5-in/5-out branch-critic round-trips through API | 7822–7839 | M00450 + M00451 | non-negotiable | false | 10 |
| R04587 | Test — each of 9 search modes runs end-to-end on sample task | 7855–7883 | M00453 | non-negotiable | false | 10 |
| R04588 | Test — adaptive compute ladder routes synthetic difficulty levels to correct compute tier | 7894–7909 | M00454 | non-negotiable | false | 10 |
| R04589 | Test — AVX-512 4-mask bulk evaluation matches scalar reference on synthetic 1000-branch corpus | 7937–7942 | M00457 | non-negotiable | false | 10 |
| R04590 | Composite — Value Plane is the 6th plane of the 8-plane full stack; integrates with M015 programming + M016 learning + M017 model registry + M019 cognitive operators + M020 semantic ISA + M021 6-layer weave + M022 Cognitive Frame + M024 adaptive programming + M025 cognitive compiler + M026 SLM swarm/RLM engine/RM-PRM judges (M027 is the value layer in the M026 reward stack) | 8061–8120 | E0257 | non-negotiable | false | 10 |

— End of M027 milestone file.
