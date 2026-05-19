# Prior-dump review findings — 2026-05-19

Source: Explore agent review of two prior dumps:
- `~/infohub/raw/dumps/2026-05-15-sain-01-master-spec-other-conversation-transposition.md` (67KB, 1139 lines) — Trinity genesis + hardware/kernel/storage/security deep spec
- `~/infohub/raw/dumps/2026-05-16-sovereign-os-macro-arc-plan.md` (29KB, 405 lines) — Plan agent output: macro-arc for first 6-10 PRs

Operator standing direction (verbatim, 2026-05-19): *"there was also other dumps before that we decided to restart and do properly in a sense, not that all was lost but it was down a rabbit role and with weird things happening versus what I asked"* / *"following the proper workflow and respect of SFIF and second-brain knowledge"*

## Must-add inventory (15 milestones M062-M076)

| slot | title | severity | source lines |
|---|---|---|---|
| M062 | Macro-Arc 10-PR Foundation Scaffold (PRs 1-3 charter/arch/mdbook; PRs 4-8 substrate/schemas/whitelabel; PRs 9-10 TDD harness) | must-add | 2026-05-16 dump 19-282 |
| M063 | SFIF Discipline (Scaffold → Foundation → Infrastructure → Features) | must-add | 2026-05-16 dump 390-396 |
| M064 | "Debian as Ark" + Q-016 distro-base reconsideration | must-add | 2026-05-16 dump 396-399 |
| M065 | Five Stage Gates SG1-SG5 + ExitPlanMode checkpoint ritual | must-add | 2026-05-16 dump 323-330 |
| M066 | Trinity Framework Genesis (The Pulse + The Weaver + The Auditor) | must-add | 2026-05-15 dump 940-987 |
| M067 | Custom Kernel Build Pipeline (-march=znver5 / GCC 14 / Linux 6.12 / bindeb-pkg) | must-add | 2026-05-15 dump 501-676 |
| M068 | ZFS Storage Architecture (tank/context / sync=always / recordsize / compression / layer-allocation) | must-add | 2026-05-15 dump 686-695, 913-925 |
| M069 | Guardian Daemon (Tetragon eBPF loop + SIGKILL + audit logging) | must-add | 2026-05-15 dump 515-567 |
| M070 | Dual-CCD Cache Topology + core pinning (CCD 0 = Pulse, CCD 1 = Weaver+Auditor+Host) | must-add | 2026-05-15 dump 1013-1025 |
| M071 | Atomic State Transition Protocol (O_DIRECT + POSIX AIO + lockless ZFS) | must-add | 2026-05-15 dump 1051-1089 |
| M072 | Master Bootstrap Verification Checklist (6 phases + invocation commands) | must-add | 2026-05-15 dump 1091-1100 |
| M073 | 1-Bit (Ternary) Logic + BitLinear Core | must-add | 2026-05-15 dump 777-788 |
| M074 | AVX-512 VNNI Hardware Fusion (512-bit ZMM / 64× INT8 / LUT-based matrix ops) | must-add | 2026-05-15 dump 805-811 |
| M075 | SRP Hardware Topology Mapping (Conductor on CPU / Logic on GPU 0 / Oracle on GPU 1) | must-add | 2026-05-15 dump 812-851 |
| M076 | Three Load-Balancing Profiles (Ultra-Sovereign Efficiency / High-Concurrency Burst / Deep Context Synthesis) | must-add | 2026-05-15 dump 852-926 |

## Nice-to-add inventory (12 items folded into future MS044+ or M077+)

- IaC Quality Bar (resumable / observable / tweakable / env-var-driven)
- Trade-Off Analysis Table (8 major decision points pre-PR)
- Dual GPU Lane Asymmetry (PCIe x8/x8 sharing under ProArt X870E-Creator)
- Secure Boot MOK Challenge + Solution
- OPNsense WAN/LAN Bridging + Tetragon socket dropout fix
- Wasm-to-AVX-512 AOT Pipeline (Cranelift/LLVM target-cpu=znver5)
- DFlash Block Diffusion (arXiv:2602.06036)
- Model Candidate Additions (Ling-2.6-flash + Nemotron-3-Nano-Omni-30B-A3B)
- GPU Persistence Mode (`nvidia-smi -pm 1`)
- eBPF Enforcement Strictness toggle (Tetragon policy activation)
- Kernel Environment Variables surface (CFLAGS/CXXFLAGS/GGML_AVX512)
- Podman/Container Storage graph driver mapping to ZFS datasets

## Discard inventory

- **None.** Agent reported no divergent "weird things versus what I asked" material in these two dumps. All findings align with operator's stated vision.

## Patch plan

- **Pass D1**: write M062-M066 (governance foundations: macro-arc / SFIF / Debian-as-Ark / stage gates / Trinity)
- **Pass D2**: write M067-M070 (technical substrate: kernel / ZFS / guardian / CCD topology)
- **Pass D3**: write M071-M076 (deep technical: atomic state / bootstrap / ternary / VNNI / SRP / load-balancing)
- **Pass D4**: catalog nice-to-add items as additional milestones M077+ or selfdef MS044+

## Project boundary notes

- **M069 Guardian Daemon** is a security-boundary enforcement organ; check whether it belongs in selfdef (IPS-side) rather than sovereign-os runtime. Per operator standing direction "if I talk about an IPS feature its obviously not in Sovereign-OS" — Guardian Daemon enforces policy violations via SIGKILL + audit logging, which is IPS-adjacent. **Likely belongs in selfdef as MS044 instead of sovereign-os M069.** TBD when authoring.
- **M073 + M074** (1-bit ternary + VNNI fusion) are runtime-execution concerns — sovereign-os.
- **M075 SRP Hardware Topology** spans both: scheduling lives in sovereign-os (M058 already) but the hardware-SRP mapping itself is a sovereign-os concern.
- **M076 Load-Balancing Profiles** is sovereign-os runtime (profile selection).

## Pending

- All 15 must-add concepts enumerated; M062-M076 authoring scheduled across passes D1/D2/D3.
- SDD/TDD implementation readiness gate now depends on M062-M076 completion.
