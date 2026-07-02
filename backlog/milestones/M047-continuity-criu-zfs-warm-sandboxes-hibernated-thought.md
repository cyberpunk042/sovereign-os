# M047 — Continuity — CRIU + ZFS + warm sandboxes + hibernated thought

> Parent: `backlog/milestones/INDEX.md` row M047 (dump 14107–14402).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 14107–14402. Operator directives 14107: "Great Great. continue. do resaerchs online too. Think of hyper features and continuity of what we are doing" + 14402: "Great Great. continue. do resaerchs online too. Think of every modules and features and configurations and continuity of what we are doing".
> All entries below extract verbatim. No invention.

## Epics (E0448–E0457)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0448 | Continuity doctrine — "Cloud agents are mostly request/response. Even when they have memory, their continuity is provider-shaped. Your station can have **machine-native continuity**"; 7 continuity types: process continuity / container continuity / workspace continuity / memory continuity / model continuity / workflow continuity / user-intent continuity; "That is how it gets better than the cloud before weight training" | 14124–14146 |
| E0449 | Hyper Feature: Checkpointed Agent Sessions — Linux CRIU (Checkpoint/Restore In Userspace); Podman integrates checkpoint/restore through CRIU letting containers be frozen and restored later; references podman.io/docs/checkpoint + criu.org/Checkpoint/Restore; "powerful for agent sandboxes"; concrete scenario — agent starts complex coding environment (dependencies installed + dev server warm + test DB seeded + browser logged into sandbox + model/tool process ready) → checkpoint; "every experiment starts from the warm checkpoint instead of rebuilding"; 6 capabilities: fast retries / branch experiments / safe rollback / session migration / forensics / reproducible agent state; caveat — "CRIU is not magic. GPU state, complex drivers, open network sockets, browsers, and some namespaces can be difficult. But for CPU/container sandboxes, build/test environments, and warmed tool sessions, it is worth testing" | 14150–14186 |
| E0450 | Hyper Feature: Semantic Checkpoints — recent work on semantics-aware checkpoint/restore for agent sandboxes (Crab — arxiv.org/abs/2604.28138); "raw process checkpoint is not enough. agent checkpoint needs semantic state"; checkpoint should include 10 fields: container/process state / filesystem snapshot / workflow node / branch state / open tool futures / memory refs / risk state / cost so far / expected next action / human gate state; "This is continuity with meaning" | 14190–14216 |
| E0451 | Hyper Feature: ZFS + CRIU Together — ZFS snapshots handle filesystem truth; CRIU handles process state; 5-layer save-state combination: ZFS snapshot (files + repo + caches + artifacts) + CRIU checkpoint (running process/container state) + Replay log (why the state exists) + Memory record (what was learned) + Profile state (what permissions and budgets apply); "That becomes a true agent save-state"; "Cloud providers rarely give you this level of continuity" | 14220–14242 |
| E0452 | Hyper Feature: Warm Sandboxes — cold-vs-warm comparison: cold (create container + install deps + start services + run tests) vs warm (restore checkpoint + apply patch + run tests); "For coding agents, this is huge"; branch-search pattern: restore baseline checkpoint → try patch A → measure → rollback → restore baseline → try patch B → measure; "This is test-time compute for software engineering" | 14246–14278 |
| E0453 | Hyper Feature: Hibernated Thought — "Agents should hibernate when waiting"; 6 wait conditions: waiting for user / waiting for long test / waiting for download / waiting for external event / low priority branch / memory pressure; runtime saves 5 fields: branch summary / state vector / tool futures / context refs / next wake condition; "free context/GPU resources"; "This is AgentRM-style resource management made local and sovereign" | 14282–14306 |
| E0454 | Systemd Continuity — systemd gives service lifecycle + watchdogs + resource limits + slices + scopes + pressure-aware OOM behavior; systemd-oomd uses cgroup v2 and PSI to react before kernel OOM (manpages.ubuntu.com/manpages/jammy/man8/systemd-oomd.8.html); Debian systemd docs also emphasize memory pressure handling through PSI; "model servers and agent sessions should be OS-managed"; 7 example unit names: gateway.service / oracle-blackwell.service / scout-4090.service / memory-os.service / agent-session@.service / sandbox@.scope / eval-worker.slice; "The OS can restart, limit, observe, or kill them" | 14310–14336 |
| E0455 | Hyper Feature: Userspace Soft Reboot — systemd added soft reboot — restart userspace without full hardware/kernel reboot; "not something to lean on blindly with GPUs, but conceptually relevant for Sovereign-OS"; sources systemd.io/PORTABLE_SERVICES + freedesktop.org/software/systemd/man/254/systemd-sysext.html; for AI station 4 capabilities: reload gateway/runtime userspace / keep kernel-hardware stable / restore model services / resume checkpoints; "This could support fast updates to the intelligence stack without rebooting the machine. But with NVIDIA/GPU services, test carefully" | 14340–14364 |
| E0456 | Continuity Layers — 8 levels: Level 0 stateless API call / Level 1 conversation memory / Level 2 workflow checkpoint / Level 3 filesystem snapshot / Level 4 process/container checkpoint / Level 5 warm model/KV context / Level 6 learned skill/profile/policy / Level 7 user-sovereign life continuity; "Cloud usually gives level 0-2. Your station can own level 3-7. That is a major advantage" | 14368–14394 |
| E0457 | How This Beats Cloud + Hyper Loop With Continuity + KEY LINE — cloud (powerful but distant + generic + metered + policy opaque) vs sovereign station (warm repo state + warm tests + warm model context + local memory + local snapshots + local user policy + reversible actions + continuous workflows); "For real work, continuity is intelligence"; "A model that remembers the exact test environment and can restore a previous working state is smarter in practice than a bigger model guessing from text"; Hyper Loop 11 steps: Map environment / Create checkpoint / Try action branch / Measure result / Restore if bad / Promote if good / Store trace / Update profile-memory / Keep warm context if useful / Hibernate if idle / Resume later; "This is not just automation. It is controlled experimentation"; KEY LINE: "Continuity turns inference into practice"; "A cloud model can answer. A sovereign station can keep working, pause, restore, compare, learn, and resume without losing the world" | 14366–14400 |

