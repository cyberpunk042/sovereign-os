# M017 — Model portfolio strategy

> Parent: `backlog/milestones/INDEX.md` row M017 (dump 4348–4631).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 4348–4631.
> All entries below are extracted from the dump line range. No invention.

> **AVX++ canon update — 2026-05-19**: this milestone is affected by backward-sweep redefinition(s) — Profiles memory-lens-to-authority-gate (BREAKING) + Authority Levels 0..6 (ADDITIVE). See sovereign-os M061 for canonical pinning (commit 6f07dca). R-rows below are interpreted under the canonical later definitions per operator standing direction "layered: new direction ON TOP OF prior direction — never discarded".


## Epics (E0146–E0155)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0146 | Current open-model trend — MoE / sparse activation / hybrid attention + linear/Mamba / long context / token efficiency / multi-token prediction / NVFP4-MXFP4 / agentic tool-use tuning / multimodal perception sub-agents | 4372–4385 |
| E0147 | Ling-2.6-flash — hybrid linear, token-efficient, tool-use, multi-step planning, 104B/active small, benchmarks BFCL-V4 / TAU2-bench / SWE-bench Verified / Claw-Eval / PinchBench | 4389 |
| E0148 | NVIDIA Nemotron 3 — hybrid Mamba-Transformer MoE, ≤ 1M context, RL across environments, reasoning budget control, MTP + NVFP4 on Super/Ultra | 4391 |
| E0149 | Nemotron 3 Nano — 31.6B total / 3.2B active / ≤ 1M context / high inference efficiency; Nano Omni adds text/image/audio/video/documents/charts/GUI in 30B-A3B hybrid MoE 256K context — eyes-and-ears of agent systems | 4393 |
| E0150 | Model portfolio (not single champion) — Oracle / Scout / Cortex three-organ assignment | 4395–4425 |
| E0151 | Blackwell deployment ladder — BF16/FP16 quality / FP8 balanced / NVFP4-MXFP4 native-compression | 4427–4438 |
| E0152 | Serving-backend matrix — vLLM / SGLang / TensorRT-LLM / llama.cpp | 4441–4453 |
| E0153 | Zen 5 AVX-512 instruction set — VPTERNLOG / VPOPCNTDQ / VP2INTERSECT / VBMI+VBMI2 / VNNI+BF16 / compress+expand + k-masks | 4456–4481 |
| E0154 | Ultimate Station Shape — Oracle / Scout / Deterministic Cortex / Memory Hierarchy / Isolation / Observability six-layer | 4483–4514 |
| E0155 | Model Portfolio Strategy + Golden Design — 7-role taxonomy (Oracle/Executor/Perception/Scout/Verifier/Retriever/Fallback) + YAML model registry + telemetry-driven scheduler + model-router-with-deterministic-infrastructure thesis | 4515–4630 |

## Modules (M00268–M00284)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00268 | Open-model trend tracker — 8 trends list with operator-overrideable additions | 4374–4383 | E0146 |
| M00269 | Ling-2.6-flash entry — `inclusionAI/Ling-2.6-flash` (hybrid linear, 104B total, smaller active) | 4389 | E0147 |
| M00270 | Nemotron 3 family entry — Super / Ultra / Nano / Nano Omni; hybrid Mamba-Transformer MoE; ≤ 1M context; RL; reasoning budget control; MTP + NVFP4 on Super/Ultra | 4391–4393 | E0148 |
| M00271 | Blackwell role binding — Ling-2.6-flash FP8/INT4/BF16 + Nemotron 3 Super/Ultra NVFP4 + Kimi/Qwen/DeepSeek large MoE quantized + oracle verification + final synthesis + long-context resident sessions | 4400–4406 | E0150 |
| M00272 | 3090 role binding — Nemotron 3 Nano / Nano Omni (if precision-fit) + Qwen small coder / reranker / embedding / vision / draft / sandboxed experiments / tool-use scout | 4408–4413 | E0150 |
| M00273 | Ryzen 9900X AVX-512 role binding — grammar masks / branch scheduler / KV-cache controller / bitset retrieval / policy engine / tool gate / telemetry-driven routing | 4415–4422 | E0150 |
| M00274 | Blackwell precision ladder — BF16/FP16 (quality) / FP8 (balanced) / NVFP4-MXFP4 (Blackwell-native compression for larger MoE) | 4433–4437 | E0151 |
| M00275 | Serving backend — vLLM (flexible serving, batching, prefix caching, broad model support) | 4442–4443 | E0152 |
| M00276 | Serving backend — SGLang (agent/program-style serving, RadixAttention, structured workflows) | 4445–4446 | E0152 |
| M00277 | Serving backend — TensorRT-LLM (highest-performance NVIDIA path) | 4448–4449 | E0152 |
| M00278 | Serving backend — llama.cpp (fallback, CPU/GPU hybrid, GGUF, quick experiments) | 4451–4452 | E0152 |
| M00279 | Zen 5 AVX-512 group — AVX512F / BW / DQ / VL / VNNI / VPOPCNTDQ / BITALG / VBMI / VBMI2 / BF16 / IFMA / VP2INTERSECT / GFNI / AVX-VNNI (per AMD64 manual Jan 2026) | 4457 | E0153 |
| M00280 | Six-layer Ultimate Station rollup — Oracle / Scout / Deterministic Cortex / Memory Hierarchy / Isolation / Observability | 4488–4513 | E0154 |
| M00281 | 7-role model taxonomy — Oracle / Executor / Perception / Scout / Verifier / Retriever / Fallback | 4519–4540 | E0155 |
| M00282 | Telemetry-driven scheduler — task.visual → Nano Omni / task.agentic_fast → Ling-Nemotron-Nano / risk.high-or-commit.final → oracle / output.structured → grammar+mask / branch.low_value → scout or kill / oracle_idle → batch+verification | 4587–4605 | E0155 |
| M00283 | YAML model registry — per-model fields role / strengths / gpu / precision / context_policy | 4555–4583 | E0155 |
| M00284 | Big-insight thesis — model-router-with-deterministic-infrastructure, hot-swappable workers inside a deterministic replayable vectorized environment | 4607–4629 | E0155 |

