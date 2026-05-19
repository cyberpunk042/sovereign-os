# M055 — Failure modes — 10 taxonomies with detect / contain / explain / recover / learn

> Parent: `backlog/milestones/INDEX.md` row M055 (dump 16896–17215).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 16896–17215. Operator directive 16896: "continue" + closing 17215: "continue".
> All entries below extract verbatim. No invention.

## Epics (E0528–E0537)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0528 | Failure architecture framing — "Next layer: failure modes. A serious architecture is not defined only by what it does when things work. It is defined by what happens when reality bites" | 16900–16906 |
| E0529 | Model Failure + Router Failure — Model 9 failure types (hallucinated fact / invalid tool call / wrong file path / bad code patch / unsafe recommendation / format-schema drift / overconfidence / context loss / looping) + 6-step response (detect / classify / trace / retry with altered route / escalate to oracle or human / store failure pattern) + "A model failure should become training/eval material, not just an error"; Router 6 failure types (cheap model chosen for hard task / oracle overused / cloud called when local required / private context routed externally / wrong adapter selected / bad fallback) + 5-step mitigation (policy veto before route / trace route reasoning / eval route after outcome / update router statistics / user-visible route override) + "Router decisions must be explainable" | 16910–16974 |
| E0530 | Policy Failure + Tool Failure — Policy 6 failure types (allowed too much / blocked useful action / ambiguous user intent / profile conflict / project policy conflict / cloud-privacy mismatch) + 5-step mitigation (deny by default for high-risk ambiguity / ask user when intent matters / record policy reason / support temporary grants / support revocation) + "Policy must never be only prompt-based"; Tool 8 failure types (command timeout / nonzero exit / partial write / network failure / dependency failure / bad working directory / unexpected side effect / permission denied) + 7-step mitigation (sandbox first / timeout always / capture stdout-stderr / detect changed files / rollback if needed / summarize failure / feed back into workflow) + "Tool output is observation, not truth until interpreted" | 16978–17030 |
| E0531 | Sandbox Failure + Memory Failure — Sandbox 7 failure types (container escape risk / mount misconfiguration / network leakage / GPU device overexposed / filesystem too broad / secret leaked into sandbox / checkpoint restore failed) + 7-step mitigation (least privilege mounts / stub credentials / network namespaces / AppArmor-seccomp / eBPF observation / ZFS snapshots / VM for high-risk tasks) + "The 3090 VFIO VM is the hard boundary profile"; Memory 7 failure types (stale fact / contradictory memory / private memory exposed / bad summary promoted / poisoned memory / irrelevant retrieval / context bloat) + 7-step mitigation (trust-freshness metadata / raw trace preservation / quarantine state / memory provenance / forget-delete support / verification before promotion / policy check on read) + "Summaries are derived artifacts, not authority" | 17034–17086 |
| E0532 | Eval Failure + Hardware Failure — Eval 6 failure types (wrong metric / judge model bias / test too shallow / benchmark contamination / reward hacking / passing tests but bad behavior) + 6-step mitigation (multiple eval types / human spot checks / local project evals / trajectory evals / negative cases / regression sets) + "Evals are instruments, not gods"; Hardware 9 failure types (GPU OOM / driver crash / NCCL-P2P weirdness / thermal throttling / NVMe throttling / ZFS degraded pool / RAM pressure / PCIe lane surprise / NIC instability) + 8-step mitigation (health probes / DCGM metrics / PSI pressure signals / fallback routes / smaller model route / context reduction / checkpoint before risk / no critical dependency on P2P) + "Hardware is part of the runtime state" | 17090–17142 |
| E0533 | Continuity Failure + Human Interface Failure — Continuity 6 failure types (resume loses context / checkpoint stale / workflow state mismatched / tool future disappeared / sandbox restored but files changed / user returns after policy changed) + 6-step mitigation (semantic checkpoint / versioned workflow state / trace replay / state reconciliation / resume summary / user confirmation on stale resume) + "Continuity must be explicit"; Human Interface 6 failure types (too many approvals / unclear risk explanation / hidden cost / unreadable trace / bad defaults / false sense of autonomy) + 6-step mitigation (batch approvals / plain-language reasons / cost preview / rollback preview / profile clarity / progressive disclosure) + "Sovereignty fails if the user is overwhelmed" | 17146–17192 |
| E0534 | System-Wide Recovery Pattern — every failure follows 5-step (detect / contain / explain / recover / learn); worked example (Tool command fails → contain in sandbox → summarize error → route to scout for diagnosis → oracle if high-value → update memory/eval → resume workflow) | 17196–17208 |
| E0535 | Architectural Law — "Failures are not exceptions. Failures are training signals and control signals" + "This is how the workstation becomes better with use" | 17210–17212 |
| E0536 | Cloud-vs-station closing — "Cloud systems often hide failure. Sovereign-OS should metabolize failure into intelligence" | 17214 |
| E0537 | Cross-module + cross-repo composition — 10 failure-mode taxonomies REALIZE sovereign-os M049 16-event taxonomy + M048 Module 9 Observability Fabric + M048 Module 10 Policy Fabric + M048 Module 7 Eval-Value Plane + M048 Module 8 Continuity Manager + selfdef MS017 agent-guard + MS019 threat model + MS026 integrity-sentinel + MS027 observability + MS033 Phase 3 Policy and Trace + MS035 Capability Tokens + MS036 Tool Sandboxes | architecture + cross-ref M048 + M049 + MS017 + MS019 + MS026 + MS027 + MS033 + MS035 + MS036 |

