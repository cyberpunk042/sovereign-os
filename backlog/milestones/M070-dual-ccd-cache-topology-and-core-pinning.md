# M070 — Dual-CCD cache topology + core pinning (CCD 0 = Pulse / CCD 1 = Weaver+Auditor+Host)

**Parent**: sovereign-os runtime — substrate microarchitecture layer
**Source**: `~/infohub/raw/dumps/2026-05-15-sain-01-master-spec-other-conversation-transposition.md` lines 1013-1037 (Section 19: The Dual-CCD Cache Topology)
**Note**: M069 slot reserved for Guardian Daemon was moved to selfdef MS044 per "Respect the projects". This milestone numbered M070 per prior-dump-review proposal mapping; sovereign-os internal sequential ID = 69th sovereign-os milestone.

## Doctrinal anchors

> "The **Ryzen 9 9900X** is an engineering masterpiece, but it contains a distinct structural boundary that will introduce severe 'Friction' if ignored: it utilizes a dual-CCD (Core Complex Die) design." (dump 1014)
> "To achieve 'Magician' grade efficiency, we physically partition the processor's architecture along the CCD boundaries, matching the **Single Responsibility Principle (SRP)** of your software trinity." (dump 1020-1021)

## Epics (E0668-E0677)

| epic | name | source |
|---|---|---|
| E0668 | Physical bottleneck — Infinity Fabric L3 cache-miss + cross-die latency penalty | dump 1016-1018 |
| E0669 | CCD 0 — Cores 0-5 / Threads 0-11 / local 32MB L3 cache | dump 1015 |
| E0670 | CCD 1 — Cores 6-11 / Threads 12-23 / isolated 32MB L3 cache | dump 1016 |
| E0671 | Core isolation strategy — partition along CCD boundaries matching SRP Trinity | dump 1020-1021 |
| E0672 | The Pulse Core allocation — Cores 0-5 (CCD 0) / threads 0-11 / thread mask 0xfff | dump 1024 |
| E0673 | The Weaver + Auditor allocation — Cores 6-9 (CCD 1) / threads 12-19 / thread mask 0xff000 | dump 1025 |
| E0674 | System Host / OS Base allocation — Cores 10-11 (CCD 1) / threads 20-23 / thread mask 0xf00000 | dump 1026 |
| E0675 | CCD-aware scheduling — taskset / cgroup v2 cpuset enforcement | dump 1024-1026 + cross-ref M058 |
| E0676 | CCD-aware memory placement — NUMA-style affinity (CCD-local L3 first) | dump 1018 + architecture |
| E0677 | CCD-aware IO routing — drivers + interrupts pinned to System Host CCD 1 cores | dump 1026 |

## Modules (M01156-M01172)

| module | name | source |
|---|---|---|
| M01156 | sovereign-ccd-topology-detector | dump 1014-1016 |
| M01157 | sovereign-ccd-0-pulse-core-allocator | dump 1024 |
| M01158 | sovereign-ccd-1-weaver-auditor-allocator | dump 1025 |
| M01159 | sovereign-ccd-1-host-os-allocator | dump 1026 |
| M01160 | sovereign-ccd-taskset-coordinator | dump 1024-1026 |
| M01161 | sovereign-ccd-cgroup-v2-cpuset-enforcer | architecture + cross-ref M045 |
| M01162 | sovereign-ccd-memory-affinity-tuner | dump 1018 |
| M01163 | sovereign-ccd-l3-cache-locality-monitor | dump 1015-1018 |
| M01164 | sovereign-ccd-infinity-fabric-latency-tracker | dump 1018 |
| M01165 | sovereign-ccd-irq-affinity-binder (network/IO interrupts to CCD 1 host cores) | dump 1026 |
| M01166 | sovereign-ccd-typed-mirror | cross-ref selfdef MS007 |
| M01167 | sovereign-ccd-event-emitter | cross-ref M049 + selfdef MS026 |
| M01168 | sovereign-ccd-dashboard-binding (D-03 + D-09) | cross-ref M060 |
| M01169 | sovereign-ccd-srp-trinity-mapper (Pulse/Weaver/Auditor → CCD allocation) | dump 1020-1026 + cross-ref M066 |
| M01170 | sovereign-ccd-allocation-replay-validator | cross-ref selfdef MS009 |
| M01171 | sovereign-ccd-allocation-signer | cross-ref selfdef MS003 |
| M01172 | sovereign-ccd-cli-subcommand-set | cross-ref selfdef MS043 |

## Features (F05781-F05865)

