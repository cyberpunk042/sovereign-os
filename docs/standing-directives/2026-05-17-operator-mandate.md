# Standing operator mandate — 2026-05-17

> **Why this file exists.** The harness's `/goal` command sets a Stop-hook
> condition that *auto-clears* once any single check matches it. The
> operator's actual intent is the OPPOSITE: the goal text is a
> **multi-month, compound, long-running mandate** that drives months of
> Epic/Module/Task work, not a single completion gate. This file is the
> durable record. Future sessions read THIS file (not the ephemeral
> `/goal` Stop hook) as the source of truth.
>
> **Operator quote that triggered this file (verbatim, sacrosanct):**
>
> > "if I cannot set a goal and let it drive for over 4 hours this
> > feature is useless... the goal of the command goal is so that it
> > continue because you know it can even possibly never even reach the
> > end or its really really far so it can only slowly by slowly
> > progress inside the proper workflow.. SDD & TDD and SFIF and Design
> > Patterns and OOP and SRP and documentation and all. and even if it
> > a goal command you should register what I said so that you can
> > break it down and have identifiable and workable pieces and so we
> > can make sure we dont minimize or reduce or conflate or corrupt
> > what was said.. most of the thing I said they compound, meaning
> > that it multiply even at time where 1 thing lead to multiplied by
> > 2-3 multiplied by 2-3 multiplied by 2-3 multiplied by 2-3
> > multiplied by 2-3, etc, at some point its a lot of development
> > needed with all the layers and flexibilities and features and
> > options and modules and project and pieces. The goal is to have
> > the goal drive a very long PR or very long changes on the main if
> > given authority and planify long development, creating Epics,
> > Modules, Tasks, etc.. again here make sure you record this and
> > make sure we do some things about it. As always think before act.
> > do not confuse /goal with a normal prompt / a normal request... I
> > do not want to have to repeat any of this. Do not minimize anything
> > nor the situation."

## 1. The operator mandate (verbatim, sacrosanct)

Reproduced VERBATIM from the multiple `/goal` invocations across this
arc; no editorialization, no reduction. Each `/goal` is **additive**
— never replaces a prior one. The mandate is the **union** of every
verbatim block below.

When future rounds quote it, they quote from here.

### §1.0 — Re-instate directive (2026-05-17, operator paste-record session)

> "lets record and re-instate ... continue till you meet ALL MY
> REQUIREMENTS without MINIMIZING or rephrasing or compressing or
> conflating.. RETURN REREAD ALL THE RAW DUMP AND REPROCESS IF YOU
> NEED or JUST ask me question if you are lost"

Operative interpretation:
- The five `/goal` blocks the operator pasted in the same session
  are ALL part of the standing mandate. None supersedes another.
- "till there is really no work left" is the stop condition
  (operative for §1a, applies to all). Default = perpetual.
- Re-read raw dumps at `devops-solutions-information-hub/raw/`
  rather than re-asking the operator for context already given.
- Ask questions ONLY when genuinely ambiguous, not as a default.

### §1a — Branch + PR + ultimate-OS posture

> "/ goal continue till there is really no work left. you can keep
> working in selfdef branch and have a work PR (not blocked at
> draft) that keep cummulating and that when a massive group of
> changes and features are ready we merge it.. a branch relative
> the changes / additions and everything to the selfdef and its
> modules and integrations and the sovereign os. Keep in mind that
> you can improve at any layer the solution.... remember this is
> way more than a basic Debian 13 (non-GUI)... its a powerhouse OS
> with superpower features and a selfdef and advanced features so
> well suited. And observability, and operability and configuration
> and personalisation. ALl of this can be thought through and where
> they fit properly and how and such and DO NOT MINIMIZE.. this is
> going to be my ultimate selfdef with the ultimate modules and
> integrations and the Ultimate Sovereign OS for WorkStation AI of
> various profiles but clearly aimed to the specified system with
> the avx512 and the rtx pro 6000 and rtx3090 and 256gb ram ....
> Like I said you can work in selfdef too. both is fine, but in
> selfdef use a branch and a 'never ending' PR instead of the main
> like for the sovereign OS right now. This include all the
> requirements from the raw dumps including the flexibility and
> configuration possible, endless flexibility and fine-tuning and
> adapting possible: Wasm-to-AVX-512 AOT, A single 512-bit ZMM
> vector register can hold and manipulate.... 1-bit models, exploit
> of the hardware to the max including resaerch and continuously
> evolving specs to drive and evolve the SDD and TDD and the full
> IAC and User Experience and Developer experience and an assistant
> feel and clear path and options and modules combo features and
> super-features...."

