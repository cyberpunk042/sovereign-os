# M034 — Anthropic-first gateway + MCP + Claude Code integration

> Parent: `backlog/milestones/INDEX.md` row M034 (dump 9958–10109).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 9958–10109 (operator declaration "I am anthropic first" at 9958 → 9-section response).
> All entries below are extracted from the dump line range. No invention.

## Epics (E0318–E0327)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0318 | Operator declaration — "I am antropic first" (sic; verbatim 9958); station exposes Anthropic-native face FIRST, OpenAI-compatible as SECOND adapter | 9958–9975 |
| E0319 | Anthropic-First Gateway — primary surface (/v1/messages + /v1/models + /v1/messages/count_tokens + streaming events + tool_use/tool_result blocks + system+messages format); secondary surface (/v1/chat/completions + /v1/responses + /v1/embeddings + /v1/models); rationale = Claude Code, Claude Agent SDK, hooks, subagents, MCP, structured outputs all naturally aligned with Anthropic ecosystem | 9977–9999 |
| E0320 | Research Signal — Claude Code has serious extension points: MCP (connects to tools+resources; servers expose prompts as slash commands) + Hooks (intercept execution events: tool calls / prompt submission / subagent activity / completion — "exactly where policy and replay can attach") + Subagents (specialized delegated agents with own context + MCP tool access) + Claude Agent SDK (structured output + typed integration surfaces; TypeScript SDK) | 10001–10009 |
| E0321 | Two-way integration plan — (1) API Compatibility: Claude Code points at your local Anthropic-compatible gateway; (2) MCP/Hook Integration: Claude Code exposes tool events and prompts into your deterministic runtime | 10010–10018 |
| E0322 | Claude Code As Client Not Kernel — important distinction; Claude Code = client / UI / workflow participant; YOUR STATION RUNTIME = the kernel | 10020–10027 |
| E0323 | Claude Code can — edit code / run subagents / invoke MCP tools / provide terminal workflow / stream interaction | 10029–10037 |
| E0324 | Runtime owns — routing / cost tracking / local-cloud toggles / policy / memory / replay / profiles / model aliasing | 10039–10050 |
| E0325 | Anthropic Model Aliases — Claude-style model names as profile handles (claude-jean-local / claude-jean-fast / claude-jean-code / claude-jean-careful / claude-jean-private / claude-jean-hybrid / claude-jean-oracle); "Claude Code thinks it is selecting a model. Your gateway interprets it as a route." 4 worked examples (claude-jean-private = local only no cloud no network strict tool gates / claude-jean-code = local scout + Blackwell oracle + tests + memory / claude-jean-hybrid = local first, Anthropic cloud only if approved / claude-jean-oracle = Anthropic cloud allowed for final review) | 10052–10081 |
| E0326 | MCP Security Note — MCP is powerful → belongs behind your policy engine; recent security reporting around MCP + MCP servers reinforces basic principle: MCP tools must NOT receive ambient authority by default; treat every MCP server as a capability-bearing tool boundary; flow = MCP tool call → gateway/runtime policy → capability check → execute/deny/ask → replay | 10083–10091 |
| E0327 | Where To Continue Next — Anthropic-first integration plan with 7 components (local Anthropic-compatible gateway / Claude Code hooks / MCP server registry / subagent profiles / cost ledger / policy/replay bridge / OpenAI adapter as compatibility shim); "keeps your preferred ecosystem as the front door while preserving the bigger idea: the station is a programmable intelligence substrate, not a pile of client configs" | 10092–10107 |

## Modules (M00561–M00577)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00561 | Primary surface — /v1/messages (Anthropic Messages API) | 9982 | E0319 |
| M00562 | Primary surface — /v1/models (Anthropic models-list) | 9983 | E0319 |
| M00563 | Primary surface — /v1/messages/count_tokens | 9984 | E0319 |
| M00564 | Primary surface — streaming events (Anthropic event-stream) | 9985 | E0319 |
| M00565 | Primary surface — tool_use / tool_result blocks | 9986 | E0319 |
| M00566 | Primary surface — system + messages format | 9987 | E0319 |
| M00567 | Secondary surface — /v1/chat/completions (OpenAI-compatible) | 9993 | E0319 |
| M00568 | Secondary surface — /v1/responses (OpenAI Responses API) | 9994 | E0319 |
| M00569 | Secondary surface — /v1/embeddings (OpenAI Embeddings API) | 9995 | E0319 |
| M00570 | Secondary surface — /v1/models (OpenAI-compatible models-list) | 9996 | E0319 |
| M00571 | Claude Code Hooks extension point — intercept tool calls / prompt submission / subagent activity / completion | 10006 | E0320 |
| M00572 | Claude Code MCP extension point — tool+resource connection; servers expose prompts as slash commands | 10005 | E0320 |
| M00573 | Claude Code Subagents extension point — specialized delegated agents with own context + MCP tool access | 10007 | E0320 |
| M00574 | Claude Agent SDK — structured output + typed integration surfaces (TypeScript SDK cited) | 10008 | E0320 |
| M00575 | Anthropic model alias catalog — 7 aliases (claude-jean-local / claude-jean-fast / claude-jean-code / claude-jean-careful / claude-jean-private / claude-jean-hybrid / claude-jean-oracle) | 10057–10063 | E0325 |
| M00576 | MCP capability gate — MCP tool call → gateway/runtime policy → capability check → execute/deny/ask → replay | 10088–10090 | E0326 |
| M00577 | Anthropic-first integration plan — 7 components (local Anthropic-compatible gateway / Claude Code hooks / MCP server registry / subagent profiles / cost ledger / policy/replay bridge / OpenAI adapter as compatibility shim) | 10096–10104 | E0327 |