| feature | name | source |
|---|---|---|
| F05781 | Ryzen 9 9900X — dual-CCD (Core Complex Die) design | dump 1014 |
| F05782 | Structural boundary — introduces severe "Friction" if ignored | dump 1014 |
| F05783 | CCD 0 — Cores 0-5 | dump 1015 |
| F05784 | CCD 0 — Threads 0-11 (12 hyperthreads) | dump 1015 |
| F05785 | CCD 0 — local 32MB L3 cache | dump 1015 |
| F05786 | CCD 1 — Cores 6-11 | dump 1016 |
| F05787 | CCD 1 — Threads 12-23 (12 hyperthreads) | dump 1016 |
| F05788 | CCD 1 — isolated 32MB L3 cache | dump 1016 |
| F05789 | Bottleneck — cross-CCD pipe traverses AMD Infinity Fabric | dump 1018 |
| F05790 | Bottleneck — cross-CCD pipe causes immediate L3 cache miss | dump 1018 |
| F05791 | Bottleneck — cross-CCD pipe causes massive cross-die latency penalty | dump 1018 |
| F05792 | Bottleneck — Conductor on Core 2 → compilation runtime on Core 8 example | dump 1018 |
| F05793 | Strategy — physically partition processor along CCD boundaries | dump 1020 |
| F05794 | Strategy — match SRP of software trinity (M066 Pulse/Weaver/Auditor) | dump 1020-1021 + cross-ref M066 |
| F05795 | Strategy — achieves "Magician" grade efficiency | dump 1020 |
| F05796 | The Pulse Core — Cores 0-5 (CCD 0) | dump 1024 |
| F05797 | The Pulse Core — Thread mask 0-11 (0xfff hex) | dump 1024 |
| F05798 | The Pulse Core — dedicated to high-speed AVX-512 vector processing | dump 1024 |
| F05799 | The Pulse Core — runs 1-bit bitnet.cpp matrix lookups | dump 1024 |
| F05800 | The Pulse Core — runs local runtime compilation (Wasm AOT) | dump 1024 |
| F05801 | The Weaver + Auditor — Cores 6-9 (CCD 1) | dump 1025 |
| F05802 | The Weaver + Auditor — Thread mask 12-19 (0xff000 hex) | dump 1025 |
| F05803 | The Weaver + Auditor — runs system state engine | dump 1025 |
| F05804 | The Weaver + Auditor — parses CLAUDE.md | dump 1025 |
| F05805 | The Weaver + Auditor — manages gRPC streams from Tetragon | dump 1025 |
| F05806 | The Weaver + Auditor — routes network I/O | dump 1025 |
| F05807 | System Host — Cores 10-11 (CCD 1) | dump 1026 |
| F05808 | System Host — Thread mask 20-23 (0xf00000 hex) | dump 1026 |
| F05809 | System Host — Debian kernel interrupts | dump 1026 |
| F05810 | System Host — Marvell 10GbE network drivers | dump 1026 |
| F05811 | System Host — background ZFS compression threads | dump 1026 |
| F05812 | Enforcement — taskset for process pinning | dump 1024-1026 |
| F05813 | Enforcement — cgroup v2 cpuset for permanent allocation | architecture + cross-ref M045 |
| F05814 | Enforcement — systemd CPUAffinity directive for service-level pinning | architecture |
| F05815 | Enforcement — operator-customizable via /etc/sovereign-os/ccd-allocation.toml | architecture |
| F05816 | Enforcement — allocation TOML signed via MS003 | cross-ref selfdef MS003 |
| F05817 | Enforcement — allocation changes emit OCSF Configuration Change 5001 | cross-ref selfdef MS026 |
| F05818 | Enforcement — allocation changes emit M049 trace | cross-ref M049 |
| F05819 | Enforcement — allocation changes signed via MS003 | cross-ref selfdef MS003 |
| F05820 | Enforcement — illegal allocation (crossing CCD boundary for SRP-pinned process) blocks merge in CI | architecture + M063 |
| F05821 | Memory affinity — NUMA-style CCD-local L3 first | dump 1018 + architecture |
| F05822 | Memory affinity — `numactl --cpunodebind` for memory locality | architecture |
| F05823 | Memory affinity — Linux memory policy MPOL_BIND for hard binding | architecture |
| F05824 | Memory affinity — operator-customizable per process | architecture |
| F05825 | L3 cache monitor — surfaces cache miss rate per CCD via D-09 | cross-ref M060 |
| F05826 | L3 cache monitor — uses perf events (LLC-load-misses) | architecture |
| F05827 | L3 cache monitor — emits M049 metric | cross-ref M049 |
| F05828 | L3 cache monitor — alerts on cross-CCD spike (potential SRP violation) | architecture + cross-ref M055 |
| F05829 | Infinity Fabric tracker — measures inter-CCD bandwidth + latency | dump 1018 |
| F05830 | Infinity Fabric tracker — surfaces via D-09 hardware pressure | cross-ref M060 |
| F05831 | IRQ affinity — network IRQs pinned to CCD 1 System Host cores | dump 1026 |
| F05832 | IRQ affinity — IO IRQs pinned to CCD 1 System Host cores | dump 1026 |
| F05833 | IRQ affinity — set via `/proc/irq/<n>/smp_affinity` | architecture |
| F05834 | IRQ affinity — operator-customizable via /etc/sovereign-os/irq-affinity.toml | architecture |
| F05835 | IRQ affinity — signed via MS003 | cross-ref selfdef MS003 |
| F05836 | Typed mirror — sovereign-ccd-allocation-mirror under MS007 8/8 SATURATED | cross-ref selfdef MS007 |
| F05837 | Typed mirror — CcdAllocation struct {layer, cpu_cores, thread_mask, responsibility} | cross-ref selfdef MS007 |
| F05838 | Typed mirror — ExecutionLayer enum (Pulse / WeaverAuditor / SystemHost) | cross-ref selfdef MS007 |
| F05839 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 |
| F05840 | Typed mirror — signed via MS003 | cross-ref selfdef MS003 |
| F05841 | Event emitter — every allocation change emits M049 trace | cross-ref M049 |
| F05842 | Event emitter — every allocation change emits OCSF Configuration Change 5001 | cross-ref selfdef MS026 |
| F05843 | Event emitter — every SRP violation (cross-CCD pipe detected) emits OCSF Detection 2004 | cross-ref selfdef MS026 |
| F05844 | Dashboard — D-03 model health shows per-CCD CPU utilization | cross-ref M060 |
| F05845 | Dashboard — D-09 hardware pressure shows L3 cache miss rate per CCD | cross-ref M060 |
| F05846 | Dashboard — D-09 hardware pressure shows Infinity Fabric utilization | cross-ref M060 |
| F05847 | SRP trinity mapper — Pulse → CCD 0, Weaver+Auditor → CCD 1 cores 6-9, Host → CCD 1 cores 10-11 | dump 1020-1026 + cross-ref M066 |
| F05848 | SRP trinity mapper — verifies trinity-process placement at start | cross-ref M066 |
| F05849 | SRP trinity mapper — emits OCSF Detection 2004 on placement violation | cross-ref selfdef MS026 |
| F05850 | Replay validator — verifies historical allocation chain | cross-ref selfdef MS009 |
| F05851 | Replay validator — detects unauthorized allocation change | cross-ref selfdef MS009 + MS003 |
| F05852 | Replay validator — emits OCSF Detection 2004 on chain break | cross-ref selfdef MS026 |
| F05853 | Replay validator — runs daily as systemd timer | cross-ref selfdef MS009 |
| F05854 | CLI — `sovereign ccd show` returns current allocation | cross-ref selfdef MS043 |
| F05855 | CLI — `sovereign ccd allocation list` shows per-layer mapping | cross-ref selfdef MS043 |
| F05856 | CLI — `sovereign ccd verify` checks all trinity processes on correct CCD | architecture |
| F05857 | CLI — `sovereign ccd mismatch` returns processes on wrong CCD | architecture |
| F05858 | CLI — all ccd subcommands emit M049 trace | cross-ref M049 |
| F05859 | Boundary — sovereign-os runtime owns CCD allocation | architecture + operator standing direction |
| F05860 | Boundary — selfdef IPS does NOT mutate CCD allocation | operator standing direction |
| F05861 | Composition — composes with M058 hardware-aware scheduler (CPU resource tracking) | cross-ref M058 |
| F05862 | Composition — composes with M066 Trinity Framework (SRP → CCD mapping) | cross-ref M066 |
| F05863 | Composition — composes with M067 kernel build (kernel scheduler honors cpuset) | cross-ref M067 |
| F05864 | Composition — composes with M068 ZFS (background ZFS compression on CCD 1 host cores) | cross-ref M068 |
| F05865 | Closing — M070 covers dump 1013-1037 verbatim dual-CCD topology scope | dump 1013-1037 |

