# M014 — Isolation and trust boundaries

> Parent: `backlog/milestones/INDEX.md` row M014 (dump 3370–3678).
> Source: `raw/dumps/2026-05-18-the-ultimate-exploitation-of-the-tech-stack-AVX-plus-plus.md` lines 3370–3678.
> All entries below are extracted from the dump line range. No invention.

> **AVX++ canon update — 2026-05-19**: this milestone is affected by backward-sweep redefinition(s) — Authority Levels 0..6 (ADDITIVE) + Trust Rings 0..4 (ADDITIVE). See sovereign-os M061 for canonical pinning (commit 6f07dca). R-rows below are interpreted under the canonical later definitions per operator standing direction "layered: new direction ON TOP OF prior direction — never discarded".


## Epics (E0116–E0125)

| Epic ID | Phrase | Dump line |
|---|---|---|
| E0116 | Isolation and trust boundaries — security architecture, not convenience | 3385–3388 |
| E0117 | Substrate — VFIO + IOMMU DMA remap / QEMU VirtIO / virtio-vsock / Kata Containers / Firecracker microVMs | 3389–3395 |
| E0118 | The Principle — four trust zones | 3397–3417 |
| E0119 | 4090 As Isolation Boundary — quarantined cognition engine | 3419–3448 |
| E0120 | Communication Boundary — compact messages, not bulk tensors | 3450–3487 |
| E0121 | Capability Tokens — every request carries a 64-bit capability word | 3489–3526 |
| E0122 | Tool Sandboxes — 4-tier ladder A/B/C/D | 3528–3548 |
| E0123 | Filesystem Boundary — explicit exchange directories + import validation | 3550–3592 |
| E0124 | Network Boundary — controlled network profiles + per-branch ToolIntent | 3594–3620 |
| E0125 | Updated runtime law — six invariants + final architecture rollup | 3637–3676 |

## Modules (M00216–M00232)

| Mod ID | Phrase | Dump line | Parent epic |
|---|---|---|---|
| M00216 | Trust zone 0 — Host Control Plane (AVX-512 scheduler / policy engine / replay log / ZFS / observability) | 3404–3405 | E0118 |
| M00217 | Trust zone 1 — Oracle Plane (RTX PRO 6000, main inference, trusted-but-not-omnipotent) | 3407–3408 | E0118 |
| M00218 | Trust zone 2 — Scout/Sandbox Plane (RTX 4090 VM, draft models, experimental agents, risky code, web/tool trials) | 3410–3411 | E0118 |
| M00219 | Trust zone 3 — Disposable Tool Sandboxes (microVM/container-per-task) | 3413–3414 | E0118 |
| M00220 | 4090-VM workload — good list (draft generation / untrusted model experiments / web browsing agents / tool planning / safe file inspection / vision-OCR of unknown files / code execution attempts / dependency installs / speculative patch generation) | 3425–3435 | E0119 |
| M00221 | 4090-VM workload — bad list (sharing tensors / tight KV cooperation / layer-split / ultra-low-latency cross-GPU sync) | 3439–3443 | E0119 |
| M00222 | Host↔4090 channels — virtio-vsock / gRPC-over-vsock / Unix-socket-proxy / explicit-exchange shared-folder | 3457–3461 | E0120 |
| M00223 | Host↔4090 message types — DraftRequest / DraftResult / EmbeddingRequest / RerankResult / VisionResult / ToolPlan / RiskAssessment / PatchProposal | 3465–3474 | E0120 |
| M00224 | VM-propose / host-commit invariant — VM output = candidate; host AVX-512 = policy filter; oracle = verify; replay log = commit | 3478–3487 | E0120 |
| M00225 | Capability word — 64-bit bitfield (allowed_tools / fs_scope / network_scope / max_runtime / max_memory / output_type / trust_level / flags) | 3492–3502 | E0121 |
| M00226 | Capability enforcement layers — CPU policy / VM config / filesystem mounts / network namespace / tool wrapper / eBPF observation | 3517–3523 | E0121 |
| M00227 | Tool tier A — deterministic host tools (rg, parsers, formatters, read-only queries) | 3533–3534 | E0122 |
| M00228 | Tool tier B — controlled host tools (tests, builds, package managers, file edits) | 3536–3537 | E0122 |
| M00229 | Tool tier C — VM tools (risky dependency installs, unknown scripts, browser actions) | 3539–3540 | E0122 |
| M00230 | Tool tier D — disposable microVM (untrusted binaries, unknown archives, hostile inputs) | 3542–3543 | E0122 |
| M00231 | Filesystem exchange directories — `/ai-exchange/{inbox,outbox,artifacts}` + host import-validation pipeline (parse / scan / diff / policy-check / oracle-review-if-needed / commit) | 3554–3592 | E0123 |
| M00232 | Network-profile ladder — offline / package-registries / docs-web / arbitrary-web / authenticated-browser-profile — each maps to policy bits | 3600–3608 | E0124 |

