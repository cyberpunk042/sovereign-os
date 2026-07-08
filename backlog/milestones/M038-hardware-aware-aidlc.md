# M038 — Hardware-aware AIDLC

> Parent: `backlog/milestones/INDEX.md` row M038 (dump 10964–11169).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 10964–11169.
> All entries below extract verbatim. No invention.

## Epics (E0358–E0367)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0358 | Operator directive — "do not forget the hardware and the tech. continue. do resaerchs online too" (verbatim 10964) | 10964 |
| E0359 | Hardware Reality — station is NOT a generic AI server; specific topology = Ryzen 9 9900X (12C/24T Zen 5; AVX-512 control fabric; strong single-thread; enough cores for schedulers/parsers/sandboxes/routing) + RTX PRO 6000 Blackwell (96GB GDDR7; PCIe Gen5; FP4-capable 5th-gen Tensor Cores; oracle/large-model/verifier/long-context card) + RTX 4090 (24GB GDDR6X; PCIe Gen4; scout/sandbox/SLM/perception/embedding/draft card) + ProArt X870E-Creator (dual GPU x8/x8; M.2_2 lane sharing caveats) | 10987–11010 |
| E0360 | Clean hardware law — "Do not pretend the two GPUs are one memory pool. Use them as separate experts." + CUDA Linux doesn't support IOMMU-enabled bare-metal PCIe peer-to-peer memory copy (IOMMU supported for VM passthrough with VFIO); reinforces Blackwell=oracle + 4090=scout/sandbox + CPU=deterministic router | 11014–11027 |
| E0361 | Zen 5 AVX-512 is the control plane — `-march=znver5` + AVX-512 subsets (VNNI / BF16 / VBMI / BITALG / VPOPCNTDQ / VP2INTERSECT); useful instructions are not only math — k-masks (branch validity, permission routing, grammar states) / VPTERNLOG (fused policy logic) / VPCOMPRESS-VPEXPAND (pack alive branches into dense queues) / VPOPCNTDQ (memory sketch scoring, bitset overlap) / VP2INTERSECT (candidate/memory/tool-set intersection) / VBMI-VBMI2 (byte/token-class manipulation) / VNNI-BF16 (small CPU-side scoring or classifier kernels); "GPU runs probability. CPU runs law." | 11029–11061 |
| E0362 | Blackwell FP4/NVFP4 strategy — software stack is moving target; NVIDIA documents FP4/NVFP4 in TensorRT/TensorRT-LLM; vLLM/llm-compressor actively adding NVFP4/MXFP4 support; model lab tier-system needed | 11063–11084 |
| E0363 | Model lab 5-tier quantization scheme — Tier 1 BF16/FP16 quality baseline / Tier 2 FP8 practical Blackwell sweet spot / Tier 3 GPTQ-AWQ-SmoothQuant compatibility + VRAM savings / Tier 4 NVFP4-MXFP4 frontier Blackwell path benchmark-before-trusting / Tier 5 KV-cache quantization long-context optimization | 11068–11084 |
| E0364 | Don't blindly quantize the oracle — qualify models per role (oracle: quality first / quantize carefully / scout: speed-cost first / aggressive quantization acceptable / router-classifier: tiny SLM or CPU model / optimize hard / perception: fit-speed matters / tolerate specialization) | 11086–11100 |
| E0365 | Storage And PCIe Discipline — lane-sharing means storage plan serves AI architecture not vanity sequential numbers; CPU Gen5 NVMe (hot models / active workspace / high-value cache) / Chipset NVMe (datasets / replay / eval artifacts / lower-priority cache) / ZFS (snapshots / rollback / trace ledger / workspace safety) / RAM (ARC / memory graph / hot indexes / context arenas); "Do not sacrifice second-GPU width just to chase a second Gen5 M.2 if the 4090's role matters" | 11102–11122 |
| E0366 | How Hardware Feeds Methodology — Spec/TDD/AIDLC hardware-aware per phase (MAP: CPU AVX-512 scans / 4090 summarizes-classifies / Blackwell sees distilled hard context; SPEC: Blackwell writes-validates spec / CPU converts acceptance criteria into test-eval structures; TDD: sandboxes run tests / CPU tracks outcome bits / 4090 suggests cheap fixes / Blackwell reviews high-risk diffs; EVAL: CPU computes trajectory metrics / 4090 tags failures / Blackwell synthesizes lessons; COMMIT: ZFS snapshot + replay log + human/oracle gate) | 11124–11151 |
| E0367 | Practical Rule + closing — "Use GPU for dense cognition. Use CPU AVX-512 for branch law. Use RAM for active world state. Use ZFS for memory, replay, rollback. Use PCIe only for compact symbols, not giant tensors."; "your 'super-model' is not one model. It is the whole machine operating as a routed, evaluated, memory-backed, hardware-aware intelligence system" | 11155–11167 |