## Requirements (R11561-R11730)

| req | description | source | feature | priority | exception | sub-reqs |
|---|---|---|---|---|---|---|
| R11561 | Doctrinal — Ryzen 9 9900X dual-CCD design | dump 1014 | F05781 | non-negotiable | false | 10 |
| R11562 | Doctrinal — dual-CCD = structural boundary causing severe "Friction" if ignored | dump 1014 | F05782 | non-negotiable | false | 10 |
| R11563 | Doctrinal — "Magician" grade efficiency via CCD partition matching SRP | dump 1020-1021 | F05795 | non-negotiable | false | 10 |
| R11564 | Doctrinal — partition matches M066 Trinity (Pulse / Weaver+Auditor / Host) | dump 1020-1021 + cross-ref M066 | F05794 | non-negotiable | false | 10 |
| R11565 | CCD 0 — Cores 0-5 verbatim | dump 1015 | F05783 | non-negotiable | false | 10 |
| R11566 | CCD 0 — Threads 0-11 verbatim | dump 1015 | F05784 | non-negotiable | false | 10 |
| R11567 | CCD 0 — local 32MB L3 cache | dump 1015 | F05785 | non-negotiable | false | 10 |
| R11568 | CCD 1 — Cores 6-11 verbatim | dump 1016 | F05786 | non-negotiable | false | 10 |
| R11569 | CCD 1 — Threads 12-23 verbatim | dump 1016 | F05787 | non-negotiable | false | 10 |
| R11570 | CCD 1 — isolated 32MB L3 cache | dump 1016 | F05788 | non-negotiable | false | 10 |
| R11571 | Friction — cross-CCD pipe traverses AMD Infinity Fabric | dump 1018 | F05789 | non-negotiable | false | 10 |
| R11572 | Friction — cross-CCD pipe causes immediate L3 cache miss | dump 1018 | F05790 | non-negotiable | false | 10 |
| R11573 | Friction — cross-CCD pipe causes massive cross-die latency penalty | dump 1018 | F05791 | non-negotiable | false | 10 |
| R11574 | Friction — example: Conductor Core 2 → compilation Core 8 | dump 1018 | F05792 | non-negotiable | false | 10 |
| R11575 | Friction — example: Core 2 = CCD 0, Core 8 = CCD 1 | dump 1018 | F05792 | non-negotiable | false | 10 |
| R11576 | Pulse — Cores 0-5 (CCD 0) | dump 1024 | F05796 | non-negotiable | false | 10 |
| R11577 | Pulse — thread mask 0-11 (0xfff hex) | dump 1024 | F05797 | non-negotiable | false | 10 |
| R11578 | Pulse — dedicated to high-speed AVX-512 vector processing | dump 1024 | F05798 | non-negotiable | false | 10 |
| R11579 | Pulse — 1-bit bitnet.cpp matrix lookups | dump 1024 | F05799 | non-negotiable | false | 10 |
| R11580 | Pulse — local runtime compilation (Wasm AOT) | dump 1024 | F05800 | non-negotiable | false | 10 |
| R11581 | Weaver+Auditor — Cores 6-9 (CCD 1) | dump 1025 | F05801 | non-negotiable | false | 10 |
| R11582 | Weaver+Auditor — thread mask 12-19 (0xff000 hex) | dump 1025 | F05802 | non-negotiable | false | 10 |
| R11583 | Weaver+Auditor — runs system state engine | dump 1025 | F05803 | non-negotiable | false | 10 |
| R11584 | Weaver+Auditor — parses CLAUDE.md | dump 1025 | F05804 | non-negotiable | false | 10 |
| R11585 | Weaver+Auditor — manages gRPC streams from Tetragon | dump 1025 | F05805 | non-negotiable | false | 10 |
| R11586 | Weaver+Auditor — routes network I/O | dump 1025 | F05806 | non-negotiable | false | 10 |
| R11587 | System Host — Cores 10-11 (CCD 1) | dump 1026 | F05807 | non-negotiable | false | 10 |
| R11588 | System Host — thread mask 20-23 (0xf00000 hex) | dump 1026 | F05808 | non-negotiable | false | 10 |
| R11589 | System Host — Debian kernel interrupts | dump 1026 | F05809 | non-negotiable | false | 10 |
| R11590 | System Host — Marvell 10GbE network drivers | dump 1026 | F05810 | non-negotiable | false | 10 |
| R11591 | System Host — background ZFS compression threads | dump 1026 | F05811 | non-negotiable | false | 10 |
| R11592 | Enforcement — taskset for process pinning | dump 1024-1026 | F05812 | non-negotiable | false | 10 |
| R11593 | Enforcement — cgroup v2 cpuset for permanent allocation | architecture + cross-ref M045 | F05813 | non-negotiable | false | 10 |
| R11594 | Enforcement — systemd CPUAffinity directive for service-level pinning | architecture | F05814 | non-negotiable | false | 10 |
| R11595 | Enforcement — operator-customizable via /etc/sovereign-os/ccd-allocation.toml | architecture | F05815 | non-negotiable | false | 10 |
| R11596 | Enforcement — allocation TOML signed via MS003 | cross-ref selfdef MS003 | F05816 | non-negotiable | false | 10 |
| R11597 | Enforcement — allocation changes emit OCSF Configuration Change 5001 | cross-ref selfdef MS026 | F05817 | non-negotiable | false | 10 |
| R11598 | Enforcement — allocation changes emit M049 trace | cross-ref M049 | F05818 | non-negotiable | false | 10 |
| R11599 | Enforcement — allocation changes signed via MS003 | cross-ref selfdef MS003 | F05819 | non-negotiable | false | 10 |
| R11600 | Enforcement — illegal allocation blocks merge in CI | architecture + M063 | F05820 | non-negotiable | false | 10 |
| R11601 | Memory — NUMA-style CCD-local L3 first | dump 1018 + architecture | F05821 | non-negotiable | false | 10 |
| R11602 | Memory — `numactl --cpunodebind` for memory locality | architecture | F05822 | non-negotiable | false | 10 |
| R11603 | Memory — MPOL_BIND for hard binding | architecture | F05823 | non-negotiable | false | 10 |
| R11604 | Memory — operator-customizable per process | architecture | F05824 | non-negotiable | false | 10 |
| R11605 | Memory — memory policy violation emits OCSF Detection 2004 | cross-ref selfdef MS026 | F05823 | non-negotiable | false | 10 |
| R11606 | L3 cache monitor — surfaces miss rate per CCD via D-09 | cross-ref M060 | F05825 | non-negotiable | false | 10 |
| R11607 | L3 cache monitor — uses perf events LLC-load-misses | architecture | F05826 | non-negotiable | false | 10 |
| R11608 | L3 cache monitor — emits M049 metric | cross-ref M049 | F05827 | non-negotiable | false | 10 |
| R11609 | L3 cache monitor — alerts on cross-CCD spike (SRP violation indicator) | architecture + cross-ref M055 | F05828 | non-negotiable | false | 10 |
| R11610 | Infinity Fabric tracker — measures inter-CCD bandwidth | dump 1018 | F05829 | non-negotiable | false | 10 |
| R11611 | Infinity Fabric tracker — measures inter-CCD latency | dump 1018 | F05829 | non-negotiable | false | 10 |
| R11612 | Infinity Fabric tracker — surfaces via D-09 | cross-ref M060 | F05830 | non-negotiable | false | 10 |
| R11613 | IRQ affinity — network IRQs pinned to CCD 1 System Host cores | dump 1026 | F05831 | non-negotiable | false | 10 |
| R11614 | IRQ affinity — IO IRQs pinned to CCD 1 System Host cores | dump 1026 | F05832 | non-negotiable | false | 10 |
| R11615 | IRQ affinity — set via /proc/irq/<n>/smp_affinity | architecture | F05833 | non-negotiable | false | 10 |
| R11616 | IRQ affinity — operator-customizable via /etc/sovereign-os/irq-affinity.toml | architecture | F05834 | non-negotiable | false | 10 |
| R11617 | IRQ affinity — signed via MS003 | cross-ref selfdef MS003 | F05835 | non-negotiable | false | 10 |
| R11618 | Typed mirror — sovereign-ccd-allocation-mirror under MS007 8/8 SATURATED | cross-ref selfdef MS007 | F05836 | non-negotiable | false | 10 |
| R11619 | Typed mirror — CcdAllocation struct fields | cross-ref selfdef MS007 | F05837 | non-negotiable | false | 10 |
| R11620 | Typed mirror — ExecutionLayer enum (Pulse / WeaverAuditor / SystemHost) | cross-ref selfdef MS007 | F05838 | non-negotiable | false | 10 |
| R11621 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 | F05839 | non-negotiable | false | 10 |
| R11622 | Typed mirror — signed via MS003 | cross-ref selfdef MS003 | F05840 | non-negotiable | false | 10 |
| R11623 | Typed mirror — re-exported via sovereign-os cargo workspace | cross-ref selfdef MS007 | F05836 | non-negotiable | false | 10 |
| R11624 | Typed mirror — no_std friendly | architecture | F05836 | non-negotiable | false | 10 |
| R11625 | Typed mirror — serde + bincode derives present | architecture | F05836 | non-negotiable | false | 10 |
| R11626 | Typed mirror — schema-breaking changes require schema_version bump | architecture + cross-ref selfdef MS007 | F05839 | non-negotiable | false | 10 |
| R11627 | Event emitter — every allocation change emits M049 trace | cross-ref M049 | F05841 | non-negotiable | false | 10 |
| R11628 | Event emitter — every allocation change emits OCSF Configuration Change 5001 | cross-ref selfdef MS026 | F05842 | non-negotiable | false | 10 |
| R11629 | Event emitter — every SRP violation emits OCSF Detection 2004 | cross-ref selfdef MS026 | F05843 | non-negotiable | false | 10 |
| R11630 | Dashboard — D-03 model health shows per-CCD CPU utilization | cross-ref M060 | F05844 | non-negotiable | false | 10 |
| R11631 | Dashboard — D-09 hardware pressure shows L3 cache miss rate per CCD | cross-ref M060 | F05845 | non-negotiable | false | 10 |
| R11632 | Dashboard — D-09 hardware pressure shows Infinity Fabric utilization | cross-ref M060 | F05846 | non-negotiable | false | 10 |
| R11633 | SRP mapper — Pulse → CCD 0 | dump 1024 + cross-ref M066 | F05847 | non-negotiable | false | 10 |
| R11634 | SRP mapper — Weaver+Auditor → CCD 1 cores 6-9 | dump 1025 + cross-ref M066 | F05847 | non-negotiable | false | 10 |
| R11635 | SRP mapper — System Host → CCD 1 cores 10-11 | dump 1026 + cross-ref M066 | F05847 | non-negotiable | false | 10 |
| R11636 | SRP mapper — verifies trinity-process placement at start | cross-ref M066 | F05848 | non-negotiable | false | 10 |
| R11637 | SRP mapper — emits OCSF Detection 2004 on placement violation | cross-ref selfdef MS026 | F05849 | non-negotiable | false | 10 |
| R11638 | Replay validator — verifies historical allocation chain | cross-ref selfdef MS009 | F05850 | non-negotiable | false | 10 |
| R11639 | Replay validator — detects unauthorized allocation change | cross-ref selfdef MS009 + MS003 | F05851 | non-negotiable | false | 10 |
| R11640 | Replay validator — emits OCSF Detection 2004 on chain break | cross-ref selfdef MS026 | F05852 | non-negotiable | false | 10 |
| R11641 | Replay validator — runs daily as systemd timer | cross-ref selfdef MS009 | F05853 | non-negotiable | false | 10 |
| R11642 | Replay validator — failures halt new allocation changes until resolved | architecture | F05850 | non-negotiable | false | 10 |
| R11643 | CLI — `sovereign ccd show` returns current allocation | cross-ref selfdef MS043 | F05854 | non-negotiable | false | 10 |
| R11644 | CLI — `sovereign ccd allocation list` shows per-layer mapping | cross-ref selfdef MS043 | F05855 | non-negotiable | false | 10 |
| R11645 | CLI — `sovereign ccd verify` checks all trinity processes on correct CCD | architecture | F05856 | non-negotiable | false | 10 |
| R11646 | CLI — `sovereign ccd mismatch` returns processes on wrong CCD | architecture | F05857 | non-negotiable | false | 10 |
| R11647 | CLI — all ccd subcommands emit M049 trace | cross-ref M049 | F05858 | non-negotiable | false | 10 |
| R11648 | CLI — all ccd subcommands signed via MS003 (when mutating) | cross-ref selfdef MS003 | F05819 | non-negotiable | false | 10 |
| R11649 | CLI — `sovereign ccd pin <pid> <cpus>` pins running process | architecture | F05812 | non-negotiable | false | 10 |
| R11650 | CLI — `sovereign ccd unpin <pid>` removes pinning | architecture | F05812 | non-negotiable | false | 10 |
| R11651 | Boundary — sovereign-os runtime owns CCD allocation | architecture + operator standing direction | F05859 | non-negotiable | false | 10 |
| R11652 | Boundary — selfdef IPS does NOT mutate CCD allocation | operator standing direction | F05860 | non-negotiable | false | 10 |
| R11653 | Boundary — sovereign-os publishes ccd-allocation-mirror; selfdef consumes read-only | cross-ref selfdef MS007 | F05836 | non-negotiable | false | 10 |
| R11654 | Boundary — info-hub indexes CCD topology as second-brain entry | operator standing direction | F05865 | non-negotiable | false | 10 |
| R11655 | Composition — composes with M058 hardware-aware scheduler (CPU resource tracking) | cross-ref M058 | F05861 | non-negotiable | false | 10 |
| R11656 | Composition — composes with M066 Trinity Framework (SRP → CCD mapping) | cross-ref M066 | F05862 | non-negotiable | false | 10 |
| R11657 | Composition — composes with M067 kernel build (kernel scheduler honors cpuset) | cross-ref M067 | F05863 | non-negotiable | false | 10 |
| R11658 | Composition — composes with M068 ZFS (background ZFS compression threads on CCD 1 host) | cross-ref M068 | F05864 | non-negotiable | false | 10 |
| R11659 | Composition — composes with M045 Linux as intelligence governor (cgroup v2) | cross-ref M045 | F05813 | non-negotiable | false | 10 |
| R11660 | Composition — composes with M057 12-step task lifecycle (Map step routes to CCD) | cross-ref M057 | F05847 | non-negotiable | false | 10 |
| R11661 | Composition — composes with M060 cockpit (D-03 + D-09 surface CCD state) | cross-ref M060 | F05844 | non-negotiable | false | 10 |
| R11662 | Composition — composes with M061 canon-update (Scheduler-as-policy-layer canon) | cross-ref M061 | F05861 | non-negotiable | false | 10 |
| R11663 | Composition — composes with M063 SFIF Infrastructure phase | cross-ref M063 | F05813 | non-negotiable | false | 10 |
| R11664 | Composition — composes forward with M071 Atomic State Transition (Weaver thread Core 12) | cross-ref M071 (pending) | F05801 | non-negotiable | false | 10 |
| R11665 | Composition — composes forward with M073 1-bit ternary (Pulse AVX-512 path) | cross-ref M073 (pending) | F05798 | non-negotiable | false | 10 |
| R11666 | Composition — composes forward with M074 AVX-512 VNNI fusion (Pulse single-cycle) | cross-ref M074 (pending) | F05798 | non-negotiable | false | 10 |
| R11667 | Composition — composes forward with M075 SRP hardware topology (full mapping) | cross-ref M075 (pending) | F05847 | non-negotiable | false | 10 |
| R11668 | Composition — composes forward with M076 3 load-balancing profiles | cross-ref M076 (pending) | F05847 | non-negotiable | false | 10 |
| R11669 | Composition — composes with selfdef MS039 (Guardian Ring 0 placement honors CCD topology) | cross-ref selfdef MS039 | F05803 | non-negotiable | false | 10 |
| R11670 | Composition — composes with selfdef MS044 (Guardian thread on Weaver+Auditor CCD 1 cores) | cross-ref selfdef MS044 | F05801 | non-negotiable | false | 10 |
| R11671 | Performance — cross-CCD pipe latency `<` 100ns measured at scheduler | architecture | F05789 | non-negotiable | false | 10 |
| R11672 | Performance — L3 cache miss rate `<` 5% per CCD (target) | architecture | F05825 | non-negotiable | false | 10 |
| R11673 | Performance — allocation change runtime `<` 100ms p95 | architecture | F05812 | non-negotiable | false | 10 |
| R11674 | Performance — `sovereign ccd show` runtime `<` 50ms p95 | architecture | F05854 | non-negotiable | false | 10 |
| R11675 | Performance — `sovereign ccd verify` runtime `<` 1s p95 | architecture | F05856 | non-negotiable | false | 10 |
| R11676 | Performance — typed-mirror publication latency `<` 100ms p95 | cross-ref selfdef MS007 | F05836 | non-negotiable | false | 10 |
| R11677 | Telemetry — per-CCD CPU utilization emitted via M049 | cross-ref M049 | F05844 | non-negotiable | false | 10 |
| R11678 | Telemetry — per-CCD L3 cache miss rate emitted via M049 | cross-ref M049 | F05845 | non-negotiable | false | 10 |
| R11679 | Telemetry — Infinity Fabric bandwidth emitted via M049 | cross-ref M049 | F05846 | non-negotiable | false | 10 |
| R11680 | Telemetry — SRP violation count emitted via M049 (high-priority alert) | cross-ref M049 | F05849 | non-negotiable | false | 10 |
| R11681 | Telemetry — allocation change count emitted via M049 | cross-ref M049 | F05818 | non-negotiable | false | 10 |
| R11682 | Operational — CCD coordinator runs as systemd unit sovereign-ccd-coordinator.service | architecture | F05813 | non-negotiable | false | 10 |
| R11683 | Operational — coordinator honors SIGHUP for allocation reload | architecture | F05813 | non-negotiable | false | 10 |
| R11684 | Operational — coordinator refuses to start with chain-break detected | cross-ref selfdef MS009 | F05850 | non-negotiable | false | 10 |
| R11685 | Operational — coordinator refuses to start with missing MS003 keys | cross-ref selfdef MS003 | F05819 | non-negotiable | false | 10 |
| R11686 | Operational — coordinator graceful drain on shutdown | architecture | F05813 | non-negotiable | false | 10 |
| R11687 | Operational — coordinator readiness probe at /run/sovereign-ccd/ready | architecture | F05813 | non-negotiable | false | 10 |
| R11688 | Operational — coordinator detects CPU topology at boot via /proc/cpuinfo + lscpu | architecture | F05781 | non-negotiable | false | 10 |
| R11689 | Operational — coordinator caches detection result with kernel-version key | architecture | F05781 | non-negotiable | false | 10 |
| R11690 | Operational — coordinator emits OCSF System Activity class 1001 on detection | cross-ref selfdef MS026 | F05841 | non-negotiable | false | 10 |
| R11691 | Doctrinal preservation — "Magician grade efficiency" verbatim | dump 1020 | F05795 | non-negotiable | false | 10 |
| R11692 | Doctrinal preservation — "Friction" verbatim | dump 1014 | F05782 | non-negotiable | false | 10 |
| R11693 | Doctrinal preservation — "Infinity Fabric" verbatim | dump 1018 | F05789 | non-negotiable | false | 10 |
| R11694 | Doctrinal preservation — thread mask hex notations (0xfff / 0xff000 / 0xf00000) verbatim | dump 1024-1026 | F05797 | non-negotiable | false | 10 |
| R11695 | Doctrinal preservation — verbatim quotes never paraphrased | operator standing direction | F05865 | non-negotiable | false | 10 |
| R11696 | Doctrinal preservation — info-hub indexes CCD topology as second-brain entry | operator standing direction "second-brain" | F05865 | non-negotiable | false | 10 |
| R11697 | High-risk — CCD allocation change is L6 Persist (super-model manifest update) | cross-ref selfdef MS039 + M059 | F05819 | non-negotiable | false | 10 |
| R11698 | High-risk — CCD allocation change requires MS041 triple-gate (snapshot + test/eval + oracle-or-human) | cross-ref selfdef MS041 | F05820 | non-negotiable | false | 10 |
| R11699 | High-risk — snapshot via ZFS pre-commit | cross-ref selfdef MS037 + M068 | F05816 | non-negotiable | false | 10 |
| R11700 | High-risk — test/eval = trinity-placement validation post-change | architecture | F05848 | non-negotiable | false | 10 |
| R11701 | High-risk — oracle-or-human = operator approval | cross-ref selfdef MS041 | F05820 | non-negotiable | false | 10 |
| R11702 | Closing — physical bottleneck section covered dump 1015-1018 verbatim | dump 1015-1018 | F05789 | non-negotiable | false | 10 |
| R11703 | Closing — core isolation strategy covered dump 1020-1026 verbatim | dump 1020-1026 | F05793 | non-negotiable | false | 10 |
| R11704 | Closing — table preserved verbatim (4-column: Execution Layer / Physical Core / Thread Mask / Responsibility) | dump 1023-1026 | F05847 | non-negotiable | false | 10 |
| R11705 | Closing — sovereign-os catalog at 69/69 milestones | architecture | F05865 | non-negotiable | false | 10 |
| R11706 | Closing — combined ecosystem 113 milestones | architecture | F05865 | non-negotiable | false | 10 |
| R11707 | Closing — combined R-rows ~22290 | architecture | F05865 | non-negotiable | false | 10 |
| R11708 | Closing — combined enforced sub-reqs ~222900 | architecture | F05865 | non-negotiable | false | 10 |
| R11709 | Closing — every R-row carries 10 hard non-negotiable sub-requirements | operator standing direction | F05781 | non-negotiable | false | 10 |
| R11710 | Closing — direct-to-main commits authorized | operator standing direction | F05865 | non-negotiable | false | 10 |
| R11711 | Closing — every commit signs via selfdef MS003 | cross-ref selfdef MS003 | F05819 | non-negotiable | false | 10 |
| R11712 | Closing — every commit emits M049 trace event | cross-ref M049 | F05818 | non-negotiable | false | 10 |
| R11713 | Closing — sovereignty preserved (peace machine axiom retained throughout CCD partitioning) | cross-ref M059 + operator standing direction | F05865 | non-negotiable | false | 10 |
| R11714 | Closing — boundary respected (CCD allocation = sovereign-os; selfdef reads only) | operator standing direction | F05860 | non-negotiable | false | 10 |
| R11715 | Closing — cross-repo binding only through MS007 8/8 SATURATED typed mirrors | cross-ref selfdef MS007 | F05836 | non-negotiable | false | 10 |
| R11716 | Closing — Trinity SRP mapping preserved (M066 narrative + M070 hardware enforcement) | cross-ref M066 + architecture | F05847 | non-negotiable | false | 10 |
| R11717 | Closing — Pulse Core never accidentally placed on CCD 1 | dump 1024 + architecture | F05848 | non-negotiable | false | 10 |
| R11718 | Closing — Weaver+Auditor never accidentally placed on CCD 0 | dump 1025 + architecture | F05848 | non-negotiable | false | 10 |
| R11719 | Closing — System Host never accidentally placed on CCD 0 | dump 1026 + architecture | F05848 | non-negotiable | false | 10 |
| R11720 | Closing — IRQ affinity violations emit OCSF Detection 2004 | cross-ref selfdef MS026 | F05831 | non-negotiable | false | 10 |
| R11721 | Closing — operator can override SRP mapping (signed override, retained 365 days) | cross-ref selfdef MS003 | F05815 | non-negotiable | false | 10 |
| R11722 | Closing — operator override emits OCSF Configuration Change 5001 | cross-ref selfdef MS026 | F05817 | non-negotiable | false | 10 |
| R11723 | Closing — operator override emits M049 trace | cross-ref M049 | F05818 | non-negotiable | false | 10 |
| R11724 | Closing — operator override requires explicit confirmation phrase | operator standing direction | F05816 | non-negotiable | false | 10 |
| R11725 | Closing — operator override historical record indelibly logged in MS009 audit chain | cross-ref selfdef MS009 | F05850 | non-negotiable | false | 10 |
| R11726 | Closing — CCD topology applies to Ryzen 9 9900X specifically (other CPUs require new mapping) | dump 1014 + architecture | F05781 | non-negotiable | false | 10 |
| R11727 | Closing — CCD topology mapping retained at /etc/sovereign-os/ccd-mapping-<cpu>.toml | architecture | F05815 | non-negotiable | false | 10 |
| R11728 | Closing — CCD mapping signed by hardware-validated identity (TPM-bound where available) | architecture + cross-ref selfdef MS003 | F05816 | non-negotiable | false | 10 |
| R11729 | Closing — operator words "you cannot invent crap" preserved (CCD mapping is hardware-fact-based, not invented) | operator standing direction + dump 1014-1026 | F05691 | non-negotiable | false | 10 |
| R11730 | Closing — M070 covers Dual-CCD scope verbatim; M071 Atomic State Transition Protocol next | dump 1013-1037 + operator standing direction | F05865 | non-negotiable | false | 10 |

