# M044 — Sovereign-OS substrate — Debian 13 / Ubuntu 24

> Parent: `backlog/milestones/INDEX.md` row M044 (dump 13307–13546).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 13307–13546. Operator directive 13308: "we are in a Debian 13 / Ubuntu 24 base OS mode (Sovereign-OS)" and 13309: "You said it.. its a 'war' machine.. or rather anti-war... it a peace, full communication and logic and intelligence everywhere. continue. do researchs online too".
> All entries below extract verbatim. No invention.

## Epics (E0418–E0427)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0418 | Operator directives — "we are in a Debian 13 / Ubuntu 24 base OS mode (Sovereign-OS)" + "its a 'war' machine.. or rather anti-war... it a peace, full communication and logic and intelligence everywhere"; "continue. do researchs online too"; AI confirmation "Yes. Debian 13 / Ubuntu 24 as the Sovereign-OS base changes the bridge in a very concrete way. This is not just 'Linux.' It is the **sovereign substrate**: package policy, kernel behavior, GPU driver reality, sandbox security, filesystem truth, and user-controlled communication" | 13308–13309 + 13328–13332 |
| E0419 | Debian 13 / Trixie — stable, modern base; "Debian says Trixie is the current stable release, with support through 2028 full support and LTS through 2030"; "Debian 13 ships around Linux 6.12 LTS, GCC 14.2, Python 3.13, and a refreshed stack"; URLs: debian.org/releases/trixie/index + debian.org/releases/trixie/release-notes/ | 13336–13340 |
| E0420 | Ubuntu 24.04 LTS — "corporate/stable AI workstation path: kernel 6.8 initially, GCC 14, glibc 2.39, five years of maintenance to May 2029, and optional extended support"; URL: documentation.ubuntu.com/release-notes/24.04/ | 13342–13344 |
| E0421 | Two personalities — Debian 13 (stable / clean / sovereign / less vendor magic / excellent base for controlled systems) vs Ubuntu 24.04 (easier NVIDIA-CUDA ecosystem / enterprise tooling / AppArmor defaults / broad vendor support); "That is not a contradiction. It is a profile choice" | 13348–13360 |
| E0422 | Peace machine frame — "Anti-war is the better term. The system is not a war machine in purpose. It is a **coordination machine**" with 10 properties: communication / translation / logic / verification / planning / memory / trust / consent / conflict reduction / shared understanding; technical implication "the OS must make intelligence accountable" — 6-step model: AI proposes / Policy checks / Tools execute in bounded space / Traces record / User can inspect / System learns; "That is peace through legibility" | 13366–13396 |
| E0423 | Security substrate — Ubuntu 24.04 AppArmor/user-namespace work directly relevant; "Ubuntu documents restricted unprivileged user namespaces via AppArmor in 24.04, limiting what unconfined apps can do inside user namespaces" (URLs: documentation.ubuntu.com/release-notes/24.04 + documentation.ubuntu.com/security/security-features/security-features-overview/); 6 sandbox vectors (rootless Podman / bubblewrap / Deno permissions / browser sandboxes / Claude Code-tool sandboxes / VMs); 4 security-profile bundles (secure: restrictive user namespaces + AppArmor enforced / developer: allow specific sandbox frameworks / agent-lab: controlled exceptions for Podman+bubblewrap+browser+VM / high-risk: move to VM-microVM instead of loosening host); "Security is not one setting. It is a user-visible operating mode" | 13400–13434 |
| E0424 | Secrets and identity — "A peace/intelligence OS must guard secrets like a body guards organs"; 7 controls (LUKS2 full disk encryption / TPM2-FIDO2 unlock options / per-project secrets / vault proxy + stub credentials / redaction before cloud / cost ledger / network egress policy); Ubuntu `systemd-cryptenroll` supports enrolling TPM2/FIDO2/PKCS#11 tokens into LUKS2 volumes (manpages.ubuntu.com/manpages/noble/man1/systemd-cryptenroll.1.html); "That fits Sovereign-OS: user presence / device identity / encrypted memory of the system" | 13438–13458 |
| E0425 | NVIDIA reality — Blackwell on Linux means driver discipline; "NVIDIA's Debian 13 data center driver listing already includes RTX PRO 6000 Blackwell Server Edition in supported RTX-series devices for driver 590.48.01" (nvidia.com/download/driverResults.aspx/259501/en-us); "Ubuntu 24.04 also tends to be the smoother path for CUDA packaging"; practical bridge — Debian 13 (stronger sovereign base; may need more NVIDIA driver care) vs Ubuntu 24.04 (smoother CUDA/NVIDIA path; more vendor-supported AI workflows); abstraction "core base: Debian-like sovereign policy / AI driver profile: Ubuntu/NVIDIA-friendly stack where needed" | 13462–13486 |
| E0426 | Kernel + compiler matter — "Zen 5 wants modern kernel and compiler. Debian 13's kernel 6.12/GCC 14.2 and Ubuntu 24.04's GCC 14 line are good signs. GCC has `znver5` targeting in the GCC 14 era, which matters for compiling the AVX-512 deterministic core"; AVX runtime build matrix — portable scalar baseline / AVX2 path / AVX-512 Zen5 path / runtime CPUID dispatch; "Never assume. Detect" | 13490–13506 |
| E0427 | Sovereign-OS 8 Planes + accountability + key line + 6-component peace machine — Kernel Plane (Linux 6.8/6.12+ + IOMMU + VFIO + cgroups2 + namespaces + io_uring) / Security Plane (AppArmor + LUKS2 + TPM-FIDO2 + seccomp + capabilities + network policy) / Compute Plane (NVIDIA driver-CUDA + ROC-free clarity + AVX-512 CPU core + model runtimes) / Storage Plane (ZFS snapshots + datasets + replay + rollback + ARC) / Sandbox Plane (Podman-rootless + bubblewrap + Deno + Python venvs + VMs + VFIO 3090) / Gateway Plane (Anthropic-first API + OpenAI-compatible shim + MCP + Claude Code hooks) / Observability Plane (journald + OpenTelemetry + DCGM + eBPF + Prometheus-Grafana) / Choice Plane (secure / dev / research / autonomous / offline / cloud-hybrid); 8 accountability questions (Who asked? / Which model-tool acted? / What context was exposed? / What permission allowed it? / What did it cost? / What changed? / Can it be rolled back? / Should it become memory?); KEY LINE — "Sovereign-OS is not a distro with AI installed. It is an operating environment where intelligence is permissioned, observable, reversible, and user-chosen"; 6-component peace machine — Debian 13/Ubuntu 24 gives the ground / Zen 5 AVX-512 gives deterministic law / Blackwell gives deep local cognition / 3090/VFIO gives safe experimentation / ZFS gives memory and rollback / AppArmor/LUKS/cgroups give boundaries / the gateway gives communication; "That is a peace machine: powerful enough to act, disciplined enough to explain itself" | 13510–13546 |

