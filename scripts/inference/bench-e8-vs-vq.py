"""Is Colibri's EXISTING fmt=6 (E8/IQ3 lattice) as good as the VQ format SDD-403 proposes?

If yes, phase 4 collapses from "design fmt=7, write packer, loader, container changes,
CPU+CUDA kernels" down to "write ONE CUDA kernel for a codec that already exists, has a
CPU reference, and has tests" — colibri.c:294 says fmt=5/6 have no CUDA kernel and so
stay CPU-side, which is exactly the wrong side of our bottleneck.
"""
import importlib.util
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path.home() / "colibri" / "c" / "tools"))
import iq3_pack  # noqa: E402

_h = pathlib.Path.home() / "sovereign-os" / "scripts" / "inference"
_s = importlib.util.spec_from_file_location("vqq", _h / "vq-quantize-experts.py")
vqq = importlib.util.module_from_spec(_s)
_s.loader.exec_module(vqq)

SHARD = "fp8_shard.safetensors"
LAYER, EID = 19, 2

hdr, base = vqq.read_header(SHARD)
p = f"model.layers.{LAYER}.mlp.experts.{EID}.gate_proj"
W = vqq.dequant_fp8(vqq.read_tensor(SHARD, hdr, base, p + ".weight"),
                    vqq.read_tensor(SHARD, hdr, base, p + ".weight_scale_inv"))
rng = np.random.default_rng(0)
x = rng.standard_normal(W.shape[1]).astype(np.float32)
ref = W @ x
nref = np.linalg.norm(ref)
print("=" * 84)
print(f"E8/IQ3 (Colibri fmt=6, already implemented) vs the SDD-403 VQ proposal")
print(f"real GLM-5.2 weights, layer {LAYER} expert {EID} gate_proj {W.shape}")
print("=" * 84)

# --- int4 per-row: production baseline
s = np.abs(W).max(axis=1, keepdims=True) / 7
Wq = np.clip(np.rint(W / s), -8, 7) * s
b_err = float(np.linalg.norm(Wq @ x - ref) / nref)

# --- E8/IQ3 via Colibri's own packer, row by row
rows = []
for r in range(W.shape[0]):
    packed = iq3_pack.encode(W[r].astype(np.float32))
    rows.append(iq3_pack.decode(packed, W.shape[1]))
We = np.stack(rows).astype(np.float32)
e_err = float(np.linalg.norm(We @ x - ref) / nref)

# --- the VQ point SDD-403 proposes at the same rate
Wv, _, _, bw = vqq.vq_encode(W, 4, [256, 16], 2, 0, iters=15, seed=EID)
v_err = float(np.linalg.norm(Wv @ x - ref) / nref)

n = 3 * 2048 * 6144
e8_mb = (n / 256 * 98) / 1e6
print(f"\n  {'format':<34} {'b/w':>5} {'err':>8} {'MB/exp':>8} {'inVRAM':>8} {'vs int4':>8}")
for name, bpw_, err, mb in (
        ("int4 per-row (PRODUCTION)", 4.00, b_err, (n * 4 / 8 + 3 * 2048 * 4) / 1e6),
        ("fmt=6 E8/IQ3  (EXISTS, CPU-only)", 98 * 8 / 256, e_err, e8_mb),
        ("SDD-403 VQ d=4 K=[256,16] x2", bw, v_err, vqq.mb_per_expert(4, [256, 16], 2, 0))):
    print(f"  {name:<34} {bpw_:>5.2f} {err:>8.4f} {mb:>8.2f} "
          f"{min(int(119.24 * 1024 / mb), 19456):>8,} {err / b_err:>7.2f}x")

print()
if e_err <= v_err * 1.10:
    print("  => E8/IQ3 matches the proposed VQ. Phase 4 becomes ONE CUDA kernel for an")
    print("     existing, tested codec — no new format, packer, loader or container work.")
else:
    print("  => E8/IQ3 is materially worse; the custom VQ format keeps its justification.")