## Features (F02806–F02890)

| F ID | Phrase | Dump line | Parent | Category | Opt-in |
|---|---|---|---|---|---|
| F02806 | Operator declaration (verbatim, 9958) — "I am antropic first btw. but yeah that's fine. lets continue other." | 9958 | E0318 | composite | false |
| F02807 | Station exposes Anthropic-native face FIRST | 9975 | E0319 | composite | false |
| F02808 | Station exposes OpenAI-compatible as SECOND adapter | 9975 | E0319 | composite | false |
| F02809 | Anthropic primary — /v1/messages | 9982 | M00561 | composite | true |
| F02810 | Anthropic primary — /v1/models | 9983 | M00562 | composite | true |
| F02811 | Anthropic primary — /v1/messages/count_tokens | 9984 | M00563 | composite | true |
| F02812 | Anthropic primary — streaming events | 9985 | M00564 | composite | true |
| F02813 | Anthropic primary — tool_use blocks | 9986 | M00565 | composite | true |
| F02814 | Anthropic primary — tool_result blocks | 9986 | M00565 | composite | true |
| F02815 | Anthropic primary — system + messages format | 9987 | M00566 | composite | true |
| F02816 | OpenAI secondary — /v1/chat/completions | 9993 | M00567 | composite | true |
| F02817 | OpenAI secondary — /v1/responses | 9994 | M00568 | composite | true |
| F02818 | OpenAI secondary — /v1/embeddings | 9995 | M00569 | composite | true |
| F02819 | OpenAI secondary — /v1/models | 9996 | M00570 | composite | true |
| F02820 | Rationale — Claude Code naturally aligned with Anthropic ecosystem | 9999 | E0319 | composite | false |
| F02821 | Rationale — Claude Agent SDK naturally aligned with Anthropic ecosystem | 9999 | E0319 | composite | false |
| F02822 | Rationale — hooks naturally aligned with Anthropic ecosystem | 9999 | E0319 | composite | false |
| F02823 | Rationale — subagents naturally aligned with Anthropic ecosystem | 9999 | E0319 | composite | false |
| F02824 | Rationale — MCP naturally aligned with Anthropic ecosystem | 9999 | E0319 | composite | false |
| F02825 | Rationale — structured outputs naturally aligned with Anthropic ecosystem | 9999 | E0319 | composite | false |
| F02826 | Claude Code MCP — connects to tools and resources | 10005 | M00572 | composite | true |
| F02827 | Claude Code MCP — servers can expose prompts as slash commands | 10005 | M00572 | composite | true |
| F02828 | Claude Code Hooks — intercept tool calls | 10006 | M00571 | composite | true |
| F02829 | Claude Code Hooks — intercept prompt submission | 10006 | M00571 | composite | true |
| F02830 | Claude Code Hooks — intercept subagent activity | 10006 | M00571 | composite | true |
| F02831 | Claude Code Hooks — intercept completion | 10006 | M00571 | composite | true |
| F02832 | Claude Code Hooks — "exactly where policy and replay can attach" | 10006 | M00571 | composite | false |
| F02833 | Claude Code Subagents — specialized delegated agents | 10007 | M00573 | composite | true |
| F02834 | Claude Code Subagents — own context | 10007 | M00573 | composite | true |
| F02835 | Claude Code Subagents — own MCP tool access | 10007 | M00573 | composite | true |
| F02836 | Claude Agent SDK — supports structured output | 10008 | M00574 | composite | true |
| F02837 | Claude Agent SDK — supports typed integration surfaces | 10008 | M00574 | composite | true |
| F02838 | Claude Agent SDK — TypeScript SDK cited | 10008 | M00574 | composite | true |
| F02839 | Integration way 1 — API Compatibility | 10013 | E0321 | composite | false |
| F02840 | Integration way 1 — Claude Code points at your local Anthropic-compatible gateway | 10014 | E0321 | composite | false |
| F02841 | Integration way 2 — MCP/Hook Integration | 10016 | E0321 | composite | false |
| F02842 | Integration way 2 — Claude Code exposes tool events and prompts into your deterministic runtime | 10017 | E0321 | composite | false |
| F02843 | Distinction — Claude Code should be a client/UI/workflow participant | 10025 | E0322 | composite | false |
| F02844 | Distinction — Your station runtime should be the kernel | 10026 | E0322 | composite | false |
| F02845 | Claude Code can — edit code | 10032 | E0323 | composite | true |
| F02846 | Claude Code can — run subagents | 10033 | E0323 | composite | true |
| F02847 | Claude Code can — invoke MCP tools | 10034 | E0323 | composite | true |
| F02848 | Claude Code can — provide terminal workflow | 10035 | E0323 | composite | true |
| F02849 | Claude Code can — stream interaction | 10036 | E0323 | composite | true |
| F02850 | Runtime owns — routing | 10042 | E0324 | composite | false |
| F02851 | Runtime owns — cost tracking | 10043 | E0324 | composite | false |
| F02852 | Runtime owns — local/cloud toggles | 10044 | E0324 | composite | false |
| F02853 | Runtime owns — policy | 10045 | E0324 | composite | false |
| F02854 | Runtime owns — memory | 10046 | E0324 | composite | false |
| F02855 | Runtime owns — replay | 10047 | E0324 | composite | false |
| F02856 | Runtime owns — profiles | 10048 | E0324 | composite | false |
| F02857 | Runtime owns — model aliasing | 10049 | E0324 | composite | false |
| F02858 | Anthropic alias — claude-jean-local | 10057 | M00575 | composite | true |
| F02859 | Anthropic alias — claude-jean-fast | 10058 | M00575 | composite | true |
| F02860 | Anthropic alias — claude-jean-code | 10059 | M00575 | composite | true |
| F02861 | Anthropic alias — claude-jean-careful | 10060 | M00575 | composite | true |
| F02862 | Anthropic alias — claude-jean-private | 10061 | M00575 | composite | true |
| F02863 | Anthropic alias — claude-jean-hybrid | 10062 | M00575 | composite | true |
| F02864 | Anthropic alias — claude-jean-oracle | 10063 | M00575 | composite | true |
| F02865 | Closing-trick — Claude Code thinks it is selecting a model | 10066 | E0325 | composite | false |
| F02866 | Closing-trick — Your gateway interprets it as a route | 10066 | E0325 | composite | false |
| F02867 | claude-jean-private — local only / no cloud / no network / strict tool gates | 10069–10070 | M00575 | composite | true |
| F02868 | claude-jean-code — local scout + Blackwell oracle + tests + memory | 10072–10073 | M00575 | composite | true |
| F02869 | claude-jean-hybrid — local first / Anthropic cloud only if approved | 10075–10076 | M00575 | composite | true |
| F02870 | claude-jean-oracle — Anthropic cloud allowed for final review | 10078–10079 | M00575 | composite | true |
| F02871 | MCP is powerful — belongs behind your policy engine | 10084 | E0326 | composite | false |
| F02872 | MCP security reporting principle — MCP tools must NOT receive ambient authority by default | 10084 | E0326 | composite | false |
| F02873 | MCP security principle — treat every MCP server as a capability-bearing tool boundary | 10084 | E0326 | composite | false |
| F02874 | MCP capability gate flow — MCP tool call → gateway/runtime policy | 10088–10089 | M00576 | composite | false |
| F02875 | MCP capability gate flow — capability check | 10089 | M00576 | composite | false |
| F02876 | MCP capability gate flow — execute/deny/ask | 10089 | M00576 | composite | false |
| F02877 | MCP capability gate flow — replay | 10090 | M00576 | composite | false |
| F02878 | Integration plan component — local Anthropic-compatible gateway | 10098 | M00577 | composite | true |
| F02879 | Integration plan component — Claude Code hooks | 10099 | M00577 | composite | true |
| F02880 | Integration plan component — MCP server registry | 10100 | M00577 | composite | true |
| F02881 | Integration plan component — subagent profiles | 10101 | M00577 | composite | true |
| F02882 | Integration plan component — cost ledger | 10102 | M00577 | composite | true |
| F02883 | Integration plan component — policy/replay bridge | 10103 | M00577 | composite | true |
| F02884 | Integration plan component — OpenAI adapter as compatibility shim | 10104 | M00577 | composite | true |
| F02885 | Closing — keeps preferred ecosystem as front door | 10106 | E0327 | composite | false |
| F02886 | Closing — preserves bigger idea: station is a programmable intelligence substrate, not a pile of client configs | 10107 | E0327 | composite | false |
| F02887 | Composite — Anthropic-first means /v1/messages is the canonical Anthropic Messages API surface; OpenAI surface is shim | 9977–9998 | E0319 | composite | false |
| F02888 | Composite — Claude Code is a client/UI/workflow participant; the station runtime is the kernel | 10025–10027 | E0322 | composite | false |
| F02889 | Composite — every MCP tool call gated through gateway/runtime policy + capability check + replay | 10088–10090 | M00576 | composite | false |
| F02890 | Composite — 7-component Anthropic-first integration plan (Anthropic gateway / Claude Code hooks / MCP server registry / subagent profiles / cost ledger / policy/replay bridge / OpenAI adapter) keeps Anthropic as front door without ceding kernel ownership; "the station is a programmable intelligence substrate, not a pile of client configs" | 10094–10107 | E0327 | composite | false |

