# M043 — Bridge layer — hardware-aware intelligence scheduling

> Parent: `backlog/milestones/INDEX.md` row M043 (dump 12614–12944).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 12614–12944. Operator directive 12643: "Focus on your tasks. you are not here to define those files you are here to be the bridge between the hardware the tech and the real world and research and advancing".
> All entries below extract verbatim. No invention.

## Epics (E0408–E0417)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0408 | Re-centering — operator pulls AI back from filename-defining trajectory; "My job here is not to domesticate the vision into filenames too early; it is to keep bridging metal, models, systems research, and real operating consequences"; "Re-centered: the bridge is **hardware-aware intelligence scheduling**" | 12643 + 12656 + 12672 |
| E0409 | New serving research — "The newest serving research is screaming one thing: the frontier bottleneck is no longer only 'can the model reason?'"; 6 frontier questions: Where is the context? / Where is the KV cache? / Which hardware owns the next step? / Is this request prefill-heavy or decode-heavy? / Can we reuse prior work? / Is this worth oracle compute? | 12676–12690 |
| E0410 | External research anchors — NVIDIA Dynamo "KV-cache-aware routing" (docs.nvidia.com/dynamo/v-0-9-0/user-guides/kv-cache-aware-routing) + Ray Serve "prefill/decode disaggregation" (docs.ray.io/en/latest/serve/llm/architecture/serving-patterns/prefill-decode.html) + Together CPD "cache-aware disaggregated inference" (together.ai/blog/cache-aware-disaggregated-inference); "Together AI's CPD work claims cache-aware prefill/decode routing can improve long-context serving by routing around KV locality"; "That is extremely relevant" | 12692–12699 |
| E0411 | Cloud-vs-station translation — cloud/datacenter (5-layer: prefill pool / decode pool / KV transfer fabric / many GPUs / routing by cache locality) vs station (4-layer: Blackwell=resident oracle context+long-context verification+final synthesis / 4090=scout/draft/rerank/perception/sandbox / Ryzen AVX-512=route by task+risk+budget+prefix-cache availability+profile / RAM-ZFS=warm/cold context+replay+memory maps+artifacts); "Do not blindly copy datacenter disaggregation"; "Without NVLink/fabric, moving KV tensors around can become poison"; principle is gold (4 rules: route to where useful context already lives / avoid recomputing prefill / reuse stable prefixes / separate cheap exploration from expensive verification) | 12706–12734 |
| E0412 | Hyper feature — Context Residency (first-class runtime idea); 6 KV types resident: system prompt KV / tool schema KV / repo map KV / project policy KV / user preference KV / active task KV; "If Blackwell already has the right prefix hot, keep using it. If a branch only needs cheap exploration, send symbolic context to the 4090 instead. If context is cold, CPU decides whether prefill is worth it"; "This is how hardware becomes intelligence" | 12736–12758 |
| E0413 | Hyper feature — AVX-512 Routing Brain — CPU keeps hot metadata (10 fields: request_id / profile / risk / budget / model_role / context_hash / kv_ref / cache_hit_prob / expected_value / privacy_flags); bulk-evaluates (8 decisions: use_local / use_cloud / use_blackwell / use_4090 / use_sandbox / reuse_context / require_oracle / require_human); "That is the Goldilocks layer. Not too much compute, not too little. Exactly enough" | 12760–12792 |
| E0414 | Hyper feature — Blackwell As Context Sovereign — RTX PRO 6000 Blackwell official page (nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-6000) positions it for agentic AI and FP4 AI workloads; with 96GB VRAM real value is NOT just "bigger model" but 5 things: keep valuable context resident / verify branches in batches / host high-quality oracle model / run long-context synthesis / serve as final commit judge; "The Blackwell should not answer every tiny request. It should preserve the expensive mental state" | 12794–12814 |
| E0415 | Hyper feature — 4090 As Cognitive Scratchpad — 8 uses: draft branches / SLM workers / embeddings / rerankers / failure classifiers / GUI-perception models / sandboxed experiments / cheap RLM child calls; "It can be wrong. That is fine. The CPU filters. Blackwell verifies" | 12816–12832 |
| E0416 | Hyper feature — KV-Aware Profiles — profiles affect context policy (6 bundles): fast (shallow context + low prefill + scout-first) / careful (reuse project KV + oracle verification) / deep (MAP phase + long context + RLM recursion) / private (local-only + no cloud + strict memory exposure) / autonomous (persistent session + replay + rollback + evals) / experimental (sandboxed + wide branches + no auto-commit); "That is not 'mode fluff.' It changes hardware behavior" | 12834–12866 |
| E0417 | Bridge formula — "research concept → hardware policy → real user choice" with 2 examples (Research: KV-aware routing improves serving / Hardware policy: keep stable project context hot on Blackwell / User-visible choice: "Careful code mode" spends more VRAM/context to avoid repeated re-understanding; Research: prefill/decode disaggregation helps at scale / Hardware policy: do not move KV across weak links unless measured + emulate disaggregation by role separation instead / User-visible choice: "Fast scout mode" uses 4090 for drafts + Blackwell only for verification); Breakthrough line — "The machine's intelligence is not only in model weights. It is in **placement**" (6 placement dimensions: which thought lives where / which context stays hot / which branch gets verified / which memory gets promoted / which model gets trusted / which action gets committed); 8 things to care about (KV locality / prefix reuse / prefill cost / decode cost / cache hit rate / batch shape / context residency / hardware placement); living resource model (9 dimensions: compute / memory / KV / risk / cost / latency / privacy / reversibility / confidence); "That is how sovereignty becomes practical rather than decorative" | 12878–12940 |

