# SAIN-01 master specification (operator-readable synthesis)

> Operator-readable rendering of the SAIN-01 master spec — the
> architectural anchor for sovereign-os's default profile.
>
> The verbatim source is at info-hub
> `raw/dumps/2026-05-15-sain-01-master-spec-other-conversation-transposition.md`
> (1139 lines; sacrosanct; never modified). This doc synthesizes that
> source for operators, maps each section to the in-repo artifact that
> implements it, and flags what's not yet built.

---

## What SAIN-01 is

SAIN-01 (Sovereign AI Node 01) is the operator's reference AI workstation.
It is the **default profile** in sovereign-os and the architecture every
other profile is measured against.

The whole point is **sovereignty**: hardware native, operator-owned signing
chain, kernel-level perimeter, no phone-home, no SaaS, no opaque
abstractions between operator and silicon. Debian 13 is the Ark we start
from; everything else is operator-customized.

---

## Hardware foundation (verbatim from master spec § 1)

| Component | Specification | Why |
|---|---|---|
| **CPU** | AMD Ryzen 9 9900X (Zen 5) | Single-cycle native AVX-512 (true 512-bit ZMM registers; legacy Zens double-pumped 256-bit) |
| **Motherboard** | ASUS ProArt X870E-Creator | Dual PCIe 5.0 slots in x8/x8 symmetric · IOMMU topology for VFIO |
| **GPU primary** | RTX PRO 6000 Blackwell (96GB GDDR7) | Oracle Core — large-scale model residence; FP16 / un-quantized |
| **GPU secondary** | RTX 3090 (24GB GDDR6X) | Logic Engine — VFIO-isolated sandbox; speculative decoding |
| **Memory** | 256GB DDR5 (initial 128GB) | High system context + ZFS ARC headroom |
| **Storage** | 2× NVMe PCIe 5.0 in ZFS RAID-0 | 31.5 GB/s sequential target |
| **Network** | Marvell AQC113C 10GbE + Intel I226-V 2.5GbE | Asymmetric VLAN — mgmt vs data |

### Hardware constraints (operator MUST honor these)

- **PCIe lane symmetry**: Slot 1 (Blackwell) and Slot 2 (3090) MUST operate
  at x8/x8. The CPU has 24 usable PCIe lanes; this is the only symmetric
  configuration that runs both GPUs at full bandwidth.
- **M.2_2 MUST remain empty**. Populating it triggers bifurcation that drops
  Slot 2 to x4 and destroys execution symmetry. The friction-audit at
  build-time AND boot-time checks for this — see
  `scripts/hooks/pre-install/friction-audit-spec.sh` and
  `scripts/hooks/post-install/friction-audit-runtime.sh`.
- **Dual-CCD aware execution**: the 9900X has 2 Core-Complex-Dies
  (CCD0 = cores 0–5 → 32MB L3; CCD1 = cores 6–11 → 32MB L3). Crossing the
  Infinity Fabric between dies costs ~50–100ns. Workloads MUST pin to one
  CCD or accept the penalty. The Trinity (below) maps directly to this.

---

## The Trinity (master spec § 17 — "The Sovereign Trinity Framework")

Three independent, decoupled SRP-aligned modules. They map to the hardware
the same way the operator's "Zero to Hero" roadmap maps to the Single
Responsibility Principle.

```
                  +---------------------------------------+
                  |  THE "ZERO TO HERO" STATE MATRIX      |
                  +---------------------------------------+
                                      |
         +----------------------------+----------------------------+
         |                            |                            |
         v                            v                            v
+------------------+        +------------------+        +------------------+
|    THE PULSE     |        |    THE WEAVER    |        |   THE AUDITOR    |
| Low-Level Kernel |        | Orchestration    |        | eBPF / ZFS Pool  |
|  (AVX-512/MASM)  |        | (Wasm Sandbox)   |        |  (The Guardian)  |
+------------------+        +------------------+        +------------------+
         |                            |                            |
         v                            v                            v
[Bit-Plane Linear]          [Stateful Agent Fabric]     [Kernel Integrity]
```

### Module 1 — The Pulse (Vector Core)

**Responsibility**: bit-plane transposition + accelerating low-bit
mathematical matrices on bare iron via AVX-512.

**Hardware pinning**: CCD0 (cores 0–5; thread mask `0xfff` = threads 0–11).

**Runtime selection**:
- Wasm AOT-compiled via Cranelift/LLVM with `-C target-cpu=znver5`
  (master spec § 20 — the Wasm-to-AVX-512 AOT Pipeline)
