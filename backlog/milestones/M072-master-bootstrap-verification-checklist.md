# M072 — Master Bootstrap Verification Checklist (6-phase operational grid)

**Parent**: sovereign-os runtime — pre-deployment validation gate
**Source**: `~/infohub/raw/dumps/2026-05-15-sain-01-master-spec-other-conversation-transposition.md` lines 1091-1100 (Section 22: The Master Bootstrap Verification Checklist)

## Doctrinal anchors

> "Before passing command execution over to your active development workflows, the downstream agent must pass this mandatory operational grid. If any check reports an anomaly, the node enters lock-state until manually cleared by the Architect." (dump 1091-1093)

## Epics (E0688-E0697)

| epic | name | source |
|---|---|---|
| E0688 | Check 01 — Microcode/ISA: avx512_vnni + avx512_bf16 present in /proc/cpuinfo | dump 1095 |
| E0689 | Check 02 — Bus Geometry: dual PCIe slots at Link Speed Gen 4/5 x8 | dump 1096 |
| E0690 | Check 03 — Linux Memory: ZFS ARC restricted to 137438953472 bytes (128GB) | dump 1097 |
| E0691 | Check 04 — Driver Fabric: NVIDIA 560+ open kernel modules operating | dump 1098 |
| E0692 | Check 05 — Security Core: Tetragon local UNIX socket active + streaming | dump 1099 |
| E0693 | Check 06 — Network Line: interface enp5s0 operational at jumbo MTU 9000 | dump 1100 |
| E0694 | Lock-state behavior — node enters lock-state on any anomaly | dump 1093 |
| E0695 | Manual clear — only Architect (operator) can clear lock-state | dump 1093 |
| E0696 | Pre-execution gate — checklist runs before workflows handed over | dump 1091 |
| E0697 | Integration with SFIF + Stage Gates — checklist gates Infrastructure → Features transition | cross-ref M063 + M065 |

## Modules (M01190-M01206)

| module | name | source |
|---|---|---|
| M01190 | sovereign-bootstrap-check-01-microcode-isa | dump 1095 |
| M01191 | sovereign-bootstrap-check-02-bus-geometry | dump 1096 |
| M01192 | sovereign-bootstrap-check-03-zfs-arc-bound | dump 1097 |
| M01193 | sovereign-bootstrap-check-04-nvidia-driver | dump 1098 |
| M01194 | sovereign-bootstrap-check-05-tetragon-socket | dump 1099 |
| M01195 | sovereign-bootstrap-check-06-network-mtu | dump 1100 |
| M01196 | sovereign-bootstrap-checklist-runner | dump 1091-1100 |
| M01197 | sovereign-bootstrap-anomaly-detector | dump 1093 |
| M01198 | sovereign-bootstrap-lock-state-coordinator | dump 1093 |
| M01199 | sovereign-bootstrap-manual-clear-coordinator | dump 1093 |
| M01200 | sovereign-bootstrap-check-result-reporter | architecture |
| M01201 | sovereign-bootstrap-typed-mirror | cross-ref selfdef MS007 |
| M01202 | sovereign-bootstrap-event-emitter | cross-ref M049 + selfdef MS026 |
| M01203 | sovereign-bootstrap-replay-validator | cross-ref selfdef MS009 |
| M01204 | sovereign-bootstrap-dashboard-binding (D-00 main + D-03 model health) | cross-ref M060 |
| M01205 | sovereign-bootstrap-cli-subcommand-set | cross-ref selfdef MS043 |
| M01206 | sovereign-bootstrap-sfif-stage-gate-bridge | cross-ref M063 + M065 |

## Features (F05951-F06035)

