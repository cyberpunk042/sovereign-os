# M060 — Cockpit + 20+ dashboards + UX surface

**Parent**: sovereign-os runtime — AI workstation user-facing layer
**Source**: `~/infohub/raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md`
- line 581 (three hats: senior systems architect / performance engineer / infra-devops engineer; "Fullstack matters only at the edges: dashboards, APIs, orchestration UI")
- lines 3290-3325 (Dashboard Philosophy: "A dashboard should not show vanity graphs" + 9 operational questions)
- lines 6789 ("That is UX for intelligence")
- lines 9979-10000 (Anthropic-first primary surface + OpenAI-compatible secondary surface)
- lines 14760-14780 (Configuration Surfaces — three levels: User / Power user / System)
- lines 15315-15345 (Fullstack Surface: local web dashboard / CLI / API / MCP-tools / Project integration)
- lines 15625-15665 (User-facing layer: local dashboard + CLI + API + IDE clients) + lines 15645-15660 (Cockpit must show: 7 items)
- lines 16440-16466 (Phase 10 Full Cockpit + UI surfaces: 11 items)
- lines 17563 (local dashboard recurrence) + lines 10923, 11639, 15330, 15629 (local dashboard recurrences)
**Operator standing direction** (verbatim, 2026-05-19): *"obviously i expect dashboards and a good UX... there is over 20 dashboards and a main one and everything can be turned on and off and there are also a tons of modes and profiles"* / *"you cannot re-invent what UX mean"*
**Project boundary**: this milestone scopes ONLY sovereign-os runtime user-facing dashboards; selfdef IPS-side operator dashboards (rules / grants / quarantine / trust scores) are catalogued in selfdef MS043 with strict project-boundary separation.

## Doctrinal anchors

> "A dashboard should not show vanity graphs." (dump 3299)
> "Fullstack matters only at the edges: dashboards, APIs, orchestration UI." (dump 581)
> "Fullstack here is not marketing UI. It is cockpit design." (dump 15643)
> "This is fullstack, but serious fullstack: the cockpit of an intelligence machine." (dump 16466)
> "That is UX for intelligence." (dump 6789)

## Epics (E0578-E0587)

| epic | name | source |
|---|---|---|
| E0578 | Dashboard philosophy — operational questions, not vanity graphs (9 operational questions enumerated) | dump 3299-3325 |
| E0579 | Main dashboard (D-00) — index of all 20+ sub-dashboards + global health + active session summary | dump 15625-15665 + dump 16450 |
| E0580 | Phase 10 cockpit must-show — 7 operator-essential views (running / cost / can-touch / changed / approval-waiting / resumable / rollback-points) | dump 15645-15660 |
| E0581 | Phase 10 UI surfaces — 11 cockpit surfaces (active sessions / profile choices / model health / costs / traces / pending approvals / memory changes / rollback points / hardware pressure / eval history / adapter status) | dump 16450-16466 |
| E0582 | Local dashboard secondary panels — profiles / costs / traces / model health / memory / approvals (the 6-item local-dashboard catalog) | dump 15625-15630, 15330-15333 |
| E0583 | CLI surface — run / resume / inspect / rollback / switch-profile | dump 15634-15640, 15336-15340 |
| E0584 | API surface — Anthropic-first primary (5 endpoints) + OpenAI-compatible secondary (4 endpoints) | dump 9979-10000 |
| E0585 | IDE/agent client surface — Claude Code / Cline / OpenCode / local tools point at local gateway | dump 15648-15665, 15343-15345 |
| E0586 | Configuration surfaces — three operator levels (User / Power user / System) | dump 14760-14780 |
| E0587 | UX coherence — keyboard shortcuts / dark mode / accessibility / responsive layout / personalization (operator-facing UX standards) | operator standing direction 2026-05-19 + dump 6789 |

## Modules (M01003-M01019)

| module | name | source |
|---|---|---|
| M01003 | sovereign-dashboard-D00-main-index | dump 15625-15665 + dump 16450 |
| M01004 | sovereign-dashboard-D01-active-sessions | dump 16452 |
| M01005 | sovereign-dashboard-D02-profile-choices | dump 16453 |
| M01006 | sovereign-dashboard-D03-model-health | dump 16454 |
| M01007 | sovereign-dashboard-D04-costs | dump 16455 |
| M01008 | sovereign-dashboard-D05-traces | dump 16456 |
| M01009 | sovereign-dashboard-D06-pending-approvals | dump 16457 |
| M01010 | sovereign-dashboard-D07-memory-changes | dump 16458 |
| M01011 | sovereign-dashboard-D08-rollback-points | dump 16459 |
| M01012 | sovereign-dashboard-D09-hardware-pressure | dump 16460 |
| M01013 | sovereign-dashboard-D10-eval-history | dump 16461 |
| M01014 | sovereign-dashboard-D11-adapter-status | dump 16462 |
| M01015 | sovereign-cli-surface | dump 15634-15640 |
| M01016 | sovereign-api-surface-anthropic-first | dump 9979-9995 |
| M01017 | sovereign-api-surface-openai-compatible | dump 9990-10000 |
| M01018 | sovereign-ide-client-surface | dump 15648-15665 |
| M01019 | sovereign-ux-coherence-engine | operator standing direction + dump 6789 |

## Features (F05016-F05100)

