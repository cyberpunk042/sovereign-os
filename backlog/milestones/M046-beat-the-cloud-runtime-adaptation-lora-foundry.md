# M046 — Beat the cloud — runtime adaptation + LoRA foundry

> Parent: `backlog/milestones/INDEX.md` row M046 (dump 13825–14107).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 13825–14107. Operator directives 13825: "yes indeed. continue like do. you can do online research too. we will make this even better than the cloud provider... so much better... even before I train and retrain and adapt weights and add my LORAs and such and whatnot.." + 14107: "Great Great. continue. do resaerchs online too. Think of hyper features and continuity of what we are doing".
> All entries below extract verbatim. No invention.

## Epics (E0438–E0447)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0438 | Cloud-vs-local doctrine — "you can become better than cloud providers **before** training weights because cloud is usually optimized for generic scale, while your station can optimize for you, your hardware, your memory, your workflows, your consent, your projects"; "Cloud providers have bigger fleets. You can have tighter coupling" | 13842–13852 |
| E0439 | The Local Advantage — cloud model sees 5 things (a request / maybe some uploaded context / generic tools / generic policy / provider memory if enabled); your Sovereign-OS station can see if user chooses 13 things: the repo / the tests / the shell / the GUI / the filesystem history / the ZFS snapshots / the prior traces / the hardware pressure / the model registry / the user preferences / the local memory graph / the workflow contracts / the cost ledger; "That is a completely different intelligence environment"; "The cloud may have stronger raw models. You can have stronger **situated intelligence**" | 13856–13898 |
| E0440 | Before LoRA: Runtime Adaptation — adapt through 12 mechanisms (routing / profiles / memory / retrieval / workflow choice / test execution / agent evals / spec-TDD contracts / tool affordances / context maps / reward scoring / trace learning); "This is cheaper, safer, reversible, and immediately useful"; "Fine-tuning changes weights. Runtime adaptation changes behavior. Runtime adaptation comes first" | 13902–13934 |
| E0441 | LoRA serving infrastructure (4 anchors) — vLLM supports serving LoRA adapters and dynamic loading/unloading at runtime (docs.vllm.ai/en/stable/features/lora/) + SGLang supports LoRA serving using ideas from S-LoRA/Punica to support multiple adapters for different sequences in one batch (sgl-project.github.io/advanced_features/lora.html) + S-LoRA showed unified paging for many concurrent LoRA adapters and KV cache improving throughput and adapter scale (arxiv.org/abs/2311.03285) + Ray Serve documents multi-LoRA as a way to support multiple domains/users/tasks from one shared model backend (docs.ray.io/en/master/serve/llm/user-guides/multi-lora.html); "That is extremely aligned" | 13942–13958 |
| E0442 | LoRA As Profiles — 8 candidate adapters: selfdef/security LoRA / sovereign-os/admin LoRA / coding-style LoRA / spec-driven LoRA / TDD-review LoRA / communication-mediation LoRA / domain-specific LoRA / user-preference LoRA; runtime decides 6 actions: use base model / use adapter A / use adapter B / stack-merge adapters if supported / route to specialist model instead / ask oracle instead; "This is adapter governance" | 13962–13988 |
| E0443 | Do Not Merge Too Early — "Dynamic adapters preserve flexibility. Merged models can be faster/simpler, but they are less flexible and can explode disk/VRAM workflows, especially with quantized bases"; 3 profile-driven adoption modes: development (dynamic LoRA adapters) / production stable (maybe merged adapter if evals prove it) / model lab (compare base vs adapter vs merged vs quantized); 3-principle adapter doctrine: "Adapters are behavioral overlays / Profiles decide overlays / Evals promote overlays" | 13992–14014 |
| E0444 | Adapter Memory — 3-tier crystallization: "Memory learns behavior / Evals validate behavior / LoRA crystallizes behavior into weights"; 7-step pipeline: trace collection → success/failure examples → curated dataset → adapter training → eval gate → profile assignment → monitored deployment | 14018–14036 |
| E0445 | 6-stage adaptation progression — Stage 1 prompt/profile adaptation / Stage 2 memory/retrieval adaptation / Stage 3 workflow/router adaptation / Stage 4 LoRA/domain adaptation / Stage 5 deeper fine-tuning/retraining / Stage 6 model distillation / specialist SLM creation; "This is the correct order" | 14040–14058 |
| E0446 | Hardware mapping for LoRA — Blackwell (base oracle + high-value adapters + multi-LoRA serving when stable + FP8-FP4 experiments) / 3090 (train small LoRAs / QLoRA experiments + serve scout adapters + domain-reflex models) / CPU AVX-512 (adapter routing + profile matching + eval filtering + dataset curation metadata + trace selection) / ZFS (dataset lineage + adapter versions + eval results + rollback); "The station becomes an adapter foundry" | 14062–14082 |
| E0447 | Better Than Cloud In Practice + Peace Machine Angle + Hyper Loop — "Not because you beat every frontier model. Because you can do things cloud often cannot" with 12 capabilities (use private local context fully / run tests and tools locally / keep raw traces private / adapt profiles to the user / control cloud spending / route across local-cloud models / use LoRAs per project-domain / retain ZFS-backed replay / enforce local policies / operate offline / explain every action / rollback side effects); Peace Machine Angle — 8 LoRA specializations (clearer communication / less escalation / better mediation / better technical rigor / better self-defense workflows / better project-specific coding style / better review discipline / coherence); Hyper Loop 6 steps (Observe traces+tests+user corrections+project outcomes / Adapt profiles+routing+memory+workflows / Evaluate local evals+trajectory scoring+cost-risk-quality / Crystallize skills+policies+LoRAs+specialist models / Govern user choice+rollback+audit+privacy / Repeat); "That is how the local station evolves past generic cloud behavior before a single full retrain" | 14086–14105 |

