#!/usr/bin/env python3
"""scripts/models/warm.py — the D-03 KV-warm actuation (SDD-049 Stage 4).

Warm a running tier's model: GET the vLLM OpenAI server's /v1/models to discover
the served model, then POST a tiny /v1/completions (max_tokens:1) to load weights
+ prime the KV cache. Non-privileged (loopback HTTP, no root/mutation). DRY-RUN
when SOVEREIGN_OS_DRY_RUN=1; otherwise it warms (the exec daemon's
SOVEREIGN_OS_ACTION_EXEC_LIVE gate governs whether the cockpit runs it at all).
Graceful when the server is down. logic|oracle only (the GPU tiers with a KV
cache).

Stage 4 — profile / dtype aware: the warm now reads the tier's loaded record from
/run/sovereign-os/model-state.json (the id + precision load.py published) and the
active runtime mode from /run/sovereign-os/active-runtime-mode, so it reports the
precision it is warming and the profile it is warming under. It also cross-checks
the served model against the loaded record and flags a drift (state_consistent:
false) when the tier is actually serving a different model than state claims —
the operationally useful part: a warm that silently primes the wrong model is a
trap. Both source paths are env-overridable (SOVEREIGN_OS_MODEL_STATE /
SOVEREIGN_OS_RUNTIME_MODE) so the awareness is testable.

stdlib-only. Exit: 0 ok/dry-run · 1 warm error (server down / non-200) · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_HOST = os.environ.get("SOVEREIGN_OS_INFERENCE_HOST", "127.0.0.1")
# role → tier listen port (LOGIC_PORT 8082 / ORACLE_PORT 8083 per the start scripts).
_ROLE_PORT = {
    "logic": int(os.environ.get("LOGIC_PORT", "8082")),
    "oracle": int(os.environ.get("ORACLE_PORT", "8083")),
}
# The runtime records the warm reads to become precision/profile aware (both
# env-overridable — the same knobs model-health.py + the runtime-mode control use).
MODEL_STATE_PATH = Path(os.environ.get("SOVEREIGN_OS_MODEL_STATE",
                                       "/run/sovereign-os/model-state.json"))
RUNTIME_MODE_PATH = Path(os.environ.get("SOVEREIGN_OS_RUNTIME_MODE",
                                        "/run/sovereign-os/active-runtime-mode"))


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


def _context(role: str) -> dict[str, Any]:
    """The loaded record for `role` — the id + precision load.py published to
    model-state.json — plus the active runtime mode. Best-effort: any missing /
    malformed source degrades to None, never raises (a warm must survive a fresh
    box with no state files)."""
    ctx: dict[str, Any] = {"state_model": None, "precision": None, "runtime_mode": None}
    try:
        state = json.loads(MODEL_STATE_PATH.read_text(encoding="utf-8"))
        entry = ((state.get("loaded") or {}).get(role) or [{}])[0]
        ctx["state_model"] = entry.get("id")
        ctx["precision"] = entry.get("precision")
    except (OSError, ValueError, AttributeError, IndexError, TypeError):
        pass
    try:
        ctx["runtime_mode"] = (RUNTIME_MODE_PATH.read_text(encoding="utf-8").strip() or None)
    except OSError:
        pass
    return ctx


def warm(role: str, *, confirm: bool = False) -> dict[str, Any]:
    if role not in _ROLE_PORT:
        return {"ok": False, "code": 2, "error": f"unknown role {role!r} (use {sorted(_ROLE_PORT)})"}
    port = _ROLE_PORT[role]
    base = f"http://{_HOST}:{port}"
    ctx = _context(role)
    dry = os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1"
    plan = {"role": role, "server": base,
            "precision": ctx["precision"], "runtime_mode": ctx["runtime_mode"],
            "would_run": [f"GET {base}/v1/models", f"POST {base}/v1/completions (max_tokens:1)"]}
    if dry:
        return {"ok": True, "code": 200, "verb": "warm", "role": role, "dry_run": True,
                "precision": ctx["precision"], "runtime_mode": ctx["runtime_mode"],
                "state_model": ctx["state_model"], "plan": plan,
                "note": "DRY-RUN (SOVEREIGN_OS_DRY_RUN=1) — a live warm probes the tier's "
                "vLLM server, sends a 1-token prime, and cross-checks the served model "
                "against the loaded record (precision + profile aware, SDD-049 Stage 4)"}
    # discover the served model, then prime it
    try:
        models = _get_json(f"{base}/v1/models")
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {"ok": False, "code": 1, "verb": "warm", "role": role,
                "precision": ctx["precision"], "runtime_mode": ctx["runtime_mode"],
                "error": f"tier server unreachable at {base} ({e}) — is the {role} tier up?"}
    served = None
    try:
        served = (models.get("data") or [{}])[0].get("id")
    except (AttributeError, IndexError):
        served = None
    if not served:
        return {"ok": False, "code": 1, "verb": "warm", "role": role,
                "precision": ctx["precision"], "runtime_mode": ctx["runtime_mode"],
                "error": f"no served model at {base}/v1/models"}
    # dtype/profile-aware: does the tier actually serve what state says is loaded?
    state_consistent = ctx["state_model"] is None or ctx["state_model"] == served
    warning = None if state_consistent else (
        f"tier serves {served!r} but model-state records {ctx['state_model']!r} loaded "
        f"for {role} — reload the tier or the warm primes the wrong model")
    status, body = _post_json(f"{base}/v1/completions",
                              {"model": served, "prompt": "warm", "max_tokens": 1})
    ok = status == 200
    return {"ok": ok, "code": 200 if ok else 1, "verb": "warm", "role": role,
            "server": base, "model": served, "state_model": ctx["state_model"],
            "precision": ctx["precision"], "runtime_mode": ctx["runtime_mode"],
            "state_consistent": state_consistent, "warning": warning,
            "warmed": ok, "http_status": status,
            "error": None if ok else f"prime request returned {status}: {body.get('error', '')[:120]}"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="D-03 KV warm (SDD-049 Stage 4 — profile/dtype aware)")
    ap.add_argument("role", choices=sorted(_ROLE_PORT))
    ap.add_argument("--confirm", action="store_true")  # accepted for symmetry
    args = ap.parse_args(argv)
    r = warm(args.role, confirm=args.confirm)
    print(json.dumps(r, indent=2))
    return 0 if r.get("ok") else int(r.get("code", 1))


if __name__ == "__main__":
    sys.exit(main())
