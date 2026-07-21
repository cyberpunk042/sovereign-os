"""tests/lint/test_networking_api_contract.py — CI contract for the unified
networking-api daemon (F-2026-070).

The unified daemon consolidates network-edge (R507), edge-firewall (R504), and
D-12 rules-mirror (R10113) into one read-only surface on port 8139.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DAEMON = REPO / "scripts" / "operator" / "networking-api.py"
UNIT = REPO / "systemd" / "system" / "sovereign-networking-api.service"


@pytest.fixture
def networking_api_url():
    return "http://127.0.0.1:8139"


def test_daemon_file_exists():
    assert DAEMON.is_file(), f"missing {DAEMON}"


def test_systemd_unit_exists():
    assert UNIT.is_file(), f"missing {UNIT}"


def test_daemon_is_executable():
    import os
    assert os.access(DAEMON, os.X_OK), f"{DAEMON} is not executable"


def test_dry_run_validates():
    proc = subprocess.run(
        [sys.executable, str(DAEMON)],
        capture_output=True,
        text=True,
        env={**dict(subprocess.os.environ), "NETWORKING_API_DRY_RUN": "1"},
    )
    assert proc.returncode == 0, proc.stderr
    assert "DRY-RUN" in proc.stdout or "configuration validated" in proc.stdout


class TestLiveEndpoints:
    """Start the daemon on an ephemeral port and hit every endpoint."""

    @pytest.fixture(scope="class")
    def url(self):
        import urllib.request
        port = 17333  # ephemeral, unlikely to collide
        proc = subprocess.Popen(
            [sys.executable, str(DAEMON), "--bind", "127.0.0.1", "--port", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # Wait until the daemon actually ACCEPTS on the port — poll the socket
        # rather than trusting the stdout banner. Under the full-suite load the
        # banner can appear before the listener is ready (or the process can die
        # on startup), which yielded a URL to a not-ready daemon → intermittent
        # ECONNREFUSED. Poll up to ~10s; if it never comes up, fail loudly with
        # the daemon's own stderr instead of a bare connection error downstream.
        import socket as _socket
        import time
        base = f"http://127.0.0.1:{port}"
        ready = False
        for _ in range(100):
            if proc.poll() is not None:  # daemon exited during startup
                break
            with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as _s:
                _s.settimeout(0.5)
                if _s.connect_ex(("127.0.0.1", port)) == 0:
                    ready = True
                    break
            time.sleep(0.1)
        if not ready:
            err = b""
            try:
                if proc.poll() is not None:
                    err = (proc.stderr.read() or b"")
            except Exception:  # noqa: BLE001
                pass
            proc.terminate()
            raise RuntimeError(
                f"networking-api did not accept on :{port} within 10s "
                f"(rc={proc.poll()}); stderr: {err.decode(errors='replace')[:500]}")
        yield base
        proc.terminate()
        proc.wait(timeout=5)

    def _get(self, url: str, path: str) -> tuple[int, dict]:
        import urllib.request
        import urllib.error
        req = urllib.request.Request(f"{url}{path}", headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 loopback
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            try:
                return e.code, json.loads(body)
            except json.JSONDecodeError:
                return e.code, {"raw": body}

    def test_healthz(self, url):
        status, body = self._get(url, "/healthz")
        assert status == 200
        assert body["status"] == "ok"

    def test_version(self, url):
        status, body = self._get(url, "/version")
        assert status == 200
        assert body["module"] == "networking-api"
        assert "components" in body
        for key in ("network-edge", "edge-firewall", "rules-mirror"):
            assert key in body["components"]

    # network-edge ──
    def test_ne_detect(self, url):
        status, body = self._get(url, "/detect")
        assert status == 200
        assert "interfaces" in body

    def test_ne_detect_namespaced(self, url):
        status, body = self._get(url, "/network-edge/detect")
        assert status == 200
        assert "interfaces" in body

    def test_ne_interfaces(self, url):
        status, body = self._get(url, "/interfaces")
        assert status == 200
        assert "count" in body

    def test_ne_nat_chain(self, url):
        status, body = self._get(url, "/nat-chain")
        assert status == 200

    def test_ne_opnsense_status(self, url):
        status, body = self._get(url, "/opnsense/status")
        assert status == 200

    def test_ne_opnsense_capabilities(self, url):
        status, body = self._get(url, "/opnsense/capabilities")
        assert status == 200

    # edge-firewall ──
    def test_ef_state(self, url):
        status, body = self._get(url, "/state")
        assert status == 200
        assert "local" in body

    def test_ef_state_namespaced(self, url):
        status, body = self._get(url, "/edge-firewall/state")
        assert status == 200
        assert "local" in body

    def test_ef_candidates(self, url):
        status, body = self._get(url, "/candidates")
        assert status == 200
        assert "candidates" in body

    def test_ef_recommend(self, url):
        status, body = self._get(url, "/recommend")
        assert status == 200
        assert "recommendations" in body

    def test_ef_install_plan_bad_request(self, url):
        status, body = self._get(url, "/install-plan")
        assert status == 400
        assert "candidate" in body.get("error", "").lower()

    # rules-mirror ──
    def test_rm_snapshot(self, url):
        status, body = self._get(url, "/api/d-12/snapshot")
        assert status == 200
        assert "schema_version" in body

    def test_404(self, url):
        import urllib.request
        import urllib.error
        req = urllib.request.Request(f"{url}/nonexistent", headers={"Accept": "application/json"})
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req, timeout=5)
        assert exc_info.value.code == 404

    def test_405_post(self, url):
        import urllib.request
        req = urllib.request.Request(f"{url}/detect", method="POST")
        with pytest.raises(Exception):
            urllib.request.urlopen(req, timeout=5)


def test_dashboard_catalog_points_to_unified():
    import yaml
    catalog = yaml.safe_load((REPO / "config" / "dashboard-catalog.yaml").read_text())
    slugs = {d["slug"]: d for d in catalog.get("dashboards", [])}
    for slug in ("network-edge", "edge-firewall", "d-12-networking"):
        assert slugs[slug]["api"] == "sovereign-networking-api", f"{slug} api mismatch"


def test_dashboard_routes_use_port_8139():
    import yaml
    routes = yaml.safe_load((REPO / "config" / "dashboard-routes.yaml").read_text())
    by_slug = {r["slug"]: r for r in routes.get("routes", [])}
    for slug in ("network-edge", "edge-firewall", "d-12-networking"):
        assert by_slug[slug]["port"] == 8139, f"{slug} port mismatch"


def test_panel_api_routes_maps_d12_to_8139():
    import yaml
    doc = yaml.safe_load((REPO / "config" / "panel-api-routes.yaml").read_text())
    by_prefix = {r["prefix"]: r for r in doc.get("routes", [])}
    assert by_prefix.get("/api/d-12", {}).get("port") == 8139