## Modules (M00765–M00781)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00765 | Cloud-coverage limitation — cloud sees 5 things | 13860–13868 | E0439 |
| M00766 | Sovereign-OS station coverage — 13 visible signals if user chooses | 13872–13890 | E0439 |
| M00767 | "Situated intelligence" doctrine — cloud has stronger raw models, station has stronger situated intelligence | 13896–13898 | E0439 |
| M00768 | 12-mechanism runtime adaptation — routing/profiles/memory/retrieval/workflow choice/test execution/agent evals/spec-TDD contracts/tool affordances/context maps/reward scoring/trace learning | 13906–13930 | E0440 |
| M00769 | Runtime-adaptation doctrine — "cheaper, safer, reversible, and immediately useful"; "Fine-tuning changes weights. Runtime adaptation changes behavior. Runtime adaptation comes first" | 13932–13934 | E0440 |
| M00770 | LoRA serving anchor — vLLM LoRA + dynamic load/unload | 13944 | E0441 |
| M00771 | LoRA serving anchor — SGLang LoRA via S-LoRA/Punica multi-adapter in one batch | 13946 | E0441 |
| M00772 | LoRA serving anchor — S-LoRA unified paging for many adapters + KV cache | 13950 | E0441 |
| M00773 | LoRA serving anchor — Ray Serve multi-LoRA for multiple domains/users/tasks | 13954 | E0441 |
| M00774 | 8 candidate LoRA adapters — security / admin / coding-style / spec-driven / TDD-review / communication-mediation / domain-specific / user-preference | 13966–13976 | E0442 |
| M00775 | Adapter governance — 6 runtime actions (base / adapter A / adapter B / stack-merge / specialist / oracle) | 13980–13988 | E0442 |
| M00776 | Merge timing — 3 profile-driven adoption modes (development=dynamic / production stable=maybe-merged / model lab=compare-all) | 13998–14010 | E0443 |
| M00777 | Adapter principles — Adapters are behavioral overlays / Profiles decide overlays / Evals promote overlays | 14012–14014 | E0443 |
| M00778 | Adapter memory pipeline — trace collection → success/failure examples → curated dataset → adapter training → eval gate → profile assignment → monitored deployment | 14026–14036 | E0444 |
| M00779 | 6-stage adaptation progression — prompt/profile → memory/retrieval → workflow/router → LoRA/domain → fine-tuning/retraining → distillation/specialist SLM | 14044–14056 | E0445 |
| M00780 | LoRA hardware mapping — Blackwell oracle+multi-LoRA / 3090 train+scout / CPU AVX-512 routing-filtering-curation / ZFS lineage-versions-results-rollback | 14066–14080 | E0446 |
| M00781 | Better-than-cloud 12 capabilities + Peace-machine 8 specializations + Hyper Loop 6 steps | 14090–14105 | E0447 |

## Features (F03826–F03910)