## Features (F01106–F01190)

| F ID | Phrase | Dump line | Parent module | Category | Opt-in |
|---|---|---|---|---|---|
| F01106 | Toggle trust-zone enforcement (full / partial / advisory) | 3399–3401 | E0118 | mode | true |
| F01107 | Profile knob — `trust_zone_enforcement = full \| partial \| advisory` | 3399–3401 | E0118 | profile | true |
| F01108 | Env var `SOVEREIGN_TRUST_ZONE_ENFORCEMENT` | 3399–3401 | E0118 | env_var | true |
| F01109 | CLI `--trust-zone-enforcement <mode>` | 3399–3401 | E0118 | cli_verb | true |
| F01110 | Toggle 4090 isolation mode (vfio-vm / bare / disabled) | 3387, 3421 | E0119 | mode | true |
| F01111 | Profile knob — `gpu_4090_isolation = vfio_vm \| bare \| disabled` | 3387 | E0119 | profile | true |
| F01112 | Env var `SOVEREIGN_GPU_4090_ISOLATION` | 3387 | E0119 | env_var | true |
| F01113 | CLI `--gpu-4090-isolation <mode>` | 3387 | E0119 | cli_verb | true |
| F01114 | Toggle Host↔4090 channel backend (virtio-vsock / grpc-over-vsock / unix-socket-proxy) | 3457–3460 | M00222 | mode | true |
| F01115 | Profile knob — `host_to_4090_channel = vsock \| grpc_vsock \| unix_socket_proxy` | 3457–3460 | M00222 | profile | true |
| F01116 | Env var `SOVEREIGN_HOST_TO_4090_CHANNEL` | 3457–3460 | M00222 | env_var | true |
| F01117 | Host↔4090 message — `DraftRequest` schema | 3466 | M00223 | data_model | false |
| F01118 | Host↔4090 message — `DraftResult` schema | 3467 | M00223 | data_model | false |
| F01119 | Host↔4090 message — `EmbeddingRequest` schema | 3468 | M00223 | data_model | false |
| F01120 | Host↔4090 message — `RerankResult` schema | 3469 | M00223 | data_model | false |
| F01121 | Host↔4090 message — `VisionResult` schema | 3470 | M00223 | data_model | false |
| F01122 | Host↔4090 message — `ToolPlan` schema | 3471 | M00223 | data_model | false |
| F01123 | Host↔4090 message — `RiskAssessment` schema | 3472 | M00223 | data_model | false |
| F01124 | Host↔4090 message — `PatchProposal` schema | 3473 | M00223 | data_model | false |
| F01125 | API `POST /v1/4090/draft` | 3466 | M00223 | api_endpoint | true |
| F01126 | API `POST /v1/4090/embedding` | 3468 | M00223 | api_endpoint | true |
| F01127 | API `POST /v1/4090/rerank` | 3469 | M00223 | api_endpoint | true |
| F01128 | API `POST /v1/4090/vision` | 3470 | M00223 | api_endpoint | true |
| F01129 | API `POST /v1/4090/tool-plan` | 3471 | M00223 | api_endpoint | true |
| F01130 | API `POST /v1/4090/risk-assessment` | 3472 | M00223 | api_endpoint | true |
| F01131 | API `POST /v1/4090/patch-proposal` | 3473 | M00223 | api_endpoint | true |
| F01132 | Capability word — `bits 0..7 allowed_tools` | 3494 | M00225 | data_model | false |
| F01133 | Capability word — `bits 8..15 filesystem_scope` | 3495 | M00225 | data_model | false |
| F01134 | Capability word — `bits 16..23 network_scope` | 3496 | M00225 | data_model | false |
| F01135 | Capability word — `bits 24..31 max_runtime` | 3497 | M00225 | data_model | false |
| F01136 | Capability word — `bits 32..39 max_memory` | 3498 | M00225 | data_model | false |
| F01137 | Capability word — `bits 40..47 output_type` | 3499 | M00225 | data_model | false |
| F01138 | Capability word — `bits 48..55 trust_level` | 3500 | M00225 | data_model | false |
| F01139 | Capability word — `bits 56..63 flags` | 3501 | M00225 | data_model | false |
| F01140 | Capability enforcement layer — CPU policy | 3518 | M00226 | composite | false |
| F01141 | Capability enforcement layer — VM config | 3519 | M00226 | composite | false |
| F01142 | Capability enforcement layer — filesystem mounts | 3520 | M00226 | composite | false |
| F01143 | Capability enforcement layer — network namespace | 3521 | M00226 | composite | false |
| F01144 | Capability enforcement layer — tool wrapper | 3522 | M00226 | composite | false |
| F01145 | Capability enforcement layer — eBPF observation | 3523 | M00226 | composite | false |
| F01146 | Defense in depth — six enforcement layers compose | 3517–3525 | M00226 | composite | false |
| F01147 | Tool intent — `READ_REPO=1` operator-discoverable bit | 3510 | M00225 | composite | true |
| F01148 | Tool intent — `WRITE_REPO=0` operator-discoverable bit | 3511 | M00225 | composite | true |
| F01149 | Tool intent — `NETWORK=0` operator-discoverable bit | 3512 | M00225 | composite | true |
| F01150 | Tool intent — `SHELL=limited` operator-discoverable bit | 3513 | M00225 | composite | true |
| F01151 | Tool tier A registry — rg, parsers, formatters, read-only queries | 3533–3534 | M00227 | composite | false |
| F01152 | Tool tier B registry — tests, builds, package managers, file edits | 3536–3537 | M00228 | composite | false |
| F01153 | Tool tier C registry — risky dependency installs, unknown scripts, browser actions | 3539–3540 | M00229 | composite | false |
| F01154 | Tool tier D registry — untrusted binaries, unknown archives, hostile inputs | 3542–3543 | M00230 | composite | false |
| F01155 | Tier-assignment authority — model never chooses tier alone | 3546–3548 | E0122 | composite | false |
| F01156 | Tier-assignment authority — CPU decides tier | 3548 | E0122 | composite | false |
| F01157 | Exchange dir — `/ai-exchange/inbox` | 3555 | M00231 | composite | false |
| F01158 | Exchange dir — `/ai-exchange/outbox` | 3556 | M00231 | composite | false |
| F01159 | Exchange dir — `/ai-exchange/artifacts` | 3557 | M00231 | composite | false |
| F01160 | Import-validation stage — parse | 3566 | M00231 | composite | false |
| F01161 | Import-validation stage — scan | 3567 | M00231 | composite | false |
| F01162 | Import-validation stage — diff | 3568 | M00231 | composite | false |
| F01163 | Import-validation stage — policy-check | 3569 | M00231 | composite | false |
| F01164 | Import-validation stage — oracle-review if needed | 3570 | M00231 | composite | false |
| F01165 | Import-validation stage — commit | 3571 | M00231 | composite | false |
| F01166 | Patch-proposal field — unified diff | 3577 | F01124 | data_model | false |
| F01167 | Patch-proposal field — metadata | 3578 | F01124 | data_model | false |
| F01168 | Patch-proposal field — declared files touched | 3579 | F01124 | data_model | false |
| F01169 | Patch-proposal field — test notes | 3580 | F01124 | data_model | false |
| F01170 | Patch-proposal field — risk flags | 3581 | F01124 | data_model | false |
| F01171 | Host-apply gate — paths inside workspace | 3586 | M00231 | composite | false |
| F01172 | Host-apply gate — no forbidden files | 3587 | M00231 | composite | false |
| F01173 | Host-apply gate — diff parses | 3588 | M00231 | composite | false |
| F01174 | Host-apply gate — policy allows writes | 3589 | M00231 | composite | false |
| F01175 | Host-apply gate — branch budget permits | 3590 | M00231 | composite | false |
| F01176 | Host-apply gate — user approval if required | 3591 | M00231 | composite | true |
| F01177 | Network profile — offline | 3601 | M00232 | mode | true |
| F01178 | Network profile — allow package registries | 3602 | M00232 | mode | true |
| F01179 | Network profile — allow documentation web | 3603 | M00232 | mode | true |
| F01180 | Network profile — allow arbitrary web | 3604 | M00232 | mode | true |
| F01181 | Network profile — allow authenticated browser profile | 3605 | M00232 | mode | true |
| F01182 | `ToolIntent` schema — network_scope field | 3614 | M00232 | data_model | false |
| F01183 | `ToolIntent` schema — reason field | 3615 | M00232 | data_model | false |
| F01184 | `ToolIntent` schema — ttl field | 3616 | M00232 | data_model | false |
| F01185 | Network approval — CPU can approve / deny / ask user | 3620 | M00232 | composite | true |
| F01186 | Dashboard — trust-zone overview (zone 0 / 1 / 2 / 3 live state) | 3404–3414 | E0118 | dashboard | true |
| F01187 | Dashboard — 4090-VM channel throughput + message-type histogram | 3457–3474 | E0120 | dashboard | true |
| F01188 | Dashboard — capability-word inspector for a given branch | 3492–3502 | M00225 | dashboard | true |
| F01189 | Dashboard — tool tier assignment heatmap | 3530–3548 | E0122 | dashboard | true |
| F01190 | Dashboard — exchange-dir import pipeline status (per stage) | 3554–3592 | M00231 | dashboard | true |

