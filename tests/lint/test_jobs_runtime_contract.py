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

import pytest

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


def _make_store(js, backend, tmp_path):
    if backend == "sqlite":
        return js.SqliteStore(tmp_path / "registry.db")
    return js.JsonStore(tmp_path / "registry.json")


@pytest.mark.parametrize("backend", ["json", "sqlite"])
def test_store_contract_holds_for_both_backends(backend, tmp_path):
    # The whole create/get/list/update/ingest/prune contract + restart-persistence
    # must be identical for json and sqlite — nothing downstream can tell them apart.
    js = _store_mod()
    s = _make_store(js, backend, tmp_path)
    assert s.backend == backend

    j = s.create("demo", "warmup", device="cpu", meta={"steps": 3}, priority="high")
    assert j["state"] == "queued" and j["progress"] == 0 and j["priority"] == "high"
    assert s.get(j["id"])["meta"] == {"steps": 3}

    # update persists across a reopen (survives restart)
    s.update(j["id"], state="running", progress=50)
    s2 = _make_store(js, backend, tmp_path)
    got = s2.get(j["id"])
    assert got["state"] == "running" and got["progress"] == 50
    assert got["updated"] >= got["created"]

    # unknown kind / priority rejected identically
    with pytest.raises(ValueError):
        s.create("bogus", "x")
    with pytest.raises(ValueError):
        s.create("demo", "x", priority="urgent")

    # ingest upserts by id and preserves the original `created` on re-ingest
    s.ingest({"id": "vm-1", "state": "running", "progress": 40, "title": "train"})
    created0 = s.get("vm-1")["created"]
    s.ingest({"id": "vm-1", "state": "done", "progress": 100})
    assert s.get("vm-1")["created"] == created0 and s.get("vm-1")["state"] == "done"

    assert {x["id"] for x in s.list()} == {j["id"], "vm-1"}
    assert js.summary(s.list())["total"] == 2

    # prune drops oldest terminal beyond keep, never the non-terminal running job
    for i in range(5):
        d = s.create("demo", f"d{i}")
        s.update(d["id"], state="done")
    removed = s.prune(keep=3)
    assert removed >= 1
    assert any(x["id"] == j["id"] for x in s.list()), "the running job must survive prune"


def test_migrate_round_trips_both_directions(tmp_path):
    # json→sqlite (enable) and sqlite→json (revert) preserve every id + field.
    js = _store_mod()
    jstore = js.JsonStore(tmp_path / "registry.json")
    jstore.create("demo", "alpha", meta={"k": 1})
    b = jstore.create("eval", "beta", priority="low")
    jstore.update(b["id"], state="running", progress=33)
    before = {x["id"]: x for x in jstore.list()}

    sq = js.SqliteStore(tmp_path / "registry.db")
    assert js.migrate(jstore, sq) == 2
    assert {x["id"]: x for x in sq.list()} == before, "json→sqlite must preserve all fields"

    jstore2 = js.JsonStore(tmp_path / "registry2.json")
    assert js.migrate(sq, jstore2) == 2
    assert {x["id"]: x for x in jstore2.list()} == before, "sqlite→json must preserve all fields"


def test_open_store_toggle_and_autoseed(tmp_path, monkeypatch):
    js = _store_mod()
    # a legacy json registry with two jobs
    jstore = js.JsonStore(tmp_path / "registry.json")
    jstore.create("demo", "legacy-a")
    jstore.create("demo", "legacy-b")

    monkeypatch.delenv("SOVEREIGN_OS_JOBS_STORE", raising=False)
    s_json = js.open_store(tmp_path / "registry.json")
    assert s_json.backend == "json" and len(s_json.list()) == 2

    # enabling sqlite with an empty db auto-seeds one-way from the sibling json
    s_sql = js.open_store(tmp_path / "registry.db", backend="sqlite")
    assert s_sql.backend == "sqlite"
    assert sorted(x["title"] for x in s_sql.list()) == ["legacy-a", "legacy-b"]
    # idempotent: a non-empty db is never re-seeded
    assert len(js.open_store(tmp_path / "registry.db", backend="sqlite").list()) == 2

    # resolve_backend honors the env and falls back on garbage
    monkeypatch.setenv("SOVEREIGN_OS_JOBS_STORE", "sqlite")
    assert js.resolve_backend() == "sqlite"
    monkeypatch.setenv("SOVEREIGN_OS_JOBS_STORE", "nonsense")
    assert js.resolve_backend() == "json"