| Feature ID | Phrase | Dump line | Parent module |
|---|---|---|---|
| F03826 | Cloud advantage — generic scale | 13844 | E0438 |
| F03827 | Station advantage — optimize for you | 13846 | E0438 |
| F03828 | Station advantage — optimize for your hardware | 13846 | E0438 |
| F03829 | Station advantage — optimize for your memory | 13846 | E0438 |
| F03830 | Station advantage — optimize for your workflows | 13846 | E0438 |
| F03831 | Station advantage — optimize for your consent | 13846 | E0438 |
| F03832 | Station advantage — optimize for your projects | 13846 | E0438 |
| F03833 | "Cloud providers have bigger fleets" | 13850 | E0438 |
| F03834 | "You can have tighter coupling" | 13852 | E0438 |
| F03835 | Cloud visibility — a request | 13862 | M00765 |
| F03836 | Cloud visibility — maybe some uploaded context | 13863 | M00765 |
| F03837 | Cloud visibility — generic tools | 13864 | M00765 |
| F03838 | Cloud visibility — generic policy | 13865 | M00765 |
| F03839 | Cloud visibility — provider memory if enabled | 13866 | M00765 |
| F03840 | Station visibility — the repo | 13874 | M00766 |
| F03841 | Station visibility — the tests | 13875 | M00766 |
| F03842 | Station visibility — the shell | 13876 | M00766 |
| F03843 | Station visibility — the GUI | 13877 | M00766 |
| F03844 | Station visibility — the filesystem history | 13878 | M00766 |
| F03845 | Station visibility — the ZFS snapshots | 13879 | M00766 |
| F03846 | Station visibility — the prior traces | 13880 | M00766 |
| F03847 | Station visibility — the hardware pressure | 13881 | M00766 |
| F03848 | Station visibility — the model registry | 13882 | M00766 |
| F03849 | Station visibility — the user preferences | 13883 | M00766 |
| F03850 | Station visibility — the local memory graph | 13884 | M00766 |
| F03851 | Station visibility — the workflow contracts | 13885 | M00766 |
| F03852 | Station visibility — the cost ledger | 13886 | M00766 |
| F03853 | "Different intelligence environment" | 13890 | E0439 |
| F03854 | "Cloud may have stronger raw models" | 13894 | M00767 |
| F03855 | "You can have stronger situated intelligence" | 13896 | M00767 |
| F03856 | Adaptation mechanism — routing | 13908 | M00768 |
| F03857 | Adaptation mechanism — profiles | 13909 | M00768 |
| F03858 | Adaptation mechanism — memory | 13910 | M00768 |
| F03859 | Adaptation mechanism — retrieval | 13911 | M00768 |
| F03860 | Adaptation mechanism — workflow choice | 13912 | M00768 |
| F03861 | Adaptation mechanism — test execution | 13913 | M00768 |
| F03862 | Adaptation mechanism — agent evals | 13914 | M00768 |
| F03863 | Adaptation mechanism — spec/TDD contracts | 13915 | M00768 |
| F03864 | Adaptation mechanism — tool affordances | 13916 | M00768 |
| F03865 | Adaptation mechanism — context maps | 13917 | M00768 |
| F03866 | Adaptation mechanism — reward scoring | 13918 | M00768 |
| F03867 | Adaptation mechanism — trace learning | 13919 | M00768 |
| F03868 | Runtime adaptation — "cheaper, safer, reversible, and immediately useful" | 13923 | M00769 |
| F03869 | "Fine-tuning changes weights" | 13927 | M00769 |
| F03870 | "Runtime adaptation changes behavior" | 13929 | M00769 |
| F03871 | "Runtime adaptation comes first" | 13934 | M00769 |
| F03872 | LoRA — perfect for architecture: "creates specialized minds without duplicating full base models" | 13938–13940 | E0441 |
| F03873 | vLLM LoRA URL — docs.vllm.ai/en/stable/features/lora/ | 13944 | M00770 |
| F03874 | SGLang LoRA URL — sgl-project.github.io/advanced_features/lora.html | 13946 | M00771 |
| F03875 | S-LoRA arxiv URL — arxiv.org/abs/2311.03285 | 13950 | M00772 |
| F03876 | Ray multi-LoRA URL — docs.ray.io/en/master/serve/llm/user-guides/multi-lora.html | 13954 | M00773 |
| F03877 | vLLM — serves LoRA adapters | 13944 | M00770 |
| F03878 | vLLM — dynamic loading/unloading at runtime | 13944 | M00770 |
| F03879 | SGLang — supports LoRA serving | 13946 | M00771 |
| F03880 | SGLang — uses ideas from S-LoRA/Punica | 13946 | M00771 |
| F03881 | SGLang — supports multiple adapters for different sequences in one batch | 13946 | M00771 |
| F03882 | S-LoRA — unified paging for many concurrent LoRA adapters AND KV cache | 13950 | M00772 |
| F03883 | S-LoRA — improves throughput and adapter scale | 13950 | M00772 |
| F03884 | Ray Serve multi-LoRA — multiple domains | 13954 | M00773 |
| F03885 | Ray Serve multi-LoRA — multiple users | 13954 | M00773 |
| F03886 | Ray Serve multi-LoRA — multiple tasks | 13954 | M00773 |
| F03887 | Ray Serve multi-LoRA — from one shared model backend | 13954 | M00773 |
| F03888 | "That is extremely aligned" | 13958 | E0441 |
| F03889 | Adapter — selfdef/security LoRA | 13968 | M00774 |
| F03890 | Adapter — sovereign-os/admin LoRA | 13969 | M00774 |
| F03891 | Adapter — coding-style LoRA | 13970 | M00774 |
| F03892 | Adapter — spec-driven LoRA | 13971 | M00774 |
| F03893 | Adapter — TDD/review LoRA | 13972 | M00774 |
| F03894 | Adapter — communication/mediation LoRA | 13973 | M00774 |
| F03895 | Adapter — domain-specific LoRA | 13974 | M00774 |
| F03896 | Adapter — user-preference LoRA | 13975 | M00774 |
| F03897 | Runtime decision — use base model / adapter A / adapter B / stack-merge / specialist / oracle | 13980–13986 | M00775 |
| F03898 | "This is adapter governance" | 13988 | M00775 |
| F03899 | "Dynamic adapters preserve flexibility" | 13994 | E0443 |
| F03900 | "Merged models can be faster/simpler, but they are less flexible and can explode disk/VRAM workflows, especially with quantized bases" | 13996 | E0443 |
| F03901 | Merge mode — development: dynamic LoRA adapters | 14000 | M00776 |
| F03902 | Merge mode — production stable: maybe merged adapter if evals prove it | 14004 | M00776 |
| F03903 | Merge mode — model lab: compare base vs adapter vs merged vs quantized | 14008 | M00776 |
| F03904 | Principle — Adapters are behavioral overlays | 14012 | M00777 |
| F03905 | Principle — Profiles decide overlays | 14013 | M00777 |
| F03906 | Principle — Evals promote overlays | 14014 | M00777 |
| F03907 | Crystallization — Memory learns behavior / Evals validate behavior / LoRA crystallizes behavior into weights | 14020–14024 | E0444 |
| F03908 | Adapter pipeline — trace collection / success-failure examples / curated dataset / adapter training / eval gate / profile assignment / monitored deployment | 14028–14036 | M00778 |
| F03909 | 6-stage progression — Stage 1 prompt-profile / Stage 2 memory-retrieval / Stage 3 workflow-router / Stage 4 LoRA-domain / Stage 5 deeper fine-tuning-retraining / Stage 6 distillation-specialist-SLM + "correct order" | 14044–14058 | M00779 |
| F03910 | Hardware-mapping 4 roles + better-than-cloud 12 capabilities + Peace-Machine 8 specializations + Hyper Loop 6-step (Observe/Adapt/Evaluate/Crystallize/Govern/Repeat) + "evolves past generic cloud behavior before a single full retrain" | 14062–14105 | M00780 + M00781 + E0446 + E0447 |

