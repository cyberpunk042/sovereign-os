# M073 — 1-bit (ternary) logic + BitLinear Core ({-1, 0, +1} ≈ 1.58 bits/parameter)

**Parent**: sovereign-os runtime — inference execution paradigm layer
**Source**: `~/infohub/raw/dumps/2026-05-15-sain-01-master-spec-other-conversation-transposition.md` lines 770-797 (Section 15: The Low-Bit Paradigm: 1-Bit (Ternary) Logic & The BitLinear Core)

## Doctrinal anchors

> "The integration of 1-bit (ternary) weights completely upends traditional Von Neumann execution bottlenecks in local AI workloads." (dump 777-778)
> "The 1-bit evolution—pioneered by architectures like Microsoft's BitNet b1.58—restricts every single weight parameter in a network's linear projections to a discrete ternary set: $\{-1, 0, +1\}$" (dump 779-781)
> "The designation 1.58-bit stems from information theory: representing three distinct states requires a minimum storage width of $\log_2(3) \approx 1.585$ bits per parameter." (dump 783)
> "By substituting expensive floating-point multiplications with basic integer additions and subtractions, the computation becomes vastly more energy-efficient" (dump 791)

## Epics (E0698-E0707)

| epic | name | source |
|---|---|---|
| E0698 | Ternary weight set — {-1, 0, +1} (BitNet b1.58 lineage) | dump 779-781 |
| E0699 | 1.58-bit storage — log2(3) ≈ 1.585 bits per parameter | dump 783 |
| E0700 | Elimination of multiplication — +1 → add / -1 → subtract / 0 → no-op | dump 786-789 |
| E0701 | Energy-efficiency shift — multiplications → integer adds/subtracts | dump 791 |
| E0702 | Performance profile shift — TFLOPS → memory bandwidth + instruction pipeline | dump 791 |
| E0703 | BitLinear core — replaces standard linear projection layers | dump 778-781 |
| E0704 | Ternary weight packing — 2 bits per parameter in host RAM (byte boundary alignment) | dump 794 |
| E0705 | bitnet.cpp + T-MAC frameworks — no de-quantization at execution | dump 794-795 |
| E0706 | Bit-wise Lookup Table (LUT) matrix operations — via AVX-512 vector path | dump 795 |
| E0707 | Integration with M066 Pulse Core — runs on CCD 0 (M070) via AVX-512 native execution | cross-ref M066 + M070 |

## Modules (M01207-M01223)

| module | name | source |
|---|---|---|
| M01207 | sovereign-ternary-weight-set-validator (-1/0/+1 only) | dump 781 |
| M01208 | sovereign-bitlinear-layer-replacer | dump 778 |
| M01209 | sovereign-ternary-add-accumulator (+1 → activation += ...) | dump 786 |
| M01210 | sovereign-ternary-sub-accumulator (-1 → activation -= ...) | dump 787 |
| M01211 | sovereign-ternary-noop-skipper (0 → bypass) | dump 788 |
| M01212 | sovereign-ternary-storage-packer (2 bits/parameter) | dump 794 |
| M01213 | sovereign-ternary-lut-operator (Bit-wise Lookup Table matrix ops) | dump 795 |
| M01214 | sovereign-bitnet-cpp-integration | dump 794 |
| M01215 | sovereign-t-mac-integration | dump 794 |
| M01216 | sovereign-ternary-energy-monitor (track add/sub vs FP MUL savings) | dump 791 |
| M01217 | sovereign-ternary-memory-bandwidth-optimizer | dump 791 |
| M01218 | sovereign-ternary-info-theory-validator (log2(3) bits/parameter) | dump 783 |
| M01219 | sovereign-ternary-typed-mirror | cross-ref selfdef MS007 |
| M01220 | sovereign-ternary-event-emitter | cross-ref M049 + selfdef MS026 |
| M01221 | sovereign-ternary-dashboard-binding (D-03 model health + D-10 eval history) | cross-ref M060 |
| M01222 | sovereign-ternary-replay-validator | cross-ref selfdef MS009 |
| M01223 | sovereign-ternary-cli-subcommand-set | cross-ref selfdef MS043 |

## Features (F06036-F06120)