| feature | name | source |
|---|---|---|
| F05951 | Doctrinal — mandatory operational grid before workflow handover | dump 1091 |
| F05952 | Doctrinal — anomaly triggers node lock-state | dump 1093 |
| F05953 | Doctrinal — only Architect (operator) can manually clear | dump 1093 |
| F05954 | Check 01 — target subsystem: Microcode / ISA | dump 1095 |
| F05955 | Check 01 — intended state: avx512_vnni present in /proc/cpuinfo | dump 1095 |
| F05956 | Check 01 — intended state: avx512_bf16 present in /proc/cpuinfo | dump 1095 |
| F05957 | Check 01 — invocation: `grep --color=always -E "avx512_vnni \| avx512_bf16" /proc/cpuinfo` | dump 1095 |
| F05958 | Check 01 — failure: AVX-512 instruction subset missing → lock-state | dump 1095 + 1093 |
| F05959 | Check 02 — target subsystem: Bus Geometry | dump 1096 |
| F05960 | Check 02 — intended state: dual slots running at Link Speed Gen 4/5 x8 | dump 1096 |
| F05961 | Check 02 — invocation: `lspci -vvv \| grep -i "LnkSta: Speed"` | dump 1096 |
| F05962 | Check 02 — failure: lane bifurcation incorrect → lock-state | dump 1096 + architecture |
| F05963 | Check 02 — composes with M044 ProArt X870E-Creator dual GPU x8/x8 mode | cross-ref M044 |
| F05964 | Check 03 — target subsystem: Linux Memory | dump 1097 |
| F05965 | Check 03 — intended state: ZFS ARC restricted to 137438953472 bytes (128GB) | dump 1097 |
| F05966 | Check 03 — invocation: `arcstat -s c` | dump 1097 |
| F05967 | Check 03 — failure: ARC larger than 128GB risks starving model workloads | architecture + dump 1097 |
| F05968 | Check 03 — composes with M068 ZFS storage architecture | cross-ref M068 |
| F05969 | Check 04 — target subsystem: Driver Fabric | dump 1098 |
| F05970 | Check 04 — intended state: NVIDIA 560+ open kernel modules operating | dump 1098 |
| F05971 | Check 04 — invocation: `modinfo nvidia \| grep -i "license"` | dump 1098 |
| F05972 | Check 04 — verifies GPU driver license + version | dump 1098 |
| F05973 | Check 04 — failure: NVIDIA driver missing OR proprietary-only → lock-state | architecture |
| F05974 | Check 05 — target subsystem: Security Core | dump 1099 |
| F05975 | Check 05 — intended state: Tetragon local UNIX socket active + streaming | dump 1099 |
| F05976 | Check 05 — invocation: `ls -la /var/run/tetragon/tetragon.events` | dump 1099 |
| F05977 | Check 05 — composes with selfdef MS044 Guardian Daemon | cross-ref selfdef MS044 |
| F05978 | Check 05 — failure: Tetragon socket missing → lock-state (no Guardian = no security) | architecture |
| F05979 | Check 06 — target subsystem: Network Line | dump 1100 |
| F05980 | Check 06 — intended state: interface enp5s0 operational at jumbo MTU 9000 | dump 1100 |
| F05981 | Check 06 — invocation: `ip link show enp5s0 \| grep -i "mtu 9000"` | dump 1100 |
| F05982 | Check 06 — interface enp5s0 = Marvell 10GbE network lane per dump 707 + M044 | cross-ref M044 + dump 707 |
| F05983 | Check 06 — composes with selfdef MS038 network boundary | cross-ref selfdef MS038 |
| F05984 | Lock-state — node enters lock-state on ANY check anomaly | dump 1093 |
| F05985 | Lock-state — sovereign-os runtime refuses to start workflows | architecture |
| F05986 | Lock-state — D-00 main dashboard shows lock-state banner (red) | cross-ref M060 |
| F05987 | Lock-state — emits OCSF Detection 2004 + M049 trace | cross-ref selfdef MS026 + M049 |
| F05988 | Lock-state — Guardian Daemon continues running (security never disabled) | cross-ref selfdef MS044 |
| F05989 | Manual clear — operator runs `sovereign bootstrap clear --rationale <text>` | architecture + cross-ref selfdef MS043 |
| F05990 | Manual clear — requires operator MS003 signature | cross-ref selfdef MS003 |
| F05991 | Manual clear — clear emits OCSF Configuration Change 5001 + M049 trace | cross-ref selfdef MS026 + M049 |
| F05992 | Manual clear — clear retained 365 days in /var/lib/sovereign-os/bootstrap-clears/ | architecture |
| F05993 | Manual clear — clear may include override to bypass specific check (signed override) | architecture + cross-ref selfdef MS003 |
| F05994 | Pre-execution gate — checklist runs at boot | architecture |
| F05995 | Pre-execution gate — checklist runs before workflow handover | dump 1091 |
| F05996 | Pre-execution gate — checklist runs on systemd ConditionPathExists for /run/sovereign-os/bootstrap-clear | architecture |
| F05997 | Pre-execution gate — composes with SFIF Infrastructure → Features transition gate | cross-ref M063 + M065 |
| F05998 | Pre-execution gate — passes/fails recorded per phase | architecture |
| F05999 | Result reporter — JSON output of all 6 check results | architecture |
| F06000 | Result reporter — signed via MS003 | cross-ref selfdef MS003 |
| F06001 | Result reporter — stored at /var/lib/sovereign-os/bootstrap-results/<ts>.json | architecture |
| F06002 | Result reporter — retained 365 days | cross-ref selfdef MS037 |
| F06003 | Result reporter — D-00 main dashboard surfaces last result | cross-ref M060 |
| F06004 | Typed mirror — sovereign-bootstrap-checklist-mirror crate under MS007 8/8 SATURATED | cross-ref selfdef MS007 |
| F06005 | Typed mirror — BootstrapCheck struct {phase, target_subsystem, intended_state, invocation, result, ts, signature} | cross-ref selfdef MS007 |
| F06006 | Typed mirror — CheckPhase enum (Microcode / BusGeometry / LinuxMemory / DriverFabric / SecurityCore / NetworkLine) | cross-ref selfdef MS007 |
| F06007 | Typed mirror — CheckResult enum (Pass / Fail / Skipped / OperatorOverride) | cross-ref selfdef MS007 |
| F06008 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 |
| F06009 | Typed mirror — signed via MS003 | cross-ref selfdef MS003 |
| F06010 | Event emitter — every check run emits M049 13-field trace span | cross-ref M049 |
| F06011 | Event emitter — every check pass emits OCSF System Activity 1001 | cross-ref selfdef MS026 |
| F06012 | Event emitter — every check fail emits OCSF Detection 2004 | cross-ref selfdef MS026 |
| F06013 | Event emitter — every operator override emits OCSF Configuration Change 5001 | cross-ref selfdef MS026 |
| F06014 | Replay validator — verifies historical bootstrap chain integrity | cross-ref selfdef MS009 |
| F06015 | Replay validator — detects missing checks | cross-ref selfdef MS009 + MS003 |
| F06016 | Replay validator — emits OCSF Detection 2004 on chain break | cross-ref selfdef MS026 |
| F06017 | Replay validator — runs daily as systemd timer | cross-ref selfdef MS009 |
| F06018 | Dashboard — D-00 main shows last bootstrap result (pass/fail per phase) | cross-ref M060 |
| F06019 | Dashboard — D-03 model health shows AVX-512 instruction presence (Check 01) | cross-ref M060 |
| F06020 | Dashboard — D-09 hardware pressure shows MTU + bus geometry | cross-ref M060 |
| F06021 | Dashboard — D-19 super-model manifest shows last successful bootstrap timestamp | cross-ref M060 |
| F06022 | CLI — `sovereign bootstrap run` runs all 6 checks | architecture + cross-ref selfdef MS043 |
| F06023 | CLI — `sovereign bootstrap check <phase>` runs specific check | architecture |
| F06024 | CLI — `sovereign bootstrap status` returns last result | architecture |
| F06025 | CLI — `sovereign bootstrap clear --rationale <text>` clears lock-state | architecture + cross-ref selfdef MS003 |
| F06026 | CLI — `sovereign bootstrap override <phase> --rationale <text>` bypasses specific check | architecture + cross-ref selfdef MS003 |
| F06027 | CLI — all bootstrap subcommands emit M049 trace | cross-ref M049 |
| F06028 | CLI — all bootstrap subcommands signed via MS003 (when mutating) | cross-ref selfdef MS003 |
| F06029 | SFIF bridge — bootstrap success required for SFIF Infrastructure → Features transition | cross-ref M063 |
| F06030 | SFIF bridge — Stage Gate 5 (foundation-complete) verification includes bootstrap pass | cross-ref M065 + M063 |
| F06031 | Composition — composes with M067 kernel build (Check 01 verifies kernel AVX-512 flags) | cross-ref M067 |
| F06032 | Composition — composes with M068 ZFS (Check 03 verifies ARC bound) | cross-ref M068 |
| F06033 | Composition — composes with selfdef MS044 Guardian Daemon (Check 05 verifies Tetragon) | cross-ref selfdef MS044 |
| F06034 | Composition — composes with selfdef MS038 network boundary (Check 06 verifies MTU) | cross-ref selfdef MS038 |
| F06035 | Closing — M072 covers dump 1091-1100 verbatim 6-phase bootstrap checklist scope | dump 1091-1100 |

