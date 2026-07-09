"""Unit tests for the SDD-062 M058 single-prompt inference engine
`scripts/inference/prompt.py`.

Covers: run() streams token deltas + a done event with real tokens/sec/tier; the
router-unreachable path yields a structured honest error (SB-077 — never fabricates);
prompt bounds (empty + oversize rejected); publish_telemetry records the REAL measured
tokens_per_sec[role] to model-state.json while PRESERVING the SDD-049 `loaded` set
(atomic), and appends a bounded model-latency.json record.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import importlib.util
import json
import urllib.error
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "scripts" / "inference" / "prompt.py"


def _load():
    spec = importlib.util.spec_from_file_location("inference_prompt", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


P = _load()


@pytest.fixture()
def runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "MODEL_STATE_PATH", tmp_path / "model-state.json")
    monkeypatch.setattr(P, "MODEL_LATENCY_PATH", tmp_path / "model-latency.json")
    monkeypatch.setattr(P, "_classify", lambda body: "oracle_core")
    return tmp_path


def _mock_stream(*deltas, usage=None, done=True):
    payloads = [json.dumps({"choices": [{"delta": {"content": d}}]}) for d in deltas]
    if usage is not None:
        payloads.append(json.dumps({"choices": [{"delta": {}}], "usage": {"completion_tokens": usage}}))
    if done:
        payloads.append("[DONE]")
    return lambda body, timeout: iter(payloads)


# ── run(): streaming + metrics ────────────────────────────────────────────────

def test_run_streams_tokens_and_done(runtime, monkeypatch):
    monkeypatch.setattr(P, "_stream_completion", _mock_stream("Hel", "lo ", "world", usage=3))
    evs = list(P.run("hi"))
    text = "".join(e["text"] for e in evs if e["type"] == "token")
    done = next(e for e in evs if e["type"] == "done")
    assert text == "Hello world"
    assert done["tokens"] == 3 and done["tier"] == "oracle_core" and done["tokens_per_sec"] >= 0


def test_run_counts_deltas_without_usage(runtime, monkeypatch):
    monkeypatch.setattr(P, "_stream_completion", _mock_stream("a", "b", "c", usage=None))
    done = next(e for e in P.run("hi") if e["type"] == "done")
    assert done["tokens"] == 3  # fell back to delta-count


def test_run_router_unreachable_honest_error(runtime, monkeypatch):
    def boom(body, timeout):
        raise urllib.error.URLError("connection refused")
    monkeypatch.setattr(P, "_stream_completion", boom)
    evs = list(P.run("hi"))
    assert len(evs) == 1 and evs[0]["type"] == "error"
    assert "router unreachable" in evs[0]["error"] and "inference start router" in evs[0]["error"]


def test_run_empty_prompt_rejected(runtime):
    assert list(P.run("   "))[0]["type"] == "error"


def test_run_oversize_prompt_rejected(runtime, monkeypatch):
    monkeypatch.setattr(P, "MAX_PROMPT_CHARS", 10)
    ev = list(P.run("x" * 11))[0]
    assert ev["type"] == "error" and "bounded" in ev["error"]


# ── publish_telemetry(): real, preserves `loaded` ─────────────────────────────

def test_publish_preserves_loaded_and_sets_tps(runtime):
    st = runtime / "model-state.json"
    st.write_text(json.dumps({"loaded": {"logic": [{"id": "qwen3-8b", "precision": "nvfp4", "path": "/m"}]}}))
    r = P.publish_telemetry("oracle_core", 42.5, latency_ms=20.0)
    assert r["ok"] is True and r["role"] == "oracle"
    d = json.loads(st.read_text())
    assert d["loaded"]["logic"][0]["id"] == "qwen3-8b"  # SDD-049 set preserved
    assert d["tokens_per_sec"]["oracle"] == 42.5 and "updated_ts" in d


def test_publish_maps_tier_to_role(runtime):
    for tier, role in [("pulse", "conductor"), ("logic", "logic"), ("oracle_core", "oracle")]:
        (runtime / "model-state.json").write_text("{}")
        r = P.publish_telemetry(tier, 1.0)
        assert r["role"] == role


def test_publish_appends_bounded_latency(runtime):
    (runtime / "model-state.json").write_text("{}")
    P.publish_telemetry("logic", 10.0, latency_ms=15.5)
    lat = json.loads((runtime / "model-latency.json").read_text())
    assert lat["models"][-1]["role"] == "logic" and lat["models"][-1]["p50_ms"] == 15.5


def test_publish_no_latency_leaves_latency_file_absent(runtime):
    (runtime / "model-state.json").write_text("{}")
    P.publish_telemetry("logic", 10.0)  # no latency_ms
    assert not (runtime / "model-latency.json").exists()