## Requirements (R07651–R07820)

| Req ID | Phrase | Dump line | Parent feature | Negotiability | Layer-B metric | Priority |
|---|---|---|---|---|---|---|
| R07651 | Doctrine — "you can become better than cloud providers before training weights" | 13842 | E0438 | non-negotiable | false | 10 |
| R07652 | Cloud — "usually optimized for generic scale" | 13844 | F03826 | non-negotiable | false | 10 |
| R07653 | Station — optimize for you | 13846 | F03827 | non-negotiable | false | 10 |
| R07654 | Station — optimize for your hardware | 13846 | F03828 | non-negotiable | false | 10 |
| R07655 | Station — optimize for your memory | 13846 | F03829 | non-negotiable | false | 10 |
| R07656 | Station — optimize for your workflows | 13846 | F03830 | non-negotiable | false | 10 |
| R07657 | Station — optimize for your consent | 13846 | F03831 | non-negotiable | false | 10 |
| R07658 | Station — optimize for your projects | 13846 | F03832 | non-negotiable | false | 10 |
| R07659 | "Cloud providers have bigger fleets" | 13850 | F03833 | non-negotiable | false | 10 |
| R07660 | "You can have tighter coupling" | 13852 | F03834 | non-negotiable | false | 10 |
| R07661 | Local Advantage header — "The Local Advantage" | 13856 | E0439 | non-negotiable | false | 10 |
| R07662 | Cloud sees — a request | 13862 | F03835 | non-negotiable | false | 10 |
| R07663 | Cloud sees — maybe some uploaded context | 13863 | F03836 | non-negotiable | false | 10 |
| R07664 | Cloud sees — generic tools | 13864 | F03837 | non-negotiable | false | 10 |
| R07665 | Cloud sees — generic policy | 13865 | F03838 | non-negotiable | false | 10 |
| R07666 | Cloud sees — provider memory if enabled | 13866 | F03839 | non-negotiable | false | 10 |
| R07667 | Station sees — the repo | 13874 | F03840 | non-negotiable | false | 10 |
| R07668 | Station sees — the tests | 13875 | F03841 | non-negotiable | false | 10 |
| R07669 | Station sees — the shell | 13876 | F03842 | non-negotiable | false | 10 |
| R07670 | Station sees — the GUI | 13877 | F03843 | non-negotiable | false | 10 |
| R07671 | Station sees — the filesystem history | 13878 | F03844 | non-negotiable | false | 10 |
| R07672 | Station sees — the ZFS snapshots | 13879 | F03845 | non-negotiable | false | 10 |
| R07673 | Station sees — the prior traces | 13880 | F03846 | non-negotiable | false | 10 |
| R07674 | Station sees — the hardware pressure | 13881 | F03847 | non-negotiable | false | 10 |
| R07675 | Station sees — the model registry | 13882 | F03848 | non-negotiable | false | 10 |
| R07676 | Station sees — the user preferences | 13883 | F03849 | non-negotiable | false | 10 |
| R07677 | Station sees — the local memory graph | 13884 | F03850 | non-negotiable | false | 10 |
| R07678 | Station sees — the workflow contracts | 13885 | F03851 | non-negotiable | false | 10 |
| R07679 | Station sees — the cost ledger | 13886 | F03852 | non-negotiable | false | 10 |
| R07680 | "That is a completely different intelligence environment" | 13890 | F03853 | non-negotiable | false | 10 |
| R07681 | "The cloud may have stronger raw models" | 13894 | F03854 | non-negotiable | false | 10 |
| R07682 | "You can have stronger situated intelligence" | 13896 | F03855 | non-negotiable | false | 10 |
| R07683 | Before-LoRA header — "Before LoRA: Runtime Adaptation" | 13902 | E0440 | non-negotiable | false | 10 |
| R07684 | Adaptation — routing | 13908 | F03856 | non-negotiable | false | 10 |
| R07685 | Adaptation — profiles | 13909 | F03857 | non-negotiable | false | 10 |
| R07686 | Adaptation — memory | 13910 | F03858 | non-negotiable | false | 10 |
| R07687 | Adaptation — retrieval | 13911 | F03859 | non-negotiable | false | 10 |
| R07688 | Adaptation — workflow choice | 13912 | F03860 | non-negotiable | false | 10 |
| R07689 | Adaptation — test execution | 13913 | F03861 | non-negotiable | false | 10 |
| R07690 | Adaptation — agent evals | 13914 | F03862 | non-negotiable | false | 10 |
| R07691 | Adaptation — spec/TDD contracts | 13915 | F03863 | non-negotiable | false | 10 |
| R07692 | Adaptation — tool affordances | 13916 | F03864 | non-negotiable | false | 10 |
| R07693 | Adaptation — context maps | 13917 | F03865 | non-negotiable | false | 10 |
| R07694 | Adaptation — reward scoring | 13918 | F03866 | non-negotiable | false | 10 |
| R07695 | Adaptation — trace learning | 13919 | F03867 | non-negotiable | false | 10 |
| R07696 | "Cheaper" | 13923 | F03868 | non-negotiable | false | 10 |
| R07697 | "Safer" | 13923 | F03868 | non-negotiable | false | 10 |
| R07698 | "Reversible" | 13923 | F03868 | non-negotiable | false | 10 |
| R07699 | "Immediately useful" | 13923 | F03868 | non-negotiable | false | 10 |
| R07700 | "Fine-tuning changes weights" | 13927 | F03869 | non-negotiable | false | 10 |
| R07701 | "Runtime adaptation changes behavior" | 13929 | F03870 | non-negotiable | false | 10 |
| R07702 | "Runtime adaptation comes first" | 13934 | F03871 | non-negotiable | false | 10 |
| R07703 | LoRA — "perfect for your architecture" | 13938 | E0441 | non-negotiable | false | 10 |
| R07704 | LoRA — "creates specialized minds without duplicating full base models" | 13940 | F03872 | non-negotiable | false | 10 |
| R07705 | vLLM — supports serving LoRA adapters | 13944 | F03877 | non-negotiable | false | 10 |
| R07706 | vLLM — dynamic loading/unloading at runtime | 13944 | F03878 | non-negotiable | false | 10 |
| R07707 | vLLM URL — docs.vllm.ai/en/stable/features/lora/ | 13944 | F03873 | non-negotiable | false | 10 |
| R07708 | SGLang — supports LoRA serving | 13946 | F03879 | non-negotiable | false | 10 |
| R07709 | SGLang — uses ideas from S-LoRA | 13946 | F03880 | non-negotiable | false | 10 |
| R07710 | SGLang — uses ideas from Punica | 13946 | F03880 | non-negotiable | false | 10 |
| R07711 | SGLang — supports multiple adapters for different sequences in one batch | 13946 | F03881 | non-negotiable | false | 10 |
| R07712 | SGLang URL — sgl-project.github.io/advanced_features/lora.html | 13946 | F03874 | non-negotiable | false | 10 |
| R07713 | S-LoRA — unified paging for many concurrent LoRA adapters | 13950 | F03882 | non-negotiable | false | 10 |
| R07714 | S-LoRA — unified paging for KV cache | 13950 | F03882 | non-negotiable | false | 10 |
| R07715 | S-LoRA — improves throughput | 13950 | F03883 | non-negotiable | false | 10 |
| R07716 | S-LoRA — improves adapter scale | 13950 | F03883 | non-negotiable | false | 10 |
| R07717 | S-LoRA URL — arxiv.org/abs/2311.03285 | 13950 | F03875 | non-negotiable | false | 10 |
| R07718 | Ray Serve — multi-LoRA for multiple domains | 13954 | F03884 | non-negotiable | false | 10 |
| R07719 | Ray Serve — multi-LoRA for multiple users | 13954 | F03885 | non-negotiable | false | 10 |
| R07720 | Ray Serve — multi-LoRA for multiple tasks | 13954 | F03886 | non-negotiable | false | 10 |
| R07721 | Ray Serve — multi-LoRA from one shared model backend | 13954 | F03887 | non-negotiable | false | 10 |
| R07722 | Ray Serve URL — docs.ray.io/en/master/serve/llm/user-guides/multi-lora.html | 13954 | F03876 | non-negotiable | false | 10 |
| R07723 | "That is extremely aligned" | 13958 | F03888 | non-negotiable | false | 10 |
| R07724 | LoRA-as-profiles header — "LoRA As Profiles" | 13962 | E0442 | non-negotiable | false | 10 |
| R07725 | Adapter — selfdef/security LoRA | 13968 | F03889 | non-negotiable | false | 10 |
| R07726 | Adapter — sovereign-os/admin LoRA | 13969 | F03890 | non-negotiable | false | 10 |
| R07727 | Adapter — coding-style LoRA | 13970 | F03891 | non-negotiable | false | 10 |
| R07728 | Adapter — spec-driven LoRA | 13971 | F03892 | non-negotiable | false | 10 |
| R07729 | Adapter — TDD/review LoRA | 13972 | F03893 | non-negotiable | false | 10 |
| R07730 | Adapter — communication/mediation LoRA | 13973 | F03894 | non-negotiable | false | 10 |
| R07731 | Adapter — domain-specific LoRA | 13974 | F03895 | non-negotiable | false | 10 |
| R07732 | Adapter — user-preference LoRA | 13975 | F03896 | non-negotiable | false | 10 |
| R07733 | Runtime decision — use base model | 13980 | F03897 | non-negotiable | false | 10 |
| R07734 | Runtime decision — use adapter A | 13981 | F03897 | non-negotiable | false | 10 |
| R07735 | Runtime decision — use adapter B | 13982 | F03897 | non-negotiable | false | 10 |
| R07736 | Runtime decision — stack/merge adapters if supported | 13983 | F03897 | non-negotiable | false | 10 |
| R07737 | Runtime decision — route to specialist model instead | 13984 | F03897 | non-negotiable | false | 10 |
| R07738 | Runtime decision — ask oracle instead | 13985 | F03897 | non-negotiable | false | 10 |
| R07739 | "This is adapter governance" | 13988 | F03898 | non-negotiable | false | 10 |
| R07740 | Don't merge too early header — "Do Not Merge Too Early" | 13992 | E0443 | non-negotiable | false | 10 |
| R07741 | "Dynamic adapters preserve flexibility" | 13994 | F03899 | non-negotiable | false | 10 |
| R07742 | "Merged models can be faster/simpler" | 13996 | F03900 | non-negotiable | false | 10 |
| R07743 | "Merged models less flexible" | 13996 | F03900 | non-negotiable | false | 10 |
| R07744 | "Merged models can explode disk/VRAM workflows" | 13996 | F03900 | non-negotiable | false | 10 |
| R07745 | "Especially with quantized bases" | 13996 | F03900 | non-negotiable | false | 10 |
| R07746 | Merge mode — development: dynamic LoRA adapters | 14000 | F03901 | non-negotiable | false | 10 |
| R07747 | Merge mode — production stable: maybe merged adapter if evals prove it | 14004 | F03902 | non-negotiable | false | 10 |
| R07748 | Merge mode — model lab: compare base vs adapter vs merged vs quantized | 14008 | F03903 | non-negotiable | false | 10 |
| R07749 | Principle — "Adapters are behavioral overlays" | 14012 | F03904 | non-negotiable | false | 10 |
| R07750 | Principle — "Profiles decide overlays" | 14013 | F03905 | non-negotiable | false | 10 |
| R07751 | Principle — "Evals promote overlays" | 14014 | F03906 | non-negotiable | false | 10 |
| R07752 | Adapter Memory header — "Adapter Memory" | 14018 | E0444 | non-negotiable | false | 10 |
| R07753 | Crystallization — Memory learns behavior | 14020 | F03907 | non-negotiable | false | 10 |
| R07754 | Crystallization — Evals validate behavior | 14022 | F03907 | non-negotiable | false | 10 |
| R07755 | Crystallization — LoRA crystallizes behavior into weights | 14024 | F03907 | non-negotiable | false | 10 |
| R07756 | Pipeline step — trace collection | 14028 | F03908 | non-negotiable | false | 10 |
| R07757 | Pipeline step — success/failure examples | 14030 | F03908 | non-negotiable | false | 10 |
| R07758 | Pipeline step — curated dataset | 14031 | F03908 | non-negotiable | false | 10 |
| R07759 | Pipeline step — adapter training | 14032 | F03908 | non-negotiable | false | 10 |
| R07760 | Pipeline step — eval gate | 14033 | F03908 | non-negotiable | false | 10 |
| R07761 | Pipeline step — profile assignment | 14034 | F03908 | non-negotiable | false | 10 |
| R07762 | Pipeline step — monitored deployment | 14035 | F03908 | non-negotiable | false | 10 |
| R07763 | 6-stage header — "the system becomes better in stages" | 14040 | E0445 | non-negotiable | false | 10 |
| R07764 | Stage 1 — prompt/profile adaptation | 14044 | F03909 | non-negotiable | false | 10 |
| R07765 | Stage 2 — memory/retrieval adaptation | 14046 | F03909 | non-negotiable | false | 10 |
| R07766 | Stage 3 — workflow/router adaptation | 14048 | F03909 | non-negotiable | false | 10 |
| R07767 | Stage 4 — LoRA/domain adaptation | 14050 | F03909 | non-negotiable | false | 10 |
| R07768 | Stage 5 — deeper fine-tuning/retraining | 14052 | F03909 | non-negotiable | false | 10 |
| R07769 | Stage 6 — model distillation / specialist SLM creation | 14054 | F03909 | non-negotiable | false | 10 |
| R07770 | "This is the correct order" | 14058 | F03909 | non-negotiable | false | 10 |
| R07771 | Hardware mapping header — "Hardware Mapping For LoRA" | 14062 | E0446 | non-negotiable | false | 10 |
| R07772 | Blackwell — base oracle | 14066 | M00780 | non-negotiable | false | 10 |
| R07773 | Blackwell — high-value adapters | 14066 | M00780 | non-negotiable | false | 10 |
| R07774 | Blackwell — multi-LoRA serving when stable | 14067 | M00780 | non-negotiable | false | 10 |
| R07775 | Blackwell — FP8/FP4 experiments | 14068 | M00780 | non-negotiable | false | 10 |
| R07776 | 3090 — train small LoRAs | 14070 | M00780 | non-negotiable | false | 10 |
| R07777 | 3090 — QLoRA experiments | 14070 | M00780 | non-negotiable | false | 10 |
| R07778 | 3090 — serve scout adapters | 14071 | M00780 | non-negotiable | false | 10 |
| R07779 | 3090 — domain/reflex models | 14072 | M00780 | non-negotiable | false | 10 |
| R07780 | CPU AVX-512 — adapter routing | 14074 | M00780 | non-negotiable | false | 10 |
| R07781 | CPU AVX-512 — profile matching | 14075 | M00780 | non-negotiable | false | 10 |
| R07782 | CPU AVX-512 — eval filtering | 14076 | M00780 | non-negotiable | false | 10 |
| R07783 | CPU AVX-512 — dataset curation metadata | 14077 | M00780 | non-negotiable | false | 10 |
| R07784 | CPU AVX-512 — trace selection | 14078 | M00780 | non-negotiable | false | 10 |
| R07785 | ZFS — dataset lineage | 14080 | M00780 | non-negotiable | false | 10 |
| R07786 | ZFS — adapter versions | 14081 | M00780 | non-negotiable | false | 10 |
| R07787 | ZFS — eval results | 14082 | M00780 | non-negotiable | false | 10 |
| R07788 | ZFS — rollback | 14082 | M00780 | non-negotiable | false | 10 |
| R07789 | "The station becomes an adapter foundry" | 14084 | E0446 | non-negotiable | false | 10 |
| R07790 | Better-than-cloud — "Not because you beat every frontier model" | 14088 | E0447 | non-negotiable | false | 10 |
| R07791 | Better-than-cloud — "Because you can do things cloud often cannot" | 14088 | E0447 | non-negotiable | false | 10 |
| R07792 | Capability — use private local context fully | 14091 | M00781 | non-negotiable | false | 10 |
| R07793 | Capability — run tests and tools locally | 14092 | M00781 | non-negotiable | false | 10 |
| R07794 | Capability — keep raw traces private | 14093 | M00781 | non-negotiable | false | 10 |
| R07795 | Capability — adapt profiles to the user | 14094 | M00781 | non-negotiable | false | 10 |
| R07796 | Capability — control cloud spending | 14095 | M00781 | non-negotiable | false | 10 |
| R07797 | Capability — route across local/cloud models | 14096 | M00781 | non-negotiable | false | 10 |
| R07798 | Capability — use LoRAs per project/domain | 14097 | M00781 | non-negotiable | false | 10 |
| R07799 | Capability — retain ZFS-backed replay | 14098 | M00781 | non-negotiable | false | 10 |
| R07800 | Capability — enforce local policies | 14099 | M00781 | non-negotiable | false | 10 |
| R07801 | Capability — operate offline | 14100 | M00781 | non-negotiable | false | 10 |
| R07802 | Capability — explain every action | 14101 | M00781 | non-negotiable | false | 10 |
| R07803 | Capability — rollback side effects | 14102 | M00781 | non-negotiable | false | 10 |
| R07804 | "More valuable than raw benchmark dominance for many real workflows" | 14104 | E0447 | non-negotiable | false | 10 |
| R07805 | Peace machine — clearer communication | 14108 | M00781 | non-negotiable | false | 10 |
| R07806 | Peace machine — less escalation | 14109 | M00781 | non-negotiable | false | 10 |
| R07807 | Peace machine — better mediation | 14110 | M00781 | non-negotiable | false | 10 |
| R07808 | Peace machine — better technical rigor | 14111 | M00781 | non-negotiable | false | 10 |
| R07809 | Peace machine — better self-defense workflows | 14112 | M00781 | non-negotiable | false | 10 |
| R07810 | Peace machine — better project-specific coding style | 14113 | M00781 | non-negotiable | false | 10 |
| R07811 | Peace machine — better review discipline | 14114 | M00781 | non-negotiable | false | 10 |
| R07812 | Peace machine — "The purpose is not dominance. It is coherence" | 14116 | M00781 | non-negotiable | false | 10 |
| R07813 | Hyper Loop — Observe (traces, tests, user corrections, project outcomes) | 14120 | M00781 | non-negotiable | false | 10 |
| R07814 | Hyper Loop — Adapt (profiles, routing, memory, workflows) | 14122 | M00781 | non-negotiable | false | 10 |
| R07815 | Hyper Loop — Evaluate (local evals, trajectory scoring, cost/risk/quality) | 14124 | M00781 | non-negotiable | false | 10 |
| R07816 | Hyper Loop — Crystallize (skills, policies, LoRAs, specialist models) | 14126 | M00781 | non-negotiable | false | 10 |
| R07817 | Hyper Loop — Govern (user choice, rollback, audit, privacy) | 14128 | M00781 | non-negotiable | false | 10 |
| R07818 | Hyper Loop — Repeat | 14130 | M00781 | non-negotiable | false | 10 |
| R07819 | Hyper Loop conclusion — "That is how the local station evolves past generic cloud behavior before a single full retrain" | 14132 | E0447 | non-negotiable | false | 10 |
| R07820 | Composite — M046 (10 epics / 17 modules / 85 features / 170 reqs) catalogs Beat-the-cloud + runtime adaptation + LoRA foundry: cloud-vs-local edge ("tighter coupling" + cloud-5 vs station-13 visible signals + "situated intelligence") + 12 runtime adaptation mechanisms + "Fine-tuning changes weights. Runtime adaptation changes behavior. Runtime adaptation comes first" + 4 LoRA-serving research anchors (vLLM dynamic + SGLang S-LoRA-Punica multi-batch + S-LoRA unified paging + Ray Serve multi-LoRA shared backend) + 8 candidate LoRA adapters + 6 runtime decisions + 3 profile-driven merge modes + 3-principle adapter doctrine (overlays/profiles/evals) + 3-tier crystallization (Memory learns + Evals validate + LoRA crystallizes) + 7-step adapter pipeline + 6-stage adaptation progression + LoRA hardware mapping (Blackwell+3090+AVX-512+ZFS) + "station becomes adapter foundry" + 12 better-than-cloud capabilities + 8 Peace-Machine specializations + "coherence not dominance" + Hyper Loop 6 steps Observe→Adapt→Evaluate→Crystallize→Govern→Repeat + "evolves past generic cloud behavior before a single full retrain" | 13825–14107 | E0438-E0447 | non-negotiable | false | 10 |

