# SDD-027 — Pulse algorithmic foundation: ternary + AVX-512 (Round 164)

> Status: **review**
> Owner: cyberpunk042
> Last updated: 2026-05-16
> Derived from: master spec § 15 (The Low-Bit Paradigm) + § 16
> (Hardware Fusion: Ternary Logic to 512-Bit Data Path) + Block 7
> Modules-1 anchor ("bit-plane transposition" verbatim operator framing);
> R152 (`scripts/pulse/build-bitnet.sh`) + R153 (`scripts/pulse/wasm-aot.sh`)
> implement the runtime; this SDD codifies the WHY.

## Problem

Master spec §§ 15-16 are content-dense theoretical sections that the
operator needs to **understand** to operate sovereign-os intelligently:

- Why are weights ternary (`{-1, 0, +1}`)? Why log₂(3) ≈ 1.585 bits?
- Why does multiplication go away?
- Why must the build script use `-march=znver5` with `-mavx512vnni
  -mavx512bf16 -mavx512vl`? Why not generic `-mavx2`?
- Why bit-plane transposition + lookup tables instead of dense GEMM?

The runtime side is already materialized:
- `scripts/pulse/build-bitnet.sh` (R152) compiles `bitnet.cpp` with the
  exact znver5 + AVX-512 flag stack.
- `scripts/pulse/wasm-aot.sh` (R153) AOT-compiles WebAssembly with the
  same znver5 target.

But operators reading those scripts see flags without the algorithmic
context. This SDD bridges that — and a tiny **reference** Python
module (`scripts/pulse/lib/ternary_lut.py`) lets operators step through
the algorithm interactively without needing the C++ toolchain.

## Decision: codify algorithmic invariants + ship a reference module

### Master spec § 15 invariants (operator-readable)

1. **Ternary state set.** Every linear-projection weight is one of
   `{-1, 0, +1}`. Three states → log₂(3) ≈ 1.585 bits theoretical
   minimum; packed at 2 bits/parameter in RAM for byte alignment.

2. **Multiplication elimination.** Forward pass for one accumulator
   element `acc` over weights `W` and activations `a`:

   ```
   for i:
       if W[i] == +1: acc += a[i]    # add
       if W[i] == -1: acc -= a[i]    # sub
       if W[i] ==  0: pass           # no-op
   ```

   No floating-point multiplication. Shifts the bottleneck from FPU
   throughput to **memory bandwidth + instruction pipeline**.

3. **Performance profile.** Operator target: 5-12 tokens/sec on
   sain-01 hardware at 1.58-bit precision, host CPU only, GPUs idle
   (the bitnet.cpp path).

### Master spec § 16 invariants

1. **Single-cycle AVX-512 on Zen 5.** Ryzen 9 9900X exposes true
   512-bit-wide ZMM registers. Legacy Zen 4 double-pumps two 256-bit
   units to emulate 512-bit; Zen 5 does not. This is why the master
   spec demands the 9900X specifically.

2. **SIMD packing density per cycle.**
   - 64× INT8 activations per ZMM register, OR
   - 128× 4-bit packed activation snippets (BitNet v2 quantization).

3. **VPDPBUSD / VNNI fast path.** AVX-512 VNNI's
   `VPDPBUSD` instruction multiplies packed INT8 by packed INT8
   (treating ternary as ±1 INT8) and accumulates into INT32 in a
   fraction of a cycle. This is the load-bearing instruction; the
   build script's `-mavx512vnni` flag is what enables the compiler to
   emit it.

4. **Bit-plane transposition.** Instead of fetching one weight at a
   time, the algorithm fetches a 64-element bit-plane: bit 0 of every
   weight in a 64-wide tile, then bit 1, etc. With 2-bit packed
   ternary, two bit-planes give the full sign + non-zero mask. SIMD
   processes 64 weights in parallel per ZMM register pass.

### Reference module

`scripts/pulse/lib/ternary_lut.py` — a **documentation-grade** Python
implementation:

- `pack_ternary(weights: List[int]) -> bytes` — pack `{-1, 0, +1}` into
  2 bits/parameter (00=zero, 01=plus_one, 10=minus_one).
- `unpack_ternary(packed: bytes, n: int) -> List[int]` — inverse.
- `bit_plane_transpose(packed: bytes, tile: int = 64) -> List[bytes]`
  — emit two bit-planes (sign + non-zero mask) for a 64-element tile.
- `accumulate(weights: List[int], acts: List[int]) -> int` — the
  multiplication-free dot-product per master spec § 15.1.

NOT production code. NOT a hot path. The real fast path is bitnet.cpp
+ AVX-512 VNNI native code. This module exists so operators can:
- step through the algorithm in a REPL
- verify `accumulate(weights, acts) == sum(w*a for w,a in zip(...))`
  on small inputs (round-trip correctness)
- understand why bit-plane transposition is a non-trivial layout
  transform vs naive AoS

Layer 2 unit tests (`tests/unit/test_ternary_lut.py`) lock in:
- pack/unpack roundtrip
- bit-plane transpose preserves information
- accumulate equals naive integer reference for random ternary +
  random INT8 inputs

### What this SDD is NOT

- Not a re-implementation of bitnet.cpp. Operators run bitnet.cpp.
- Not a benchmark suite. Real performance is measured on hardware.
- Not a kernel selector. The kernel and AVX-512 flags are set in
  R152 build-bitnet.sh.

## References

- master spec § 15 (verbatim)
- master spec § 16 (verbatim) + §§ 15.1, 16.1
- master spec Block 7 Module 1 (The Pulse — "bit-plane transposition"
  operator phrasing preserved)
- scripts/pulse/build-bitnet.sh (R152 — compile flags)
- scripts/pulse/wasm-aot.sh (R153 — AOT target = znver5)
- profiles/runtime/{ultra-sovereign-efficiency,high-concurrency-burst}.yaml
  (R150 — pulse-tier core_mask + model bindings)