| feature | name | source |
|---|---|---|
| F06036 | Doctrinal — 1-bit (ternary) weights upend Von Neumann bottlenecks | dump 777 |
| F06037 | Doctrinal — pioneered by Microsoft BitNet b1.58 | dump 779 |
| F06038 | Doctrinal — restricts every weight parameter in linear projections | dump 780 |
| F06039 | Ternary set — {-1, 0, +1} verbatim | dump 781 |
| F06040 | Information theory — log2(3) ≈ 1.585 bits per parameter | dump 783 |
| F06041 | Information theory — 3 distinct states minimum storage 1.585 bits | dump 783 |
| F06042 | Elimination — fundamental arithmetic shifts multiplication → conditional allocation | dump 785 |
| F06043 | Elimination — +1 → activation added to accumulator | dump 786 |
| F06044 | Elimination — -1 → activation subtracted from accumulator | dump 787 |
| F06045 | Elimination — 0 → No-Op, bypassed entirely | dump 788 |
| F06046 | Energy — floating-point multiplications replaced with integer add/sub | dump 791 |
| F06047 | Energy — vastly more energy-efficient | dump 791 |
| F06048 | Profile shift — away from raw TFLOPS throughput | dump 791 |
| F06049 | Profile shift — toward memory bandwidth optimization | dump 791 |
| F06050 | Profile shift — toward instruction pipeline optimization | dump 791 |
| F06051 | BitLinear — replaces standard linear projection layers | dump 778 |
| F06052 | BitLinear — replaces GEMM (Floating-Point General Matrix Multiplication) | dump 778 |
| F06053 | BitLinear — eliminates GPU Tensor Core + CPU FPU saturation | dump 778 |
| F06054 | Packing — ternary weights packed 2 bits per parameter | dump 794 |
| F06055 | Packing — aligns with standard byte boundaries | dump 794 |
| F06056 | Packing — host RAM storage | dump 794 |
| F06057 | Frameworks — bitnet.cpp specialized low-level compilation | dump 794 |
| F06058 | Frameworks — T-MAC specialized low-level compilation | dump 794 |
| F06059 | Frameworks — no de-quantization back to floating-point at execution | dump 794-795 |
| F06060 | LUT operations — Bit-wise Lookup Table matrix operations | dump 795 |
| F06061 | LUT operations — leverages AVX-512 vector path | dump 795 |
| F06062 | LUT operations — single-pass through CPU registers | dump 795 |
| F06063 | Pulse Core integration — runs on CCD 0 per M070 | cross-ref M070 + dump 1024 |
| F06064 | Pulse Core integration — Pulse manifestation per M066 Trinity | cross-ref M066 + dump 959-961 |
| F06065 | Pulse Core integration — uses kernel -march=znver5 AVX-512 path per M067 | cross-ref M067 |
| F06066 | Pulse Core integration — composes with M074 VNNI fusion (pending) | cross-ref M074 (pending) |
| F06067 | Energy monitor — tracks add/sub vs FP MUL savings | dump 791 |
| F06068 | Energy monitor — emits M049 metric per inference run | cross-ref M049 |
| F06069 | Energy monitor — surfaces via D-09 hardware pressure | cross-ref M060 |
| F06070 | Energy monitor — composes with M058 Goldilocks objective (energy unit) | cross-ref M058 |
| F06071 | Memory bandwidth optimizer — tracks bytes/inference | architecture + dump 791 |
| F06072 | Memory bandwidth optimizer — surfaces via D-09 hardware pressure | cross-ref M060 |
| F06073 | Memory bandwidth optimizer — alerts on bandwidth saturation | architecture + cross-ref M055 |
| F06074 | Info theory validator — verifies storage width ≈ 1.585 bits/parameter | dump 783 |
| F06075 | Info theory validator — rejects models storing > 2 bits/parameter for ternary weights | architecture |
| F06076 | Typed mirror — sovereign-ternary-runtime-mirror under MS007 8/8 SATURATED | cross-ref selfdef MS007 |
| F06077 | Typed mirror — TernaryWeight enum (Minus / Zero / Plus) | cross-ref selfdef MS007 |
| F06078 | Typed mirror — BitLinearLayer struct {input_dim, output_dim, ternary_weights, scaling} | cross-ref selfdef MS007 |
| F06079 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 |
| F06080 | Typed mirror — signed via MS003 | cross-ref selfdef MS003 |
| F06081 | Event emitter — every inference run emits M049 trace | cross-ref M049 |
| F06082 | Event emitter — emits OCSF System Activity 1001 per inference | cross-ref selfdef MS026 |
| F06083 | Event emitter — energy + bandwidth metrics per run | architecture + cross-ref M049 |
| F06084 | Dashboard — D-03 model health surfaces BitLinear model status | cross-ref M060 |
| F06085 | Dashboard — D-10 eval history surfaces ternary-model eval scores | cross-ref M060 |
| F06086 | Dashboard — D-09 hardware pressure surfaces add/sub vs FP MUL ratio | cross-ref M060 |
| F06087 | Replay validator — verifies historical ternary-inference chain | cross-ref selfdef MS009 |
| F06088 | Replay validator — detects weight tampering | cross-ref selfdef MS009 + MS003 |
| F06089 | Replay validator — emits OCSF Detection 2004 on chain break | cross-ref selfdef MS026 |
| F06090 | CLI — `sovereign ternary inference --model <m> --prompt <p>` runs ternary inference | architecture + cross-ref selfdef MS043 |
| F06091 | CLI — `sovereign ternary energy` returns energy savings stats | architecture |
| F06092 | CLI — `sovereign ternary verify <model-id>` verifies model uses ternary weights only | architecture |
| F06093 | CLI — `sovereign ternary throughput` returns tokens/sec on CPU | architecture |
| F06094 | CLI — all ternary subcommands emit M049 trace | cross-ref M049 |
| F06095 | Composition — composes with M058 hardware-aware scheduler (BitLinear models routed to Pulse CCD 0) | cross-ref M058 |
| F06096 | Composition — composes with M066 Trinity Pulse Core | cross-ref M066 |
| F06097 | Composition — composes with M067 kernel build (AVX-512 path) | cross-ref M067 |
| F06098 | Composition — composes with M070 Dual-CCD (Pulse on CCD 0) | cross-ref M070 |
| F06099 | Composition — composes forward with M074 AVX-512 VNNI fusion | cross-ref M074 (pending) |
| F06100 | Composition — composes forward with M076 3 load-balancing profiles (Ultra-Sovereign Efficiency uses ternary) | cross-ref M076 (pending) |
| F06101 | Composition — composes with M046 LoRA Foundry (adapters can target ternary base) | cross-ref M046 |
| F06102 | Composition — composes with M048 modules map (Compute Fabric Pulse role) | cross-ref M048 |
| F06103 | Composition — composes with selfdef MS035 capability tokens (capability_word.compute_mode bit) | cross-ref selfdef MS035 |
| F06104 | Composition — composes with selfdef MS039 authority levels (model load is L5 Commit) | cross-ref selfdef MS039 |
| F06105 | Composition — composes with selfdef MS041 commit authority (adapter promotion is L6) | cross-ref selfdef MS041 |
| F06106 | Composition — composes with selfdef MS043 IPS operator surface (CLI integration) | cross-ref selfdef MS043 |
| F06107 | Boundary — ternary inference runs in sovereign-os runtime | architecture + operator standing direction |
| F06108 | Boundary — selfdef IPS enforces sandbox/network boundary per MS036/MS038 | cross-ref selfdef MS036 + MS038 |
| F06109 | Boundary — info-hub indexes ternary models metadata as read-only | operator standing direction "second-brain" |
| F06110 | Cross-ref — Microsoft BitNet b1.58 paper lineage | dump 779 |
| F06111 | Cross-ref — DeepSeek-V3-Quant model candidate per dump 921 | cross-ref M068 F05755 |
| F06112 | Cross-ref — Ling-2.6-flash + Nemotron-3-Nano-Omni model candidates | prior-dump-review findings + cross-ref M048 |
| F06113 | Doctrinal preservation — ternary set notation `{-1, 0, +1}` verbatim | dump 781 |
| F06114 | Doctrinal preservation — `log_2(3) \approx 1.585` verbatim | dump 783 |
| F06115 | Doctrinal preservation — BitNet b1.58 + bitnet.cpp + T-MAC names verbatim | dump 779 + 794 |
| F06116 | Doctrinal preservation — verbatim quotes never paraphrased | operator standing direction |
| F06117 | Doctrinal preservation — info-hub indexes 1-bit paradigm as second-brain entry | operator standing direction |
| F06118 | Operational — `sovereign-ternary-runtime.service` systemd unit | architecture |
| F06119 | Operational — service pinned to CCD 0 cores 0-5 via systemd CPUAffinity | architecture + cross-ref M070 |
| F06120 | Closing — M073 covers dump 770-797 verbatim 1-bit ternary scope; M074 AVX-512 VNNI fusion next | dump 770-797 + operator standing direction |