## Sub-requirements accounting

- 170 requirements covering: cloud-vs-station 6-property + tighter-coupling (R07651–R07660) + Local Advantage cloud-5 + station-13 + situated-intelligence (R07661–R07682) + Before-LoRA 12 mechanisms + 4-property runtime-adaptation doctrine (R07683–R07702) + LoRA infra "perfect for architecture" + 4 research anchors (vLLM/SGLang/S-LoRA/Ray Serve) (R07703–R07723) + 8 candidate adapters + 6 runtime decisions + "adapter governance" (R07724–R07739) + Don't-merge-too-early + 4-property merge trade-off + 3 merge modes + 3 principles (R07740–R07751) + Adapter Memory 3-tier crystallization + 7-step pipeline (R07752–R07762) + 6-stage progression + "correct order" (R07763–R07770) + Hardware mapping (Blackwell + 3090 + AVX-512 + ZFS) + adapter-foundry (R07771–R07789) + Better-than-cloud 12 capabilities + "valuable than benchmark dominance" (R07790–R07804) + Peace Machine 8 specializations + coherence-not-dominance (R07805–R07812) + Hyper Loop 6 steps + "evolves past cloud before retrain" (R07813–R07819) + composite (R07820)
- Source range 13825–14107 yields 282 lines; 170 R-rows represent ~60% line-coverage at the verbatim-citation level
- Project boundary — M046 is sovereign-os runtime-adaptation + LoRA-foundry scope; selfdef IPS-side may consume the security-LoRA adapter (one of 8 candidate adapters) for agent-guard policy refinement; cross-repo binding via MS007 typed-mirror crates (model_registry surface)

