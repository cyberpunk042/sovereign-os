"""SDD-1000 runtime-attestation contract tests."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path


MODULE = Path(__file__).resolve().parents[2] / "scripts/iac/assets/publish-model-state.py"
SPEC = importlib.util.spec_from_file_location("publish_model_state", MODULE)
assert SPEC and SPEC.loader
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)


def test_qwythos_worker_is_added_only_for_the_active_three_card_profile():
    runtime = {"worker": {"port": 8086, "catalog_id": "Qwythos-GGUF"}}

    assert publisher._effective_tiers("logic@127.0.0.1:8082@Logic", "other", runtime) == "logic@127.0.0.1:8082@Logic"
    assert publisher._effective_tiers("logic@127.0.0.1:8082@Logic", "qwythos-three-card", runtime).endswith(
        "router@127.0.0.1:8086@Qwythos-GGUF"
    )


def test_nested_quant_subdir_resolves_to_the_catalog_id(monkeypatch):
    """2026-10-07 D-21 bug: sharded HF repos store GGUFs at
    <vault>/<catalog-id>/<QUANT>/<shard>.gguf (Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S
    lives under an inner IQ3_S/). The old immediate-parent rule published
    'IQ3_S' as the resident model id; the publisher must resolve to the vault
    catalog directory."""
    monkeypatch.setattr(publisher, "_probe_tier", lambda endpoint: {
        "endpoint": endpoint, "reachable": True,
        # llama.cpp answers /v1/models with its --alias, which matches no catalog id
        "models": [{"id": "gpu-oracle", "resident_context_tokens": 262144}],
    })
    monkeypatch.setattr(publisher, "_model_path_from_process", lambda port:
        "/mnt/vault/models/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S/IQ3_S/"
        "Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf")
    index = {"Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S": {
        "id": "Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S", "precision": None}}

    loaded, _observations = publisher.collect("oracle@127.0.0.1:8083@gpt-oss-120b", index)

    assert loaded["oracle"][0]["id"] == "Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S"
    assert loaded["oracle"][0]["served_as"] == "gpu-oracle"

    # STALE deployed catalog (the 2026-10-07 reality: /opt predates the model) —
    # the vault first level (SOVEREIGN_OS_MODELS_DIR default /mnt/vault/models)
    # is still the catalog directory, so the quant subfolder never wins.
    loaded_stale, _ = publisher.collect("oracle@127.0.0.1:8083@gpt-oss-120b", {})
    assert loaded_stale["oracle"][0]["id"] == "Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S"


def test_flat_vault_layout_still_resolves_and_unknown_stays_honest(monkeypatch):
    """The plain <vault>/<catalog-id>/<file>.gguf case keeps working, and a
    genuinely non-catalogued model publishes its parent dir name (bare row),
    never a configured-but-stale fallback id."""
    monkeypatch.setattr(publisher, "_probe_tier", lambda endpoint: {
        "endpoint": endpoint, "reachable": True,
        "models": [{"id": "gpu-logic", "resident_context_tokens": 131072}],
    })
    monkeypatch.setattr(publisher, "_model_path_from_process", lambda port:
        "/mnt/vault/models/Qwen3.8-27B-Q4_K_M/Qwen3.8-27B-Q4_K_M.gguf")
    loaded, _ = publisher.collect("logic@127.0.0.1:8082@Stale-Id",
                                  {"Qwen3.8-27B-Q4_K_M": {"id": "Qwen3.8-27B-Q4_K_M"}})
    assert loaded["logic"][0]["id"] == "Qwen3.8-27B-Q4_K_M"

    monkeypatch.setattr(publisher, "_model_path_from_process", lambda port:
        "/home/operator/experiments/mystery/mystery-00001-of-00002.gguf")
    loaded, _ = publisher.collect("logic@127.0.0.1:8082@Stale-Id", {})
    assert loaded["logic"][0]["id"] == "mystery"  # parent-dir fallback, honest bare row


def test_attestation_requires_backend_context_and_matching_openclaw_entry(monkeypatch):
    monkeypatch.setattr(publisher, "_profile_revision", lambda _: "profile-sha")
    runtime = {
        "worker": {
            "port": 8086,
            "served_model_name": "gpu-qwythos-worker",
            "context_tokens": 32768,
        }
    }
    observations = [{
        "role": "router", "catalog_id": "Qwythos-GGUF",
        "endpoint": "127.0.0.1:8086", "reachable": True,
        "models": [{"id": "gpu-qwythos-worker", "resident_context_tokens": 32768}],
    }]
    consumer = {
        "profile_id": "qwythos-three-card",
        "profile_revision_sha256": "profile-sha",
        "consumer_revision_sha256": "consumer-sha",
        "models": [{
            "id": "gpu-qwythos-worker",
            "context_window_tokens": 32768,
            "max_output_tokens": 4096,
        }],
    }

    got = publisher._attestation("qwythos-three-card", observations, runtime, consumer)

    assert got["consistent"] is True
    assert got["providers"][0]["served_as"] == "gpu-qwythos-worker"
    assert got["providers"][0]["resident_context_tokens"] == 32768

    consumer["models"][0]["context_window_tokens"] = 16384
    failed = publisher._attestation("qwythos-three-card", observations, runtime, consumer)
    assert failed["consistent"] is False
    assert "router:openclaw-context-mismatch" in failed["violations"]


def test_catalog_revision_is_secret_free_and_is_profile_bound(tmp_path):
    sync_path = Path(__file__).resolve().parents[2] / "scripts/inference/sync-openclaw-models.py"
    sync_spec = importlib.util.spec_from_file_location("sync_openclaw_models", sync_path)
    assert sync_spec and sync_spec.loader
    sync = importlib.util.module_from_spec(sync_spec)
    sync_spec.loader.exec_module(sync)
    profile = tmp_path / "profile.yaml"
    profile.write_text("profile: qwythos\n", encoding="utf-8")

    got = sync._catalog_revision("qwythos-three-card", profile, tmp_path / "openclaw.json", [
        {"id": "gpu-qwythos-worker", "name": "Qwythos", "contextWindow": 32768,
         "maxTokens": 4096, "apiKey": "must-not-appear"},
        {"id": "operator-custom", "apiKey": "also-not-appear"},
    ])

    encoded = json.dumps(got)
    assert got["profile_id"] == "qwythos-three-card"
    assert got["models"] == [{"id": "gpu-qwythos-worker", "name": "Qwythos",
                                "context_window_tokens": 32768, "max_output_tokens": 4096}]
    assert "must-not-appear" not in encoded
    assert "also-not-appear" not in encoded


def test_agent_materialized_catalog_is_refreshed_from_profile_catalog(tmp_path):
    """A gateway restart must not revive a prior profile from models.json."""
    sync_path = Path(__file__).resolve().parents[2] / "scripts/inference/sync-openclaw-models.py"
    sync_spec = importlib.util.spec_from_file_location("sync_openclaw_models_agent_catalog", sync_path)
    assert sync_spec and sync_spec.loader
    sync = importlib.util.module_from_spec(sync_spec)
    sync_spec.loader.exec_module(sync)

    cfg_path = tmp_path / ".openclaw" / "openclaw.json"
    cfg_path.parent.mkdir(parents=True)
    cfg_path.write_text("{}\n", encoding="utf-8")
    agent_path = cfg_path.parent / "agents" / "main" / "agent" / "models.json"
    agent_path.parent.mkdir(parents=True)
    agent_path.write_text(json.dumps({"providers": {"sovereign": {"models": [
        {"id": "gpu-oracle", "name": "old oracle", "contextWindow": 131072},
        {"id": "gpu-logic", "name": "old logic", "contextWindow": 32768},
        {"id": "gpu-qwythos-worker", "name": "stale Qwythos worker"},
        {"id": "operator-custom", "name": "keep me"},
    ]}}}, indent=2) + "\n", encoding="utf-8")

    changed = sync._sync_agent_model_catalogs(cfg_path, [
        {"id": "gpu-oracle", "name": "new oracle", "contextWindow": 65536},
        {"id": "gpu-logic", "name": "new logic", "contextWindow": 65536},
        {"id": "local-oracle", "name": "CPU fallback"},
    ], dry_run=False)

    assert changed == [str(agent_path)]
    got = json.loads(agent_path.read_text(encoding="utf-8"))["providers"]["sovereign"]["models"]
    assert {entry["id"] for entry in got} == {"gpu-oracle", "gpu-logic", "operator-custom"}
    assert next(entry for entry in got if entry["id"] == "gpu-logic")["name"] == "new logic"
    assert next(entry for entry in got if entry["id"] == "operator-custom")["name"] == "keep me"


def test_openclaw_output_budget_leaves_agent_prompt_headroom():
    """The advertised budget becomes max_tokens on every OpenClaw request."""
    sync_path = Path(__file__).resolve().parents[2] / "scripts/inference/sync-openclaw-models.py"
    sync_spec = importlib.util.spec_from_file_location("sync_openclaw_models_output_budget", sync_path)
    assert sync_spec and sync_spec.loader
    sync = importlib.util.module_from_spec(sync_spec)
    sync_spec.loader.exec_module(sync)

    oracle = sync._derive_entry(
        {"model": "Qwen3-Coder-32B-Instruct", "tier": "oracle", "target_hardware": "cuda:0",
         "context_tokens": 65536, "max_output_tokens": 16384},
        {"Qwen3-Coder-32B-Instruct": {"context_window_tokens": 131072}},
        "gpu-oracle",
    )
    assert oracle["contextWindow"] == 65536
    assert oracle["maxTokens"] == 8192


def test_ollama_shaped_tier_witnesses_itself_and_maps_to_the_catalog_id(monkeypatch):
    """Pulse/bitnet.cpp answers /v1/models in ollama shape ({"models":
    [{"name": ...}]}). A tier that ANSWERS must witness itself — treating it
    as silent kept the conductor role permanently out of `loaded`, which the
    panel papered over with catalog candidates (plan-as-state again). The
    casefold pass maps the HF-repo-derived vault dir
    (microsoft__bitnet-b1.58-2B-4T-gguf) to the display-cased catalog id
    (BitNet-b1.58-2B-4T) instead of publishing the raw directory name."""
    path = "/mnt/vault/models/microsoft__bitnet-b1.58-2B-4T-gguf/ggml-model-i2_s.gguf"
    doc = {"models": [{"name": path}]}
    monkeypatch.setattr(publisher, "_json_endpoint",
                        lambda ep, p: doc if p == "/v1/models" else None)
    probe = publisher._probe_tier("127.0.0.1:8081")
    assert probe["reachable"] is True
    assert probe["models"][0]["id"] == path

    monkeypatch.setattr(publisher, "_model_path_from_process", lambda port: path)
    index = {"BitNet-b1.58-2B-4T": {"id": "BitNet-b1.58-2B-4T",
                                    "precision": "ternary-1.58bit"}}
    loaded, observations = publisher.collect(
        "conductor@127.0.0.1:8081@BitNet-b1.58-2B-4T", index)
    assert loaded["conductor"][0]["id"] == "BitNet-b1.58-2B-4T"
    assert observations[0]["reachable"] is True