## Requirements (R12071-R12240)

| req | description | source | feature | priority | exception | sub-reqs |
|---|---|---|---|---|---|---|
| R12071 | Doctrinal — 1-bit (ternary) weights upend traditional Von Neumann bottlenecks | dump 777 | F06036 | non-negotiable | false | 10 |
| R12072 | Doctrinal — pioneered by Microsoft BitNet b1.58 | dump 779 | F06037 | non-negotiable | false | 10 |
| R12073 | Doctrinal — restricts every weight parameter in linear projections | dump 780 | F06038 | non-negotiable | false | 10 |
| R12074 | Doctrinal — discrete ternary set {-1, 0, +1} verbatim | dump 781 | F06039 | non-negotiable | false | 10 |
| R12075 | Doctrinal — log2(3) ≈ 1.585 bits per parameter | dump 783 | F06040 | non-negotiable | false | 10 |
| R12076 | Doctrinal — 1.58-bit designation from information theory | dump 783 | F06041 | non-negotiable | false | 10 |
| R12077 | Doctrinal — fundamental arithmetic shifts to conditional allocation | dump 785 | F06042 | non-negotiable | false | 10 |
| R12078 | Doctrinal — +1 → activation added to accumulator | dump 786 | F06043 | non-negotiable | false | 10 |
| R12079 | Doctrinal — -1 → activation subtracted from accumulator | dump 787 | F06044 | non-negotiable | false | 10 |
| R12080 | Doctrinal — 0 → No-Op, bypassed entirely | dump 788 | F06045 | non-negotiable | false | 10 |
| R12081 | Energy — multiplications replaced with integer add/sub | dump 791 | F06046 | non-negotiable | false | 10 |
| R12082 | Energy — vastly more energy-efficient | dump 791 | F06047 | non-negotiable | false | 10 |
| R12083 | Profile shift — away from raw TFLOPS throughput | dump 791 | F06048 | non-negotiable | false | 10 |
| R12084 | Profile shift — toward memory bandwidth optimization | dump 791 | F06049 | non-negotiable | false | 10 |
| R12085 | Profile shift — toward instruction pipeline optimization | dump 791 | F06050 | non-negotiable | false | 10 |
| R12086 | BitLinear — replaces standard linear projection layers | dump 778 | F06051 | non-negotiable | false | 10 |
| R12087 | BitLinear — replaces GEMM (Floating-Point General Matrix Multiplication) | dump 778 | F06052 | non-negotiable | false | 10 |
| R12088 | BitLinear — eliminates GPU Tensor Core saturation | dump 778 | F06053 | non-negotiable | false | 10 |
| R12089 | BitLinear — eliminates CPU FPU saturation | dump 778 | F06053 | non-negotiable | false | 10 |
| R12090 | BitLinear — validates only ternary weights stored | dump 781 + architecture | F06051 | non-negotiable | false | 10 |
| R12091 | Packing — ternary weights packed 2 bits per parameter | dump 794 | F06054 | non-negotiable | false | 10 |
| R12092 | Packing — aligns with standard byte boundaries | dump 794 | F06055 | non-negotiable | false | 10 |
| R12093 | Packing — host RAM storage | dump 794 | F06056 | non-negotiable | false | 10 |
| R12094 | Packing — packed format verified by MS003-signed validator | cross-ref selfdef MS003 | F06054 | non-negotiable | false | 10 |
| R12095 | Packing — packing emits OCSF System Activity 1001 on model load | cross-ref selfdef MS026 | F06082 | non-negotiable | false | 10 |
| R12096 | Frameworks — bitnet.cpp specialized low-level compilation supported | dump 794 | F06057 | non-negotiable | false | 10 |
| R12097 | Frameworks — T-MAC specialized low-level compilation supported | dump 794 | F06058 | non-negotiable | false | 10 |
| R12098 | Frameworks — no de-quantization back to floating-point at execution | dump 795 | F06059 | non-negotiable | false | 10 |
| R12099 | LUT operations — Bit-wise Lookup Table matrix operations | dump 795 | F06060 | non-negotiable | false | 10 |
| R12100 | LUT operations — leverages AVX-512 vector path | dump 795 | F06061 | non-negotiable | false | 10 |
| R12101 | LUT operations — single-pass through CPU registers | dump 795 | F06062 | non-negotiable | false | 10 |
| R12102 | Pulse Core — runs on CCD 0 per M070 | cross-ref M070 + dump 1024 | F06063 | non-negotiable | false | 10 |
| R12103 | Pulse Core — Pulse manifestation per M066 Trinity | cross-ref M066 + dump 959-961 | F06064 | non-negotiable | false | 10 |
| R12104 | Pulse Core — uses kernel -march=znver5 AVX-512 path per M067 | cross-ref M067 | F06065 | non-negotiable | false | 10 |
| R12105 | Pulse Core — composes with M074 VNNI fusion (pending) | cross-ref M074 (pending) | F06066 | non-negotiable | false | 10 |
| R12106 | Pulse Core — pinned via systemd CPUAffinity to cores 0-5 | architecture + cross-ref M070 | F06119 | non-negotiable | false | 10 |
| R12107 | Energy monitor — tracks add/sub vs FP MUL savings | dump 791 | F06067 | non-negotiable | false | 10 |
| R12108 | Energy monitor — emits M049 metric per inference run | cross-ref M049 | F06068 | non-negotiable | false | 10 |
| R12109 | Energy monitor — surfaces via D-09 hardware pressure | cross-ref M060 | F06069 | non-negotiable | false | 10 |
| R12110 | Energy monitor — composes with M058 Goldilocks energy unit | cross-ref M058 | F06070 | non-negotiable | false | 10 |
| R12111 | Memory bandwidth optimizer — tracks bytes/inference | architecture + dump 791 | F06071 | non-negotiable | false | 10 |
| R12112 | Memory bandwidth optimizer — surfaces via D-09 hardware pressure | cross-ref M060 | F06072 | non-negotiable | false | 10 |
| R12113 | Memory bandwidth optimizer — alerts on saturation | architecture + cross-ref M055 | F06073 | non-negotiable | false | 10 |
| R12114 | Info theory validator — verifies storage width ≈ 1.585 bits/parameter | dump 783 | F06074 | non-negotiable | false | 10 |
| R12115 | Info theory validator — rejects models storing > 2 bits/parameter for ternary | architecture | F06075 | non-negotiable | false | 10 |
| R12116 | Info theory validator — emits OCSF Detection 2004 on violation | cross-ref selfdef MS026 | F06075 | non-negotiable | false | 10 |
| R12117 | Typed mirror — sovereign-ternary-runtime-mirror under MS007 8/8 SATURATED | cross-ref selfdef MS007 | F06076 | non-negotiable | false | 10 |
| R12118 | Typed mirror — TernaryWeight enum {Minus, Zero, Plus} | cross-ref selfdef MS007 | F06077 | non-negotiable | false | 10 |
| R12119 | Typed mirror — BitLinearLayer struct {input_dim, output_dim, ternary_weights, scaling} | cross-ref selfdef MS007 | F06078 | non-negotiable | false | 10 |
| R12120 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 | F06079 | non-negotiable | false | 10 |
| R12121 | Typed mirror — signed via MS003 | cross-ref selfdef MS003 | F06080 | non-negotiable | false | 10 |
| R12122 | Typed mirror — re-exported via sovereign-os cargo workspace | cross-ref selfdef MS007 | F06076 | non-negotiable | false | 10 |
| R12123 | Typed mirror — no_std friendly | architecture | F06076 | non-negotiable | false | 10 |
| R12124 | Typed mirror — serde + bincode derives present | architecture | F06076 | non-negotiable | false | 10 |
| R12125 | Typed mirror — schema-breaking changes require schema_version bump | architecture + cross-ref selfdef MS007 | F06079 | non-negotiable | false | 10 |
| R12126 | Event — every inference run emits M049 13-field trace span | cross-ref M049 | F06081 | non-negotiable | false | 10 |
| R12127 | Event — emits OCSF System Activity 1001 per inference | cross-ref selfdef MS026 | F06082 | non-negotiable | false | 10 |
| R12128 | Event — energy + bandwidth metrics per run | architecture + cross-ref M049 | F06083 | non-negotiable | false | 10 |
| R12129 | Event — span includes weight-set-digest + activation-set-digest | architecture + cross-ref selfdef MS003 | F06081 | non-negotiable | false | 10 |
| R12130 | Event — span deterministic for MS009 replay | cross-ref selfdef MS009 | F06081 | non-negotiable | false | 10 |
| R12131 | Dashboard — D-03 surfaces BitLinear model status | cross-ref M060 | F06084 | non-negotiable | false | 10 |
| R12132 | Dashboard — D-10 surfaces ternary-model eval scores | cross-ref M060 | F06085 | non-negotiable | false | 10 |
| R12133 | Dashboard — D-09 surfaces add/sub vs FP MUL ratio | cross-ref M060 | F06086 | non-negotiable | false | 10 |
| R12134 | Dashboard — D-04 costs surfaces energy savings per model | cross-ref M060 + dump 791 | F06067 | non-negotiable | false | 10 |
| R12135 | Replay validator — verifies historical ternary-inference chain | cross-ref selfdef MS009 | F06087 | non-negotiable | false | 10 |
| R12136 | Replay validator — detects weight tampering | cross-ref selfdef MS009 + MS003 | F06088 | non-negotiable | false | 10 |
| R12137 | Replay validator — emits OCSF Detection 2004 on chain break | cross-ref selfdef MS026 | F06089 | non-negotiable | false | 10 |
| R12138 | Replay validator — runs daily | cross-ref selfdef MS009 | F06087 | non-negotiable | false | 10 |
| R12139 | Replay validator — failures halt new ternary model loads | architecture | F06087 | non-negotiable | false | 10 |
| R12140 | CLI — `sovereign ternary inference --model <m> --prompt <p>` runs ternary inference | architecture + cross-ref selfdef MS043 | F06090 | non-negotiable | false | 10 |
| R12141 | CLI — `sovereign ternary energy` returns energy savings stats | architecture | F06091 | non-negotiable | false | 10 |
| R12142 | CLI — `sovereign ternary verify <model-id>` verifies ternary-only | architecture | F06092 | non-negotiable | false | 10 |
| R12143 | CLI — `sovereign ternary throughput` returns tokens/sec on CPU | architecture | F06093 | non-negotiable | false | 10 |
| R12144 | CLI — `sovereign ternary models` lists installed ternary models | architecture | F06090 | non-negotiable | false | 10 |
| R12145 | CLI — all ternary subcommands emit M049 trace | cross-ref M049 | F06094 | non-negotiable | false | 10 |
| R12146 | CLI — `--json` flag returns structured output | architecture | F06090 | non-negotiable | false | 10 |
| R12147 | CLI — `--watch` flag streams inference progress | architecture | F06090 | non-negotiable | false | 10 |
| R12148 | Composition — composes with M058 (BitLinear routed to Pulse CCD 0) | cross-ref M058 | F06095 | non-negotiable | false | 10 |
| R12149 | Composition — composes with M066 Trinity Pulse | cross-ref M066 | F06096 | non-negotiable | false | 10 |
| R12150 | Composition — composes with M067 kernel build AVX-512 path | cross-ref M067 | F06097 | non-negotiable | false | 10 |
| R12151 | Composition — composes with M070 Dual-CCD Pulse on CCD 0 | cross-ref M070 | F06098 | non-negotiable | false | 10 |
| R12152 | Composition — composes forward with M074 VNNI fusion | cross-ref M074 (pending) | F06099 | non-negotiable | false | 10 |
| R12153 | Composition — composes forward with M076 Ultra-Sovereign Efficiency profile | cross-ref M076 (pending) | F06100 | non-negotiable | false | 10 |
| R12154 | Composition — composes with M046 LoRA Foundry (adapters target ternary base) | cross-ref M046 | F06101 | non-negotiable | false | 10 |
| R12155 | Composition — composes with M048 Compute Fabric Pulse role | cross-ref M048 | F06102 | non-negotiable | false | 10 |
| R12156 | Composition — composes with selfdef MS035 capability_word.compute_mode | cross-ref selfdef MS035 | F06103 | non-negotiable | false | 10 |
| R12157 | Composition — composes with selfdef MS039 authority levels (model load = L5 Commit) | cross-ref selfdef MS039 | F06104 | non-negotiable | false | 10 |
| R12158 | Composition — composes with selfdef MS041 commit authority (adapter promotion = L6) | cross-ref selfdef MS041 | F06105 | non-negotiable | false | 10 |
| R12159 | Composition — composes with selfdef MS043 IPS operator surface | cross-ref selfdef MS043 | F06106 | non-negotiable | false | 10 |
| R12160 | Boundary — ternary inference runs in sovereign-os runtime | architecture + operator standing direction | F06107 | non-negotiable | false | 10 |
| R12161 | Boundary — selfdef IPS enforces sandbox per MS036 | cross-ref selfdef MS036 | F06108 | non-negotiable | false | 10 |
| R12162 | Boundary — selfdef IPS enforces network per MS038 | cross-ref selfdef MS038 | F06108 | non-negotiable | false | 10 |
| R12163 | Boundary — info-hub indexes ternary models metadata as read-only | operator standing direction "second-brain" | F06109 | non-negotiable | false | 10 |
| R12164 | Boundary — info-hub never mutated by ternary runtime | operator standing direction | F06109 | non-negotiable | false | 10 |
| R12165 | Cross-ref — Microsoft BitNet b1.58 paper lineage cited | dump 779 | F06110 | non-negotiable | false | 10 |
| R12166 | Cross-ref — DeepSeek-V3-Quant model per dump 921 | cross-ref M068 + dump 921 | F06111 | non-negotiable | false | 10 |
| R12167 | Cross-ref — Ling-2.6-flash model per prior-dump review | prior-dump review | F06112 | non-negotiable | false | 10 |
| R12168 | Cross-ref — Nemotron-3-Nano-Omni model per prior-dump review | prior-dump review | F06112 | non-negotiable | false | 10 |
| R12169 | Performance — token throughput 5-12 tokens/sec on CPU (per dump 1126 reference) | dump 1126 | F06093 | non-negotiable | false | 10 |
| R12170 | Performance — `sovereign ternary inference` first-token latency `<` 200ms p95 | architecture | F06090 | non-negotiable | false | 10 |
| R12171 | Performance — `sovereign ternary verify` runtime `<` 5s for typical 7B-param model | architecture | F06092 | non-negotiable | false | 10 |
| R12172 | Performance — typed-mirror publication latency `<` 100ms p95 | cross-ref selfdef MS007 | F06076 | non-negotiable | false | 10 |
| R12173 | Performance — replay validator daily run `<` 60s | cross-ref selfdef MS009 | F06087 | non-negotiable | false | 10 |
| R12174 | Telemetry — ternary inference count emitted via M049 | cross-ref M049 | F06081 | non-negotiable | false | 10 |
| R12175 | Telemetry — token throughput emitted via M049 | cross-ref M049 | F06093 | non-negotiable | false | 10 |
| R12176 | Telemetry — energy savings ratio emitted via M049 | cross-ref M049 | F06067 | non-negotiable | false | 10 |
| R12177 | Telemetry — memory bandwidth usage emitted via M049 | cross-ref M049 | F06071 | non-negotiable | false | 10 |
| R12178 | Telemetry — ternary verify pass-rate emitted via M049 | cross-ref M049 | F06074 | non-negotiable | false | 10 |
| R12179 | Operational — sovereign-ternary-runtime.service systemd unit | architecture | F06118 | non-negotiable | false | 10 |
| R12180 | Operational — service pinned to CCD 0 cores 0-5 via CPUAffinity | architecture + cross-ref M070 | F06119 | non-negotiable | false | 10 |
| R12181 | Operational — service honors SIGTERM (graceful drain) | architecture | F06118 | non-negotiable | false | 10 |
| R12182 | Operational — service refuses to start with chain-break detected | cross-ref selfdef MS009 | F06087 | non-negotiable | false | 10 |
| R12183 | Operational — service refuses to start with missing MS003 keys | cross-ref selfdef MS003 | F06080 | non-negotiable | false | 10 |
| R12184 | Operational — service readiness probe at /run/sovereign-ternary/ready | architecture | F06118 | non-negotiable | false | 10 |
| R12185 | Operational — service liveness probe at /run/sovereign-ternary/alive | architecture | F06118 | non-negotiable | false | 10 |
| R12186 | Operational — service emits start/stop events via M049 | cross-ref M049 | F06081 | non-negotiable | false | 10 |
| R12187 | Operational — service Wants=sovereign-os.target | architecture | F06118 | non-negotiable | false | 10 |
| R12188 | Operational — service After=bootstrap-clear.service (M072 ordering) | architecture + cross-ref M072 | F06118 | non-negotiable | false | 10 |
| R12189 | Doctrinal preservation — `{-1, 0, +1}` verbatim notation | dump 781 | F06113 | non-negotiable | false | 10 |
| R12190 | Doctrinal preservation — `log_2(3) \approx 1.585` verbatim mathematical expression | dump 783 | F06114 | non-negotiable | false | 10 |
| R12191 | Doctrinal preservation — `BitNet b1.58` verbatim | dump 779 | F06115 | non-negotiable | false | 10 |
| R12192 | Doctrinal preservation — `bitnet.cpp` verbatim | dump 794 | F06115 | non-negotiable | false | 10 |
| R12193 | Doctrinal preservation — `T-MAC` verbatim | dump 794 | F06115 | non-negotiable | false | 10 |
| R12194 | Doctrinal preservation — verbatim quotes never paraphrased | operator standing direction | F06116 | non-negotiable | false | 10 |
| R12195 | Doctrinal preservation — info-hub indexes 1-bit paradigm as second-brain entry | operator standing direction "second-brain" | F06117 | non-negotiable | false | 10 |
| R12196 | Doctrinal preservation — Von Neumann bottleneck reference preserved verbatim | dump 777 | F06036 | non-negotiable | false | 10 |
| R12197 | Doctrinal preservation — operator words "you cannot invent crap" preserved | operator standing direction | F06116 | non-negotiable | false | 10 |
| R12198 | Doctrinal preservation — Microsoft BitNet b1.58 attribution preserved | dump 779 | F06037 | non-negotiable | false | 10 |
| R12199 | Doctrinal preservation — conditional-allocation framing preserved | dump 785 | F06042 | non-negotiable | false | 10 |
| R12200 | Doctrinal preservation — energy-efficiency claim preserved | dump 791 | F06047 | non-negotiable | false | 10 |
| R12201 | Operator UX — operator may toggle ternary inference on/off per profile | operator standing direction "everything can be turned on and off" | F06090 | non-negotiable | false | 10 |
| R12202 | Operator UX — operator may select ternary model preference per profile | cross-ref selfdef MS040 | F06090 | non-negotiable | false | 10 |
| R12203 | Operator UX — operator may set energy-savings budget alert thresholds | architecture | F06091 | non-negotiable | false | 10 |
| R12204 | Operator UX — operator may compare ternary vs FP model accuracy | cross-ref M060 + M046 | F06085 | non-negotiable | false | 10 |
| R12205 | Operator UX — operator may view ternary inference progress in D-01 active sessions | cross-ref M060 | F06090 | non-negotiable | false | 10 |
| R12206 | Reproducibility — every ternary model load signed via MS003 | cross-ref selfdef MS003 | F06080 | non-negotiable | false | 10 |
| R12207 | Reproducibility — model weight digest signed at load + recorded in /var/lib/sovereign-os/ternary-models/ | architecture + cross-ref selfdef MS003 | F06054 | non-negotiable | false | 10 |
| R12208 | Reproducibility — model signature verified at every inference start | cross-ref selfdef MS003 | F06090 | non-negotiable | false | 10 |
| R12209 | Reproducibility — signature mismatch emits OCSF Detection 2004 + halts inference | cross-ref selfdef MS026 | F06088 | non-negotiable | false | 10 |
| R12210 | Reproducibility — model load + verify recorded in MS009 audit chain | cross-ref selfdef MS009 | F06087 | non-negotiable | false | 10 |
| R12211 | Closing — 1-bit paradigm covers dump 777-783 verbatim | dump 777-783 | F06036 | non-negotiable | false | 10 |
| R12212 | Closing — Elimination of multiplication covers dump 785-791 verbatim | dump 785-791 | F06042 | non-negotiable | false | 10 |
| R12213 | Closing — Packing + frameworks cover dump 794-795 verbatim | dump 794-795 | F06054 | non-negotiable | false | 10 |
| R12214 | Closing — sovereign-os catalog at 72/72 milestones | architecture | F06120 | non-negotiable | false | 10 |
| R12215 | Closing — combined ecosystem 116 milestones | architecture | F06120 | non-negotiable | false | 10 |
| R12216 | Closing — combined R-rows ~22800 | architecture | F06120 | non-negotiable | false | 10 |
| R12217 | Closing — combined enforced sub-reqs ~228000 | architecture | F06120 | non-negotiable | false | 10 |
| R12218 | Closing — every R-row carries 10 hard non-negotiable sub-requirements | operator standing direction | F06036 | non-negotiable | false | 10 |
| R12219 | Closing — direct-to-main commits authorized | operator standing direction | F06120 | non-negotiable | false | 10 |
| R12220 | Closing — sovereignty preserved (peace machine axiom) | cross-ref M059 + operator standing direction | F06120 | non-negotiable | false | 10 |
| R12221 | Closing — boundary respected (sovereign-os runs ternary inference; selfdef IPS enforces boundaries) | operator standing direction | F06107 | non-negotiable | false | 10 |
| R12222 | Closing — cross-repo binding only through MS007 8/8 SATURATED typed mirrors | cross-ref selfdef MS007 | F06076 | non-negotiable | false | 10 |
| R12223 | Closing — every commit signs via selfdef MS003 | cross-ref selfdef MS003 | F06080 | non-negotiable | false | 10 |
| R12224 | Closing — every commit emits M049 trace event | cross-ref M049 | F06081 | non-negotiable | false | 10 |
| R12225 | Closing — Trinity Pulse Core fully manifested across M066+M067+M070+M073 | cross-ref M066 + M067 + M070 | F06064 | non-negotiable | false | 10 |
| R12226 | Closing — ternary runtime + AVX-512 path + CCD 0 placement form coherent Pulse stack | cross-ref M066 + M070 + dump 1024 | F06065 | non-negotiable | false | 10 |
| R12227 | Closing — VNNI fusion (M074 pending) completes hardware-side Pulse manifestation | cross-ref M074 (pending) | F06066 | non-negotiable | false | 10 |
| R12228 | Closing — operator may exempt specific models from ternary requirement (signed override) | architecture + cross-ref selfdef MS003 | F06075 | non-negotiable | false | 10 |
| R12229 | Closing — exempt models still tracked via MS007 mirror with non-ternary flag | cross-ref selfdef MS007 | F06078 | non-negotiable | false | 10 |
| R12230 | Closing — exempt models emit OCSF Configuration Change 5001 on grant | cross-ref selfdef MS026 | F06013 | non-negotiable | false | 10 |
| R12231 | Closing — exempt models composable with M040 production profile gates | cross-ref selfdef MS040 | F06108 | non-negotiable | false | 10 |
| R12232 | Closing — model registry composed from MS007 mirror + sovereign-os runtime model store | cross-ref selfdef MS007 + M048 | F06076 | non-negotiable | false | 10 |
| R12233 | Closing — model registry retains ternary + non-ternary models in unified view | cross-ref M060 | F06084 | non-negotiable | false | 10 |
| R12234 | Closing — model registry exposes per-model energy savings projection | architecture + dump 791 | F06067 | non-negotiable | false | 10 |
| R12235 | Closing — model registry surfaced via D-03 model health + D-11 adapter status | cross-ref M060 | F06084 | non-negotiable | false | 10 |
| R12236 | Closing — `sovereign ternary` CLI subcommand set integrated with `selfdef` CLI for cross-repo workflows | cross-ref selfdef MS043 | F06090 | non-negotiable | false | 10 |
| R12237 | Closing — info-hub knowledge layer preserves doctrinal lineage from BitNet b1.58 to local sovereign-os execution | operator standing direction "second-brain" | F06117 | non-negotiable | false | 10 |
| R12238 | Closing — operator standing direction "Respect the projects" upheld (ternary runtime = sovereign-os; selfdef enforces) | operator standing direction | F06107 | non-negotiable | false | 10 |
| R12239 | Closing — operator standing direction "Do not minimize" upheld (full ternary catalog with 170 R-rows) | operator standing direction | F06036 | non-negotiable | false | 10 |
| R12240 | Closing — M073 covers 1-bit ternary scope verbatim; M074 AVX-512 VNNI hardware fusion next | dump 770-797 + operator standing direction | F06120 | non-negotiable | false | 10 |

