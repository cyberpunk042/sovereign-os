# M040 — Hyper features — MIG / FP4 / VFIO / ZFS commit gate

> Parent: `backlog/milestones/INDEX.md` row M040 (dump 11410–11790).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 11410–11790. Operator directive 11410: "Great Great. continue. do resaerchs online too. Think of hyper features".
> All entries below extract verbatim. No invention.

## Epics (E0378–E0387)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0378 | Operator directive — "Think of hyper features"; framing: "machine is not just CPU + GPUs — it is a stack of hardware affordances that can become software superpowers if exposed correctly" | 11410 + 11427–11429 |
| E0379 | Hyper Feature 1 — MIG / GPU Partitioning — RTX PRO 6000 Blackwell Workstation supports up to 4 MIG instances (NVIDIA docs + datasheet); MIG profiles become runtime profiles (Monolith Mode full 96GB / Partition Mode oracle+verifier+embedding-rerank+service slices / Sandbox Mode isolate experimental from production / Multi-tenant Mode per-client slices); fragmenting VRAM limits flexibility → treat as toggle not default; 4 example profiles (max-oracle MIG off / multi-agent-lab MIG on / production-stable MIG on / model-benchmark MIG off unless testing) | 11431–11472 |
| E0380 | Hyper Feature 2 — Blackwell FP4 / NVFP4 — "FP4 is not just compression. It changes the model portfolio"; 96GB hosts larger quantized MoE/oracle candidates; not blind trust — model lab qualification (BF16 baseline / FP8 / NVFP4-MXFP4 / GPTQ-AWQ-SmoothQuant / KV quantized) tested on 9 dimensions (coding / tool use / schema validity / agent trajectory / long-context recall / reasoning / latency / VRAM / energy); FP4 becomes profile decision (quality-critical BF16/FP8 / throughput FP8 / huge-model experiment FP4 / scout INT4/GPTQ) | 11474–11519 |
| E0381 | Hyper Feature 3 — AVX-512 As A Bit Engine — Zen 5 is deterministic accelerator; hyper feature is NOT just vector math but policy fusion + branch compaction + memory bitmap search + grammar masks + tool permission checks + reward-vector filtering + workflow state transitions; "makes adaptive profiles cheap enough to run constantly"; 512 candidate memories per bitset chunk / 8 branches per u64 vector / 64 tiny state flags per vector; 6 hot tables (BranchTable / MemoryMetaTable / ToolCapabilityTable / ModelRegistryTable / EvalResultTable / KVBlockTable); 5 operations (filter / intersect / popcount score / compress survivors / route batches) | 11521–11564 |
| E0382 | Hyper Feature 4 — GPUDirect Storage / NVMe To GPU — future/advanced; NVIDIA GDS documents direct path between local/remote storage and GPU memory, bypassing CPU bounce buffers; RAPIDS KvikIO wraps for GPU-friendly I/O; use carefully; wins: large model load / embedding-vector shard load / dataset streaming / GPU-side preprocessing / large binary cache movement; NOT first priority for: small prompts / agent traces / JSON logs / tool calls / workflow metadata; 3-phase plan (Phase 1 ZFS+normal-mmap-iouring+RAM cache / Phase 2 profile model/data load bottlenecks / Phase 3 test GDS-KvikIO for model/cache datasets); "Do not build around GDS until profiling proves it matters" | 11566–11605 |
| E0383 | Hyper Feature 5 — USB4 / External Expansion + Hyper Feature 6 — 10GbE + 2.5GbE Network Split — ProArt dual USB4 40Gbps (fast external backup / portable dataset drives / capture devices / external display / possible eGPU experiments not ideal); USB4 NOT main model path; 10GbE data plane (NAS / dataset sync / model artifact transfer / cluster peer) + 2.5GbE management (web dashboard / SSH / observability); Linux NIC support needs care — AQC113C/atlantic quirks on ProArt X870E + I226-V ASPM/WoL issues; NIC validation in setup (iperf3 10Gb test / ASPM stability test / suspend-resume test / driver-kernel pin / management VLAN failover); "Networking is part of reliability" | 11607–11654 |
| E0384 | Hyper Feature 7 — VFIO / IOMMU — second GPU (3090) becomes hard trust boundary; 3090 bare-metal (lower latency, simpler local services) vs 3090 VFIO VM (stronger isolation, sandboxed agents, risky tools) vs 3090 passthrough profile (computer-use agent / web automation / untrusted model-tool experiments); profile-level choice (performance: 3090 on host / security: 3090 in VM / experiment: snapshot VM, run wild, discard) | 11656–11684 |
| E0385 | Hyper Feature 8 — ZFS Snapshots As Commit Gate — ZFS is autonomy infrastructure (NOT just storage); before agent writes: snapshot → apply patch → test → commit or rollback; for experiments: clone workspace → run branch → compare artifacts → promote or destroy; "gives safe aggressive agents" | 11686–11708 |
| E0386 | Hyper Feature 9 — NPU Absence Is A Non-Issue — Ryzen 9000 desktop CPUs generally do not include Ryzen AI NPU; 9900X is not NPU platform; NPU equivalent = AVX-512 CPU (deterministic control) + 3090 (cheap SLM/perception) + Blackwell (oracle); "Do not chase NPU unless you add a separate Ryzen AI box later" | 11710–11720 |
| E0387 | Hyper Feature 10 — Modes As Hardware Configurations + Big Hardware Law — profiles should control hardware NOT just prompts; 4 example YAML profiles (max_oracle blackwell.mig=off + largest_oracle FP8 + 3090 scout + AVX high + cloud false; secure_agent_lab blackwell.mig=on slices oracle+verifier + 3090 vfio true sandbox + tools.network gated + zfs.snapshot_before_write true; fast_code blackwell.model=code_oracle + 3090 code_scout + CPU route aggressive + tests targeted; research_deep blackwell.oracle long_context + 3090 rerank + memory.graph_expansion high + eval.citation_verification true); "profiles drive the whole machine"; Big Hardware Law — "A feature is only powerful if the runtime can choose when to use it"; MIG / FP4 / VFIO / AVX-512 / ZFS / GDS / 10GbE / USB4 / quantization / cloud fallback: NONE should be hardcoded; "programmable knobs in your intelligence OS" | 11722–11784 |

