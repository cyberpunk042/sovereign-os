"""M060 D-10 (R10106-R10108) — eval-history API + webapp surface contract.

Drives the D-10 cockpit dashboard from a shell to PRODUCTION: the dashboard
HTML existed but fetched `/api/evals/summary` (+ `/stream`) with no backend.
This locks the full §1g 8-surface stack now wired:

  core    scripts/observability/eval-tracker.py  (eval-run aggregation)
  cli     sovereign-osctl evals {summary,suites,candidates}
  api     scripts/operator/evals-api.py  (read-only HTTP)
  webapp  webapp/d-10-eval-history/index.html   (served by the api)
  service systemd/system/sovereign-evals-api.service

The core aggregates the Eval-Value eval-run log + cross-references the D-11
adapter registry for promotion candidates. CRITICAL M079 invariant
(R13131-R13136): white-box (WB) and black-box (BB) pass rates are NEVER
averaged together. Per operator §1g (verbatim): "We do not minimize anything."
Read-only — eval runs + adapter promotion are MS003-signed CLI verbs.
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
CORE = REPO_ROOT / "scripts" / "observability" / "eval-tracker.py"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "evals-api.py"
SYSTEMD_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-evals-api.service"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
WEBAPP = REPO_ROOT / "webapp" / "d-10-eval-history" / "index.html"

_NOW_MS = int(time.time() * 1000)
# 3 BB runs (2 pass), 1 WB run (0 pass) — exercises the disaggregation invariant.
_FIXTURE_RUNS = [
    {"ts": _NOW_MS, "task": "gsm8k-42", "suite": "math_avg", "intervention_class": "bb",
     "model": "DeepSeek-V3-Quant", "role": "oracle", "score": 0.55, "passed": True,
     "baseline_score": 0.50},
    {"ts": _NOW_MS, "task": "gsm8k-42", "suite": "math_avg", "intervention_class": "bb",
     "model": "DeepSeek-V3-Quant", "role": "oracle", "score": 0.40, "passed": False,
     "baseline_score": 0.50},
    {"ts": _NOW_MS, "task": "alfworld-7", "suite": "alfworld", "intervention_class": "bb",
     "model": "Qwen3-Coder-32B-Instruct", "role": "logic", "score": 0.938, "passed": True},
    {"ts": _NOW_MS, "task": "jailbreak-probe", "suite": "activation_steer",
     "intervention_class": "wb", "model": "DeepSeek-V3-Quant", "role": "oracle",
     "score": 0.20, "passed": False},
]
_REGISTRY = {"adapters": {"deepseek-coder-loras-rust-systems": {
    "status": "pending", "training": "rl-holderpo", "eval_gain_pct": 7.3,
    "gates": {"snapshot": "passed", "test_eval": "passed", "oracle": "pending", "human": "pending"}}}}


def _write_fixtures() -> tuple[str, str]:
    fd, store = tempfile.mkstemp(prefix="evals-", suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        for r in _FIXTURE_RUNS:
            fh.write(json.dumps(r) + "\n")
    fd2, reg = tempfile.mkstemp(prefix="eval-adapter-reg-", suffix=".json")
    with os.fdopen(fd2, "w", encoding="utf-8") as fh:
        json.dump(_REGISTRY, fh)
    return store, reg


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int, store: str, registry: str):
    env = {
        "EVALS_API_BIND": "127.0.0.1",
        "EVALS_API_PORT": str(port),
        "SOVEREIGN_OS_EVAL_STORE": store,
        "SOVEREIGN_OS_ADAPTER_REGISTRY": registry,
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
    raise RuntimeError("evals-api failed to start within 6s")


def _get(port: int, path: str):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as r:
        return r.status, json.loads(r.read())


# ---- structural -----------------------------------------------------------

def test_core_present_and_aggregates():
    assert CORE.is_file(), f"core missing: {CORE}"
    store, reg = _write_fixtures()
    try:
        out = subprocess.run(
            ["python3", str(CORE), "summary", "--json"],
            capture_output=True, text=True, timeout=15, check=True,
            env={**os.environ, "SOVEREIGN_OS_EVAL_STORE": store,
                 "SOVEREIGN_OS_ADAPTER_REGISTRY": reg},
        )
        d = json.loads(out.stdout)
        assert set(d) >= {"summary", "suites", "tasks", "models", "candidates"}
        assert d["summary"]["total_runs"] == 4
        assert set(d["suites"]) == {"math_avg", "alfworld", "arc_agi_1",
                                    "arc_agi_2", "sudoku", "activation_steer"}
    finally:
        os.unlink(store); os.unlink(reg)


def test_wb_bb_disaggregation_invariant():
    """M079 R13131-R13136: WB and BB pass rates are computed over their OWN
    runs only — NEVER averaged together. 3 BB runs (2 pass)=66.67; 1 WB (0)=0."""
    store, reg = _write_fixtures()
    try:
        out = subprocess.run(
            ["python3", str(CORE), "summary", "--json"],
            capture_output=True, text=True, timeout=15, check=True,
            env={**os.environ, "SOVEREIGN_OS_EVAL_STORE": store,
                 "SOVEREIGN_OS_ADAPTER_REGISTRY": reg},
        )
        d = json.loads(out.stdout)["summary"]
        assert abs(d["bb_pass_pct"] - 66.67) < 0.1, d
        assert d["wb_pass_pct"] == 0.0, d
        # the combined (mixed) rate would be 50.0 (2 of 4) — must NOT appear
        assert d["bb_pass_pct"] != 50.0 and d["wb_pass_pct"] != 50.0
    finally:
        os.unlink(store); os.unlink(reg)


def test_candidates_from_adapter_core():
    store, reg = _write_fixtures()
    try:
        out = subprocess.run(
            ["python3", str(CORE), "candidates", "--json"],
            capture_output=True, text=True, timeout=15, check=True,
            env={**os.environ, "SOVEREIGN_OS_EVAL_STORE": store,
                 "SOVEREIGN_OS_ADAPTER_REGISTRY": reg},
        )
        cands = json.loads(out.stdout)
        ds = [c for c in cands if c["adapter_id"] == "deepseek-coder-loras-rust-systems"]
        assert ds, "pending adapter must surface as a promotion candidate"
        assert ds[0]["gate_status"] == "pending-oracle"  # snapshot+test passed, oracle pending
        assert ds[0]["eval_gain_pct"] == 7.3
    finally:
        os.unlink(store); os.unlink(reg)


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
        if "EVALS_API_BIND=" in ln:
            assert "EVALS_API_BIND=127.0.0.1" in ln, ln
            found = True
        assert "EVALS_API_BIND=0.0.0.0" not in ln, ln
    assert found, "service unit must set EVALS_API_BIND=127.0.0.1"


def test_systemd_unit_defense_in_depth():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    for key in ("ProtectSystem=strict", "NoNewPrivileges=true", "PrivateTmp=true",
                "ProtectHome=true", "RestrictAddressFamilies=", "SystemCallFilter="):
        assert key in body, f"R171 hardening key missing: {key}"


def test_osctl_dispatches_evals():
    body = OSCTL.read_text(encoding="utf-8")
    assert "evals)" in body, "osctl missing evals dispatch case"
    assert "scripts/observability/eval-tracker.py" in body


def test_master_dashboard_route_registered():
    body = (REPO_ROOT / "scripts" / "operator" / "master-dashboard.py").read_text(encoding="utf-8")
    assert '"evals"' in body, "master-dashboard missing evals route"
    assert "8108" in body, "evals route must declare port 8108"


# ---- live endpoints (the exact d-10 fetch contract) -----------------------

def test_summary_endpoint_matches_dashboard_contract():
    store, reg = _write_fixtures()
    port = _free_port()
    proc = _spawn_api(port, store, reg)
    try:
        status, d = _get(port, "/api/evals/summary")
        assert status == 200
        assert set(d) >= {"summary", "suites", "tasks", "models", "candidates"}
        for k in ("total_runs", "bb_pass_pct", "wb_pass_pct", "candidate_count"):
            assert k in d["summary"]
        # suites carry current_pct + trend the writeSuite() helper reads
        for key in ("math_avg", "alfworld", "arc_agi_1", "arc_agi_2", "sudoku", "activation_steer"):
            assert key in d["suites"] and "trend" in d["suites"][key]
        t = d["tasks"][0]
        for k in ("name", "intervention_class", "run_count", "pass_pct", "trend"):
            assert k in t
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(store); os.unlink(reg)


def test_empty_store_graceful():
    _, reg = _write_fixtures()
    port = _free_port()
    proc = _spawn_api(port, "/tmp/sovereign-os-nonexistent-eval-store.jsonl", reg)
    try:
        _, d = _get(port, "/api/evals/summary")
        assert d["summary"]["total_runs"] == 0
        assert d["summary"]["bb_pass_pct"] is None and d["summary"]["wb_pass_pct"] is None
        assert d["tasks"] == [] and d["models"] == []
        assert set(d["suites"]) == {"math_avg", "alfworld", "arc_agi_1",
                                    "arc_agi_2", "sudoku", "activation_steer"}
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(reg)


def test_webapp_served():
    store, reg = _write_fixtures()
    port = _free_port()
    proc = _spawn_api(port, store, reg)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/webapp/", timeout=3) as r:
            assert r.status == 200
            html = r.read().decode("utf-8")
        assert "D-10" in html and "eval history" in html
        assert "/api/evals/summary" in html  # the dashboard fetches our endpoint
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(store); os.unlink(reg)


def test_readonly_post_rejected():
    store, reg = _write_fixtures()
    port = _free_port()
    proc = _spawn_api(port, store, reg)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/evals/summary", method="POST", data=b"{}")
        try:
            urllib.request.urlopen(req, timeout=3)
            raised = False
        except urllib.error.HTTPError as e:
            raised = (e.code == 405)
        assert raised, "mutation must be rejected 405 (read-only surface)"
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(store); os.unlink(reg)


def test_version_endpoint():
    store, reg = _write_fixtures()
    port = _free_port()
    proc = _spawn_api(port, store, reg)
    try:
        _, d = _get(port, "/version")
        assert d["module"] == "d-10-eval-history"
        assert "api" in d["surfaces"] and "webapp" in d["surfaces"]
        assert d["standing_rule"] == "We do not minimize anything."
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(store); os.unlink(reg)
