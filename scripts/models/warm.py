#!/usr/bin/env python3
"""scripts/models/warm.py — the D-03 KV-warm actuation (SDD-049 Stage 3, minimal).

Warm a running tier's model: GET the vLLM OpenAI server's /v1/models to discover
the served model, then POST a tiny /v1/completions (max_tokens:1) to load weights
+ prime the KV cache. Non-privileged (loopback HTTP, no root/mutation). DRY-RUN
when SOVEREIGN_OS_DRY_RUN=1; otherwise it warms (the exec daemon's
SOVEREIGN_OS_ACTION_EXEC_LIVE gate governs whether the cockpit runs it at all).
Graceful when the server is down. logic|oracle only (the GPU tiers with a KV
cache). Richer profile/dtype-aware warm is Stage 4.

stdlib-only. Exit: 0 ok/dry-run · 1 warm error (server down / non-200) · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

_HOST = os.environ.get("SOVEREIGN_OS_INFERENCE_HOST", "127.0.0.1")
# role → tier listen port (LOGIC_PORT 8082 / ORACLE_PORT 8083 per the start scripts).
_ROLE_PORT = {
    "logic": int(os.environ.get("LOGIC_PORT", "8082")),
    "oracle": int(os.environ.get("ORACLE_PORT", "8083")),
}


def _get_json(url: str, timeout: float = 3.0) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def _post_json(url: str, body: dict, timeout: float = 30.0) -> tuple[int, Any]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[-200:]}


def warm(role: str, *, confirm: bool = False) -> dict[str, Any]:
    if role not in _ROLE_PORT:
        return {"ok": False, "code": 2, "error": f"unknown role {role!r} (use {sorted(_ROLE_PORT)})"}
    port = _ROLE_PORT[role]
    base = f"http://{_HOST}:{port}"
    dry = os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1"
    plan = {"role": role, "server": base,
            "would_run": [f"GET {base}/v1/models", f"POST {base}/v1/completions (max_tokens:1)"]}
    if dry:
        return {"ok": True, "code": 200, "verb": "warm", "role": role, "dry_run": True,
                "plan": plan, "note": "DRY-RUN (SOVEREIGN_OS_DRY_RUN=1) — a live warm probes "
                "the tier's vLLM server and sends a 1-token prime request"}
    # discover the served model, then prime it
    try:
        models = _get_json(f"{base}/v1/models")
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {"ok": False, "code": 1, "verb": "warm", "role": role,
                "error": f"tier server unreachable at {base} ({e}) — is the {role} tier up?"}
    served = None
    try:
        served = (models.get("data") or [{}])[0].get("id")
    except (AttributeError, IndexError):
        served = None
    if not served:
        return {"ok": False, "code": 1, "verb": "warm", "role": role,
                "error": f"no served model at {base}/v1/models"}
    status, body = _post_json(f"{base}/v1/completions",
                              {"model": served, "prompt": "warm", "max_tokens": 1})
    ok = status == 200
    return {"ok": ok, "code": 200 if ok else 1, "verb": "warm", "role": role,
            "server": base, "model": served,
            "warmed": ok, "http_status": status,
            "error": None if ok else f"prime request returned {status}: {body.get('error', '')[:120]}"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="D-03 KV warm (SDD-049)")
    ap.add_argument("role", choices=sorted(_ROLE_PORT))
    ap.add_argument("--confirm", action="store_true")  # accepted for symmetry
    args = ap.parse_args(argv)
    r = warm(args.role, confirm=args.confirm)
    print(json.dumps(r, indent=2))
    return 0 if r.get("ok") else int(r.get("code", 1))


if __name__ == "__main__":
    sys.exit(main())
