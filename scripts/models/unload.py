#!/usr/bin/env python3
"""scripts/models/unload.py — the D-03 model-UNLOAD actuation (SDD-049 Stage 2).

Manual unload = stop the role's Trinity tier unit + clear its entry from
/run/sovereign-os/model-state.json. (`--idle-for` auto-unload is Stage 4.)
DRY-RUN unless --confirm AND SOVEREIGN_OS_DRY_RUN unset; the exec daemon adds
operator-key + type-to-confirm. logic|oracle only (the GPU tiers).

stdlib-only (+ model-health.py MODEL_STATE_PATH). Exit: 0 ok/dry-run · 1 error ·
2 usage.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_MH_PATH = Path(__file__).resolve().parents[1] / "inference" / "model-health.py"
_spec = importlib.util.spec_from_file_location("_model_health_reader_u", _MH_PATH)
_mh = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_mh)  # type: ignore[union-attr]
MODEL_STATE_PATH = _mh.MODEL_STATE_PATH

# role → (tier, systemd unit). GPU tiers only (Q-049-B).
_ROLE_TIER = {"logic": ("logic", "sovereign-logic-engine"),
              "oracle": ("oracle", "sovereign-oracle-core")}


def _clear_state(role: str) -> None:
    try:
        try:
            state = json.loads(MODEL_STATE_PATH.read_text())
            if not isinstance(state, dict):
                return
        except (OSError, ValueError):
            return
        loaded = state.get("loaded")
        if isinstance(loaded, dict) and role in loaded:
            loaded.pop(role, None)
            state["loaded"] = loaded
            state["updated_ts"] = datetime.now(tz=timezone.utc).isoformat()
            fd, tmp = tempfile.mkstemp(dir=str(MODEL_STATE_PATH.parent), prefix=".ms-", suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(state, fh, indent=2)
            os.replace(tmp, MODEL_STATE_PATH)
    except OSError:
        pass


def unload(role: str, *, confirm: bool = False) -> dict[str, Any]:
    if role not in _ROLE_TIER:
        return {"ok": False, "code": 2, "error": f"unknown role {role!r} (use {sorted(_ROLE_TIER)})"}
    tier, unit = _ROLE_TIER[role]
    dry = (not confirm) or os.environ.get("SOVEREIGN_OS_DRY_RUN") == "1"
    plan = {"role": role, "tier": tier, "unit": unit,
            "would_run": ["sovereign-osctl", "inference", "stop", tier]}
    if dry:
        why = "no --confirm" if not confirm else "SOVEREIGN_OS_DRY_RUN=1"
        return {"ok": True, "code": 200, "verb": "unload", "role": role, "dry_run": True,
                "plan": plan, "note": f"DRY-RUN ({why}) — a live unload stops {unit} + clears "
                "model-state.json[loaded][{role}]; operator-key + type-to-confirm gated"}
    r = subprocess.run(["sovereign-osctl", "inference", "stop", tier],
                       capture_output=True, text=True)
    _clear_state(role)
    return {"ok": r.returncode == 0, "code": 200 if r.returncode == 0 else 1, "verb": "unload",
            "role": role, "stopped": tier, "stop_rc": r.returncode,
            "stop_err": (r.stderr or "").strip()[-200:] or None}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="D-03 model unload (SDD-049)")
    ap.add_argument("role", choices=sorted(_ROLE_TIER))
    ap.add_argument("--confirm", action="store_true")
    args = ap.parse_args(argv)
    r = unload(args.role, confirm=args.confirm)
    print(json.dumps(r, indent=2))
    return 0 if r.get("ok") else int(r.get("code", 1))


if __name__ == "__main__":
    sys.exit(main())