| feature | name | source |
|---|---|---|
| F05016 | Dashboard rule — never show vanity graphs | dump 3299 |
| F05017 | Dashboard question 1 — Is the Blackwell idle? | dump 3304 |
| F05018 | Dashboard question 2 — Is the 3090 helping? | dump 3305 |
| F05019 | Dashboard question 3 — Is speculation worth it? | dump 3306 |
| F05020 | Dashboard question 4 — Are token masks expensive? | dump 3307 |
| F05021 | Dashboard question 5 — Is KV reuse saving prefill? | dump 3308 |
| F05022 | Dashboard question 6 — Are tools being rejected too often? | dump 3309 |
| F05023 | Dashboard question 7 — Are branches dying for useful reasons? | dump 3310 |
| F05024 | Dashboard question 8 — Is storage latency hurting context? | dump 3311 |
| F05025 | Dashboard question 9 — Is the system becoming more efficient over time? | dump 3312-3314 |
| F05026 | D-00 main dashboard — index card per sub-dashboard (D-01..D-11+) with status indicator | architecture + dump 15625-15665 |
| F05027 | D-00 main dashboard — global health badge (green/amber/red) | architecture + dump 16450 |
| F05028 | D-00 main dashboard — active-session count + current profile name | dump 15625-15665 + cross-ref MS040 |
| F05029 | D-00 main dashboard — quick-action bar (resume / inspect / rollback / switch profile) | dump 15634-15640 |
| F05030 | D-00 main dashboard — keyboard shortcut palette (operator UX) | operator standing direction 2026-05-19 |
| F05031 | D-01 active sessions — list of running tasks with M057 12-step lifecycle step | dump 16452 + cross-ref M057 |
| F05032 | D-01 active sessions — per-task profile + branch count + ETA | dump 16452 + cross-ref MS040 |
| F05033 | D-01 active sessions — per-task hibernate / resume / kill controls | cross-ref M047 + dump 16452 |
| F05034 | D-02 profile choices — six-profile selector (private/fast/careful/autonomous/experimental/production) | dump 16453 + cross-ref MS040 |
| F05035 | D-02 profile choices — current-profile envelope visualization (L0..L6 ladder + ring 0..4 highlights) | dump 16453 + cross-ref MS039 + MS040 |
| F05036 | D-02 profile choices — profile-change history with timestamps + actor | dump 16453 + cross-ref MS040 |
| F05037 | D-02 profile choices — predeclared-gate editor (autonomous profile only) | cross-ref MS040 + dump 16453 |
| F05038 | D-03 model health — Blackwell/3090/CPU status indicators | dump 16454 + cross-ref M058 |
| F05039 | D-03 model health — VRAM occupancy + KV cache utilization charts | dump 16454 + cross-ref M058 |
| F05040 | D-03 model health — per-model latency p50/p95/p99 | dump 16454 |
| F05041 | D-03 model health — model availability heatmap | dump 16454 |
| F05042 | D-04 costs — daily budget + per-request actual cost | dump 16455 + dump 9890 |
| F05043 | D-04 costs — cost-by-project / cost-by-profile / cost-by-model breakdowns | dump 16455 + dump 9920 |
| F05044 | D-04 costs — cost forecast + budget exhaustion ETA | dump 16455 |
| F05045 | D-04 costs — operator alert thresholds (cost halts task) | dump 16455 + dump 9890 |
| F05046 | D-05 traces — M049 13-field span search/filter | dump 16456 + cross-ref M049 |
| F05047 | D-05 traces — trace timeline visualization (span tree) | dump 16456 + cross-ref M049 |
| F05048 | D-05 traces — trace replay (read-only) integration with MS009 | dump 16456 + cross-ref MS009 |
| F05049 | D-05 traces — OCSF event detail panel (16-event taxonomy) | dump 16456 + cross-ref MS026 + M049 |
| F05050 | D-06 pending approvals — operator-facing approval queue | dump 16457 + cross-ref MS039 + MS040 |
| F05051 | D-06 pending approvals — per-approval context (declaration + observed + diff) | dump 16457 + cross-ref MS042 |
| F05052 | D-06 pending approvals — approve / deny / defer actions | dump 16457 + cross-ref MS003 |
| F05053 | D-06 pending approvals — batch-approve action for autonomous-profile gates | cross-ref MS040 + dump 16457 |
| F05054 | D-07 memory changes — memory graph diff visualization | dump 16458 + cross-ref M048 |
| F05055 | D-07 memory changes — promote / forget / pin controls | dump 16458 + cross-ref M048 |
| F05056 | D-07 memory changes — memory trust dimension filters (7 dimensions) | dump 16458 + cross-ref MS039 |
| F05057 | D-08 rollback points — ZFS snapshot list + commit history | dump 16459 + cross-ref MS037 + MS041 |
| F05058 | D-08 rollback points — rollback-preview action (dry-run) | dump 16459 + cross-ref MS041 |
| F05059 | D-08 rollback points — rollback-apply action (gated by operator confirmation) | dump 16459 + cross-ref MS041 + MS003 |
| F05060 | D-09 hardware pressure — Linux PSI gauges (CPU / IO / memory) | dump 16460 + cross-ref M045 + M058 |
| F05061 | D-09 hardware pressure — DCGM GPU pressure gauges (Blackwell + 3090) | dump 16460 + cross-ref M058 |
| F05062 | D-09 hardware pressure — backpressure-rule live indicators | dump 16460 + cross-ref M058 |
| F05063 | D-10 eval history — per-task eval pass/fail trend | dump 16461 + cross-ref M049 |
| F05064 | D-10 eval history — per-model eval-score over time | dump 16461 + cross-ref M046 |
| F05065 | D-10 eval history — eval-driven adapter-promotion candidates list | dump 16461 + cross-ref M046 |
| F05066 | D-11 adapter status — LoRA Foundry adapter inventory | dump 16462 + cross-ref M046 |
| F05067 | D-11 adapter status — adapter promotion gates + audit trail | dump 16462 + cross-ref MS041 + M046 |
| F05068 | D-11 adapter status — adapter rollback action | dump 16462 + cross-ref MS041 + M046 |
| F05069 | D-12 networking — selfdef Ring 0-4 traffic visualization (cross-repo via MS007 selfdef-network-mirror) | cross-ref selfdef MS038 + MS039 + MS007 |
| F05070 | D-13 filesystem grants — selfdef filesystem-grant state (read-only mirror via MS007) | cross-ref selfdef MS037 + MS007 |
| F05071 | D-14 capability tokens — active capability_word grants (read-only mirror via MS007 selfdef-capability-mirror) | cross-ref selfdef MS035 + MS007 |
| F05072 | D-15 sandboxes — MS036 tier A/B/C/D allocation visualization | cross-ref selfdef MS036 + MS007 |
| F05073 | D-16 audit cycles — MS009 audit cycle results + replay validator status | cross-ref selfdef MS009 + MS007 |
| F05074 | D-17 quarantine — MS042 tool-quarantine archive viewer (read-only mirror via MS007) | cross-ref selfdef MS042 + MS007 |
| F05075 | D-18 trust scores — per-tool trust score history (read-only mirror via MS007) | cross-ref selfdef MS042 + MS007 |
| F05076 | D-19 super-model manifest — current super-model version + module-version table | cross-ref M059 |
| F05077 | D-20 peace machine health — 5 peace-machine properties live status | cross-ref M059 |
| F05078 | CLI — `sovereign run <task>` invokes a task | dump 15634-15636 |
| F05079 | CLI — `sovereign resume <session-id>` resumes a hibernated session | dump 15634-15636 + cross-ref M047 |
| F05080 | CLI — `sovereign inspect <trace-id>` opens trace detail | dump 15634-15636 + cross-ref M049 |
| F05081 | CLI — `sovereign rollback <commit-id>` rolls back a commit | dump 15634-15636 + cross-ref MS041 |
| F05082 | CLI — `sovereign profile <name>` switches active profile | dump 15634-15636 + cross-ref MS040 |
| F05083 | API — Anthropic primary: POST /v1/messages | dump 9981 |
| F05084 | API — Anthropic primary: GET /v1/models | dump 9981 |
| F05085 | API — Anthropic primary: POST /v1/messages/count_tokens | dump 9981 |
| F05086 | API — Anthropic primary: SSE streaming events | dump 9982 |
| F05087 | API — Anthropic primary: tool_use / tool_result blocks | dump 9982 |
| F05088 | API — OpenAI-compatible secondary: POST /v1/chat/completions | dump 9991 |
| F05089 | API — OpenAI-compatible secondary: POST /v1/responses | dump 9992 |
| F05090 | API — OpenAI-compatible secondary: POST /v1/embeddings | dump 9993 |
| F05091 | API — OpenAI-compatible secondary: GET /v1/models | dump 9994 |
| F05092 | IDE — Claude Code points at local gateway via base_url override | dump 9732-9740 |
| F05093 | IDE — Cline points at local gateway via base_url override | dump 9732-9740 + dump 15660 |
| F05094 | IDE — OpenCode points at local gateway via base_url override | dump 9732-9740 + dump 15660 |
| F05095 | Configuration — User level (simple profiles + prompts) | dump 14763-14765 |
| F05096 | Configuration — Power-user level (toggles + budgets + allowed providers + sandbox levels) | dump 14767-14769 |
| F05097 | Configuration — System level (policy + hardware profile + routing weights + eval thresholds) | dump 14771-14773 |
| F05098 | UX coherence — keyboard shortcuts (one-key navigation between dashboards) | operator standing direction 2026-05-19 |
| F05099 | UX coherence — dark mode + light mode + auto-from-system | operator standing direction 2026-05-19 |
| F05100 | UX coherence — accessibility (WCAG 2.1 AA minimum: contrast / keyboard / screen-reader / focus visible) | operator standing direction 2026-05-19 |

