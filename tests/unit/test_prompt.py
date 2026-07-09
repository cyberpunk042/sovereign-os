"""Unit tests for the SDD-062/SDD-103 inference prompt engine
`scripts/inference/prompt.py` — the `_bound_messages` bounding + `run(messages=…)`
multi-turn extension + `run(text=…)` back-compat.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = REPO_ROOT / "scripts" / "inference" / "prompt.py"


def _load():
    spec = importlib.util.spec_from_file_location("prompt_engine", PROMPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


P = _load()


# ── _bound_messages (SDD-103) ──────────────────────────────────────────────────

def test_bound_messages_keeps_valid_turns():
    b, err = P._bound_messages([
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "more"}])
    assert err is None and [m["role"] for m in b] == ["user", "assistant", "user"]


def test_bound_messages_trims_to_max_turns():
    many = [{"role": "user", "content": f"m{i}"} for i in range(P.MAX_CHAT_TURNS + 12)]
    b, err = P._bound_messages(many)
    assert err is None and len(b) == P.MAX_CHAT_TURNS
    assert b[-1]["content"] == f"m{P.MAX_CHAT_TURNS + 11}"   # keeps the most recent


def test_bound_messages_filters_bad_roles_no_injection():
    b, _ = P._bound_messages([
        {"role": "system", "content": "x"},
        {"role": "evil", "content": "y"},           # dropped — never injected
        {"role": "user", "content": "z"}])
    assert [m["role"] for m in b] == ["system", "user"]


def test_bound_messages_empty_errors():
    _, err = P._bound_messages([])
    assert err and "turns" in err


def test_bound_messages_char_cap():
    _, err = P._bound_messages([{"role": "user", "content": "a" * (P.MAX_PROMPT_CHARS + 1)}])
    assert err and str(P.MAX_PROMPT_CHARS) in err


def test_bound_messages_skips_blank_and_nondict():
    b, _ = P._bound_messages([
        "not a dict", {"role": "user", "content": "  "}, {"role": "user", "content": "ok"}])
    assert [m["content"] for m in b] == ["ok"]


# ── run(messages=…) + run(text) back-compat ────────────────────────────────────

def _capture_body(monkeypatch):
    captured: dict = {}

    def fake_stream(body, timeout):
        captured["body"] = body
        yield '{"choices":[{"delta":{"content":"ok"}}]}'
        yield "[DONE]"

    monkeypatch.setattr(P, "_stream_completion", fake_stream)
    return captured


def test_run_messages_builds_multiturn_body(monkeypatch):
    cap = _capture_body(monkeypatch)
    evs = list(P.run(messages=[
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "b"},
        {"role": "user", "content": "c"}]))
    assert [m["role"] for m in cap["body"]["messages"]] == ["user", "assistant", "user"]
    assert any(e["type"] == "token" for e in evs)


def test_run_messages_bounds_before_sending(monkeypatch):
    cap = _capture_body(monkeypatch)
    list(P.run(messages=[{"role": "user", "content": f"m{i}"}
                         for i in range(P.MAX_CHAT_TURNS + 5)]))
    assert len(cap["body"]["messages"]) == P.MAX_CHAT_TURNS


def test_run_messages_invalid_yields_error(monkeypatch):
    _capture_body(monkeypatch)
    evs = list(P.run(messages=[{"role": "evil", "content": "x"}]))   # no valid turns
    assert evs and evs[0]["type"] == "error"


def test_run_text_back_compat(monkeypatch):
    cap = _capture_body(monkeypatch)
    list(P.run("just text"))
    assert cap["body"]["messages"] == [{"role": "user", "content": "just text"}]


def test_run_text_empty_errors(monkeypatch):
    _capture_body(monkeypatch)
    evs = list(P.run("  "))
    assert evs and evs[0]["type"] == "error" and "empty" in evs[0]["error"]
