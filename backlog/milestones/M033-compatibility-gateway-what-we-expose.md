# M033 — Compatibility Gateway — what we expose

> Parent: `backlog/milestones/INDEX.md` row M033 (dump 9728–9958).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 9728–9956 (operator addendum at 9728–9729 followed by 9-section response).
> All entries below are extracted from the dump line range. No invention.

## Epics (E0308–E0317)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0308 | Operator clarification — sovereign-os should expose its own OpenAI/Anthropic-compatible API surface so existing clients (Claude Code / Cline / OpenCode / Continue / aider / any OpenAI SDK app) point at local intelligence runtime by changing `base_url` / env vars; "much more important infrastructure move" than just being a remote-expert consumer | 9728–9744 |
| E0309 | API-compatible intelligence gateway — Station Gateway sits between (Claude Code / Cline / OpenCode / Cline / custom apps) and (local models / cloud APIs / tools / memory / workflows); instead of every tool talking directly to OpenAI / Anthropic / vLLM, they talk to your gateway with local routing + profiles + policies + telemetry + cost tracking | 9746–9762 |
| E0310 | What To Expose — at least 2 compatibility surfaces (OpenAI-compatible: /v1/chat/completions + /v1/responses + /v1/embeddings + /v1/models; Anthropic-compatible: /v1/messages + /v1/models + token counting if needed); clients vary (Cline supports OpenAI custom Base URL; OpenCode supports OpenAI-compatible providers + custom provider setups; vLLM already exposes OpenAI-compatible server; Claude Code is more Anthropic-shaped with ANTHROPIC_BASE_URL/proxy layers though "fussier") | 9764–9785 |
| E0311 | Gateway Responsibilities — 6 capabilities NOT a dumb proxy (1 Compatibility Translation: OpenAI request → internal Frame / Anthropic request → internal Frame / internal result → client-compatible response; 2 Model Routing: alias-resolution "gpt-5.2" → local oracle / cloud OpenAI / fallback OR "claude-sonnet" → local / Anthropic / policy-denied; 3 Profiles: model names encode behavior jean/fast jean/careful jean/local-only jean/oracle jean/code jean/research jean/sandbox; 4 Cost Tracking: tokens in/out / local GPU time / cloud spend / cache hits / per-client budget; 5 Policy: block cloud for private work / require approval for paid remote / enforce project-level limits / redact secrets before remote APIs; 6 Observability: trace every request, latency, model route, cost, cache, failures) | 9787–9828 |
| E0312 | Big Trick — Model Aliases As Profiles — clients let you choose a "model"; use that as profile selector; 6 example aliases (jean/local-fast local-SLM-scout-only; jean/code-careful local-first + oracle verify + tools-allowed-by-policy; jean/cloud-openai OpenAI-backend-allowed; jean/cloud-anthropic Anthropic-backend-allowed; jean/hybrid-oracle local-draft + cloud-or-Blackwell-verify; jean/private no-cloud-no-network-no-external-logging); "From Cline/OpenCode/etc., it just looks like model selection. Inside, it is a whole route." | 9830–9856 |
| E0313 | Environment Examples — OpenAI-compatible client uses OPENAI_API_KEY=local-or-real-key + OPENAI_BASE_URL=http://127.0.0.1:8080/v1; Python OpenAI SDK passes api_key + base_url; Cline/OpenCode configure OpenAI-compatible Base URL http://127.0.0.1:8080/v1; Anthropic-shaped clients use ANTHROPIC_AUTH_TOKEN + ANTHROPIC_BASE_URL=http://127.0.0.1:8081; "exact Claude Code behavior can be version-sensitive, so that adapter should be tested against the installed client" | 9858–9889 |
| E0314 | Cost And Toggle Layer — gateway is where you solve cost; 6 example knobs (cloud_enabled / cloud_requires_approval / daily_budget_usd / per_request_max_usd / private_paths_never_cloud / log_prompts); 5 profile toggles (local-only / local-first / ask-before-cloud / cloud-allowed / cloud-for-final-review); per-request records (client / project / profile / route / tokens / estimated cost / actual cost / cache hit / decision reason) | 9891–9926 |
| E0315 | Architecture Component — Compatibility Gateway with 8 sub-parts (OpenAI facade / Anthropic facade / model alias registry / provider router / cost ledger / policy-redaction layer / streaming translator / tool-function-call translator) | 9928–9942 |
| E0316 | Core Rule — "External clients should see a normal API. Your station should see typed frames, profiles, policies, and routes." Plug-into-existing-environment without rewriting every tool | 9944–9951 |
| E0317 | Closing — "Cline thinks it is calling OpenAI-compatible chat completions. Claude Code thinks it is calling Anthropic messages. OpenCode thinks it is calling a provider. But really, they are entering your deterministic intelligence gateway." | 9953–9956 |

