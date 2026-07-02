# M035 — Frontier — inference-time intelligence

> Parent: `backlog/milestones/INDEX.md` row M035 (dump 10109–10378).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 10109–10378.
> All entries below are extracted from the dump line range. No invention.

## Epics (E0328–E0337)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0328 | 2026 frontier shift — no longer "bigger model, bigger context, bigger GPU"; new frontier = inference-time intelligence + agentic execution + memory + verification + local autonomy + energy/cost-aware reasoning; "that fits your station almost perfectly" | 10124–10143 |
| E0329 | Research substrate — 5 directions: (1) Inference-time scaling now major performance driver with real cost+latency; Microsoft BAPO analyzes lower bounds on reasoning-token complexity; (2) Energy studies separate normal inference from long reasoning/agentic queries; long reasoning + agents can increase energy by more than order of magnitude due to extra generated tokens + reduced batching; (3) Agent infrastructure 2026 emphasizes state machines + idempotency + observability + security + memory + interoperability as real wall (not model quality); (4) Memory vendors + papers converging on explicit memory tools + temporal graphs + memory-as-state instead of giant context windows; (5) Agentic AI moves from chatbot toward trusted digital coworker but trust/security gating | 10145–10153 |
| E0330 | Revolution = architectural — "Intelligence becomes an operating system problem" | 10155–10159 |
| E0331 | Frontier Principle — system decides how much intelligence to spend; not every request deserves a reasoning storm; 5-tier intelligence budget (reflex SLM/local-fast / deliberate scout+oracle+validation / deep tree-search+reward-model+tools / autonomous workflow+memory+world-model+rollback / high-assurance formal-checks+multiple-verifiers+human-gate) | 10161–10184 |
| E0332 | Why Breakthrough Territory — single LLM call has ONE intelligence profile; station synthesizes 9 (cheap reflex / careful thought / recursive context navigation / formal plan validation / tool execution / world simulation / memory retrieval / reward-guided search / human approval); "That is not just 'using AI'. That is programmable cognition" | 10186–10204 |
| E0333 | New Scaling Law — old "more training compute → smarter model"; new practical "better runtime allocation of inference compute → smarter system"; architecture exploits locally (4090 cheap candidate generation / Blackwell expensive verification-synthesis / AVX-512 CPU branch selection+masks+scheduling+policy+compaction / Memory-ZFS experience+replay / Gateway integrates Claude Code+Anthropic-first+OpenAI-compatible) — "inference-time scaling with governance" | 10206–10239 |
| E0334 | Energy + Cost Intelligence — long agentic reasoning burns compute; runtime tracks 9 dimensions (tokens / GPU seconds / cloud dollars / energy estimate / latency / cache hits / branch acceptance / tool retries / oracle calls); choose "is more thinking worth it?"; smart station stopping rule (confidence high enough / verification passed / marginal gain low / budget exhausted / risk requires human) — "intelligence with restraint" | 10241–10276 |
| E0335 | Revolutionary Runtime Shape (9-layer stack) — Anthropic-first Gateway (Claude Code+MCP+hooks+subagents enter) / Cognitive Compiler (intent → typed DAGs/workflows) / AVX-512 Cortex (branch/action/memory/policy bitfields) / Model Fabric (local LLM/SLM/RLM/RM/perception + optional cloud experts) / World Model (action consequences) / Execution Plane (REPL/tools/sandboxes/VM/GUI actions) / Memory OS (episodic+semantic+procedural+temporal-graph+value memory) / Observability (DCGM+OTel+eBPF+replay+cost ledger) / Profile System (reflex/normal/deliberate/autonomous/high-assurance) | 10278–10307 |
| E0336 | Deeper Breakthrough — "the more I look at it, the more the 'ultimate station' is not a workstation. It is a personal intelligence kernel"; like OS kernel, controls 9 things (processes=branches-agents / memory=context-KV-episodic-semantic / devices=GPUs-tools-browser-shell-files / permissions=capabilities-policy-bits / scheduling=model-tool-workflow queues / syscalls=tool-intents / logs=replay-observability / drivers=API-model-tool-adapters / security-rings=host-oracle-sandbox-VM-cloud); "analogy is not cute. It is exact enough to design from"; Kernel Law (Models=userland; Tools=devices; Memory=managed; Side effects=syscalls; Policies=permissions; Replay=audit log; Deterministic runtime=kernel space) | 10309–10343 |
| E0337 | Why Your Hardware Matters + Next Frontier — AM5 Zen 5 AVX-512 CPU = deterministic kernel fast enough to matter; Blackwell = local frontier-ish inference; 4090 = cheap/sandboxed auxiliary cognition; 256GB RAM + ZFS = memory + history; API gateway = Claude-first tools use station without caring what's behind; 8-front next-frontier list (Anthropic-compatible local gateway behavior with Claude Code / Model portfolio Ling-Nemotron-Qwen-Kimi-DeepSeek / RLM context-folding engine / Reward+value models for branch selection / AVX-512 bitset scheduler prototype / Memory OS with temporal graph+replay / Tool sandbox + MCP security boundary / Cost-energy-intelligence budget profiles); closing "the revolution is not a single feature. It is making intelligence scheduled, measured, replayed, constrained, and evolved" | 10345–10377 |

