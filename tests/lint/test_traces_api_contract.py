"""M060 D-05 (R10083-R10087) — traces API + webapp surface contract.

Drives the D-05 cockpit dashboard from a shell to PRODUCTION: the dashboard
HTML existed but fetched `/api/traces/spans` (+ `/<trace_id>` + `/stream`) with
no backend. This locks the full §1g 8-surface stack now wired:

  core    scripts/observability/trace-store.py  (M049 13-field span store+query)
  cli     sovereign-osctl traces {spans,trace,summary}
  api     scripts/operator/traces-api.py  (read-only HTTP)
  webapp  webapp/d-05-traces/index.html   (served by the api)
  service systemd/system/sovereign-traces-api.service

The core reads the observability fabric's append-only JSONL span log and
filters by time window / text / severity / OCSF class (MS026 16-event
taxonomy). Per operator §1g (verbatim, sacrosanct): "We do not minimize
anything." Read-only — spans are observed, MS009 replay-verify is a CLI verb.
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
CORE = REPO_ROOT / "scripts" / "observability" / "trace-store.py"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "traces-api.py"
SYSTEMD_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-traces-api.service"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
WEBAPP = REPO_ROOT / "webapp" / "d-05-traces" / "index.html"

# Two-span trace + one out-of-window span — exercises window, severity, OCSF,
# attribute search and per-trace assembly without depending on a live fabric.
_NOW_MS = int(time.time() * 1000)
_OLD_MS = int((time.time() - 100_000) * 1000)
_FIXTURE_SPANS = [
    {"trace_id": "t-aaaa1111", "span_id": "s-root01", "parent_span_id": None,
     "operation": "model_call", "start_ts": _NOW_MS, "duration_ms": 1820.5,
     "severity": "info", "actor": "oracle", "profile": "careful",
     "ocsf_class": 1001, "attributes": {"model": "DeepSeek-V3-Quant", "tokens": 4096}},
    {"trace_id": "t-aaaa1111", "span_id": "s-child1", "parent_span_id": "s-root01",
     "operation": "tool_call", "start_ts": _NOW_MS, "duration_ms": 42.0,
     "severity": "error", "actor": "tool:fs", "profile": "careful",
     "ocsf_class": 2004, "attributes": {"tool_refs": ["fs.read"]},
     "ocsf_payload": {"class_uid": 2004, "finding": "declaration mismatch"}},
    {"trace_id": "t-bbbb2222", "span_id": "s-old001", "parent_span_id": None,
     "operation": "route_decision", "start_ts": _OLD_MS, "duration_ms": 3.1,
     "severity": "info", "actor": "router", "profile": "fast", "ocsf_class": 5001,
     "attributes": {"branch_id": "main"}},
]


def _write_store() -> str:
    fd, path = tempfile.mkstemp(prefix="spans-", suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        for s in _FIXTURE_SPANS:
            fh.write(json.dumps(s) + "\n")
    return path


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int, store: str):
    env = {
        "TRACES_API_BIND": "127.0.0.1",
        "TRACES_API_PORT": str(port),
        "SOVEREIGN_OS_SPAN_STORE": store,
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
    raise RuntimeError("traces-api failed to start within 6s")


def _get(port: int, path: str):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as r:
        return r.status, json.loads(r.read())


# ---- structural -----------------------------------------------------------

def test_core_present_and_runs():
    assert CORE.is_file(), f"core missing: {CORE}"
    store = _write_store()
    try:
        out = subprocess.run(
            ["python3", str(CORE), "spans", "--window", "3600", "--json"],
            capture_output=True, text=True, timeout=15, check=True,
            env={**os.environ, "SOVEREIGN_OS_SPAN_STORE": store},
        )
        d = json.loads(out.stdout)
        assert set(d) >= {"spans", "summary"}
        assert set(d["summary"]) >= {"total", "errors", "p95_ms", "ocsf"}
        # the old span is outside the 1h window
        assert d["summary"]["total"] == 2
        assert d["summary"]["errors"] == 1
    finally:
        os.unlink(store)


def test_core_13_field_schema():
    """The core must normalise to the M049 13-field span schema verbatim."""
    expected = {"trace_id", "span_id", "parent_span_id", "operation", "start_ts",
                "duration_ms", "severity", "attributes", "ocsf_class", "actor",
                "profile", "signature", "schema_version"}
    out = subprocess.run(
        ["python3", "-c",
         f"import importlib.util,sys;"
         f"s=importlib.util.spec_from_file_location('c',{str(CORE)!r});"
         f"m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
         f"print(','.join(m.SPAN_FIELDS))"],
        capture_output=True, text=True, timeout=15, check=True,
    )
    fields = set(out.stdout.strip().split(","))
    assert fields == expected, f"13-field schema drift: {fields ^ expected}"


def test_core_per_trace_assembly():
    store = _write_store()
    try:
        out = subprocess.run(
            ["python3", str(CORE), "trace", "t-aaaa1111", "--json"],
            capture_output=True, text=True, timeout=15, check=True,
            env={**os.environ, "SOVEREIGN_OS_SPAN_STORE": store},
        )
        d = json.loads(out.stdout)
        assert [s["span_id"] for s in d["spans"]] == ["s-root01", "s-child1"]
    finally:
        os.unlink(store)


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
        if "TRACES_API_BIND=" in ln:
            assert "TRACES_API_BIND=127.0.0.1" in ln, ln
            found = True
        assert "TRACES_API_BIND=0.0.0.0" not in ln, ln
    assert found, "service unit must set TRACES_API_BIND=127.0.0.1"


def test_systemd_unit_defense_in_depth():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    for key in ("ProtectSystem=strict", "NoNewPrivileges=true", "PrivateTmp=true",
                "ProtectHome=true", "RestrictAddressFamilies=", "SystemCallFilter="):
        assert key in body, f"R171 hardening key missing: {key}"


def test_osctl_dispatches_traces():
    body = OSCTL.read_text(encoding="utf-8")
    assert "traces)" in body, "osctl missing traces dispatch case"
    assert "scripts/observability/trace-store.py" in body


def test_master_dashboard_route_registered():
    # F-2026-072: the aggregator route table moved to the generated
    # config/dashboard-routes.yaml and uses the canonical catalog slug.
    routes = (REPO_ROOT / "config" / "dashboard-routes.yaml").read_text(encoding="utf-8")
    assert "d-05-traces" in routes, "aggregator table missing d-05-traces route"
    assert "8105" in routes, "d-05-traces route must declare port 8105"


# ---- live endpoints (the exact d-05 fetch contract) -----------------------

def test_spans_endpoint_matches_dashboard_contract():
    store = _write_store()
    port = _free_port()
    proc = _spawn_api(port, store)
    try:
        status, d = _get(port, "/api/traces/spans?window=3600")
        assert status == 200
        assert set(d) >= {"spans", "summary"}
        assert set(d["summary"]) >= {"total", "errors", "p95_ms", "ocsf"}
        assert d["summary"]["total"] == 2  # old span windowed out
        for c in ("1001", "1003", "2004", "4001", "5001"):
            assert c in d["summary"]["ocsf"]
        # spans carry the structural fields the table renders
        s = d["spans"][0]
        for k in ("trace_id", "span_id", "operation", "start_ts", "duration_ms", "severity"):
            assert k in s
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(store)


def test_spans_severity_and_ocsf_filters():
    store = _write_store()
    port = _free_port()
    proc = _spawn_api(port, store)
    try:
        _, d = _get(port, "/api/traces/spans?severity=error")
        assert [s["span_id"] for s in d["spans"]] == ["s-child1"]
        _, d2 = _get(port, "/api/traces/spans?ocsf_class=2004")
        assert [s["span_id"] for s in d2["spans"]] == ["s-child1"]
        _, d3 = _get(port, "/api/traces/spans?q=DeepSeek")
        assert [s["span_id"] for s in d3["spans"]] == ["s-root01"]
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(store)


def test_trace_detail_endpoint():
    store = _write_store()
    port = _free_port()
    proc = _spawn_api(port, store)
    try:
        _, d = _get(port, "/api/traces/t-aaaa1111")
        assert d["trace_id"] == "t-aaaa1111"
        assert [s["span_id"] for s in d["spans"]] == ["s-root01", "s-child1"]
        # the error child carries its OCSF payload for the detail panel
        child = d["spans"][1]
        assert child["ocsf_payload"]["class_uid"] == 2004
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(store)


def test_empty_store_graceful():
    port = _free_port()
    proc = _spawn_api(port, "/tmp/sovereign-os-nonexistent-span-store.jsonl")
    try:
        _, d = _get(port, "/api/traces/spans")
        assert d["spans"] == [] and d["summary"]["total"] == 0
    finally:
        proc.kill(); proc.wait(timeout=3)


def test_webapp_served():
    store = _write_store()
    port = _free_port()
    proc = _spawn_api(port, store)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/webapp/", timeout=3) as r:
            assert r.status == 200
            html = r.read().decode("utf-8")
        assert "D-05" in html and "traces" in html
        assert "/api/traces/spans" in html  # the dashboard fetches our endpoint
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(store)


def test_readonly_post_rejected():
    store = _write_store()
    port = _free_port()
    proc = _spawn_api(port, store)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/traces/spans", method="POST", data=b"{}")
        try:
            urllib.request.urlopen(req, timeout=3)
            raised = False
        except urllib.error.HTTPError as e:
            raised = (e.code == 405)
        assert raised, "mutation must be rejected 405 (read-only surface)"
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(store)


def test_version_endpoint():
    store = _write_store()
    port = _free_port()
    proc = _spawn_api(port, store)
    try:
        _, d = _get(port, "/version")
        assert d["module"] == "d-05-traces"
        assert "api" in d["surfaces"] and "webapp" in d["surfaces"]
        assert d["standing_rule"] == "We do not minimize anything."
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(store)