## Modules (M00731–M00747)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00731 | Operator framing — "peace, full communication and logic and intelligence everywhere" | 13309 | E0418 |
| M00732 | Sovereign substrate definition — package policy + kernel behavior + GPU driver reality + sandbox security + filesystem truth + user-controlled communication | 13328–13332 | E0418 |
| M00733 | Debian 13 reality — Trixie + support 2028 full + LTS 2030 + kernel 6.12 LTS + GCC 14.2 + Python 3.13 | 13336–13340 | E0419 |
| M00734 | Ubuntu 24.04 reality — kernel 6.8 + GCC 14 + glibc 2.39 + 5yr maintenance to May 2029 + optional extended | 13342–13344 | E0420 |
| M00735 | Two-personalities profile choice — Debian (stable/clean/sovereign/less vendor magic) vs Ubuntu (easier NVIDIA-CUDA/enterprise tooling/AppArmor defaults/broad vendor support) | 13350–13360 | E0421 |
| M00736 | Coordination machine — 10 properties (communication/translation/logic/verification/planning/memory/trust/consent/conflict reduction/shared understanding) | 13374–13384 | E0422 |
| M00737 | Accountable AI 6-step model — AI proposes / Policy checks / Tools execute in bounded space / Traces record / User can inspect / System learns | 13390–13396 | E0422 |
| M00738 | Sandbox vectors — 6 (rootless Podman / bubblewrap / Deno permissions / browser / Claude Code-tool sandboxes / VMs) | 13412–13418 | E0423 |
| M00739 | Security-profile bundles — 4 (secure / developer / agent-lab / high-risk) | 13422–13432 | E0423 |
| M00740 | Secrets controls — 7 (LUKS2 / TPM2-FIDO2 / per-project secrets / vault proxy / redaction / cost ledger / network egress) | 13442–13450 | E0424 |
| M00741 | systemd-cryptenroll — enrolls TPM2/FIDO2/PKCS#11 tokens into LUKS2 | 13452–13454 | E0424 |
| M00742 | NVIDIA driver listing — RTX PRO 6000 Blackwell Server Edition in driver 590.48.01 for Debian 13 | 13466–13468 | E0425 |
| M00743 | Driver-profile abstraction — core base (Debian-like sovereign policy) / AI driver profile (Ubuntu/NVIDIA-friendly stack where needed) | 13480–13486 | E0425 |
| M00744 | AVX runtime build matrix — portable scalar baseline / AVX2 path / AVX-512 Zen5 path / runtime CPUID dispatch ("Never assume. Detect") | 13498–13506 | E0426 |
| M00745 | 8 Sovereign-OS Planes — Kernel / Security / Compute / Storage / Sandbox / Gateway / Observability / Choice | 13510–13530 | E0427 |
| M00746 | 8 accountability questions — Who asked / Which model-tool / What context / What permission / What cost / What changed / Can roll back / Should become memory | 13534–13542 | E0427 |
| M00747 | Peace machine 6-substrate composition — Debian 13/Ubuntu 24 ground + Zen 5 AVX-512 law + Blackwell cognition + 3090/VFIO experimentation + ZFS memory/rollback + AppArmor/LUKS/cgroups boundaries + gateway communication | 13545–13546 + closing | E0427 |

## Features (F03656–F03740)

