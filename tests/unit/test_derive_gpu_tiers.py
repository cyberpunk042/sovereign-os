"""SDD-903 Phase 1b — unit tests for the pure tier-derivation core.

Proves the derivation is a faithful drop-in for 84-gpu-route BEFORE it is ever
wired in (the module caused the 256-wedge outage; wiring is integration-gated).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "scripts" / "inference" / "derive-gpu-tiers.py"
DENSE = REPO_ROOT / "profiles" / "orchestration" / "dense-4090.yaml"

yaml = pytest.importorskip("yaml")


def _mod():
    spec = importlib.util.spec_from_file_location("derive_gpu_tiers", MOD_PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _dense() -> dict:
    return yaml.safe_load(DENSE.read_text())


def test_round_trip_matches_todays_hardcoded_tiers():
    """A logic+oracle layout with no explicit ports/vram must derive the exact
    string 84-gpu-route hardcodes today — the drop-in guarantee."""
    m = _mod()
    prof = {"orchestration_profile": {"allocations": [
        {"agent_id": "logic_coder", "tier": "logic", "target_hardware": "cuda:0",
         "engine": "vllm", "model": "X", "active": True},
        {"agent_id": "oracle_core", "tier": "oracle", "target_hardware": "cuda:1",
         "engine": "vllm", "model": "Y", "active": True},
    ]}}
    r = m.derive_routing(prof)
    assert m.tiers_string(r["proxy_tiers"]) == (
        "gpu-logic@127.0.0.1:8082@logic@32,gpu-oracle@127.0.0.1:8083@oracle@96"
    )


def test_dense_4090_derives_two_pooling_tiers_on_one_card():
    m = _mod()
    r = m.derive_routing(_dense())
    # generative proxies unchanged (logic + oracle), embed/rerank are pooling.
    assert m.tiers_string(r["proxy_tiers"]) == (
        "gpu-logic@127.0.0.1:8082@logic@32,gpu-oracle@127.0.0.1:8083@oracle@96"
    )
    assert r["embed"] == {"endpoint": "127.0.0.1:8084", "model": "gpu-embed"}
    assert r["rerank"] == {"endpoint": "127.0.0.1:8085"}
    # both 4090 endpoints are in the SSRF allowlist
    assert "127.0.0.1:8084" in r["allow"] and "127.0.0.1:8085" in r["allow"]


def test_cpu_and_inactive_allocations_are_skipped():
    m = _mod()
    prof = {"orchestration_profile": {"allocations": [
        {"agent_id": "pulse", "tier": "pulse", "target_hardware": "cpu",
         "engine": "bitnet.cpp", "model": "Z", "active": True},
        {"agent_id": "idle", "tier": "oracle", "target_hardware": "cuda:1",
         "engine": "vllm", "model": "Y", "active": False},
    ]}}
    r = m.derive_routing(prof)
    assert r["proxy_tiers"] == [] and r["embed"] is None and r["allow"] == []


def test_vram_limit_bytes_overrides_default_gb():
    m = _mod()
    prof = {"orchestration_profile": {"allocations": [
        {"agent_id": "l", "tier": "logic", "target_hardware": "cuda:0",
         "engine": "vllm", "model": "X", "active": True,
         "vram_limit_bytes": 20 * 1024 ** 3},
    ]}}
    r = m.derive_routing(prof)
    assert r["proxy_tiers"][0]["vram_gb"] == 20


def test_validate_flags_port_collision():
    m = _mod()
    prof = {"orchestration_profile": {"allocations": [
        {"agent_id": "a", "tier": "embed", "target_hardware": "cuda:2", "port": 8084,
         "engine": "vllm", "model": "M", "active": True},
        {"agent_id": "b", "tier": "rerank", "target_hardware": "cuda:2", "port": 8084,
         "engine": "vllm", "model": "N", "active": True},
    ]}}
    errs = m.validate(prof)
    assert errs and "8084" in errs[0] and "cuda:2" in errs[0]


def test_validate_flags_vram_overcommit():
    m = _mod()
    prof = {"orchestration_profile": {"allocations": [
        {"agent_id": "a", "tier": "embed", "target_hardware": "cuda:2", "port": 8084,
         "engine": "vllm", "model": "M", "active": True, "vram_limit_bytes": 20 * 1024 ** 3},
        {"agent_id": "b", "tier": "rerank", "target_hardware": "cuda:2", "port": 8085,
         "engine": "vllm", "model": "N", "active": True, "vram_limit_bytes": 20 * 1024 ** 3},
    ]}}
    errs = m.validate(prof, card_vram_bytes={"cuda:2": 24 * 1024 ** 3})
    assert errs and "overcommitted" in errs[0]


def test_validate_clean_dense_profile_ok():
    m = _mod()
    # dense-4090 within a real 24 GiB 4090 (2 x 4 GiB caps fit)
    errs = m.validate(_dense(), card_vram_bytes={"cuda:2": 24 * 1024 ** 3})
    assert errs == []