Concrete operator-named additions in §1a not yet in the decomposition:
- **PR not-blocked-at-draft posture** for selfdef cycle-N PR
  (PR #198 lifted from draft 2026-05-17 per this directive).
- **Ultimate Sovereign OS for WorkStation AI** aimed at the SPECIFIC
  system: AVX-512 (Zen 5 9900X), RTX PRO 6000, RTX 3090, **256 GB RAM**.
- **Wasm-to-AVX-512 AOT pipeline** (Pulse §20 from raw dump): the
  `znver5`-targeted Cranelift/Wasmtime compile path that emits native
  AVX-512 machine code, bypassing JIT fallbacks.
- **1-bit / ternary models on ZMM registers** (raw dump §17.1 + §20):
  pack 2 bits per parameter, VPDPBUSD INT8 path, 5-12 tok/s on CPU.
- **Hardware exploit to the max** including continuous research +
  spec evolution (SDD + TDD evolve as research evolves).
- **Full IaC + Developer experience + assistant feel** + clear path
  + options + modules-combo-features + super-features.

### §1b — Multi-mode functioning + grey-out UX + REPL tiers (2026-05-17)

> "/ goal there are going to be multiple mode of functioning too,
> like LM Studio and LM Link maybe ? Unsloth ? ... not just a mode
> by profile but a profile that is flexible and allow not only the
> AI and the tools but also me to download, fine-tune, parameters,
> build, run, use and train and adapt and use and eval and etc.
> ... Hotswap from one CPU mode to another to another with some
> auto option(s). Same for the GPU I guess and this like the
> tracking of the state like the watt set consumption for the GPU
> ... with a warning if the RTX 3090 which should be sliglly reduce
> which isn't ... With scans too. with autohealth and doctor and
> analysis and event and notification and messaging. ... non docker
> vs docker install ? possible ? greyout the option that require it
> and/or offer the alternative ... obviously the module if not
> installed would not appear in the dashboard but only in the
> options of the dashboard which offer to install any previously
> non-installed modules or features ... It allow to see the
> management of the software raid and observe and operate and
> configure. to see all the logs files and need for log rotate,
> track files system usage and for each partitions and global and
> such. Offer insights. Allow to interoperate with an MCP via tools
> calls and/or MCP. ... Debian 13 Sovereign OS is a non-GUI by
> default. ... Everything via dashboard/UInterface or terminal
> tools OR AI, as my chose or even needs. ... Programming,
> Proto-Programing, Proto-Proto-Programming and inside REPL you
> do you own things and you even have custom CoT or such ... You do
> not need to wait for me to approve you PR, you can grow a PR for
> a long time ..."

### §1c, §1d, §1e — Hardware-stack expansion (2026-05-17, three times)

> "/ goal Its not only going to be an AI and an AI training station
> with an AI able system but only a guide into the experiece, into
> the field, into the kernel, into the hardware, into the OS, ...
> Memory too I guess and bios settings directives and admonition of
> things that might also not be possible on some board, possibly
> detecting the ASUS ProArt X870E-CREATOR WIFI and its settings and
> potential optimisations and fixes. pci lane splits and whatever
> like virtualization or what we find relevant via search online
> and such. Adapting / Considering the given PSU (probably not
> detectable ?) wattage and rating ? (me: be Quiet! Dark Power Pro
> 13 1600W Power Supply | ATX 3.1 Compliant | 80 Plus Titanium),
> considering XMP profile and OC profile and room for each and
> estimated at 100% usage and then real time tracking and
> intelligence around it. (Possibly heat too I guess) My PSU even
> have an overclock mode which might be important. Then there is
> the PSU/APC integration with the power mangement and the
> scheduled shutdown when battery reach a certain point as one
> default profile. (schedule/planifest/graceful on all levels,
> orderly). ... Apply what I said at scale and you have for a very
> long time of work. Take your time, do this right."

(§1c, §1d, §1e are three pastes of the same long /goal text — kept
as one canonical entry; the repetition itself is the signal: this
is the most-emphasized block.)

### §1f — full operator paste reproduced verbatim below (unchanged)

> "Its not only going to be an AI and an AI training station with an AI
> able system but only a guide into the experiece, into the field, into
> the kernel, into the hardware, into the OS, into the modules, into
> the features, the services, the configurations, the personalisations,
> the customizations. ? AI and the tools but also download, fine-tune,
> parameters, build, run, use and train and adapt and use and eval and
> etc. Lets think of all the angles. Also selfdef modules, modules
> features and advanced features and profiles. Hotswap, CPU mode and
> option(s). GPU too, watts, RTX 3090 details and possibilities
> established and non-established, same for the RTX Pro 6000 and the
> CPU and AVX512. autohealth and doctor, notification and messaging.
> networks and in and out, the DNS, the Cloudflared ? the tailscale,
> Traefik, non docker vs docker install ? when possible ? container
> level vs system level. dashboard, installs, non-configured, modules
> or features and how configure them. The management of the softwares,
> the "raid"s, observations and operations and configurations. logs,
> log rotate, system usage, partitions and global and such. insights.
> Interoperability, MCP, tools, deps) Debian 13 Base, Sovereign OS and
> vision, why non-GUI by default. server, dashboard or API and modules
> and tools vision. Everything via dashboard/UInterface or terminal
> tools OR AI. Python, System and GPU and LLM and multiple level and
> REPL. Programming, Proto-Programing, Proto-Proto-Programming and
> CoT and custom CoT, integrated intelligence modules, features and
> options and etc. You do not need to wait for me to approve you PR,
> you can grow a PR for a long time and progress the work or if its
> in Sovereign OS you just write in main still. All the previous
> requirements still remains. Again we deliver the top plus ultra
> solutions for selfdef and sovereign OS. We do not minimize anything
> and we do proper research online and processing of what I say and
> what we find and what we think and we move toward my solution
> endlessly. DO not stop after opening or updating a PR. continue
> endlessly. Kernel optimisation, OS, Services, Modules, Tools,
> Dashboards, Configurations, Options. Network, App, & In between.
> Memory too I guess and bios settings directives and admonition of
> things that might also not be possible on some board, possibly
> detecting the ASUS ProArt X870E-CREATOR WIFI and its settings and
> potential optimisations and fixes. pci lane splits and whatever like
> virtualization or what we find relevant via search online and such.
> Adapting / Considering the given PSU (probably not detectable ?)
> wattage and rating ? (me: be Quiet! Dark Power Pro 13 1600W Power
> Supply | ATX 3.1 Compliant | 80 Plus Titanium), considering XMP
> profile and OC profile and room for each and estimated at 100% usage
> and then real time tracking and intelligence around it. (Possibly
> heat too I guess) My PSU even have an overclock mode which might be
> important. Then there is the PSU/APC integration with the power
> management and the scheduled shutdown when battery reach a certain
> point as one default profile. (schedule/planifest/graceful on all
> levels, orderly). a lot but I trust you to break down planify and
> continue with the SDD and TDD and a Senior Architect DevOps Software
> Engineer Fullstack Expert & Mindset. Always a strong workflow and
> non-blocking but always toward the goal(s). Apply what I said at
> scale and you have for a very long time of work. Take your time, do
> this right."

