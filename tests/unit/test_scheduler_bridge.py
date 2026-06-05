"""Layer 2 unit tests for scripts/inference/scheduler-bridge.py (MS048).

Locks the cross-repo consumer contract: the runtime gateway's consumption
of the selfdef-scheduler-decide Decision (route → backend tier, honor
Hibernate, graceful-offline). The producer lives in selfdef; this test
pins the sovereign-os CONSUMER obligations without needing the real binary
(a tiny fake binary stands in for the producer).
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import stat
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
BRIDGE_PATH = REPO_ROOT / "scripts" / "inference" / "scheduler-bridge.py"


def _load_bridge():
    spec = importlib.util.spec_from_file_location("scheduler_bridge", BRIDGE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bridge = _load_bridge()


def _fake_decide_binary(tmp_path: pathlib.Path, route: str, *, exit_code: int = 0,
                        stdout: str | None = None) -> str:
    """Write a tiny fake selfdef-scheduler-decide that emits a Decision with
    the given route (or arbitrary stdout / exit code)."""
    if stdout is None:
        decision = {
            "request_id": "req-test",
            "profile": "careful",
            "route": route,
            "axis_scores": {"compound": 0.7},
            "rationale": f"route={route} [test]",
        }
        stdout = json.dumps(decision)
    script = tmp_path / "fake-decide"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"sys.stdout.write({stdout!r})\n"
        f"sys.exit({exit_code})\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(script)


# ---- build_task -----------------------------------------------------------

def test_build_task_carries_profile_and_four_axes():
    t = bridge.build_task("careful", latency=0.7, cost=0.6, risk=0.2, energy=0.5)
    assert t["profile"] == "careful"
    assert t["latency"] == 0.7 and t["cost"] == 0.6
    assert t["risk"] == 0.2 and t["energy"] == 0.5
    # the two substrate axes are NEVER sent (measured by the binary)
    assert "hardware_pressure" not in t and "human_attention" not in t


def test_build_task_omits_request_id_when_absent():
    assert "request_id" not in bridge.build_task("fast")
    assert bridge.build_task("fast", request_id="r1")["request_id"] == "r1"


# ---- route → tier mapping (obligation #2) ---------------------------------

def test_route_to_tier_covers_all_five_routes():
    assert bridge.ROUTE_TO_TIER == {
        "blackwell": "oracle",
        "rtx3090": "scout",
        "cpu": "cortex",
        "hybrid": "hybrid",
        "hibernate": "defer",
    }


# ---- consult: real-ish (fake binary) --------------------------------------

def test_consult_maps_blackwell_to_oracle(tmp_path):
    b = _fake_decide_binary(tmp_path, "blackwell")
    v = bridge.consult(bridge.build_task("careful"), binary=b)
    assert v["scheduler_available"] is True
    assert v["route"] == "blackwell"
    assert v["backend_tier"] == "oracle"
    assert v["runtime_service"] == "Oracle Core"
    assert v["defer"] is False
    assert v["compound"] == 0.7


def test_route_to_service_via_tier(tmp_path):
    # the three compute routes map to the three running services
    for route, service in [
        ("blackwell", "Oracle Core"),
        ("rtx3090", "Logic Engine"),
        ("cpu", "Pulse"),
    ]:
        b = _fake_decide_binary(tmp_path, route)
        v = bridge.consult(bridge.build_task("production"), binary=b)
        assert v["runtime_service"] == service, route


def test_hybrid_and_defer_have_no_single_service(tmp_path):
    for route in ("hybrid", "hibernate"):
        b = _fake_decide_binary(tmp_path, route)
        v = bridge.consult(bridge.build_task("production"), binary=b)
        assert v["runtime_service"] is None, route


def test_consult_hibernate_sets_defer(tmp_path):
    b = _fake_decide_binary(tmp_path, "hibernate")
    v = bridge.consult(bridge.build_task("careful"), binary=b)
    assert v["route"] == "hibernate"
    assert v["backend_tier"] == "defer"
    assert v["defer"] is True  # obligation #1


# ---- consult: graceful offline (obligation: never crash/fabricate) --------

def test_consult_missing_binary_is_unavailable():
    v = bridge.consult(bridge.build_task("fast"), binary="/nonexistent/decide")
    assert v["scheduler_available"] is False
    assert v["route"] is None and v["backend_tier"] is None
    assert v["defer"] is False  # not a scheduler defer — gateway uses own routing
    assert "reason" in v


def test_consult_nonzero_exit_is_unavailable(tmp_path):
    b = _fake_decide_binary(tmp_path, "blackwell", exit_code=2,
                            stdout="bad profile")
    v = bridge.consult(bridge.build_task("careful"), binary=b)
    assert v["scheduler_available"] is False


def test_consult_unparseable_output_is_unavailable(tmp_path):
    b = _fake_decide_binary(tmp_path, "blackwell", stdout="{not json")
    v = bridge.consult(bridge.build_task("careful"), binary=b)
    assert v["scheduler_available"] is False
    assert "unparseable" in v["reason"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
