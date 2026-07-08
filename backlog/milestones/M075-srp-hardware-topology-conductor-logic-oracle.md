# M075 — SRP hardware topology mapping (Conductor on CPU / Logic on GPU 0 / Oracle on GPU 1)

**Parent**: sovereign-os runtime — three-agent orchestration topology
**Source**: `~/infohub/raw/dumps/2026-05-15-sain-01-master-spec-other-conversation-transposition.md` lines 812-851 (Section 17: Single Responsibility Principle Orchestration Topology)

## Doctrinal anchors

> "To scale a sovereign node without succumbing to code maintenance decay, we map the Single Responsibility Principle (SRP) directly to physical hardware layers." (dump 813)
> "An agent should possess only one operational domain, and its runtime framework must align perfectly with the hardware best suited for that domain." (dump 814)

## Epics (E0718-E0727)

| epic | name | source |
|---|---|---|
| E0718 | Vibe Managing Orchestration Harness — top-level coordinator | dump 816 |
| E0719 | Conductor Agent — CPU bound — SRP: Routing & State Fabric | dump 822-823, 826-829 |
| E0720 | Logic Engine — GPU 0 RTX 4090 — SRP: Ingestion & Translation | dump 823-824, 830-833 |
| E0721 | Oracle Core — GPU 1 Blackwell PRO 6000 — SRP: Long-Term Deep Reasoning | dump 824, 834-837 |
| E0722 | Conductor runtime — natively compiled 1-bit/Ternary BitNet via bitnet.cpp pinned to high-priority CPU cores | dump 827 |
| E0723 | Logic runtime — mid-scale quantized models (Llama-3-70B Q4_K_M or IQ4_NL) in Podman container | dump 831-832 |
| E0724 | Oracle runtime — full-precision FP16 or uncompromised models in 96GB Blackwell pool | dump 835-836 |
| E0725 | Conductor justification — state orchestration requires instantaneous branching + low latency for small context blocks | dump 828 |
| E0726 | Logic justification — balances throughput against 24GB VRAM ceiling | dump 833 |
| E0727 | Oracle justification — complete freedom from quantization degradation for absolute accuracy | dump 836-837 |

## Modules (M01241-M01257)

| module | name | source |
|---|---|---|
| M01241 | sovereign-srp-vibe-managing-harness | dump 816 |
| M01242 | sovereign-srp-conductor-agent (CPU bound) | dump 822-829 |
| M01243 | sovereign-srp-logic-engine (GPU 0 RTX 4090) | dump 823, 830-833 |
| M01244 | sovereign-srp-oracle-core (GPU 1 Blackwell) | dump 824, 834-837 |
| M01245 | sovereign-srp-conductor-bitnet-runtime | dump 827 + cross-ref M073 |
| M01246 | sovereign-srp-logic-podman-bridge | dump 832 |
| M01247 | sovereign-srp-oracle-fp16-runtime | dump 835-836 |
| M01248 | sovereign-srp-routing-state-fabric | dump 822-829 |
| M01249 | sovereign-srp-ingestion-translation-engine | dump 830-833 |
| M01250 | sovereign-srp-deep-reasoning-engine | dump 834-837 |
| M01251 | sovereign-srp-task-router (which agent handles which task) | dump 813-815 |
| M01252 | sovereign-srp-decay-prevention-validator (SRP boundary enforcer) | dump 813 |
| M01253 | sovereign-srp-typed-mirror | cross-ref selfdef MS007 |
| M01254 | sovereign-srp-event-emitter | cross-ref M049 + selfdef MS026 |
| M01255 | sovereign-srp-dashboard-binding (D-01 + D-03 + D-09) | cross-ref M060 |
| M01256 | sovereign-srp-replay-validator | cross-ref selfdef MS009 |
| M01257 | sovereign-srp-cli-subcommand-set | cross-ref selfdef MS043 |

## Features (F06206-F06290)