def test_persisted_backend_choice_wins_over_env(tmp_path, monkeypatch):
    # The cockpit "Jobs Registry Backend" control persists the choice; it must take
    # precedence over the env default so a settings switch sticks across restarts.
    js = _store_mod()
    js.JOBS_DIR = tmp_path  # point the persisted-choice file at the temp jobs dir
    monkeypatch.setenv("SOVEREIGN_OS_JOBS_STORE", "json")
    assert js.resolve_backend() == "json"  # env default, no persisted choice yet
    js.set_persisted_backend("sqlite", tmp_path)
    assert js.persisted_backend(tmp_path) == "sqlite"
    assert js.resolve_backend() == "sqlite"  # persisted settings choice beats the env
    assert js.resolve_backend("json") == "json"  # an explicit arg still wins over all
    with pytest.raises(ValueError):
        js.set_persisted_backend("bogus", tmp_path)


def test_jobs_store_is_a_registered_signed_control():
    # The backend toggle is a first-class control-systems entry (its appropriate
    # place), executed via the signed /api/control/execute → sudo path — NOT a
    # webapp mutation and NOT clipboard-only. Surfaced data-driven on the Code
    # Console via applies_to.
    reg = (REPO / "config" / "control-systems.yaml").read_text(encoding="utf-8")
    assert "id: jobs-store" in reg, "the backend toggle must be in the control registry"
    assert "sovereign-osctl jobs store <id>" in reg, "change_cli must be the store verb"
    assert "applies_to: [code-console]" in reg, "must surface on the Code Console pane"
    cli = (REPO / "scripts/operator/lib/jobs_cli.py").read_text(encoding="utf-8")
    assert '"store"' in cli, "osctl jobs must expose the `store` verb"
    sudoers = (REPO / "config/sudoers.d/sovereign-os-cockpit").read_text(encoding="utf-8")
    assert "sovereign-osctl jobs store *" in sudoers, "the store verb must be sudo-allowlisted"


def test_jobs_api_uses_the_store_toggle_and_migrate_cli():
    # jobs-api must construct via the factory (so the toggle is honored) and expose
    # the manual migration CLI.
    src = (REPO / "scripts" / "operator" / "jobs-api.py").read_text(encoding="utf-8")
    assert "_js.open_store()" in src, "jobs-api must open the registry via the backend factory"
    assert "--migrate-to" in src, "jobs-api must expose the migrate CLI"


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


def test_deliberation_submit_needs_no_token_but_command_submit_does(tmp_path):
    # F-2026-063 steering: the brain webapp (via brain-api) submits a
    # "deliberation" job. A deliberation is NOT a command kind, so the mutation
    # guard allows it from loopback + same-origin with NO token — that's what lets
    # the webapp path work without an RCE-grade credential. A command-executing
    # submit stays strict (token required when one is configured).
    api = _api_mod(tmp_path / "guard")
    api._JOBS_TOKEN = "sekret"  # a configured command-submit token
    allow = api.mutation_guard({"Content-Type": "application/json"}, "127.0.0.1",
                               path="/jobs",
                               body={"kind": "deliberation", "meta": {"problem": "x"}})
    assert allow is None, f"deliberation submit must pass without a token, got {allow}"
    reject = api.mutation_guard({"Content-Type": "application/json"}, "127.0.0.1",
                                path="/jobs",
                                body={"kind": "eval", "meta": {"command": ["true"]}})
    assert reject is not None and reject[0] == 401, \
        f"a command submit must still require the token, got {reject}"


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


def test_background_deliberation_targets_the_secondary(tmp_path):
    """A deliberation job sends the reserved model alias `"background"` to /v1/coat
    so it runs on the secondary, keeping the primary free for interactive chat."""
    import json as _json
    import threading as _threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    api = _api_mod(tmp_path / "bg")
    seen: list[dict] = []

    class _H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            seen.append(_json.loads(self.rfile.read(n) or b"{}"))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"kind":"coat-trace","trace":{"summary":"ok","best_path":[]}}')

    gw = ThreadingHTTPServer(("127.0.0.1", 0), _H)
    _threading.Thread(target=gw.serve_forever, daemon=True).start()
    api.GATEWAY_ADDR = f"127.0.0.1:{gw.server_address[1]}"
    try:
        job = api.submit("deliberation", "plan the migration", meta={"rung": "cot"})
        for _ in range(600):
            if api.STORE.get(job["id"])["state"] in api._js.TERMINAL:
                break
            time.sleep(0.02)
        assert api.STORE.get(job["id"])["state"] == "done"
        assert seen, "the deliberation must call the gateway"
        assert seen[0].get("model") == "background", \
            "a background deliberation must target the secondary via the 'background' alias"
    finally:
        gw.shutdown()


