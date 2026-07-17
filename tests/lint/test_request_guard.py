#!/usr/bin/env python3
"""tests/lint/test_request_guard.py — shared loopback-daemon CSRF/RCE guard.

`scripts/operator/lib/request_guard.py` is the one place the privileged
loopback daemons (jobs-api command-exec, build-configurator root OS build,
flash-api USB write) decide whether a mutating request is authentic. Before
it, a web page the operator visited could drive them cross-origin. This pins
the guard's behavior + that the three daemons actually call it on their
privileged POST paths.

Stdlib + pytest only.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "scripts" / "operator" / "lib"
GUARD = LIB / "request_guard.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


g = _load("request_guard", GUARD)


def test_allows_loopback_json_no_origin():
    assert g.guard({"Content-Type": "application/json"}, "127.0.0.1") is None
    assert g.guard({"Content-Type": "application/json"}, "::1") is None


def test_allows_same_site_loopback_origin():
    assert g.guard(
        {"Origin": "http://127.0.0.1:8100", "Content-Type": "application/json"},
        "127.0.0.1") is None


def test_blocks_cross_site_origin():
    r = g.guard({"Origin": "https://evil.example", "Content-Type": "application/json"},
                "127.0.0.1")
    assert r is not None and r[0] == 403


def test_blocks_cross_site_referer():
    r = g.guard({"Referer": "https://evil.example/x", "Content-Type": "application/json"},
                "127.0.0.1")
    assert r is not None and r[0] == 403


def test_blocks_non_loopback_peer():
    r = g.guard({"Content-Type": "application/json"}, "192.168.1.5")
    assert r is not None and r[0] == 403


def test_requires_json_by_default():
    r = g.guard({"Content-Type": "text/plain"}, "127.0.0.1")
    assert r is not None and r[0] == 415
    # simple-request form encodings also refused
    assert g.guard({"Content-Type": "multipart/form-data"}, "127.0.0.1")[0] == 415


def test_require_json_false_allows_bodyless_cancel():
    # cancel posts carry no Content-Type — loopback + no cross-site origin passes
    assert g.guard({}, "127.0.0.1", require_json=False) is None
    # but a cross-site cancel is still refused
    assert g.guard({"Origin": "https://evil.example"}, "127.0.0.1",
                   require_json=False)[0] == 403


def test_allow_nonloopback_opt_in():
    assert g.guard({"Content-Type": "application/json"}, "10.0.0.1",
                   allow_nonloopback=True) is None


def test_privileged_daemons_call_the_guard():
    """build-configurator + flash must guard their /api/run (root build /
    USB write) — regression guard so a refactor can't drop the CSRF gate."""
    for name in ("build-configurator-api.py", "flash-api.py"):
        body = (REPO / "scripts" / "operator" / name).read_text(encoding="utf-8")
        assert "import request_guard" in body, f"{name} does not import the guard"
        assert "_guard.guard(" in body, f"{name} does not call the guard"
        assert "/api/run" in body
