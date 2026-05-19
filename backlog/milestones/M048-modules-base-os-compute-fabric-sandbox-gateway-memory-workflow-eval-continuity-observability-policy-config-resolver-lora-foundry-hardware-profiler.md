# M048 — Modules — Base OS / Compute Fabric / Sandbox Fabric / Gateway / Memory OS / Workflow Compiler / Eval-Value / Continuity / Observability / Policy / Config Resolver / LoRA Foundry / Hardware Profiler

> Parent: `backlog/milestones/INDEX.md` row M048 (dump 14402–14812).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 14402–14812. Operator directives 14402 + 14812: "Great Great. continue. do resaerchs online too. Think of every modules and features and configurations and continuity of what we are doing".
> All entries below extract verbatim. No invention.

## Epics (E0458–E0467)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0458 | Continuity Principle — "Now we think in modules, continuity, and configuration surfaces. Not static config files as the goal, but modules as living organs of Sovereign-OS"; "Every module must answer" 7 questions: How does it start? / How does it stop? / How does it recover? / How does it checkpoint? / How does it expose cost/risk? / How does the user choose its behavior? / How does it prove what happened?; "That is the continuity standard" | 14420–14442 |
| E0459 | Module 1: Base OS Module — Debian 13 / Ubuntu 24 base; 10 responsibilities (kernel / firmware / NVIDIA drivers / AppArmor / cgroup v2 / systemd / ZFS / LUKS / networking / VFIO-IOMMU); 5 config modes (stable / ai-driver-latest / secure / developer / offline); "OS base must be reproducible enough to rebuild, but flexible enough for NVIDIA reality"; "Nix-style systems prove the value of reproducible configuration and rollback, while Debian/Ubuntu give the practical AI driver base"; Chezmoi supports encrypted dotfiles with age/gpg/git-crypt + password manager integration (chezmoi.io/user-guide/encryption); principle "declarative where it protects continuity / imperative where hardware reality demands adaptation" | 14446–14490 |
| E0460 | Module 2: Compute Fabric — 4 compute workers: blackwell-oracle / 3090-scout / cpu-avx-cortex / cloud-optional; each worker exposes 7 capabilities (capabilities / model roles / current load / memory pressure / cost estimate / privacy class / available precision); Hyper feature: dynamic placement — "same task can route: local SLM / 3090 scout / Blackwell oracle / cloud Anthropic / cloud OpenAI / human gate"; "The user chooses profile; runtime chooses exact placement" | 14494–14534 |
| E0461 | Module 3: Container/Sandbox Fabric — Podman Quadlet runs Podman containers under systemd declaratively (docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html); NVIDIA Container Toolkit supports CDI specs for exposing NVIDIA devices to Podman/CRI-O/containerd (docs.nvidia.com/datacenter/cloud-native/container-toolkit/1.14.4/cdi-support.html); clean pattern (agent containers as systemd-managed units / GPU access through CDI when allowed / rootless where possible / rootful only when needed / resource limits through cgroup v2); 8 sandbox profiles (read-only repo / write-workspace / network-denied / network-docs-only / gpu-scout / no-gpu / vm-isolated / vfio-3090) | 14538–14580 |
| E0462 | Module 4: Gateway — Anthropic-first; exposes 6 surfaces (Anthropic Messages-compatible API / OpenAI-compatible API shim / MCP bridge / Claude Code integration / OpenCode-Cline compatibility / cost and route ledger); Hyper feature: provider inversion — "Instead of tools owning provider keys: client → Sovereign Gateway → local/cloud/model router"; gateway owns 7 responsibilities (cost / privacy / redaction / routing / profiles / approval / tracing) | 14584–14610 |
| E0463 | Module 5+6: Memory OS + Workflow Compiler — Memory OS 8 memory types (working / episodic / semantic / procedural / temporal graph / value memory / KV-prefix cache / artifact memory) + 4 continuity rules (raw trace never destroyed without policy / summaries are derived not truth / memory writes gated by trust / user can inspect-remove-export) + Hyper feature memory-as-tools (6 calls: search / write / link / verify / forget / promote); Workflow Compiler input (7: user goal / profile / environment map / policy / model registry / tool catalog / hardware pressure) → output (7: workflow DAG / tool calls / model calls / checkpoints / human gates / evals / commit conditions) + Hyper feature adaptive recompile ("If tests fail or context changes: do not blindly continue. re-map / re-plan / re-route") | 14614–14674 |
| E0464 | Module 7+8: Eval/Value + Continuity Manager — Eval Plane scores every run on 10 dimensions (correctness / evidence / test pass / schema validity / risk / cost / latency / human burden / reversibility / learning value); profile weights for 8 modes (fast / careful / offline / research / autonomous / production / experimental / communication-peace); Continuity Manager — "sleeper module" — uses (ZFS snapshots / Podman-CRIU checkpoints / workflow hibernation / context compaction / model server warm pools / session resume); Podman supports checkpoint/restore with CRIU (use experimentally for warm CPU/tool sandboxes; for GPU/model state rely more on warm services and KV/context references); 8 continuity states (active / paused / hibernated / checkpointed / archived / quarantined / promoted / rolled back) | 14678–14720 |
| E0465 | Module 9+10: Observability + LoRA Foundry — Observability sources (9: OpenTelemetry traces / journald / DCGM / PSI / eBPF / ZFS events / test output / gateway logs / cost ledger); answers 6 questions (what happened? / what changed? / which model decided? / which policy allowed it? / what did it cost? / what pressure did hardware experience?); LoRA Foundry — Before training (6: profile tuning / router tuning / memory tuning / workflow tuning / prompt-program tuning / model choice) → Then (7: trace curation / dataset creation / LoRA training / adapter serving / eval gating / profile assignment); vLLM supports dynamic LoRA serving (docs.vllm.ai/en/stable/features/lora/) + SGLang supports multi-adapter serving (sgl-project.github.io/advanced_features/lora.html); "behavior specialize without duplicating whole models" | 14724–14758 |
| E0466 | Configuration Surfaces — "Every module should expose choices at three levels": User (simple profiles and prompts) / Power user (toggles + budgets + allowed providers + sandbox levels) / System (policy + hardware profile + routing weights + eval thresholds); "That is how you keep flexibility without chaos" | 14762–14780 |
| E0467 | The Continuity Stack 6-layer + KEY LINE — Hardware continuity (stable drivers + thermal/power profiles + GPU service health) / OS continuity (systemd services + cgroups + AppArmor + ZFS + LUKS) / Agent continuity (workflow checkpoints + session hibernation + sandbox snapshots) / Memory continuity (traces + graph + skills + evals + user preferences) / Model continuity (warm servers + adapters + registry + quant-eval lineage) / Human continuity (visible choices + consent + explanations + rollback); "That is the difference from cloud. Cloud gives model continuity. Sovereign-OS gives life/work continuity"; KEY LINE — "Every module is a controlled continuation of user intent across hardware, software, memory, and time" — "That is the architecture becoming whole" | 14784–14810 |