## Modules (M00782–M00798)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00782 | Continuity contrast — cloud=request/response provider-shaped vs station=machine-native | 14126–14130 | E0448 |
| M00783 | 7-type continuity taxonomy — process/container/workspace/memory/model/workflow/user-intent | 14134–14144 | E0448 |
| M00784 | CRIU primitive — Checkpoint/Restore In Userspace (Linux) | 14152 | E0449 |
| M00785 | Podman+CRIU integration — containers frozen and restored later | 14154 | E0449 |
| M00786 | Warm-checkpoint scenario — 5 warm-state ingredients (deps + dev server + test DB + browser + model-tool) | 14160–14166 | E0449 |
| M00787 | CRIU 6-capability roster — fast retries / branch experiments / safe rollback / session migration / forensics / reproducible agent state | 14172–14178 | E0449 |
| M00788 | CRIU caveat — GPU state + drivers + sockets + browsers + namespaces difficult | 14182–14186 | E0449 |
| M00789 | Semantic Checkpoint inclusion — 10-field semantic state (container-process state / filesystem snapshot / workflow node / branch state / open tool futures / memory refs / risk state / cost so far / expected next action / human gate state) | 14200–14214 | E0450 |
| M00790 | 5-layer save-state — ZFS snapshot + CRIU checkpoint + Replay log + Memory record + Profile state | 14224–14238 | E0451 |
| M00791 | Branch-search pattern — restore baseline + try A + measure + rollback + try B + measure | 14264–14274 | E0452 |
| M00792 | Hibernated-thought trigger — 6 wait conditions (user / long test / download / external event / low priority branch / memory pressure) | 14286–14296 | E0453 |
| M00793 | Hibernated-thought state save — 5 fields (branch summary / state vector / tool futures / context refs / next wake condition) | 14298–14304 | E0453 |
| M00794 | systemd-oomd — cgroup v2 + PSI reacts before kernel OOM | 14316 | E0454 |
| M00795 | Systemd 7-unit example — gateway / oracle-blackwell / scout-4090 / memory-os / agent-session@ / sandbox@ / eval-worker | 14326–14334 | E0454 |
| M00796 | Soft reboot — restart userspace without full hardware/kernel reboot | 14342–14344 | E0455 |
| M00797 | 8-level continuity ladder — Level 0 stateless → Level 7 user-sovereign life | 14372–14388 | E0456 |
| M00798 | 11-step Hyper Loop With Continuity — Map → Checkpoint → Try → Measure → Restore/Promote → Store → Update → Warm-keep → Hibernate → Resume | 14380–14398 | E0457 |

## Features (F03911–F03995)

