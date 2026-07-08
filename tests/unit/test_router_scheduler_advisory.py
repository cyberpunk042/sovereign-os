"""Layer 2 unit tests for the MS048 opt-in scheduler advisory in
scripts/inference/router.py.

Pins the CONSERVATIVE contract: the advisory is OFF by default (routing
completely unchanged), and when ON it is fail-safe (a missing/broken
scheduler never raises and never affects routing — it just yields an empty
advisory). The advisory NEVER changes the routed tier; it is observability
only (an X-Sovereign-Scheduler-Advisory header).
"""

from __future__ import annotations

import importlib.util
import os
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
ROUTER_PATH = REPO_ROOT / "scripts" / "inference" / "router.py"


def _load_router(monkeypatch, consult: bool, decide_bin: str = "/nonexistent/decide"):
    # the flags are read at import time, so set env before loading
    monkeypatch.setenv("SOVEREIGN_OS_CONSULT_SCHEDULER", "1" if consult else "0")
    monkeypatch.setenv("SELFDEF_SCHEDULER_DECIDE_BIN", decide_bin)
    monkeypatch.setenv("SOVEREIGN_OS_METRICS_DISABLE", "1")
    spec = importlib.util.spec_from_file_location("router_under_test", ROUTER_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_advisory_off_by_default(monkeypatch):
    r = _load_router(monkeypatch, consult=False)
    assert r._CONSULT_SCHEDULER is False
    # OFF → empty advisory, no bridge call at all
    assert r._scheduler_advisory({"model": "x"}) == ""


def test_advisory_on_but_scheduler_absent_is_graceful(monkeypatch):
    # ON, but the decide binary doesn't exist → graceful-offline → empty
    # advisory (routing must not be affected, no exception).
    r = _load_router(monkeypatch, consult=True, decide_bin="/nonexistent/decide")
    assert r._CONSULT_SCHEDULER is True
    assert r._scheduler_advisory({"model": "x"}) == ""


def test_advisory_never_raises_even_if_bridge_explodes(monkeypatch):
    r = _load_router(monkeypatch, consult=True)

    class Boom:
        def build_task(self, *a, **k):
            raise RuntimeError("boom")

    # force the lazy bridge to a broken stand-in
    r._bridge_mod = Boom()
    # must swallow the error and return "" — routing is never affected
    assert r._scheduler_advisory({"model": "x"}) == ""


def test_advisory_on_returns_service_from_a_fake_bridge(monkeypatch):
    r = _load_router(monkeypatch, consult=True)

    class FakeBridge:
        def build_task(self, profile, **k):
            return {"profile": profile}

        def consult(self, task, **k):
            return {
                "scheduler_available": True,
                "defer": False,
                "runtime_service": "Oracle Core",
                "backend_tier": "oracle",
            }

    r._bridge_mod = FakeBridge()
    assert r._scheduler_advisory({"model": "x"}) == "Oracle Core"


def test_advisory_surfaces_defer(monkeypatch):
    r = _load_router(monkeypatch, consult=True)

    class DeferBridge:
        def build_task(self, profile, **k):
            return {"profile": profile}

        def consult(self, task, **k):
            return {"scheduler_available": True, "defer": True, "runtime_service": None}

    r._bridge_mod = DeferBridge()
    assert r._scheduler_advisory({"model": "x"}) == "defer"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