## Modules (M00578–M00594)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00578 | Intelligence Budget tier — reflex (SLM / local fast model) | 10168–10169 | E0331 |
| M00579 | Intelligence Budget tier — deliberate (scout + oracle + validation) | 10171–10172 | E0331 |
| M00580 | Intelligence Budget tier — deep (tree search + reward model + tools) | 10174–10175 | E0331 |
| M00581 | Intelligence Budget tier — autonomous (workflow + memory + world model + rollback) | 10177–10178 | E0331 |
| M00582 | Intelligence Budget tier — high assurance (formal checks + multiple verifiers + human gate) | 10180–10181 | E0331 |
| M00583 | Inference-time-scaling-with-governance hardware mapping — 4090 candidate gen / Blackwell verification / AVX-512 branch+mask+schedule+policy+compaction / Memory-ZFS experience+replay / Gateway client-integration | 10223–10237 | E0333 |
| M00584 | Cost-tracking 9-axis ledger — tokens / GPU seconds / cloud dollars / energy estimate / latency / cache hits / branch acceptance / tool retries / oracle calls | 10248–10257 | E0334 |
| M00585 | Stopping rule — confidence high enough / verification passed / marginal gain low / budget exhausted / risk requires human | 10268–10274 | E0334 |
| M00586 | Layer 1 — Anthropic-first Gateway (Claude Code / MCP / hooks / subagents enter here) | 10281–10282 | E0335 |
| M00587 | Layer 2 — Cognitive Compiler (turns intent into typed DAGs / workflows) | 10284–10285 | E0335 |
| M00588 | Layer 3 — AVX-512 Cortex (evaluates branch/action/memory/policy bitfields) | 10287–10288 | E0335 |
| M00589 | Layer 4 — Model Fabric (local LLM/SLM/RLM/RM/perception + optional cloud experts) | 10290–10291 | E0335 |
| M00590 | Layer 5 — World Model (predicts action consequences) | 10293–10294 | E0335 |
| M00591 | Layer 6 — Execution Plane (REPL / tools / sandboxes / VM / GUI actions) | 10296–10297 | E0335 |
| M00592 | Layer 7 — Memory OS (episodic / semantic / procedural / temporal graph / value) | 10299–10300 | E0335 |
| M00593 | Layer 8 — Observability (DCGM / OTel / eBPF / replay / cost ledger) | 10302–10303 | E0335 |
| M00594 | Layer 9 — Profile System (reflex / normal / deliberate / autonomous / high-assurance) | 10305–10306 | E0335 |

## Features (F02891–F02975)