## Modules (M00799–M00815)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00799 | Continuity 7-question standard — start / stop / recover / checkpoint / expose cost+risk / user choice / proof | 14428–14438 | E0458 |
| M00800 | Module 1: Base OS — Debian 13 / Ubuntu 24 base with 10 responsibilities + 5 config modes + declarative-vs-imperative principle | 14448–14488 | E0459 |
| M00801 | Module 2: Compute Fabric — 4 workers (blackwell-oracle / 3090-scout / cpu-avx-cortex / cloud-optional) | 14498–14506 | E0460 |
| M00802 | Compute worker capability schema — 7 fields (capabilities / model roles / current load / memory pressure / cost estimate / privacy class / available precision) | 14510–14518 | E0460 |
| M00803 | Hyper feature — dynamic placement (6 routing destinations) | 14522–14532 | E0460 |
| M00804 | Module 3: Container/Sandbox Fabric — Podman Quadlet + NVIDIA CDI + 5-rule clean pattern | 14542–14564 | E0461 |
| M00805 | Sandbox profile catalog — 8 profiles (read-only repo / write-workspace / network-denied / network-docs-only / gpu-scout / no-gpu / vm-isolated / vfio-3090) | 14570–14578 | E0461 |
| M00806 | Module 4: Gateway — Anthropic-first with 6 surface protocols + 7-responsibility provider-inversion ownership | 14586–14608 | E0462 |
| M00807 | Module 5: Memory OS — 8 memory types + 4 continuity rules + 6 memory-as-tools calls | 14616–14644 | E0463 |
| M00808 | Module 6: Workflow Compiler — 7-input + 7-output + adaptive-recompile hyper feature | 14648–14672 | E0463 |
| M00809 | Module 7: Eval/Value Plane — 10-dimension scoring + 8-profile weighting | 14682–14702 | E0464 |
| M00810 | Module 8: Continuity Manager — sleeper module; uses 6 primitives + 8 continuity states | 14706–14718 | E0464 |
| M00811 | Module 9: Observability — 9-source aggregation + 6 questions answered | 14728–14744 | E0465 |
| M00812 | Module 10: LoRA Foundry — 6 before-training + 7 training-to-deployment steps | 14748–14756 | E0465 |
| M00813 | Configuration Surfaces 3-level — User / Power user / System | 14764–14778 | E0466 |
| M00814 | Continuity Stack 6-layer — Hardware / OS / Agent / Memory / Model / Human | 14784–14808 | E0467 |
| M00815 | KEY LINE module — "Every module is a controlled continuation of user intent across hardware, software, memory, and time" | 14810 | E0467 |

## Features (F03996–F04080)

