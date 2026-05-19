# M018 — Serving topology — local inference fabric

> Parent: `backlog/milestones/INDEX.md` row M018 (dump 4631–4991).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 4631–4991.
> All entries below are extracted from the dump line range. No invention.

## Epics (E0156–E0166)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0156 | Serving topology — how inference actually flows through the machine | 4646–4658 |
| E0157 | Substrate research — Dynamo + TensorRT-LLM disaggregated serving (NIXL/UCX KV transfer) + KV cache reuse + SGLang EAGLE + RadixAttention | 4660–4662 |
| E0158 | Local Inference Fabric — not "one server process" | 4664–4666 |
| E0159 | Six serving roles — Oracle / Scout / Perception / Embedding-Rerank / Control Runtime / KV-Memory | 4668–4694 |
| E0160 | The Split — hardware split vs phase split; do NOT layer-split a single model across two non-NVLink GPUs | 4696–4735 |
| E0161 | Three Serving Modes — A Low-Latency Interactive / B Agentic Batch / C Long-Context Workbench | 4737–4785 |
| E0162 | KV-Aware Routing — route by cache, not just load | 4787–4814 |
| E0163 | Speculative Parallelism — service-level not just model-level; 3090 ahead / Blackwell verifying / CPU packed queues | 4816–4843 |
| E0164 | Queue Design — 9 named queues + per-queue 6-axis weight | 4845–4872 |
| E0165 | Batching Rules + Backend Strategy + Abstraction Layer — multi-backend abstraction surface | 4874–4922 |
| E0166 | Model Fit Reality + Final Serving Fabric + "Model server dumb / runtime smart" rule | 4924–4990 |

## Modules (M00285–M00301)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00285 | Serving role — Oracle Server (RTX PRO 6000, large model, final verification, synthesis, long context) | 4670–4673 | E0159 |
| M00286 | Serving role — Scout Server (RTX 3090 or VM, draft model, small agent, reranker, perception, speculative expansion) | 4675–4677 | E0159 |
| M00287 | Serving role — Perception Server (optional, 3090, Nemotron Nano Omni screen/doc/audio/video understanding) | 4679–4681 | E0159 |
| M00288 | Serving role — Embedding/Rerank Server (3090 or CPU, memory retrieval support) | 4683–4685 | E0159 |
| M00289 | Serving role — Control Runtime (CPU AVX-512, receives user task, chooses routes, owns branch state) | 4687–4689 | E0159 |
| M00290 | Serving role — KV/Memory Service (RAM/ZFS, content-addressed KV refs, prompt blocks, cache metadata) | 4691–4693 | E0159 |
| M00291 | Mode A Low-Latency Interactive — CPU retrieves context → 3090 drafts/reranks → Blackwell generates → CPU enforces structured output/tools (chat / coding help / command planning) | 4741–4754 | E0161 |
| M00292 | Mode B Agentic Batch — CPU spawns branch frontier → 3090 expands many options → CPU compresses+prunes → Blackwell verifies frontier winners → tools execute transactionally (coding/research/automation agents) | 4756–4770 | E0161 |
| M00293 | Mode C Long-Context Workbench — CPU builds content-addressed context → KV cache + prefix reuse aggressively → Blackwell prefill = expensive asset → 3090 handles summaries+retrieval (repo-wide / documents / audits) | 4772–4785 | E0161 |
| M00294 | Request envelope for routing — model_id / tokenizer_id / prompt_hashes / kv_ref_candidates / branch_parent / cache_policy | 4801–4810 | E0162 |
| M00295 | Speculation triangle — 3090 ahead / Blackwell verifying / CPU packed queues | 4839–4842 | E0163 |
| M00296 | Nine named queues — oracle_prefill / oracle_decode / oracle_verify / scout_draft / scout_rerank / perception / embedding / tool_intent / human_gate | 4849–4858 | E0164 |
| M00297 | Per-queue 6-axis weight — priority / deadline / batchability / risk / cache_affinity / model_affinity | 4862–4870 | E0164 |
| M00298 | Batching rule positives + negatives — same model/tokenizer/schema/max-tokens/context-length/cache-affinity vs latency-critical-vs-huge / different-grammar-mask / high-risk-tool-boundary / will-evict-valuable-KV | 4876–4891 | E0165 |
| M00299 | Multi-backend strategy — vLLM / SGLang / TensorRT-LLM / llama.cpp (do not marry one) | 4894–4910 | E0165 |
| M00300 | Backend abstraction layer — `Generate / Embed / Rerank / Perceive / Verify` surface | 4912–4922 | E0165 |
| M00301 | Final Serving Fabric — Control Runtime / Model Gateway / Cache Router / GPU Workers / Tool Workers / Telemetry + Model-server-dumb-runtime-smart rule | 4943–4990 | E0166 |