## Sub-requirements accounting

Every R-row carries 10 hard non-negotiable sub-requirements. Total = 170 R × 10 = **1,700 sub-requirements** for M073.

## Cross-references

- **M046** — LoRA Foundry (adapters target ternary base)
- **M048** — modules map (Compute Fabric)
- **M049** — observability + trace pipeline
- **M055** — failure modes (bandwidth saturation alert)
- **M058** — hardware-aware scheduler (BitLinear → Pulse CCD 0)
- **M060** — cockpit + dashboards (D-03 / D-04 / D-09 / D-10 / D-11)
- **M066** — Trinity Framework Genesis (Pulse Vector Core)
- **M067** — Custom Kernel Build (AVX-512 path)
- **M068** — ZFS Storage (model storage in tank/models)
- **M070** — Dual-CCD topology (Pulse on CCD 0)
- **M072** — Bootstrap Verification Checklist (Check 01 AVX-512 instruction presence)
- **M074** — AVX-512 VNNI hardware fusion (pending)
- **M076** — 3 load-balancing profiles (pending; Ultra-Sovereign Efficiency uses ternary)
- **selfdef MS003** — selfdef-signing
- **selfdef MS007** — typed-mirror crate scheme (sovereign-ternary-runtime-mirror)
- **selfdef MS009** — replay validator
- **selfdef MS026** — observability + OCSF event emission
- **selfdef MS035** — capability tokens (capability_word.compute_mode)
- **selfdef MS036** — sandbox tiers
- **selfdef MS038** — network boundary
- **selfdef MS039** — authority levels (model load = L5 Commit)
- **selfdef MS040** — six-profile authority matrix
- **selfdef MS041** — commit authority (adapter promotion = L6 Persist)
- **selfdef MS043** — IPS operator surface (CLI integration)

## Schema

```
schema_version: "1.0.0"
milestone_id: M073
parent: sovereign-os
epics: 10
modules: 17
features: 85
requirements: 170
sub_requirements_per_requirement: 10
total_sub_requirements: 1700
source_dump_lines: 770-797 (Section 15: The Low-Bit Paradigm)
ternary_weight_set: "{-1, 0, +1}"
storage_width: "log_2(3) ≈ 1.585 bits per parameter"
arithmetic_shift:
  multiplication: "replaced with conditional allocation"
  plus_one: "activation added to accumulator"
  minus_one: "activation subtracted from accumulator"
  zero: "no-op, bypassed entirely"
frameworks: [bitnet.cpp, T-MAC]
hardware_target: "AVX-512 ZMM registers via Pulse Core (CCD 0)"
typed_mirror_crate: sovereign-ternary-runtime-mirror
catalog_status:
  sovereign_os: 72/72 milestones
  selfdef: 44/44 milestones
  combined: 116 milestones
```
