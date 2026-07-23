"""SDD-511 (F00796) — token-law mask-coverage heatmap panel + daemon contract.

The last piece of the token-law Expose arc: a read-only cockpit panel that
renders per-layer coverage (grammar / regex / denylist / regex_denylist /
policy) as a heatmap, derived by the daemon POSTing a built-in sample scenario
to the gateway's checkpoint-free fuse route. Read-only + honest-degrade.
"""
from __future__ import annotations

import importlib.util
import json
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PANEL = REPO / "webapp" / "token-law-coverage" / "index.html"
DAEMON = REPO / "scripts" / "operator" / "token-law-coverage-api.py"
UNIT = REPO / "systemd" / "system" / "sovereign-token-law-coverage-api.service"
CATALOG = REPO / "config" / "dashboard-catalog.yaml"

CANON_LAYERS = ["grammar", "regex", "denylist", "regex_denylist", "policy"]


def _load_daemon():
    spec = importlib.util.spec_from_file_location("tlc_api", DAEMON)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ── panel ────────────────────────────────────────────────────────────────────

def test_panel_present_and_html5():
    assert PANEL.is_file()
    body = PANEL.read_text(encoding="utf-8")
    assert body.lstrip().lower().startswith("<!doctype html>")
    assert 'name="viewport"' in body
    assert "token-law-coverage-webapp" in body


def test_panel_fetches_only_the_coverage_endpoint_same_origin():
    body = PANEL.read_text(encoding="utf-8")
    assert "/api/token-law-coverage/coverage" in body, "panel must read its coverage feed"
    # every literal fetch target is same-origin (no external egress)
    for m in re.finditer(r'fetch\(\s*[\'"]([^\'"]+)[\'"]', body):
        t = m.group(1)
        assert t.startswith("/") and "//" not in t, f"non-same-origin fetch {t!r}"


def test_panel_renders_a_heatmap_and_degrades_honestly():
    body = PANEL.read_text(encoding="utf-8")
    assert 'id="heatmap"' in body and "hm-row" in body, "panel must render the per-layer heatmap"
    # a continuous color scale (permitted-fraction), not just 3 fixed states
    assert "hsl(" in body and "renderOffline" in body
    # honest-degrade wording — never fabricate when the gateway is down
    assert "offline" in body.lower() and "fabricate" in body.lower()


def test_panel_inlines_control_surface_no_external_script():
    body = PANEL.read_text(encoding="utf-8")
    assert 'id="control-surface"' in body
    assert "filterSlug:'token-law-coverage'" in body
    assert re.search(r'<script[^>]+\bsrc\s*=\s*["\'][^"\']*\.js["\']', body) is None


# ── daemon ───────────────────────────────────────────────────────────────────

def test_daemon_sample_scenario_covers_the_five_canonical_layers():
    m = _load_daemon()
    assert [name for name, _ in m.SAMPLE_LAYERS] == CANON_LAYERS
    assert len(m.SAMPLE_VOCAB) >= 8


def test_daemon_serves_the_read_only_routes():
    src = DAEMON.read_text(encoding="utf-8")
    assert "/api/token-law-coverage/coverage" in src
    assert "/v1/data-plane/token-law/fuse" in src, "coverage derives from the fuse route"
    assert "do_POST" in src and "405" in src, "the daemon is read-only (405 on writes)"


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_daemon_degrades_offline_when_gateway_down():
    """Live-spawn the daemon pointed at a closed gateway port → the coverage
    feed reports up:false + an error (never a crash, never fabricated data)."""
    port = _free_port()
    env = {
        "TOKEN_LAW_COVERAGE_API_BIND": "127.0.0.1",
        "TOKEN_LAW_COVERAGE_API_PORT": str(port),
        "SOVEREIGN_GATEWAY_ADDR": "127.0.0.1:1",  # nothing listens → offline
        "PATH": "/usr/bin:/bin",
    }
    proc = subprocess.Popen([sys.executable, str(DAEMON)], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.time() + 6
        ok = False
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=0.5) as r:
                    if r.status == 200:
                        ok = True
                        break
            except (urllib.error.URLError, OSError):
                time.sleep(0.1)
        assert ok, "daemon did not start"
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/token-law-coverage/coverage", timeout=3
        ) as r:
            payload = json.loads(r.read())
        assert payload["up"] is False and payload["error"], payload
    finally:
        proc.kill()


# ── registration ─────────────────────────────────────────────────────────────

def test_systemd_unit_loopback_and_port_8148():
    u = UNIT.read_text(encoding="utf-8")
    assert "TOKEN_LAW_COVERAGE_API_BIND=127.0.0.1" in u
    assert "TOKEN_LAW_COVERAGE_API_PORT=8148" in u
    assert "ProtectSystem=strict" in u  # R171 hardening carried


def test_catalog_entry_present_and_mapped():
    import yaml
    cat = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    entry = next((d for d in cat["dashboards"] if d["slug"] == "token-law-coverage"), None)
    assert entry is not None
    assert entry["api"] == "sovereign-token-law-coverage-api"
    assert entry["path"] == "/token-law-coverage/"
