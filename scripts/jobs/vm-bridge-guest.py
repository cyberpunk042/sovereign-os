#!/usr/bin/env python3
"""
scripts/jobs/vm-bridge-guest.py — the RTX-4090-VM → host Background Tasks bridge.

Runs INSIDE the VFIO passthrough VM that owns the RTX 4090 (and 3090). The host
cockpit can't see the guest's GPU jobs directly — the card is passed through — so
this agent probes the guest's own `nvidia-smi`, builds vm-job entries, and POSTs
them to the HOST's jobs-api (`POST /jobs/ingest`) so they appear in the Code
Console's Background Tasks pane alongside host jobs. Stdlib only.

Honest gating (SB-077): this agent + the ingest protocol SHIP and are testable
(`--once --dry-run` prints the payload without a network). What is DEPLOYMENT-
specific is the guest→host CHANNEL — the VM must be able to reach the host's
jobs-api, e.g. via the libvirt NAT gateway IP or a virtio-vsock proxy. Set that
address in SOVEREIGN_JOBS_HOST; until then this agent is inert (it just probes).

ENVIRONMENT:
  SOVEREIGN_JOBS_HOST   host jobs-api reachable from the guest (e.g. 192.168.122.1:8142)
  SOVEREIGN_VM_DEVICE   device label for the entries (default rtx-4090-vm)
  SOVEREIGN_VM_POLL     seconds between reports (default 5)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

HOST = os.environ.get("SOVEREIGN_JOBS_HOST", "")
DEVICE = os.environ.get("SOVEREIGN_VM_DEVICE", "rtx-4090-vm")
POLL = max(1, int(os.environ.get("SOVEREIGN_VM_POLL", "5")))


def probe_gpu_jobs() -> list[dict]:
    """One vm-job per running CUDA process on the guest's GPU. Empty when there's
    no nvidia-smi (degrade-safe) or nothing running."""
    if shutil.which("nvidia-smi") is None:
        return []
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    jobs = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3 or not parts[0]:
            continue
        pid, name, mem = parts[0], parts[1], parts[2]
        jobs.append({
            "id": f"vm-{pid}",
            "kind": "vm-job",
            "title": f"{name} (pid {pid})",
            "device": DEVICE,
            "state": "running",
            "progress": 0,  # a real trainer can override via its own status file
            "output": f"{mem} MiB VRAM",
            "meta": {"pid": pid},
        })
    return jobs


def report(jobs: list[dict]) -> tuple[int, int]:
    """POST each entry to the host jobs-api /jobs/ingest. Returns (ok, fail)."""
    if not HOST:
        return 0, 0
    ok = fail = 0
    for job in jobs:
        data = json.dumps(job).encode()
        req = urllib.request.Request(f"http://{HOST}/jobs/ingest", data=data,
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=8):  # noqa: S310
                ok += 1
        except (urllib.error.URLError, OSError):
            fail += 1
    return ok, fail


def main(argv: list[str]) -> int:
    once = "--once" in argv
    dry = "--dry-run" in argv
    while True:
        jobs = probe_gpu_jobs()
        if dry:
            print(json.dumps({"host": HOST or "(unset — inert)", "device": DEVICE, "jobs": jobs}, indent=2))
        else:
            ok, fail = report(jobs)
            if not HOST:
                print(f"[vm-bridge] {len(jobs)} gpu job(s); SOVEREIGN_JOBS_HOST unset — not reporting", file=sys.stderr)
            else:
                print(f"[vm-bridge] reported {ok} ok / {fail} fail to {HOST}", file=sys.stderr)
        if once:
            return 0
        time.sleep(POLL)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