| F ID | Phrase | Dump line | Parent | Category | Opt-in |
|---|---|---|---|---|---|
| F02891 | 2026 frontier is no longer "bigger model, bigger context, bigger GPU" | 10128–10130 | E0328 | composite | false |
| F02892 | New frontier — inference-time intelligence | 10135 | E0328 | composite | false |
| F02893 | New frontier — agentic execution | 10136 | E0328 | composite | false |
| F02894 | New frontier — memory | 10137 | E0328 | composite | false |
| F02895 | New frontier — verification | 10138 | E0328 | composite | false |
| F02896 | New frontier — local autonomy | 10139 | E0328 | composite | false |
| F02897 | New frontier — energy/cost-aware reasoning | 10140 | E0328 | composite | false |
| F02898 | "That fits your station almost perfectly" | 10143 | E0328 | composite | false |
| F02899 | Research — Microsoft BAPO analyzes lower bounds on reasoning-token complexity | 10149 | E0329 | composite | true |
| F02900 | Research — Joule 2026 energy study: long reasoning + agents increase energy by >1 order of magnitude | 10150 | E0329 | composite | true |
| F02901 | Research — Conectia agent analysis: agent infrastructure wall = state machines + idempotency + observability + security + memory + interoperability | 10151 | E0329 | composite | true |
| F02902 | Research — Agent memory vendor landscape: explicit memory tools + temporal graphs + memory-as-state | 10152 | E0329 | composite | true |
| F02903 | Research — Tool-based memory pattern (memory as tools) | 10152 | E0329 | composite | true |
| F02904 | Research — TechRadar 2026: agentic AI moves from chatbot to trusted digital coworker | 10153 | E0329 | composite | true |
| F02905 | Research — trust/security remain gating problems | 10153 | E0329 | composite | false |
| F02906 | "Intelligence becomes an operating system problem" | 10158 | E0330 | composite | false |
| F02907 | Frontier Principle — system decides how much intelligence to spend | 10163 | E0331 | composite | false |
| F02908 | Frontier Principle — not every request deserves a reasoning storm | 10165 | E0331 | composite | false |
| F02909 | Intelligence Budget tier — reflex (SLM / local fast model) | 10168–10169 | M00578 | composite | true |
| F02910 | Intelligence Budget tier — deliberate (scout + oracle + validation) | 10171–10172 | M00579 | composite | true |
| F02911 | Intelligence Budget tier — deep (tree search + reward model + tools) | 10174–10175 | M00580 | composite | true |
| F02912 | Intelligence Budget tier — autonomous (workflow + memory + world model + rollback) | 10177–10178 | M00581 | composite | true |
| F02913 | Intelligence Budget tier — high assurance (formal checks + multiple verifiers + human gate) | 10180–10181 | M00582 | composite | true |
| F02914 | "This is the intelligence budget" | 10184 | E0331 | composite | false |
| F02915 | Single LLM call has ONE intelligence profile | 10188 | E0332 | composite | false |
| F02916 | Station synthesizes many — cheap reflex | 10193 | E0332 | composite | true |
| F02917 | Station synthesizes many — careful thought | 10194 | E0332 | composite | true |
| F02918 | Station synthesizes many — recursive context navigation | 10195 | E0332 | composite | true |
| F02919 | Station synthesizes many — formal plan validation | 10196 | E0332 | composite | true |
| F02920 | Station synthesizes many — tool execution | 10197 | E0332 | composite | true |
| F02921 | Station synthesizes many — world simulation | 10198 | E0332 | composite | true |
| F02922 | Station synthesizes many — memory retrieval | 10199 | E0332 | composite | true |
| F02923 | Station synthesizes many — reward-guided search | 10200 | E0332 | composite | true |
| F02924 | Station synthesizes many — human approval | 10201 | E0332 | composite | true |
| F02925 | "That is not just using AI. That is programmable cognition." | 10204 | E0332 | composite | false |
| F02926 | Old scaling law — more training compute → smarter model | 10210 | E0333 | composite | false |
| F02927 | New scaling law — better runtime allocation of inference compute → smarter system | 10216 | E0333 | composite | false |
| F02928 | Architecture exploits new scaling law locally | 10219 | E0333 | composite | false |
| F02929 | Hardware — 4090 does cheap candidate generation | 10223–10224 | M00583 | composite | true |
| F02930 | Hardware — Blackwell does expensive verification/synthesis | 10226–10227 | M00583 | composite | true |
| F02931 | Hardware — AVX-512 CPU does branch selection / masks / scheduling / policy / compaction | 10229–10230 | M00583 | composite | true |
| F02932 | Hardware — Memory/ZFS does experience and replay | 10232–10233 | M00583 | composite | true |
| F02933 | Hardware — Gateway integrates Claude Code / Anthropic-first / OpenAI-compatible | 10235–10236 | M00583 | composite | true |
| F02934 | "That is inference-time scaling with governance" | 10239 | E0333 | composite | false |
| F02935 | Long agentic reasoning burns compute | 10243 | E0334 | composite | false |
| F02936 | Runtime tracks — tokens | 10248 | M00584 | composite | true |
| F02937 | Runtime tracks — GPU seconds | 10249 | M00584 | composite | true |
| F02938 | Runtime tracks — cloud dollars | 10250 | M00584 | composite | true |
| F02939 | Runtime tracks — energy estimate | 10251 | M00584 | composite | true |
| F02940 | Runtime tracks — latency | 10252 | M00584 | composite | true |
| F02941 | Runtime tracks — cache hits | 10253 | M00584 | composite | true |
| F02942 | Runtime tracks — branch acceptance | 10254 | M00584 | composite | true |
| F02943 | Runtime tracks — tool retries | 10255 | M00584 | composite | true |
| F02944 | Runtime tracks — oracle calls | 10256 | M00584 | composite | true |
| F02945 | Stopping rule — is more thinking worth it? | 10262 | M00585 | composite | false |
| F02946 | Stopping rule — confidence high enough | 10269 | M00585 | composite | true |
| F02947 | Stopping rule — verification passed | 10270 | M00585 | composite | true |
| F02948 | Stopping rule — marginal gain low | 10271 | M00585 | composite | true |
| F02949 | Stopping rule — budget exhausted | 10272 | M00585 | composite | true |
| F02950 | Stopping rule — risk requires human | 10273 | M00585 | composite | true |
| F02951 | "That is intelligence with restraint" | 10276 | E0334 | composite | false |
| F02952 | Runtime shape Layer — Anthropic-first Gateway | 10281 | M00586 | composite | true |
| F02953 | Runtime shape Layer — Cognitive Compiler | 10284 | M00587 | composite | true |
| F02954 | Runtime shape Layer — AVX-512 Cortex | 10287 | M00588 | composite | true |
| F02955 | Runtime shape Layer — Model Fabric | 10290 | M00589 | composite | true |
| F02956 | Runtime shape Layer — World Model | 10293 | M00590 | composite | true |
| F02957 | Runtime shape Layer — Execution Plane | 10296 | M00591 | composite | true |
| F02958 | Runtime shape Layer — Memory OS | 10299 | M00592 | composite | true |
| F02959 | Runtime shape Layer — Observability | 10302 | M00593 | composite | true |
| F02960 | Runtime shape Layer — Profile System | 10305 | M00594 | composite | true |
| F02961 | "The ultimate station is not a workstation. It is a personal intelligence kernel." | 10311–10313 | E0336 | composite | false |
| F02962 | Kernel analogy — processes → branches/agents | 10318 | E0336 | composite | false |
| F02963 | Kernel analogy — memory → context/KV/episodic/semantic stores | 10319 | E0336 | composite | false |
| F02964 | Kernel analogy — devices → GPUs/tools/browser/shell/files | 10320 | E0336 | composite | false |
| F02965 | Kernel analogy — permissions → capabilities/policy bits | 10321 | E0336 | composite | false |
| F02966 | Kernel analogy — scheduling → model/tool/workflow queues | 10322 | E0336 | composite | false |
| F02967 | Kernel analogy — syscalls → tool intents | 10323 | E0336 | composite | false |
| F02968 | Kernel analogy — logs → replay/observability | 10324 | E0336 | composite | false |
| F02969 | Kernel analogy — drivers → API/model/tool adapters | 10325 | E0336 | composite | false |
| F02970 | Kernel analogy — security rings → host/oracle/sandbox/VM/cloud | 10326 | E0336 | composite | false |
| F02971 | "That analogy is not cute. It is exact enough to design from." | 10329 | E0336 | composite | false |
| F02972 | Kernel Law — Models are userland | 10334 | E0336 | composite | false |
| F02973 | Kernel Law — Tools are devices | 10335 | E0336 | composite | false |
| F02974 | Kernel Law — Memory is managed; Side effects are syscalls; Policies are permissions; Replay is audit log; Deterministic runtime is kernel space | 10336–10340 | E0336 | composite | false |
| F02975 | Composite — Hardware-fits-frontier (AM5 Zen 5 AVX-512 CPU = deterministic kernel / Blackwell = local frontier-ish inference / 4090 = cheap auxiliary cognition / 256GB RAM + ZFS = memory + history / API gateway = Claude-first integration) + Next Frontier 8-front list (Anthropic gateway / Model portfolio Ling-Nemotron-Qwen-Kimi-DeepSeek / RLM context-folding / Reward/value branch selection / AVX-512 bitset scheduler / Memory OS temporal graph + replay / Tool sandbox + MCP security / Cost-energy-intelligence profiles) + closing "the revolution is not a single feature. It is making intelligence scheduled, measured, replayed, constrained, and evolved" | 10345–10377 | E0337 | composite | false |