| Feature ID | Phrase | Dump line | Parent module |
|---|---|---|---|
| F03911 | Continuity becomes the next hyper feature | 14122 | E0448 |
| F03912 | Cloud — request/response model | 14126 | M00782 |
| F03913 | Cloud — "continuity is provider-shaped" even with memory | 14128 | M00782 |
| F03914 | Station — "machine-native continuity" | 14130 | M00782 |
| F03915 | Continuity type — process | 14134 | M00783 |
| F03916 | Continuity type — container | 14135 | M00783 |
| F03917 | Continuity type — workspace | 14136 | M00783 |
| F03918 | Continuity type — memory | 14137 | M00783 |
| F03919 | Continuity type — model | 14138 | M00783 |
| F03920 | Continuity type — workflow | 14139 | M00783 |
| F03921 | Continuity type — user-intent | 14140 | M00783 |
| F03922 | "That is how it gets better than the cloud before weight training" | 14146 | E0448 |
| F03923 | Hyper feature header — Checkpointed Agent Sessions | 14150 | E0449 |
| F03924 | Linux has CRIU — Checkpoint/Restore In Userspace | 14152 | M00784 |
| F03925 | Podman integrates checkpoint/restore through CRIU | 14154 | M00785 |
| F03926 | Podman — containers can be frozen and restored later | 14154 | M00785 |
| F03927 | Podman checkpoint URL — podman.io/docs/checkpoint | 14155 | M00785 |
| F03928 | CRIU URL — criu.org/Checkpoint/Restore | 14155 | M00784 |
| F03929 | "That is powerful for agent sandboxes" | 14157 | E0449 |
| F03930 | Warm scenario — agent starts complex coding environment | 14160 | M00786 |
| F03931 | Warm scenario — dependencies installed | 14161 | M00786 |
| F03932 | Warm scenario — dev server warm | 14162 | M00786 |
| F03933 | Warm scenario — test DB seeded | 14163 | M00786 |
| F03934 | Warm scenario — browser logged into sandbox | 14164 | M00786 |
| F03935 | Warm scenario — model/tool process ready | 14165 | M00786 |
| F03936 | Warm scenario — checkpoint | 14166 | M00786 |
| F03937 | "Every experiment starts from the warm checkpoint instead of rebuilding" | 14170 | E0449 |
| F03938 | Capability — fast retries | 14172 | M00787 |
| F03939 | Capability — branch experiments | 14173 | M00787 |
| F03940 | Capability — safe rollback | 14174 | M00787 |
| F03941 | Capability — session migration | 14175 | M00787 |
| F03942 | Capability — forensics | 14176 | M00787 |
| F03943 | Capability — reproducible agent state | 14177 | M00787 |
| F03944 | Caveat — "CRIU is not magic" | 14182 | M00788 |
| F03945 | Caveat — GPU state difficult | 14182 | M00788 |
| F03946 | Caveat — complex drivers difficult | 14182 | M00788 |
| F03947 | Caveat — open network sockets difficult | 14183 | M00788 |
| F03948 | Caveat — browsers difficult | 14183 | M00788 |
| F03949 | Caveat — some namespaces difficult | 14183 | M00788 |
| F03950 | Caveat — CPU/container sandboxes worth testing | 14185 | E0449 |
| F03951 | Caveat — build/test environments worth testing | 14185 | E0449 |
| F03952 | Caveat — warmed tool sessions worth testing | 14186 | E0449 |
| F03953 | Hyper feature header — Semantic Checkpoints | 14190 | E0450 |
| F03954 | Crab — semantics-aware checkpoint/restore for agent sandboxes | 14192 | E0450 |
| F03955 | Crab URL — arxiv.org/abs/2604.28138 | 14193 | E0450 |
| F03956 | Doctrine — "raw process checkpoint is not enough" | 14198 | E0450 |
| F03957 | Doctrine — "agent checkpoint needs semantic state" | 14199 | E0450 |
| F03958 | Semantic state — container/process state | 14204 | M00789 |
| F03959 | Semantic state — filesystem snapshot | 14205 | M00789 |
| F03960 | Semantic state — workflow node | 14206 | M00789 |
| F03961 | Semantic state — branch state | 14207 | M00789 |
| F03962 | Semantic state — open tool futures | 14208 | M00789 |
| F03963 | Semantic state — memory refs | 14209 | M00789 |
| F03964 | Semantic state — risk state | 14210 | M00789 |
| F03965 | Semantic state — cost so far | 14211 | M00789 |
| F03966 | Semantic state — expected next action | 14212 | M00789 |
| F03967 | Semantic state — human gate state | 14213 | M00789 |
| F03968 | "This is continuity with meaning" | 14216 | E0450 |
| F03969 | Hyper feature header — ZFS + CRIU Together | 14220 | E0451 |
| F03970 | "ZFS snapshots handle filesystem truth" | 14222 | M00790 |
| F03971 | "CRIU handles process state" | 14222 | M00790 |
| F03972 | Layer 1 — ZFS snapshot: files, repo, caches, artifacts | 14228 | M00790 |
| F03973 | Layer 2 — CRIU checkpoint: running process/container state | 14230 | M00790 |
| F03974 | Layer 3 — Replay log: why the state exists | 14232 | M00790 |
| F03975 | Layer 4 — Memory record: what was learned | 14234 | M00790 |
| F03976 | Layer 5 — Profile state: what permissions and budgets apply | 14236 | M00790 |
| F03977 | "That becomes a true agent save-state" | 14238 | E0451 |
| F03978 | "Cloud providers rarely give you this level of continuity" | 14242 | E0451 |
| F03979 | Hyper feature header — Warm Sandboxes | 14246 | E0452 |
| F03980 | Cold pattern — create + install deps + start services + run tests | 14250–14256 | E0452 |
| F03981 | Warm pattern — restore checkpoint + apply patch + run tests | 14258–14262 | E0452 |
| F03982 | "For coding agents, this is huge" | 14264 | E0452 |
| F03983 | Branch-search — restore baseline checkpoint | 14266 | M00791 |
| F03984 | Branch-search — try patch A | 14267 | M00791 |
| F03985 | Branch-search — measure | 14268 | M00791 |
| F03986 | Branch-search — rollback | 14269 | M00791 |
| F03987 | Branch-search — restore baseline | 14270 | M00791 |
| F03988 | Branch-search — try patch B | 14271 | M00791 |
| F03989 | Branch-search — measure | 14272 | M00791 |
| F03990 | "This is test-time compute for software engineering" | 14278 | E0452 |
| F03991 | Hyper feature header — Hibernated Thought | 14282 | E0453 |
| F03992 | Hibernate doctrine — "Agents should hibernate when waiting" | 14284 | E0453 |
| F03993 | Hibernate condition — waiting for user | 14286 | M00792 |
| F03994 | Hibernate condition — waiting for long test | 14287 | M00792 |
| F03995 | Hibernate state-save 5 fields + systemd-oomd + 7 systemd-unit examples + soft-reboot 4 capabilities + 8-level continuity ladder + 11-step hyper-loop + KEY LINE "Continuity turns inference into practice" | 14288–14400 | M00793 + E0454 + E0455 + M00796 + M00797 + M00798 + E0457 |

