"""Is grouped 2-bit viable FROM THE FP8 SOURCE? The gate for the whole 2-bit project.

Earlier test used the int4 container and got 26.6% error -- but that was int4->2bit DOUBLE
quantization, and group-wise scales showed zero gain because the container is already
per-row normalised. This uses the real FP8 source (128x128 block scales) so the comparison
is honest.

The decision rule: 2-bit is worth building ONLY if its error is close to what int4-per-row
(today's production container) already costs. If 2-bit is far worse, the project dies here.

Reference = fp32 dequantised from FP8 e4m3.
"""
import json
import struct

import numpy as np

SHARD = "fp8_shard.safetensors"
LAYER = 19
BLOCK = 128  # config: weight_block_size [128,128]


# ---- FP8 e4m3fn -> fp32 via a 256-entry LUT -------------------------------------
def e4m3_lut():
    lut = np.zeros(256, dtype=np.float32)
    for b in range(256):
        s = -1.0 if (b >> 7) else 1.0
        e = (b >> 3) & 0xF
        m = b & 0x7
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
        hdr = json.loads(f.read(n))
    base = 8 + n
    return hdr, base


def tensor(path, hdr, base, key):
    v = hdr[key]
    dt = {"F32": np.float32, "F8_E4M3": np.uint8, "BF16": np.uint16}[v["dtype"]]
    with open(path, "rb") as f:
        f.seek(base + v["data_offsets"][0])
        raw = f.read(v["data_offsets"][1] - v["data_offsets"][0])
    return np.frombuffer(raw, dtype=dt).reshape(v["shape"])


def dequant_fp8(q, sinv):
    """q: [R,C] uint8 e4m3 ; sinv: [R/128, C/128] fp32 block scales."""
    W = LUT[q].astype(np.float32)
    R, C = W.shape
    br, bc = sinv.shape
    S = np.repeat(np.repeat(sinv, BLOCK, axis=0), BLOCK, axis=1)[:R, :C]
    return W * S


# ---- quantizers -----------------------------------------------------------------
def q_per_row(W, bits):
    qmax = 2 ** (bits - 1) - 1
    s = np.abs(W).max(axis=1, keepdims=True) / max(qmax, 1)
    s = np.where(s == 0, 1e-12, s)
    return np.clip(np.rint(W / s), -qmax - 1, qmax) * s


def q_group(W, bits, gs):
    R, C = W.shape
    pad = (-C) % gs
    Wp = np.concatenate([W, np.zeros((R, pad), W.dtype)], axis=1) if pad else W
    G = Wp.reshape(R, -1, gs)
    qmax = 2 ** (bits - 1) - 1
    s = np.abs(G).max(axis=2, keepdims=True) / max(qmax, 1)
    s = np.where(s == 0, 1e-12, s)
    Q = np.clip(np.rint(G / s), -qmax - 1, qmax) * s
    return Q.reshape(R, -1)[:, :C]


def q_group_lloyd(W, bits, gs, iters=12):
    """Per-group Lloyd-Max (k-means on 2^bits levels) — a proper non-uniform codebook,
    the cheap stand-in for AQLM/QuIP#-class methods."""
    R, C = W.shape
    pad = (-C) % gs
    Wp = np.concatenate([W, np.zeros((R, pad), W.dtype)], axis=1) if pad else W
    G = Wp.reshape(-1, gs).astype(np.float32)
    K = 2 ** bits
    lo, hi = G.min(axis=1, keepdims=True), G.max(axis=1, keepdims=True)
    cb = lo + (hi - lo) * (np.arange(K, dtype=np.float32) + 0.5) / K   # [n, K]
    for _ in range(iters):
        d = np.abs(G[:, :, None] - cb[:, None, :])
        a = d.argmin(axis=2)
        for k in range(K):
            m = a == k
            cnt = m.sum(axis=1)
            sm = (G * m).sum(axis=1)
            cb[:, k] = np.where(cnt > 0, sm / np.maximum(cnt, 1), cb[:, k])
    d = np.abs(G[:, :, None] - cb[:, None, :])
    a = d.argmin(axis=2)
    Q = np.take_along_axis(cb, a, axis=1)
    return Q.reshape(R, -1)[:, :C]


hdr, base = load(SHARD)
eids = sorted({int(k.split(".experts.")[1].split(".")[0])
               for k in hdr if f".layers.{LAYER}.mlp.experts." in k and k.endswith("gate_proj.weight")})[:3]
print("=" * 92)
print(f"GROUPED 2-BIT FROM THE FP8 SOURCE — layer {LAYER}, gate_proj, experts {eids}")
print("=" * 92)

rng = np.random.default_rng(0)
x = rng.standard_normal(6144).astype(np.float32)
rows = []
for eid in eids:
    p = f"model.layers.{LAYER}.mlp.experts.{eid}.gate_proj"
    W = dequant_fp8(tensor(SHARD, hdr, base, p + ".weight"),
                    tensor(SHARD, hdr, base, p + ".weight_scale_inv"))
    ref = W @ x
    nref = np.linalg.norm(ref)
    scen = [
        ("int4 per-row  (TODAY'S CONTAINER)", q_per_row(W, 4), 4, 1),
        ("2-bit per-row (fmt=3 today)",       q_per_row(W, 2), 2, 1),
        ("2-bit group-128",                   q_group(W, 2, 128), 2, 128),
        ("2-bit group-64",                    q_group(W, 2, 64), 2, 64),
        ("2-bit group-32",                    q_group(W, 2, 32), 2, 32),
        ("2-bit group-64 Lloyd-Max",          q_group_lloyd(W, 2, 64), 2, 64),
        ("3-bit group-64",                    q_group(W, 3, 64), 3, 64),
    ]
    if eid == eids[0]:
        print(f"\n  {'scheme':<34} {'matvec rel-err':>15} {'MB/expert':>11} {'experts in VRAM':>16}")
    for name, Wq, bits, gs in scen:
        err = np.linalg.norm(Wq @ x - ref) / nref
        nsc = 2048 if gs == 1 else 2048 * (6144 // gs)
        mb = (3 * 2048 * 6144 * bits / 8 + 3 * nsc * 4) / 1e6
        nvram = int(119.24 * 1024 / mb)
        if eid == eids[0]:
            print(f"  {name:<34} {err:>15.4f} {mb:>11.2f} {min(nvram,19456):>16,}")
        rows.append((name, err))

print("\n" + "=" * 92)
print("MEAN over the 3 experts")
print("=" * 92)
agg = {}
for n, e in rows:
    agg.setdefault(n, []).append(e)
base_err = np.mean(agg["int4 per-row  (TODAY'S CONTAINER)"])
for n, v in agg.items():
    m = np.mean(v)
    print(f"  {n:<34} {m:.4f}   {'x%.2f vs production int4' % (m/base_err) if base_err>0 else ''}")
print()
print("  DECISION RULE: 2-bit is worth building only if its error is close to the int4")
print("  per-row row above — that is the quality the model ships with TODAY.")