## Requirements (R05781–R05950)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R05781 | 2026 frontier is no longer bigger model / bigger context / bigger GPU | 10128–10130 | F02891 | non-negotiable | false | 10 |
| R05782 | New frontier dimension — inference-time intelligence | 10135 | F02892 | non-negotiable | false | 10 |
| R05783 | New frontier dimension — agentic execution | 10136 | F02893 | non-negotiable | false | 10 |
| R05784 | New frontier dimension — memory | 10137 | F02894 | non-negotiable | false | 10 |
| R05785 | New frontier dimension — verification | 10138 | F02895 | non-negotiable | false | 10 |
| R05786 | New frontier dimension — local autonomy | 10139 | F02896 | non-negotiable | false | 10 |
| R05787 | New frontier dimension — energy/cost-aware reasoning | 10140 | F02897 | non-negotiable | false | 10 |
| R05788 | "That fits your station almost perfectly" | 10143 | F02898 | non-negotiable | false | 10 |
| R05789 | Microsoft BAPO cited (lower bounds on chain-of-thought token complexity) | 10149 | F02899 | non-negotiable | true | 10 |
| R05790 | Joule 2026 study cited (long reasoning + agents increase energy by >1 order of magnitude) | 10150 | F02900 | non-negotiable | true | 10 |
| R05791 | Conectia agent analysis cited (real wall = state machines + idempotency + observability + security + memory + interoperability) | 10151 | F02901 | non-negotiable | true | 10 |
| R05792 | Agent memory landscape cited (Letta / Zep / Mem0 / LangMem) | 10152 | F02902 | non-negotiable | true | 10 |
| R05793 | Tool-based memory pattern cited (memory as tools) | 10152 | F02903 | non-negotiable | true | 10 |
| R05794 | TechRadar 2026 cited (agentic AI moves from chatbot to trusted digital coworker) | 10153 | F02904 | non-negotiable | true | 10 |
| R05795 | Trust/security remain gating problems for agentic adoption | 10153 | F02905 | non-negotiable | false | 10 |
| R05796 | Architectural revolution — "Intelligence becomes an operating system problem" | 10158 | F02906 | non-negotiable | false | 10 |
| R05797 | Frontier Principle — system decides how much intelligence to spend | 10163 | F02907 | non-negotiable | false | 10 |
| R05798 | Frontier Principle — not every request deserves a reasoning storm | 10165 | F02908 | non-negotiable | false | 10 |
| R05799 | Intelligence Budget tier — reflex (SLM / local fast model) | 10168–10169 | F02909 | non-negotiable | true | 10 |
| R05800 | Intelligence Budget tier — deliberate (scout + oracle + validation) | 10171–10172 | F02910 | non-negotiable | true | 10 |
| R05801 | Intelligence Budget tier — deep (tree search + reward model + tools) | 10174–10175 | F02911 | non-negotiable | true | 10 |
| R05802 | Intelligence Budget tier — autonomous (workflow + memory + world model + rollback) | 10177–10178 | F02912 | non-negotiable | true | 10 |
| R05803 | Intelligence Budget tier — high assurance (formal checks + multiple verifiers + human gate) | 10180–10181 | F02913 | non-negotiable | true | 10 |
| R05804 | "This is the intelligence budget" | 10184 | F02914 | non-negotiable | false | 10 |
| R05805 | A single LLM call has ONE intelligence profile | 10188 | F02915 | non-negotiable | false | 10 |
| R05806 | Station synthesizes profile — cheap reflex | 10193 | F02916 | non-negotiable | true | 10 |
| R05807 | Station synthesizes profile — careful thought | 10194 | F02917 | non-negotiable | true | 10 |
| R05808 | Station synthesizes profile — recursive context navigation | 10195 | F02918 | non-negotiable | true | 10 |
| R05809 | Station synthesizes profile — formal plan validation | 10196 | F02919 | non-negotiable | true | 10 |
| R05810 | Station synthesizes profile — tool execution | 10197 | F02920 | non-negotiable | true | 10 |
| R05811 | Station synthesizes profile — world simulation | 10198 | F02921 | non-negotiable | true | 10 |
| R05812 | Station synthesizes profile — memory retrieval | 10199 | F02922 | non-negotiable | true | 10 |
| R05813 | Station synthesizes profile — reward-guided search | 10200 | F02923 | non-negotiable | true | 10 |
| R05814 | Station synthesizes profile — human approval | 10201 | F02924 | non-negotiable | true | 10 |
| R05815 | "That is not just using AI. That is programmable cognition." | 10204 | F02925 | non-negotiable | false | 10 |
| R05816 | Old scaling law — more training compute → smarter model | 10210 | F02926 | non-negotiable | false | 10 |
| R05817 | New scaling law — better runtime allocation of inference compute → smarter system | 10216 | F02927 | non-negotiable | false | 10 |
| R05818 | Architecture exploits new scaling law locally | 10219 | F02928 | non-negotiable | false | 10 |
| R05819 | Hardware — 4090 does cheap candidate generation | 10223–10224 | F02929 | non-negotiable | true | 10 |
| R05820 | Hardware — Blackwell does expensive verification/synthesis | 10226–10227 | F02930 | non-negotiable | true | 10 |
| R05821 | Hardware — AVX-512 CPU does branch selection / masks / scheduling / policy / compaction | 10229–10230 | F02931 | non-negotiable | true | 10 |
| R05822 | Hardware — Memory/ZFS does experience and replay | 10232–10233 | F02932 | non-negotiable | true | 10 |
| R05823 | Hardware — Gateway integrates Claude Code / Anthropic-first / OpenAI-compatible | 10235–10236 | F02933 | non-negotiable | true | 10 |
| R05824 | "Inference-time scaling with governance" | 10239 | F02934 | non-negotiable | false | 10 |
| R05825 | Long agentic reasoning burns compute (must be tracked) | 10243 | F02935 | non-negotiable | false | 10 |
| R05826 | Cost ledger — tokens | 10248 | F02936 | non-negotiable | true | 10 |
| R05827 | Cost ledger — GPU seconds | 10249 | F02937 | non-negotiable | true | 10 |
| R05828 | Cost ledger — cloud dollars | 10250 | F02938 | non-negotiable | true | 10 |
| R05829 | Cost ledger — energy estimate | 10251 | F02939 | non-negotiable | true | 10 |
| R05830 | Cost ledger — latency | 10252 | F02940 | non-negotiable | true | 10 |
| R05831 | Cost ledger — cache hits | 10253 | F02941 | non-negotiable | true | 10 |
| R05832 | Cost ledger — branch acceptance | 10254 | F02942 | non-negotiable | true | 10 |
| R05833 | Cost ledger — tool retries | 10255 | F02943 | non-negotiable | true | 10 |
| R05834 | Cost ledger — oracle calls | 10256 | F02944 | non-negotiable | true | 10 |
| R05835 | Decision — "Is more thinking worth it?" is the runtime question | 10262 | F02945 | non-negotiable | false | 10 |
| R05836 | Stopping rule — confidence high enough | 10269 | F02946 | non-negotiable | true | 10 |
| R05837 | Stopping rule — verification passed | 10270 | F02947 | non-negotiable | true | 10 |
| R05838 | Stopping rule — marginal gain low | 10271 | F02948 | non-negotiable | true | 10 |
| R05839 | Stopping rule — budget exhausted | 10272 | F02949 | non-negotiable | true | 10 |
| R05840 | Stopping rule — risk requires human | 10273 | F02950 | non-negotiable | true | 10 |
| R05841 | "Intelligence with restraint" | 10276 | F02951 | non-negotiable | false | 10 |
| R05842 | Runtime shape Layer 1 — Anthropic-first Gateway (Claude Code / MCP / hooks / subagents enter here) | 10281–10282 | F02952 | non-negotiable | true | 10 |
| R05843 | Runtime shape Layer 2 — Cognitive Compiler (intent → typed DAGs / workflows) | 10284–10285 | F02953 | non-negotiable | true | 10 |
| R05844 | Runtime shape Layer 3 — AVX-512 Cortex (branch/action/memory/policy bitfields) | 10287–10288 | F02954 | non-negotiable | true | 10 |
| R05845 | Runtime shape Layer 4 — Model Fabric (local LLM/SLM/RLM/RM/perception + optional cloud experts) | 10290–10291 | F02955 | non-negotiable | true | 10 |
| R05846 | Runtime shape Layer 5 — World Model (predicts action consequences) | 10293–10294 | F02956 | non-negotiable | true | 10 |
| R05847 | Runtime shape Layer 6 — Execution Plane (REPL / tools / sandboxes / VM / GUI actions) | 10296–10297 | F02957 | non-negotiable | true | 10 |
| R05848 | Runtime shape Layer 7 — Memory OS (episodic / semantic / procedural / temporal graph / value) | 10299–10300 | F02958 | non-negotiable | true | 10 |
| R05849 | Runtime shape Layer 8 — Observability (DCGM / OTel / eBPF / replay / cost ledger) | 10302–10303 | F02959 | non-negotiable | true | 10 |
| R05850 | Runtime shape Layer 9 — Profile System (reflex / normal / deliberate / autonomous / high-assurance) | 10305–10306 | F02960 | non-negotiable | true | 10 |
| R05851 | "The ultimate station is not a workstation. It is a personal intelligence kernel." | 10311–10313 | F02961 | non-negotiable | false | 10 |
| R05852 | Kernel analogy — processes → branches/agents | 10318 | F02962 | non-negotiable | true | 10 |
| R05853 | Kernel analogy — memory → context/KV/episodic/semantic stores | 10319 | F02963 | non-negotiable | true | 10 |
| R05854 | Kernel analogy — devices → GPUs/tools/browser/shell/files | 10320 | F02964 | non-negotiable | true | 10 |
| R05855 | Kernel analogy — permissions → capabilities/policy bits | 10321 | F02965 | non-negotiable | true | 10 |
| R05856 | Kernel analogy — scheduling → model/tool/workflow queues | 10322 | F02966 | non-negotiable | true | 10 |
| R05857 | Kernel analogy — syscalls → tool intents | 10323 | F02967 | non-negotiable | true | 10 |
| R05858 | Kernel analogy — logs → replay/observability | 10324 | F02968 | non-negotiable | true | 10 |
| R05859 | Kernel analogy — drivers → API/model/tool adapters | 10325 | F02969 | non-negotiable | true | 10 |
| R05860 | Kernel analogy — security rings → host/oracle/sandbox/VM/cloud | 10326 | F02970 | non-negotiable | true | 10 |
| R05861 | "That analogy is not cute. It is exact enough to design from." | 10329 | F02971 | non-negotiable | false | 10 |
| R05862 | Kernel Law — Models are userland | 10334 | F02972 | non-negotiable | false | 10 |
| R05863 | Kernel Law — Tools are devices | 10335 | F02973 | non-negotiable | false | 10 |
| R05864 | Kernel Law — Memory is managed | 10336 | F02974 | non-negotiable | false | 10 |
| R05865 | Kernel Law — Side effects are syscalls | 10337 | F02974 | non-negotiable | false | 10 |
| R05866 | Kernel Law — Policies are permissions | 10338 | F02974 | non-negotiable | false | 10 |
| R05867 | Kernel Law — Replay is audit log | 10339 | F02974 | non-negotiable | false | 10 |
| R05868 | Kernel Law — Deterministic runtime is kernel space | 10340 | F02974 | non-negotiable | false | 10 |
| R05869 | "That is the breakthrough architecture" | 10343 | E0336 | non-negotiable | false | 10 |
| R05870 | Hardware fit — AM5 Zen 5 AVX-512 CPU = deterministic kernel fast enough to matter | 10347 | F02975 | non-negotiable | false | 10 |
| R05871 | Hardware fit — Blackwell card = local frontier-ish inference | 10349 | F02975 | non-negotiable | false | 10 |
| R05872 | Hardware fit — 4090 = cheap/sandboxed auxiliary cognition | 10351 | F02975 | non-negotiable | false | 10 |
| R05873 | Hardware fit — 256GB RAM + ZFS = memory + history | 10353 | F02975 | non-negotiable | false | 10 |
| R05874 | Hardware fit — API gateway lets Claude-first tools use station without caring what's behind it | 10355 | F02975 | non-negotiable | false | 10 |
| R05875 | "That is the weave" | 10357 | F02975 | non-negotiable | false | 10 |
| R05876 | Next Frontier — Anthropic-compatible local gateway behavior with Claude Code | 10364 | F02975 | non-negotiable | true | 10 |
| R05877 | Next Frontier — Model portfolio (Ling / Nemotron / Qwen / Kimi / DeepSeek roles) | 10365 | F02975 | non-negotiable | true | 10 |
| R05878 | Next Frontier — RLM / context-folding engine over local files and traces | 10366 | F02975 | non-negotiable | true | 10 |
| R05879 | Next Frontier — Reward/value models for branch selection | 10367 | F02975 | non-negotiable | true | 10 |
| R05880 | Next Frontier — AVX-512 bitset scheduler prototype | 10368 | F02975 | non-negotiable | true | 10 |
| R05881 | Next Frontier — Memory OS with temporal graph + replay | 10369 | F02975 | non-negotiable | true | 10 |
| R05882 | Next Frontier — Tool sandbox and MCP security boundary | 10370 | F02975 | non-negotiable | true | 10 |
| R05883 | Next Frontier — Cost/energy/intelligence budget profiles | 10371 | F02975 | non-negotiable | true | 10 |
| R05884 | Closing — "The revolution is not a single feature" | 10374 | F02975 | non-negotiable | false | 10 |
| R05885 | Closing — "It is making intelligence scheduled, measured, replayed, constrained, and evolved" | 10376 | F02975 | non-negotiable | false | 10 |
| R05886 | M035 integrates with M027 Value Plane — intelligence budget + stopping rule consume Value Plane reward vector | 10168–10184 + cross-ref M027 | M00585 | non-negotiable | false | 10 |
| R05887 | M035 integrates with M028 Memory OS — Layer 7 of runtime shape | 10299 + cross-ref M028 | M00592 | non-negotiable | false | 10 |
| R05888 | M035 integrates with M029 Computer-Use Plane — Layer 6 Execution Plane includes GUI actions | 10297 + cross-ref M029 | M00591 | non-negotiable | false | 10 |
| R05889 | M035 integrates with M030 World Model Plane — Layer 5 | 10293 + cross-ref M030 | M00590 | non-negotiable | false | 10 |
| R05890 | M035 integrates with M031 Symbolic Planning Plane — formal plan validation profile + high-assurance tier | 10182 + 10196 + cross-ref M031 | F02913 + F02919 | non-negotiable | false | 10 |
| R05891 | M035 integrates with M032 Cloud Expert Plane — Model Fabric includes optional cloud experts | 10291 + cross-ref M032 | M00589 | non-negotiable | false | 10 |
| R05892 | M035 integrates with M033 Compatibility Gateway + M034 Anthropic-first Gateway — Layer 1 | 10281 + cross-ref M033 + M034 | M00586 | non-negotiable | false | 10 |
| R05893 | M035 integrates with M025 Cognitive Compiler — Layer 2 | 10284 + cross-ref M025 | M00587 | non-negotiable | false | 10 |
| R05894 | M035 integrates with M026 SLM swarm + RLM engine — Model Fabric local SLM/RLM | 10291 + cross-ref M026 | M00589 | non-negotiable | false | 10 |
| R05895 | M035 closes the 9-layer runtime shape (M025 → M026 → M027 → M028 → M029 → M030 → M031 → M032 → M033/M034) into a single "personal intelligence kernel" frame | 10278–10307 | E0335 | non-negotiable | false | 10 |
| R05896 | Project boundary — Frontier doctrine is sovereign-os runtime; selfdef observes via selfdef-collector-eventstream (NOT prompt content; only metadata + cost ledger) | architecture + 10248–10257 | E0334 | non-negotiable | false | 10 |
| R05897 | Project boundary — selfdef MS006 agent-guard may enforce profile-tier constraints (e.g. high-assurance profile requires human gate for irreversible side-effects) | MS006 + 10180–10181 | F02913 | non-negotiable | false | 10 |
| R05898 | Project boundary — selfdef MS007 typed-mirror crates may carry Intelligence Budget tier + Stopping Rule schemas for cross-repo binding | MS007 + SDD-038 | M00578 + M00585 | non-negotiable | false | 10 |
| R05899 | Cost ledger integrates with M033 Compatibility Gateway cost-ledger (M033 R05452-R05485) — same 9-dimension tracking + 5-rule stopping rule + per-request decision-reason | cross-ref M033 R05452–R05485 + 10248–10274 | M00584 + M00585 | non-negotiable | false | 10 |
| R05900 | Profile System reuses M033/M034 alias trick — claude-jean-reflex, claude-jean-deliberate, claude-jean-deep, claude-jean-autonomous, claude-jean-high-assurance | cross-ref M034 R05663–R05669 + 10168–10184 | M00594 | non-negotiable | false | 10 |
| R05901 | Reflex tier maps to claude-jean-fast OR claude-jean-local (M034) | 10168 + cross-ref M034 | F02909 | non-negotiable | false | 10 |
| R05902 | Deliberate tier maps to claude-jean-careful OR claude-jean-code (M034) | 10171 + cross-ref M034 | F02910 | non-negotiable | false | 10 |
| R05903 | Deep tier maps to claude-jean-oracle OR claude-jean-hybrid (M034) | 10174 + cross-ref M034 | F02911 | non-negotiable | false | 10 |
| R05904 | Autonomous tier maps to a new alias (claude-jean-autonomous; operator-defined) — workflow + memory + world model + rollback | 10177 | F02912 | non-negotiable | false | 10 |
| R05905 | High-assurance tier maps to claude-jean-high-assurance (M034 disagreement-check pattern) | 10180 + cross-ref M034 | F02913 | non-negotiable | false | 10 |
| R05906 | Cost-ledger row schema — per-request: client / project / profile / route / tokens / GPU-seconds / cloud-dollars / energy-estimate / latency / cache-hit / branch-acceptance / tool-retries / oracle-calls / decision-reason (extends M033 9-field with M035 additions) | cross-ref M033 R05521–R05529 + 10248–10257 | M00584 | non-negotiable | false | 10 |
| R05907 | Cost-ledger invariant — every request records ALL 9 dimensions (NOT optional) | 10248–10257 | M00584 | non-negotiable | false | 10 |
| R05908 | Cost-ledger invariant — energy estimate uses operator-configurable kWh/token coefficient | 10251 | F02939 | non-negotiable | false | 10 |
| R05909 | Cost-ledger invariant — cloud-dollars uses provider-published per-token pricing | 10250 + cross-ref M033 R05553 | F02938 | non-negotiable | false | 10 |
| R05910 | Stopping rule invariant — runtime checks AFTER each branch (NOT only at request end) | 10268 | M00585 | non-negotiable | false | 10 |
| R05911 | Stopping rule invariant — confidence threshold operator-configurable per profile | 10269 | F02946 | non-negotiable | false | 10 |
| R05912 | Stopping rule invariant — verification gate consults Symbolic Planning Plane policy engine (M031) | 10270 + cross-ref M031 | F02947 | non-negotiable | false | 10 |
| R05913 | Stopping rule invariant — marginal gain computed as expected_reward(continue) - expected_reward(stop) (Value Plane M027) | 10271 + cross-ref M027 | F02948 | non-negotiable | false | 10 |
| R05914 | Stopping rule invariant — budget exhaustion fails closed (NOT fails open) | 10272 | F02949 | non-negotiable | false | 10 |
| R05915 | Stopping rule invariant — risk threshold profile-configurable; human-gate is the default for high-risk (M029 high_risk + M035 high-assurance) | 10273 + cross-ref M029 R04831 | F02950 | non-negotiable | false | 10 |
| R05916 | Energy-aware reasoning invariant — long reasoning burns energy → operator opt-in (default = false in private/sovereign profiles) | 10243 + cross-ref M033 R05576 | E0334 | non-negotiable | false | 10 |
| R05917 | Energy-aware reasoning invariant — Joule 2026 cited (>1 OOM energy increase for long agents) | 10150 | F02900 | non-negotiable | false | 10 |
| R05918 | Frontier doctrine invariant — system MUST decide how much intelligence to spend (NOT just respond to every request with max-intelligence) | 10163 + 10165 | E0331 | non-negotiable | false | 10 |
| R05919 | Frontier doctrine invariant — 5 budget tiers covered by Profile System Layer 9 | 10168–10184 + 10305 | M00594 | non-negotiable | false | 10 |
| R05920 | Frontier doctrine invariant — 9 cognition profiles available (cheap reflex / careful thought / recursive context navigation / formal plan validation / tool execution / world simulation / memory retrieval / reward-guided search / human approval) | 10192–10202 | E0332 | non-negotiable | false | 10 |
| R05921 | Frontier doctrine invariant — programmable cognition is the architectural goal | 10204 | F02925 | non-negotiable | false | 10 |
| R05922 | New scaling law operationalization — AVX-512 bitset scheduler prototype is the priority work | 10368 | F02975 | non-negotiable | false | 10 |
| R05923 | New scaling law operationalization — Memory OS with temporal graph + replay is priority work | 10369 | F02975 | non-negotiable | false | 10 |
| R05924 | New scaling law operationalization — Tool sandbox + MCP security boundary is priority work | 10370 | F02975 | non-negotiable | false | 10 |
| R05925 | New scaling law operationalization — Cost/energy/intelligence budget profiles is priority work | 10371 | F02975 | non-negotiable | false | 10 |
| R05926 | Kernel-Law invariant — Models are userland (NOT the kernel; subject to scheduling and policy) | 10334 | F02972 | non-negotiable | false | 10 |
| R05927 | Kernel-Law invariant — Tools are devices (capability-gated; subject to permission bits) | 10335 | F02973 | non-negotiable | false | 10 |
| R05928 | Kernel-Law invariant — Memory is managed (kernel-allocated; subject to admission + decay) | 10336 + cross-ref M028 | F02974 | non-negotiable | false | 10 |
| R05929 | Kernel-Law invariant — Side effects are syscalls (typed Action contract; M030 World Model invariant) | 10337 + cross-ref M030 R05003–R05007 | F02974 | non-negotiable | false | 10 |
| R05930 | Kernel-Law invariant — Policies are permissions (M031 symbolic veto contract) | 10338 + cross-ref M031 R05225–R05227 | F02974 | non-negotiable | false | 10 |
| R05931 | Kernel-Law invariant — Replay is audit log (M029 mandatory replay + M033 per-request record) | 10339 + cross-ref M029 R04871 + M033 R05521–R05529 | F02974 | non-negotiable | false | 10 |
| R05932 | Kernel-Law invariant — Deterministic runtime is kernel space (M032 R05330 "Remote models propose. Local runtime commits.") | 10340 + cross-ref M032 R05330 | F02974 | non-negotiable | false | 10 |
| R05933 | Frontier integration with MS001 selfdef daemon core — daemon emits cost-ledger events to selfdef bus for cross-host correlation via MS015 NATS | MS001 + MS015 + 10248–10257 | M00584 | non-negotiable | false | 10 |
| R05934 | Frontier integration with MS002 collector fabric — selfdef-collector-eventstream may re-ingest cost-ledger events (metadata only, not prompt content) for incident correlation | MS002 + 10248–10257 | M00584 | non-negotiable | false | 10 |
| R05935 | Frontier integration with MS003 correlator — high-cost outlier events trigger correlator rules (e.g. tokens > threshold OR cloud-dollars > daily budget) | MS003 + 10248–10257 | M00584 | non-negotiable | false | 10 |
| R05936 | Frontier integration with MS006 agent-guard — agent-guard policy may rate-limit calls per profile tier (reflex unlimited; high-assurance must include human-gate) | MS006 + 10180–10181 | F02913 | non-negotiable | false | 10 |
| R05937 | Frontier integration with MS007 typed-mirror crates — Intelligence Budget tier schema + Stopping Rule schema + Cost Ledger schema mirrored cross-repo | MS007 + SDD-038 | M00578 + M00584 + M00585 | non-negotiable | false | 10 |
| R05938 | Frontier integration with MS010 hardware-aware modules — Layer 3 AVX-512 Cortex + Layer 8 Observability (DCGM) consume MS010 contracts | MS010 + 10287 + 10302 | M00588 + M00593 | non-negotiable | false | 10 |
| R05939 | Frontier integration with MS011 operator dashboard — dashboard MCP tab + Hardware tab show cost ledger + intelligence budget + stopping-rule status | MS011 + 10248–10276 | M00584 + M00585 | non-negotiable | false | 10 |
| R05940 | Frontier integration with MS012 perimeter coexistence — Layer 6 Execution Plane includes sandboxes governed by perimeter | MS012 + 10297 | M00591 | non-negotiable | false | 10 |
| R05941 | Frontier integration with MS013 27-SDD charter — Frontier doctrine has no dedicated SDD today; future SDD slot available if scope grows | MS013 + `docs/sdd/` ledger | E0328 | non-negotiable | false | 10 |
| R05942 | Frontier integration with MS014 SSH-wrap — ssh-wrap policy-strip events feed Layer 8 Observability cost ledger (tool retries dimension) | MS014 + 10255 | F02943 | non-negotiable | false | 10 |
| R05943 | Frontier integration with MS015 NATS messaging — cost-ledger events propagate via NATS bridge for fleet-wide cost tracking | MS015 + 10248–10257 | M00584 | non-negotiable | false | 10 |
| R05944 | Frontier integration with MS016 eBPF + Tetragon — Layer 8 Observability eBPF feed (selfdef.ebpf logsource); kernel events contribute to runtime cost-of-execution accounting | MS016 + 10302 | M00593 | non-negotiable | false | 10 |
| R05945 | Frontier doctrine — runtime makes the kernel-vs-userland separation explicit and enforceable | 10311–10343 | E0336 | non-negotiable | false | 10 |
| R05946 | Frontier doctrine — operator can OBSERVE the intelligence budget being spent (via dashboard) and INTERVENE (via profile change or human-gate) | 10248–10276 + MS011 + 10305 | M00584 + M00594 | non-negotiable | false | 10 |
| R05947 | Frontier doctrine — operator can REPLAY past runs to audit intelligence spending (via replay log) | 10324 + 10339 + cross-ref M029 R04871 | F02968 | non-negotiable | false | 10 |
| R05948 | Frontier doctrine — operator can EVOLVE the system over time (memory feedback + profile tuning + reward-model updates) | 10376 + cross-ref M028 + M027 | F02975 | non-negotiable | false | 10 |
| R05949 | Frontier doctrine summary — intelligence is "scheduled, measured, replayed, constrained, and evolved" | 10376 | F02975 | non-negotiable | false | 10 |
| R05950 | Composite — Frontier inference-time intelligence is the 15th plane (extending M027 8-plane stack + M028 Memory OS + M029 Computer-Use + M030 World Model + M031 Symbolic Planning + M032 Cloud Expert + M033 Compatibility Gateway + M034 Anthropic-first); 5-tier intelligence budget (reflex / deliberate / deep / autonomous / high-assurance); 9-dimension cost ledger; 5-rule stopping rule; 9-layer runtime shape; OS kernel analogy (processes/memory/devices/permissions/scheduling/syscalls/logs/drivers/security-rings); Kernel Law (Models=userland / Tools=devices / Memory=managed / Side effects=syscalls / Policies=permissions / Replay=audit log / Deterministic runtime=kernel space); hardware-fit (Zen 5 AVX-512 / Blackwell / 4090 / 256GB RAM / ZFS / API gateway); 8-front next-frontier list | 10109–10377 | E0328 + E0329 + E0330 + E0331 + E0332 + E0333 + E0334 + E0335 + E0336 + E0337 | non-negotiable | false | 10 |

## Cross-references

- Adjacent dump-range milestones: M034 Anthropic-first gateway (9958–10109) / M036 MAP — map-then-act paradigm (10378–10712)
- 9-layer Runtime Shape components: M025 cognitive compiler (Layer 2) / M026 SLM swarm + RLM engine (Layer 4 Model Fabric) / M027 Value Plane (Layer 9 Profile System reward integration) / M028 Memory OS (Layer 7) / M029 Computer-Use Plane (Layer 6 Execution Plane) / M030 World Model Plane (Layer 5) / M031 Symbolic Planning Plane (Layer 4+5 formal/verifier) / M032 Cloud Expert Plane (Layer 4 cloud experts) / M033 Compatibility Gateway + M034 Anthropic-first (Layer 1)
- Selfdef boundary: cost-ledger metadata flows into selfdef-collector-eventstream for incident correlation; agent-guard (MS006) may rate-limit calls per profile tier; MS007 typed mirrors carry Intelligence Budget + Stopping Rule + Cost Ledger schemas; NATS bridge (MS015) propagates cost-ledger events fleet-wide
- Kernel analogy doctrine — "the deterministic runtime is kernel space" (line 10340); selfdef (host defense) sits OUTSIDE the kernel as observability layer; sovereign-os IS the kernel
