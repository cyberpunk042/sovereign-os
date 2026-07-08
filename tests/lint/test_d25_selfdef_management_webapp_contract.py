"""D-25 selfdef-management webapp surface contract lint.

Pins the D-25 "Self-Defense Management" cockpit panel to the sovereignty-clean
webapp doctrine: single-file monochrome SPA, zero external deps, same-origin
fetches only, READ-ONLY. This panel is BOUNDARY-SENSITIVE (R10212): sovereign-os
is the CONSUMER, selfdef is the PRODUCER. The panel only READS selfdef state via
the sanctioned M060 consumer proxy (scripts/operator/m060-health.py probe()) and
NEVER mutates selfdef — the on/off control is a clipboard-copied signed CLI verb
(sovereign-osctl selfdef {on|off}), never an HTTP mutation.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
"""
from __future__ import annotations

import json
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_HTML = REPO_ROOT / "webapp" / "d-25-selfdef-management" / "index.html"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "selfdef-management-api.py"
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int):
    env = {
        "SELFDEF_MGMT_API_BIND": "127.0.0.1",
        "SELFDEF_MGMT_API_PORT": str(port),
        "SOVEREIGN_OS_METRICS_DIR": "/tmp/sovereign-os-test-metrics",
        "PATH": "/usr/bin:/bin",
    }
    proc = subprocess.Popen(
        ["python3", str(API_DAEMON)], env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    deadline = time.time() + 6
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=0.5) as r:
                if r.status == 200:
                    return proc
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.1)
    proc.kill()
    raise RuntimeError("selfdef-management-api failed to start within 6s")


def test_webapp_html_present():
    assert WEBAPP_HTML.is_file(), f"D-25 webapp asset missing: {WEBAPP_HTML}"


def test_webapp_html_is_html5():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert body.lstrip().lower().startswith("<!doctype html>")
    assert "<html lang=" in body
    assert 'name="viewport"' in body


def test_webapp_carries_sovereign_meta_tags():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "d-25-selfdef-management-webapp" in body
    assert "D-25" in body
    assert "We do not minimize anything." in body


def test_webapp_declares_read_only_boundary():
    """R10212: the panel must self-declare it is a READ-ONLY consumer of the
    selfdef producer (documented boundary meta tag)."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "R10212" in body
    assert "x-sovereign-boundary" in body


def test_webapp_has_zero_external_dependencies():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    for host in ["https://cdn.", "http://cdn.", "https://cdnjs.", "https://unpkg.",
                 "https://fonts.googleapis.", "https://fonts.gstatic.", "//cdn."]:
        assert host not in body
    assert re.search(r'<script[^>]+src="https?://', body) is None
    assert re.search(r'<link[^>]+href="https?://', body) is None


def test_webapp_fetches_only_same_origin_endpoints():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    for m in re.finditer(r'fetch\(\s*(["\'])([^"\']+)\1', body):
        target = m.group(2)
        assert target.startswith("/") and "//" not in target


def test_webapp_is_read_only():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "/api/selfdef-management/state" in body
    assert re.search(r'fetch\(\s*["\']/(set|apply|mutate)', body) is None


def test_webapp_declares_canonical_palette_and_mono():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "--mono:" in body
    for token in ("--good:#7ad17a", "--bad:#ff7676", "--warn:#e6c062"):
        assert token in body


def test_webapp_inlines_control_surface():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert 'id="control-surface"' in body
    assert "SovereignControlSurface" in body
    # filterSlug matches config/control-systems.yaml selfdef.applies_to so the
    # signed on/off control actually renders on this panel.
    assert "filterSlug:'selfdef-management'" in body


def test_api_daemon_serves_webapp_and_state():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/webapp/", timeout=3) as r:
            assert r.status == 200
            body = r.read().decode("utf-8")
            assert "d-25-selfdef-management" in body
            assert r.headers.get("X-Sovereign-Module") == "d-25-selfdef-management-webapp"
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/selfdef-management/state", timeout=6) as r:
            data = json.loads(r.read())
        # graceful consumer envelope: selfdef + m060 blocks always present, even
        # when the producer is unreachable (the CI/dev case).
        assert "selfdef" in data and "enablement" in data["selfdef"]
        assert "m060_chain" in data and "state" in data["m060_chain"]
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_api_daemon_is_read_only():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/selfdef-management/state", method="POST", data=b"{}")
        try:
            urllib.request.urlopen(req, timeout=3)
            raised = False
        except urllib.error.HTTPError as e:
            raised = e.code == 405
        assert raised, "POST must be rejected 405 (read-only consumer cockpit — R10212)"
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_api_daemon_version_advertises_webapp_surface():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/version", timeout=3) as r:
            data = json.loads(r.read())
        assert "webapp" in data.get("surfaces", [])
        assert "D-25" in data.get("shipped_in", "")
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_surface_map_registers_module():
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module", "selfdef-management", "--json"],
        capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entry = (data.get("coverage", [data]) or [data])[0]
    webapp_row = next((r for r in entry.get("matrix", []) if r.get("surface") == "webapp"), None)
    assert webapp_row is not None and webapp_row.get("state") == "shipped"


def test_nav_registry_includes_d25():
    nav = (REPO_ROOT / "webapp" / "_shared" / "nav-snippet.html").read_text()
    assert "d-25-selfdef-management" in nav
