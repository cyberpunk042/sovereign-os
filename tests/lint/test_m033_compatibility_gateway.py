"""M033 compatibility-gateway contract lint.

Locks `config/inference/m033-compatibility-gateway.yaml` to the M033 spec: the
OpenAI + Anthropic facades (E0310), the translation + router aliases + profile
registry + cost tracker + policy + observability (E0311), and the streaming
translator (E0315). No minimization of the spec.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "config" / "inference" / "m033-compatibility-gateway.yaml"
MILESTONE = REPO_ROOT / "backlog" / "milestones" / "M033-compatibility-gateway-what-we-expose.md"


def _c() -> dict:
    return yaml.safe_load(CONTRACT.read_text())


def test_contract_present_and_parses():
    assert CONTRACT.is_file(), f"missing {CONTRACT}"
    assert _c().get("milestone") == "M033"


def test_openai_facade_four_endpoints_verbatim():
    e = _c()["openai_facade"]["endpoints"]
    assert e == ["/v1/chat/completions", "/v1/responses", "/v1/embeddings",
                 "/v1/models"], f"OpenAI facade drift: {e}"


def test_anthropic_facade_endpoints():
    e = _c()["anthropic_facade"]["endpoints"]
    assert e == ["/v1/messages", "/v1/models"], f"Anthropic facade drift: {e}"


def test_profile_registry_seven_jean_aliases():
    a = _c()["profile_registry"]["aliases"]
    assert a == ["jean/fast", "jean/careful", "jean/local-only", "jean/oracle",
                 "jean/code", "jean/research", "jean/sandbox"], f"alias drift: {a}"


def test_cost_tracker_five_metrics():
    t = _c()["cost_tracker"]["tracks"]
    assert t == ["tokens_in_out", "local_gpu_time", "cloud_spend", "cache_hits",
                 "per_client_budget"], f"cost-tracker drift: {t}"


def test_policy_layer_redacts_secrets_and_gates_cloud():
    p = _c()["policy_layer"]["policies"]
    assert "redact-secrets-before-remote-apis" in p
    assert "block-cloud-for-private-work" in p
    assert len(p) == 4


def test_translation_to_internal_frame():
    r = _c()["translation"]["rule"]
    assert "internal Frame" in r and "client-compatible response" in r


def test_traces_to_real_milestone():
    assert MILESTONE.is_file(), f"missing {MILESTONE}"
    body = MILESTONE.read_text()
    for mod in ("M00544", "M00548", "M00551", "M00552", "M00553", "M00555", "M00557"):
        assert mod in body, f"{mod} not in the M033 milestone (must trace to spec)"