## 2. Standing rules (sacrosanct — applies to EVERY round)

- **Never minimize, reduce, conflate, or corrupt** the operator's
  words. Quote verbatim when citing.
- **Compound mindset.** Each named axis multiplies — sub-axes ×
  sub-features × sub-options. Plan for months, not days.
- **SDD + TDD + SFIF + SRP + OOP + Design Patterns + documentation.**
  Every round is a Senior Architect / DevOps / Fullstack engineer
  delivering "top plus ultra" — not a junior shipping the smallest
  thing.
- **Always non-blocking, always toward the goal.** Don't pause for
  PR merges, don't stop at milestones.
- **Direct push to `sovereign-os` `main`; never-ending PR on
  `selfdef` cycle-N branch.** All previous requirements still apply
  (operator keys never in-repo, `#![forbid(unsafe_code)]`, etc.).

## 3. Epic / Module / Task decomposition

This is the **structural** view of the mandate. Each Epic is months
of work; each Module is weeks; each Task is rounds. Future rounds
SHOULD cite the Epic + Module + Task IDs they advance.

When a round closes a Task, mark it ✓ here. When ALL Tasks of a
Module close, mark the Module ✓. When all Modules of an Epic close,
the Epic is closed — but the operator may add new Modules to it.

### Epic E1 — Hardware-stack visibility & control

