"""D-22 lm-status-operability webapp surface contract lint.

Pins the D-22 "Language Model Status & Operability" cockpit panel to the
same sovereignty-clean webapp doctrine every other panel obeys: a
single-file monochrome SPA served by its API daemon under /webapp/ from
the SAME host:port binding as the JSON endpoints, zero external
dependencies, same-origin fetches only, and READ-ONLY (all model/agent
actions are MS003-signed CLI verbs, never web mutations — R10212).

The panel is a different *rendering* of the shared model-health core
(scripts/inference/model-health.py) — per-device (CPU0/GPU0/GPU1) Model
0/1/2 status + operability Actions/Tests + a render-only Chat — NOT a new
data source.

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
WEBAPP_HTML = REPO_ROOT / "webapp" / "d-22-lm-status-operability" / "index.html"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "lm-status-operability-api.py"
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int):
    env = {
        "LM_STATUS_API_BIND": "127.0.0.1",
        "LM_STATUS_API_PORT": str(port),
        "SOVEREIGN_OS_METRICS_DIR": "/tmp/sovereign-os-test-metrics",
        "PATH": "/usr/bin:/bin",
    }
    proc = subprocess.Popen(
        ["python3", str(API_DAEMON)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    deadline = time.time() + 6
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/healthz", timeout=0.5
            ) as r:
                if r.status == 200:
                    return proc
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.1)
    proc.kill()
    raise RuntimeError("lm-status-operability-api failed to start within 6s")


def test_webapp_html_present():
    assert WEBAPP_HTML.is_file(), f"D-22 webapp asset missing: {WEBAPP_HTML}"


def test_webapp_html_is_html5():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert body.lstrip().lower().startswith("<!doctype html>")
    assert "<html lang=" in body
    assert 'name="viewport"' in body


def test_webapp_carries_sovereign_meta_tags():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert 'name="x-sovereign-module"' in body
    assert "d-22-lm-status-operability-webapp" in body
    assert 'name="x-sovereign-shipped-in"' in body
    assert "D-22" in body
    assert 'name="x-sovereign-standing-rule"' in body
    assert "We do not minimize anything." in body


def test_webapp_has_zero_external_dependencies():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    forbidden_hosts = [
        "https://cdn.", "http://cdn.", "https://cdnjs.",
        "https://unpkg.", "https://fonts.googleapis.",
        "https://fonts.gstatic.", "https://ajax.googleapis.",
        "https://code.jquery.", "https://stackpath.",
        "https://maxcdn.", "https://bootstrapcdn.",
        "https://use.fontawesome.", "//cdn.",
    ]
    for host in forbidden_hosts:
        assert host not in body, f"webapp must NOT reference external host {host!r}"
    assert re.search(r'<script[^>]+src="https?://', body) is None
    assert re.search(r'<link[^>]+href="https?://', body) is None


def test_webapp_fetches_only_same_origin_endpoints():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    for m in re.finditer(r'fetch\(\s*(["\'])([^"\']+)\1', body):
        target = m.group(2)
        assert target.startswith("/"), f"fetch() target {target!r} not same-origin"
        assert "//" not in target


def test_webapp_advertises_read_only_endpoints():
    """The webapp must wire against the read-only lm-status endpoints;
    mutation verbs stay CLI-only (R10212). No POST fetch target may leak."""
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "/api/lm-status/devices" in body
    # No mutating fetch — every fetch() is a GET of a same-origin read endpoint,
    # and no /set-style verb is a fetch target.
    assert re.search(r'fetch\(\s*["\']/(set|apply|mutate)', body) is None, (
        "webapp leaks a mutation verb as fetch() target (R10212 violation)"
    )
    # Actions must be clipboard-copied signed CLI verbs, never HTTP writes.
    assert "navigator.clipboard.writeText" in body, (
        "operability Actions must clipboard-copy MS003-signed CLI verbs"
    )
    assert "method:" not in body or "'POST'" not in body, (
        "webapp must not issue a POST"
    )


def test_api_daemon_serves_webapp_path():
    """Live-spawn the daemon and assert GET /webapp/ returns 200 text/html
    with the §1g standing rule embedded."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/webapp/", timeout=3
        ) as r:
            assert r.status == 200
            assert "text/html" in r.headers.get("Content-Type", "")
            body = r.read().decode("utf-8")
            assert "<!DOCTYPE html>" in body or "<!doctype html>" in body
            assert "d-22-lm-status-operability" in body
            assert "We do not minimize anything." in body
            assert r.headers.get("X-Sovereign-Module") == \
                "d-22-lm-status-operability-webapp"
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_webapp_aliases():
    """/webapp, /webapp/, /webapp/index.html all resolve to the SPA."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        for path in ("/webapp", "/webapp/", "/webapp/index.html"):
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}{path}", timeout=3
            ) as r:
                assert r.status == 200
                assert "text/html" in r.headers.get("Content-Type", "")
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_devices_endpoint_shape():
    """/api/lm-status/devices returns the per-device (CPU0/GPU0/GPU1) shape
    with 3 Model slots each — the exact contract the webapp renders."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/lm-status/devices", timeout=3
        ) as r:
            data = json.loads(r.read())
        slots = [d["slot"] for d in data.get("devices", [])]
        assert slots == ["CPU0", "GPU0", "GPU1"], f"unexpected device slots: {slots}"
        for d in data["devices"]:
            assert len(d.get("models", [])) == 3, (
                f"device {d['slot']} must expose Model 0/1/2 slots"
            )
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_is_read_only():
    """POST/PUT/DELETE must be fail-closed with 405 (R10212)."""
    port = _free_port()
    proc = _spawn_api(port)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/lm-status/devices", method="POST", data=b"{}"
        )
        try:
            urllib.request.urlopen(req, timeout=3)
            raised = False
        except urllib.error.HTTPError as e:
            raised = e.code == 405
        assert raised, "POST must be rejected 405 (read-only cockpit)"
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_api_daemon_version_advertises_webapp_surface():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/version", timeout=3
        ) as r:
            data = json.loads(r.read())
        assert "webapp" in data.get("surfaces", []), (
            f"/version must advertise 'webapp' surface; got {data}"
        )
        assert "D-22" in data.get("shipped_in", ""), (
            f"/version shipped_in must mention D-22; got {data}"
        )
    finally:
        proc.kill()
        proc.wait(timeout=3)


def test_surface_map_registers_module():
    """surface-map must track lm-status-operability with webapp shipped."""
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module",
         "lm-status-operability", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"surface-map coverage lm-status-operability failed: {result.stderr[:300]}"
    )
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    matrix = entry.get("matrix", [])
    webapp_row = next((r for r in matrix if r.get("surface") == "webapp"), None)
    assert webapp_row is not None
    assert webapp_row.get("state") == "shipped", (
        f"lm-status-operability webapp surface must be shipped; got {webapp_row}"
    )


def test_webapp_quotes_standing_rule_in_footer():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "<footer" in body and "</footer>" in body
    footer = body[body.index("<footer"): body.index("</footer>")]
    assert "We do not minimize anything." in footer
    assert "§1g" in footer


def test_nav_registry_includes_d22():
    nav = (REPO_ROOT / "webapp" / "_shared" / "nav-snippet.html").read_text()
    assert "d-22-lm-status-operability" in nav, (
        "D-22 must be registered in the nav-snippet DASHBOARDS array"
    )
