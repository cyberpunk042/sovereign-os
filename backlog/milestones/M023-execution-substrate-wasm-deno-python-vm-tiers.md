# M023 — Execution substrate — WASM / Deno / Python / VM tiers

> Parent: `backlog/milestones/INDEX.md` row M023 (dump 6366–6672).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 6366–6672.
> All entries below are extracted from the dump line range. No invention.

## Epics (E0208–E0217)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0208 | Execution substrate question — what kind of hand: shell / Python / Deno / WASM / VM / Container | 6381–6388 |
| E0209 | Research substrate — Deno secure-by-default permissions + Deno sandbox security (untrusted/AI-generated workloads) + Extism WASM plugins + WASI / MCP-SandboxScan | 6390–6395 |
| E0210 | Principle — tools must be capability-shaped (not "agent can run X" but "agent can read these files / write this dir / call this host / run this function / spend this budget / return this schema") | 6397–6420 |
| E0211 | Execution Tiers — Tier 0 Pure Logic / Tier 1 WASM Plugins / Tier 2 Deno Scripts / Tier 3 Python REPL / Tier 4 Containers-MicroVMs / Tier 5 VFIO 3090 VM | 6422–6459 |
| E0212 | REPL Is Not One Thing — 8 named REPLs (math / Python / Deno / SQL / shell / browser / simulation / WASM-plugin) each with capability descriptor YAML | 6461–6493 |
| E0213 | WASM As Tool ABI — common tool interfaces (parse / score / filter / transform / validate) implemented as WASM plugins in Rust/Go/Zig/TinyGo | 6495–6521 |
| E0214 | Capability Words — 64-bit per-execution capability word (8 bitfields: runtime_tier / fs_scope / net_scope / subprocess_scope / time_budget / memory_budget / trust_level / audit_flags) + AVX-512 batch check | 6523–6547 |
| E0215 | Tool ABI — every tool speaks strict ABI (tool_id / version / input_schema / output_schema / capabilities_required / side_effect_class / determinism / timeout_ms) | 6549–6566 |
| E0216 | Generated Code Path — 7-step pipeline (propose → validate caps → run-in-tier → capture I/O → validate schema → attach trace → commit-or-reject) + Promotion ladder (ad-hoc → sandboxed script → tested tool → WASM plugin → trusted runtime primitive) | 6568–6627 |
| E0217 | Execution Plane = 9th plane; closing rule "A tool is not a command. A tool is a typed, capability-limited, observable state transition." | 6629–6670 |

## Modules (M00371–M00388)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00371 | Tier 0 — Pure Logic (AVX-512 masks / parsers / validators / FSMs; no side effects) | 6427–6429 | E0211 |
| M00372 | Tier 1 — WASM Plugins (deterministic-ish / portable / capability-limited; parsers / filters / scorers / transforms) | 6431–6434 | E0211 |
| M00373 | Tier 2 — Deno Scripts (JS/TS tools with explicit file/net/env/run permissions; web/API glue + agent-authored scripts) | 6435–6438 | E0211 |
| M00374 | Tier 3 — Python REPL (rich science/data/code environment; powerful but more dangerous) | 6439–6441 | E0211 |
| M00375 | Tier 4 — Containers / MicroVMs (package installs / builds / untrusted code / browsers) | 6443–6444 | E0211 |
| M00376 | Tier 5 — VFIO 3090 VM (heavy sandboxed model work / risky tool exploration / perception agents) | 6446–6447 | E0211 |
| M00377 | REPL — math REPL | 6466 | E0212 |
| M00378 | REPL — Python REPL | 6467 | E0212 |
| M00379 | REPL — Deno/TypeScript REPL | 6468 | E0212 |
| M00380 | REPL — SQL REPL | 6469 | E0212 |
| M00381 | REPL — shell REPL | 6470 | E0212 |
| M00382 | REPL — browser REPL | 6471 | E0212 |
| M00383 | REPL — simulation REPL | 6472 | E0212 |
| M00384 | REPL — WASM plugin REPL | 6473 | E0212 |
| M00385 | REPL capability descriptor YAML — runtime / allow_net / allow_read / allow_write / allow_run / max_time_ms / output_schema | 6478–6491 | E0212 |
| M00386 | WASM tool interface — 5 named signatures (parse / score / filter / transform / validate) | 6500–6507 | E0213 |
| M00387 | 64-bit capability word — 8 bitfields | 6527–6536 | E0214 |
| M00388 | Tool-ABI manifest — 8 named fields | 6553–6563 | E0215 |

## Features (F01871–F01955)