## Modules (M00714–M00730)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00714 | Operator directive — "you are not here to define those files you are here to be the bridge between the hardware the tech and the real world and research and advancing" | 12643 | E0408 |
| M00715 | Bridge mandate — "hardware-aware intelligence scheduling" | 12672 | E0408 |
| M00716 | 6 frontier questions — context loc / KV cache loc / hardware owner / prefill-vs-decode / reuse / oracle compute | 12676–12690 | E0409 |
| M00717 | External research anchor — NVIDIA Dynamo KV-cache-aware routing | 12693 | E0410 |
| M00718 | External research anchor — Ray Serve prefill/decode disaggregation | 12693 | E0410 |
| M00719 | External research anchor — Together CPD cache-aware disaggregated inference | 12695 | E0410 |
| M00720 | Cloud reference architecture — 5-layer (prefill pool / decode pool / KV transfer fabric / many GPUs / routing by cache locality) | 12706–12712 | E0411 |
| M00721 | Station translation — 4-layer (Blackwell / 4090 / Ryzen AVX-512 / RAM-ZFS) | 12716–12728 | E0411 |
| M00722 | 4 principles — route to useful context + avoid recomputing prefill + reuse stable prefixes + separate cheap exploration from expensive verification | 12730–12734 | E0411 |
| M00723 | Context Residency hyper feature — 6 KV types resident (system prompt / tool schema / repo map / project policy / user pref / active task) | 12736–12752 | E0412 |
| M00724 | AVX-512 Routing Brain — 10 hot-metadata fields | 12762–12774 | E0413 |
| M00725 | AVX-512 Routing Brain — 8 bulk-eval decisions | 12778–12790 | E0413 |
| M00726 | Blackwell as Context Sovereign — 5 things (keep context resident / verify branches in batches / host oracle / long-context synthesis / final commit judge) | 12798–12810 | E0414 |
| M00727 | 4090 as Cognitive Scratchpad — 8 uses | 12818–12830 | E0415 |
| M00728 | KV-Aware Profiles — 6 bundles (fast / careful / deep / private / autonomous / experimental) | 12838–12862 | E0416 |
| M00729 | Bridge formula — research concept → hardware policy → real user choice (2 worked examples) | 12878–12908 | E0417 |
| M00730 | Living resource model — 9 dimensions (compute / memory / KV / risk / cost / latency / privacy / reversibility / confidence) + 6 placement dimensions + 8 care-about list | 12920–12940 | E0417 |

## Features (F03571–F03655)