- `bitnet.cpp` for 1-bit/ternary BitNet-b1.58 execution
- VNNI/VPDPBUSD instructions for packed INT8/INT4 inference

**Why it exists**: state orchestration needs instantaneous branching with
low latency on small context blocks. Doing it on the CPU via AVX-512
avoids constant small-kernel context-switching on the GPUs.

**Master spec content**: §§ 9, 15-16, 17 (Layered Responsibility Mapping),
20 (Wasm-to-AVX-512 AOT Pipeline).

**In-repo state**:
- `scripts/inference/backends/bitnet.py` exists as a placeholder.
- `scripts/inference/start-pulse.sh` exists with affinity-pinning groundwork.
- **NOT YET BUILT** as of this writing: real bitnet.cpp build (from source,
  znver5 flags, model fetch); Wasm AOT pipeline (Cranelift/wasmtime
  binary fetch, znver5 target wiring, sample `pulse_core.wasm`).
  Tracked in arc R152-R153.

### Module 2 — The Weaver (Sandboxed Fabric)

**Responsibility**: stateful agent fabric — Wasm-sandbox orchestration
+ atomic state transitions on the ZFS state-fabric files.

**Hardware pinning**: CCD1 cores 6–9 (thread mask `0xff000` = 12–19).

**Runtime selection**:
- Rootless Podman for sub-agent containers (no Docker daemon overhead)
- VFIO 3090 for the Logic Engine sandbox
- Atomic state writes via O_DIRECT + POSIX AIO + ZFS `sync=always` on
  `tank/context`

**State fabric** (master spec § 7):
```
/mnt/vault/context/
├── IDENTITY.md      # Immutable persona — RO to agents
├── SOUL.md          # Behavioral logic / long-term memory — RW via manager
├── AGENTS.md        # Sub-agent routing + hardware pinning map — RO to subs
└── CLAUDE.md        # Active session context — atomic append-only
```

The ZFS commands that materialize this:
```sh
zfs set sync=always tank/context
zfs set primarycache=all tank/context
zfs set logbias=latency tank/context
```

**Master spec content**: §§ 7 (Vibe State Fabric), 17 (SRP topology), 18
(load balancing profiles), 21 (Atomic State Transition Protocol).

**In-repo state**:
- `scripts/hooks/during-install/zfs-pool-create.sh` creates the pool.
- `scripts/hooks/during-install/zfs-datasets-create.sh` creates `tank/context`
  with the prescribed recordsize/compression/copies/sync settings per SDD-017.
