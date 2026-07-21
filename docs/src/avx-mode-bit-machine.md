# The AVX-mode bit-machine

The `avx-mode` switch chooses **how the box uses AVX-512**. It is one master
control with four modes, each backed by real, tested, live-verified code. This
page is the map: what each mode is, which milestones / crates / routes / panel
surfaces stand behind it, and the honest boundaries.

The switch is the hot-swappable state file `/etc/sovereign-os/avx-mode.active`
(override `SOVEREIGN_OS_AVX_MODE_STATE`). The daemon **reads it per request** —
write the file, the next request sees the new mode, no restart. Set it with
`sovereign-osctl avx-mode set <mode>`.

## The four modes

| Mode | What it is | Backed by | Kernels |
|------|-----------|-----------|---------|
| **custom** | The M002/M007/M008 **bit-machine** — a packed control word per branch, policy becomes bits, one masked AVX-512 op routes 8 branches at once | M002 · M007 · M008 | real |
| **builtin** | Stock AVX-512 **math** — VNNI INT8, BF16, the three-tier kernels | M085 · M086 | real |
| **hybrid** | Both — the bit-machine routes, the math tiers compute | M002 · M007 · M008 · M085 · M086 | real |
| **off** | Scalar baseline — the portable path, any x86-64 | sovereign-cpu-dispatch | real |

`avx-mode.runs_bit_machine()` is true only for **custom** and **hybrid**: the
M002 bit-machine is opt-in, so the honest default `builtin` and `off` do not run
it. This is the gate the `/v1/control-word/round` route reads.

## What backs `custom` — the M002/M007/M008 bit-machine

**M002 — control-word injected logic.** A 64-bit control word per branch
(mode/event/intensity/cooldown/neighborhood/paramA/paramB, R00180) whose bits
gate execution. The round engine evolves 8 lanes through a 5-step round over a
strong ZMM layout (state/memory/rule/random).

- Crates: [`sovereign-control-word`](https://docs.rs) (the word + M00013 layout +
  M00104 branch permissions), `sovereign-simd::round` (the AVX-512 round kernel,
  bit-identical to scalar), `sovereign-control-word-service` (DNA fingerprints,
  quarantine, replay, metrics, OTLP export, ZFS/CRIU persistence backend).
- CLI: `scripts/hardware/control-word.py`, `scripts/hardware/simd-round.py`,
  `scripts/hardware/control-word-service.py`.
- Routes: `POST /v1/control-word/round`, `GET /v1/control-word/config`.
- Config knobs (opt-in, hot-swap): `SOVEREIGN_CTRL_*` env vars — overflow mode,
  rule-word width, LUT condition width, masked-op mode, per-lane DNA.

**M007 — the 8-step branch loop.** Spawn → Retrieve → Draft → Filter → Verify →
Act → Commit → Learn, over a Structure-of-Arrays batch of 8 branches. v2 consumes
the M008 building blocks: bloom memory recall, the branch predictor (learns
across ticks with a `session_id`), the two-level rule table, and microcode.

- Crate: `sovereign-branch-scheduler`.
- Routes: `POST /v1/branch-scheduler/tick`, `POST /v1/branch-scheduler/tick-v2`.

**M008 — the 13 bit-level cheats.** AVX-512 instructions as AI control
infrastructure. The SIMD half is in `sovereign-simd::cheats`; the policy/logic
half in `sovereign-bit-cheats`.

| Cheat | Where |
|-------|-------|
| M00114 VPTERNLOG fuse-policy | `sovereign-simd::cheats::fuse_policy` |
| M00115 k-mask routing | `sovereign-simd::cheats::routing_planes` |
| M00116 VPCOMPRESS pack | `sovereign-simd::cheats::compress_survivors` |
| M00117 token-law bitset | `sovereign-simd::cheats::token_law_combine` |
| M00120 speculative accept | `sovereign-simd::cheats::speculative_accept` |
| M00122 bloom overlap (VPOPCNTQ) | `sovereign-simd::cheats::bloom_overlap` |
| M00123 SIMD FSM | `sovereign-simd::cheats::fsm_step` |
| M00125 filter cascade | `sovereign-simd::cheats::filter_cascade` |
| M00113 bitfields-as-microcode | `sovereign-bit-cheats::decode_microcode` |
| M00119 two-level rule table | `sovereign-bit-cheats::TwoLevelTable` |
| M00121 branch predictor | `sovereign-bit-cheats::BranchPredictor` |
| M00126 three-representation | `sovereign-bit-cheats::ThreeRep` |

