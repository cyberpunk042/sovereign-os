#!/usr/bin/env python3
"""scripts/science/science-download.py — SDD-302 science-tools download + verify job.

The operator-facing surface (`scripts/science/science.py`, the science-api daemon,
the osctl bridge) is stdlib-only and shells out to THIS file. A download is a
**background job**: a large `hf` pull or `git clone` can take minutes, far beyond
the exec-rail's 30 s window, so `start <tool-id>` spawns a DETACHED worker
(start_new_session) that streams progress into a state file and exits immediately
(spawn-and-return — well under the rail). The panel reads progress from
`/science.json`'s `download_jobs` (assembled from the state dir) and polls on its
5 s refresh.

Catalog-only, no user-provided paths or commands (the `download-job.py` precedent):
the tool's `install` + `detect` specs drive everything. Ids are validated against a
strict token. Jobs are **user-level** — pip `--user` / `hf download` into the HF hub
cache / `git clone` into a user dir — so no root is required and no sudoers entry is
needed.

State file: `SOVEREIGN_OS_SCIENCE_DOWNLOADS` (default
~/.local/state/sovereign-os/science-downloads) / <tool-id>.json, written atomically
(tmp + replace). One file per tool. Fields (SDD-302 state contract):
    {tool_id, status, method, pid, bytes_done, bytes_total, dest, error, updated_at}
status ∈ queued | preflight | downloading | verifying | complete | failed | interrupted

A job whose recorded PID is dead is surfaced as `interrupted` (a restart must not
leave a permanent spinner) — the `download-job.py readiness()` rule. A bare
directory is NEVER "ready" (SB-077): readiness/verify require the method's usability
check to pass, not just that a path exists.

Verify ("test the download") is a first-class, standalone, re-checkable action
(`--verify <id>`): it re-runs the method's check (a canonical import where one is
declared, else artifact/weight presence) and returns the SDD-302 verify contract
{tool_id, method, state, checks:[{check, ok, detail}], ok}. Detection failures report
`unknown`, never a fake `installed`.

CLI:
  science-download.py start <tool-id>            spawn-and-return the background job
  science-download.py --worker <tool-id>         the detached worker (not operator-facing)
  science-download.py --verify <tool-id>         verify-only (no download) → verify JSON
  science-download.py status [--json]            all jobs (newest-activity order)
  science-download.py state <tool-id> [--json]   one job's state

Exit codes: 0 clean / accepted; 1 worker-domain error; 2 usage / unknown tool.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_FILE = REPO_ROOT / "config" / "science-tools.yaml"

# State root — USER-LOCAL (science downloads are user-level; NOT /var/lib/sovereign-os,
# which the root-owned model-download precedent uses because it writes to /mnt/vault).
STATE_ENV = "SOVEREIGN_OS_SCIENCE_DOWNLOADS"
DEFAULT_STATE_DIR = Path("~/.local/state/sovereign-os/science-downloads")

# github clone destination (user dir; env-overridable for tests / operator layout).
GIT_DIR_ENV = "SOVEREIGN_OS_SCIENCE_GIT_DIR"
DEFAULT_GIT_DIR = Path("~/.local/share/sovereign-os/science")

# HF hub cache root — where `hf download`/snapshot_download default and where
# science.py detect_tool() looks (models--org--name). Resolved at call time.
HF_CACHE_ENV = "HF_HOME"
DEFAULT_HF_CACHE = Path("~/.cache/huggingface")

# In-progress statuses that mean "a download is already running — don't double-start."
IN_PROGRESS = ("queued", "preflight", "downloading", "verifying")

SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}")


# ── catalog + state ──────────────────────────────────────────────────────────

def load_catalog() -> dict[str, Any]:
    try:
        import yaml
    except ImportError:
        return {"error": "python3-yaml not installed", "tools": []}
    try:
        with CATALOG_FILE.open() as f:
            return (yaml.safe_load(f) or {}).get("catalog", {}) or {"tools": []}
    except OSError as exc:
        return {"error": str(exc), "tools": []}


def load_tool(tool_id: str) -> dict[str, Any]:
    """Load one cataloged tool by id. Raises ValueError on an unknown/invalid id
    (catalog-only — no user-supplied tool specs)."""
    if not SAFE_ID.fullmatch(tool_id or "") or ".." in (tool_id or ""):
        raise ValueError(f"invalid science tool id: {tool_id!r}")
    cat = load_catalog()
    if cat.get("error"):
        raise ValueError(cat["error"])
    for t in cat.get("tools", []) or []:
        if t.get("id") == tool_id:
            return t
    raise ValueError(f"unknown science tool id: {tool_id!r} (see `sovereign-osctl science list`)")


def state_dir() -> Path:
    env = os.environ.get(STATE_ENV, "").strip()
    return Path(env).expanduser() if env else DEFAULT_STATE_DIR.expanduser()


def _state_path(tool_id: str) -> Path:
    return state_dir() / f"{tool_id}.json"


def write_state(tool_id: str, value: dict[str, Any]) -> None:
    value = dict(value)
    value["updated_at"] = time.time()
    value["tool_id"] = tool_id
    d = state_dir()
    d.mkdir(parents=True, exist_ok=True)
    tmp = _state_path(tool_id).with_suffix(".json.tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n")
    tmp.replace(_state_path(tool_id))


def read_state(tool_id: str) -> dict[str, Any]:
    try:
        return json.loads(_state_path(tool_id).read_text())
    except (OSError, ValueError):
        return {}


def _pid_alive(pid: int) -> bool:
    try:
        if pid <= 0:
            return False
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # alive but owned by another uid


def read_jobs() -> dict[str, dict[str, Any]]:
    """All jobs keyed by tool_id; a job whose PID is dead and that was in-progress
    is surfaced as `interrupted` (the download-job.py rule). Read-only."""
    out: dict[str, dict[str, Any]] = {}
    d = state_dir()
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.json")):
        if p.name.endswith(".tmp"):
            continue
        try:
            st = json.loads(p.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(st, dict):
            continue
        if st.get("status") in IN_PROGRESS and not _pid_alive(int(st.get("pid") or 0)):
            st = dict(st, status="interrupted")
        out[p.stem] = st
    return out


def dest_for(tool: dict[str, Any]) -> str:
    method = (tool.get("install") or {}).get("method")
    ref = (tool.get("install") or {}).get("ref", "")
    if method == "hf":
        return str(_hf_hub_root() / f"models--{ref.replace('/', '--')}")
    if method == "github":
        return str(git_dir() / tool["id"])
    if method == "checkout":
        return str(Path(ref).expanduser()) if ref else ""
    if method == "pip":
        return f"pip:{ref}"
    return ""


def git_dir() -> Path:
    env = os.environ.get(GIT_DIR_ENV, "").strip()
    return Path(env).expanduser() if env else DEFAULT_GIT_DIR.expanduser()


def _hf_hub_root() -> Path:
    env = os.environ.get(HF_CACHE_ENV, "").strip()
    base = Path(env).expanduser() if env else DEFAULT_HF_CACHE.expanduser()
    return base / "hub"


# ── verification (the "test the download" core) ──────────────────────────────

def _import_ok(module: str) -> tuple[bool, str]:
    """Return (ok, detail). ok=False with a clear detail when the module can't be
    imported; ok is None-ish via the detail string when it cannot be determined."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", module or ""):
        return False, f"invalid module name: {module!r}"
    try:
        r = subprocess.run([sys.executable, "-c", f"import {module}"],
                           capture_output=True, text=True, timeout=60, check=False)
        if r.returncode == 0:
            return True, f"import {module} → ok"
        tail = (r.stderr.strip().splitlines() or ["import failed"])[-1][:160]
        return False, f"import {module} → {tail}"
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"import {module} → {type(exc).__name__}"