| Feature ID | Phrase | Dump line | Parent module |
|---|---|---|---|
| F03996 | "Now we think in modules, continuity, and configuration surfaces" | 14420 | E0458 |
| F03997 | "Not static config files as the goal" | 14422 | E0458 |
| F03998 | "But modules as living organs of Sovereign-OS" | 14422 | E0458 |
| F03999 | Continuity question — How does it start? | 14428 | M00799 |
| F04000 | Continuity question — How does it stop? | 14429 | M00799 |
| F04001 | Continuity question — How does it recover? | 14430 | M00799 |
| F04002 | Continuity question — How does it checkpoint? | 14431 | M00799 |
| F04003 | Continuity question — How does it expose cost/risk? | 14432 | M00799 |
| F04004 | Continuity question — How does the user choose its behavior? | 14433 | M00799 |
| F04005 | Continuity question — How does it prove what happened? | 14434 | M00799 |
| F04006 | "That is the continuity standard" | 14442 | E0458 |
| F04007 | Module 1 — Base OS = Debian 13 / Ubuntu 24 | 14448 | M00800 |
| F04008 | Base OS responsibility — kernel | 14452 | M00800 |
| F04009 | Base OS responsibility — firmware | 14453 | M00800 |
| F04010 | Base OS responsibility — NVIDIA drivers | 14454 | M00800 |
| F04011 | Base OS responsibility — AppArmor | 14455 | M00800 |
| F04012 | Base OS responsibility — cgroup v2 | 14456 | M00800 |
| F04013 | Base OS responsibility — systemd | 14457 | M00800 |
| F04014 | Base OS responsibility — ZFS | 14458 | M00800 |
| F04015 | Base OS responsibility — LUKS | 14459 | M00800 |
| F04016 | Base OS responsibility — networking | 14460 | M00800 |
| F04017 | Base OS responsibility — VFIO/IOMMU | 14461 | M00800 |
| F04018 | Base OS config mode — stable | 14466 | M00800 |
| F04019 | Base OS config mode — ai-driver-latest | 14467 | M00800 |
| F04020 | Base OS config mode — secure | 14468 | M00800 |
| F04021 | Base OS config mode — developer | 14469 | M00800 |
| F04022 | Base OS config mode — offline | 14470 | M00800 |
| F04023 | OS base — "reproducible enough to rebuild, but flexible enough for NVIDIA reality" | 14474 | M00800 |
| F04024 | "Nix-style systems prove the value of reproducible configuration and rollback" | 14476 | M00800 |
| F04025 | "Debian/Ubuntu give the practical AI driver base" | 14478 | M00800 |
| F04026 | Chezmoi — supports encrypted dotfiles with age/gpg/git-crypt | 14480 | M00800 |
| F04027 | Chezmoi — password manager integration | 14481 | M00800 |
| F04028 | Chezmoi URL — chezmoi.io/user-guide/encryption | 14482 | M00800 |
| F04029 | Base OS principle — "declarative where it protects continuity" | 14486 | M00800 |
| F04030 | Base OS principle — "imperative where hardware reality demands adaptation" | 14488 | M00800 |
| F04031 | Module 2 — Compute Fabric | 14494 | M00801 |
| F04032 | Compute worker — blackwell-oracle | 14498 | M00801 |
| F04033 | Compute worker — 3090-scout | 14499 | M00801 |
| F04034 | Compute worker — cpu-avx-cortex | 14500 | M00801 |
| F04035 | Compute worker — cloud-optional | 14501 | M00801 |
| F04036 | Capability — capabilities (advertised feature set) | 14510 | M00802 |
| F04037 | Capability — model roles | 14511 | M00802 |
| F04038 | Capability — current load | 14512 | M00802 |
| F04039 | Capability — memory pressure | 14513 | M00802 |
| F04040 | Capability — cost estimate | 14514 | M00802 |
| F04041 | Capability — privacy class | 14515 | M00802 |
| F04042 | Capability — available precision | 14516 | M00802 |
| F04043 | Hyper feature — dynamic placement | 14520 | M00803 |
| F04044 | Routing destination — local SLM | 14524 | M00803 |
| F04045 | Routing destination — 3090 scout | 14525 | M00803 |
| F04046 | Routing destination — Blackwell oracle | 14526 | M00803 |
| F04047 | Routing destination — cloud Anthropic | 14527 | M00803 |
| F04048 | Routing destination — cloud OpenAI | 14528 | M00803 |
| F04049 | Routing destination — human gate | 14529 | M00803 |
| F04050 | "The user chooses profile; runtime chooses exact placement" | 14534 | M00803 |
| F04051 | Module 3 — Container/Sandbox Fabric | 14538 | M00804 |
| F04052 | Podman Quadlet — runs Podman containers under systemd declaratively | 14542 | M00804 |
| F04053 | Podman Quadlet URL — docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html | 14542 | M00804 |
| F04054 | NVIDIA Container Toolkit — supports CDI specs for NVIDIA devices | 14544 | M00804 |
| F04055 | NVIDIA CDI — exposes NVIDIA devices to Podman / CRI-O / containerd | 14545 | M00804 |
| F04056 | NVIDIA CDI URL — docs.nvidia.com/datacenter/cloud-native/container-toolkit/1.14.4/cdi-support.html | 14546 | M00804 |
| F04057 | Clean pattern — agent containers as systemd-managed units | 14550 | M00804 |
| F04058 | Clean pattern — GPU access through CDI when allowed | 14551 | M00804 |
| F04059 | Clean pattern — rootless where possible | 14552 | M00804 |
| F04060 | Clean pattern — rootful only when needed | 14553 | M00804 |
| F04061 | Clean pattern — resource limits through cgroup v2 | 14554 | M00804 |
| F04062 | Sandbox profile — read-only repo | 14570 | M00805 |
| F04063 | Sandbox profile — write-workspace | 14571 | M00805 |
| F04064 | Sandbox profile — network-denied | 14572 | M00805 |
| F04065 | Sandbox profile — network-docs-only | 14573 | M00805 |
| F04066 | Sandbox profile — gpu-scout | 14574 | M00805 |
| F04067 | Sandbox profile — no-gpu | 14575 | M00805 |
| F04068 | Sandbox profile — vm-isolated | 14576 | M00805 |
| F04069 | Sandbox profile — vfio-3090 | 14577 | M00805 |
| F04070 | Module 4 — Gateway (Anthropic-first) | 14584–14586 | M00806 |
| F04071 | Gateway surface — Anthropic Messages-compatible API | 14590 | M00806 |
| F04072 | Gateway surface — OpenAI-compatible API shim | 14591 | M00806 |
| F04073 | Gateway surface — MCP bridge | 14592 | M00806 |
| F04074 | Gateway surface — Claude Code integration | 14593 | M00806 |
| F04075 | Gateway surface — OpenCode/Cline compatibility | 14594 | M00806 |
| F04076 | Gateway surface — cost and route ledger | 14595 | M00806 |
| F04077 | Hyper feature — provider inversion | 14598 | M00806 |
| F04078 | Provider inversion — "Instead of tools owning provider keys" | 14600 | M00806 |
| F04079 | Provider inversion — "client → Sovereign Gateway → local/cloud/model router" | 14602 | M00806 |
| F04080 | Modules 5+6+7+8+9+10 + Configuration Surfaces 3-level + Continuity Stack 6-layer + KEY LINE | 14614–14810 | M00807 + M00808 + M00809 + M00810 + M00811 + M00812 + M00813 + M00814 + M00815 |