## Modules (M00629–M00645)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00629 | Ryzen 9 9900X — 12C/24T Zen 5; AVX-512 control fabric | 10991–10994 | E0359 |
| M00630 | RTX PRO 6000 Blackwell — 96GB GDDR7; PCIe Gen5; FP4-capable 5th-gen Tensor Cores; 1.8TB/s bandwidth | 10996–11000 + 11012 | E0359 |
| M00631 | RTX 4090 — 24GB GDDR6X; PCIe Gen4 | 11002–11005 | E0359 |
| M00632 | ProArt X870E-Creator — supports first two PCIe 5.0 x16 slots as x16 or x8/x8 with lane-sharing caveats around M.2 usage | 11007–11010 + 11012 | E0359 |
| M00633 | Hardware Law — "Do not pretend the two GPUs are one memory pool. Use them as separate experts." | 11016–11018 | E0360 |
| M00634 | CUDA Linux IOMMU note — does NOT support IOMMU-enabled bare-metal PCIe peer-to-peer memory copy; IOMMU is supported for VM passthrough with VFIO | 11021 | E0360 |
| M00635 | Compiler target — `-march=znver5` per AMD Zen 5/EPYC tuning materials | 11031 | E0361 |
| M00636 | AVX-512 instruction — k-masks (branch validity, permission routing, grammar states) | 11036–11037 | E0361 |
| M00637 | AVX-512 instruction — VPTERNLOG (fused policy logic) | 11039–11040 | E0361 |
| M00638 | AVX-512 instruction — VPCOMPRESS/VPEXPAND (pack alive branches into dense queues) | 11042–11043 | E0361 |
| M00639 | AVX-512 instruction — VPOPCNTDQ (memory sketch scoring, bitset overlap) | 11045–11046 | E0361 |
| M00640 | AVX-512 instruction — VP2INTERSECT (candidate/memory/tool-set intersection) | 11048–11049 | E0361 |
| M00641 | AVX-512 instruction — VBMI/VBMI2 (byte/token-class manipulation) | 11051–11052 | E0361 |
| M00642 | AVX-512 instruction — VNNI/BF16 (small CPU-side scoring or classifier kernels) | 11054–11055 | E0361 |
| M00643 | Quantization tier catalog — 5 tiers (BF16/FP16 / FP8 / GPTQ-AWQ-SmoothQuant / NVFP4-MXFP4 / KV-cache) | 11069–11084 | E0363 |
| M00644 | Storage tier catalog — CPU Gen5 NVMe / Chipset NVMe / ZFS / RAM | 11109–11120 | E0365 |
| M00645 | Hardware-aware AIDLC phase catalog — MAP / SPEC / TDD / EVAL / COMMIT mapped to per-component executor | 11128–11151 | E0366 |

## Features (F03146–F03230)

