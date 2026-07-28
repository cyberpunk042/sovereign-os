#!/usr/bin/env python3
"""vq-quantize-experts — SDD-403 phase 2: offline VQ pipeline for a MoE expert bank.

Builds a shared, precomputed codebook + fixed-width index stream from an FP8
checkpoint, so experts shrink enough to become VRAM-resident. The expensive fit is
offline; the online decode is one table lookup (ChromoFold P9: build != query).

Why VQ and not the lanes already measured negative (see SDD-403):
  - block-Huffman  33x slower to decode  (variable-length codes serialise)
  - per-group Lloyd 18.87 MB == int4      (per-group codebooks cost what they save)
  - scalar 2-bit    4.4x worse than int4  (scalar is information-starved at 2 bits)
VQ shares none of those: fixed-width index, per-tensor codebook, and it beats scalar
at equal rate.

Over the SDD-403 prototype this adds three things, none of which need calibration data:
  1. k-means++ init          — the prototype seeded randomly and landed in poor local minima
  2. residual (2-stage) VQ   — stage 2 quantises what stage 1 could not represent
  3. per-group normalisation — optional, folds scale out before the codebook sees the data

Activation-aware weighting (the AWQ/GPTQ lever) is stubbed behind --calib and is the
main remaining quality headroom; see the note at `weighted_fit`.

READ-ONLY on inputs. Pure numpy. No GPU.

  vq-quantize-experts.py --shard <fp8.safetensors> --layer 19 --report
  vq-quantize-experts.py --shard <fp8.safetensors> --layer 19 --d 4 --k 256 --stages 2
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
import time

import numpy as np

EXIT_OFFLINE = 3


# ----------------------------------------------------------------- fp8 e4m3 -> fp32
def _e4m3_lut() -> np.ndarray:
    lut = np.zeros(256, dtype=np.float32)
    for b in range(256):
        s = -1.0 if (b >> 7) else 1.0
        e, m = (b >> 3) & 0xF, b & 0x7
        if e == 0:
            v = (m / 8.0) * (2.0 ** -6)
        elif e == 0xF and m == 0x7:
            v = np.nan
        else:
            v = (1.0 + m / 8.0) * (2.0 ** (e - 7))
        lut[b] = s * v
    return lut


LUT = _e4m3_lut()


def read_header(path):
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        return json.loads(f.read(n)), 8 + n


def read_tensor(path, hdr, base, key):
    v = hdr[key]
    dt = {"F32": np.float32, "F8_E4M3": np.uint8}[v["dtype"]]
    with open(path, "rb") as f:
        f.seek(base + v["data_offsets"][0])
        raw = f.read(v["data_offsets"][1] - v["data_offsets"][0])
    return np.frombuffer(raw, dtype=dt).reshape(v["shape"])


def dequant_fp8(q, sinv, block=128):
    W = LUT[q].astype(np.float32)
    R, C = W.shape
    S = np.repeat(np.repeat(sinv, block, axis=0), block, axis=1)[:R, :C]
    return W * S


# ----------------------------------------------------------------- VQ core
def assign(X, C, chunk=500_000):
    """argmin_k ||x - c_k||^2, via matmul (||x||^2 is constant per row)."""
    cn = (C * C).sum(1)
    out = np.empty(len(X), dtype=np.int32)
    for s in range(0, len(X), chunk):
        b = X[s:s + chunk]
        out[s:s + chunk] = (cn[None, :] - 2.0 * (b @ C.T)).argmin(1)
    return out


def kmeanspp_init(X, K, rng):
    """k-means++ seeding. The prototype used a random subset and landed in poor
    local minima; ++ spreads the initial centres by squared distance."""
    C = np.empty((K, X.shape[1]), dtype=np.float32)
    C[0] = X[rng.integers(len(X))]
    d2 = ((X - C[0]) ** 2).sum(1)
    for k in range(1, K):
        tot = d2.sum()
        if not np.isfinite(tot) or tot <= 0:
            C[k] = X[rng.integers(len(X))]
        else:
            C[k] = X[np.searchsorted(np.cumsum(d2 / tot), rng.random())]
        d2 = np.minimum(d2, ((X - C[k]) ** 2).sum(1))
    return C


def fit_codebook(X, K, iters, rng):
    C = kmeanspp_init(X, K, rng)
    for _ in range(iters):
        idx = assign(X, C)
        for k in range(K):
            m = idx == k
            if m.any():
                C[k] = X[m].mean(0)
            else:                                  # revive a dead centre on the worst point
                C[k] = X[rng.integers(len(X))]
    return C


def weighted_fit(X, K, iters, rng, calib=None):
    """Fit a codebook, optionally in an activation-weighted metric.

    NOTE (the remaining quality headroom): minimising ||W - W'||^2 is NOT the goal --
    the goal is minimising ||(W - W')x||^2 over real activations x. Scaling each
    dimension by sqrt(E[x_j^2]) before the fit makes plain Euclidean k-means minimise
    the weighted objective, which is the AWQ/GPTQ insight. `calib` is that per-column
    RMS vector. Without it the fit is unweighted, which is what SDD-403's floor
    numbers used. Capturing real activations needs the model running and is phase 2b.
    """
    if calib is None:
        return fit_codebook(X, K, iters, rng), None
    w = np.asarray(calib, dtype=np.float32)
    w = np.maximum(w, 1e-8)
    C = fit_codebook(X * w[None, :], K, iters, rng)
    return C / w[None, :], w


def vq_encode(W, d, K, stages=1, group=0, iters=15, fit_n=200_000, seed=0, calib=None):
    """Residual VQ. `K` may be an int (same K each stage) or a per-stage list --
    asymmetric stages (a coarse refinement after a fine one) buy accuracy far more
    cheaply than doubling K, which is what fills in the 2-4 b/w frontier.

    Returns (reconstruction, codebooks, indices, bits/weight)."""
    Ks = list(K) if isinstance(K, (list, tuple)) else [K] * stages
    stages = len(Ks)
    R, C = W.shape
    flat = W.reshape(-1).astype(np.float32)
    scales = None
    if group:
        g = flat.reshape(-1, group)
        scales = np.abs(g).max(axis=1, keepdims=True)
        scales[scales == 0] = 1e-12
        flat = (g / scales).reshape(-1)

    V = np.ascontiguousarray(flat.reshape(-1, d))
    rng = np.random.default_rng(seed)
    resid = V.copy()
    books, idxs = [], []
    for Ki in Ks:
        sub = resid[rng.choice(len(resid), min(fit_n, len(resid)), replace=False)]
        CB, _ = weighted_fit(sub, Ki, iters, rng, calib)
        ix = assign(resid, CB)
        resid = resid - CB[ix]                     # stage n+1 fits what stage n missed
        books.append(CB)
        idxs.append(ix)

    Q = np.zeros_like(V)
    for CB, ix in zip(books, idxs):
        Q += CB[ix]
    Q = Q.reshape(-1)
    if group:
        Q = (Q.reshape(-1, group) * scales).reshape(-1)
    bw = sum(np.log2(k) for k in Ks) / d + (32.0 / group if group else 0.0)
    return Q.reshape(R, C), books, idxs, bw


def mb_per_expert(d, K, stages, group):
    Ks = list(K) if isinstance(K, (list, tuple)) else [K] * stages
    n = 3 * 2048 * 6144                            # gate + up + down
    payload = n / d * sum(np.log2(k) for k in Ks) / 8
    cbook = 3 * sum(k * d * 4 for k in Ks)
    sc = (n / group * 4) if group else 0
    return (payload + cbook + sc) / 1e6


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--shard", required=True, help="FP8 safetensors shard")
    ap.add_argument("--layer", type=int, default=19)
    ap.add_argument("--role", default="gate_proj")
    ap.add_argument("--experts", type=int, default=1)
    ap.add_argument("--d", type=int, default=4)
    ap.add_argument("--k", type=int, default=256)
    ap.add_argument("--stages", type=int, default=1)
    ap.add_argument("--group", type=int, default=0)
    ap.add_argument("--iters", type=int, default=15)
    ap.add_argument("--report", action="store_true",
                    help="sweep the configurations SDD-403 tabulates")
    a = ap.parse_args()

    try:
        hdr, base = read_header(a.shard)
    except OSError as e:
        print(f"cannot read {a.shard}: {e} — nothing to quantise (honest-degrade)")
        return EXIT_OFFLINE

    eids = sorted({int(k.split(".experts.")[1].split(".")[0])
                   for k in hdr if f".layers.{a.layer}.mlp.experts." in k
                   and k.endswith(f"{a.role}.weight")})[:a.experts]
    if not eids:
        print(f"no {a.role} experts for layer {a.layer} in this shard")
        return EXIT_OFFLINE

    rng = np.random.default_rng(0)
    x = rng.standard_normal(6144).astype(np.float32)

    # Frontier sweep: find the SMALLEST size that still matches production int4
    # quality. Asymmetric stages (fine then coarse) fill in the 2-4 b/w range that
    # doubling K cannot reach.
    configs = ([(4, 256,           1, 0),    # 2.00 b/w
                (4, [256, 4],      2, 0),    # 2.50
                (4, [256, 16],     2, 0),    # 3.00
                (4, [256, 64],     2, 0),    # 3.50
                (4, [256, 256],    2, 0),    # 4.00
                (2, [16, 4],       2, 0),    # 3.00
                (6, [256, 256],    2, 0)]    # 2.67
               if a.report else [(a.d, a.k, a.stages, a.group)])

    print("=" * 88)
    print(f"SDD-403 phase 2 — offline VQ  (layer {a.layer} {a.role}, {len(eids)} expert(s))")
    print("=" * 88)
    print(f"\n  {'config':<34} {'b/w':>5} {'err':>8} {'MB/exp':>8} {'inVRAM':>8} "
          f"{'vs int4':>8} {'fit s':>7}")

    for eid in eids:
        p = f"model.layers.{a.layer}.mlp.experts.{eid}.{a.role}"
        W = dequant_fp8(read_tensor(a.shard, hdr, base, p + ".weight"),
                        read_tensor(a.shard, hdr, base, p + ".weight_scale_inv"))
        ref = W @ x
        nref = np.linalg.norm(ref)

        s = np.abs(W).max(axis=1, keepdims=True) / 7
        Wq = np.clip(np.rint(W / s), -8, 7) * s
        b_err = float(np.linalg.norm(Wq @ x - ref) / nref)
        b_mb = (3 * 2048 * 6144 * 4 / 8 + 3 * 2048 * 4) / 1e6
        print(f"  {'int4 per-row (PRODUCTION)':<34} {4.0:>5.2f} {b_err:>8.4f} {b_mb:>8.2f} "
              f"{min(int(119.24 * 1024 / b_mb), 19456):>8,} {1.0:>7.2f}x {'-':>7}")

        for d, K, st, grp in configs:
            t0 = time.perf_counter()
            Wv, books, _, bw = vq_encode(W, d, K, st, grp, a.iters, seed=eid)
            dt = time.perf_counter() - t0
            err = float(np.linalg.norm(Wv @ x - ref) / nref)
            mb = mb_per_expert(d, K, st, grp)
            name = f"VQ d={d} K={K} x{st}" + (f" +g{grp}" if grp else "")
            print(f"  {name:<34} {bw:>5.2f} {err:>8.4f} {mb:>8.2f} "
                  f"{min(int(119.24 * 1024 / mb), 19456):>8,} {err / b_err:>7.2f}x {dt:>7.1f}")

    print("\n  Bar: err near the int4 row at materially less than 18.90 MB.")
    print("  Gate (SDD-403 phase 3): weight error is NOT model quality — an end-to-end")
    print("  eval against the int4 reference decides, and can still kill the lane.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
