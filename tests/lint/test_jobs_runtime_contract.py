#!/usr/bin/env python3
"""
tests/lint/test_jobs_runtime_contract.py — the Background Tasks runtime.

Guards the job runtime behind the Code Console's Background Tasks pane:
  * the persisted registry (jobs_store) creates/updates/persists/prunes correctly;
  * the runtime worker drives a job through queued→running→done, and cancellation
    lands it in `cancelled`;
  * a deliberation job fails GRACEFULLY when the gateway is down (never hangs);
  * the `sovereign-osctl jobs` verb + the CLI face exist.

Stdlib + pytest only. Runs against a temp registry dir; never touches /var/lib.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "scripts" / "operator" / "lib"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _store_mod():
    sys.path.insert(0, str(LIB))
    return _load("jobs_store", LIB / "jobs_store.py")


def test_registry_persists_and_summarizes(tmp_path):
    js = _store_mod()
    reg = tmp_path / "registry.json"
    s = js.JobStore(reg)
    j = s.create("demo", "warmup", device="cpu", meta={"steps": 3})
    assert j["state"] == "queued" and j["progress"] == 0
    s.update(j["id"], state="running", progress=50)
    # a fresh store reading the same file sees the persisted update (survives restart)
    s2 = js.JobStore(reg)
    assert s2.get(j["id"])["progress"] == 50
    # unknown kind is rejected
    try:
        s.create("bogus", "x")
        raise AssertionError("unknown kind must raise")
    except ValueError:
        pass
    # summary counts by state
    summ = js.summary(s.list())
    assert summ["total"] == 1 and summ["running"] == 1


def test_ingest_and_prune(tmp_path):
    js = _store_mod()
    s = js.JobStore(tmp_path / "r.json")
    v = s.ingest({"id": "vm-1", "state": "running", "progress": 40, "title": "train"})
    assert v["kind"] == "vm-job" and s.get("vm-1")["progress"] == 40
    # prune keeps recent, drops old terminal
    for i in range(5):
        d = s.create("demo", f"d{i}")
        s.update(d["id"], state="done")
    removed = s.prune(keep=3)
    assert removed >= 1 and len(s.list()) <= 3 + 1  # vm-1 is non-terminal, kept


def _api_mod(tmp_dir: Path):
    os.environ["SOVEREIGN_OS_JOBS_DIR"] = str(tmp_dir)
    sys.path.insert(0, str(LIB))
    return _load("jobs_api_under_test", REPO / "scripts" / "operator" / "jobs-api.py")


def test_worker_drives_a_job_to_done(tmp_path):
    api = _api_mod(tmp_path / "j1")
    job = api.submit("demo", "lifecycle", meta={"steps": 3, "delay": 0.01})
    for _ in range(300):
        cur = api.STORE.get(job["id"])
        if cur and cur["state"] in api._js.TERMINAL:
            break
        time.sleep(0.02)
    cur = api.STORE.get(job["id"])
    assert cur["state"] == "done" and cur["progress"] == 100 and cur["output"]


def test_cancellation_lands_in_cancelled(tmp_path):
    api = _api_mod(tmp_path / "j2")
    job = api.submit("demo", "cancel-me", meta={"steps": 200, "delay": 0.02})
    time.sleep(0.1)
    api.cancel(job["id"])
    for _ in range(300):
        cur = api.STORE.get(job["id"])
        if cur and cur["state"] in api._js.TERMINAL:
            break
        time.sleep(0.02)
    assert api.STORE.get(job["id"])["state"] == "cancelled"


def test_deliberation_fails_gracefully_without_a_gateway(tmp_path):
    api = _api_mod(tmp_path / "j3")
    # point at a dead port so the runner must fail cleanly, not hang
    api.GATEWAY_ADDR = "127.0.0.1:1"
    job = api.submit("deliberation", "no gateway", meta={"problem": "x", "rung": "coat"})
    for _ in range(600):
        cur = api.STORE.get(job["id"])
        if cur and cur["state"] in api._js.TERMINAL:
            break
        time.sleep(0.02)
    cur = api.STORE.get(job["id"])
    assert cur["state"] == "failed" and "unreachable" in cur["error"].lower()


def test_osctl_jobs_verb_and_cli_exist():
    osctl = (REPO / "scripts" / "sovereign-osctl").read_text(encoding="utf-8")
    assert "jobs)" in osctl and "jobs_cli.py" in osctl, "osctl jobs verb missing"
    assert (LIB / "jobs_cli.py").is_file(), "the jobs CLI face is missing"


def test_compute_plane_surfaces_exist():
    assert (LIB / "compute_plane.py").is_file(), "the compute plane module is missing"
    api = (REPO / "scripts" / "operator" / "jobs-api.py").read_text(encoding="utf-8")
    assert "compute_plane" in api and "PLANE" in api and "PLANE.place" in api, \
        "jobs-api must place jobs via the compute plane"
    assert "/plane.json" in api, "jobs-api must expose the compute-plane state"
    # the plane is the SINGLE VRAM claims authority: the gateway registers model
    # residents here so models + jobs share one VRAM view (no double-booking)
    for ep in ("/plane/place", "/plane/claim", "/plane/release"):
        assert ep in api, f"the compute plane must expose the claim endpoint {ep}"
    osctl = (REPO / "scripts" / "sovereign-osctl").read_text(encoding="utf-8")
    assert "plane)" in osctl, "osctl plane verb missing"
    cov = (REPO / "config" / "feature-coverage.yaml").read_text(encoding="utf-8")
    assert "plane" in cov, "plane verb not covered"


def test_the_code_console_pane_and_proxy_exist():
    api = (REPO / "scripts" / "operator" / "code-console-api.py").read_text(encoding="utf-8")
    assert "/api/code-console/jobs" in api and "_jobs_view" in api, \
        "code-console-api must proxy the jobs runtime read model"
    panel = (REPO / "webapp" / "code-console" / "index.html").read_text(encoding="utf-8")
    for token in ("cc-plan-split", "cc-tasks", "renderTasks", "/api/code-console/jobs", "sovereign-osctl jobs cancel"):
        assert token in panel, f"the Background Tasks pane is missing: {token!r}"
    # feature-coverage maps the verb to its dashboard home (the code console).
    cov = (REPO / "config" / "feature-coverage.yaml").read_text(encoding="utf-8")
    assert "code-console:" in cov and "jobs" in cov, "jobs verb not mapped to code-console"


def test_systemd_unit_is_hardened():
    unit = REPO / "systemd" / "system" / "sovereign-jobs-api.service"
    assert unit.is_file(), "the jobs-api systemd unit is missing"
    txt = unit.read_text(encoding="utf-8")
    for token in ("ProtectSystem=strict", "NoNewPrivileges=true", "ReadWritePaths=/var/lib/sovereign-os/jobs"):
        assert token in txt, f"jobs-api unit missing hardening/rw token: {token!r}"


def _plane_mod():
    sys.path.insert(0, str(LIB))
    return _load("compute_plane", LIB / "compute_plane.py")


def test_compute_plane_places_by_live_vram_fit():
    cp = _plane_mod()
    # Oracle (PRO 6000, 96 GB, 90 free) + Logic (4090, 24 GB, 20 free)
    mock = lambda: [
        {"key": "gpu0", "role": cp.ROLE_ORACLE, "name": "Blackwell PRO 6000", "total_gb": 96.0, "live_free_gb": 90.0},
        {"key": "gpu1", "role": cp.ROLE_LOGIC, "name": "RTX 4090", "total_gb": 24.0, "live_free_gb": 20.0},
    ]
    p = cp.ComputePlane(probe=mock)
    assert p.place(40) == "gpu0", "a 40 GB model fits only the 96 GB Oracle"
    assert p.place(40, cp.ROLE_LOGIC) == "gpu0", "prefer logic, but 24 GB can't hold 40 → oracle"
    assert p.place(10, cp.ROLE_LOGIC) == "gpu1", "10 GB fits + prefers the logic device"
    assert p.place(0) == "cpu", "no-VRAM work → the CPU (Conductor)"
    # a claim reduces effective free VRAM → a too-big job now has no fit (queue)
    p.claim("j1", "gpu0", 85, kind="model-load")
    assert p.place(40) is None, "with 85 GB claimed on oracle, 40 GB no longer fits anywhere"
    assert p.place(10) == "gpu1", "logic still has room"
    assert p.release("j1") and p.place(40) == "gpu0", "releasing frees the device"
    # no nvidia-smi → CPU only; a GPU job never places (waits forever, honestly)
    p2 = cp.ComputePlane(probe=lambda: [])
    assert p2.place(0) == "cpu" and p2.place(10) is None


def test_jobs_api_queues_a_job_when_vram_is_exhausted(tmp_path):
    api = _api_mod(tmp_path / "plane")
    cp = api._plane
    # a plane with a single small GPU, fully claimed → no fit for a VRAM job
    api.PLANE = cp.ComputePlane(probe=lambda: [
        {"key": "gpu0", "role": cp.ROLE_ORACLE, "name": "GPU", "total_gb": 8.0, "live_free_gb": 2.0},
    ])
    job = api.submit("demo", "needs vram", device="oracle",
                     meta={"steps": 2, "delay": 0.01, "vram_gb": 6})
    # it cannot place (2 GB free < 6) → stays queued, never runs
    time.sleep(0.3)
    assert api.STORE.get(job["id"])["state"] == "queued", "a job that can't place must WAIT, not OOM"
    api.cancel(job["id"])
    for _ in range(200):
        if api.STORE.get(job["id"])["state"] in api._js.TERMINAL:
            break
        time.sleep(0.02)
    assert api.STORE.get(job["id"])["state"] == "cancelled", "a queued (waiting) job is cancellable"


def test_vm_bridge_guest_ships_and_is_degrade_safe(tmp_path):
    bridge = REPO / "scripts" / "jobs" / "vm-bridge-guest.py"
    assert bridge.is_file(), "the 4090-VM bridge guest agent is missing"
    txt = bridge.read_text(encoding="utf-8")
    assert "/jobs/ingest" in txt and "def probe_gpu_jobs" in txt, "bridge must probe GPU + ingest to the host"
    # a mirrored vm-job is a first-class registry entry.
    js = _store_mod()
    s = js.JobStore(tmp_path / "vm.json")
    v = s.ingest({"id": "vm-9", "title": "finetune", "device": "rtx-4090-vm", "state": "running", "progress": 12})
    assert v["kind"] == "vm-job" and v["device"] == "rtx-4090-vm"
