"""M060 D-04 (R10075-R10082) — costs API + webapp surface contract.

Drives the D-04 cockpit dashboard from a shell to PRODUCTION: the dashboard
HTML existed but fetched `/api/costs/summary` (+ `/stream`) with no backend.
This locks the full §1g 8-surface stack now wired:

  core    scripts/observability/cost-tracker.py  (policy + per-span cost sum)
  cli     sovereign-osctl costs {summary,policy,today}
  api     scripts/operator/costs-api.py  (read-only HTTP)
  webapp  webapp/d-04-costs/index.html   (served by the api)
  service systemd/system/sovereign-costs-api.service

The core joins the operator cost-policy.toml (dump 9885-9930 keys) to the
per-span `cost` attribute of the M049 span log, summing by day/project/MS040
profile/model. Per operator §1g (verbatim, sacrosanct): "We do not minimize
anything." Read-only — cost-policy edits + cloud-halt are MS003-signed CLI verbs.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE = REPO_ROOT / "scripts" / "observability" / "cost-tracker.py"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "costs-api.py"
SYSTEMD_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-costs-api.service"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
WEBAPP = REPO_ROOT / "webapp" / "d-04-costs" / "index.html"

_NOW_MS = int(time.time() * 1000)
_FIXTURE_SPANS = [
    {"trace_id": "t1", "span_id": "s1", "operation": "model_call", "start_ts": _NOW_MS,
     "duration_ms": 900, "severity": "info", "profile": "careful",
     "attributes": {"model": "DeepSeek-V3-Quant", "role": "oracle", "cost": 0.12,
                    "tokens_in": 3000, "tokens_out": 1200, "project": "sovereign-os"}},
    {"trace_id": "t2", "span_id": "s2", "operation": "model_call", "start_ts": _NOW_MS,
     "duration_ms": 40, "severity": "info", "profile": "fast",
     "attributes": {"model": "Qwen3-Coder-32B-Instruct", "role": "logic", "cost": 0.03,
                    "tokens_in": 800, "tokens_out": 400, "project": "selfdef"}},
    {"trace_id": "t3", "span_id": "s3", "operation": "model_call", "start_ts": _NOW_MS,
     "duration_ms": 10, "severity": "info", "profile": "private",
     "attributes": {"model": "BitNet-b1.58-2B-4T", "role": "conductor", "cost": 0.0,
                    "tokens_in": 500, "tokens_out": 200, "project": "sovereign-os"}},
]
_POLICY_TOML = (
    'cloud_enabled = true\n'
    'cloud_requires_approval = true\n'
    'daily_budget_usd = 5.00\n'
    'per_request_max_usd = 0.50\n'
    'private_paths_never_cloud = true\n'
    'log_prompts = "local_only"\n'
)


def _write_fixtures() -> tuple[str, str]:
    fd, store = tempfile.mkstemp(prefix="cost-spans-", suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        for s in _FIXTURE_SPANS:
            fh.write(json.dumps(s) + "\n")
    fd2, pol = tempfile.mkstemp(prefix="cost-policy-", suffix=".toml")
    with os.fdopen(fd2, "w", encoding="utf-8") as fh:
        fh.write(_POLICY_TOML)
    return store, pol


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int, store: str, policy: str):
    env = {
        "COSTS_API_BIND": "127.0.0.1",
        "COSTS_API_PORT": str(port),
        "SOVEREIGN_OS_SPAN_STORE": store,
        "SOVEREIGN_OS_COST_POLICY": policy,
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
    raise RuntimeError("costs-api failed to start within 6s")


def _get(port: int, path: str):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as r:
        return r.status, json.loads(r.read())


# ---- structural -----------------------------------------------------------

def test_core_present_and_aggregates():
    assert CORE.is_file(), f"core missing: {CORE}"
    store, pol = _write_fixtures()
    try:
        out = subprocess.run(
            ["python3", str(CORE), "summary", "--json"],
            capture_output=True, text=True, timeout=15, check=True,
            env={**os.environ, "SOVEREIGN_OS_SPAN_STORE": store,
                 "SOVEREIGN_OS_COST_POLICY": pol},
        )
        d = json.loads(out.stdout)
        assert set(d) >= {"today", "projects", "profiles", "models", "trend30d", "policy"}
        assert abs(d["today"]["spend"] - 0.15) < 1e-9
        assert d["today"]["requests"] == 3
        assert d["today"]["budget"] == 5.0
        # project + profile grouping
        names = {p["name"]: p["today"] for p in d["projects"]}
        assert abs(names["sovereign-os"] - 0.12) < 1e-9 and abs(names["selfdef"] - 0.03) < 1e-9
        assert set(d["profiles"]) == {"private", "fast", "careful", "autonomous",
                                      "experimental", "production"}
        assert len(d["trend30d"]) == 30
    finally:
        os.unlink(store); os.unlink(pol)


def test_core_sovereign_safe_defaults_when_absent():
    """No policy file → cloud disabled, private paths never cloud (dump 9885)."""
    out = subprocess.run(
        ["python3", str(CORE), "policy", "--json"],
        capture_output=True, text=True, timeout=15, check=True,
        env={**os.environ, "SOVEREIGN_OS_COST_POLICY": "/tmp/sovereign-os-no-such-policy.toml"},
    )
    pol = json.loads(out.stdout)
    assert pol["cloud_enabled"] is False
    assert pol["private_paths_never_cloud"] is True
    assert pol["daily_budget_usd"] is None


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
        if "COSTS_API_BIND=" in ln:
            assert "COSTS_API_BIND=127.0.0.1" in ln, ln
            found = True
        assert "COSTS_API_BIND=0.0.0.0" not in ln, ln
    assert found, "service unit must set COSTS_API_BIND=127.0.0.1"


def test_systemd_unit_defense_in_depth():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    for key in ("ProtectSystem=strict", "NoNewPrivileges=true", "PrivateTmp=true",
                "ProtectHome=true", "RestrictAddressFamilies=", "SystemCallFilter="):
        assert key in body, f"R171 hardening key missing: {key}"


def test_osctl_dispatches_costs():
    body = OSCTL.read_text(encoding="utf-8")
    assert "costs)" in body, "osctl missing costs dispatch case"
    assert "scripts/observability/cost-tracker.py" in body


def test_master_dashboard_route_registered():
    body = (REPO_ROOT / "scripts" / "operator" / "master-dashboard.py").read_text(encoding="utf-8")
    assert '"costs"' in body, "master-dashboard missing costs route"
    assert "8106" in body, "costs route must declare port 8106"


# ---- live endpoints (the exact d-04 fetch contract) -----------------------

def test_summary_endpoint_matches_dashboard_contract():
    store, pol = _write_fixtures()
    port = _free_port()
    proc = _spawn_api(port, store, pol)
    try:
        status, d = _get(port, "/api/costs/summary")
        assert status == 200
        assert set(d) >= {"today", "projects", "profiles", "models", "trend30d", "policy"}
        for k in ("spend", "budget", "requests", "avg_req_cost", "per_request_max", "eod_forecast"):
            assert k in d["today"]
        for k in ("cloud_enabled", "cloud_requires_approval", "daily_budget_usd",
                  "per_request_max_usd", "private_paths_never_cloud", "log_prompts"):
            assert k in d["policy"]
        # model rows carry the columns the table renders
        m = d["models"][0]
        for k in ("name", "role", "today", "tokens_in", "tokens_out", "usd_per_mtok"):
            assert k in m
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(store); os.unlink(pol)


def test_policy_endpoint():
    store, pol = _write_fixtures()
    port = _free_port()
    proc = _spawn_api(port, store, pol)
    try:
        _, d = _get(port, "/api/costs/policy")
        assert d["cloud_enabled"] is True and d["daily_budget_usd"] == 5.0
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(store); os.unlink(pol)


def test_empty_store_graceful():
    _, pol = _write_fixtures()
    port = _free_port()
    proc = _spawn_api(port, "/tmp/sovereign-os-nonexistent-cost-spans.jsonl", pol)
    try:
        _, d = _get(port, "/api/costs/summary")
        assert d["today"]["spend"] == 0.0 and d["today"]["requests"] == 0
        assert d["projects"] == [] and d["models"] == []
        assert len(d["trend30d"]) == 30
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(pol)


def test_webapp_served():
    store, pol = _write_fixtures()
    port = _free_port()
    proc = _spawn_api(port, store, pol)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/webapp/", timeout=3) as r:
            assert r.status == 200
            html = r.read().decode("utf-8")
        assert "D-04" in html and "costs" in html
        assert "/api/costs/summary" in html  # the dashboard fetches our endpoint
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(store); os.unlink(pol)


def test_readonly_post_rejected():
    store, pol = _write_fixtures()
    port = _free_port()
    proc = _spawn_api(port, store, pol)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/costs/summary", method="POST", data=b"{}")
        try:
            urllib.request.urlopen(req, timeout=3)
            raised = False
        except urllib.error.HTTPError as e:
            raised = (e.code == 405)
        assert raised, "mutation must be rejected 405 (read-only surface)"
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(store); os.unlink(pol)


def test_version_endpoint():
    store, pol = _write_fixtures()
    port = _free_port()
    proc = _spawn_api(port, store, pol)
    try:
        _, d = _get(port, "/version")
        assert d["module"] == "d-04-costs"
        assert "api" in d["surfaces"] and "webapp" in d["surfaces"]
        assert d["standing_rule"] == "We do not minimize anything."
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(store); os.unlink(pol)
