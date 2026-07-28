"""Confirm or dismiss each audit-sizes flag against config.json + the file tree.

audit-sizes is triage. A flag is only real if the published dtype/quantization actually
disagrees with the catalog, or the entry names a variant the repo does not ship. This
does the second pass so the catalog gets corrected on evidence, not on a heuristic.
"""
import json
import urllib.error
import urllib.request

import yaml

FLAGGED = [
    "DeepSeek-R1-Distill-Llama-70B-Q4_K_M", "DeepSeek-V3-Quant", "Falcon-E-3B-Instruct",
    "Ling-2.6-flash", "Phi-4-mini-instruct", "Prism-Ternary-Bonsai-8B",
    "Qwythos-9B-Claude-Mythos-5-1M-GGUF", "Spectra-TriLM-3.9B", "StarCoder2-3B",
    "Ternary-Bonsai-27B", "nomic-embed-text-v2-moe",
]


def get(url, timeout=30):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.load(r), None
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError) as e:
        return None, f"{type(e).__name__}"


doc = yaml.safe_load(open("/home/jfortin/sovereign-os/models/catalog.yaml"))
models = {m["id"]: m for m in doc["catalog"]["models"]}

print(f"{'model':<38} {'catalog quant':<16} {'published dtype':<18} verdict")
print("-" * 100)
for mid in FLAGGED:
    m = models.get(mid)
    if not m:
        print(f"{mid:<38} (not in catalog)")
        continue
    repo = m["hf_repo_id"]
    cfg, err = get(f"https://huggingface.co/{repo}/resolve/main/config.json")
    tree, terr = get(f"https://huggingface.co/api/models/{repo}/tree/main?recursive=true")

    dtype = "-"
    if cfg:
        dtype = cfg.get("dtype") or cfg.get("torch_dtype") or "-"
        if cfg.get("quantization_config"):
            qc = cfg["quantization_config"]
            dtype += f" +{qc.get('quant_method', 'quantized')}"
    elif err:
        dtype = f"(no config: {err})"

    ggufs = sorted({f["path"] for f in (tree or []) if isinstance(f, dict)
                    and f.get("path", "").endswith(".gguf")})
    cat_q = str(m.get("quantization"))

    verdict = []
    if ggufs:
        # catalog names a specific GGUF variant -- does the repo ship it?
        want = cat_q.replace("gguf-", "").upper()
        if want and want != "NONE" and not any(want in g.upper() for g in ggufs):
            verdict.append(f"variant {want} NOT in repo ({len(ggufs)} gguf files)")
        else:
            verdict.append(f"gguf repo, {len(ggufs)} variants — audit sum is not the pull size")
    if cfg and "bfloat16" in str(dtype) and cat_q not in ("bf16", "None"):
        verdict.append(f"DTYPE MISMATCH: catalog says {cat_q}, repo is bfloat16")
    print(f"{mid:<38} {cat_q:<16} {dtype:<18} {'; '.join(verdict) if verdict else 'no dtype conflict'}")
