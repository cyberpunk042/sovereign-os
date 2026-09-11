#!/usr/bin/env python3
"""Atomically converge the Qwythos three-card profile before advertising it.

The previous switch wrote Qwythos labels into OpenClaw while the two old vLLM
units continued to serve their former models.  This reconciler owns the three
llama.cpp residents, waits for their health endpoints, and only then commits
the active-profile marker and refreshes OpenClaw's advertised labels.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PROFILE_ID = sys.argv[1] if len(sys.argv) == 2 else "qwythos-three-card"
if PROFILE_ID not in {"qwythos-three-card", "qwythos-dual-memory"}:
    raise SystemExit(f"unsupported Qwythos reconciler profile: {PROFILE_ID}")
PROFILE = ROOT / "profiles/orchestration" / f"{PROFILE_ID}.yaml"
STATE_DIR = Path("/etc/sovereign-os")
RUNTIME_DIR = STATE_DIR / "profile-runtime"
LLAMA_LAUNCHER = ROOT / "scripts/inference/profile-llama-server.py"
CUDA_LLAMA_SERVER = Path(os.environ.get(
    "SOVEREIGN_OS_QWYTHOS_LLAMA_SERVER",
    "/home/jfortin/.local/lib/sovereign-os/llama-cuda/llama-server",
))
GATEWAY_QWYTHOS_DROPIN = Path("/etc/systemd/system/sovereign-gatewayd.service.d/90-qwythos-profile.conf")
QWYTHOS_ROUTE_ENV = STATE_DIR / "qwythos-gpu-route.env"
GATEWAY_BUILD = ROOT / "target" / "release" / "sovereign-gatewayd"
GATEWAY_INSTALL = Path("/usr/local/bin/sovereign-gatewayd")
ROUTER_LAUNCHER_SOURCE = ROOT / "scripts" / "iac" / "assets" / "start-router-tier.sh"
ROUTER_LAUNCHER_INSTALL = Path("/usr/local/lib/sovereign-os/start-router-tier.sh")


def atomic(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".new-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(contents)
        os.replace(tmp, path)
    except BaseException:
        try: os.unlink(tmp)
        except OSError: pass
        raise


def run(*args: str) -> None:
    subprocess.run(args, check=True, text=True)


def model_path(model_id: str) -> Path:
    base = Path(os.environ.get("SOVEREIGN_OS_MODELS_DIR", "/mnt/vault/models")) / model_id
    # Qwythos ships an auxiliary MTP GGUF beside the main checkpoint.  The
    # primary model must be loaded with `-m`; the MTP file is only useful when
    # deliberately configured as a speculative draft model.
    primary_stem = model_id.removesuffix("-GGUF")
    primary = base / f"{primary_stem}-Q4_K_M.gguf"
    if not primary.is_file():
        raise RuntimeError(f"Qwythos Q4_K_M GGUF missing under {base}; download it before applying")
    return primary


def cuda_server() -> Path | None:
    """Return only a llama-server binary that enumerates real CUDA devices."""
    candidates = [CUDA_LLAMA_SERVER]
    fallback = shutil.which("llama-server")
    if fallback:
        candidates.append(Path(fallback))
    for server in candidates:
        if not server.is_file():
            continue
        probe_env = os.environ.copy()
        probe_env["LD_LIBRARY_PATH"] = ":".join([
            str(server.parent),
            "/opt/sovereign-os/venv/vllm/lib/python3.14/site-packages/nvidia/cu13/lib",
            probe_env.get("LD_LIBRARY_PATH", ""),
        ])
        probe_env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
        probe = subprocess.run([str(server), "--list-devices"], text=True,
                               env=probe_env,
                               capture_output=True, check=False)
        if any(line.strip() and not line.startswith("Available devices:")
               for line in probe.stdout.splitlines()):
            return server
    return None


def healthy(port: int, timeout: float = 180.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(2)
    return False


def unit_dropin(role: str) -> str:
    # Clear the packaged ExecStart/ExecStop before installing this profile's
    # llama.cpp launcher.  The normal profiles clear this drop-in on switch.
    return f"""# Managed by Qwythos profile reconciler; do not edit.\n[Service]\nExecStart=\nExecStart=/usr/bin/python3 {LLAMA_LAUNCHER} {role}\nExecStop=\nTimeoutStartSec=300\n"""


def worker_unit() -> str:
    return f"""[Unit]\nDescription=sovereign-os Qwythos profile worker (RTX 4090)\nAfter=network-online.target\nWants=network-online.target\n[Service]\nType=simple\nExecStart=/usr/bin/python3 {LLAMA_LAUNCHER} worker\nRestart=on-failure\nRestartSec=5\nTimeoutStartSec=300\nNoNewPrivileges=true\nProtectSystem=strict\nReadOnlyPaths=-/mnt/vault/models\n[Install]\nWantedBy=multi-user.target\n"""


