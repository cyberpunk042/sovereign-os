"""Catalog-selected Hugging Face artifacts must reach the puller unchanged."""
from pathlib import Path

import yaml


REPO = Path(__file__).resolve().parents[2]
CATALOG = REPO / "models" / "catalog.yaml"
PULLER = REPO / "scripts" / "models" / "pull.sh"


def test_qwythos_pulls_only_its_q4_model_and_vision_projector():
    models = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))["catalog"]["models"]
    qwythos = next(m for m in models if m["id"] == "Qwythos-9B-Claude-Mythos-5-1M-GGUF")
    assert qwythos["hf_include_patterns"] == [
        "Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M.gguf",
        "mmproj-Qwythos-9B-Claude-Mythos-5-1M-F16.gguf",
        "README.md",
        "SHA256SUMS",
    ]


def test_puller_passes_catalog_include_patterns_to_huggingface():
    body = PULLER.read_text(encoding="utf-8")
    assert 'query.startswith("include:")' in body
    assert 'catalog_query "include:${model_id}"' in body
    assert '"${_include_args[@]}"' in body
    assert "SOVEREIGN_OS_PULL_ATTEMPTS" in body
    assert "local files will resume" in body
    assert 'log_info "             --include ${_pattern}"' in body


def test_deepseek_q4_does_not_download_other_quantizations():
    import fnmatch
    models = yaml.safe_load(CATALOG.read_text())["catalog"]["models"]
    row = next(m for m in models if m["id"] == "DeepSeek-R1-Distill-Llama-70B-Q4_K_M")
    patterns = row["hf_include_patterns"]
    assert "DeepSeek-R1-Distill-Llama-70B-Q4_K_M.gguf" in patterns
    for filename in ("DeepSeek-R1-Distill-Llama-70B-Q8_0/a.gguf", "BF16/a.gguf", "DeepSeek-R1-Distill-Llama-70B-Q5_K_M.gguf"):
        assert not any(fnmatch.fnmatch(filename, pattern) for pattern in patterns)
