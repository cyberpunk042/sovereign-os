#!/usr/bin/env python3
"""vq-expert-block-error — SDD-403 phase 3a: error through a WHOLE expert block.

Everything measured so far is single-matmul error on `gate_proj`. That is not the
quantity that matters. A routed expert computes

    y = down_proj( silu(gate_proj(x)) * up_proj(x) )

so quantisation error passes through a nonlinearity and a second matmul, where it can
amplify (SiLU is expansive around its knee) or cancel (the gate/up product is a
difference of correlated errors). Single-matmul error cannot tell you which.

This quantises all THREE matrices of an expert with the same VQ config and measures the
error of the block output vs an fp32 reference — the closest honest proxy to model
quality that does not require the model running.

WHY NOT THE REAL THING: SDD-403's phase 3 (end-to-end eval in Colibri) needs Colibri to
LOAD vq weights, which needs the fmt=5 format — that is phase 4. The SDD had these in
the wrong order. This is the strongest gate available before that lands.

READ-ONLY. Pure numpy. No GPU.

  vq-expert-block-error.py --shard <fp8.safetensors> --layer 19 [--calib <int4-container>]
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys

import numpy as np

_here = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("vqq", _here / "vq-quantize-experts.py")
_vqq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_vqq)

EXIT_OFFLINE = 3


def silu(v):
    return v / (1.0 + np.exp(-v))


def expert_forward(x, Wg, Wu, Wd):
    return (silu(Wg @ x) * (Wu @ x)) @ Wd.T


def int4_per_row(W):
    s = np.abs(W).max(axis=1, keepdims=True) / 7
    s = np.where(s == 0, 1e-12, s)
    return np.clip(np.rint(W / s), -8, 7) * s


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--shard", required=True)
    ap.add_argument("--layer", type=int, default=19)
    ap.add_argument("--experts", type=int, default=2)
    ap.add_argument("--tokens", type=int, default=64)
    ap.add_argument("--calib", metavar="CONTAINER")
    ap.add_argument("--iters", type=int, default=15)
    a = ap.parse_args()

    try:
        hdr, base = _vqq.read_header(a.shard)
    except OSError as e:
        print(f"cannot read {a.shard}: {e} (honest-degrade)")
        return EXIT_OFFLINE

    eids = sorted({int(k.split(".experts.")[1].split(".")[0])
                   for k in hdr if f".layers.{a.layer}.mlp.experts." in k
                   and k.endswith("gate_proj.weight")})[:a.experts]
    if not eids:
        print(f"no experts for layer {a.layer} in this shard")
        return EXIT_OFFLINE

    calib = _vqq.load_calib(a.calib, a.layer) if a.calib else None
    rng = np.random.default_rng(0)

    configs = [("int4 per-row (PRODUCTION)", None),
               ("VQ d=4 K=[256,256] x2", (4, [256, 256], 2, 0)),
               ("VQ d=4 K=[256,64]  x2", (4, [256, 64], 2, 0)),
               ("VQ d=4 K=[256,16]  x2", (4, [256, 16], 2, 0)),
               ("VQ d=4 K=[256,4]   x2", (4, [256, 4], 2, 0)),
               ("VQ d=4 K=256       x1", (4, 256, 1, 0))]

    print("=" * 90)
    print(f"SDD-403 phase 3a — WHOLE-EXPERT-BLOCK error (layer {a.layer}, "
          f"{len(eids)} experts, {a.tokens} tokens)")
    print("=" * 90)
    print("\n  y = down( silu(gate(x)) * up(x) )   — error vs fp32, relative Frobenius\n")
    print(f"  {'config':<28} {'matmul err':>11} {'BLOCK err':>11} {'amplify':>9} {'MB/exp':>8}")

    acc = {}
    for eid in eids:
        p = f"model.layers.{a.layer}.mlp.experts.{eid}"
        mats = {}
        for role in ("gate_proj", "up_proj", "down_proj"):
            mats[role] = _vqq.dequant_fp8(
                _vqq.read_tensor(a.shard, hdr, base, f"{p}.{role}.weight"),
                _vqq.read_tensor(a.shard, hdr, base, f"{p}.{role}.weight_scale_inv"))
        Wg, Wu, Wd = mats["gate_proj"], mats["up_proj"], mats["down_proj"]

        # realistic-ish token batch: unit-variance, scaled by the layernorm gain if known
        X = rng.standard_normal((a.tokens, Wg.shape[1])).astype(np.float32)
        if calib is not None:
            X = X * calib[None, :]
        ref = np.stack([expert_forward(x, Wg, Wu, Wd) for x in X])
        nref = np.linalg.norm(ref)

        for name, cfg in configs:
            if cfg is None:
                qg, qu, qd = int4_per_row(Wg), int4_per_row(Wu), int4_per_row(Wd)
                mb = (3 * 2048 * 6144 * 4 / 8 + 3 * 2048 * 4) / 1e6
            else:
                d, K, st, grp = cfg
                qg = _vqq.vq_encode(Wg, d, K, st, grp, a.iters, seed=eid, calib=calib)[0]
                qu = _vqq.vq_encode(Wu, d, K, st, grp, a.iters, seed=eid + 1, calib=calib)[0]
                qd = _vqq.vq_encode(Wd, d, K, st, grp, a.iters, seed=eid + 2, calib=None)[0]
                mb = _vqq.mb_per_expert(d, K, st, grp)
            mm = float(np.linalg.norm((qg - Wg) @ X[0]) / np.linalg.norm(Wg @ X[0]))
            out = np.stack([expert_forward(x, qg, qu, qd) for x in X])
            blk = float(np.linalg.norm(out - ref) / nref)
            acc.setdefault(name, []).append((mm, blk, mb))

    for name, v in acc.items():
        mm = np.mean([a_ for a_, _, _ in v])
        blk = np.mean([b for _, b, _ in v])
        mb = v[0][2]
        print(f"  {name:<28} {mm:>11.4f} {blk:>11.4f} {blk / mm:>8.2f}x {mb:>8.2f}")

    print("\n  amplify > 1 means the nonlinearity + second matmul MAGNIFY quantisation error;")
    print("  < 1 means gate/up errors partly cancel in the product. This is the number that")
    print("  should drive the operating-point choice, not the single-matmul column.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
