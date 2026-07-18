"""M060 D-03 (R10069-R10074) — model-health API + webapp surface contract.

Drives the D-03 cockpit dashboard from a shell to PRODUCTION: the dashboard
HTML existed but fetched `/api/models/health` (+ `/stream`) with no backend.
This locks the full §1g 8-surface stack now wired:

  core    scripts/inference/model-health.py   (catalog↔SRP topology↔GPU↔runtime)
  cli     sovereign-osctl model-health <verb>
  api     scripts/operator/model-health-api.py  (read-only HTTP)
  webapp  webapp/d-03-model-health/index.html   (served by the api)
  service systemd/system/sovereign-model-health-api.service

The core joins models/catalog.yaml to the M075 SRP topology (Conductor/Logic/
Oracle), overlays live nvidia-smi GPU telemetry + optional inference-fabric
runtime state. Per operator §1g (verbatim, sacrosanct): "We do not minimize
anything." Read-only surface — model load/unload are MS003-signed CLI verbs.
"""
from __future__ import annotations

import json
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE = REPO_ROOT / "scripts" / "inference" / "model-health.py"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "model-health-api.py"
SYSTEMD_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-model-health-api.service"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
WEBAPP = REPO_ROOT / "webapp" / "d-03-model-health" / "index.html"
CATALOG = REPO_ROOT / "models" / "catalog.yaml"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int):
    env = {
        "MODEL_HEALTH_API_BIND": "127.0.0.1",
        "MODEL_HEALTH_API_PORT": str(port),
        "SOVEREIGN_OS_METRICS_DIR": "/tmp/sovereign-os-test-metrics",
        "PATH": "/usr/bin:/bin",
    }
    proc = subprocess.Popen(
        ["python3", str(API_DAEMON)],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
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
    raise RuntimeError("model-health-api failed to start within 6s")


# ---- structural -----------------------------------------------------------

def test_core_present_and_runs():
    assert CORE.is_file(), f"core missing: {CORE}"
    out = subprocess.run(
        ["python3", str(CORE), "status", "--json"],
        capture_output=True, text=True, timeout=15, check=True,
    )
    snap = json.loads(out.stdout)
    assert set(snap) >= {"summary", "roles", "gpus", "models", "kvcache", "heatmap"}
    assert set(snap["roles"]) >= {"conductor", "logic", "oracle"}


def test_core_parses_catalog_into_srp_roles():
    """The catalog YAML subset parser must extract real models and bucket them
    by SRP role (no invention — every row comes from models/catalog.yaml)."""
    out = subprocess.run(
        ["python3", str(CORE), "catalog", "--json"],
        capture_output=True, text=True, timeout=15, check=True,
    )
    buckets = json.loads(out.stdout)
    assert set(buckets) == {"conductor", "logic", "oracle"}
    # The committed catalog has ≥1 model per role; conductor hosts the
    # bitnet.cpp ternary tier (M073), oracle hosts the Blackwell NVFP4 tier.
    assert buckets["conductor"], "conductor (pulse tier) must have ≥1 catalog model"
    assert buckets["oracle"], "oracle tier must have ≥1 catalog model"
    precisions = {m["precision"] for ms in buckets.values() for m in ms}
    assert "ternary" in precisions, "M073 ternary precision must appear"
    assert "nvfp4" in precisions, "M077 NVFP4 precision must appear"
    # Every emitted model id must exist verbatim in the catalog source.
    catalog_text = CATALOG.read_text(encoding="utf-8")
    for ms in buckets.values():
        for m in ms:
            assert f"id: {m['id']}" in catalog_text, f"invented model id: {m['id']}"


def test_api_daemon_present():
    assert API_DAEMON.is_file(), f"api daemon missing: {API_DAEMON}"


def test_systemd_unit_present():
    assert SYSTEMD_UNIT.is_file(), f"service unit missing: {SYSTEMD_UNIT}"


def test_systemd_unit_loopback_default():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    active = [ln for ln in body.splitlines()
              if ln.strip() and not ln.lstrip().startswith("#")]
    found = False
    for ln in active:
        if "MODEL_HEALTH_API_BIND=" in ln:
            assert "MODEL_HEALTH_API_BIND=127.0.0.1" in ln, ln
            found = True
        assert "MODEL_HEALTH_API_BIND=0.0.0.0" not in ln, ln
    assert found, "service unit must set MODEL_HEALTH_API_BIND=127.0.0.1"


def test_systemd_unit_defense_in_depth():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    for key in ("ProtectSystem=strict", "NoNewPrivileges=true", "PrivateTmp=true",
                "ProtectHome=true", "RestrictAddressFamilies=", "SystemCallFilter="):
        assert key in body, f"R171 hardening key missing: {key}"


def test_osctl_dispatches_model_health():
    body = OSCTL.read_text(encoding="utf-8")
    assert "model-health)" in body, "osctl missing model-health dispatch case"
    assert "scripts/inference/model-health.py" in body


def test_master_dashboard_route_registered():
    # F-2026-072: the aggregator route table moved to the generated
    # config/dashboard-routes.yaml and uses the canonical catalog slug.
    routes = (REPO_ROOT / "config" / "dashboard-routes.yaml").read_text(encoding="utf-8")
    assert "d-03-model-health" in routes, "aggregator table missing d-03-model-health route"
    assert "8104" in routes, "d-03-model-health route must declare port 8104"


# ---- live endpoints (the exact d-03 fetch contract) -----------------------

def test_health_endpoint_matches_dashboard_contract():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/models/health", timeout=3) as r:
            assert r.status == 200
            d = json.loads(r.read())
        # The d-03 webapp refresh() reads exactly these shapes.
        assert set(d) >= {"summary", "roles", "models", "kvcache", "heatmap"}
        for k in ("total", "blackwell", "rtx4090", "cpu"):
            assert k in d["summary"]
        for role in ("conductor", "logic", "oracle"):
            assert role in d["roles"]
            assert "models" in d["roles"][role] and isinstance(d["roles"][role]["models"], list)
        assert "util_pct" in d["roles"]["conductor"]  # gauge field
        assert "vram_total_gb" in d["roles"]["oracle"]  # gauge ceiling field
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_catalog_endpoint():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/models/catalog", timeout=3) as r:
            assert r.status == 200
            d = json.loads(r.read())
        assert set(d) == {"conductor", "logic", "oracle"}
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_gpus_endpoint():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/models/gpus", timeout=3) as r:
            assert r.status == 200
            d = json.loads(r.read())
        assert "gpus" in d and isinstance(d["gpus"], list)  # empty when no GPU
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_webapp_served():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/webapp/", timeout=3) as r:
            assert r.status == 200
            html = r.read().decode("utf-8")
        assert "D-03" in html and "model health" in html
        assert "/api/models/health" in html  # the dashboard fetches our endpoint
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_readonly_post_rejected():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/models/health", method="POST", data=b"{}")
        try:
            urllib.request.urlopen(req, timeout=3)
            raised = False
        except urllib.error.HTTPError as e:
            raised = (e.code == 405)
        assert raised, "mutation must be rejected 405 (read-only surface)"
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_version_endpoint():
    port = _free_port()
    proc = _spawn_api(port)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/version", timeout=3) as r:
            d = json.loads(r.read())
        assert d["module"] == "d-03-model-health"
        assert "api" in d["surfaces"] and "webapp" in d["surfaces"]
        assert d["standing_rule"] == "We do not minimize anything."
    finally:
        proc.kill(); proc.wait(timeout=3)