def _dir_bytes(path: Path) -> int:
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    except OSError:
        pass
    return total


def _artifact_present(tool: dict[str, Any]) -> tuple[bool, str]:
    """Method-specific presence check (a bare directory alone is never enough)."""
    method = (tool.get("install") or {}).get("method")
    det = tool.get("detect") or {}
    ref = det.get("ref") or (tool.get("install") or {}).get("ref", "")
    wf = (tool.get("verify") or {}).get("weight_file")
    if method == "hf":
        hub = _hf_hub_root() / f"models--{ref.replace('/', '--')}"
        snaps = hub / "snapshots"
        if snaps.is_dir() and any(snaps.iterdir()):
            return True, f"snapshot present at {snaps} ({_gb(_dir_bytes(hub))} GB)"
        return False, f"no snapshot for {ref} in the HF hub cache"
    if method == "github" or method == "checkout":
        # Presence is satisfied at EITHER the user-level clone dest OR the catalog's
        # declared detect.ref (an operator-placed /opt/… checkout). The download
        # clones to the user git_dir (no root); the ref covers manual placement.
        cands = [git_dir() / tool["id"]]
        ref = det.get("ref") or (tool.get("install") or {}).get("ref", "")
        if not str(ref).startswith(("http", "git@", "git:")):
            cands.append(Path(ref).expanduser())
        base = next((c for c in cands if c.is_dir()), None)
        if base is None:
            where = str(cands[0]) + (f" (or declared {cands[-1]})" if len(cands) > 1 else "")
            return False, f"checkout not present at {where}"
        if wf:
            wp = base / wf
            if wp.is_file():
                return True, f"checkout + weight {wf} present at {base} ({_gb(wp.stat().st_size)} GB)"
            return False, f"code present at {base} but weight {wf} not fetched (separate step — see catalog gotchas)"
        return True, f"checkout present at {base}"
    if method in ("pip", "import"):
        # the package IS the artifact; presence == importable (checked by the import check)
        return True, "pip package (presence = importability, checked below)"
    return False, f"no presence check for method {method!r}"