def test_model_serve_launches_registers_and_unregisters(tmp_path):
    """A model-serve job PLACES VRAM, launches the serve process, registers a gateway
    proxy once its endpoint is up, and on cancel terminates it + unregisters."""
    import json as _json
    import socket as _socket
    import threading as _threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    api = _api_mod(tmp_path / "serve")
    cp = api._plane
    # a plane with one GPU that has room for the model
    api.PLANE = cp.ComputePlane(probe=lambda: [
        {"key": "gpu0", "role": cp.ROLE_LOGIC, "name": "RTX 4090", "total_gb": 24.0, "live_free_gb": 20.0},
    ])
    # a mock gateway capturing register / unload POSTs
    seen: list[tuple[str, dict]] = []

    class _H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # silence
            pass

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            body = _json.loads(self.rfile.read(n) or b"{}")
            seen.append((self.path, body))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

    gw = ThreadingHTTPServer(("127.0.0.1", 0), _H)
    _threading.Thread(target=gw.serve_forever, daemon=True).start()
    api.GATEWAY_ADDR = f"127.0.0.1:{gw.server_address[1]}"

    # a free port for the mock serve process to bind
    probe = _socket.socket()
    probe.bind(("127.0.0.1", 0))
    serve_port = probe.getsockname()[1]
    probe.close()
    endpoint = f"127.0.0.1:{serve_port}"
    serve_src = (
        "import socket,time;"
        "s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);"
        f"s.bind(('127.0.0.1',{serve_port}));s.listen(8);time.sleep(600)"
    )
    try:
        job = api.submit("model-serve", "gpu-llama", device="logic", meta={
            "command": [sys.executable, "-c", serve_src],
            "endpoint": endpoint, "model_id": "gpu-llama", "dialect": "openai",
            "vram_gb": 12, "ready_timeout": 15,
        })
        # wait until it registers the proxy (serving)
        for _ in range(1000):
            if any(p == "/v1/models/register" for p, _ in seen):
                break
            time.sleep(0.02)
        reg = next((b for p, b in seen if p == "/v1/models/register"), None)
        assert reg is not None, "model-serve must register a gateway proxy once its endpoint is up"
        assert reg["id"] == "gpu-llama" and reg["endpoint"] == endpoint
        assert reg["dialect"] == "openai" and reg["vram_gb"] == 12
        assert reg["device"] == "gpu0", "it must register the ACTUAL plane-placed device"
        assert api.STORE.get(job["id"])["state"] == "running", "a serving job stays running until stopped"
        # cancel → terminate serve process, unregister proxy, release VRAM
        api.cancel(job["id"])
        for _ in range(1000):
            if api.STORE.get(job["id"])["state"] in api._js.TERMINAL:
                break
            time.sleep(0.02)
        assert api.STORE.get(job["id"])["state"] == "cancelled"
        assert any(p == "/v1/models/unload" for p, _ in seen), "on stop it must unregister the proxy"
        # the VRAM claim was released — the device is free again
        assert api.PLANE.place(20, cp.ROLE_LOGIC) == "gpu0", "cancel must release the plane VRAM claim"
    finally:
        gw.shutdown()


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


def test_the_code_console_wires_the_model_registry():
    """The UX loop: the console reads the gateway model registry, the composer picks a
    model (incl. the 'background' alias), and the chat POST carries it."""
    api = (REPO / "scripts" / "operator" / "code-console-api.py").read_text(encoding="utf-8")
    # a read-only proxy of GET /v1/models + the chat POST threads a model id
    assert "/api/code-console/models" in api and "_models_view" in api, \
        "code-console-api must proxy the gateway model registry"
    assert 'req.get("model"' in api and "model=model" in api, \
        "the chat proxy must thread a model id to the inference runner"
    panel = (REPO / "webapp" / "code-console" / "index.html").read_text(encoding="utf-8")
    for token in ("cc-model", "renderModels", "refreshModels", "/api/code-console/models"):
        assert token in panel, f"the model picker wiring is missing: {token!r}"
    # the composer send body carries the chosen model (incl. the 'background' alias)
    assert "model: ($('cc-model')" in panel, "the chat send must include the selected model"
    assert "value=\"background\"" in panel or "'background'" in panel, \
        "the picker must offer the 'background' alias"