## Features (F01446–F01530)

| F ID | Phrase | Dump line | Parent module | Category | Opt-in |
|---|---|---|---|---|---|
| F01446 | Toggle serving mode (A interactive / B agentic batch / C long-context workbench / auto) | 4737–4785 | E0161 | mode | true |
| F01447 | Profile knob — `serving_mode = interactive \| agentic_batch \| long_context \| auto` | 4737–4785 | E0161 | profile | true |
| F01448 | Env var `SOVEREIGN_SERVING_MODE` | 4737–4785 | E0161 | env_var | true |
| F01449 | CLI `--serving-mode <mode>` | 4737–4785 | E0161 | cli_verb | true |
| F01450 | Mode A pipeline node — CPU retrieves context | 4748 | M00291 | composite | false |
| F01451 | Mode A pipeline node — 3090 drafts / reranks | 4749 | M00291 | composite | false |
| F01452 | Mode A pipeline node — Blackwell generates | 4750 | M00291 | composite | false |
| F01453 | Mode A pipeline node — CPU enforces structured output / tools | 4751 | M00291 | composite | false |
| F01454 | Mode A target — chat / coding help / command planning | 4754 | M00291 | composite | true |
| F01455 | Mode B pipeline node — CPU spawns branch frontier | 4763 | M00292 | composite | false |
| F01456 | Mode B pipeline node — 3090 expands many options | 4764 | M00292 | composite | false |
| F01457 | Mode B pipeline node — CPU compresses and prunes | 4765 | M00292 | composite | false |
| F01458 | Mode B pipeline node — Blackwell verifies frontier winners | 4766 | M00292 | composite | false |
| F01459 | Mode B pipeline node — tools execute transactionally | 4767 | M00292 | composite | false |
| F01460 | Mode B target — coding agents / research agents / automation | 4770 | M00292 | composite | true |
| F01461 | Mode C pipeline node — CPU builds content-addressed context | 4779 | M00293 | composite | false |
| F01462 | Mode C pipeline node — KV cache / prefix reuse aggressively | 4780 | M00293 | composite | false |
| F01463 | Mode C pipeline node — Blackwell prefill is treated as expensive asset | 4781 | M00293 | composite | false |
| F01464 | Mode C pipeline node — 3090 handles summaries and retrieval | 4782 | M00293 | composite | false |
| F01465 | Mode C target — repo-wide work / documents / audits | 4785 | M00293 | composite | true |
| F01466 | Disaggregated serving — split prefill vs decode | 4660 | E0157 | mode | true |
| F01467 | Disaggregated KV transfer — NIXL / UCX | 4660 | E0157 | mode | true |
| F01468 | Disaggregated KV-aware routing — event-driven | 4660 | E0162 | mode | true |
| F01469 | Request envelope field — `model_id` | 4804 | M00294 | data_model | false |
| F01470 | Request envelope field — `tokenizer_id` | 4805 | M00294 | data_model | false |
| F01471 | Request envelope field — `prompt_hashes` | 4806 | M00294 | data_model | false |
| F01472 | Request envelope field — `kv_ref_candidates` | 4807 | M00294 | data_model | false |
| F01473 | Request envelope field — `branch_parent` | 4808 | M00294 | data_model | false |
| F01474 | Request envelope field — `cache_policy` | 4809 | M00294 | data_model | false |
| F01475 | KV-aware routing question — Which server already has this prefix hot? | 4794 | E0162 | composite | false |
| F01476 | KV-aware routing question — Which model has matching tokenizer? | 4795 | E0162 | composite | false |
| F01477 | KV-aware routing question — Which KV blocks are reusable? | 4796 | E0162 | composite | false |
| F01478 | KV-aware routing question — Which branch shares parent context? | 4797 | E0162 | composite | false |
| F01479 | KV-aware routing question — Which context block is expensive to rebuild? | 4798 | E0162 | composite | false |
| F01480 | Speculation triangle — 3090 should almost always be working ahead | 4840 | M00295 | composite | false |
| F01481 | Speculation triangle — Blackwell should almost always be verifying or generating | 4841 | M00295 | composite | false |
| F01482 | Speculation triangle — CPU should almost always have packed queues ready | 4842 | M00295 | composite | false |
| F01483 | Queue — `oracle_prefill_queue` | 4850 | M00296 | data_model | false |
| F01484 | Queue — `oracle_decode_queue` | 4851 | M00296 | data_model | false |
| F01485 | Queue — `oracle_verify_queue` | 4852 | M00296 | data_model | false |
| F01486 | Queue — `scout_draft_queue` | 4853 | M00296 | data_model | false |
| F01487 | Queue — `scout_rerank_queue` | 4854 | M00296 | data_model | false |
| F01488 | Queue — `perception_queue` | 4855 | M00296 | data_model | false |
| F01489 | Queue — `embedding_queue` | 4856 | M00296 | data_model | false |
| F01490 | Queue — `tool_intent_queue` | 4857 | M00296 | data_model | false |
| F01491 | Queue — `human_gate_queue` | 4858 | M00296 | data_model | false |
| F01492 | Queue-weight axis — priority | 4863 | M00297 | data_model | false |
| F01493 | Queue-weight axis — deadline | 4864 | M00297 | data_model | false |
| F01494 | Queue-weight axis — batchability | 4865 | M00297 | data_model | false |
| F01495 | Queue-weight axis — risk | 4866 | M00297 | data_model | false |
| F01496 | Queue-weight axis — cache_affinity | 4867 | M00297 | data_model | false |
| F01497 | Queue-weight axis — model_affinity | 4868 | M00297 | data_model | false |
| F01498 | Batch positive — same model | 4878 | M00298 | composite | false |
| F01499 | Batch positive — same tokenizer | 4879 | M00298 | composite | false |
| F01500 | Batch positive — same output schema | 4880 | M00298 | composite | false |
| F01501 | Batch positive — compatible max tokens | 4881 | M00298 | composite | false |
| F01502 | Batch positive — similar context length | 4882 | M00298 | composite | false |
| F01503 | Batch positive — same cache affinity | 4883 | M00298 | composite | false |
| F01504 | Batch negative — one is latency-critical and one is huge | 4886 | M00298 | composite | false |
| F01505 | Batch negative — different grammar masks cause overhead | 4887 | M00298 | composite | false |
| F01506 | Batch negative — one has high-risk tool boundary | 4888 | M00298 | composite | false |
| F01507 | Batch negative — one will evict valuable KV | 4889 | M00298 | composite | false |
| F01508 | Backend abstraction — `Generate(request) -> tokens/result` | 4915 | M00300 | api_endpoint | false |
| F01509 | Backend abstraction — `Embed(request) -> vectors` | 4916 | M00300 | api_endpoint | false |
| F01510 | Backend abstraction — `Rerank(request) -> scores` | 4917 | M00300 | api_endpoint | false |
| F01511 | Backend abstraction — `Perceive(request) -> structured scene/doc/audio state` | 4918 | M00300 | api_endpoint | false |
| F01512 | Backend abstraction — `Verify(request) -> accept/reject/score` | 4919 | M00300 | api_endpoint | false |
| F01513 | Model fit advisory — single 96GB Blackwell may not host every model official high-throughput config | 4926–4928 | M00301 | composite | true |
| F01514 | Workstation strength — run one strong oracle | 4935 | M00301 | composite | false |
| F01515 | Workstation strength — run several fast specialists | 4936 | M00301 | composite | false |
| F01516 | Workstation strength — route intelligently | 4937 | M00301 | composite | false |
| F01517 | Workstation strength — cache aggressively | 4938 | M00301 | composite | false |
| F01518 | Workstation strength — speculate safely | 4939 | M00301 | composite | false |
| F01519 | Workstation strength — commit deterministically | 4940 | M00301 | composite | false |
| F01520 | Final Serving Fabric — Control Runtime owns task graph, branches, policy, queues | 4948–4950 | M00301 | composite | false |
| F01521 | Final Serving Fabric — Model Gateway abstracts vLLM/SGLang/TRT-LLM/llama.cpp | 4951–4952 | M00301 | composite | false |
| F01522 | Final Serving Fabric — Cache Router tracks KV/prefix/model affinity | 4954–4955 | M00301 | composite | false |
| F01523 | Final Serving Fabric — GPU Workers (blackwell-oracle / 3090-scout / 3090-perception / cpu-rerank fallback) | 4957–4961 | M00301 | composite | false |
| F01524 | Final Serving Fabric — Tool Workers (sandboxed, gated, replayed) | 4963–4964 | M00301 | composite | false |
| F01525 | Final Serving Fabric — Telemetry feeds queue weights and routing | 4966–4967 | M00301 | composite | false |
| F01526 | API `POST /v1/route` — returns chosen-server + reason for a request envelope | 4787–4814 | E0162 | api_endpoint | true |
| F01527 | API `GET /v1/queues` — returns per-queue depth + 6-axis weight summary | 4845–4872 | M00296 | api_endpoint | true |
| F01528 | Dashboard — local inference fabric overview (6 serving roles + 3 modes + 9 queues + telemetry overlay) | 4664–4990 | E0158 | dashboard | true |
| F01529 | Dashboard — KV-aware routing inspector (per request envelope + matched cache+model) | 4787–4814 | M00294 | dashboard | true |
| F01530 | Composite — "The model server should be dumb. The runtime should be smart." rule enforcement | 4972–4988 | M00301 | composite | false |

