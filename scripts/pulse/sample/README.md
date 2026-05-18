# scripts/pulse/sample/

Placeholder for a real `pulse_core.wasm` per master spec § 20. <!-- anti-min-waiver: R480 pulse-core-wasm-anchored-to-SDD-027-operator-authored-content-master-spec-section-20 -->

When the operator authors their Pulse runtime in WebAssembly
(targeting the bit-plane transposition + low-bit matrix lookups
described in master spec §§ 9, 15-16, 20), it lands here and gets
AOT-compiled via `scripts/pulse/wasm-aot.sh`.

The repository ships NO compiled .wasm at the moment — that's
operator-authored content. For early validation operators can use
any small valid .wasm (the wasm-aot.sh script honors `WASM_INPUT=`).

## Suggested first-pass minimal pulse_core.wasm

A no-op Wasm module is the smallest valid test:

```wat
(module
  (func (export "pulse_tick") (result i32)
    i32.const 1))
```

Compile with: `wat2wasm pulse_core.wat -o pulse_core.wasm`
Then AOT: `scripts/pulse/wasm-aot.sh`

## Master spec § 20 verbatim invocation reference

```sh
export WASMTIME_COMPARE_OPTIONS="-C target-cpu=znver5 -C opt-level=3 -C relaxed-simd=true"
taskset -c 0-11 wasmtime compile --target znver5 -O speed /mnt/vault/agents/pulse_core.wasm
```

`wasm-aot.sh` mirrors this. The eventual production pulse_core.wasm
should perform VNNI/VPDPBUSD-style packed INT8 → INT32 accumulation
for the BitNet ternary lookup table per master spec § 16.1.