| Feature ID | Phrase | Dump line | Parent module |
|---|---|---|---|
| F03571 | Operator's re-centering rebuke — "right to pull me back" | 12654 | E0408 |
| F03572 | AI self-correction — "My job here is not to domesticate the vision into filenames too early" | 12656 | E0408 |
| F03573 | AI self-correction — "to keep bridging metal, models, systems research, and real operating consequences" | 12656 | E0408 |
| F03574 | AI commitment — "I'll stay at that layer" | 12660 | E0408 |
| F03575 | Re-centering output — "the bridge is hardware-aware intelligence scheduling" | 12672 | M00715 |
| F03576 | Newest serving research — "screaming one thing" | 12676 | E0409 |
| F03577 | Frontier bottleneck — "no longer only 'can the model reason?'" | 12678 | E0409 |
| F03578 | Frontier question — Where is the context? | 12682 | M00716 |
| F03579 | Frontier question — Where is the KV cache? | 12683 | M00716 |
| F03580 | Frontier question — Which hardware owns the next step? | 12684 | M00716 |
| F03581 | Frontier question — Is this request prefill-heavy or decode-heavy? | 12685 | M00716 |
| F03582 | Frontier question — Can we reuse prior work? | 12686 | M00716 |
| F03583 | Frontier question — Is this worth oracle compute? | 12687 | M00716 |
| F03584 | NVIDIA Dynamo has KV-cache-aware routing | 12693 | M00717 |
| F03585 | Ray Serve documents prefill/decode disaggregation | 12693 | M00718 |
| F03586 | Together CPD — "cache-aware prefill/decode routing can improve long-context serving by routing around KV locality" | 12695 | M00719 |
| F03587 | "That is extremely relevant" | 12699 | E0410 |
| F03588 | Cloud version — prefill pool | 12707 | M00720 |
| F03589 | Cloud version — decode pool | 12708 | M00720 |
| F03590 | Cloud version — KV transfer fabric | 12709 | M00720 |
| F03591 | Cloud version — many GPUs | 12710 | M00720 |
| F03592 | Cloud version — routing by cache locality | 12711 | M00720 |
| F03593 | Station — Blackwell role = resident oracle context + long-context verification + final synthesis | 12717–12719 | M00721 |
| F03594 | Station — 4090 role = scout/draft/rerank/perception/sandbox | 12720–12722 | M00721 |
| F03595 | Station — Ryzen AVX-512 role = route by task + risk + budget + prefix/cache availability + profile | 12723–12726 | M00721 |
| F03596 | Station — RAM/ZFS role = warm/cold context + replay + memory maps + artifacts | 12727–12729 | M00721 |
| F03597 | "Do not blindly copy datacenter disaggregation" | 12731 | E0411 |
| F03598 | "Without NVLink/fabric, moving KV tensors around can become poison" | 12732 | E0411 |
| F03599 | Principle — route to where useful context already lives | 12734 | M00722 |
| F03600 | Principle — avoid recomputing prefill | 12734 | M00722 |
| F03601 | Principle — reuse stable prefixes | 12734 | M00722 |
| F03602 | Principle — separate cheap exploration from expensive verification | 12734 | M00722 |
| F03603 | Hyper feature header — Context Residency | 12736 | E0412 |
| F03604 | Context Residency — "first-class runtime idea" | 12738 | E0412 |
| F03605 | KV type resident — system prompt KV | 12742 | M00723 |
| F03606 | KV type resident — tool schema KV | 12743 | M00723 |
| F03607 | KV type resident — repo map KV | 12744 | M00723 |
| F03608 | KV type resident — project policy KV | 12745 | M00723 |
| F03609 | KV type resident — user preference KV | 12746 | M00723 |
| F03610 | KV type resident — active task KV | 12747 | M00723 |
| F03611 | Residency rule — "If Blackwell already has the right prefix hot, keep using it" | 12750 | M00723 |
| F03612 | Residency rule — "If a branch only needs cheap exploration, send symbolic context to the 4090 instead" | 12751 | M00723 |
| F03613 | Residency rule — "If context is cold, CPU decides whether prefill is worth it" | 12752 | M00723 |
| F03614 | Closing statement — "This is how hardware becomes intelligence" | 12758 | E0412 |
| F03615 | Hyper feature header — AVX-512 Routing Brain | 12760 | E0413 |
| F03616 | CPU keeps hot metadata (intro) | 12762 | M00724 |
| F03617 | Hot metadata field — request_id | 12764 | M00724 |
| F03618 | Hot metadata field — profile | 12765 | M00724 |
| F03619 | Hot metadata field — risk | 12766 | M00724 |
| F03620 | Hot metadata field — budget | 12767 | M00724 |
| F03621 | Hot metadata field — model_role | 12768 | M00724 |
| F03622 | Hot metadata field — context_hash | 12769 | M00724 |
| F03623 | Hot metadata field — kv_ref | 12770 | M00724 |
| F03624 | Hot metadata field — cache_hit_prob | 12771 | M00724 |
| F03625 | Hot metadata field — expected_value | 12772 | M00724 |
| F03626 | Hot metadata field — privacy_flags | 12773 | M00724 |
| F03627 | Bulk-eval decision — use_local | 12780 | M00725 |
| F03628 | Bulk-eval decision — use_cloud | 12781 | M00725 |
| F03629 | Bulk-eval decision — use_blackwell | 12782 | M00725 |
| F03630 | Bulk-eval decision — use_4090 | 12783 | M00725 |
| F03631 | Bulk-eval decision — use_sandbox | 12784 | M00725 |
| F03632 | Bulk-eval decision — reuse_context | 12785 | M00725 |
| F03633 | Bulk-eval decision — require_oracle | 12786 | M00725 |
| F03634 | Bulk-eval decision — require_human | 12787 | M00725 |
| F03635 | Goldilocks layer — "Not too much compute, not too little. Exactly enough" | 12792 | E0413 |
| F03636 | Hyper feature header — Blackwell As Context Sovereign | 12794 | E0414 |
| F03637 | RTX PRO 6000 Blackwell official page — positions for agentic AI and FP4 AI workloads | 12796–12798 | E0414 |
| F03638 | Blackwell value NOT just "bigger model" | 12800 | E0414 |
| F03639 | Blackwell role — keep valuable context resident | 12804 | M00726 |
| F03640 | Blackwell role — verify branches in batches | 12805 | M00726 |
| F03641 | Blackwell role — host high-quality oracle model | 12806 | M00726 |
| F03642 | Blackwell role — run long-context synthesis | 12807 | M00726 |
| F03643 | Blackwell role — serve as final commit judge | 12808 | M00726 |
| F03644 | Blackwell mandate — "should not answer every tiny request" | 12812 | E0414 |
| F03645 | Blackwell mandate — "should preserve the expensive mental state" | 12814 | E0414 |
| F03646 | 4090 use — draft branches | 12820 | M00727 |
| F03647 | 4090 use — SLM workers | 12821 | M00727 |
| F03648 | 4090 use — embeddings | 12822 | M00727 |
| F03649 | 4090 use — rerankers | 12823 | M00727 |
| F03650 | 4090 use — failure classifiers | 12824 | M00727 |
| F03651 | 4090 use — GUI/perception models | 12825 | M00727 |
| F03652 | 4090 use — sandboxed experiments | 12826 | M00727 |
| F03653 | 4090 use — cheap RLM child calls | 12827 | M00727 |
| F03654 | 4090 doctrine — "It can be wrong. That is fine. The CPU filters. Blackwell verifies" | 12832 | E0415 |
| F03655 | KV-Aware Profiles header + 6 bundles + "not mode fluff. It changes hardware behavior" + Bridge formula 2 examples + Breakthrough placement line + 8 care-about items + 9-dimension resource model + "how sovereignty becomes practical rather than decorative" | 12834–12940 | M00728 + M00729 + M00730 + E0416 + E0417 |