## Requirements (R07821–R07990)

| Req ID | Phrase | Dump line | Parent feature | Negotiability | Layer-B metric | Priority |
|---|---|---|---|---|---|---|
| R07821 | "Continuity becomes the next hyper feature" | 14122 | F03911 | non-negotiable | false | 10 |
| R07822 | Cloud — "mostly request/response" | 14126 | F03912 | non-negotiable | false | 10 |
| R07823 | Cloud — "even when they have memory, their continuity is provider-shaped" | 14128 | F03913 | non-negotiable | false | 10 |
| R07824 | Station — "machine-native continuity" | 14130 | F03914 | non-negotiable | false | 10 |
| R07825 | Continuity type — process | 14134 | F03915 | non-negotiable | false | 10 |
| R07826 | Continuity type — container | 14135 | F03916 | non-negotiable | false | 10 |
| R07827 | Continuity type — workspace | 14136 | F03917 | non-negotiable | false | 10 |
| R07828 | Continuity type — memory | 14137 | F03918 | non-negotiable | false | 10 |
| R07829 | Continuity type — model | 14138 | F03919 | non-negotiable | false | 10 |
| R07830 | Continuity type — workflow | 14139 | F03920 | non-negotiable | false | 10 |
| R07831 | Continuity type — user-intent | 14140 | F03921 | non-negotiable | false | 10 |
| R07832 | "That is how it gets better than the cloud before weight training" | 14146 | F03922 | non-negotiable | false | 10 |
| R07833 | Hyper feature label — Checkpointed Agent Sessions | 14150 | E0449 | non-negotiable | false | 10 |
| R07834 | Linux primitive — CRIU Checkpoint/Restore In Userspace | 14152 | F03924 | non-negotiable | false | 10 |
| R07835 | Podman — integrates checkpoint/restore through CRIU | 14154 | F03925 | non-negotiable | false | 10 |
| R07836 | Podman — containers can be frozen and restored later | 14154 | F03926 | non-negotiable | false | 10 |
| R07837 | Podman checkpoint URL — podman.io/docs/checkpoint | 14155 | F03927 | non-negotiable | false | 10 |
| R07838 | CRIU URL — criu.org/Checkpoint/Restore | 14155 | F03928 | non-negotiable | false | 10 |
| R07839 | "That is powerful for agent sandboxes" | 14157 | F03929 | non-negotiable | false | 10 |
| R07840 | Warm scenario — agent starts complex coding environment | 14160 | F03930 | non-negotiable | false | 10 |
| R07841 | Warm scenario — dependencies installed | 14161 | F03931 | non-negotiable | false | 10 |
| R07842 | Warm scenario — dev server warm | 14162 | F03932 | non-negotiable | false | 10 |
| R07843 | Warm scenario — test DB seeded | 14163 | F03933 | non-negotiable | false | 10 |
| R07844 | Warm scenario — browser logged into sandbox | 14164 | F03934 | non-negotiable | false | 10 |
| R07845 | Warm scenario — model/tool process ready | 14165 | F03935 | non-negotiable | false | 10 |
| R07846 | Warm scenario — checkpoint as terminating action | 14166 | F03936 | non-negotiable | false | 10 |
| R07847 | "Every experiment starts from the warm checkpoint instead of rebuilding" | 14170 | F03937 | non-negotiable | false | 10 |
| R07848 | Capability — fast retries | 14172 | F03938 | non-negotiable | false | 10 |
| R07849 | Capability — branch experiments | 14173 | F03939 | non-negotiable | false | 10 |
| R07850 | Capability — safe rollback | 14174 | F03940 | non-negotiable | false | 10 |
| R07851 | Capability — session migration | 14175 | F03941 | non-negotiable | false | 10 |
| R07852 | Capability — forensics | 14176 | F03942 | non-negotiable | false | 10 |
| R07853 | Capability — reproducible agent state | 14177 | F03943 | non-negotiable | false | 10 |
| R07854 | Caveat — "CRIU is not magic" | 14182 | F03944 | non-negotiable | false | 10 |
| R07855 | Caveat — GPU state difficult | 14182 | F03945 | non-negotiable | false | 10 |
| R07856 | Caveat — complex drivers difficult | 14182 | F03946 | non-negotiable | false | 10 |
| R07857 | Caveat — open network sockets difficult | 14183 | F03947 | non-negotiable | false | 10 |
| R07858 | Caveat — browsers difficult | 14183 | F03948 | non-negotiable | false | 10 |
| R07859 | Caveat — some namespaces difficult | 14183 | F03949 | non-negotiable | false | 10 |
| R07860 | CRIU coverage — CPU/container sandboxes worth testing | 14185 | F03950 | non-negotiable | false | 10 |
| R07861 | CRIU coverage — build/test environments worth testing | 14185 | F03951 | non-negotiable | false | 10 |
| R07862 | CRIU coverage — warmed tool sessions worth testing | 14186 | F03952 | non-negotiable | false | 10 |
| R07863 | Hyper feature label — Semantic Checkpoints | 14190 | E0450 | non-negotiable | false | 10 |
| R07864 | Crab — semantics-aware checkpoint/restore for agent sandboxes | 14192 | F03954 | non-negotiable | false | 10 |
| R07865 | Crab URL — arxiv.org/abs/2604.28138 | 14193 | F03955 | non-negotiable | false | 10 |
| R07866 | Doctrine — "raw process checkpoint is not enough" | 14198 | F03956 | non-negotiable | false | 10 |
| R07867 | Doctrine — "agent checkpoint needs semantic state" | 14199 | F03957 | non-negotiable | false | 10 |
| R07868 | Semantic state — container/process state | 14204 | F03958 | non-negotiable | false | 10 |
| R07869 | Semantic state — filesystem snapshot | 14205 | F03959 | non-negotiable | false | 10 |
| R07870 | Semantic state — workflow node | 14206 | F03960 | non-negotiable | false | 10 |
| R07871 | Semantic state — branch state | 14207 | F03961 | non-negotiable | false | 10 |
| R07872 | Semantic state — open tool futures | 14208 | F03962 | non-negotiable | false | 10 |
| R07873 | Semantic state — memory refs | 14209 | F03963 | non-negotiable | false | 10 |
| R07874 | Semantic state — risk state | 14210 | F03964 | non-negotiable | false | 10 |
| R07875 | Semantic state — cost so far | 14211 | F03965 | non-negotiable | false | 10 |
| R07876 | Semantic state — expected next action | 14212 | F03966 | non-negotiable | false | 10 |
| R07877 | Semantic state — human gate state | 14213 | F03967 | non-negotiable | false | 10 |
| R07878 | "This is continuity with meaning" | 14216 | F03968 | non-negotiable | false | 10 |
| R07879 | Hyper feature label — ZFS + CRIU Together | 14220 | E0451 | non-negotiable | false | 10 |
| R07880 | "ZFS snapshots handle filesystem truth" | 14222 | F03970 | non-negotiable | false | 10 |
| R07881 | "CRIU handles process state" | 14222 | F03971 | non-negotiable | false | 10 |
| R07882 | Save-state layer — ZFS snapshot: files, repo, caches, artifacts | 14228 | F03972 | non-negotiable | false | 10 |
| R07883 | Save-state layer — CRIU checkpoint: running process/container state | 14230 | F03973 | non-negotiable | false | 10 |
| R07884 | Save-state layer — Replay log: why the state exists | 14232 | F03974 | non-negotiable | false | 10 |
| R07885 | Save-state layer — Memory record: what was learned | 14234 | F03975 | non-negotiable | false | 10 |
| R07886 | Save-state layer — Profile state: what permissions and budgets apply | 14236 | F03976 | non-negotiable | false | 10 |
| R07887 | "That becomes a true agent save-state" | 14238 | F03977 | non-negotiable | false | 10 |
| R07888 | "Cloud providers rarely give you this level of continuity" | 14242 | F03978 | non-negotiable | false | 10 |
| R07889 | Hyper feature label — Warm Sandboxes | 14246 | E0452 | non-negotiable | false | 10 |
| R07890 | Cold pattern — create container | 14250 | F03980 | non-negotiable | false | 10 |
| R07891 | Cold pattern — install deps | 14251 | F03980 | non-negotiable | false | 10 |
| R07892 | Cold pattern — start services | 14252 | F03980 | non-negotiable | false | 10 |
| R07893 | Cold pattern — run tests | 14253 | F03980 | non-negotiable | false | 10 |
| R07894 | Warm pattern — restore checkpoint | 14258 | F03981 | non-negotiable | false | 10 |
| R07895 | Warm pattern — apply patch | 14259 | F03981 | non-negotiable | false | 10 |
| R07896 | Warm pattern — run tests | 14260 | F03981 | non-negotiable | false | 10 |
| R07897 | "For coding agents, this is huge" | 14264 | F03982 | non-negotiable | false | 10 |
| R07898 | Branch-search — restore baseline checkpoint | 14266 | F03983 | non-negotiable | false | 10 |
| R07899 | Branch-search — try patch A | 14267 | F03984 | non-negotiable | false | 10 |
| R07900 | Branch-search — measure | 14268 | F03985 | non-negotiable | false | 10 |
| R07901 | Branch-search — rollback | 14269 | F03986 | non-negotiable | false | 10 |
| R07902 | Branch-search — restore baseline (second time) | 14270 | F03987 | non-negotiable | false | 10 |
| R07903 | Branch-search — try patch B | 14271 | F03988 | non-negotiable | false | 10 |
| R07904 | Branch-search — measure (second time) | 14272 | F03989 | non-negotiable | false | 10 |
| R07905 | "This is test-time compute for software engineering" | 14278 | F03990 | non-negotiable | false | 10 |
| R07906 | Hyper feature label — Hibernated Thought | 14282 | E0453 | non-negotiable | false | 10 |
| R07907 | Doctrine — "Agents should hibernate when waiting" | 14284 | F03992 | non-negotiable | false | 10 |
| R07908 | Hibernate condition — waiting for user | 14286 | F03993 | non-negotiable | false | 10 |
| R07909 | Hibernate condition — waiting for long test | 14287 | F03994 | non-negotiable | false | 10 |
| R07910 | Hibernate condition — waiting for download | 14288 | M00792 | non-negotiable | false | 10 |
| R07911 | Hibernate condition — waiting for external event | 14289 | M00792 | non-negotiable | false | 10 |
| R07912 | Hibernate condition — low priority branch | 14290 | M00792 | non-negotiable | false | 10 |
| R07913 | Hibernate condition — memory pressure | 14291 | M00792 | non-negotiable | false | 10 |
| R07914 | Hibernate state save — branch summary | 14298 | M00793 | non-negotiable | false | 10 |
| R07915 | Hibernate state save — state vector | 14299 | M00793 | non-negotiable | false | 10 |
| R07916 | Hibernate state save — tool futures | 14300 | M00793 | non-negotiable | false | 10 |
| R07917 | Hibernate state save — context refs | 14301 | M00793 | non-negotiable | false | 10 |
| R07918 | Hibernate state save — next wake condition | 14302 | M00793 | non-negotiable | false | 10 |
| R07919 | "Free context/GPU resources" | 14304 | E0453 | non-negotiable | false | 10 |
| R07920 | "This is AgentRM-style resource management made local and sovereign" | 14306 | E0453 | non-negotiable | false | 10 |
| R07921 | Systemd Continuity header | 14310 | E0454 | non-negotiable | false | 10 |
| R07922 | systemd provides — service lifecycle | 14312 | E0454 | non-negotiable | false | 10 |
| R07923 | systemd provides — watchdogs | 14312 | E0454 | non-negotiable | false | 10 |
| R07924 | systemd provides — resource limits | 14312 | E0454 | non-negotiable | false | 10 |
| R07925 | systemd provides — slices | 14313 | E0454 | non-negotiable | false | 10 |
| R07926 | systemd provides — scopes | 14313 | E0454 | non-negotiable | false | 10 |
| R07927 | systemd provides — pressure-aware OOM behavior | 14314 | E0454 | non-negotiable | false | 10 |
| R07928 | systemd-oomd — uses cgroup v2 and PSI | 14316 | M00794 | non-negotiable | false | 10 |
| R07929 | systemd-oomd — reacts before kernel OOM | 14316 | M00794 | non-negotiable | false | 10 |
| R07930 | systemd-oomd URL — manpages.ubuntu.com/manpages/jammy/man8/systemd-oomd.8.html | 14318 | M00794 | non-negotiable | false | 10 |
| R07931 | "Debian systemd docs also emphasize memory pressure handling through PSI" | 14320 | E0454 | non-negotiable | false | 10 |
| R07932 | Doctrine — "model servers and agent sessions should be OS-managed" | 14324 | E0454 | non-negotiable | false | 10 |
| R07933 | Unit example — gateway.service | 14328 | M00795 | non-negotiable | false | 10 |
| R07934 | Unit example — oracle-blackwell.service | 14329 | M00795 | non-negotiable | false | 10 |
| R07935 | Unit example — scout-4090.service | 14330 | M00795 | non-negotiable | false | 10 |
| R07936 | Unit example — memory-os.service | 14331 | M00795 | non-negotiable | false | 10 |
| R07937 | Unit example — agent-session@.service | 14332 | M00795 | non-negotiable | false | 10 |
| R07938 | Unit example — sandbox@.scope | 14333 | M00795 | non-negotiable | false | 10 |
| R07939 | Unit example — eval-worker.slice | 14334 | M00795 | non-negotiable | false | 10 |
| R07940 | "The OS can restart, limit, observe, or kill them" | 14336 | E0454 | non-negotiable | false | 10 |
| R07941 | Hyper feature label — Userspace Soft Reboot | 14340 | E0455 | non-negotiable | false | 10 |
| R07942 | systemd — added soft reboot | 14342 | M00796 | non-negotiable | false | 10 |
| R07943 | Soft reboot — restart userspace without full hardware/kernel reboot | 14344 | M00796 | non-negotiable | false | 10 |
| R07944 | Caveat — "not something to lean on blindly with GPUs" | 14346 | E0455 | non-negotiable | false | 10 |
| R07945 | "It is conceptually relevant for Sovereign-OS" | 14348 | E0455 | non-negotiable | false | 10 |
| R07946 | systemd portable services URL — systemd.io/PORTABLE_SERVICES | 14350 | E0455 | non-negotiable | false | 10 |
| R07947 | systemd-sysext URL — freedesktop.org/software/systemd/man/254/systemd-sysext.html | 14350 | E0455 | non-negotiable | false | 10 |
| R07948 | Soft-reboot capability — reload gateway/runtime userspace | 14356 | E0455 | non-negotiable | false | 10 |
| R07949 | Soft-reboot capability — keep kernel/hardware stable | 14358 | E0455 | non-negotiable | false | 10 |
| R07950 | Soft-reboot capability — restore model services | 14360 | E0455 | non-negotiable | false | 10 |
| R07951 | Soft-reboot capability — resume checkpoints | 14362 | E0455 | non-negotiable | false | 10 |
| R07952 | "This could support fast updates to the intelligence stack without rebooting the machine" | 14364 | E0455 | non-negotiable | false | 10 |
| R07953 | "But with NVIDIA/GPU services, test carefully" | 14364 | E0455 | non-negotiable | false | 10 |
| R07954 | Continuity Layers header | 14368 | E0456 | non-negotiable | false | 10 |
| R07955 | Level 0 — stateless API call | 14372 | M00797 | non-negotiable | false | 10 |
| R07956 | Level 1 — conversation memory | 14374 | M00797 | non-negotiable | false | 10 |
| R07957 | Level 2 — workflow checkpoint | 14376 | M00797 | non-negotiable | false | 10 |
| R07958 | Level 3 — filesystem snapshot | 14378 | M00797 | non-negotiable | false | 10 |
| R07959 | Level 4 — process/container checkpoint | 14380 | M00797 | non-negotiable | false | 10 |
| R07960 | Level 5 — warm model/KV context | 14382 | M00797 | non-negotiable | false | 10 |
| R07961 | Level 6 — learned skill/profile/policy | 14384 | M00797 | non-negotiable | false | 10 |
| R07962 | Level 7 — user-sovereign life continuity | 14386 | M00797 | non-negotiable | false | 10 |
| R07963 | "Cloud usually gives level 0-2" | 14390 | E0456 | non-negotiable | false | 10 |
| R07964 | "Your station can own level 3-7" | 14392 | E0456 | non-negotiable | false | 10 |
| R07965 | "That is a major advantage" | 14394 | E0456 | non-negotiable | false | 10 |
| R07966 | Cloud properties — powerful but distant | 14366 | E0457 | non-negotiable | false | 10 |
| R07967 | Cloud properties — generic | 14366 | E0457 | non-negotiable | false | 10 |
| R07968 | Cloud properties — metered | 14366 | E0457 | non-negotiable | false | 10 |
| R07969 | Cloud properties — policy opaque | 14366 | E0457 | non-negotiable | false | 10 |
| R07970 | Sovereign station — warm repo state | 14368 | E0457 | non-negotiable | false | 10 |
| R07971 | Sovereign station — warm tests | 14369 | E0457 | non-negotiable | false | 10 |
| R07972 | Sovereign station — warm model context | 14370 | E0457 | non-negotiable | false | 10 |
| R07973 | Sovereign station — local memory | 14371 | E0457 | non-negotiable | false | 10 |
| R07974 | Sovereign station — local snapshots | 14372 | E0457 | non-negotiable | false | 10 |
| R07975 | Sovereign station — local user policy | 14373 | E0457 | non-negotiable | false | 10 |
| R07976 | Sovereign station — reversible actions | 14374 | E0457 | non-negotiable | false | 10 |
| R07977 | Sovereign station — continuous workflows | 14375 | E0457 | non-negotiable | false | 10 |
| R07978 | "For real work, continuity is intelligence" | 14377 | E0457 | non-negotiable | false | 10 |
| R07979 | Argument — "A model that remembers the exact test environment and can restore a previous working state is smarter in practice than a bigger model guessing from text" | 14378 | E0457 | non-negotiable | false | 10 |
| R07980 | Hyper Loop — Map environment | 14380 | M00798 | non-negotiable | false | 10 |
| R07981 | Hyper Loop — Create checkpoint | 14381 | M00798 | non-negotiable | false | 10 |
| R07982 | Hyper Loop — Try action branch | 14382 | M00798 | non-negotiable | false | 10 |
| R07983 | Hyper Loop — Measure result | 14383 | M00798 | non-negotiable | false | 10 |
| R07984 | Hyper Loop — Restore if bad | 14384 | M00798 | non-negotiable | false | 10 |
| R07985 | Hyper Loop — Promote if good | 14385 | M00798 | non-negotiable | false | 10 |
| R07986 | Hyper Loop — Store trace + Update profile/memory + Keep warm context if useful + Hibernate if idle + Resume later | 14386–14390 | M00798 | non-negotiable | false | 10 |
| R07987 | "This is not just automation. It is controlled experimentation" | 14392 | E0457 | non-negotiable | false | 10 |
| R07988 | KEY LINE — "Continuity turns inference into practice" | 14396 | E0457 | non-negotiable | false | 10 |
| R07989 | KEY LINE — "A cloud model can answer. A sovereign station can keep working, pause, restore, compare, learn, and resume without losing the world" | 14398–14400 | E0457 | non-negotiable | false | 10 |
| R07990 | Composite — M047 (10 epics / 17 modules / 85 features / 170 reqs) catalogs continuity hyper features: 7-type continuity taxonomy + Checkpointed Agent Sessions (CRIU + Podman + 6 capabilities + 5 caveats + 3 coverage areas) + Semantic Checkpoints (Crab arxiv 2604.28138 + 10-field semantic state + "continuity with meaning") + ZFS + CRIU Together (5-layer save-state) + Warm Sandboxes (cold-vs-warm + branch-search pattern + "test-time compute for software engineering") + Hibernated Thought (6 wait conditions + 5-field state save + "AgentRM-style resource management made local and sovereign") + Systemd Continuity (systemd-oomd + cgroup v2 + PSI + 7 unit examples) + Userspace Soft Reboot (4 capabilities + GPU caveat) + 8-level continuity ladder (cloud=0-2 / station=3-7) + 11-step Hyper Loop with continuity + KEY LINE "Continuity turns inference into practice" + "A cloud model can answer. A sovereign station can keep working, pause, restore, compare, learn, and resume without losing the world" | 14107–14402 | E0448-E0457 | non-negotiable | false | 10 |

