"""D-24 cpu-features webapp surface contract lint.

Pins the D-24 "CPU Features" cockpit panel to the sovereignty-clean webapp
doctrine: single-file monochrome SPA, zero external deps, same-origin
fetches only, READ-ONLY (pure capability observation — R10212). Reuses the
shipped scripts/hardware/avx512-advisor.py.

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
WEBAPP_HTML = REPO_ROOT / "webapp" / "d-24-cpu-features" / "index.html"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "cpu-features-api.py"
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int):
    env = {
        "CPU_FEATURES_API_BIND": "127.0.0.1",
        "CPU_FEATURES_API_PORT": str(port),
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
    raise RuntimeError("cpu-features-api failed to start within 6s")


def test_webapp_html_present():
    assert WEBAPP_HTML.is_file(), f"D-24 webapp asset missing: {WEBAPP_HTML}"


def test_webapp_html_is_html5():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert body.lstrip().lower().startswith("<!doctype html>")
    assert "<html lang=" in body
    assert 'name="viewport"' in body


def test_webapp_carries_sovereign_meta_tags():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "d-24-cpu-features-webapp" in body
    assert "D-24" in body
    assert "We do not minimize anything." in body


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
    assert "/api/cpu-features/probe" in body
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
    assert "filterSlug:'d-24-cpu-features'" in body


def test_api_daemon_serves_webapp_and_probe():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/webapp/", timeout=3) as r:
            assert r.status == 200
            body = r.read().decode("utf-8")
            assert "d-24-cpu-features" in body
            assert r.headers.get("X-Sovereign-Module") == "d-24-cpu-features-webapp"
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/cpu-features/probe", timeout=6) as r:
            data = json.loads(r.read())
        # probe returns either real extension data or an honest error envelope
        assert "extensions" in data or "error" in data
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_api_daemon_is_read_only():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/cpu-features/probe", method="POST", data=b"{}")
        try:
            urllib.request.urlopen(req, timeout=3)
            raised = False
        except urllib.error.HTTPError as e:
            raised = e.code == 405
        assert raised, "POST must be rejected 405 (read-only cockpit)"
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_api_daemon_version_advertises_webapp_surface():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/version", timeout=3) as r:
            data = json.loads(r.read())
        assert "webapp" in data.get("surfaces", [])
        assert "D-24" in data.get("shipped_in", "")
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_surface_map_registers_module():
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module", "cpu-features", "--json"],
        capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr[:300]
    data = json.loads(result.stdout)
    entry = (data.get("coverage", [data]) or [data])[0]
    webapp_row = next((r for r in entry.get("matrix", []) if r.get("surface") == "webapp"), None)
    assert webapp_row is not None and webapp_row.get("state") == "shipped"


def test_nav_registry_includes_d24():
    nav = (REPO_ROOT / "webapp" / "_shared" / "nav-snippet.html").read_text()
    assert "d-24-cpu-features" in nav


# ── SDD-115: the CPU-features scaffold stays visible when the daemon is offline ──

def test_sections_always_visible_when_daemon_offline():
    """The four sections must render even with the daemon unreachable — an
    initial paint + a fallback render in the fetch catch (an honest offline card,
    never blank). The SDD-111/113 lesson applied to d-24 (SB-077)."""
    import re
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert re.search(r"if\s*\(\s*probe\.offline\s*\)", body), (
        "render() must handle the offline case with an explicit honest card"
    )
    assert re.search(r"catch\s*\([^)]*\)\s*\{[^}]*render\(\s*\{\s*offline:\s*true", body, re.DOTALL), (
        "the fetch catch must render render({offline:true}, ...) (never a blank panel)"
    )
    assert body.count("render({offline: true}, {}, {})") >= 2, (
        "an initial paint of the scaffold must run before the live fetch"
    )