## Requirements (R07141–R07310)

| Req ID | Phrase | Dump line | Parent feature | Negotiability | Layer-B metric | Priority |
|---|---|---|---|---|---|---|
| R07141 | Operator directive — "Focus on your tasks" | 12643 | F03571 | non-negotiable | false | 10 |
| R07142 | Operator directive — "you are not here to define those files" | 12643 | F03571 | non-negotiable | false | 10 |
| R07143 | Operator directive — "you are here to be the bridge between the hardware the tech and the real world and research and advancing" | 12643 | M00714 | non-negotiable | false | 10 |
| R07144 | AI re-centering — "You're right to pull me back" | 12654 | F03571 | non-negotiable | false | 10 |
| R07145 | AI re-centering — "not to domesticate the vision into filenames too early" | 12656 | F03572 | non-negotiable | false | 10 |
| R07146 | AI re-centering — "to keep bridging metal, models, systems research, and real operating consequences" | 12656 | F03573 | non-negotiable | false | 10 |
| R07147 | AI commitment — "I'll stay at that layer" | 12660 | F03574 | non-negotiable | false | 10 |
| R07148 | Re-centered phrase — "the bridge is hardware-aware intelligence scheduling" | 12672 | F03575 | non-negotiable | false | 10 |
| R07149 | Newest serving research — "screaming one thing" | 12676 | F03576 | non-negotiable | false | 10 |
| R07150 | Frontier bottleneck — "no longer only 'can the model reason?'" | 12678 | F03577 | non-negotiable | false | 10 |
| R07151 | Frontier question — Where is the context? | 12682 | F03578 | non-negotiable | false | 10 |
| R07152 | Frontier question — Where is the KV cache? | 12683 | F03579 | non-negotiable | false | 10 |
| R07153 | Frontier question — Which hardware owns the next step? | 12684 | F03580 | non-negotiable | false | 10 |
| R07154 | Frontier question — Is this request prefill-heavy or decode-heavy? | 12685 | F03581 | non-negotiable | false | 10 |
| R07155 | Frontier question — Can we reuse prior work? | 12686 | F03582 | non-negotiable | false | 10 |
| R07156 | Frontier question — Is this worth oracle compute? | 12687 | F03583 | non-negotiable | false | 10 |
| R07157 | NVIDIA Dynamo URL — docs.nvidia.com/dynamo/v-0-9-0/user-guides/kv-cache-aware-routing | 12693 | F03584 | non-negotiable | false | 10 |
| R07158 | Ray Serve URL — docs.ray.io/en/latest/serve/llm/architecture/serving-patterns/prefill-decode.html | 12693 | F03585 | non-negotiable | false | 10 |
| R07159 | Together CPD URL — together.ai/blog/cache-aware-disaggregated-inference | 12695 | F03586 | non-negotiable | false | 10 |
| R07160 | NVIDIA Dynamo has KV-cache-aware routing | 12693 | F03584 | non-negotiable | false | 10 |
| R07161 | Ray Serve has prefill/decode disaggregation | 12693 | F03585 | non-negotiable | false | 10 |
| R07162 | Together CPD claim — cache-aware prefill/decode routing improves long-context serving | 12695 | F03586 | non-negotiable | false | 10 |
| R07163 | Together CPD claim — routes around KV locality | 12695 | F03586 | non-negotiable | false | 10 |
| R07164 | "That is extremely relevant" | 12699 | F03587 | non-negotiable | false | 10 |
| R07165 | Cloud version — prefill pool | 12707 | F03588 | non-negotiable | false | 10 |
| R07166 | Cloud version — decode pool | 12708 | F03589 | non-negotiable | false | 10 |
| R07167 | Cloud version — KV transfer fabric | 12709 | F03590 | non-negotiable | false | 10 |
| R07168 | Cloud version — many GPUs | 12710 | F03591 | non-negotiable | false | 10 |
| R07169 | Cloud version — routing by cache locality | 12711 | F03592 | non-negotiable | false | 10 |
| R07170 | Station — Blackwell = resident oracle context | 12717 | F03593 | non-negotiable | false | 10 |
| R07171 | Station — Blackwell = long-context verification | 12718 | F03593 | non-negotiable | false | 10 |
| R07172 | Station — Blackwell = final synthesis | 12719 | F03593 | non-negotiable | false | 10 |
| R07173 | Station — 4090 = scout | 12720 | F03594 | non-negotiable | false | 10 |
| R07174 | Station — 4090 = draft | 12720 | F03594 | non-negotiable | false | 10 |
| R07175 | Station — 4090 = rerank | 12721 | F03594 | non-negotiable | false | 10 |
| R07176 | Station — 4090 = perception | 12721 | F03594 | non-negotiable | false | 10 |
| R07177 | Station — 4090 = sandbox | 12722 | F03594 | non-negotiable | false | 10 |
| R07178 | Station — Ryzen AVX-512 = route by task | 12723 | F03595 | non-negotiable | false | 10 |
| R07179 | Station — Ryzen AVX-512 = route by risk | 12724 | F03595 | non-negotiable | false | 10 |
| R07180 | Station — Ryzen AVX-512 = route by budget | 12725 | F03595 | non-negotiable | false | 10 |
| R07181 | Station — Ryzen AVX-512 = route by prefix/cache availability | 12725 | F03595 | non-negotiable | false | 10 |
| R07182 | Station — Ryzen AVX-512 = route by profile | 12726 | F03595 | non-negotiable | false | 10 |
| R07183 | Station — RAM/ZFS = warm/cold context | 12727 | F03596 | non-negotiable | false | 10 |
| R07184 | Station — RAM/ZFS = replay | 12728 | F03596 | non-negotiable | false | 10 |
| R07185 | Station — RAM/ZFS = memory maps | 12728 | F03596 | non-negotiable | false | 10 |
| R07186 | Station — RAM/ZFS = artifacts | 12729 | F03596 | non-negotiable | false | 10 |
| R07187 | "Do not blindly copy datacenter disaggregation" | 12731 | F03597 | non-negotiable | false | 10 |
| R07188 | "Without NVLink/fabric, moving KV tensors around can become poison" | 12732 | F03598 | non-negotiable | false | 10 |
| R07189 | Principle — route to where useful context already lives | 12734 | F03599 | non-negotiable | false | 10 |
| R07190 | Principle — avoid recomputing prefill | 12734 | F03600 | non-negotiable | false | 10 |
| R07191 | Principle — reuse stable prefixes | 12734 | F03601 | non-negotiable | false | 10 |
| R07192 | Principle — separate cheap exploration from expensive verification | 12734 | F03602 | non-negotiable | false | 10 |
| R07193 | Hyper feature label — Context Residency | 12736 | F03603 | non-negotiable | false | 10 |
| R07194 | Context Residency is "first-class runtime idea" | 12738 | F03604 | non-negotiable | false | 10 |
| R07195 | KV resident type — system prompt KV | 12742 | F03605 | non-negotiable | false | 10 |
| R07196 | KV resident type — tool schema KV | 12743 | F03606 | non-negotiable | false | 10 |
| R07197 | KV resident type — repo map KV | 12744 | F03607 | non-negotiable | false | 10 |
| R07198 | KV resident type — project policy KV | 12745 | F03608 | non-negotiable | false | 10 |
| R07199 | KV resident type — user preference KV | 12746 | F03609 | non-negotiable | false | 10 |
| R07200 | KV resident type — active task KV | 12747 | F03610 | non-negotiable | false | 10 |
| R07201 | Residency rule — "If Blackwell already has the right prefix hot, keep using it" | 12750 | F03611 | non-negotiable | false | 10 |
| R07202 | Residency rule — "If a branch only needs cheap exploration, send symbolic context to the 4090 instead" | 12751 | F03612 | non-negotiable | false | 10 |
| R07203 | Residency rule — "If context is cold, CPU decides whether prefill is worth it" | 12752 | F03613 | non-negotiable | false | 10 |
| R07204 | Statement — "This is how hardware becomes intelligence" | 12758 | F03614 | non-negotiable | false | 10 |
| R07205 | Hyper feature label — AVX-512 Routing Brain | 12760 | F03615 | non-negotiable | false | 10 |
| R07206 | CPU keeps hot metadata | 12762 | F03616 | non-negotiable | false | 10 |
| R07207 | Hot metadata field — request_id | 12764 | F03617 | non-negotiable | false | 10 |
| R07208 | Hot metadata field — profile | 12765 | F03618 | non-negotiable | false | 10 |
| R07209 | Hot metadata field — risk | 12766 | F03619 | non-negotiable | false | 10 |
| R07210 | Hot metadata field — budget | 12767 | F03620 | non-negotiable | false | 10 |
| R07211 | Hot metadata field — model_role | 12768 | F03621 | non-negotiable | false | 10 |
| R07212 | Hot metadata field — context_hash | 12769 | F03622 | non-negotiable | false | 10 |
| R07213 | Hot metadata field — kv_ref | 12770 | F03623 | non-negotiable | false | 10 |
| R07214 | Hot metadata field — cache_hit_prob | 12771 | F03624 | non-negotiable | false | 10 |
| R07215 | Hot metadata field — expected_value | 12772 | F03625 | non-negotiable | false | 10 |
| R07216 | Hot metadata field — privacy_flags | 12773 | F03626 | non-negotiable | false | 10 |
| R07217 | CPU bulk-evaluates decisions | 12777 | M00725 | non-negotiable | false | 10 |
| R07218 | Bulk-eval decision — use_local | 12780 | F03627 | non-negotiable | false | 10 |
| R07219 | Bulk-eval decision — use_cloud | 12781 | F03628 | non-negotiable | false | 10 |
| R07220 | Bulk-eval decision — use_blackwell | 12782 | F03629 | non-negotiable | false | 10 |
| R07221 | Bulk-eval decision — use_4090 | 12783 | F03630 | non-negotiable | false | 10 |
| R07222 | Bulk-eval decision — use_sandbox | 12784 | F03631 | non-negotiable | false | 10 |
| R07223 | Bulk-eval decision — reuse_context | 12785 | F03632 | non-negotiable | false | 10 |
| R07224 | Bulk-eval decision — require_oracle | 12786 | F03633 | non-negotiable | false | 10 |
| R07225 | Bulk-eval decision — require_human | 12787 | F03634 | non-negotiable | false | 10 |
| R07226 | "That is the Goldilocks layer" | 12790 | F03635 | non-negotiable | false | 10 |
| R07227 | Goldilocks rule — "Not too much compute, not too little. Exactly enough" | 12792 | F03635 | non-negotiable | false | 10 |
| R07228 | Hyper feature label — Blackwell As Context Sovereign | 12794 | F03636 | non-negotiable | false | 10 |
| R07229 | RTX PRO 6000 Blackwell URL — nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-6000 | 12798 | F03637 | non-negotiable | false | 10 |
| R07230 | Blackwell positioned for agentic AI | 12798 | F03637 | non-negotiable | false | 10 |
| R07231 | Blackwell positioned for FP4 AI workloads | 12798 | F03637 | non-negotiable | false | 10 |
| R07232 | Blackwell has 96GB VRAM | 12800 | E0414 | non-negotiable | false | 10 |
| R07233 | Blackwell value NOT just "bigger model" | 12800 | F03638 | non-negotiable | false | 10 |
| R07234 | Blackwell role — keep valuable context resident | 12804 | F03639 | non-negotiable | false | 10 |
| R07235 | Blackwell role — verify branches in batches | 12805 | F03640 | non-negotiable | false | 10 |
| R07236 | Blackwell role — host high-quality oracle model | 12806 | F03641 | non-negotiable | false | 10 |
| R07237 | Blackwell role — run long-context synthesis | 12807 | F03642 | non-negotiable | false | 10 |
| R07238 | Blackwell role — serve as final commit judge | 12808 | F03643 | non-negotiable | false | 10 |
| R07239 | Blackwell mandate — "should not answer every tiny request" | 12812 | F03644 | non-negotiable | false | 10 |
| R07240 | Blackwell mandate — "should preserve the expensive mental state" | 12814 | F03645 | non-negotiable | false | 10 |
| R07241 | Hyper feature label — 4090 As Cognitive Scratchpad | 12816 | E0415 | non-negotiable | false | 10 |
| R07242 | 4090 use — draft branches | 12820 | F03646 | non-negotiable | false | 10 |
| R07243 | 4090 use — SLM workers | 12821 | F03647 | non-negotiable | false | 10 |
| R07244 | 4090 use — embeddings | 12822 | F03648 | non-negotiable | false | 10 |
| R07245 | 4090 use — rerankers | 12823 | F03649 | non-negotiable | false | 10 |
| R07246 | 4090 use — failure classifiers | 12824 | F03650 | non-negotiable | false | 10 |
| R07247 | 4090 use — GUI/perception models | 12825 | F03651 | non-negotiable | false | 10 |
| R07248 | 4090 use — sandboxed experiments | 12826 | F03652 | non-negotiable | false | 10 |
| R07249 | 4090 use — cheap RLM child calls | 12827 | F03653 | non-negotiable | false | 10 |
| R07250 | 4090 doctrine — "It can be wrong. That is fine" | 12832 | F03654 | non-negotiable | false | 10 |
| R07251 | 4090 doctrine — "The CPU filters. Blackwell verifies" | 12832 | F03654 | non-negotiable | false | 10 |
| R07252 | Hyper feature label — KV-Aware Profiles | 12834 | M00728 | non-negotiable | false | 10 |
| R07253 | Profile fast — shallow context | 12840 | M00728 | non-negotiable | false | 10 |
| R07254 | Profile fast — low prefill | 12840 | M00728 | non-negotiable | false | 10 |
| R07255 | Profile fast — scout-first | 12841 | M00728 | non-negotiable | false | 10 |
| R07256 | Profile careful — reuse project KV | 12844 | M00728 | non-negotiable | false | 10 |
| R07257 | Profile careful — oracle verification | 12845 | M00728 | non-negotiable | false | 10 |
| R07258 | Profile deep — MAP phase | 12848 | M00728 | non-negotiable | false | 10 |
| R07259 | Profile deep — long context | 12849 | M00728 | non-negotiable | false | 10 |
| R07260 | Profile deep — RLM recursion | 12850 | M00728 | non-negotiable | false | 10 |
| R07261 | Profile private — local-only | 12853 | M00728 | non-negotiable | false | 10 |
| R07262 | Profile private — no cloud | 12854 | M00728 | non-negotiable | false | 10 |
| R07263 | Profile private — strict memory exposure | 12855 | M00728 | non-negotiable | false | 10 |
| R07264 | Profile autonomous — persistent session | 12858 | M00728 | non-negotiable | false | 10 |
| R07265 | Profile autonomous — replay | 12859 | M00728 | non-negotiable | false | 10 |
| R07266 | Profile autonomous — rollback | 12860 | M00728 | non-negotiable | false | 10 |
| R07267 | Profile autonomous — evals | 12860 | M00728 | non-negotiable | false | 10 |
| R07268 | Profile experimental — sandboxed | 12862 | M00728 | non-negotiable | false | 10 |
| R07269 | Profile experimental — wide branches | 12863 | M00728 | non-negotiable | false | 10 |
| R07270 | Profile experimental — no auto-commit | 12864 | M00728 | non-negotiable | false | 10 |
| R07271 | KV-aware profiles — "not mode fluff" | 12866 | E0416 | non-negotiable | false | 10 |
| R07272 | KV-aware profiles — "changes hardware behavior" | 12866 | E0416 | non-negotiable | false | 10 |
| R07273 | Bridge formula — research concept → hardware policy → real user choice | 12878 | M00729 | non-negotiable | false | 10 |
| R07274 | Bridge example 1 — Research: KV-aware routing improves serving | 12882 | M00729 | non-negotiable | false | 10 |
| R07275 | Bridge example 1 — Hardware policy: keep stable project context hot on Blackwell | 12884 | M00729 | non-negotiable | false | 10 |
| R07276 | Bridge example 1 — User choice: "Careful code mode" spends more VRAM/context to avoid repeated re-understanding | 12886 | M00729 | non-negotiable | false | 10 |
| R07277 | Bridge example 2 — Research: prefill/decode disaggregation helps at scale | 12892 | M00729 | non-negotiable | false | 10 |
| R07278 | Bridge example 2 — Hardware policy: do not move KV across weak links unless measured | 12894 | M00729 | non-negotiable | false | 10 |
| R07279 | Bridge example 2 — Hardware policy: emulate disaggregation by role separation instead | 12895 | M00729 | non-negotiable | false | 10 |
| R07280 | Bridge example 2 — User choice: "Fast scout mode" uses 4090 for drafts, Blackwell only for verification | 12897 | M00729 | non-negotiable | false | 10 |
| R07281 | Breakthrough line — "machine's intelligence is not only in model weights. It is in placement" | 12906 | E0417 | non-negotiable | false | 10 |
| R07282 | Placement dimension — which thought lives where | 12910 | E0417 | non-negotiable | false | 10 |
| R07283 | Placement dimension — which context stays hot | 12911 | E0417 | non-negotiable | false | 10 |
| R07284 | Placement dimension — which branch gets verified | 12912 | E0417 | non-negotiable | false | 10 |
| R07285 | Placement dimension — which memory gets promoted | 12913 | E0417 | non-negotiable | false | 10 |
| R07286 | Placement dimension — which model gets trusted | 12914 | E0417 | non-negotiable | false | 10 |
| R07287 | Placement dimension — which action gets committed | 12915 | E0417 | non-negotiable | false | 10 |
| R07288 | "That is the bridge between hardware, tech, research, and real-world use" | 12918 | E0417 | non-negotiable | false | 10 |
| R07289 | Care-about — KV locality | 12922 | M00730 | non-negotiable | false | 10 |
| R07290 | Care-about — prefix reuse | 12923 | M00730 | non-negotiable | false | 10 |
| R07291 | Care-about — prefill cost | 12924 | M00730 | non-negotiable | false | 10 |
| R07292 | Care-about — decode cost | 12925 | M00730 | non-negotiable | false | 10 |
| R07293 | Care-about — cache hit rate | 12926 | M00730 | non-negotiable | false | 10 |
| R07294 | Care-about — batch shape | 12927 | M00730 | non-negotiable | false | 10 |
| R07295 | Care-about — context residency | 12928 | M00730 | non-negotiable | false | 10 |
| R07296 | Care-about — hardware placement | 12929 | M00730 | non-negotiable | false | 10 |
| R07297 | Resource model dimension — compute | 12932 | M00730 | non-negotiable | false | 10 |
| R07298 | Resource model dimension — memory | 12933 | M00730 | non-negotiable | false | 10 |
| R07299 | Resource model dimension — KV | 12934 | M00730 | non-negotiable | false | 10 |
| R07300 | Resource model dimension — risk | 12935 | M00730 | non-negotiable | false | 10 |
| R07301 | Resource model dimension — cost | 12936 | M00730 | non-negotiable | false | 10 |
| R07302 | Resource model dimension — latency | 12937 | M00730 | non-negotiable | false | 10 |
| R07303 | Resource model dimension — privacy | 12938 | M00730 | non-negotiable | false | 10 |
| R07304 | Resource model dimension — reversibility | 12939 | M00730 | non-negotiable | false | 10 |
| R07305 | Resource model dimension — confidence | 12940 | M00730 | non-negotiable | false | 10 |
| R07306 | "That is how sovereignty becomes practical rather than decorative" | 12940 | E0417 | non-negotiable | false | 10 |
| R07307 | "Your projects can expose infinite choice, yes. But underneath those choices, the station needs a living resource model" | 12920 | M00730 | non-negotiable | false | 10 |
| R07308 | External research — heterogeneous LLM serving CPU GPU scheduling KV cache routing agent systems (2026 search) | 12692 | E0410 | non-negotiable | false | 10 |
| R07309 | AVX-512 Routing Brain serves as the Goldilocks router; the 8 bulk-eval decisions are the per-request output of the AVX cortex hot path (M039 extension to runtime) | 12790 + cross-ref M039 | M00725 | non-negotiable | false | 10 |
| R07310 | Composite — M043 (10 epics / 17 modules / 85 features / 170 reqs) catalogs the bridge layer = hardware-aware intelligence scheduling: 6 frontier questions + 3 external research anchors (NVIDIA Dynamo + Ray Serve + Together CPD) + cloud-vs-station translation (5-layer vs 4-layer) + 4 datacenter-disaggregation principles + Context Residency hyper feature (6 KV types + 3 residency rules + "hardware becomes intelligence") + AVX-512 Routing Brain hyper feature (10 hot-metadata fields + 8 bulk-eval decisions + Goldilocks layer) + Blackwell Context Sovereign hyper feature (5 roles + "preserve the expensive mental state") + 4090 Cognitive Scratchpad hyper feature (8 uses + "CPU filters Blackwell verifies") + KV-Aware Profiles hyper feature (6 bundles + "changes hardware behavior") + bridge formula (research → hardware policy → user choice + 2 worked examples) + Breakthrough placement line (6 placement dimensions) + 8 care-about items + 9-dimension living resource model + "sovereignty becomes practical rather than decorative" | 12614–12944 | E0408-E0417 | non-negotiable | false | 10 |