## Sub-requirements accounting

- 170 requirements covering: continuity contrast + 7-type taxonomy (R07821–R07832) + CRIU + Podman + URL anchors + warm scenario + 6 capabilities + caveats + coverage (R07833–R07862) + Semantic Checkpoints + Crab + 10-field state (R07863–R07878) + ZFS + CRIU 5-layer save-state (R07879–R07888) + Warm Sandboxes + cold-vs-warm + branch-search (R07889–R07905) + Hibernated Thought + 6 conditions + 5-field state save + AgentRM (R07906–R07920) + Systemd Continuity + systemd-oomd + 7 units (R07921–R07940) + Userspace Soft Reboot + 4 capabilities + GPU caveat (R07941–R07953) + 8-level continuity ladder + cloud-vs-station (R07954–R07965) + cloud-vs-station-property comparison (R07966–R07979) + 11-step Hyper Loop + key lines (R07980–R07989) + composite (R07990)
- Source range 14107–14402 yields 295 lines; 170 R-rows represent ~58% line-coverage at the verbatim-citation level
- Project boundary — M047 is sovereign-os continuity scope; selfdef IPS-side may consume CRIU checkpoint primitives via MS017 agent-guard for sandbox lifecycle; cross-repo binding via MS007 typed-mirror crates

## Cross-references