def _gb(n: float) -> float:
    return round(n / 1024**3, 2)


def verify_tool(tool: dict[str, Any]) -> dict[str, Any]:
    """The SDD-302 verify contract. `ok` (state `installed`) is true only when the
    artifact is present AND every usability check the catalog declares passes. A
    present-but-incomplete artifact (missing separate weight / failed import) is
    `artifacts-present`, never `installed` (SB-077). Detection failures report
    `unknown`.

    Sub-checks (each {check, ok, detail}): always `artifact-present`; a separate
    `weight <name>` check when a single declared weight_file is missing (the code
    clone is present but the weight is a documented separate fetch); and `import`
    when a module is declared. `state` = installed when present AND every declared
    sub-check passes; artifacts-present when present but a sub-check fails;
    downloadable when the artifact is absent."""
    method = (tool.get("install") or {}).get("method")
    det = tool.get("detect") or {}
    vfy = tool.get("verify") or {}
    present, present_detail = _artifact_present(tool)

    # Which module, if any, proves usability? The deliberate `verify.import_module`
    # wins; `detect.import_module` is the fallback; import/pip methods fall back to
    # the detect.ref (the module the package installs). A bare git clone is NOT
    # pip-importable, so github/checkout tools only carry an import check when the
    # code genuinely installs import-in-place (deliberate, per-tool).
    module = vfy.get("import_module") or det.get("import_module")
    if method in ("import", "pip") and not module:
        module = det.get("ref")

    checks: list[dict[str, Any]] = [{"check": "artifact-present", "ok": present, "detail": present_detail}]
    wf = vfy.get("weight_file")
    weights_ok = True
    # github/checkout: code cloned but the declared separate weight is missing →
    # present=False from _artifact_present, but the CODE is present. Re-treat as
    # present (so we don't report `downloadable`) and add a distinct weight sub-check.
    if present is False and wf and "weight" in present_detail:
        present = True
        weights_ok = False
        checks[0] = {"check": "artifact-present (code)", "ok": True, "detail": "code present"}
        checks.append({"check": f"weight {wf}", "ok": False, "detail": "not fetched (separate step — see catalog gotchas)"})

    state = "unknown"
    if not present:
        state = "downloadable"
    elif module:
        ok, detail = _import_ok(module)
        checks.append({"check": "import", "ok": bool(ok), "detail": detail})
        state = "installed" if (ok and weights_ok) else "artifacts-present"
    else:
        state = "installed" if weights_ok else "artifacts-present"
    return {
        "tool_id": tool.get("id"),
        "method": method,
        "state": state,
        "checks": checks,
        "ok": state == "installed",
    }


# ── the download worker (detached) ───────────────────────────────────────────

def _run(cmd: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    merged = dict(os.environ)
    if env:
        merged.update(env)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=3600, check=False, env=merged)


def _pip_install(ref: str, state: dict[str, Any]) -> None:
    cmd = [sys.executable, "-m", "pip", "install", "--user", ref]
    r = _run(cmd)
    if r.returncode != 0:
        raise RuntimeError(f"pip install {ref} failed: {r.stderr.strip().splitlines()[-1][:160] if r.stderr.strip() else 'see log'}")