## Requirements (R10031-R10200)

| req | description | source | feature | priority | exception | sub-reqs |
|---|---|---|---|---|---|---|
| R10031 | Doctrinal — "A dashboard should not show vanity graphs" | dump 3299 | F05016 | non-negotiable | false | 10 |
| R10032 | Doctrinal — dashboard answers operational questions | dump 3301-3314 | F05016 | non-negotiable | false | 10 |
| R10033 | Doctrinal — "Fullstack matters only at the edges: dashboards, APIs, orchestration UI" | dump 581 | F05026 | non-negotiable | false | 10 |
| R10034 | Doctrinal — "Fullstack here is not marketing UI. It is cockpit design." | dump 15643 | F05026 | non-negotiable | false | 10 |
| R10035 | Doctrinal — "This is fullstack, but serious fullstack: the cockpit of an intelligence machine." | dump 16466 | F05026 | non-negotiable | false | 10 |
| R10036 | Doctrinal — "That is UX for intelligence" | dump 6789 | F05016 | non-negotiable | false | 10 |
| R10037 | Operator direction — 20+ dashboards + 1 main dashboard | operator standing direction 2026-05-19 | F05026 | non-negotiable | false | 10 |
| R10038 | Operator direction — everything can be turned on and off | operator standing direction 2026-05-19 | F05096 | non-negotiable | false | 10 |
| R10039 | Operator direction — many modes and profiles | operator standing direction 2026-05-19 + cross-ref MS040 | F05034 | non-negotiable | false | 10 |
| R10040 | Operator direction — "you cannot re-invent what UX mean" (use industry-standard UX patterns) | operator standing direction 2026-05-19 | F05098 | non-negotiable | false | 10 |
| R10041 | Question 1 — Is the Blackwell idle? answered in D-09 | dump 3304 + cross-ref D09 | F05017 | non-negotiable | false | 10 |
| R10042 | Question 2 — Is the 3090 helping? answered in D-03 + D-09 | dump 3305 | F05018 | non-negotiable | false | 10 |
| R10043 | Question 3 — Is speculation worth it? answered in D-10 eval history | dump 3306 | F05019 | non-negotiable | false | 10 |
| R10044 | Question 4 — Are token masks expensive? answered in D-03 + D-09 | dump 3307 | F05020 | non-negotiable | false | 10 |
| R10045 | Question 5 — Is KV reuse saving prefill? answered in D-03 KV cache utilization | dump 3308 | F05021 | non-negotiable | false | 10 |
| R10046 | Question 6 — Are tools being rejected too often? answered in D-17 quarantine + D-18 trust scores | dump 3309 | F05022 | non-negotiable | false | 10 |
| R10047 | Question 7 — Are branches dying for useful reasons? answered in D-05 traces + D-10 eval | dump 3310 | F05023 | non-negotiable | false | 10 |
| R10048 | Question 8 — Is storage latency hurting context? answered in D-09 hardware pressure | dump 3311 | F05024 | non-negotiable | false | 10 |
| R10049 | Question 9 — Is the system becoming more efficient over time? answered in D-10 eval history | dump 3312-3314 | F05025 | non-negotiable | false | 10 |
| R10050 | D-00 main — index card per sub-dashboard with live status indicator | architecture | F05026 | non-negotiable | false | 10 |
| R10051 | D-00 main — global health badge (green/amber/red) | architecture | F05027 | non-negotiable | false | 10 |
| R10052 | D-00 main — active-session count surfaced | dump 15625-15665 | F05028 | non-negotiable | false | 10 |
| R10053 | D-00 main — current profile name surfaced | cross-ref MS040 | F05028 | non-negotiable | false | 10 |
| R10054 | D-00 main — quick-action bar (resume / inspect / rollback / switch profile) | dump 15634-15640 | F05029 | non-negotiable | false | 10 |
| R10055 | D-00 main — keyboard shortcut palette (Cmd-K / Ctrl-K opens) | operator standing direction 2026-05-19 | F05030 | non-negotiable | false | 10 |
| R10056 | D-00 main — every link to sub-dashboard one-click navigation | architecture | F05026 | non-negotiable | false | 10 |
| R10057 | D-00 main — index updates live (no manual refresh) | architecture | F05027 | non-negotiable | false | 10 |
| R10058 | D-00 main — accessible via Cmd-1 / Ctrl-1 shortcut | operator standing direction 2026-05-19 | F05030 | non-negotiable | false | 10 |
| R10059 | D-01 active sessions — list running tasks with M057 12-step lifecycle step | cross-ref M057 | F05031 | non-negotiable | false | 10 |
| R10060 | D-01 active sessions — per-task profile + branch count + ETA | cross-ref MS040 + cross-ref M057 | F05032 | non-negotiable | false | 10 |
| R10061 | D-01 active sessions — per-task hibernate / resume / kill controls | cross-ref M047 + cross-ref M057 | F05033 | non-negotiable | false | 10 |
| R10062 | D-01 active sessions — accessible via Cmd-2 / Ctrl-2 shortcut | operator standing direction 2026-05-19 | F05030 | non-negotiable | false | 10 |
| R10063 | D-02 profile choices — six-profile selector | cross-ref MS040 | F05034 | non-negotiable | false | 10 |
| R10064 | D-02 profile choices — current-profile L0..L6 envelope visualization | cross-ref MS039 + MS040 | F05035 | non-negotiable | false | 10 |
| R10065 | D-02 profile choices — current-profile ring 0..4 highlights | cross-ref MS039 + MS040 | F05035 | non-negotiable | false | 10 |
| R10066 | D-02 profile choices — profile-change history (timestamps + actor) | cross-ref MS040 | F05036 | non-negotiable | false | 10 |
| R10067 | D-02 profile choices — predeclared-gate editor (autonomous only) | cross-ref MS040 | F05037 | non-negotiable | false | 10 |
| R10068 | D-02 profile choices — accessible via Cmd-3 / Ctrl-3 shortcut | operator standing direction 2026-05-19 | F05030 | non-negotiable | false | 10 |
| R10069 | D-03 model health — Blackwell/3090/CPU status indicators | cross-ref M058 | F05038 | non-negotiable | false | 10 |
| R10070 | D-03 model health — VRAM occupancy charts | cross-ref M058 | F05039 | non-negotiable | false | 10 |
| R10071 | D-03 model health — KV cache utilization charts | cross-ref M058 | F05039 | non-negotiable | false | 10 |
| R10072 | D-03 model health — per-model latency p50/p95/p99 | cross-ref M049 | F05040 | non-negotiable | false | 10 |
| R10073 | D-03 model health — model availability heatmap | cross-ref M049 | F05041 | non-negotiable | false | 10 |
| R10074 | D-03 model health — accessible via Cmd-4 / Ctrl-4 shortcut | operator standing direction 2026-05-19 | F05030 | non-negotiable | false | 10 |
| R10075 | D-04 costs — daily budget surfaced | dump 9890 | F05042 | non-negotiable | false | 10 |
| R10076 | D-04 costs — per-request actual cost surfaced | dump 16455 | F05042 | non-negotiable | false | 10 |
| R10077 | D-04 costs — cost-by-project breakdown | dump 9920 | F05043 | non-negotiable | false | 10 |
| R10078 | D-04 costs — cost-by-profile breakdown | cross-ref MS040 | F05043 | non-negotiable | false | 10 |
| R10079 | D-04 costs — cost-by-model breakdown | dump 9920 | F05043 | non-negotiable | false | 10 |
| R10080 | D-04 costs — cost forecast + budget exhaustion ETA | architecture | F05044 | non-negotiable | false | 10 |
| R10081 | D-04 costs — operator alert thresholds halt task on exhaustion | dump 9890 + dump 16455 | F05045 | non-negotiable | false | 10 |
| R10082 | D-04 costs — accessible via Cmd-5 / Ctrl-5 shortcut | operator standing direction 2026-05-19 | F05030 | non-negotiable | false | 10 |
| R10083 | D-05 traces — M049 13-field span search/filter | cross-ref M049 | F05046 | non-negotiable | false | 10 |
| R10084 | D-05 traces — trace timeline (span tree) visualization | cross-ref M049 | F05047 | non-negotiable | false | 10 |
| R10085 | D-05 traces — trace replay integration with MS009 | cross-ref MS009 | F05048 | non-negotiable | false | 10 |
| R10086 | D-05 traces — OCSF 16-event taxonomy detail panel | cross-ref MS026 + M049 | F05049 | non-negotiable | false | 10 |
| R10087 | D-05 traces — accessible via Cmd-6 / Ctrl-6 shortcut | operator standing direction 2026-05-19 | F05030 | non-negotiable | false | 10 |
| R10088 | D-06 pending approvals — operator-facing approval queue | cross-ref MS039 + MS040 | F05050 | non-negotiable | false | 10 |
| R10089 | D-06 pending approvals — per-approval context shown (declaration + observed + diff) | cross-ref MS042 | F05051 | non-negotiable | false | 10 |
| R10090 | D-06 pending approvals — approve / deny / defer actions | cross-ref MS003 | F05052 | non-negotiable | false | 10 |
| R10091 | D-06 pending approvals — batch-approve for autonomous-profile gates | cross-ref MS040 | F05053 | non-negotiable | false | 10 |
| R10092 | D-06 pending approvals — accessible via Cmd-7 / Ctrl-7 shortcut | operator standing direction 2026-05-19 | F05030 | non-negotiable | false | 10 |
| R10093 | D-07 memory changes — memory graph diff visualization | cross-ref M048 | F05054 | non-negotiable | false | 10 |
| R10094 | D-07 memory changes — promote / forget / pin controls | cross-ref M048 | F05055 | non-negotiable | false | 10 |
| R10095 | D-07 memory changes — 7 memory trust dimension filters | cross-ref MS039 | F05056 | non-negotiable | false | 10 |
| R10096 | D-07 memory changes — accessible via Cmd-8 / Ctrl-8 shortcut | operator standing direction 2026-05-19 | F05030 | non-negotiable | false | 10 |
| R10097 | D-08 rollback points — ZFS snapshot list | cross-ref MS037 | F05057 | non-negotiable | false | 10 |
| R10098 | D-08 rollback points — commit history (MS041 commit receipts) | cross-ref MS041 | F05057 | non-negotiable | false | 10 |
| R10099 | D-08 rollback points — rollback-preview action (dry-run) | cross-ref MS041 | F05058 | non-negotiable | false | 10 |
| R10100 | D-08 rollback points — rollback-apply action (operator confirmation gated) | cross-ref MS041 + MS003 | F05059 | non-negotiable | false | 10 |
| R10101 | D-08 rollback points — accessible via Cmd-9 / Ctrl-9 shortcut | operator standing direction 2026-05-19 | F05030 | non-negotiable | false | 10 |
| R10102 | D-09 hardware pressure — Linux PSI gauges (CPU/IO/memory) | cross-ref M045 + M058 | F05060 | non-negotiable | false | 10 |
| R10103 | D-09 hardware pressure — DCGM GPU pressure gauges | cross-ref M058 | F05061 | non-negotiable | false | 10 |
| R10104 | D-09 hardware pressure — backpressure-rule live indicators | cross-ref M058 | F05062 | non-negotiable | false | 10 |
| R10105 | D-09 hardware pressure — accessible via Cmd-0 / Ctrl-0 shortcut | operator standing direction 2026-05-19 | F05030 | non-negotiable | false | 10 |
| R10106 | D-10 eval history — per-task eval pass/fail trend | cross-ref M049 | F05063 | non-negotiable | false | 10 |
| R10107 | D-10 eval history — per-model eval-score over time | cross-ref M046 | F05064 | non-negotiable | false | 10 |
| R10108 | D-10 eval history — adapter-promotion candidates list | cross-ref M046 | F05065 | non-negotiable | false | 10 |
| R10109 | D-11 adapter status — LoRA Foundry adapter inventory | cross-ref M046 | F05066 | non-negotiable | false | 10 |
| R10110 | D-11 adapter status — promotion gates + audit trail | cross-ref MS041 + M046 | F05067 | non-negotiable | false | 10 |
| R10111 | D-11 adapter status — adapter rollback action | cross-ref MS041 + M046 | F05068 | non-negotiable | false | 10 |
| R10112 | D-12 networking — Ring 0-4 traffic visualization via MS007 mirror | cross-ref selfdef MS038 + MS039 + MS007 | F05069 | non-negotiable | false | 10 |
| R10113 | D-12 networking — never mutates IPS state (read-only mirror) | cross-ref MS007 + operator standing direction | F05069 | non-negotiable | false | 10 |
| R10114 | D-13 filesystem grants — selfdef state via MS007 mirror | cross-ref selfdef MS037 + MS007 | F05070 | non-negotiable | false | 10 |
| R10115 | D-13 filesystem grants — never mutates IPS state (read-only mirror) | cross-ref MS007 | F05070 | non-negotiable | false | 10 |
| R10116 | D-14 capability tokens — active capability_word grants via MS007 mirror | cross-ref selfdef MS035 + MS007 | F05071 | non-negotiable | false | 10 |
| R10117 | D-14 capability tokens — never mutates IPS state (read-only mirror) | cross-ref MS007 | F05071 | non-negotiable | false | 10 |
| R10118 | D-15 sandboxes — MS036 tier A/B/C/D allocation visualization | cross-ref selfdef MS036 + MS007 | F05072 | non-negotiable | false | 10 |
| R10119 | D-15 sandboxes — never mutates IPS state (read-only mirror) | cross-ref MS007 | F05072 | non-negotiable | false | 10 |
| R10120 | D-16 audit cycles — MS009 results + replay validator status via MS007 mirror | cross-ref selfdef MS009 + MS007 | F05073 | non-negotiable | false | 10 |
| R10121 | D-17 quarantine — MS042 tool-quarantine archive viewer via MS007 mirror | cross-ref selfdef MS042 + MS007 | F05074 | non-negotiable | false | 10 |
| R10122 | D-17 quarantine — operator restore action proxies to selfdef via MS003-signed request | cross-ref MS042 + MS003 | F05074 | non-negotiable | false | 10 |
| R10123 | D-18 trust scores — per-tool trust score history via MS007 mirror | cross-ref selfdef MS042 + MS007 | F05075 | non-negotiable | false | 10 |
| R10124 | D-19 super-model manifest — current super-model version | cross-ref M059 | F05076 | non-negotiable | false | 10 |
| R10125 | D-19 super-model manifest — module-version table (M001..M060) | cross-ref M059 | F05076 | non-negotiable | false | 10 |
| R10126 | D-20 peace machine health — 5 properties live status | cross-ref M059 | F05077 | non-negotiable | false | 10 |
| R10127 | D-20 peace machine health — peace-machine validator integration | cross-ref M059 | F05077 | non-negotiable | false | 10 |
| R10128 | Total dashboards — 21 dashboards (D-00..D-20) satisfy operator "20+ dashboards and a main one" | operator standing direction 2026-05-19 | F05026 | non-negotiable | false | 10 |
| R10129 | Dashboard toggle — every dashboard can be turned on/off | operator standing direction 2026-05-19 | F05096 | non-negotiable | false | 10 |
| R10130 | Dashboard toggle — toggle state persisted under /etc/sovereign-os/dashboards.toml | architecture + operator standing direction | F05096 | non-negotiable | false | 10 |
| R10131 | Dashboard toggle — toggle state signed via selfdef MS003 | cross-ref selfdef MS003 | F05096 | non-negotiable | false | 10 |
| R10132 | Dashboard toggle — toggle changes emit M049 trace + OCSF Configuration Change class 5001 | cross-ref M049 + cross-ref MS026 | F05096 | non-negotiable | false | 10 |
| R10133 | Dashboard re-export — every dashboard view emits M049 trace span on render | cross-ref M049 | F05026 | non-negotiable | false | 10 |
| R10134 | Dashboard performance — first paint `<` 200ms p95 | architecture | F05026 | non-negotiable | false | 10 |
| R10135 | Dashboard performance — incremental update `<` 50ms p95 | architecture | F05057 | non-negotiable | false | 10 |
| R10136 | Dashboard performance — no blocking server-side render for `>` 16ms frame budget | architecture | F05026 | non-negotiable | false | 10 |
| R10137 | Dashboard styling — dark mode + light mode + auto-from-system | operator standing direction 2026-05-19 | F05099 | non-negotiable | false | 10 |
| R10138 | Dashboard styling — WCAG 2.1 AA minimum (contrast / keyboard / screen-reader / focus visible) | operator standing direction 2026-05-19 | F05100 | non-negotiable | false | 10 |
| R10139 | Dashboard styling — responsive layout (desktop / tablet / phone) | operator standing direction 2026-05-19 | F05098 | non-negotiable | false | 10 |
| R10140 | Dashboard styling — operator-configurable accent color (personalization) | operator standing direction 2026-05-19 | F05098 | non-negotiable | false | 10 |
| R10141 | Dashboard styling — operator-configurable typography scale | operator standing direction 2026-05-19 | F05098 | non-negotiable | false | 10 |
| R10142 | CLI — `sovereign run <task>` invokes a task | dump 15634 | F05078 | non-negotiable | false | 10 |
| R10143 | CLI — `sovereign resume <session-id>` resumes hibernated session | dump 15634 + cross-ref M047 | F05079 | non-negotiable | false | 10 |
| R10144 | CLI — `sovereign inspect <trace-id>` opens trace detail | dump 15634 + cross-ref M049 | F05080 | non-negotiable | false | 10 |
| R10145 | CLI — `sovereign rollback <commit-id>` rolls back commit | dump 15634 + cross-ref MS041 | F05081 | non-negotiable | false | 10 |
| R10146 | CLI — `sovereign profile <name>` switches active profile | dump 15634 + cross-ref MS040 | F05082 | non-negotiable | false | 10 |
| R10147 | CLI — all commands emit M049 trace | cross-ref M049 | F05078 | non-negotiable | false | 10 |
| R10148 | CLI — all commands signed via MS003 | cross-ref selfdef MS003 | F05081 | non-negotiable | false | 10 |
| R10149 | CLI — `--json` flag returns structured output | architecture | F05078 | non-negotiable | false | 10 |
| R10150 | CLI — `--watch` flag streams updates | architecture | F05078 | non-negotiable | false | 10 |
| R10151 | API — Anthropic-first primary surface (5 endpoints) per dump 9979-9985 | dump 9979-9985 | F05083 | non-negotiable | false | 10 |
| R10152 | API — POST /v1/messages | dump 9981 | F05083 | non-negotiable | false | 10 |
| R10153 | API — GET /v1/models | dump 9981 | F05084 | non-negotiable | false | 10 |
| R10154 | API — POST /v1/messages/count_tokens | dump 9981 | F05085 | non-negotiable | false | 10 |
| R10155 | API — SSE streaming events | dump 9982 | F05086 | non-negotiable | false | 10 |
| R10156 | API — tool_use / tool_result blocks | dump 9982 | F05087 | non-negotiable | false | 10 |
| R10157 | API — system + messages format | dump 9982 | F05083 | non-negotiable | false | 10 |
| R10158 | API — OpenAI-compatible secondary surface (4 endpoints) per dump 9991-9994 | dump 9991-9994 | F05088 | non-negotiable | false | 10 |
| R10159 | API — POST /v1/chat/completions | dump 9991 | F05088 | non-negotiable | false | 10 |
| R10160 | API — POST /v1/responses | dump 9992 | F05089 | non-negotiable | false | 10 |
| R10161 | API — POST /v1/embeddings | dump 9993 | F05090 | non-negotiable | false | 10 |
| R10162 | API — OpenAI GET /v1/models | dump 9994 | F05091 | non-negotiable | false | 10 |
| R10163 | API — Anthropic-first is primary; OpenAI is secondary adapter | dump 9979-9990 | F05083 | non-negotiable | false | 10 |
| R10164 | API — gateway listens on configurable port (default 11434, mirroring Ollama tradition) | architecture | F05083 | non-negotiable | false | 10 |
| R10165 | API — TLS enabled by default with selfdef MS003 cert chain | cross-ref selfdef MS003 | F05083 | non-negotiable | false | 10 |
| R10166 | API — every request emits M049 trace + OCSF event | cross-ref M049 + cross-ref selfdef MS026 | F05083 | non-negotiable | false | 10 |
| R10167 | IDE — Claude Code via base_url override | dump 9732-9740 | F05092 | non-negotiable | false | 10 |
| R10168 | IDE — Cline via base_url override | dump 9732-9740 + dump 15660 | F05093 | non-negotiable | false | 10 |
| R10169 | IDE — OpenCode via base_url override | dump 9732-9740 + dump 15660 | F05094 | non-negotiable | false | 10 |
| R10170 | IDE — local tools via env-var BASE_URL or per-tool config | dump 9734-9740 | F05092 | non-negotiable | false | 10 |
| R10171 | IDE — Claude Code remains the CLIENT; sovereign-os runtime is the KERNEL (dump 10012-10044) | dump 10012-10044 | F05092 | non-negotiable | false | 10 |
| R10172 | IDE — MCP/Hook integration documented for Claude Code (dump 10005-10010) | dump 10005-10010 | F05092 | non-negotiable | false | 10 |
| R10173 | Configuration — User level: simple profiles + prompts | dump 14763-14765 | F05095 | non-negotiable | false | 10 |
| R10174 | Configuration — Power-user level: toggles + budgets + allowed providers + sandbox levels | dump 14767-14769 | F05096 | non-negotiable | false | 10 |
| R10175 | Configuration — System level: policy + hardware profile + routing weights + eval thresholds | dump 14771-14773 | F05097 | non-negotiable | false | 10 |
| R10176 | Configuration — three levels never auto-promote (operator must opt-in) | dump 14776 + operator standing direction | F05095 | non-negotiable | false | 10 |
| R10177 | Configuration — config changes emit M049 trace + OCSF Configuration Change class 5001 | cross-ref M049 + cross-ref MS026 | F05096 | non-negotiable | false | 10 |
| R10178 | Configuration — config changes signed via selfdef MS003 | cross-ref selfdef MS003 | F05096 | non-negotiable | false | 10 |
| R10179 | Configuration — config retained 365 days with prior versions accessible | architecture | F05095 | non-negotiable | false | 10 |
| R10180 | UX — keyboard shortcuts work in every dashboard (Cmd-K opens palette) | operator standing direction 2026-05-19 | F05098 | non-negotiable | false | 10 |
| R10181 | UX — every action surfaceable via keyboard (no mouse-only paths) | operator standing direction 2026-05-19 + WCAG 2.1 | F05100 | non-negotiable | false | 10 |
| R10182 | UX — focus indicators visible (3px outline minimum) | operator standing direction 2026-05-19 + WCAG 2.1 | F05100 | non-negotiable | false | 10 |
| R10183 | UX — color contrast 4.5:1 minimum (WCAG 2.1 AA text) | operator standing direction 2026-05-19 + WCAG 2.1 | F05100 | non-negotiable | false | 10 |
| R10184 | UX — destructive actions require confirmation (rollback / kill / forget) | operator standing direction 2026-05-19 + architecture | F05033 | non-negotiable | false | 10 |
| R10185 | UX — undo available where action is reversible (memory promote/forget) | architecture | F05055 | non-negotiable | false | 10 |
| R10186 | UX — toast notifications for asynchronous results | operator standing direction 2026-05-19 | F05098 | non-negotiable | false | 10 |
| R10187 | UX — empty states show next-action hint (never blank panel) | operator standing direction 2026-05-19 | F05098 | non-negotiable | false | 10 |
| R10188 | UX — error states show root-cause + recovery action | operator standing direction 2026-05-19 + cross-ref M055 | F05098 | non-negotiable | false | 10 |
| R10189 | UX — long-running operations show progress + ETA + cancel | operator standing direction 2026-05-19 | F05031 | non-negotiable | false | 10 |
| R10190 | Boundary — sovereign-os runtime OWNS user-facing dashboards | architecture + operator standing direction | F05026 | non-negotiable | false | 10 |
| R10191 | Boundary — selfdef IPS state surfaced READ-ONLY via MS007 typed mirrors | cross-ref MS007 + operator standing direction | F05069 | non-negotiable | false | 10 |
| R10192 | Boundary — operator restore actions for selfdef state proxied via MS003-signed requests | cross-ref selfdef MS003 + cross-ref MS042 | F05074 | non-negotiable | false | 10 |
| R10193 | Boundary — info-hub knowledge layer surfaces read-only in optional contextual panels | operator standing direction (knowledge = second-brain) | F05098 | non-negotiable | false | 10 |
| R10194 | Boundary — cockpit never mutates info-hub | operator standing direction | F05098 | non-negotiable | false | 10 |
| R10195 | Boundary — cockpit never mutates selfdef directly | operator standing direction + cross-ref MS007 | F05069 | non-negotiable | false | 10 |
| R10196 | Implementation — cockpit web frontend = Next.js or SvelteKit, fingerprint-CSP, no eval | architecture | F05026 | non-negotiable | false | 10 |
| R10197 | Implementation — cockpit served by sovereign-os runtime on localhost-only by default | architecture | F05026 | non-negotiable | false | 10 |
| R10198 | Implementation — cockpit reachable via LAN only when operator-toggled (default off) | architecture + operator standing direction | F05096 | non-negotiable | false | 10 |
| R10199 | Closing — 21 dashboards (D-00..D-20) satisfy operator "20+ dashboards and a main one" verbatim | operator standing direction 2026-05-19 | F05026 | non-negotiable | false | 10 |
| R10200 | Closing — every R-row carries 10 hard non-negotiable sub-requirements | operator standing direction | F05016 | non-negotiable | false | 10 |

