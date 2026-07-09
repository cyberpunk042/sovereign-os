"""M060 D-07 (R10093-R10096) — memory-changes API + webapp surface contract.

Drives the D-07 cockpit dashboard from a shell to PRODUCTION: the dashboard
HTML shipped with inline MOCK data + a no-op applySnapshot. This locks the full
§1g 8-surface stack now wired AND the frontend fetch-rewire:

  core    scripts/intelligence/memory-changes.py  (M028 Memory OS projection)
  cli     sovereign-osctl memory-changes {snapshot,types,lifecycle}
  api     scripts/operator/memory-changes-api.py  (read-only HTTP)
  webapp  webapp/d-07-memory-changes/index.html   (now fetches /api/d-07/*)
  service systemd/system/sovereign-memory-changes-api.service

The core reads the M028 Memory OS state and projects the 8 memory types
(E0260+E0265) + 11-stage admission lifecycle (M00471) + graph diff + pending
promote/pin/forget queue + MS039 7 trust dims. Per operator §1g (verbatim):
"We do not minimize anything." Read-only — promote/pin/forget are CLI verbs.
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
CORE = REPO_ROOT / "scripts" / "intelligence" / "memory-changes.py"
API_DAEMON = REPO_ROOT / "scripts" / "operator" / "memory-changes-api.py"
SYSTEMD_UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-memory-changes-api.service"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"
WEBAPP = REPO_ROOT / "webapp" / "d-07-memory-changes" / "index.html"

_STATE = {
    "profile": "careful", "diffBase": "memos.v1147", "diffHead": "memos.v1183",
    "counts": {"working": 23, "episodic": 412, "semantic": 6841, "procedural": 87,
               "temporal": 1209, "value": 358, "kv": 1280, "reward": 942},
    "lifecycle": {"observe": 7, "classify": 4, "quarantine": 2, "link": 11, "score": 8,
                  "store-raw": 14, "extract": 9, "verify": 6, "promote": 3,
                  "decay": 21, "archive": 5},
    "diffs": [{"op": "added", "text": "+ semantic NVFP4 fact"},
              {"op": "bogus", "text": "normalised op"}],
    "pending": [{"id": "mc-001", "op": "promote", "mtype": "semantic",
                 "scope": "NVFP4 taxonomy", "delta": "+0.12 trust", "requester": "operator-fp"},
                {"id": "mc-002", "op": "weird", "mtype": "x", "scope": "y"},
                {"op": "forget"}],  # no id → dropped
}


def _write_state() -> str:
    fd, path = tempfile.mkstemp(prefix="memory-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(_STATE, fh)
    return path


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _spawn_api(port: int, state: str, extra_env: dict | None = None):
    env = {
        "MEMORY_CHANGES_API_BIND": "127.0.0.1",
        "MEMORY_CHANGES_API_PORT": str(port),
        "SOVEREIGN_OS_MEMORY_STATE": state,
        "SOVEREIGN_OS_METRICS_DIR": "/tmp/sovereign-os-test-metrics",
        "PATH": "/usr/bin:/bin",
    }
    if extra_env:
        env.update(extra_env)
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
    raise RuntimeError("memory-changes-api failed to start within 6s")


def _get(port: int, path: str):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as r:
        return r.status, json.loads(r.read())


# ---- structural -----------------------------------------------------------

def test_core_present_and_projects_m028():
    assert CORE.is_file(), f"core missing: {CORE}"
    state = _write_state()
    try:
        out = subprocess.run(
            ["python3", str(CORE), "snapshot", "--json"],
            capture_output=True, text=True, timeout=15, check=True,
            env={**os.environ, "SOVEREIGN_OS_MEMORY_STATE": state},
        )
        d = json.loads(out.stdout)
        assert set(d) >= {"counts", "profile", "lifecycle", "diffBase",
                          "diffHead", "diffs", "pending", "trust_dimensions"}
        # 8 memory types (E0260 + E0265 reward)
        assert set(d["counts"]) == {"working", "episodic", "semantic", "procedural",
                                    "temporal", "value", "kv", "reward"}
        assert d["counts"]["semantic"] == 6841
        # 11-stage lifecycle in canonical order
        assert [s for s, _ in d["lifecycle"]] == [
            "observe", "classify", "quarantine", "link", "score", "store-raw",
            "extract", "verify", "promote", "decay", "archive"]
        # MS039 7 trust dimensions
        assert d["trust_dimensions"] == ["trust", "value", "freshness", "permission",
                                         "topic", "user-scope", "failure-relevance"]
        # malformed diff op normalised; pending entry without id dropped
        assert [x["op"] for x in d["diffs"]] == ["added", "changed"]
        assert {p["id"] for p in d["pending"]} == {"mc-001", "mc-002"}
        assert [p["op"] for p in d["pending"] if p["id"] == "mc-002"] == ["promote"]
    finally:
        os.unlink(state)


def test_core_empty_state_graceful():
    out = subprocess.run(
        ["python3", str(CORE), "snapshot", "--json"],
        capture_output=True, text=True, timeout=15, check=True,
        env={**os.environ, "SOVEREIGN_OS_MEMORY_STATE": "/tmp/sovereign-os-no-memory.json"},
    )
    d = json.loads(out.stdout)
    assert all(v == 0 for v in d["counts"].values())
    assert len(d["lifecycle"]) == 11 and d["diffs"] == [] and d["pending"] == []
    assert d["profile"] == "private"


def test_frontend_rewired_to_live_api():
    html = WEBAPP.read_text(encoding="utf-8")
    assert "/api/d-07/snapshot" in html, "webapp must fetch /api/d-07/snapshot"
    # the inline mock-seed rows must be gone
    assert "mock seed data" not in html
    assert '"semantic": 6841' not in html and "semantic: 6841" not in html
    # applySnapshot must now actually render (not a no-op stub)
    assert "function applySnapshot" in html and "render();" in html


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
        if "MEMORY_CHANGES_API_BIND=" in ln:
            assert "MEMORY_CHANGES_API_BIND=127.0.0.1" in ln, ln
            found = True
        assert "MEMORY_CHANGES_API_BIND=0.0.0.0" not in ln, ln
    assert found, "service unit must set MEMORY_CHANGES_API_BIND=127.0.0.1"


def test_systemd_unit_defense_in_depth():
    body = SYSTEMD_UNIT.read_text(encoding="utf-8")
    for key in ("ProtectSystem=strict", "NoNewPrivileges=true", "PrivateTmp=true",
                "ProtectHome=true", "RestrictAddressFamilies=", "SystemCallFilter="):
        assert key in body, f"R171 hardening key missing: {key}"


def test_osctl_dispatches_memory_changes():
    body = OSCTL.read_text(encoding="utf-8")
    assert "memory-changes)" in body, "osctl missing memory-changes dispatch case"
    assert "scripts/intelligence/memory-changes.py" in body


def test_master_dashboard_route_registered():
    body = (REPO_ROOT / "scripts" / "operator" / "master-dashboard.py").read_text(encoding="utf-8")
    assert '"memory-changes"' in body, "master-dashboard missing memory-changes route"
    assert "8112" in body, "memory-changes route must declare port 8112"


# ---- live endpoints (the exact d-07 fetch contract) -----------------------

def test_snapshot_endpoint_matches_dashboard_contract():
    state = _write_state()
    port = _free_port()
    proc = _spawn_api(port, state)
    try:
        status, d = _get(port, "/api/d-07/snapshot")
        assert status == 200
        assert set(d) >= {"counts", "profile", "lifecycle", "diffs", "pending"}
        assert set(d["counts"]) == {"working", "episodic", "semantic", "procedural",
                                    "temporal", "value", "kv", "reward"}
        assert len(d["lifecycle"]) == 11
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(state)


def test_entries_endpoint_empty_safe():
    """SDD-060 — /api/d-07/entries is read-only + empty-safe when no store exists."""
    state = _write_state()
    port = _free_port()
    proc = _spawn_api(port, state, extra_env={
        "SOVEREIGN_OS_MEMORY_STORE_DB": "/tmp/sovereign-os-no-store.json"})
    try:
        status, d = _get(port, "/api/d-07/entries")
        assert status == 200
        assert isinstance(d.get("entries"), list) and d["entries"] == []
        assert "schema_version" in d
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(state)


def test_entries_endpoint_projects_the_store():
    """SDD-060 — the entries endpoint surfaces the addressable mem-<id> store
    (a SECOND read source; the snapshot projection is separate)."""
    state = _write_state()
    fd, store = tempfile.mkstemp(prefix="memory-store-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"entries": {
            "mem-aa11": {"id": "mem-aa11", "type": 3, "stage": "store-raw",
                         "summary": "a semantic fact", "state": "active",
                         "created": "2026-07-09T00:00:00+00:00",
                         "updated": "2026-07-09T00:00:00+00:00"},
            "mem-bb22": {"id": "mem-bb22", "type": 1, "stage": "store-raw",
                         "summary": "a working note", "state": "forgotten",
                         "created": "2026-07-09T00:00:00+00:00",
                         "updated": "2026-07-09T00:00:00+00:00"},
        }}, fh)
    port = _free_port()
    proc = _spawn_api(port, state, extra_env={"SOVEREIGN_OS_MEMORY_STORE_DB": store})
    try:
        status, d = _get(port, "/api/d-07/entries")
        assert status == 200
        ids = {e["id"] for e in d["entries"]}
        assert ids == {"mem-aa11", "mem-bb22"}
        states = {e["id"]: e["state"] for e in d["entries"]}
        assert states["mem-aa11"] == "active" and states["mem-bb22"] == "forgotten"
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(state); os.unlink(store)


def test_entries_endpoint_readonly_post_rejected():
    """SDD-060 — the new read endpoint keeps the surface read-only (POST → 405)."""
    state = _write_state()
    port = _free_port()
    proc = _spawn_api(port, state)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/d-07/entries", method="POST", data=b"{}")
        try:
            urllib.request.urlopen(req, timeout=3)
            raised = False
        except urllib.error.HTTPError as e:
            raised = (e.code == 405)
        assert raised, "mutation on /api/d-07/entries must be rejected 405"
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(state)


def test_webapp_fetches_entries_endpoint():
    """SDD-060 — the D-07 webapp must fetch the entries list."""
    html = WEBAPP.read_text(encoding="utf-8")
    assert "/api/d-07/entries" in html, "webapp must fetch /api/d-07/entries"
    assert "loadEntries" in html and "memory-entries" in html
    # the per-row forget button must jump to the wired control with the id prefilled
    assert "jumpToControl('memory-forget', " in html


def test_navigate_endpoint_projects_the_store():
    """SDD-068 — the RLM navigator GET ranks matching slices from the store
    (read-compute; honest-defer for the composed answer with no LM)."""
    state = _write_state()
    fd, store = tempfile.mkstemp(prefix="memory-store-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"entries": {
            "mem-aa11": {"id": "mem-aa11", "type": 2, "stage": "verify",
                         "summary": "router failed on gpu one after a dependency bump",
                         "state": "active", "topic": "networking",
                         "tags": ["router", "gpu", "dependency"],
                         "created": "2026-07-01T00:00:00+00:00",
                         "updated": "2026-07-05T00:00:00+00:00"},
            "mem-bb22": {"id": "mem-bb22", "type": 3, "stage": "observe",
                         "summary": "grocery list milk eggs", "state": "active",
                         "created": "2026-07-02T00:00:00+00:00",
                         "updated": "2026-07-02T00:00:00+00:00"},
        }}, fh)
    port = _free_port()
    proc = _spawn_api(port, state, extra_env={"SOVEREIGN_OS_MEMORY_STORE_DB": store})
    try:
        # deterministic slice-select (compose=0 → no LM); the router entry ranks, grocery drops.
        status, d = _get(port, "/api/d-07/navigate?q=router%20dependency&compose=0")
        assert status == 200
        ids = {s["id"] for s in d["slices"]}
        assert "mem-aa11" in ids and "mem-bb22" not in ids
        # a temporal verb (changed → updated != created) over the same store.
        status2, d2 = _get(port, "/api/d-07/navigate?verb=changed&compose=0")
        assert status2 == 200 and [s["id"] for s in d2["slices"]] == ["mem-aa11"]
        # contradicted-by honest-defers (no contradiction substrate) — never fabricated.
        status3, d3 = _get(port, "/api/d-07/navigate?verb=contradicted-by")
        assert status3 == 200 and d3["deferred"] is True and d3["count"] == 0
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(state); os.unlink(store)


def test_navigate_endpoint_empty_safe():
    """SDD-068 — navigate over an absent/empty store is empty-safe, never a crash."""
    state = _write_state()
    port = _free_port()
    proc = _spawn_api(port, state, extra_env={
        "SOVEREIGN_OS_MEMORY_STORE_DB": "/nonexistent/store.json"})
    try:
        status, d = _get(port, "/api/d-07/navigate?q=anything&compose=0")
        assert status == 200 and d["ok"] is True and d["count"] == 0
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(state)


def test_navigate_endpoint_readonly_post_rejected():
    """SDD-068 — the navigator is a read-only GET; a POST stays 405 (R10212)."""
    state = _write_state()
    port = _free_port()
    proc = _spawn_api(port, state)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/d-07/navigate", method="POST", data=b"{}")
        try:
            urllib.request.urlopen(req, timeout=3)
            raised = False
        except urllib.error.HTTPError as e:
            raised = (e.code == 405)
        assert raised, "mutation on /api/d-07/navigate must be rejected 405"
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(state)


def test_webapp_has_navigate_query_box():
    """SDD-068 — the D-07 webapp must fetch the navigator + expose the query box."""
    html = WEBAPP.read_text(encoding="utf-8")
    assert "/api/d-07/navigate" in html, "webapp must fetch /api/d-07/navigate"
    assert "function navigate(" in html and "nav-q" in html


def test_webapp_served():
    state = _write_state()
    port = _free_port()
    proc = _spawn_api(port, state)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/webapp/", timeout=3) as r:
            assert r.status == 200
            html = r.read().decode("utf-8")
        assert "D-07" in html and "memory changes" in html
        assert "/api/d-07/snapshot" in html
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(state)


def test_readonly_post_rejected():
    state = _write_state()
    port = _free_port()
    proc = _spawn_api(port, state)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/d-07/snapshot", method="POST", data=b"{}")
        try:
            urllib.request.urlopen(req, timeout=3)
            raised = False
        except urllib.error.HTTPError as e:
            raised = (e.code == 405)
        assert raised, "mutation must be rejected 405 (read-only surface)"
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(state)


def test_version_endpoint():
    state = _write_state()
    port = _free_port()
    proc = _spawn_api(port, state)
    try:
        _, d = _get(port, "/version")
        assert d["module"] == "d-07-memory-changes"
        assert "api" in d["surfaces"] and "webapp" in d["surfaces"]
        assert d["standing_rule"] == "We do not minimize anything."
    finally:
        proc.kill(); proc.wait(timeout=3); os.unlink(state)