## Modules (M00544–M00560)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00544 | OpenAI facade — /v1/chat/completions | 9770 | E0310 |
| M00545 | OpenAI facade — /v1/responses | 9771 | E0310 |
| M00546 | OpenAI facade — /v1/embeddings | 9772 | E0310 |
| M00547 | OpenAI facade — /v1/models | 9773 | E0310 |
| M00548 | Anthropic facade — /v1/messages | 9776 | E0310 |
| M00549 | Anthropic facade — /v1/models | 9777 | E0310 |
| M00550 | Anthropic facade — token counting (if needed) | 9778 | E0310 |
| M00551 | Compatibility translation — OpenAI request → internal Frame; Anthropic request → internal Frame; internal result → client-compatible response | 9792–9795 | E0311 |
| M00552 | Model router — alias resolution (e.g. "gpt-5.2" → local oracle profile OR cloud OpenAI OR fallback; "claude-sonnet" → local route OR Anthropic OR policy-denied) | 9797–9801 | E0311 |
| M00553 | Profile registry — 7 example aliases (jean/fast / jean/careful / jean/local-only / jean/oracle / jean/code / jean/research / jean/sandbox) | 9803–9810 | E0311 |
| M00554 | Cost tracker — tokens in/out / local GPU time / cloud spend / cache hits / per-client budget | 9813–9817 | E0311 |
| M00555 | Policy layer — block cloud for private work / require approval for paid remote calls / enforce project-level limits / redact secrets before remote APIs | 9820–9823 | E0311 |
| M00556 | Observability — trace every request / latency / model route / cost / cache / failures | 9826–9827 | E0311 |
| M00557 | Streaming translator (OpenAI SSE chunks ↔ Anthropic event stream ↔ internal frame stream) | 9940 | E0315 |
| M00558 | Tool / function-call translator (OpenAI tool_calls ↔ Anthropic tool_use ↔ internal ToolIntent) | 9941 | E0315 |
| M00559 | Default bind — OpenAI facade `http://127.0.0.1:8080/v1` + Anthropic facade `http://127.0.0.1:8081` | 9864 + 9886 | E0313 |
| M00560 | Per-request record — client / project / profile / route / tokens / estimated cost / actual cost / cache hit / decision reason | 9917–9925 | E0314 |

## Features (F02721–F02805)

