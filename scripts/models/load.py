#!/usr/bin/env python3
"""scripts/models/load.py — the D-03 model-LOAD actuation (SDD-049 Stage 1).

There is no per-model hot-swap: a Trinity tier serves ONE model bound at
systemd-unit start via a `<TIER>_MODEL` env. So `models load <id>` means:
resolve the catalog id → (tier, on-disk path), VRAM-fit gate, write the tier's
highest-precedence env drop-in (/etc/sovereign-os/inference-<tier>.env), restart
the tier unit, and publish /run/sovereign-os/model-state.json.

Safety (the sanctioned R10274 pattern):
  - DRY-RUN unless --confirm AND SOVEREIGN_OS_DRY_RUN is unset; the cockpit path
    adds operator-key presence + type-to-confirm via the exec daemon.
  - VRAM-fit REFUSE by default (vram_gib_min > live free VRAM on the role's GPU),
    --force is the only (logged) bypass.
  - id→path is RESOLVED (catalog → hf_repo_id → verified on-disk dir), never
    string-munged; a load never fabricates a path.
  - the env drop-in + model-state.json are written atomically (os.replace); the
    tier restart is the only host mutation.

stdlib-only (+ imports the model-health.py reader helpers). Exit: 0 ok/dry-run ·
1 write/restart error · 2 usage/unknown-id/unresolved-path/won't-fit.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── import the D-03 reader helpers (hyphenated filename → importlib) ─────────
_MH_PATH = Path(__file__).resolve().parents[1] / "inference" / "model-health.py"
_spec = importlib.util.spec_from_file_location("_model_health_reader", _MH_PATH)
_mh = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mh)  # type: ignore[union-attr]

MODEL_STATE_PATH = _mh.MODEL_STATE_PATH
TIER_TO_ROLE = _mh.TIER_TO_ROLE

MODELS_DIR = Path(os.environ.get("SOVEREIGN_OS_MODELS_DIR", "/mnt/vault/models"))
# loadable tiers → (systemd unit, env var, env drop-in file)
_TIERS = {
    "pulse": ("sovereign-pulse", "PULSE_MODEL", "inference-pulse.env"),
    "logic": ("sovereign-logic-engine", "LOGIC_MODEL", "inference-logic-engine.env"),
    "oracle": ("sovereign-oracle-core", "ORACLE_MODEL", "inference-oracle-core.env"),
}
_ENV_DIR = Path(os.environ.get("SOVEREIGN_OS_INFERENCE_ENV_DIR", "/etc/sovereign-os"))
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@=-]*")


def _catalog_entry(model_id: str) -> dict[str, Any] | None:
    for m in _mh.load_catalog():
        if str(m.get("id")) == model_id:
            return m
    return None


def resolve_path(entry: dict[str, Any]) -> tuple[str | None, list[str]]:
    """id → on-disk path via hf_repo_id (org/name) → try org__name / basename /
    id under MODELS_DIR; verify is_dir(). Returns (path or None, tried[])."""
    hf = str(entry.get("hf_repo_id") or "")
    cands: list[str] = []
    if "/" in hf:
        org, name = hf.split("/", 1)
        cands.append(str(MODELS_DIR / f"{org}__{name}"))
        cands.append(str(MODELS_DIR / name))
    elif hf:
        cands.append(str(MODELS_DIR / hf))
    cands.append(str(MODELS_DIR / str(entry.get("id"))))
    for c in cands:
        if Path(c).is_dir():
            return c, cands
    return None, cands


def _free_vram_gb(role: str) -> float | None:
    """Live free VRAM (GB) on the role's GPU: oracle→Blackwell, logic→the other.
    None when GPU telemetry is unavailable (cannot verify)."""
    gpus = _mh.collect_gpus()
    if not gpus:
        return None
    if role == "oracle":
        cands = [g for g in gpus if g.get("is_blackwell")] or gpus
    else:  # logic (and helpers riding logic)
        cands = [g for g in gpus if not g.get("is_blackwell")] or gpus
    g = cands[0]
    tot, used = g.get("vram_total_gb"), g.get("vram_used_gb")
    if tot is None or used is None:
        return None
    return round(tot - used, 1)


def _write_env_drop_in(env_file: Path, var: str, path: str) -> None:
    """Merge <var>=<path> into the tier's EnvironmentFile atomically (preserve
    other lines; replace the var if present)."""
    lines: list[str] = []
    if env_file.is_file():
        lines = [ln for ln in env_file.read_text().splitlines() if not ln.startswith(f"{var}=")]
    lines.append(f"{var}={path}")
    env_file.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(env_file.parent), prefix=".inf-", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(tmp, env_file)


def _publish_state(role: str, model_id: str, precision: str, path: str) -> None:
    """Atomically update /run/sovereign-os/model-state.json's `loaded[role]` in
    the shape model-health.py reads. Best-effort; never raises."""
    try:
        try:
            state = json.loads(MODEL_STATE_PATH.read_text())
            if not isinstance(state, dict):
                state = {}
        except (OSError, ValueError):
            state = {}
        loaded = state.get("loaded")
        if not isinstance(loaded, dict):
            loaded = {}
        loaded[role] = [{"id": model_id, "precision": precision, "path": path}]
        state["loaded"] = loaded
        state["updated_ts"] = datetime.now(tz=timezone.utc).isoformat()
        MODEL_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(MODEL_STATE_PATH.parent), prefix=".ms-", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
        os.replace(tmp, MODEL_STATE_PATH)
    except OSError:
        pass


def load(model_id: str, *, force: bool = False, confirm: bool = False) -> dict[str, Any]:
    if not _SAFE_ID.fullmatch(model_id):
        return {"ok": False, "code": 2, "error": f"unsafe model id {model_id!r} (no '/'; _SAFE_VALUE)"}
    entry = _catalog_entry(model_id)
    if entry is None:
        return {"ok": False, "code": 2, "error": f"unknown model id {model_id!r} (not in catalog)"}
    tier = str(entry.get("tier"))
    if tier not in _TIERS:
        return {"ok": False, "code": 2, "id": model_id, "tier": tier,
                "error": f"tier {tier!r} is not loadable (loadable: {sorted(_TIERS)})"}
    role = TIER_TO_ROLE.get(tier, tier)
    unit, var, env_name = _TIERS[tier]
    env_file = _ENV_DIR / env_name
    path, tried = resolve_path(entry)
    precision = str(entry.get("quantization") or "unknown")
    vram_min = entry.get("vram_gib_min")
    free = _free_vram_gb(role)
    fits = None if (free is None or vram_min is None) else (float(vram_min) <= free)

    dry = (not confirm) or os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1"
    plan = {"id": model_id, "tier": tier, "role": role, "path": path, "precision": precision,
            "env_file": str(env_file), "env_var": var, "unit": unit, "tried_paths": tried,
            "vram": {"min": vram_min, "free": free, "fits": fits, "forced": bool(fits is False and force)},
            "would_run": ["sovereign-osctl", "inference", "restart", tier]}
    if dry:
        blockers = []
        if path is None:
            blockers.append(f"model not on disk (tried {tried}) — pull it first")
        if fits is False and not force:
            blockers.append(f"won't fit: needs {vram_min} GiB, {free} GiB free (use --force)")
        why = "no --confirm" if not confirm else "SOVEREIGN_OS_DRY_RUN=1"
        return {"ok": True, "code": 200, "verb": "load", "id": model_id, "dry_run": True,
                "plan": plan, "blockers": blockers,
                "note": f"DRY-RUN ({why}) — a live load writes {env_file}, restarts {unit}, "
                "publishes model-state.json; operator-key + type-to-confirm gated at the exec daemon"}

    # ── LIVE: enforce path-exists + VRAM-fit ──
    if path is None:
        return {"ok": False, "code": 2, "id": model_id, "error": "model not found on disk",
                "tried_paths": tried, "hint": f"`sovereign-osctl models pull {model_id}` first"}
    if fits is False and not force:
        return {"ok": False, "code": 2, "id": model_id, "role": role,
                "error": f"won't fit: needs {vram_min} GiB, {free} GiB free on {role} GPU "
                f"(pass --force to override)", "vram": {"min": vram_min, "free": free}}
    try:
        _write_env_drop_in(env_file, var, path)
    except OSError as e:
        return {"ok": False, "code": 1, "id": model_id, "error": f"env drop-in write failed: {e}"}
    r = subprocess.run(["sovereign-osctl", "inference", "restart", tier],
                       capture_output=True, text=True)
    _publish_state(role, model_id, precision, path)
    return {"ok": r.returncode == 0, "code": 200 if r.returncode == 0 else 1, "verb": "load",
            "id": model_id, "role": role, "tier": tier, "path": path, "restarted": tier,
            "restart_rc": r.returncode, "restart_err": (r.stderr or "").strip()[-200:] or None}


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="D-03 model load (SDD-049)")
    ap.add_argument("id")
    ap.add_argument("--force", action="store_true", help="bypass the VRAM-fit refusal (logged)")
    ap.add_argument("--confirm", action="store_true", help="apply (default is dry-run)")
    args = ap.parse_args(argv)
    r = load(args.id, force=args.force, confirm=args.confirm)
    _print(r)
    return 0 if r.get("ok") else int(r.get("code", 1))


if __name__ == "__main__":
    sys.exit(main())
