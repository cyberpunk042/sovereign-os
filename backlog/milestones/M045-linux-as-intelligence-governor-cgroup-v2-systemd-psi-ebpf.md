# M045 — Linux as intelligence governor — cgroup v2 / systemd / PSI / eBPF

> Parent: `backlog/milestones/INDEX.md` row M045 (dump 13546–13825).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 13546–13825. Operator directive 13546: "alright. just continue" + closing directive 13825: "yes indeed. continue like do. you can do online research too. we will make this even better than the cloud provider... so much better... even before I train and retrain and adapt weights and add my LORAs and such and whatnot..".
> All entries below extract verbatim. No invention.

## Epics (E0428–E0437)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0428 | Linux as intelligence governor — 8 primitives (cgroup v2 resource control / systemd lifecycle service-boundaries slices scopes / PSI pressure sensing CPU-memory-IO / eBPF + LSM observation possible-enforcement / AppArmor mandatory access boundaries / namespaces isolation / ZFS rollback durable memory / LUKS-TPM-FIDO2 identity sealed storage); "This is not incidental. This is the peace-machine substrate" | 13564–13594 |
| E0429 | Linux Resource Intelligence — cgroup v2 controls CPU + memory + IO + PIDs + delegation; systemd exposes CPUWeight + MemoryMax + IOWeight + task limits + slices + scopes; sources: kernel.org/doc/html/latest/admin-guide/cgroup-v2.html + freedesktop.org/software/systemd/man/devel/systemd.resource-control.html; "agent workloads can be given real boundaries"; 5 example boundaries (oracle.service high GPU priority memory protected no random shell access / scout.slice medium CPU-GPU can be killed-restarted freely / sandbox.slice strict memory IO network time limits / eval.slice low priority background / gateway.service protected always-on small trusted surface); "This is how 'profiles' become real OS behavior" | 13602–13632 |
| E0430 | Pressure As Sensation — Linux PSI reports time tasks stalled because of CPU memory IO pressure via /proc/pressure/* (kernel.org/doc/html/v6.0/accounting/psi.html); AI scheduler should ask 6 pressure questions: CPU pressure / Memory pressure / IO pressure / GPU pressure / Human-attention pressure / Cost pressure; "PSI gives system pressure. DCGM gives GPU pressure. The runtime gives cost and attention pressure" | 13636–13660 |
| E0431 | Adaptive intelligence reactions (5 profile-adaptation rules) — if memory pressure high (hibernate branches / shrink context / evict low-value KV-cache); if IO pressure high (stop cold memory scans / delay replay compaction / prefer RAM-hot context); if CPU pressure high (reduce branch width / move reranking to 3090 / defer evals); if GPU oracle idle (increase verification batch); if 3090 idle (widen scout speculation); "This is adaptive intelligence grounded in the OS" | 13664–13688 |
| E0432 | eBPF As Truth Sensor — eBPF can observe what processes actually do; eBPF LSM programs can attach to Linux Security Module hooks and allow/deny operations such as socket creation depending on policy (docs.ebpf.io/linux/program-type/BPF_PROG_TYPE_LSM); for Sovereign-OS: model claims "I only read files" / eBPF observes "process opened network socket" / runtime: "block, log, alert, quarantine"; "This is a peace feature: reality over claims"; "Use eBPF carefully. It is powerful and sharp. But as an observability/enforcement layer for high-risk agent sandboxes, it fits" | 13692–13714 |
| E0433 | Systemd As Agent Lifecycle Manager — "Agent sessions should not be loose processes. They should be scopes/services"; 7 example unit names: agent-session@123.service / agent-sandbox@abc.scope / model-server@blackwell.service / model-server@scout.service / gateway.service / memory-os.service / eval-worker.slice; 8 OS operations: start / stop / restart / limit / observe / journal / kill zombies / freeze-hibernate; "This maps directly to the AgentRM idea of scheduling, zombie reaping, and context lifecycle management" | 13718–13740 |
| E0434 | Sovereign Profiles As OS Profiles — "User choice becomes enforceable"; 5 enforceable profiles: Offline Peace Mode (network egress denied / cloud providers disabled / local models only) / Research Mode (network allowed through gateway / citations required / cost tracked) / Autonomous Code Mode (sandbox required / ZFS snapshot before writes / tests required before commit) / High-Risk Mode (VM-microVM only / no host filesystem write / human gate for promotion) / Fast Local Mode (3090 scout first / shallow memory / oracle only if confidence low); "These are not prompt styles. They are OS policies + runtime policies" | 13744–13766 |
| E0435 | Hardware Meets OS — 7 layer mappings: AVX-512 fast policy and scheduling decisions / cgroup-systemd enforce resource decisions / PSI-DCGM sense pressure / AppArmor-eBPF observe and constrain behavior / ZFS make action reversible / VFIO hard isolate the 3090 sandbox / Gateway make all model-API communication auditable; "This is the bridge: hardware capability becomes social trust only when the OS can govern it" | 13770–13790 |
| E0436 | Anti-war framing — peace machine needs 8 virtues + 8 technical-primitive mappings: clarity (explain what is happening) → traces/dashboard / consent (ask when boundaries matter) → human gates/profiles / reversibility (rollback when possible) → ZFS/snapshots / proportionality (spend just enough intelligence) → scheduler/profiles / containment (risky action stays sandboxed) → cgroups/AppArmor/VMs / memory (learn from harm and success) → memory OS/replay / communication (translate between humans systems models tools) → Anthropic-first gateway/MCP / truth (tests traces observations not vibes) → tests/eBPF/PSI/evals; "Those are not abstract virtues. They map to technical primitives"; "That is where Sovereign-OS becomes something more than an OS image. It becomes an environment where intelligence can act without becoming opaque power" | 13794–13820 |
| E0437 | Operator final affirmation — "yes indeed. continue like do. you can do online research too. we will make this even better than the cloud provider... so much better... even before I train and retrain and adapt weights and add my LORAs and such and whatnot.." | 13825 |

## Modules (M00748–M00764)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00748 | OS primitive — cgroup v2 (resource control) | 13568 | E0428 |
| M00749 | OS primitive — systemd (lifecycle / service boundaries / slices / scopes) | 13571 | E0428 |
| M00750 | OS primitive — PSI (pressure sensing CPU/memory/IO) | 13574 | E0428 + E0430 |
| M00751 | OS primitive — eBPF / LSM (observation + possible enforcement) | 13577 | E0428 + E0432 |
| M00752 | OS primitive — AppArmor (mandatory access boundaries) | 13580 | E0428 |
| M00753 | OS primitive — namespaces (isolation) | 13583 | E0428 |
| M00754 | OS primitive — ZFS (rollback + durable memory) | 13586 | E0428 |
| M00755 | OS primitive — LUKS/TPM/FIDO2 (identity + sealed storage) | 13589 | E0428 |
| M00756 | cgroup-v2 + systemd resource knobs — CPUWeight + MemoryMax + IOWeight + task limits + slices + scopes | 13604–13608 | E0429 |
| M00757 | 5 example workload boundaries — oracle.service / scout.slice / sandbox.slice / eval.slice / gateway.service | 13613–13627 | E0429 |
| M00758 | 6 pressure questions — CPU / Memory / IO / GPU / Human-attention / Cost | 13648–13655 | E0430 |
| M00759 | Pressure sources — PSI (system) / DCGM (GPU) / runtime (cost + attention) | 13658–13660 | E0430 |
| M00760 | 5 adaptive-intelligence reactions — memory-pressure / IO-pressure / CPU-pressure / GPU-oracle-idle / 3090-idle | 13664–13688 | E0431 |
| M00761 | 7 systemd unit-name examples + 8 OS operations + AgentRM mapping | 13724–13740 | E0433 |
| M00762 | 5 enforceable Sovereign Profiles — Offline Peace / Research / Autonomous Code / High-Risk / Fast Local | 13746–13766 | E0434 |
| M00763 | Hardware-meets-OS 7 layer mapping (AVX-512 / cgroup-systemd / PSI-DCGM / AppArmor-eBPF / ZFS / VFIO / Gateway) | 13772–13788 | E0435 |
| M00764 | Anti-war framing — 8 virtue-to-primitive mappings (clarity / consent / reversibility / proportionality / containment / memory / communication / truth) | 13804–13818 | E0436 |

## Features (F03741–F03825)

| Feature ID | Phrase | Dump line | Parent module |
|---|---|---|---|
| F03741 | Bridge re-centering — "the next bridge is Linux as the intelligence governor" | 13560 | E0428 |
| F03742 | "On Debian 13 / Ubuntu 24, the OS already has several primitives that map beautifully to sovereign intelligence" | 13562 | E0428 |
| F03743 | cgroup v2 — resource control | 13568 | M00748 |
| F03744 | systemd — lifecycle | 13571 | M00749 |
| F03745 | systemd — service boundaries | 13571 | M00749 |
| F03746 | systemd — slices | 13571 | M00749 |
| F03747 | systemd — scopes | 13571 | M00749 |
| F03748 | PSI — pressure sensing for CPU / memory / IO | 13574 | M00750 |
| F03749 | eBPF — observation | 13577 | M00751 |
| F03750 | LSM — possible enforcement | 13577 | M00751 |
| F03751 | AppArmor — mandatory access boundaries | 13580 | M00752 |
| F03752 | namespaces — isolation | 13583 | M00753 |
| F03753 | ZFS — rollback | 13586 | M00754 |
| F03754 | ZFS — durable memory | 13586 | M00754 |
| F03755 | LUKS/TPM/FIDO2 — identity | 13589 | M00755 |
| F03756 | LUKS/TPM/FIDO2 — sealed storage | 13589 | M00755 |
| F03757 | "This is not incidental. This is the peace-machine substrate" | 13594 | E0428 |
| F03758 | Resource control — cgroup v2 lets OS control CPU, memory, IO, PIDs, and delegation | 13604 | M00756 |
| F03759 | Resource control — systemd exposes CPUWeight | 13606 | M00756 |
| F03760 | Resource control — systemd exposes MemoryMax | 13606 | M00756 |
| F03761 | Resource control — systemd exposes IOWeight | 13606 | M00756 |
| F03762 | Resource control — systemd exposes task limits | 13606 | M00756 |
| F03763 | Resource control — systemd exposes slices | 13606 | M00756 |
| F03764 | Resource control — systemd exposes scopes | 13606 | M00756 |
| F03765 | kernel cgroup v2 docs URL — kernel.org/doc/html/latest/admin-guide/cgroup-v2.html | 13608 | E0429 |
| F03766 | systemd resource-control docs URL — freedesktop.org/software/systemd/man/devel/systemd.resource-control.html | 13608 | E0429 |
| F03767 | Workload — oracle.service (high GPU priority + memory protected + no random shell access) | 13613 | M00757 |
| F03768 | Workload — scout.slice (medium CPU/GPU + can be killed/restarted freely) | 13616 | M00757 |
| F03769 | Workload — sandbox.slice (strict memory + IO + network + time limits) | 13619 | M00757 |
| F03770 | Workload — eval.slice (low priority + background) | 13622 | M00757 |
| F03771 | Workload — gateway.service (protected + always-on + small trusted surface) | 13625 | M00757 |
| F03772 | "This is how 'profiles' become real OS behavior" | 13632 | E0429 |
| F03773 | PSI heading — "Pressure As Sensation" | 13636 | E0430 |
| F03774 | PSI — reports time tasks stalled because of CPU/memory/IO via /proc/pressure/* | 13640 | M00750 |
| F03775 | PSI docs URL — kernel.org/doc/html/v6.0/accounting/psi.html | 13642 | E0430 |
| F03776 | AI scheduler — should not only ask "What does the model want?" | 13644–13646 | E0430 |
| F03777 | AI scheduler — should ask: Is the machine under CPU pressure? | 13650 | M00758 |
| F03778 | AI scheduler — Memory pressure? | 13651 | M00758 |
| F03779 | AI scheduler — IO pressure? | 13652 | M00758 |
| F03780 | AI scheduler — GPU pressure? | 13653 | M00758 |
| F03781 | AI scheduler — Human-attention pressure? | 13654 | M00758 |
| F03782 | AI scheduler — Cost pressure? | 13655 | M00758 |
| F03783 | Pressure source — PSI gives system pressure | 13658 | M00759 |
| F03784 | Pressure source — DCGM gives GPU pressure | 13659 | M00759 |
| F03785 | Pressure source — runtime gives cost and attention pressure | 13660 | M00759 |
| F03786 | Adaptive reaction — memory pressure high: hibernate branches | 13666 | M00760 |
| F03787 | Adaptive reaction — memory pressure high: shrink context | 13667 | M00760 |
| F03788 | Adaptive reaction — memory pressure high: evict low-value KV/cache | 13668 | M00760 |
| F03789 | Adaptive reaction — IO pressure high: stop cold memory scans | 13670 | M00760 |
| F03790 | Adaptive reaction — IO pressure high: delay replay compaction | 13671 | M00760 |
| F03791 | Adaptive reaction — IO pressure high: prefer RAM-hot context | 13672 | M00760 |
| F03792 | Adaptive reaction — CPU pressure high: reduce branch width | 13675 | M00760 |
| F03793 | Adaptive reaction — CPU pressure high: move reranking to 3090 | 13676 | M00760 |
| F03794 | Adaptive reaction — CPU pressure high: defer evals | 13677 | M00760 |
| F03795 | Adaptive reaction — GPU oracle idle: increase verification batch | 13682 | M00760 |
| F03796 | Adaptive reaction — 3090 idle: widen scout speculation | 13686 | M00760 |
| F03797 | "This is adaptive intelligence grounded in the OS" | 13688 | E0431 |
| F03798 | eBPF heading — "eBPF As Truth Sensor" | 13692 | E0432 |
| F03799 | eBPF — observes what processes actually do | 13694 | M00751 |
| F03800 | eBPF LSM — attaches to Linux Security Module hooks | 13696 | M00751 |
| F03801 | eBPF LSM — allow/deny operations such as socket creation depending on policy | 13696–13697 | M00751 |
| F03802 | eBPF LSM docs URL — docs.ebpf.io/linux/program-type/BPF_PROG_TYPE_LSM | 13698 | E0432 |
| F03803 | Truth pattern — model says: "I only read files" | 13704 | E0432 |
| F03804 | Truth pattern — eBPF observes: "process opened network socket" | 13706 | E0432 |
| F03805 | Truth pattern — runtime: block, log, alert, quarantine | 13708 | E0432 |
| F03806 | "This is a peace feature: reality over claims" | 13710 | E0432 |
| F03807 | "Use eBPF carefully. It is powerful and sharp" | 13712 | E0432 |
| F03808 | "But as an observability/enforcement layer for high-risk agent sandboxes, it fits" | 13713–13714 | E0432 |
| F03809 | Systemd heading — "Systemd As Agent Lifecycle Manager" | 13718 | E0433 |
| F03810 | Agent sessions — "should not be loose processes" | 13720 | E0433 |
| F03811 | Agent sessions — "should be scopes/services" | 13720 | E0433 |
| F03812 | Unit example — agent-session@123.service | 13724 | M00761 |
| F03813 | Unit example — agent-sandbox@abc.scope | 13725 | M00761 |
| F03814 | Unit example — model-server@blackwell.service | 13726 | M00761 |
| F03815 | Unit example — model-server@scout.service | 13727 | M00761 |
| F03816 | Unit example — gateway.service | 13728 | M00761 |
| F03817 | Unit example — memory-os.service | 13729 | M00761 |
| F03818 | Unit example — eval-worker.slice | 13730 | M00761 |
| F03819 | OS operations — start / stop / restart / limit / observe / journal / kill zombies / freeze-hibernate | 13734–13738 | M00761 |
| F03820 | AgentRM mapping — "This maps directly to the AgentRM idea of scheduling, zombie reaping, and context lifecycle management" | 13740 | E0433 |
| F03821 | Profile — Offline Peace Mode (network egress denied + cloud providers disabled + local models only) | 13748–13752 | M00762 |
| F03822 | Profile — Research Mode (network allowed through gateway + citations required + cost tracked) | 13754–13757 | M00762 |
| F03823 | Profile — Autonomous Code Mode (sandbox required + ZFS snapshot before writes + tests required before commit) | 13759–13762 | M00762 |
| F03824 | Profile — High-Risk Mode (VM/microVM only + no host filesystem write + human gate for promotion) + Fast Local Mode (3090 scout first + shallow memory + oracle only if confidence low) + "not prompt styles" + "OS policies + runtime policies" | 13759–13766 | M00762 |
| F03825 | Hardware-meets-OS 7 mappings + 8 anti-war virtue-to-primitive + key line "environment where intelligence can act without becoming opaque power" + operator final affirmation "better than the cloud provider...even before I train...add my LORAs" | 13770–13825 | M00763 + M00764 + E0437 |

## Requirements (R07481–R07650)

| Req ID | Phrase | Dump line | Parent feature | Negotiability | Layer-B metric | Priority |
|---|---|---|---|---|---|---|
| R07481 | Operator directive — "alright. just continue" | 13546 | E0428 | non-negotiable | false | 10 |
| R07482 | Next bridge — "Linux as the intelligence governor" | 13560 | F03741 | non-negotiable | false | 10 |
| R07483 | Debian 13 / Ubuntu 24 has primitives that map to sovereign intelligence | 13562 | F03742 | non-negotiable | false | 10 |
| R07484 | OS primitive — cgroup v2 (resource control) | 13568 | F03743 | non-negotiable | false | 10 |
| R07485 | OS primitive — systemd lifecycle | 13571 | F03744 | non-negotiable | false | 10 |
| R07486 | OS primitive — systemd service boundaries | 13571 | F03745 | non-negotiable | false | 10 |
| R07487 | OS primitive — systemd slices | 13571 | F03746 | non-negotiable | false | 10 |
| R07488 | OS primitive — systemd scopes | 13571 | F03747 | non-negotiable | false | 10 |
| R07489 | OS primitive — PSI pressure sensing | 13574 | F03748 | non-negotiable | false | 10 |
| R07490 | OS primitive — PSI for CPU | 13574 | F03748 | non-negotiable | false | 10 |
| R07491 | OS primitive — PSI for memory | 13574 | F03748 | non-negotiable | false | 10 |
| R07492 | OS primitive — PSI for IO | 13574 | F03748 | non-negotiable | false | 10 |
| R07493 | OS primitive — eBPF (observation) | 13577 | F03749 | non-negotiable | false | 10 |
| R07494 | OS primitive — LSM (possible enforcement) | 13577 | F03750 | non-negotiable | false | 10 |
| R07495 | OS primitive — AppArmor (mandatory access boundaries) | 13580 | F03751 | non-negotiable | false | 10 |
| R07496 | OS primitive — namespaces (isolation) | 13583 | F03752 | non-negotiable | false | 10 |
| R07497 | OS primitive — ZFS (rollback) | 13586 | F03753 | non-negotiable | false | 10 |
| R07498 | OS primitive — ZFS (durable memory) | 13586 | F03754 | non-negotiable | false | 10 |
| R07499 | OS primitive — LUKS/TPM/FIDO2 (identity) | 13589 | F03755 | non-negotiable | false | 10 |
| R07500 | OS primitive — LUKS/TPM/FIDO2 (sealed storage) | 13589 | F03756 | non-negotiable | false | 10 |
| R07501 | "This is not incidental" | 13594 | F03757 | non-negotiable | false | 10 |
| R07502 | "This is the peace-machine substrate" | 13594 | F03757 | non-negotiable | false | 10 |
| R07503 | cgroup v2 — controls CPU | 13604 | F03758 | non-negotiable | false | 10 |
| R07504 | cgroup v2 — controls memory | 13604 | F03758 | non-negotiable | false | 10 |
| R07505 | cgroup v2 — controls IO | 13604 | F03758 | non-negotiable | false | 10 |
| R07506 | cgroup v2 — controls PIDs | 13604 | F03758 | non-negotiable | false | 10 |
| R07507 | cgroup v2 — controls delegation | 13604 | F03758 | non-negotiable | false | 10 |
| R07508 | systemd — exposes CPUWeight | 13606 | F03759 | non-negotiable | false | 10 |
| R07509 | systemd — exposes MemoryMax | 13606 | F03760 | non-negotiable | false | 10 |
| R07510 | systemd — exposes IOWeight | 13606 | F03761 | non-negotiable | false | 10 |
| R07511 | systemd — exposes task limits | 13606 | F03762 | non-negotiable | false | 10 |
| R07512 | systemd — exposes slices | 13606 | F03763 | non-negotiable | false | 10 |
| R07513 | systemd — exposes scopes | 13606 | F03764 | non-negotiable | false | 10 |
| R07514 | Source URL — kernel.org cgroup v2 docs | 13608 | F03765 | non-negotiable | false | 10 |
| R07515 | Source URL — freedesktop.org systemd.resource-control | 13608 | F03766 | non-negotiable | false | 10 |
| R07516 | "Agent workloads can be given real boundaries" | 13610 | E0429 | non-negotiable | false | 10 |
| R07517 | Workload — oracle.service: high GPU priority | 13613 | F03767 | non-negotiable | false | 10 |
| R07518 | Workload — oracle.service: memory protected | 13614 | F03767 | non-negotiable | false | 10 |
| R07519 | Workload — oracle.service: no random shell access | 13615 | F03767 | non-negotiable | false | 10 |
| R07520 | Workload — scout.slice: medium CPU/GPU | 13617 | F03768 | non-negotiable | false | 10 |
| R07521 | Workload — scout.slice: can be killed/restarted freely | 13618 | F03768 | non-negotiable | false | 10 |
| R07522 | Workload — sandbox.slice: strict memory limits | 13620 | F03769 | non-negotiable | false | 10 |
| R07523 | Workload — sandbox.slice: strict IO limits | 13620 | F03769 | non-negotiable | false | 10 |
| R07524 | Workload — sandbox.slice: strict network limits | 13620 | F03769 | non-negotiable | false | 10 |
| R07525 | Workload — sandbox.slice: strict time limits | 13620 | F03769 | non-negotiable | false | 10 |
| R07526 | Workload — eval.slice: low priority | 13623 | F03770 | non-negotiable | false | 10 |
| R07527 | Workload — eval.slice: background | 13623 | F03770 | non-negotiable | false | 10 |
| R07528 | Workload — gateway.service: protected | 13626 | F03771 | non-negotiable | false | 10 |
| R07529 | Workload — gateway.service: always-on | 13626 | F03771 | non-negotiable | false | 10 |
| R07530 | Workload — gateway.service: small trusted surface | 13627 | F03771 | non-negotiable | false | 10 |
| R07531 | "This is how 'profiles' become real OS behavior" | 13632 | F03772 | non-negotiable | false | 10 |
| R07532 | PSI section header | 13636 | F03773 | non-negotiable | false | 10 |
| R07533 | PSI — "Linux PSI is wonderful here" | 13638 | E0430 | non-negotiable | false | 10 |
| R07534 | PSI — reports time tasks stalled because of CPU pressure | 13640 | F03774 | non-negotiable | false | 10 |
| R07535 | PSI — reports time tasks stalled because of memory pressure | 13640 | F03774 | non-negotiable | false | 10 |
| R07536 | PSI — reports time tasks stalled because of IO pressure | 13640 | F03774 | non-negotiable | false | 10 |
| R07537 | PSI — via /proc/pressure/* | 13641 | F03774 | non-negotiable | false | 10 |
| R07538 | PSI URL — kernel.org/doc/html/v6.0/accounting/psi.html | 13642 | F03775 | non-negotiable | false | 10 |
| R07539 | AI scheduler doctrine — not only "What does the model want?" | 13646 | F03776 | non-negotiable | false | 10 |
| R07540 | Pressure question — Is the machine under CPU pressure? | 13650 | F03777 | non-negotiable | false | 10 |
| R07541 | Pressure question — Memory pressure? | 13651 | F03778 | non-negotiable | false | 10 |
| R07542 | Pressure question — IO pressure? | 13652 | F03779 | non-negotiable | false | 10 |
| R07543 | Pressure question — GPU pressure? | 13653 | F03780 | non-negotiable | false | 10 |
| R07544 | Pressure question — Human-attention pressure? | 13654 | F03781 | non-negotiable | false | 10 |
| R07545 | Pressure question — Cost pressure? | 13655 | F03782 | non-negotiable | false | 10 |
| R07546 | Pressure source — PSI gives system pressure | 13658 | F03783 | non-negotiable | false | 10 |
| R07547 | Pressure source — DCGM gives GPU pressure | 13659 | F03784 | non-negotiable | false | 10 |
| R07548 | Pressure source — runtime gives cost pressure | 13660 | F03785 | non-negotiable | false | 10 |
| R07549 | Pressure source — runtime gives attention pressure | 13660 | F03785 | non-negotiable | false | 10 |
| R07550 | "Then profiles adapt" | 13662 | E0431 | non-negotiable | false | 10 |
| R07551 | Adaptive reaction — memory pressure high: hibernate branches | 13666 | F03786 | non-negotiable | false | 10 |
| R07552 | Adaptive reaction — memory pressure high: shrink context | 13667 | F03787 | non-negotiable | false | 10 |
| R07553 | Adaptive reaction — memory pressure high: evict low-value KV/cache | 13668 | F03788 | non-negotiable | false | 10 |
| R07554 | Adaptive reaction — IO pressure high: stop cold memory scans | 13670 | F03789 | non-negotiable | false | 10 |
| R07555 | Adaptive reaction — IO pressure high: delay replay compaction | 13671 | F03790 | non-negotiable | false | 10 |
| R07556 | Adaptive reaction — IO pressure high: prefer RAM-hot context | 13672 | F03791 | non-negotiable | false | 10 |
| R07557 | Adaptive reaction — CPU pressure high: reduce branch width | 13675 | F03792 | non-negotiable | false | 10 |
| R07558 | Adaptive reaction — CPU pressure high: move reranking to 3090 | 13676 | F03793 | non-negotiable | false | 10 |
| R07559 | Adaptive reaction — CPU pressure high: defer evals | 13677 | F03794 | non-negotiable | false | 10 |
| R07560 | Adaptive reaction — GPU oracle idle: increase verification batch | 13682 | F03795 | non-negotiable | false | 10 |
| R07561 | Adaptive reaction — 3090 idle: widen scout speculation | 13686 | F03796 | non-negotiable | false | 10 |
| R07562 | "This is adaptive intelligence grounded in the OS" | 13688 | F03797 | non-negotiable | false | 10 |
| R07563 | eBPF section header | 13692 | F03798 | non-negotiable | false | 10 |
| R07564 | eBPF — observes what processes actually do | 13694 | F03799 | non-negotiable | false | 10 |
| R07565 | eBPF LSM programs — attach to Linux Security Module hooks | 13696 | F03800 | non-negotiable | false | 10 |
| R07566 | eBPF LSM — allow/deny operations | 13696 | F03801 | non-negotiable | false | 10 |
| R07567 | eBPF LSM — example: socket creation | 13697 | F03801 | non-negotiable | false | 10 |
| R07568 | eBPF LSM — policy-dependent allow/deny | 13697 | F03801 | non-negotiable | false | 10 |
| R07569 | eBPF LSM URL — docs.ebpf.io/linux/program-type/BPF_PROG_TYPE_LSM | 13698 | F03802 | non-negotiable | false | 10 |
| R07570 | Truth pattern — "model says: I only read files" | 13704 | F03803 | non-negotiable | false | 10 |
| R07571 | Truth pattern — "eBPF observes: process opened network socket" | 13706 | F03804 | non-negotiable | false | 10 |
| R07572 | Truth pattern — runtime: block | 13708 | F03805 | non-negotiable | false | 10 |
| R07573 | Truth pattern — runtime: log | 13708 | F03805 | non-negotiable | false | 10 |
| R07574 | Truth pattern — runtime: alert | 13708 | F03805 | non-negotiable | false | 10 |
| R07575 | Truth pattern — runtime: quarantine | 13708 | F03805 | non-negotiable | false | 10 |
| R07576 | "This is a peace feature: reality over claims" | 13710 | F03806 | non-negotiable | false | 10 |
| R07577 | "Use eBPF carefully. It is powerful and sharp" | 13712 | F03807 | non-negotiable | false | 10 |
| R07578 | "But as an observability/enforcement layer for high-risk agent sandboxes, it fits" | 13713 | F03808 | non-negotiable | false | 10 |
| R07579 | Systemd section header | 13718 | F03809 | non-negotiable | false | 10 |
| R07580 | Agent sessions — "should not be loose processes" | 13720 | F03810 | non-negotiable | false | 10 |
| R07581 | Agent sessions — "should be scopes/services" | 13720 | F03811 | non-negotiable | false | 10 |
| R07582 | Unit example — agent-session@123.service | 13724 | F03812 | non-negotiable | false | 10 |
| R07583 | Unit example — agent-sandbox@abc.scope | 13725 | F03813 | non-negotiable | false | 10 |
| R07584 | Unit example — model-server@blackwell.service | 13726 | F03814 | non-negotiable | false | 10 |
| R07585 | Unit example — model-server@scout.service | 13727 | F03815 | non-negotiable | false | 10 |
| R07586 | Unit example — gateway.service | 13728 | F03816 | non-negotiable | false | 10 |
| R07587 | Unit example — memory-os.service | 13729 | F03817 | non-negotiable | false | 10 |
| R07588 | Unit example — eval-worker.slice | 13730 | F03818 | non-negotiable | false | 10 |
| R07589 | OS operation — start | 13734 | F03819 | non-negotiable | false | 10 |
| R07590 | OS operation — stop | 13734 | F03819 | non-negotiable | false | 10 |
| R07591 | OS operation — restart | 13734 | F03819 | non-negotiable | false | 10 |
| R07592 | OS operation — limit | 13735 | F03819 | non-negotiable | false | 10 |
| R07593 | OS operation — observe | 13735 | F03819 | non-negotiable | false | 10 |
| R07594 | OS operation — journal | 13736 | F03819 | non-negotiable | false | 10 |
| R07595 | OS operation — kill zombies | 13737 | F03819 | non-negotiable | false | 10 |
| R07596 | OS operation — freeze/hibernate | 13738 | F03819 | non-negotiable | false | 10 |
| R07597 | AgentRM mapping — scheduling | 13740 | F03820 | non-negotiable | false | 10 |
| R07598 | AgentRM mapping — zombie reaping | 13740 | F03820 | non-negotiable | false | 10 |
| R07599 | AgentRM mapping — context lifecycle management | 13740 | F03820 | non-negotiable | false | 10 |
| R07600 | Sovereign Profiles header | 13744 | E0434 | non-negotiable | false | 10 |
| R07601 | "User choice becomes enforceable" | 13746 | E0434 | non-negotiable | false | 10 |
| R07602 | Profile Offline Peace Mode — network egress denied | 13750 | F03821 | non-negotiable | false | 10 |
| R07603 | Profile Offline Peace Mode — cloud providers disabled | 13751 | F03821 | non-negotiable | false | 10 |
| R07604 | Profile Offline Peace Mode — local models only | 13752 | F03821 | non-negotiable | false | 10 |
| R07605 | Profile Research Mode — network allowed through gateway | 13755 | F03822 | non-negotiable | false | 10 |
| R07606 | Profile Research Mode — citations required | 13756 | F03822 | non-negotiable | false | 10 |
| R07607 | Profile Research Mode — cost tracked | 13757 | F03822 | non-negotiable | false | 10 |
| R07608 | Profile Autonomous Code Mode — sandbox required | 13760 | F03823 | non-negotiable | false | 10 |
| R07609 | Profile Autonomous Code Mode — ZFS snapshot before writes | 13761 | F03823 | non-negotiable | false | 10 |
| R07610 | Profile Autonomous Code Mode — tests required before commit | 13762 | F03823 | non-negotiable | false | 10 |
| R07611 | Profile High-Risk Mode — VM/microVM only | 13765 | F03824 | non-negotiable | false | 10 |
| R07612 | Profile High-Risk Mode — no host filesystem write | 13766 | F03824 | non-negotiable | false | 10 |
| R07613 | Profile High-Risk Mode — human gate for promotion | 13767 | F03824 | non-negotiable | false | 10 |
| R07614 | Profile Fast Local Mode — 3090 scout first | 13770 | F03824 | non-negotiable | false | 10 |
| R07615 | Profile Fast Local Mode — shallow memory | 13771 | F03824 | non-negotiable | false | 10 |
| R07616 | Profile Fast Local Mode — oracle only if confidence low | 13772 | F03824 | non-negotiable | false | 10 |
| R07617 | "These are not prompt styles" | 13774 | F03824 | non-negotiable | false | 10 |
| R07618 | "They are OS policies + runtime policies" | 13774 | F03824 | non-negotiable | false | 10 |
| R07619 | Hardware-meets-OS — AVX-512: fast policy and scheduling decisions | 13778 | M00763 | non-negotiable | false | 10 |
| R07620 | Hardware-meets-OS — cgroup/systemd: enforce resource decisions | 13780 | M00763 | non-negotiable | false | 10 |
| R07621 | Hardware-meets-OS — PSI/DCGM: sense pressure | 13782 | M00763 | non-negotiable | false | 10 |
| R07622 | Hardware-meets-OS — AppArmor/eBPF: observe and constrain behavior | 13784 | M00763 | non-negotiable | false | 10 |
| R07623 | Hardware-meets-OS — ZFS: make action reversible | 13786 | M00763 | non-negotiable | false | 10 |
| R07624 | Hardware-meets-OS — VFIO: hard isolate the 3090 sandbox | 13788 | M00763 | non-negotiable | false | 10 |
| R07625 | Hardware-meets-OS — Gateway: make all model/API communication auditable | 13790 | M00763 | non-negotiable | false | 10 |
| R07626 | "This is the bridge: hardware capability becomes social trust only when the OS can govern it" | 13794 | E0435 | non-negotiable | false | 10 |
| R07627 | Anti-war framing — clarity → traces/dashboard | 13806 | M00764 | non-negotiable | false | 10 |
| R07628 | Anti-war framing — consent → human gates/profiles | 13808 | M00764 | non-negotiable | false | 10 |
| R07629 | Anti-war framing — reversibility → ZFS/snapshots | 13810 | M00764 | non-negotiable | false | 10 |
| R07630 | Anti-war framing — proportionality → scheduler/profiles | 13812 | M00764 | non-negotiable | false | 10 |
| R07631 | Anti-war framing — containment → cgroups/AppArmor/VMs | 13814 | M00764 | non-negotiable | false | 10 |
| R07632 | Anti-war framing — memory → memory OS/replay | 13816 | M00764 | non-negotiable | false | 10 |
| R07633 | Anti-war framing — communication → Anthropic-first gateway/MCP | 13818 | M00764 | non-negotiable | false | 10 |
| R07634 | Anti-war framing — truth → tests/eBPF/PSI/evals | 13820 | M00764 | non-negotiable | false | 10 |
| R07635 | Peace machine virtue — clarity (explain what is happening) | 13796 | M00764 | non-negotiable | false | 10 |
| R07636 | Peace machine virtue — consent (ask when boundaries matter) | 13798 | M00764 | non-negotiable | false | 10 |
| R07637 | Peace machine virtue — reversibility (rollback when possible) | 13800 | M00764 | non-negotiable | false | 10 |
| R07638 | Peace machine virtue — proportionality (spend just enough intelligence) | 13802 | M00764 | non-negotiable | false | 10 |
| R07639 | Peace machine virtue — containment (risky action stays sandboxed) | 13804 | M00764 | non-negotiable | false | 10 |
| R07640 | Peace machine virtue — memory (learn from harm and success) | 13806 | M00764 | non-negotiable | false | 10 |
| R07641 | Peace machine virtue — communication (translate between humans systems models tools) | 13808 | M00764 | non-negotiable | false | 10 |
| R07642 | Peace machine virtue — truth (tests traces observations not vibes) | 13810 | M00764 | non-negotiable | false | 10 |
| R07643 | "Those are not abstract virtues. They map to technical primitives" | 13824 | E0436 | non-negotiable | false | 10 |
| R07644 | Key line — "Sovereign-OS becomes something more than an OS image" | 13826 | E0436 | non-negotiable | false | 10 |
| R07645 | Key line — "It becomes an environment where intelligence can act without becoming opaque power" | 13828 | E0436 | non-negotiable | false | 10 |
| R07646 | Operator final affirmation — "yes indeed. continue like do" | 13830 | E0437 | non-negotiable | false | 10 |
| R07647 | Operator final affirmation — "you can do online research too" | 13830 | E0437 | non-negotiable | false | 10 |
| R07648 | Operator final affirmation — "we will make this even better than the cloud provider... so much better" | 13830 | E0437 | non-negotiable | false | 10 |
| R07649 | Operator final affirmation — "even before I train and retrain and adapt weights and add my LORAs and such and whatnot" | 13830 | E0437 | non-negotiable | false | 10 |
| R07650 | Composite — M045 (10 epics / 17 modules / 85 features / 170 reqs) catalogs Linux as intelligence governor: 8 OS primitives (cgroup v2 / systemd / PSI / eBPF-LSM / AppArmor / namespaces / ZFS / LUKS-TPM-FIDO2) + Linux resource intelligence (CPUWeight/MemoryMax/IOWeight/task limits/slices/scopes) + 5 example workload boundaries (oracle.service / scout.slice / sandbox.slice / eval.slice / gateway.service) + PSI 6 pressure questions (CPU/Mem/IO/GPU/Human-attention/Cost) + 3 pressure sources (PSI=system / DCGM=GPU / runtime=cost-attention) + 5 adaptive-intelligence reactions + eBPF as truth sensor (LSM hook allow/deny + reality-over-claims + use carefully) + systemd 7-example unit names + 8 OS operations + AgentRM scheduling-zombie-reaping-context-lifecycle mapping + 5 enforceable sovereign profiles (Offline Peace / Research / Autonomous Code / High-Risk / Fast Local) + hardware-meets-OS 7 layer mappings + anti-war framing 8 virtue→primitive mappings + KEY LINE "environment where intelligence can act without becoming opaque power" + operator final affirmation "better than the cloud provider... so much better... even before I train and retrain and adapt weights and add my LORAs" | 13546–13825 | E0428-E0437 | non-negotiable | false | 10 |

## Sub-requirements accounting

- 170 requirements covering: operator directive + 8 OS primitives + "peace-machine substrate" (R07481–R07502) + Linux resource intelligence (R07503–R07515) + 5 example workload boundaries (R07516–R07531) + PSI doctrine + 6 pressure questions + 3 pressure sources (R07532–R07549) + 5 adaptive-intelligence reactions (R07550–R07562) + eBPF as truth sensor (LSM hooks + reality-over-claims + use carefully) (R07563–R07578) + systemd as agent lifecycle manager + 7 unit examples + 8 OS operations + AgentRM mapping (R07579–R07599) + 5 sovereign profiles + "OS policies + runtime policies" (R07600–R07618) + hardware-meets-OS 7 mappings (R07619–R07626) + anti-war framing 8 virtues + 8 mappings + key line (R07627–R07645) + operator final affirmation (R07646–R07649) + composite (R07650)
- Source range 13546–13825 yields 279 lines; 170 R-rows represent ~61% line-coverage at the verbatim-citation level
- Project boundary — M045 is sovereign-os OS-governance scope; selfdef MS017 agent-guard enforces a subset of these OS primitives (cgroup/seccomp/AppArmor) for the IPS-side; selfdef MS019 threat model treats these primitives as defense surfaces

## Cross-references

- Adjacent dump-range milestones: M044 Sovereign-OS substrate Debian 13/Ubuntu 24 (13307–13546) / M046 Beat the cloud — runtime adaptation + LoRA foundry (next; dump 13825–14107)
- Plane integration — M045 sits on M044's Sovereign-OS 8-plane substrate (Kernel + Security + Compute + Storage + Sandbox + Gateway + Observability + Choice); refines the Sandbox + Security + Observability planes with cgroup v2 / systemd / PSI / eBPF; extends M043 hardware-aware intelligence scheduling with kernel-level pressure sensing
- Profile integration — M045's 5 enforceable Sovereign Profiles (Offline Peace / Research / Autonomous Code / High-Risk / Fast Local) extend M044's 4 security profiles (secure / developer / agent-lab / high-risk) and M042's 4 profile bundles (private / careful / fast / sovereign)
- Adaptive intelligence — 5 pressure-reactions (memory / IO / CPU / GPU oracle idle / 3090 idle) realize M043's AVX-512 Routing Brain 8 bulk-eval decisions at the OS-pressure-feedback layer
- AgentRM integration — systemd unit-management (start/stop/restart/limit/observe/journal/kill zombies/freeze-hibernate) is the AgentRM idea grounded in OS primitives
- Selfdef integration — MS017 agent-guard 2 profiles + 2 scope strategies align with M045's 5 sovereign profiles; MS016 eBPF (Tetragon TracingPolicies) implements the eBPF LSM truth sensor; MS019 threat model treats cgroup/AppArmor/eBPF as defense layer
- Operator references: kernel.org/doc/html/latest/admin-guide/cgroup-v2.html + freedesktop.org/software/systemd/man/devel/systemd.resource-control.html + kernel.org/doc/html/v6.0/accounting/psi.html + docs.ebpf.io/linux/program-type/BPF_PROG_TYPE_LSM + Linux cgroup v2 resource control systemd delegation containers official docs (web search)