| F ID | Phrase | Dump line | Parent module | Category | Opt-in |
|---|---|---|---|---|---|
| F01871 | Toggle execution tier (auto / tier0 / tier1 / tier2 / tier3 / tier4 / tier5) | 6424–6448 | E0211 | mode | true |
| F01872 | Profile knob — `execution_tier_default = auto \| tier0 \| tier1 \| tier2 \| tier3 \| tier4 \| tier5` | 6424–6448 | E0211 | profile | true |
| F01873 | Env var `SOVEREIGN_EXECUTION_TIER_DEFAULT` | 6424–6448 | E0211 | env_var | true |
| F01874 | CLI `--execution-tier <name>` | 6424–6448 | E0211 | cli_verb | true |
| F01875 | Tier 0 — Pure Logic kernel (AVX-512 masks / parsers / validators / FSMs) | 6427–6429 | M00371 | composite | false |
| F01876 | Tier 1 — WASM Plugin runtime (deterministic, portable, capability-limited) | 6431–6434 | M00372 | composite | false |
| F01877 | Tier 2 — Deno Script runtime with explicit permissions | 6435–6438 | M00373 | composite | true |
| F01878 | Tier 3 — Python REPL (jupyter-style kernel) | 6439–6441 | M00374 | composite | true |
| F01879 | Tier 4 — Container / MicroVM (Podman / Firecracker) | 6443–6444 | M00375 | composite | true |
| F01880 | Tier 5 — VFIO 3090 VM (heavy sandboxed model work) | 6446–6447 | M00376 | composite | true |
| F01881 | Tier-selection rule — router chooses lowest tier that can solve the problem | 6450 | E0211 | composite | false |
| F01882 | Tier-preference rule — Prefer pure logic over code | 6455 | E0211 | composite | false |
| F01883 | Tier-preference rule — Prefer WASM over shell | 6456 | E0211 | composite | false |
| F01884 | Tier-preference rule — Prefer Deno with narrow permissions over Python with ambient access | 6457 | E0211 | composite | false |
| F01885 | Tier-preference rule — Prefer VM for unknown/risky execution | 6458 | E0211 | composite | false |
| F01886 | REPL — math REPL (closed-form calculator with no side effects) | 6466 | M00377 | composite | true |
| F01887 | REPL — Python REPL (ipykernel-backed) | 6467 | M00378 | composite | true |
| F01888 | REPL — Deno/TypeScript REPL (deno run with explicit permissions) | 6468 | M00379 | composite | true |
| F01889 | REPL — SQL REPL (DuckDB or sqlite) | 6469 | M00380 | composite | true |
| F01890 | REPL — shell REPL (bash in sandbox) | 6470 | M00381 | composite | true |
| F01891 | REPL — browser REPL (Playwright headless) | 6471 | M00382 | composite | true |
| F01892 | REPL — simulation REPL (user-defined deterministic simulator) | 6472 | M00383 | composite | true |
| F01893 | REPL — WASM plugin REPL (wasmtime/wasmer invocation) | 6473 | M00384 | composite | true |
| F01894 | REPL capability descriptor — `name` (string) | 6480 | M00385 | data_model | false |
| F01895 | REPL capability descriptor — `runtime` enum (deno/python/deno-ts/sql/shell/browser/sim/wasm) | 6481 | M00385 | data_model | false |
| F01896 | REPL capability descriptor — `allow_net` (string list of allowed hosts) | 6482 | M00385 | data_model | false |
| F01897 | REPL capability descriptor — `allow_read` (path list) | 6485 | M00385 | data_model | false |
| F01898 | REPL capability descriptor — `allow_write` (path list) | 6486 | M00385 | data_model | false |
| F01899 | REPL capability descriptor — `allow_run` (subprocess permission bool) | 6488 | M00385 | data_model | false |
| F01900 | REPL capability descriptor — `max_time_ms` (time budget) | 6489 | M00385 | data_model | false |
| F01901 | REPL capability descriptor — `output_schema` (typed result shape) | 6490 | M00385 | data_model | false |
| F01902 | WASM tool interface — `parse(input_bytes) -> ParsedDocument` | 6502 | M00386 | composite | false |
| F01903 | WASM tool interface — `score(candidate, context) -> Score` | 6503 | M00386 | composite | false |
| F01904 | WASM tool interface — `filter(memory_refs, query) -> MemoryRefs` | 6504 | M00386 | composite | false |
| F01905 | WASM tool interface — `transform(json) -> json` | 6505 | M00386 | composite | false |
| F01906 | WASM tool interface — `validate(tool_intent) -> ValidationResult` | 6506 | M00386 | composite | false |
| F01907 | WASM plugin language — Rust supported | 6509 | M00372 | composite | true |
| F01908 | WASM plugin language — Go supported | 6509 | M00372 | composite | true |
| F01909 | WASM plugin language — Zig supported | 6509 | M00372 | composite | true |
| F01910 | WASM plugin language — TinyGo supported | 6509 | M00372 | composite | true |
| F01911 | WASM plugin sandbox — host grants only memory + input buffer + maybe specific host function | 6513–6515 | M00372 | composite | false |
| F01912 | WASM plugin sandbox — no ambient filesystem | 6518 | M00372 | composite | false |
| F01913 | WASM plugin sandbox — no random network | 6519 | M00372 | composite | false |
| F01914 | Capability word — `bits 0..7 runtime_tier` | 6528 | M00387 | data_model | false |
| F01915 | Capability word — `bits 8..15 filesystem_scope` | 6529 | M00387 | data_model | false |
| F01916 | Capability word — `bits 16..23 network_scope` | 6530 | M00387 | data_model | false |
| F01917 | Capability word — `bits 24..31 subprocess_scope` | 6531 | M00387 | data_model | false |
| F01918 | Capability word — `bits 32..39 time_budget` | 6532 | M00387 | data_model | false |
| F01919 | Capability word — `bits 40..47 memory_budget` | 6533 | M00387 | data_model | false |
| F01920 | Capability word — `bits 48..55 trust_level` | 6534 | M00387 | data_model | false |
| F01921 | Capability word — `bits 56..63 audit_flags` | 6535 | M00387 | data_model | false |
| F01922 | AVX-512 capability batch check — `requested & allowed == requested` | 6541 | M00387 | composite | false |
| F01923 | AVX-512 capability batch check — `budget > estimated_cost` | 6542 | M00387 | composite | false |
| F01924 | AVX-512 capability batch check — `risk <= threshold` | 6543 | M00387 | composite | false |
| F01925 | AVX-512 capability batch check — `sandbox_available` | 6544 | M00387 | composite | false |
| F01926 | Tool-ABI field — `tool_id` | 6555 | M00388 | data_model | false |
| F01927 | Tool-ABI field — `version` | 6556 | M00388 | data_model | false |
| F01928 | Tool-ABI field — `input_schema` | 6557 | M00388 | data_model | false |
| F01929 | Tool-ABI field — `output_schema` | 6558 | M00388 | data_model | false |
| F01930 | Tool-ABI field — `capabilities_required` (bitfield) | 6559 | M00388 | data_model | false |
| F01931 | Tool-ABI field — `side_effect_class` (read_only / read_write / external) | 6560 | M00388 | data_model | false |
| F01932 | Tool-ABI field — `determinism` (deterministic / nondeterministic) | 6561 | M00388 | data_model | false |
| F01933 | Tool-ABI field — `timeout_ms` | 6562 | M00388 | data_model | false |
| F01934 | Tool catalog — model receives typed-capabilities catalog (not raw host power) | 6566 | E0215 | composite | false |
| F01935 | Generated code path step 1 — model proposes code/tool | 6572 | E0216 | composite | false |
| F01936 | Generated code path step 2 — CPU validates declared capabilities | 6573 | E0216 | composite | false |
| F01937 | Generated code path step 3 — run in WASM/Deno/Python/VM depending on risk | 6574 | E0216 | composite | false |
| F01938 | Generated code path step 4 — capture stdout/stderr/files/network | 6575 | E0216 | composite | false |
| F01939 | Generated code path step 5 — validate output schema | 6576 | E0216 | composite | false |
| F01940 | Generated code path step 6 — attach trace | 6577 | E0216 | composite | false |
| F01941 | Generated code path step 7 — commit result or reject | 6578 | E0216 | composite | false |
| F01942 | Promotion ladder — ad hoc code → sandboxed script → tested tool → WASM plugin → trusted runtime primitive | 6622–6624 | E0216 | composite | true |
| F01943 | Intelligence connection — `language uncertainty → executable hypothesis → observed result → updated state` | 6588–6590 | E0216 | composite | false |
| F01944 | 9-plane architecture — Execution Plane (added) | 6642 | E0217 | composite | false |
| F01945 | Closing rule — "A tool is not a command. A tool is a typed, capability-limited, observable state transition." | 6660–6661 | E0217 | composite | false |
| F01946 | API `POST /v1/exec/tier` (select+execute tier-specific REPL request) | 6422–6448 | E0211 | api_endpoint | true |
| F01947 | API `POST /v1/exec/wasm` (invoke WASM plugin) | 6495–6521 | M00372 | api_endpoint | true |
| F01948 | API `POST /v1/exec/deno` (invoke Deno script) | 6435–6438 | M00373 | api_endpoint | true |
| F01949 | API `POST /v1/exec/python` (invoke Python REPL cell) | 6439–6441 | M00374 | api_endpoint | true |
| F01950 | API `GET /v1/tools/catalog` (list typed tool catalog with capabilities) | 6566 | E0215 | api_endpoint | true |
| F01951 | Dashboard — Execution tier occupancy (per tier: active requests + queue depth + avg latency) | 6422–6448 | E0211 | dashboard | true |
| F01952 | Dashboard — REPL catalog (8 named REPLs with capability descriptor preview) | 6461–6493 | E0212 | dashboard | true |
| F01953 | Dashboard — WASM plugin registry (per plugin: capability word + last invocation + determinism) | 6495–6521 | M00372 | dashboard | true |
| F01954 | Dashboard — Tool-ABI catalog (per tool: ABI manifest + side-effect class + determinism + capability bitfield) | 6549–6566 | M00388 | dashboard | true |
| F01955 | Dashboard — Promotion ladder visualizer (ad-hoc → script → tool → WASM → primitive transitions) | 6622–6624 | F01942 | dashboard | true |