## Requirements (R02211–R02380)

| R ID | Phrase | Dump line | Parent | Class | Opt-in | Sub-reqs |
|---|---|---|---|---|---|---|
| R02211 | 4090 + VFIO becomes a security architecture, not convenience | 3385–3388 | E0116 | non-negotiable | false | 10 |
| R02212 | VFIO exposes PCI devices directly to userspace/VMs using IOMMU DMA remapping | 3391 | E0117 | non-negotiable | false | 10 |
| R02213 | VFIO conceptual flow — guest driver → VFIO → IOMMU remap → hardware | 3391 | E0117 | non-negotiable | false | 10 |
| R02214 | QEMU recommends VirtIO devices as efficient paravirtual devices for VMs | 3392 | E0117 | non-negotiable | false | 10 |
| R02215 | virtio-vsock provides host/guest communication through normal socket-style APIs without normal networking | 3393 | M00222 | non-negotiable | false | 10 |
| R02216 | Kata Containers use lightweight VMs for container-like ergonomics with stronger hardware-virtualization isolation | 3394 | E0117 | non-negotiable | true | 10 |
| R02217 | Firecracker microVMs are designed for slim, isolated VM execution | 3395 | E0117 | non-negotiable | true | 10 |
| R02218 | Firecracker vsock mediates guest AF_VSOCK to host AF_UNIX sockets | 3395 | M00222 | non-negotiable | true | 10 |
| R02219 | Not all AI work deserves the same trust level | 3399 | E0118 | non-negotiable | false | 10 |
| R02220 | Trust zone 0 — Host Control Plane | 3404 | M00216 | non-negotiable | false | 10 |
| R02221 | Trust zone 0 includes AVX-512 scheduler | 3405 | M00216 | non-negotiable | false | 10 |
| R02222 | Trust zone 0 includes policy engine | 3405 | M00216 | non-negotiable | false | 10 |
| R02223 | Trust zone 0 includes replay log | 3405 | M00216 | non-negotiable | false | 10 |
| R02224 | Trust zone 0 includes ZFS | 3405 | M00216 | non-negotiable | false | 10 |
| R02225 | Trust zone 0 includes observability | 3405 | M00216 | non-negotiable | false | 10 |
| R02226 | Trust zone 1 — Oracle Plane (RTX PRO 6000) | 3407–3408 | M00217 | non-negotiable | false | 10 |
| R02227 | Trust zone 1 — main inference, trusted but not omnipotent | 3408 | M00217 | non-negotiable | false | 10 |
| R02228 | Trust zone 2 — Scout/Sandbox Plane (RTX 4090 VM) | 3410–3411 | M00218 | non-negotiable | false | 10 |
| R02229 | Trust zone 2 holds draft models | 3411 | M00218 | non-negotiable | false | 10 |
| R02230 | Trust zone 2 holds experimental agents | 3411 | M00218 | non-negotiable | false | 10 |
| R02231 | Trust zone 2 holds risky code | 3411 | M00218 | non-negotiable | false | 10 |
| R02232 | Trust zone 2 holds web/tool trials | 3411 | M00218 | non-negotiable | false | 10 |
| R02233 | Trust zone 3 — Disposable Tool Sandboxes (microVM/container per task) | 3413–3414 | M00219 | non-negotiable | false | 10 |
| R02234 | The host owns truth; the models do not | 3417 | E0118 | non-negotiable | false | 10 |
| R02235 | 4090 in VFIO VM is a quarantined cognition engine, not "slower second GPU" | 3421 | E0119 | non-negotiable | false | 10 |
| R02236 | 4090-VM workload — draft generation | 3426 | M00220 | non-negotiable | true | 10 |
| R02237 | 4090-VM workload — untrusted model experiments | 3427 | M00220 | non-negotiable | true | 10 |
| R02238 | 4090-VM workload — web browsing agents | 3428 | M00220 | non-negotiable | true | 10 |
| R02239 | 4090-VM workload — tool planning | 3429 | M00220 | non-negotiable | true | 10 |
| R02240 | 4090-VM workload — malware-ish file inspection in safe environments | 3430 | M00220 | non-negotiable | true | 10 |
| R02241 | 4090-VM workload — vision/OCR of unknown files | 3431 | M00220 | non-negotiable | true | 10 |
| R02242 | 4090-VM workload — code execution attempts | 3432 | M00220 | non-negotiable | true | 10 |
| R02243 | 4090-VM workload — dependency installs | 3433 | M00220 | non-negotiable | true | 10 |
| R02244 | 4090-VM workload — speculative patch generation | 3434 | M00220 | non-negotiable | true | 10 |
| R02245 | 4090-VM bad workload — sharing tensors with Blackwell | 3440 | M00221 | non-negotiable | false | 10 |
| R02246 | 4090-VM bad workload — tight KV-cache cooperation | 3441 | M00221 | non-negotiable | false | 10 |
| R02247 | 4090-VM bad workload — layer-split inference | 3442 | M00221 | non-negotiable | false | 10 |
| R02248 | 4090-VM bad workload — ultra-low latency cross-GPU sync | 3443 | M00221 | non-negotiable | false | 10 |
| R02249 | VFIO limits cooperation but buys trust separation | 3446 | E0119 | non-negotiable | false | 10 |
| R02250 | Excellent trade when 4090's role is scout/sandbox | 3448 | E0119 | non-negotiable | false | 10 |
| R02251 | Host↔4090 uses compact messages, not bulk tensors | 3452 | E0120 | non-negotiable | false | 10 |
| R02252 | Host↔4090 channel — virtio-vsock | 3458 | M00222 | non-negotiable | true | 10 |
| R02253 | Host↔4090 channel — gRPC over vsock | 3459 | M00222 | non-negotiable | true | 10 |
| R02254 | Host↔4090 channel — Unix socket proxy | 3460 | M00222 | non-negotiable | true | 10 |
| R02255 | Host↔4090 channel — shared folder only for explicit exchange dirs | 3461 | M00222 | non-negotiable | false | 10 |
| R02256 | Host↔4090 message — DraftRequest | 3466 | M00223 | non-negotiable | false | 10 |
| R02257 | Host↔4090 message — DraftResult | 3467 | M00223 | non-negotiable | false | 10 |
| R02258 | Host↔4090 message — EmbeddingRequest | 3468 | M00223 | non-negotiable | false | 10 |
| R02259 | Host↔4090 message — RerankResult | 3469 | M00223 | non-negotiable | false | 10 |
| R02260 | Host↔4090 message — VisionResult | 3470 | M00223 | non-negotiable | false | 10 |
| R02261 | Host↔4090 message — ToolPlan | 3471 | M00223 | non-negotiable | false | 10 |
| R02262 | Host↔4090 message — RiskAssessment | 3472 | M00223 | non-negotiable | false | 10 |
| R02263 | Host↔4090 message — PatchProposal | 3473 | M00223 | non-negotiable | false | 10 |
| R02264 | Never let the VM directly mutate host truth | 3476 | M00224 | non-negotiable | false | 10 |
| R02265 | VM proposes; host commits | 3478 | M00224 | non-negotiable | false | 10 |
| R02266 | VM output = candidate | 3481 | M00224 | non-negotiable | false | 10 |
| R02267 | Host AVX-512 policy = filter | 3482 | M00224 | non-negotiable | false | 10 |
| R02268 | Oracle = verify | 3483 | M00224 | non-negotiable | false | 10 |
| R02269 | Replay log = commit | 3484 | M00224 | non-negotiable | false | 10 |
| R02270 | Every request to the VM carries a capability word | 3491 | M00225 | non-negotiable | false | 10 |
| R02271 | Capability word — bits 0..7 allowed tools | 3494 | M00225 | non-negotiable | false | 10 |
| R02272 | Capability word — bits 8..15 filesystem scope | 3495 | M00225 | non-negotiable | false | 10 |
| R02273 | Capability word — bits 16..23 network scope | 3496 | M00225 | non-negotiable | false | 10 |
| R02274 | Capability word — bits 24..31 max runtime | 3497 | M00225 | non-negotiable | false | 10 |
| R02275 | Capability word — bits 32..39 max memory | 3498 | M00225 | non-negotiable | false | 10 |
| R02276 | Capability word — bits 40..47 output type | 3499 | M00225 | non-negotiable | false | 10 |
| R02277 | Capability word — bits 48..55 trust level | 3500 | M00225 | non-negotiable | false | 10 |
| R02278 | Capability word — bits 56..63 flags | 3501 | M00225 | non-negotiable | false | 10 |
| R02279 | The VM receives capabilities, not ambient authority | 3504 | M00225 | non-negotiable | false | 10 |
| R02280 | Capability example — READ_REPO=1 | 3510 | M00225 | non-negotiable | true | 10 |
| R02281 | Capability example — WRITE_REPO=0 | 3511 | M00225 | non-negotiable | true | 10 |
| R02282 | Capability example — NETWORK=0 | 3512 | M00225 | non-negotiable | true | 10 |
| R02283 | Capability example — SHELL=limited | 3513 | M00225 | non-negotiable | true | 10 |
| R02284 | Capability enforced at CPU policy layer | 3518 | M00226 | non-negotiable | false | 10 |
| R02285 | Capability enforced at VM config layer | 3519 | M00226 | non-negotiable | false | 10 |
| R02286 | Capability enforced at filesystem mount layer | 3520 | M00226 | non-negotiable | false | 10 |
| R02287 | Capability enforced at network namespace layer | 3521 | M00226 | non-negotiable | false | 10 |
| R02288 | Capability enforced at tool wrapper layer | 3522 | M00226 | non-negotiable | false | 10 |
| R02289 | Capability enforced at eBPF observation layer | 3523 | M00226 | non-negotiable | false | 10 |
| R02290 | Defense in depth — very senior, very boring, very necessary | 3526 | M00226 | non-negotiable | false | 10 |
| R02291 | Tool tier A — deterministic host tools (rg / parsers / formatters / read-only queries) | 3533–3534 | M00227 | non-negotiable | false | 10 |
| R02292 | Tool tier B — controlled host tools (tests / builds / package managers / file edits) | 3536–3537 | M00228 | non-negotiable | false | 10 |
| R02293 | Tool tier C — VM tools (risky dependency installs / unknown scripts / browser actions) | 3539–3540 | M00229 | non-negotiable | false | 10 |
| R02294 | Tool tier D — disposable microVM (untrusted binaries / unknown archives / hostile inputs) | 3542–3543 | M00230 | non-negotiable | false | 10 |
| R02295 | The model never chooses tier alone | 3546 | E0122 | non-negotiable | false | 10 |
| R02296 | The model emits intent | 3547 | E0122 | non-negotiable | false | 10 |
| R02297 | CPU decides tier | 3548 | E0122 | non-negotiable | false | 10 |
| R02298 | Exchange directory — `/ai-exchange/inbox` | 3555 | M00231 | non-negotiable | false | 10 |
| R02299 | Exchange directory — `/ai-exchange/outbox` | 3556 | M00231 | non-negotiable | false | 10 |
| R02300 | Exchange directory — `/ai-exchange/artifacts` | 3557 | M00231 | non-negotiable | false | 10 |
| R02301 | VM writes proposals, not final state | 3560 | M00231 | non-negotiable | false | 10 |
| R02302 | Host imports only after validation — parse | 3566 | M00231 | non-negotiable | false | 10 |
| R02303 | Host imports only after validation — scan | 3567 | M00231 | non-negotiable | false | 10 |
| R02304 | Host imports only after validation — diff | 3568 | M00231 | non-negotiable | false | 10 |
| R02305 | Host imports only after validation — policy-check | 3569 | M00231 | non-negotiable | false | 10 |
| R02306 | Host imports only after validation — oracle-review if needed | 3570 | M00231 | non-negotiable | true | 10 |
| R02307 | Host imports only after validation — commit | 3571 | M00231 | non-negotiable | false | 10 |
| R02308 | Patch proposal carries — unified diff | 3577 | F01124 | non-negotiable | false | 10 |
| R02309 | Patch proposal carries — metadata | 3578 | F01124 | non-negotiable | false | 10 |
| R02310 | Patch proposal carries — declared files touched | 3579 | F01124 | non-negotiable | false | 10 |
| R02311 | Patch proposal carries — test notes | 3580 | F01124 | non-negotiable | false | 10 |
| R02312 | Patch proposal carries — risk flags | 3581 | F01124 | non-negotiable | false | 10 |
| R02313 | Host applies patch only if paths inside workspace | 3586 | M00231 | non-negotiable | false | 10 |
| R02314 | Host applies patch only if no forbidden files | 3587 | M00231 | non-negotiable | false | 10 |
| R02315 | Host applies patch only if diff parses | 3588 | M00231 | non-negotiable | false | 10 |
| R02316 | Host applies patch only if policy allows writes | 3589 | M00231 | non-negotiable | false | 10 |
| R02317 | Host applies patch only if branch budget permits | 3590 | M00231 | non-negotiable | false | 10 |
| R02318 | Host applies patch only if user approval present when required | 3591 | M00231 | non-negotiable | true | 10 |
| R02319 | Network boundary matters | 3596 | E0124 | non-negotiable | false | 10 |
| R02320 | Network profile — offline | 3601 | M00232 | non-negotiable | true | 10 |
| R02321 | Network profile — allow package registries | 3602 | M00232 | non-negotiable | true | 10 |
| R02322 | Network profile — allow documentation web | 3603 | M00232 | non-negotiable | true | 10 |
| R02323 | Network profile — allow arbitrary web | 3604 | M00232 | non-negotiable | true | 10 |
| R02324 | Network profile — allow authenticated browser profile | 3605 | M00232 | non-negotiable | true | 10 |
| R02325 | Each network profile maps to policy bits | 3608 | M00232 | non-negotiable | false | 10 |
| R02326 | Branch requesting network produces a `ToolIntent` carrying network_scope | 3614 | M00232 | non-negotiable | false | 10 |
| R02327 | `ToolIntent` carries reason field | 3615 | M00232 | non-negotiable | false | 10 |
| R02328 | `ToolIntent` carries ttl field | 3616 | M00232 | non-negotiable | false | 10 |
| R02329 | CPU can approve a network ToolIntent | 3620 | M00232 | non-negotiable | false | 10 |
| R02330 | CPU can deny a network ToolIntent | 3620 | M00232 | non-negotiable | false | 10 |
| R02331 | CPU can ask user about a network ToolIntent | 3620 | M00232 | non-negotiable | true | 10 |
| R02332 | AI agents fail dangerously when authority is ambient | 3624 | E0125 | non-negotiable | false | 10 |
| R02333 | This architecture prevents ambient authority | 3626 | E0125 | non-negotiable | false | 10 |
| R02334 | AI can be creative in the sandbox | 3628 | E0125 | non-negotiable | false | 10 |
| R02335 | AI can be reckless where blast radius is tiny | 3628 | E0125 | non-negotiable | false | 10 |
| R02336 | Host remains deterministic | 3628 | E0125 | non-negotiable | false | 10 |
| R02337 | 4090's point — not just more tokens, more safe experimentation | 3633–3634 | E0119 | non-negotiable | false | 10 |
| R02338 | Updated runtime law #1 — No model has ambient write authority | 3642 | E0125 | non-negotiable | false | 10 |
| R02339 | Updated runtime law #2 — No sandbox output is trusted until host validation | 3643 | E0125 | non-negotiable | false | 10 |
| R02340 | Updated runtime law #3 — No network access without explicit capability bits | 3644 | E0125 | non-negotiable | false | 10 |
| R02341 | Updated runtime law #4 — No tool side effect without replay log entry | 3645 | E0125 | non-negotiable | false | 10 |
| R02342 | Updated runtime law #5 — No VM result bypasses policy/oracle commit | 3646 | E0125 | non-negotiable | false | 10 |
| R02343 | Updated runtime law #6 — Host owns memory, truth, and final state | 3647 | E0125 | non-negotiable | false | 10 |
| R02344 | Architecture — Blackwell Oracle = trusted high-quality inference | 3653–3654 | M00217 | non-negotiable | false | 10 |
| R02345 | Architecture — 4090 Sandbox = speculative, risky, exploratory inference | 3656–3657 | M00218 | non-negotiable | false | 10 |
| R02346 | Architecture — AVX-512 Host Runtime = policy, branch state, permissions, validation, commit | 3659–3660 | M00216 | non-negotiable | false | 10 |
| R02347 | Architecture — ZFS = snapshots, replay, rollback | 3662–3663 | M00216 | non-negotiable | false | 10 |
| R02348 | Architecture — eBPF/DCGM/OTel = observe side effects and resource behavior | 3665–3666 | M00216 | non-negotiable | false | 10 |
| R02349 | Architecture — VirtIO/vsock = compact controlled communication | 3668–3669 | M00222 | non-negotiable | false | 10 |
| R02350 | Limited-by-no-NVLink / separate-GPUs / VFIO-overhead becomes a strength | 3672 | E0125 | non-negotiable | false | 10 |
| R02351 | Building a local AI system with trust zones, deterministic commit, speculative cognition, hardware-enforced isolation | 3676 | E0125 | non-negotiable | false | 10 |
| R02352 | Trust-zone enforcement operator-overrideable (full / partial / advisory) | 3399–3401 | F01106 | non-negotiable | true | 10 |
| R02353 | 4090 isolation mode operator-overrideable (vfio_vm / bare / disabled) | 3387 | F01110 | non-negotiable | true | 10 |
| R02354 | Host↔4090 channel backend operator-overrideable (vsock / grpc_vsock / unix_socket_proxy) | 3457–3460 | F01114 | non-negotiable | true | 10 |
| R02355 | Env var `SOVEREIGN_TRUST_ZONE_ENFORCEMENT` | 3399–3401 | F01108 | non-negotiable | true | 10 |
| R02356 | Env var `SOVEREIGN_GPU_4090_ISOLATION` | 3387 | F01112 | non-negotiable | true | 10 |
| R02357 | Env var `SOVEREIGN_HOST_TO_4090_CHANNEL` | 3457–3460 | F01116 | non-negotiable | true | 10 |
| R02358 | CLI `--trust-zone-enforcement <mode>` | 3399–3401 | F01109 | non-negotiable | true | 10 |
| R02359 | CLI `--gpu-4090-isolation <mode>` | 3387 | F01113 | non-negotiable | true | 10 |
| R02360 | Dashboard — trust-zone overview (zone 0 / 1 / 2 / 3 live state) | 3404–3414 | F01186 | non-negotiable | true | 10 |
| R02361 | Dashboard — 4090-VM channel throughput + message-type histogram | 3457–3474 | F01187 | non-negotiable | true | 10 |
| R02362 | Dashboard — capability-word inspector for a given branch | 3492–3502 | F01188 | non-negotiable | true | 10 |
| R02363 | Dashboard — tool tier assignment heatmap | 3530–3548 | F01189 | non-negotiable | true | 10 |
| R02364 | Dashboard — exchange-dir import pipeline status (per stage) | 3554–3592 | F01190 | non-negotiable | true | 10 |
| R02365 | API `POST /v1/4090/draft` | 3466 | F01125 | non-negotiable | true | 10 |
| R02366 | API `POST /v1/4090/embedding` | 3468 | F01126 | non-negotiable | true | 10 |
| R02367 | API `POST /v1/4090/rerank` | 3469 | F01127 | non-negotiable | true | 10 |
| R02368 | API `POST /v1/4090/vision` | 3470 | F01128 | non-negotiable | true | 10 |
| R02369 | API `POST /v1/4090/tool-plan` | 3471 | F01129 | non-negotiable | true | 10 |
| R02370 | API `POST /v1/4090/risk-assessment` | 3472 | F01130 | non-negotiable | true | 10 |
| R02371 | API `POST /v1/4090/patch-proposal` | 3473 | F01131 | non-negotiable | true | 10 |
| R02372 | Test — capability word encodes / decodes round-trip across all 8 bitfields | 3494–3501 | M00225 | non-negotiable | false | 10 |
| R02373 | Test — defense-in-depth: blocking at any one of 6 enforcement layers prevents the action | 3517–3525 | M00226 | non-negotiable | false | 10 |
| R02374 | Test — tool-tier assignment refuses model-side tier selection | 3546–3548 | E0122 | non-negotiable | false | 10 |
| R02375 | Test — import-validation 6-stage pipeline rejects at correct stage for each failure type | 3565–3571 | M00231 | non-negotiable | false | 10 |
| R02376 | Test — host-apply refuses each forbidden path / file / diff / policy / budget / approval scenario | 3585–3591 | M00231 | non-negotiable | false | 10 |
| R02377 | Test — network-profile ladder enforces declared scope at runtime | 3600–3608 | M00232 | non-negotiable | false | 10 |
| R02378 | Test — `ToolIntent` round-trip preserves network_scope + reason + ttl | 3612–3617 | M00232 | non-negotiable | false | 10 |
| R02379 | Test — six runtime laws each have an enforcement assertion + a recorded violation in the test corpus | 3642–3647 | E0125 | non-negotiable | false | 10 |
| R02380 | Composite — trust-zone architecture rollup (zones + channels + capabilities + tiers + exchange + network) integrates with M013 observability + M012 storage + M011 KV + M009 DCR | 3650–3676 | E0125 | non-negotiable | false | 10 |

— End of M014 milestone file.