## Cross-references

- Adjacent dump-range milestones: M045 Linux as intelligence governor (13546–13825) / M047 Continuity — CRIU + ZFS + warm sandboxes + hibernated thought (next; dump 14107–14402)
- Plane integration — M046 builds on M042 Choice Architecture (profile bundles) + M043 Bridge Layer hardware-aware intelligence scheduling (AVX-512 Routing Brain becomes adapter routing) + M044 Sovereign-OS substrate (ZFS dataset lineage + adapter versions + eval results) + M045 Linux as intelligence governor (Pressure-As-Sensation guides Stage 1-3 runtime adaptations)
- 6-stage adaptation — Stage 1 prompt/profile = M042 Choice Architecture + M040 Modes-as-hardware-configurations; Stage 2 memory/retrieval = M028 Memory OS + M030 World Model; Stage 3 workflow/router = M025 Cognitive Compiler + M043 AVX-512 Routing Brain; Stage 4 LoRA/domain = M046; Stage 5 fine-tuning = future; Stage 6 distillation = future
- 8 candidate adapters — selfdef/security LoRA cross-binds via MS007 model_registry typed-mirror crate to selfdef MS017 agent-guard (host-level invariants on AI agents); sovereign-os/admin LoRA is sovereign-os internal; coding-style + spec-driven + TDD-review LoRAs align with M037 Spec/TDD evidence-driven autonomy
- LoRA serving infra — M046's vLLM + SGLang + S-LoRA + Ray Serve multi-LoRA become the model-serving subsystem under M035 Frontier inference-time intelligence + M032 Cloud Expert Plane (when local Blackwell hosts the multi-LoRA backend)
- Hardware mapping — Blackwell base + adapters + multi-LoRA stable serving + FP8/FP4 experiments aligns with M040 Hyper Feature 1 MIG profiles + Hyper Feature 2 Blackwell FP4 + M043 Blackwell-as-context-sovereign
- Hyper Loop 6 steps — Observe (M037 evidence-driven autonomy traces) → Adapt (M042 Choice Architecture) → Evaluate (M037 EVALS.yaml + M041 EVALS contract) → Crystallize (M046 LoRA foundry) → Govern (M042 + M044 Choice/Security planes + M026 ZFS commit gate) → Repeat
- Selfdef integration — selfdef/security LoRA (one of 8 candidate adapters) crystallizes selfdef IPS doctrine; agent-guard MS017 + threat model MS019 + 27-SDD ledger MS013 are training inputs
- Operator references: docs.vllm.ai/en/stable/features/lora/ + sgl-project.github.io/advanced_features/lora.html + arxiv.org/abs/2311.03285 + docs.ray.io/en/master/serve/llm/user-guides/multi-lora.html + QLoRA LoRA adapter serving vLLM multiple LoRA adapters documentation 2026 (web search)
