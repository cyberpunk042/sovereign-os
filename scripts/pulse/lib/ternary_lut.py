"""Reference ternary-weight lookup primitives (SDD-027).

Master spec § 15-16 codified as readable Python so operators can step
through the algorithm interactively and reason about why bitnet.cpp +
AVX-512 VNNI is fast.

NOT a production kernel. NOT on the inference hot path. The real fast
path is `bitnet.cpp` compiled with `-march=znver5 -mavx512vnni
-mavx512bf16 -mavx512vl` (see `scripts/pulse/build-bitnet.sh`).

What this module IS:
  - A REPL-explorable implementation of the master spec's bit-plane
    transposition + accumulate algorithm
  - The reference correctness oracle for Layer 2 unit tests
  - Operator-facing documentation in code form (the manifest as
    runnable text)

Pack format (2 bits per ternary weight):
  00 → 0   (zero — no-op slot per master spec § 15.1)
  01 → +1  (add)
  10 → -1  (subtract)
  11 → reserved / invalid (raises ValueError)

Bit-planes (master spec § 16.1):
  For a tile of N weights packed at 2 bits each, two bit-planes
  emerge:
    plane_0: low bit of each weight (1 iff weight != 0)
    plane_1: high bit (1 iff weight == -1)
  AVX-512 VNNI on real hardware processes these planes 64 weights at
  a time; this module processes one element at a time but produces
  byte-equivalent output a hardware kernel could consume.

Master spec citations preserved verbatim:
  "If W_ij = +1, the corresponding activation element is simply added"
  "If W_ij = -1, the activation element is subtracted"
  "If W_ij = 0, the operation is treated as a No-Op and bypassed"
  — master spec § 15.1
"""

from __future__ import annotations

from typing import Iterable


_PACK = {0: 0b00, 1: 0b01, -1: 0b10}
_UNPACK = {0b00: 0, 0b01: 1, 0b10: -1}


def pack_ternary(weights: Iterable[int]) -> bytes:
    """Pack a sequence of ternary weights {-1, 0, +1} into 2 bits each.

    Output length: ceil(len(weights) / 4) bytes.
    Bit layout: weight[0] occupies bits 0-1 of byte 0; weight[1] in
    bits 2-3; weight[2] in 4-5; weight[3] in 6-7; weight[4] in bits
    0-1 of byte 1; etc. Little-bit-first within byte — operator-
    readable when dumped with `bin(byte)`.
    """
    out = bytearray()
    accum = 0
    bits = 0
    for w in weights:
        if w not in _PACK:
            raise ValueError(
                f"ternary weights must be -1, 0, or 1; got {w!r}"
            )
        accum |= _PACK[w] << bits
        bits += 2
        if bits == 8:
            out.append(accum)
            accum = 0
            bits = 0
    if bits != 0:
        out.append(accum)
    return bytes(out)


def unpack_ternary(packed: bytes, n: int) -> list[int]:
    """Inverse of pack_ternary. n = expected weight count.

    Raises ValueError if the reserved 11 bit-pattern is observed (a
    corrupt buffer or wrong format).
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    if (n + 3) // 4 > len(packed):
        raise ValueError(
            f"need {(n + 3) // 4} bytes for {n} weights; got {len(packed)}"
        )
    out: list[int] = []
    for i in range(n):
        byte = packed[i // 4]
        bits = (byte >> (2 * (i % 4))) & 0b11
        if bits not in _UNPACK:
            raise ValueError(
                f"invalid 2-bit pattern 0b{bits:02b} at weight index {i}"
            )
        out.append(_UNPACK[bits])
    return out


def bit_plane_transpose(packed: bytes, n: int) -> tuple[bytes, bytes]:
    """Emit (plane_nonzero, plane_negative) for n weights from packed buffer.

    plane_nonzero: bit i is 1 iff weight i is nonzero.
    plane_negative: bit i is 1 iff weight i is -1.

    The combination gives the operator the master spec § 15.1 decision
    triple:
      (nz=0, neg=0) → No-Op (skip)
      (nz=1, neg=0) → +1 add
      (nz=1, neg=1) → -1 subtract
      (nz=0, neg=1) → INVALID (corrupted packed buffer)
    """
    pn_bytes = bytearray((n + 7) // 8)
    pg_bytes = bytearray((n + 7) // 8)
    for i in range(n):
        byte = packed[i // 4]
        bits = (byte >> (2 * (i % 4))) & 0b11
        if bits == 0b11:
            raise ValueError(f"invalid 2-bit pattern at weight index {i}")
        # Packed encoding: 0b00 → 0, 0b01 → +1, 0b10 → -1.
        # plane_nonzero = (bits != 0); plane_negative = high-bit of pack.
        nz = 1 if bits != 0 else 0
        neg = (bits >> 1) & 0b01
        if nz:
            pn_bytes[i // 8] |= 1 << (i % 8)
        if neg:
            pg_bytes[i // 8] |= 1 << (i % 8)
    return bytes(pn_bytes), bytes(pg_bytes)


def accumulate(weights: list[int], activations: list[int]) -> int:
    """Master spec § 15.1 verbatim algorithm — multiplication-free dot product.

    Returns sum over i of (W_i op A_i) where op is add / sub / no-op
    determined by W_i ∈ {-1, 0, +1}.
    """
    if len(weights) != len(activations):
        raise ValueError(
            f"length mismatch: weights={len(weights)} activations={len(activations)}"
        )
    acc = 0
    for w, a in zip(weights, activations):
        if w == 1:
            acc += a
        elif w == -1:
            acc -= a
        elif w == 0:
            pass  # No-Op per master spec § 15.1
        else:
            raise ValueError(f"non-ternary weight: {w!r}")
    return acc


def accumulate_from_planes(
    plane_nonzero: bytes,
    plane_negative: bytes,
    activations: list[int],
) -> int:
    """Same as `accumulate` but consumes the bit-plane representation.

    This is the layout the AVX-512 VNNI / bitnet.cpp hot path consumes
    (modulo bit width). Useful for verifying round-trip correctness:

        plane_nz, plane_neg = bit_plane_transpose(packed, n)
        assert accumulate_from_planes(plane_nz, plane_neg, acts) \\
            == accumulate(unpack_ternary(packed, n), acts)
    """
    n = len(activations)
    acc = 0
    for i in range(n):
        nz = (plane_nonzero[i // 8] >> (i % 8)) & 1
        neg = (plane_negative[i // 8] >> (i % 8)) & 1
        if nz == 0:
            continue  # No-Op
        if neg:
            acc -= activations[i]
        else:
            acc += activations[i]
    return acc


__all__ = [
    "pack_ternary",
    "unpack_ternary",
    "bit_plane_transpose",
    "accumulate",
    "accumulate_from_planes",
]