def _hf_download(ref: str, state: dict[str, Any]) -> None:
    from huggingface_hub import HfApi, snapshot_download  # heavy import — worker only
    auth = _hf_token_env()
    info = HfApi(token=auth.get("HF_TOKEN")).model_info(ref, files_metadata=True)
    total = sum(s.size for s in info.siblings if s.size)
    state["bytes_total"] = total
    hub_repo = _hf_hub_root() / f"models--{ref.replace('/', '--')}"
    def progress():
        while state.get("status") == "downloading":
            state["bytes_done"] = min(total, _dir_bytes(hub_repo))
            write_state(state["tool_id"], state)
            time.sleep(2)
    import threading
    mon = threading.Thread(target=progress, daemon=True)
    mon.start()
    try:
        snapshot_download(repo_id=ref, token=auth.get("HF_TOKEN"), max_workers=2)
    finally:
        time.sleep(3)  # let the last progress write land
        state["bytes_done"] = min(total, _dir_bytes(hub_repo))
    mon.join(timeout=5)


def _git_clone(ref: str, tool: dict[str, Any], state: dict[str, Any]) -> None:
    dest = git_dir() / tool["id"]
    if not (dest / ".git").is_dir():
        dest.parent.mkdir(parents=True, exist_ok=True)
        r = _run(["git", "clone", "--depth", "1", str(ref), str(dest)])
        if r.returncode != 0:
            raise RuntimeError(f"git clone {ref} failed: {r.stderr.strip().splitlines()[-1][:160] if r.stderr.strip() else 'see log'}")
    # A declared in-repo weight file must exist for the artifact to be complete.
    wf = (tool.get("verify") or {}).get("weight_file")
    if wf and not (dest / wf).is_file():
        # Weights that require a separate fetch (Google storage / install script) are
        # NOT auto-fetched here (Stage-N); surface it honestly, don't fake success.
        raise RuntimeError(f"weight file {wf} not in the clone — this tool needs a separate weight fetch (see catalog gotchas)")


def _hf_token_env() -> dict[str, str]:
    """Reuse scripts/models/hf-auth.py for the HF token (the download-job.py path).
    Fails soft: no token file → empty env (public repos still work)."""
    try:
        import runpy
        res = runpy.run_path(str(REPO_ROOT / "scripts" / "models" / "hf-auth.py"))
        fn = res.get("token_environment")
        return fn(os.environ) if callable(fn) else dict(os.environ)
    except Exception:
        return {}


def worker(tool_id: str) -> int:
    tool = load_tool(tool_id)
    method = (tool.get("install") or {}).get("method")
    state: dict[str, Any] = {
        "tool_id": tool_id,
        "status": "queued",
        "method": method,
        "pid": os.getpid(),
        "bytes_done": 0,
        "bytes_total": 0,
        "dest": dest_for(tool),
        "error": None,
    }
    try:
        if method == "checkout":
            state["status"] = "verifying"
            write_state(tool_id, state)
            # verify-only; the download is a no-op
        else:
            state["status"] = "preflight"
            write_state(tool_id, state)
            if method == "pip":
                state["status"] = "downloading"
                write_state(tool_id, state)
                _pip_install((tool.get("install") or {}).get("ref", ""), state)
            elif method == "hf":
                state["status"] = "downloading"
                write_state(tool_id, state)
                _hf_download((tool.get("install") or {}).get("ref", ""), state)
            elif method == "github":
                state["status"] = "downloading"
                write_state(tool_id, state)
                _git_clone((tool.get("install") or {}).get("ref", ""), tool, state)
            else:
                raise RuntimeError(f"install.method {method!r} is not downloadable")
            state["status"] = "verifying"
            write_state(tool_id, state)
            verify = verify_tool(tool)
            if not verify["ok"]:
                raise RuntimeError("download finished but verify failed: " +
                                   "; ".join(c["detail"] for c in verify["checks"] if not c["ok"]))
        state.update(status="complete", error=None)
        write_state(tool_id, state)
        return 0
    except Exception as exc:
        # No raw traceback into the state file (diagnostics can carry URLs/tokens).
        state.update(status="failed", error=f"{type(exc).__name__}: {str(exc)[:300]}")
        write_state(tool_id, state)
        return 1


# ── operator-facing entry points ─────────────────────────────────────────────

