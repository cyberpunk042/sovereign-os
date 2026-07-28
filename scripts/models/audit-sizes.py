#!/usr/bin/env python3
"""audit-sizes — check catalog vram_gib_min / quantization against the REAL HF repo.

Written after GLM-4.7-Flash was found declaring quantization=fp8 / vram_gib_min=32
while the repo is BF16 at 62.47 GB — a checkpoint that does not exist. That claim
would have cost a 62 GB download and a failed deploy on a 32 GB card.

For each catalog entry carrying an hf_repo_id this fetches the file tree, sums the
weight files, and flags entries where the declared footprint and the published bytes
disagree. Read-only: HF API only, no downloads.

  audit-sizes.py                 # every entry with a repo
  audit-sizes.py --tier logic    # one tier
  audit-sizes.py --fit 31.84     # also flag what will not fit a given GiB budget
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

import yaml

API = "https://huggingface.co/api/models/{}/tree/main?recursive=true"
WEIGHT_SUFFIX = (".safetensors", ".bin", ".gguf", ".pt")
# Directories that are ALTERNATE copies of the same model, not additive. gpt-oss-120b
# ships root + original/ + metal/, each a full 65 GB copy.
ALT_DIRS = ("original", "metal", "consolidated")


def repo_bytes(repo, timeout=45):
    try:
        with urllib.request.urlopen(API.format(repo), timeout=timeout) as r:
            tree = json.load(r)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        return None, f"unreachable ({type(e).__name__})"
    if not isinstance(tree, list):
        return None, "unexpected API response"
    root, alts, ggufs = 0, {}, {}
    for f in tree:
        if f.get("type") != "file" or not f["path"].endswith(WEIGHT_SUFFIX):
            continue
        top = f["path"].split("/")[0] if "/" in f["path"] else None
        if f["path"].endswith(".gguf"):
            # A GGUF repo usually ships MANY quant levels and you pull exactly one.
            # Summing them overstates the download by 5-13x, so group by variant and
            # report the largest single variant instead.
            import re as _re
            base = _re.sub(r"[-.]?(Q\d[_A-Za-z0-9]*|IQ\d[_A-Za-z0-9]*|F16|BF16|F32)"
                           r"(-\d+-of-\d+)?\.gguf$", "", f["path"], flags=_re.I)
            key = _re.search(r"(Q\d[_A-Za-z0-9]*|IQ\d[_A-Za-z0-9]*|F16|BF16|F32)",
                             f["path"], _re.I)
            k = key.group(1).upper() if key else base
            ggufs[k] = ggufs.get(k, 0) + f.get("size", 0)
        elif top in ALT_DIRS:
            alts[top] = alts.get(top, 0) + f.get("size", 0)
        else:
            root += f.get("size", 0)
    if ggufs and not root:
        root = max(ggufs.values())          # the one variant you would actually pull
    return (root, alts, ggufs), None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--catalog", default="models/catalog.yaml")
    ap.add_argument("--tier")
    ap.add_argument("--fit", type=float, metavar="GIB",
                    help="also flag entries whose weights exceed this VRAM budget")
    a = ap.parse_args()

    doc = yaml.safe_load(open(a.catalog))
    models = [m for m in doc["catalog"]["models"] if m.get("hf_repo_id")]
    if a.tier:
        models = [m for m in models if m.get("tier") == a.tier]

    print(f"{'model':<34} {'declared':>9} {'actual':>9} {'quant':>8} {'verdict'}")
    print("-" * 88)
    bad = 0
    for m in sorted(models, key=lambda x: x["id"]):
        got, err = repo_bytes(m["hf_repo_id"])
        if err:
            print(f"{m['id']:<34} {'-':>9} {'-':>9} {'-':>8} {err}")
            continue
        root, alts, ggufs = got
        gib = root / (1024 ** 3)
        decl = m.get("vram_gib_min")
        note = []
        if ggufs and len(ggufs) > 1:
            note.append(f"{len(ggufs)} GGUF variants (largest shown)")
        if alts:
            extra = ", ".join(f"{k}/ +{v/1024**3:.0f}GiB" for k, v in alts.items())
            note.append(f"ALT COPIES: {extra}")
        if decl:
            ratio = gib / decl if decl else 0
            if ratio > 1.25:
                note.append(f"UNDER-DECLARED {ratio:.2f}x")
                bad += 1
            elif ratio < 0.75:
                note.append(f"over-declared {1/ratio:.2f}x")
        if a.fit and gib > a.fit:
            note.append(f"does NOT fit {a.fit:.1f} GiB")
        print(f"{m['id']:<34} {str(decl)+' GiB':>9} {gib:>8.1f}G {str(m.get('quantization')):>8} "
              f"{'; '.join(note) if note else 'ok'}")

    print()
    print(f"  {bad} entr{'y' if bad == 1 else 'ies'} under-declare footprint by >1.25x.")
    print()
    print("  TRIAGE TOOL, NOT AN ORACLE. It flags candidates for manual checking. Known")
    print("  imprecision: a repo shipping BOTH safetensors and GGUF sums the safetensors")
    print("  and ignores the GGUF grouping, so a catalog entry naming a GGUF variant of a")
    print("  BF16 repo reads as under-declared when it is not. Confirm a flag against")
    print("  config.json + the file tree before editing the catalog (that is how the real")
    print("  GLM-4.7-Flash error was confirmed: dtype bfloat16, no quantization_config).")
    print("  'ALT COPIES' means the repo ships the same model in several formats — pull")
    print("  with --exclude or you fetch it 2-3x over (gpt-oss-120b is 196 GB for a 65 GB model).")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