## Requirements (R03741–R03910)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R03741 | Execution substrate question — what kind of hand: shell / Python / Deno / WASM / VM / Container | 6385–6388 | E0208 | non-negotiable | false | 10 |
| R03742 | Deno is secure by default — no file/network/env/subprocess access unless explicitly allowed | 6392 | M00373 | non-negotiable | false | 10 |
| R03743 | Deno sandbox is aimed at untrusted or AI-generated workloads | 6393 | M00373 | non-negotiable | false | 10 |
| R03744 | Deno emphasizes traceability of commands/HTTP/SSH behavior | 6393 | M00373 | non-negotiable | false | 10 |
| R03745 | Extism provides a cross-language WebAssembly plugin system | 6394 | M00372 | non-negotiable | false | 10 |
| R03746 | Raw WebAssembly is basically a sandboxed calculator unless the host grants capabilities | 6394 | M00372 | non-negotiable | false | 10 |
| R03747 | WebAssembly/WASI is increasingly relevant for agent tools because it gives portable, capability-shaped execution | 6395 | M00372 | non-negotiable | false | 10 |
| R03748 | MCP-SandboxScan uses WASM/WASI to safely execute untrusted MCP tools and produce auditable reports | 6395 | M00372 | non-negotiable | true | 10 |
| R03749 | Tools must be capability-shaped | 6400 | E0210 | non-negotiable | false | 10 |
| R03750 | Capability-shape NOT — "agent can run Python" | 6406 | E0210 | non-negotiable | false | 10 |
| R03751 | Capability-shape NOT — "agent can run shell" | 6407 | E0210 | non-negotiable | false | 10 |
| R03752 | Capability-shape NOT — "agent can use browser" | 6408 | E0210 | non-negotiable | false | 10 |
| R03753 | Capability-shape — "agent can read these files" | 6414 | E0210 | non-negotiable | false | 10 |
| R03754 | Capability-shape — "agent can write this directory" | 6415 | E0210 | non-negotiable | false | 10 |
| R03755 | Capability-shape — "agent can call this host" | 6416 | E0210 | non-negotiable | false | 10 |
| R03756 | Capability-shape — "agent can run this bounded function" | 6417 | E0210 | non-negotiable | false | 10 |
| R03757 | Capability-shape — "agent can spend this time/budget" | 6418 | E0210 | non-negotiable | false | 10 |
| R03758 | Capability-shape — "agent can return this schema" | 6419 | E0210 | non-negotiable | false | 10 |
| R03759 | Tier 0 — Pure Logic (AVX-512 masks / parsers / validators / FSMs; no side effects) | 6427–6429 | M00371 | non-negotiable | false | 10 |
| R03760 | Tier 1 — WASM Plugins (deterministic-ish / portable / capability-limited / parsers-filters-scorers-transforms) | 6431–6434 | M00372 | non-negotiable | false | 10 |
| R03761 | Tier 2 — Deno Scripts (JS/TS tools with explicit file/net/env/run permissions / web-API glue / agent-authored scripts) | 6435–6438 | M00373 | non-negotiable | false | 10 |
| R03762 | Tier 3 — Python REPL (rich science/data/code environment / powerful but more dangerous) | 6439–6441 | M00374 | non-negotiable | false | 10 |
| R03763 | Tier 4 — Containers / MicroVMs (package installs / builds / untrusted code / browsers) | 6443–6444 | M00375 | non-negotiable | false | 10 |
| R03764 | Tier 5 — VFIO 3090 VM (heavy sandboxed model work / risky tool exploration / perception agents) | 6446–6447 | M00376 | non-negotiable | false | 10 |
| R03765 | Router chooses the lowest tier that can solve the problem | 6450 | E0211 | non-negotiable | false | 10 |
| R03766 | Tier preference — Prefer pure logic over code | 6455 | E0211 | non-negotiable | false | 10 |
| R03767 | Tier preference — Prefer WASM over shell | 6456 | E0211 | non-negotiable | false | 10 |
| R03768 | Tier preference — Prefer Deno with narrow permissions over Python with ambient access | 6457 | E0211 | non-negotiable | false | 10 |
| R03769 | Tier preference — Prefer VM for unknown/risky execution | 6458 | E0211 | non-negotiable | false | 10 |
| R03770 | There should be several REPLs | 6463 | E0212 | non-negotiable | false | 10 |
| R03771 | REPL — math REPL | 6466 | M00377 | non-negotiable | true | 10 |
| R03772 | REPL — Python REPL | 6467 | M00378 | non-negotiable | true | 10 |
| R03773 | REPL — Deno/TypeScript REPL | 6468 | M00379 | non-negotiable | true | 10 |
| R03774 | REPL — SQL REPL | 6469 | M00380 | non-negotiable | true | 10 |
| R03775 | REPL — shell REPL | 6470 | M00381 | non-negotiable | true | 10 |
| R03776 | REPL — browser REPL | 6471 | M00382 | non-negotiable | true | 10 |
| R03777 | REPL — simulation REPL | 6472 | M00383 | non-negotiable | true | 10 |
| R03778 | REPL — WASM plugin REPL | 6473 | M00384 | non-negotiable | true | 10 |
| R03779 | Each REPL has a capability descriptor | 6476 | M00385 | non-negotiable | false | 10 |
| R03780 | Capability descriptor field — `name` | 6480 | M00385 | non-negotiable | false | 10 |
| R03781 | Capability descriptor field — `runtime` | 6481 | M00385 | non-negotiable | false | 10 |
| R03782 | Capability descriptor field — `allow_net` (list of allowed hosts) | 6482–6484 | M00385 | non-negotiable | false | 10 |
| R03783 | Capability descriptor field — `allow_read` (path list) | 6485 | M00385 | non-negotiable | false | 10 |
| R03784 | Capability descriptor field — `allow_write` (path list) | 6486–6487 | M00385 | non-negotiable | false | 10 |
| R03785 | Capability descriptor field — `allow_run` (subprocess permission bool) | 6488 | M00385 | non-negotiable | false | 10 |
| R03786 | Capability descriptor field — `max_time_ms` (time budget) | 6489 | M00385 | non-negotiable | false | 10 |
| R03787 | Capability descriptor field — `output_schema` (typed result shape) | 6490 | M00385 | non-negotiable | false | 10 |
| R03788 | Now REPL is governable | 6493 | E0212 | non-negotiable | false | 10 |
| R03789 | WASM defines common tool interfaces using typed schemas | 6499 | E0213 | non-negotiable | false | 10 |
| R03790 | WASM tool interface — `parse(input_bytes) -> ParsedDocument` | 6502 | M00386 | non-negotiable | false | 10 |
| R03791 | WASM tool interface — `score(candidate, context) -> Score` | 6503 | M00386 | non-negotiable | false | 10 |
| R03792 | WASM tool interface — `filter(memory_refs, query) -> MemoryRefs` | 6504 | M00386 | non-negotiable | false | 10 |
| R03793 | WASM tool interface — `transform(json) -> json` | 6505 | M00386 | non-negotiable | false | 10 |
| R03794 | WASM tool interface — `validate(tool_intent) -> ValidationResult` | 6506 | M00386 | non-negotiable | false | 10 |
| R03795 | WASM plugins implementable in Rust | 6509 | M00372 | non-negotiable | true | 10 |
| R03796 | WASM plugins implementable in Go | 6509 | M00372 | non-negotiable | true | 10 |
| R03797 | WASM plugins implementable in Zig | 6509 | M00372 | non-negotiable | true | 10 |
| R03798 | WASM plugins implementable in TinyGo | 6509 | M00372 | non-negotiable | true | 10 |
| R03799 | WASM plugin sandbox — host grants only memory | 6514 | M00372 | non-negotiable | false | 10 |
| R03800 | WASM plugin sandbox — host grants only input buffer | 6515 | M00372 | non-negotiable | false | 10 |
| R03801 | WASM plugin sandbox — host grants only specific host function | 6516 | M00372 | non-negotiable | false | 10 |
| R03802 | WASM plugin sandbox — no ambient filesystem | 6518 | M00372 | non-negotiable | false | 10 |
| R03803 | WASM plugin sandbox — no random network | 6519 | M00372 | non-negotiable | false | 10 |
| R03804 | WASM gives an AI tool ecosystem that is portable and safer | 6521 | E0213 | non-negotiable | false | 10 |
| R03805 | Every execution request gets a 64-bit capability word | 6525 | M00387 | non-negotiable | false | 10 |
| R03806 | Capability word — bits 0..7 runtime tier | 6528 | M00387 | non-negotiable | false | 10 |
| R03807 | Capability word — bits 8..15 filesystem scope | 6529 | M00387 | non-negotiable | false | 10 |
| R03808 | Capability word — bits 16..23 network scope | 6530 | M00387 | non-negotiable | false | 10 |
| R03809 | Capability word — bits 24..31 subprocess scope | 6531 | M00387 | non-negotiable | false | 10 |
| R03810 | Capability word — bits 32..39 time budget | 6532 | M00387 | non-negotiable | false | 10 |
| R03811 | Capability word — bits 40..47 memory budget | 6533 | M00387 | non-negotiable | false | 10 |
| R03812 | Capability word — bits 48..55 trust level | 6534 | M00387 | non-negotiable | false | 10 |
| R03813 | Capability word — bits 56..63 audit flags | 6535 | M00387 | non-negotiable | false | 10 |
| R03814 | AVX-512 scheduler batch-check — `requested & allowed == requested` | 6541 | M00387 | non-negotiable | false | 10 |
| R03815 | AVX-512 scheduler batch-check — `budget > estimated_cost` | 6542 | M00387 | non-negotiable | false | 10 |
| R03816 | AVX-512 scheduler batch-check — `risk <= threshold` | 6543 | M00387 | non-negotiable | false | 10 |
| R03817 | AVX-512 scheduler batch-check — `sandbox_available` | 6544 | M00387 | non-negotiable | false | 10 |
| R03818 | If checks pass — enqueue | 6547 | M00387 | non-negotiable | false | 10 |
| R03819 | If checks fail — reject or human-gate | 6547 | M00387 | non-negotiable | false | 10 |
| R03820 | Every tool speaks a strict ABI | 6551 | M00388 | non-negotiable | false | 10 |
| R03821 | Tool-ABI field — `tool_id` | 6555 | M00388 | non-negotiable | false | 10 |
| R03822 | Tool-ABI field — `version` | 6556 | M00388 | non-negotiable | false | 10 |
| R03823 | Tool-ABI field — `input_schema` | 6557 | M00388 | non-negotiable | false | 10 |
| R03824 | Tool-ABI field — `output_schema` | 6558 | M00388 | non-negotiable | false | 10 |
| R03825 | Tool-ABI field — `capabilities_required` (bitfield) | 6559 | M00388 | non-negotiable | false | 10 |
| R03826 | Tool-ABI field — `side_effect_class` (read_only / read_write / external) | 6560 | M00388 | non-negotiable | false | 10 |
| R03827 | Tool-ABI field — `determinism` (deterministic / nondeterministic) | 6561 | M00388 | non-negotiable | false | 10 |
| R03828 | Tool-ABI field — `timeout_ms` | 6562 | M00388 | non-negotiable | false | 10 |
| R03829 | The model never receives raw host power — it receives a catalog of typed capabilities | 6566 | E0215 | non-negotiable | false | 10 |
| R03830 | Generated code path step 1 — model proposes code/tool | 6572 | E0216 | non-negotiable | false | 10 |
| R03831 | Generated code path step 2 — CPU validates declared capabilities | 6573 | E0216 | non-negotiable | false | 10 |
| R03832 | Generated code path step 3 — run in WASM/Deno/Python/VM depending on risk | 6574 | E0216 | non-negotiable | false | 10 |
| R03833 | Generated code path step 4 — capture stdout/stderr/files/network | 6575 | E0216 | non-negotiable | false | 10 |
| R03834 | Generated code path step 5 — validate output schema | 6576 | E0216 | non-negotiable | false | 10 |
| R03835 | Generated code path step 6 — attach trace | 6577 | E0216 | non-negotiable | false | 10 |
| R03836 | Generated code path step 7 — commit result or reject | 6578 | E0216 | non-negotiable | false | 10 |
| R03837 | Generated code becomes a candidate action, not authority | 6582 | E0216 | non-negotiable | false | 10 |
| R03838 | Intelligence connection — `language uncertainty → executable hypothesis → observed result → updated state` | 6588–6590 | E0216 | non-negotiable | false | 10 |
| R03839 | Observation IS intelligence — it sharpens the system | 6604 | E0216 | non-negotiable | false | 10 |
| R03840 | Promotion ladder — ad hoc code | 6624 | E0216 | non-negotiable | false | 10 |
| R03841 | Promotion ladder — sandboxed script | 6624 | E0216 | non-negotiable | false | 10 |
| R03842 | Promotion ladder — tested tool | 6624 | E0216 | non-negotiable | false | 10 |
| R03843 | Promotion ladder — WASM plugin | 6624 | E0216 | non-negotiable | false | 10 |
| R03844 | Promotion ladder — trusted runtime primitive | 6624 | E0216 | non-negotiable | false | 10 |
| R03845 | Intelligence crystallizes into infrastructure via promotion ladder | 6627 | E0216 | non-negotiable | false | 10 |
| R03846 | Execution Plane is the 9th plane | 6642 | E0217 | non-negotiable | false | 10 |
| R03847 | Execution plane is tiered — AVX logic / WASM plugins / Deno scripts / Python REPL / containers / microVMs / VFIO VM | 6647–6654 | E0217 | non-negotiable | false | 10 |
| R03848 | Closing rule — A tool is not a command | 6660 | E0217 | non-negotiable | false | 10 |
| R03849 | Closing rule — A tool is a typed, capability-limited, observable state transition | 6661 | E0217 | non-negotiable | false | 10 |
| R03850 | REPL gives the system hands | 6666 | E0217 | non-negotiable | false | 10 |
| R03851 | Capabilities give the hands gloves | 6667 | E0217 | non-negotiable | false | 10 |
| R03852 | Logic decides when to move | 6668 | E0217 | non-negotiable | false | 10 |
| R03853 | Replay remembers what happened | 6669 | E0217 | non-negotiable | false | 10 |
| R03854 | Memory learns what worked | 6670 | E0217 | non-negotiable | false | 10 |
| R03855 | Execution tier operator-overrideable (auto / tier0..tier5) | 6422–6448 | F01871 | non-negotiable | true | 10 |
| R03856 | Env var `SOVEREIGN_EXECUTION_TIER_DEFAULT` | 6422–6448 | F01873 | non-negotiable | true | 10 |
| R03857 | CLI `--execution-tier <name>` | 6422–6448 | F01874 | non-negotiable | true | 10 |
| R03858 | Tier 0 implementation — AVX-512 mask / parser / validator / FSM library | 6427–6429 | F01875 | non-negotiable | false | 10 |
| R03859 | Tier 1 implementation — wasmtime + Extism plugin runtime | 6431–6434 | F01876 | non-negotiable | false | 10 |
| R03860 | Tier 2 implementation — `deno run --allow-...` explicit-permissions runner | 6435–6438 | F01877 | non-negotiable | true | 10 |
| R03861 | Tier 3 implementation — ipykernel-backed jupyter-style Python REPL | 6439–6441 | F01878 | non-negotiable | true | 10 |
| R03862 | Tier 4 implementation — Podman + Firecracker microVM hybrid | 6443–6444 | F01879 | non-negotiable | true | 10 |
| R03863 | Tier 5 implementation — VFIO PCI passthrough to 3090 GPU within QEMU/KVM VM | 6446–6447 | F01880 | non-negotiable | true | 10 |
| R03864 | REPL capability descriptor YAML round-trips through serde | 6478–6491 | M00385 | non-negotiable | false | 10 |
| R03865 | Capability word 64-bit encoding round-trips through bitfield encode/decode | 6527–6536 | M00387 | non-negotiable | false | 10 |
| R03866 | Tool-ABI manifest round-trips through JSON serde with all 8 fields | 6553–6563 | M00388 | non-negotiable | false | 10 |
| R03867 | API `POST /v1/exec/tier` selects + executes tier-specific REPL request | 6422–6448 | F01946 | non-negotiable | true | 10 |
| R03868 | API `POST /v1/exec/wasm` invokes WASM plugin | 6495–6521 | F01947 | non-negotiable | true | 10 |
| R03869 | API `POST /v1/exec/deno` invokes Deno script with explicit permissions | 6435–6438 | F01948 | non-negotiable | true | 10 |
| R03870 | API `POST /v1/exec/python` invokes Python REPL cell | 6439–6441 | F01949 | non-negotiable | true | 10 |
| R03871 | API `GET /v1/tools/catalog` lists typed tool catalog with capabilities | 6566 | F01950 | non-negotiable | true | 10 |
| R03872 | Dashboard — Execution tier occupancy (per tier: active requests + queue depth + avg latency) | 6422–6448 | F01951 | non-negotiable | true | 10 |
| R03873 | Dashboard — REPL catalog (8 REPLs with capability descriptor preview) | 6461–6493 | F01952 | non-negotiable | true | 10 |
| R03874 | Dashboard — WASM plugin registry (per plugin: capability word + last invocation + determinism) | 6495–6521 | F01953 | non-negotiable | true | 10 |
| R03875 | Dashboard — Tool-ABI catalog (per tool: ABI manifest + side-effect class + determinism + capability bitfield) | 6549–6566 | F01954 | non-negotiable | true | 10 |
| R03876 | Dashboard — Promotion ladder visualizer (5-stage ad-hoc → primitive) | 6622–6624 | F01955 | non-negotiable | true | 10 |
| R03877 | Test — capability word 64-bit encode/decode round-trip for all 8 bitfields | 6527–6536 | M00387 | non-negotiable | false | 10 |
| R03878 | Test — AVX-512 batch-check correctly accepts capability subset and rejects superset | 6541–6544 | M00387 | non-negotiable | false | 10 |
| R03879 | Test — Tool-ABI manifest 8-field round-trip via JSON | 6553–6563 | M00388 | non-negotiable | false | 10 |
| R03880 | Test — REPL capability descriptor YAML refuses on missing required field | 6478–6491 | M00385 | non-negotiable | false | 10 |
| R03881 | Test — Tier 0 pure-logic refuses on attempted side effect | 6427–6429 | M00371 | non-negotiable | false | 10 |
| R03882 | Test — Tier 1 WASM plugin refuses on un-granted host function | 6513–6519 | M00372 | non-negotiable | false | 10 |
| R03883 | Test — Tier 2 Deno refuses on un-allowlisted host | 6482–6484 | M00373 | non-negotiable | false | 10 |
| R03884 | Test — Tier 2 Deno refuses on un-allowlisted write path | 6486–6487 | M00373 | non-negotiable | false | 10 |
| R03885 | Test — Tier 3 Python honors `allow_run = false` | 6488 | M00374 | non-negotiable | false | 10 |
| R03886 | Test — Tier 4 container refuses outbound when no `network_scope` granted | 6530 | M00375 | non-negotiable | false | 10 |
| R03887 | Test — Tier 5 VFIO VM passthrough to 3090 honors capability budget | 6446–6447 | M00376 | non-negotiable | true | 10 |
| R03888 | Test — generated-code 7-step pipeline rejects at correct step for each failure type | 6572–6578 | E0216 | non-negotiable | false | 10 |
| R03889 | Test — promotion ladder transition (ad-hoc → script → tool → WASM → primitive) preserves traces | 6622–6624 | E0216 | non-negotiable | false | 10 |
| R03890 | Test — router chooses lowest tier that can solve a synthetic task | 6450 | E0211 | non-negotiable | false | 10 |
| R03891 | Test — every shipped WASM tool implements all 5 interfaces (parse / score / filter / transform / validate) when applicable | 6500–6507 | M00386 | non-negotiable | false | 10 |
| R03892 | Test — tool catalog returns 0 raw-host-power affordances | 6566 | E0215 | non-negotiable | false | 10 |
| R03893 | Composite — Execution Plane integrates with M015 programming plane (Tool Nodes execute here) | 6629–6655 | E0217 | non-negotiable | false | 10 |
| R03894 | Composite — Execution Plane integrates with M020 semantic ISA (instruction `EXECUTE_REPL` lands here) | 6629–6655 | E0217 | non-negotiable | false | 10 |
| R03895 | Composite — Execution Plane integrates with M021 6-layer weave (REPL Layer 1 substrate) | 6629–6655 | E0217 | non-negotiable | false | 10 |
| R03896 | Composite — Execution Plane integrates with M022 Cognitive Frame (REPL-execution variant lives here) | 6629–6655 | E0217 | non-negotiable | false | 10 |
| R03897 | Composite — Execution Plane integrates with M014 isolation+trust boundaries (Tier 4/5 sandbox enforcement) | 6443–6447 | E0217 | non-negotiable | false | 10 |
| R03898 | Composite — Execution Plane integrates with M013 observability (per-tier latency + drop rate + capability-check metrics) | 6629–6655 | E0217 | non-negotiable | false | 10 |
| R03899 | Composite — Execution Plane integrates with M016 learning plane (promotion ladder feeds skill library) | 6622–6624 | E0217 | non-negotiable | false | 10 |
| R03900 | Composite — Execution Plane integrates with M012 storage (sandboxed REPL workspaces live in ZFS `tank/workspaces`) | 6629–6655 | E0217 | non-negotiable | false | 10 |
| R03901 | Composite — Execution Plane is operator-extensible (new REPL or new WASM plugin can be added by operator at runtime) | 6478–6491 | E0212 | non-negotiable | true | 10 |
| R03902 | Anti-pattern — NO ambient filesystem access for any tier above 0 without explicit capability grant | 6518 | E0210 | non-negotiable | false | 10 |
| R03903 | Anti-pattern — NO ambient network access for any tier above 0 without explicit capability grant | 6519 | E0210 | non-negotiable | false | 10 |
| R03904 | Anti-pattern — NO ambient subprocess access for any tier above 0 without explicit capability grant | 6531 | E0210 | non-negotiable | false | 10 |
| R03905 | Anti-pattern — NO untyped output from any tool (output_schema mandatory) | 6490 | M00388 | non-negotiable | false | 10 |
| R03906 | Anti-pattern — NO untimed execution (max_time_ms mandatory) | 6489 | M00388 | non-negotiable | false | 10 |
| R03907 | Anti-pattern — NO un-audited tier transition (audit_flags must include trace) | 6535 | M00387 | non-negotiable | false | 10 |
| R03908 | Anti-pattern — NO tier promotion without operator-confirmed promotion ladder step | 6622–6624 | E0216 | non-negotiable | false | 10 |
| R03909 | Anti-pattern — NO direct host shell access from any AI-generated code (always through capability-shaped REPL) | 6404–6409 | E0210 | non-negotiable | false | 10 |
| R03910 | Composite — Execution substrate is how the workstation keeps its hands on the whole system while still letting it evolve | 6664 | E0217 | non-negotiable | false | 10 |

— End of M023 milestone file.
