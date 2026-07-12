#!/usr/bin/env python3
"""
tests/lint/test_brain_panel_contract.py — the Sovereign Brain observatory + console.

Guards the dedicated panel that makes the Rust intelligence layer observable +
operable (not the status-strip that trinity/model-health carry):

  * brain-api serves the observe feeds (status + DECODED cortex memory + the
    Python Memory-OS store + the daemon map) and the operate surfaces (a routing
    probe + a chat proxy), and is read-only over memory;
  * the panel renders the memory browser, the routing probe, chat, the daemon
    map, and the sovereignty tripwire;
  * it is registered (dashboard-catalog + app-shell nav + a systemd unit).

Stdlib + pytest only.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def test_brain_api_exposes_observe_and_operate():
    src = _read("scripts/operator/brain-api.py")
    for ep in ("/brain.json", "/brain/memory", "/brain/route", "/brain/chat", "/brain/daemons"):
        assert ep in src, f"brain-api missing endpoint {ep}"
    # observe: decodes BOTH memory stores + the daemon map
    assert "cortex_memory" in src and "python_memory" in src and "daemon_map" in src
    assert "MEMORY_TYPES" in src, "must decode the 8 CoALA memory types, not a count"


def test_brain_api_is_read_only_over_memory():
    src = _read("scripts/operator/brain-api.py")
    # the only mutating verb is POST /brain/chat (a non-mutating compute); there
    # is no memory-write path in the daemon (forget/clear stay CLI-gated).
    assert 'if parsed.path.rstrip("/") != "/brain/chat"' in src, \
        "do_POST must accept only /brain/chat"
    for forbidden in ('open(PY_STORE, "w"', 'open(path, "w"', "def forget", "def clear"):
        assert forbidden not in src, f"brain-api must not {forbidden} — memory is read-only here"
    # the routing probe must use the no-learn endpoint so previewing never
    # pollutes memory (the /v1/simple-explain read-only sibling of /v1/simple).
    assert "/v1/simple-explain" in src, "routing probe must use /v1/simple-explain (no-learn)"
    assert "/v1/simple\"" not in src.replace("/v1/simple-explain", ""), \
        "routing probe must not POST the learning /v1/simple"


def test_brain_panel_renders_memory_and_operate():
    body = _read("webapp/brain/index.html")
    assert 'id="mem-rows"' in body and "renderMemRows" in body, "cortex memory browser missing"
    assert 'id="pymem-rows"' in body and "renderPyMemRows" in body, "Python Memory-OS browser missing"
    assert 'id="probe-axes"' in body and "buildAxes" in body, "routing probe missing"
    assert 'id="chat-log"' in body and "/brain/chat" in body, "chat console missing"
    assert 'id="daemon-rows"' in body and "renderDaemons" in body, "daemon map missing"
    assert 'id="gw-tripwire"' in body, "sovereignty tripwire missing"


def test_brain_memory_lifecycle_controls_are_surfaced():
    # the CLI-gated Memory-OS lifecycle (forget/undo/decide) is offered on the
    # brain panel via the control-surface (copy-able commands; mutation stays CLI).
    cs = _read("config/control-systems.yaml")
    import yaml  # PyYAML is available in the lint env
    systems = yaml.safe_load(cs)["systems"]
    on_brain = {s["id"] for s in systems if "brain" in (s.get("applies_to") or [])}
    assert {"memory-forget", "memory-undo"} <= on_brain, \
        f"forget/undo must be surfaced on the brain panel (got {on_brain})"


def test_old_strips_cross_link_to_the_brain():
    for slug in ("trinity", "d-03-model-health"):
        body = _read(f"webapp/{slug}/index.html")
        assert "../brain/" in body, f"{slug} must link to the Sovereign Brain observatory"


def test_brain_is_registered_everywhere():
    cat = _read("config/dashboard-catalog.yaml")
    assert "slug: brain" in cat and "sovereign-brain-api" in cat, "not in dashboard-catalog"
    shell = _read("webapp/_shared/app-shell-snippet.html")
    assert "dir:'brain'" in shell, "not in the app-shell nav catalog"
    unit = _read("systemd/system/sovereign-brain-api.service")
    assert "brain-api.py" in unit and "BRAIN_API_PORT=8141" in unit, "systemd unit missing/misbound"