## Requirements (R07991–R08160)

| Req ID | Phrase | Dump line | Parent feature | Negotiability | Layer-B metric | Priority |
|---|---|---|---|---|---|---|
| R07991 | "Now we think in modules, continuity, and configuration surfaces" | 14420 | F03996 | non-negotiable | false | 10 |
| R07992 | "Not static config files as the goal" | 14422 | F03997 | non-negotiable | false | 10 |
| R07993 | "Modules as living organs of Sovereign-OS" | 14422 | F03998 | non-negotiable | false | 10 |
| R07994 | Continuity question — How does it start? | 14428 | F03999 | non-negotiable | false | 10 |
| R07995 | Continuity question — How does it stop? | 14429 | F04000 | non-negotiable | false | 10 |
| R07996 | Continuity question — How does it recover? | 14430 | F04001 | non-negotiable | false | 10 |
| R07997 | Continuity question — How does it checkpoint? | 14431 | F04002 | non-negotiable | false | 10 |
| R07998 | Continuity question — How does it expose cost/risk? | 14432 | F04003 | non-negotiable | false | 10 |
| R07999 | Continuity question — How does the user choose its behavior? | 14433 | F04004 | non-negotiable | false | 10 |
| R08000 | Continuity question — How does it prove what happened? | 14434 | F04005 | non-negotiable | false | 10 |
| R08001 | "That is the continuity standard" | 14442 | F04006 | non-negotiable | false | 10 |
| R08002 | Module 1 — Base OS = Debian 13 / Ubuntu 24 | 14448 | F04007 | non-negotiable | false | 10 |
| R08003 | Base OS owns — kernel | 14452 | F04008 | non-negotiable | false | 10 |
| R08004 | Base OS owns — firmware | 14453 | F04009 | non-negotiable | false | 10 |
| R08005 | Base OS owns — NVIDIA drivers | 14454 | F04010 | non-negotiable | false | 10 |
| R08006 | Base OS owns — AppArmor | 14455 | F04011 | non-negotiable | false | 10 |
| R08007 | Base OS owns — cgroup v2 | 14456 | F04012 | non-negotiable | false | 10 |
| R08008 | Base OS owns — systemd | 14457 | F04013 | non-negotiable | false | 10 |
| R08009 | Base OS owns — ZFS | 14458 | F04014 | non-negotiable | false | 10 |
| R08010 | Base OS owns — LUKS | 14459 | F04015 | non-negotiable | false | 10 |
| R08011 | Base OS owns — networking | 14460 | F04016 | non-negotiable | false | 10 |
| R08012 | Base OS owns — VFIO/IOMMU | 14461 | F04017 | non-negotiable | false | 10 |
| R08013 | Base OS config mode — stable | 14466 | F04018 | non-negotiable | false | 10 |
| R08014 | Base OS config mode — ai-driver-latest | 14467 | F04019 | non-negotiable | false | 10 |
| R08015 | Base OS config mode — secure | 14468 | F04020 | non-negotiable | false | 10 |
| R08016 | Base OS config mode — developer | 14469 | F04021 | non-negotiable | false | 10 |
| R08017 | Base OS config mode — offline | 14470 | F04022 | non-negotiable | false | 10 |
| R08018 | Base OS — "reproducible enough to rebuild" | 14474 | F04023 | non-negotiable | false | 10 |
| R08019 | Base OS — "flexible enough for NVIDIA reality" | 14474 | F04023 | non-negotiable | false | 10 |
| R08020 | "Nix-style systems prove the value of reproducible configuration and rollback" | 14476 | F04024 | non-negotiable | false | 10 |
| R08021 | "Debian/Ubuntu give the practical AI driver base" | 14478 | F04025 | non-negotiable | false | 10 |
| R08022 | Chezmoi — supports encrypted dotfiles with age | 14480 | F04026 | non-negotiable | false | 10 |
| R08023 | Chezmoi — supports encrypted dotfiles with gpg | 14480 | F04026 | non-negotiable | false | 10 |
| R08024 | Chezmoi — supports encrypted dotfiles with git-crypt | 14480 | F04026 | non-negotiable | false | 10 |
| R08025 | Chezmoi — password manager integration | 14481 | F04027 | non-negotiable | false | 10 |
| R08026 | Chezmoi URL — chezmoi.io/user-guide/encryption | 14482 | F04028 | non-negotiable | false | 10 |
| R08027 | Base OS principle — "declarative where it protects continuity" | 14486 | F04029 | non-negotiable | false | 10 |
| R08028 | Base OS principle — "imperative where hardware reality demands adaptation" | 14488 | F04030 | non-negotiable | false | 10 |
| R08029 | Module 2 — Compute Fabric | 14494 | F04031 | non-negotiable | false | 10 |
| R08030 | Compute worker — blackwell-oracle | 14498 | F04032 | non-negotiable | false | 10 |
| R08031 | Compute worker — 3090-scout | 14499 | F04033 | non-negotiable | false | 10 |
| R08032 | Compute worker — cpu-avx-cortex | 14500 | F04034 | non-negotiable | false | 10 |
| R08033 | Compute worker — cloud-optional | 14501 | F04035 | non-negotiable | false | 10 |
| R08034 | Worker capability — capabilities | 14510 | F04036 | non-negotiable | false | 10 |
| R08035 | Worker capability — model roles | 14511 | F04037 | non-negotiable | false | 10 |
| R08036 | Worker capability — current load | 14512 | F04038 | non-negotiable | false | 10 |
| R08037 | Worker capability — memory pressure | 14513 | F04039 | non-negotiable | false | 10 |
| R08038 | Worker capability — cost estimate | 14514 | F04040 | non-negotiable | false | 10 |
| R08039 | Worker capability — privacy class | 14515 | F04041 | non-negotiable | false | 10 |
| R08040 | Worker capability — available precision | 14516 | F04042 | non-negotiable | false | 10 |
| R08041 | Hyper feature — dynamic placement | 14520 | F04043 | non-negotiable | false | 10 |
| R08042 | Routing destination — local SLM | 14524 | F04044 | non-negotiable | false | 10 |
| R08043 | Routing destination — 3090 scout | 14525 | F04045 | non-negotiable | false | 10 |
| R08044 | Routing destination — Blackwell oracle | 14526 | F04046 | non-negotiable | false | 10 |
| R08045 | Routing destination — cloud Anthropic | 14527 | F04047 | non-negotiable | false | 10 |
| R08046 | Routing destination — cloud OpenAI | 14528 | F04048 | non-negotiable | false | 10 |
| R08047 | Routing destination — human gate | 14529 | F04049 | non-negotiable | false | 10 |
| R08048 | "The user chooses profile; runtime chooses exact placement" | 14534 | F04050 | non-negotiable | false | 10 |
| R08049 | Module 3 — Container/Sandbox Fabric | 14538 | F04051 | non-negotiable | false | 10 |
| R08050 | Podman Quadlet — runs Podman containers under systemd declaratively | 14542 | F04052 | non-negotiable | false | 10 |
| R08051 | Podman Quadlet URL — docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html | 14542 | F04053 | non-negotiable | false | 10 |
| R08052 | NVIDIA Container Toolkit — supports CDI specs | 14544 | F04054 | non-negotiable | false | 10 |
| R08053 | NVIDIA CDI — exposes NVIDIA devices to Podman | 14545 | F04055 | non-negotiable | false | 10 |
| R08054 | NVIDIA CDI — exposes NVIDIA devices to CRI-O | 14545 | F04055 | non-negotiable | false | 10 |
| R08055 | NVIDIA CDI — exposes NVIDIA devices to containerd | 14545 | F04055 | non-negotiable | false | 10 |
| R08056 | NVIDIA CDI URL — docs.nvidia.com/datacenter/cloud-native/container-toolkit/1.14.4/cdi-support.html | 14546 | F04056 | non-negotiable | false | 10 |
| R08057 | Clean pattern — agent containers as systemd-managed units | 14550 | F04057 | non-negotiable | false | 10 |
| R08058 | Clean pattern — GPU access through CDI when allowed | 14551 | F04058 | non-negotiable | false | 10 |
| R08059 | Clean pattern — rootless where possible | 14552 | F04059 | non-negotiable | false | 10 |
| R08060 | Clean pattern — rootful only when needed | 14553 | F04060 | non-negotiable | false | 10 |
| R08061 | Clean pattern — resource limits through cgroup v2 | 14554 | F04061 | non-negotiable | false | 10 |
| R08062 | Sandbox profile — read-only repo | 14570 | F04062 | non-negotiable | false | 10 |
| R08063 | Sandbox profile — write-workspace | 14571 | F04063 | non-negotiable | false | 10 |
| R08064 | Sandbox profile — network-denied | 14572 | F04064 | non-negotiable | false | 10 |
| R08065 | Sandbox profile — network-docs-only | 14573 | F04065 | non-negotiable | false | 10 |
| R08066 | Sandbox profile — gpu-scout | 14574 | F04066 | non-negotiable | false | 10 |
| R08067 | Sandbox profile — no-gpu | 14575 | F04067 | non-negotiable | false | 10 |
| R08068 | Sandbox profile — vm-isolated | 14576 | F04068 | non-negotiable | false | 10 |
| R08069 | Sandbox profile — vfio-3090 | 14577 | F04069 | non-negotiable | false | 10 |
| R08070 | Module 4 — Gateway | 14584 | F04070 | non-negotiable | false | 10 |
| R08071 | Gateway — Anthropic-first | 14586 | F04070 | non-negotiable | false | 10 |
| R08072 | Gateway surface — Anthropic Messages-compatible API | 14590 | F04071 | non-negotiable | false | 10 |
| R08073 | Gateway surface — OpenAI-compatible API shim | 14591 | F04072 | non-negotiable | false | 10 |
| R08074 | Gateway surface — MCP bridge | 14592 | F04073 | non-negotiable | false | 10 |
| R08075 | Gateway surface — Claude Code integration | 14593 | F04074 | non-negotiable | false | 10 |
| R08076 | Gateway surface — OpenCode/Cline compatibility | 14594 | F04075 | non-negotiable | false | 10 |
| R08077 | Gateway surface — cost and route ledger | 14595 | F04076 | non-negotiable | false | 10 |
| R08078 | Hyper feature — provider inversion | 14598 | F04077 | non-negotiable | false | 10 |
| R08079 | Provider inversion — "Instead of tools owning provider keys" | 14600 | F04078 | non-negotiable | false | 10 |
| R08080 | Provider inversion flow — client → Sovereign Gateway → local/cloud/model router | 14602 | F04079 | non-negotiable | false | 10 |
| R08081 | Gateway owns — cost | 14606 | M00806 | non-negotiable | false | 10 |
| R08082 | Gateway owns — privacy | 14607 | M00806 | non-negotiable | false | 10 |
| R08083 | Gateway owns — redaction | 14608 | M00806 | non-negotiable | false | 10 |
| R08084 | Gateway owns — routing | 14609 | M00806 | non-negotiable | false | 10 |
| R08085 | Gateway owns — profiles | 14610 | M00806 | non-negotiable | false | 10 |
| R08086 | Gateway owns — approval | 14611 | M00806 | non-negotiable | false | 10 |
| R08087 | Gateway owns — tracing | 14612 | M00806 | non-negotiable | false | 10 |
| R08088 | Module 5 — Memory OS | 14614 | M00807 | non-negotiable | false | 10 |
| R08089 | Memory type — working | 14618 | M00807 | non-negotiable | false | 10 |
| R08090 | Memory type — episodic | 14619 | M00807 | non-negotiable | false | 10 |
| R08091 | Memory type — semantic | 14620 | M00807 | non-negotiable | false | 10 |
| R08092 | Memory type — procedural | 14621 | M00807 | non-negotiable | false | 10 |
| R08093 | Memory type — temporal graph | 14622 | M00807 | non-negotiable | false | 10 |
| R08094 | Memory type — value memory | 14623 | M00807 | non-negotiable | false | 10 |
| R08095 | Memory type — KV/prefix cache | 14624 | M00807 | non-negotiable | false | 10 |
| R08096 | Memory type — artifact memory | 14625 | M00807 | non-negotiable | false | 10 |
| R08097 | Continuity rule — raw trace never destroyed without policy | 14630 | M00807 | non-negotiable | false | 10 |
| R08098 | Continuity rule — summaries are derived, not truth | 14631 | M00807 | non-negotiable | false | 10 |
| R08099 | Continuity rule — memory writes gated by trust | 14632 | M00807 | non-negotiable | false | 10 |
| R08100 | Continuity rule — user can inspect/remove/export | 14633 | M00807 | non-negotiable | false | 10 |
| R08101 | Hyper feature — memory as tools | 14636 | M00807 | non-negotiable | false | 10 |
| R08102 | Memory call — search_memory | 14640 | M00807 | non-negotiable | false | 10 |
| R08103 | Memory call — write_memory | 14641 | M00807 | non-negotiable | false | 10 |
| R08104 | Memory call — link_memory | 14642 | M00807 | non-negotiable | false | 10 |
| R08105 | Memory call — verify_memory | 14643 | M00807 | non-negotiable | false | 10 |
| R08106 | Memory call — forget_memory | 14644 | M00807 | non-negotiable | false | 10 |
| R08107 | Memory call — promote_memory | 14645 | M00807 | non-negotiable | false | 10 |
| R08108 | Module 6 — Workflow Compiler | 14648 | M00808 | non-negotiable | false | 10 |
| R08109 | Workflow Compiler input — user goal | 14654 | M00808 | non-negotiable | false | 10 |
| R08110 | Workflow Compiler input — profile | 14655 | M00808 | non-negotiable | false | 10 |
| R08111 | Workflow Compiler input — environment map | 14656 | M00808 | non-negotiable | false | 10 |
| R08112 | Workflow Compiler input — policy | 14657 | M00808 | non-negotiable | false | 10 |
| R08113 | Workflow Compiler input — model registry | 14658 | M00808 | non-negotiable | false | 10 |
| R08114 | Workflow Compiler input — tool catalog | 14659 | M00808 | non-negotiable | false | 10 |
| R08115 | Workflow Compiler input — hardware pressure | 14660 | M00808 | non-negotiable | false | 10 |
| R08116 | Workflow Compiler output — workflow DAG | 14664 | M00808 | non-negotiable | false | 10 |
| R08117 | Workflow Compiler output — tool calls | 14665 | M00808 | non-negotiable | false | 10 |
| R08118 | Workflow Compiler output — model calls | 14666 | M00808 | non-negotiable | false | 10 |
| R08119 | Workflow Compiler output — checkpoints | 14667 | M00808 | non-negotiable | false | 10 |
| R08120 | Workflow Compiler output — human gates | 14668 | M00808 | non-negotiable | false | 10 |
| R08121 | Workflow Compiler output — evals | 14669 | M00808 | non-negotiable | false | 10 |
| R08122 | Workflow Compiler output — commit conditions | 14670 | M00808 | non-negotiable | false | 10 |
| R08123 | Hyper feature — adaptive recompile | 14672 | M00808 | non-negotiable | false | 10 |
| R08124 | Adaptive recompile — "If tests fail or context changes: do not blindly continue" | 14674 | M00808 | non-negotiable | false | 10 |
| R08125 | Adaptive recompile — re-map / re-plan / re-route | 14676 | M00808 | non-negotiable | false | 10 |
| R08126 | Module 7 — Eval And Value Plane | 14682 | M00809 | non-negotiable | false | 10 |
| R08127 | Eval dimension — correctness | 14686 | M00809 | non-negotiable | false | 10 |
| R08128 | Eval dimension — evidence | 14687 | M00809 | non-negotiable | false | 10 |
| R08129 | Eval dimension — test pass | 14688 | M00809 | non-negotiable | false | 10 |
| R08130 | Eval dimension — schema validity | 14689 | M00809 | non-negotiable | false | 10 |
| R08131 | Eval dimension — risk | 14690 | M00809 | non-negotiable | false | 10 |
| R08132 | Eval dimension — cost | 14691 | M00809 | non-negotiable | false | 10 |
| R08133 | Eval dimension — latency | 14692 | M00809 | non-negotiable | false | 10 |
| R08134 | Eval dimension — human burden | 14693 | M00809 | non-negotiable | false | 10 |
| R08135 | Eval dimension — reversibility | 14694 | M00809 | non-negotiable | false | 10 |
| R08136 | Eval dimension — learning value | 14695 | M00809 | non-negotiable | false | 10 |
| R08137 | Profile weight — fast | 14700 | M00809 | non-negotiable | false | 10 |
| R08138 | Profile weight — careful | 14701 | M00809 | non-negotiable | false | 10 |
| R08139 | Profile weight — offline | 14702 | M00809 | non-negotiable | false | 10 |
| R08140 | Profile weight — research | 14703 | M00809 | non-negotiable | false | 10 |
| R08141 | Profile weight — autonomous | 14704 | M00809 | non-negotiable | false | 10 |
| R08142 | Profile weight — production | 14705 | M00809 | non-negotiable | false | 10 |
| R08143 | Profile weight — experimental | 14706 | M00809 | non-negotiable | false | 10 |
| R08144 | Profile weight — communication/peace | 14707 | M00809 | non-negotiable | false | 10 |
| R08145 | Module 8 — Continuity Manager ("sleeper module") | 14710 | M00810 | non-negotiable | false | 10 |
| R08146 | Continuity Manager uses — ZFS snapshots + Podman/CRIU checkpoints + workflow hibernation + context compaction + model server warm pools + session resume | 14714–14718 | M00810 | non-negotiable | false | 10 |
| R08147 | Continuity state — active / paused / hibernated / checkpointed / archived / quarantined / promoted / rolled back | 14720 | M00810 | non-negotiable | false | 10 |
| R08148 | Module 9 — Observability And Truth | 14724 | M00811 | non-negotiable | false | 10 |
| R08149 | Observability source — OpenTelemetry traces + journald + DCGM + PSI + eBPF + ZFS events + test output + gateway logs + cost ledger | 14728–14736 | M00811 | non-negotiable | false | 10 |
| R08150 | Observability question — what happened? + what changed? + which model decided? + which policy allowed it? + what did it cost? + what pressure did hardware experience? | 14740–14744 | M00811 | non-negotiable | false | 10 |
| R08151 | Module 10 — Adaptation / LoRA Foundry | 14748 | M00812 | non-negotiable | false | 10 |
| R08152 | Before-training — profile tuning + router tuning + memory tuning + workflow tuning + prompt-program tuning + model choice | 14752–14755 | M00812 | non-negotiable | false | 10 |
| R08153 | Training-to-deployment — trace curation + dataset creation + LoRA training + adapter serving + eval gating + profile assignment | 14757–14760 | M00812 | non-negotiable | false | 10 |
| R08154 | vLLM URL — docs.vllm.ai/en/stable/features/lora/ | 14762 | M00812 | non-negotiable | false | 10 |
| R08155 | SGLang URL — sgl-project.github.io/advanced_features/lora.html | 14762 | M00812 | non-negotiable | false | 10 |
| R08156 | Configuration surface — User (simple profiles and prompts) | 14770 | M00813 | non-negotiable | false | 10 |
| R08157 | Configuration surface — Power user (toggles + budgets + allowed providers + sandbox levels) | 14774 | M00813 | non-negotiable | false | 10 |
| R08158 | Configuration surface — System (policy + hardware profile + routing weights + eval thresholds) | 14778 | M00813 | non-negotiable | false | 10 |
| R08159 | Continuity Stack — Hardware + OS + Agent + Memory + Model + Human (6-layer); "Cloud gives model continuity. Sovereign-OS gives life/work continuity"; KEY LINE "Every module is a controlled continuation of user intent across hardware, software, memory, and time" — "That is the architecture becoming whole" | 14784–14810 | M00814 + M00815 | non-negotiable | false | 10 |
| R08160 | Composite — M048 (10 epics / 17 modules / 85 features / 170 reqs) catalogs the 10 Sovereign-OS modules + 3 configuration surfaces + 6-layer Continuity Stack + KEY LINE: 7-question continuity standard + Module 1 Base OS (Debian13/Ubuntu24 + 10 responsibilities + 5 config modes + Nix-vs-Debian principle + Chezmoi encryption) + Module 2 Compute Fabric (4 workers + 7-capability schema + dynamic-placement hyper feature) + Module 3 Container/Sandbox Fabric (Podman Quadlet + NVIDIA CDI + 5-rule pattern + 8 sandbox profiles) + Module 4 Gateway (Anthropic-first + 6 surfaces + provider-inversion + 7 owned concerns) + Module 5 Memory OS (8 types + 4 continuity rules + 6 memory-as-tools calls) + Module 6 Workflow Compiler (7-input → 7-output + adaptive-recompile) + Module 7 Eval/Value (10 dimensions + 8 profiles) + Module 8 Continuity Manager ("sleeper" + 6 primitives + 8 states) + Module 9 Observability (9 sources + 6 questions) + Module 10 LoRA Foundry (6-before + 7-training-to-deployment + vLLM + SGLang anchors) + 3-level Configuration Surfaces + 6-layer Continuity Stack + KEY LINE "Every module is a controlled continuation of user intent across hardware, software, memory, and time" | 14402–14812 | E0458-E0467 | non-negotiable | false | 10 |