## Requirements (R11901-R12070)

| req | description | source | feature | priority | exception | sub-reqs |
|---|---|---|---|---|---|---|
| R11901 | Doctrinal — mandatory operational grid before workflow handover | dump 1091 | F05951 | non-negotiable | false | 10 |
| R11902 | Doctrinal — "If any check reports an anomaly, the node enters lock-state until manually cleared by the Architect" | dump 1093 | F05952 | non-negotiable | false | 10 |
| R11903 | Doctrinal — only Architect (operator) can manually clear | dump 1093 | F05953 | non-negotiable | false | 10 |
| R11904 | Doctrinal — 6 check phases verbatim from dump | dump 1095-1100 | F05951 | non-negotiable | false | 10 |
| R11905 | Doctrinal — 4-column table preserved verbatim (Check Phase / Target Subsystem / Intended State / Verification Invocation) | dump 1094 | F05951 | non-negotiable | false | 10 |
| R11906 | Check 01 — target subsystem: Microcode / ISA | dump 1095 | F05954 | non-negotiable | false | 10 |
| R11907 | Check 01 — avx512_vnni present in /proc/cpuinfo | dump 1095 | F05955 | non-negotiable | false | 10 |
| R11908 | Check 01 — avx512_bf16 present in /proc/cpuinfo | dump 1095 | F05956 | non-negotiable | false | 10 |
| R11909 | Check 01 — invocation `grep --color=always -E "avx512_vnni \| avx512_bf16" /proc/cpuinfo` | dump 1095 | F05957 | non-negotiable | false | 10 |
| R11910 | Check 01 — failure triggers lock-state | dump 1095 + 1093 | F05958 | non-negotiable | false | 10 |
| R11911 | Check 01 — composes with M067 kernel build AVX-512 flag set | cross-ref M067 | F06031 | non-negotiable | false | 10 |
| R11912 | Check 02 — target subsystem: Bus Geometry | dump 1096 | F05959 | non-negotiable | false | 10 |
| R11913 | Check 02 — dual slots running at Link Speed Gen 4/5 x8 | dump 1096 | F05960 | non-negotiable | false | 10 |
| R11914 | Check 02 — invocation `lspci -vvv \| grep -i "LnkSta: Speed"` | dump 1096 | F05961 | non-negotiable | false | 10 |
| R11915 | Check 02 — failure triggers lock-state | dump 1096 + 1093 | F05962 | non-negotiable | false | 10 |
| R11916 | Check 02 — composes with M044 ProArt X870E-Creator dual GPU x8/x8 | cross-ref M044 | F05963 | non-negotiable | false | 10 |
| R11917 | Check 03 — target subsystem: Linux Memory | dump 1097 | F05964 | non-negotiable | false | 10 |
| R11918 | Check 03 — ZFS ARC restricted to 137438953472 bytes (128GB) | dump 1097 | F05965 | non-negotiable | false | 10 |
| R11919 | Check 03 — invocation `arcstat -s c` | dump 1097 | F05966 | non-negotiable | false | 10 |
| R11920 | Check 03 — failure triggers lock-state | dump 1097 + 1093 | F05967 | non-negotiable | false | 10 |
| R11921 | Check 03 — composes with M068 ZFS storage architecture | cross-ref M068 | F06032 | non-negotiable | false | 10 |
| R11922 | Check 03 — 128GB = half of 256GB system RAM (M044 substrate) | architecture + cross-ref M044 | F05965 | non-negotiable | false | 10 |
| R11923 | Check 04 — target subsystem: Driver Fabric | dump 1098 | F05969 | non-negotiable | false | 10 |
| R11924 | Check 04 — NVIDIA 560+ open kernel modules operating | dump 1098 | F05970 | non-negotiable | false | 10 |
| R11925 | Check 04 — invocation `modinfo nvidia \| grep -i "license"` | dump 1098 | F05971 | non-negotiable | false | 10 |
| R11926 | Check 04 — verifies driver license + version | dump 1098 | F05972 | non-negotiable | false | 10 |
| R11927 | Check 04 — failure triggers lock-state (no GPU = no oracle) | dump 1098 + 1093 | F05973 | non-negotiable | false | 10 |
| R11928 | Check 05 — target subsystem: Security Core | dump 1099 | F05974 | non-negotiable | false | 10 |
| R11929 | Check 05 — Tetragon local UNIX socket active + streaming | dump 1099 | F05975 | non-negotiable | false | 10 |
| R11930 | Check 05 — invocation `ls -la /var/run/tetragon/tetragon.events` | dump 1099 | F05976 | non-negotiable | false | 10 |
| R11931 | Check 05 — failure triggers lock-state | dump 1099 + 1093 | F05978 | non-negotiable | false | 10 |
| R11932 | Check 05 — composes with selfdef MS044 Guardian Daemon | cross-ref selfdef MS044 | F05977 | non-negotiable | false | 10 |
| R11933 | Check 06 — target subsystem: Network Line | dump 1100 | F05979 | non-negotiable | false | 10 |
| R11934 | Check 06 — interface enp5s0 operational at jumbo MTU 9000 | dump 1100 | F05980 | non-negotiable | false | 10 |
| R11935 | Check 06 — invocation `ip link show enp5s0 \| grep -i "mtu 9000"` | dump 1100 | F05981 | non-negotiable | false | 10 |
| R11936 | Check 06 — failure triggers lock-state | dump 1100 + 1093 | F05979 | non-negotiable | false | 10 |
| R11937 | Check 06 — enp5s0 = Marvell 10GbE network lane | cross-ref M044 + dump 707 | F05982 | non-negotiable | false | 10 |
| R11938 | Check 06 — composes with selfdef MS038 network boundary | cross-ref selfdef MS038 | F05983 | non-negotiable | false | 10 |
| R11939 | Lock-state — node enters lock-state on ANY check anomaly | dump 1093 | F05984 | non-negotiable | false | 10 |
| R11940 | Lock-state — sovereign-os runtime refuses to start workflows | architecture | F05985 | non-negotiable | false | 10 |
| R11941 | Lock-state — D-00 main dashboard shows lock-state banner (red) | cross-ref M060 | F05986 | non-negotiable | false | 10 |
| R11942 | Lock-state — emits OCSF Detection 2004 | cross-ref selfdef MS026 | F05987 | non-negotiable | false | 10 |
| R11943 | Lock-state — emits M049 trace | cross-ref M049 | F05987 | non-negotiable | false | 10 |
| R11944 | Lock-state — Guardian Daemon continues running (security never disabled) | cross-ref selfdef MS044 | F05988 | non-negotiable | false | 10 |
| R11945 | Lock-state — selfdef IPS continues running (boundary enforcement never disabled) | operator standing direction | F05988 | non-negotiable | false | 10 |
| R11946 | Manual clear — operator runs `sovereign bootstrap clear --rationale <text>` | architecture | F05989 | non-negotiable | false | 10 |
| R11947 | Manual clear — requires operator MS003 signature | cross-ref selfdef MS003 | F05990 | non-negotiable | false | 10 |
| R11948 | Manual clear — emits OCSF Configuration Change 5001 | cross-ref selfdef MS026 | F05991 | non-negotiable | false | 10 |
| R11949 | Manual clear — emits M049 trace | cross-ref M049 | F05991 | non-negotiable | false | 10 |
| R11950 | Manual clear — retained 365 days | architecture | F05992 | non-negotiable | false | 10 |
| R11951 | Manual clear — clear may include override for specific check | architecture + cross-ref selfdef MS003 | F05993 | non-negotiable | false | 10 |
| R11952 | Manual clear — operator override emits separate OCSF Detection 2004 (logged anomaly) | cross-ref selfdef MS026 | F05993 | non-negotiable | false | 10 |
| R11953 | Manual clear — override TTL operator-specified (default 24h) | architecture + cross-ref selfdef MS038 | F05993 | non-negotiable | false | 10 |
| R11954 | Manual clear — override expiration re-triggers check | architecture | F05993 | non-negotiable | false | 10 |
| R11955 | Pre-execution — checklist runs at boot via systemd unit | architecture | F05994 | non-negotiable | false | 10 |
| R11956 | Pre-execution — checklist runs before workflow handover | dump 1091 | F05995 | non-negotiable | false | 10 |
| R11957 | Pre-execution — checklist gated on ConditionPathExists /run/sovereign-os/bootstrap-clear | architecture | F05996 | non-negotiable | false | 10 |
| R11958 | Pre-execution — composes with SFIF Infrastructure → Features transition | cross-ref M063 | F05997 | non-negotiable | false | 10 |
| R11959 | Pre-execution — composes with M065 Stage Gate 5 verification | cross-ref M065 | F06030 | non-negotiable | false | 10 |
| R11960 | Pre-execution — per-phase pass/fail recorded | architecture | F05998 | non-negotiable | false | 10 |
| R11961 | Result — JSON output of all 6 check results | architecture | F05999 | non-negotiable | false | 10 |
| R11962 | Result — signed via MS003 | cross-ref selfdef MS003 | F06000 | non-negotiable | false | 10 |
| R11963 | Result — stored at /var/lib/sovereign-os/bootstrap-results/<ts>.json | architecture | F06001 | non-negotiable | false | 10 |
| R11964 | Result — retained 365 days | cross-ref selfdef MS037 | F06002 | non-negotiable | false | 10 |
| R11965 | Result — D-00 main dashboard surfaces last result | cross-ref M060 | F06003 | non-negotiable | false | 10 |
| R11966 | Result — historical results queryable via `sovereign bootstrap history` | architecture | F06001 | non-negotiable | false | 10 |
| R11967 | Result — historical results indexed by timestamp + phase + result | architecture | F06001 | non-negotiable | false | 10 |
| R11968 | Result — failed results trigger operator notification (toast in D-00 / D-06 dashboards) | cross-ref M060 | F05986 | non-negotiable | false | 10 |
| R11969 | Result — failed results emit M049 metric (high-priority alert) | cross-ref M049 | F05987 | non-negotiable | false | 10 |
| R11970 | Result — historical results contribute to long-term reproducibility audit | cross-ref selfdef MS009 | F06014 | non-negotiable | false | 10 |
| R11971 | Typed mirror — sovereign-bootstrap-checklist-mirror under MS007 8/8 SATURATED | cross-ref selfdef MS007 | F06004 | non-negotiable | false | 10 |
| R11972 | Typed mirror — BootstrapCheck struct fields | cross-ref selfdef MS007 | F06005 | non-negotiable | false | 10 |
| R11973 | Typed mirror — CheckPhase enum 6 variants | cross-ref selfdef MS007 | F06006 | non-negotiable | false | 10 |
| R11974 | Typed mirror — CheckResult enum 4 variants | cross-ref selfdef MS007 | F06007 | non-negotiable | false | 10 |
| R11975 | Typed mirror — schema_version "1.0.0" | cross-ref selfdef MS007 | F06008 | non-negotiable | false | 10 |
| R11976 | Typed mirror — signed via MS003 | cross-ref selfdef MS003 | F06009 | non-negotiable | false | 10 |
| R11977 | Typed mirror — re-exported via sovereign-os cargo workspace | cross-ref selfdef MS007 | F06004 | non-negotiable | false | 10 |
| R11978 | Typed mirror — no_std friendly | architecture | F06004 | non-negotiable | false | 10 |
| R11979 | Typed mirror — serde + bincode derives present | architecture | F06004 | non-negotiable | false | 10 |
| R11980 | Typed mirror — schema-breaking changes require schema_version bump | architecture + cross-ref selfdef MS007 | F06008 | non-negotiable | false | 10 |
| R11981 | Event — every check run emits M049 13-field trace span | cross-ref M049 | F06010 | non-negotiable | false | 10 |
| R11982 | Event — every check pass emits OCSF System Activity 1001 | cross-ref selfdef MS026 | F06011 | non-negotiable | false | 10 |
| R11983 | Event — every check fail emits OCSF Detection 2004 | cross-ref selfdef MS026 | F06012 | non-negotiable | false | 10 |
| R11984 | Event — every operator override emits OCSF Configuration Change 5001 | cross-ref selfdef MS026 | F06013 | non-negotiable | false | 10 |
| R11985 | Event — span deterministic for MS009 replay | cross-ref selfdef MS009 | F06010 | non-negotiable | false | 10 |
| R11986 | Replay — verifies historical bootstrap chain integrity | cross-ref selfdef MS009 | F06014 | non-negotiable | false | 10 |
| R11987 | Replay — detects missing checks | cross-ref selfdef MS009 + MS003 | F06015 | non-negotiable | false | 10 |
| R11988 | Replay — emits OCSF Detection 2004 on chain break | cross-ref selfdef MS026 | F06016 | non-negotiable | false | 10 |
| R11989 | Replay — runs daily as systemd timer | cross-ref selfdef MS009 | F06017 | non-negotiable | false | 10 |
| R11990 | Replay — failures halt new bootstrap clears until resolved | architecture | F06014 | non-negotiable | false | 10 |
| R11991 | Dashboard — D-00 main shows last bootstrap result | cross-ref M060 | F06018 | non-negotiable | false | 10 |
| R11992 | Dashboard — D-03 model health shows AVX-512 instruction presence | cross-ref M060 | F06019 | non-negotiable | false | 10 |
| R11993 | Dashboard — D-09 hardware pressure shows MTU + bus geometry | cross-ref M060 | F06020 | non-negotiable | false | 10 |
| R11994 | Dashboard — D-19 super-model manifest shows last successful bootstrap timestamp | cross-ref M060 | F06021 | non-negotiable | false | 10 |
| R11995 | CLI — `sovereign bootstrap run` runs all 6 checks | architecture + cross-ref selfdef MS043 | F06022 | non-negotiable | false | 10 |
| R11996 | CLI — `sovereign bootstrap check <phase>` runs specific check | architecture | F06023 | non-negotiable | false | 10 |
| R11997 | CLI — `sovereign bootstrap status` returns last result | architecture | F06024 | non-negotiable | false | 10 |
| R11998 | CLI — `sovereign bootstrap clear --rationale <text>` clears lock-state | architecture + cross-ref selfdef MS003 | F06025 | non-negotiable | false | 10 |
| R11999 | CLI — `sovereign bootstrap override <phase> --rationale <text>` bypasses specific check | architecture + cross-ref selfdef MS003 | F06026 | non-negotiable | false | 10 |
| R12000 | CLI — all bootstrap subcommands emit M049 trace | cross-ref M049 | F06027 | non-negotiable | false | 10 |
| R12001 | CLI — all mutating bootstrap subcommands signed via MS003 | cross-ref selfdef MS003 | F06028 | non-negotiable | false | 10 |
| R12002 | CLI — `sovereign bootstrap history` returns prior results | architecture | F06001 | non-negotiable | false | 10 |
| R12003 | CLI — `--json` flag returns structured output | architecture | F06024 | non-negotiable | false | 10 |
| R12004 | CLI — exit codes follow sysexits.h | architecture | F06022 | non-negotiable | false | 10 |
| R12005 | SFIF — bootstrap success required for SFIF Infrastructure → Features transition | cross-ref M063 | F06029 | non-negotiable | false | 10 |
| R12006 | SFIF — Stage Gate 5 includes bootstrap pass verification | cross-ref M065 + M063 | F06030 | non-negotiable | false | 10 |
| R12007 | SFIF — bootstrap fail blocks SFIF transition until cleared | cross-ref M063 + dump 1093 | F05984 | non-negotiable | false | 10 |
| R12008 | SFIF — bootstrap pass recorded in docs/decisions.md per L6 Persist | cross-ref selfdef MS039 + M062 dump 99 | F06000 | non-negotiable | false | 10 |
| R12009 | SFIF — bootstrap fail records do NOT block SFIF retrospective | architecture | F06014 | non-negotiable | false | 10 |
| R12010 | Composition — composes with M067 kernel build (Check 01) | cross-ref M067 | F06031 | non-negotiable | false | 10 |
| R12011 | Composition — composes with M068 ZFS (Check 03) | cross-ref M068 | F06032 | non-negotiable | false | 10 |
| R12012 | Composition — composes with selfdef MS044 Guardian Daemon (Check 05) | cross-ref selfdef MS044 | F06033 | non-negotiable | false | 10 |
| R12013 | Composition — composes with selfdef MS038 network boundary (Check 06) | cross-ref selfdef MS038 | F06034 | non-negotiable | false | 10 |
| R12014 | Composition — composes with M044 substrate (Checks 01 + 02 hardware-anchored) | cross-ref M044 | F05963 | non-negotiable | false | 10 |
| R12015 | Composition — composes with M058 hardware-aware scheduler (Check 03 ZFS ARC constrains memory) | cross-ref M058 | F05965 | non-negotiable | false | 10 |
| R12016 | Composition — composes with M060 cockpit dashboards (D-00 / D-03 / D-09 / D-19) | cross-ref M060 | F06018 | non-negotiable | false | 10 |
| R12017 | Composition — composes with M062 PR 9 TDD harness (test layer 1 schema-lint validates checklist YAML) | cross-ref M062 | F06022 | non-negotiable | false | 10 |
| R12018 | Composition — composes with M065 Five Stage Gates | cross-ref M065 | F06030 | non-negotiable | false | 10 |
| R12019 | Composition — composes with M070 Dual-CCD (post-bootstrap workload routing) | cross-ref M070 | F06022 | non-negotiable | false | 10 |
| R12020 | Composition — composes with M071 Atomic State (post-bootstrap atomic writes) | cross-ref M071 | F05997 | non-negotiable | false | 10 |
| R12021 | Performance — full 6-check runtime `<` 5s p95 | architecture | F06022 | non-negotiable | false | 10 |
| R12022 | Performance — per-check runtime `<` 1s p95 | architecture | F06023 | non-negotiable | false | 10 |
| R12023 | Performance — `sovereign bootstrap status` runtime `<` 50ms p95 | architecture | F06024 | non-negotiable | false | 10 |
| R12024 | Performance — typed-mirror publication latency `<` 100ms p95 | cross-ref selfdef MS007 | F06004 | non-negotiable | false | 10 |
| R12025 | Performance — replay validator daily run `<` 30s on 365-day chain | cross-ref selfdef MS009 | F06014 | non-negotiable | false | 10 |
| R12026 | Telemetry — check pass-rate per phase emitted via M049 | cross-ref M049 | F06010 | non-negotiable | false | 10 |
| R12027 | Telemetry — check failure root-cause distribution emitted via M049 | cross-ref M049 + M055 | F06012 | non-negotiable | false | 10 |
| R12028 | Telemetry — lock-state duration histograms emitted via M049 | cross-ref M049 | F05984 | non-negotiable | false | 10 |
| R12029 | Telemetry — operator override count emitted via M049 (high-priority alert) | cross-ref M049 | F06013 | non-negotiable | false | 10 |
| R12030 | Telemetry — bootstrap pass rate over 30/90/365 days emitted via M049 | cross-ref M049 | F06017 | non-negotiable | false | 10 |
| R12031 | Operational — checklist runner runs as systemd unit sovereign-bootstrap.service | architecture | F05994 | non-negotiable | false | 10 |
| R12032 | Operational — runner honors SIGHUP for re-run | architecture | F06023 | non-negotiable | false | 10 |
| R12033 | Operational — runner refuses to start with chain-break detected | cross-ref selfdef MS009 | F06014 | non-negotiable | false | 10 |
| R12034 | Operational — runner refuses to start with missing MS003 keys | cross-ref selfdef MS003 | F06000 | non-negotiable | false | 10 |
| R12035 | Operational — runner graceful drain on shutdown | architecture | F05994 | non-negotiable | false | 10 |
| R12036 | Operational — runner readiness probe at /run/sovereign-bootstrap/ready | architecture | F05994 | non-negotiable | false | 10 |
| R12037 | Operational — runner emits start/stop events via M049 | cross-ref M049 | F05994 | non-negotiable | false | 10 |
| R12038 | Operational — runner integrates with systemd ordering (After=tetragon.service / Wants=sovereign-os.target) | architecture + cross-ref selfdef MS044 | F05996 | non-negotiable | false | 10 |
| R12039 | Operational — runner exit code 1 on any check fail | architecture + dump 1093 | F05984 | non-negotiable | false | 10 |
| R12040 | Operational — runner exit code 0 on all 6 checks pass | architecture | F05984 | non-negotiable | false | 10 |
| R12041 | Doctrinal preservation — `avx512_vnni` verbatim | dump 1095 | F05955 | non-negotiable | false | 10 |
| R12042 | Doctrinal preservation — `avx512_bf16` verbatim | dump 1095 | F05956 | non-negotiable | false | 10 |
| R12043 | Doctrinal preservation — `137438953472` byte count verbatim | dump 1097 | F05965 | non-negotiable | false | 10 |
| R12044 | Doctrinal preservation — `enp5s0` interface name verbatim | dump 1100 | F05980 | non-negotiable | false | 10 |
| R12045 | Doctrinal preservation — `MTU 9000` verbatim | dump 1100 | F05980 | non-negotiable | false | 10 |
| R12046 | Doctrinal preservation — `/var/run/tetragon/tetragon.events` path verbatim | dump 1099 | F05975 | non-negotiable | false | 10 |
| R12047 | Doctrinal preservation — operator override may NOT bypass Check 05 (security never optional) | architecture + operator standing direction | F05988 | non-negotiable | false | 10 |
| R12048 | Doctrinal preservation — verbatim quotes never paraphrased | operator standing direction | F06035 | non-negotiable | false | 10 |
| R12049 | Doctrinal preservation — info-hub indexes bootstrap checklist as second-brain entry | operator standing direction "second-brain" | F06035 | non-negotiable | false | 10 |
| R12050 | Boundary — bootstrap = sovereign-os runtime responsibility | architecture + operator standing direction | F05951 | non-negotiable | false | 10 |
| R12051 | Boundary — selfdef IPS consumes bootstrap state via MS007 mirror (read-only) | cross-ref selfdef MS007 | F06004 | non-negotiable | false | 10 |
| R12052 | Boundary — Check 05 confirms selfdef-side Tetragon socket (cross-boundary verification) | dump 1099 + cross-ref selfdef MS044 | F05977 | non-negotiable | false | 10 |
| R12053 | Boundary — bootstrap result NEVER overrides selfdef state | operator standing direction | F06051 | non-negotiable | false | 10 |
| R12054 | Boundary — info-hub knowledge layer surfaces bootstrap results as read-only entries | operator standing direction "second-brain" | F06049 | non-negotiable | false | 10 |
| R12055 | Closing — 6 checks cover dump 1094-1100 verbatim | dump 1094-1100 | F05951 | non-negotiable | false | 10 |
| R12056 | Closing — lock-state mechanic covers dump 1093 verbatim | dump 1093 | F05984 | non-negotiable | false | 10 |
| R12057 | Closing — manual clear by Architect covers dump 1093 verbatim | dump 1093 | F05989 | non-negotiable | false | 10 |
| R12058 | Closing — sovereign-os catalog at 71/71 milestones | architecture | F06035 | non-negotiable | false | 10 |
| R12059 | Closing — combined ecosystem 115 milestones | architecture | F06035 | non-negotiable | false | 10 |
| R12060 | Closing — combined R-rows ~22630 | architecture | F06035 | non-negotiable | false | 10 |
| R12061 | Closing — combined enforced sub-reqs ~226300 | architecture | F06035 | non-negotiable | false | 10 |
| R12062 | Closing — every R-row carries 10 hard non-negotiable sub-requirements | operator standing direction | F05951 | non-negotiable | false | 10 |
| R12063 | Closing — direct-to-main commits authorized | operator standing direction | F06035 | non-negotiable | false | 10 |
| R12064 | Closing — every commit signs via selfdef MS003 | cross-ref selfdef MS003 | F06000 | non-negotiable | false | 10 |
| R12065 | Closing — every commit emits M049 trace event | cross-ref M049 | F06010 | non-negotiable | false | 10 |
| R12066 | Closing — sovereignty preserved (peace machine axiom retained throughout bootstrap) | cross-ref M059 + operator standing direction | F06035 | non-negotiable | false | 10 |
| R12067 | Closing — Architect-only clear preserves operator authority | dump 1093 + operator standing direction | F05953 | non-negotiable | false | 10 |
| R12068 | Closing — cross-repo binding only through MS007 8/8 SATURATED typed mirrors | cross-ref selfdef MS007 | F06004 | non-negotiable | false | 10 |
| R12069 | Closing — bootstrap composes the full ecosystem (hardware + kernel + ZFS + GPU + security + network) into single gate | architecture + dump 1091-1100 | F05951 | non-negotiable | false | 10 |
| R12070 | Closing — M072 covers bootstrap checklist scope verbatim; M073 1-bit ternary logic next | dump 1091-1100 + operator standing direction | F06035 | non-negotiable | false | 10 |