## Requirements (R05611–R05780)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R05611 | Operator declaration — "I am antropic first" (verbatim 9958) | 9958 | F02806 | non-negotiable | false | 10 |
| R05612 | Station MUST expose Anthropic-native face FIRST | 9975 | F02807 | non-negotiable | false | 10 |
| R05613 | Station MUST expose OpenAI-compatible as SECOND adapter | 9975 | F02808 | non-negotiable | false | 10 |
| R05614 | Anthropic primary surface — /v1/messages | 9982 | F02809 | non-negotiable | true | 10 |
| R05615 | Anthropic primary surface — /v1/models | 9983 | F02810 | non-negotiable | true | 10 |
| R05616 | Anthropic primary surface — /v1/messages/count_tokens | 9984 | F02811 | non-negotiable | true | 10 |
| R05617 | Anthropic primary surface — streaming events | 9985 | F02812 | non-negotiable | true | 10 |
| R05618 | Anthropic primary surface — tool_use blocks | 9986 | F02813 | non-negotiable | true | 10 |
| R05619 | Anthropic primary surface — tool_result blocks | 9986 | F02814 | non-negotiable | true | 10 |
| R05620 | Anthropic primary surface — system + messages format | 9987 | F02815 | non-negotiable | true | 10 |
| R05621 | OpenAI secondary surface — /v1/chat/completions | 9993 | F02816 | non-negotiable | true | 10 |
| R05622 | OpenAI secondary surface — /v1/responses | 9994 | F02817 | non-negotiable | true | 10 |
| R05623 | OpenAI secondary surface — /v1/embeddings | 9995 | F02818 | non-negotiable | true | 10 |
| R05624 | OpenAI secondary surface — /v1/models | 9996 | F02819 | non-negotiable | true | 10 |
| R05625 | Rationale — Claude Code aligned with Anthropic ecosystem | 9999 | F02820 | non-negotiable | false | 10 |
| R05626 | Rationale — Claude Agent SDK aligned with Anthropic ecosystem | 9999 | F02821 | non-negotiable | false | 10 |
| R05627 | Rationale — hooks aligned with Anthropic ecosystem | 9999 | F02822 | non-negotiable | false | 10 |
| R05628 | Rationale — subagents aligned with Anthropic ecosystem | 9999 | F02823 | non-negotiable | false | 10 |
| R05629 | Rationale — MCP aligned with Anthropic ecosystem | 9999 | F02824 | non-negotiable | false | 10 |
| R05630 | Rationale — structured outputs aligned with Anthropic ecosystem | 9999 | F02825 | non-negotiable | false | 10 |
| R05631 | Claude Code MCP — connects to tools and resources | 10005 | F02826 | non-negotiable | true | 10 |
| R05632 | Claude Code MCP — servers expose prompts as slash commands | 10005 | F02827 | non-negotiable | true | 10 |
| R05633 | Claude Code Hooks — intercept tool calls | 10006 | F02828 | non-negotiable | true | 10 |
| R05634 | Claude Code Hooks — intercept prompt submission | 10006 | F02829 | non-negotiable | true | 10 |
| R05635 | Claude Code Hooks — intercept subagent activity | 10006 | F02830 | non-negotiable | true | 10 |
| R05636 | Claude Code Hooks — intercept completion | 10006 | F02831 | non-negotiable | true | 10 |
| R05637 | Claude Code Hooks — "exactly where policy and replay can attach" | 10006 | F02832 | non-negotiable | false | 10 |
| R05638 | Claude Code Subagents — specialized delegated agents | 10007 | F02833 | non-negotiable | true | 10 |
| R05639 | Claude Code Subagents — own context | 10007 | F02834 | non-negotiable | true | 10 |
| R05640 | Claude Code Subagents — own MCP tool access | 10007 | F02835 | non-negotiable | true | 10 |
| R05641 | Claude Agent SDK — structured output | 10008 | F02836 | non-negotiable | true | 10 |
| R05642 | Claude Agent SDK — typed integration surfaces | 10008 | F02837 | non-negotiable | true | 10 |
| R05643 | Claude Agent SDK — TypeScript SDK cited | 10008 | F02838 | non-negotiable | true | 10 |
| R05644 | Integration way 1 — API Compatibility | 10013 | F02839 | non-negotiable | false | 10 |
| R05645 | Integration way 1 — Claude Code points at local Anthropic-compatible gateway | 10014 | F02840 | non-negotiable | false | 10 |
| R05646 | Integration way 2 — MCP/Hook Integration | 10016 | F02841 | non-negotiable | false | 10 |
| R05647 | Integration way 2 — Claude Code exposes tool events and prompts into deterministic runtime | 10017 | F02842 | non-negotiable | false | 10 |
| R05648 | Distinction — Claude Code is a client/UI/workflow participant | 10025 | F02843 | non-negotiable | false | 10 |
| R05649 | Distinction — Your station runtime is the kernel | 10026 | F02844 | non-negotiable | false | 10 |
| R05650 | Claude Code can — edit code | 10032 | F02845 | non-negotiable | true | 10 |
| R05651 | Claude Code can — run subagents | 10033 | F02846 | non-negotiable | true | 10 |
| R05652 | Claude Code can — invoke MCP tools | 10034 | F02847 | non-negotiable | true | 10 |
| R05653 | Claude Code can — provide terminal workflow | 10035 | F02848 | non-negotiable | true | 10 |
| R05654 | Claude Code can — stream interaction | 10036 | F02849 | non-negotiable | true | 10 |
| R05655 | Runtime owns — routing | 10042 | F02850 | non-negotiable | false | 10 |
| R05656 | Runtime owns — cost tracking | 10043 | F02851 | non-negotiable | false | 10 |
| R05657 | Runtime owns — local/cloud toggles | 10044 | F02852 | non-negotiable | false | 10 |
| R05658 | Runtime owns — policy | 10045 | F02853 | non-negotiable | false | 10 |
| R05659 | Runtime owns — memory | 10046 | F02854 | non-negotiable | false | 10 |
| R05660 | Runtime owns — replay | 10047 | F02855 | non-negotiable | false | 10 |
| R05661 | Runtime owns — profiles | 10048 | F02856 | non-negotiable | false | 10 |
| R05662 | Runtime owns — model aliasing | 10049 | F02857 | non-negotiable | false | 10 |
| R05663 | Anthropic alias — claude-jean-local | 10057 | F02858 | non-negotiable | true | 10 |
| R05664 | Anthropic alias — claude-jean-fast | 10058 | F02859 | non-negotiable | true | 10 |
| R05665 | Anthropic alias — claude-jean-code | 10059 | F02860 | non-negotiable | true | 10 |
| R05666 | Anthropic alias — claude-jean-careful | 10060 | F02861 | non-negotiable | true | 10 |
| R05667 | Anthropic alias — claude-jean-private | 10061 | F02862 | non-negotiable | true | 10 |
| R05668 | Anthropic alias — claude-jean-hybrid | 10062 | F02863 | non-negotiable | true | 10 |
| R05669 | Anthropic alias — claude-jean-oracle | 10063 | F02864 | non-negotiable | true | 10 |
| R05670 | Closing-trick — "Claude Code thinks it is selecting a model. Your gateway interprets it as a route." | 10066 | F02865 + F02866 | non-negotiable | false | 10 |
| R05671 | claude-jean-private — local only / no cloud / no network / strict tool gates | 10069–10070 | F02867 | non-negotiable | true | 10 |
| R05672 | claude-jean-code — local scout + Blackwell oracle + tests + memory | 10072–10073 | F02868 | non-negotiable | true | 10 |
| R05673 | claude-jean-hybrid — local first / Anthropic cloud only if approved | 10075–10076 | F02869 | non-negotiable | true | 10 |
| R05674 | claude-jean-oracle — Anthropic cloud allowed for final review | 10078–10079 | F02870 | non-negotiable | true | 10 |
| R05675 | MCP security — MCP is powerful, belongs behind your policy engine | 10084 | F02871 | non-negotiable | false | 10 |
| R05676 | MCP security — MCP tools must NOT receive ambient authority by default | 10084 | F02872 | non-negotiable | false | 10 |
| R05677 | MCP security — treat every MCP server as a capability-bearing tool boundary | 10084 | F02873 | non-negotiable | false | 10 |
| R05678 | MCP capability gate flow — MCP tool call | 10088 | F02874 | non-negotiable | false | 10 |
| R05679 | MCP capability gate flow — gateway/runtime policy | 10089 | F02874 | non-negotiable | false | 10 |
| R05680 | MCP capability gate flow — capability check | 10089 | F02875 | non-negotiable | false | 10 |
| R05681 | MCP capability gate flow — execute/deny/ask | 10089 | F02876 | non-negotiable | false | 10 |
| R05682 | MCP capability gate flow — replay | 10090 | F02877 | non-negotiable | false | 10 |
| R05683 | Integration plan component — local Anthropic-compatible gateway | 10098 | F02878 | non-negotiable | true | 10 |
| R05684 | Integration plan component — Claude Code hooks | 10099 | F02879 | non-negotiable | true | 10 |
| R05685 | Integration plan component — MCP server registry | 10100 | F02880 | non-negotiable | true | 10 |
| R05686 | Integration plan component — subagent profiles | 10101 | F02881 | non-negotiable | true | 10 |
| R05687 | Integration plan component — cost ledger | 10102 | F02882 | non-negotiable | true | 10 |
| R05688 | Integration plan component — policy/replay bridge | 10103 | F02883 | non-negotiable | true | 10 |
| R05689 | Integration plan component — OpenAI adapter as compatibility shim | 10104 | F02884 | non-negotiable | true | 10 |
| R05690 | Closing — keeps preferred ecosystem (Anthropic) as front door | 10106 | F02885 | non-negotiable | false | 10 |
| R05691 | Closing — preserves bigger idea: station is a programmable intelligence substrate | 10107 | F02886 | non-negotiable | false | 10 |
| R05692 | Closing — station is NOT a pile of client configs | 10107 | F02886 | non-negotiable | false | 10 |
| R05693 | M034 supersedes M033 surface ordering — Anthropic primary / OpenAI secondary (M033 listed them as parallel) | 9975 + cross-ref M033 R05451 | F02887 | non-negotiable | false | 10 |
| R05694 | M034 retains M033 OpenAI surface as compatibility shim | 9993–9996 + 10104 | F02884 | non-negotiable | false | 10 |
| R05695 | M034 reaffirms M033 Core Rule — external clients see a normal API; station sees typed frames | cross-ref M033 R05539–R05540 | F02844 | non-negotiable | false | 10 |
| R05696 | M034 integration with Compatibility Gateway (M033) — Anthropic facade = primary; OpenAI facade = secondary shim | M033 + M034 | E0319 | non-negotiable | false | 10 |
| R05697 | M034 reuses M033 model alias trick — model names encode behavior; Claude Code uses Anthropic-style claude-jean-* aliases | 10052–10066 + cross-ref M033 R05492–R05501 | M00575 | non-negotiable | false | 10 |
| R05698 | M034 reuses M033 cost ledger — claude-jean-* routes feed same cost-tracking ledger | 10043 + cross-ref M033 R05481–R05485 | F02851 | non-negotiable | false | 10 |
| R05699 | M034 reuses M033 policy layer — claude-jean-private/local/code routes feed same policy enforcement | 10045 + cross-ref M033 R05486–R05489 | F02853 | non-negotiable | false | 10 |
| R05700 | M034 reuses M033 streaming translator — Anthropic event-stream is the primary; OpenAI SSE is shim translation | 9985 + cross-ref M033 R05598 | M00564 | non-negotiable | false | 10 |
| R05701 | M034 reuses M033 tool/function-call translator — tool_use/tool_result is primary; OpenAI tool_calls is shim translation | 9986 + cross-ref M033 R05600–R05602 | M00565 | non-negotiable | false | 10 |
| R05702 | Hooks attach point — tool calls (per Claude Code Hooks documentation) | 10006 | M00571 | non-negotiable | false | 10 |
| R05703 | Hooks attach point — prompt submission | 10006 | M00571 | non-negotiable | false | 10 |
| R05704 | Hooks attach point — subagent activity | 10006 | M00571 | non-negotiable | false | 10 |
| R05705 | Hooks attach point — completion | 10006 | M00571 | non-negotiable | false | 10 |
| R05706 | Hooks are the policy + replay attach surface in Claude Code | 10006 | F02832 | non-negotiable | false | 10 |
| R05707 | MCP — Claude Code connects to tools and resources via MCP servers | 10005 | M00572 | non-negotiable | false | 10 |
| R05708 | MCP — servers can expose prompts as slash commands | 10005 | M00572 | non-negotiable | false | 10 |
| R05709 | Subagents — specialized delegated agents | 10007 | M00573 | non-negotiable | false | 10 |
| R05710 | Subagents — own context | 10007 | M00573 | non-negotiable | false | 10 |
| R05711 | Subagents — own MCP tool access | 10007 | M00573 | non-negotiable | false | 10 |
| R05712 | Claude Agent SDK is the typed integration surface for structured output | 10008 | M00574 | non-negotiable | false | 10 |
| R05713 | TypeScript SDK is one Claude Agent SDK form factor | 10008 | M00574 | non-negotiable | false | 10 |
| R05714 | Two-way integration is the canonical plan — API Compatibility AND MCP/Hook Integration | 10012 | E0321 | non-negotiable | false | 10 |
| R05715 | API Compatibility direction — Claude Code → gateway (consumer of /v1/messages) | 10014 | F02840 | non-negotiable | false | 10 |
| R05716 | MCP/Hook Integration direction — Claude Code → runtime (producer of tool events + prompts) | 10017 | F02842 | non-negotiable | false | 10 |
| R05717 | Claude Code = client/UI/workflow participant (NOT the kernel) | 10025 | F02843 | non-negotiable | false | 10 |
| R05718 | Station runtime = the kernel (NOT a client) | 10026 | F02844 | non-negotiable | false | 10 |
| R05719 | Claude Code edits code | 10032 | F02845 | non-negotiable | true | 10 |
| R05720 | Claude Code runs subagents | 10033 | F02846 | non-negotiable | true | 10 |
| R05721 | Claude Code invokes MCP tools | 10034 | F02847 | non-negotiable | true | 10 |
| R05722 | Claude Code provides terminal workflow | 10035 | F02848 | non-negotiable | true | 10 |
| R05723 | Claude Code streams interaction | 10036 | F02849 | non-negotiable | true | 10 |
| R05724 | Runtime owns routing decisions (not Claude Code) | 10042 | F02850 | non-negotiable | false | 10 |
| R05725 | Runtime owns cost tracking (not Claude Code) | 10043 | F02851 | non-negotiable | false | 10 |
| R05726 | Runtime owns local/cloud toggles (not Claude Code) | 10044 | F02852 | non-negotiable | false | 10 |
| R05727 | Runtime owns policy (not Claude Code) | 10045 | F02853 | non-negotiable | false | 10 |
| R05728 | Runtime owns memory (not Claude Code) | 10046 | F02854 | non-negotiable | false | 10 |
| R05729 | Runtime owns replay (not Claude Code) | 10047 | F02855 | non-negotiable | false | 10 |
| R05730 | Runtime owns profiles (not Claude Code) | 10048 | F02856 | non-negotiable | false | 10 |
| R05731 | Runtime owns model aliasing (not Claude Code) | 10049 | F02857 | non-negotiable | false | 10 |
| R05732 | Anthropic model aliases use claude-jean-* prefix convention | 10057–10063 | M00575 | non-negotiable | false | 10 |
| R05733 | Anthropic model aliases are profile handles | 10054 | M00575 | non-negotiable | false | 10 |
| R05734 | Claude Code thinks it is selecting a model | 10066 | F02865 | non-negotiable | false | 10 |
| R05735 | Gateway interprets the model selection as a route | 10066 | F02866 | non-negotiable | false | 10 |
| R05736 | claude-jean-private semantics — local only | 10069 | F02867 | non-negotiable | false | 10 |
| R05737 | claude-jean-private semantics — no cloud | 10069 | F02867 | non-negotiable | false | 10 |
| R05738 | claude-jean-private semantics — no network | 10069 | F02867 | non-negotiable | false | 10 |
| R05739 | claude-jean-private semantics — strict tool gates | 10070 | F02867 | non-negotiable | false | 10 |
| R05740 | claude-jean-code semantics — local scout | 10072 | F02868 | non-negotiable | false | 10 |
| R05741 | claude-jean-code semantics — Blackwell oracle | 10072 | F02868 | non-negotiable | false | 10 |
| R05742 | claude-jean-code semantics — tests | 10073 | F02868 | non-negotiable | false | 10 |
| R05743 | claude-jean-code semantics — memory | 10073 | F02868 | non-negotiable | false | 10 |
| R05744 | claude-jean-hybrid semantics — local first | 10075 | F02869 | non-negotiable | false | 10 |
| R05745 | claude-jean-hybrid semantics — Anthropic cloud only if approved | 10076 | F02869 | non-negotiable | false | 10 |
| R05746 | claude-jean-oracle semantics — Anthropic cloud allowed for final review | 10078–10079 | F02870 | non-negotiable | false | 10 |
| R05747 | MCP policy gate enforces capability boundaries (MCP servers do NOT have ambient authority) | 10084 | F02872 | non-negotiable | false | 10 |
| R05748 | MCP policy gate treats each MCP server as a capability-bearing tool boundary | 10084 | F02873 | non-negotiable | false | 10 |
| R05749 | MCP capability gate is mandatory (recent security reporting reinforces) | 10084 | F02871 | non-negotiable | false | 10 |
| R05750 | MCP capability gate flow step 1 — MCP tool call enters gateway | 10088 | F02874 | non-negotiable | false | 10 |
| R05751 | MCP capability gate flow step 2 — gateway/runtime policy evaluates the call | 10089 | F02874 | non-negotiable | false | 10 |
| R05752 | MCP capability gate flow step 3 — capability check (tool permitted in current profile?) | 10089 | F02875 | non-negotiable | false | 10 |
| R05753 | MCP capability gate flow step 4 — execute OR deny OR ask | 10089 | F02876 | non-negotiable | false | 10 |
| R05754 | MCP capability gate flow step 5 — replay (the action is logged for audit) | 10090 | F02877 | non-negotiable | false | 10 |
| R05755 | Anthropic-first integration plan has 7 components | 10094–10104 | M00577 | non-negotiable | false | 10 |
| R05756 | Component 1 — local Anthropic-compatible gateway | 10098 | F02878 | non-negotiable | true | 10 |
| R05757 | Component 2 — Claude Code hooks | 10099 | F02879 | non-negotiable | true | 10 |
| R05758 | Component 3 — MCP server registry | 10100 | F02880 | non-negotiable | true | 10 |
| R05759 | Component 4 — subagent profiles | 10101 | F02881 | non-negotiable | true | 10 |
| R05760 | Component 5 — cost ledger | 10102 | F02882 | non-negotiable | true | 10 |
| R05761 | Component 6 — policy/replay bridge | 10103 | F02883 | non-negotiable | true | 10 |
| R05762 | Component 7 — OpenAI adapter as compatibility shim | 10104 | F02884 | non-negotiable | true | 10 |
| R05763 | Anthropic-first plan keeps preferred ecosystem as front door | 10106 | F02885 | non-negotiable | false | 10 |
| R05764 | Anthropic-first plan preserves the bigger idea — station is a programmable intelligence substrate | 10107 | F02886 | non-negotiable | false | 10 |
| R05765 | Anthropic-first plan preserves the bigger idea — station is NOT a pile of client configs | 10107 | F02886 | non-negotiable | false | 10 |
| R05766 | M034 integrates with M025 cognitive compiler — Claude Code prompts → compile DAG when needed | cross-ref M025 | E0321 | non-negotiable | false | 10 |
| R05767 | M034 integrates with M026 SLM swarm + RLM engine — claude-jean-local routes to SLM/RLM | 10061 + cross-ref M026 | F02862 | non-negotiable | false | 10 |
| R05768 | M034 integrates with M027 Value Plane — reward formula scores cloud vs local on cost/latency/privacy | cross-ref M027 R04471 | F02856 | non-negotiable | false | 10 |
| R05769 | M034 integrates with M028 Memory OS — Memory OS persists Claude Code session memory + replay | 10046 + 10090 + cross-ref M028 | F02854 + F02877 | non-negotiable | false | 10 |
| R05770 | M034 integrates with M029 Computer-Use Plane — Claude Code computer-use tool calls flow via M034 gateway → M029 typed action system | cross-ref M029 | M00576 | non-negotiable | false | 10 |
| R05771 | M034 integrates with M030 World Model Plane — Claude Code Action is World-Model Action with expected/success/failure/rollback/risk | cross-ref M030 R05003–R05007 | F02855 | non-negotiable | false | 10 |
| R05772 | M034 integrates with M031 Symbolic Planning Plane — policy layer can VETO Claude Code action via M031 policy engine | cross-ref M031 R05225–R05227 | F02853 | non-negotiable | false | 10 |
| R05773 | M034 integrates with M032 Cloud Expert Plane — claude-jean-oracle/hybrid routes through M032 cloud-expert path | 10075–10079 + cross-ref M032 | F02869 + F02870 | non-negotiable | false | 10 |
| R05774 | M034 integrates with M033 Compatibility Gateway — M034 IS the Anthropic-first specialization of M033 (primary Anthropic facade + secondary OpenAI shim) | M033 + M034 | F02887 | non-negotiable | false | 10 |
| R05775 | Project boundary — Anthropic-first gateway is sovereign-os runtime; selfdef may observe MCP tool-call events via selfdef-collector-eventstream (NOT prompt content) | architecture + cross-ref MS002 + MS014 | E0326 | non-negotiable | false | 10 |
| R05776 | Project boundary — selfdef MS006 agent-guard may rate-limit MCP tool calls per profile + emit policy-strip-equivalent events on deny | MS006 + 10088–10090 | M00576 | non-negotiable | false | 10 |
| R05777 | Project boundary — selfdef MS007 typed-mirror crates may carry MCP server registry + subagent profile manifests for cross-repo binding | MS007 + SDD-038 | M00577 | non-negotiable | false | 10 |
| R05778 | Anthropic-first gateway is the 14th plane (extending M027 + M028 + M029 + M030 + M031 + M032 + M033) | cross-ref M027 R04590 + M028 + M029 + M030 + M031 + M032 + M033 | E0319 | non-negotiable | false | 10 |
| R05779 | Anthropic-first gateway respects the Local-Runtime-Commits invariant (M032 R05330) — Claude Code is client; runtime commits | 10025–10026 + cross-ref M032 R05330 | F02844 | non-negotiable | false | 10 |
| R05780 | Composite — Anthropic-first gateway is the operator-preferred specialization of M033 Compatibility Gateway; primary surface /v1/messages + tool_use/tool_result + streaming events; 7-component integration plan (local Anthropic gateway + Claude Code hooks + MCP server registry + subagent profiles + cost ledger + policy/replay bridge + OpenAI adapter compatibility shim); Claude Code is a client, NOT the kernel; runtime owns routing/cost/policy/memory/replay/profiles/model-aliasing; claude-jean-* alias trick (Claude Code thinks model → gateway interprets as route); MCP behind policy engine (no ambient authority; capability boundary; gate flow tool-call → policy → check → execute/deny/ask → replay); "the station is a programmable intelligence substrate, not a pile of client configs" | 9958–10107 | E0319 + E0320 + E0321 + E0322 + E0325 + E0326 + E0327 | non-negotiable | false | 10 |

## Cross-references

- Adjacent dump-range milestones: M033 Compatibility Gateway (9728–9958) / M035 (next; dump 10109–…)
- Plane integration: M025 cognitive compiler / M026 SLM swarm + RLM engine / M027 Value Plane / M028 Memory OS / M029 Computer-Use Plane / M030 World Model Plane / M031 Symbolic Planning Plane / M032 Cloud Expert Plane / M033 Compatibility Gateway / M034 Anthropic-first specialization (this)
- Selfdef boundary: selfdef-collector-eventstream may re-ingest MCP tool-call events for incident correlation (NOT prompt content); MS006 agent-guard may rate-limit + cost-track + policy-strip-equivalent on MCP denies; MS007 typed mirrors may carry MCP-server-registry + subagent-profile-manifest contracts
- Operator preference: Anthropic FIRST per operator declaration 9958 ("I am antropic first")