## Modules (M00663–M00679)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00663 | MIG profile — Monolith Mode (full 96GB Blackwell for one large oracle) | 11440–11441 | E0379 |
| M00664 | MIG profile — Partition Mode (oracle slice + verifier slice + embedding-rerank slice + service slice) | 11443–11447 | E0379 |
| M00665 | MIG profile — Sandbox Mode (isolate experimental model from production oracle) | 11449–11450 | E0379 |
| M00666 | MIG profile — Multi-tenant Mode (one slice for Claude Code + one for OpenCode/Cline + one for background evals) | 11452–11455 | E0379 |
| M00667 | FP4 quantization candidate roster — BF16 baseline / FP8 / NVFP4-MXFP4 / GPTQ-AWQ-SmoothQuant / KV quantized | 11491–11496 | E0380 |
| M00668 | Model qualification test axes (9) — coding / tool use / schema validity / agent trajectory / long-context recall / reasoning / latency / VRAM / energy | 11501–11509 | E0380 |
| M00669 | AVX-512 hot table — BranchTable | 11548 | E0381 |
| M00670 | AVX-512 hot table — MemoryMetaTable | 11549 | E0381 |
| M00671 | AVX-512 hot table — ToolCapabilityTable | 11550 | E0381 |
| M00672 | AVX-512 hot table — ModelRegistryTable | 11551 | E0381 |
| M00673 | AVX-512 hot table — EvalResultTable | 11552 | E0381 |
| M00674 | AVX-512 hot table — KVBlockTable | 11553 | E0381 |
| M00675 | AVX-512 ops — filter / intersect / popcount-score / compress-survivors / route-batches | 11558–11563 | E0381 |
| M00676 | GDS adoption phases — Phase 1 ZFS+mmap+iouring+RAM / Phase 2 profile bottlenecks / Phase 3 test GDS-KvikIO | 11595–11603 | E0382 |
| M00677 | VFIO 3090 profile (performance/security/experiment) | 11675–11684 | E0384 |
| M00678 | ZFS commit-gate cycle — snapshot → apply patch → test → commit or rollback | 11692–11697 | E0385 |
| M00679 | NPU substitute trio — AVX-512 CPU + 3090 + Blackwell (replaces NPU) | 11713–11718 | E0386 |

## Features (F03316–F03400)