## Sub-requirements accounting

Every R-row carries 10 hard non-negotiable sub-requirements. Total = 170 R × 10 = **1,700 sub-requirements** for M072.

## Cross-references

- **M044** — substrate (Checks 01 + 02 + 06 hardware-anchored)
- **M048** — modules map
- **M049** — observability + trace pipeline
- **M055** — failure modes
- **M058** — hardware-aware scheduler
- **M060** — cockpit + dashboards (D-00 / D-03 / D-09 / D-19)
- **M062** — Macro-Arc PR 9 TDD harness
- **M063** — SFIF Infrastructure → Features gate
- **M065** — Five Stage Gates (SG5 includes bootstrap)
- **M067** — Custom Kernel Build (Check 01 AVX-512 flags)
- **M068** — ZFS Storage (Check 03 ARC bound)
- **M070** — Dual-CCD topology (post-bootstrap workload)
- **M071** — Atomic State (post-bootstrap writes)
- **selfdef MS003** — selfdef-signing
- **selfdef MS007** — typed-mirror crate scheme (sovereign-bootstrap-checklist-mirror)
- **selfdef MS009** — replay validator
- **selfdef MS026** — observability + OCSF event emission
- **selfdef MS037** — filesystem boundary
- **selfdef MS038** — network boundary (Check 06 MTU)
- **selfdef MS039** — authority levels
- **selfdef MS043** — IPS operator surface (CLI integration)
- **selfdef MS044** — Guardian Daemon (Check 05 Tetragon socket)

