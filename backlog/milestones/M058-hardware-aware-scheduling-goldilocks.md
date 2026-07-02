# M058 — Hardware-aware scheduling — the Goldilocks scheduler

**Parent**: sovereign-os runtime — AI workstation intelligence layer
**Source**: `~/infohub/raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 17914-18268 (Hardware-aware scheduling: Resource Types / Queue Types / Scheduling Policies / Blackwell / 4090 / CPU AVX / KV-Context / Memory / Tool / Backpressure / Objective / Concrete Example / Key Law)

## Doctrinal anchor

> "This is where the architecture becomes alive. The runtime should not simply execute tasks. It should schedule intelligence across the machine." (dump 17916-17918)

> "maximize useful intelligence per unit of: latency / cost / risk / energy / human attention / hardware pressure" (dump 18203-18209)

> "Never let expensive cognition wait on cheap preparation. Never let cheap speculation commit without expensive verification when risk demands it." (dump 18261-18264)

## Epics (E0558-E0567)

| epic | name | source |
|---|---|---|
| E0558 | Resource Types catalog — CPU/GPU-Blackwell/GPU-4090/RAM/NVMe-ZFS/Network/Human | dump 17920-17970 |
| E0559 | Queue Types catalog — 8 queues (oracle/scout/embedding/tool/eval/memory/human-gate/background) | dump 17972-17999 |
| E0560 | Scheduling Policies — 6 profile-specific policies (fast/careful/private/autonomous/experimental/production) | dump 18001-18030 |
| E0561 | Blackwell Scheduling — accept hard reasoning, avoid cheap classification | dump 18040-18060 |
| E0562 | 4090 Scheduling — work-ahead drafts/scouts/embeddings/rerank/vision | dump 18062-18095 |
| E0563 | CPU AVX Scheduling — batch hot operations, "batch when useful, don't worship SIMD" | dump 18097-18130 |
| E0564 | KV/Context Scheduling — prefix-cache awareness, prefill-vs-decode aware | dump 18132-18156 |
| E0565 | Memory + Tool Scheduling — staged retrieval + read-only-parallel + destructive-human-gate | dump 18158-18190 |
| E0566 | Backpressure — Linux PSI + DCGM + trace metrics feedback | dump 18192-18201 |
| E0567 | Goldilocks Objective + Key Law — "maximize useful intelligence per unit" | dump 18203-18264 |

## Modules (M00969-M00985)

| module | name | source |
|---|---|---|
| M00969 | sovereign-scheduler-resource-tracker | dump 17920-17970 |
| M00970 | sovereign-scheduler-queue-multiplexer | dump 17972-17999 |
| M00971 | sovereign-scheduler-policy-engine | dump 18001-18030 |
| M00972 | sovereign-scheduler-blackwell-arbitrator | dump 18040-18060 |
| M00973 | sovereign-scheduler-4090-prefetcher | dump 18062-18095 |
| M00974 | sovereign-scheduler-avx-batcher | dump 18097-18130 |
| M00975 | sovereign-scheduler-kv-cache-affinity | dump 18132-18156 |
| M00976 | sovereign-scheduler-memory-staged-retriever | dump 18158-18172 |
| M00977 | sovereign-scheduler-tool-classifier | dump 18174-18190 |
| M00978 | sovereign-scheduler-backpressure-controller | dump 18192-18201 |
| M00979 | sovereign-scheduler-psi-sensor | dump 18201 + cross-ref M045 |
| M00980 | sovereign-scheduler-dcgm-sensor | dump 18201 + cross-ref M048 |
| M00981 | sovereign-scheduler-goldilocks-objective | dump 18203-18209 |
| M00982 | sovereign-scheduler-key-law-enforcer | dump 18261-18264 |
| M00983 | sovereign-scheduler-concrete-decision-engine | dump 18213-18259 |
| M00984 | sovereign-scheduler-hibernation-bridge | dump 18254-18259 + cross-ref M047 |
| M00985 | sovereign-scheduler-typed-interface-bridge | cross-ref M054 |

## Features (F04846-F04930)

| feature | name | source |
|---|---|---|
| F04846 | CPU resource tracked: scalar cores | dump 17923 |
| F04847 | CPU resource tracked: AVX-512 lanes | dump 17924 |
| F04848 | CPU resource tracked: cache pressure | dump 17925 |
| F04849 | GPU Blackwell resource tracked: VRAM | dump 17928 |
| F04850 | GPU Blackwell resource tracked: compute | dump 17929 |
| F04851 | GPU Blackwell resource tracked: KV cache | dump 17930 |
| F04852 | GPU Blackwell resource tracked: batch slots | dump 17931 |
| F04853 | GPU 4090 resource tracked: VRAM | dump 17934 |
| F04854 | GPU 4090 resource tracked: compute | dump 17935 |
| F04855 | GPU 4090 resource tracked: sandbox availability | dump 17936 |
| F04856 | GPU 4090 resource tracked: draft/scout queues | dump 17937 |
| F04857 | RAM resource tracked: context arenas | dump 17940 |
| F04858 | RAM resource tracked: memory graph | dump 17941 |
| F04859 | RAM resource tracked: ZFS ARC | dump 17942 |
| F04860 | RAM resource tracked: active traces | dump 17943 |
| F04861 | NVMe/ZFS resource tracked: read/write bandwidth | dump 17946 |
| F04862 | NVMe/ZFS resource tracked: snapshot pressure | dump 17947 |
| F04863 | NVMe/ZFS resource tracked: replay writes | dump 17948 |
| F04864 | Network resource tracked: local LAN | dump 17951 |
| F04865 | Network resource tracked: internet/cloud | dump 17952 |
| F04866 | Network resource tracked: approved domains | dump 17953 |
| F04867 | Human resource tracked: approval attention | dump 17956 |
| F04868 | Human resource tracked: interruption budget | dump 17957 |
| F04869 | Human attention belongs in the scheduler (doctrinal) | dump 17970 |
| F04870 | Queue: oracle_queue — high-value model calls | dump 17974-17975 |
| F04871 | Queue: scout_queue — cheap drafts, classifiers, SLM | dump 17977-17978 |
| F04872 | Queue: embedding_queue — memory and retrieval | dump 17980-17981 |
| F04873 | Queue: tool_queue — shell, file, API, browser | dump 17983-17984 |
| F04874 | Queue: eval_queue — tests, judges, metrics | dump 17986-17987 |
| F04875 | Queue: memory_queue — read/write/promote/forget | dump 17989-17990 |
| F04876 | Queue: human_gate_queue — approvals and clarifications | dump 17992-17993 |
| F04877 | Queue: background_queue — compression, indexing, eval mining | dump 17995-17996 |
| F04878 | Queue item field: priority | dump 17999 |
| F04879 | Queue item field: deadline | dump 17999 |
| F04880 | Queue item field: risk | dump 17999 |
| F04881 | Queue item field: cost | dump 17999 |
| F04882 | Queue item field: expected value | dump 17999 |
| F04883 | Queue item field: profile | dump 17999 |
| F04884 | Queue item field: hardware affinity | dump 17999 |
| F04885 | Queue item field: cache affinity | dump 17999 |
| F04886 | Policy fast — favor latency, scout-first, shallow verification | dump 18003-18006 |
| F04887 | Policy careful — favor correctness, oracle verification, tests required | dump 18008-18011 |
| F04888 | Policy private — local-only, cloud routes disabled, strict memory exposure | dump 18013-18016 |
| F04889 | Policy autonomous — preserve continuity, batch approvals, sandbox-first, checkpoint often | dump 18018-18022 |
| F04890 | Policy experimental — wide branch search, sandbox only, no host commit | dump 18024-18027 |
| F04891 | Policy production — strict commit gates, low variance, strong observability | dump 18029-18032 |
| F04892 | Same request schedules differently under different profiles (doctrinal) | dump 18036 |
| F04893 | Blackwell accept: final synthesis | dump 18042 |
| F04894 | Blackwell accept: hard reasoning | dump 18043 |
| F04895 | Blackwell accept: high-risk verification | dump 18044 |
| F04896 | Blackwell accept: long-context parent calls | dump 18045 |
| F04897 | Blackwell accept: batch verification | dump 18046 |
| F04898 | Blackwell avoid: cheap classification | dump 18049 |
| F04899 | Blackwell avoid: trivial rewrites | dump 18050 |
| F04900 | Blackwell avoid: noisy branch expansion | dump 18051 |
| F04901 | Blackwell avoid: repeated boilerplate prefill | dump 18052 |
| F04902 | "Keep the Blackwell hot with meaningful work, not busy with junk." | dump 18056 |
| F04903 | 4090 use for: draft branches | dump 18065 |
| F04904 | 4090 use for: small models | dump 18066 |
| F04905 | 4090 use for: rerank | dump 18067 |
| F04906 | 4090 use for: embeddings | dump 18068 |
| F04907 | 4090 use for: vision/perception | dump 18069 |
| F04908 | 4090 use for: tool-plan sketches | dump 18070 |
| F04909 | 4090 use for: failure classification | dump 18071 |
| F04910 | 4090 work-ahead: idle + uncertain → generate candidate branches | dump 18078-18080 |
| F04911 | 4090 work-ahead: Blackwell busy → scout prepares summaries + verification candidates | dump 18082-18084 |
| F04912 | 4090 work-ahead: Blackwell idle → feed compressed high-value batch | dump 18086-18088 |
| F04913 | AVX hot ops: filter branches | dump 18101 |
| F04914 | AVX hot ops: score candidates | dump 18102 |
| F04915 | AVX hot ops: match memory | dump 18103 |
| F04916 | AVX hot ops: merge policy | dump 18104 |
| F04917 | AVX hot ops: detect duplicates | dump 18105 |
| F04918 | AVX hot ops: compress queues | dump 18106 |
| F04919 | AVX hot ops: apply budgets | dump 18107 |
| F04920 | AVX hot ops: compute route masks | dump 18108 |
| F04921 | AVX rule: "batch when useful, don't worship SIMD" | dump 18118 |
| F04922 | KV scheduling: prefix-cache awareness | dump 18137-18138 |
| F04923 | KV scheduling: parent context sharing | dump 18141 |
| F04924 | KV scheduling: prefill-vs-decode classification | dump 18142 |
| F04925 | KV scheduling: eviction-value calculation | dump 18143 |
| F04926 | Memory staged retrieval: bitset → popcount → embedding → graph → oracle | dump 18162-18170 |
| F04927 | Tool scheduling: read-only parallel, write snapshot/policy, network profile, destructive human-gate | dump 18176-18190 |
| F04928 | Backpressure: PSI + DCGM + trace metrics feed scheduler | dump 18201 |
| F04929 | Goldilocks Objective: maximize useful intelligence per unit | dump 18203-18209 |
| F04930 | Key Law: never let expensive wait on cheap; never let cheap commit without expensive when risk demands | dump 18261-18264 |

## Requirements (R09691-R09860)

| req | description | source | feature | priority | exception | sub-reqs |
|---|---|---|---|---|---|---|
| R09691 | Doctrinal — runtime schedules intelligence, not just executes tasks | dump 17916-17918 | F04929 | non-negotiable | false | 10 |
| R09692 | Doctrinal — human attention belongs in the scheduler | dump 17970 | F04867 | non-negotiable | false | 10 |
| R09693 | Doctrinal — "batch when useful, don't worship SIMD" | dump 18118 | F04921 | non-negotiable | false | 10 |
| R09694 | Doctrinal — keep Blackwell hot with meaningful work, not busy with junk | dump 18056 | F04902 | non-negotiable | false | 10 |
| R09695 | Doctrinal — 4090 should work ahead | dump 18074 | F04910 | non-negotiable | false | 10 |
| R09696 | Doctrinal — the CPU decides | dump 18099 | F04913 | non-negotiable | false | 10 |
| R09697 | Doctrinal — do not throw every memory query at a model | dump 18172 | F04926 | non-negotiable | false | 10 |
| R09698 | Doctrinal — tools are slow and risky compared to pure logic | dump 18175 | F04927 | non-negotiable | false | 10 |
| R09699 | Doctrinal — Goldilocks scheduler maximizes useful intelligence per unit | dump 18203-18209 | F04929 | non-negotiable | false | 10 |
| R09700 | Doctrinal — Key Scheduling Law (both halves) | dump 18261-18264 | F04930 | non-negotiable | false | 10 |
| R09701 | Resource — track CPU scalar cores | dump 17923 | F04846 | non-negotiable | false | 10 |
| R09702 | Resource — track CPU AVX-512 lanes | dump 17924 | F04847 | non-negotiable | false | 10 |
| R09703 | Resource — track CPU cache pressure | dump 17925 | F04848 | non-negotiable | false | 10 |
| R09704 | Resource — track Blackwell VRAM (96GB GDDR7) | dump 17928 | F04849 | non-negotiable | false | 10 |
| R09705 | Resource — track Blackwell compute (SM occupancy) | dump 17929 | F04850 | non-negotiable | false | 10 |
| R09706 | Resource — track Blackwell KV cache occupancy | dump 17930 | F04851 | non-negotiable | false | 10 |
| R09707 | Resource — track Blackwell batch slots | dump 17931 | F04852 | non-negotiable | false | 10 |
| R09708 | Resource — track 4090 VRAM (24GB GDDR6X) | dump 17934 | F04853 | non-negotiable | false | 10 |
| R09709 | Resource — track 4090 compute | dump 17935 | F04854 | non-negotiable | false | 10 |
| R09710 | Resource — track 4090 sandbox availability | dump 17936 | F04855 | non-negotiable | false | 10 |
| R09711 | Resource — track 4090 draft/scout queue depth | dump 17937 | F04856 | non-negotiable | false | 10 |
| R09712 | Resource — track RAM context arenas | dump 17940 | F04857 | non-negotiable | false | 10 |
| R09713 | Resource — track RAM memory graph footprint | dump 17941 | F04858 | non-negotiable | false | 10 |
| R09714 | Resource — track RAM ZFS ARC usage | dump 17942 | F04859 | non-negotiable | false | 10 |
| R09715 | Resource — track RAM active trace buffers | dump 17943 | F04860 | non-negotiable | false | 10 |
| R09716 | Resource — track NVMe/ZFS read bandwidth | dump 17946 | F04861 | non-negotiable | false | 10 |
| R09717 | Resource — track NVMe/ZFS write bandwidth | dump 17946 | F04861 | non-negotiable | false | 10 |
| R09718 | Resource — track ZFS snapshot pressure | dump 17947 | F04862 | non-negotiable | false | 10 |
| R09719 | Resource — track ZFS replay writes | dump 17948 | F04863 | non-negotiable | false | 10 |
| R09720 | Resource — track local LAN bandwidth | dump 17951 | F04864 | non-negotiable | false | 10 |
| R09721 | Resource — track internet/cloud egress bandwidth | dump 17952 | F04865 | non-negotiable | false | 10 |
| R09722 | Resource — track approved-domains active connections | dump 17953 | F04866 | non-negotiable | false | 10 |
| R09723 | Resource — track human approval attention budget | dump 17956 | F04867 | non-negotiable | false | 10 |
| R09724 | Resource — track human interruption budget | dump 17957 | F04868 | non-negotiable | false | 10 |
| R09725 | Queue — oracle_queue admits only high-value model calls | dump 17974-17975 | F04870 | non-negotiable | false | 10 |
| R09726 | Queue — scout_queue admits cheap drafts, classifiers, SLM calls | dump 17977-17978 | F04871 | non-negotiable | false | 10 |
| R09727 | Queue — embedding_queue admits memory and retrieval ops | dump 17980-17981 | F04872 | non-negotiable | false | 10 |
| R09728 | Queue — tool_queue admits shell, file, API, browser ops | dump 17983-17984 | F04873 | non-negotiable | false | 10 |
| R09729 | Queue — eval_queue admits tests, judges, metrics | dump 17986-17987 | F04874 | non-negotiable | false | 10 |
| R09730 | Queue — memory_queue admits read/write/promote/forget ops | dump 17989-17990 | F04875 | non-negotiable | false | 10 |
| R09731 | Queue — human_gate_queue admits approvals and clarifications | dump 17992-17993 | F04876 | non-negotiable | false | 10 |
| R09732 | Queue — background_queue admits compression, indexing, eval mining | dump 17995-17996 | F04877 | non-negotiable | false | 10 |
| R09733 | Queue item — carries priority field | dump 17999 | F04878 | non-negotiable | false | 10 |
| R09734 | Queue item — carries deadline field | dump 17999 | F04879 | non-negotiable | false | 10 |
| R09735 | Queue item — carries risk field | dump 17999 | F04880 | non-negotiable | false | 10 |
| R09736 | Queue item — carries cost field | dump 17999 | F04881 | non-negotiable | false | 10 |
| R09737 | Queue item — carries expected_value field | dump 17999 | F04882 | non-negotiable | false | 10 |
| R09738 | Queue item — carries profile field | dump 17999 | F04883 | non-negotiable | false | 10 |
| R09739 | Queue item — carries hardware_affinity field | dump 17999 | F04884 | non-negotiable | false | 10 |
| R09740 | Queue item — carries cache_affinity field | dump 17999 | F04885 | non-negotiable | false | 10 |
| R09741 | Policy fast — favor latency | dump 18003 | F04886 | non-negotiable | false | 10 |
| R09742 | Policy fast — scout-first routing | dump 18004 | F04886 | non-negotiable | false | 10 |
| R09743 | Policy fast — shallow verification | dump 18005 | F04886 | non-negotiable | false | 10 |
| R09744 | Policy careful — favor correctness | dump 18008 | F04887 | non-negotiable | false | 10 |
| R09745 | Policy careful — oracle verification required | dump 18009 | F04887 | non-negotiable | false | 10 |
| R09746 | Policy careful — tests required | dump 18010 | F04887 | non-negotiable | false | 10 |
| R09747 | Policy private — local-only routing | dump 18013 | F04888 | non-negotiable | false | 10 |
| R09748 | Policy private — cloud routes disabled | dump 18014 | F04888 | non-negotiable | false | 10 |
| R09749 | Policy private — strict memory exposure | dump 18015 | F04888 | non-negotiable | false | 10 |
| R09750 | Policy autonomous — preserve continuity | dump 18018 | F04889 | non-negotiable | false | 10 |
| R09751 | Policy autonomous — batch approvals | dump 18019 | F04889 | non-negotiable | false | 10 |
| R09752 | Policy autonomous — sandbox-first | dump 18020 | F04889 | non-negotiable | false | 10 |
| R09753 | Policy autonomous — checkpoint often | dump 18021 | F04889 | non-negotiable | false | 10 |
| R09754 | Policy experimental — wide branch search | dump 18024 | F04890 | non-negotiable | false | 10 |
| R09755 | Policy experimental — sandbox only | dump 18025 | F04890 | non-negotiable | false | 10 |
| R09756 | Policy experimental — no host commit | dump 18026 | F04890 | non-negotiable | false | 10 |
| R09757 | Policy production — strict commit gates | dump 18029 | F04891 | non-negotiable | false | 10 |
| R09758 | Policy production — low variance | dump 18030 | F04891 | non-negotiable | false | 10 |
| R09759 | Policy production — strong observability | dump 18031 | F04891 | non-negotiable | false | 10 |
| R09760 | Policy — same request schedules differently under different profiles | dump 18036 | F04892 | non-negotiable | false | 10 |
| R09761 | Blackwell accept — final synthesis | dump 18042 | F04893 | non-negotiable | false | 10 |
| R09762 | Blackwell accept — hard reasoning | dump 18043 | F04894 | non-negotiable | false | 10 |
| R09763 | Blackwell accept — high-risk verification | dump 18044 | F04895 | non-negotiable | false | 10 |
| R09764 | Blackwell accept — long-context parent calls | dump 18045 | F04896 | non-negotiable | false | 10 |
| R09765 | Blackwell accept — batch verification | dump 18046 | F04897 | non-negotiable | false | 10 |
| R09766 | Blackwell avoid — cheap classification | dump 18049 | F04898 | non-negotiable | false | 10 |
| R09767 | Blackwell avoid — trivial rewrites | dump 18050 | F04899 | non-negotiable | false | 10 |
| R09768 | Blackwell avoid — noisy branch expansion | dump 18051 | F04900 | non-negotiable | false | 10 |
| R09769 | Blackwell avoid — repeated boilerplate prefill | dump 18052 | F04901 | non-negotiable | false | 10 |
| R09770 | Blackwell — protect it (doctrinal directive) | dump 18040 | F04902 | non-negotiable | false | 10 |
| R09771 | 4090 use — draft branches | dump 18065 | F04903 | non-negotiable | false | 10 |
| R09772 | 4090 use — small models (SLM, draft models) | dump 18066 | F04904 | non-negotiable | false | 10 |
| R09773 | 4090 use — rerank | dump 18067 | F04905 | non-negotiable | false | 10 |
| R09774 | 4090 use — embeddings | dump 18068 | F04906 | non-negotiable | false | 10 |
| R09775 | 4090 use — vision/perception | dump 18069 | F04907 | non-negotiable | false | 10 |
| R09776 | 4090 use — tool-plan sketches | dump 18070 | F04908 | non-negotiable | false | 10 |
| R09777 | 4090 use — failure classification | dump 18071 | F04909 | non-negotiable | false | 10 |
| R09778 | 4090 — exploit it (doctrinal directive) | dump 18062 | F04902 | non-negotiable | false | 10 |
| R09779 | 4090 work-ahead — if idle and active task uncertain, generate candidate branches | dump 18078-18080 | F04910 | non-negotiable | false | 10 |
| R09780 | 4090 work-ahead — if Blackwell busy, scout prepares summaries + verification candidates | dump 18082-18084 | F04911 | non-negotiable | false | 10 |
| R09781 | 4090 work-ahead — if Blackwell idle, feed compressed high-value batch | dump 18086-18088 | F04912 | non-negotiable | false | 10 |
| R09782 | AVX hot op — filter branches | dump 18101 | F04913 | non-negotiable | false | 10 |
| R09783 | AVX hot op — score candidates | dump 18102 | F04914 | non-negotiable | false | 10 |
| R09784 | AVX hot op — match memory | dump 18103 | F04915 | non-negotiable | false | 10 |
| R09785 | AVX hot op — merge policy | dump 18104 | F04916 | non-negotiable | false | 10 |
| R09786 | AVX hot op — detect duplicates | dump 18105 | F04917 | non-negotiable | false | 10 |
| R09787 | AVX hot op — compress queues | dump 18106 | F04918 | non-negotiable | false | 10 |
| R09788 | AVX hot op — apply budgets | dump 18107 | F04919 | non-negotiable | false | 10 |
| R09789 | AVX hot op — compute route masks | dump 18108 | F04920 | non-negotiable | false | 10 |
| R09790 | AVX scheduler — used when enough items to batch | dump 18114-18116 | F04921 | non-negotiable | false | 10 |
| R09791 | AVX scheduler — for tiny requests, scalar is fine | dump 18116 | F04921 | non-negotiable | false | 10 |
| R09792 | KV scheduling — is prefix cached? | dump 18137 | F04922 | non-negotiable | false | 10 |
| R09793 | KV scheduling — is context already resident? | dump 18138 | F04922 | non-negotiable | false | 10 |
| R09794 | KV scheduling — can this branch share parent context? | dump 18141 | F04923 | non-negotiable | false | 10 |
| R09795 | KV scheduling — is the request decode-heavy or prefill-heavy? | dump 18142 | F04924 | non-negotiable | false | 10 |
| R09796 | KV scheduling — will this evict valuable KV? | dump 18143 | F04925 | non-negotiable | false | 10 |
| R09797 | KV routing — prefer reuse hot context | dump 18148 | F04922 | non-negotiable | false | 10 |
| R09798 | KV routing — avoid unnecessary prefill | dump 18149 | F04924 | non-negotiable | false | 10 |
| R09799 | KV routing — batch similar context shapes | dump 18150 | F04924 | non-negotiable | false | 10 |
| R09800 | KV routing — keep stable prefixes resident | dump 18151 | F04922 | non-negotiable | false | 10 |
| R09801 | Memory stage 1 — metadata bitset filter | dump 18162 | F04926 | non-negotiable | false | 10 |
| R09802 | Memory stage 2 — sketch/popcount relevance | dump 18163 | F04926 | non-negotiable | false | 10 |
| R09803 | Memory stage 3 — embedding/rerank | dump 18164 | F04926 | non-negotiable | false | 10 |
| R09804 | Memory stage 4 — graph expansion | dump 18165 | F04926 | non-negotiable | false | 10 |
| R09805 | Memory stage 5 — oracle synthesis only if needed | dump 18166 | F04926 | non-negotiable | false | 10 |
| R09806 | Tool — read-only tools can run early and parallel | dump 18177-18178 | F04927 | non-negotiable | false | 10 |
| R09807 | Tool — write tools require snapshot/policy | dump 18180-18181 | F04927 | non-negotiable | false | 10 |
| R09808 | Tool — network tools require profile permission | dump 18183-18184 | F04927 | non-negotiable | false | 10 |
| R09809 | Tool — long tests can run async, branch hibernates | dump 18186-18187 | F04927 | non-negotiable | false | 10 |
| R09810 | Tool — destructive tools require human gate | dump 18189-18190 | F04927 | non-negotiable | false | 10 |
| R09811 | Backpressure — Blackwell VRAM high → reduce context | dump 18194 | F04928 | non-negotiable | false | 10 |
| R09812 | Backpressure — Blackwell VRAM high → evict low-value KV | dump 18194 | F04928 | non-negotiable | false | 10 |
| R09813 | Backpressure — Blackwell VRAM high → switch smaller oracle | dump 18194 | F04928 | non-negotiable | false | 10 |
| R09814 | Backpressure — 4090 busy → reduce branch width | dump 18196 | F04928 | non-negotiable | false | 10 |
| R09815 | Backpressure — 4090 busy → use CPU classifiers | dump 18196 | F04928 | non-negotiable | false | 10 |
| R09816 | Backpressure — CPU pressure high → defer background indexing/evals | dump 18197 | F04928 | non-negotiable | false | 10 |
| R09817 | Backpressure — RAM pressure high → hibernate branches | dump 18198 | F04928 | non-negotiable | false | 10 |
| R09818 | Backpressure — RAM pressure high → compact memory | dump 18198 | F04928 | non-negotiable | false | 10 |
| R09819 | Backpressure — IO pressure high → delay cold scans | dump 18199 | F04928 | non-negotiable | false | 10 |
| R09820 | Backpressure — IO pressure high → avoid large snapshots | dump 18199 | F04928 | non-negotiable | false | 10 |
| R09821 | Backpressure — human gate queue high → batch approvals | dump 18200 | F04928 | non-negotiable | false | 10 |
| R09822 | Backpressure — human gate queue high → lower autonomy | dump 18200 | F04928 | non-negotiable | false | 10 |
| R09823 | Backpressure — Linux PSI feeds scheduler | dump 18201 + cross-ref M045 | F04928 | non-negotiable | false | 10 |
| R09824 | Backpressure — DCGM feeds scheduler | dump 18201 + cross-ref M048 | F04928 | non-negotiable | false | 10 |
| R09825 | Backpressure — trace metrics feed scheduler | dump 18201 + cross-ref M049 | F04928 | non-negotiable | false | 10 |
| R09826 | Objective — maximize useful intelligence per unit of latency | dump 18205 | F04929 | non-negotiable | false | 10 |
| R09827 | Objective — maximize useful intelligence per unit of cost | dump 18206 | F04929 | non-negotiable | false | 10 |
| R09828 | Objective — maximize useful intelligence per unit of risk | dump 18207 | F04929 | non-negotiable | false | 10 |
| R09829 | Objective — maximize useful intelligence per unit of energy | dump 18208 | F04929 | non-negotiable | false | 10 |
| R09830 | Objective — maximize useful intelligence per unit of human attention | dump 18209 | F04929 | non-negotiable | false | 10 |
| R09831 | Objective — maximize useful intelligence per unit of hardware pressure | dump 18209 | F04929 | non-negotiable | false | 10 |
| R09832 | Objective — explicitly NOT maximum throughput | dump 18203 | F04929 | non-negotiable | false | 10 |
| R09833 | Concrete example task — code bug | dump 18213 | F04929 | non-negotiable | false | 10 |
| R09834 | Concrete step 1 (Map) — CPU + tools inspect repo | dump 18215 | F04920 | non-negotiable | false | 10 |
| R09835 | Concrete step 2 (Draft) — 4090 produces 4 patch candidates | dump 18217 | F04903 | non-negotiable | false | 10 |
| R09836 | Concrete step 3 (Filter) — AVX checks touched paths, risk, duplicate edits | dump 18219 | F04913 | non-negotiable | false | 10 |
| R09837 | Concrete step 4 (Verify) — Blackwell reviews top 2 | dump 18221 | F04895 | non-negotiable | false | 10 |
| R09838 | Concrete step 5 (Test) — sandbox runs targeted tests | dump 18223 | F04874 | non-negotiable | false | 10 |
| R09839 | Concrete step 6 (Commit) — if pass, ZFS snapshot + apply | dump 18225 | F04862 | non-negotiable | false | 10 |
| R09840 | Concrete fallback — if Blackwell busy: 4090 generates more diagnostics | dump 18229 | F04911 | non-negotiable | false | 10 |
| R09841 | Concrete fallback — if Blackwell busy: CPU runs static checks | dump 18230 | F04913 | non-negotiable | false | 10 |
| R09842 | Concrete fallback — if Blackwell busy: memory retrieves similar failures | dump 18231 | F04915 | non-negotiable | false | 10 |
| R09843 | Concrete fallback — if tests slow: branch hibernates | dump 18234 | F04927 | non-negotiable | false | 10 |
| R09844 | Concrete fallback — if tests slow: other work proceeds | dump 18235 | F04877 | non-negotiable | false | 10 |
| R09845 | Concrete fallback — if tests slow: resume on test result | dump 18236 | F04927 | non-negotiable | false | 10 |
| R09846 | Key Law part 1 — never let expensive cognition wait on cheap preparation | dump 18261 | F04930 | non-negotiable | false | 10 |
| R09847 | Key Law part 2 — never let cheap speculation commit without expensive verification when risk demands | dump 18262-18264 | F04930 | non-negotiable | false | 10 |
| R09848 | Hardware reality — Ryzen 9 9900X Zen 5 AVX-512 substrate | architecture + cross-ref M044 | F04847 | non-negotiable | false | 10 |
| R09849 | Hardware reality — RTX PRO 6000 Blackwell 96GB GDDR7 FP4 substrate | architecture + cross-ref M044 | F04849 | non-negotiable | false | 10 |
| R09850 | Hardware reality — RTX 4090 24GB GDDR6X substrate | architecture + cross-ref M044 | F04853 | non-negotiable | false | 10 |
| R09851 | Hardware reality — 256GB DDR5 RAM substrate | architecture + cross-ref M044 | F04857 | non-negotiable | false | 10 |
| R09852 | Hardware reality — NVMe + ZFS substrate | architecture + cross-ref M044 | F04861 | non-negotiable | false | 10 |
| R09853 | Hardware reality — ProArt X870E-Creator 10GbE + 2.5GbE substrate | architecture + cross-ref M044 | F04864 | non-negotiable | false | 10 |
| R09854 | Cross-ref — scheduler consumes M053 11 build phases for state machine | cross-ref M053 | F04892 | non-negotiable | false | 10 |
| R09855 | Cross-ref — scheduler exposes 11 typed interfaces via M054 | cross-ref M054 | F04985 | non-negotiable | false | 10 |
| R09856 | Cross-ref — scheduler integrates with M055 10 failure-mode taxonomies | cross-ref M055 | F04930 | non-negotiable | false | 10 |
| R09857 | Cross-ref — scheduler respects M056 trust boundaries + authority levels | cross-ref M056 | F04891 | non-negotiable | false | 10 |
| R09858 | Cross-ref — scheduler emits M057 12-step lifecycle events | cross-ref M057 | F04891 | non-negotiable | false | 10 |
| R09859 | Cross-ref — scheduler hibernation hands off to M047 CRIU + ZFS continuity | cross-ref M047 | F04843 | non-negotiable | false | 10 |
| R09860 | Cross-ref — scheduler exposes typed mirror to selfdef IPS via MS007 8/8 SATURATED | cross-ref MS007 | F04985 | non-negotiable | false | 10 |

## Sub-requirements accounting

Every R-row carries 10 hard non-negotiable sub-requirements per operator standing direction. Total enforced sub-reqs = 170 R × 10 = **1,700 sub-requirements** for M058.

## Cross-references

- **M044** — sovereign-os substrate (Ryzen 9 9900X / Blackwell 96GB / 4090 24GB / 256GB RAM / NVMe ZFS / ProArt X870E)
- **M045** — Linux as intelligence governor (cgroup v2 / systemd / PSI / eBPF)
- **M046** — beat-the-cloud runtime adaptation + LoRA Foundry
- **M047** — continuity (CRIU + ZFS + warm sandboxes + hibernated thought)
- **M048** — modules map (Hardware Profiler / Compute Fabric / Sandbox Fabric / Memory OS)
- **M049** — continuity through observability + policy
- **M053** — implementation language (11 build phases)
- **M054** — 11 typed interfaces (Gateway / ProfileResolver / Router / ModelAdapter / Policy / Tool / Memory / Workflow / Eval / Observability / AVX Cortex)
- **M055** — failure modes (10 taxonomies + 5-step recovery)
- **M056** — trust boundaries + authority levels
- **M057** — data flow + 12-step task lifecycle
- **selfdef MS007** — typed-mirror crate scheme (cross-repo binding)
- **selfdef MS033** — policy + trace (scheduler reads policy bus decisions)
- **selfdef MS039** — authority levels + trust rings (scheduler honors L0..L6 + Ring 0..4)

## Schema

```
schema_version: "1.0.0"
milestone_id: M058
parent: sovereign-os
epics: 10
modules: 17
features: 85
requirements: 170
sub_requirements_per_requirement: 10
total_sub_requirements: 1700
source_dump_lines: 17914-18268
goldilocks_objective: maximize useful intelligence per unit
key_scheduling_law: |
  Never let expensive cognition wait on cheap preparation.
  Never let cheap speculation commit without expensive verification when risk demands it.
```