| F ID | Phrase | Dump line | Parent | Category | Opt-in |
|---|---|---|---|---|---|
| F03146 | Operator directive — do not forget the hardware and the tech; continue + research online | 10964 | E0358 | composite | false |
| F03147 | "The breakthrough only matters if the metal is used correctly" | 10983 | E0359 | composite | false |
| F03148 | Station has a very specific topology (not generic AI server) | 10985–10987 | E0359 | composite | false |
| F03149 | Ryzen 9 9900X — 12C/24T Zen 5 | 10991 | M00629 | composite | true |
| F03150 | Ryzen 9 9900X — AVX-512 control fabric | 10992 | M00629 | composite | false |
| F03151 | Ryzen 9 9900X — strong single-thread latency | 10993 | M00629 | composite | false |
| F03152 | Ryzen 9 9900X — enough cores for schedulers / parsers / sandboxes / routing | 10994 | M00629 | composite | false |
| F03153 | RTX PRO 6000 Blackwell — 96GB GDDR7 | 10997 | M00630 | composite | true |
| F03154 | RTX PRO 6000 Blackwell — PCIe Gen5 | 10998 | M00630 | composite | true |
| F03155 | RTX PRO 6000 Blackwell — FP4-capable 5th-gen Tensor Cores | 10999 | M00630 | composite | true |
| F03156 | RTX PRO 6000 Blackwell — oracle / large-model / verifier / long-context card | 11000 | M00630 | composite | false |
| F03157 | RTX PRO 6000 Blackwell — 1.8TB/s bandwidth (NVIDIA datasheet) | 11012 | M00630 | composite | false |
| F03158 | RTX 4090 — 24GB GDDR6X | 11003 | M00631 | composite | true |
| F03159 | RTX 4090 — PCIe Gen4 | 11004 | M00631 | composite | true |
| F03160 | RTX 4090 — scout / sandbox / SLM / perception / embedding / draft card | 11005 | M00631 | composite | false |
| F03161 | ProArt X870E-Creator — dual GPU possible at x8/x8 | 11008 | M00632 | composite | false |
| F03162 | ProArt X870E-Creator — M.2_2 lane sharing can drop second slot behavior | 11009 | M00632 | composite | false |
| F03163 | ProArt X870E-Creator — supports first two PCIe 5.0 x16 slots as x16 or x8/x8 (ASUS specs) | 11012 | M00632 | composite | true |
| F03164 | Hardware Law — "Do not pretend the two GPUs are one memory pool" | 11017 | M00633 | composite | false |
| F03165 | Hardware Law — "Use them as separate experts" | 11018 | M00633 | composite | false |
| F03166 | CUDA Linux — does NOT support IOMMU-enabled bare-metal PCIe peer-to-peer memory copy | 11021 | M00634 | composite | false |
| F03167 | CUDA Linux — IOMMU IS supported for VM passthrough with VFIO | 11021 | M00634 | composite | true |
| F03168 | Design reinforced — Blackwell = oracle | 11024 | E0360 | composite | false |
| F03169 | Design reinforced — 4090 = scout/sandbox | 11025 | E0360 | composite | false |
| F03170 | Design reinforced — CPU = deterministic router | 11026 | E0360 | composite | false |
| F03171 | AMD Zen 5 / EPYC supports enhanced AVX-512 usage + `-march=znver5` | 11031 | M00635 | composite | true |
| F03172 | AVX-512 subset — VNNI | 11031 | M00635 | composite | true |
| F03173 | AVX-512 subset — BF16 | 11031 | M00635 | composite | true |
| F03174 | AVX-512 subset — VBMI | 11031 | M00635 | composite | true |
| F03175 | AVX-512 subset — BITALG | 11031 | M00635 | composite | true |
| F03176 | AVX-512 subset — VPOPCNTDQ | 11031 | M00635 | composite | true |
| F03177 | AVX-512 subset — VP2INTERSECT | 11031 | M00635 | composite | true |
| F03178 | Useful AVX-512 instructions are not only math | 11033 | E0361 | composite | false |
| F03179 | AVX-512 use — k-masks for branch validity | 11036–11037 | M00636 | composite | true |
| F03180 | AVX-512 use — k-masks for permission routing | 11037 | M00636 | composite | true |
| F03181 | AVX-512 use — k-masks for grammar states | 11037 | M00636 | composite | true |
| F03182 | AVX-512 use — VPTERNLOG for fused policy logic | 11039–11040 | M00637 | composite | true |
| F03183 | AVX-512 use — VPCOMPRESS/VPEXPAND for packing alive branches into dense queues | 11042–11043 | M00638 | composite | true |
| F03184 | AVX-512 use — VPOPCNTDQ for memory sketch scoring | 11045–11046 | M00639 | composite | true |
| F03185 | AVX-512 use — VPOPCNTDQ for bitset overlap | 11046 | M00639 | composite | true |
| F03186 | AVX-512 use — VP2INTERSECT for candidate/memory/tool-set intersection | 11048–11049 | M00640 | composite | true |
| F03187 | AVX-512 use — VBMI/VBMI2 for byte/token-class manipulation | 11051–11052 | M00641 | composite | true |
| F03188 | AVX-512 use — VNNI/BF16 for small CPU-side scoring or classifier kernels | 11054–11055 | M00642 | composite | true |
| F03189 | "This is the deterministic cortex" | 11058 | E0361 | composite | false |
| F03190 | "The GPU runs probability. The CPU runs law." | 11060–11061 | E0361 | composite | false |
| F03191 | Blackwell FP4 strategically huge | 11064 | E0362 | composite | false |
| F03192 | Software stack still moving target | 11064 | E0362 | composite | false |
| F03193 | NVIDIA documents FP4/NVFP4 in TensorRT/TensorRT-LLM contexts | 11065 | E0362 | composite | true |
| F03194 | vLLM/llm-compressor docs actively adding NVFP4/MXFP4 support | 11065 | E0362 | composite | true |
| F03195 | Quantization tier 1 — BF16/FP16 quality baseline | 11070–11071 | M00643 | composite | true |
| F03196 | Quantization tier 2 — FP8 practical Blackwell sweet spot | 11073–11074 | M00643 | composite | true |
| F03197 | Quantization tier 3 — GPTQ/AWQ/SmoothQuant compatibility + VRAM savings | 11076–11077 | M00643 | composite | true |
| F03198 | Quantization tier 4 — NVFP4/MXFP4 frontier Blackwell path benchmark-before-trusting | 11079–11080 | M00643 | composite | true |
| F03199 | Quantization tier 5 — KV-cache quantization long-context optimization | 11082–11083 | M00643 | composite | true |
| F03200 | "Do not blindly quantize the oracle" | 11086 | E0364 | composite | false |
| F03201 | Qualify per role — oracle quality first, quantize carefully | 11089–11090 | E0364 | composite | true |
| F03202 | Qualify per role — scout speed/cost first, aggressive quantization acceptable | 11092–11093 | E0364 | composite | true |
| F03203 | Qualify per role — router/classifier tiny SLM or CPU model, optimize hard | 11095–11096 | E0364 | composite | true |
| F03204 | Qualify per role — perception fit/speed matters, tolerate specialization | 11098–11099 | E0364 | composite | true |
| F03205 | Storage plan serves AI architecture, not vanity sequential numbers | 11104 | E0365 | composite | false |
| F03206 | Storage tier — CPU Gen5 NVMe (hot models / active workspace / high-value cache) | 11109–11110 | M00644 | composite | true |
| F03207 | Storage tier — Chipset NVMe (datasets / replay / eval artifacts / lower-priority cache) | 11112–11113 | M00644 | composite | true |
| F03208 | Storage tier — ZFS (snapshots / rollback / trace ledger / workspace safety) | 11115–11116 | M00644 | composite | true |
| F03209 | Storage tier — RAM (ARC / memory graph / hot indexes / context arenas) | 11118–11119 | M00644 | composite | true |
| F03210 | "Do not sacrifice second-GPU width just to chase a second Gen5 M.2 if the 4090's role matters" | 11122 | E0365 | composite | false |
| F03211 | Spec/TDD/AIDLC becomes hardware-aware | 11126 | E0366 | composite | false |
| F03212 | MAP phase — CPU scans repo/memory/indexes with AVX-512 | 11130 | M00645 | composite | true |
| F03213 | MAP phase — 4090 summarizes and classifies | 11131 | M00645 | composite | true |
| F03214 | MAP phase — Blackwell only sees distilled hard context | 11132 | M00645 | composite | true |
| F03215 | SPEC phase — Blackwell writes/validates high-level spec | 11135 | M00645 | composite | true |
| F03216 | SPEC phase — CPU converts acceptance criteria into test/eval structures | 11136 | M00645 | composite | true |
| F03217 | TDD phase — sandboxes run tests | 11139 | M00645 | composite | true |
| F03218 | TDD phase — CPU tracks outcome bits | 11140 | M00645 | composite | true |
| F03219 | TDD phase — 4090 suggests cheap fixes | 11141 | M00645 | composite | true |
| F03220 | TDD phase — Blackwell reviews high-risk diffs | 11142 | M00645 | composite | true |
| F03221 | EVAL phase — CPU computes trajectory metrics | 11145 | M00645 | composite | true |
| F03222 | EVAL phase — 4090 tags failures | 11146 | M00645 | composite | true |
| F03223 | EVAL phase — Blackwell synthesizes lessons | 11147 | M00645 | composite | true |
| F03224 | COMMIT phase — ZFS snapshot + replay log + human/oracle gate | 11150 | M00645 | composite | true |
| F03225 | "Every phase has a best hardware executor" | 11153 | E0366 | composite | false |
| F03226 | Practical Rule — Use GPU for dense cognition | 11158 | E0367 | composite | false |
| F03227 | Practical Rule — Use CPU AVX-512 for branch law | 11159 | E0367 | composite | false |
| F03228 | Practical Rule — Use RAM for active world state | 11160 | E0367 | composite | false |
| F03229 | Practical Rule — Use ZFS for memory, replay, rollback | 11161 | E0367 | composite | false |
| F03230 | Composite — "your 'super-model' is not one model. It is the whole machine operating as a routed, evaluated, memory-backed, hardware-aware intelligence system" + "Use PCIe only for compact symbols, not giant tensors" | 11162 + 11167 | E0367 | composite | false |