## Requirements (R02891–R03060)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R02891 | How should inference actually flow through the machine? | 4650–4651 | E0156 | non-negotiable | false | 10 |
| R02892 | Theme — separate phases, reuse KV, route by cache/state, speculate in parallel | 4656–4657 | E0156 | non-negotiable | false | 10 |
| R02893 | NVIDIA Dynamo and TensorRT-LLM support disaggregated serving — splitting prefill vs decode | 4660 | E0157 | non-negotiable | false | 10 |
| R02894 | TensorRT-LLM uses NIXL/UCX for KV cache transfer in disaggregated setups | 4660 | E0157 | non-negotiable | false | 10 |
| R02895 | TensorRT-LLM has KV cache reuse optimizations and event-driven KV-aware routing | 4660 | E0157 | non-negotiable | false | 10 |
| R02896 | SGLang has EAGLE-style speculative decoding | 4662 | E0157 | non-negotiable | false | 10 |
| R02897 | SGLang has RadixAttention for KV reuse in generation programs with loops/conditionals | 4662 | E0157 | non-negotiable | false | 10 |
| R02898 | Strong design is NOT "one server process" | 4664 | E0158 | non-negotiable | false | 10 |
| R02899 | Strong design is a local inference fabric | 4666 | E0158 | non-negotiable | false | 10 |
| R02900 | Role — Oracle Server (RTX PRO 6000, large model, final verification, synthesis, long context) | 4671–4673 | M00285 | non-negotiable | false | 10 |
| R02901 | Role — Scout Server (RTX 3090 or VM, draft model, small agent model, reranker, perception, speculative expansion) | 4675–4677 | M00286 | non-negotiable | false | 10 |
| R02902 | Role — Perception Server (optional, 3090, Nemotron Nano Omni screen/doc/audio/video understanding) | 4679–4681 | M00287 | non-negotiable | false | 10 |
| R02903 | Role — Embedding/Rerank Server (3090 or CPU, memory retrieval support) | 4683–4685 | M00288 | non-negotiable | false | 10 |
| R02904 | Role — Control Runtime (CPU AVX-512, receives user task, chooses routes, owns branch state) | 4687–4689 | M00289 | non-negotiable | false | 10 |
| R02905 | Role — KV/Memory Service (RAM/ZFS, content-addressed KV refs, prompt blocks, cache metadata) | 4691–4693 | M00290 | non-negotiable | false | 10 |
| R02906 | Two kinds of split — hardware split vs phase split | 4700–4706 | E0160 | non-negotiable | false | 10 |
| R02907 | Two-GPU workstation without NVLink — do NOT split a single model layer-by-layer across GPUs | 4708 | E0160 | non-negotiable | false | 10 |
| R02908 | Prefer separate services | 4713 | E0160 | non-negotiable | false | 10 |
| R02909 | Prefer separate model roles | 4714 | E0160 | non-negotiable | false | 10 |
| R02910 | Prefer compact message passing | 4715 | E0160 | non-negotiable | false | 10 |
| R02911 | Move tokens | 4721 | E0160 | non-negotiable | false | 10 |
| R02912 | Move candidate ids | 4722 | E0160 | non-negotiable | false | 10 |
| R02913 | Move summaries | 4723 | E0160 | non-negotiable | false | 10 |
| R02914 | Move scores | 4724 | E0160 | non-negotiable | false | 10 |
| R02915 | Move hashes | 4725 | E0160 | non-negotiable | false | 10 |
| R02916 | Move KV refs when local to same engine | 4726 | E0160 | non-negotiable | false | 10 |
| R02917 | Avoid moving huge activations | 4732 | E0160 | non-negotiable | false | 10 |
| R02918 | Avoid moving large KV tensors across VFIO boundaries | 4733 | E0160 | non-negotiable | false | 10 |
| R02919 | Avoid moving layer outputs | 4734 | E0160 | non-negotiable | false | 10 |
| R02920 | Mode A — Low-Latency Interactive — fastest good answer | 4744–4745 | M00291 | non-negotiable | false | 10 |
| R02921 | Mode A flow — CPU retrieves context | 4748 | M00291 | non-negotiable | false | 10 |
| R02922 | Mode A flow — 3090 drafts / reranks | 4749 | M00291 | non-negotiable | false | 10 |
| R02923 | Mode A flow — Blackwell generates | 4750 | M00291 | non-negotiable | false | 10 |
| R02924 | Mode A flow — CPU enforces structured output / tools | 4751 | M00291 | non-negotiable | false | 10 |
| R02925 | Mode A target — chat / coding help / command planning | 4754 | M00291 | non-negotiable | true | 10 |
| R02926 | Mode B — Agentic Batch — many branches / tool loops | 4759–4760 | M00292 | non-negotiable | false | 10 |
| R02927 | Mode B flow — CPU spawns branch frontier | 4763 | M00292 | non-negotiable | false | 10 |
| R02928 | Mode B flow — 3090 expands many options | 4764 | M00292 | non-negotiable | false | 10 |
| R02929 | Mode B flow — CPU compresses and prunes | 4765 | M00292 | non-negotiable | false | 10 |
| R02930 | Mode B flow — Blackwell verifies frontier winners | 4766 | M00292 | non-negotiable | false | 10 |
| R02931 | Mode B flow — tools execute transactionally | 4767 | M00292 | non-negotiable | false | 10 |
| R02932 | Mode B target — coding agents / research agents / automation | 4770 | M00292 | non-negotiable | true | 10 |
| R02933 | Mode C — Long-Context Workbench — huge docs / repo / long sessions | 4774–4775 | M00293 | non-negotiable | false | 10 |
| R02934 | Mode C flow — CPU builds content-addressed context | 4779 | M00293 | non-negotiable | false | 10 |
| R02935 | Mode C flow — KV cache / prefix reuse aggressively | 4780 | M00293 | non-negotiable | false | 10 |
| R02936 | Mode C flow — Blackwell prefill is treated as expensive asset | 4781 | M00293 | non-negotiable | false | 10 |
| R02937 | Mode C flow — 3090 handles summaries and retrieval | 4782 | M00293 | non-negotiable | false | 10 |
| R02938 | Mode C target — repo-wide work / documents / audits | 4785 | M00293 | non-negotiable | true | 10 |
| R02939 | KV-aware routing is a serious optimization | 4789 | E0162 | non-negotiable | false | 10 |
| R02940 | Scheduler asks — Which server already has this prefix hot? | 4794 | E0162 | non-negotiable | false | 10 |
| R02941 | Scheduler asks — Which model has matching tokenizer? | 4795 | E0162 | non-negotiable | false | 10 |
| R02942 | Scheduler asks — Which KV blocks are reusable? | 4796 | E0162 | non-negotiable | false | 10 |
| R02943 | Scheduler asks — Which branch shares parent context? | 4797 | E0162 | non-negotiable | false | 10 |
| R02944 | Scheduler asks — Which context block is expensive to rebuild? | 4798 | E0162 | non-negotiable | false | 10 |
| R02945 | Request carries `model_id` | 4804 | M00294 | non-negotiable | false | 10 |
| R02946 | Request carries `tokenizer_id` | 4805 | M00294 | non-negotiable | false | 10 |
| R02947 | Request carries `prompt_hashes` | 4806 | M00294 | non-negotiable | false | 10 |
| R02948 | Request carries `kv_ref_candidates` | 4807 | M00294 | non-negotiable | false | 10 |
| R02949 | Request carries `branch_parent` | 4808 | M00294 | non-negotiable | false | 10 |
| R02950 | Request carries `cache_policy` | 4809 | M00294 | non-negotiable | false | 10 |
| R02951 | CPU routes based on cache, not just load | 4812 | E0162 | non-negotiable | false | 10 |
| R02952 | That is what modern serving stacks are converging toward | 4814 | E0162 | non-negotiable | false | 10 |
| R02953 | Speculation is service-level, not only model-level | 4818 | E0163 | non-negotiable | false | 10 |
| R02954 | Classic — draft model predicts tokens / target model verifies | 4823–4825 | E0163 | non-negotiable | false | 10 |
| R02955 | Workstation version — 3090 predicts branches / plans / token continuations | 4830 | E0163 | non-negotiable | false | 10 |
| R02956 | Workstation version — CPU prunes with deterministic law | 4831 | E0163 | non-negotiable | false | 10 |
| R02957 | Workstation version — Blackwell verifies in chunks | 4832 | E0163 | non-negotiable | false | 10 |
| R02958 | SPECTRE-style — preserve draft-target overlap rather than making one wait | 4835 | E0163 | non-negotiable | false | 10 |
| R02959 | 3090 should almost always be working ahead | 4840 | M00295 | non-negotiable | false | 10 |
| R02960 | Blackwell should almost always be verifying or generating | 4841 | M00295 | non-negotiable | false | 10 |
| R02961 | CPU should almost always have packed queues ready | 4842 | M00295 | non-negotiable | false | 10 |
| R02962 | Queue — oracle_prefill_queue | 4850 | M00296 | non-negotiable | false | 10 |
| R02963 | Queue — oracle_decode_queue | 4851 | M00296 | non-negotiable | false | 10 |
| R02964 | Queue — oracle_verify_queue | 4852 | M00296 | non-negotiable | false | 10 |
| R02965 | Queue — scout_draft_queue | 4853 | M00296 | non-negotiable | false | 10 |
| R02966 | Queue — scout_rerank_queue | 4854 | M00296 | non-negotiable | false | 10 |
| R02967 | Queue — perception_queue | 4855 | M00296 | non-negotiable | false | 10 |
| R02968 | Queue — embedding_queue | 4856 | M00296 | non-negotiable | false | 10 |
| R02969 | Queue — tool_intent_queue | 4857 | M00296 | non-negotiable | false | 10 |
| R02970 | Queue — human_gate_queue | 4858 | M00296 | non-negotiable | false | 10 |
| R02971 | Queue weight axis — priority | 4863 | M00297 | non-negotiable | false | 10 |
| R02972 | Queue weight axis — deadline | 4864 | M00297 | non-negotiable | false | 10 |
| R02973 | Queue weight axis — batchability | 4865 | M00297 | non-negotiable | false | 10 |
| R02974 | Queue weight axis — risk | 4866 | M00297 | non-negotiable | false | 10 |
| R02975 | Queue weight axis — cache_affinity | 4867 | M00297 | non-negotiable | false | 10 |
| R02976 | Queue weight axis — model_affinity | 4868 | M00297 | non-negotiable | false | 10 |
| R02977 | AVX-512 scheduler evaluates queue entries in bulk | 4872 | M00297 | non-negotiable | false | 10 |
| R02978 | Batch together if same model | 4878 | M00298 | non-negotiable | false | 10 |
| R02979 | Batch together if same tokenizer | 4879 | M00298 | non-negotiable | false | 10 |
| R02980 | Batch together if same output schema | 4880 | M00298 | non-negotiable | false | 10 |
| R02981 | Batch together if compatible max tokens | 4881 | M00298 | non-negotiable | false | 10 |
| R02982 | Batch together if similar context length | 4882 | M00298 | non-negotiable | false | 10 |
| R02983 | Batch together if same cache affinity | 4883 | M00298 | non-negotiable | false | 10 |
| R02984 | Do NOT batch if one is latency critical and one is huge | 4886 | M00298 | non-negotiable | false | 10 |
| R02985 | Do NOT batch if different grammar masks cause overhead | 4887 | M00298 | non-negotiable | false | 10 |
| R02986 | Do NOT batch if one has high-risk tool boundary | 4888 | M00298 | non-negotiable | false | 10 |
| R02987 | Do NOT batch if one will evict valuable KV | 4889 | M00298 | non-negotiable | false | 10 |
| R02988 | CPU decides batching with bitfields | 4892 | M00298 | non-negotiable | false | 10 |
| R02989 | Backend — vLLM general purpose serving / prefix caching / batching / broad model support | 4899–4900 | M00299 | non-negotiable | true | 10 |
| R02990 | Backend — SGLang structured agent programs / RadixAttention / speculative decoding / constrained workflows | 4902–4903 | M00299 | non-negotiable | true | 10 |
| R02991 | Backend — TensorRT-LLM production optimized path for stable models on Blackwell (especially FP8/NVFP4) | 4905–4906 | M00299 | non-negotiable | true | 10 |
| R02992 | Backend — llama.cpp GGUF experiments / CPU+GPU hybrid / resilience / quick local tests | 4908–4909 | M00299 | non-negotiable | true | 10 |
| R02993 | Do not marry one backend | 4912 | M00299 | non-negotiable | false | 10 |
| R02994 | Build an abstraction layer | 4912 | M00300 | non-negotiable | false | 10 |
| R02995 | Abstraction — `Generate(request) -> tokens/result` | 4915 | M00300 | non-negotiable | false | 10 |
| R02996 | Abstraction — `Embed(request) -> vectors` | 4916 | M00300 | non-negotiable | false | 10 |
| R02997 | Abstraction — `Rerank(request) -> scores` | 4917 | M00300 | non-negotiable | false | 10 |
| R02998 | Abstraction — `Perceive(request) -> structured scene/doc/audio state` | 4918 | M00300 | non-negotiable | false | 10 |
| R02999 | Abstraction — `Verify(request) -> accept/reject/score` | 4919 | M00300 | non-negotiable | false | 10 |
| R03000 | Model servers are replaceable through the abstraction | 4922 | M00300 | non-negotiable | false | 10 |
| R03001 | NVIDIA RAG docs — self-hosted local NIM `nemotron-3-super-120b-a12b` needs 3× RTX PRO 6000 in that profile | 4926 | M00301 | non-negotiable | false | 10 |
| R03002 | On single 96GB Blackwell, do not assume every "workstation model" fits in official high-throughput config | 4926 | M00301 | non-negotiable | false | 10 |
| R03003 | Workstation strength — run one strong oracle | 4935 | M00301 | non-negotiable | false | 10 |
| R03004 | Workstation strength — run several fast specialists | 4936 | M00301 | non-negotiable | false | 10 |
| R03005 | Workstation strength — route intelligently | 4937 | M00301 | non-negotiable | false | 10 |
| R03006 | Workstation strength — cache aggressively | 4938 | M00301 | non-negotiable | false | 10 |
| R03007 | Workstation strength — speculate safely | 4939 | M00301 | non-negotiable | false | 10 |
| R03008 | Workstation strength — commit deterministically | 4940 | M00301 | non-negotiable | false | 10 |
| R03009 | Final shape — Control Runtime owns task graph, branches, policy, queues | 4948–4950 | M00301 | non-negotiable | false | 10 |
| R03010 | Final shape — Model Gateway abstracts vLLM/SGLang/TRT-LLM/llama.cpp servers | 4951–4952 | M00301 | non-negotiable | false | 10 |
| R03011 | Final shape — Cache Router tracks KV/prefix/model affinity | 4954–4955 | M00301 | non-negotiable | false | 10 |
| R03012 | Final shape — GPU Workers (blackwell-oracle, 3090-scout, 3090-perception, cpu-rerank fallback) | 4957–4961 | M00301 | non-negotiable | false | 10 |
| R03013 | Final shape — Tool Workers (sandboxed, gated, replayed) | 4963–4964 | M00301 | non-negotiable | false | 10 |
| R03014 | Final shape — Telemetry feeds queue weights and routing | 4966–4967 | M00301 | non-negotiable | false | 10 |
| R03015 | Rule — The model server should be dumb | 4973 | M00301 | non-negotiable | false | 10 |
| R03016 | Rule — The runtime should be smart | 4974 | M00301 | non-negotiable | false | 10 |
| R03017 | Model servers — generate, embed, rerank, perceive, verify | 4977 | M00300 | non-negotiable | false | 10 |
| R03018 | Deterministic runtime decides — what to ask | 4982 | M00301 | non-negotiable | false | 10 |
| R03019 | Deterministic runtime decides — when to ask | 4983 | M00301 | non-negotiable | false | 10 |
| R03020 | Deterministic runtime decides — who to ask | 4984 | M00301 | non-negotiable | false | 10 |
| R03021 | Deterministic runtime decides — what to trust | 4985 | M00301 | non-negotiable | false | 10 |
| R03022 | Deterministic runtime decides — what to cache | 4986 | M00301 | non-negotiable | false | 10 |
| R03023 | Deterministic runtime decides — what to commit | 4987 | M00301 | non-negotiable | false | 10 |
| R03024 | Ultimate is not reliance on the latest model alone, but making every new model a plug-in component inside a serious local inference fabric | 4990 | M00301 | non-negotiable | false | 10 |
| R03025 | Serving mode operator-overrideable (interactive / agentic_batch / long_context / auto) | 4737–4785 | F01446 | non-negotiable | true | 10 |
| R03026 | Env var `SOVEREIGN_SERVING_MODE` | 4737–4785 | F01448 | non-negotiable | true | 10 |
| R03027 | CLI `--serving-mode <mode>` | 4737–4785 | F01449 | non-negotiable | true | 10 |
| R03028 | API `POST /v1/route` returns chosen-server + reason | 4787–4814 | F01526 | non-negotiable | true | 10 |
| R03029 | API `GET /v1/queues` returns per-queue depth + 6-axis weight summary | 4845–4872 | F01527 | non-negotiable | true | 10 |
| R03030 | Dashboard — local inference fabric overview | 4664–4990 | F01528 | non-negotiable | true | 10 |
| R03031 | Dashboard — KV-aware routing inspector | 4787–4814 | F01529 | non-negotiable | true | 10 |
| R03032 | Test — request envelope round-trips all 6 fields | 4801–4810 | M00294 | non-negotiable | false | 10 |
| R03033 | Test — each of 9 queues spins up with declared 6-axis weight | 4849–4870 | M00296 | non-negotiable | false | 10 |
| R03034 | Test — batching positive 6 rules + negative 4 rules each fire on declared trigger | 4876–4891 | M00298 | non-negotiable | false | 10 |
| R03035 | Test — backend abstraction surface (Generate/Embed/Rerank/Perceive/Verify) routes to vLLM | 4915–4919 | M00300 | non-negotiable | false | 10 |
| R03036 | Test — backend abstraction surface routes to SGLang | 4915–4919 | M00300 | non-negotiable | false | 10 |
| R03037 | Test — backend abstraction surface routes to TensorRT-LLM | 4915–4919 | M00300 | non-negotiable | false | 10 |
| R03038 | Test — backend abstraction surface routes to llama.cpp | 4915–4919 | M00300 | non-negotiable | false | 10 |
| R03039 | Test — Mode A interactive end-to-end on sample chat task | 4741–4754 | M00291 | non-negotiable | false | 10 |
| R03040 | Test — Mode B agentic-batch end-to-end on sample coding agent task | 4756–4770 | M00292 | non-negotiable | false | 10 |
| R03041 | Test — Mode C long-context end-to-end on sample repo-wide task | 4772–4785 | M00293 | non-negotiable | false | 10 |
| R03042 | Test — speculation triangle keeps 3090 working ahead while Blackwell verifies (overlap > 0 for sample workload) | 4840–4842 | M00295 | non-negotiable | false | 10 |
| R03043 | Test — KV-aware routing picks server with hot prefix when multiple candidates exist | 4794 | E0162 | non-negotiable | false | 10 |
| R03044 | Test — KV-aware routing prefers matching tokenizer when multiple candidates exist | 4795 | E0162 | non-negotiable | false | 10 |
| R03045 | Test — KV-aware routing reuses KV blocks when reusable | 4796 | E0162 | non-negotiable | false | 10 |
| R03046 | Test — KV-aware routing exploits branch parent context sharing | 4797 | E0162 | non-negotiable | false | 10 |
| R03047 | Test — KV-aware routing avoids rebuilding expensive context blocks | 4798 | E0162 | non-negotiable | false | 10 |
| R03048 | Test — Cache Router tracks per-server KV/prefix/model affinity correctly | 4954–4955 | M00301 | non-negotiable | false | 10 |
| R03049 | Test — Telemetry-fed queue weights change ranking under load | 4966–4967 | M00301 | non-negotiable | false | 10 |
| R03050 | Test — Tool Worker sandboxed-gated-replayed path enforced | 4963–4964 | M00301 | non-negotiable | false | 10 |
| R03051 | Test — Disaggregated prefill + decode handoff transmits KV via configured backend (NIXL/UCX) | 4660 | E0157 | non-negotiable | true | 10 |
| R03052 | Test — "Model server dumb / runtime smart" — server APIs respond with `Unauthorized` if asked to make routing decisions | 4972–4974 | M00301 | non-negotiable | false | 10 |
| R03053 | Backend toggle persists across daemon restart | 4441–4453 | F01394 | non-negotiable | true | 10 |
| R03054 | Composite — Serving Fabric integrates with M013 observability (queue + cache + telemetry metrics) | 4966–4967 | M00301 | non-negotiable | false | 10 |
| R03055 | Composite — Serving Fabric integrates with M011 KV memory hierarchy (cache router shares L1/L2/L3 view) | 4954–4955 | M00301 | non-negotiable | false | 10 |
| R03056 | Composite — Serving Fabric integrates with M014 isolation (3090 perception/scout speak via VFIO host channels) | 4675–4681 | E0160 | non-negotiable | false | 10 |
| R03057 | Composite — Serving Fabric integrates with M017 model registry (per-role model + per-precision binding) | 4900–4910 | M00299 | non-negotiable | false | 10 |
| R03058 | Composite — Serving Fabric integrates with M015 programming plane (Tool Workers are Tool Nodes) | 4963–4964 | M00301 | non-negotiable | false | 10 |
| R03059 | Composite — Serving Fabric integrates with M016 learning plane (telemetry → queue-weight feedback loop) | 4966–4967 | M00301 | non-negotiable | false | 10 |
| R03060 | Composite — Serving Fabric is the bridge from "workstation with GPUs" to "local agentic AI workstation" | 4988–4990 | M00301 | non-negotiable | false | 10 |

— End of M018 milestone file.