## Modules (M00918–M00934)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00918 | Failure-architecture doctrine — "what happens when reality bites" | 16906 | E0528 |
| M00919 | Failure mode 1 — Model Failure (9 types + 6-step response + "training/eval material doctrine") | 16910–16940 | E0529 |
| M00920 | Failure mode 2 — Router Failure (6 types + 5-step mitigation + "explainable router doctrine") | 16944–16974 | E0529 |
| M00921 | Failure mode 3 — Policy Failure (6 types + 5-step mitigation + "policy never only prompt-based doctrine") | 16978–17006 | E0530 |
| M00922 | Failure mode 4 — Tool Failure (8 types + 7-step mitigation + "observation not truth doctrine") | 17010–17030 | E0530 |
| M00923 | Failure mode 5 — Sandbox Failure (7 types + 7-step mitigation + "3090 VFIO VM is the hard boundary profile") | 17034–17064 | E0531 |
| M00924 | Failure mode 6 — Memory Failure (7 types + 7-step mitigation + "summaries are derived artifacts not authority") | 17068–17086 | E0531 |
| M00925 | Failure mode 7 — Eval Failure (6 types + 6-step mitigation + "evals are instruments not gods") | 17090–17110 | E0532 |
| M00926 | Failure mode 8 — Hardware Failure (9 types + 8-step mitigation + "hardware is part of the runtime state") | 17114–17142 | E0532 |
| M00927 | Failure mode 9 — Continuity Failure (6 types + 6-step mitigation + "continuity must be explicit") | 17146–17172 | E0533 |
| M00928 | Failure mode 10 — Human Interface Failure (6 types + 6-step mitigation + "sovereignty fails if the user is overwhelmed") | 17176–17192 | E0533 |
| M00929 | System-Wide Recovery Pattern 5-step — detect / contain / explain / recover / learn | 17198–17200 | E0534 |
| M00930 | Recovery worked example — Tool command fails → contain in sandbox → summarize error → route to scout for diagnosis → oracle if high-value → update memory-eval → resume workflow | 17204–17208 | E0534 |
| M00931 | Architectural Law — "Failures are not exceptions. Failures are training signals and control signals" | 17210 | E0535 |
| M00932 | Doctrine — "This is how the workstation becomes better with use" | 17212 | E0535 |
| M00933 | Cloud-vs-station — "Cloud systems often hide failure. Sovereign-OS should metabolize failure into intelligence" | 17214 | E0536 |
| M00934 | Cross-module realization — 10 failure modes map to M049 16-event taxonomy / M048 10-module fabric + selfdef MS001-MS036 enforcement | architecture | E0537 |

## Features (F04591–F04675)

