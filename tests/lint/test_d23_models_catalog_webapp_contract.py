"""D-23 models-catalog webapp surface contract lint.

Pins the D-23 "Model Catalog" cockpit panel to the sovereignty-clean webapp
doctrine: single-file monochrome SPA served by its API daemon under
/webapp/, zero external dependencies, same-origin fetches only, READ-ONLY
(model lifecycle is signed `sovereign-osctl models …` CLI verbs, never web
mutations — R10212). Reuses the shared model-health load_catalog reader.

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
WEBAPP_HTML = REPO_ROOT / "webapp" / "d-23-models-catalog" / "index.html"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "models-catalog-api.py"
SURFACE_MAP = REPO_ROOT / "scripts" / "operator" / "surface-map.py"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int):
    env = {
        "MODELS_CATALOG_API_BIND": "127.0.0.1",
        "MODELS_CATALOG_API_PORT": str(port),
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
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/healthz", timeout=0.5
            ) as r:
                if r.status == 200:
                    return proc
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.1)
    proc.kill()
    raise RuntimeError("models-catalog-api failed to start within 6s")


def test_webapp_html_present():
    assert WEBAPP_HTML.is_file(), f"D-23 webapp asset missing: {WEBAPP_HTML}"


def test_webapp_html_is_html5():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert body.lstrip().lower().startswith("<!doctype html>")
    assert "<html lang=" in body
    assert 'name="viewport"' in body


def test_webapp_carries_sovereign_meta_tags():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert 'name="x-sovereign-module"' in body
    assert "d-23-models-catalog-webapp" in body
    assert 'name="x-sovereign-shipped-in"' in body
    assert "D-23" in body
    assert "We do not minimize anything." in body


def test_webapp_has_zero_external_dependencies():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    for host in ["https://cdn.", "http://cdn.", "https://cdnjs.", "https://unpkg.",
                 "https://fonts.googleapis.", "https://fonts.gstatic.",
                 "https://ajax.googleapis.", "https://code.jquery.", "//cdn."]:
        assert host not in body, f"webapp must NOT reference external host {host!r}"
    assert re.search(r'<script[^>]+src="https?://', body) is None
    assert re.search(r'<link[^>]+href="https?://', body) is None


def test_webapp_fetches_only_same_origin_endpoints():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    for m in re.finditer(r'fetch\(\s*(["\'])([^"\']+)\1', body):
        target = m.group(2)
        assert target.startswith("/"), f"fetch() target {target!r} not same-origin"
        assert "//" not in target


def test_webapp_is_read_only():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "/api/models-catalog/catalog" in body
    assert re.search(r'fetch\(\s*["\']/(set|apply|mutate)', body) is None


def test_webapp_declares_canonical_palette_and_mono():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert "--mono:" in body
    for token in ("--good:#7ad17a", "--bad:#ff7676", "--warn:#e6c062"):
        assert token in body, f"missing canonical palette token {token}"


def test_webapp_inlines_control_surface():
    body = WEBAPP_HTML.read_text(encoding="utf-8")
    assert 'id="control-surface"' in body
    assert "SovereignControlSurface" in body
    assert "filterSlug:'d-23-models-catalog'" in body


def test_api_daemon_serves_webapp_path():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/webapp/", timeout=3) as r:
            assert r.status == 200
            assert "text/html" in r.headers.get("Content-Type", "")
            body = r.read().decode("utf-8")
            assert "d-23-models-catalog" in body
            assert "We do not minimize anything." in body
            assert r.headers.get("X-Sovereign-Module") == "d-23-models-catalog-webapp"
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_api_daemon_catalog_endpoint_shape():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/models-catalog/catalog", timeout=3
        ) as r:
            data = json.loads(r.read())
        assert isinstance(data.get("total"), int) and data["total"] > 0
        tiers = {t["tier"] for t in data.get("tiers", [])}
        # the SRP tiers must be present in the grouped catalog
        assert {"pulse", "logic", "oracle"} & tiers, f"tiers: {tiers}"
        for t in data["tiers"]:
            for m in t["models"]:
                assert "id" in m
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_api_daemon_is_read_only():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/models-catalog/catalog", method="POST", data=b"{}"
        )
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
        assert "D-23" in data.get("shipped_in", "")
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_surface_map_registers_module():
    result = subprocess.run(
        ["python3", str(SURFACE_MAP), "coverage", "--module", "models-catalog", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, f"surface-map failed: {result.stderr[:300]}"
    data = json.loads(result.stdout)
    entries = data.get("coverage", [data])
    entry = entries[0] if entries else {}
    webapp_row = next((r for r in entry.get("matrix", []) if r.get("surface") == "webapp"), None)
    assert webapp_row is not None and webapp_row.get("state") == "shipped"


def test_nav_registry_includes_d23():
    nav = (REPO_ROOT / "webapp" / "_shared" / "nav-snippet.html").read_text()
    assert "d-23-models-catalog" in nav


# ── SDD-113: the catalog scaffold stays visible when the daemon is offline ──

def test_catalog_always_visible_when_daemon_offline():
    """The catalog section must render even with the daemon unreachable — an
    initial paint + a fallback render in the fetch catch (an honest offline card,
    never a blank #tiers). Closes the operator's D-21 bug class 'I dont see the
    grid...' applied to d-23 (SDD-111 lesson; SB-077)."""
    import re
    body = (REPO_ROOT / "webapp" / "d-23-models-catalog" / "index.html").read_text()
    # renderTiers handles the offline case explicitly (never a blank #tiers)
    assert re.search(r"if\s*\(\s*data\.offline\s*\)", body), (
        "renderTiers must handle the offline case with an explicit honest card"
    )
    # the fetch catch renders a fallback rather than leaving the catalog blank
    assert re.search(r"catch\s*\([^)]*\)\s*\{[^}]*renderTiers\(\s*\{\s*offline:\s*true", body, re.DOTALL), (
        "the fetch catch must render renderTiers({offline:true}) (never a blank catalog)"
    )
    # an initial paint runs before the live fetch
    assert body.count("renderTiers({offline: true})") >= 2, (
        "an initial paint of the scaffold must run before the live fetch"
    )
