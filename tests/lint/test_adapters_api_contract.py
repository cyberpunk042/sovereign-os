"""M060 D-11 (R10109-R10111) — adapter-status API + webapp surface contract.

Drives the D-11 cockpit dashboard from a shell to PRODUCTION: the dashboard
HTML existed but fetched `/api/adapters/inventory` (+ `/stream`) with no
backend. This locks the full §1g 8-surface stack now wired:

  core    scripts/inference/adapter-foundry.py  (catalog adapters + registry overlay)
  cli     sovereign-osctl adapters {inventory,list,history}
  api     scripts/operator/adapters-api.py  (read-only HTTP)
  webapp  webapp/d-11-adapter-status/index.html   (served by the api)
  service systemd/system/sovereign-adapters-api.service

The core joins the model catalog's class=lora-adapter entries (M046) to the
LoRA-Foundry promotion registry (status + MS041 triple-gate + eval gain +
NVFP4). Per operator §1g (verbatim, sacrosanct): "We do not minimize
anything." Read-only — promote/demote/rollback are MS003-signed CLI verbs.
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
CORE = REPO_ROOT / "scripts" / "inference" / "adapter-foundry.py"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "adapters-api.py"
SYSTEMD_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-adapters-api.service"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
WEBAPP = REPO_ROOT / "webapp" / "d-11-adapter-status" / "index.html"

_REGISTRY = {
    "adapters": {
        "deepseek-coder-loras-rust-systems": {
            "status": "active", "training": "rl-holderpo", "eval_gain_pct": 7.3,
            "gates": {"snapshot": "passed", "test_eval": "passed",
                      "oracle": "passed", "human": "pending"}},
        "nvfp4-math-adapter": {
            "base_model": "DeepSeek-V3-Quant", "precision": "nvfp4", "status": "pending",
            "size_bytes": 1_200_000_000, "vram_bf16_bytes": 4_800_000_000,
            "gates": {"snapshot": "passed", "test_eval": "pending"}},
    },
    "history": [{"ts": "2026-05-27T10:00:00Z", "action": "promote",
                 "adapter_id": "deepseek-coder-loras-rust-systems",
                 "actor": "operator", "rationale": "+7.3% rust eval",
                 "signature": "deadbeef1234"}],
    "hrm": {"text_1b": {"installed": True}},
}


def _write_registry() -> str:
    fd, path = tempfile.mkstemp(prefix="adapter-reg-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(_REGISTRY, fh)
    return path


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int, registry: str):
    env = {
        "ADAPTERS_API_BIND": "127.0.0.1",
        "ADAPTERS_API_PORT": str(port),
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
    raise RuntimeError("adapters-api failed to start within 6s")


def _get(port: int, path: str):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as r:
        return r.status, json.loads(r.read())


# ---- structural -----------------------------------------------------------

def test_core_present_and_reads_catalog():
    """No registry → catalog lora-adapter entries surface as pending (the
    committed catalog has ≥1 class=lora-adapter row with a base_model)."""
    assert CORE.is_file(), f"core missing: {CORE}"
    out = subprocess.run(
        ["python3", str(CORE), "inventory", "--json"],
        capture_output=True, text=True, timeout=15, check=True,
        env={**os.environ, "SOVEREIGN_OS_ADAPTER_REGISTRY": "/tmp/sovereign-os-no-adapter-reg.json"},
    )
    d = json.loads(out.stdout)
    assert set(d) >= {"summary", "adapters", "history", "hrm"}
    assert d["summary"]["total"] >= 1, "catalog must contribute ≥1 lora-adapter"
    for a in d["adapters"]:
        assert a["base_model"], "every adapter must carry its base_model (schema 1.1.0)"
        assert a["status"] in {"active", "pending", "quarantined", "rolled-back"}
    assert set(d["hrm"]) == {"canonical_27m", "text_1b", "trm_7m"}


def test_core_registry_overlay():
    reg = _write_registry()
    try:
        out = subprocess.run(
            ["python3", str(CORE), "inventory", "--json"],
            capture_output=True, text=True, timeout=15, check=True,
            env={**os.environ, "SOVEREIGN_OS_ADAPTER_REGISTRY": reg},
        )
        d = json.loads(out.stdout)
        by_id = {a["id"]: a for a in d["adapters"]}
        # registry promotes the catalog adapter to active + merges gates
        ds = by_id["deepseek-coder-loras-rust-systems"]
        assert ds["status"] == "active"
        assert ds["gates"]["oracle_or_human"] == "passed"  # oracle passed
        # registry-only NVFP4 adapter gets the M077 detail fields
        nv = by_id["nvfp4-math-adapter"]
        assert nv["precision"] == "nvfp4"
        assert nv["vram_4bit_bytes"] == 1_200_000_000
        assert nv["vram_bf16_bytes"] == 4_800_000_000
        # promoted: deepseek (registry active). pending: nvfp4 (registry-only)
        # + the 2 catalog-only Bonsai adapters SDD-715 added (sovereign-os-admin-lora
        # + coding-style-lora), which this fixture registry does not promote.
        assert d["summary"]["promoted"] == 1 and d["summary"]["pending"] == 3
        assert d["hrm"]["text_1b"]["installed"] is True
        assert d["history"][0]["action"] == "promote"
    finally:
        os.unlink(reg)


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
        if "ADAPTERS_API_BIND=" in ln:
            assert "ADAPTERS_API_BIND=127.0.0.1" in ln, ln
            found = True
        assert "ADAPTERS_API_BIND=0.0.0.0" not in ln, ln
    assert found, "service unit must set ADAPTERS_API_BIND=127.0.0.1"


def test_systemd_unit_defense_in_depth():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    for key in ("ProtectSystem=strict", "NoNewPrivileges=true", "PrivateTmp=true",
                "ProtectHome=true", "RestrictAddressFamilies=", "SystemCallFilter="):
        assert key in body, f"R171 hardening key missing: {key}"


def test_osctl_dispatches_adapters():
    body = OSCTL.read_text(encoding="utf-8")
    assert "adapters)" in body, "osctl missing adapters dispatch case"
    assert "scripts/inference/adapter-foundry.py" in body


def test_master_dashboard_route_registered():
    # F-2026-072: the aggregator route table moved to the generated
    # config/dashboard-routes.yaml and uses the canonical catalog slug.
    routes = (REPO_ROOT / "config" / "dashboard-routes.yaml").read_text(encoding="utf-8")
    assert "d-11-adapter-status" in routes, "aggregator table missing d-11-adapter-status route"
    assert "8107" in routes, "d-11-adapter-status route must declare port 8107"


# ---- live endpoints (the exact d-11 fetch contract) -----------------------

def test_inventory_endpoint_matches_dashboard_contract():
    reg = _write_registry()
    port = _free_port()
    proc = _spawn_api(port, reg)
    try:
        status, d = _get(port, "/api/adapters/inventory")
        assert status == 200
        assert set(d) >= {"summary", "adapters", "history", "hrm"}
        for k in ("total", "promoted", "pending", "vram_loaded_bytes"):
            assert k in d["summary"]
        a = d["adapters"][0]
        for k in ("id", "base_model", "precision", "training", "size_bytes",
                  "eval_gain_pct", "status", "gates"):
            assert k in a
        for g in ("snapshot", "test_eval", "oracle", "human", "oracle_or_human"):
            assert g in a["gates"]
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(reg)


def test_history_endpoint():
    reg = _write_registry()
    port = _free_port()
    proc = _spawn_api(port, reg)
    try:
        _, d = _get(port, "/api/adapters/history")
        assert "history" in d and d["history"][0]["action"] == "promote"
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(reg)


def test_webapp_served():
    reg = _write_registry()
    port = _free_port()
    proc = _spawn_api(port, reg)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/webapp/", timeout=3) as r:
            assert r.status == 200
            html = r.read().decode("utf-8")
        assert "D-11" in html and "adapter status" in html
        assert "/api/adapters/inventory" in html  # the dashboard fetches our endpoint
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(reg)


def test_readonly_post_rejected():
    reg = _write_registry()
    port = _free_port()
    proc = _spawn_api(port, reg)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/adapters/inventory", method="POST", data=b"{}")
        try:
            urllib.request.urlopen(req, timeout=3)
            raised = False
        except urllib.error.HTTPError as e:
            raised = (e.code == 405)
        assert raised, "mutation must be rejected 405 (read-only surface)"
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(reg)


def test_version_endpoint():
    reg = _write_registry()
    port = _free_port()
    proc = _spawn_api(port, reg)
    try:
        _, d = _get(port, "/version")
        assert d["module"] == "d-11-adapter-status"
        assert "api" in d["surfaces"] and "webapp" in d["surfaces"]
        assert d["standing_rule"] == "We do not minimize anything."
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(reg)