## Sub-requirements accounting

Every R-row carries 10 hard non-negotiable sub-requirements per operator standing direction. Total enforced sub-reqs = 170 R × 10 = **1,700 sub-requirements** for M060.

## Cross-references

- **M045** — Linux as intelligence governor (PSI gauges for D-09)
- **M046** — beat-the-cloud runtime adaptation + LoRA Foundry (D-10 + D-11)
- **M047** — continuity (D-01 hibernate/resume + D-08 rollback points)
- **M048** — modules map (D-03 model health + D-07 memory)
- **M049** — observability + trace pipeline (D-05 traces + every dashboard's M049 span)
- **M053** — implementation language (11 build phases — D-19 reflects current phase)
- **M055** — failure modes (error states reference 10 taxonomies)
- **M057** — 12-step task lifecycle (D-01 step indicators)
- **M058** — hardware-aware scheduler (D-03 + D-09)
- **M059** — peace machine close (D-19 + D-20)
- **selfdef MS003** — selfdef-signing (signs cockpit config + dashboard toggles + CLI commands + API certs)
- **selfdef MS007** — 8/8 SATURATED typed-mirror crate scheme (cross-repo dashboards D-12..D-18 only via mirrors)
- **selfdef MS009** — audit cycles (D-16)
- **selfdef MS026** — observability + OCSF events
- **selfdef MS035** — capability tokens (D-14)
- **selfdef MS036** — sandbox tiers (D-15)
- **selfdef MS037** — filesystem boundary (D-13)
- **selfdef MS038** — network boundary (D-12)
- **selfdef MS039** — authority levels + trust rings (D-02 envelope visualization)
- **selfdef MS040** — six-profile authority matrix (D-02 selector + D-06 batch approve)
- **selfdef MS041** — commit authority (D-08 rollback)
- **selfdef MS042** — tool authority (D-17 quarantine + D-18 trust scores)

## Schema

```
schema_version: "1.0.0"
milestone_id: M060
parent: sovereign-os
epics: 10
modules: 17
features: 85
requirements: 170
sub_requirements_per_requirement: 10
total_sub_requirements: 1700
source_dump_lines:
  - 581
  - 3290-3325
  - 6789
  - 9979-10000
  - 9732-9740
  - 14760-14780
  - 15315-15345
  - 15625-15665
  - 16440-16466
dashboards:
  - D-00: main index
  - D-01: active sessions
  - D-02: profile choices
  - D-03: model health
  - D-04: costs
  - D-05: traces
  - D-06: pending approvals
  - D-07: memory changes
  - D-08: rollback points
  - D-09: hardware pressure
  - D-10: eval history
  - D-11: adapter status
  - D-12: networking (selfdef MS038 + MS039 mirror)
  - D-13: filesystem grants (selfdef MS037 mirror)
  - D-14: capability tokens (selfdef MS035 mirror)
  - D-15: sandboxes (selfdef MS036 mirror)
  - D-16: audit cycles (selfdef MS009 mirror)
  - D-17: quarantine (selfdef MS042 mirror)
  - D-18: trust scores (selfdef MS042 mirror)
  - D-19: super-model manifest
  - D-20: peace machine health
total_dashboards: 21
```