| Feature ID | Phrase | Dump line | Parent module |
|---|---|---|---|
| F03656 | Operator — "we are in a Debian 13 / Ubuntu 24 base OS mode (Sovereign-OS)" | 13308 | E0418 |
| F03657 | Operator — "You said it.. its a 'war' machine.. or rather anti-war" | 13309 | M00731 |
| F03658 | Operator — "peace, full communication and logic and intelligence everywhere" | 13309 | M00731 |
| F03659 | Operator — "continue. do researchs online too" | 13309 | E0418 |
| F03660 | AI confirmation — "Debian 13 / Ubuntu 24 as the Sovereign-OS base changes the bridge in a very concrete way" | 13328 | E0418 |
| F03661 | AI confirmation — "This is not just 'Linux'" | 13330 | E0418 |
| F03662 | AI confirmation — "It is the sovereign substrate" | 13330 | M00732 |
| F03663 | Sovereign substrate property — package policy | 13332 | M00732 |
| F03664 | Sovereign substrate property — kernel behavior | 13332 | M00732 |
| F03665 | Sovereign substrate property — GPU driver reality | 13332 | M00732 |
| F03666 | Sovereign substrate property — sandbox security | 13332 | M00732 |
| F03667 | Sovereign substrate property — filesystem truth | 13332 | M00732 |
| F03668 | Sovereign substrate property — user-controlled communication | 13332 | M00732 |
| F03669 | Debian 13 — "Trixie is the current stable release" | 13338 | M00733 |
| F03670 | Debian 13 — "support through 2028 full support" | 13338 | M00733 |
| F03671 | Debian 13 — "LTS through 2030" | 13338 | M00733 |
| F03672 | Debian 13 — "ships around Linux 6.12 LTS" | 13340 | M00733 |
| F03673 | Debian 13 — GCC 14.2 | 13340 | M00733 |
| F03674 | Debian 13 — Python 3.13 | 13340 | M00733 |
| F03675 | Debian 13 — refreshed stack | 13340 | M00733 |
| F03676 | Debian 13 URL — debian.org/releases/trixie/index | 13340 | M00733 |
| F03677 | Debian 13 URL — debian.org/releases/trixie/release-notes/ | 13340 | M00733 |
| F03678 | Ubuntu 24.04 — corporate/stable AI workstation path | 13342 | M00734 |
| F03679 | Ubuntu 24.04 — kernel 6.8 initially | 13344 | M00734 |
| F03680 | Ubuntu 24.04 — GCC 14 | 13344 | M00734 |
| F03681 | Ubuntu 24.04 — glibc 2.39 | 13344 | M00734 |
| F03682 | Ubuntu 24.04 — 5yr maintenance to May 2029 | 13344 | M00734 |
| F03683 | Ubuntu 24.04 — optional extended support | 13344 | M00734 |
| F03684 | Ubuntu 24.04 URL — documentation.ubuntu.com/release-notes/24.04 | 13344 | M00734 |
| F03685 | Two personalities — "Sovereign-OS can have two personalities" | 13348 | M00735 |
| F03686 | Debian 13 personality — stable | 13352 | M00735 |
| F03687 | Debian 13 personality — clean | 13352 | M00735 |
| F03688 | Debian 13 personality — sovereign | 13352 | M00735 |
| F03689 | Debian 13 personality — less vendor magic | 13352 | M00735 |
| F03690 | Debian 13 personality — excellent base for controlled systems | 13352 | M00735 |
| F03691 | Ubuntu 24.04 personality — easier NVIDIA/CUDA ecosystem | 13355 | M00735 |
| F03692 | Ubuntu 24.04 personality — enterprise tooling | 13355 | M00735 |
| F03693 | Ubuntu 24.04 personality — AppArmor defaults | 13355 | M00735 |
| F03694 | Ubuntu 24.04 personality — broad vendor support | 13355 | M00735 |
| F03695 | Profile choice — "That is not a contradiction. It is a profile choice" | 13360 | M00735 |
| F03696 | Peace machine — "Anti-war is the better term" | 13366 | E0422 |
| F03697 | Peace machine — "not a war machine in purpose" | 13370 | E0422 |
| F03698 | Peace machine — "coordination machine" | 13372 | M00736 |
| F03699 | Coordination — communication | 13374 | M00736 |
| F03700 | Coordination — translation | 13375 | M00736 |
| F03701 | Coordination — logic | 13376 | M00736 |
| F03702 | Coordination — verification | 13377 | M00736 |
| F03703 | Coordination — planning | 13378 | M00736 |
| F03704 | Coordination — memory | 13379 | M00736 |
| F03705 | Coordination — trust | 13380 | M00736 |
| F03706 | Coordination — consent | 13381 | M00736 |
| F03707 | Coordination — conflict reduction | 13382 | M00736 |
| F03708 | Coordination — shared understanding | 13383 | M00736 |
| F03709 | Accountability rule — "the OS must make intelligence accountable" | 13386 | E0422 |
| F03710 | Accountability — NOT "AI acts invisibly" | 13388 | M00737 |
| F03711 | Accountability step — AI proposes | 13390 | M00737 |
| F03712 | Accountability step — Policy checks | 13391 | M00737 |
| F03713 | Accountability step — Tools execute in bounded space | 13392 | M00737 |
| F03714 | Accountability step — Traces record | 13393 | M00737 |
| F03715 | Accountability step — User can inspect | 13394 | M00737 |
| F03716 | Accountability step — System learns | 13395 | M00737 |
| F03717 | "That is peace through legibility" | 13396 | E0422 |
| F03718 | Ubuntu 24.04 — "restricted unprivileged user namespaces via AppArmor" | 13404 | E0423 |
| F03719 | Ubuntu 24.04 — "limiting what unconfined apps can do inside user namespaces" | 13406 | E0423 |
| F03720 | Security URL — documentation.ubuntu.com/security/security-features/security-features-overview/ | 13408 | E0423 |
| F03721 | Sandbox vector — rootless Podman | 13412 | M00738 |
| F03722 | Sandbox vector — bubblewrap | 13413 | M00738 |
| F03723 | Sandbox vector — Deno permissions | 13414 | M00738 |
| F03724 | Sandbox vector — browser sandboxes | 13415 | M00738 |
| F03725 | Sandbox vector — Claude Code / tool sandboxes | 13416 | M00738 |
| F03726 | Sandbox vector — VMs | 13417 | M00738 |
| F03727 | Security profile — secure (restrictive user namespaces + AppArmor enforced) | 13422–13424 | M00739 |
| F03728 | Security profile — developer (allow specific sandbox frameworks) | 13425–13426 | M00739 |
| F03729 | Security profile — agent-lab (controlled exceptions for Podman/bubblewrap/browser/VM) | 13427–13429 | M00739 |
| F03730 | Security profile — high-risk (move to VM/microVM instead of loosening host) | 13430–13432 | M00739 |
| F03731 | "Security is not one setting. It is a user-visible operating mode" | 13434 | E0423 |
| F03732 | Secrets — "must guard secrets like a body guards organs" | 13438 | E0424 |
| F03733 | Secrets — LUKS2 / TPM2-FIDO2 / per-project / vault proxy / redaction / cost ledger / network egress | 13442–13450 | M00740 |
| F03734 | systemd-cryptenroll — TPM2/FIDO2/PKCS#11 into LUKS2 + URL manpages.ubuntu.com/manpages/noble/man1/systemd-cryptenroll.1.html | 13452–13454 | M00741 |
| F03735 | NVIDIA — RTX PRO 6000 Blackwell Server Edition in Debian-13 driver 590.48.01 + URL nvidia.com/download/driverResults.aspx/259501/en-us | 13464–13468 | M00742 |
| F03736 | NVIDIA — Ubuntu 24.04 smoother CUDA packaging | 13470 | E0425 |
| F03737 | Driver abstraction — core base Debian-like sovereign policy / AI driver profile Ubuntu/NVIDIA-friendly | 13480–13486 | M00743 |
| F03738 | AVX build matrix — portable scalar baseline / AVX2 path / AVX-512 Zen5 path / runtime CPUID dispatch | 13498–13504 | M00744 |
| F03739 | "Never assume. Detect" | 13506 | M00744 |
| F03740 | 8 Sovereign-OS Planes + 8 accountability questions + key line + 6-component peace machine ("powerful enough to act, disciplined enough to explain itself") | 13510–13546 | M00745 + M00746 + M00747 |