## Sub-requirements accounting

- 170 requirements covering: operator re-centering rebuke (R07141–R07148) + 6 frontier questions (R07149–R07156) + 3 external research URLs + claims (R07157–R07164) + cloud 5-layer vs station 4-layer (R07165–R07186) + 2 cautions + 4 principles (R07187–R07192) + Context Residency hyper feature + 6 KV types + 3 residency rules + closing (R07193–R07204) + AVX-512 Routing Brain + 10 hot-metadata fields + 8 bulk-eval decisions + Goldilocks (R07205–R07227) + Blackwell Context Sovereign + URL + 5 roles + 2 mandates (R07228–R07240) + 4090 Cognitive Scratchpad + 8 uses + doctrine (R07241–R07251) + 6 KV-aware profiles + "not mode fluff" (R07252–R07272) + bridge formula + 2 examples (R07273–R07280) + breakthrough placement + 6 dimensions + closing (R07281–R07288) + 8 care-about + 9-dimension resource model + sovereignty (R07289–R07307) + research-anchor cross-ref + composite (R07308–R07310)
- Source range 12614–12944 yields 330 lines; 170 R-rows represent ~52% line-coverage at the verbatim-citation level (web-search trace lines + redundant operator re-prompt echo excluded)
- Project boundary — M043 is sovereign-os runtime scheduler/scheduling-policy scope; selfdef does NOT own intelligence scheduling (its scope is host-defense/IPS surface); cross-repo binding via MS007 typed-mirror crates if hardware-policy schemas need IPS-side audit