def test_model_serve_cli_builds_and_submits():
    """The `osctl model-serve` operability verb: `serve_command` builds the engine
    argv, and `start` submits a model-serve job to jobs-api with the right meta."""
    import json as _json
    import threading as _threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    sys.path.insert(0, str(LIB))
    msc = _load("model_serve_cli", LIB / "model_serve_cli.py")
    # engine argv templates (no shell)
    llama = msc.serve_command("llama-server", "/m/x", 8090)
    assert llama[:3] == ["llama-server", "--model", "/m/x"] and "8090" in llama
    assert msc.serve_command("vllm", "/m/x", 8091)[:2] == ["vllm", "serve"]

    seen: list[dict] = []

    class _H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            seen.append(_json.loads(self.rfile.read(n) or b"{}"))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"id":"job-1","state":"queued"}')

    srv = ThreadingHTTPServer(("127.0.0.1", 0), _H)
    _threading.Thread(target=srv.serve_forever, daemon=True).start()
    msc.JOBS_ADDR = f"127.0.0.1:{srv.server_address[1]}"
    # this test exercises the submit/meta logic, not engine presence — skip preflight
    os.environ["SOVEREIGN_MODEL_SERVE_NO_PREFLIGHT"] = "1"
    try:
        rc = msc.main(["start", "big", "--model", "/models/llama-70b", "--vram", "40",
                       "--port", "8090", "--dialect", "openai", "--device", "oracle", "--json"])
        assert rc == 0, "start must succeed against a live jobs-api"
        assert seen, "start must POST to jobs-api"
        body = seen[0]
        assert body["kind"] == "model-serve" and body["title"] == "big" and body["device"] == "oracle"
        meta = body["meta"]
        assert meta["endpoint"] == "127.0.0.1:8090" and meta["dialect"] == "openai"
        assert meta["vram_gb"] == 40 and meta["model_id"] == "big"
        assert meta["command"][0] == "llama-server", "the runner launches the serve argv"
    finally:
        srv.shutdown()
        os.environ.pop("SOVEREIGN_MODEL_SERVE_NO_PREFLIGHT", None)

    # start PREFLIGHTS the engine: a missing binary fails at submit, not opaquely at
    # launch. Guarded so a box that happens to have llama-server installed doesn't
    # false-fail the assertion.
    import shutil as _shutil
    os.environ.pop("SOVEREIGN_MODEL_SERVE_NO_PREFLIGHT", None)
    if _shutil.which("llama-server") is None:
        rc = msc.main(["start", "x", "--model", "/m", "--vram", "1", "--json"])
        assert rc == 1, "start must refuse when the serve engine is not on PATH"

    # osctl wires the verb to the CLI
    osctl = (REPO / "scripts" / "sovereign-osctl").read_text(encoding="utf-8")
    assert "model-serve)" in osctl and "model_serve_cli.py" in osctl, "osctl model-serve verb missing"
    cov = (REPO / "config" / "feature-coverage.yaml").read_text(encoding="utf-8")
    assert "model-serve" in cov, "model-serve verb not mapped in feature-coverage"


def test_systemd_unit_is_hardened():
    unit = REPO / "systemd" / "system" / "sovereign-jobs-api.service"
    assert unit.is_file(), "the jobs-api systemd unit is missing"
    txt = unit.read_text(encoding="utf-8")
    for token in ("ProtectSystem=strict", "NoNewPrivileges=true", "ReadWritePaths=/var/lib/sovereign-os/jobs"):
        assert token in txt, f"jobs-api unit missing hardening/rw token: {token!r}"


def _plane_mod():
    sys.path.insert(0, str(LIB))
    return _load("compute_plane", LIB / "compute_plane.py")


