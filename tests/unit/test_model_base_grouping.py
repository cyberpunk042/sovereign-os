"""Base-model quantization grouping (load-time quant-picker source of truth).

Quant variants of one model are separate catalog ids (…-FP16 / …-Q4_K_M, or
per-quant HF repos like the Nemotron BF16/FP8/NVFP4 trio), so a load-time
quantization picker needs the catalog regrouped by BASE model with its available
quant variants. This locks that grouping (model-health.group_by_base) + the
read-only endpoint shape (models-catalog-api.by_base_view) against both synthetic
fixtures (robust to catalog edits) and the real catalog.

Read-only: the picker resolves (base, quant) → an existing catalog id and hands
off to the signed `sovereign-osctl models load <id>` control — no web mutation
(R10212).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MH = _load("model_health", "scripts/inference/model-health.py")
MCA = _load("models_catalog_api", "scripts/operator/models-catalog-api.py")


# ── base-id derivation (the grouping key) ────────────────────────────────────

def test_quant_suffix_mapping():
    assert MH._quant_suffix("gguf-q4_k_m") == "Q4_K_M"
    assert MH._quant_suffix("gguf-q6_k") == "Q6_K"
    assert MH._quant_suffix("fp16") == "FP16"
    assert MH._quant_suffix("nvfp4") == "NVFP4"
    assert MH._quant_suffix("bf16") == "BF16"
    assert MH._quant_suffix("") == ""


def test_base_id_strips_only_matching_suffix():
    # id carries the quant suffix → stripped to the base
    assert MH._base_id({"id": "DeepSeek-R1-Distill-Llama-70B-FP16",
                        "quantization": "fp16"}) == "DeepSeek-R1-Distill-Llama-70B"
    assert MH._base_id({"id": "DeepSeek-R1-Distill-Llama-70B-Q4_K_M",
                        "quantization": "gguf-q4_k_m"}) == "DeepSeek-R1-Distill-Llama-70B"
    assert MH._base_id({"id": "Nemotron-3-Nano-Omni-30B-Reasoning-NVFP4",
                        "quantization": "nvfp4"}) == "Nemotron-3-Nano-Omni-30B-Reasoning"
    # id with NO quant suffix → its own base (no accidental stripping)
    assert MH._base_id({"id": "Ling-2.6-flash", "quantization": "bf16"}) == "Ling-2.6-flash"
    # a suffix that doesn't match the entry's quantization is NOT stripped
    assert MH._base_id({"id": "Weird-Name-FP16", "quantization": "bf16"}) == "Weird-Name-FP16"


# ── grouping (synthetic — robust to catalog edits) ───────────────────────────

def test_group_by_base_collapses_variants_synthetic():
    models = [
        {"id": "Foo-70B-FP16", "quantization": "fp16", "tier": "oracle",
         "vram_gib_min": 140, "parameters_millions": 70000, "status": "verified-real"},
        {"id": "Foo-70B-Q4_K_M", "quantization": "gguf-q4_k_m", "tier": "oracle",
         "vram_gib_min": 42, "parameters_millions": 70000, "status": "verified-real"},
        {"id": "Bar-Solo", "quantization": "bf16", "tier": "logic",
         "vram_gib_min": 8, "parameters_millions": 8000, "status": "verified-real"},
    ]
    groups = MH.group_by_base(models)
    by_base = {g["base"]: g for g in groups}
    assert set(by_base) == {"Foo-70B", "Bar-Solo"}
    foo = by_base["Foo-70B"]
    assert foo["variant_count"] == 2
    assert [v["quantization"] for v in foo["variants"]] == ["fp16", "gguf-q4_k_m"]
    assert [v["id"] for v in foo["variants"]] == ["Foo-70B-FP16", "Foo-70B-Q4_K_M"]
    # per-quant footprint is preserved so the picker can show the vram tradeoff
    assert [v["vram_gib_min"] for v in foo["variants"]] == [140, 42]
    assert by_base["Bar-Solo"]["variant_count"] == 1


def test_group_by_base_preserves_catalog_order():
    models = [{"id": f"M{i}", "quantization": "bf16"} for i in range(5)]
    assert [g["base"] for g in MH.group_by_base(models)] == [f"M{i}" for i in range(5)]


# ── against the real catalog ─────────────────────────────────────────────────

def test_real_catalog_groups_deepseek_and_nemotron():
    groups = {g["base"]: g for g in MH.group_by_base()}
    ds = groups.get("DeepSeek-R1-Distill-Llama-70B")
    assert ds and ds["variant_count"] == 2
    assert {v["quantization"] for v in ds["variants"]} == {"fp16", "gguf-q4_k_m"}
    nem = groups.get("Nemotron-3-Nano-Omni-30B-Reasoning")
    assert nem and nem["variant_count"] == 3
    assert {v["quantization"] for v in nem["variants"]} == {"bf16", "fp8", "nvfp4"}


def test_every_catalog_model_appears_in_exactly_one_group():
    models = MH.load_catalog()
    grouped_ids = [v["id"] for g in MH.group_by_base(models) for v in g["variants"]]
    assert sorted(grouped_ids) == sorted(m["id"] for m in models)  # no drop, no dupe


# ── the read-only endpoint shape ─────────────────────────────────────────────

def test_by_base_view_shape():
    v = MCA.by_base_view()
    assert v["total_bases"] == len(v["bases"])
    assert v["multi_quant_bases"] == sum(1 for b in v["bases"] if b["variant_count"] > 1)
    assert v["multi_quant_bases"] >= 2  # DeepSeek + Nemotron at least
    # every variant carries what the picker renders
    for b in v["bases"]:
        for var in b["variants"]:
            assert "id" in var and "quantization" in var and "precision" in var


def test_by_base_route_registered_and_read_only():
    src = (REPO / "scripts/operator/models-catalog-api.py").read_text(encoding="utf-8")
    assert '"/api/models-catalog/by-base"' in src, "the by-base route must be wired"
    # the catalog daemon stays read-only — mutations are the signed CLI (R10212)
    assert "def do_POST" in src and "_reject" in src