| F ID | Phrase | Dump line | Parent | Category | Opt-in |
|---|---|---|---|---|---|
| F02721 | Operator addendum 9728 — modes toggle on/off / config one-time / cost tracking | 9728 | E0308 | composite | false |
| F02722 | Operator addendum 9729 — "what WE expose" interpretation: sovereign-os REPLACES env-var-API for Claude Code / OpenCode / Cline / OpenAI-consuming systems | 9729 | E0308 | composite | false |
| F02723 | Station = API-compatible intelligence gateway | 9748 | E0309 | composite | false |
| F02724 | Gateway client list — Claude Code / Cline / OpenCode / Cline (sic; duplicated in dump) / custom apps | 9751 | E0309 | composite | true |
| F02725 | Gateway interface — OpenAI-compatible OR Anthropic-compatible API | 9753 | E0309 | composite | false |
| F02726 | Gateway internal flow — local routing / profiles / policies / telemetry / cost tracking | 9757 | E0309 | composite | false |
| F02727 | Gateway downstream — local models / cloud APIs / tools / memory / workflows | 9759 | E0309 | composite | false |
| F02728 | Replacement pattern — every tool talks to gateway instead of OpenAI/Anthropic/vLLM directly | 9762 | E0309 | composite | false |
| F02729 | Compatibility surface count — at least 2 (OpenAI + Anthropic) | 9766–9768 | E0310 | composite | false |
| F02730 | OpenAI facade — /v1/chat/completions | 9770 | M00544 | composite | true |
| F02731 | OpenAI facade — /v1/responses | 9771 | M00545 | composite | true |
| F02732 | OpenAI facade — /v1/embeddings | 9772 | M00546 | composite | true |
| F02733 | OpenAI facade — /v1/models | 9773 | M00547 | composite | true |
| F02734 | Anthropic facade — /v1/messages | 9776 | M00548 | composite | true |
| F02735 | Anthropic facade — /v1/models | 9777 | M00549 | composite | true |
| F02736 | Anthropic facade — token counting if needed | 9778 | M00550 | composite | true |
| F02737 | Cline supports OpenAI-compatible custom Base URLs | 9783 | E0310 | composite | true |
| F02738 | OpenCode supports OpenAI-compatible providers + custom provider setups | 9783 | E0310 | composite | true |
| F02739 | vLLM exposes OpenAI-compatible server including chat/completions and related APIs | 9783 | E0310 | composite | true |
| F02740 | Claude Code is more Anthropic-shaped — wants Anthropic-compatible facade | 9785 | E0310 | composite | true |
| F02741 | Anthropic documents proxy/base URL style configuration for Claude Code corporate proxy | 9785 | E0310 | composite | false |
| F02742 | Community usage around ANTHROPIC_BASE_URL/proxy layers exists (fussier) | 9785 | E0310 | composite | false |
| F02743 | Gateway responsibility — NOT a dumb proxy | 9789 | E0311 | composite | false |
| F02744 | Gateway responsibility — control point | 9789 | E0311 | composite | false |
| F02745 | Capability 1 — Compatibility Translation (OpenAI req → internal Frame) | 9793 | M00551 | composite | false |
| F02746 | Capability 1 — Compatibility Translation (Anthropic req → internal Frame) | 9794 | M00551 | composite | false |
| F02747 | Capability 1 — Compatibility Translation (internal result → client-compatible response) | 9795 | M00551 | composite | false |
| F02748 | Capability 2 — Model Routing (requested model may be alias) | 9798 | M00552 | composite | false |
| F02749 | Capability 2 — model alias example — "gpt-5.2" → local oracle profile / cloud OpenAI / fallback | 9799 | M00552 | composite | true |
| F02750 | Capability 2 — model alias example — "claude-sonnet" → local route / Anthropic / policy-denied | 9800 | M00552 | composite | true |
| F02751 | Capability 3 — Profiles (model names encode behavior) | 9803 | M00553 | composite | false |
| F02752 | Profile alias — jean/fast | 9804 | M00553 | composite | true |
| F02753 | Profile alias — jean/careful | 9805 | M00553 | composite | true |
| F02754 | Profile alias — jean/local-only | 9806 | M00553 | composite | true |
| F02755 | Profile alias — jean/oracle | 9807 | M00553 | composite | true |
| F02756 | Profile alias — jean/code | 9808 | M00553 | composite | true |
| F02757 | Profile alias — jean/research | 9809 | M00553 | composite | true |
| F02758 | Profile alias — jean/sandbox | 9810 | M00553 | composite | true |
| F02759 | Capability 4 — Cost Tracking (tokens in/out) | 9813 | M00554 | composite | true |
| F02760 | Capability 4 — Cost Tracking (local GPU time) | 9814 | M00554 | composite | true |
| F02761 | Capability 4 — Cost Tracking (cloud spend) | 9815 | M00554 | composite | true |
| F02762 | Capability 4 — Cost Tracking (cache hits) | 9816 | M00554 | composite | true |
| F02763 | Capability 4 — Cost Tracking (per-client budget) | 9817 | M00554 | composite | true |
| F02764 | Capability 5 — Policy (block cloud for private work) | 9820 | M00555 | composite | false |
| F02765 | Capability 5 — Policy (require approval for paid remote calls) | 9821 | M00555 | composite | false |
| F02766 | Capability 5 — Policy (enforce project-level limits) | 9822 | M00555 | composite | false |
| F02767 | Capability 5 — Policy (redact secrets before remote APIs) | 9823 | M00555 | composite | false |
| F02768 | Capability 6 — Observability (trace every request) | 9826 | M00556 | composite | false |
| F02769 | Capability 6 — Observability (latency / model route / cost / cache / failures) | 9827 | M00556 | composite | false |
| F02770 | Big Trick — Model Aliases As Profiles — existing clients let you choose a "model"; use that as your profile selector | 9831–9832 | E0312 | composite | false |
| F02771 | Model alias example — jean/local-fast → local SLM/scout only | 9835–9836 | E0312 | composite | true |
| F02772 | Model alias example — jean/code-careful → local first / oracle verify / tools allowed by policy | 9838–9839 | E0312 | composite | true |
| F02773 | Model alias example — jean/cloud-openai → OpenAI backend allowed | 9841–9842 | E0312 | composite | true |
| F02774 | Model alias example — jean/cloud-anthropic → Anthropic backend allowed | 9844–9845 | E0312 | composite | true |
| F02775 | Model alias example — jean/hybrid-oracle → local draft + cloud or Blackwell verify | 9847–9848 | E0312 | composite | true |
| F02776 | Model alias example — jean/private → no cloud / no network / no external logging | 9850–9851 | E0312 | composite | true |
| F02777 | "From Cline/OpenCode/etc., it just looks like model selection" | 9854 | E0312 | composite | false |
| F02778 | "Inside, it is a whole route" | 9856 | E0312 | composite | false |
| F02779 | OpenAI-compatible env example — OPENAI_API_KEY=local-or-real-key | 9863 | E0313 | composite | true |
| F02780 | OpenAI-compatible env example — OPENAI_BASE_URL=http://127.0.0.1:8080/v1 | 9864 | E0313 | composite | true |
| F02781 | Python OpenAI SDK example — `client = OpenAI(api_key="local-key", base_url="http://127.0.0.1:8080/v1")` | 9869–9874 | E0313 | composite | true |
| F02782 | Cline/OpenCode base URL — http://127.0.0.1:8080/v1 | 9879 | E0313 | composite | true |
| F02783 | Anthropic-shaped env example — ANTHROPIC_AUTH_TOKEN=local-or-real-key | 9885 | E0313 | composite | true |
| F02784 | Anthropic-shaped env example — ANTHROPIC_BASE_URL=http://127.0.0.1:8081 | 9886 | E0313 | composite | true |
| F02785 | Claude Code adapter caveat — version-sensitive; must be tested against installed client | 9889 | E0313 | composite | false |
| F02786 | Gateway is where you solve cost | 9893 | E0314 | composite | false |
| F02787 | Cost knob — cloud_enabled (bool, default false) | 9896 | E0314 | composite | true |
| F02788 | Cost knob — cloud_requires_approval (bool, default true) | 9897 | E0314 | composite | true |
| F02789 | Cost knob — daily_budget_usd (number, default 5) | 9898 | E0314 | composite | true |
| F02790 | Cost knob — per_request_max_usd (number, default 0.25) | 9899 | E0314 | composite | true |
| F02791 | Cost knob — private_paths_never_cloud (bool, default true) | 9900 | E0314 | composite | true |
| F02792 | Cost knob — log_prompts: local_only | 9901 | E0314 | composite | true |
| F02793 | Profile toggle — local-only | 9907 | E0314 | composite | true |
| F02794 | Profile toggle — local-first | 9908 | E0314 | composite | true |
| F02795 | Profile toggle — ask-before-cloud | 9909 | E0314 | composite | true |
| F02796 | Profile toggle — cloud-allowed | 9910 | E0314 | composite | true |
| F02797 | Profile toggle — cloud-for-final-review | 9911 | E0314 | composite | true |
| F02798 | Per-request record fields — client / project / profile / route / tokens / estimated cost / actual cost / cache hit / decision reason | 9917–9925 | M00560 | composite | false |
| F02799 | Architecture component — Compatibility Gateway | 9933 | E0315 | composite | false |
| F02800 | Compatibility Gateway sub-part — model alias registry | 9936 | M00552 + M00553 | composite | false |
| F02801 | Compatibility Gateway sub-part — provider router | 9937 | M00552 | composite | false |
| F02802 | Compatibility Gateway sub-part — cost ledger | 9938 | M00554 | composite | false |
| F02803 | Compatibility Gateway sub-part — streaming translator | 9940 | M00557 | composite | false |
| F02804 | Compatibility Gateway sub-part — tool/function-call translator | 9941 | M00558 | composite | false |
| F02805 | Composite — Core Rule "External clients should see a normal API. Your station should see typed frames, profiles, policies, and routes." + Closing "Cline thinks it is calling OpenAI-compatible chat completions. Claude Code thinks it is calling Anthropic messages. OpenCode thinks it is calling a provider. But really, they are entering your deterministic intelligence gateway." | 9944–9956 | E0316 + E0317 | composite | false |