- Adjacent dump-range milestones: M046 Beat the cloud — runtime adaptation + LoRA foundry (13825–14107) / M048 Modules — Base OS + Compute Fabric + ... (next; dump 14402–14812)
- Plane integration — M047 sits on M044 Sovereign-OS substrate (8-plane: Kernel + Security + Compute + Storage + Sandbox + Gateway + Observability + Choice); refines Storage Plane (ZFS snapshots) + Sandbox Plane (CRIU + Podman + warm sandboxes) + Kernel Plane (systemd lifecycle) + Observability Plane (replay log)
- M045 — Linux as intelligence governor — systemd-oomd + cgroup v2 + PSI integrate with M047 systemd Continuity (model servers + agent sessions as OS-managed units)
- M042 Choice Architecture — Profile state (M047 layer 5 of 5-layer save-state) realizes M042 8 inheritance artifacts (PROFILES.yaml + POLICY.yaml)
- M043 Bridge layer hardware-aware intelligence scheduling — Hibernated Thought triggers (memory pressure) directly use M043 PSI/DCGM pressure signals
- M046 LoRA foundry — Keep warm context if useful + Update profile/memory steps of Hyper Loop feed M046's 6-stage adaptation progression Stage 1 (prompt/profile) + Stage 2 (memory/retrieval) before Stage 4 LoRA crystallization
- Selfdef integration — selfdef MS017 agent-guard 2 profiles + 2 scope strategies can consume CRIU checkpoint primitive for sandbox lifecycle management; MS016 eBPF (Tetragon TracingPolicies) can observe checkpoint/restore events; MS026 integrity-sentinel can baseline checkpoint files
- AgentRM — explicit reference to "AgentRM-style resource management made local and sovereign"; M047 is the local-sovereign realization of the AgentRM idea
- Operator references: podman.io/docs/checkpoint + criu.org/Checkpoint/Restore + arxiv.org/abs/2604.28138 Crab + manpages.ubuntu.com/manpages/jammy/man8/systemd-oomd.8.html + systemd.io/PORTABLE_SERVICES + freedesktop.org/software/systemd/man/254/systemd-sysext.html + CRIU checkpoint restore Linux containers documentation 2026 + systemd soft reboot soft-reboot userspace reboot documentation (web searches)