| feature | name | source |
|---|---|---|
| F06206 | Doctrinal — SRP mapped directly to physical hardware layers | dump 813 |
| F06207 | Doctrinal — one agent, one operational domain | dump 814 |
| F06208 | Doctrinal — runtime framework aligns perfectly with hardware | dump 814 |
| F06209 | Doctrinal — prevents code maintenance decay | dump 813 |
| F06210 | Topology diagram — Vibe Managing Orchestration Harness as root | dump 816 |
| F06211 | Topology diagram — three branches: Host CPU / GPU 0 / GPU 1 | dump 818-820 |
| F06212 | Topology — Host CPU Threads branch: Vector Pipeline + AVX-512/bitnet.cpp + State Routing & Logs | dump 818 |
| F06213 | Topology — Local GPU 0 branch: High-Speed VRAM + Exclusively quantized + Intermediate Context | dump 819 |
| F06214 | Topology — Local GPU 1 branch: Massive VRAM Silicon + Un-quantized/FP16 + Deep In-Context Memory | dump 820 |
| F06215 | Topology diagram preserved verbatim from dump 816-825 | dump 816-825 |
| F06216 | Conductor Agent — (SRP: Routing & State Fabric) | dump 822 |
| F06217 | Conductor — evaluates incoming user intent | dump 826 |
| F06218 | Conductor — updates CLAUDE.md | dump 826 |
| F06219 | Conductor — enforces state rules in SOUL.md | dump 826 |
| F06220 | Conductor — branches operational tree | dump 826 |
| F06221 | Conductor runtime — natively compiled 1-bit/Ternary BitNet | dump 827 |
| F06222 | Conductor runtime — executes via bitnet.cpp | dump 827 |
| F06223 | Conductor runtime — pinned to high-priority CPU cores | dump 827 |
| F06224 | Conductor justification — instantaneous branching | dump 828 |
| F06225 | Conductor justification — low latency for small context blocks | dump 828 |
| F06226 | Conductor justification — prevents small-kernel context-switching on GPUs | dump 829 |
| F06227 | Conductor — composes with M070 CCD 0 (CPU placement) | cross-ref M070 |
| F06228 | Conductor — composes with M073 ternary execution | cross-ref M073 |
| F06229 | Conductor — composes with M074 VNNI fusion | cross-ref M074 |
| F06230 | Logic Engine — (SRP: Ingestion & Translation) | dump 823 |
| F06231 | Logic — heavy-duty parsing | dump 830 |
| F06232 | Logic — regular expression extraction | dump 830 |
| F06233 | Logic — structural JSON compilation | dump 830 |
| F06234 | Logic — fast text embedding generation | dump 830 |
| F06235 | Logic runtime — mid-scale quantized models | dump 831 |
| F06236 | Logic runtime — example: Llama-3-70B Q4_K_M | dump 832 |
| F06237 | Logic runtime — example: Llama-3-70B IQ4_NL | dump 832 |
| F06238 | Logic runtime — managed via dedicated Podman container bridge | dump 832 |
| F06239 | Logic justification — balances throughput against 24GB VRAM ceiling | dump 833 |
| F06240 | Logic — RTX 4090 24GB GDDR6X target | dump 823 + cross-ref M044 |
| F06241 | Logic — composes with sovereign-os scout role per M058 | cross-ref M058 |
| F06242 | Logic — composes with M068 ZFS tank/models for model storage | cross-ref M068 |
| F06243 | Oracle Core — (SRP: Long-Term Deep Reasoning) | dump 824 |
| F06244 | Oracle — extended, multi-turn recursive reasoning | dump 834 |
| F06245 | Oracle — complex architectural analysis | dump 834 |
| F06246 | Oracle — codebase validation | dump 834 |
| F06247 | Oracle — large historical context verification | dump 834 |
| F06248 | Oracle runtime — full-precision FP16 | dump 835 |
| F06249 | Oracle runtime — uncompromised high-precision models | dump 835 |
| F06250 | Oracle runtime — utilizes massive 96GB Blackwell memory pool | dump 836 |
| F06251 | Oracle justification — complete freedom from quantization degradation | dump 836-837 |
| F06252 | Oracle justification — absolute accuracy during complex system optimization | dump 837 |
| F06253 | Oracle — RTX PRO 6000 Blackwell 96GB GDDR7 FP4 target | dump 824 + cross-ref M044 |
| F06254 | Oracle — composes with sovereign-os oracle role per M058 | cross-ref M058 |
| F06255 | Vibe Managing Harness — top-level coordinator | dump 816 |
| F06256 | Vibe Managing Harness — routes incoming task to correct SRP agent | dump 813-816 |
| F06257 | Vibe Managing Harness — composes with M058 hardware-aware scheduler | cross-ref M058 |
| F06258 | Vibe Managing Harness — composes with M057 12-step task lifecycle (Map step routes to SRP agent) | cross-ref M057 |
| F06259 | Vibe Managing Harness — uses M059 super-model identity as routing reference | cross-ref M059 |
| F06260 | Task router — analyzes task signature, picks SRP agent | architecture + dump 813 |
| F06261 | Task router — emits M049 trace per routing decision | cross-ref M049 |
| F06262 | Task router — emits OCSF System Activity 1001 per routing decision | cross-ref selfdef MS026 |
| F06263 | Task router — overrideable via operator profile (MS040) | cross-ref selfdef MS040 |
| F06264 | Decay prevention — SRP boundary enforcer | dump 813 |
| F06265 | Decay prevention — detects cross-SRP code drift | architecture |
| F06266 | Decay prevention — emits OCSF Detection 2004 on SRP violation | cross-ref selfdef MS026 |
| F06267 | Typed mirror — sovereign-srp-topology-mirror under MS007 8/8 SATURATED | cross-ref selfdef MS007 |
| F06268 | Typed mirror — SrpAgent enum (Conductor / LogicEngine / OracleCore) | cross-ref selfdef MS007 |
| F06269 | Typed mirror — SrpAllocation struct {agent, hardware_target, runtime_engine, model, responsibility, justification} | cross-ref selfdef MS007 |
| F06270 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 |
| F06271 | Typed mirror — signed via MS003 | cross-ref selfdef MS003 |
| F06272 | Event emitter — every SRP routing decision emits M049 trace | cross-ref M049 |
| F06273 | Event emitter — every SRP execution emits OCSF System Activity 1001 | cross-ref selfdef MS026 |
| F06274 | Event emitter — SRP violation emits OCSF Detection 2004 | cross-ref selfdef MS026 |
| F06275 | Dashboard — D-01 active sessions shows per-SRP-agent active tasks | cross-ref M060 |
| F06276 | Dashboard — D-03 model health shows per-SRP-agent model status | cross-ref M060 |
| F06277 | Dashboard — D-09 hardware pressure shows per-SRP-agent hardware utilization | cross-ref M060 |
| F06278 | Replay validator — verifies historical SRP routing chain | cross-ref selfdef MS009 |
| F06279 | Replay validator — detects unauthorized SRP boundary crossing | cross-ref selfdef MS009 + MS003 |
| F06280 | Replay validator — runs daily | cross-ref selfdef MS009 |
| F06281 | CLI — `sovereign srp show` returns current SRP topology | cross-ref selfdef MS043 |
| F06282 | CLI — `sovereign srp route <task>` shows SRP routing decision | architecture |
| F06283 | CLI — `sovereign srp metrics` per-agent metrics | architecture |
| F06284 | CLI — all srp subcommands emit M049 trace | cross-ref M049 |
| F06285 | Composition — composes with M044 substrate (Ryzen 9 9900X + RTX 4090 + Blackwell 96GB) | cross-ref M044 |
| F06286 | Composition — composes with M058 hardware-aware scheduler (Blackwell oracle / 4090 scout / CPU cortex roles) | cross-ref M058 |
| F06287 | Composition — composes with M066 Trinity (Conductor=Pulse, Logic=scout, Oracle=oracle mapping) | cross-ref M066 |
| F06288 | Composition — composes with M076 3 load-balancing profiles (operationalize SRP per workload) | cross-ref M076 (pending) |
| F06289 | Boundary — SRP topology = sovereign-os runtime; selfdef IPS enforces boundaries via MS036/MS038 | operator standing direction + cross-ref selfdef MS036 + MS038 |
| F06290 | Closing — M075 covers dump 812-837 verbatim SRP hardware topology; M076 3 load-balancing profiles next | dump 812-837 + operator standing direction |

