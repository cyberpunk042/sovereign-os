#!/usr/bin/env python3
"""scripts/intelligence/architecture-qa.py — R355 (E10.M3) +
R357 (E10.M4) concepts extension.

Operator-pull entry-point for the SAIN-01 master spec's verbatim
§13 Architectural Q&A Matrix + §14 Critical Edge Cases & Operational
Gotchas + §15-16 1-Bit Paradigm & Hardware Fusion concepts. Surfaces
operator-stated architectural rationale + per-board edge cases +
hardware-fusion explanations as discoverable operator-pull verbs.

Until R355, operator's §13 rationale ("why Debian 13?", "why
sync=always?", "why -march=znver5?", "why bindeb-pkg?") + §14 gotchas
(dual-GPU lane asymmetry, Secure Boot MOK blockades, OPNsense
bridging + Tetragon disconnects) lived only in the master spec text
under docs/src/sain-01-master-spec.md. No operator-pull verb made
them queryable by topic.

R355 catalogs both:
  - Q&A items from §13 (operator-verbatim question + answer + tags)
  - Gotchas from §14 (operator-named edge case + prevention + tags)

CLI:
  architecture-qa.py questions          [--tag T] [--config P] [--json|--human]
  architecture-qa.py gotchas            [--tag T] [--config P] [--json|--human]
  architecture-qa.py concepts           [--tag T] [--config P] [--json|--human]
  architecture-qa.py show <id>          [--config P] [--json|--human]
  architecture-qa.py search <substring> [--config P] [--json|--human]

Operator-overlay (R283/SDD-030): /etc/sovereign-os/architecture-qa.toml
adds operator-authored Q&A or gotchas (e.g. operator notes a new
edge case from a hardware shift).

Exit codes:
  0  rendered
  1  unknown id / no matches
  2  usage
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
try:
    from operator_overlay import load_with_overlay  # type: ignore
except Exception:  # pragma: no cover
    load_with_overlay = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R355"
SDD_VECTOR = "E10.M3"


# ── §13 Architectural Q&A Matrix (verbatim from master spec) ─────
#
# Each entry binds:
#   - id              short slug (Q-NN)
#   - question        operator-verbatim question (NO REPHRASING)
#   - answer          operator-verbatim answer (NO REPHRASING)
#   - tags            searchable tags
#   - spec_ref        master spec section reference
ARCHITECTURE_QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "Q-01",
        "question": ("Why choose Debian 13 (Trixie) over enterprise-grade "
                      "Red Hat derivatives or bleeding-edge Arch Linux "
                      "distributions for an AI Orchestration Node?"),
        "answer": ("Arch Linux introduces excessive rolling upstream "
                    "entropy. A breaking package upgrade can compromise "
                    "out-of-tree kernel interfaces (like ZFS-DKMS or "
                    "proprietary NVIDIA compute stacks) at runtime "
                    "without warning. Conversely, enterprise Red Hat "
                    "variations backport heavily mutated patches into "
                    "antiquated kernels, generating artificial friction "
                    "during custom compilations. Debian 13 offers a "
                    "pristine upstream GNU foundation, combining modern "
                    "libraries (GCC 14) with a predictable development "
                    "baseline, making it the perfect substrate for "
                    "building optimized binaries."),
        "tags": ["distro-choice", "debian-13", "trixie", "stability",
                 "kernel-interfaces", "substrate"],
        "spec_ref": "master spec §13 (Q1 verbatim)",
    },
    {
        "id": "Q-02",
        "question": ("Why map the multi-agent context files (CLAUDE.md, "
                      "etc.) to a custom ZFS pool set to sync=always "
                      "instead of using standard ext4/XFS filesystems "
                      "with default parameters?"),
        "answer": ("Standard Linux filesystems utilize lazy write "
                    "page-caching mechanisms. If an agent writes an "
                    "explicit state update to CLAUDE.md and immediately "
                    "transfers control to a downstream execution agent, "
                    "the secondary agent could query the underlying "
                    "block file before the operating system kernel "
                    "physically flushes the dirty cache pages to NVMe "
                    "silicon. This introduces immediate context race "
                    "conditions. Forcing sync=always via ZFS enforces "
                    "synchronous write paths across the transactional "
                    "pipeline, ensuring that execution blocks do not "
                    "process downstream routines until the state is "
                    "physically secured onto the hardware layer."),
        "tags": ["zfs", "sync-always", "state-fabric", "context-race",
                 "tank-context", "multi-agent", "atomic-write"],
        "spec_ref": "master spec §13 (Q2 verbatim)",
    },
    {
        "id": "Q-03",
        "question": ("What is the specific performance yield of building "
                      "a custom kernel using -march=znver5 compared to "
                      "generic distribution kernels (-march=x86-64-v3)?"),
        "answer": ("Generic distribution kernels utilize "
                    "common-denominator instruction targets (x86-64-v3 "
                    "or v4) to maintain wide physical deployment "
                    "compatibility. This locks out the unique "
                    "microarchitectural advantages of the AMD Zen 5 "
                    "core layout. Compiling natively with -march=znver5 "
                    "exposes the full execution profile to the "
                    "compiler: it leverages specific instruction "
                    "latencies, branch prediction models, optimized "
                    "caching alignments, and natively executes code "
                    "inside single-cycle 512-bit wide AVX-512 vector "
                    "pipelines. For computational tasks processing "
                    "large local numerical models or parsing massive "
                    "context vectors via customized WASM/Assembly "
                    "runtimes, this bypasses the multi-cycle emulation "
                    "penalties incurred by lower instruction sets."),
        "tags": ["kernel-build", "znver5", "avx-512", "ryzen-9-9900x",
                 "march", "vectorization", "bitnet"],
        "spec_ref": "master spec §13 (Q3 verbatim)",
    },
    {
        "id": "Q-04",
        "question": ("How do we bypass the DKMS compilation failure loop "
                      "when booting a brand-new custom kernel version?"),
        "answer": ("When custom kernels are deployed via traditional "
                    "means, standard DKMS automations frequently fail "
                    "to bind properly due to missing version flags or "
                    "non-standard naming schemes inside your custom "
                    "/usr/src/linux-headers-* configurations. We "
                    "systematically negate this issue by outputting the "
                    "compilation directly into official internal "
                    "Debian-wrapped archive structures (bindeb-pkg). "
                    "This ensures the generated package implicitly "
                    "updates the system package registry with precise "
                    "dependency structures, ensuring that zfs-dkms "
                    "tracks, compiles, and injects its kernel modules "
                    "automatically on every system update."),
        "tags": ["dkms", "bindeb-pkg", "custom-kernel", "zfs-dkms",
                 "kernel-module", "package-registry"],
        "spec_ref": "master spec §13 (Q4 verbatim)",
    },
]


# ── §14 Critical Edge Cases & Operational Gotchas (verbatim) ─────
ARCHITECTURE_GOTCHAS: list[dict[str, Any]] = [
    {
        "id": "G-01",
        "name": "Dual GPU Lane Asymmetry & Bandwidth Throttle",
        "context": ("The ASUS ProArt X870E-Creator motherboard shares "
                     "internal high-speed PCIe lanes coming off the "
                     "Ryzen 9 9900X CPU. When you operate a dual GPU "
                     "layout (e.g., matching your future NVIDIA RTX PRO "
                     "6000 Blackwell with your current RTX 3090), the "
                     "physical top two PCIe 5.0 slots drop down from "
                     "an isolated x16 lanes execution mode to a shared "
                     "x8 / x8 execution topology."),
        "gotcha": ("If an agent tries to load a sprawling model across "
                    "both cards simultaneously, data passing through the "
                    "PCIe system bus will experience increased latency "
                    "compared to a single slot execution layout."),
        "prevention": ("You must hard-code model partitioning scripts "
                        "to optimize execution allocations based on "
                        "VRAM capacity. Load the core attention layers "
                        "and high-frequency context loops entirely "
                        "inside the primary card's high-speed VRAM "
                        "allocation window to prevent excessive data "
                        "bouncing over the shared x8 bus lane."),
        "tags": ["pcie", "dual-gpu", "x8-x8", "x870e-creator", "lane-split",
                 "bifurcation", "model-partitioning"],
        "spec_ref": "master spec §14 (gotcha 1 verbatim)",
        "related_verbs": [
            "sovereign-osctl pcie-lanes --json",
            "sovereign-osctl gpu-card-advisor --json",
            "sovereign-osctl model-build plan <base> --recipe quantize-awq-int4",
        ],
    },
    {
        "id": "G-02",
        "name": "Secure Boot Machine Owner Key (MOK) Blockades",
        "context": ("If your system motherboard has Secure Boot fully "
                     "initialized in the UEFI firmware subsystem, your "
                     "custom-built 6.12-znver5 kernel along with the "
                     "compiled ZFS/NVIDIA kernel modules will "
                     "immediately be rejected by the bootloader at "
                     "startup, causing a catastrophic kernel panic or "
                     "silent boot failure."),
        "gotcha": ("Third-party binary objects compiled outside "
                    "distribution automated code signers lack "
                    "recognized cryptographic validation keys."),
        "prevention": ("You must generate a local Machine Owner Key "
                        "(MOK) cryptographic pair using openssl. Enroll "
                        "the public certificate target into the "
                        "physical system firmware via the mokutil "
                        "console utility during initialization, and "
                        "force your custom build wrappers to sign the "
                        "resulting kernel image and DKMS artifacts "
                        "before reboot sequences are initiated."),
        "tags": ["secure-boot", "mok", "uefi", "custom-kernel",
                 "zfs-dkms", "nvidia-dkms", "signing", "mokutil"],
        "spec_ref": "master spec §14 (gotcha 2 verbatim)",
        "related_verbs": [
            "# openssl req -new -x509 -newkey rsa:2048 -keyout MOK.key "
            "-out MOK.crt -nodes -days 3650 -subj '/CN=Sovereign Node/'",
            "# mokutil --import MOK.crt",
            "sovereign-osctl bios-directives show secure-boot",
        ],
    },
    {
        "id": "G-03",
        "name": "OPNsense WAN/LAN Bridging and Tetragon Interface Dropouts",
        "context": ("Your network design separates management traffic "
                     "(Intel 2.5GbE) from data processing paths "
                     "(Marvell 10GbE). If your OPNsense/SD-WAN firewall "
                     "dynamically re-shuffles interface addresses or "
                     "drops a lease connection along the management "
                     "path, the system loopback hooks used by the "
                     "Tetragon socket stream can experience buffer "
                     "disconnects."),
        "gotcha": ("If Tetragon drops its connection to the system "
                    "logging pipeline during a network reconfiguration "
                    "event, the guardian-core script will stall on its "
                    "read loop, blinding your real-time exploit "
                    "containment system."),
        "prevention": ("The guardian-core.service systemd unit file "
                        "must include explicit service binding controls "
                        "(BindsTo=tetragon.service) and include health "
                        "checking routines that instantly restart the "
                        "security loop if the local UNIX socket "
                        "encounters an end-of-file (EOF) exception."),
        "tags": ["network", "opnsense", "tetragon", "guardian-core",
                 "binds-to", "eof", "socket", "dual-nic"],
        "spec_ref": "master spec §14 (gotcha 3 verbatim)",
        "related_verbs": [
            "sovereign-osctl tetragon-status --json",
            "sovereign-osctl net-state --json",
            "systemctl cat sovereign-guardian-core",
        ],
    },
]


# ── §15-16 1-Bit Paradigm + Hardware Fusion concepts (verbatim) ──
#
# R357 extension: operator-verbatim explanatory blocks for the
# Pulse/CPU-bound architecture justification. Without first-classing
# these, operator had to read master spec doc to remember WHY ternary
# weights + AVX-512 + VNNI/VPDPBUSD are the inference floor.
ARCHITECTURE_CONCEPTS: list[dict[str, Any]] = [
    {
        "id": "C-01",
        "name": "Ternary weights eliminate floating-point multiplication",
        "explanation": ("The 1-bit evolution—pioneered by architectures "
                         "like Microsoft's BitNet b1.58—restricts every "
                         "single weight parameter in a network's linear "
                         "projections to a discrete ternary set: "
                         "{-1, 0, +1}. The designation 1.58-bit stems "
                         "from information theory: representing three "
                         "distinct states requires a minimum storage "
                         "width of log_2(3) ≈ 1.585 bits per parameter. "
                         "When your weights are strictly bounded to "
                         "ternary values, the fundamental arithmetic of "
                         "deep learning shifts from multiplication to "
                         "conditional allocation: if W_ij = +1, the "
                         "corresponding activation element is simply "
                         "added to the accumulator. If W_ij = -1, the "
                         "activation element is subtracted from the "
                         "accumulator. If W_ij = 0, the operation is "
                         "treated as a No-Op and bypassed entirely. By "
                         "substituting expensive floating-point "
                         "multiplications with basic integer additions "
                         "and subtractions, the computation becomes "
                         "vastly more energy-efficient and shifts the "
                         "performance profile away from raw TFLOPS "
                         "throughput toward memory bandwidth and "
                         "instruction pipeline optimization."),
        "tags": ["bitnet", "ternary", "1.58-bit", "no-op",
                 "energy-efficiency", "memory-bandwidth"],
        "spec_ref": "master spec §15 + §15.1 verbatim",
    },
    {
        "id": "C-02",
        "name": "AVX-512 ZMM register packs 64x INT8 per cycle",
        "explanation": ("The true advantage of your Ryzen 9 9900X lies "
                         "in its single-cycle, native AVX-512 (Zen 5) "
                         "implementation. While legacy architectures "
                         "double-pump two 256-bit execution units to "
                         "emulate a 512-bit instruction, Zen 5 exposes "
                         "true 512-bit wide ZMM registers. A single "
                         "512-bit ZMM vector register can hold and "
                         "manipulate 64 independent 8-bit integer "
                         "(INT8) activations simultaneously, or 128 "
                         "independent 4-bit packed activation snippets "
                         "(in newer quantized variations like BitNet "
                         "v2). Because ternary weights are packed at 2 "
                         "bits per parameter in host RAM (to align with "
                         "standard byte boundaries), specialized "
                         "low-level compilation frameworks (such as "
                         "bitnet.cpp and T-MAC) do not de-quantize "
                         "these weights back into floating-point "
                         "structures at execution time. Instead, they "
                         "leverage the AVX-512 vector path to run "
                         "Bit-wise Lookup Table (LUT) matrix operations."),
        "tags": ["avx-512", "zmm", "zen-5", "ryzen-9-9900x", "int8",
                 "bitnet-cpp", "t-mac", "single-cycle", "lut"],
        "spec_ref": "master spec §16 + §16.1 verbatim",
    },
    {
        "id": "C-03",
        "name": "VNNI / VPDPBUSD fused multiply-accumulate",
        "explanation": ("Using the VNNI (Vector Neural Network "
                         "Instructions) extension native to your CPU's "
                         "AVX-512 instruction block, multiple INT8 "
                         "activations are multiplied by packed ternary "
                         "weights and accumulated into 32-bit "
                         "destination registers in a fraction of a "
                         "clock cycle. This allows an ultra-low "
                         "precision model to execute on your local CPU "
                         "threads at speeds matching or exceeding human "
                         "reading rates (5–12 tokens/sec even at high "
                         "parameter scales), bypassing the PCIe bus "
                         "bottleneck entirely and leaving your GPU "
                         "memory unencumbered."),
        "tags": ["vnni", "vpdpbusd", "fma", "tokens-per-sec",
                 "pcie-bypass", "gpu-unencumbered", "cpu-inference"],
        "spec_ref": "master spec §16.1 verbatim (closing paragraph)",
    },
    {
        "id": "C-04",
        "name": "Dual-CCD Infinity Fabric cross-die penalty",
        "explanation": ("The Ryzen 9 9900X is an engineering "
                         "masterpiece, but it contains a distinct "
                         "structural boundary that will introduce "
                         "severe 'Friction' if ignored: it utilizes a "
                         "dual-CCD (Core Complex Die) design. CCD 0: "
                         "Cores 0–5 (Threads 0–11) — Accesses its own "
                         "local 32MB of L3 cache. CCD 1: Cores 6–11 "
                         "(Threads 12–23) — Accesses its own isolated "
                         "32MB of L3 cache. If the Conductor Agent "
                         "running your state logic is executing on "
                         "Core 2 (CCD 0), and it attempts to pipe a "
                         "vector array to a compilation runtime "
                         "executing on Core 8 (CCD 1), the data must "
                         "traverse the internal AMD Infinity Fabric. "
                         "This introduces an immediate L3 cache miss "
                         "and a massive cross-die latency penalty."),
        "tags": ["dual-ccd", "ccd-0", "ccd-1", "infinity-fabric",
                 "l3-cache", "ryzen-9-9900x", "core-isolation"],
        "spec_ref": "master spec §19 + §19.1 verbatim",
    },
    {
        "id": "C-05",
        "name": "Trinity Genesis: Pulse + Weaver + Auditor (decoupled SRP)",
        "explanation": ("Before we discussed motherboard lanes, "
                         "dual-GPU bifurcation, or specific kernel "
                         "flags, this ecosystem was conceived as a "
                         "pure, decoupled software trinity. THE PULSE "
                         "was conceived as a low-level, high-"
                         "performance assembly kernel utilizing MASM "
                         "(Microsoft Macro Assembler) and raw "
                         "WebAssembly (Wasm) primitives. Its sole "
                         "responsibility was bit-plane transposition "
                         "and accelerating low-bit mathematical "
                         "matrices directly on the bare iron. "
                         "THE WEAVER was designed as a lightweight "
                         "orchestration engine. Instead of spinning up "
                         "massive, bloated operating system images or "
                         "slow virtual machines to run sub-agents, "
                         "The Weaver used structured Wasm-based "
                         "sandboxing to dynamically isolate and weave "
                         "together multiple agent execution contexts. "
                         "THE AUDITOR was established as the "
                         "uncompromised security, logging, and "
                         "validation framework of the ecosystem. Its "
                         "single responsibility was to ensure that no "
                         "executing agent could deviate from the core "
                         "rules laid out in the system's manifest, "
                         "acting as an automated, immediate circuit "
                         "breaker against code regressions or "
                         "unauthorized execution escapes."),
        "tags": ["trinity", "pulse", "weaver", "auditor", "srp",
                 "genesis", "decoupled", "masm", "wasm", "bit-plane"],
        "spec_ref": "master spec Block 6 §Modules 1/2/3 verbatim",
    },
    # ── R360 (E10.M5) extension — 5 more verbatim concepts ────────
    {
        "id": "C-06",
        "name": "Layered Responsibility Mapping (Conductor / Logic Engine / Oracle Core)",
        "explanation": ("The Conductor Agent (CPU Bound): Evaluates "
                         "incoming user intent, updates CLAUDE.md, "
                         "enforces state rules in SOUL.md, and branches "
                         "the operational tree. Runtime Selection: "
                         "Natively compiled 1-bit / Ternary BitNet "
                         "models executing via bitnet.cpp pinned "
                         "directly to high-priority CPU cores. "
                         "Justification: State orchestration requires "
                         "instantaneous branching and low latency for "
                         "small context blocks. Executing this on the "
                         "CPU via AVX-512 prevents constant small-"
                         "kernel context-switching on the GPUs. "
                         "The Logic Engine (GPU 0 - RTX 3090): Heavy-"
                         "duty parsing, regular expression extraction, "
                         "structural JSON compilation, and fast text "
                         "embedding generation. Mid-scale quantized "
                         "models (e.g., Llama-3-70B running at a highly "
                         "dense Q4_K_M or IQ4_NL quantization profile) "
                         "managed via a dedicated Podman container "
                         "bridge. Justification: Balances high "
                         "processing throughput against the physical "
                         "constraint of a 24GB VRAM ceiling. "
                         "The Oracle Core (GPU 1 - Blackwell PRO 6000): "
                         "Extended, multi-turn recursive reasoning, "
                         "complex architectural analysis, codebase "
                         "validation, and large historical context "
                         "verification. Full-precision FP16 or "
                         "uncompromised high-precision models utilizing "
                         "the massive 96GB Blackwell memory pool. "
                         "Justification: Complete freedom from "
                         "quantization degradation allows for absolute "
                         "accuracy during complex system optimization."),
        "tags": ["srp", "conductor", "logic-engine", "oracle-core",
                 "blackwell", "rtx-3090", "rtx-pro-6000", "q4_k_m",
                 "iq4_nl", "fp16", "podman", "bitnet-cpp"],
        "spec_ref": "master spec §17.1 verbatim (Layered Responsibility Mapping)",
    },
    {
        "id": "C-07",
        "name": "Native Guardian Event Loop (eBPF Tetragon listener)",
        "explanation": ("To replace the legacy Windows-centric "
                         "SecureToast.ps1 concept without introducing "
                         "visual or network bloat, we introduce a "
                         "lightweight, native Linux event supervisor. "
                         "This daemon listens to the local Tetragon "
                         "eBPF UNIX socket and acts as an autonomous "
                         "circuit breaker. The Guardian Daemon "
                         "(/usr/local/bin/guardian-core) reads raw JSON "
                         "stream from the kernel eBPF filter. Parse "
                         "for policy trigger actions labeled as "
                         "SIGKILL. The systemd unit MUST include "
                         "BindsTo=tetragon.service so the Guardian "
                         "restarts on Tetragon socket EOF — otherwise "
                         "the guardian-core script will stall on its "
                         "read loop, blinding your real-time exploit "
                         "containment system."),
        "tags": ["guardian-core", "tetragon", "ebpf", "sigkill",
                 "binds-to", "auditor", "circuit-breaker",
                 "unix-socket", "securetoast"],
        "spec_ref": "master spec §10 + §14 G-03 verbatim",
    },
    {
        "id": "C-08",
        "name": "Atomic State Transition Protocol (O_DIRECT + O_SYNC + rename)",
        "explanation": ("To ensure that state adjustments across "
                         "CLAUDE.md, SOUL.md, and IDENTITY.md happen "
                         "without filesystem lag or concurrent write "
                         "collisions, The Weaver executes a strict, "
                         "lockless loopback write sequence on the ZFS "
                         "layer. The Weaver thread reads atomic input "
                         "from memory-mapped /mnt/vault/context/"
                         "CLAUDE.md, processes the state mutation "
                         "(AVX-512 pinned), writes via O_DIRECT / "
                         "POSIX AIO to ZFS Pool tank/context "
                         "(sync=always) for atomic NVMe block commit, "
                         "then broadcasts the state-synced "
                         "notification via gRPC. The python primitive "
                         "uses os.open with O_WRONLY | O_CREAT | "
                         "O_TRUNC | O_DIRECT | O_SYNC flags, "
                         "memory-aligned encoding for NVMe physical "
                         "block alignment (4K boundary), and atomic "
                         "rename so no reader ever views a partially "
                         "written file."),
        "tags": ["weaver", "atomic-state", "o_direct", "o_sync",
                 "rename", "claude-md", "soul-md", "4k-boundary",
                 "posix-aio", "zfs-sync-always"],
        "spec_ref": "master spec §21 + §21.1 verbatim",
    },
    {
        "id": "C-09",
        "name": "Consolidated Execution Strategy (5 Phases I-V)",
        "explanation": ("When you transpose this data into a new "
                         "context, instruct the downstream agent to "
                         "execute the deployment in this strict order: "
                         "Phase I (Iron Validation): Execute Section "
                         "5.1 (friction-audit) to verify the x8/x8 "
                         "hardware lane topology on the ProArt board "
                         "before compiling a single dependency. "
                         "Phase II (The Engine): Build the custom "
                         "Kernel 6.12 in tmpfs using the precise "
                         "compiler flags specified in Section 2.2 "
                         "(-march=znver5). "
                         "Phase III (The OS Image): Assemble the "
                         "Sovereign OS .iso using the exact "
                         "configuration paths from Section 3. "
                         "Phase IV (The File System): Initialize the "
                         "ZFS NVMe pool applying the custom block "
                         "sizes and synchronization profiles outlined "
                         "in Section 4.1 and Section 7.2. "
                         "Phase V (The Perimeter): Initialize Tetragon "
                         "and launch the Native Guardian Loop (Section "
                         "10) to secure the 120GB multi-GPU execution "
                         "array. This artifact is complete, "
                         "deterministic, and self-contained. No hacks, "
                         "no shortcuts, no compromises."),
        "tags": ["phase-i", "phase-ii", "phase-iii", "phase-iv",
                 "phase-v", "iron-validation", "engine", "os-image",
                 "file-system", "perimeter", "deployment-order"],
        "spec_ref": "master spec §11 verbatim (Consolidated Execution Strategy)",
    },
    {
        "id": "C-11",
        "name": "Operational Logic / Vibe Manager (120GB total VRAM tiered execution fabric)",
        "explanation": ("The orchestration layer treats the 120GB total "
                         "VRAM as a tiered execution fabric. Primary "
                         "Reasoning: Hosted on the 96GB Blackwell "
                         "(Direct Host). Speculative Decoding: Smaller "
                         "draft models run on the 24GB 3090 (VFIO "
                         "Sandbox). State Persistence: The 9900X "
                         "manages the 'Vibe' by updating state files "
                         "in the tank/context ZFS dataset, ensuring "
                         "atomic writes and data integrity. The context "
                         "management of your multi-agent architecture "
                         "is driven by a highly specific file-state "
                         "matrix mapped to the high-safety ZFS dataset "
                         "(tank/context) with strict synchronization "
                         "enforcement."),
        "tags": ["vibe-manager", "120gb-vram", "tiered-execution",
                 "primary-reasoning", "speculative-decoding", "vfio-sandbox",
                 "state-persistence", "tank-context", "atomic-writes",
                 "9900x", "blackwell-96gb", "rtx-3090-24gb"],
        "spec_ref": "master spec §5 + §7 verbatim (Operational Logic / Vibe Manager)",
    },
    {
        "id": "C-12",
        "name": "Container Build AVX-512 Vectorization (Dockerfile env vars)",
        "explanation": ("The primary reason for selecting the Ryzen 9 "
                         "9900X is its single-cycle, native 512-bit "
                         "AVX-512 data path (unlike the double-pumped "
                         "256-bit execution models of previous "
                         "generations). The user-space container "
                         "runtimes must be forced to compile and "
                         "execute instructions using these vectors for "
                         "the 'Manager' agent routines. When building "
                         "containerized execution backends (e.g., "
                         "llama.cpp or custom WASM/Assembly runtimes) "
                         "inside your Podman infrastructure, the "
                         "following compiler hooks must be hard-coded "
                         "into your build pipelines to avoid fallback "
                         "emulation: "
                         "ENV CFLAGS=\"-march=znver5 -mavx512f "
                         "-mavx512dq -mavx512bw -mavx512vl -mavx512bf16 "
                         "-mavx512fp16\" + ENV CXXFLAGS=\"-march=znver5 "
                         "-mavx512f -mavx512dq -mavx512bw -mavx512vl "
                         "-mavx512bf16 -mavx512fp16\" + ENV GGML_AVX512=1 "
                         "+ ENV GGML_AVX512_VBMI=1 + ENV GGML_AVX512_VNNI=1 "
                         "to Force GGML/vLLM backends to explicitly "
                         "target the 512-bit vector paths."),
        "tags": ["dockerfile", "podman", "avx-512", "ggml", "vllm",
                 "znver5", "container-build", "manager-agent",
                 "fallback-emulation", "ggml-avx512-vnni"],
        "spec_ref": "master spec §9 + §9.1 verbatim (Low-Level Orchestration Vectorization)",
    },
    {
        "id": "C-13",
        "name": "Load Balancing Runtime Profiles (Asymmetric_Burst JSON)",
        "explanation": ("To implement this architecture "
                         "deterministically, you must construct "
                         "explicit runtime configuration profiles. "
                         "These profiles are ingested by the "
                         "orchestration layer to dynamically balance "
                         "model deployment across your hardware based "
                         "on current workload demands. Profile 2: "
                         "High-Concurrency Agent Burst Mode "
                         "(Asymmetric Load Balancing) — node_"
                         "allocation_profile: Asymmetric_Burst with "
                         "three allocations: conductor_01 on cpu with "
                         "core_mask 0-11 using bitnet.cpp engine "
                         "running BitNet-b1.58-13B; translator_01 on "
                         "cuda:0 with vram_limit_bytes 22548578304 "
                         "using vllm-vulkan engine running "
                         "Qwen-32B-Ternary-Quant; deep_reasoner_01 on "
                         "cuda:1 with vram_limit_bytes 94489280512 "
                         "using llama.cpp engine running "
                         "DeepSeek-R1-Distill-Llama-70B-FP16. The host "
                         "CPU coordinates state tracking while the "
                         "workloads are strictly distributed according "
                         "to VRAM capacity and compute generation."),
        "tags": ["runtime-profiles", "asymmetric-burst", "load-balancing",
                 "node-allocation-profile", "bitnet-13b",
                 "qwen-32b-ternary-quant", "deepseek-r1", "vllm-vulkan",
                 "llama-cpp", "vram-limit-bytes"],
        "spec_ref": "master spec §18 verbatim (Load Balancing & Runtime Profiles Profile 2)",
    },
    {
        "id": "C-14",
        "name": "Tetragon TracingPolicy verbatim (sovereign-kernel-fence)",
        "explanation": ("A native eBPF profile running inside Tetragon "
                         "provides structural security without high "
                         "application-layer parsing overhead. This "
                         "architecture monitors container execution "
                         "contexts dealing directly with model "
                         "variables. The operator-verbatim §4 "
                         "TracingPolicy YAML: "
                         "apiVersion: cilium.io/v1alpha1 / kind: "
                         "TracingPolicy / metadata.name: "
                         "\"sovereign-kernel-fence\" / spec.kprobes "
                         "with call: \"sys_execve\", syscall: true, "
                         "args [index 0 type string], selectors "
                         "matchArgs operator NotIn values: "
                         "/usr/bin/python3, /usr/bin/nvidia-smi, "
                         "/usr/local/bin/vllm, /usr/bin/podman; "
                         "matchActions action: Sigkill. This script "
                         "terminates any thread requesting system call "
                         "execution outside the authorized execution "
                         "boundaries directly in kernel space, "
                         "maintaining system integrity. Implementation "
                         "note: shipped policy uses __x64_sys_execve "
                         "(architecture-specific syscall prefix per "
                         "modern Tetragon convention) and matchBinaries "
                         "(more efficient than matchArgs string match) "
                         "while preserving the operator's 4-binary "
                         "allowlist exactly: python3, nvidia-smi, vllm, "
                         "podman."),
        "tags": ["tetragon", "tracingpolicy", "ebpf", "sigkill",
                 "sovereign-kernel-fence", "sys_execve", "allowlist",
                 "kernel-space", "auditor", "podman", "vllm",
                 "nvidia-smi", "python3"],
        "spec_ref": "master spec §4 + §4.1 verbatim (Security & Isolation Perimeter)",
    },
    {
        "id": "C-15",
        "name": "Storage Architecture (ZFS dataset sharding per access pattern)",
        "explanation": ("ZFS on Linux (ZoL) is utilized to shard data "
                         "based on access patterns and reliability "
                         "requirements. Three datasets with explicit "
                         "operator-named purposes: tank/models with "
                         "recordsize 1M and lz4 compression and "
                         "Redundant Metadata — Optimized for 100GB+ "
                         "weight files; tank/context with recordsize "
                         "16k and zstd-9 compression and copies=2 — "
                         "Stores [SOUL.md], [IDENTITY.md]; tank/agents "
                         "with recordsize 128k and zstd-3 compression "
                         "and Standard redundancy — Stateful local "
                         "storage for agent fleets. The pool is "
                         "created via zpool create -o ashift=12 -O "
                         "compression=lz4 -m none tank /dev/nvme0n1 "
                         "/dev/nvme1n1 (2x PCIe 5.0 NVMe in ZFS RAID 0 "
                         "for maximum sequential throughput, 31.5 GB/s "
                         "target). Per-dataset settings applied via "
                         "zfs create + zfs set commands per the §4.1 "
                         "ZFS Storage Tuning Matrix."),
        "tags": ["zfs", "tank-models", "tank-context", "tank-agents",
                 "recordsize", "compression", "lz4", "zstd-9", "zstd-3",
                 "copies", "redundant-metadata", "raid-0", "nvme",
                 "31.5gb-s", "ashift-12"],
        "spec_ref": "master spec §3 + §4.1 verbatim (Storage Architecture + Tuning Matrix)",
    },
    {
        "id": "C-16",
        "name": "Hardware Infrastructure Table (operator-verbatim 6-row spec)",
        "explanation": ("Section 1.1 Core Components — operator-verbatim "
                         "hardware table: CPU AMD Ryzen 9 9900X (Rationale: "
                         "Single-cycle AVX-512 (512-bit data path) for "
                         "orchestration throughput); Motherboard ASUS "
                         "ProArt X870E-Creator (Rationale: Dual PCIe 5.0 "
                         "lanes; IOMMU topology support for VFIO "
                         "isolation); GPU Primary RTX PRO 6000 Blackwell "
                         "(96GB) (Rationale: Primary inference engine; "
                         "96GB VRAM for large-scale model residence); "
                         "GPU Secondary RTX 3090 (24GB) (Rationale: "
                         "Sandbox isolation; speculative decoding or "
                         "security agent offloading); Memory 256GB DDR5 "
                         "(Initial: 128GB) (Rationale: High-capacity "
                         "system context for ZFS ARC and GGUF "
                         "offloading); Networking Marvell AQC113C 10GbE "
                         "(Rationale: Native high-speed model ingestion "
                         "from local storage). PCIe & Storage Topology: "
                         "Lane Symmetry Slot 1 (Blackwell) and Slot 2 "
                         "(3090) must operate in x8/x8 mode. Critical "
                         "Constraint: The M.2_2 slot must remain empty. "
                         "Occupying M.2_2 triggers bifurcation that "
                         "drops Slot 2 to x4, compromising the "
                         "'Magician' symmetry. Storage: 2x PCIe 5.0 NVMe "
                         "in ZFS RAID 0 for maximum sequential "
                         "throughput (31.5 GB/s target)."),
        "tags": ["hardware", "ryzen-9-9900x", "asus-proart",
                 "x870e-creator", "rtx-pro-6000", "rtx-3090", "96gb",
                 "24gb", "256gb-ddr5", "marvell-aqc113c", "10gbe",
                 "pcie-5", "m2_2-empty", "x8-x8", "magician-symmetry",
                 "zfs-raid-0", "31.5gb-s"],
        "spec_ref": "master spec §1 + §1.1 + §1.2 verbatim (Hardware Infrastructure)",
    },
    {
        "id": "C-17",
        "name": "Summary of System Cohesion (operator's 3-point closing)",
        "explanation": ("We have achieved a complete synthesis of your "
                         "technical vision: 1. The Pulse operates "
                         "inside CCD 0, leveraging native AVX-512 "
                         "vectors to stream 1-bit ternary logic at "
                         "hardware speeds. 2. The Weaver coordinates "
                         "session state within CCD 1, driving "
                         "synchronous, lockless file transactions "
                         "straight onto a highly specialized ZFS "
                         "layout. 3. The Auditor acts as the silent "
                         "kernel executor, using eBPF (Tetragon) paths "
                         "to immediately destroy any process "
                         "attempting to cross your defined operational "
                         "boundaries. The blueprint is complete, "
                         "unified, and engineered to standard."),
        "tags": ["summary", "synthesis", "pulse-ccd0", "weaver-ccd1",
                 "auditor", "ebpf", "ternary", "lockless-transactions",
                 "engineered-to-standard"],
        "spec_ref": "master spec §23 verbatim (Summary of System Cohesion)",
    },
    {
        "id": "C-18",
        "name": "Sovereign Forge Package List (sovereign.list.chroot verbatim)",
        "explanation": ("The Sovereign Forge live-build package list — "
                         "operator-verbatim §3.2 config/package-lists/"
                         "sovereign.list.chroot 12-package baseline: "
                         "nvidia-open-kernel-dkms / nvidia-driver / "
                         "nvidia-smi / nvidia-container-toolkit / "
                         "zfsutils-linux / zfs-dkms / podman / git / "
                         "curl / tmux / python3-minimal / python3-pip. "
                         "These packages are baked into the .iso via "
                         "live-build at Stage 2 (The Sovereign OS "
                         "Artifact); the resulting image enforces "
                         "system identity (/etc/os-release: NAME="
                         "\"Sovereign OS\" / ID=sovereign / "
                         "ID_LIKE=debian / VERSION_ID=\"1.0\") and "
                         "contains the pre-compiled hardware "
                         "abstraction layer (Stage 1 znver5 kernel "
                         ".deb + ZFS DKMS + NVIDIA 560+ driver stack)."),
        "tags": ["sovereign-forge", "live-build", "package-list",
                 "nvidia-open-kernel-dkms", "nvidia-container-toolkit",
                 "zfs-dkms", "podman", "python3-minimal",
                 "os-release", "sovereign-os-id", "stage-2"],
        "spec_ref": "master spec §3.2 verbatim (sovereign.list.chroot + os-release)",
    },
    {
        "id": "C-19",
        "name": "DFlash + Model Candidates (operator-verbatim dump-tail additions)",
        "explanation": ("Post-Block 7 operator-verbatim additions to "
                         "the dump (2026-05-15). DFlash: 'And there is "
                         "also Dflash I recently learned about that "
                         "somehow with code task on model that fit in "
                         "memory like any functional model in general "
                         "it can work 3 times faster, does not work on "
                         "creative tasks in general but interesting "
                         "topic and place of introspection and "
                         "knowledge'. Cross-ref: arxiv 2602.06036 "
                         "'DFlash: Block Diffusion for Flash "
                         "Speculative Decoding' (Z-Lab Feb 2026); "
                         "github.com/z-lab/dflash. Operator framing "
                         "'3x faster on code tasks, doesn't work on "
                         "creative' matches paper's reported pattern "
                         "(highest gains on math/code, moderate on "
                         "conversational). Model candidates: 'There is "
                         "also those I think will be good candidate in "
                         "general for the rtx pro 6000 96gb amongs "
                         "other we will add to the list': "
                         "huggingface.co/inclusionAI/Ling-2.6-flash "
                         "(107494M params, bailing_hybrid architecture, "
                         "MIT license); huggingface.co/nvidia/"
                         "Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16 "
                         "(33015M params, NemotronH_Nano_Omni_Reasoning"
                         "_V3 architecture, multimodal any-to-any, "
                         "license 'other')."),
        "tags": ["dflash", "speculative-decoding", "arxiv-2602.06036",
                 "z-lab", "ling-2.6-flash", "inclusionai",
                 "nemotron-3-nano-omni", "nvidia-30b", "multimodal",
                 "model-candidates", "pro-6000-96gb"],
        "spec_ref": ("master spec dump-tail operator additions "
                      "(2026-05-15, after Block 7)"),
    },
    {
        "id": "C-10",
        "name": "Wasm-to-AVX-512 AOT Pipeline (The Pulse implementation)",
        "explanation": ("When The Pulse processes low-bit matrix logic "
                         "via WebAssembly, it avoids standard JIT "
                         "(Just-In-Time) compilation bloat. Instead, "
                         "it uses an Ahead-Of-Time (AOT) compilation "
                         "lifecycle optimized via Cranelift or LLVM to "
                         "output native Zen 5 machine code. To execute "
                         "a ternary matrix step, the runtime takes "
                         "packed 2-bit weight pairs from memory and "
                         "uses the AVX-512 execution path to stream "
                         "instructions natively through the CPU "
                         "registers without unpacking overhead. The "
                         "VNNI / VPDPBUSD instruction executes Parallel "
                         "Fused Multiply-Accumulate into 32-bit "
                         "Integer Registers. When compiling the Wasm "
                         "execution layer natively on the node, the "
                         "toolchain runtime parameters must be locked "
                         "down to prevent generic x86 fallbacks: "
                         "WASMTIME_COMPARE_OPTIONS=\"-C "
                         "target-cpu=znver5 -C opt-level=3 -C "
                         "relaxed-simd=true\" plus taskset -c 0-11 "
                         "wasmtime compile --target znver5 -O speed "
                         "/mnt/vault/agents/pulse_core.wasm to enforce "
                         "explicit task execution on the native vector "
                         "cores (CCD 0) only."),
        "tags": ["wasm", "aot", "cranelift", "llvm", "znver5",
                 "wasmtime", "vnni", "vpdpbusd", "fused-multiply-accumulate",
                 "ccd-0", "pulse"],
        "spec_ref": "master spec §20 + §20.1 + §20.2 verbatim",
    },
]


# ── Loading + filtering ───────────────────────────────────────────
def load_state(overlay_path: Path | None) -> tuple[list[dict], list[dict], list[dict], dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    questions = list(ARCHITECTURE_QUESTIONS)
    gotchas = list(ARCHITECTURE_GOTCHAS)
    concepts = list(ARCHITECTURE_CONCEPTS)
    if load_with_overlay is not None:
        loaded = load_with_overlay(
            "architecture-qa",
            {"questions": [], "gotchas": [], "concepts": []},
            explicit_path=overlay_path,
        )
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
        if loaded.get("questions"):
            questions = list(loaded["questions"])
        if loaded.get("gotchas"):
            gotchas = list(loaded["gotchas"])
        if loaded.get("concepts"):
            concepts = list(loaded["concepts"])
    return questions, gotchas, concepts, meta


def filter_tag(items: list[dict], tag: str | None) -> list[dict]:
    if not tag:
        return items
    return [x for x in items if isinstance(x, dict)
            and tag in (x.get("tags") or [])]


def resolve_by_id(
    questions: list[dict], gotchas: list[dict], concepts: list[dict],
    item_id: str,
) -> tuple[dict | None, str]:
    """Returns (item_dict, kind) or (None, ''). kind ∈ {'question', 'gotcha', 'concept'}."""
    for q in questions:
        if isinstance(q, dict) and q.get("id") == item_id:
            return q, "question"
    for g in gotchas:
        if isinstance(g, dict) and g.get("id") == item_id:
            return g, "gotcha"
    for c in concepts:
        if isinstance(c, dict) and c.get("id") == item_id:
            return c, "concept"
    return None, ""


def search_items(
    questions: list[dict], gotchas: list[dict], concepts: list[dict],
    needle: str,
) -> tuple[list[dict], list[dict], list[dict]]:
    n = needle.lower()
    qm = [q for q in questions if isinstance(q, dict) and (
        n in (q.get("question") or "").lower()
        or n in (q.get("answer") or "").lower()
        or any(n in t for t in (q.get("tags") or []))
    )]
    gm = [g for g in gotchas if isinstance(g, dict) and (
        n in (g.get("name") or "").lower()
        or n in (g.get("context") or "").lower()
        or n in (g.get("gotcha") or "").lower()
        or n in (g.get("prevention") or "").lower()
        or any(n in t for t in (g.get("tags") or []))
    )]
    cm = [c for c in concepts if isinstance(c, dict) and (
        n in (c.get("name") or "").lower()
        or n in (c.get("explanation") or "").lower()
        or any(n in t for t in (c.get("tags") or []))
    )]
    return qm, gm, cm


# ── Renderers ─────────────────────────────────────────────────────
def render_questions_human(items: list[dict]) -> str:
    lines = ["── R355 architecture-qa questions (master spec §13 verbatim) ──"]
    for q in items:
        lines.append("")
        lines.append(f"  [{q.get('id')}]  {q.get('question')}")
        lines.append(f"    tags: {', '.join(q.get('tags') or [])}")
        lines.append(f"    spec: {q.get('spec_ref')}")
        lines.append(f"    → sovereign-osctl architecture-qa show {q.get('id')}")
    return "\n".join(lines) + "\n"


def render_gotchas_human(items: list[dict]) -> str:
    lines = ["── R355 architecture-qa gotchas (master spec §14 verbatim) ──"]
    for g in items:
        lines.append("")
        lines.append(f"  [{g.get('id')}]  {g.get('name')}")
        lines.append(f"    tags: {', '.join(g.get('tags') or [])}")
        lines.append(f"    spec: {g.get('spec_ref')}")
        lines.append(f"    → sovereign-osctl architecture-qa show {g.get('id')}")
    return "\n".join(lines) + "\n"


def render_question_show(q: dict) -> str:
    lines = [f"── R355 question: {q.get('id')} (master spec §13) ──"]
    lines.append("")
    lines.append("  QUESTION (operator verbatim):")
    for ln in (q.get("question") or "").split("\n"):
        lines.append(f"    {ln}")
    lines.append("")
    lines.append("  ANSWER (operator verbatim):")
    # word-wrap-ish for readability
    body = q.get("answer") or ""
    cur = "    "
    for word in body.split():
        if len(cur) + len(word) > 76 and cur.strip():
            lines.append(cur.rstrip())
            cur = "    "
        cur += word + " "
    if cur.strip():
        lines.append(cur.rstrip())
    lines.append("")
    lines.append(f"  spec ref: {q.get('spec_ref')}")
    lines.append(f"  tags:     {', '.join(q.get('tags') or [])}")
    return "\n".join(lines) + "\n"


def render_concept_show(c: dict) -> str:
    lines = [f"── R357 concept: {c.get('id')} — {c.get('name')} (master spec §15-16) ──"]
    lines.append("")
    lines.append("  EXPLANATION (operator verbatim):")
    body = c.get("explanation") or ""
    cur = "    "
    for word in body.split():
        if len(cur) + len(word) > 76 and cur.strip():
            lines.append(cur.rstrip())
            cur = "    "
        cur += word + " "
    if cur.strip():
        lines.append(cur.rstrip())
    lines.append("")
    lines.append(f"  spec ref: {c.get('spec_ref')}")
    lines.append(f"  tags:     {', '.join(c.get('tags') or [])}")
    return "\n".join(lines) + "\n"


def render_concepts_human(items: list[dict]) -> str:
    lines = ["── R357 architecture-qa concepts (master spec §15-16 + §19 verbatim) ──"]
    for c in items:
        lines.append("")
        lines.append(f"  [{c.get('id')}]  {c.get('name')}")
        lines.append(f"    tags: {', '.join(c.get('tags') or [])}")
        lines.append(f"    spec: {c.get('spec_ref')}")
        lines.append(f"    → sovereign-osctl architecture-qa show {c.get('id')}")
    return "\n".join(lines) + "\n"


def render_gotcha_show(g: dict) -> str:
    lines = [f"── R355 gotcha: {g.get('id')} — {g.get('name')} (master spec §14) ──"]
    for field, label in (
        ("context", "CONTEXT"),
        ("gotcha", "THE GOTCHA"),
        ("prevention", "PREVENTION"),
    ):
        body = g.get(field) or ""
        lines.append("")
        lines.append(f"  {label} (operator verbatim):")
        cur = "    "
        for word in body.split():
            if len(cur) + len(word) > 76 and cur.strip():
                lines.append(cur.rstrip())
                cur = "    "
            cur += word + " "
        if cur.strip():
            lines.append(cur.rstrip())
    if g.get("related_verbs"):
        lines.append("")
        lines.append("  RELATED OPERATOR VERBS:")
        for v in g["related_verbs"]:
            lines.append(f"    $ {v}")
    lines.append("")
    lines.append(f"  spec ref: {g.get('spec_ref')}")
    lines.append(f"  tags:     {', '.join(g.get('tags') or [])}")
    return "\n".join(lines) + "\n"


# ── Main ──────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="architecture-qa.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    for verb in ("questions", "gotchas", "concepts"):
        sp = sub.add_parser(verb)
        sp.add_argument("--tag")
        sp.add_argument("--config", type=Path)
        spg = sp.add_mutually_exclusive_group()
        spg.add_argument("--json", dest="fmt", action="store_const", const="json")
        spg.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")

    ps = sub.add_parser("show")
    ps.add_argument("item_id")
    ps.add_argument("--config", type=Path)
    psg = ps.add_mutually_exclusive_group()
    psg.add_argument("--json", dest="fmt", action="store_const", const="json")
    psg.add_argument("--human", dest="fmt", action="store_const", const="human")
    ps.set_defaults(fmt="json")

    psr = sub.add_parser("search")
    psr.add_argument("needle")
    psr.add_argument("--config", type=Path)
    psrg = psr.add_mutually_exclusive_group()
    psrg.add_argument("--json", dest="fmt", action="store_const", const="json")
    psrg.add_argument("--human", dest="fmt", action="store_const", const="human")
    psr.set_defaults(fmt="json")

    args = p.parse_args(argv)
    questions, gotchas, concepts, meta = load_state(getattr(args, "config", None))

    if args.cmd == "questions":
        items = filter_tag(questions, getattr(args, "tag", None))
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "tag_filter": getattr(args, "tag", None),
                "question_count": len(items),
                "questions": items,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_questions_human(items), end="")
        return 0 if items else 1

    if args.cmd == "gotchas":
        items = filter_tag(gotchas, getattr(args, "tag", None))
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "tag_filter": getattr(args, "tag", None),
                "gotcha_count": len(items),
                "gotchas": items,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_gotchas_human(items), end="")
        return 0 if items else 1

    if args.cmd == "concepts":
        items = filter_tag(concepts, getattr(args, "tag", None))
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": "R357",
                "sdd_vector": "E10.M4",
                "tag_filter": getattr(args, "tag", None),
                "concept_count": len(items),
                "concepts": items,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_concepts_human(items), end="")
        return 0 if items else 1

    if args.cmd == "show":
        item, kind = resolve_by_id(questions, gotchas, concepts, args.item_id)
        if item is None:
            print(json.dumps({
                "error": f"unknown id: {args.item_id}",
                "known_questions": [q.get("id") for q in questions if isinstance(q, dict)],
                "known_gotchas":   [g.get("id") for g in gotchas if isinstance(g, dict)],
                "known_concepts":  [c.get("id") for c in concepts if isinstance(c, dict)],
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 1
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "kind": kind,
                "item": item,
                "overlay": meta,
            }, indent=2))
        else:
            renderer = {
                "question": render_question_show,
                "gotcha":   render_gotcha_show,
                "concept":  render_concept_show,
            }[kind]
            print(renderer(item), end="")
        return 0

    if args.cmd == "search":
        qm, gm, cm = search_items(questions, gotchas, concepts, args.needle)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "needle": args.needle,
                "question_match_count": len(qm),
                "gotcha_match_count": len(gm),
                "concept_match_count": len(cm),
                "matched_questions": qm,
                "matched_gotchas": gm,
                "matched_concepts": cm,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R355+R357 search: '{args.needle}' ──")
            print(f"  {len(qm)} question / {len(gm)} gotcha / {len(cm)} concept match(es)")
            for q in qm:
                print(f"    [Q] {q.get('id')}: {(q.get('question') or '')[:60]}…")
            for g in gm:
                print(f"    [G] {g.get('id')}: {g.get('name')}")
            for c in cm:
                print(f"    [C] {c.get('id')}: {c.get('name')}")
        return 0 if (qm or gm or cm) else 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
