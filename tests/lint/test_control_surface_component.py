"""Shared control-surface component + wiring (SDD-045 §2/§4).

The control-surface component renders config/control-systems.yaml (served at
GET /control-systems) as the Controls surface — the operator's "everything
can be turned on/off + tons of modes and profiles". These locks keep the
shared asset present, same-origin + read-only (copies the command, never
mutates), served by the API, and wired into the master-dashboard.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
JS = REPO / "webapp" / "_shared" / "control-surface.js"
CSS = REPO / "webapp" / "_shared" / "control-surface.css"
API = REPO / "scripts" / "operator" / "build-configurator-api.py"
MDASH = REPO / "webapp" / "master-dashboard" / "index.html"
REGISTRY = REPO / "config" / "control-systems.yaml"


def test_shared_component_files_exist():
    assert JS.is_file(), f"missing {JS}"
    assert CSS.is_file(), f"missing {CSS}"


def test_component_is_same_origin_only():
    """No CDN / external fetch — the component talks only to the same-origin
    /control-systems endpoint."""
    body = JS.read_text(encoding="utf-8")
    for m in re.finditer(r'fetch\(\s*(["\'])([^"\']+)\1', body):
        target = m.group(2)
        assert target.startswith("/") and "//" not in target, (
            f"control-surface.js fetch target {target!r} is not same-origin"
        )
    for host in ("http://", "https://", "cdn.", "unpkg", "jsdelivr"):
        assert host not in body, f"control-surface.js references external {host!r}"


def test_component_is_read_only():
    """Web never mutates privileged state — the component copies the command,
    it must not POST/PUT/DELETE or call a mutate verb."""
    body = JS.read_text(encoding="utf-8")
    assert "clipboard" in body, "component must copy the change_cli to clipboard"
    assert not re.search(r'method:\s*["\'](POST|PUT|DELETE|PATCH)', body), (
        "control-surface.js must not issue mutating HTTP requests"
    )


def test_api_serves_control_systems_endpoint():
    body = API.read_text(encoding="utf-8")
    assert "/control-systems" in body, "API must serve the /control-systems endpoint"
    assert "_load_control_systems" in body, "API must load config/control-systems.yaml"


def test_master_dashboard_wires_the_component():
    body = MDASH.read_text(encoding="utf-8")
    for needle in ('../_shared/control-surface.css',
                   '../_shared/control-surface.js',
                   'id="control-surface"',
                   'renderControls',
                   'SovereignControlSurface'):
        assert needle in body, f"master-dashboard missing control-surface wiring: {needle!r}"
    # rendered on the refresh cycle
    assert "renderControls();" in body, "renderControls() must be called from refresh()"


def test_component_renders_the_copy_command():
    """The card must surface each system's change_cli as a copy button (the
    read-only control) — the operator's way to actually flip things."""
    body = JS.read_text(encoding="utf-8")
    assert "change_cli" in body and "data-cmd" in body and "cs-cmd" in body, (
        "control-surface.js must render change_cli as a copy-command control"
    )
