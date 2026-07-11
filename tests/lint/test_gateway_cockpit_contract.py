#!/usr/bin/env python3
"""
tests/lint/test_gateway_cockpit_contract.py — Phase-1 "cockpit ↔ live gateway"
contract.

Guards the read-only wiring that surfaces the running sovereign-gatewayd
(:8787, the M048 provider-inversion gateway over the deterministic cortex) in
the cockpit:

  * the shared probe helper (scripts/operator/lib/gateway_probe.py) degrades
    gracefully when the gateway is down and still reads the persisted Memory-OS
    snapshot from disk;
  * the trinity + model-health api daemons expose a read-only /gateway probe;
  * the osctl `gateway` verb delegates to the same helper;
  * both panels render the sovereignty tripwire section.

Zero third-party deps — stdlib + pytest only, no running daemon required.
"""
from __future__ import annotations

import importlib.util
import json
import socket
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    assert spec and spec.loader, f"cannot load {rel}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _dead_port() -> int:
    """An ephemeral port that was just released — connects → connection refused."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_probe_degrades_when_gateway_down(tmp_path, monkeypatch):
    gp = _load("gateway_probe", "scripts/operator/lib/gateway_probe.py")
    monkeypatch.setenv("SOVEREIGN_GATEWAY_MEMORY", str(tmp_path / "absent.json"))
    d = gp.probe_gateway(f"127.0.0.1:{_dead_port()}", timeout=0.5)
    assert d["up"] is False, "a dead gateway must report up=False, not raise"
    assert d["error"], "the failure reason must be surfaced"
    assert isinstance(d["surfaces"], list)
    assert d["memory"]["exists"] is False
    # the whole thing must be JSON-serialisable (it crosses the HTTP boundary)
    json.dumps(d)


def test_probe_reads_persisted_memory_from_disk(tmp_path, monkeypatch):
    gp = _load("gateway_probe", "scripts/operator/lib/gateway_probe.py")
    store = tmp_path / "cortex.json"
    store.write_text(json.dumps({
        "hot": [{"id": 1}, {"id": 2}, {"id": 3}],
        "cold": {"1": {}, "2": {}, "3": {}},
        "capacity": None,
    }))
    monkeypatch.setenv("SOVEREIGN_GATEWAY_MEMORY", str(store))
    # Even with the daemon DOWN, the persisted snapshot is readable from disk —
    # this is what makes the activation-#2 persistence milestone visible.
    d = gp.probe_gateway(f"127.0.0.1:{_dead_port()}", timeout=0.5)
    assert d["memory"]["exists"] is True
    assert d["memory"]["items"] == 3
    assert d["memory"]["cold"] == 3


def test_daemons_and_cli_expose_the_gateway_probe():
    trinity = (REPO / "scripts/operator/trinity-api.py").read_text()
    assert '"/gateway"' in trinity and "gateway_probe" in trinity, \
        "trinity-api must serve a read-only /gateway probe"

    mh = (REPO / "scripts/operator/model-health-api.py").read_text()
    assert '"/api/models/gateway"' in mh and "gateway_probe" in mh, \
        "model-health-api must serve /api/models/gateway"

    osctl = (REPO / "scripts/sovereign-osctl").read_text()
    assert "gateway)" in osctl and "gateway_probe.py" in osctl, \
        "osctl must delegate the `gateway` verb to the shared probe helper"


def test_panels_render_the_sovereignty_tripwire():
    for slug in ("trinity", "d-03-model-health"):
        body = (REPO / "webapp" / slug / "index.html").read_text()
        assert "gw-tripwire" in body, f"{slug}: missing the tripwire element"
        assert "refreshGateway" in body, f"{slug}: missing the gateway refresh"
        low = body.lower()
        assert ("never-cloud-spill" in low or "never_cloud_spill" in low), \
            f"{slug}: the never-cloud-spill invariant must be surfaced"


def test_probe_is_read_only():
    """The helper must never issue a mutating verb — the cockpit is read-only."""
    src = (REPO / "scripts/operator/lib/gateway_probe.py").read_text()
    assert 'method="GET"' in src, "probe must GET"
    for verb in ('method="POST"', 'method="PUT"', 'method="DELETE"', 'method="PATCH"'):
        assert verb not in src, f"probe must not {verb}"