## Features (F01361–F01445)

| F ID | Phrase | Dump line | Parent module | Category | Opt-in |
|---|---|---|---|---|---|
| F01361 | Open-model trend — MoE / sparse activation | 4375 | M00268 | mode | true |
| F01362 | Open-model trend — hybrid attention + linear / Mamba layers | 4376 | M00268 | mode | true |
| F01363 | Open-model trend — long context | 4377 | M00268 | mode | true |
| F01364 | Open-model trend — token efficiency | 4378 | M00268 | mode | true |
| F01365 | Open-model trend — multi-token prediction | 4379 | M00268 | mode | true |
| F01366 | Open-model trend — NVFP4 / MXFP4 quantized deployment | 4380 | M00268 | mode | true |
| F01367 | Open-model trend — agentic tool-use tuning | 4381 | M00268 | mode | true |
| F01368 | Open-model trend — multimodal perception sub-agents | 4382 | M00268 | mode | true |
| F01369 | Catalog entry — Ling-2.6-flash (hybrid linear, 104B total) | 4389 | M00269 | data_model | false |
| F01370 | Ling-2.6-flash benchmark — BFCL-V4 | 4389 | M00269 | data_model | false |
| F01371 | Ling-2.6-flash benchmark — TAU2-bench | 4389 | M00269 | data_model | false |
| F01372 | Ling-2.6-flash benchmark — SWE-bench Verified | 4389 | M00269 | data_model | false |
| F01373 | Ling-2.6-flash benchmark — Claw-Eval | 4389 | M00269 | data_model | false |
| F01374 | Ling-2.6-flash benchmark — PinchBench | 4389 | M00269 | data_model | false |
| F01375 | Catalog entry — Nemotron 3 Super (hybrid Mamba-Transformer MoE, ≤ 1M context, MTP + NVFP4) | 4391 | M00270 | data_model | false |
| F01376 | Catalog entry — Nemotron 3 Ultra (hybrid Mamba-Transformer MoE, ≤ 1M context, MTP + NVFP4) | 4391 | M00270 | data_model | false |
| F01377 | Catalog entry — Nemotron 3 Nano (31.6B total / 3.2B active / ≤ 1M context / high inference efficiency) | 4393 | M00270 | data_model | false |
| F01378 | Catalog entry — Nemotron 3 Nano Omni (30B-A3B hybrid MoE, 256K context, text/image/audio/video/documents/charts/GUI) | 4393 | M00270 | data_model | false |
| F01379 | Catalog entry — Kimi (large MoE quantized) | 4403 | M00271 | data_model | true |
| F01380 | Catalog entry — Qwen large MoE quantized | 4403 | M00271 | data_model | true |
| F01381 | Catalog entry — DeepSeek large MoE quantized | 4403 | M00271 | data_model | true |
| F01382 | Catalog entry — small Qwen coder / reranker / embedding / vision (3090) | 4410 | M00272 | data_model | true |
| F01383 | Per-organ binding — Blackwell hosts oracle verification + final synthesis + long-context resident sessions | 4404–4406 | M00271 | composite | false |
| F01384 | Per-organ binding — 3090 hosts Nemotron 3 Nano / Nano Omni + Qwen small / draft / sandboxed / scout | 4408–4413 | M00272 | composite | false |
| F01385 | Per-organ binding — Ryzen AVX-512 hosts grammar masks + branch scheduler + KV controller + bitset retrieval + policy + tool gate + telemetry routing | 4415–4422 | M00273 | composite | false |
| F01386 | Precision mode — BF16/FP16 (quality matters, model fits) | 4434 | M00274 | mode | true |
| F01387 | Precision mode — FP8 (balanced throughput/memory) | 4435 | M00274 | mode | true |
| F01388 | Precision mode — NVFP4 (Blackwell-native, larger MoE) | 4436 | M00274 | mode | true |
| F01389 | Precision mode — MXFP4 (Blackwell-native alternative) | 4436 | M00274 | mode | true |
| F01390 | Serving-backend toggle — vLLM | 4442 | M00275 | mode | true |
| F01391 | Serving-backend toggle — SGLang | 4445 | M00276 | mode | true |
| F01392 | Serving-backend toggle — TensorRT-LLM | 4448 | M00277 | mode | true |
| F01393 | Serving-backend toggle — llama.cpp | 4451 | M00278 | mode | true |
| F01394 | Profile knob — `serving_backend = vllm \| sglang \| tensorrt_llm \| llama_cpp` | 4441–4453 | E0152 | profile | true |
| F01395 | Env var `SOVEREIGN_SERVING_BACKEND` | 4441–4453 | E0152 | env_var | true |
| F01396 | CLI `--serving-backend <name>` | 4441–4453 | E0152 | cli_verb | true |
| F01397 | Profile knob — `blackwell_precision = bf16 \| fp16 \| fp8 \| nvfp4 \| mxfp4` | 4433–4437 | M00274 | profile | true |
| F01398 | Env var `SOVEREIGN_BLACKWELL_PRECISION` | 4433–4437 | M00274 | env_var | true |
| F01399 | CLI `--blackwell-precision <mode>` | 4433–4437 | M00274 | cli_verb | true |
| F01400 | AVX-512 group — VPTERNLOG fused boolean law | 4463 | M00279 | composite | false |
| F01401 | AVX-512 group — VPOPCNTDQ memory-sketch overlap | 4466 | M00279 | composite | false |
| F01402 | AVX-512 group — VP2INTERSECT candidate-set intersection | 4469 | M00279 | composite | false |
| F01403 | AVX-512 group — VBMI/VBMI2 token-class + byte-shuffle | 4472 | M00279 | composite | false |
| F01404 | AVX-512 group — VNNI/BF16 CPU-side small inference / reranking / embedding / scoring | 4475 | M00279 | composite | false |
| F01405 | AVX-512 group — compress/expand + k-masks branch compaction + dense batching | 4478 | M00279 | composite | false |
| F01406 | Six-layer Ultimate Station — Oracle Layer | 4488–4490 | M00280 | composite | false |
| F01407 | Six-layer Ultimate Station — Scout Layer | 4492–4495 | M00280 | composite | false |
| F01408 | Six-layer Ultimate Station — Deterministic Cortex | 4496–4499 | M00280 | composite | false |
| F01409 | Six-layer Ultimate Station — Memory Hierarchy | 4500–4503 | M00280 | composite | false |
| F01410 | Six-layer Ultimate Station — Isolation Layer | 4505–4508 | M00280 | composite | false |
| F01411 | Six-layer Ultimate Station — Observability Layer | 4510–4512 | M00280 | composite | false |
| F01412 | Role taxonomy — Oracle (highest-quality model that fits on 96GB with useful context) | 4520–4521 | M00281 | composite | false |
| F01413 | Role taxonomy — Executor (token-efficient agent model like Ling-2.6-flash) | 4523–4524 | M00281 | composite | false |
| F01414 | Role taxonomy — Perception (Nemotron 3 Nano Omni for GUI/video/document/audio) | 4526–4527 | M00281 | composite | false |
| F01415 | Role taxonomy — Scout (Nemotron 3 Nano / small Qwen / small coder on 3090) | 4529–4530 | M00281 | composite | false |
| F01416 | Role taxonomy — Verifier (same oracle with strict prompt, or specialized judge/reward) | 4532–4533 | M00281 | composite | false |
| F01417 | Role taxonomy — Retriever (embedding + reranker, 3090 or CPU per size) | 4535–4536 | M00281 | composite | false |
| F01418 | Role taxonomy — Fallback (llama.cpp/GGUF local models, robust offline) | 4538–4539 | M00281 | composite | false |
| F01419 | Telemetry-driven routing — `if task.visual: route perception to Nano Omni` | 4588 | M00282 | composite | true |
| F01420 | Telemetry-driven routing — `if task.agentic_fast: route draft to Ling/Nemotron Nano` | 4591 | M00282 | composite | true |
| F01421 | Telemetry-driven routing — `if risk.high or commit.final: route to oracle` | 4594 | M00282 | composite | true |
| F01422 | Telemetry-driven routing — `if output.structured: enable grammar/token masks` | 4597 | M00282 | composite | true |
| F01423 | Telemetry-driven routing — `if branch.low_value: keep on scout or kill` | 4600 | M00282 | composite | true |
| F01424 | Telemetry-driven routing — `if oracle_idle: increase batch or verification depth` | 4603 | M00282 | composite | true |
| F01425 | Model registry — `ling_2_6_flash` entry (role: executor / gpu: blackwell / precision: fp8_or_int4 / context_policy: medium_long) | 4559–4564 | M00283 | data_model | false |
| F01426 | Model registry — `nemotron_3_nano` entry (role: scout / gpu: rtx3090_or_blackwell / precision: fp8_or_4bit) | 4566–4570 | M00283 | data_model | false |
| F01427 | Model registry — `nemotron_3_nano_omni` entry (role: perception / vision-audio-video-docs-gui / gpu: rtx3090_or_blackwell / precision: fp8_or_4bit) | 4572–4576 | M00283 | data_model | false |
| F01428 | Model registry — `large_oracle` entry (role: verifier / deep-reasoning + final-synthesis / gpu: blackwell / precision: bf16_fp8_nvfp4) | 4578–4583 | M00283 | data_model | false |
| F01429 | Model registry YAML schema — per-model `role` field | 4555–4583 | M00283 | data_model | false |
| F01430 | Model registry YAML schema — per-model `strengths` list | 4555–4583 | M00283 | data_model | false |
| F01431 | Model registry YAML schema — per-model `gpu` field | 4555–4583 | M00283 | data_model | false |
| F01432 | Model registry YAML schema — per-model `precision` field | 4555–4583 | M00283 | data_model | false |
| F01433 | Model registry YAML schema — per-model `context_policy` field | 4555–4583 | M00283 | data_model | false |
| F01434 | API `GET /v1/models` (lists registry) | 4555–4583 | M00283 | api_endpoint | true |
| F01435 | API `GET /v1/models/{name}` (returns single entry) | 4555–4583 | M00283 | api_endpoint | true |
| F01436 | API `POST /v1/models/route` (returns chosen model + reason for a task spec) | 4587–4605 | M00282 | api_endpoint | true |
| F01437 | Dashboard — model portfolio overview (per-role active model + state + telemetry) | 4519–4583 | M00281 | dashboard | true |
| F01438 | Dashboard — Blackwell precision ladder selector (current + alternatives + memory/perf tradeoff) | 4429–4438 | M00274 | dashboard | true |
| F01439 | Dashboard — serving-backend overview (vLLM / SGLang / TensorRT-LLM / llama.cpp state + active per-model) | 4441–4453 | E0152 | dashboard | true |
| F01440 | Metric — `sovereign_model_active_total{name,role,gpu}` | 4555–4583 | M00283 | observability_metric | true |
| F01441 | Metric — `sovereign_model_route_decision_total{model,reason}` | 4587–4605 | M00282 | observability_metric | true |
| F01442 | Metric — `sovereign_serving_backend_active{backend}` | 4441–4453 | E0152 | observability_metric | true |
| F01443 | Composite — model portfolio is hot-swappable workers inside deterministic replayable vectorized environment | 4626–4629 | M00284 | composite | false |
| F01444 | Composite — CPU is law / Blackwell is depth / 3090 is parallel perception+speculation / ZFS+RAM is memory / Observability is adaptation | 4622–4627 | M00284 | composite | false |
| F01445 | Composite — Ultimate Station is "a local agentic AI workstation where the newest models are hot-swappable workers inside a deterministic, replayable, vectorized operating environment" | 4628–4629 | M00284 | composite | false |

