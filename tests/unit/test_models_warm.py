"""Unit tests for scripts/models/warm.py (SDD-049 Stage 4 — profile/dtype aware).

The warm reads the tier's loaded record (id + precision) from model-state.json +
the active runtime mode, primes the served model with a 1-token request, and
cross-checks the served model against the loaded record — flagging a drift when
the tier serves something other than what state records loaded. These pin that
awareness + the drift check against a threaded mock vLLM server, with the state /
runtime-mode source paths + tier port pointed at temp fixtures (env-overridable).
"""
from __future__ import annotations

import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MOD_PATH = REPO_ROOT / "scripts" / "models" / "warm.py"


def _load_warm(monkeypatch, *, port, state_path=None, runtime_path=None):
    """Load warm.py fresh with the tier port + state/runtime paths pointed at
    fixtures (both read at module import from env)."""
    monkeypatch.setenv("LOGIC_PORT", str(port))
    monkeypatch.setenv("SOVEREIGN_OS_MODEL_STATE", str(state_path or "/nonexistent/ms.json"))
    monkeypatch.setenv("SOVEREIGN_OS_RUNTIME_MODE", str(runtime_path or "/nonexistent/rm"))
    monkeypatch.delenv("SOVEREIGN_OS_DRY_RUN", raising=False)
    spec = importlib.util.spec_from_file_location("warm", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _MockVLLM(BaseHTTPRequestHandler):
    served_id = "served-model"

    def _json(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):  # noqa: N802
        if self.path == "/v1/models":
            self._json(200, {"data": [{"id": self.served_id}]})
        else:
            self._json(404, {"error": "nope"})

    def do_POST(self):  # noqa: N802
        if self.path == "/v1/completions":
            self._json(200, {"choices": [{"text": "!"}]})
        else:
            self._json(404, {"error": "nope"})

    def log_message(self, *a):  # quiet
        pass


def _serve(served_id="served-model"):
    handler = type("H", (_MockVLLM,), {"served_id": served_id})
    srv = HTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, srv.server_address[1]


def _write_state(tmp_path, role, model_id, precision):
    p = tmp_path / "model-state.json"
    p.write_text(json.dumps({"loaded": {role: [{"id": model_id, "precision": precision}]}}))
    return p


# ── context reading ──────────────────────────────────────────────────────────

def test_context_reads_precision_and_runtime_mode(monkeypatch, tmp_path):
    state = _write_state(tmp_path, "logic", "served-model", "gguf-q4_k_m")
    rm = tmp_path / "rm"; rm.write_text("high-concurrency-burst\n")
    warm = _load_warm(monkeypatch, port=1, state_path=state, runtime_path=rm)
    ctx = warm._context("logic")
    assert ctx["state_model"] == "served-model"
    assert ctx["precision"] == "gguf-q4_k_m"
    assert ctx["runtime_mode"] == "high-concurrency-burst"


def test_context_degrades_gracefully_without_state(monkeypatch):
    warm = _load_warm(monkeypatch, port=1)  # nonexistent paths
    ctx = warm._context("logic")
    assert ctx == {"state_model": None, "precision": None, "runtime_mode": None}


# ── dry-run + unreachable ────────────────────────────────────────────────────

def test_dry_run_is_precision_aware(monkeypatch, tmp_path):
    state = _write_state(tmp_path, "logic", "m", "nvfp4")
    warm = _load_warm(monkeypatch, port=1, state_path=state)
    monkeypatch.setenv("SOVEREIGN_OS_DRY_RUN", "1")
    r = warm.warm("logic")
    assert r["ok"] and r["dry_run"] and r["precision"] == "nvfp4"


def test_unreachable_tier_is_graceful_and_carries_precision(monkeypatch, tmp_path):
    state = _write_state(tmp_path, "logic", "m", "fp8")
    # port 1 → nothing listening → unreachable
    warm = _load_warm(monkeypatch, port=1, state_path=state)
    r = warm.warm("logic")
    assert not r["ok"] and r["code"] == 1 and "unreachable" in r["error"]
    assert r["precision"] == "fp8"


def test_unknown_role_rejected(monkeypatch):
    warm = _load_warm(monkeypatch, port=1)
    r = warm.warm("bogus")
    assert not r["ok"] and r["code"] == 2


# ── the drift check (real substance) against a mock vLLM ──────────────────────

def test_warm_consistent_when_served_matches_state(monkeypatch, tmp_path):
    srv, port = _serve(served_id="deepseek-q4")
    try:
        state = _write_state(tmp_path, "logic", "deepseek-q4", "gguf-q4_k_m")
        warm = _load_warm(monkeypatch, port=port, state_path=state)
        r = warm.warm("logic")
        assert r["ok"] and r["warmed"] and r["state_consistent"] is True
        assert r["warning"] is None and r["model"] == "deepseek-q4"
        assert r["precision"] == "gguf-q4_k_m"
    finally:
        srv.shutdown()


def test_warm_flags_drift_when_served_differs_from_state(monkeypatch, tmp_path):
    """The operationally useful part: the tier serves a DIFFERENT model than
    model-state records loaded → warm still primes but flags the drift."""
    srv, port = _serve(served_id="something-else")
    try:
        state = _write_state(tmp_path, "logic", "deepseek-q4", "gguf-q4_k_m")
        warm = _load_warm(monkeypatch, port=port, state_path=state)
        r = warm.warm("logic")
        assert r["ok"] and r["warmed"]           # the prime still succeeded
        assert r["state_consistent"] is False
        assert r["warning"] and "something-else" in r["warning"] and "deepseek-q4" in r["warning"]
    finally:
        srv.shutdown()


def test_warm_consistent_when_state_absent(monkeypatch, tmp_path):
    """No loaded record → nothing to contradict → consistent (not a false drift)."""
    srv, port = _serve(served_id="whatever")
    try:
        warm = _load_warm(monkeypatch, port=port)  # no state file
        r = warm.warm("logic")
        assert r["ok"] and r["state_consistent"] is True and r["warning"] is None
    finally:
        srv.shutdown()