def start(tool_id: str) -> dict[str, Any]:
    """Spawn-and-return: validate, refuse a double-start, write queued, Popen the
    detached worker, record its pid, and exit immediately (well under the rail)."""
    tool = load_tool(tool_id)
    existing = read_state(tool_id)
    if existing.get("status") in IN_PROGRESS and _pid_alive(int(existing.get("pid") or 0)):
        return {"status": "already-running", "tool_id": tool_id, "job": existing}
    state: dict[str, Any] = {
        "tool_id": tool_id,
        "status": "queued",
        "method": (tool.get("install") or {}).get("method"),
        "pid": 0,
        "bytes_done": 0,
        "bytes_total": 0,
        "dest": dest_for(tool),
        "error": None,
    }
    write_state(tool_id, state)
    argv = [sys.executable, str(Path(__file__).resolve()), "--worker", tool_id]
    log = state_dir() / f"{tool_id}.log"
    state_dir().mkdir(parents=True, exist_ok=True)
    with log.open("ab") as lf:
        proc = subprocess.Popen(argv, stdout=lf, stderr=lf,
                                stdin=subprocess.DEVNULL, start_new_session=True)
    state["pid"] = proc.pid
    state["status"] = "queued"
    write_state(tool_id, state)
    return {"status": "accepted", "tool_id": tool_id, "pid": proc.pid, "job": state}


def cmd_verify(tool_id: str, json_out: bool) -> int:
    tool = load_tool(tool_id)
    res = verify_tool(tool)
    if json_out:
        print(json.dumps(res, indent=2))
    else:
        mark = "✓" if res["ok"] else "✗"
        print(f"── SDD-302 science · verify {tool_id} → {res['state']} {mark} ──")
        for c in res["checks"]:
            print(f"    [{'ok' if c['ok'] else 'FAIL'}] {c['check']}: {c['detail']}")
    return 0 if res["ok"] else 1


def cmd_status(json_out: bool) -> int:
    jobs = read_jobs()
    if json_out:
        print(json.dumps({"jobs": jobs}, indent=2))
        return 0
    if not jobs:
        print("── SDD-302 science · downloads ──\n  (no download jobs recorded)")
        return 0
    print("── SDD-302 science · downloads ──")
    for tid in sorted(jobs, key=lambda k: jobs[k].get("updated_at", 0), reverse=True):
        j = jobs[tid]
        prog = ""
        if j.get("bytes_total"):
            prog = f"  {_gb(j.get('bytes_done', 0))}/{_gb(j['bytes_total'])} GB"
        err = f"  err={j['error']}" if j.get("error") else ""
        print(f"  {j.get('status', '?'):<13} {tid}{prog}{err}")
    return 0


def cmd_state(tool_id: str, json_out: bool) -> int:
    st = read_state(tool_id)
    if not st:
        if json_out:
            print(json.dumps({"tool_id": tool_id, "status": "none"}))
        else:
            print(f"no download job recorded for {tool_id}")
        return 0
    if json_out:
        print(json.dumps(st, indent=2))
    else:
        print(f"  {tool_id}: {st.get('status')}"
              + (f"  {_gb(st.get('bytes_done', 0))}/{_gb(st.get('bytes_total', 0))} GB" if st.get("bytes_total") else "")
              + (f"  err={st['error']}" if st.get("error") else ""))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="SDD-302 science-tools download + verify job.")
    p.add_argument("action", nargs="?", choices=["start", "status", "state"])
    p.add_argument("tool_id", nargs="?")
    p.add_argument("--worker", metavar="TOOL_ID", default=None, help=argparse.SUPPRESS)
    p.add_argument("--verify", metavar="TOOL_ID", help=argparse.SUPPRESS)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    if args.verify:
        try:
            return cmd_verify(args.verify, args.json)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    if args.worker:
        return worker(args.worker)

    if args.action == "status":
        return cmd_status(args.json)
    if args.action == "state":
        if not args.tool_id:
            print("usage: state <tool-id>", file=sys.stderr)
            return 2
        return cmd_state(args.tool_id, args.json)
    if args.action == "start" or (args.action is None and args.tool_id):
        if not args.tool_id:
            print("usage: start <tool-id>", file=sys.stderr)
            return 2
        try:
            res = start(args.tool_id)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if res["status"] == "already-running":
                print(f"  {args.tool_id}: already running (status={res['job'].get('status')})")
            else:
                print(f"  {args.tool_id}: download accepted (pid {res['pid']}) — "
                      f"track with `sovereign-osctl science download {args.tool_id} --status`")
        return 0
    p.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
