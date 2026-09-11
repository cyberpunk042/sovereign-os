#!/usr/bin/env python3
"""Start one reconciled llama.cpp profile allocation.

This intentionally has no profile-selection logic.  The reconciler writes one
root-owned JSON record per role, then systemd owns restart/crash recovery just
as it does for the standard vLLM tiers.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: profile-llama-server.py <role>", file=sys.stderr)
        return 2
    record = Path("/etc/sovereign-os/profile-runtime") / f"{sys.argv[1]}.json"
    try:
        cfg = json.loads(record.read_text(encoding="utf-8"))
        model = Path(cfg["model_path"])
        gpu = str(cfg["cuda_visible_devices"])
        port = int(cfg["port"])
        ctx = int(cfg["context_tokens"])
        server_path = str(cfg.get("server_path") or "llama-server")
        served_model_name = str(cfg.get("served_model_name") or "")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"invalid profile allocation {record}: {exc}", file=sys.stderr)
        return 2
    if not model.is_file():
        print(f"profile model missing: {model}", file=sys.stderr)
        return 3
    server = server_path if Path(server_path).is_file() else shutil.which(server_path)
    if not server:
        print("llama-server is required for this profile", file=sys.stderr)
        return 4
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = gpu
    # The profile's cuda:N identifiers follow nvidia-smi / PCI-bus order. CUDA's
    # default "fastest first" ordering can otherwise map the same N to another
    # card on this mixed Blackwell + Ada workstation.
    env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    server_dir = str(Path(server).resolve().parent)
    cuda_lib = "/opt/sovereign-os/venv/vllm/lib/python3.14/site-packages/nvidia/cu13/lib"
    env["LD_LIBRARY_PATH"] = ":".join(
        [server_dir, cuda_lib, env.get("LD_LIBRARY_PATH", "")]
    )
    argv = [server, "-m", str(model), "--host", "127.0.0.1", "--port", str(port),
            "-ngl", "999", "--ctx-size", str(ctx)]
    # llama.cpp calls this an API alias (unlike vLLM's --served-model-name).
    # gatewayd relays the selected OpenClaw model id unchanged, so serving the
    # GGUF filename here would make a healthy backend reject every proxy call.
    if served_model_name:
        argv.extend(["--alias", served_model_name])
    os.execvpe(server, argv, env)
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