| F ID | Phrase | Dump line | Parent | Category | Opt-in |
|---|---|---|---|---|---|
| F03316 | Operator directive — "Think of hyper features" (verbatim 11410) | 11410 | E0378 | composite | false |
| F03317 | Framing — machine is stack of hardware affordances that can become software superpowers if exposed correctly | 11427–11429 | E0378 | composite | false |
| F03318 | MIG hyper feature — RTX PRO 6000 Blackwell Workstation supports up to 4 MIG instances (NVIDIA docs) | 11433 | E0379 | composite | true |
| F03319 | MIG datasheet confirms — MIG support + PCIe Gen5 + 96GB GDDR7 + FP4 tensor cores | 11433 | E0379 | composite | false |
| F03320 | MIG runtime profile — Monolith Mode (full 96GB) | 11440 | M00663 | composite | true |
| F03321 | MIG runtime profile — Partition Mode (oracle/verifier/embedding/service slices) | 11443 | M00664 | composite | true |
| F03322 | MIG runtime profile — Sandbox Mode (isolate experimental from production) | 11449 | M00665 | composite | true |
| F03323 | MIG runtime profile — Multi-tenant Mode (Claude Code / OpenCode-Cline / background evals slices) | 11452 | M00666 | composite | true |
| F03324 | MIG caveat — fragments VRAM + can limit flexibility; toggle not default | 11458 | E0379 | composite | false |
| F03325 | MIG profile — max-oracle (MIG off) | 11461 | E0379 | composite | true |
| F03326 | MIG profile — multi-agent-lab (MIG on) | 11464 | E0379 | composite | true |
| F03327 | MIG profile — production-stable (MIG on for isolation) | 11467 | E0379 | composite | true |
| F03328 | MIG profile — model-benchmark (MIG off unless testing smaller services) | 11470 | E0379 | composite | true |
| F03329 | FP4 hyper feature — "not just compression. changes the model portfolio" | 11476 | E0380 | composite | false |
| F03330 | FP4 enables 96GB hosting larger quantized MoE/oracle candidates | 11482–11483 | E0380 | composite | false |
| F03331 | Model qualification candidate — BF16 baseline | 11491 | M00667 | composite | true |
| F03332 | Model qualification candidate — FP8 | 11492 | M00667 | composite | true |
| F03333 | Model qualification candidate — NVFP4/MXFP4 | 11493 | M00667 | composite | true |
| F03334 | Model qualification candidate — GPTQ/AWQ/SmoothQuant | 11494 | M00667 | composite | true |
| F03335 | Model qualification candidate — KV quantized | 11495 | M00667 | composite | true |
| F03336 | Test axis — coding | 11501 | M00668 | composite | true |
| F03337 | Test axis — tool use | 11502 | M00668 | composite | true |
| F03338 | Test axis — schema validity | 11503 | M00668 | composite | true |
| F03339 | Test axis — agent trajectory | 11504 | M00668 | composite | true |
| F03340 | Test axis — long-context recall | 11505 | M00668 | composite | true |
| F03341 | Test axis — reasoning | 11506 | M00668 | composite | true |
| F03342 | Test axis — latency | 11507 | M00668 | composite | true |
| F03343 | Test axis — VRAM | 11508 | M00668 | composite | true |
| F03344 | Test axis — energy | 11509 | M00668 | composite | true |
| F03345 | FP4 profile — quality-critical (BF16/FP8) | 11515 | E0380 | composite | true |
| F03346 | FP4 profile — throughput (FP8) | 11516 | E0380 | composite | true |
| F03347 | FP4 profile — huge-model experiment (FP4) | 11517 | E0380 | composite | true |
| F03348 | FP4 profile — scout (INT4/GPTQ) | 11518 | E0380 | composite | true |
| F03349 | AVX-512 hyper feature — policy fusion | 11528 | E0381 | composite | true |
| F03350 | AVX-512 hyper feature — branch compaction | 11529 | E0381 | composite | true |
| F03351 | AVX-512 hyper feature — memory bitmap search | 11530 | E0381 | composite | true |
| F03352 | AVX-512 hyper feature — grammar masks | 11531 | E0381 | composite | true |
| F03353 | AVX-512 hyper feature — tool permission checks | 11532 | E0381 | composite | true |
| F03354 | AVX-512 hyper feature — reward-vector filtering | 11533 | E0381 | composite | true |
| F03355 | AVX-512 hyper feature — workflow state transitions | 11534 | E0381 | composite | true |
| F03356 | "Makes adaptive profiles cheap enough to run constantly" | 11537 | E0381 | composite | false |
| F03357 | AVX-512 throughput — 512 candidate memories per bitset chunk | 11540 | E0381 | composite | false |
| F03358 | AVX-512 throughput — 8 branches per u64 vector | 11541 | E0381 | composite | false |
| F03359 | AVX-512 throughput — 64 tiny state flags per vector | 11542 | E0381 | composite | false |
| F03360 | CPU hot table — BranchTable | 11548 | M00669 | composite | true |
| F03361 | CPU hot table — MemoryMetaTable | 11549 | M00670 | composite | true |
| F03362 | CPU hot table — ToolCapabilityTable | 11550 | M00671 | composite | true |
| F03363 | CPU hot table — ModelRegistryTable | 11551 | M00672 | composite | true |
| F03364 | CPU hot table — EvalResultTable | 11552 | M00673 | composite | true |
| F03365 | CPU hot table — KVBlockTable | 11553 | M00674 | composite | true |
| F03366 | CPU op — filter | 11559 | M00675 | composite | true |
| F03367 | CPU op — intersect | 11560 | M00675 | composite | true |
| F03368 | CPU op — popcount score | 11561 | M00675 | composite | true |
| F03369 | CPU op — compress survivors | 11562 | M00675 | composite | true |
| F03370 | CPU op — route batches | 11563 | M00675 | composite | true |
| F03371 | GDS — NVIDIA documents direct path between storage and GPU memory, bypassing CPU bounce buffers | 11568 | E0382 | composite | true |
| F03372 | GDS — RAPIDS KvikIO wraps for GPU-friendly I/O | 11568 | E0382 | composite | true |
| F03373 | GDS win — large model load | 11575 | E0382 | composite | true |
| F03374 | GDS win — embedding/vector shard load | 11576 | E0382 | composite | true |
| F03375 | GDS win — dataset streaming | 11577 | E0382 | composite | true |
| F03376 | GDS win — GPU-side preprocessing | 11578 | E0382 | composite | true |
| F03377 | GDS win — large binary cache movement | 11579 | E0382 | composite | true |
| F03378 | GDS NOT first priority for — small prompts | 11585 | E0382 | composite | false |
| F03379 | GDS NOT first priority for — agent traces | 11586 | E0382 | composite | false |
| F03380 | GDS NOT first priority for — JSON logs | 11587 | E0382 | composite | false |
| F03381 | GDS NOT first priority for — tool calls | 11588 | E0382 | composite | false |
| F03382 | GDS NOT first priority for — workflow metadata | 11589 | E0382 | composite | false |
| F03383 | GDS adoption Phase 1 — ZFS + normal mmap/io_uring + RAM cache | 11596 | M00676 | composite | false |
| F03384 | GDS adoption Phase 2 — profile model/data load bottlenecks | 11599 | M00676 | composite | false |
| F03385 | GDS adoption Phase 3 — test GDS/KvikIO for model/cache datasets | 11602 | M00676 | composite | false |
| F03386 | "Do not build around GDS until profiling proves it matters" | 11605 | E0382 | composite | false |
| F03387 | USB4 hyper feature — ProArt dual USB4 40Gbps (per ASUS) | 11609 | E0383 | composite | true |
| F03388 | USB4 uses — fast external backup / portable dataset drives / capture devices / external display+perception / possible eGPU (not ideal) | 11611–11616 | E0383 | composite | true |
| F03389 | USB4 placement — backup / ingest / peripheral expansion (NOT main model path) | 11622 | E0383 | composite | false |
| F03390 | Network hyper feature — 10GbE data plane + 2.5GbE management split | 11625–11642 | E0383 | composite | true |
| F03391 | Network — Linux NIC support needs care (AQC113C/atlantic quirks on ProArt X870E + I226-V ASPM/WoL issues) | 11644 | E0383 | composite | false |
| F03392 | Network — ASUS officially lists Marvell 10Gb + Intel 2.5Gb | 11644 | E0383 | composite | false |
| F03393 | Network validation — iperf3 10Gb test / ASPM stability test / suspend-resume test / driver-kernel pin / management VLAN failover | 11647–11651 | E0383 | composite | true |
| F03394 | "Networking is part of reliability" | 11654 | E0383 | composite | false |
| F03395 | VFIO hyper feature — second GPU becomes hard trust boundary | 11658 | E0384 | composite | false |
| F03396 | VFIO profiles — 3090 bare-metal (perf) / 3090 VFIO VM (security) / 3090 passthrough (computer-use+web automation+untrusted experiments) | 11661–11671 | M00677 | composite | true |
| F03397 | VFIO profile — performance (3090 on host) / security (3090 in VM) / experiment (snapshot VM, run wild, discard) | 11676–11684 | M00677 | composite | true |
| F03398 | ZFS hyper feature — autonomy infrastructure (NOT just storage); commit-gate cycle snapshot → apply → test → commit-or-rollback | 11688–11708 | M00678 | composite | false |
| F03399 | NPU absence is a non-issue — AVX-512 + 3090 + Blackwell substitute trio | 11710–11720 | M00679 | composite | false |
| F03400 | Composite — Hyper Feature 10 Modes As Hardware Configurations (4 example YAML profiles: max_oracle / secure_agent_lab / fast_code / research_deep) + Big Hardware Law "A feature is only powerful if the runtime can choose when to use it" (MIG/FP4/VFIO/AVX-512/ZFS/GDS/10GbE/USB4/quantization/cloud-fallback all programmable knobs, NONE hardcoded) | 11722–11784 | E0387 | composite | false |

