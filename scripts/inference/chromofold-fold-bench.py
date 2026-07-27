#!/usr/bin/env python3
"""chromofold-fold-bench — measure ChromoFold fold techniques against a REAL MoE expert bank.

SDD-400/401/402 size the ChromoFold weight fold from ChromoFold's own *synthetic* benches, which
disagree by 3x (`bench_fold_cost` 3.68x vs `bench_model_fold` 1.21x) purely because they assume
different inter-expert similarity. ChromoFold's own `bench_model_fold` docstring concedes the gap:
"a real model (a true expert bank from the venv) is the SAIN/venv-gated follow-on."

This is that follow-on. It measures, on a real quantized MoE container:

  heat     routing-heat concentration from Colibri's .coli_usage (is a hot set pinnable?)
  entropy  the M6 block-Huffman lane: H0/H1 of the int4 symbol stream + the block-size trade
  group    the M20/M21 lane: grouped-delta across experts, index-aligned AND permutation-aligned
  rank     within-expert low-rank structure (SVD spectrum)

READ-ONLY. Pure numpy (+ ChromoFold's Warp prototype for the `group` mode). No GPU, no CUDA, no
libchromofold. Honest-degrades when the model or the Warp checkout is absent.

Usage:
    chromofold-fold-bench.py --model /nvme/glm52_i4 --mode all
    chromofold-fold-bench.py --model /nvme/glm52_i4 --mode entropy --layers 7,19,30,60

Measured on SAIN-01 / ai-workstation 2026-07-27 against GLM-5.2 int4 (per-row scales):
    entropy  2.9619 b/w aggregate over 201M weights -> 1.350x lossless (358 GB -> 266 GB)
    group    0.99x vs baseline in every configuration -> the grouping lane does not pay
See docs/evaluations/chromofold-fold-measurement-glm52-2026-07-27.md.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import struct
import sys
from collections import defaultdict

import numpy as np

K = 16  # int4 alphabet
EXIT_OFFLINE = 3


# ----------------------------------------------------------------- container access (read-only)
def index_layer(model_dir: str, layer: int) -> dict:
    """Map expert tensor-name -> (file, byte-lo, byte-hi). Reads safetensors headers only."""
    idx = {}
    for f in sorted(glob.glob(os.path.join(model_dir, "out-*.safetensors"))):
        with open(f, "rb") as fh:
            n = struct.unpack("<Q", fh.read(8))[0]
            hdr = json.loads(fh.read(n))
        base = 8 + n
        for k, v in hdr.items():
            if k == "__metadata__" or f".layers.{layer}.mlp.experts." not in k:
                continue
            idx[k] = (f, base + v["data_offsets"][0], base + v["data_offsets"][1])
    return idx


def _read(idx: dict, key: str, dtype=np.uint8) -> np.ndarray:
    f, lo, hi = idx[key]
    with open(f, "rb") as fh:
        fh.seek(lo)
        return np.frombuffer(fh.read(hi - lo), dtype=dtype)


def nibbles(idx: dict, layer: int, eid: int, role: str) -> np.ndarray:
    """Unpack the U8-packed int4 payload to one uint8 symbol (0..15) per weight."""
    p = _read(idx, f"model.layers.{layer}.mlp.experts.{eid}.{role}.weight")
    out = np.empty(p.size * 2, dtype=np.uint8)
    out[0::2] = p & 0x0F
    out[1::2] = p >> 4
    return out


def row_scales(idx: dict, layer: int, eid: int, role: str) -> np.ndarray:
    return _read(idx, f"model.layers.{layer}.mlp.experts.{eid}.{role}.weight.qs", np.float32)


# ----------------------------------------------------------------- entropy (the M6 lane)
def h0(sym: np.ndarray) -> float:
    c = np.bincount(sym, minlength=K).astype(np.float64)
    p = c[c > 0] / c.sum()
    return float(-(p * np.log2(p)).sum())


def h1(sym: np.ndarray) -> float:
    """Order-1 conditional entropy H(x_t | x_{t-1}) — is there sequential context to exploit?"""
    a, b = sym[:-1].astype(np.int64), sym[1:].astype(np.int64)
    j = np.bincount(a * K + b, minlength=K * K).astype(np.float64).reshape(K, K)
    tot, acc = j.sum(), 0.0
    for i in range(K):
        s = j[i].sum()
        if s > 0:
            p = j[i][j[i] > 0] / s
            acc += (s / tot) * float(-(p * np.log2(p)).sum())
    return acc


def mode_entropy(model: str, layers, roles, experts, bank_gb: float) -> None:
    print("=" * 78)
    print("ENTROPY — the M6 block-Huffman lane (cf_bh_decode_at / cf_fused_matmul_async)")
    print("=" * 78)
    print(f"  {'layer':>6} {'role':>11} {'expert':>7} {'H0 b/w':>9} {'H1 b/w':>9} {'ratio':>8}")
    tot_bits = tot_n = 0
    for layer in layers:
        idx = index_layer(model, layer)
        if not idx:
            print(f"  layer {layer}: no expert tensors found — skipping")
            continue
        for role in roles:
            for eid in experts:
                s = nibbles(idx, layer, eid, role)
                a, b = h0(s), h1(s)
                tot_bits += a * s.size
                tot_n += s.size
                print(f"  {layer:>6} {role:>11} {eid:>7} {a:>9.4f} {b:>9.4f} {4 / a:>7.3f}x")
    if not tot_n:
        return
    agg = tot_bits / tot_n
    print(f"\n  AGGREGATE over {tot_n / 1e6:.0f}M weights: {agg:.4f} b/w -> {4 / agg:.3f}x lossless")
    print(f"  H1 == H0 => no sequential context; a STATIC canonical Huffman table hits the floor.")

    print(f"\n  block-size trade (one shared lut + 32-bit block_off per block):")
    print(f"  {'block':>8} {'b/w':>9} {'ratio':>8}   random-access granularity")
    for blk in (64, 128, 256, 512, 1024, 4096, 16384):
        r = agg + 32.0 / blk
        print(f"  {blk:>8} {r:>9.4f} {4 / r:>7.3f}x   {blk} weights")
    print(f"\n  NOTE: small blocks are counterproductive — the block_off index eats the win.")
    print(f"        With PER-BLOCK tables (64 bits each) block=64 goes below 1.0x (expansion).")
    print(f"\n  residency: {bank_gb:.0f} GB bank -> {bank_gb * agg / 4:.1f} GB at H0 "
          f"(block=4096: {bank_gb * (agg + 32.0 / 4096) / 4:.1f} GB)")


# ----------------------------------------------------------------- grouping (the M20/M21 lane)
def mode_group(model: str, layer: int, role: str, n_members: int, warp_root: str) -> None:
    print("=" * 78)
    print("GROUP — the M20 grouped-delta / M21 super-elastic lane")
    print("=" * 78)
    sys.path.insert(0, warp_root)
    try:
        from warp_compress import grouped_delta as gd
    except ImportError:
        print(f"  Warp prototype not resident at {warp_root} — grouping mode offline (honest-degrade).")
        print(f"  Set WARP_ROOT or pass --warp-root. Exit {EXIT_OFFLINE}.")
        sys.exit(EXIT_OFFLINE)

    idx = index_layer(model, layer)
    grp = np.stack([nibbles(idx, layer, e, role) for e in range(n_members)])
    ref = gd.build_reference(grp, mode="centroid")
    d = np.abs(grp.astype(np.int64) - ref.astype(np.int64)).mean()
    native, base = grp.size / 2, gd.baseline_bytes(grp)
    m20 = gd.encoded_bytes(gd.compress(grp, rank=None))
    print(f"  layer {layer} {role}, {n_members} experts, {grp.shape[1]:,} values each")
    print(f"    mean|Δ| vs centroid            {d:.3f} of 15 levels ({100 * d / 15:.1f}% of range)")
    print(f"    resident int4 (packed)         {native / 1e6:9.2f} MB   1.00x")
    print(f"    baseline (per-member entropy)  {base / 1e6:9.2f} MB   {native / base:5.2f}x")
    print(f"    M20 grouped-delta (lossless)   {m20 / 1e6:9.2f} MB   {native / m20:5.2f}x"
          f"   vs-baseline {base / m20:5.2f}x")

    a = grp[0].astype(np.int64)
    b = grp[1].astype(np.int64)
    print(f"\n    cross-expert corrcoef          {np.corrcoef(a, b)[0, 1]:+.4f}"
          f"   (0 => nothing for grouping to remove)")
    print(f"    verdict: {'PAYS' if base / m20 > 1.05 else 'DOES NOT PAY'} — grouping is worth "
          f"{base / m20:.2f}x over coding each expert alone.")


def mode_permutation(model: str, layer: int, role: str, warp_root: str) -> None:
    """MoE experts are permutation-symmetric in the intermediate dim — index-aligned correlation
    cannot see similarity hiding under a row permutation. This is the strongest form of the
    grouping hypothesis; test it against the correct null."""
    print("=" * 78)
    print("PERMUTATION — cross-expert similarity under optimal row alignment")
    print("=" * 78)
    idx = index_layer(model, layer)
    rng = np.random.default_rng(7)
    sigs = {}
    rows = None
    proj = None
    for e in (0, 1):
        v = nibbles(idx, layer, e, role).astype(np.float32)
        qs = row_scales(idx, layer, e, role)
        rows = qs.size
        m = ((v.reshape(rows, -1) - 8.0) * qs[:, None])
        if proj is None:
            proj = rng.standard_normal((m.shape[1], 24)).astype(np.float32)
        s = m @ proj
        sigs[e] = s / (np.linalg.norm(s, axis=1, keepdims=True) + 1e-9)

    best = (sigs[0] @ sigs[1].T).max(axis=1)
    rand = rng.standard_normal((rows, 24)).astype(np.float32)
    rand /= np.linalg.norm(rand, axis=1, keepdims=True)
    null = (sigs[0] @ rand.T).max(axis=1)
    print(f"  {rows} rows, 24-dim random-projection signature")
    print(f"    mean best-match cosine         {best.mean():+.4f}")
    print(f"    RANDOM-vector null             {null.mean():+.4f}")
    print(f"    frac rows matched > 0.9        {(best > 0.9).mean():.4f}")
    print(f"\n    verdict: {'ALIGNMENT FOUND' if best.mean() > null.mean() + 0.05 else 'NO ALIGNMENT'}"
          f" — the real number must sit far above the null to mean anything.")


def mode_rank(model: str, layer: int, role: str) -> None:
    print("=" * 78)
    print("RANK — within-expert low-rank structure (a fold needing no cross-expert similarity)")
    print("=" * 78)
    idx = index_layer(model, layer)
    qs = row_scales(idx, layer, 0, role)
    rows = qs.size
    m = ((nibbles(idx, layer, 0, role).astype(np.float32).reshape(rows, -1) - 8.0) * qs[:, None])
    m = m[:, :rows]
    sv = np.linalg.svd(m, compute_uv=False)
    en = np.cumsum(sv**2) / (sv**2).sum()
    print(f"  SVD of a {m.shape} dequantized slice:")
    for k in (16, 64, 128, 256, 512, 1024):
        if k <= len(en):
            print(f"    top {k:>4} of {len(sv)} singular values hold {100 * en[k - 1]:5.2f}% of energy")
    eff = int(np.searchsorted(en, 0.95)) + 1
    print(f"  effective rank (95% energy)  {eff} of {len(sv)}"
          f"   (random gaussian needs ~{int(0.95 * len(sv))})")
    print(f"  verdict: {'LOW-RANK' if eff < len(sv) // 4 else 'NOT LOW-RANK'} — a rank-r fold "
          f"costs 2*n*r; it only pays when r << n/2.")


# ----------------------------------------------------------------- routing heat
def mode_heat(model: str) -> None:
    path = os.path.join(model, ".coli_usage")
    print("=" * 78)
    print("HEAT — routing concentration (is there a pinnable hot set?)")
    print("=" * 78)
    if not os.path.exists(path):
        print(f"  {path} absent — no engine has run against this container yet. Offline.")
        return
    h = defaultdict(dict)
    for line in open(path):
        q = line.split()
        if len(q) == 3:
            h[int(q[0])][int(q[1])] = int(q[2])
    counts = np.array([c for lay in h.values() for c in lay.values()], dtype=np.int64)
    total = counts.sum()
    slots = len(h) * 256
    print(f"  layers seen {len(h)} · experts touched {counts.size} of {slots} "
          f"({100 * counts.size / slots:.1f}%) · {total:,} routings")
    cum = np.cumsum(np.sort(counts)[::-1]) / total
    for pct in (1, 10, 20, 50):
        k = max(1, counts.size * pct // 100)
        print(f"    top {pct:>2}% of touched experts carry {100 * cum[k - 1]:5.1f}% of routings")
    for tgt in (0.80, 0.90):
        k = int(np.searchsorted(cum, tgt)) + 1
        print(f"    {int(tgt * 100)}% of routings needs {k:>6} experts (~{k * 18.9 / 1024:.1f} GB int4)")
    print(f"\n  verdict: a hot set is pinnable only if a small expert count covers most routings.")


# ----------------------------------------------------------------- entry
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", default=os.environ.get("COLI_MODEL", "/nvme/glm52_i4"))
    ap.add_argument("--mode", default="all",
                    choices=["all", "heat", "entropy", "group", "permutation", "rank"])
    ap.add_argument("--layers", default="7,19,30,60")
    ap.add_argument("--roles", default="gate_proj,down_proj")
    ap.add_argument("--experts", default="0,128")
    ap.add_argument("--members", type=int, default=24)
    ap.add_argument("--bank-gb", type=float, default=358.0)
    ap.add_argument("--warp-root", default=os.environ.get(
        "WARP_ROOT", os.path.expanduser("~/warp-solar-system-shaders")))
    a = ap.parse_args()

    if not os.path.isdir(a.model) or not glob.glob(os.path.join(a.model, "out-*.safetensors")):
        print(f"model container not resident at {a.model} — nothing to measure (honest-degrade).")
        sys.exit(EXIT_OFFLINE)

    layers = [int(x) for x in a.layers.split(",")]
    roles = a.roles.split(",")
    experts = [int(x) for x in a.experts.split(",")]

    if a.mode in ("all", "heat"):
        mode_heat(a.model)
        print()
    if a.mode in ("all", "entropy"):
        mode_entropy(a.model, layers, roles, experts, a.bank_gb)
        print()
    if a.mode in ("all", "group"):
        mode_group(a.model, layers[0], roles[0], a.members, a.warp_root)
        print()
    if a.mode in ("all", "permutation"):
        mode_permutation(a.model, layers[0], roles[0], a.warp_root)
        print()
    if a.mode in ("all", "rank"):
        mode_rank(a.model, layers[0], roles[0])


if __name__ == "__main__":
    main()