## Cross-references

- Adjacent dump-range milestones: M042 choice architecture (12094–12614) / M044 Sovereign-OS substrate Debian-13 Ubuntu-24 (dump 13307–13546; gap 12944–13307 likely covered by M043 backward-sweep)
- Plane integration — M043 supersedes/extends M039 AVX-512 cortex hot path (AVX cortex now serves as the 8-bulk-eval-decision Goldilocks router); M040 hyper features (4 new hyper features added: Context Residency / AVX-512 Routing Brain / Blackwell Context Sovereign / 4090 Cognitive Scratchpad / KV-Aware Profiles); M025 Cognitive Compiler (compiles bridge-formula research→hardware→user-choice into DAG); M026 SLM swarm + M027 Value Plane (4090 hosts SLM workers; reward vector influences require_oracle decision); M028 Memory OS (KV resident types align with Memory Plane); M032 Cloud Expert Plane (use_cloud bulk-eval decision); M035 Frontier inference-time intelligence (Blackwell-as-context-sovereign extends Frontier 9-layer Runtime Shape); M042 Choice Architecture (KV-aware profiles + bridge formula realize choice envelopes in hardware)
- Cross-repo binding — bridge formula research→hardware-policy→user-choice may surface via MS007 surface-manifest typed-mirror crate (the user-choice layer is the operator-facing dashboard surface)
- Hardware reality — Ryzen 9 9900X Zen 5 AVX-512 + RTX PRO 6000 Blackwell 96GB GDDR7 + RTX 4090 24GB + ProArt X870E-Creator + ZFS + 10GbE+2.5GbE; this is the substrate on which the 4-layer station model executes
- Operator references: docs.nvidia.com/dynamo/v-0-9-0/user-guides/kv-cache-aware-routing + docs.ray.io/en/latest/serve/llm/architecture/serving-patterns/prefill-decode.html + together.ai/blog/cache-aware-disaggregated-inference + nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-6000 + 2026 heterogeneous LLM serving CPU GPU scheduling KV cache routing agent systems (web search)
