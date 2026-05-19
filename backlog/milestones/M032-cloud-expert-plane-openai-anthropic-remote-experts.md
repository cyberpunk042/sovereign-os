# M032 — Cloud Expert plane — OpenAI + Anthropic as remote experts

> Parent: `backlog/milestones/INDEX.md` row M032 (dump 9486–9728).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 9486–9728 + operator addendum 9728–9729.
> All entries below are extracted from the dump line range. No invention.

## Epics (E0298–E0307)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0298 | Cloud APIs as boundary layer / optional expert backends — NOT the core of the local station; "Local station = sovereign deterministic runtime; OpenAI/Anthropic = optional remote experts"; do not make cloud APIs own workflow / memory / tools / commit layer; plug into router like any other model backend | 9486–9514 |
| E0299 | OpenAI research signal — Responses API (recommended unified primitive for agent-like apps: tools / multimodal input / conversation state / function calling / web+file search / computer use / code interpreter / remote MCP) + Structured Outputs with JSON Schema adherence (fits typed-frame / typed-tool-call) + model families GPT-5.2 / GPT-5 mini / GPT-5 nano (GPT-5.2 for coding+agentic) + Agents SDK (tools / handoffs / streaming / tracing) | 9517–9523 |
| E0300 | Anthropic research signal — extended thinking with tool use for harder coding/analysis + prompt caching with short and longer cache durations for stable prefixes/system/tool schemas + structured output support in Agent SDK / developer platform + models-list API (runtime discovers Claude models dynamically; don't hardcode) | 9524–9530 |
| E0301 | Cloud Expert Plane — OpenAI / Anthropic / maybe Gemini, Mistral, Groq, Cerebras later; Local AVX-512 runtime owns state+policy+memory+replay+tools+commit; Cloud APIs provide expert generation+verification+coding+reasoning+vision+research; invariant "Remote models propose. Local runtime commits." | 9532–9558 |
| E0302 | Use Cases For Cloud Experts — OpenAI (6: hard coding review / agentic tool reasoning / structured extraction / computer-use comparison / remote web+file-search workflows / fallback oracle when local model uncertain); Anthropic (6: long-form code reasoning / careful analysis / agentic coding review / extended thinking on hard architecture / alternative critique voice / prompt-cached large context workflows); Local models (8: private work / fast loops / drafting / memory extraction / SLM-RLM recursion / sandboxed tool plans / offline operation / high-volume cheap inference) | 9559–9594 |
| E0303 | Model Router YAML schema — every model local-or-cloud represented same way (id / provider / role / strengths / locality / privacy / cost / latency / supports); 2 worked examples (openai:gpt-5.2 oracle with structured_outputs+tools+vision+reasoning_effort; anthropic:claude-sonnet critic with tool_use+extended_thinking+prompt_caching); router chooses based on 8 axes (privacy / cost / latency / risk / task type / local model confidence / cloud availability / user profile) | 9596–9644 |
| E0304 | Cloud-Expert Profiles — 6 profiles (sovereign local-only / hybrid local-first cloud-if-uncertain / oracle cloud-allowed-for-final-review / private_code no-cloud-unless-explicitly-approved / research cloud-allowed-for-web-search-synthesis / high_assurance local + OpenAI + Anthropic disagreement check) | 9646–9666 |
| E0305 | Environment setup direction — 3 module trees (providers/ with 6 adapters: openai_adapter / anthropic_adapter / local_vllm_adapter / sglang_adapter / trtllm_adapter / llama_cpp_adapter; runtime/ with 7 modules: router / policy_engine / memory_os / workflow_dag / tool_gate / replay_log / evals; schemas/ with 6 types: Frame / ToolIntent / ModelRequest / ModelResponse / VerificationResult / MemoryWrite) | 9668–9697 |
| E0306 | Secrets discipline — `OPENAI_API_KEY` + `ANTHROPIC_API_KEY` handled by environment OR OS secret store; "Never in prompts, logs, replay payloads, or client-side code" | 9699–9706 |
| E0307 | The Big Rule — "Cloud APIs are not 'another level' separate from the system. They are experts behind capability gates"; 5-line station-says capability matrix (private→local only / hard→OpenAI oracle / critique→Anthropic / speed→local SLM / proof→tools+tests+symbolic verifier); first serious step when sharing existing environment = map current OS / GPU stack / model servers / secrets / tools / repos / automation / sandboxes / deterministic-runtime location into this architecture; OPERATOR ADDENDUM — "as long as those are modes you can easily toggle on and off… leads to cost and need for tracking"; SECOND OPERATOR ADDENDUM — "what WE expose" — sovereign-os replaces env-var-API for Claude Code / OpenCode / Cline / OpenAI-based systems (sovereign-os IS the AI provider, not just consumer) | 9708–9730 |

## Modules (M00527–M00543)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00527 | Local AVX-512 runtime owns — state / policy / memory / replay / tools / commit | 9544–9547 | E0301 |
| M00528 | Cloud APIs provide — expert generation / verification / coding / reasoning / vision / research | 9549–9550 | E0301 |
| M00529 | Invariant — "Remote models propose. Local runtime commits." | 9553–9557 | E0301 |
| M00530 | OpenAI Responses API adapter (recommended unified primitive) | 9519 | E0299 |
| M00531 | OpenAI Structured Outputs (JSON Schema adherence) | 9520 | E0299 |
| M00532 | OpenAI model family — GPT-5.2 / GPT-5 mini / GPT-5 nano (GPT-5.2 for coding+agentic) | 9521 | E0299 |
| M00533 | OpenAI Agents SDK (tools / handoffs / streaming / tracing) | 9522 | E0299 |
| M00534 | Anthropic extended thinking with tool use | 9526 | E0300 |
| M00535 | Anthropic prompt caching (short + longer cache durations for stable prefixes / system / tool schemas) | 9527 | E0300 |
| M00536 | Anthropic structured output support in Agent SDK | 9528 | E0300 |
| M00537 | Anthropic models-list API — runtime discovers Claude models DYNAMICALLY (NOT hardcoded) | 9529 | E0300 |
| M00538 | Model Router YAML — 9-field schema (id / provider / role / strengths / locality / privacy / cost / latency / supports) | 9600–9615 | E0303 |
| M00539 | Router selection axes — 8 axes (privacy / cost / latency / risk / task type / local model confidence / cloud availability / user profile) | 9636–9644 | E0303 |
| M00540 | providers/ tree — 6 adapter modules (openai_adapter / anthropic_adapter / local_vllm_adapter / sglang_adapter / trtllm_adapter / llama_cpp_adapter) | 9673–9679 | E0305 |
| M00541 | runtime/ tree — 7 modules (router / policy_engine / memory_os / workflow_dag / tool_gate / replay_log / evals) | 9681–9689 | E0305 |
| M00542 | schemas/ tree — 6 typed schemas (Frame / ToolIntent / ModelRequest / ModelResponse / VerificationResult / MemoryWrite) | 9690–9697 | E0305 |
| M00543 | Bidirectional cloud-expert role — sovereign-os IS the AI provider replacing OpenAI/Anthropic env vars for Claude Code / OpenCode / Cline (per operator addendum 9728–9729) | 9728–9729 | E0307 |

## Features (F02636–F02720)

| F ID | Phrase | Dump line | Parent | Category | Opt-in |
|---|---|---|---|---|---|
| F02636 | OpenAI + Anthropic support belongs in the architecture | 9504 | E0298 | composite | false |
| F02637 | NOT as "the brain" | 9504 | E0298 | composite | false |
| F02638 | As external expert planes | 9504 | E0298 | composite | false |
| F02639 | Local station = sovereign deterministic runtime | 9509 | E0301 | composite | false |
| F02640 | OpenAI/Anthropic = optional remote experts | 9510 | E0301 | composite | false |
| F02641 | Do not make cloud APIs own the workflow | 9513 | E0298 | composite | false |
| F02642 | Do not make cloud APIs own memory | 9513 | E0298 | composite | false |
| F02643 | Do not make cloud APIs own tools | 9513 | E0298 | composite | false |
| F02644 | Do not make cloud APIs own commit layer | 9513 | E0298 | composite | false |
| F02645 | Cloud APIs should plug into your router like any other model backend | 9513 | E0298 | composite | false |
| F02646 | OpenAI direction aligned with our architecture | 9517 | E0299 | composite | false |
| F02647 | OpenAI Responses API — recommended unified primitive for agent-like apps | 9519 | M00530 | composite | true |
| F02648 | Responses API supports — tools | 9519 | M00530 | composite | true |
| F02649 | Responses API supports — multimodal input | 9519 | M00530 | composite | true |
| F02650 | Responses API supports — conversation state | 9519 | M00530 | composite | true |
| F02651 | Responses API supports — function calling | 9519 | M00530 | composite | true |
| F02652 | Responses API supports — web search | 9519 | M00530 | composite | true |
| F02653 | Responses API supports — file search | 9519 | M00530 | composite | true |
| F02654 | Responses API supports — computer use | 9519 | M00530 | composite | true |
| F02655 | Responses API supports — code interpreter | 9519 | M00530 | composite | true |
| F02656 | Responses API supports — remote MCP | 9519 | M00530 | composite | true |
| F02657 | OpenAI Structured Outputs — JSON Schema adherence | 9520 | M00531 | composite | true |
| F02658 | Structured Outputs fits typed-frame architecture | 9520 | M00531 | composite | false |
| F02659 | Structured Outputs fits typed-tool-call architecture | 9520 | M00531 | composite | false |
| F02660 | OpenAI model GPT-5.2 — coding + agentic tasks | 9521 | M00532 | composite | true |
| F02661 | OpenAI model GPT-5 mini | 9521 | M00532 | composite | true |
| F02662 | OpenAI model GPT-5 nano | 9521 | M00532 | composite | true |
| F02663 | OpenAI Agents SDK — tools | 9522 | M00533 | composite | true |
| F02664 | OpenAI Agents SDK — handoffs | 9522 | M00533 | composite | true |
| F02665 | OpenAI Agents SDK — streaming | 9522 | M00533 | composite | true |
| F02666 | OpenAI Agents SDK — tracing | 9522 | M00533 | composite | true |
| F02667 | Anthropic Claude API — extended thinking with tool use | 9526 | M00534 | composite | true |
| F02668 | Anthropic prompt caching — short cache duration | 9527 | M00535 | composite | true |
| F02669 | Anthropic prompt caching — longer cache duration | 9527 | M00535 | composite | true |
| F02670 | Anthropic prompt caching useful for stable prefixes | 9527 | M00535 | composite | false |
| F02671 | Anthropic prompt caching useful for stable system prompts | 9527 | M00535 | composite | false |
| F02672 | Anthropic prompt caching useful for stable tool schemas | 9527 | M00535 | composite | false |
| F02673 | Anthropic structured output in Agent SDK / developer platform | 9528 | M00536 | composite | true |
| F02674 | Anthropic models-list API — runtime discovers Claude models dynamically | 9529 | M00537 | composite | true |
| F02675 | Anthropic models-list — DO NOT hardcode model names | 9529 | M00537 | composite | false |
| F02676 | New plane — Cloud Expert Plane | 9536 | E0301 | composite | false |
| F02677 | Cloud Expert Plane includes OpenAI | 9537 | E0301 | composite | true |
| F02678 | Cloud Expert Plane includes Anthropic | 9538 | E0301 | composite | true |
| F02679 | Cloud Expert Plane maybe later — Gemini | 9539 | E0301 | composite | true |
| F02680 | Cloud Expert Plane maybe later — Mistral | 9539 | E0301 | composite | true |
| F02681 | Cloud Expert Plane maybe later — Groq | 9539 | E0301 | composite | true |
| F02682 | Cloud Expert Plane maybe later — Cerebras | 9539 | E0301 | composite | true |
| F02683 | Local AVX-512 runtime owns — state | 9544–9547 | M00527 | composite | false |
| F02684 | Local AVX-512 runtime owns — policy | 9544–9547 | M00527 | composite | false |
| F02685 | Local AVX-512 runtime owns — memory | 9544–9547 | M00527 | composite | false |
| F02686 | Local AVX-512 runtime owns — replay | 9544–9547 | M00527 | composite | false |
| F02687 | Local AVX-512 runtime owns — tools | 9544–9547 | M00527 | composite | false |
| F02688 | Local AVX-512 runtime owns — commit | 9544–9547 | M00527 | composite | false |
| F02689 | Cloud APIs provide — expert generation | 9549–9550 | M00528 | composite | false |
| F02690 | Cloud APIs provide — verification / coding / reasoning / vision / research | 9550 | M00528 | composite | false |
| F02691 | Invariant — Remote models propose. Local runtime commits. | 9555–9557 | M00529 | composite | false |
| F02692 | OpenAI use case — hard coding review | 9564 | E0302 | composite | true |
| F02693 | OpenAI use case — agentic tool reasoning | 9565 | E0302 | composite | true |
| F02694 | OpenAI use case — structured extraction | 9566 | E0302 | composite | true |
| F02695 | OpenAI use case — computer-use comparison | 9567 | E0302 | composite | true |
| F02696 | OpenAI use case — remote web/file-search workflows | 9568 | E0302 | composite | true |
| F02697 | OpenAI use case — fallback oracle when local model uncertain | 9569 | E0302 | composite | true |
| F02698 | Anthropic use case — long-form code reasoning | 9575 | E0302 | composite | true |
| F02699 | Anthropic use case — careful analysis | 9576 | E0302 | composite | true |
| F02700 | Anthropic use case — agentic coding review | 9577 | E0302 | composite | true |
| F02701 | Anthropic use case — extended thinking on hard architecture | 9578 | E0302 | composite | true |
| F02702 | Anthropic use case — alternative critique voice | 9579 | E0302 | composite | true |
| F02703 | Anthropic use case — prompt-cached large context workflows | 9580 | E0302 | composite | true |
| F02704 | Local model use case — private work / fast loops / drafting / memory extraction / SLM-RLM recursion / sandboxed tool plans / offline operation / high-volume cheap inference | 9586–9593 | E0302 | composite | false |
| F02705 | Model Router YAML — every model represented the same way | 9598 | M00538 | composite | false |
| F02706 | Model Router YAML field — id (e.g. openai:gpt-5.2) | 9602 | M00538 | composite | true |
| F02707 | Model Router YAML field — provider | 9603 | M00538 | composite | true |
| F02708 | Model Router YAML field — role (oracle / critic / …) | 9604 | M00538 | composite | true |
| F02709 | Model Router YAML field — strengths (list) | 9605 | M00538 | composite | true |
| F02710 | Model Router YAML field — locality (remote / local) | 9606 | M00538 | composite | true |
| F02711 | Model Router YAML field — privacy (external / internal) | 9607 | M00538 | composite | true |
| F02712 | Model Router YAML field — cost (high / medium / low) | 9608 | M00538 | composite | true |
| F02713 | Model Router YAML field — latency (high / medium / low) | 9609 | M00538 | composite | true |
| F02714 | Model Router YAML field — supports (list of capabilities) | 9610–9615 | M00538 | composite | true |
| F02715 | Router selection axis catalog — privacy / cost / latency / risk / task type / local model confidence / cloud availability / user profile | 9636–9644 | M00539 | composite | false |
| F02716 | Profiles — sovereign (local only) / hybrid (local first cloud if uncertain) / oracle (cloud allowed for final review) / private_code (no cloud unless explicitly approved) / research (cloud allowed for web/search/synthesis) / high_assurance (local + OpenAI + Anthropic disagreement check) | 9649–9666 | E0304 | composite | true |
| F02717 | Environment module — providers/ with 6 adapters (openai / anthropic / local_vllm / sglang / trtllm / llama_cpp) | 9673–9679 | M00540 | composite | true |
| F02718 | Environment module — runtime/ with 7 modules (router / policy_engine / memory_os / workflow_dag / tool_gate / replay_log / evals) | 9681–9689 | M00541 | composite | true |
| F02719 | Environment module — schemas/ with 6 types (Frame / ToolIntent / ModelRequest / ModelResponse / VerificationResult / MemoryWrite) | 9690–9697 | M00542 | composite | true |
| F02720 | Composite — Big Rule "Cloud APIs are not 'another level' separate from the system. They are experts behind capability gates"; 5-line station-says (private→local only / hard→OpenAI oracle / critique→Anthropic / speed→local SLM / proof→tools+tests+symbolic verifier); OPERATOR ADDENDUM 9728–9729 — "modes you can easily toggle on and off"; OPERATOR ADDENDUM 9729 — "what WE expose" — sovereign-os AS the AI provider (replaces OPENAI_API_KEY / ANTHROPIC_API_KEY env var for Claude Code / OpenCode / Cline / OpenAI-consuming systems) — bidirectional pattern (sovereign-os is BOTH consumer of cloud experts AND provider for cloud-API-shaped clients) | 9708–9729 | E0307 + M00543 | composite | false |

## Requirements (R05271–R05440)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R05271 | OpenAI + Anthropic support belongs in the architecture as boundary layer | 9486 + 9490 | E0298 | non-negotiable | false | 10 |
| R05272 | Cloud APIs should be OPTIONAL expert backends, NOT core of local station | 9490 | E0298 | non-negotiable | false | 10 |
| R05273 | Local station = sovereign deterministic runtime | 9509 | F02639 | non-negotiable | false | 10 |
| R05274 | OpenAI/Anthropic = optional remote experts | 9510 | F02640 | non-negotiable | false | 10 |
| R05275 | Cloud APIs do NOT own the workflow | 9513 | F02641 | non-negotiable | false | 10 |
| R05276 | Cloud APIs do NOT own memory | 9513 | F02642 | non-negotiable | false | 10 |
| R05277 | Cloud APIs do NOT own tools | 9513 | F02643 | non-negotiable | false | 10 |
| R05278 | Cloud APIs do NOT own commit layer | 9513 | F02644 | non-negotiable | false | 10 |
| R05279 | Cloud APIs plug into router like any other model backend | 9513 | F02645 | non-negotiable | false | 10 |
| R05280 | OpenAI direction is aligned with our architecture | 9517 | E0299 | non-negotiable | false | 10 |
| R05281 | OpenAI Responses API is recommended unified primitive for agent-like apps | 9519 | F02647 | non-negotiable | true | 10 |
| R05282 | Responses API supports tools | 9519 | F02648 | non-negotiable | true | 10 |
| R05283 | Responses API supports multimodal input | 9519 | F02649 | non-negotiable | true | 10 |
| R05284 | Responses API supports conversation state | 9519 | F02650 | non-negotiable | true | 10 |
| R05285 | Responses API supports function calling | 9519 | F02651 | non-negotiable | true | 10 |
| R05286 | Responses API supports web search | 9519 | F02652 | non-negotiable | true | 10 |
| R05287 | Responses API supports file search | 9519 | F02653 | non-negotiable | true | 10 |
| R05288 | Responses API supports computer use | 9519 | F02654 | non-negotiable | true | 10 |
| R05289 | Responses API supports code interpreter | 9519 | F02655 | non-negotiable | true | 10 |
| R05290 | Responses API supports remote MCP | 9519 | F02656 | non-negotiable | true | 10 |
| R05291 | OpenAI Structured Outputs with JSON Schema adherence | 9520 | F02657 | non-negotiable | true | 10 |
| R05292 | Structured Outputs fits typed-frame architecture | 9520 | F02658 | non-negotiable | false | 10 |
| R05293 | Structured Outputs fits typed-tool-call architecture | 9520 | F02659 | non-negotiable | false | 10 |
| R05294 | OpenAI model — GPT-5.2 (positioned for coding + agentic tasks) | 9521 | F02660 | non-negotiable | true | 10 |
| R05295 | OpenAI model — GPT-5 mini | 9521 | F02661 | non-negotiable | true | 10 |
| R05296 | OpenAI model — GPT-5 nano | 9521 | F02662 | non-negotiable | true | 10 |
| R05297 | OpenAI Agents SDK supports tools | 9522 | F02663 | non-negotiable | true | 10 |
| R05298 | OpenAI Agents SDK supports handoffs | 9522 | F02664 | non-negotiable | true | 10 |
| R05299 | OpenAI Agents SDK supports streaming | 9522 | F02665 | non-negotiable | true | 10 |
| R05300 | OpenAI Agents SDK supports tracing | 9522 | F02666 | non-negotiable | true | 10 |
| R05301 | Anthropic Claude API supports extended thinking with tool use | 9526 | F02667 | non-negotiable | true | 10 |
| R05302 | Anthropic prompt caching — short cache duration | 9527 | F02668 | non-negotiable | true | 10 |
| R05303 | Anthropic prompt caching — longer cache duration | 9527 | F02669 | non-negotiable | true | 10 |
| R05304 | Anthropic prompt caching useful for stable prefixes | 9527 | F02670 | non-negotiable | false | 10 |
| R05305 | Anthropic prompt caching useful for stable system prompts | 9527 | F02671 | non-negotiable | false | 10 |
| R05306 | Anthropic prompt caching useful for stable tool schemas | 9527 | F02672 | non-negotiable | false | 10 |
| R05307 | Anthropic structured output supported in Agent SDK + developer platform | 9528 | F02673 | non-negotiable | true | 10 |
| R05308 | Anthropic models-list API discovers Claude models DYNAMICALLY | 9529 | F02674 | non-negotiable | true | 10 |
| R05309 | Runtime MUST NOT hardcode Anthropic model names | 9529 | F02675 | non-negotiable | false | 10 |
| R05310 | Add new plane — Cloud Expert Plane | 9534–9536 | E0301 | non-negotiable | false | 10 |
| R05311 | Cloud Expert Plane MUST include OpenAI | 9537 | F02677 | non-negotiable | true | 10 |
| R05312 | Cloud Expert Plane MUST include Anthropic | 9538 | F02678 | non-negotiable | true | 10 |
| R05313 | Cloud Expert Plane MAY later include Gemini | 9539 | F02679 | non-negotiable | true | 10 |
| R05314 | Cloud Expert Plane MAY later include Mistral | 9539 | F02680 | non-negotiable | true | 10 |
| R05315 | Cloud Expert Plane MAY later include Groq | 9539 | F02681 | non-negotiable | true | 10 |
| R05316 | Cloud Expert Plane MAY later include Cerebras | 9539 | F02682 | non-negotiable | true | 10 |
| R05317 | Local AVX-512 runtime owns state | 9544–9547 | F02683 | non-negotiable | false | 10 |
| R05318 | Local AVX-512 runtime owns policy | 9544–9547 | F02684 | non-negotiable | false | 10 |
| R05319 | Local AVX-512 runtime owns memory | 9544–9547 | F02685 | non-negotiable | false | 10 |
| R05320 | Local AVX-512 runtime owns replay | 9544–9547 | F02686 | non-negotiable | false | 10 |
| R05321 | Local AVX-512 runtime owns tools | 9544–9547 | F02687 | non-negotiable | false | 10 |
| R05322 | Local AVX-512 runtime owns commit | 9544–9547 | F02688 | non-negotiable | false | 10 |
| R05323 | Cloud APIs provide expert generation | 9549–9550 | F02689 | non-negotiable | false | 10 |
| R05324 | Cloud APIs provide verification | 9550 | F02690 | non-negotiable | false | 10 |
| R05325 | Cloud APIs provide coding | 9550 | F02690 | non-negotiable | false | 10 |
| R05326 | Cloud APIs provide reasoning | 9550 | F02690 | non-negotiable | false | 10 |
| R05327 | Cloud APIs provide vision | 9550 | F02690 | non-negotiable | false | 10 |
| R05328 | Cloud APIs provide research | 9550 | F02690 | non-negotiable | false | 10 |
| R05329 | Invariant — Remote models propose | 9555 | F02691 | non-negotiable | false | 10 |
| R05330 | Invariant — Local runtime commits | 9557 | F02691 | non-negotiable | false | 10 |
| R05331 | OpenAI use case — hard coding review | 9564 | F02692 | non-negotiable | true | 10 |
| R05332 | OpenAI use case — agentic tool reasoning | 9565 | F02693 | non-negotiable | true | 10 |
| R05333 | OpenAI use case — structured extraction | 9566 | F02694 | non-negotiable | true | 10 |
| R05334 | OpenAI use case — computer-use comparison | 9567 | F02695 | non-negotiable | true | 10 |
| R05335 | OpenAI use case — remote web/file-search workflows | 9568 | F02696 | non-negotiable | true | 10 |
| R05336 | OpenAI use case — fallback oracle when local model uncertain | 9569 | F02697 | non-negotiable | true | 10 |
| R05337 | Anthropic use case — long-form code reasoning | 9575 | F02698 | non-negotiable | true | 10 |
| R05338 | Anthropic use case — careful analysis | 9576 | F02699 | non-negotiable | true | 10 |
| R05339 | Anthropic use case — agentic coding review | 9577 | F02700 | non-negotiable | true | 10 |
| R05340 | Anthropic use case — extended thinking on hard architecture | 9578 | F02701 | non-negotiable | true | 10 |
| R05341 | Anthropic use case — alternative critique voice | 9579 | F02702 | non-negotiable | true | 10 |
| R05342 | Anthropic use case — prompt-cached large context workflows | 9580 | F02703 | non-negotiable | true | 10 |
| R05343 | Local model use case — private work | 9586 | F02704 | non-negotiable | true | 10 |
| R05344 | Local model use case — fast loops | 9587 | F02704 | non-negotiable | true | 10 |
| R05345 | Local model use case — drafting | 9588 | F02704 | non-negotiable | true | 10 |
| R05346 | Local model use case — memory extraction | 9589 | F02704 | non-negotiable | true | 10 |
| R05347 | Local model use case — SLM/RLM recursion | 9590 | F02704 | non-negotiable | true | 10 |
| R05348 | Local model use case — sandboxed tool plans | 9591 | F02704 | non-negotiable | true | 10 |
| R05349 | Local model use case — offline operation | 9592 | F02704 | non-negotiable | true | 10 |
| R05350 | Local model use case — high-volume cheap inference | 9593 | F02704 | non-negotiable | true | 10 |
| R05351 | Every model (local or cloud) MUST be represented the same way | 9598 | M00538 | non-negotiable | false | 10 |
| R05352 | Model Router YAML — field id | 9602 | F02706 | non-negotiable | true | 10 |
| R05353 | Model Router YAML — field provider | 9603 | F02707 | non-negotiable | true | 10 |
| R05354 | Model Router YAML — field role | 9604 | F02708 | non-negotiable | true | 10 |
| R05355 | Model Router YAML — field strengths (list) | 9605 | F02709 | non-negotiable | true | 10 |
| R05356 | Model Router YAML — field locality (remote/local) | 9606 | F02710 | non-negotiable | true | 10 |
| R05357 | Model Router YAML — field privacy (external/internal) | 9607 | F02711 | non-negotiable | true | 10 |
| R05358 | Model Router YAML — field cost (high/medium/low) | 9608 | F02712 | non-negotiable | true | 10 |
| R05359 | Model Router YAML — field latency (high/medium/low) | 9609 | F02713 | non-negotiable | true | 10 |
| R05360 | Model Router YAML — field supports (list of capabilities) | 9610 | F02714 | non-negotiable | true | 10 |
| R05361 | Example model — openai:gpt-5.2 oracle role; strengths [coding, agentic, structured_outputs]; remote; external; high cost; medium latency; supports [structured_outputs / tools / vision / reasoning_effort] | 9600–9615 | M00538 | non-negotiable | false | 10 |
| R05362 | Example model — anthropic:claude-sonnet critic role; strengths [coding, long_reasoning, analysis]; remote; external; supports [tool_use / extended_thinking / prompt_caching] | 9619–9631 | M00538 | non-negotiable | false | 10 |
| R05363 | Router chooses based on — privacy | 9636 | F02715 | non-negotiable | true | 10 |
| R05364 | Router chooses based on — cost | 9637 | F02715 | non-negotiable | true | 10 |
| R05365 | Router chooses based on — latency | 9638 | F02715 | non-negotiable | true | 10 |
| R05366 | Router chooses based on — risk | 9639 | F02715 | non-negotiable | true | 10 |
| R05367 | Router chooses based on — task type | 9640 | F02715 | non-negotiable | true | 10 |
| R05368 | Router chooses based on — local model confidence | 9641 | F02715 | non-negotiable | true | 10 |
| R05369 | Router chooses based on — cloud availability | 9642 | F02715 | non-negotiable | true | 10 |
| R05370 | Router chooses based on — user profile | 9643 | F02715 | non-negotiable | true | 10 |
| R05371 | Profile — sovereign (local only) | 9649–9650 | F02716 | non-negotiable | true | 10 |
| R05372 | Profile — hybrid (local first, cloud if uncertain) | 9652–9653 | F02716 | non-negotiable | true | 10 |
| R05373 | Profile — oracle (cloud allowed for final review) | 9655–9656 | F02716 | non-negotiable | true | 10 |
| R05374 | Profile — private_code (no cloud unless explicitly approved) | 9658–9659 | F02716 | non-negotiable | true | 10 |
| R05375 | Profile — research (cloud allowed for web/search/synthesis) | 9661–9662 | F02716 | non-negotiable | true | 10 |
| R05376 | Profile — high_assurance (local + OpenAI + Anthropic disagreement check) | 9664–9665 | F02716 | non-negotiable | true | 10 |
| R05377 | Environment module providers/ tree | 9673 | M00540 | non-negotiable | false | 10 |
| R05378 | providers/ — openai_adapter | 9674 | M00540 | non-negotiable | true | 10 |
| R05379 | providers/ — anthropic_adapter | 9675 | M00540 | non-negotiable | true | 10 |
| R05380 | providers/ — local_vllm_adapter | 9676 | M00540 | non-negotiable | true | 10 |
| R05381 | providers/ — sglang_adapter | 9677 | M00540 | non-negotiable | true | 10 |
| R05382 | providers/ — trtllm_adapter | 9678 | M00540 | non-negotiable | true | 10 |
| R05383 | providers/ — llama_cpp_adapter | 9679 | M00540 | non-negotiable | true | 10 |
| R05384 | Environment module runtime/ tree | 9681 | M00541 | non-negotiable | false | 10 |
| R05385 | runtime/ — router | 9682 | M00541 | non-negotiable | true | 10 |
| R05386 | runtime/ — policy_engine | 9683 | M00541 | non-negotiable | true | 10 |
| R05387 | runtime/ — memory_os | 9684 | M00541 | non-negotiable | true | 10 |
| R05388 | runtime/ — workflow_dag | 9685 | M00541 | non-negotiable | true | 10 |
| R05389 | runtime/ — tool_gate | 9686 | M00541 | non-negotiable | true | 10 |
| R05390 | runtime/ — replay_log | 9687 | M00541 | non-negotiable | true | 10 |
| R05391 | runtime/ — evals | 9688 | M00541 | non-negotiable | true | 10 |
| R05392 | Environment module schemas/ tree | 9690 | M00542 | non-negotiable | false | 10 |
| R05393 | schemas/ — Frame | 9691 | M00542 | non-negotiable | true | 10 |
| R05394 | schemas/ — ToolIntent | 9692 | M00542 | non-negotiable | true | 10 |
| R05395 | schemas/ — ModelRequest | 9693 | M00542 | non-negotiable | true | 10 |
| R05396 | schemas/ — ModelResponse | 9694 | M00542 | non-negotiable | true | 10 |
| R05397 | schemas/ — VerificationResult | 9695 | M00542 | non-negotiable | true | 10 |
| R05398 | schemas/ — MemoryWrite | 9696 | M00542 | non-negotiable | true | 10 |
| R05399 | Secrets MUST be handled by environment OR OS secret store | 9699 | E0306 | non-negotiable | false | 10 |
| R05400 | Secret env var — OPENAI_API_KEY | 9702 | E0306 | non-negotiable | true | 10 |
| R05401 | Secret env var — ANTHROPIC_API_KEY | 9703 | E0306 | non-negotiable | true | 10 |
| R05402 | Secrets NEVER in prompts | 9706 | E0306 | non-negotiable | false | 10 |
| R05403 | Secrets NEVER in logs | 9706 | E0306 | non-negotiable | false | 10 |
| R05404 | Secrets NEVER in replay payloads | 9706 | E0306 | non-negotiable | false | 10 |
| R05405 | Secrets NEVER in client-side code | 9706 | E0306 | non-negotiable | false | 10 |
| R05406 | The Big Rule — Cloud APIs are NOT "another level" separate from the system | 9710 | E0307 | non-negotiable | false | 10 |
| R05407 | The Big Rule — Cloud APIs are experts behind capability gates | 9712 | E0307 | non-negotiable | false | 10 |
| R05408 | Station-says — This task is private: local only | 9717 | E0307 | non-negotiable | true | 10 |
| R05409 | Station-says — This task is hard: ask OpenAI oracle | 9718 | E0307 | non-negotiable | true | 10 |
| R05410 | Station-says — This task needs critique: ask Anthropic | 9719 | E0307 | non-negotiable | true | 10 |
| R05411 | Station-says — This task needs speed: use local SLM | 9720 | E0307 | non-negotiable | true | 10 |
| R05412 | Station-says — This task needs proof: run tools/tests/symbolic verifier | 9721 | E0307 | non-negotiable | true | 10 |
| R05413 | "That is the right shape" | 9724 | E0307 | non-negotiable | false | 10 |
| R05414 | First serious step when sharing existing environment — map current OS / GPU stack / model servers / secrets / tools / repos / automation / sandboxes / deterministic-runtime location into this architecture | 9726 | E0307 | non-negotiable | false | 10 |
| R05415 | OPERATOR ADDENDUM (verbatim, 9728) — "as long as those are modes you can easily toggle on and off, not that you dont need to configure them / add keys in the first place anyway but it leads to cost and need for tracking" | 9728 | E0307 | non-negotiable | false | 10 |
| R05416 | Cloud-expert mode MUST be toggle-on/toggle-off easy (per operator addendum) | 9728 | E0307 | non-negotiable | false | 10 |
| R05417 | Configuration step is one-time (per operator) — add keys in the first place | 9728 | E0307 | non-negotiable | false | 10 |
| R05418 | Cost tracking is mandatory when cloud-expert mode is enabled | 9728 | E0307 | non-negotiable | false | 10 |
| R05419 | OPERATOR ADDENDUM (verbatim, 9729) — "I was talking otherwise about the what WE expose. so I can use this AI system from Claude Code replacing the env var for the API and same for OpenAI in other system or for OpenCode for example or Cline" | 9729 | E0307 + M00543 | non-negotiable | false | 10 |
| R05420 | Bidirectional cloud-expert role — sovereign-os IS the AI provider, NOT only consumer | 9729 | M00543 | non-negotiable | false | 10 |
| R05421 | Sovereign-os replaces ANTHROPIC_API_KEY env var for Claude Code (per operator addendum) | 9729 | M00543 | non-negotiable | true | 10 |
| R05422 | Sovereign-os replaces OPENAI_API_KEY env var for OpenCode (per operator addendum) | 9729 | M00543 | non-negotiable | true | 10 |
| R05423 | Sovereign-os replaces OpenAI/Anthropic env var for Cline (per operator addendum) | 9729 | M00543 | non-negotiable | true | 10 |
| R05424 | Sovereign-os MUST expose OpenAI-compatible API endpoint (Responses + Structured Outputs schema) | 9519 + 9520 + 9729 | M00543 | non-negotiable | true | 10 |
| R05425 | Sovereign-os MUST expose Anthropic-compatible API endpoint (extended thinking + tool use + prompt caching shape) | 9526 + 9527 + 9729 | M00543 | non-negotiable | true | 10 |
| R05426 | Cloud Expert Plane integrates with M025 cognitive compiler — router routes compiled DAG nodes to local or cloud expert | 9596–9644 + cross-ref M025 | E0303 | non-negotiable | false | 10 |
| R05427 | Cloud Expert Plane integrates with M026 SLM swarm + RLM engine — local SLM/RLM are alternatives to cloud experts on the same router | 9596 + cross-ref M026 | E0303 | non-negotiable | false | 10 |
| R05428 | Cloud Expert Plane integrates with M027 Value Plane — reward formula scores cloud vs local on cost/latency/privacy/risk | 9636–9644 + cross-ref M027 | E0303 | non-negotiable | false | 10 |
| R05429 | Cloud Expert Plane integrates with M028 Memory OS — cloud prompt caching maps to Memory OS KV cache | 9527 + cross-ref M028 | M00535 | non-negotiable | false | 10 |
| R05430 | Cloud Expert Plane integrates with M029 Computer-Use Plane — OpenAI computer-use capability is a remote variant of M029's typed action system | 9519 + cross-ref M029 | M00530 | non-negotiable | false | 10 |
| R05431 | Cloud Expert Plane integrates with M030 World Model Plane — cloud experts propose plans; local World Model predicts; local runtime commits (invariant) | 9555–9557 + cross-ref M030 | F02691 | non-negotiable | false | 10 |
| R05432 | Cloud Expert Plane integrates with M031 Symbolic Planning Plane — cloud LLM proposes formalization; local symbolic solver validates; local policy engine vetoes | cross-ref M031 + 9230–9234 | E0301 | non-negotiable | false | 10 |
| R05433 | Project boundary — Cloud Expert Plane is sovereign-os runtime; selfdef-collector-eventstream may re-ingest cloud-expert request/response logs for incident correlation (NOT for prompt content; only metadata) | architecture | E0298 | non-negotiable | false | 10 |
| R05434 | Project boundary — selfdef MS006 agent-guard policy may rate-limit cloud-expert calls + enforce cost-tracking via Layer-B metrics | MS006 + 9728 | E0307 | non-negotiable | false | 10 |
| R05435 | Project boundary — selfdef MS007 typed-mirror crates may carry Cloud-Expert Plane router/provider/profile manifest contracts for cross-repo binding | MS007 + SDD-038 | E0305 | non-negotiable | false | 10 |
| R05436 | Cloud Expert Plane is the 12th plane (extending M027 8-plane stack + M028 Memory OS + M029 Computer-Use Plane + M030 World Model Plane + M031 Symbolic Planning Plane) | cross-ref M027 R04590 + M028 + M029 + M030 + M031 | E0301 | non-negotiable | false | 10 |
| R05437 | Cloud Expert Plane respects the deterministic-runtime invariant — "Remote models propose. Local runtime commits." NEVER reversed | 9555–9557 | F02691 | non-negotiable | false | 10 |
| R05438 | Cloud Expert Plane respects the privacy invariant — sovereign profile = local only; private_code profile = no cloud unless explicit; secrets never leak | 9649 + 9658 + 9706 | E0304 + E0306 | non-negotiable | false | 10 |
| R05439 | Cloud Expert Plane respects the cost-tracking invariant — operator-toggleable; cost surfaces in Layer-B metrics; profile-driven (per operator addendum) | 9728 | E0307 | non-negotiable | false | 10 |
| R05440 | Composite — Cloud Expert Plane is BIDIRECTIONAL — sovereign-os consumes OpenAI/Anthropic as remote experts AND exposes OpenAI/Anthropic-compatible endpoints so Claude Code / OpenCode / Cline / OpenAI-consuming systems can use sovereign-os as their AI provider (per operator addendums 9728–9729); operator-toggleable on/off; cost-tracked; profile-gated; deterministic-runtime-invariant ("Remote models propose. Local runtime commits.") | 9486–9729 | E0307 + M00543 | non-negotiable | false | 10 |

## Cross-references

- Adjacent dump-range milestones: M031 Symbolic Planning plane (9151–9486) / M033 (next; dump 9728–…)
- Plane integration: M025 cognitive compiler / M026 SLM swarm + RLM engine / M027 Value Plane / M028 Memory OS / M029 Computer-Use Plane / M030 World Model Plane / M031 Symbolic Planning Plane / M032 Cloud Expert Plane (this)
- Selfdef boundary: cloud-expert metadata may flow into selfdef-collector-eventstream for incident correlation (NOT prompt content); agent-guard (MS006) may rate-limit + cost-track; MS007 typed mirrors may carry router/provider/profile manifests
- Bidirectional pattern (operator addendum 9729): sovereign-os IS the AI provider for Claude Code / OpenCode / Cline / OpenAI-consuming systems by replacing the API env var