def gateway_dropin() -> str:
    """Allow the profile-owned 4090 endpoint through gatewayd's SSRF guard."""
    return """# Managed by Qwythos profile reconciler; do not edit.\n[Service]\nEnvironment=SOVEREIGN_GATEWAY_PROXY_ALLOW=127.0.0.1:8082,127.0.0.1:8083,127.0.0.1:8084,127.0.0.1:8085,127.0.0.1:8086\n"""


def route_env() -> str:
    """Register all three routes after gatewayd's in-memory registry resets."""
    if PROFILE_ID == "qwythos-dual-memory":
        return """GPU_ROUTE_GATEWAY=http://127.0.0.1:8787
GPU_ROUTE_TIERS=gpu-logic@127.0.0.1:8082@logic@28,gpu-oracle@127.0.0.1:8083@oracle@80
GPU_ROUTE_DEFAULT=gpu-logic
GPU_ROUTE_BACKGROUND=gpu-oracle
GPU_ROUTE_SET_DEFAULT=0
GPU_ROUTE_SET_BACKGROUND=0
GPU_ROUTE_GATEWAY_TRIES=30
GPU_ROUTE_TIER_TRIES=30
GPU_ROUTE_SLEEP=2
"""
    return """GPU_ROUTE_GATEWAY=http://127.0.0.1:8787\nGPU_ROUTE_TIERS=gpu-logic@127.0.0.1:8082@logic@28,gpu-oracle@127.0.0.1:8083@oracle@80,gpu-qwythos-worker@127.0.0.1:8086@worker@18\nGPU_ROUTE_DEFAULT=gpu-logic\nGPU_ROUTE_BACKGROUND=gpu-oracle\nGPU_ROUTE_SET_DEFAULT=0\nGPU_ROUTE_SET_BACKGROUND=0\nGPU_ROUTE_GATEWAY_TRIES=30\nGPU_ROUTE_TIER_TRIES=30\nGPU_ROUTE_SLEEP=2\n"""


def install_built_gateway() -> None:
    """Atomically install the gateway build required by this profile transaction."""
    if not GATEWAY_BUILD.is_file():
        raise RuntimeError(f"gateway build missing: {GATEWAY_BUILD}; build it before applying Qwythos")
    fd, tmp = tempfile.mkstemp(dir=GATEWAY_INSTALL.parent, prefix=".sovereign-gatewayd-")
    try:
        with os.fdopen(fd, "wb") as out, GATEWAY_BUILD.open("rb") as source:
            shutil.copyfileobj(source, out)
        os.chmod(tmp, 0o755)
        os.replace(tmp, GATEWAY_INSTALL)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def install_router_launcher() -> None:
    # The live-linked /usr/local/lib tree can be mounted read-only. Once the
    # launcher exists it is immutable runtime infrastructure, not a profile
    # artifact; reusing it keeps an otherwise healthy dual-profile switch from
    # failing after the 4090 services are already running.
    if ROUTER_LAUNCHER_INSTALL.is_file() and os.access(ROUTER_LAUNCHER_INSTALL, os.X_OK):
        return
    if not ROUTER_LAUNCHER_SOURCE.is_file():
        raise RuntimeError(f"router launcher missing: {ROUTER_LAUNCHER_SOURCE}")
    ROUTER_LAUNCHER_INSTALL.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=ROUTER_LAUNCHER_INSTALL.parent, prefix=".router-launcher-")
    try:
        with os.fdopen(fd, "wb") as out, ROUTER_LAUNCHER_SOURCE.open("rb") as source:
            shutil.copyfileobj(source, out)
        os.chmod(tmp, 0o755)
        os.replace(tmp, ROUTER_LAUNCHER_INSTALL)
    except BaseException:
        try: os.unlink(tmp)
        except OSError: pass
        raise