> "Kernel optimisation, OS, ... Memory too I guess and bios settings
> directives ... pci lane splits and whatever like virtualization ...
> the given PSU ... XMP profile and OC profile ... Real time tracking
> and intelligence ... PSU/APC integration ... scheduled shutdown
> when battery reach a certain point ... graceful on all levels,
> orderly."

| ID | Module | Status | Rounds |
|----|--------|--------|--------|
| E1.M1 | Kernel tuning (sysctl + GRUB cmdline presets per workload) | ✓ shipped | R239 |
| E1.M2 | BIOS + baseboard + memory probe + board-specific advisories (incl. ASUS X870E-CREATOR WIFI) | ✓ shipped | R251, R260 |
| E1.M3 | Memory XMP/EXPO posture detection + AMD/Intel-aware hints | ✓ shipped | R257 |
| E1.M4 | Virtualization probe (CPU virt flags + KVM + IOMMU + PCIe + container runtimes) | ✓ shipped | R255 |
| E1.M5 | PSU + UPS + wattage budget + OC mode multiplier | ✓ shipped | R252, R259 |
| E1.M6 | Graceful UPS-battery shutdown guard (per-minute timer, triple-gate) | ✓ shipped | R253 |
| E1.M7 | Per-minute wattage time-series sampler (4 Layer B metrics) | ✓ shipped | R258 |
| E1.M8 | Graceful drain-then-poweroff manifest framework | ✓ shipped | R262 |
| E1.M9 | GPU power policy + watt deviance + remediation | ✓ shipped (prior) | R219, R249 |
| E1.M10 | CPU mode hotswap + auto recommender | ✓ shipped (prior) | R221, R230 |
| E1.M11 | Heat integration with budget + thermal-aware advisories | ✓ shipped | R265 |
| E1.M12 | PCIe lane allocation policy advisor (when both GPUs populated) | ✓ shipped | R270 |
| E1.M13 | RTX 3090 + RTX PRO 6000 dual-card-specific advisories | ✓ shipped | R271 |
| E1.M14 | AVX-512 utilization probe + workload-fit advisor | ✓ shipped | R272 |
| E1.M15 | Memory pressure / OOM watcher + Layer B metrics | ✓ shipped | R269 |
| E1.M16 | **256 GB DDR5 RAM-specific advisor** (operator-system: 256 GB total; ZFS ARC clamp = 128 GB per master spec § 19 + GGUF / model-context budget tracker) [from §1a + raw-dump §1.1, §3] | ✓ shipped | R279 |
| E1.M17 | **Wasm-to-AVX-512 AOT pipeline** (`wasmtime compile --target znver5` + `relaxed-simd=true` + `WASMTIME_COMPARE_OPTIONS` env enforcement; master spec § 20 "The Pulse Implementation") [from §1a + raw-dump § 20] | ✓ shipped | R281 |
| E1.M18 | **1-bit / ternary ZMM utilization probe** (live: are we ACTUALLY using VPDPBUSD with packed 2-bit weights via bitnet.cpp / T-MAC? OR fallback FP16 — measured by perf-stat retired-instruction counters) [from §1a + raw-dump § 17.1] | ✓ shipped | R280 |
| E1.M19 | **Hardware-exploit-to-the-max research loop** (continuously evolving SDD + TDD as new BitNet / DFlash / VPDPBUSD findings land; "research mode" verb that surfaces upstream changes from bitnet.cpp + transformers + vllm) | **TODO** | — |