## Requirements (R06291–R06460)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R06291 | Operator directive — do not forget hardware + tech; continue + research online | 10964 | F03146 | non-negotiable | false | 10 |
| R06292 | "The breakthrough only matters if the metal is used correctly" | 10983 | F03147 | non-negotiable | false | 10 |
| R06293 | Station is not a generic AI server | 10985 | F03148 | non-negotiable | false | 10 |
| R06294 | Station has a very specific topology | 10987 | F03148 | non-negotiable | false | 10 |
| R06295 | Ryzen 9 9900X — 12 cores / 24 threads | 10991 | F03149 | non-negotiable | true | 10 |
| R06296 | Ryzen 9 9900X — Zen 5 microarchitecture | 10991 | F03149 | non-negotiable | true | 10 |
| R06297 | Ryzen 9 9900X — AVX-512 control fabric | 10992 | F03150 | non-negotiable | false | 10 |
| R06298 | Ryzen 9 9900X — strong single-thread latency | 10993 | F03151 | non-negotiable | false | 10 |
| R06299 | Ryzen 9 9900X — enough cores for schedulers / parsers / sandboxes / routing | 10994 | F03152 | non-negotiable | false | 10 |
| R06300 | RTX PRO 6000 Blackwell — 96GB GDDR7 | 10997 | F03153 | non-negotiable | true | 10 |
| R06301 | RTX PRO 6000 Blackwell — PCIe Gen5 | 10998 | F03154 | non-negotiable | true | 10 |
| R06302 | RTX PRO 6000 Blackwell — FP4-capable 5th-gen Tensor Cores | 10999 | F03155 | non-negotiable | true | 10 |
| R06303 | RTX PRO 6000 Blackwell — oracle/large-model/verifier/long-context card | 11000 | F03156 | non-negotiable | false | 10 |
| R06304 | RTX PRO 6000 Blackwell — 1.8TB/s bandwidth (NVIDIA datasheet) | 11012 | F03157 | non-negotiable | false | 10 |
| R06305 | RTX 4090 — 24GB GDDR6X | 11003 | F03158 | non-negotiable | true | 10 |
| R06306 | RTX 4090 — PCIe Gen4 | 11004 | F03159 | non-negotiable | true | 10 |
| R06307 | RTX 4090 — scout/sandbox/SLM/perception/embedding/draft card | 11005 | F03160 | non-negotiable | false | 10 |
| R06308 | ProArt X870E-Creator — dual GPU possible at x8/x8 | 11008 | F03161 | non-negotiable | false | 10 |
| R06309 | ProArt X870E-Creator — M.2_2 lane sharing can drop second slot behavior | 11009 | F03162 | non-negotiable | false | 10 |
| R06310 | ProArt X870E-Creator — supports first two PCIe 5.0 x16 slots as x16 or x8/x8 per ASUS specs | 11012 | F03163 | non-negotiable | true | 10 |
| R06311 | Hardware Law — "Do not pretend the two GPUs are one memory pool" | 11017 | F03164 | non-negotiable | false | 10 |
| R06312 | Hardware Law — "Use them as separate experts" | 11018 | F03165 | non-negotiable | false | 10 |
| R06313 | CUDA Linux note — does NOT support IOMMU-enabled bare-metal PCIe peer-to-peer memory copy | 11021 | F03166 | non-negotiable | false | 10 |
| R06314 | CUDA Linux note — IOMMU IS supported for VM passthrough with VFIO | 11021 | F03167 | non-negotiable | true | 10 |
| R06315 | Design — Blackwell = oracle | 11024 | F03168 | non-negotiable | false | 10 |
| R06316 | Design — 4090 = scout/sandbox | 11025 | F03169 | non-negotiable | false | 10 |
| R06317 | Design — CPU = deterministic router | 11026 | F03170 | non-negotiable | false | 10 |
| R06318 | AMD Zen 5 / EPYC supports enhanced AVX-512 usage | 11031 | F03171 | non-negotiable | false | 10 |
| R06319 | Compiler target — `-march=znver5` per AMD tuning guide | 11031 | F03171 | non-negotiable | true | 10 |
| R06320 | AVX-512 subset — VNNI | 11031 | F03172 | non-negotiable | true | 10 |
| R06321 | AVX-512 subset — BF16 | 11031 | F03173 | non-negotiable | true | 10 |
| R06322 | AVX-512 subset — VBMI | 11031 | F03174 | non-negotiable | true | 10 |
| R06323 | AVX-512 subset — BITALG | 11031 | F03175 | non-negotiable | true | 10 |
| R06324 | AVX-512 subset — VPOPCNTDQ | 11031 | F03176 | non-negotiable | true | 10 |
| R06325 | AVX-512 subset — VP2INTERSECT | 11031 | F03177 | non-negotiable | true | 10 |
| R06326 | Useful AVX-512 instructions are not only math | 11033 | F03178 | non-negotiable | false | 10 |
| R06327 | AVX-512 use — k-masks for branch validity | 11036 | F03179 | non-negotiable | true | 10 |
| R06328 | AVX-512 use — k-masks for permission routing | 11037 | F03180 | non-negotiable | true | 10 |
| R06329 | AVX-512 use — k-masks for grammar states | 11037 | F03181 | non-negotiable | true | 10 |
| R06330 | AVX-512 use — VPTERNLOG for fused policy logic | 11040 | F03182 | non-negotiable | true | 10 |
| R06331 | AVX-512 use — VPCOMPRESS/VPEXPAND for packing alive branches into dense queues | 11043 | F03183 | non-negotiable | true | 10 |
| R06332 | AVX-512 use — VPOPCNTDQ for memory sketch scoring | 11046 | F03184 | non-negotiable | true | 10 |
| R06333 | AVX-512 use — VPOPCNTDQ for bitset overlap | 11046 | F03185 | non-negotiable | true | 10 |
| R06334 | AVX-512 use — VP2INTERSECT for candidate/memory/tool-set intersection | 11049 | F03186 | non-negotiable | true | 10 |
| R06335 | AVX-512 use — VBMI/VBMI2 for byte/token-class manipulation | 11052 | F03187 | non-negotiable | true | 10 |
| R06336 | AVX-512 use — VNNI/BF16 for small CPU-side scoring or classifier kernels | 11055 | F03188 | non-negotiable | true | 10 |
| R06337 | "This is the deterministic cortex" | 11058 | F03189 | non-negotiable | false | 10 |
| R06338 | "The GPU runs probability" | 11060 | F03190 | non-negotiable | false | 10 |
| R06339 | "The CPU runs law" | 11061 | F03190 | non-negotiable | false | 10 |
| R06340 | Blackwell FP4 support is strategically huge | 11064 | F03191 | non-negotiable | false | 10 |
| R06341 | Software stack is still a moving target | 11064 | F03192 | non-negotiable | false | 10 |
| R06342 | NVIDIA documents FP4/NVFP4 in TensorRT/TensorRT-LLM contexts | 11065 | F03193 | non-negotiable | true | 10 |
| R06343 | vLLM/llm-compressor docs are actively adding NVFP4/MXFP4 support | 11065 | F03194 | non-negotiable | true | 10 |
| R06344 | Quantization tier 1 — BF16/FP16, quality baseline | 11070–11071 | F03195 | non-negotiable | true | 10 |
| R06345 | Quantization tier 2 — FP8, practical Blackwell sweet spot | 11073–11074 | F03196 | non-negotiable | true | 10 |
| R06346 | Quantization tier 3 — GPTQ/AWQ/SmoothQuant, compatibility and VRAM savings | 11076–11077 | F03197 | non-negotiable | true | 10 |
| R06347 | Quantization tier 4 — NVFP4/MXFP4, frontier Blackwell path, benchmark before trusting | 11079–11080 | F03198 | non-negotiable | true | 10 |
| R06348 | Quantization tier 5 — KV-cache quantization, long-context optimization | 11082–11083 | F03199 | non-negotiable | true | 10 |
| R06349 | "Do not blindly quantize the oracle" | 11086 | F03200 | non-negotiable | false | 10 |
| R06350 | Model qualification per role — oracle quality first, quantize carefully | 11089–11090 | F03201 | non-negotiable | true | 10 |
| R06351 | Model qualification per role — scout speed/cost first, aggressive quantization acceptable | 11092–11093 | F03202 | non-negotiable | true | 10 |
| R06352 | Model qualification per role — router/classifier tiny SLM or CPU model, optimize hard | 11095–11096 | F03203 | non-negotiable | true | 10 |
| R06353 | Model qualification per role — perception fit/speed matters, tolerate specialization | 11098–11099 | F03204 | non-negotiable | true | 10 |
| R06354 | Storage plan must serve AI architecture, NOT vanity sequential numbers | 11104 | F03205 | non-negotiable | false | 10 |
| R06355 | Storage tier — CPU Gen5 NVMe carries hot models | 11109 | F03206 | non-negotiable | true | 10 |
| R06356 | Storage tier — CPU Gen5 NVMe carries active workspace | 11110 | F03206 | non-negotiable | true | 10 |
| R06357 | Storage tier — CPU Gen5 NVMe carries high-value cache | 11110 | F03206 | non-negotiable | true | 10 |
| R06358 | Storage tier — Chipset NVMe carries datasets | 11112 | F03207 | non-negotiable | true | 10 |
| R06359 | Storage tier — Chipset NVMe carries replay | 11113 | F03207 | non-negotiable | true | 10 |
| R06360 | Storage tier — Chipset NVMe carries eval artifacts | 11113 | F03207 | non-negotiable | true | 10 |
| R06361 | Storage tier — Chipset NVMe carries lower-priority cache | 11113 | F03207 | non-negotiable | true | 10 |
| R06362 | Storage tier — ZFS carries snapshots | 11115 | F03208 | non-negotiable | true | 10 |
| R06363 | Storage tier — ZFS carries rollback | 11116 | F03208 | non-negotiable | true | 10 |
| R06364 | Storage tier — ZFS carries trace ledger | 11116 | F03208 | non-negotiable | true | 10 |
| R06365 | Storage tier — ZFS carries workspace safety | 11116 | F03208 | non-negotiable | true | 10 |
| R06366 | Storage tier — RAM carries ARC | 11118 | F03209 | non-negotiable | true | 10 |
| R06367 | Storage tier — RAM carries memory graph | 11119 | F03209 | non-negotiable | true | 10 |
| R06368 | Storage tier — RAM carries hot indexes | 11119 | F03209 | non-negotiable | true | 10 |
| R06369 | Storage tier — RAM carries context arenas | 11119 | F03209 | non-negotiable | true | 10 |
| R06370 | "Do not sacrifice second-GPU width just to chase a second Gen5 M.2 if the 4090's role matters" | 11122 | F03210 | non-negotiable | false | 10 |
| R06371 | Spec/TDD/AIDLC methodology becomes hardware-aware | 11126 | F03211 | non-negotiable | false | 10 |
| R06372 | MAP phase — CPU scans repo / memory / indexes with AVX-512 | 11130 | F03212 | non-negotiable | true | 10 |
| R06373 | MAP phase — 4090 summarizes and classifies | 11131 | F03213 | non-negotiable | true | 10 |
| R06374 | MAP phase — Blackwell only sees distilled hard context | 11132 | F03214 | non-negotiable | true | 10 |
| R06375 | SPEC phase — Blackwell writes/validates high-level spec | 11135 | F03215 | non-negotiable | true | 10 |
| R06376 | SPEC phase — CPU converts acceptance criteria into test/eval structures | 11136 | F03216 | non-negotiable | true | 10 |
| R06377 | TDD phase — sandboxes run tests | 11139 | F03217 | non-negotiable | true | 10 |
| R06378 | TDD phase — CPU tracks outcome bits | 11140 | F03218 | non-negotiable | true | 10 |
| R06379 | TDD phase — 4090 suggests cheap fixes | 11141 | F03219 | non-negotiable | true | 10 |
| R06380 | TDD phase — Blackwell reviews high-risk diffs | 11142 | F03220 | non-negotiable | true | 10 |
| R06381 | EVAL phase — CPU computes trajectory metrics | 11145 | F03221 | non-negotiable | true | 10 |
| R06382 | EVAL phase — 4090 tags failures | 11146 | F03222 | non-negotiable | true | 10 |
| R06383 | EVAL phase — Blackwell synthesizes lessons | 11147 | F03223 | non-negotiable | true | 10 |
| R06384 | COMMIT phase — ZFS snapshot + replay log + human/oracle gate | 11150 | F03224 | non-negotiable | true | 10 |
| R06385 | "Every phase has a best hardware executor" | 11153 | F03225 | non-negotiable | false | 10 |
| R06386 | Practical Rule — Use GPU for dense cognition | 11158 | F03226 | non-negotiable | false | 10 |
| R06387 | Practical Rule — Use CPU AVX-512 for branch law | 11159 | F03227 | non-negotiable | false | 10 |
| R06388 | Practical Rule — Use RAM for active world state | 11160 | F03228 | non-negotiable | false | 10 |
| R06389 | Practical Rule — Use ZFS for memory, replay, rollback | 11161 | F03229 | non-negotiable | false | 10 |
| R06390 | Practical Rule — Use PCIe only for compact symbols, not giant tensors | 11162 | F03230 | non-negotiable | false | 10 |
| R06391 | "That is the core" | 11164 | E0367 | non-negotiable | false | 10 |
| R06392 | "Your super-model is not one model" | 11166 | F03230 | non-negotiable | false | 10 |
| R06393 | Super-model — "the whole machine operating as a routed, evaluated, memory-backed, hardware-aware intelligence system" | 11167 | F03230 | non-negotiable | false | 10 |
| R06394 | M038 integrates with M025 cognitive compiler — CPU-AVX-512-driven map+spec→DAG via VPTERNLOG/VPCOMPRESS | cross-ref M025 + 11042 | M00637 + M00638 | non-negotiable | false | 10 |
| R06395 | M038 integrates with M026 SLM swarm + RLM engine — 4090 runs SLM scouts; Blackwell runs RLM oracle | cross-ref M026 + 11005 + 11000 | F03160 + F03156 | non-negotiable | false | 10 |
| R06396 | M038 integrates with M027 Value Plane — CPU computes trajectory metrics in EVAL phase | 11145 + cross-ref M027 | F03221 | non-negotiable | false | 10 |
| R06397 | M038 integrates with M028 Memory OS — RAM carries memory graph + hot indexes + ARC | 11118–11119 + cross-ref M028 | F03209 | non-negotiable | false | 10 |
| R06398 | M038 integrates with M029 Computer-Use Plane — 4090 runs perception + draft card | 11005 + cross-ref M029 | F03160 | non-negotiable | false | 10 |
| R06399 | M038 integrates with M030 World Model Plane — COMMIT phase ZFS snapshot + replay log carries action history | 11150 + cross-ref M030 | F03224 | non-negotiable | false | 10 |
| R06400 | M038 integrates with M031 Symbolic Planning Plane — VPTERNLOG carries fused policy logic for symbolic verifier | 11040 + cross-ref M031 | F03182 | non-negotiable | false | 10 |
| R06401 | M038 integrates with M032 Cloud Expert Plane — local AVX-512 router invariant + Blackwell oracle reduces cloud-expert reliance | 11026 + 11000 + cross-ref M032 | F03170 + F03156 | non-negotiable | false | 10 |
| R06402 | M038 integrates with M033 Compatibility Gateway + M034 Anthropic-first Gateway — CPU runs gateway logic; profile routing decisions | 11026 + cross-ref M033 + M034 | F03170 | non-negotiable | false | 10 |
| R06403 | M038 integrates with M035 Frontier — Frontier 9-layer Runtime Shape Layer 3 AVX-512 Cortex is M038's CPU control plane | 11026 + cross-ref M035 R05844 | E0361 | non-negotiable | false | 10 |
| R06404 | M038 integrates with M036 MAP-then-act — MAP phase hardware mapping (CPU + 4090 + Blackwell) is M036's pre-act mapping operationalized | 11128–11132 + cross-ref M036 | F03212 + F03213 + F03214 | non-negotiable | false | 10 |
| R06405 | M038 integrates with M037 evidence-driven autonomy — every methodology phase has hardware executor | 11128–11151 + cross-ref M037 | M00645 | non-negotiable | false | 10 |
| R06406 | Project boundary — M038 covers sovereign-os hardware-aware methodology; selfdef MS010 [requires_hardware] gates align with model qualification per role | architecture + MS010 | E0364 | non-negotiable | false | 10 |
| R06407 | Project boundary — selfdef may consume hardware-fingerprint metadata via NATS bridge MS015 with mTLS | MS015 + MS007 + SDD-038 | E0359 | non-negotiable | false | 10 |
| R06408 | Project boundary — selfdef MS007 typed-mirror crates may carry hardware-aware AIDLC schema (quantization tiers / storage tiers / phase executors) | MS007 + SDD-038 | M00643 + M00644 + M00645 | non-negotiable | false | 10 |
| R06409 | Hardware-aware AIDLC closes M035 R05818 "exploits new scaling law locally" — every phase mapped to best hardware | 11153 + cross-ref M035 | E0366 | non-negotiable | false | 10 |
| R06410 | Hardware-aware AIDLC is the 18th plane (extending M027 + M028 + M029 + M030 + M031 + M032 + M033 + M034 + M035 + M036 + M037) | cross-ref M027 R04590 + M028..M037 | E0367 | non-negotiable | false | 10 |
| R06411 | Q-A — How to use 12 cores when only 3-4 are needed for routing? Use remaining for parallel sandboxes (TDD phase) and parallel CPU-side scoring (k-mask + VPTERNLOG batches) | 10994 + 11140 | F03217 + F03218 | non-negotiable | false | 10 |
| R06412 | Q-B — Should /CPU be NUMA-aware? Single-socket workstation (no NUMA at Zen 5 single-die scale) | 10994 (single CPU) | E0359 | non-negotiable | false | 10 |
| R06413 | Q-C — Two GPUs share PCIe lanes (x8/x8) — accept PCIe Gen5 x8 for Blackwell + PCIe Gen4 x8 for 4090 | 11008–11010 + 11003 | F03161 + F03162 | non-negotiable | false | 10 |
| R06414 | Doctrine — quantization tier choice per role (oracle Tier 1-2 / scout Tier 3-4 / router-classifier CPU-only / perception Tier 3) | 11086–11100 | E0364 | non-negotiable | false | 10 |
| R06415 | Doctrine — Tier 4 NVFP4/MXFP4 benchmark-before-trusting (not blind frontier adoption) | 11080 | F03198 | non-negotiable | false | 10 |
| R06416 | Doctrine — Tier 5 KV-cache quantization only for long-context optimization (not default for short context) | 11083 | F03199 | non-negotiable | false | 10 |
| R06417 | Doctrine — storage discipline: hot-models-CPU-NVMe + datasets-Chipset-NVMe + ZFS-snapshots + RAM-ARC | 11109–11120 | M00644 | non-negotiable | false | 10 |
| R06418 | Doctrine — never trade GPU width for second Gen5 M.2 if scout role matters | 11122 | F03210 | non-negotiable | false | 10 |
| R06419 | Doctrine — operator-overridable hardware-aware AIDLC (operator may flip executor per phase via profile config) | cross-ref MS011 SDD-026 + 11128–11151 | M00645 | non-negotiable | false | 10 |
| R06420 | Doctrine — bench every Tier per model + per role (model lab discipline per M036) | 11080 + cross-ref M036 R06046 | M00643 | non-negotiable | false | 10 |
| R06421 | AVX-512 control plane — CPU runs k-masks for branch validity | 11036–11037 | F03179 | non-negotiable | false | 10 |
| R06422 | AVX-512 control plane — CPU runs VPTERNLOG for fused policy logic | 11040 | F03182 | non-negotiable | false | 10 |
| R06423 | AVX-512 control plane — CPU runs VPCOMPRESS/VPEXPAND for branch packing | 11043 | F03183 | non-negotiable | false | 10 |
| R06424 | AVX-512 control plane — CPU runs VPOPCNTDQ for memory sketch scoring | 11046 | F03184 | non-negotiable | false | 10 |
| R06425 | AVX-512 control plane — CPU runs VP2INTERSECT for candidate-memory-tool-set intersection | 11049 | F03186 | non-negotiable | false | 10 |
| R06426 | AVX-512 control plane — CPU runs VBMI/VBMI2 for byte/token-class manipulation | 11052 | F03187 | non-negotiable | false | 10 |
| R06427 | AVX-512 control plane — CPU runs VNNI/BF16 for CPU-side scoring/classifier kernels | 11055 | F03188 | non-negotiable | false | 10 |
| R06428 | "GPU runs probability. CPU runs law." — invariant | 11060–11061 | F03190 | non-negotiable | false | 10 |
| R06429 | CUDA Linux IOMMU + VFIO — supports VM passthrough only; no bare-metal P2P memory copy | 11021 | F03166 + F03167 | non-negotiable | false | 10 |
| R06430 | Compiler convention — `-march=znver5` for sovereign-os build artifacts targeting workstation | 11031 | F03171 | non-negotiable | true | 10 |
| R06431 | AVX-512 detection — runtime CPUID checks for VNNI / BF16 / VBMI / VBMI2 / BITALG / VPOPCNTDQ / VP2INTERSECT before invoking instructions | cross-ref MS010 R02236 (selfdef-hardware) + 11031 | E0361 | non-negotiable | false | 10 |
| R06432 | Hardware-aware AIDLC EVAL phase — CPU computes trajectory metrics (cost / latency / steps / branch acceptance) | 11145 + cross-ref M027 + M035 | F03221 | non-negotiable | false | 10 |
| R06433 | Hardware-aware AIDLC TDD phase — sandboxes run tests (selfdef-side sandbox tiers per cross-ref M033 / M029) | 11139 + cross-ref M033 jean/sandbox + M029 | F03217 | non-negotiable | false | 10 |
| R06434 | Hardware-aware AIDLC SPEC phase — Blackwell writes spec; CPU compiles acceptance criteria | 11135–11136 | F03215 + F03216 | non-negotiable | false | 10 |
| R06435 | Hardware-aware AIDLC MAP phase — CPU scans + 4090 summarizes + Blackwell sees distilled context | 11130–11132 | F03212 + F03213 + F03214 | non-negotiable | false | 10 |
| R06436 | Hardware-aware AIDLC COMMIT phase — ZFS snapshot + replay log + human/oracle gate | 11150 | F03224 | non-negotiable | false | 10 |
| R06437 | Layer-B metric (implied) — `sovereign_os_hardware_aidlc_phase_executor_total{phase, executor}` | architecture + 11128–11151 | M00645 | non-negotiable | true | 10 |
| R06438 | Layer-B metric (implied) — `sovereign_os_hardware_aidlc_quantization_tier_in_use{tier, role}` | architecture + 11069–11100 | M00643 | non-negotiable | true | 10 |
| R06439 | Layer-B metric (implied) — `sovereign_os_hardware_aidlc_avx512_kmask_operations_total{op}` | architecture + 11036 | F03179 | non-negotiable | true | 10 |
| R06440 | Composite — M038 closes the hardware-software gap by mapping every Spec/TDD/AIDLC phase to its best hardware executor; honors "GPU runs probability / CPU runs law" invariant; 5-tier quantization scheme with role-based qualification; storage discipline per-AI-architecture (not vanity); PCIe peer-to-peer Linux limitation respected (Blackwell oracle + 4090 scout + CPU router); ProArt X870E-Creator x8/x8 lane-sharing accepted; closing rule "Use PCIe only for compact symbols, not giant tensors" + "super-model is the whole machine operating as a routed, evaluated, memory-backed, hardware-aware intelligence system" | 10964–11167 | E0358 + E0359 + E0360 + E0361 + E0362 + E0363 + E0364 + E0365 + E0366 + E0367 | non-negotiable | false | 10 |
| R06441 | M038 integrates with sovereign-os hardware profile (sain-01 deployment target per selfdef SDD-017) — Blackwell + 4090 + Zen 5 9900X + ProArt X870E-Creator + 256GB DDR5 + dual NVMe | cross-ref selfdef SDD-017 R01747-R01756 | E0359 | non-negotiable | false | 10 |
| R06442 | M038 integrates with selfdef SDD-018 hardware-aware modules — [requires_hardware] gpu_count_min / memory_gib_min / avx512_vnni map to M038 hardware reality | cross-ref selfdef SDD-018 + MS010 | E0359 | non-negotiable | false | 10 |
| R06443 | M038 integrates with selfdef SDD-022 hardware exploit doctrine — AVX-512 instruction catalog (VPTERNLOG / VPCOMPRESS / VPOPCNTDQ / VP2INTERSECT / VBMI / VNNI) is cross-repo doctrine | cross-ref selfdef SDD-022 | E0361 | non-negotiable | false | 10 |
| R06444 | M038 integrates with selfdef SDD-023 cross-repo model taxonomy mirror — R212 model catalog encodes role + quantization tier per M038 | cross-ref selfdef SDD-023 + 11069–11100 | M00643 + E0364 | non-negotiable | false | 10 |
| R06445 | M038 honors M032 Cloud Expert Plane invariant "Remote models propose. Local runtime commits." — CPU=deterministic router commits | 11026 + cross-ref M032 R05330 | F03170 | non-negotiable | false | 10 |
| R06446 | M038 honors M035 Kernel Law — Models are userland; Tools are devices; Memory is managed; Side effects are syscalls; Policies are permissions; Replay is audit log; Deterministic runtime is kernel space | cross-ref M035 R05862-R05868 | E0367 | non-negotiable | false | 10 |
| R06447 | Storage tier composition — CPU Gen5 NVMe + Chipset NVMe + ZFS overlay + 256GB RAM ARC | 11109–11120 | M00644 | non-negotiable | false | 10 |
| R06448 | Storage tier hierarchy — Gen5 NVMe (hot models) > Chipset NVMe (datasets) > ZFS (snapshots) > RAM (ARC); priority order from fastest to memory-graph | 11109–11120 | M00644 | non-negotiable | false | 10 |
| R06449 | Lane-sharing acceptance — ProArt X870E-Creator x8/x8 is documented constraint, not bug | 11008–11010 + 11012 | F03162 + F03163 | non-negotiable | false | 10 |
| R06450 | Lane-sharing strategy — second-GPU width prioritized over second Gen5 M.2 when 4090 role matters | 11122 | F03210 | non-negotiable | false | 10 |
| R06451 | Quantization tier mapping — oracle uses Tier 1/2 only (BF16/FP16 baseline + FP8 sweet spot) | 11089–11090 + 11070–11074 | F03201 + F03195 + F03196 | non-negotiable | false | 10 |
| R06452 | Quantization tier mapping — scout uses Tier 3/4 (GPTQ/AWQ/SmoothQuant + NVFP4/MXFP4 when benchmarked) | 11092–11093 + 11076–11080 | F03202 + F03197 + F03198 | non-negotiable | false | 10 |
| R06453 | Quantization tier mapping — router/classifier uses CPU-only or tiny SLM (no GPU quant tier) | 11095–11096 | F03203 | non-negotiable | false | 10 |
| R06454 | Quantization tier mapping — perception uses Tier 3 (specialization-tolerant) | 11098–11099 | F03204 | non-negotiable | false | 10 |
| R06455 | Phase-executor mapping is hardware policy (not just suggestion) — daemon-enforceable | 11128–11151 | M00645 | non-negotiable | false | 10 |
| R06456 | Phase-executor mapping operator-overridable per profile (per MS011 SDD-026 Z-1 dashboard) | cross-ref MS011 + 11128–11151 | M00645 | non-negotiable | false | 10 |
| R06457 | AVX-512 instruction subset support is runtime-CPUID-detected (selfdef-hardware crate) | cross-ref selfdef MS010 R02236 | E0361 | non-negotiable | false | 10 |
| R06458 | AVX-512 instruction subset fallback — when subset absent, fall back to scalar code path (no fail) | architecture + cross-ref MS010 R02224 | E0361 | non-negotiable | false | 10 |
| R06459 | Compiler convention — workstation build uses `-march=znver5` + `-mprefer-vector-width=512` + each detected -mavx512* flag | 11031 + cross-ref selfdef MS010 R02240-R02243 | F03171 | non-negotiable | false | 10 |
| R06460 | Composite — M038 Hardware-aware AIDLC is the bridge from software methodology to specific workstation metal; every Spec/TDD/AIDLC phase has best hardware executor; 5-tier quantization with role-based qualification; 4-tier storage discipline; "GPU runs probability / CPU runs law" invariant; "super-model is the whole machine"; integrates with M025-M037 + selfdef SDD-017 + SDD-018 + SDD-022 + SDD-023 + MS010 hardware-aware modules | 10964–11167 + cross-refs | E0358 + E0367 | non-negotiable | false | 10 |

