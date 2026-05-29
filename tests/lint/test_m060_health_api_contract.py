"""M060 chain-health API daemon contract.

Locks the wire contract between webapp/master-dashboard/index.html
(which fetches /api/m060/health for the chain-health banner) and
scripts/operator/m060-health-api.py (which serves that route).

The handler delegates probing to scripts/operator/m060-health.py;
this test exercises the HTTP wrap + dispatch + headers, with the
underlying probe monkey-patched to return a known payload — no
selfdef daemon needed.
"""
from __future__ import annotations

import importlib.util
import io
import os
import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
API_PATH = REPO_ROOT / "scripts" / "operator" / "m060-health-api.py"


def _load_api_module():
    spec = importlib.util.spec_from_file_location("_m060_health_api", API_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeWFile(io.BytesIO):
    """Captures the bytes a handler would have written to the socket."""


class _FakeRFile(io.BytesIO):
    pass


def _make_handler(api_mod, path: str, method: str = "GET"):
    """Instantiate a handler without going through a real socket."""
    handler = api_mod.M060HealthAPIHandler.__new__(api_mod.M060HealthAPIHandler)
    # Bare-minimum BaseHTTPRequestHandler init: we set the attributes
    # do_GET inspects directly, then call the dispatch.
    handler.command = method
    handler.path = path
    handler.request_version = "HTTP/1.1"
    handler.headers = {}
    handler.rfile = _FakeRFile(b"")
    handler.wfile = _FakeWFile()
    handler.client_address = ("127.0.0.1", 0)
    handler.server = None
    handler._headers_buffer = []  # required by BaseHTTPRequestHandler internals
    # Also required by send_response/log_request inside BaseHTTPRequestHandler.
    handler.requestline = f"{method} {path} HTTP/1.1"
    return handler


def _drain(handler) -> str:
    return handler.wfile.getvalue().decode("utf-8", errors="replace")


def test_api_module_loads_cleanly():
    api_mod = _load_api_module()
    assert api_mod.API_VERSION == "1.0.0"
    assert callable(api_mod.serve)
    assert hasattr(api_mod, "M060HealthAPIHandler")


def test_version_payload_advertises_endpoint_doctrine():
    api_mod = _load_api_module()
    v = api_mod._version_payload()
    assert v["service"] == "m060-health-api"
    assert v["selfdef_endpoint"] == "/v1/m060/health"
    # State enumeration must include the 5 documented states.
    for s in ("online", "degraded", "stale", "offline", "unreachable"):
        assert s in v["states"], f"missing state {s} in {v['states']}"
    # READ-ONLY doctrine carried in the version surface.
    assert "READ-ONLY" in v["mirror_doctrine"]
    assert "no mutation" in v["mirror_doctrine"].lower()


def test_dispatch_routes_health_endpoint_to_probe():
    api_mod = _load_api_module()
    fake_payload = {
        "schema_version": "1.0.0",
        "state": "online",
        "artifacts_present": 10,
        "artifacts_expected": 10,
        "newest_age_seconds": 7,
        "artifacts": [],
    }
    with patch.object(api_mod._core, "probe", return_value=fake_payload):
        h = _make_handler(api_mod, "/api/m060/health")
        os.environ["M060_HEALTH_API_DRY_RUN"] = "1"  # suppress metric I/O
        try:
            h.do_GET()
        finally:
            os.environ.pop("M060_HEALTH_API_DRY_RUN", None)
        body = _drain(h)
    assert "200 OK" in body or "200" in body
    assert "\"state\": \"online\"" in body
    assert "\"artifacts_present\": 10" in body


def test_dispatch_state_endpoint_returns_bare_state():
    api_mod = _load_api_module()
    fake_payload = {"state": "degraded", "artifacts_present": 3}
    with patch.object(api_mod._core, "probe", return_value=fake_payload):
        h = _make_handler(api_mod, "/api/m060/state")
        os.environ["M060_HEALTH_API_DRY_RUN"] = "1"
        try:
            h.do_GET()
        finally:
            os.environ.pop("M060_HEALTH_API_DRY_RUN", None)
        body = _drain(h)
    assert "\"state\": \"degraded\"" in body
    assert "artifacts_present" not in body, "state endpoint must NOT leak full probe"


def test_dispatch_unknown_path_returns_404_with_available_list():
    api_mod = _load_api_module()
    h = _make_handler(api_mod, "/api/m060/unknown-verb")
    os.environ["M060_HEALTH_API_DRY_RUN"] = "1"
    try:
        h.do_GET()
    finally:
        os.environ.pop("M060_HEALTH_API_DRY_RUN", None)
    body = _drain(h)
    assert "404" in body
    assert "/api/m060/health" in body
    assert "/api/m060/state" in body


def test_dispatch_mutation_methods_reject_with_405():
    api_mod = _load_api_module()
    for method in ("POST", "PUT", "DELETE"):
        h = _make_handler(api_mod, "/api/m060/health", method=method)
        os.environ["M060_HEALTH_API_DRY_RUN"] = "1"
        try:
            getattr(h, f"do_{method}")()
        finally:
            os.environ.pop("M060_HEALTH_API_DRY_RUN", None)
        body = _drain(h)
        assert "405" in body, f"{method} must be rejected with 405"
        assert "read-only" in body.lower() or "mirror" in body.lower()


def test_self_check_mode_completes_without_daemon():
    """`--self-check` must complete cleanly even when the selfdef
    daemon is unreachable — required for CI smoke testing."""
    import subprocess
    result = subprocess.run(
        ["python3", str(API_PATH), "--self-check"],
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "m060-health-api" in result.stdout
    assert "sample_probe" in result.stdout


def test_healthz_and_root_return_ok():
    api_mod = _load_api_module()
    for path in ("/", "/healthz"):
        h = _make_handler(api_mod, path)
        os.environ["M060_HEALTH_API_DRY_RUN"] = "1"
        try:
            h.do_GET()
        finally:
            os.environ.pop("M060_HEALTH_API_DRY_RUN", None)
        body = _drain(h)
        assert "200" in body
        assert "\"status\": \"ok\"" in body
        assert "\"version\": \"1.0.0\"" in body