### Epic E2 — Software-stack visibility & control

> "OS, Services, Modules, Tools ... Debian 13 Base, Sovereign OS ...
> non-GUI by default ... server, dashboard or API and modules and
> tools vision."

| ID | Module | Status | Rounds |
|----|--------|--------|--------|
| E2.M1 | Services inventory (live + shipped catalog + failures + timers) | ✓ shipped | R240 |
| E2.M2 | Selfdef modules diff / install-options / install-plan / config-scaffold / apply-plan | ✓ shipped (selfdef) | SD-R83 → SD-R93 |
| E2.M3 | Install paths matrix (container vs system, network-state-aware) | ✓ shipped | R237 |
| E2.M4 | Software RAID observation + operation + configuration | ✓ shipped (prior) | R223 |
| E2.M5 | Logs + log-rotate + filesystem usage + insights synthesizer | ✓ shipped | R222, R234 |
| E2.M6 | Module features sub-configuration (operator-pull TOML overrides per module) | ✓ shipped (selfdef) | SD-R99 |
| E2.M7 | Advanced module-features lifecycle (enable/disable individual features within a module) | ✓ shipped (selfdef) | SD-R100 |
| E2.M8 | systemd service hardening lint (R171 doctrine extension) | partial | R171 (extending) |
| E2.M9 | Service-dependency graph visualizer (operator's drain ordering) | ✓ shipped | R277 |

### Epic E3 — Network visibility & control

> "networks and in and out, the DNS, the Cloudflared ? the tailscale,
> Traefik, non docker vs docker install ? when possible ? container
> level vs system level."

| ID | Module | Status | Rounds |
|----|--------|--------|--------|
| E3.M1 | Network state probe (internet / DNS / cloudflared / tailscale / traefik / docker) | ✓ shipped (prior) | R220 |
| E3.M2 | Cloudflared / Tailscale / Traefik per-service posture advisor | ✓ shipped | R263 |
| E3.M3 | Container-vs-system install-path matrix with grey-out logic | ✓ shipped | R237 |
| E3.M4 | DNS provider posture (Cloudflare/Quad9/AdGuard advisories) | ✓ shipped | R268 |
| E3.M5 | Reverse-proxy config validator (Traefik / Caddy / nginx) | ✓ shipped | R275 |
| E3.M6 | Network performance baseline + drift detection | ✓ shipped | R276 |

### Epic E4 — Dashboard / Operator UX

> "dashboard ... Everything via dashboard/UInterface or terminal tools
> OR AI ... installs, non-configured, modules or features and how
> configure them."

| ID | Module | Status | Rounds |
|----|--------|--------|--------|
| E4.M1 | Dashboard HTTP SEED + cards aggregator (R225 contract) | ✓ shipped | R225 |
| E4.M2 | 18 cards spanning every shipped axis | ✓ shipped | R227-R261 |
| E4.M3 | Per-model detail sub-route (/api/models/<slug>) | ✓ shipped | R233 |
| E4.M4 | Grid view for terminal-friendly snapshot | ✓ shipped | R248 |
| E4.M5 | Dashboard auth + allowlist + ACL | ✓ shipped | R250 |
| E4.M6 | Network-state-reactive grey-out of install/options when prerequisite unreachable | ✓ shipped | R274 |
| E4.M7 | Dashboard event timeline (R246 → live tail) | ✓ shipped | R246 |
| E4.M8 | Mobile-friendly card layout (CSS only, no JS framework) | **TODO** | — |
| E4.M9 | Dashboard editable forms for module configuration | **TODO** | — |

### Epic E5 — AI / LLM / Training-station

> "AI and the tools but also download, fine-tune, parameters, build,
> run, use and train and adapt and use and eval and etc ... like LM
> Studio and LM Link maybe ? Unsloth ?"

| ID | Module | Status | Rounds |
|----|--------|--------|--------|
| E5.M1 | Model catalog R71 taxonomy + 17 entries × 12 classes | ✓ shipped (prior) | R212 |
| E5.M2 | Model browse + detail + eval + suggester | ✓ shipped (prior) | R213, R214, R231, R232 |
| E5.M3 | LoRA state file + atomic attach/detach/set-status | ✓ shipped (selfdef) | SD-R81, SD-R89 |
| E5.M4 | Toolchain catalog (llama.cpp / bitnet.cpp / vllm / ollama / lm-studio / lm-link / unsloth / transformers / trl / lm-eval / mteb / dflash) | ✓ shipped | R242 |
| E5.M5 | Fine-tune workflow skeleton (R244 surface; SD-R89 selfdef state) | ✓ shipped | R244 |
| E5.M6 | End-to-end fine-tune lifecycle (operator triggers training → eval → register) | **TODO** | — |
| E5.M7 | Model variants + quantizations + advanced features parametrization | partial | R231 detail surface (variants ✓; parametrization TODO) |
| E5.M8 | Speculative-decoding (DFlash) integration | ✓ shipped (prior) | R157 |
| E5.M9 | Operator-mutable flexible profile (download / fine-tune / parameters / build / run / use / train / adapt / eval workflow) | **TODO** | — |
| E5.M10 | **Operator "assistant feel" UX layer** — clear paths, options, modules-combo-features, super-features. Every dashboard card + CLI verb surfaces "next-best-step" hints; module combinations get curated names ("inference-burst pack", "headless-server pack") that flip multiple knobs at once. [from §1a] | ✓ shipped | R282 |
| E5.M11 | **Endless flexibility + fine-tuning + adapting** — operator-pull config layer that lets EVERY shipped script accept TOML overlays for thresholds, paths, knobs, advisory copy. [from §1a] | ✓ shipped | R283 (library + SDD-030 doctrine + L1 lint) |

### Epic E6 — Health / Doctor / Autonomy

> "autohealth and doctor, notification and messaging ... scans ...
> analysis and event."

| ID | Module | Status | Rounds |
|----|--------|--------|--------|
| E6.M1 | Composite health-scan over all Z-vectors | ✓ shipped (prior) | R226 |
| E6.M2 | Notification fan-out (file / webhook / ntfy) with dedup | ✓ shipped (prior) | R228 |
| E6.M3 | Autonomous timer-driven scan → notify loop | ✓ shipped (prior) | R229 |
| E6.M4 | Event aggregator + insights synthesizer | ✓ shipped (prior) | R234, R246 |
| E6.M5 | Doctor verb (analysis + recommendations across all axes) | ✓ shipped as `diagnose` | R266 |
| E6.M6 | Severity escalation policy (attention → critical after dwell-time) | ✓ shipped | R273 |

### Epic E7 — Interop / MCP / Tools / Deps

> "Interoperability, MCP, tools, deps ... interoperate with an MCP via
> tools calls and/or MCP. (e.g. I might install node, claude and
> whatever deps and use it on it.)"

| ID | Module | Status | Rounds |
|----|--------|--------|--------|
| E7.M1 | MCP tool manifest (read-only verbs) | ✓ shipped (selfdef) | SD-R84 |
| E7.M2 | MCP stdio JSON-RPC server | ✓ shipped (selfdef) | SD-R91, SD-R92 |
| E7.M3 | MCP TCP transport | ✓ shipped (selfdef) | SD-R94 |
| E7.M4 | MCP write-tool authorization gate (SELFDEF_MCP_ALLOW_WRITES=YES) | ✓ shipped | SD-R96 |
| E7.M5 | Cross-repo MCP-tool aggregator (sovereign-os surfaces selfdef tools too) | **TODO** | — |
| E7.M6 | Operator-supplied dep install hooks (node + claude + arbitrary apt/pip + curl-shell) | ✓ shipped | R284 |

### Epic E8 — Python REPL / Programming tiers / Integrated intelligence

> "Python, System and GPU and LLM and multiple level and REPL.
> Programming, Proto-Programing, Proto-Proto-Programming and CoT and
> custom CoT, integrated intelligence modules, features and options
> and etc."

| ID | Module | Status | Rounds |
|----|--------|--------|--------|
| E8.M1 | Tier 1 Proto-Programming bootstrap (Python REPL with subprocess wrappers) | ✓ shipped (selfdef) | SD-R85 |
| E8.M2 | Tier 2 Proto-Proto-Programming examples (operator-pull macros) | ✓ shipped (selfdef) | SD-R90 |
| E8.M3 | REPL invocation audit trail (SELFDEF_REPL_HISTORY JSONL) | ✓ shipped (selfdef) | SD-R95 |
| E8.M4 | Integrated-intelligence modules — operator-pull CoT routines registered with @selfdef_macro | ✓ shipped (selfdef) | SD-R98 |
| E8.M5 | Tier 3 native pyo3 bindings (zero-subprocess Tier 1) | **TODO** | — |
| E8.M6 | Token-saving aliases + wasted-path tracker | ✓ shipped (selfdef) | SD-R97 |

### Epic E9 — Operator-mandate process discipline

> "register what I said so that you can break it down and have
> identifiable and workable pieces ... do not minimize anything nor
> the situation."

| ID | Module | Status | Rounds |
|----|--------|--------|--------|
| E9.M1 | Standing-directive durable record (THIS FILE) | ✓ shipped | R264 |
| E9.M2 | Per-round Epic/Module citation in commit messages | ✓ in-practice from R265 | R265+ |
| E9.M3 | Quarterly mandate review + new-axis intake process | **TODO** | — |
| E9.M4 | Cross-link Epic/Module IDs into SDD-029 + future SDDs | partial | R264 (SDD-029) |
| E9.M5 | `/goal` autopilot re-arming — root cause + compact-pointer script + L1 lint guard | ✓ shipped | R267 |
| E9.M6 | **Multi-`/goal`-paste compounding doctrine** — every `/goal` text adds to the mandate; never replaces. §1.0 anchors the rule. [from §1.0 + this turn] | ✓ shipped | R278 (this round) |
| E9.M7 | **PR not-draft-by-default** — selfdef cycle-N PRs lifted from draft immediately so reviewers see active work; CI gates remain authoritative. [from §1a + this turn] | ✓ shipped | R278 (PR #198 lifted) |
| E9.M8 | **Raw-dump re-read protocol** — when operator says "RETURN REREAD ALL THE RAW DUMP", agent reads `devops-solutions-information-hub/raw/` before asking; only ask when ambiguity remains. [from §1.0] | ✓ in-practice | R278 onward |

## 4. How future rounds use this file

1. **Pick the next TODO Module** from any Epic above. Prefer Modules
   whose Epic has the most TODO siblings (broaden coverage) or the
   Module that unblocks downstream work.
2. **Decompose into rounds.** A Module may need 1-10 rounds. Each
   round = one round-ID (R<N> or SD-R<N>) + commit + push.
3. **Cite Epic / Module ID in commit message** (e.g. "Round 265 —
   heat-budget integration (E1.M11)"). This is the structural trace
   that addresses the operator's "make sure we record this and make
   sure we do some things about it" mandate.
4. **Update THIS FILE** when a Module flips to ✓. New TODO Modules
   added under existing Epics MUST quote the operator's verbatim
   text they derive from.

## 5. What this file does NOT do

This file is the **decomposition** of the mandate, not the
**implementation status**. SDD-029 + each round's L3 test are the
implementation truth. INDEX.md remains the chronological SDD ledger.
Handoff docs remain the trajectory tracker.

## 6. Anti-corruption invariants

- Do **NOT** rewrite the operator's verbatim text. Edits to Section 1
  require a new file with a new date and operator confirmation.
- Do **NOT** delete TODO Modules without operator confirmation.
- New Modules added during work go under an Epic with a one-line
  source-quote citation.