## Sub-requirements accounting

- 170 requirements covering: continuity principle + 7-question standard (R07991–R08001) + Module 1 Base OS responsibilities + config modes + principle (R08002–R08028) + Module 2 Compute Fabric 4 workers + 7-capability schema + dynamic placement (R08029–R08048) + Module 3 Container/Sandbox Fabric Podman/CDI + 5-rule pattern + 8 sandbox profiles (R08049–R08069) + Module 4 Gateway 6 surfaces + provider inversion + 7 owned (R08070–R08087) + Module 5 Memory OS 8 types + 4 continuity rules + 6 memory-as-tools (R08088–R08107) + Module 6 Workflow Compiler 7+7 + adaptive recompile (R08108–R08125) + Module 7 Eval 10 dimensions + 8 profiles (R08126–R08144) + Module 8 Continuity Manager 6 primitives + 8 states (R08145–R08147) + Module 9 Observability 9 sources + 6 questions (R08148–R08150) + Module 10 LoRA 6-before + 7-training (R08151–R08155) + 3 configuration surfaces (R08156–R08158) + 6-layer Continuity Stack + KEY LINE (R08159) + composite (R08160)
- Source range 14402–14812 yields 410 lines; 170 R-rows represent ~41% line-coverage at the verbatim-citation level
- Project boundary — M048 is sovereign-os module-catalog scope; selfdef IPS-side has its own 14-functional-modules catalog (MS006); cross-repo binding via MS007 typed-mirror crates