def test_place_and_claim_is_atomic_no_overcommit():
    """The no-OOM invariant: place+claim is atomic, so a second admission observes
    the first's committed VRAM and cannot over-commit the same device (the check-then-
    act race that `place()` then a separate `claim()` allowed)."""
    cp = _plane_mod()
    p = cp.ComputePlane(probe=lambda: [
        {"key": "gpu0", "role": cp.ROLE_LOGIC, "name": "RTX 4090", "total_gb": 24.0, "live_free_gb": 24.0},
    ])
    assert p.place_and_claim("a", 20, cp.ROLE_LOGIC) == "gpu0", "the first 20 GB claim fits + is recorded"
    # a second 20 GB claim now sees only 4 GB effective-free → cannot place (no over-commit)
    assert p.place_and_claim("b", 20, cp.ROLE_LOGIC) is None, "20 GB must not fit after 20 GB is claimed"
    assert p.place_and_claim("c", 4, cp.ROLE_LOGIC) == "gpu0", "4 GB still fits the remaining headroom"
    # releasing the first frees the device again
    assert p.release("a")
    assert p.place_and_claim("d", 18, cp.ROLE_LOGIC) == "gpu0", "releasing frees the VRAM for a new claim"


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


# ── mutation_guard: jobs-api RCE hardening (2026-07-17) ──────────────────────
# `POST /jobs {kind:"eval",meta:{command:[...]}}` runs an argv as the daemon's
# user (root under the shipped unit). Before the guard it had NO authenticity
# check and _body() parses JSON regardless of Content-Type, so a web page the
# operator visited could drive it cross-origin — RCE-as-root via browser CSRF.

def test_guard_allows_legit_loopback_osctl_submit(tmp_path):
    api = _api_mod(tmp_path / "g1")
    # osctl/control-exec: loopback peer, no Origin, application/json.
    assert api.mutation_guard(
        {"Content-Type": "application/json"}, "127.0.0.1",
        path="/jobs", body={"kind": "eval", "meta": {"command": ["echo", "hi"]}}
    ) is None


def test_guard_blocks_cross_site_origin(tmp_path):
    api = _api_mod(tmp_path / "g2")
    r = api.mutation_guard(
        {"Origin": "https://evil.example", "Content-Type": "text/plain"},
        "127.0.0.1", path="/jobs",
        body={"kind": "eval", "meta": {"command": ["rm", "-rf", "/"]}})
    assert r is not None and r[0] == 403, "browser CSRF (cross-site Origin) must be refused"


def test_guard_blocks_referer_cross_site(tmp_path):
    api = _api_mod(tmp_path / "g2b")
    r = api.mutation_guard(
        {"Referer": "https://evil.example/x", "Content-Type": "application/json"},
        "127.0.0.1", path="/jobs", body={"kind": "eval", "meta": {"command": ["x"]}})
    assert r is not None and r[0] == 403


def test_guard_blocks_text_plain_command_submit(tmp_path):
    """The browser 'simple request' CSRF vector: a text/plain POST needs no
    preflight. The command submit path must reject non-application/json."""
    api = _api_mod(tmp_path / "g3")
    r = api.mutation_guard(
        {"Content-Type": "text/plain"}, "127.0.0.1",
        path="/jobs", body={"kind": "eval", "meta": {"command": ["x"]}})
    assert r is not None and r[0] == 415


def test_guard_blocks_non_loopback_peer(tmp_path):
    api = _api_mod(tmp_path / "g4")
    r = api.mutation_guard(
        {"Content-Type": "application/json"}, "10.0.0.9",
        path="/jobs", body={"kind": "eval", "meta": {"command": ["x"]}})
    assert r is not None and r[0] == 403


def test_guard_allows_gateway_plane_calls(tmp_path):
    """The gateway's /plane/* machine calls (no Origin, loopback) must pass —
    the guard hardens without breaking the compute-plane authority path."""
    api = _api_mod(tmp_path / "g5")
    assert api.mutation_guard({}, "127.0.0.1", path="/plane/place",
                              body={"need_gb": 4}) is None


def test_guard_token_required_when_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("SOVEREIGN_OS_JOBS_TOKEN", "s3cr3t")
    api = _api_mod(tmp_path / "g6")
    base = {"Content-Type": "application/json"}
    body = {"kind": "eval", "meta": {"command": ["x"]}}
    # missing token → 401
    r = api.mutation_guard(base, "127.0.0.1", path="/jobs", body=body)
    assert r is not None and r[0] == 401
    # correct token → allowed
    ok = dict(base, **{"X-Sovereign-Jobs-Token": "s3cr3t"})
    assert api.mutation_guard(ok, "127.0.0.1", path="/jobs", body=body) is None
    # wrong token → 401
    bad = dict(base, **{"X-Sovereign-Jobs-Token": "nope"})
    assert api.mutation_guard(bad, "127.0.0.1", path="/jobs", body=body)[0] == 401