- VFIO bind exists at `scripts/hooks/post-install/vfio-bind-3090.sh`.
- **NOT YET BUILT**: the atomic state transition protocol primitives
  (`scripts/weaver/atomic-state.py` per master spec § 21.1's Python blueprint).
  Tracked in R154.

### Module 3 — The Auditor (Immutable Gatekeeper)

**Responsibility**: kernel-level perimeter enforcement. SIGKILL processes
that violate policy. Atomic logs.

**Hardware pinning**: always-on, low-priority. Native eBPF runs in-kernel.

**Runtime selection**:
- Tetragon (Cilium) `TracingPolicy` — `sys_execve` allow-list per
  master spec § 6
- Guardian Daemon (`/usr/local/bin/guardian-core`) — Python supervisor
  reading the Tetragon UNIX socket and triggering `podman kill` +
  atomic append to `/mnt/vault/context/security_audit.log`

**Sample policy**: the master spec's `sovereign-kernel-fence` allow-list
is `python3 / nvidia-smi / vllm / podman`. Anything else attempting
`sys_execve` inside an agent container gets SIGKILL'd in-kernel.

**Master spec content**: §§ 4 (Tetragon policy), 6 (Real-Time Security
Perimeter Engine), 10 (Native Guardian Event Loop), 17 (the Auditor module).

**In-repo state**:
- `scripts/hooks/post-install/tetragon-policy-load.sh` loads the policy.
- `scripts/hooks/recurrent/tetragon-policy-verify.sh` re-checks daily.
- `sovereign-osctl perimeter {status, verify, reload}` operator surface.
- **NOT YET BUILT**: Guardian Daemon proper. The Tetragon policy alone is
  most of what the master spec demands — the Guardian's `podman kill +
  log + native bell` flow is the missing 30%. Tracked in R155.
  (Possible the operator's `selfdef` repo is the actual home for this;
  cross-repo decision pending.)

---

## The 5-phase chronological pipeline (master spec § 12)

This is THE pipeline. The 9-step build at `scripts/build/01..09-*.sh`
materializes Phases I-III + portions of IV-V. The lifecycle hooks
(`scripts/hooks/{pre,during,post}-install`) materialize the rest.

```
+----------------------------+
| Phase I: Minimal Trixie    | -> Netinst, DEB822, Base Unfettered Userspace
+----------------------------+
              |
              v
+----------------------------+
| Phase II: Zen 5 Compilation| -> GCC 14, Native -march=znver5, Linux 6.12 Custom
+----------------------------+
              |
              v
+----------------------------+
| Phase III: Storage & DKMS  | -> ZFS Native Pool, Custom DKMS Module Hooking
+----------------------------+
              |
              v
+----------------------------+
| Phase IV: Edge Isolation   | -> Network Asymmetry, Podman Storage Mapping
+----------------------------+
              |
              v
+----------------------------+
| Phase V: Orchestration     | -> Tetragon eBPF, Guardian Daemon, State Fabric Mounts
+----------------------------+
```

### Phase I — Minimal Trixie Base

**Master spec section**: 12 Phase I.

**What happens**: Debian 13 (Trixie) netinst → expert install → no DE
selected, no `tasksel` extras → OpenSSH only → DEB822 sources.

**In repo**:
- `scripts/build/01-bootstrap-forge.sh` — installs the build toolchain.
- `config/preseed/sain-01.preseed.example.cfg` — operator-customizable
  netinst preseed (for unattended provisioning).
- `config/cloud-init/sain-01.user-data.example.yaml` — cloud-init path.

### Phase II — Zen 5 Kernel Compilation

**Master spec section**: 12 Phase II + § 2.

**What happens**: kernel source fetched into `/mnt/kernel_forge` (64GB
tmpfs by default; honors `SOVEREIGN_OS_FORGE_SIZE`) → `.config` hardened
(VFIO, IOMMU, ZFS, AQC10GbE, MT7925 WiFi 7) → compiled with
`KCFLAGS="-march=znver5 -O3 -mavx512f -mavx512dq -mavx512bw -mavx512vl -mavx512bf16 -mavx512fp16"`
→ `make -j$(nproc) bindeb-pkg` → resulting .debs land in `kernel-debs/`.

**In repo**:
- `scripts/build/02-kernel-fetch.sh` (shallow-clone the configured tag)
- `scripts/build/03-kernel-config.sh` (operator-customizable; profile-aware)
- `scripts/build/04-kernel-compile.sh` (bindeb-pkg + SOURCE_DATE_EPOCH
  reproducibility per SDD-019)

**Customization points**: `profiles/sain-01.yaml § kernel.config.enable / disable`
lets the operator add/remove specific kernel options without forking the
build script.

### Phase III — Storage Layer + DKMS

**Master spec sections**: 12 Phase III + § 3, 4.1.

**What happens**: ZFS DKMS installed → `tank` pool created
(`ashift=12 -O compression=lz4`) → 3 datasets created with the master spec's
exact recordsize/compression/copies/sync values:

| Dataset | Recordsize | Compression | Copies | Sync | Purpose |
|---|---|---|---|---|---|
| `tank/models` | 1M | lz4 | 1 (redundant metadata) | standard | 100GB+ model weight files; sequential read-optimized |
| `tank/context` | 16k | zstd-9 | **2** | **always** | State fabric (IDENTITY/SOUL/AGENTS/CLAUDE) — irreducible state needs durability |
| `tank/agents` | 128k | zstd-3 | 1 | standard | Agent runtime cache |

ZFS ARC clamped to 128GB (half of 256GB) via
`zfs-arc-tune.service` → `modprobe zfs zfs_arc_max=137438953472`.

**In repo**:
- `scripts/hooks/during-install/zfs-pool-create.sh`
- `scripts/hooks/during-install/zfs-datasets-create.sh`
- `scripts/hooks/post-install/zfs-arc-clamp.sh`
- `scripts/hooks/recurrent/zfs-scrub.sh` (weekly)

### Phase IV — Container + Network Edge Isolation

**Master spec sections**: 12 Phase IV + §§ 4.3 (VFIO), 8 (asymmetric networking).

**What happens**: Podman installed (rootless ready) → VFIO 3090 bound at
boot (`vfio-pci.ids=10de:2204,10de:1ad8` in kernel cmdline) → asymmetric
networking applied:
- `enp6s0` (Intel 2.5GbE) → mgmt VLAN 100, default gateway, DNS
- `enp5s0` (Marvell 10GbE) → data VLAN 200, MTU 9000 jumbo, no default gateway

**In repo**:
- `scripts/hooks/post-install/vfio-bind-3090.sh` (VFIO ✅)
- `scripts/hooks/post-install/network-vlan-config.sh` (generic VLAN
  renderer; profile-driven ✅)
- `scripts/network/render-asymmetric.sh` (R158: opinionated master
  spec § 8.1 verbatim renderer — VLAN 100/200, MTU 9000, addresses ✅)

### Phase V — Tetragon eBPF + Guardian + State Fabric Mount

**Master spec sections**: 12 Phase V + §§ 5, 6, 10.

**What happens**: Tetragon installed + `sovereign-kernel-fence` policy
loaded → Guardian Daemon (`guardian-core.service`) reads Tetragon's UNIX
socket and kills offending containers → friction-audit verifies x8/x8
PCIe link state + ZFS pool health + AVX-512 presence at every boot.

**In repo**:
- `scripts/hooks/post-install/tetragon-policy-load.sh` (✅)
- `scripts/hooks/recurrent/tetragon-policy-verify.sh` (✅)
- `scripts/auditor/guardian-core.py` (R155: eBPF circuit-breaker
  daemon ✅; master spec § 10 verbatim)
- `systemd/system/sovereign-guardian-core.service` (R155 ✅; master
  spec § 10.2 verbatim After=/Requires=tetragon.service)
- `scripts/weaver/atomic-state.py` (R154: master spec § 21 atomic
  state transitions for IDENTITY/SOUL/AGENTS/CLAUDE ✅)

**Operator inventory**: `sovereign-osctl bootstrap phases` (R162)
surfaces all 5 phases with ✓/✗ markers and JSON output for fleet
tooling.

---

## 3 runtime profiles (master spec § 18)

After the build is installed, the operator picks how the Trinity gets
worked. The master spec defines 3 explicit profiles. **These are not yet
materialized as `sovereign-osctl trinity profile <name>` picks**;
tracked in R150.

### Profile 1 — Ultra-Sovereign Efficiency (CPU focused)

Designed for continuous background state monitoring, log auditing,
autonomous maintenance with near-zero power draw.

- **Conductor** (Pulse): pinned to CPU cores 0–7. Executes BitNet-b1.58-3B
  via bitnet.cpp.
- **GPU state**: low-power compute sleep (`nvidia-smi -pm 1`, clocks throttled).

```sh
# Master spec verbatim invocation
taskset -c 0-7 bitnet-cli -m ./models/bitnet_b1_58_3b/ggml-model-i2.gguf \
  -p "Evaluate state transition from CLAUDE.md" \
  --threads 8 --memory-f32
```

### Profile 2 — High-Concurrency Agent Burst (asymmetric)

Designed for multiple specialist sub-agents processing an extensive codebase.

```json
{
  "node_allocation_profile": "Asymmetric_Burst",
  "allocations": [
    {"agent_id": "conductor_01",    "target_hardware": "cpu",     "core_mask": "0-11",  "engine": "bitnet.cpp", "model": "BitNet-b1.58-13B"},
    {"agent_id": "translator_01",   "target_hardware": "cuda:0",  "vram_limit_bytes": 22548578304, "engine": "vllm-vulkan", "model": "Qwen-32B-Ternary-Quant"},
    {"agent_id": "deep_reasoner_01","target_hardware": "cuda:1",  "vram_limit_bytes": 94489280512, "engine": "llama.cpp",   "model": "DeepSeek-R1-Distill-Llama-70B-FP16"}
  ]
}
```

### Profile 3 — Deep Context Synthesis (unified GPU memory)

Designed for whole-system telemetry reads or full-codebase parsing.

```sh
podman run --device nvidia.com/gpu=all -v /mnt/vault/models:/models:ro \
  vllm/vllm-openai:latest \
  --model /models/DeepSeek-V3-Quant \
  --tensor-parallel-size 2 \
  --pipeline-parallel-size 1 \
  --gpu-memory-utilization 0.95 \
  --kv-cache-dtype fp8
```

---

## Models (master spec + operator additions)

| Model | Role | Tier | Status in repo |
|---|---|---|---|
| **BitNet-b1.58-3B** | Conductor (low-power) | Pulse / CPU | Backend stub at `scripts/inference/backends/bitnet.py` (R152) |
| **BitNet-b1.58-13B** | Conductor (high-concurrency) | Pulse / CPU | same |
| **Qwen-32B-Ternary-Quant** | Translator / Logic Engine | vllm-vulkan / 3090 | not configured (R156) |
| **DeepSeek-R1-Distill-Llama-70B-FP16** | Deep Reasoner | llama.cpp / Blackwell | not configured (R156) |
| **DeepSeek-V3-Quant** | Unified-memory inference | vLLM tensor-parallel | not configured (R156) |
| **Ling-2.6-flash** (107B bailing_hybrid; MIT) | Operator-added candidate | TBD | not configured (R156) |
| **Nemotron-3-Nano-Omni-30B-Reasoning-BF16** | Operator-added candidate (multimodal any-to-any) | TBD | not configured (R156) |
| **DFlash** speculative decoder | 3× speedup on code/math (operator-added) | layered on top of Pulse/Logic | not integrated (R157) |

---

## Master bootstrap verification checklist (master spec § 22)

After build + install + first boot, the operator runs this on the target
hardware. Six checks; any anomaly → lock-state until the Architect clears.

| Check | Subsystem | Target metric | Verification |
|---|---|---|---|
| 01 | Microcode / ISA | avx512_vnni + avx512_bf16 present | `grep -E "avx512_vnni\|avx512_bf16" /proc/cpuinfo` |
| 02 | Bus geometry | Both slots at Gen 4/5 x8 | `lspci -vvv \| grep -i "LnkSta: Speed"` |
| 03 | Linux memory | ZFS ARC capped at 137438953472 bytes | `arcstat -s c` |
| 04 | Driver fabric | NVIDIA 560+ open-kernel modules loaded | `modinfo nvidia \| grep -i license` |
| 05 | Security core | Tetragon UNIX socket active + streaming | `ls -la /var/run/tetragon/tetragon.events` |
| 06 | Network line | enp5s0 at Jumbo MTU 9000 | `ip link show enp5s0 \| grep -i "mtu 9000"` |

**In repo**: piecewise covered by preflight + audit + status verbs.
**NOT YET BUILT** as one single `sovereign-osctl bootstrap verify`
command. Tracked in R159.

---

## Cross-references

- **Verbatim source** (sacrosanct, L0): info-hub
  `raw/dumps/2026-05-15-sain-01-master-spec-other-conversation-transposition.md`
- **L1 synthesis** at info-hub `wiki/sources/src-sain-01-sovereign-node-spec.md`
- **Operator directive** (verbatim arc-opening): info-hub
  `raw/notes/2026-05-16-user-directive-sovereign-os-arc-opening.md`
- **Profile YAML**: [`profiles/sain-01.yaml`](../../profiles/sain-01.yaml)
- **Build pipeline**: [`scripts/build/`](../../scripts/build/)
- **Lifecycle hooks**: [`scripts/hooks/`](../../scripts/hooks/)
- **SDDs**: [`docs/sdd/INDEX.md`](../sdd/INDEX.md) — 26 decisions
  documented; SDD-017 (ZFS layout), SDD-015 (secure-boot), SDD-022 (disk
  encryption), SDD-018 (kernel choice), SDD-019 (reproducibility) are
  the most master-spec-load-bearing.

---

## What's NOT yet built (honest gap list)

Tracked rounds in the arc:

| Master spec section | What's missing | Round |
|---|---|---|
| § 17 — Trinity surfaced as first-class | `sovereign-osctl trinity {status,pulse,weaver,auditor}` verb | R149 |
| § 18 — 3 runtime profiles selectable | `profiles/runtime/*.yaml` + `trinity profile <name>` | R150 |
| § 19 — CCD-pinned core masks | Per-profile `taskset` wiring in start scripts | R151 |
| §§ 15-16 — Real bitnet.cpp | Build-from-source + znver5 flags + model fetch | R152 |
| § 20 — Wasm-to-AVX-512 AOT | Cranelift/wasmtime + sample pulse_core.wasm | R153 |
| § 21 — Atomic state transition protocol | `scripts/weaver/atomic-state.py` (O_DIRECT + atomic rename) | R154 |
| § 10 — Guardian Daemon | `/usr/local/bin/guardian-core` (or selfdef wire) | R155 |
| Model catalog | Pre-configured BitNet + Qwen + DeepSeek + Ling + Nemotron | R156 |
| DFlash integration | Speculative-decoder fast-path for code/math | R157 |
| § 8 — Asymmetric networking opinionated | VLAN 100/200 + MTU 9000 master-spec defaults | R158 |
| § 22 — Bootstrap verification checklist | `sovereign-osctl bootstrap verify` (6 checks) | R159 |

Each round lands as a substantive direct-to-main commit with tests
+ inline doc updates. The R145-R148 documentation arc surfaces the
WHOLE PICTURE so operators understand what's being delivered; R149-R159
materializes the substantive gaps.