## Cross-references

- Adjacent dump-range milestones: M047 Continuity — CRIU + ZFS + warm sandboxes + hibernated thought (14107–14402) / M049 Continuity through observability and policy (next; dump 14812–15120)
- Module 1 Base OS — overlays M044 Sovereign-OS substrate Debian-13 Ubuntu-24 + adds Chezmoi user-config continuity
- Module 2 Compute Fabric — extends M043 Bridge layer hardware-aware intelligence scheduling 4-layer station translation (Blackwell/3090/AVX-512/RAM-ZFS) with 7-capability schema + dynamic placement
- Module 3 Container/Sandbox Fabric — refines M045 Linux as intelligence governor's sandbox vectors with Podman Quadlet + NVIDIA CDI specifics; 8 sandbox profiles align with M042 Choice Architecture envelopes
- Module 4 Gateway — realizes M034 Anthropic-first Gateway + M033 Compatibility Gateway via provider-inversion pattern; M046 LoRA foundry vault-proxy pattern (LiteLLM sidecar) consumed here
- Module 5 Memory OS — extends M028 Memory OS 8-type taxonomy with 4 continuity rules + 6 memory-as-tools calls
- Module 6 Workflow Compiler — extends M025 Cognitive Compiler with adaptive-recompile + M036 MAP→SPEC→TEST→ACT→EVAL→COMMIT→LEARN compilation + M042 7 canonical contracts (SPEC/WORKFLOW/PROFILES/EVALS/MAP/MODEL_REGISTRY/POLICY) inputs
- Module 7 Eval/Value — extends M027 Value Plane + M037 Spec/TDD evidence-driven autonomy with 10-dimension scoring + 8-profile weighting (production / experimental / communication-peace are new modes)
- Module 8 Continuity Manager — direct extension of M047 Continuity (CRIU + ZFS + warm sandboxes + hibernated thought) with 8 states (active/paused/hibernated/checkpointed/archived/quarantined/promoted/rolled back)
- Module 9 Observability — overlays M045 Linux as intelligence governor's Observability Plane (journald + OpenTelemetry + DCGM + eBPF + Prometheus-Grafana stack)
- Module 10 LoRA Foundry — extends M046 Beat the cloud — runtime adaptation + LoRA foundry with the before-training-vs-training-to-deployment split
- Configuration Surfaces 3-level — User/Power user/System aligns with selfdef MS011 operator dashboard's role-based dashboards
- Continuity Stack 6-layer — Hardware/OS/Agent/Memory/Model/Human is the unifying frame across M043-M047
- Selfdef integration — selfdef MS006 14-functional-modules catalog mirrors this module taxonomy from the IPS side (detect-host/agent-guard/bridge-l2/polarproxy/etc.); cross-repo binding via MS007 module-manifest typed-mirror crate
- Operator references: chezmoi.io/user-guide/encryption + docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html + docs.nvidia.com/datacenter/cloud-native/container-toolkit/1.14.4/cdi-support.html + docs.podman.io/docs/checkpoint + docs.vllm.ai/en/stable/features/lora/ + sgl-project.github.io/advanced_features/lora.html + web searches "NixOS home-manager declarative configuration reproducible workstations AI development 2026" + "NVIDIA Container Toolkit CDI GPU containers rootless Podman documentation 2026"