def test_cli_forwards_token_when_set(monkeypatch):
    monkeypatch.setenv("SOVEREIGN_OS_JOBS_TOKEN", "abc")
    cli = _load("jobs_cli_ut", LIB / "jobs_cli.py")
    captured = {}

    class _FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"ok": true}'

    def _fake_urlopen(req, timeout=0):
        captured["headers"] = {k.lower(): v for k, v in req.header_items()}
        return _FakeResp()

    monkeypatch.setattr(cli.urllib.request, "urlopen", _fake_urlopen)
    cli._call("POST", "/jobs", {"kind": "eval"})
    assert captured["headers"].get("X-sovereign-jobs-token".lower()) == "abc", (
        "jobs_cli must forward the shared token so the sanctioned path still works"
    )


# ── F-2026-091: grow the runtime (workdir sandbox / rlimits+timeout / priority /
#    checkpoint-resume) ──────────────────────────────────────────────────────

def test_priority_persists_and_summary_counts(tmp_path):
    js = _store_mod()
    s = js.JobStore(tmp_path / "p.json")
    s.create("demo", "hi", priority="high")
    s.create("demo", "lo", priority="low")
    s.create("demo", "def")  # default normal
    by = js.summary(s.list())["by_priority"]
    assert by == {"high": 1, "low": 1, "normal": 1}
    # an unknown priority is rejected at create
    try:
        s.create("demo", "x", priority="bogus")
        raise AssertionError("unknown priority must raise")
    except ValueError:
        pass


def test_priority_queue_orders_high_before_low(tmp_path):
    """The dispatch queue drains high before normal before low (the ordering
    contract), independent of submit order — tested deterministically over the
    priority tuple so it never races the worker threads."""
    import queue as _q
    api = _api_mod(tmp_path / "pq")
    pq: _q.PriorityQueue = _q.PriorityQueue()
    for prio, jid in [("low", "a"), ("high", "b"), ("normal", "c")]:
        pq.put((api._PRIORITY_RANK[prio], 0, jid))
    drained = [pq.get()[2] for _ in range(3)]
    assert drained == ["b", "c", "a"], "must drain high → normal → low"
    # and a submitted job carries its priority into the registry
    j = api.submit("demo", "hp", meta={"steps": 1, "delay": 0.01}, priority="high")
    assert api.STORE.get(j["id"])["priority"] == "high"


def test_command_job_output_is_confined_to_the_jobs_tree(tmp_path):
    """A command runner's cwd + log live under WORK_ROOT/<id> (inside the one
    ReadWritePaths the unit grants), not read-only REPO or PrivateTmp — the
    F-2026-091 sandbox-breakage fix. The job records its workdir."""
    api = _api_mod(tmp_path / "wd")
    j = api.submit("eval", "write-a-file", meta={"command": [
        sys.executable, "-c", "open('out.txt','w').write('hi'); print('wrote out.txt')"]})
    for _ in range(500):
        cur = api.STORE.get(j["id"])
        if cur and cur["state"] in api._js.TERMINAL:
            break
        time.sleep(0.02)
    cur = api.STORE.get(j["id"])
    assert cur["state"] == "done", cur.get("error")
    wd = Path(cur["workdir"])
    # the scratch dir is under the registry's own tree (WORK_ROOT), not REPO/tmp
    assert api.STORE.path.parent.resolve() in wd.resolve().parents, \
        "workdir must be under the jobs tree"
    assert wd == api.STORE.work_root / cur["id"]
    # the child wrote its relative file INTO the scratch dir (cwd == workdir)
    assert (wd / "out.txt").read_text() == "hi"
    assert (wd / "run.log").exists(), "the job log lives in the scratch dir"


def test_command_job_is_killed_at_its_wall_clock_deadline(tmp_path):
    api = _api_mod(tmp_path / "to")
    t0 = time.monotonic()
    j = api.submit("eval", "sleeper", meta={
        "command": [sys.executable, "-c", "import time; time.sleep(60)"],
        "timeout_secs": 1})
    for _ in range(600):
        cur = api.STORE.get(j["id"])
        if cur and cur["state"] in api._js.TERMINAL:
            break
        time.sleep(0.02)
    cur = api.STORE.get(j["id"])
    assert cur["state"] == "failed" and "timeout" in cur["error"].lower()
    assert time.monotonic() - t0 < 10, "must terminate near the 1s deadline, not run 60s"