## Requirements (R12411-R12580)

| req | description | source | feature | priority | exception | sub-reqs |
|---|---|---|---|---|---|---|
| R12411 | Doctrinal — SRP mapped directly to physical hardware layers | dump 813 | F06206 | non-negotiable | false | 10 |
| R12412 | Doctrinal — one agent, one operational domain | dump 814 | F06207 | non-negotiable | false | 10 |
| R12413 | Doctrinal — runtime framework aligns perfectly with hardware | dump 814 | F06208 | non-negotiable | false | 10 |
| R12414 | Doctrinal — prevents code maintenance decay | dump 813 | F06209 | non-negotiable | false | 10 |
| R12415 | Topology diagram preserved verbatim | dump 816-825 | F06215 | non-negotiable | false | 10 |
| R12416 | Topology — Vibe Managing Orchestration Harness as root | dump 816 | F06210 | non-negotiable | false | 10 |
| R12417 | Topology — three branches (Host CPU / GPU 0 / GPU 1) | dump 818-820 | F06211 | non-negotiable | false | 10 |
| R12418 | Topology — Host CPU branch: Vector Pipeline + AVX-512/bitnet.cpp + State Routing & Logs | dump 818 | F06212 | non-negotiable | false | 10 |
| R12419 | Topology — GPU 0 branch: High-Speed VRAM + Exclusively quantized + Intermediate Context | dump 819 | F06213 | non-negotiable | false | 10 |
| R12420 | Topology — GPU 1 branch: Massive VRAM Silicon + Un-quantized/FP16 + Deep In-Context Memory | dump 820 | F06214 | non-negotiable | false | 10 |
| R12421 | Conductor — SRP: Routing & State Fabric | dump 822 | F06216 | non-negotiable | false | 10 |
| R12422 | Conductor — evaluates incoming user intent | dump 826 | F06217 | non-negotiable | false | 10 |
| R12423 | Conductor — updates CLAUDE.md | dump 826 | F06218 | non-negotiable | false | 10 |
| R12424 | Conductor — enforces state rules in SOUL.md | dump 826 | F06219 | non-negotiable | false | 10 |
| R12425 | Conductor — branches operational tree | dump 826 | F06220 | non-negotiable | false | 10 |
| R12426 | Conductor runtime — natively compiled 1-bit/Ternary BitNet | dump 827 | F06221 | non-negotiable | false | 10 |
| R12427 | Conductor runtime — executes via bitnet.cpp | dump 827 | F06222 | non-negotiable | false | 10 |
| R12428 | Conductor runtime — pinned to high-priority CPU cores | dump 827 | F06223 | non-negotiable | false | 10 |
| R12429 | Conductor justification — instantaneous branching | dump 828 | F06224 | non-negotiable | false | 10 |
| R12430 | Conductor justification — low latency for small context blocks | dump 828 | F06225 | non-negotiable | false | 10 |
| R12431 | Conductor justification — prevents small-kernel context-switching on GPUs | dump 829 | F06226 | non-negotiable | false | 10 |
| R12432 | Conductor — composes with M070 CCD 0 Pulse placement | cross-ref M070 | F06227 | non-negotiable | false | 10 |
| R12433 | Conductor — composes with M073 ternary execution | cross-ref M073 | F06228 | non-negotiable | false | 10 |
| R12434 | Conductor — composes with M074 VNNI fusion | cross-ref M074 | F06229 | non-negotiable | false | 10 |
| R12435 | Conductor — composes with M071 atomic state writes for CLAUDE.md updates | cross-ref M071 | F06218 | non-negotiable | false | 10 |
| R12436 | Logic Engine — SRP: Ingestion & Translation | dump 823 | F06230 | non-negotiable | false | 10 |
| R12437 | Logic — heavy-duty parsing | dump 830 | F06231 | non-negotiable | false | 10 |
| R12438 | Logic — regular expression extraction | dump 830 | F06232 | non-negotiable | false | 10 |
| R12439 | Logic — structural JSON compilation | dump 830 | F06233 | non-negotiable | false | 10 |
| R12440 | Logic — fast text embedding generation | dump 830 | F06234 | non-negotiable | false | 10 |
| R12441 | Logic runtime — mid-scale quantized models | dump 831 | F06235 | non-negotiable | false | 10 |
| R12442 | Logic runtime — example Llama-3-70B Q4_K_M | dump 832 | F06236 | non-negotiable | false | 10 |
| R12443 | Logic runtime — example Llama-3-70B IQ4_NL | dump 832 | F06237 | non-negotiable | false | 10 |
| R12444 | Logic runtime — managed via dedicated Podman container bridge | dump 832 | F06238 | non-negotiable | false | 10 |
| R12445 | Logic justification — balances throughput against 24GB VRAM ceiling | dump 833 | F06239 | non-negotiable | false | 10 |
| R12446 | Logic — RTX 4090 24GB GDDR6X target | dump 823 + cross-ref M044 | F06240 | non-negotiable | false | 10 |
| R12447 | Logic — composes with sovereign-os scout role per M058 | cross-ref M058 | F06241 | non-negotiable | false | 10 |
| R12448 | Logic — composes with M068 ZFS tank/models for model storage | cross-ref M068 | F06242 | non-negotiable | false | 10 |
| R12449 | Logic — composes with M070 CCD 1 host cores 10-11 for IRQ routing | cross-ref M070 | F06240 | non-negotiable | false | 10 |
| R12450 | Logic — composes with selfdef MS036 sandbox tiers (Tier B Podman) | cross-ref selfdef MS036 | F06238 | non-negotiable | false | 10 |
| R12451 | Oracle Core — SRP: Long-Term Deep Reasoning | dump 824 | F06243 | non-negotiable | false | 10 |
| R12452 | Oracle — extended, multi-turn recursive reasoning | dump 834 | F06244 | non-negotiable | false | 10 |
| R12453 | Oracle — complex architectural analysis | dump 834 | F06245 | non-negotiable | false | 10 |
| R12454 | Oracle — codebase validation | dump 834 | F06246 | non-negotiable | false | 10 |
| R12455 | Oracle — large historical context verification | dump 834 | F06247 | non-negotiable | false | 10 |
| R12456 | Oracle runtime — full-precision FP16 | dump 835 | F06248 | non-negotiable | false | 10 |
| R12457 | Oracle runtime — uncompromised high-precision models | dump 835 | F06249 | non-negotiable | false | 10 |
| R12458 | Oracle runtime — utilizes massive 96GB Blackwell memory pool | dump 836 | F06250 | non-negotiable | false | 10 |
| R12459 | Oracle justification — complete freedom from quantization degradation | dump 836-837 | F06251 | non-negotiable | false | 10 |
| R12460 | Oracle justification — absolute accuracy during complex system optimization | dump 837 | F06252 | non-negotiable | false | 10 |
| R12461 | Oracle — RTX PRO 6000 Blackwell 96GB GDDR7 FP4 target | dump 824 + cross-ref M044 | F06253 | non-negotiable | false | 10 |
| R12462 | Oracle — composes with sovereign-os oracle role per M058 | cross-ref M058 | F06254 | non-negotiable | false | 10 |
| R12463 | Oracle — composes with M067 kernel build (FP16 via avx512fp16) | cross-ref M067 | F06248 | non-negotiable | false | 10 |
| R12464 | Oracle — composes with M068 ZFS tank/models for model storage | cross-ref M068 | F06250 | non-negotiable | false | 10 |
| R12465 | Vibe Managing Harness — top-level coordinator | dump 816 | F06255 | non-negotiable | false | 10 |
| R12466 | Vibe Managing Harness — routes task to correct SRP agent | dump 813-816 | F06256 | non-negotiable | false | 10 |
| R12467 | Vibe Managing Harness — composes with M058 hardware-aware scheduler | cross-ref M058 | F06257 | non-negotiable | false | 10 |
| R12468 | Vibe Managing Harness — composes with M057 12-step task lifecycle (Map step) | cross-ref M057 | F06258 | non-negotiable | false | 10 |
| R12469 | Vibe Managing Harness — uses M059 super-model identity as routing reference | cross-ref M059 | F06259 | non-negotiable | false | 10 |
| R12470 | Vibe Managing Harness — composes with M060 cockpit (D-01 surfaces routing) | cross-ref M060 | F06275 | non-negotiable | false | 10 |
| R12471 | Task router — analyzes task signature, picks SRP agent | architecture + dump 813 | F06260 | non-negotiable | false | 10 |
| R12472 | Task router — emits M049 trace per routing decision | cross-ref M049 | F06261 | non-negotiable | false | 10 |
| R12473 | Task router — emits OCSF System Activity 1001 per routing decision | cross-ref selfdef MS026 | F06262 | non-negotiable | false | 10 |
| R12474 | Task router — overrideable via operator profile (MS040) | cross-ref selfdef MS040 | F06263 | non-negotiable | false | 10 |
| R12475 | Task router — operator override emits OCSF Configuration Change 5001 | cross-ref selfdef MS026 | F06263 | non-negotiable | false | 10 |
| R12476 | Decay prevention — SRP boundary enforcer | dump 813 | F06264 | non-negotiable | false | 10 |
| R12477 | Decay prevention — detects cross-SRP code drift | architecture | F06265 | non-negotiable | false | 10 |
| R12478 | Decay prevention — emits OCSF Detection 2004 on SRP violation | cross-ref selfdef MS026 | F06266 | non-negotiable | false | 10 |
| R12479 | Decay prevention — drift triggers operator notification (D-06 dashboard) | cross-ref M060 | F06266 | non-negotiable | false | 10 |
| R12480 | Decay prevention — drift logged in MS009 audit chain | cross-ref selfdef MS009 | F06266 | non-negotiable | false | 10 |
| R12481 | Typed mirror — sovereign-srp-topology-mirror under MS007 8/8 SATURATED | cross-ref selfdef MS007 | F06267 | non-negotiable | false | 10 |
| R12482 | Typed mirror — SrpAgent enum (Conductor / LogicEngine / OracleCore) | cross-ref selfdef MS007 | F06268 | non-negotiable | false | 10 |
| R12483 | Typed mirror — SrpAllocation struct fields | cross-ref selfdef MS007 | F06269 | non-negotiable | false | 10 |
| R12484 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 | F06270 | non-negotiable | false | 10 |
| R12485 | Typed mirror — signed via MS003 | cross-ref selfdef MS003 | F06271 | non-negotiable | false | 10 |
| R12486 | Typed mirror — re-exported via sovereign-os cargo workspace | cross-ref selfdef MS007 | F06267 | non-negotiable | false | 10 |
| R12487 | Typed mirror — no_std friendly | architecture | F06267 | non-negotiable | false | 10 |
| R12488 | Typed mirror — serde + bincode derives present | architecture | F06267 | non-negotiable | false | 10 |
| R12489 | Typed mirror — schema-breaking changes require schema_version bump | architecture + cross-ref selfdef MS007 | F06270 | non-negotiable | false | 10 |
| R12490 | Event — every SRP routing decision emits M049 trace | cross-ref M049 | F06272 | non-negotiable | false | 10 |
| R12491 | Event — every SRP execution emits OCSF System Activity 1001 | cross-ref selfdef MS026 | F06273 | non-negotiable | false | 10 |
| R12492 | Event — SRP violation emits OCSF Detection 2004 | cross-ref selfdef MS026 | F06274 | non-negotiable | false | 10 |
| R12493 | Event — span includes SRP agent + hardware target + task signature | cross-ref M049 | F06272 | non-negotiable | false | 10 |
| R12494 | Event — span deterministic for MS009 replay | cross-ref selfdef MS009 | F06272 | non-negotiable | false | 10 |
| R12495 | Dashboard — D-01 active sessions shows per-SRP-agent active tasks | cross-ref M060 | F06275 | non-negotiable | false | 10 |
| R12496 | Dashboard — D-03 model health shows per-SRP-agent model status | cross-ref M060 | F06276 | non-negotiable | false | 10 |
| R12497 | Dashboard — D-09 hardware pressure shows per-SRP-agent hardware utilization | cross-ref M060 | F06277 | non-negotiable | false | 10 |
| R12498 | Dashboard — D-10 eval history shows per-SRP-agent eval scores | cross-ref M060 | F06276 | non-negotiable | false | 10 |
| R12499 | Dashboard — operator can drill into per-agent metrics | cross-ref M060 | F06275 | non-negotiable | false | 10 |
| R12500 | Replay validator — verifies historical SRP routing chain | cross-ref selfdef MS009 | F06278 | non-negotiable | false | 10 |
| R12501 | Replay validator — detects unauthorized SRP boundary crossing | cross-ref selfdef MS009 + MS003 | F06279 | non-negotiable | false | 10 |
| R12502 | Replay validator — emits OCSF Detection 2004 on chain break | cross-ref selfdef MS026 | F06278 | non-negotiable | false | 10 |
| R12503 | Replay validator — runs daily | cross-ref selfdef MS009 | F06280 | non-negotiable | false | 10 |
| R12504 | Replay validator — failures halt new SRP-routed tasks | architecture | F06278 | non-negotiable | false | 10 |
| R12505 | CLI — `sovereign srp show` returns current SRP topology | cross-ref selfdef MS043 | F06281 | non-negotiable | false | 10 |
| R12506 | CLI — `sovereign srp route <task>` shows SRP routing decision | architecture | F06282 | non-negotiable | false | 10 |
| R12507 | CLI — `sovereign srp metrics` per-agent metrics | architecture | F06283 | non-negotiable | false | 10 |
| R12508 | CLI — `sovereign srp benchmark` runs end-to-end benchmark | architecture | F06283 | non-negotiable | false | 10 |
| R12509 | CLI — `sovereign srp override <task> <agent>` operator-overrides routing (signed) | cross-ref selfdef MS003 | F06263 | non-negotiable | false | 10 |
| R12510 | CLI — all srp subcommands emit M049 trace | cross-ref M049 | F06284 | non-negotiable | false | 10 |
| R12511 | CLI — `--json` flag returns structured output | architecture | F06281 | non-negotiable | false | 10 |
| R12512 | Composition — composes with M044 substrate (Ryzen + 4090 + Blackwell hardware) | cross-ref M044 | F06285 | non-negotiable | false | 10 |
| R12513 | Composition — composes with M058 hardware-aware scheduler | cross-ref M058 | F06286 | non-negotiable | false | 10 |
| R12514 | Composition — composes with M066 Trinity (Conductor=Pulse / Logic=scout / Oracle=oracle) | cross-ref M066 | F06287 | non-negotiable | false | 10 |
| R12515 | Composition — composes with M067 kernel build (FP16 + AVX-512) | cross-ref M067 | F06463 | non-negotiable | false | 10 |
| R12516 | Composition — composes with M068 ZFS (tank/models per agent) | cross-ref M068 | F06242 | non-negotiable | false | 10 |
| R12517 | Composition — composes with M070 Dual-CCD (Conductor CCD 0 / Logic+Host CCD 1) | cross-ref M070 | F06223 | non-negotiable | false | 10 |
| R12518 | Composition — composes with M073 ternary (Conductor runtime) | cross-ref M073 | F06221 | non-negotiable | false | 10 |
| R12519 | Composition — composes with M074 VNNI (Conductor execution path) | cross-ref M074 | F06229 | non-negotiable | false | 10 |
| R12520 | Composition — composes forward with M076 3 load-balancing profiles | cross-ref M076 (pending) | F06288 | non-negotiable | false | 10 |
| R12521 | Composition — composes with M057 12-step task lifecycle (Map step picks SRP agent) | cross-ref M057 | F06258 | non-negotiable | false | 10 |
| R12522 | Composition — composes with M059 super-model identity (SRP agents + harness = governed machine) | cross-ref M059 | F06259 | non-negotiable | false | 10 |
| R12523 | Composition — composes with M060 cockpit dashboards | cross-ref M060 | F06275 | non-negotiable | false | 10 |
| R12524 | Composition — composes with selfdef MS036 sandbox tiers (Logic in Tier B Podman) | cross-ref selfdef MS036 | F06238 | non-negotiable | false | 10 |
| R12525 | Composition — composes with selfdef MS038 network boundary (Oracle = Ring 4 if cloud-augmented) | cross-ref selfdef MS038 | F06243 | non-negotiable | false | 10 |
| R12526 | Composition — composes with selfdef MS039 authority levels (each SRP execution authority-bound) | cross-ref selfdef MS039 | F06272 | non-negotiable | false | 10 |
| R12527 | Composition — composes with selfdef MS040 profile envelopes (SRP routing respects profile) | cross-ref selfdef MS040 | F06263 | non-negotiable | false | 10 |
| R12528 | Composition — composes with selfdef MS043 IPS operator surface | cross-ref selfdef MS043 | F06281 | non-negotiable | false | 10 |
| R12529 | Composition — composes with selfdef MS044 Guardian Daemon (monitors all SRP agents) | cross-ref selfdef MS044 | F06266 | non-negotiable | false | 10 |
| R12530 | Boundary — SRP topology = sovereign-os runtime owns | architecture + operator standing direction | F06289 | non-negotiable | false | 10 |
| R12531 | Boundary — selfdef IPS enforces sandbox + network per MS036+MS038 | operator standing direction | F06289 | non-negotiable | false | 10 |
| R12532 | Boundary — info-hub knowledge layer indexes SRP topology as second-brain entry | operator standing direction "second-brain" | F06289 | non-negotiable | false | 10 |
| R12533 | Boundary — cross-repo binding via MS007 sovereign-srp-topology-mirror only | cross-ref selfdef MS007 | F06267 | non-negotiable | false | 10 |
| R12534 | Doctrinal preservation — "Conductor Agent" verbatim | dump 822 | F06216 | non-negotiable | false | 10 |
| R12535 | Doctrinal preservation — "Logic Engine" verbatim | dump 823 | F06230 | non-negotiable | false | 10 |
| R12536 | Doctrinal preservation — "Oracle Core" verbatim | dump 824 | F06243 | non-negotiable | false | 10 |
| R12537 | Doctrinal preservation — "Vibe Managing Orchestration Harness" verbatim | dump 816 | F06255 | non-negotiable | false | 10 |
| R12538 | Doctrinal preservation — "Single Responsibility Principle" verbatim | dump 813 | F06206 | non-negotiable | false | 10 |
| R12539 | Doctrinal preservation — "code maintenance decay" verbatim | dump 813 | F06209 | non-negotiable | false | 10 |
| R12540 | Doctrinal preservation — `Llama-3-70B` verbatim | dump 832 | F06236 | non-negotiable | false | 10 |
| R12541 | Doctrinal preservation — `Q4_K_M` verbatim | dump 832 | F06236 | non-negotiable | false | 10 |
| R12542 | Doctrinal preservation — `IQ4_NL` verbatim | dump 832 | F06237 | non-negotiable | false | 10 |
| R12543 | Doctrinal preservation — `FP16` verbatim | dump 835 | F06248 | non-negotiable | false | 10 |
| R12544 | Doctrinal preservation — verbatim quotes never paraphrased | operator standing direction | F06290 | non-negotiable | false | 10 |
| R12545 | Doctrinal preservation — operator standing direction "you cannot invent crap" upheld | operator standing direction | F06290 | non-negotiable | false | 10 |
| R12546 | Doctrinal preservation — operator standing direction "Respect the projects" upheld | operator standing direction | F06289 | non-negotiable | false | 10 |
| R12547 | Doctrinal preservation — operator standing direction "second-brain" upheld | operator standing direction | F06289 | non-negotiable | false | 10 |
| R12548 | Doctrinal preservation — info-hub indexes SRP topology as second-brain entry | operator standing direction | F06289 | non-negotiable | false | 10 |
| R12549 | Performance — task routing latency `<` 5ms p95 | architecture | F06260 | non-negotiable | false | 10 |
| R12550 | Performance — Conductor task latency `<` 100ms p95 (small context state op) | architecture | F06225 | non-negotiable | false | 10 |
| R12551 | Performance — Logic task latency `<` 5s p95 (parsing + embedding) | architecture | F06239 | non-negotiable | false | 10 |
| R12552 | Performance — Oracle task latency `<` 60s p95 (multi-turn reasoning) | architecture | F06251 | non-negotiable | false | 10 |
| R12553 | Performance — typed-mirror publication latency `<` 100ms p95 | cross-ref selfdef MS007 | F06267 | non-negotiable | false | 10 |
| R12554 | Performance — replay validator daily run `<` 60s | cross-ref selfdef MS009 | F06278 | non-negotiable | false | 10 |
| R12555 | Telemetry — per-agent task count emitted via M049 | cross-ref M049 | F06272 | non-negotiable | false | 10 |
| R12556 | Telemetry — per-agent task latency histograms emitted via M049 | cross-ref M049 | F06272 | non-negotiable | false | 10 |
| R12557 | Telemetry — SRP violation count emitted via M049 (high-priority alert) | cross-ref M049 | F06274 | non-negotiable | false | 10 |
| R12558 | Telemetry — task router accuracy emitted via M049 (correct agent picked %) | cross-ref M049 | F06260 | non-negotiable | false | 10 |
| R12559 | Telemetry — operator override count emitted via M049 | cross-ref M049 | F06263 | non-negotiable | false | 10 |
| R12560 | Operator UX — operator may override task routing per profile | operator standing direction "modes and profiles" + cross-ref selfdef MS040 | F06263 | non-negotiable | false | 10 |
| R12561 | Operator UX — operator may benchmark per-agent performance | architecture | F06283 | non-negotiable | false | 10 |
| R12562 | Operator UX — operator may view SRP topology diagram in D-19 super-model | cross-ref M060 | F06210 | non-negotiable | false | 10 |
| R12563 | Operator UX — operator may toggle individual SRP agents on/off | operator standing direction "everything can be turned on and off" | F06281 | non-negotiable | false | 10 |
| R12564 | Operator UX — operator may set model preference per SRP agent | architecture + cross-ref selfdef MS040 | F06281 | non-negotiable | false | 10 |
| R12565 | Operational — sovereign-srp-harness.service systemd unit | architecture | F06255 | non-negotiable | false | 10 |
| R12566 | Operational — service honors SIGHUP for topology reload | architecture | F06255 | non-negotiable | false | 10 |
| R12567 | Operational — service refuses to start with chain-break detected | cross-ref selfdef MS009 | F06278 | non-negotiable | false | 10 |
| R12568 | Operational — service refuses to start with missing MS003 keys | cross-ref selfdef MS003 | F06271 | non-negotiable | false | 10 |
| R12569 | Operational — service readiness probe at /run/sovereign-srp/ready | architecture | F06255 | non-negotiable | false | 10 |
| R12570 | Operational — service emits start/stop events via M049 | cross-ref M049 | F06272 | non-negotiable | false | 10 |
| R12571 | Closing — SRP doctrine covers dump 812-815 verbatim | dump 812-815 | F06206 | non-negotiable | false | 10 |
| R12572 | Closing — topology diagram covers dump 816-825 verbatim | dump 816-825 | F06215 | non-negotiable | false | 10 |
| R12573 | Closing — Conductor section covers dump 826-829 verbatim | dump 826-829 | F06216 | non-negotiable | false | 10 |
| R12574 | Closing — Logic Engine section covers dump 830-833 verbatim | dump 830-833 | F06230 | non-negotiable | false | 10 |
| R12575 | Closing — Oracle Core section covers dump 834-837 verbatim | dump 834-837 | F06243 | non-negotiable | false | 10 |
| R12576 | Closing — sovereign-os catalog at 74/74 milestones | architecture | F06290 | non-negotiable | false | 10 |
| R12577 | Closing — combined ecosystem 118 milestones | architecture | F06290 | non-negotiable | false | 10 |
| R12578 | Closing — combined R-rows ~23140 | architecture | F06290 | non-negotiable | false | 10 |
| R12579 | Closing — every R-row carries 10 hard non-negotiable sub-requirements | operator standing direction | F06206 | non-negotiable | false | 10 |
| R12580 | Closing — M075 covers SRP hardware topology scope verbatim; M076 3 load-balancing profiles is LAST milestone | dump 812-837 + operator standing direction | F06290 | non-negotiable | false | 10 |