## Cross-references

- Adjacent dump-range milestones: M037 evidence-driven autonomy (10712–10964) / M039 (next; dump 11169–...)
- Plane integration: M025 cognitive compiler / M026 SLM swarm + RLM engine / M027 Value Plane / M028 Memory OS / M029 Computer-Use Plane / M030 World Model Plane / M031 Symbolic Planning Plane / M032 Cloud Expert Plane / M033 Compatibility Gateway / M034 Anthropic-first Gateway / M035 Frontier inference-time intelligence / M036 MAP-then-act paradigm / M037 evidence-driven autonomy / M038 Hardware-aware AIDLC (this)
- Selfdef integration: SDD-017 SAIN-01 hardware inventory matches M038 hardware reality / SDD-018 hardware-aware modules [requires_hardware] gates / SDD-022 hardware exploit doctrine codifies AVX-512 instruction catalog / SDD-023 cross-repo model taxonomy mirror carries role+quantization-tier metadata
- ASUS ProArt X870E-Creator official specs (lane-sharing reference): asus.com
- NVIDIA RTX PRO 6000 Blackwell Workstation datasheet (1.8TB/s + FP4 reference): nvidia.com
- NVIDIA RTX 4090 official page (24GB GDDR6X + PCIe Gen4 reference): nvidia.com
- AMD Zen 5 / EPYC AVX-512 tuning guide + validation blog (znver5 + AVX-512 subsets reference): amd.com
- NVIDIA CUDA C Programming Guide (IOMMU + VFIO reference): nvidia.com
- TensorRT-LLM precision docs + Torch-TensorRT quantization docs (FP4/NVFP4 reference): nvidia.github.io + docs.pytorch.org
- vLLM LLM Compressor compression schemes (NVFP4/MXFP4 reference): docs.vllm.ai