## Requirements (R05441–R05610)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R05441 | Operator addendum 9728 — modes toggle on/off / configure-keys-once / cost tracking is needed | 9728 | F02721 | non-negotiable | false | 10 |
| R05442 | Operator addendum 9729 — sovereign-os exposes OpenAI/Anthropic-compatible API to be consumed by Claude Code / Cline / OpenCode | 9729 | F02722 | non-negotiable | false | 10 |
| R05443 | Station must become an API-compatible intelligence gateway | 9748 | E0309 | non-negotiable | false | 10 |
| R05444 | Gateway sits between clients (Claude Code / Cline / OpenCode / custom apps) and downstream (local models / cloud APIs / tools / memory / workflows) | 9751–9760 | E0309 | non-negotiable | false | 10 |
| R05445 | Gateway adds local routing | 9757 | F02726 | non-negotiable | true | 10 |
| R05446 | Gateway adds profiles | 9757 | F02726 | non-negotiable | true | 10 |
| R05447 | Gateway adds policies | 9757 | F02726 | non-negotiable | true | 10 |
| R05448 | Gateway adds telemetry | 9757 | F02726 | non-negotiable | true | 10 |
| R05449 | Gateway adds cost tracking | 9757 | F02726 | non-negotiable | true | 10 |
| R05450 | Replacement — every tool talks to gateway instead of OpenAI / Anthropic / vLLM directly | 9762 | F02728 | non-negotiable | false | 10 |
| R05451 | Expose at least 2 compatibility surfaces (OpenAI + Anthropic) | 9766 | E0310 | non-negotiable | false | 10 |
| R05452 | OpenAI facade — /v1/chat/completions | 9770 | F02730 | non-negotiable | true | 10 |
| R05453 | OpenAI facade — /v1/responses | 9771 | F02731 | non-negotiable | true | 10 |
| R05454 | OpenAI facade — /v1/embeddings | 9772 | F02732 | non-negotiable | true | 10 |
| R05455 | OpenAI facade — /v1/models | 9773 | F02733 | non-negotiable | true | 10 |
| R05456 | Anthropic facade — /v1/messages | 9776 | F02734 | non-negotiable | true | 10 |
| R05457 | Anthropic facade — /v1/models | 9777 | F02735 | non-negotiable | true | 10 |
| R05458 | Anthropic facade — token counting if needed | 9778 | F02736 | non-negotiable | true | 10 |
| R05459 | Cline supports OpenAI-compatible custom Base URLs | 9783 | F02737 | non-negotiable | true | 10 |
| R05460 | OpenCode supports OpenAI-compatible providers + custom provider setups | 9783 | F02738 | non-negotiable | true | 10 |
| R05461 | vLLM already exposes OpenAI-compatible server | 9783 | F02739 | non-negotiable | true | 10 |
| R05462 | Claude Code is Anthropic-shaped — wants Anthropic-compatible facade | 9785 | F02740 | non-negotiable | true | 10 |
| R05463 | Anthropic documents proxy/base URL style configuration for Claude Code corporate proxy | 9785 | F02741 | non-negotiable | false | 10 |
| R05464 | Community usage around ANTHROPIC_BASE_URL/proxy layers exists (fussier) | 9785 | F02742 | non-negotiable | false | 10 |
| R05465 | Gateway is NOT a dumb proxy | 9789 | F02743 | non-negotiable | false | 10 |
| R05466 | Gateway is the control point | 9789 | F02744 | non-negotiable | false | 10 |
| R05467 | Capability 1 — Compatibility Translation: OpenAI request → internal Frame | 9793 | F02745 | non-negotiable | false | 10 |
| R05468 | Capability 1 — Compatibility Translation: Anthropic request → internal Frame | 9794 | F02746 | non-negotiable | false | 10 |
| R05469 | Capability 1 — Compatibility Translation: internal result → client-compatible response | 9795 | F02747 | non-negotiable | false | 10 |
| R05470 | Capability 2 — Model Routing: requested model may be alias | 9798 | F02748 | non-negotiable | false | 10 |
| R05471 | Capability 2 — alias resolution example "gpt-5.2" → local oracle profile / cloud OpenAI / fallback | 9799 | F02749 | non-negotiable | true | 10 |
| R05472 | Capability 2 — alias resolution example "claude-sonnet" → local route / Anthropic / policy-denied | 9800 | F02750 | non-negotiable | true | 10 |
| R05473 | Capability 3 — Profiles: model names encode behavior | 9803 | F02751 | non-negotiable | false | 10 |
| R05474 | Profile alias — jean/fast | 9804 | F02752 | non-negotiable | true | 10 |
| R05475 | Profile alias — jean/careful | 9805 | F02753 | non-negotiable | true | 10 |
| R05476 | Profile alias — jean/local-only | 9806 | F02754 | non-negotiable | true | 10 |
| R05477 | Profile alias — jean/oracle | 9807 | F02755 | non-negotiable | true | 10 |
| R05478 | Profile alias — jean/code | 9808 | F02756 | non-negotiable | true | 10 |
| R05479 | Profile alias — jean/research | 9809 | F02757 | non-negotiable | true | 10 |
| R05480 | Profile alias — jean/sandbox | 9810 | F02758 | non-negotiable | true | 10 |
| R05481 | Capability 4 — Cost Tracking (tokens in/out) | 9813 | F02759 | non-negotiable | true | 10 |
| R05482 | Capability 4 — Cost Tracking (local GPU time) | 9814 | F02760 | non-negotiable | true | 10 |
| R05483 | Capability 4 — Cost Tracking (cloud spend) | 9815 | F02761 | non-negotiable | true | 10 |
| R05484 | Capability 4 — Cost Tracking (cache hits) | 9816 | F02762 | non-negotiable | true | 10 |
| R05485 | Capability 4 — Cost Tracking (per-client budget) | 9817 | F02763 | non-negotiable | true | 10 |
| R05486 | Capability 5 — Policy (block cloud for private work) | 9820 | F02764 | non-negotiable | false | 10 |
| R05487 | Capability 5 — Policy (require approval for paid remote calls) | 9821 | F02765 | non-negotiable | false | 10 |
| R05488 | Capability 5 — Policy (enforce project-level limits) | 9822 | F02766 | non-negotiable | false | 10 |
| R05489 | Capability 5 — Policy (redact secrets before remote APIs) | 9823 | F02767 | non-negotiable | false | 10 |
| R05490 | Capability 6 — Observability (trace every request) | 9826 | F02768 | non-negotiable | false | 10 |
| R05491 | Capability 6 — Observability (latency / model route / cost / cache / failures) | 9827 | F02769 | non-negotiable | false | 10 |
| R05492 | Big Trick — Model Aliases As Profiles | 9831 | E0312 | non-negotiable | false | 10 |
| R05493 | Existing clients let you choose a "model" → use that as your profile selector | 9832 | F02770 | non-negotiable | false | 10 |
| R05494 | Model alias jean/local-fast → local SLM/scout only | 9835–9836 | F02771 | non-negotiable | true | 10 |
| R05495 | Model alias jean/code-careful → local first + oracle verify + tools allowed by policy | 9838–9839 | F02772 | non-negotiable | true | 10 |
| R05496 | Model alias jean/cloud-openai → OpenAI backend allowed | 9841–9842 | F02773 | non-negotiable | true | 10 |
| R05497 | Model alias jean/cloud-anthropic → Anthropic backend allowed | 9844–9845 | F02774 | non-negotiable | true | 10 |
| R05498 | Model alias jean/hybrid-oracle → local draft + cloud or Blackwell verify | 9847–9848 | F02775 | non-negotiable | true | 10 |
| R05499 | Model alias jean/private → no cloud / no network / no external logging | 9850–9851 | F02776 | non-negotiable | true | 10 |
| R05500 | "From Cline/OpenCode/etc., it just looks like model selection" | 9854 | F02777 | non-negotiable | false | 10 |
| R05501 | "Inside, it is a whole route" | 9856 | F02778 | non-negotiable | false | 10 |
| R05502 | OpenAI-compatible env — OPENAI_API_KEY=local-or-real-key | 9863 | F02779 | non-negotiable | true | 10 |
| R05503 | OpenAI-compatible env — OPENAI_BASE_URL=http://127.0.0.1:8080/v1 | 9864 | F02780 | non-negotiable | true | 10 |
| R05504 | Python OpenAI SDK example — client = OpenAI(api_key="local-key", base_url="http://127.0.0.1:8080/v1") | 9869–9874 | F02781 | non-negotiable | true | 10 |
| R05505 | Cline/OpenCode OpenAI-compatible Base URL — http://127.0.0.1:8080/v1 | 9879 | F02782 | non-negotiable | true | 10 |
| R05506 | Anthropic-shaped env — ANTHROPIC_AUTH_TOKEN=local-or-real-key | 9885 | F02783 | non-negotiable | true | 10 |
| R05507 | Anthropic-shaped env — ANTHROPIC_BASE_URL=http://127.0.0.1:8081 | 9886 | F02784 | non-negotiable | true | 10 |
| R05508 | Claude Code adapter is version-sensitive — must be tested against installed client | 9889 | F02785 | non-negotiable | false | 10 |
| R05509 | Cost-and-toggle layer is where cost is solved | 9893 | E0314 | non-negotiable | false | 10 |
| R05510 | Cost knob — cloud_enabled | 9896 | F02787 | non-negotiable | true | 10 |
| R05511 | Cost knob — cloud_requires_approval | 9897 | F02788 | non-negotiable | true | 10 |
| R05512 | Cost knob — daily_budget_usd | 9898 | F02789 | non-negotiable | true | 10 |
| R05513 | Cost knob — per_request_max_usd | 9899 | F02790 | non-negotiable | true | 10 |
| R05514 | Cost knob — private_paths_never_cloud | 9900 | F02791 | non-negotiable | true | 10 |
| R05515 | Cost knob — log_prompts: local_only | 9901 | F02792 | non-negotiable | true | 10 |
| R05516 | Profile toggle — local-only | 9907 | F02793 | non-negotiable | true | 10 |
| R05517 | Profile toggle — local-first | 9908 | F02794 | non-negotiable | true | 10 |
| R05518 | Profile toggle — ask-before-cloud | 9909 | F02795 | non-negotiable | true | 10 |
| R05519 | Profile toggle — cloud-allowed | 9910 | F02796 | non-negotiable | true | 10 |
| R05520 | Profile toggle — cloud-for-final-review | 9911 | F02797 | non-negotiable | true | 10 |
| R05521 | Per-request record — client | 9917 | F02798 | non-negotiable | true | 10 |
| R05522 | Per-request record — project | 9918 | F02798 | non-negotiable | true | 10 |
| R05523 | Per-request record — profile | 9919 | F02798 | non-negotiable | true | 10 |
| R05524 | Per-request record — route | 9920 | F02798 | non-negotiable | true | 10 |
| R05525 | Per-request record — tokens | 9921 | F02798 | non-negotiable | true | 10 |
| R05526 | Per-request record — estimated cost | 9922 | F02798 | non-negotiable | true | 10 |
| R05527 | Per-request record — actual cost | 9923 | F02798 | non-negotiable | true | 10 |
| R05528 | Per-request record — cache hit | 9924 | F02798 | non-negotiable | true | 10 |
| R05529 | Per-request record — decision reason | 9925 | F02798 | non-negotiable | true | 10 |
| R05530 | Architecture component — Compatibility Gateway | 9933 | E0315 | non-negotiable | false | 10 |
| R05531 | Compatibility Gateway sub-part — OpenAI facade | 9934 | M00544 + M00545 + M00546 + M00547 | non-negotiable | true | 10 |
| R05532 | Compatibility Gateway sub-part — Anthropic facade | 9935 | M00548 + M00549 + M00550 | non-negotiable | true | 10 |
| R05533 | Compatibility Gateway sub-part — model alias registry | 9936 | F02800 | non-negotiable | true | 10 |
| R05534 | Compatibility Gateway sub-part — provider router | 9937 | F02801 | non-negotiable | true | 10 |
| R05535 | Compatibility Gateway sub-part — cost ledger | 9938 | F02802 | non-negotiable | true | 10 |
| R05536 | Compatibility Gateway sub-part — policy/redaction layer | 9939 | M00555 | non-negotiable | true | 10 |
| R05537 | Compatibility Gateway sub-part — streaming translator | 9940 | F02803 | non-negotiable | true | 10 |
| R05538 | Compatibility Gateway sub-part — tool/function-call translator | 9941 | F02804 | non-negotiable | true | 10 |
| R05539 | Core Rule — External clients should see a normal API | 9947 | E0316 | non-negotiable | false | 10 |
| R05540 | Core Rule — Your station should see typed frames, profiles, policies, and routes | 9948 | E0316 | non-negotiable | false | 10 |
| R05541 | Gateway plugs into existing environment without rewriting every tool | 9951 | E0316 | non-negotiable | false | 10 |
| R05542 | Closing — "Cline thinks it is calling OpenAI-compatible chat completions" | 9953 | E0317 | non-negotiable | false | 10 |
| R05543 | Closing — "Claude Code thinks it is calling Anthropic messages" | 9954 | E0317 | non-negotiable | false | 10 |
| R05544 | Closing — "OpenCode thinks it is calling a provider" | 9955 | E0317 | non-negotiable | false | 10 |
| R05545 | Closing — "But really, they are entering your deterministic intelligence gateway" | 9956 | E0317 | non-negotiable | false | 10 |
| R05546 | Default bind — OpenAI facade `http://127.0.0.1:8080/v1` | 9864 | M00559 | non-negotiable | true | 10 |
| R05547 | Default bind — Anthropic facade `http://127.0.0.1:8081` | 9886 | M00559 | non-negotiable | true | 10 |
| R05548 | Gateway exposes Cline + OpenCode + Continue + aider-style + any OpenAI SDK app via OpenAI-compatible base_url change | 9733 | E0308 | non-negotiable | false | 10 |
| R05549 | Gateway exposes Claude Code via Anthropic-compatible base_url change | 9733 + 9785 | E0308 | non-negotiable | false | 10 |
| R05550 | "Local-or-real-key" pattern — gateway accepts any key (local-key works; real OpenAI key works too; gateway makes its own decision) | 9863 + 9885 | E0313 | non-negotiable | false | 10 |
| R05551 | Streaming translator handles OpenAI SSE chunks | 9940 | M00557 | non-negotiable | false | 10 |
| R05552 | Streaming translator handles Anthropic event stream | 9940 | M00557 | non-negotiable | false | 10 |
| R05553 | Streaming translator handles internal frame stream | 9940 | M00557 | non-negotiable | false | 10 |
| R05554 | Tool/function-call translator handles OpenAI tool_calls | 9941 | M00558 | non-negotiable | false | 10 |
| R05555 | Tool/function-call translator handles Anthropic tool_use | 9941 | M00558 | non-negotiable | false | 10 |
| R05556 | Tool/function-call translator handles internal ToolIntent | 9941 + cross-ref M032 schemas/ToolIntent | M00558 | non-negotiable | false | 10 |
| R05557 | Cost ledger records every request (every request enters the ledger) | 9914 + 9917–9925 | M00554 + M00560 | non-negotiable | false | 10 |
| R05558 | Cost ledger records — decision reason (operator-readable explanation of route choice) | 9925 | F02798 | non-negotiable | false | 10 |
| R05559 | Policy layer redacts secrets before remote APIs (per Capability 5) | 9823 | F02767 | non-negotiable | false | 10 |
| R05560 | Policy layer redacts secret env vars + private file paths + identity material before any cloud call | 9823 | F02767 | non-negotiable | false | 10 |
| R05561 | Profile alias namespace — `jean/<profile-name>` (operator-scoped) | 9804–9810 | M00553 | non-negotiable | false | 10 |
| R05562 | Profile alias resolution — operator-defined; new profiles via configuration, not code change | 9803 | M00553 | non-negotiable | false | 10 |
| R05563 | Model alias resolution — gateway maps alias → (routing decision + downstream backend) | 9797–9810 | M00552 + M00553 | non-negotiable | false | 10 |
| R05564 | Alias resolution priority — operator-defined alias > literal model name passthrough | 9797–9810 | M00552 + M00553 | non-negotiable | false | 10 |
| R05565 | Frame typed schema — internal request representation; OpenAI/Anthropic facades translate to/from this | 9793–9795 + cross-ref M032 schemas/Frame | M00551 | non-negotiable | false | 10 |
| R05566 | ModelRequest typed schema — gateway-side request to downstream backend (local or cloud) | cross-ref M032 schemas/ModelRequest | M00551 | non-negotiable | false | 10 |
| R05567 | ModelResponse typed schema — gateway-side response from downstream backend | cross-ref M032 schemas/ModelResponse | M00551 | non-negotiable | false | 10 |
| R05568 | VerificationResult typed schema — for high_assurance profile (local + cloud disagreement check) | cross-ref M032 schemas/VerificationResult + M032 high_assurance | M00551 | non-negotiable | false | 10 |
| R05569 | MemoryWrite typed schema — when gateway commits memory from a request (per Local AVX-512 runtime owns commit invariant) | cross-ref M032 schemas/MemoryWrite + M032 R05322 | M00551 | non-negotiable | false | 10 |
| R05570 | Compatibility Gateway integrates with M032 Cloud Expert Plane — gateway IS the bidirectional surface; cloud-expert "consume" direction + cloud-API-compatible "provide" direction share the gateway | 9728–9956 + cross-ref M032 R05420–R05425 | E0309 | non-negotiable | false | 10 |
| R05571 | Compatibility Gateway integrates with M025 cognitive compiler — gateway request triggers compile DAG when needed | cross-ref M025 | E0311 | non-negotiable | false | 10 |
| R05572 | Compatibility Gateway integrates with M026 SLM swarm + RLM engine — local-only profile routes to SLM/RLM | 9806 + cross-ref M026 | F02754 + F02776 | non-negotiable | false | 10 |
| R05573 | Compatibility Gateway integrates with M027 Value Plane — reward formula scores route on cost + latency + privacy | 9636–9644 (M032) + cross-ref M027 | E0311 | non-negotiable | false | 10 |
| R05574 | Compatibility Gateway integrates with M028 Memory OS — cache hits feed Memory OS KV cache | 9816 + cross-ref M028 | F02762 | non-negotiable | false | 10 |
| R05575 | Compatibility Gateway integrates with M029 Computer-Use Plane — computer-use tool-call surface flows through gateway as a tool/function-call translation | 9941 + cross-ref M029 | M00558 | non-negotiable | false | 10 |
| R05576 | Compatibility Gateway integrates with M030 World Model Plane — every gateway request is an Action with predicted-transition + success-detector + risk-bits | cross-ref M030 R04971–R04972 | M00551 | non-negotiable | false | 10 |
| R05577 | Compatibility Gateway integrates with M031 Symbolic Planning Plane — policy layer (Capability 5) is the symbolic veto channel | 9819–9823 + cross-ref M031 R05225–R05227 | M00555 | non-negotiable | false | 10 |
| R05578 | Project boundary — Compatibility Gateway is sovereign-os runtime; selfdef-collector-eventstream may re-ingest gateway request/response metadata (NOT prompt content) for incident correlation | architecture | E0309 | non-negotiable | false | 10 |
| R05579 | Project boundary — selfdef MS006 agent-guard policy may rate-limit gateway calls + enforce per-route cost limits via Layer-B metrics | MS006 + 9920–9923 | M00554 | non-negotiable | false | 10 |
| R05580 | Project boundary — selfdef MS007 typed-mirror crates may carry gateway-facade contracts (model alias registry / cost-ledger schema / profile manifest) for cross-repo binding | MS007 + SDD-038 | E0315 | non-negotiable | false | 10 |
| R05581 | Project boundary — Compatibility Gateway secrets (OPENAI_API_KEY / ANTHROPIC_API_KEY upstream) MUST be handled by OS secret store; NEVER in client-side OPENAI_API_KEY env var (client passes local-key) | 9699–9706 (M032) + 9863 (M033) | E0313 | non-negotiable | false | 10 |
| R05582 | Compatibility Gateway is the 13th plane (extending M027 8-plane stack + M028 Memory OS + M029 Computer-Use Plane + M030 World Model Plane + M031 Symbolic Planning Plane + M032 Cloud Expert Plane) | cross-ref M027 R04590 + M028 + M029 + M030 + M031 + M032 | E0315 | non-negotiable | false | 10 |
| R05583 | Compatibility Gateway respects the Local-Runtime-Commits invariant (M032 R05330) — gateway never lets a remote model COMMIT (memory / artifact); commit always flows through local runtime | cross-ref M032 R05330 + 9947–9948 | E0316 | non-negotiable | false | 10 |
| R05584 | Compatibility Gateway respects the privacy invariant — jean/private and local-only profile route NEVER hit network | 9851 + 9907 | F02776 + F02793 | non-negotiable | false | 10 |
| R05585 | Compatibility Gateway respects the cost invariant — operator-set daily_budget_usd is enforced; over-budget calls fail-closed | 9898 + 9893 | F02789 | non-negotiable | false | 10 |
| R05586 | Compatibility Gateway respects the policy invariant — private_paths_never_cloud=true means project-detected private paths never trigger cloud calls regardless of profile | 9900 | F02791 | non-negotiable | false | 10 |
| R05587 | Compatibility Gateway respects the redaction invariant — secrets stripped from prompt + tool args BEFORE leaving the gateway for any remote API | 9823 | F02767 | non-negotiable | false | 10 |
| R05588 | Compatibility Gateway respects the cache invariant — cache hits do NOT trigger cloud calls; cost is local-only-time | 9924 + 9816 | F02762 + F02798 | non-negotiable | false | 10 |
| R05589 | Compatibility Gateway respects the audit invariant — every request records decision reason (Capability 6 observability) for operator post-hoc audit | 9925 + 9826 | F02769 + F02798 | non-negotiable | false | 10 |
| R05590 | Compatibility Gateway respects the cost-ledger invariant — actual cost is recorded alongside estimated cost so operator sees variance | 9922–9923 | F02798 | non-negotiable | false | 10 |
| R05591 | OpenAI facade — /v1/chat/completions request shape matches OpenAI public API (messages array + tools array + tool_choice + stream flag) | 9770 | M00544 | non-negotiable | false | 10 |
| R05592 | OpenAI facade — /v1/responses request shape matches OpenAI Responses API (input array + tools + previous_response_id) | 9771 | M00545 | non-negotiable | false | 10 |
| R05593 | OpenAI facade — /v1/embeddings request shape matches OpenAI public API (input + model + dimensions) | 9772 | M00546 | non-negotiable | false | 10 |
| R05594 | OpenAI facade — /v1/models returns gateway's model alias registry + downstream models | 9773 | M00547 | non-negotiable | false | 10 |
| R05595 | Anthropic facade — /v1/messages request shape matches Anthropic public API (model + max_tokens + messages array + tools + stream) | 9776 | M00548 | non-negotiable | false | 10 |
| R05596 | Anthropic facade — /v1/models returns gateway's model alias registry + downstream Anthropic models | 9777 | M00549 | non-negotiable | false | 10 |
| R05597 | Anthropic facade — token counting endpoint (e.g. /v1/messages/count_tokens) if needed | 9778 | M00550 | non-negotiable | true | 10 |
| R05598 | Gateway streams responses — OpenAI SSE event-stream format with `data:` prefix and `[DONE]` terminator | 9940 | M00557 | non-negotiable | false | 10 |
| R05599 | Gateway streams responses — Anthropic event-stream with content_block_start / content_block_delta / content_block_stop / message_stop events | 9940 | M00557 | non-negotiable | false | 10 |
| R05600 | Gateway tool/function-call translator — OpenAI tool_calls array translated to internal ToolIntent list | 9941 + cross-ref M032 schemas/ToolIntent | M00558 | non-negotiable | false | 10 |
| R05601 | Gateway tool/function-call translator — Anthropic tool_use blocks translated to internal ToolIntent list | 9941 | M00558 | non-negotiable | false | 10 |
| R05602 | Gateway tool/function-call translator — internal ToolIntent translated back to OpenAI tool_calls OR Anthropic tool_use per client | 9941 | M00558 | non-negotiable | false | 10 |
| R05603 | Gateway accepts `local-or-real-key` — operator may use a placeholder local-key or a real OpenAI/Anthropic key; gateway enforces its own policy regardless | 9863 + 9885 | E0313 | non-negotiable | false | 10 |
| R05604 | Gateway models endpoint /v1/models lists profile aliases (jean/*) alongside downstream model names | 9803–9810 + 9773 + 9777 | M00547 + M00549 | non-negotiable | false | 10 |
| R05605 | Gateway model alias jean/private (and any local-only profile) refuses to call any cloud endpoint regardless of operator config | 9851 | F02776 | non-negotiable | false | 10 |
| R05606 | Gateway model alias jean/oracle requires explicit operator approval per call when cloud_requires_approval=true | 9807 + 9897 | F02755 + F02788 | non-negotiable | false | 10 |
| R05607 | Gateway per-client budget enforced at request entry; over-budget returns 429 (or equivalent error) with cost-ledger reason in body | 9817 + 9898 | F02763 + F02789 | non-negotiable | false | 10 |
| R05608 | Gateway sandbox profile (jean/sandbox) routes through M029 Computer-Use Plane sandbox tier; never touches host | 9810 + cross-ref M029 R04829 | F02758 | non-negotiable | false | 10 |
| R05609 | Gateway hybrid profile (jean/hybrid-oracle) runs local draft + cloud-or-Blackwell verify; final commit is local (M032 R05330 invariant) | 9847–9848 + cross-ref M032 R05330 | F02775 | non-negotiable | false | 10 |
| R05610 | Composite — Compatibility Gateway is the bidirectional API-compatible intelligence surface; OpenAI + Anthropic facades; 8 sub-parts; 6 capabilities (compatibility translation / model routing / profiles / cost tracking / policy / observability); model aliases as profiles trick (jean/*); 6 cost knobs + 5 profile toggles + 9-field per-request record; Core Rule "External clients see a normal API. Your station sees typed frames, profiles, policies, and routes."; integrates with M025 cognitive compiler + M026 SLM swarm + M027 Value Plane + M028 Memory OS + M029 Computer-Use Plane + M030 World Model Plane + M031 Symbolic Planning Plane + M032 Cloud Expert Plane | 9728–9956 | E0316 + E0317 | non-negotiable | false | 10 |

## Cross-references

- Adjacent dump-range milestones: M032 Cloud Expert plane (9486–9728) / M034 Anthropic-first gateway + MCP + Claude Code integration (9958–10109)
- Plane integration: M025 cognitive compiler / M026 SLM swarm + RLM engine / M027 Value Plane / M028 Memory OS / M029 Computer-Use Plane / M030 World Model Plane / M031 Symbolic Planning Plane / M032 Cloud Expert Plane / M033 Compatibility Gateway (this)
- Selfdef boundary: cloud-expert metadata may flow into selfdef-collector-eventstream for incident correlation (NOT prompt content); agent-guard (MS006) may rate-limit + per-route cost-track; MS007 typed mirrors may carry model-alias-registry / cost-ledger-schema / profile-manifest contracts
- Bidirectional pattern: M033 IS the surface that fulfills M032 R05420–R05425 (sovereign-os replaces OpenAI/Anthropic env vars for Claude Code / OpenCode / Cline)