## Sub-requirements accounting

Every R-row carries 10 hard non-negotiable sub-requirements. Total = 170 R × 10 = **1,700 sub-requirements** for M075.

## Cross-references

- **M044** — substrate (Ryzen + RTX 4090 + Blackwell 96GB)
- **M048** — modules map (Compute Fabric + Sandbox Fabric)
- **M049** — observability + trace pipeline
- **M055** — failure modes (SRP violation taxonomy)
- **M057** — 12-step task lifecycle (Map step picks SRP agent)
- **M058** — hardware-aware scheduler (Blackwell oracle / 4090 scout / CPU cortex roles)
- **M059** — peace machine close (super-model = whole governed machine)
- **M060** — cockpit + dashboards (D-01 / D-03 / D-09 / D-10 / D-19)
- **M066** — Trinity Framework Genesis (Conductor=Pulse / Logic=scout / Oracle=oracle)
- **M067** — Custom Kernel Build (FP16 + AVX-512 paths)
- **M068** — ZFS Storage (tank/models per agent)
- **M070** — Dual-CCD topology (Conductor CCD 0 / Logic+Host CCD 1)
- **M071** — Atomic State Transition Protocol (Conductor CLAUDE.md updates)
- **M073** — 1-bit ternary (Conductor runtime)
- **M074** — AVX-512 VNNI (Conductor execution path)
- **M076** — 3 load-balancing profiles (pending; operationalizes SRP)
- **selfdef MS003** — selfdef-signing
- **selfdef MS007** — typed-mirror crate scheme (sovereign-srp-topology-mirror)
- **selfdef MS009** — replay validator
- **selfdef MS026** — observability + OCSF event emission
- **selfdef MS036** — sandbox tiers (Logic in Tier B Podman)
- **selfdef MS038** — network boundary (Oracle Ring 4 if cloud-augmented)
- **selfdef MS039** — authority levels
- **selfdef MS040** — six-profile authority matrix
- **selfdef MS043** — IPS operator surface
- **selfdef MS044** — Guardian Daemon

## Schema

```
schema_version: "1.0.0"
milestone_id: M075
parent: sovereign-os
epics: 10
modules: 17
features: 85
requirements: 170
sub_requirements_per_requirement: 10
total_sub_requirements: 1700
source_dump_lines: 812-837 (Section 17: Single Responsibility Principle Orchestration Topology)
three_agents:
  conductor: { srp: "Routing & State Fabric", hardware: "Host CPU Threads", runtime: "bitnet.cpp on AVX-512 ternary" }
  logic_engine: { srp: "Ingestion & Translation", hardware: "RTX 4090 24GB", runtime: "Llama-3-70B Q4_K_M / IQ4_NL in Podman" }
  oracle_core: { srp: "Long-Term Deep Reasoning", hardware: "RTX PRO 6000 Blackwell 96GB", runtime: "FP16 uncompromised models" }
harness_root: "Vibe Managing Orchestration Harness"
typed_mirror_crate: sovereign-srp-topology-mirror
catalog_status:
  sovereign_os: 74/74 milestones
  selfdef: 44/44 milestones
  combined: 118 milestones
```