def main() -> int:
    if os.geteuid() != 0:
        print("reconciler must run as root", file=sys.stderr); return 2
    server = cuda_server()
    if server is None:
        print("llama-server has no CUDA device support; Qwythos was not applied", file=sys.stderr)
        return 3
    data = yaml.safe_load(PROFILE.read_text()) or {}
    allocs = (data.get("orchestration_profile") or {}).get("allocations") or []
    roles = {a.get("tier"): a for a in allocs}
    expected_tiers = {"logic", "oracle", "router"} if PROFILE_ID == "qwythos-three-card" else {"logic", "oracle", "embed", "rerank"}
    if set(roles) != expected_tiers:
        print("invalid Qwythos allocation topology", file=sys.stderr); return 4
    named = {"logic": roles["logic"], "oracle": roles["oracle"]}
    if PROFILE_ID == "qwythos-three-card":
        named["worker"] = roles["router"]
    served_names = {"logic": "gpu-logic", "oracle": "gpu-oracle", "worker": "gpu-qwythos-worker"}
    records = {}
    try:
        for role, allocation in named.items():
            if allocation.get("engine") != "llama.cpp":
                raise RuntimeError(f"{role} is not a llama.cpp allocation")
            cuda = str(allocation["target_hardware"]).removeprefix("cuda:")
            records[role] = {"model_path": str(model_path(allocation["model"])),
                             "server_path": str(server),
                             "cuda_visible_devices": cuda, "port": int(allocation["port"]),
                             "served_model_name": served_names[role],
                             "catalog_id": str(allocation["model"]),
                             "context_tokens": int((data["orchestration_profile"].get("context_budget") or {}).get("initial_tokens", {}).get(allocation["target_hardware"], 16384))}
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        print(f"Qwythos was not applied: {exc}", file=sys.stderr); return 5
    for role, record in records.items():
        atomic(RUNTIME_DIR / f"{role}.json", json.dumps(record) + "\n")
    atomic(Path("/etc/systemd/system/sovereign-logic-engine.service.d/90-qwythos-profile.conf"), unit_dropin("logic"))
    atomic(Path("/etc/systemd/system/sovereign-oracle-core.service.d/90-qwythos-profile.conf"), unit_dropin("oracle"))
    if PROFILE_ID == "qwythos-three-card":
        atomic(Path("/etc/systemd/system/sovereign-qwythos-worker.service"), worker_unit())
    atomic(GATEWAY_QWYTHOS_DROPIN, gateway_dropin())
    atomic(QWYTHOS_ROUTE_ENV, route_env())
    try:
        run("systemctl", "daemon-reload")
        run("systemctl", "restart", "sovereign-logic-engine.service")
        run("systemctl", "restart", "sovereign-oracle-core.service")
        # `enable --now` does not replace an already-running worker.  A profile
        # apply is a declared model replacement, so restart it just like Logic
        # and Oracle; otherwise an old auxiliary/draft model can linger on 8086.
        if PROFILE_ID == "qwythos-three-card":
            run("systemctl", "enable", "sovereign-qwythos-worker.service")
            run("systemctl", "restart", "sovereign-qwythos-worker.service")
        else:
            install_router_launcher()
            run("systemctl", "disable", "--now", "sovereign-qwythos-worker.service")
            run("systemctl", "restart", "sovereign-router-embed.service")
            run("systemctl", "restart", "sovereign-router-rerank.service")
    except subprocess.CalledProcessError as exc:
        print(f"Qwythos launch failed before profile commit: {exc}", file=sys.stderr); return 6
    health_ports = [int(r["port"]) for r in records.values()]
    if PROFILE_ID == "qwythos-dual-memory":
        health_ports.extend([8084, 8085])
    if not all(healthy(port) for port in health_ports):
        print("Qwythos health checks failed; profile was not committed or advertised", file=sys.stderr); return 7
    try:
        # gatewayd's registry is intentionally in-memory, so restart then
        # repopulate all three routes as one profile-apply operation.
        install_built_gateway()
        run("systemctl", "restart", "sovereign-gatewayd.service")
        env = os.environ.copy()
        env["GPU_ROUTE_ENV"] = str(QWYTHOS_ROUTE_ENV)
        # The installed asset is deliberately non-executable in source trees;
        # invoke its declared shell rather than depending on a checkout mode.
        subprocess.run(["/usr/bin/env", "bash", str(ROOT / "scripts/iac/assets/gpu-route-apply.sh")],
                       check=True, text=True, env=env)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Qwythos gateway route registration failed before profile commit: {exc}", file=sys.stderr); return 8
    # This is a non-secret state witness consumed by the unprivileged cockpit
    # control rail for its postcondition. A root-only marker made a successful
    # profile switch appear as HTTP 500 because the rail could not verify it.
    active_marker = STATE_DIR / "active-runtime-profile"
    atomic(active_marker, PROFILE_ID + "\n")
    os.chmod(active_marker, 0o644)
    sync = ROOT / "scripts/inference/sync-openclaw-models.py"
    result = subprocess.run([sys.executable, str(sync), "--profile", PROFILE_ID], text=True)
    if result.returncode:
        print("Qwythos is serving, but OpenClaw sync failed", file=sys.stderr); return 9
    try:
        # The timer eventually refreshes this state, but profile application is
        # the moment operators need a truthful cockpit. Publish it now so the
        # Qwythos worker joins the same attested state as Logic and Oracle.
        run("systemctl", "start", "sovereign-model-state.service")
    except subprocess.CalledProcessError as exc:
        print(f"Qwythos is serving, but runtime attestation publish failed: {exc}", file=sys.stderr); return 10
    print(f"Qwythos profile {PROFILE_ID} is serving and committed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
