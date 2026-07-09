# docs/MASTER-PLAN.md — cross-repo synthesis of the two-ultimate-solutions catalog

> Single-page synthesis of the existing 128 milestones across both repos —
> **selfdef** (Solution 2: IPS daemon) + **sovereign-os** (Solution 1: AI
> workstation runtime + cockpit). Factually derived from
> `selfdef/backlog/milestones/MS*.md` + `sovereign-os/backlog/milestones/M*.md`;
> no invention. The catalog is the operator's master plan; this doc surfaces
> it as one navigable timeline + dependency view.

## Top-line numbers

| dimension | selfdef | sovereign-os | combined |
|---|---:|---:|---:|
| Milestones (M*.md files) | 48 | 82 | **130** |
| R-rows | 11,520 | 14,080 | **25,600** |
| Each R-row is a non-negotiable requirement; combined catalog satisfies the operator's stated "10,000+ requirements" mandate (~2.5× over). |

## Stage Gates (sovereign-os build phases — synthesized from M053 + Pulse-Tooling)

| Gate | Coverage | Status |
|---|---|---|
| **SG1** philosophy + open-questions | M006 deterministic substrate, M001 lineage | catalog ✓ |
| **SG2** microarchitecture + topology | M002 control-word, M003 PCIe topology, M070 Dual-CCD | catalog ✓ |
| **SG3** substrate kernel + storage | M008-M020 kernel/ZFS/dataset layers | catalog ✓ |
| **SG4** intelligence layer | M004 SRP roles, M058 scheduler, M075 SRP topology | catalog ✓ |
| **SG5** image-build TDD | M033 TDD discipline, M082 hardware-free validation | catalog ✓ |
| **SG6** cockpit + dashboards | **M060 (DONE this session, see PR #200 + #12)** + the 20 D-NN dashboards | **producer→consumer chain at prod end-to-end** |
| **SG7** inference paradigms | M046 LoRA Foundry, M048 modules map, M077 NVFP4, M073 ternary BitLinear, M078 HölderPO post-training | catalog ✓ |
| **SG8** interpretability + safety | M079 activation steering (cross-cutting MS039+MS042+MS044) | catalog ✓ |

## Cross-repo dependency map (selfdef → sovereign-os)

| selfdef artifact | sovereign-os consumer | status |
|---|---|---|
| `selfdef-profile-mirror` (MS007) | D-02 active-profile dashboard | **at prod (PR #200)** |
| `selfdef-grants-mirror` (MS007) | D-13 filesystem grants dashboard | **at prod** |
| `selfdef-capability-mirror` (MS007) | D-14 capability tokens dashboard | **at prod** |
| `selfdef-sandbox-mirror` (MS007) | D-15 sandboxes dashboard | **at prod** |
| `selfdef-quarantine-mirror` (MS007) | D-17 quarantine dashboard | **at prod** |
| `selfdef-trust-score-mirror` (MS007) | D-18 trust-scores dashboard | **at prod** |
| `selfdef-audit-mirror` (MS007) | D-16 audit chain | catalog ✓ (not yet wired) |
| `selfdef-rules-mirror` (MS007) | D-12 networking (in part) | catalog ✓ (not yet wired) |
| `selfdef-cli-mirror` + `selfdef-tui-mirror` (MS007) | sovereign-os surface integration | catalog ✓ |
| MS039 authority levels + MS040 profiles + MS042 tool authority + MS044 Guardian | M079 activation steering safety surface | catalog ✓ |
| MS035 capability_word.compute_mode | M080 model portfolio extension | catalog ✓ |

## The 130 milestones (by repo, by ID)

### selfdef · MS001–MS048 (11,520 R-rows)

- [MS001-selfdef-daemon-core](../../selfdef/backlog/milestones/MS001-selfdef-daemon-core.md)  ·  240 R-rows  ·  MS001 — Selfdef daemon core — selfdef-core / selfdef-daemon / selfdef-bus / selfdef-config / selfdef-api / selfdef-cli
- [MS002-collector-fabric](../../selfdef/backlog/milestones/MS002-collector-fabric.md)  ·  240 R-rows  ·  MS002 — Collector fabric — auditd / journald / eBPF / Tetragon / Suricata / eventstream / canary
- [MS003-correlator-store-responder-signing](../../selfdef/backlog/milestones/MS003-correlator-store-responder-signing.md)  ·  240 R-rows  ·  MS003 — Correlator + store + responder + signing — time-windowed rules pipeline
- [MS004-fourteen-notifier-integrations](../../selfdef/backlog/milestones/MS004-fourteen-notifier-integrations.md)  ·  240 R-rows  ·  MS004 — 14 notifier integrations — Discord / Loki / ntfy / OpenSearch / Oracle-Triage / PagerDuty / Shared-Audit-Summary / Signal / Slack / SMTP / TheHive / Twilio / Wall / Write
- [MS005-notifier-engine-orchestrator](../../selfdef/backlog/milestones/MS005-notifier-engine-orchestrator.md)  ·  240 R-rows  ·  MS005 — Notifier engine + orchestrator
- [MS006-fourteen-functional-modules](../../selfdef/backlog/milestones/MS006-fourteen-functional-modules.md)  ·  240 R-rows  ·  MS006 — 14 functional modules — agent-guard / bitnet-gpu-inference / bridge-l2 / detect-host / hardware-tune-cache / integrity-sentinel / observability / polarproxy / slm-cpu-loop / suricata / tensor-parallel-inference / tetragon / vpn-bridge / wasm-aot-cache
- [MS007-cross-repo-typed-mirror-crates-saturated-8-of-8](../../selfdef/backlog/milestones/MS007-cross-repo-typed-mirror-crates-saturated-8-of-8.md)  ·  240 R-rows  ·  MS007 — 8/8 SATURATED cross-repo typed-mirror crates — auth-tier / bashrc-install / history-sink / dashboard-manifest / surface-manifest / ux-checklist / audit-manifest / doc-manifest
- [MS008-selfdef-on-sain01-integration](../../selfdef/backlog/milestones/MS008-selfdef-on-sain01-integration.md)  ·  240 R-rows  ·  MS008 — selfdef-on-SAIN-01 integration
- [MS009-audit-cycles](../../selfdef/backlog/milestones/MS009-audit-cycles.md)  ·  240 R-rows  ·  MS009 — Audit cycles
- [MS010-hardware-aware-modules-and-tune-surface](../../selfdef/backlog/milestones/MS010-hardware-aware-modules-and-tune-surface.md)  ·  240 R-rows  ·  MS010 — Hardware-aware modules + tune surface
- [MS011-operator-dashboard-and-flex-profile](../../selfdef/backlog/milestones/MS011-operator-dashboard-and-flex-profile.md)  ·  240 R-rows  ·  MS011 — Operator dashboard + flex profile
- [MS012-perimeter-coexistence](../../selfdef/backlog/milestones/MS012-perimeter-coexistence.md)  ·  240 R-rows  ·  MS012 — Perimeter coexistence
- [MS013-twenty-seven-sdd-charter-framework](../../selfdef/backlog/milestones/MS013-twenty-seven-sdd-charter-framework.md)  ·  240 R-rows  ·  MS013 — 27-SDD charter framework
- [MS014-ssh-wrap-client-side-defense](../../selfdef/backlog/milestones/MS014-ssh-wrap-client-side-defense.md)  ·  240 R-rows  ·  MS014 — SSH-wrap — client-side defense when YOU are the client
- [MS015-nats-messaging-backbone](../../selfdef/backlog/milestones/MS015-nats-messaging-backbone.md)  ·  240 R-rows  ·  MS015 — NATS messaging backbone
- [MS016-ebpf-programs-tetragon-tracingpolicies](../../selfdef/backlog/milestones/MS016-ebpf-programs-tetragon-tracingpolicies.md)  ·  240 R-rows  ·  MS016 — eBPF programs + Tetragon TracingPolicies
- [MS017-agent-guard-host-level-invariants-on-ai-agents](../../selfdef/backlog/milestones/MS017-agent-guard-host-level-invariants-on-ai-agents.md)  ·  240 R-rows  ·  MS017 — agent-guard — host-level invariants on AI agents in Docker / Podman / containerd
- [MS018-vpn-bridge-multi-instance](../../selfdef/backlog/milestones/MS018-vpn-bridge-multi-instance.md)  ·  240 R-rows  ·  MS018 — VPN-bridge multi-instance
- [MS019-security-threat-model](../../selfdef/backlog/milestones/MS019-security-threat-model.md)  ·  240 R-rows  ·  MS019 — Security threat model
- [MS020-test-contract-l1-l5-layered-harness](../../selfdef/backlog/milestones/MS020-test-contract-l1-l5-layered-harness.md)  ·  240 R-rows  ·  MS020 — Test contract — L1–L5 layered harness
- [MS021-shared-module-script-lib](../../selfdef/backlog/milestones/MS021-shared-module-script-lib.md)  ·  240 R-rows  ·  MS021 — Shared module-script lib
- [MS022-per-token-sse-subscriber-quota](../../selfdef/backlog/milestones/MS022-per-token-sse-subscriber-quota.md)  ·  240 R-rows  ·  MS022 — Per-token SSE subscriber quota
- [MS023-polarproxy-module-tls-inspection](../../selfdef/backlog/milestones/MS023-polarproxy-module-tls-inspection.md)  ·  240 R-rows  ·  MS023 — Polarproxy module — TLS inspection
- [MS024-bridge-l2-module-layer-2-transparent-bridge](../../selfdef/backlog/milestones/MS024-bridge-l2-module-layer-2-transparent-bridge.md)  ·  240 R-rows  ·  MS024 — Bridge-L2 module — layer-2 transparent bridge
- [MS025-detect-host-module-host-class-detection](../../selfdef/backlog/milestones/MS025-detect-host-module-host-class-detection.md)  ·  240 R-rows  ·  MS025 — Detect-host module — host-class detection
- [MS026-integrity-sentinel-module](../../selfdef/backlog/milestones/MS026-integrity-sentinel-module.md)  ·  240 R-rows  ·  MS026 — Integrity-sentinel module
- [MS027-observability-module](../../selfdef/backlog/milestones/MS027-observability-module.md)  ·  240 R-rows  ·  MS027 — Observability module (selfdef-side)
- [MS028-bitnet-gpu-inference-module](../../selfdef/backlog/milestones/MS028-bitnet-gpu-inference-module.md)  ·  240 R-rows  ·  MS028 — BitNet GPU inference module
- [MS029-slm-cpu-loop-module](../../selfdef/backlog/milestones/MS029-slm-cpu-loop-module.md)  ·  240 R-rows  ·  MS029 — SLM CPU loop module
- [MS030-tensor-parallel-inference-module](../../selfdef/backlog/milestones/MS030-tensor-parallel-inference-module.md)  ·  240 R-rows  ·  MS030 — Tensor parallel inference module
- [MS031-wasm-aot-cache-module](../../selfdef/backlog/milestones/MS031-wasm-aot-cache-module.md)  ·  240 R-rows  ·  MS031 — WASM AOT cache module
- [MS032-sandbox-tiers](../../selfdef/backlog/milestones/MS032-sandbox-tiers.md)  ·  240 R-rows  ·  MS032 — Sandbox tiers — read-only / workspace-write / Podman / network-denied / network-allowed / VFIO 4090 / browser-GUI / CRIU / ZFS clone
- [MS033-policy-and-trace](../../selfdef/backlog/milestones/MS033-policy-and-trace.md)  ·  240 R-rows  ·  MS033 — Policy and trace — every action observable + governed
- [MS034-communication-boundary](../../selfdef/backlog/milestones/MS034-communication-boundary.md)  ·  240 R-rows  ·  MS034 — Communication boundary
- [MS035-capability-tokens-typed-authority-handles](../../selfdef/backlog/milestones/MS035-capability-tokens-typed-authority-handles.md)  ·  240 R-rows  ·  MS035 — Capability tokens — typed authority handles
- [MS036-tool-sandboxes](../../selfdef/backlog/milestones/MS036-tool-sandboxes.md)  ·  240 R-rows  ·  MS036 — Tool sandboxes (Tier A/B/C/D)
- [MS037-filesystem-boundary](../../selfdef/backlog/milestones/MS037-filesystem-boundary.md)  ·  240 R-rows  ·  MS037 — Filesystem boundary
- [MS038-network-boundary](../../selfdef/backlog/milestones/MS038-network-boundary.md)  ·  240 R-rows  ·  MS038 — Network boundary
- [MS039-authority-levels-and-trust-rings](../../selfdef/backlog/milestones/MS039-authority-levels-and-trust-rings.md)  ·  240 R-rows  ·  MS039 — Authority levels (L0..L6) and trust rings (Ring 0..4) — IPS-side projection
- [MS040-authority-and-profiles-six-profile-authority-matrix](../../selfdef/backlog/milestones/MS040-authority-and-profiles-six-profile-authority-matrix.md)  ·  240 R-rows  ·  MS040 — Authority-and-profiles — six-profile authority matrix — IPS-side projection
- [MS041-commit-authority-durable-change-discipline](../../selfdef/backlog/milestones/MS041-commit-authority-durable-change-discipline.md)  ·  240 R-rows  ·  MS041 — Commit authority — durable-change discipline — IPS-side projection
- [MS042-tool-authority-declaration-vs-observed-discipline](../../selfdef/backlog/milestones/MS042-tool-authority-declaration-vs-observed-discipline.md)  ·  240 R-rows  ·  MS042 — Tool authority — declaration-vs-observed discipline — IPS-side projection (CATALOG CLOSE)
- [MS043-ips-operator-surface-cli-tui-and-dashboard-mirrors](../../selfdef/backlog/milestones/MS043-ips-operator-surface-cli-tui-and-dashboard-mirrors.md)  ·  240 R-rows  ·  MS043 — IPS operator surface — CLI + TUI + dashboard-mirror exports
- [MS044-guardian-daemon-tetragon-ebpf-supervisor](../../selfdef/backlog/milestones/MS044-guardian-daemon-tetragon-ebpf-supervisor.md)  ·  240 R-rows  ·  MS044 — Guardian Daemon — Tetragon eBPF supervisor + SIGKILL + atomic ZFS audit logs
- [MS045-ux-coherence-test-harness-cli-tui-minimal-web](../../selfdef/backlog/milestones/MS045-ux-coherence-test-harness-cli-tui-minimal-web.md)  ·  240 R-rows  ·  MS045 — UX coherence test harness (CLI + TUI + minimal-web) — TDD validator for MS043 operator surface
- [MS046-friction-audit-system-boot-time-hardware-integrity-gate](../../selfdef/backlog/milestones/MS046-friction-audit-system-boot-time-hardware-integrity-gate.md)  ·  240 R-rows  ·  MS046 — Friction Audit System — boot-time hardware-integrity gate (sain-01 §5)
- [MS047-real-time-security-perimeter-engine-tetragon-kernel-fence](../../selfdef/backlog/milestones/MS047-real-time-security-perimeter-engine-tetragon-kernel-fence.md)  ·  240 R-rows  ·  MS047 — Real-Time Security Perimeter Engine — Tetragon kernel-fence (sain-01 §6)
- [MS048-goldilocks-scheduler-hardware-aware-resource-routing](../../selfdef/backlog/milestones/MS048-goldilocks-scheduler-hardware-aware-resource-routing.md)  ·  240 R-rows  ·  MS048 — Goldilocks Scheduler — hardware-aware resource routing

### sovereign-os · 82 milestones (14,080 R-rows)

- [M002-control-word-injected-logic](../backlog/milestones/M002-control-word-injected-logic.md)  ·  170 R-rows  ·  M002 — 32/64-bit injected logic / control word per branch
- [M003-hardware-topology-pcie-discipline](../backlog/milestones/M003-hardware-topology-pcie-discipline.md)  ·  170 R-rows  ·  M003 — Hardware topology + PCIe lane discipline
- [M004-oracle-scout-vector-arbiter-roles](../backlog/milestones/M004-oracle-scout-vector-arbiter-roles.md)  ·  170 R-rows  ·  M004 — Oracle / Scout / Vector Arbiter role split
- [M005-agent-runtime-four-planes](../backlog/milestones/M005-agent-runtime-four-planes.md)  ·  170 R-rows  ·  M005 — Agent runtime — four planes (Inference / Control / Memory / Tool)
- [M006-deterministic-ai-control-substrate](../backlog/milestones/M006-deterministic-ai-control-substrate.md)  ·  170 R-rows  ·  M006 — Deterministic AI control substrate
- [M007-execution-model-branch-primitive-scheduler](../backlog/milestones/M007-execution-model-branch-primitive-scheduler.md)  ·  170 R-rows  ·  M007 — Execution model — branch primitive + AVX-512 scheduler
- [M008-bit-level-cheats-avx512-features](../backlog/milestones/M008-bit-level-cheats-avx512-features.md)  ·  170 R-rows  ·  M008 — Bit-level cheats — AVX-512 features as AI infrastructure
- [M009-deterministic-cortex-runtime-v0](../backlog/milestones/M009-deterministic-cortex-runtime-v0.md)  ·  170 R-rows  ·  M009 — Deterministic Cortex Runtime v0 (full spec)
- [M010-deterministic-data-plane](../backlog/milestones/M010-deterministic-data-plane.md)  ·  170 R-rows  ·  M010 — Deterministic data plane — simdjson + Hyperscan + CRoaring
- [M011-kv-cache-memory-hierarchy](../backlog/milestones/M011-kv-cache-memory-hierarchy.md)  ·  170 R-rows  ·  M011 — KV cache as memory hierarchy
- [M012-storage-and-replay-plane](../backlog/milestones/M012-storage-and-replay-plane.md)  ·  170 R-rows  ·  M012 — Storage and replay plane
- [M013-observability-as-control-input](../backlog/milestones/M013-observability-as-control-input.md)  ·  170 R-rows  ·  M013 — Observability as control input
- [M014-isolation-and-trust-boundaries](../backlog/milestones/M014-isolation-and-trust-boundaries.md)  ·  170 R-rows  ·  M014 — Isolation and trust boundaries
- [M015-agent-programming-model](../backlog/milestones/M015-agent-programming-model.md)  ·  170 R-rows  ·  M015 — Agent programming model
- [M016-learning-without-retraining](../backlog/milestones/M016-learning-without-retraining.md)  ·  170 R-rows  ·  M016 — Learning without retraining
- [M017-model-portfolio-strategy](../backlog/milestones/M017-model-portfolio-strategy.md)  ·  170 R-rows  ·  M017 — Model portfolio strategy
- [M018-serving-topology-local-inference-fabric](../backlog/milestones/M018-serving-topology-local-inference-fabric.md)  ·  170 R-rows  ·  M018 — Serving topology — local inference fabric
- [M019-intelligence-creation-composable-cognitive-operators](../backlog/milestones/M019-intelligence-creation-composable-cognitive-operators.md)  ·  170 R-rows  ·  M019 — Intelligence creation — composable cognitive operators
- [M020-orchestration-without-captivity-semantic-isa](../backlog/milestones/M020-orchestration-without-captivity-semantic-isa.md)  ·  170 R-rows  ·  M020 — Orchestration without captivity — semantic ISA
- [M021-repl-cot-moe-workflow-logic-intelligence-weave](../backlog/milestones/M021-repl-cot-moe-workflow-logic-intelligence-weave.md)  ·  170 R-rows  ·  M021 — REPL / CoT / MoE / workflow / logic / intelligence weave
- [M022-cognitive-frame-system-level-moe](../backlog/milestones/M022-cognitive-frame-system-level-moe.md)  ·  170 R-rows  ·  M022 — Cognitive Frame — system-level MoE
- [M023-execution-substrate-wasm-deno-python-vm-tiers](../backlog/milestones/M023-execution-substrate-wasm-deno-python-vm-tiers.md)  ·  170 R-rows  ·  M023 — Execution substrate — WASM / Deno / Python / VM tiers
- [M024-adaptive-programming-profiles-as-reward-weights](../backlog/milestones/M024-adaptive-programming-profiles-as-reward-weights.md)  ·  170 R-rows  ·  M024 — Adaptive programming — profiles as reward weights
- [M025-cognitive-compiler-intent-to-dag](../backlog/milestones/M025-cognitive-compiler-intent-to-dag.md)  ·  170 R-rows  ·  M025 — Cognitive Compiler — intent to DAG
- [M026-slm-swarm-rlm-engine-rm-prm-judges](../backlog/milestones/M026-slm-swarm-rlm-engine-rm-prm-judges.md)  ·  170 R-rows  ·  M026 — SLM swarm + RLM engine + RM/PRM judges
- [M027-value-plane-reward-vector-prm-as-branch-critic](../backlog/milestones/M027-value-plane-reward-vector-prm-as-branch-critic.md)  ·  170 R-rows  ·  M027 — Value plane — reward vector + PRM as branch critic
- [M028-memory-os-8-memory-types](../backlog/milestones/M028-memory-os-8-memory-types.md)  ·  170 R-rows  ·  M028 — Memory OS — 8 memory types
- [M029-computer-use-plane-perception-planning-execution](../backlog/milestones/M029-computer-use-plane-perception-planning-execution.md)  ·  170 R-rows  ·  M029 — Computer-Use plane — perception + planning + execution
- [M030-world-model-plane-state-action-transition](../backlog/milestones/M030-world-model-plane-state-action-transition.md)  ·  170 R-rows  ·  M030 — World Model plane — state / action / transition
- [M031-symbolic-planning-plane-pddl-sat-smt-ltl](../backlog/milestones/M031-symbolic-planning-plane-pddl-sat-smt-ltl.md)  ·  170 R-rows  ·  M031 — Symbolic Planning plane — PDDL / SAT-SMT / LTL
- [M032-cloud-expert-plane-openai-anthropic-remote-experts](../backlog/milestones/M032-cloud-expert-plane-openai-anthropic-remote-experts.md)  ·  170 R-rows  ·  M032 — Cloud Expert plane — OpenAI + Anthropic as remote experts
- [M033-compatibility-gateway-what-we-expose](../backlog/milestones/M033-compatibility-gateway-what-we-expose.md)  ·  170 R-rows  ·  M033 — Compatibility Gateway — what we expose
- [M034-anthropic-first-gateway-mcp-claude-code-integration](../backlog/milestones/M034-anthropic-first-gateway-mcp-claude-code-integration.md)  ·  170 R-rows  ·  M034 — Anthropic-first gateway + MCP + Claude Code integration
- [M035-frontier-inference-time-intelligence](../backlog/milestones/M035-frontier-inference-time-intelligence.md)  ·  170 R-rows  ·  M035 — Frontier — inference-time intelligence
- [M036-map-then-act-paradigm](../backlog/milestones/M036-map-then-act-paradigm.md)  ·  170 R-rows  ·  M036 — MAP — map-then-act paradigm
- [M037-spec-tdd-agent-evals-evidence-driven-autonomy](../backlog/milestones/M037-spec-tdd-agent-evals-evidence-driven-autonomy.md)  ·  170 R-rows  ·  M037 — Spec / TDD / agent evals as evidence-driven autonomy
- [M038-hardware-aware-aidlc](../backlog/milestones/M038-hardware-aware-aidlc.md)  ·  170 R-rows  ·  M038 — Hardware-aware AIDLC
- [M039-avx512-cortex-hot-path](../backlog/milestones/M039-avx512-cortex-hot-path.md)  ·  170 R-rows  ·  M039 — AVX-512 cortex hot path
- [M040-hyper-features-mig-fp4-vfio-zfs-commit-gate](../backlog/milestones/M040-hyper-features-mig-fp4-vfio-zfs-commit-gate.md)  ·  170 R-rows  ·  M040 — Hyper features — MIG / FP4 / VFIO / ZFS commit gate
- [M041-spec-workflow-profiles-evals-policy-model-registry-hardware-profiles-contracts](../backlog/milestones/M041-spec-workflow-profiles-evals-policy-model-registry-hardware-profiles-contracts.md)  ·  170 R-rows  ·  M041 — Spec / WORKFLOW / PROFILES / EVALS / POLICY / MODEL_REGISTRY / HARDWARE_PROFILES contracts
- [M042-choice-architecture-sovereignty-as-policy-composable](../backlog/milestones/M042-choice-architecture-sovereignty-as-policy-composable.md)  ·  170 R-rows  ·  M042 — Choice architecture — sovereignty as policy-composable
- [M043-bridge-layer-hardware-aware-intelligence-scheduling](../backlog/milestones/M043-bridge-layer-hardware-aware-intelligence-scheduling.md)  ·  170 R-rows  ·  M043 — Bridge layer — hardware-aware intelligence scheduling
- [M044-sovereign-os-substrate-debian-13-ubuntu-24](../backlog/milestones/M044-sovereign-os-substrate-debian-13-ubuntu-24.md)  ·  170 R-rows  ·  M044 — Sovereign-OS substrate — Debian 13 / Ubuntu 24
- [M045-linux-as-intelligence-governor-cgroup-v2-systemd-psi-ebpf](../backlog/milestones/M045-linux-as-intelligence-governor-cgroup-v2-systemd-psi-ebpf.md)  ·  170 R-rows  ·  M045 — Linux as intelligence governor — cgroup v2 / systemd / PSI / eBPF
- [M046-beat-the-cloud-runtime-adaptation-lora-foundry](../backlog/milestones/M046-beat-the-cloud-runtime-adaptation-lora-foundry.md)  ·  170 R-rows  ·  M046 — Beat the cloud — runtime adaptation + LoRA foundry
- [M047-continuity-criu-zfs-warm-sandboxes-hibernated-thought](../backlog/milestones/M047-continuity-criu-zfs-warm-sandboxes-hibernated-thought.md)  ·  170 R-rows  ·  M047 — Continuity — CRIU + ZFS + warm sandboxes + hibernated thought
- [M048-modules-base-os-compute-fabric-sandbox-gateway-memory-workflow-eval-continuity-observability-policy-config-resolver-lora-foundry-hardware-profiler](../backlog/milestones/M048-modules-base-os-compute-fabric-sandbox-gateway-memory-workflow-eval-continuity-observability-policy-config-resolver-lora-foundry-hardware-profiler.md)  ·  170 R-rows  ·  M048 — Modules — Base OS / Compute Fabric / Sandbox Fabric / Gateway / Memory OS / Workflow Compiler / Eval-Value / Continuity / Observability / Policy / Config Resolver / LoRA Foundry / Hardware Profiler
- [M049-continuity-through-observability-and-policy](../backlog/milestones/M049-continuity-through-observability-and-policy.md)  ·  170 R-rows  ·  M049 — Continuity through observability and policy
- [M050-architect-engineer-seat-heterogeneous-intelligence-system](../backlog/milestones/M050-architect-engineer-seat-heterogeneous-intelligence-system.md)  ·  170 R-rows  ·  M050 — Architect and Engineer seat — heterogeneous intelligence system
- [M051-devops-fullstack-ai-expert-layer](../backlog/milestones/M051-devops-fullstack-ai-expert-layer.md)  ·  170 R-rows  ·  M051 — DevOps + Fullstack + AI expert layer
- [M052-vision-recap-ultimate-ai-workstation](../backlog/milestones/M052-vision-recap-ultimate-ai-workstation.md)  ·  170 R-rows  ·  M052 — Vision recap — Ultimate AI Workstation
- [M053-implementation-language-11-build-phases](../backlog/milestones/M053-implementation-language-11-build-phases.md)  ·  170 R-rows  ·  M053 — Implementation language — 11 build phases (Phase 0..10)
- [M054-11-typed-interfaces](../backlog/milestones/M054-11-typed-interfaces.md)  ·  170 R-rows  ·  M054 — 11 typed interfaces — Gateway / Profile Resolver / Router / Model Adapter / Policy / Tool / Memory / Workflow / Eval / Observability / AVX Cortex
- [M055-failure-modes-10-taxonomies](../backlog/milestones/M055-failure-modes-10-taxonomies.md)  ·  170 R-rows  ·  M055 — Failure modes — 10 taxonomies with detect / contain / explain / recover / learn
- [M056-trust-boundaries-and-authority](../backlog/milestones/M056-trust-boundaries-and-authority.md)  ·  170 R-rows  ·  M056 — Trust boundaries and authority — 7 authority levels / 5 trust rings
- [M057-data-flow-and-lifecycle-12-step](../backlog/milestones/M057-data-flow-and-lifecycle-12-step.md)  ·  170 R-rows  ·  M057 — Data flow and lifecycle — 12-step task lifecycle
- [M058-hardware-aware-scheduling-goldilocks](../backlog/milestones/M058-hardware-aware-scheduling-goldilocks.md)  ·  170 R-rows  ·  M058 — Hardware-aware scheduling — the Goldilocks scheduler
- [M059-sovereign-close-peace-machine](../backlog/milestones/M059-sovereign-close-peace-machine.md)  ·  170 R-rows  ·  M059 — Sovereign close — the peace machine
- [M060-cockpit-and-dashboards-ux-surface](../backlog/milestones/M060-cockpit-and-dashboards-ux-surface.md)  ·  170 R-rows  ·  M060 — Cockpit + 20+ dashboards + UX surface
- [M061-avx-plus-plus-canon-update-backward-sweep-2026-05-19](../backlog/milestones/M061-avx-plus-plus-canon-update-backward-sweep-2026-05-19.md)  ·  170 R-rows  ·  M061 — AVX++ canon update — backward-sweep redefinitions (2026-05-19)
- [M062-macro-arc-10-pr-foundation-scaffold](../backlog/milestones/M062-macro-arc-10-pr-foundation-scaffold.md)  ·  170 R-rows  ·  M062 — Macro-Arc 10-PR Foundation Scaffold (Stage 1)
- [M063-sfif-discipline-scaffold-foundation-infrastructure-features](../backlog/milestones/M063-sfif-discipline-scaffold-foundation-infrastructure-features.md)  ·  170 R-rows  ·  M063 — SFIF discipline — Scaffold → Foundation → Infrastructure → Features
- [M064-debian-as-ark-and-q-016-distro-base-reconsideration](../backlog/milestones/M064-debian-as-ark-and-q-016-distro-base-reconsideration.md)  ·  170 R-rows  ·  M064 — "Debian as Ark" framing + Q-016 distro-base reconsideration
- [M065-five-stage-gates-sg1-sg5-checkpoint-ritual](../backlog/milestones/M065-five-stage-gates-sg1-sg5-checkpoint-ritual.md)  ·  170 R-rows  ·  M065 — Five Stage Gates SG1-SG5 + ExitPlanMode checkpoint ritual
- [M066-trinity-framework-genesis-pulse-weaver-auditor](../backlog/milestones/M066-trinity-framework-genesis-pulse-weaver-auditor.md)  ·  170 R-rows  ·  M066 — Trinity Framework Genesis — The Pulse / The Weaver / The Auditor
- [M067-custom-kernel-build-pipeline-znver5-avx512](../backlog/milestones/M067-custom-kernel-build-pipeline-znver5-avx512.md)  ·  170 R-rows  ·  M067 — Custom kernel build pipeline (-march=znver5 / GCC 14 / Linux 6.12 / bindeb-pkg)
- [M068-zfs-storage-architecture](../backlog/milestones/M068-zfs-storage-architecture.md)  ·  170 R-rows  ·  M068 — ZFS storage architecture (tank/context + sync=always + ashift=12 + lz4 + recordsize)
- [M070-dual-ccd-cache-topology-and-core-pinning](../backlog/milestones/M070-dual-ccd-cache-topology-and-core-pinning.md)  ·  170 R-rows  ·  M070 — Dual-CCD cache topology + core pinning (CCD 0 = Pulse / CCD 1 = Weaver+Auditor+Host)
- [M071-atomic-state-transition-protocol-weaver-execution](../backlog/milestones/M071-atomic-state-transition-protocol-weaver-execution.md)  ·  170 R-rows  ·  M071 — Atomic State Transition Protocol (The Weaver Execution) — O_DIRECT + POSIX AIO + lockless ZFS
- [M072-master-bootstrap-verification-checklist](../backlog/milestones/M072-master-bootstrap-verification-checklist.md)  ·  170 R-rows  ·  M072 — Master Bootstrap Verification Checklist (6-phase operational grid)
- [M073-one-bit-ternary-logic-bitlinear-core](../backlog/milestones/M073-one-bit-ternary-logic-bitlinear-core.md)  ·  170 R-rows  ·  M073 — 1-bit (ternary) logic + BitLinear Core ({-1, 0, +1} ≈ 1.58 bits/parameter)
- [M074-avx-512-vnni-hardware-fusion](../backlog/milestones/M074-avx-512-vnni-hardware-fusion.md)  ·  170 R-rows  ·  M074 — AVX-512 VNNI hardware fusion (512-bit ZMM / 64× INT8 / VPDPBUSD single-cycle / LUT matrix ops)
- [M075-srp-hardware-topology-conductor-logic-oracle](../backlog/milestones/M075-srp-hardware-topology-conductor-logic-oracle.md)  ·  170 R-rows  ·  M075 — SRP hardware topology mapping (Conductor on CPU / Logic on GPU 0 / Oracle on GPU 1)
- [M076-three-load-balancing-profiles-ultra-sovereign-burst-deep-context](../backlog/milestones/M076-three-load-balancing-profiles-ultra-sovereign-burst-deep-context.md)  ·  170 R-rows  ·  M076 — Three load-balancing profiles (Ultra-Sovereign Efficiency / High-Concurrency Burst / Deep Context Synthesis) — LAST MUST-ADD MILESTONE
- [M077-nvfp4-pretraining-and-inference-pipeline](../backlog/milestones/M077-nvfp4-pretraining-and-inference-pipeline.md)  ·  170 R-rows  ·  M077 — NVFP4 pretraining + inference pipeline (Blackwell-native 4-bit, RHT + 2D quantization + stochastic rounding + selective high-precision)
- [M078-holderpo-grpo-post-training-pipeline](../backlog/milestones/M078-holderpo-grpo-post-training-pipeline.md)  ·  170 R-rows  ·  M078 — HölderPO + GRPO post-training pipeline (Hölder-mean token aggregation + dynamic-p annealing)
- [M079-activation-steering-interpretability-surface](../backlog/milestones/M079-activation-steering-interpretability-surface.md)  ·  170 R-rows  ·  M079 — Activation steering interpretability surface (white-box vs black-box intervention class)
- [M080-hrm-hierarchical-reasoning-model-architectural-class](../backlog/milestones/M080-hrm-hierarchical-reasoning-model-architectural-class.md)  ·  170 R-rows  ·  M080 — HRM (Hierarchical Reasoning Model) architectural class — recurrent two-timescale brain-inspired alternative to Transformer/Mamba/BitNet
- [M081-whitelabel-architecture-audit-and-mechanism](../backlog/milestones/M081-whitelabel-architecture-audit-and-mechanism.md)  ·  240 R-rows  ·  M081 — Whitelabel Architecture — Debian surface audit + declarative rebrand mechanism
- [M082-tdd-harness-architecture-hardware-free-validation](../backlog/milestones/M082-tdd-harness-architecture-hardware-free-validation.md)  ·  240 R-rows  ·  M082 — TDD Harness Architecture — hardware-free validation (macro-arc PRs 9 + 10)
- [M083-dflash-speculative-decoding-fast-path](../backlog/milestones/M083-dflash-speculative-decoding-fast-path.md)  ·  170 R-rows  ·  M083 — DFlash speculative decoding fast-path — task-type-gated 3× decode acceleration
- [M084-opnsense-sdwan-boundary-contract-tetragon-dropout-resilience](../backlog/milestones/M084-opnsense-sdwan-boundary-contract-tetragon-dropout-resilience.md)  ·  170 R-rows  ·  M084 — OPNsense/SD-WAN boundary contract + Tetragon-dropout resilience (Zero-Trust dual-NIC perimeter)

## Status conventions (per `selfdef/context.md` + `sovereign-os/context.md`)

- **catalog ✓** = the milestone's R-rows are written + traceable to the
  source dump (avx-plus-plus, the transposition dump, or earlier). All 130 milestones meet this bar.
- **at prod** = the milestone's deliverable has reached production through
  all §1g layers (core → cli → tui → api → mcp → dashboard → webapp →
  service). M060 mirror producers are the most recent to reach this bar
  (PR `cyberpunk042/selfdef#200` + PR `cyberpunk042/sovereign-os#12`).
- "Not yet wired" = catalog ✓ + Rust crate exists, but the daemon-side
  producer or operator surface that brings the milestone to prod is
  pending (e.g. `selfdef-audit-mirror` exists as a typed-mirror crate,
  but the daemon doesn't yet write `audit.json` to the mirror dir).

## Project-boundary discipline (MS043 R10212)

- IPS state mutation lives in **selfdef only**.
- sovereign-os renders **READ-ONLY** (web NEVER mutates IPS state).
- The two solutions combine through the MS007 typed-mirror crates; each is
  independently bootable (selfdef per MS043 R10217-R10225 offline-survivability;
  sovereign-os shows mirror-status=offline when selfdef is absent).

## Doctrine pointers

- `selfdef/context.md` § "Current arc" — latest selfdef state.
- `sovereign-os/context.md` § "Current arc" — latest sovereign-os state.
- `selfdef/backlog/INDEX.md` + `sovereign-os/backlog/INDEX.md` — per-repo
  factual indexes (R-row counts per milestone).
- `sovereign-os/docs/operator/m060-deployment-guide.md` — operator
  deployment recipe for the most-recent prod milestone (M060 cockpit
  mirror chain).
- `docs/standing-directives/two-ultimate-solutions.md` — operator doctrine
  on independence + combination.

## What's NOT in this doc

- A per-R-row dependency graph (operator-controlled prioritization; not
  amenable to mechanical derivation).
- "Target completion dates" (operator-controlled; multi-year project).
- New requirements (the catalog is intentionally complete per the
  operator's "Catalog phase — COMPLETE" + "Do not get stuck at the
  cataloging step" standing direction).

This synthesis surfaces the existing structure for cross-repo
navigation; production work continues milestone-by-milestone.