## Requirements (R07311–R07480)

| Req ID | Phrase | Dump line | Parent feature | Negotiability | Layer-B metric | Priority |
|---|---|---|---|---|---|---|
| R07311 | Operator directive — Sovereign-OS is in Debian 13 / Ubuntu 24 base OS mode | 13308 | F03656 | non-negotiable | false | 10 |
| R07312 | Operator phrase — "war machine" | 13309 | F03657 | non-negotiable | false | 10 |
| R07313 | Operator phrase — "anti-war" preferred | 13309 | F03657 | non-negotiable | false | 10 |
| R07314 | Operator phrase — "peace" | 13309 | F03658 | non-negotiable | false | 10 |
| R07315 | Operator phrase — "full communication" | 13309 | F03658 | non-negotiable | false | 10 |
| R07316 | Operator phrase — "logic and intelligence everywhere" | 13309 | F03658 | non-negotiable | false | 10 |
| R07317 | Operator directive — "continue. do researchs online too" | 13309 | F03659 | non-negotiable | false | 10 |
| R07318 | "Debian 13 / Ubuntu 24 as the Sovereign-OS base changes the bridge in a very concrete way" | 13328 | F03660 | non-negotiable | false | 10 |
| R07319 | "This is not just 'Linux'" | 13330 | F03661 | non-negotiable | false | 10 |
| R07320 | "It is the sovereign substrate" | 13330 | F03662 | non-negotiable | false | 10 |
| R07321 | Sovereign substrate — package policy | 13332 | F03663 | non-negotiable | false | 10 |
| R07322 | Sovereign substrate — kernel behavior | 13332 | F03664 | non-negotiable | false | 10 |
| R07323 | Sovereign substrate — GPU driver reality | 13332 | F03665 | non-negotiable | false | 10 |
| R07324 | Sovereign substrate — sandbox security | 13332 | F03666 | non-negotiable | false | 10 |
| R07325 | Sovereign substrate — filesystem truth | 13332 | F03667 | non-negotiable | false | 10 |
| R07326 | Sovereign substrate — user-controlled communication | 13332 | F03668 | non-negotiable | false | 10 |
| R07327 | Debian 13 — Trixie is the current stable release | 13338 | F03669 | non-negotiable | false | 10 |
| R07328 | Debian 13 — support through 2028 full support | 13338 | F03670 | non-negotiable | false | 10 |
| R07329 | Debian 13 — LTS through 2030 | 13338 | F03671 | non-negotiable | false | 10 |
| R07330 | Debian 13 — Linux 6.12 LTS | 13340 | F03672 | non-negotiable | false | 10 |
| R07331 | Debian 13 — GCC 14.2 | 13340 | F03673 | non-negotiable | false | 10 |
| R07332 | Debian 13 — Python 3.13 | 13340 | F03674 | non-negotiable | false | 10 |
| R07333 | Debian 13 — refreshed stack | 13340 | F03675 | non-negotiable | false | 10 |
| R07334 | Debian 13 release info URL | 13340 | F03676 | non-negotiable | false | 10 |
| R07335 | Debian 13 release notes URL | 13340 | F03677 | non-negotiable | false | 10 |
| R07336 | Ubuntu 24.04 — corporate/stable AI workstation path | 13342 | F03678 | non-negotiable | false | 10 |
| R07337 | Ubuntu 24.04 — kernel 6.8 initially | 13344 | F03679 | non-negotiable | false | 10 |
| R07338 | Ubuntu 24.04 — GCC 14 | 13344 | F03680 | non-negotiable | false | 10 |
| R07339 | Ubuntu 24.04 — glibc 2.39 | 13344 | F03681 | non-negotiable | false | 10 |
| R07340 | Ubuntu 24.04 — 5 years maintenance to May 2029 | 13344 | F03682 | non-negotiable | false | 10 |
| R07341 | Ubuntu 24.04 — optional extended support | 13344 | F03683 | non-negotiable | false | 10 |
| R07342 | Ubuntu 24.04 release notes URL | 13344 | F03684 | non-negotiable | false | 10 |
| R07343 | "Sovereign-OS can have two personalities" | 13348 | F03685 | non-negotiable | false | 10 |
| R07344 | Debian 13 personality — stable | 13352 | F03686 | non-negotiable | false | 10 |
| R07345 | Debian 13 personality — clean | 13352 | F03687 | non-negotiable | false | 10 |
| R07346 | Debian 13 personality — sovereign | 13352 | F03688 | non-negotiable | false | 10 |
| R07347 | Debian 13 personality — less vendor magic | 13352 | F03689 | non-negotiable | false | 10 |
| R07348 | Debian 13 personality — excellent base for controlled systems | 13352 | F03690 | non-negotiable | false | 10 |
| R07349 | Ubuntu 24.04 personality — easier NVIDIA/CUDA ecosystem | 13355 | F03691 | non-negotiable | false | 10 |
| R07350 | Ubuntu 24.04 personality — enterprise tooling | 13355 | F03692 | non-negotiable | false | 10 |
| R07351 | Ubuntu 24.04 personality — AppArmor defaults | 13355 | F03693 | non-negotiable | false | 10 |
| R07352 | Ubuntu 24.04 personality — broad vendor support | 13355 | F03694 | non-negotiable | false | 10 |
| R07353 | "That is not a contradiction. It is a profile choice" | 13360 | F03695 | non-negotiable | false | 10 |
| R07354 | "Anti-war is the better term" | 13366 | F03696 | non-negotiable | false | 10 |
| R07355 | "The system is not a war machine in purpose" | 13370 | F03697 | non-negotiable | false | 10 |
| R07356 | "It is a coordination machine" | 13372 | F03698 | non-negotiable | false | 10 |
| R07357 | Coordination property — communication | 13374 | F03699 | non-negotiable | false | 10 |
| R07358 | Coordination property — translation | 13375 | F03700 | non-negotiable | false | 10 |
| R07359 | Coordination property — logic | 13376 | F03701 | non-negotiable | false | 10 |
| R07360 | Coordination property — verification | 13377 | F03702 | non-negotiable | false | 10 |
| R07361 | Coordination property — planning | 13378 | F03703 | non-negotiable | false | 10 |
| R07362 | Coordination property — memory | 13379 | F03704 | non-negotiable | false | 10 |
| R07363 | Coordination property — trust | 13380 | F03705 | non-negotiable | false | 10 |
| R07364 | Coordination property — consent | 13381 | F03706 | non-negotiable | false | 10 |
| R07365 | Coordination property — conflict reduction | 13382 | F03707 | non-negotiable | false | 10 |
| R07366 | Coordination property — shared understanding | 13383 | F03708 | non-negotiable | false | 10 |
| R07367 | "The OS must make intelligence accountable" | 13386 | F03709 | non-negotiable | false | 10 |
| R07368 | NOT — "AI acts invisibly" | 13388 | F03710 | non-negotiable | false | 10 |
| R07369 | Accountability — AI proposes | 13390 | F03711 | non-negotiable | false | 10 |
| R07370 | Accountability — Policy checks | 13391 | F03712 | non-negotiable | false | 10 |
| R07371 | Accountability — Tools execute in bounded space | 13392 | F03713 | non-negotiable | false | 10 |
| R07372 | Accountability — Traces record | 13393 | F03714 | non-negotiable | false | 10 |
| R07373 | Accountability — User can inspect | 13394 | F03715 | non-negotiable | false | 10 |
| R07374 | Accountability — System learns | 13395 | F03716 | non-negotiable | false | 10 |
| R07375 | "That is peace through legibility" | 13396 | F03717 | non-negotiable | false | 10 |
| R07376 | Security — Ubuntu 24.04 AppArmor/user-namespace work directly relevant | 13400 | E0423 | non-negotiable | false | 10 |
| R07377 | Security — Ubuntu documents restricted unprivileged user namespaces via AppArmor in 24.04 | 13404 | F03718 | non-negotiable | false | 10 |
| R07378 | Security — limits what unconfined apps can do inside user namespaces | 13406 | F03719 | non-negotiable | false | 10 |
| R07379 | Security URL — Ubuntu security-features overview | 13408 | F03720 | non-negotiable | false | 10 |
| R07380 | Security — "agents love sandboxes" | 13410 | E0423 | non-negotiable | false | 10 |
| R07381 | Sandbox vector — rootless Podman | 13412 | F03721 | non-negotiable | false | 10 |
| R07382 | Sandbox vector — bubblewrap | 13413 | F03722 | non-negotiable | false | 10 |
| R07383 | Sandbox vector — Deno permissions | 13414 | F03723 | non-negotiable | false | 10 |
| R07384 | Sandbox vector — browser sandboxes | 13415 | F03724 | non-negotiable | false | 10 |
| R07385 | Sandbox vector — Claude Code / tool sandboxes | 13416 | F03725 | non-negotiable | false | 10 |
| R07386 | Sandbox vector — VMs | 13417 | F03726 | non-negotiable | false | 10 |
| R07387 | Security — "sandboxing depends on kernel/user namespace behavior" | 13420 | E0423 | non-negotiable | false | 10 |
| R07388 | Security profile — secure: restrictive user namespaces | 13423 | F03727 | non-negotiable | false | 10 |
| R07389 | Security profile — secure: AppArmor enforced | 13424 | F03727 | non-negotiable | false | 10 |
| R07390 | Security profile — developer: allow specific sandbox frameworks | 13426 | F03728 | non-negotiable | false | 10 |
| R07391 | Security profile — agent-lab: controlled exceptions for Podman | 13428 | F03729 | non-negotiable | false | 10 |
| R07392 | Security profile — agent-lab: controlled exceptions for bubblewrap | 13428 | F03729 | non-negotiable | false | 10 |
| R07393 | Security profile — agent-lab: controlled exceptions for browser | 13428 | F03729 | non-negotiable | false | 10 |
| R07394 | Security profile — agent-lab: controlled exceptions for VM | 13428 | F03729 | non-negotiable | false | 10 |
| R07395 | Security profile — high-risk: move to VM/microVM instead of loosening host | 13431 | F03730 | non-negotiable | false | 10 |
| R07396 | "Security is not one setting. It is a user-visible operating mode" | 13434 | F03731 | non-negotiable | false | 10 |
| R07397 | Secrets — "A peace/intelligence OS must guard secrets like a body guards organs" | 13438 | F03732 | non-negotiable | false | 10 |
| R07398 | Secret control — LUKS2 full disk encryption | 13442 | F03733 | non-negotiable | false | 10 |
| R07399 | Secret control — TPM2/FIDO2 unlock options | 13443 | F03733 | non-negotiable | false | 10 |
| R07400 | Secret control — per-project secrets | 13444 | F03733 | non-negotiable | false | 10 |
| R07401 | Secret control — vault proxy / stub credentials | 13445 | F03733 | non-negotiable | false | 10 |
| R07402 | Secret control — redaction before cloud | 13446 | F03733 | non-negotiable | false | 10 |
| R07403 | Secret control — cost ledger | 13447 | F03733 | non-negotiable | false | 10 |
| R07404 | Secret control — network egress policy | 13448 | F03733 | non-negotiable | false | 10 |
| R07405 | systemd-cryptenroll supports TPM2 token enrollment into LUKS2 | 13452 | F03734 | non-negotiable | false | 10 |
| R07406 | systemd-cryptenroll supports FIDO2 token enrollment into LUKS2 | 13452 | F03734 | non-negotiable | false | 10 |
| R07407 | systemd-cryptenroll supports PKCS#11 token enrollment into LUKS2 | 13452 | F03734 | non-negotiable | false | 10 |
| R07408 | systemd-cryptenroll URL — manpages.ubuntu.com/manpages/noble/man1/systemd-cryptenroll.1.html | 13454 | F03734 | non-negotiable | false | 10 |
| R07409 | Sovereign-OS identity — user presence | 13458 | M00741 | non-negotiable | false | 10 |
| R07410 | Sovereign-OS identity — device identity | 13458 | M00741 | non-negotiable | false | 10 |
| R07411 | Sovereign-OS identity — encrypted memory of the system | 13458 | M00741 | non-negotiable | false | 10 |
| R07412 | NVIDIA — Blackwell on Linux means driver discipline | 13462 | E0425 | non-negotiable | false | 10 |
| R07413 | NVIDIA — Debian 13 data center driver listing | 13464 | F03735 | non-negotiable | false | 10 |
| R07414 | NVIDIA — RTX PRO 6000 Blackwell Server Edition in driver 590.48.01 | 13466 | F03735 | non-negotiable | false | 10 |
| R07415 | NVIDIA driver URL — nvidia.com/download/driverResults.aspx/259501/en-us | 13468 | F03735 | non-negotiable | false | 10 |
| R07416 | NVIDIA — Ubuntu 24.04 smoother path for CUDA packaging | 13470 | F03736 | non-negotiable | false | 10 |
| R07417 | NVIDIA Practical bridge — Debian 13 stronger sovereign base | 13474 | E0425 | non-negotiable | false | 10 |
| R07418 | NVIDIA Practical bridge — Debian 13 may need more NVIDIA driver care | 13475 | E0425 | non-negotiable | false | 10 |
| R07419 | NVIDIA Practical bridge — Ubuntu 24.04 smoother CUDA/NVIDIA path | 13477 | E0425 | non-negotiable | false | 10 |
| R07420 | NVIDIA Practical bridge — Ubuntu 24.04 more vendor-supported AI workflows | 13478 | E0425 | non-negotiable | false | 10 |
| R07421 | Driver abstraction — core base: Debian-like sovereign policy | 13483 | F03737 | non-negotiable | false | 10 |
| R07422 | Driver abstraction — AI driver profile: Ubuntu/NVIDIA-friendly stack where needed | 13485 | F03737 | non-negotiable | false | 10 |
| R07423 | Kernel/Compiler — "Zen 5 wants modern kernel and compiler" | 13490 | E0426 | non-negotiable | false | 10 |
| R07424 | Kernel/Compiler — Debian 13's kernel 6.12/GCC 14.2 are good signs | 13492 | E0426 | non-negotiable | false | 10 |
| R07425 | Kernel/Compiler — Ubuntu 24.04's GCC 14 line is a good sign | 13494 | E0426 | non-negotiable | false | 10 |
| R07426 | Kernel/Compiler — GCC has `znver5` targeting in the GCC 14 era | 13496 | E0426 | non-negotiable | false | 10 |
| R07427 | Kernel/Compiler — `znver5` matters for compiling the AVX-512 deterministic core | 13496 | E0426 | non-negotiable | false | 10 |
| R07428 | AVX build matrix — portable scalar baseline | 13500 | F03738 | non-negotiable | false | 10 |
| R07429 | AVX build matrix — AVX2 path | 13501 | F03738 | non-negotiable | false | 10 |
| R07430 | AVX build matrix — AVX-512 Zen5 path | 13502 | F03738 | non-negotiable | false | 10 |
| R07431 | AVX build matrix — runtime CPUID dispatch | 13503 | F03738 | non-negotiable | false | 10 |
| R07432 | AVX build matrix doctrine — "Never assume" | 13506 | F03739 | non-negotiable | false | 10 |
| R07433 | AVX build matrix doctrine — "Detect" | 13506 | F03739 | non-negotiable | false | 10 |
| R07434 | Sovereign-OS Plane — Kernel | 13512 | M00745 | non-negotiable | false | 10 |
| R07435 | Kernel Plane — Linux 6.8/6.12+ | 13513 | M00745 | non-negotiable | false | 10 |
| R07436 | Kernel Plane — IOMMU | 13513 | M00745 | non-negotiable | false | 10 |
| R07437 | Kernel Plane — VFIO | 13513 | M00745 | non-negotiable | false | 10 |
| R07438 | Kernel Plane — cgroups2 | 13513 | M00745 | non-negotiable | false | 10 |
| R07439 | Kernel Plane — namespaces | 13513 | M00745 | non-negotiable | false | 10 |
| R07440 | Kernel Plane — io_uring | 13513 | M00745 | non-negotiable | false | 10 |
| R07441 | Sovereign-OS Plane — Security | 13515 | M00745 | non-negotiable | false | 10 |
| R07442 | Security Plane — AppArmor | 13516 | M00745 | non-negotiable | false | 10 |
| R07443 | Security Plane — LUKS2 | 13516 | M00745 | non-negotiable | false | 10 |
| R07444 | Security Plane — TPM/FIDO2 | 13516 | M00745 | non-negotiable | false | 10 |
| R07445 | Security Plane — seccomp | 13516 | M00745 | non-negotiable | false | 10 |
| R07446 | Security Plane — capabilities | 13516 | M00745 | non-negotiable | false | 10 |
| R07447 | Security Plane — network policy | 13516 | M00745 | non-negotiable | false | 10 |
| R07448 | Sovereign-OS Plane — Compute | 13518 | M00745 | non-negotiable | false | 10 |
| R07449 | Compute Plane — NVIDIA driver/CUDA | 13519 | M00745 | non-negotiable | false | 10 |
| R07450 | Compute Plane — ROC-free clarity | 13519 | M00745 | non-negotiable | false | 10 |
| R07451 | Compute Plane — AVX-512 CPU core | 13519 | M00745 | non-negotiable | false | 10 |
| R07452 | Compute Plane — model runtimes | 13519 | M00745 | non-negotiable | false | 10 |
| R07453 | Sovereign-OS Plane — Storage | 13521 | M00745 | non-negotiable | false | 10 |
| R07454 | Storage Plane — ZFS snapshots | 13522 | M00745 | non-negotiable | false | 10 |
| R07455 | Storage Plane — datasets | 13522 | M00745 | non-negotiable | false | 10 |
| R07456 | Storage Plane — replay | 13522 | M00745 | non-negotiable | false | 10 |
| R07457 | Storage Plane — rollback | 13522 | M00745 | non-negotiable | false | 10 |
| R07458 | Storage Plane — ARC | 13522 | M00745 | non-negotiable | false | 10 |
| R07459 | Sovereign-OS Plane — Sandbox | 13524 | M00745 | non-negotiable | false | 10 |
| R07460 | Sandbox Plane — Podman/rootless | 13525 | M00745 | non-negotiable | false | 10 |
| R07461 | Sandbox Plane — bubblewrap + Deno + Python venvs + VMs + VFIO 3090 | 13525 | M00745 | non-negotiable | false | 10 |
| R07462 | Sovereign-OS Plane — Gateway | 13527 | M00745 | non-negotiable | false | 10 |
| R07463 | Gateway Plane — Anthropic-first API | 13528 | M00745 | non-negotiable | false | 10 |
| R07464 | Gateway Plane — OpenAI-compatible shim | 13528 | M00745 | non-negotiable | false | 10 |
| R07465 | Gateway Plane — MCP | 13528 | M00745 | non-negotiable | false | 10 |
| R07466 | Gateway Plane — Claude Code hooks | 13528 | M00745 | non-negotiable | false | 10 |
| R07467 | Sovereign-OS Plane — Observability | 13530 | M00745 | non-negotiable | false | 10 |
| R07468 | Observability Plane — journald + OpenTelemetry + DCGM + eBPF + Prometheus/Grafana | 13531 | M00745 | non-negotiable | false | 10 |
| R07469 | Sovereign-OS Plane — Choice | 13533 | M00745 | non-negotiable | false | 10 |
| R07470 | Choice Plane — secure / dev / research / autonomous / offline / cloud-hybrid | 13534 | M00745 | non-negotiable | false | 10 |
| R07471 | Accountability question — Who asked? | 13536 | M00746 | non-negotiable | false | 10 |
| R07472 | Accountability question — Which model/tool acted? | 13537 | M00746 | non-negotiable | false | 10 |
| R07473 | Accountability question — What context was exposed? | 13538 | M00746 | non-negotiable | false | 10 |
| R07474 | Accountability question — What permission allowed it? | 13539 | M00746 | non-negotiable | false | 10 |
| R07475 | Accountability question — What did it cost? + What changed? + Can it be rolled back? + Should it become memory? | 13540–13542 | M00746 | non-negotiable | false | 10 |
| R07476 | Key line — "Sovereign-OS is not a distro with AI installed" | 13544 | M00747 | non-negotiable | false | 10 |
| R07477 | Key line — "It is an operating environment where intelligence is permissioned, observable, reversible, and user-chosen" | 13546 | M00747 | non-negotiable | false | 10 |
| R07478 | Peace machine substrate — Debian 13/Ubuntu 24 gives the ground + Zen 5 AVX-512 gives deterministic law + Blackwell gives deep local cognition + 3090/VFIO gives safe experimentation + ZFS gives memory and rollback + AppArmor/LUKS/cgroups give boundaries + gateway gives communication | closing of M044 section | M00747 | non-negotiable | false | 10 |
| R07479 | Peace machine doctrine — "powerful enough to act, disciplined enough to explain itself" | closing of M044 section | M00747 | non-negotiable | false | 10 |
| R07480 | Composite — M044 (10 epics / 17 modules / 85 features / 170 reqs) catalogs Sovereign-OS substrate Debian 13 / Ubuntu 24: sovereign substrate definition (6 properties) + Debian 13 reality (Trixie, 2028/2030 support, Linux 6.12 LTS, GCC 14.2, Python 3.13) + Ubuntu 24.04 reality (kernel 6.8, GCC 14, glibc 2.39, 2029 maintenance) + two-personalities profile choice + peace machine frame (anti-war coordination machine 10 properties + accountable AI 6-step model + "peace through legibility") + security substrate (AppArmor restricted user namespaces + 6 sandbox vectors + 4 security-profile bundles + "user-visible operating mode") + secrets + identity (7 controls + systemd-cryptenroll TPM2/FIDO2/PKCS#11 LUKS2) + NVIDIA reality (RTX PRO 6000 Blackwell driver 590.48.01 + driver-profile abstraction) + kernel/compiler (Zen 5 + GCC 14 znver5 + AVX runtime build matrix "Never assume. Detect") + 8 Sovereign-OS Planes (Kernel/Security/Compute/Storage/Sandbox/Gateway/Observability/Choice) + 8 accountability questions + KEY LINE "Sovereign-OS is not a distro with AI installed. It is an operating environment where intelligence is permissioned, observable, reversible, and user-chosen" + 6-component peace machine "powerful enough to act, disciplined enough to explain itself" | 13307–13546 | E0418-E0427 | non-negotiable | false | 10 |

## Sub-requirements accounting

- 170 requirements covering: operator directives (R07311–R07317) + sovereign substrate 6 properties (R07318–R07326) + Debian 13 reality + URLs (R07327–R07335) + Ubuntu 24.04 reality + URL (R07336–R07342) + two personalities (R07343–R07353) + peace machine + 10 coordination properties + accountable AI 6 steps + "peace through legibility" (R07354–R07375) + security substrate (AppArmor + 6 sandbox vectors + 4 profiles + "user-visible operating mode") (R07376–R07396) + secrets + 7 controls + systemd-cryptenroll + identity (R07397–R07411) + NVIDIA reality + driver-profile abstraction (R07412–R07422) + kernel/compiler + AVX build matrix (R07423–R07433) + 8 Sovereign-OS Planes (Kernel/Security/Compute/Storage/Sandbox/Gateway/Observability/Choice) (R07434–R07470) + 8 accountability questions + key line + peace machine substrate (R07471–R07479) + composite (R07480)
- Source range 13307–13546 yields 239 lines; 170 R-rows represent ~71% line-coverage at the verbatim-citation level
- Project boundary — M044 is sovereign-os OS-substrate scope; selfdef IPS substrate runs ON TOP of M044 base (Debian 13 / Ubuntu 24) but is itself an installed Debian package (MS025 detect-host)

## Cross-references

- Adjacent dump-range milestones: M043 bridge layer hardware-aware intelligence scheduling (12614–12944) / M045 Linux as intelligence governor — cgroup v2 / systemd / PSI / eBPF (next; dump 13546–13825)
- Plane integration — M044 8 Sovereign-OS Planes overlay ALL prior milestones (M025 Cognitive Compiler runs on Compute Plane / M026 SLM swarm + M027 Value Plane in Compute / M028 Memory OS in Storage + Compute / M029 Computer-Use in Sandbox + Compute / M030 World Model in Storage + Compute / M031 Symbolic Planning in Compute / M032 Cloud Expert in Gateway / M033 Compatibility Gateway + M034 Anthropic-first Gateway in Gateway / M035 Frontier in Compute / M036 MAP in Compute + Storage / M037 Spec-TDD evidence-driven autonomy in Observability + Choice / M038 Hardware-aware AIDLC in Compute / M039 AVX-512 cortex hot path in Compute / M040 hyper features in Compute + Sandbox + Storage + Choice / M041 7-contract architecture in Choice + Observability + Security / M042 Choice Architecture in Choice / M043 Bridge Layer hardware-aware intelligence scheduling in Compute + Choice)
- Selfdef integration — selfdef IPS substrate (MS025 detect-host) runs ON M044 Debian 13/Ubuntu 24 base; selfdef-daemon Debian package installs into M044 substrate; selfdef MS013 27-SDD ledger F-2027-022 documents the kind=debian-package contract that detect-host uses on the M044 base; selfdef MS019 threat model attack surfaces are scoped on the M044 8-plane substrate
- Security profile — M044 4 security profiles (secure/developer/agent-lab/high-risk) align with selfdef MS017 agent-guard 2 profiles + 2 scope strategies
- Hardware reality — M044 base hosts Ryzen 9900X Zen 5 AVX-512 + RTX PRO 6000 Blackwell 96GB + RTX 3090 24GB + ProArt X870E-Creator; NVIDIA driver 590.48.01 supports RTX PRO 6000 Blackwell Server Edition on Debian 13
- Cross-repo binding — M044 8-plane definition may surface to selfdef via MS007 audit-manifest typed-mirror crate (the Sovereign-OS-substrate definition is a doctrine selfdef can audit against)
- Operator references: debian.org/releases/trixie/index + debian.org/releases/trixie/release-notes/ + documentation.ubuntu.com/release-notes/24.04 + documentation.ubuntu.com/security/security-features/security-features-overview/ + manpages.ubuntu.com/manpages/noble/man1/systemd-cryptenroll.1.html + nvidia.com/download/driverResults.aspx/259501/en-us + Debian 13 AppArmor systemd bubblewrap podman rootless docs (web search) + GCC 14 znver5 manual