## Sub-requirements accounting

Every R-row carries 10 hard non-negotiable sub-requirements. Total = 170 R × 10 = **1,700 sub-requirements** for M070.

## Cross-references

- **M044** — substrate (Ryzen 9 9900X hardware)
- **M045** — Linux as intelligence governor (cgroup v2 cpuset)
- **M048** — modules map (Compute Fabric)
- **M049** — observability + trace pipeline
- **M055** — failure modes (cross-CCD spike alert)
- **M057** — 12-step task lifecycle (Map step routes to CCD)
- **M058** — hardware-aware scheduler (CPU resource tracking)
- **M060** — cockpit + dashboards (D-03 + D-09)
- **M061** — canon-update (Scheduler-as-policy-layer canonical layering)
- **M063** — SFIF Infrastructure phase
- **M066** — Trinity Framework Genesis (SRP mapping)
- **M067** — Custom Kernel Build (kernel scheduler honors cpuset)
- **M068** — ZFS Storage Architecture (background compression on CCD 1 host)
- **M071** — Atomic State Transition Protocol (pending; Weaver thread on Core 12)
- **M073** — 1-bit ternary logic (pending; Pulse AVX-512 path)
- **M074** — AVX-512 VNNI fusion (pending)
- **M075** — SRP hardware topology mapping (pending; full SRP→hardware mapping)
- **M076** — 3 load-balancing profiles (pending)
- **selfdef MS003** — selfdef-signing
- **selfdef MS007** — typed-mirror crate scheme (sovereign-ccd-allocation-mirror)
- **selfdef MS009** — replay validator
- **selfdef MS026** — observability + OCSF event emission
- **selfdef MS037** — filesystem boundary (ZFS snapshot pre-allocation-change)
- **selfdef MS039** — authority levels + trust rings (CCD allocation = L6 Persist)
- **selfdef MS041** — commit authority (CCD allocation high-risk triple-gate)
- **selfdef MS043** — IPS operator surface (CLI integration)
- **selfdef MS044** — Guardian Daemon (process on Weaver+Auditor CCD 1 cores)

## Schema

```
schema_version: "1.0.0"
milestone_id: M070
parent: sovereign-os
epics: 10
modules: 17
features: 85
requirements: 170
sub_requirements_per_requirement: 10
total_sub_requirements: 1700
source_dump_lines: 1013-1037 (Section 19: Dual-CCD Cache Topology)
ccd_topology:
  ccd_0: { cores: 0-5, threads: 0-11, l3_cache: 32MB, layer: Pulse, mask: "0xfff" }
  ccd_1_part_a: { cores: 6-9, threads: 12-19, l3_cache: 32MB (shared), layer: WeaverAuditor, mask: "0xff000" }
  ccd_1_part_b: { cores: 10-11, threads: 20-23, l3_cache: 32MB (shared), layer: SystemHost, mask: "0xf00000" }
typed_mirror_crate: sovereign-ccd-allocation-mirror
catalog_status:
  sovereign_os: 69/69 milestones
  selfdef: 44/44 milestones
  combined: 113 milestones
```