| Feature ID | Phrase | Dump line | Parent module |
|---|---|---|---|
| F04591 | "Next layer: failure modes" | 16900 | E0528 |
| F04592 | "A serious architecture is not defined only by what it does when things work" | 16902 | M00918 |
| F04593 | "It is defined by what happens when reality bites" | 16906 | M00918 |
| F04594 | Model Failure — hallucinated fact | 16914 | M00919 |
| F04595 | Model Failure — invalid tool call | 16915 | M00919 |
| F04596 | Model Failure — wrong file path | 16916 | M00919 |
| F04597 | Model Failure — bad code patch | 16917 | M00919 |
| F04598 | Model Failure — unsafe recommendation | 16918 | M00919 |
| F04599 | Model Failure — format/schema drift | 16919 | M00919 |
| F04600 | Model Failure — overconfidence | 16920 | M00919 |
| F04601 | Model Failure — context loss | 16921 | M00919 |
| F04602 | Model Failure — looping | 16922 | M00919 |
| F04603 | Model Failure response — detect | 16928 | M00919 |
| F04604 | Model Failure response — classify | 16929 | M00919 |
| F04605 | Model Failure response — trace | 16930 | M00919 |
| F04606 | Model Failure response — retry with altered route | 16931 | M00919 |
| F04607 | Model Failure response — escalate to oracle or human | 16932 | M00919 |
| F04608 | Model Failure response — store failure pattern | 16933 | M00919 |
| F04609 | Model Failure rule — "A model failure should become training/eval material, not just an error" | 16940 | M00919 |
| F04610 | Router Failure — cheap model chosen for hard task | 16948 | M00920 |
| F04611 | Router Failure — oracle overused | 16949 | M00920 |
| F04612 | Router Failure — cloud called when local required | 16950 | M00920 |
| F04613 | Router Failure — private context routed externally | 16951 | M00920 |
| F04614 | Router Failure — wrong adapter selected | 16952 | M00920 |
| F04615 | Router Failure — bad fallback | 16953 | M00920 |
| F04616 | Router mitigation — policy veto before route | 16958 | M00920 |
| F04617 | Router mitigation — trace route reasoning | 16959 | M00920 |
| F04618 | Router mitigation — eval route after outcome | 16960 | M00920 |
| F04619 | Router mitigation — update router statistics | 16961 | M00920 |
| F04620 | Router mitigation — user-visible route override | 16962 | M00920 |
| F04621 | Router doctrine — "Router decisions must be explainable" | 16974 | M00920 |
| F04622 | Policy Failure — allowed too much + blocked useful action + ambiguous user intent + profile conflict + project policy conflict + cloud/privacy mismatch | 16982–16994 | M00921 |
| F04623 | Policy mitigation — deny by default for high-risk ambiguity / ask user when intent matters / record policy reason / support temporary grants / support revocation | 17000–17006 | M00921 |
| F04624 | Policy doctrine — "Policy must never be only prompt-based" | 17006 | M00921 |
| F04625 | Tool Failure — command timeout + nonzero exit + partial write + network failure + dependency failure + bad working directory + unexpected side effect + permission denied | 17012–17022 | M00922 |
| F04626 | Tool mitigation — sandbox first / timeout always / capture stdout-stderr / detect changed files / rollback if needed / summarize failure / feed back into workflow | 17026–17030 | M00922 |
| F04627 | Tool doctrine — "Tool output is observation, not truth until interpreted" | 17030 | M00922 |
| F04628 | Sandbox Failure — container escape risk + mount misconfiguration + network leakage + GPU device overexposed + filesystem too broad + secret leaked into sandbox + checkpoint restore failed | 17040–17050 | M00923 |
| F04629 | Sandbox mitigation — least privilege mounts / stub credentials / network namespaces / AppArmor-seccomp / eBPF observation / ZFS snapshots / VM for high-risk tasks | 17056–17062 | M00923 |
| F04630 | Sandbox doctrine — "The 3090 VFIO VM is the hard boundary profile" | 17064 | M00923 |
| F04631 | Memory Failure — stale fact + contradictory memory + private memory exposed + bad summary promoted + poisoned memory + irrelevant retrieval + context bloat | 17072–17080 | M00924 |
| F04632 | Memory mitigation — trust-freshness metadata / raw trace preservation / quarantine state / memory provenance / forget-delete support / verification before promotion / policy check on read | 17084–17086 | M00924 |
| F04633 | Memory doctrine — "Summaries are derived artifacts, not authority" | 17086 | M00924 |
| F04634 | Eval Failure — wrong metric + judge model bias + test too shallow + benchmark contamination + reward hacking + passing tests but bad behavior | 17094–17102 | M00925 |
| F04635 | Eval mitigation — multiple eval types / human spot checks / local project evals / trajectory evals / negative cases / regression sets | 17106–17110 | M00925 |
| F04636 | Eval doctrine — "Evals are instruments, not gods" | 17110 | M00925 |
| F04637 | Hardware Failure — GPU OOM + driver crash + NCCL/P2P weirdness + thermal throttling + NVMe throttling + ZFS degraded pool + RAM pressure + PCIe lane surprise + NIC instability | 17118–17126 | M00926 |
| F04638 | Hardware mitigation — health probes / DCGM metrics / PSI pressure signals / fallback routes / smaller model route / context reduction / checkpoint before risk / no critical dependency on P2P | 17130–17140 | M00926 |
| F04639 | Hardware doctrine — "Hardware is part of the runtime state" | 17142 | M00926 |
| F04640 | Continuity Failure — resume loses context + checkpoint stale + workflow state mismatched + tool future disappeared + sandbox restored but files changed + user returns after policy changed | 17150–17158 | M00927 |
| F04641 | Continuity mitigation — semantic checkpoint / versioned workflow state / trace replay / state reconciliation / resume summary / user confirmation on stale resume | 17162–17168 | M00927 |
| F04642 | Continuity doctrine — "Continuity must be explicit" | 17172 | M00927 |
| F04643 | Human Interface Failure — too many approvals + unclear risk explanation + hidden cost + unreadable trace + bad defaults + false sense of autonomy | 17180–17186 | M00928 |
| F04644 | Human Interface mitigation — batch approvals / plain-language reasons / cost preview / rollback preview / profile clarity / progressive disclosure | 17190–17192 | M00928 |
| F04645 | Human Interface doctrine — "Sovereignty fails if the user is overwhelmed" | 17192 | M00928 |
| F04646 | Recovery step — detect | 17198 | M00929 |
| F04647 | Recovery step — contain | 17199 | M00929 |
| F04648 | Recovery step — explain | 17200 | M00929 |
| F04649 | Recovery step — recover | 17201 | M00929 |
| F04650 | Recovery step — learn | 17202 | M00929 |
| F04651 | Recovery example — Tool command fails | 17204 | M00930 |
| F04652 | Recovery example — contain in sandbox | 17205 | M00930 |
| F04653 | Recovery example — summarize error | 17206 | M00930 |
| F04654 | Recovery example — route to scout for diagnosis | 17207 | M00930 |
| F04655 | Recovery example — oracle if high-value | 17208 | M00930 |
| F04656 | Recovery example — update memory/eval | 17209 | M00930 |
| F04657 | Recovery example — resume workflow | 17210 | M00930 |
| F04658 | Architectural Law — "Failures are not exceptions" | 17210 | M00931 |
| F04659 | Architectural Law — "Failures are training signals and control signals" | 17210 | M00931 |
| F04660 | "This is how the workstation becomes better with use" | 17212 | M00932 |
| F04661 | "Cloud systems often hide failure" | 17214 | M00933 |
| F04662 | "Sovereign-OS should metabolize failure into intelligence" | 17214 | M00933 |
| F04663 | Cross-module — 10 failure modes map to M049 16-event taxonomy (model_call/tool_call/memory_read/write/route_decision/policy_decision/sandbox_start/stop/test_run/eval_score/checkpoint/rollback/human_gate/cloud_call/cost_event) | cross-ref M049 | M00934 |
| F04664 | Cross-module — failure events emit class_uid=2004 Detection Finding (selfdef MS026 integrity-sentinel pattern) | cross-ref MS026 + M049 | M00934 |
| F04665 | Cross-module — Model Failure handled by sovereign-os M026 SLM swarm + RLM + M032 Cloud Expert + M046 LoRA foundry | cross-ref M026 + M032 + M046 | M00919 |
| F04666 | Cross-module — Router Failure handled by sovereign-os M043 Bridge Layer hardware-aware intelligence scheduling | cross-ref M043 | M00920 |
| F04667 | Cross-module — Policy Failure handled by sovereign-os M049 Policy Fabric (OPA/Cedar/OpenFGA) + selfdef MS017 agent-guard + MS033 Phase 3 Policy and Trace | cross-ref M049 + MS017 + MS033 | M00921 |
| F04668 | Cross-module — Tool Failure handled by selfdef MS036 Tool Sandboxes (Tier A/B/C/D) + M054 Tool Interface 4-state pipeline | cross-ref MS036 + M054 | M00922 |
| F04669 | Cross-module — Sandbox Failure handled by selfdef MS032 sandbox tiers + sovereign-os M048 Module 3 Container/Sandbox Fabric + M044 VFIO/IOMMU substrate | cross-ref MS032 + M048 + M044 | M00923 |
| F04670 | Cross-module — Memory Failure handled by sovereign-os M028 Memory OS + M049 9-class memory sensitivity + selfdef MS035 capability_word trust level | cross-ref M028 + M049 + MS035 | M00924 |
| F04671 | Cross-module — Eval Failure handled by sovereign-os M027 Value Plane + M037 Spec/TDD agent-evals + selfdef MS020 L1-L5 test harness | cross-ref M027 + M037 + MS020 | M00925 |
| F04672 | Cross-module — Hardware Failure handled by sovereign-os M044 Sovereign-OS substrate (DCGM + PSI) + M045 Linux as intelligence governor + selfdef MS010 hardware-tune-cache | cross-ref M044 + M045 + MS010 | M00926 |
| F04673 | Cross-module — Continuity Failure handled by sovereign-os M047 Continuity (CRIU + ZFS) + M048 Module 8 Continuity Manager | cross-ref M047 + M048 | M00927 |
| F04674 | Cross-module — Human Interface Failure handled by sovereign-os M048 Configuration Surfaces 3-level + M050 Section 10 Fullstack Surface + selfdef MS011 operator dashboard | cross-ref M048 + M050 + MS011 | M00928 |
| F04675 | Cross-repo binding — 10 failure-mode taxonomies + 5-step recovery pattern + Architectural Law published via MS007 doc-manifest typed-mirror crate | cross-ref MS007 | M00934 |