## Requirements (R06631–R06800)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R06631 | Operator directive — "Think of hyper features" | 11410 | F03316 | non-negotiable | false | 10 |
| R06632 | Framing — machine is stack of hardware affordances that can become software superpowers if exposed correctly | 11427–11429 | F03317 | non-negotiable | false | 10 |
| R06633 | MIG hyper feature — RTX PRO 6000 Blackwell Workstation supports up to 4 MIG instances | 11433 | F03318 | non-negotiable | false | 10 |
| R06634 | MIG datasheet — MIG support + PCIe Gen5 + 96GB GDDR7 + FP4 tensor cores | 11433 | F03319 | non-negotiable | false | 10 |
| R06635 | MIG runtime profile — Monolith Mode (full 96GB Blackwell for one large oracle) | 11440–11441 | F03320 | non-negotiable | true | 10 |
| R06636 | MIG runtime profile — Partition Mode (oracle + verifier + embedding-rerank + service slices) | 11443–11447 | F03321 | non-negotiable | true | 10 |
| R06637 | MIG runtime profile — Sandbox Mode (isolate experimental model from production oracle) | 11449–11450 | F03322 | non-negotiable | true | 10 |
| R06638 | MIG runtime profile — Multi-tenant Mode (Claude Code / OpenCode-Cline / background evals slices) | 11452–11455 | F03323 | non-negotiable | true | 10 |
| R06639 | MIG caveat — fragments VRAM + can limit flexibility | 11458 | F03324 | non-negotiable | false | 10 |
| R06640 | MIG treat as toggle, not default | 11458 | F03324 | non-negotiable | false | 10 |
| R06641 | MIG profile — max-oracle MIG off | 11461 | F03325 | non-negotiable | true | 10 |
| R06642 | MIG profile — multi-agent-lab MIG on | 11464 | F03326 | non-negotiable | true | 10 |
| R06643 | MIG profile — production-stable MIG on for isolation | 11467 | F03327 | non-negotiable | true | 10 |
| R06644 | MIG profile — model-benchmark MIG off unless testing smaller services | 11470 | F03328 | non-negotiable | true | 10 |
| R06645 | FP4 hyper feature — "not just compression. changes the model portfolio" | 11476 | F03329 | non-negotiable | false | 10 |
| R06646 | FP4 — 96GB may host much larger quantized MoE/oracle candidates | 11482–11483 | F03330 | non-negotiable | false | 10 |
| R06647 | Model qualification — BF16 baseline | 11491 | F03331 | non-negotiable | true | 10 |
| R06648 | Model qualification — FP8 candidate | 11492 | F03332 | non-negotiable | true | 10 |
| R06649 | Model qualification — NVFP4/MXFP4 candidate | 11493 | F03333 | non-negotiable | true | 10 |
| R06650 | Model qualification — GPTQ/AWQ/SmoothQuant candidate | 11494 | F03334 | non-negotiable | true | 10 |
| R06651 | Model qualification — KV quantized candidate | 11495 | F03335 | non-negotiable | true | 10 |
| R06652 | Test axis — coding | 11501 | F03336 | non-negotiable | true | 10 |
| R06653 | Test axis — tool use | 11502 | F03337 | non-negotiable | true | 10 |
| R06654 | Test axis — schema validity | 11503 | F03338 | non-negotiable | true | 10 |
| R06655 | Test axis — agent trajectory | 11504 | F03339 | non-negotiable | true | 10 |
| R06656 | Test axis — long-context recall | 11505 | F03340 | non-negotiable | true | 10 |
| R06657 | Test axis — reasoning | 11506 | F03341 | non-negotiable | true | 10 |
| R06658 | Test axis — latency | 11507 | F03342 | non-negotiable | true | 10 |
| R06659 | Test axis — VRAM | 11508 | F03343 | non-negotiable | true | 10 |
| R06660 | Test axis — energy | 11509 | F03344 | non-negotiable | true | 10 |
| R06661 | FP4 profile decision — quality-critical = BF16/FP8 | 11515 | F03345 | non-negotiable | true | 10 |
| R06662 | FP4 profile decision — throughput = FP8 | 11516 | F03346 | non-negotiable | true | 10 |
| R06663 | FP4 profile decision — huge-model experiment = FP4 | 11517 | F03347 | non-negotiable | true | 10 |
| R06664 | FP4 profile decision — scout = INT4/GPTQ | 11518 | F03348 | non-negotiable | true | 10 |
| R06665 | AVX-512 hyper feature — policy fusion | 11528 | F03349 | non-negotiable | true | 10 |
| R06666 | AVX-512 hyper feature — branch compaction | 11529 | F03350 | non-negotiable | true | 10 |
| R06667 | AVX-512 hyper feature — memory bitmap search | 11530 | F03351 | non-negotiable | true | 10 |
| R06668 | AVX-512 hyper feature — grammar masks | 11531 | F03352 | non-negotiable | true | 10 |
| R06669 | AVX-512 hyper feature — tool permission checks | 11532 | F03353 | non-negotiable | true | 10 |
| R06670 | AVX-512 hyper feature — reward-vector filtering | 11533 | F03354 | non-negotiable | true | 10 |
| R06671 | AVX-512 hyper feature — workflow state transitions | 11534 | F03355 | non-negotiable | true | 10 |
| R06672 | "Makes adaptive profiles cheap enough to run constantly" | 11537 | F03356 | non-negotiable | false | 10 |
| R06673 | AVX-512 throughput — 512 candidate memories per bitset chunk | 11540 | F03357 | non-negotiable | false | 10 |
| R06674 | AVX-512 throughput — 8 branches per u64 vector | 11541 | F03358 | non-negotiable | false | 10 |
| R06675 | AVX-512 throughput — 64 tiny state flags per vector | 11542 | F03359 | non-negotiable | false | 10 |
| R06676 | CPU hot table — BranchTable | 11548 | F03360 | non-negotiable | true | 10 |
| R06677 | CPU hot table — MemoryMetaTable | 11549 | F03361 | non-negotiable | true | 10 |
| R06678 | CPU hot table — ToolCapabilityTable | 11550 | F03362 | non-negotiable | true | 10 |
| R06679 | CPU hot table — ModelRegistryTable | 11551 | F03363 | non-negotiable | true | 10 |
| R06680 | CPU hot table — EvalResultTable | 11552 | F03364 | non-negotiable | true | 10 |
| R06681 | CPU hot table — KVBlockTable | 11553 | F03365 | non-negotiable | true | 10 |
| R06682 | CPU operation — filter | 11559 | F03366 | non-negotiable | true | 10 |
| R06683 | CPU operation — intersect | 11560 | F03367 | non-negotiable | true | 10 |
| R06684 | CPU operation — popcount score | 11561 | F03368 | non-negotiable | true | 10 |
| R06685 | CPU operation — compress survivors | 11562 | F03369 | non-negotiable | true | 10 |
| R06686 | CPU operation — route batches | 11563 | F03370 | non-negotiable | true | 10 |
| R06687 | GDS hyper feature — direct path between storage and GPU memory bypassing CPU bounce buffers (NVIDIA cited) | 11568 | F03371 | non-negotiable | true | 10 |
| R06688 | GDS — RAPIDS KvikIO wraps for GPU-friendly I/O | 11568 | F03372 | non-negotiable | true | 10 |
| R06689 | GDS win — large model load | 11575 | F03373 | non-negotiable | true | 10 |
| R06690 | GDS win — embedding/vector shard load | 11576 | F03374 | non-negotiable | true | 10 |
| R06691 | GDS win — dataset streaming | 11577 | F03375 | non-negotiable | true | 10 |
| R06692 | GDS win — GPU-side preprocessing | 11578 | F03376 | non-negotiable | true | 10 |
| R06693 | GDS win — large binary cache movement | 11579 | F03377 | non-negotiable | true | 10 |
| R06694 | GDS NOT first priority for — small prompts | 11585 | F03378 | non-negotiable | false | 10 |
| R06695 | GDS NOT first priority for — agent traces | 11586 | F03379 | non-negotiable | false | 10 |
| R06696 | GDS NOT first priority for — JSON logs | 11587 | F03380 | non-negotiable | false | 10 |
| R06697 | GDS NOT first priority for — tool calls | 11588 | F03381 | non-negotiable | false | 10 |
| R06698 | GDS NOT first priority for — workflow metadata | 11589 | F03382 | non-negotiable | false | 10 |
| R06699 | GDS Phase 1 — ZFS + normal mmap/io_uring + RAM cache | 11596 | F03383 | non-negotiable | false | 10 |
| R06700 | GDS Phase 2 — profile model/data load bottlenecks | 11599 | F03384 | non-negotiable | false | 10 |
| R06701 | GDS Phase 3 — test GDS/KvikIO for model/cache datasets | 11602 | F03385 | non-negotiable | false | 10 |
| R06702 | "Do not build around GDS until profiling proves it matters" | 11605 | F03386 | non-negotiable | false | 10 |
| R06703 | USB4 hyper feature — ProArt dual USB4 40Gbps | 11609 | F03387 | non-negotiable | true | 10 |
| R06704 | USB4 use — fast external backup | 11611 | F03388 | non-negotiable | true | 10 |
| R06705 | USB4 use — portable dataset drives | 11612 | F03388 | non-negotiable | true | 10 |
| R06706 | USB4 use — capture devices | 11613 | F03388 | non-negotiable | true | 10 |
| R06707 | USB4 use — external display/perception rigs | 11614 | F03388 | non-negotiable | true | 10 |
| R06708 | USB4 use — possible eGPU experiments though not ideal | 11615–11616 | F03388 | non-negotiable | true | 10 |
| R06709 | USB4 NOT main model path; placement = backup/ingest/peripheral expansion | 11619–11622 | F03389 | non-negotiable | false | 10 |
| R06710 | Network — 10GbE data plane (NAS / dataset sync / model artifact transfer / cluster peer later) | 11630–11634 | F03390 | non-negotiable | true | 10 |
| R06711 | Network — 2.5GbE management plane (web dashboard / SSH / observability) | 11637–11641 | F03390 | non-negotiable | true | 10 |
| R06712 | Network — Linux NIC support needs care (AQC113C/atlantic quirks on ProArt X870E) | 11644 | F03391 | non-negotiable | false | 10 |
| R06713 | Network — I226-V ASPM/WoL issues | 11644 | F03391 | non-negotiable | false | 10 |
| R06714 | Network — ASUS officially lists Marvell 10Gb + Intel 2.5Gb | 11644 | F03392 | non-negotiable | false | 10 |
| R06715 | NIC validation — iperf3 10Gb test | 11647 | F03393 | non-negotiable | true | 10 |
| R06716 | NIC validation — ASPM stability test | 11648 | F03393 | non-negotiable | true | 10 |
| R06717 | NIC validation — suspend/resume test | 11649 | F03393 | non-negotiable | true | 10 |
| R06718 | NIC validation — driver/kernel pin if needed | 11650 | F03393 | non-negotiable | true | 10 |
| R06719 | NIC validation — management VLAN failover | 11651 | F03393 | non-negotiable | true | 10 |
| R06720 | "Networking is part of reliability" | 11654 | F03394 | non-negotiable | false | 10 |
| R06721 | VFIO hyper feature — second GPU becomes hard trust boundary | 11658 | F03395 | non-negotiable | false | 10 |
| R06722 | VFIO profile — 3090 bare-metal (lower latency, simpler local services) | 11661 | F03396 | non-negotiable | true | 10 |
| R06723 | VFIO profile — 3090 VFIO VM (stronger isolation, sandboxed agents, risky tools) | 11664 | F03396 | non-negotiable | true | 10 |
| R06724 | VFIO profile — 3090 passthrough profile (computer-use agent / web automation / untrusted model-tool experiments) | 11667–11670 | F03396 | non-negotiable | true | 10 |
| R06725 | VFIO profile-level choice — performance profile (3090 on host) | 11676 | F03397 | non-negotiable | true | 10 |
| R06726 | VFIO profile-level choice — security profile (3090 in VM) | 11679 | F03397 | non-negotiable | true | 10 |
| R06727 | VFIO profile-level choice — experiment profile (snapshot VM, run wild, discard) | 11682 | F03397 | non-negotiable | true | 10 |
| R06728 | ZFS hyper feature — autonomy infrastructure (NOT just storage) | 11688 | F03398 | non-negotiable | false | 10 |
| R06729 | ZFS commit-gate before agent writes — snapshot | 11693 | M00678 | non-negotiable | true | 10 |
| R06730 | ZFS commit-gate before agent writes — apply patch | 11694 | M00678 | non-negotiable | true | 10 |
| R06731 | ZFS commit-gate before agent writes — test | 11695 | M00678 | non-negotiable | true | 10 |
| R06732 | ZFS commit-gate before agent writes — commit or rollback | 11696 | M00678 | non-negotiable | true | 10 |
| R06733 | ZFS experiments — clone workspace | 11701 | M00678 | non-negotiable | true | 10 |
| R06734 | ZFS experiments — run branch | 11702 | M00678 | non-negotiable | true | 10 |
| R06735 | ZFS experiments — compare artifacts | 11703 | M00678 | non-negotiable | true | 10 |
| R06736 | ZFS experiments — promote or destroy | 11704 | M00678 | non-negotiable | true | 10 |
| R06737 | "This gives you safe aggressive agents" | 11708 | E0385 | non-negotiable | false | 10 |
| R06738 | NPU absence — Ryzen 9000 desktop CPUs generally do not include Ryzen AI NPU | 11712 | F03399 | non-negotiable | false | 10 |
| R06739 | NPU absence — 9900X is not your NPU platform | 11712 | F03399 | non-negotiable | false | 10 |
| R06740 | NPU equivalent — AVX-512 CPU for deterministic control | 11715 | F03399 | non-negotiable | true | 10 |
| R06741 | NPU equivalent — 3090 for cheap SLM/perception | 11716 | F03399 | non-negotiable | true | 10 |
| R06742 | NPU equivalent — Blackwell for oracle | 11717 | F03399 | non-negotiable | true | 10 |
| R06743 | "Do not chase NPU unless you add a separate Ryzen AI box later" | 11720 | F03399 | non-negotiable | false | 10 |
| R06744 | Hyper Feature 10 — Modes As Hardware Configurations; profiles control hardware NOT just prompts | 11722–11724 | F03400 | non-negotiable | false | 10 |
| R06745 | Profile YAML — max_oracle (blackwell.mig=off + largest_oracle + fp8 + 3090 scout + AVX high + cloud false) | 11727–11737 | E0387 | non-negotiable | true | 10 |
| R06746 | Profile YAML — secure_agent_lab (blackwell.mig=on + slices=[oracle, verifier] + rtx3090.vfio=true + sandbox + tools.network=gated + zfs.snapshot_before_write=true) | 11739–11750 | E0387 | non-negotiable | true | 10 |
| R06747 | Profile YAML — fast_code (blackwell.model=code_oracle + 3090 code_scout + CPU route=aggressive + tests=targeted) | 11751–11759 | E0387 | non-negotiable | true | 10 |
| R06748 | Profile YAML — research_deep (blackwell.oracle=long_context + 3090 rerank + memory.graph_expansion=high + eval.citation_verification=true) | 11761–11770 | E0387 | non-negotiable | true | 10 |
| R06749 | "Profiles drive the whole machine" | 11772 | F03400 | non-negotiable | false | 10 |
| R06750 | Big Hardware Law — "A feature is only powerful if the runtime can choose when to use it" | 11776 | F03400 | non-negotiable | false | 10 |
| R06751 | Programmable knob — MIG | 11780 | F03400 | non-negotiable | true | 10 |
| R06752 | Programmable knob — FP4 | 11780 | F03400 | non-negotiable | true | 10 |
| R06753 | Programmable knob — VFIO | 11780 | F03400 | non-negotiable | true | 10 |
| R06754 | Programmable knob — AVX-512 | 11780 | F03400 | non-negotiable | true | 10 |
| R06755 | Programmable knob — ZFS | 11780 | F03400 | non-negotiable | true | 10 |
| R06756 | Programmable knob — GDS | 11780 | F03400 | non-negotiable | true | 10 |
| R06757 | Programmable knob — 10GbE | 11780 | F03400 | non-negotiable | true | 10 |
| R06758 | Programmable knob — USB4 | 11780 | F03400 | non-negotiable | true | 10 |
| R06759 | Programmable knob — quantization | 11780 | F03400 | non-negotiable | true | 10 |
| R06760 | Programmable knob — cloud fallback | 11780 | F03400 | non-negotiable | true | 10 |
| R06761 | None of these knobs should be hardcoded | 11780 | F03400 | non-negotiable | false | 10 |
| R06762 | They should be programmable knobs in your intelligence OS | 11782 | F03400 | non-negotiable | false | 10 |
| R06763 | "That is how you avoid locking yourself into one profile while still exploiting every breakthrough" | 11784 | F03400 | non-negotiable | false | 10 |
| R06764 | M040 integrates with M025 cognitive compiler — profile YAML compiles to runtime DAG with hardware knobs | 11722–11770 + cross-ref M025 | F03400 | non-negotiable | false | 10 |
| R06765 | M040 integrates with M026 SLM swarm + RLM engine — 3090 scout role + MIG slices host SLM swarm | cross-ref M026 + 11005 + 11444 | M00664 + F03396 | non-negotiable | false | 10 |
| R06766 | M040 integrates with M027 Value Plane — reward-vector filtering is an AVX-512 hyper feature | 11533 + cross-ref M027 | F03354 | non-negotiable | false | 10 |
| R06767 | M040 integrates with M028 Memory OS — MemoryMetaTable + KVBlockTable + memory bitmap search are hot tables | 11530 + 11549 + 11553 + cross-ref M028 | M00670 + M00674 + F03351 | non-negotiable | false | 10 |
| R06768 | M040 integrates with M029 Computer-Use Plane — 3090 VFIO passthrough for computer-use agent + web automation | 11668–11669 + cross-ref M029 | F03396 | non-negotiable | false | 10 |
| R06769 | M040 integrates with M030 World Model Plane — ZFS snapshot/commit/rollback is the World-Model rollback channel | 11690–11708 + cross-ref M030 | M00678 | non-negotiable | false | 10 |
| R06770 | M040 integrates with M031 Symbolic Planning Plane — tool permission checks + grammar masks are AVX-512 hyper features | 11531 + 11532 + cross-ref M031 | F03352 + F03353 | non-negotiable | false | 10 |
| R06771 | M040 integrates with M032 Cloud Expert Plane — cloud fallback is one of 10 programmable knobs | 11780 + cross-ref M032 | R06760 | non-negotiable | false | 10 |
| R06772 | M040 integrates with M033 Compatibility Gateway + M034 Anthropic-first Gateway — Claude Code / OpenCode-Cline get dedicated MIG slices under Multi-tenant Mode | 11453–11454 + cross-ref M033 + M034 | M00666 | non-negotiable | false | 10 |
| R06773 | M040 integrates with M035 Frontier — programmable knobs operationalize Frontier 9-layer Runtime Shape | cross-ref M035 + 11780 | E0387 | non-negotiable | false | 10 |
| R06774 | M040 integrates with M036 MAP-then-act — profile YAML is the MAP-before-act configuration substrate | cross-ref M036 + 11722–11770 | F03400 | non-negotiable | false | 10 |
| R06775 | M040 integrates with M037 evidence-driven autonomy — ModelRegistryTable + EvalResultTable are 2 of the 6 AVX-512 hot tables | 11551 + 11552 + cross-ref M037 | M00672 + M00673 | non-negotiable | false | 10 |
| R06776 | M040 integrates with M038 Hardware-aware AIDLC — profile YAML extends M038's phase-to-hardware mapping with runtime-toggleable hyper features | cross-ref M038 + 11722–11770 | E0387 | non-negotiable | false | 10 |
| R06777 | M040 integrates with M039 AVX-512 Cortex Hot Path — AVX-512 hyper feature 3 catalogs the same 6 hot tables + 5 operations | 11548–11563 + cross-ref M039 | M00669-M00674 + M00675 | non-negotiable | false | 10 |
| R06778 | Project boundary — M040 covers sovereign-os hyper features; selfdef MS010 [requires_hardware] gates check MIG/FP4/VFIO availability | architecture + MS010 | E0387 | non-negotiable | false | 10 |
| R06779 | Project boundary — selfdef MS007 typed-mirror crates may carry profile-YAML schema for cross-repo audit | MS007 + SDD-038 | E0387 | non-negotiable | false | 10 |
| R06780 | Project boundary — selfdef MS017 agent-guard may enforce Hyper Feature 7 VFIO trust boundary (3090 in VM for sandboxed agents) | MS017 + 11664 | F03396 | non-negotiable | false | 10 |
| R06781 | MIG enablement workflow — Hyper Feature 1 toggle on/off via profile (NOT default-on; opt-in per workload) | 11458 + 11460 | R06640 | non-negotiable | false | 10 |
| R06782 | FP4 enablement workflow — Hyper Feature 2 model-lab qualification gate (NOT blind trust) | 11486–11496 | E0380 | non-negotiable | false | 10 |
| R06783 | AVX-512 enablement workflow — Hyper Feature 3 hot-table maintenance via runtime feeders | 11545–11546 | E0381 | non-negotiable | false | 10 |
| R06784 | GDS enablement workflow — Hyper Feature 4 3-phase adoption (Phase 1 conservative / Phase 2 profile / Phase 3 test) | 11593–11603 | M00676 | non-negotiable | false | 10 |
| R06785 | USB4 + Network enablement workflow — Hyper Feature 5+6 setup includes NIC validation (5-step) | 11647–11651 | F03393 | non-negotiable | false | 10 |
| R06786 | VFIO enablement workflow — Hyper Feature 7 profile-level choice (performance/security/experiment) | 11675–11684 | F03397 | non-negotiable | false | 10 |
| R06787 | ZFS enablement workflow — Hyper Feature 8 mandatory for autonomous profiles (snapshot_before_write=true) | 11748 | M00678 | non-negotiable | false | 10 |
| R06788 | NPU enablement workflow — Hyper Feature 9 N/A (deliberate non-feature; substitute trio fills role) | 11713–11720 | M00679 | non-negotiable | false | 10 |
| R06789 | Modes enablement workflow — Hyper Feature 10 profile YAML is the operator-facing surface | 11725 + 11722 | F03400 | non-negotiable | false | 10 |
| R06790 | Big Hardware Law operationalization — runtime profile selector reads profile YAML + applies all 10 hyper-feature knobs in one transaction | 11776 + 11780 | F03400 | non-negotiable | false | 10 |
| R06791 | Layer-B metric (implied) — `sovereign_os_hyper_feature_state{feature, value}` (MIG on/off; FP4 in use; VFIO mode; ZFS snapshot count; etc.) | architecture + 11780 | E0387 | non-negotiable | true | 10 |
| R06792 | Layer-B metric (implied) — `sovereign_os_profile_in_use{name}` (max_oracle / secure_agent_lab / fast_code / research_deep / etc.) | architecture + 11727–11770 | F03400 | non-negotiable | true | 10 |
| R06793 | Layer-B metric (implied) — `sovereign_os_mig_slice_count_total{role}` (oracle/verifier/embedding/service) | architecture + 11443–11447 | M00664 | non-negotiable | true | 10 |
| R06794 | Layer-B metric (implied) — `sovereign_os_zfs_commit_gate_outcomes_total{outcome}` (commit/rollback) | architecture + 11696 | M00678 | non-negotiable | true | 10 |
| R06795 | Layer-B metric (implied) — `sovereign_os_vfio_3090_passthrough_active` (gauge) | architecture + 11667 | F03396 | non-negotiable | true | 10 |
| R06796 | Layer-B metric (implied) — `sovereign_os_avx512_hot_table_rows{table}` (BranchTable / MemoryMetaTable / etc.) | architecture + 11548–11553 | M00669-M00674 | non-negotiable | true | 10 |
| R06797 | Doctrine — every hyper feature is a SOFTWARE-EXPOSED HARDWARE AFFORDANCE; runtime decides when to use | 11429 + 11776 | F03317 + F03400 | non-negotiable | false | 10 |
| R06798 | Doctrine — profile YAML is the canonical operator-facing surface (NOT prompt-only configuration) | 11725 | F03400 | non-negotiable | false | 10 |
| R06799 | Doctrine — hyper features are NOT hardcoded; runtime can choose when to use each | 11780 | R06761 | non-negotiable | false | 10 |
| R06800 | Composite — M040 Hyper Features (10 catalog) covers MIG / FP4 / AVX-512 / GDS / USB4 / 10GbE-2.5GbE / VFIO / ZFS / NPU-absence / Modes-as-hardware-configurations; Big Hardware Law "feature is only powerful if runtime can choose when to use it"; profile YAML drives all 10 knobs in one transaction; "programmable knobs in your intelligence OS"; integrates with M025-M039 + selfdef MS010 [requires_hardware] gates + MS017 agent-guard VFIO trust boundary + MS007 typed-mirror cross-repo schema | 11410–11784 + cross-refs | E0378 + E0379 + E0380 + E0381 + E0382 + E0383 + E0384 + E0385 + E0386 + E0387 | non-negotiable | false | 10 |

## Cross-references

- Adjacent dump-range milestones: M039 AVX-512 cortex hot path (11169–11410) / M041 (next; dump 11790–…)
- Plane integration: M025-M039 all integrate with M040 (hyper features expose hardware affordances; profile YAML is the operator-facing surface; programmable knobs in intelligence OS)
- 10 hyper features catalog: MIG (1) / FP4 (2) / AVX-512 (3) / GDS (4) / USB4 (5) / 10GbE+2.5GbE (6) / VFIO (7) / ZFS (8) / NPU-absence-is-non-issue (9) / Modes-as-hardware-configurations (10)
- 4 example profile YAMLs: max_oracle / secure_agent_lab / fast_code / research_deep
- Selfdef integration: MS010 [requires_hardware] gates / MS007 typed-mirror crates carry profile-YAML schema / MS017 agent-guard enforces VFIO trust boundary
- Operator references: NVIDIA RTX PRO 6000 docs + datasheet (MIG + FP4 + PCIe Gen5 + 96GB GDDR7) + Linux io_uring docs + AMD Ryzen 9000 NPU absence + NVIDIA GDS docs + RAPIDS KvikIO + ASUS ProArt X870E (USB4 + 10GbE + 2.5GbE)