## Requirements (R02721–R02890)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R02721 | Current open-model trend is NOT simply bigger dense models | 4372 | E0146 | non-negotiable | false | 10 |
| R02722 | Trend — MoE / sparse activation | 4375 | E0146 | non-negotiable | false | 10 |
| R02723 | Trend — hybrid attention + linear / Mamba layers | 4376 | E0146 | non-negotiable | false | 10 |
| R02724 | Trend — long context | 4377 | E0146 | non-negotiable | false | 10 |
| R02725 | Trend — token efficiency | 4378 | E0146 | non-negotiable | false | 10 |
| R02726 | Trend — multi-token prediction | 4379 | E0146 | non-negotiable | false | 10 |
| R02727 | Trend — NVFP4 / MXFP4 quantized deployment | 4380 | E0146 | non-negotiable | false | 10 |
| R02728 | Trend — agentic tool-use tuning | 4381 | E0146 | non-negotiable | false | 10 |
| R02729 | Trend — multimodal perception sub-agents | 4382 | E0146 | non-negotiable | false | 10 |
| R02730 | Ling-2.6-flash is real and very relevant | 4389 | M00269 | non-negotiable | false | 10 |
| R02731 | Ling-2.6-flash uses a hybrid linear architecture | 4389 | M00269 | non-negotiable | false | 10 |
| R02732 | Ling-2.6-flash is optimized for token efficiency | 4389 | M00269 | non-negotiable | false | 10 |
| R02733 | Ling-2.6-flash is refined for tool use, multi-step planning, task execution | 4389 | M00269 | non-negotiable | false | 10 |
| R02734 | Ling-2.6-flash is 104B total with much smaller active compute | 4389 | M00269 | non-negotiable | false | 10 |
| R02735 | Ling-2.6-flash positioned around benchmark BFCL-V4 | 4389 | M00269 | non-negotiable | false | 10 |
| R02736 | Ling-2.6-flash positioned around benchmark TAU2-bench | 4389 | M00269 | non-negotiable | false | 10 |
| R02737 | Ling-2.6-flash positioned around benchmark SWE-bench Verified | 4389 | M00269 | non-negotiable | false | 10 |
| R02738 | Ling-2.6-flash positioned around benchmark Claw-Eval | 4389 | M00269 | non-negotiable | false | 10 |
| R02739 | Ling-2.6-flash positioned around benchmark PinchBench | 4389 | M00269 | non-negotiable | false | 10 |
| R02740 | NVIDIA Nemotron 3 is an open family for agentic AI | 4391 | M00270 | non-negotiable | false | 10 |
| R02741 | NVIDIA Nemotron 3 has hybrid Mamba-Transformer MoE architecture | 4391 | M00270 | non-negotiable | false | 10 |
| R02742 | NVIDIA Nemotron 3 has long context up to 1M tokens | 4391 | M00270 | non-negotiable | false | 10 |
| R02743 | NVIDIA Nemotron 3 has reinforcement learning across environments | 4391 | M00270 | non-negotiable | false | 10 |
| R02744 | NVIDIA Nemotron 3 has reasoning budget control | 4391 | M00270 | non-negotiable | false | 10 |
| R02745 | Nemotron 3 Super/Ultra have multi-token prediction | 4391 | M00270 | non-negotiable | false | 10 |
| R02746 | Nemotron 3 Super/Ultra have NVFP4 deployment | 4391 | M00270 | non-negotiable | false | 10 |
| R02747 | Nemotron 3 Nano is 31.6B total | 4393 | M00270 | non-negotiable | false | 10 |
| R02748 | Nemotron 3 Nano is 3.2B active | 4393 | M00270 | non-negotiable | false | 10 |
| R02749 | Nemotron 3 Nano supports up to 1M context | 4393 | M00270 | non-negotiable | false | 10 |
| R02750 | Nemotron 3 Nano has high inference efficiency | 4393 | M00270 | non-negotiable | false | 10 |
| R02751 | Nemotron 3 Nano Omni adds text + image + audio + video + documents + charts + GUI perception | 4393 | M00270 | non-negotiable | false | 10 |
| R02752 | Nemotron 3 Nano Omni is 30B-A3B hybrid MoE | 4393 | M00270 | non-negotiable | false | 10 |
| R02753 | Nemotron 3 Nano Omni has 256K context | 4393 | M00270 | non-negotiable | false | 10 |
| R02754 | Nemotron 3 Nano Omni positioned as the "eyes and ears" of agent systems | 4393 | M00270 | non-negotiable | false | 10 |
| R02755 | Workstation should NOT be designed around one model | 4395 | E0150 | non-negotiable | false | 10 |
| R02756 | Workstation should be designed around a model portfolio | 4395 | E0150 | non-negotiable | false | 10 |
| R02757 | Blackwell hosts Ling-2.6-flash FP8 / INT4 / maybe BF16 | 4401 | M00271 | non-negotiable | false | 10 |
| R02758 | Blackwell hosts Nemotron 3 Super / large NVFP4 models when practical | 4402 | M00271 | non-negotiable | false | 10 |
| R02759 | Blackwell hosts Kimi / Qwen / DeepSeek style large MoE quantized models | 4403 | M00271 | non-negotiable | false | 10 |
| R02760 | Blackwell hosts oracle verification | 4404 | M00271 | non-negotiable | false | 10 |
| R02761 | Blackwell hosts final synthesis | 4405 | M00271 | non-negotiable | false | 10 |
| R02762 | Blackwell hosts long context resident sessions | 4406 | M00271 | non-negotiable | false | 10 |
| R02763 | 3090 hosts Nemotron 3 Nano / Nano Omni if precision fits | 4409 | M00272 | non-negotiable | false | 10 |
| R02764 | 3090 hosts Qwen small coder / reranker / embedding / vision helpers | 4410 | M00272 | non-negotiable | false | 10 |
| R02765 | 3090 hosts draft models for speculation | 4411 | M00272 | non-negotiable | false | 10 |
| R02766 | 3090 hosts sandboxed model experiments | 4412 | M00272 | non-negotiable | false | 10 |
| R02767 | 3090 hosts tool-use scout | 4413 | M00272 | non-negotiable | false | 10 |
| R02768 | Ryzen 9900X AVX-512 hosts grammar masks | 4416 | M00273 | non-negotiable | false | 10 |
| R02769 | Ryzen 9900X AVX-512 hosts branch scheduler | 4417 | M00273 | non-negotiable | false | 10 |
| R02770 | Ryzen 9900X AVX-512 hosts KV-cache controller | 4418 | M00273 | non-negotiable | false | 10 |
| R02771 | Ryzen 9900X AVX-512 hosts bitset retrieval | 4419 | M00273 | non-negotiable | false | 10 |
| R02772 | Ryzen 9900X AVX-512 hosts policy engine | 4420 | M00273 | non-negotiable | false | 10 |
| R02773 | Ryzen 9900X AVX-512 hosts tool gate | 4421 | M00273 | non-negotiable | false | 10 |
| R02774 | Ryzen 9900X AVX-512 hosts telemetry-driven routing | 4422 | M00273 | non-negotiable | false | 10 |
| R02775 | The 96GB card is where the high-value model lives | 4425 | M00271 | non-negotiable | false | 10 |
| R02776 | The 3090 becomes fast auxiliary cognition | 4425 | M00272 | non-negotiable | false | 10 |
| R02777 | The CPU becomes law | 4425 | M00273 | non-negotiable | false | 10 |
| R02778 | Blackwell precision — BF16/FP16 when quality matters and model fits | 4434 | M00274 | non-negotiable | true | 10 |
| R02779 | Blackwell precision — FP8 when balanced throughput/memory matters | 4435 | M00274 | non-negotiable | true | 10 |
| R02780 | Blackwell precision — NVFP4 when Blackwell-native compression unlocks larger MoE models | 4436 | M00274 | non-negotiable | true | 10 |
| R02781 | Blackwell precision — MXFP4 as Blackwell-native alternative | 4436 | M00274 | non-negotiable | true | 10 |
| R02782 | vLLM compressor docs list NVFP4 / MXFP4 as Blackwell compute capability 10.0 schemes | 4429 | M00271 | non-negotiable | false | 10 |
| R02783 | NVIDIA RTX PRO 6000 page confirms 5th-gen Tensor Cores support FP4 | 4429 | M00271 | non-negotiable | false | 10 |
| R02784 | Software stack still moving — NVFP4 not as stable as FP8 in vLLM/SGLang/TensorRT-LLM yet | 4439 | E0152 | non-negotiable | false | 10 |
| R02785 | Workstation supports multiple serving backends | 4439 | E0152 | non-negotiable | false | 10 |
| R02786 | Serving backend — vLLM (flexible, batching, prefix caching, broad model support) | 4442–4443 | M00275 | non-negotiable | true | 10 |
| R02787 | Serving backend — SGLang (agent/program-style, RadixAttention, structured workflows) | 4445–4446 | M00276 | non-negotiable | true | 10 |
| R02788 | Serving backend — TensorRT-LLM (highest-performance NVIDIA path) | 4448–4449 | M00277 | non-negotiable | true | 10 |
| R02789 | Serving backend — llama.cpp (fallback, CPU/GPU hybrid, GGUF, quick experiments) | 4451–4452 | M00278 | non-negotiable | true | 10 |
| R02790 | AMD AMD64 manual Jan 2026 lists AVX512F | 4457 | M00279 | non-negotiable | false | 10 |
| R02791 | AMD AMD64 manual Jan 2026 lists AVX512 BW | 4457 | M00279 | non-negotiable | false | 10 |
| R02792 | AMD AMD64 manual Jan 2026 lists AVX512 DQ | 4457 | M00279 | non-negotiable | false | 10 |
| R02793 | AMD AMD64 manual Jan 2026 lists AVX512 VL | 4457 | M00279 | non-negotiable | false | 10 |
| R02794 | AMD AMD64 manual Jan 2026 lists VNNI | 4457 | M00279 | non-negotiable | false | 10 |
| R02795 | AMD AMD64 manual Jan 2026 lists VPOPCNTDQ | 4457 | M00279 | non-negotiable | false | 10 |
| R02796 | AMD AMD64 manual Jan 2026 lists BITALG | 4457 | M00279 | non-negotiable | false | 10 |
| R02797 | AMD AMD64 manual Jan 2026 lists VBMI | 4457 | M00279 | non-negotiable | false | 10 |
| R02798 | AMD AMD64 manual Jan 2026 lists VBMI2 | 4457 | M00279 | non-negotiable | false | 10 |
| R02799 | AMD AMD64 manual Jan 2026 lists BF16 | 4457 | M00279 | non-negotiable | false | 10 |
| R02800 | AMD AMD64 manual Jan 2026 lists IFMA | 4457 | M00279 | non-negotiable | false | 10 |
| R02801 | AMD AMD64 manual Jan 2026 lists VP2INTERSECT | 4457 | M00279 | non-negotiable | false | 10 |
| R02802 | AMD AMD64 manual Jan 2026 lists GFNI | 4457 | M00279 | non-negotiable | false | 10 |
| R02803 | AMD AMD64 manual Jan 2026 lists AVX-VNNI | 4457 | M00279 | non-negotiable | false | 10 |
| R02804 | AMD 9900X page confirms AVX512 support | 4457 | M00279 | non-negotiable | false | 10 |
| R02805 | AVX-512 architectural piece — VPTERNLOG fused boolean law | 4463 | F01400 | non-negotiable | false | 10 |
| R02806 | AVX-512 architectural piece — VPOPCNTDQ memory sketch overlap / bitset scoring | 4466 | F01401 | non-negotiable | false | 10 |
| R02807 | AVX-512 architectural piece — VP2INTERSECT candidate set intersection / phrase / search / memory ID matching | 4469 | F01402 | non-negotiable | false | 10 |
| R02808 | AVX-512 architectural piece — VBMI/VBMI2 token-class and byte-shuffle tricks | 4472 | F01403 | non-negotiable | false | 10 |
| R02809 | AVX-512 architectural piece — VNNI/BF16 CPU-side small inference / reranking / embedding / scoring kernels | 4475 | F01404 | non-negotiable | false | 10 |
| R02810 | AVX-512 architectural piece — compress/expand + k-masks branch compaction + dense batching | 4478 | F01405 | non-negotiable | false | 10 |
| R02811 | CPU is not merely orchestrating with scalar Python glue | 4481 | M00279 | non-negotiable | false | 10 |
| R02812 | CPU can run a real vectorized control fabric | 4481 | M00279 | non-negotiable | false | 10 |
| R02813 | Ultimate station is not one model | 4485 | E0154 | non-negotiable | false | 10 |
| R02814 | Ultimate station is a local AI operating system | 4485 | E0154 | non-negotiable | false | 10 |
| R02815 | Ultimate station layer 1 — Oracle Layer (Large model on RTX PRO 6000) | 4488–4490 | M00280 | non-negotiable | false | 10 |
| R02816 | Ultimate station layer 1 — best model available for the task: Ling, Nemotron Super, Kimi, Qwen, DeepSeek | 4490 | M00280 | non-negotiable | false | 10 |
| R02817 | Ultimate station layer 2 — Scout Layer (3090 runs Nano/Flash/small coder/perception models) | 4492–4495 | M00280 | non-negotiable | false | 10 |
| R02818 | Ultimate station layer 2 — produces drafts, plans, embeddings, reranks, GUI/audio/document perception | 4494 | M00280 | non-negotiable | false | 10 |
| R02819 | Ultimate station layer 3 — Deterministic Cortex (AVX-512 branch engine) | 4496–4499 | M00280 | non-negotiable | false | 10 |
| R02820 | Ultimate station layer 3 — controls routing, policy, grammar, tool permissions, replay, KV cache, batching | 4498 | M00280 | non-negotiable | false | 10 |
| R02821 | Ultimate station layer 4 — Memory Hierarchy (VRAM KV = hot active / RAM = warm context+cache / ZFS+NVMe = replay+artifacts+cold+model library) | 4500–4503 | M00280 | non-negotiable | false | 10 |
| R02822 | Ultimate station layer 5 — Isolation Layer (VFIO 3090 VM, host owns truth, VM proposes host commits) | 4505–4508 | M00280 | non-negotiable | false | 10 |
| R02823 | Ultimate station layer 6 — Observability Layer (DCGM / OTel / eBPF / Prometheus, telemetry feeds scheduling) | 4510–4512 | M00280 | non-negotiable | false | 10 |
| R02824 | Classify models by role, not hype | 4517 | M00281 | non-negotiable | false | 10 |
| R02825 | Role — Oracle (highest quality model that fits on 96GB with useful context) | 4520–4521 | M00281 | non-negotiable | false | 10 |
| R02826 | Role — Executor (token-efficient agent model like Ling-2.6-flash) | 4523–4524 | M00281 | non-negotiable | false | 10 |
| R02827 | Role — Perception (Nemotron 3 Nano Omni for GUI, video, document, audio) | 4526–4527 | M00281 | non-negotiable | false | 10 |
| R02828 | Role — Scout (Nemotron 3 Nano / small Qwen / small coder on 3090) | 4529–4530 | M00281 | non-negotiable | false | 10 |
| R02829 | Role — Verifier (same oracle with strict prompt OR specialized judge/reward model) | 4532–4533 | M00281 | non-negotiable | false | 10 |
| R02830 | Role — Retriever (embedding + reranker, 3090 or CPU per size) | 4535–4536 | M00281 | non-negotiable | false | 10 |
| R02831 | Role — Fallback (llama.cpp / GGUF, robust offline operation) | 4538–4539 | M00281 | non-negotiable | false | 10 |
| R02832 | Runtime chooses dynamically — fast tool plan → Scout | 4545 | M00282 | non-negotiable | false | 10 |
| R02833 | Runtime chooses dynamically — visual screen state → Nano Omni | 4546 | M00282 | non-negotiable | false | 10 |
| R02834 | Runtime chooses dynamically — final code review → Oracle | 4547 | M00282 | non-negotiable | false | 10 |
| R02835 | Runtime chooses dynamically — 500 memory candidates filtered → CPU AVX-512 first | 4548 | M00282 | non-negotiable | false | 10 |
| R02836 | Runtime chooses dynamically — schema-valid JSON → grammar engine before sampling | 4549 | M00282 | non-negotiable | false | 10 |
| R02837 | Runtime chooses dynamically — risky shell → sandbox VM | 4550 | M00282 | non-negotiable | false | 10 |
| R02838 | Workstation has a model registry | 4555 | M00283 | non-negotiable | false | 10 |
| R02839 | Model registry entry — `ling_2_6_flash` role: executor | 4559–4564 | M00283 | non-negotiable | false | 10 |
| R02840 | Model registry entry — `ling_2_6_flash` strengths: [agentic, token-efficient, tool-use] | 4561 | M00283 | non-negotiable | false | 10 |
| R02841 | Model registry entry — `ling_2_6_flash` gpu: blackwell | 4562 | M00283 | non-negotiable | false | 10 |
| R02842 | Model registry entry — `ling_2_6_flash` precision: fp8_or_int4 | 4563 | M00283 | non-negotiable | false | 10 |
| R02843 | Model registry entry — `ling_2_6_flash` context_policy: medium_long | 4564 | M00283 | non-negotiable | false | 10 |
| R02844 | Model registry entry — `nemotron_3_nano` role: scout | 4566–4570 | M00283 | non-negotiable | false | 10 |
| R02845 | Model registry entry — `nemotron_3_nano` strengths: [fast, agentic, long-context] | 4568 | M00283 | non-negotiable | false | 10 |
| R02846 | Model registry entry — `nemotron_3_nano` gpu: rtx3090_or_blackwell | 4569 | M00283 | non-negotiable | false | 10 |
| R02847 | Model registry entry — `nemotron_3_nano` precision: fp8_or_4bit | 4570 | M00283 | non-negotiable | false | 10 |
| R02848 | Model registry entry — `nemotron_3_nano_omni` role: perception | 4572–4576 | M00283 | non-negotiable | false | 10 |
| R02849 | Model registry entry — `nemotron_3_nano_omni` strengths: [vision, audio, video, docs, gui] | 4574 | M00283 | non-negotiable | false | 10 |
| R02850 | Model registry entry — `nemotron_3_nano_omni` gpu: rtx3090_or_blackwell | 4575 | M00283 | non-negotiable | false | 10 |
| R02851 | Model registry entry — `nemotron_3_nano_omni` precision: fp8_or_4bit | 4576 | M00283 | non-negotiable | false | 10 |
| R02852 | Model registry entry — `large_oracle` role: verifier | 4578–4583 | M00283 | non-negotiable | false | 10 |
| R02853 | Model registry entry — `large_oracle` strengths: [deep reasoning, final synthesis] | 4580 | M00283 | non-negotiable | false | 10 |
| R02854 | Model registry entry — `large_oracle` gpu: blackwell | 4581 | M00283 | non-negotiable | false | 10 |
| R02855 | Model registry entry — `large_oracle` precision: bf16_fp8_nvfp4 | 4582 | M00283 | non-negotiable | false | 10 |
| R02856 | Scheduler uses telemetry and policy — `if task.visual: route perception to Nano Omni` | 4588 | M00282 | non-negotiable | true | 10 |
| R02857 | Scheduler uses telemetry and policy — `if task.agentic_fast: route draft to Ling/Nemotron Nano` | 4591 | M00282 | non-negotiable | true | 10 |
| R02858 | Scheduler uses telemetry and policy — `if risk.high or commit.final: route to oracle` | 4594 | M00282 | non-negotiable | true | 10 |
| R02859 | Scheduler uses telemetry and policy — `if output.structured: enable grammar/token masks` | 4597 | M00282 | non-negotiable | true | 10 |
| R02860 | Scheduler uses telemetry and policy — `if branch.low_value: keep on scout or kill` | 4600 | M00282 | non-negotiable | true | 10 |
| R02861 | Scheduler uses telemetry and policy — `if oracle_idle: increase batch or verification depth` | 4603 | M00282 | non-negotiable | true | 10 |
| R02862 | Big insight — Ling: token-efficient agent executor | 4612 | M00284 | non-negotiable | false | 10 |
| R02863 | Big insight — Nemotron: hybrid MoE, MTP, long context, NVFP4, multimodal Nano Omni | 4613 | M00284 | non-negotiable | false | 10 |
| R02864 | Big insight — Qwen / Kimi / DeepSeek: huge sparse agentic/coding models | 4614 | M00284 | non-negotiable | false | 10 |
| R02865 | Big insight — Blackwell: FP4 / NVFP4 hardware | 4615 | M00284 | non-negotiable | false | 10 |
| R02866 | Big insight — Zen 5: full-width AVX-512 control fabric | 4616 | M00284 | non-negotiable | false | 10 |
| R02867 | Ultimate station should not chase a single champion model | 4619 | M00284 | non-negotiable | false | 10 |
| R02868 | Ultimate station should become a model router with deterministic infrastructure | 4621 | M00284 | non-negotiable | false | 10 |
| R02869 | The CPU gives you law | 4623 | M00284 | non-negotiable | false | 10 |
| R02870 | The Blackwell gives you depth | 4624 | M00284 | non-negotiable | false | 10 |
| R02871 | The 3090 gives you cheap parallel perception and speculation | 4625 | M00284 | non-negotiable | false | 10 |
| R02872 | ZFS/RAM give you memory | 4626 | M00284 | non-negotiable | false | 10 |
| R02873 | Observability gives you adaptation | 4627 | M00284 | non-negotiable | false | 10 |
| R02874 | High-end move — local agentic AI workstation where newest models are hot-swappable workers inside deterministic replayable vectorized operating environment | 4628–4629 | M00284 | non-negotiable | false | 10 |
| R02875 | Serving backend operator-overrideable (vllm / sglang / tensorrt_llm / llama_cpp) | 4441–4453 | F01394 | non-negotiable | true | 10 |
| R02876 | Blackwell precision operator-overrideable (bf16 / fp16 / fp8 / nvfp4 / mxfp4) | 4433–4437 | F01397 | non-negotiable | true | 10 |
| R02877 | Env var `SOVEREIGN_SERVING_BACKEND` | 4441–4453 | F01395 | non-negotiable | true | 10 |
| R02878 | Env var `SOVEREIGN_BLACKWELL_PRECISION` | 4433–4437 | F01398 | non-negotiable | true | 10 |
| R02879 | CLI `--serving-backend <name>` | 4441–4453 | F01396 | non-negotiable | true | 10 |
| R02880 | CLI `--blackwell-precision <mode>` | 4433–4437 | F01399 | non-negotiable | true | 10 |
| R02881 | API `GET /v1/models` lists registry | 4555–4583 | F01434 | non-negotiable | true | 10 |
| R02882 | API `GET /v1/models/{name}` returns single entry | 4555–4583 | F01435 | non-negotiable | true | 10 |
| R02883 | API `POST /v1/models/route` returns chosen model + reason for a task spec | 4587–4605 | F01436 | non-negotiable | true | 10 |
| R02884 | Dashboard — model portfolio overview | 4519–4583 | F01437 | non-negotiable | true | 10 |
| R02885 | Dashboard — Blackwell precision ladder selector | 4429–4438 | F01438 | non-negotiable | true | 10 |
| R02886 | Dashboard — serving-backend overview | 4441–4453 | F01439 | non-negotiable | true | 10 |
| R02887 | Test — model registry round-trips per-model YAML schema (role / strengths / gpu / precision / context_policy) | 4555–4583 | M00283 | non-negotiable | false | 10 |
| R02888 | Test — telemetry-driven routing produces expected model choice for each of the 6 task-spec rules | 4587–4605 | M00282 | non-negotiable | false | 10 |
| R02889 | Test — 7-role taxonomy is closed (Oracle/Executor/Perception/Scout/Verifier/Retriever/Fallback) | 4519–4540 | M00281 | non-negotiable | false | 10 |
| R02890 | Test — Ultimate Station 6-layer rollup enumerates all six layers by operator-named title | 4488–4513 | M00280 | non-negotiable | false | 10 |

— End of M017 milestone file.