## Requirements (R09181–R09350)

| Req ID | Phrase | Dump line | Parent feature | Negotiability | Layer-B metric | Priority |
|---|---|---|---|---|---|---|
| R09181 | "Next layer: failure modes" | 16900 | F04591 | non-negotiable | false | 10 |
| R09182 | "A serious architecture is not defined only by what it does when things work" | 16902 | F04592 | non-negotiable | false | 10 |
| R09183 | "It is defined by what happens when reality bites" | 16906 | F04593 | non-negotiable | false | 10 |
| R09184 | Model Failure — hallucinated fact | 16914 | F04594 | non-negotiable | false | 10 |
| R09185 | Model Failure — invalid tool call | 16915 | F04595 | non-negotiable | false | 10 |
| R09186 | Model Failure — wrong file path | 16916 | F04596 | non-negotiable | false | 10 |
| R09187 | Model Failure — bad code patch | 16917 | F04597 | non-negotiable | false | 10 |
| R09188 | Model Failure — unsafe recommendation | 16918 | F04598 | non-negotiable | false | 10 |
| R09189 | Model Failure — format/schema drift | 16919 | F04599 | non-negotiable | false | 10 |
| R09190 | Model Failure — overconfidence | 16920 | F04600 | non-negotiable | false | 10 |
| R09191 | Model Failure — context loss | 16921 | F04601 | non-negotiable | false | 10 |
| R09192 | Model Failure — looping | 16922 | F04602 | non-negotiable | false | 10 |
| R09193 | Model Failure response — detect | 16928 | F04603 | non-negotiable | false | 10 |
| R09194 | Model Failure response — classify | 16929 | F04604 | non-negotiable | false | 10 |
| R09195 | Model Failure response — trace | 16930 | F04605 | non-negotiable | false | 10 |
| R09196 | Model Failure response — retry with altered route | 16931 | F04606 | non-negotiable | false | 10 |
| R09197 | Model Failure response — escalate to oracle or human | 16932 | F04607 | non-negotiable | false | 10 |
| R09198 | Model Failure response — store failure pattern | 16933 | F04608 | non-negotiable | false | 10 |
| R09199 | Model Failure rule — "should become training/eval material, not just an error" | 16940 | F04609 | non-negotiable | false | 10 |
| R09200 | Router Failure — cheap model chosen for hard task | 16948 | F04610 | non-negotiable | false | 10 |
| R09201 | Router Failure — oracle overused | 16949 | F04611 | non-negotiable | false | 10 |
| R09202 | Router Failure — cloud called when local required | 16950 | F04612 | non-negotiable | false | 10 |
| R09203 | Router Failure — private context routed externally | 16951 | F04613 | non-negotiable | false | 10 |
| R09204 | Router Failure — wrong adapter selected | 16952 | F04614 | non-negotiable | false | 10 |
| R09205 | Router Failure — bad fallback | 16953 | F04615 | non-negotiable | false | 10 |
| R09206 | Router mitigation — policy veto before route | 16958 | F04616 | non-negotiable | false | 10 |
| R09207 | Router mitigation — trace route reasoning | 16959 | F04617 | non-negotiable | false | 10 |
| R09208 | Router mitigation — eval route after outcome | 16960 | F04618 | non-negotiable | false | 10 |
| R09209 | Router mitigation — update router statistics | 16961 | F04619 | non-negotiable | false | 10 |
| R09210 | Router mitigation — user-visible route override | 16962 | F04620 | non-negotiable | false | 10 |
| R09211 | "Router decisions must be explainable" | 16974 | F04621 | non-negotiable | false | 10 |
| R09212 | Policy Failure — allowed too much | 16982 | F04622 | non-negotiable | false | 10 |
| R09213 | Policy Failure — blocked useful action | 16983 | F04622 | non-negotiable | false | 10 |
| R09214 | Policy Failure — ambiguous user intent | 16984 | F04622 | non-negotiable | false | 10 |
| R09215 | Policy Failure — profile conflict | 16985 | F04622 | non-negotiable | false | 10 |
| R09216 | Policy Failure — project policy conflict | 16986 | F04622 | non-negotiable | false | 10 |
| R09217 | Policy Failure — cloud/privacy mismatch | 16987 | F04622 | non-negotiable | false | 10 |
| R09218 | Policy mitigation — deny by default for high-risk ambiguity | 17000 | F04623 | non-negotiable | false | 10 |
| R09219 | Policy mitigation — ask user when intent matters | 17001 | F04623 | non-negotiable | false | 10 |
| R09220 | Policy mitigation — record policy reason | 17002 | F04623 | non-negotiable | false | 10 |
| R09221 | Policy mitigation — support temporary grants | 17003 | F04623 | non-negotiable | false | 10 |
| R09222 | Policy mitigation — support revocation | 17004 | F04623 | non-negotiable | false | 10 |
| R09223 | "Policy must never be only prompt-based" | 17006 | F04624 | non-negotiable | false | 10 |
| R09224 | Tool Failure — command timeout | 17012 | F04625 | non-negotiable | false | 10 |
| R09225 | Tool Failure — nonzero exit | 17013 | F04625 | non-negotiable | false | 10 |
| R09226 | Tool Failure — partial write | 17014 | F04625 | non-negotiable | false | 10 |
| R09227 | Tool Failure — network failure | 17015 | F04625 | non-negotiable | false | 10 |
| R09228 | Tool Failure — dependency failure | 17016 | F04625 | non-negotiable | false | 10 |
| R09229 | Tool Failure — bad working directory | 17017 | F04625 | non-negotiable | false | 10 |
| R09230 | Tool Failure — unexpected side effect | 17018 | F04625 | non-negotiable | false | 10 |
| R09231 | Tool Failure — permission denied | 17019 | F04625 | non-negotiable | false | 10 |
| R09232 | Tool mitigation — sandbox first | 17024 | F04626 | non-negotiable | false | 10 |
| R09233 | Tool mitigation — timeout always | 17025 | F04626 | non-negotiable | false | 10 |
| R09234 | Tool mitigation — capture stdout/stderr | 17026 | F04626 | non-negotiable | false | 10 |
| R09235 | Tool mitigation — detect changed files | 17027 | F04626 | non-negotiable | false | 10 |
| R09236 | Tool mitigation — rollback if needed | 17028 | F04626 | non-negotiable | false | 10 |
| R09237 | Tool mitigation — summarize failure | 17029 | F04626 | non-negotiable | false | 10 |
| R09238 | Tool mitigation — feed back into workflow | 17030 | F04626 | non-negotiable | false | 10 |
| R09239 | "Tool output is observation, not truth until interpreted" | 17030 | F04627 | non-negotiable | false | 10 |
| R09240 | Sandbox Failure — container escape risk | 17040 | F04628 | non-negotiable | false | 10 |
| R09241 | Sandbox Failure — mount misconfiguration | 17041 | F04628 | non-negotiable | false | 10 |
| R09242 | Sandbox Failure — network leakage | 17042 | F04628 | non-negotiable | false | 10 |
| R09243 | Sandbox Failure — GPU device overexposed | 17043 | F04628 | non-negotiable | false | 10 |
| R09244 | Sandbox Failure — filesystem too broad | 17044 | F04628 | non-negotiable | false | 10 |
| R09245 | Sandbox Failure — secret leaked into sandbox | 17045 | F04628 | non-negotiable | false | 10 |
| R09246 | Sandbox Failure — checkpoint restore failed | 17046 | F04628 | non-negotiable | false | 10 |
| R09247 | Sandbox mitigation — least privilege mounts | 17052 | F04629 | non-negotiable | false | 10 |
| R09248 | Sandbox mitigation — stub credentials | 17053 | F04629 | non-negotiable | false | 10 |
| R09249 | Sandbox mitigation — network namespaces | 17054 | F04629 | non-negotiable | false | 10 |
| R09250 | Sandbox mitigation — AppArmor/seccomp | 17055 | F04629 | non-negotiable | false | 10 |
| R09251 | Sandbox mitigation — eBPF observation | 17056 | F04629 | non-negotiable | false | 10 |
| R09252 | Sandbox mitigation — ZFS snapshots | 17057 | F04629 | non-negotiable | false | 10 |
| R09253 | Sandbox mitigation — VM for high-risk tasks | 17058 | F04629 | non-negotiable | false | 10 |
| R09254 | "The 3090 VFIO VM is the hard boundary profile" | 17064 | F04630 | non-negotiable | false | 10 |
| R09255 | Memory Failure — stale fact | 17072 | F04631 | non-negotiable | false | 10 |
| R09256 | Memory Failure — contradictory memory | 17073 | F04631 | non-negotiable | false | 10 |
| R09257 | Memory Failure — private memory exposed | 17074 | F04631 | non-negotiable | false | 10 |
| R09258 | Memory Failure — bad summary promoted | 17075 | F04631 | non-negotiable | false | 10 |
| R09259 | Memory Failure — poisoned memory | 17076 | F04631 | non-negotiable | false | 10 |
| R09260 | Memory Failure — irrelevant retrieval | 17077 | F04631 | non-negotiable | false | 10 |
| R09261 | Memory Failure — context bloat | 17078 | F04631 | non-negotiable | false | 10 |
| R09262 | Memory mitigation — trust/freshness metadata | 17082 | F04632 | non-negotiable | false | 10 |
| R09263 | Memory mitigation — raw trace preservation | 17083 | F04632 | non-negotiable | false | 10 |
| R09264 | Memory mitigation — quarantine state | 17084 | F04632 | non-negotiable | false | 10 |
| R09265 | Memory mitigation — memory provenance | 17085 | F04632 | non-negotiable | false | 10 |
| R09266 | Memory mitigation — forget/delete support | 17086 | F04632 | non-negotiable | false | 10 |
| R09267 | Memory mitigation — verification before promotion | 17087 | F04632 | non-negotiable | false | 10 |
| R09268 | Memory mitigation — policy check on read | 17088 | F04632 | non-negotiable | false | 10 |
| R09269 | "Summaries are derived artifacts, not authority" | 17086 | F04633 | non-negotiable | false | 10 |
| R09270 | Eval Failure — wrong metric | 17094 | F04634 | non-negotiable | false | 10 |
| R09271 | Eval Failure — judge model bias | 17095 | F04634 | non-negotiable | false | 10 |
| R09272 | Eval Failure — test too shallow | 17096 | F04634 | non-negotiable | false | 10 |
| R09273 | Eval Failure — benchmark contamination | 17097 | F04634 | non-negotiable | false | 10 |
| R09274 | Eval Failure — reward hacking | 17098 | F04634 | non-negotiable | false | 10 |
| R09275 | Eval Failure — passing tests but bad behavior | 17099 | F04634 | non-negotiable | false | 10 |
| R09276 | Eval mitigation — multiple eval types | 17104 | F04635 | non-negotiable | false | 10 |
| R09277 | Eval mitigation — human spot checks | 17105 | F04635 | non-negotiable | false | 10 |
| R09278 | Eval mitigation — local project evals | 17106 | F04635 | non-negotiable | false | 10 |
| R09279 | Eval mitigation — trajectory evals | 17107 | F04635 | non-negotiable | false | 10 |
| R09280 | Eval mitigation — negative cases | 17108 | F04635 | non-negotiable | false | 10 |
| R09281 | Eval mitigation — regression sets | 17109 | F04635 | non-negotiable | false | 10 |
| R09282 | "Evals are instruments, not gods" | 17110 | F04636 | non-negotiable | false | 10 |
| R09283 | Hardware Failure — GPU OOM | 17118 | F04637 | non-negotiable | false | 10 |
| R09284 | Hardware Failure — driver crash | 17119 | F04637 | non-negotiable | false | 10 |
| R09285 | Hardware Failure — NCCL/P2P weirdness | 17120 | F04637 | non-negotiable | false | 10 |
| R09286 | Hardware Failure — thermal throttling | 17121 | F04637 | non-negotiable | false | 10 |
| R09287 | Hardware Failure — NVMe throttling | 17122 | F04637 | non-negotiable | false | 10 |
| R09288 | Hardware Failure — ZFS degraded pool | 17123 | F04637 | non-negotiable | false | 10 |
| R09289 | Hardware Failure — RAM pressure | 17124 | F04637 | non-negotiable | false | 10 |
| R09290 | Hardware Failure — PCIe lane surprise | 17125 | F04637 | non-negotiable | false | 10 |
| R09291 | Hardware Failure — NIC instability | 17126 | F04637 | non-negotiable | false | 10 |
| R09292 | Hardware mitigation — health probes | 17130 | F04638 | non-negotiable | false | 10 |
| R09293 | Hardware mitigation — DCGM metrics | 17131 | F04638 | non-negotiable | false | 10 |
| R09294 | Hardware mitigation — PSI pressure signals | 17132 | F04638 | non-negotiable | false | 10 |
| R09295 | Hardware mitigation — fallback routes | 17133 | F04638 | non-negotiable | false | 10 |
| R09296 | Hardware mitigation — smaller model route | 17134 | F04638 | non-negotiable | false | 10 |
| R09297 | Hardware mitigation — context reduction | 17135 | F04638 | non-negotiable | false | 10 |
| R09298 | Hardware mitigation — checkpoint before risk | 17136 | F04638 | non-negotiable | false | 10 |
| R09299 | Hardware mitigation — no critical dependency on P2P | 17137 | F04638 | non-negotiable | false | 10 |
| R09300 | "Hardware is part of the runtime state" | 17142 | F04639 | non-negotiable | false | 10 |
| R09301 | Continuity Failure — resume loses context | 17150 | F04640 | non-negotiable | false | 10 |
| R09302 | Continuity Failure — checkpoint stale | 17151 | F04640 | non-negotiable | false | 10 |
| R09303 | Continuity Failure — workflow state mismatched | 17152 | F04640 | non-negotiable | false | 10 |
| R09304 | Continuity Failure — tool future disappeared | 17153 | F04640 | non-negotiable | false | 10 |
| R09305 | Continuity Failure — sandbox restored but files changed | 17154 | F04640 | non-negotiable | false | 10 |
| R09306 | Continuity Failure — user returns after policy changed | 17155 | F04640 | non-negotiable | false | 10 |
| R09307 | Continuity mitigation — semantic checkpoint | 17160 | F04641 | non-negotiable | false | 10 |
| R09308 | Continuity mitigation — versioned workflow state | 17161 | F04641 | non-negotiable | false | 10 |
| R09309 | Continuity mitigation — trace replay | 17162 | F04641 | non-negotiable | false | 10 |
| R09310 | Continuity mitigation — state reconciliation | 17163 | F04641 | non-negotiable | false | 10 |
| R09311 | Continuity mitigation — resume summary | 17164 | F04641 | non-negotiable | false | 10 |
| R09312 | Continuity mitigation — user confirmation on stale resume | 17165 | F04641 | non-negotiable | false | 10 |
| R09313 | "Continuity must be explicit" | 17172 | F04642 | non-negotiable | false | 10 |
| R09314 | Human Interface Failure — too many approvals | 17180 | F04643 | non-negotiable | false | 10 |
| R09315 | Human Interface Failure — unclear risk explanation | 17181 | F04643 | non-negotiable | false | 10 |
| R09316 | Human Interface Failure — hidden cost | 17182 | F04643 | non-negotiable | false | 10 |
| R09317 | Human Interface Failure — unreadable trace | 17183 | F04643 | non-negotiable | false | 10 |
| R09318 | Human Interface Failure — bad defaults | 17184 | F04643 | non-negotiable | false | 10 |
| R09319 | Human Interface Failure — false sense of autonomy | 17185 | F04643 | non-negotiable | false | 10 |
| R09320 | Human Interface mitigation — batch approvals | 17188 | F04644 | non-negotiable | false | 10 |
| R09321 | Human Interface mitigation — plain-language reasons | 17189 | F04644 | non-negotiable | false | 10 |
| R09322 | Human Interface mitigation — cost preview | 17190 | F04644 | non-negotiable | false | 10 |
| R09323 | Human Interface mitigation — rollback preview | 17191 | F04644 | non-negotiable | false | 10 |
| R09324 | Human Interface mitigation — profile clarity | 17192 | F04644 | non-negotiable | false | 10 |
| R09325 | Human Interface mitigation — progressive disclosure | 17193 | F04644 | non-negotiable | false | 10 |
| R09326 | "Sovereignty fails if the user is overwhelmed" | 17192 | F04645 | non-negotiable | false | 10 |
| R09327 | System-Wide Recovery — detect | 17198 | F04646 | non-negotiable | false | 10 |
| R09328 | System-Wide Recovery — contain | 17199 | F04647 | non-negotiable | false | 10 |
| R09329 | System-Wide Recovery — explain | 17200 | F04648 | non-negotiable | false | 10 |
| R09330 | System-Wide Recovery — recover | 17201 | F04649 | non-negotiable | false | 10 |
| R09331 | System-Wide Recovery — learn | 17202 | F04650 | non-negotiable | false | 10 |
| R09332 | Recovery example — Tool command fails | 17204 | F04651 | non-negotiable | false | 10 |
| R09333 | Recovery example — contain in sandbox | 17205 | F04652 | non-negotiable | false | 10 |
| R09334 | Recovery example — summarize error | 17206 | F04653 | non-negotiable | false | 10 |
| R09335 | Recovery example — route to scout for diagnosis | 17207 | F04654 | non-negotiable | false | 10 |
| R09336 | Recovery example — oracle if high-value | 17208 | F04655 | non-negotiable | false | 10 |
| R09337 | Recovery example — update memory/eval | 17209 | F04656 | non-negotiable | false | 10 |
| R09338 | Recovery example — resume workflow | 17210 | F04657 | non-negotiable | false | 10 |
| R09339 | Architectural Law — "Failures are not exceptions" | 17210 | F04658 | non-negotiable | false | 10 |
| R09340 | Architectural Law — "Failures are training signals and control signals" | 17210 | F04659 | non-negotiable | false | 10 |
| R09341 | "This is how the workstation becomes better with use" | 17212 | F04660 | non-negotiable | false | 10 |
| R09342 | "Cloud systems often hide failure" | 17214 | F04661 | non-negotiable | false | 10 |
| R09343 | "Sovereign-OS should metabolize failure into intelligence" | 17214 | F04662 | non-negotiable | false | 10 |
| R09344 | Cross-module — 10 failure modes map to M049 16-event taxonomy | cross-ref M049 | F04663 | non-negotiable | false | 10 |
| R09345 | Cross-module — Model Failure handled by M026 + M032 + M046 | cross-ref M026 + M032 + M046 | F04665 | non-negotiable | false | 10 |
| R09346 | Cross-module — Router Failure handled by M043 | cross-ref M043 | F04666 | non-negotiable | false | 10 |
| R09347 | Cross-module — Policy Failure handled by M049 + MS017 + MS033 | cross-ref M049 + MS017 + MS033 | F04667 | non-negotiable | false | 10 |
| R09348 | Cross-module — Tool Failure handled by MS036 + M054 | cross-ref MS036 + M054 | F04668 | non-negotiable | false | 10 |
| R09349 | Cross-module — Sandbox Failure handled by MS032 + M048 + M044 / Memory by M028 + M049 + MS035 / Eval by M027 + M037 + MS020 / Hardware by M044 + M045 + MS010 / Continuity by M047 + M048 / Human Interface by M048 + M050 + MS011 | cross-ref M048 + M044 + M027 + M037 + MS010 + M047 + MS011 + architecture | F04669–F04674 | non-negotiable | false | 10 |
| R09350 | Composite — M055 (10 epics / 17 modules / 85 features / 170 reqs) catalogs 10 failure-mode taxonomies (Model / Router / Policy / Tool / Sandbox / Memory / Eval / Hardware / Continuity / Human Interface) + per-mode failure-type catalog + per-mode mitigation catalog + per-mode doctrine + 5-step System-Wide Recovery Pattern (detect / contain / explain / recover / learn) + 7-step worked recovery example + Architectural Law "Failures are not exceptions. Failures are training signals and control signals." + cloud-vs-station closing "Sovereign-OS should metabolize failure into intelligence" + cross-module realization mapping 10 failure modes to sovereign-os M026/M027/M028/M032/M037/M043/M044/M045/M046/M047/M048/M049/M050 + selfdef MS010/MS011/MS017/MS019/MS020/MS026/MS027/MS032/MS033/MS035/MS036/MS054 + cross-repo binding via MS007 doc-manifest typed-mirror crate | dump 16896–17215 | E0528-E0537 | non-negotiable | false | 10 |

## Sub-references

- Adjacent dump-range milestones: M054 11 typed interfaces (16493–16896) / M056 Trust boundaries and authority (next; dump 17215–17532)
- 10 failure modes correspond to + extend M049 16-event taxonomy + M048 13-module fabric
- 5-step Recovery Pattern (detect/contain/explain/recover/learn) overlays M036 MAP→SPEC→TEST→ACT→EVAL→COMMIT→LEARN methodology + M050 Design Law
- Architectural Law "Failures are not exceptions" extends M050 Design Law + M052 Vision Recap "evidence-driven autonomy"
- Selfdef integration — MS010 + MS011 + MS016 + MS017 + MS019 + MS020 + MS025 + MS026 + MS027 + MS032 + MS033 + MS034 + MS035 + MS036 all realize failure-mode handling
- Cross-repo binding — MS007 doc-manifest + audit-manifest + dashboard-manifest typed-mirror crates carry 10 failure-mode taxonomy + 5-step recovery pattern + Architectural Law across selfdef + sovereign-os
- Operator references: dump 16896–17215 (10 failure modes + recovery pattern + architectural law + cloud-vs-station closing)