## Schema

```
schema_version: "1.0.0"
milestone_id: M072
parent: sovereign-os
epics: 10
modules: 17
features: 85
requirements: 170
sub_requirements_per_requirement: 10
total_sub_requirements: 1700
source_dump_lines: 1091-1100 (Section 22: Master Bootstrap Verification Checklist)
six_checks:
  - check_01: { subsystem: "Microcode/ISA", state: "avx512_vnni + avx512_bf16 present", invocation: "grep -E 'avx512_vnni|avx512_bf16' /proc/cpuinfo" }
  - check_02: { subsystem: "Bus Geometry", state: "Dual Slots Gen 4/5 x8", invocation: "lspci -vvv | grep 'LnkSta: Speed'" }
  - check_03: { subsystem: "Linux Memory", state: "ZFS ARC <= 137438953472 bytes", invocation: "arcstat -s c" }
  - check_04: { subsystem: "Driver Fabric", state: "NVIDIA 560+ open kernel modules", invocation: "modinfo nvidia | grep license" }
  - check_05: { subsystem: "Security Core", state: "Tetragon socket active", invocation: "ls -la /var/run/tetragon/tetragon.events" }
  - check_06: { subsystem: "Network Line", state: "enp5s0 MTU 9000", invocation: "ip link show enp5s0 | grep 'mtu 9000'" }
anomaly_behavior: "node enters lock-state until manually cleared by Architect"
typed_mirror_crate: sovereign-bootstrap-checklist-mirror
catalog_status:
  sovereign_os: 71/71 milestones
  selfdef: 44/44 milestones
  combined: 115 milestones
```
