"""Shared-codebook VQ, fast version. ||x-c||^2 = ||x||^2 - 2 x.c + ||c||^2 -> one matmul.

Same question as vq_precompute.py: can a PRECOMPUTED codebook shared across the tensor
hit production-int4 accuracy at ~half the bytes, with a FIXED-WIDTH (fast) decode?
"""
import json
import struct
import sys
import time

import numpy as np

SHARD = "fp8_shard.safetensors"
LAYER = 19
BLOCK = 128


def log(*a):
    print(*a, flush=True)


def e4m3_lut():
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


LUT = e4m3_lut()


def load(path):
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        return json.loads(f.read(n)), 8 + n


def tensor(path, hdr, base, key):
    v = hdr[key]
    dt = {"F32": np.float32, "F8_E4M3": np.uint8}[v["dtype"]]
    with open(path, "rb") as f:
        f.seek(base + v["data_offsets"][0])
        raw = f.read(v["data_offsets"][1] - v["data_offsets"][0])
    return np.frombuffer(raw, dtype=dt).reshape(v["shape"])


def dequant_fp8(q, sinv):
    W = LUT[q].astype(np.float32)
    R, C = W.shape
    S = np.repeat(np.repeat(sinv, BLOCK, axis=0), BLOCK, axis=1)[:R, :C]
    return W * S


def assign(X, C, chunk=500_000):
    """argmin_k ||x - c_k||^2 via matmul."""
    cn = (C * C).sum(1)
    out = np.empty(len(X), dtype=np.int32)
    for s in range(0, len(X), chunk):
        b = X[s:s + chunk]
        d = cn[None, :] - 2.0 * (b @ C.T)          # ||x||^2 is constant per row
        out[s:s + chunk] = d.argmin(1)
    return out


def kmeans(X, K, iters=15, seed=0):
    r = np.random.default_rng(seed)
    C = X[r.choice(len(X), K, replace=False)].astype(np.float32).copy()
    for _ in range(iters):
        idx = assign(X, C)
        for k in range(K):
            m = idx == k
            if m.any():
                C[k] = X[m].mean(0)
    return C


def vq(W, d, K, group=0, fit_n=200_000, seed=0):
    R, C = W.shape
    flat = W.reshape(-1).astype(np.float32)
    sc = None
    if group:
        g = flat.reshape(-1, group)
        sc = np.abs(g).max(axis=1, keepdims=True)
        sc[sc == 0] = 1e-12
        flat = (g / sc).reshape(-1)
    V = np.ascontiguousarray(flat.reshape(-1, d))
    r = np.random.default_rng(seed)
    sub = V[r.choice(len(V), min(fit_n, len(V)), replace=False)]
    CB = kmeans(sub, K, seed=seed)                 # OFFLINE precompute
    Q = CB[assign(V, CB)].reshape(-1)              # ONLINE: one table lookup
    if group:
        Q = (Q.reshape(-1, group) * sc).reshape(-1)
    return Q.reshape(R, C)


def mb_per_expert(d, K, group):
    n = 3 * 2048 * 6144
    payload = n / d * np.log2(K) / 8
    cbook = 3 * K * d * 4
    scales = (n / group * 4) if group else 0
    return (payload + cbook + scales) / 1e6


hdr, base = load(SHARD)
eid = sorted({int(k.split(".experts.")[1].split(".")[0])
              for k in hdr if f".layers.{LAYER}.mlp.experts." in k
              and k.endswith("gate_proj.weight")})[0]
p = f"model.layers.{LAYER}.mlp.experts.{eid}.gate_proj"
W = dequant_fp8(tensor(SHARD, hdr, base, p + ".weight"),
                tensor(SHARD, hdr, base, p + ".weight_scale_inv"))
x = np.random.default_rng(0).standard_normal(6144).astype(np.float32)
ref = W @ x
nref = np.linalg.norm(ref)

log("=" * 92)
log(f"SHARED-CODEBOOK VQ — real FP8 weights, layer {LAYER} expert {eid} gate_proj [2048x6144]")
log("=" * 92)

# production baseline
s = np.abs(W).max(axis=1, keepdims=True) / 7
Wq = np.clip(np.rint(W / s), -8, 7) * s
base_err = float(np.linalg.norm(Wq @ x - ref) / nref)
base_mb = (3 * 2048 * 6144 * 4 / 8 + 3 * 2048 * 4) / 1e6
log(f"\n  {'scheme':<34} {'b/w':>5} {'err':>8} {'MB/exp':>8} {'inVRAM':>8} {'vs int4':>8}  {'fit s':>6}")
log(f"  {'int4 per-row (PRODUCTION)':<34} {4.0:>5.2f} {base_err:>8.4f} {base_mb:>8.2f} "
    f"{min(int(119.24*1024/base_mb),19456):>8,} {1.0:>7.2f}x {'-':>6}")

for name, d, K, grp in [
    ("VQ d=4 K=256",              4,  256, 0),
    ("VQ d=2 K=16",               2,   16, 0),
    ("VQ d=8 K=256",              8,  256, 0),
    ("VQ d=4 K=256 +group128",    4,  256, 128),
    ("VQ d=2 K=256 +group128",    2,  256, 128),
    ("VQ d=4 K=1024 +group128",   4, 1024, 128),
]:
    t = time.perf_counter()
    Wv = vq(W, d, K, grp, seed=eid)
    dt = time.perf_counter() - t
    err = float(np.linalg.norm(Wv @ x - ref) / nref)
    mb = mb_per_expert(d, K, grp)
    bw = np.log2(K) / d + (32.0 / grp if grp else 0.0)
    log(f"  {name:<34} {bw:>5.2f} {err:>8.4f} {mb:>8.2f} "
        f"{min(int(119.24*1024/mb),19456):>8,} {err/base_err:>7.2f}x {dt:>6.1f}")

log("\n  Bar to clear: err near 0.1631 at MUCH less than 18.90 MB.")
log("  14,192 experts in VRAM => 98.6% of routings on GPU (81.6% today).")