def test_resource_limits_resolve_defaults_meta_and_env_ceiling(tmp_path, monkeypatch):
    api = _api_mod(tmp_path / "rl")
    # per-kind default
    d = api._resolve_limits({"kind": "eval", "meta": {}})
    assert d["cpu_secs"] == 900 and d["mem_bytes"] == 4 * api.GB
    # meta tightens
    m = api._resolve_limits({"kind": "eval", "meta": {"limits": {"cpu_secs": 30}}})
    assert m["cpu_secs"] == 30
    # env ceiling clamps DOWN (a job can't loosen past it)
    monkeypatch.setenv("SOVEREIGN_OS_JOBS_MAX_CPU_SECS", "10")
    c = api._resolve_limits({"kind": "eval", "meta": {"limits": {"cpu_secs": 999}}})
    assert c["cpu_secs"] == 10, "env ceiling must clamp the per-job cap down"


def test_resource_limit_is_enforced_on_the_child(tmp_path):
    """A memory cap actually applies in the child (RLIMIT_AS trips a MemoryError),
    proving the preexec rlimits reach the subprocess."""
    if getattr(__import__("resource", fromlist=["x"]), "RLIMIT_AS", None) is None:
        return  # non-POSIX; skip
    api = _api_mod(tmp_path / "rlim")
    # 64 MiB address-space cap; the child tries to grab ~512 MiB → dies non-zero.
    j = api.submit("eval", "hog", meta={
        "command": [sys.executable, "-c", "b = bytearray(512*1024*1024); print(len(b))"],
        "limits": {"mem_bytes": 64 * 1024 * 1024}})
    for _ in range(600):
        cur = api.STORE.get(j["id"])
        if cur and cur["state"] in api._js.TERMINAL:
            break
        time.sleep(0.02)
    cur = api.STORE.get(j["id"])
    assert cur["state"] == "failed", "a job exceeding its memory cap must fail, not succeed"


def test_resume_resumes_idempotent_from_checkpoint_and_fails_command_kinds(tmp_path):
    """resume_orphans re-runs a crashed idempotent job from its checkpoint (attempt
    bumped) but fails a side-effecting command kind loudly."""
    api = _api_mod(tmp_path / "rr")
    # seed two crashed (state=running) jobs directly in the runtime's own store
    d = api.STORE.create("demo", "crashed", meta={"steps": 3, "delay": 0.01})
    api.STORE.update(d["id"], state="running", progress=66, checkpoint={"step": 2})
    c = api.STORE.create("eval", "cmd", meta={"command": ["true"]})
    api.STORE.update(c["id"], state="running")

    api.resume_orphans()
    for _ in range(400):
        dd = api.STORE.get(d["id"])
        if dd and dd["state"] in api._js.TERMINAL:
            break
        time.sleep(0.02)
    dd = api.STORE.get(d["id"])
    cc = api.STORE.get(c["id"])
    assert dd["state"] == "done" and dd["attempt"] == 2 and "resumed" in dd["output"]
    assert cc["state"] == "failed" and "non-resumable" in cc["error"]


def test_resume_gives_up_after_the_attempt_cap(tmp_path):
    api = _api_mod(tmp_path / "cap")
    d = api.STORE.create("demo", "flaky", meta={"steps": 1}, max_attempts=2)
    api.STORE.update(d["id"], state="running", attempt=2)  # already at the cap
    api.resume_orphans()
    time.sleep(0.1)
    cur = api.STORE.get(d["id"])
    assert cur["state"] == "failed" and "max attempts" in cur["error"]


def test_prune_removes_the_job_scratch_dir(tmp_path):
    js = _store_mod()
    s = js.JobStore(tmp_path / "pr" / "registry.json")
    j = s.create("demo", "leaves-a-dir")
    wd = s.workdir(j["id"])
    (wd / "run.log").write_text("noise")
    assert wd.exists()
    s.update(j["id"], state="done")
    for i in range(3):
        x = s.create("demo", f"x{i}")
        s.update(x["id"], state="done")
    s.prune(keep=1)
    assert not wd.exists(), "a pruned job's scratch dir must be removed"