- Routes: `POST /v1/token-law/allowed-mask`, `POST /v1/microcode/decode`.

## What backs `builtin`/`hybrid` — the M085/M086 math tiers

**M085** named three AVX-512 math tiers; **M086** is the SIMD lift of each scalar
reference (`sovereign-vnni`, `sovereign-bitops`) into a real `std::arch` kernel in
`sovereign-simd::lift`, dispatched by detected capability, differential-tested
against the scalar oracle.

| Tier | Kernel | Flag |
|------|--------|------|
| T1 | `dot_i8` — VPDPBUSD INT8 dot | `avx512vnni` |
| T1 | `dot_bf16` — VDPBF16PS BF16 dot | `avx512bf16` |
| T2 | `attention_mask_fuse` — VPTERNLOG fuse | `avx512f` |

- Routes: `POST /v1/math/dot-i8`, `POST /v1/math/attention-fuse`.

## Panel

The `/avx-modes` cockpit page carries the interactive surfaces for all of the
above — the control-word bit inspector, the permission gate, the 9 M002
dashboards, the M007/M008 cheat surfaces, and the M085/M086 math tiers — each
computing live from the same logic as the Rust kernels (parity-locked).

## Verify it live

`scripts/verify/control-word-daemon.sh` builds and runs the real
`sovereign-gatewayd --http` binary and asserts every route over a real socket —
including the avx-mode hot-swap (write the state file, the next request sees it).
Requires cargo + curl + python3.

## Compatibility

The `avx-mode` switch is under the ⚖ compat registry (`config/compatibility.yaml`)
— which is itself the M002 "policy becomes bits" pattern applied at the
OS-config layer: `scripts/operator/compat.py` compiles every declared option to
a stable bit in a u64 universe, pick-one exclusivity is an AND-mask per group
(avx-mode `custom|builtin|hybrid|off` is one such group), and rule checks are
`(word >> bit) & 1` membership tests — the same shift-and-AND primitive as the
M00017 LUT.

What gates this switch today:

- **C008** (warn) — inference-tier **pulse** conflicts with avx-mode **off**:
  Pulse is the CPU/AVX-512 bitnet.cpp tier; the scalar baseline starves it.
- **C011** (suggest) — the **ultra-sovereign-efficiency** runtime profile leans
  on the CPU's AVX-512 engine; avx-mode **off** drops it to scalar.
- **Pick-one exclusivity** — the four modes are mutually exclusive by
  construction (the u64 group mask); the ⚖ pane's drill-in shows it.

Enforcement is layered: `sovereign-osctl avx-mode set <mode>` runs the compat
precheck before executing (force refuses with reason + remediation;
`SOVEREIGN_OS_COMPAT_OVERRIDE=1` is the audited override), the exec-rail
`POST /api/control/execute` applies the same pre-change gate, and the panel
selects grey force-incompatible options with the rule as tooltip.

## Honest boundaries

- **The kernels are real and live-verified; deep inference integration is the
  remaining downstream step.** Flipping `avx-mode` gates the control-word round
  engine on/off (the `/v1/control-word/round` route honors it), and every kernel
  runs and is tested. Wiring the bit-machine into the daemon's *per-token model
  routing* is the next integration, not built here.
- **VNNI/BF16 AVX execution is CPU-gated.** The M086 SIMD paths compile
  everywhere but only *run* on a host carrying `avx512vnni` / `avx512bf16`; the
  CI/SAIN-01 baseline lacks them, so those paths are scalar-verified against the
  oracle there (M086's documented P4 contract). The T2 VPTERNLOG kernel uses only
  `avx512f` and is genuinely exercised on CI.
- **Persistence + tracing are shapes, not OS integrations.** The replay ledger
  serializes to JSON and the persistence backend detects + builds the exact
  `zfs snapshot` / `criu dump` argv, but their *execution* is host-gated; OTLP
  export emits valid payloads without a live collector wired.
- **The predictor session store is in-process.** Cross-request learning works
  within one daemon; a distributed store would be the multi-node step.
