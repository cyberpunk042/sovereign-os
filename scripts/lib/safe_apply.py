"""scripts/lib/safe_apply.py — R328 (E9.M12) helper library.

Codifies the triple-gate apply pattern (R318) + maintenance-window
check (R323) + audit-write (R327) into ONE `run_apply_safe()`
function that future apply verbs import. Eliminates copy-paste of
the apply ceremony.

Match for the read-side R283 `load_with_overlay` helper.

Usage in a consumer apply verb:

  from safe_apply import run_apply_safe

  def my_write_fn():
      target_path.write_text(new_content)

  result = run_apply_safe(
      verb="my-verb apply",
      round_origin="R<NNN>",
      apply_flag=args.apply,
      confirm_flag=args.confirm_<verb>,
      env_var_name="SOVEREIGN_OS_CONFIRM_DESTROY",
      env_var_value="YES",
      what_was_written={"key": new_value, ...},
      target_path=str(target),
      write_fn=my_write_fn,
      maintenance_window=args.maintenance_window,  # optional
      force=args.force,                              # optional
  )

  # result schema (operator-stable):
  # {
  #   "gates": {"--apply": bool, "--confirm-<verb>": bool,
  #              "<env-var>=<value>": bool},
  #   "gates_satisfied": bool,
  #   "maintenance_window": str | None,
  #   "window_check": {"checked": bool, "active": bool,
  #                     "allowed": bool, "reason": str},
  #   "wrote": bool,
  #   "write_error": str | None,
  #   "rc": int,
  #   "audit_row": dict (from R327),
  # }

NEVER raises — gate failure / window violation / write failure all
return a structured result with `wrote=False` + a reason. The
consumer decides rc semantics for its CLI.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

# Locate sibling helper modules.
LIB_DIR = Path(__file__).resolve().parent
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

try:
    import apply_audit  # R327 audit helper
except Exception:  # pragma: no cover
    apply_audit = None


REPO_ROOT = Path(__file__).resolve().parents[2]
MAINTENANCE_WINDOW_SCRIPT = (
    REPO_ROOT / "scripts" / "lifecycle" / "maintenance-window.py"
)


def evaluate_triple_gate(
    apply_flag: bool,
    confirm_flag: bool,
    env_var_name: str = "SOVEREIGN_OS_CONFIRM_DESTROY",
    env_var_value: str = "YES",
    confirm_flag_label: str = "--confirm-apply",
) -> tuple[dict[str, bool], bool]:
    """Returns (per-gate dict, triple_gate_ok bool)."""
    gates = {
        "--apply": bool(apply_flag),
        confirm_flag_label: bool(confirm_flag),
        f"{env_var_name}={env_var_value}":
            os.environ.get(env_var_name) == env_var_value,
    }
    return gates, all(gates.values())


def check_maintenance_window(
    window_name: str | None,
    force: bool = False,
) -> dict[str, Any]:
    """Spawn R323 maintenance-window.py to check if window is active.

    Returns:
      {"checked": bool, "active": bool, "allowed": bool, "reason": str}

    - When window_name is None → not checked; allowed=True.
    - When force=True → not checked; allowed=True (operator override).
    - Otherwise: subprocess to R323; allowed = active.
    """
    if window_name is None:
        return {"checked": False, "active": True, "allowed": True,
                "reason": "no window required"}
    if force:
        return {"checked": False, "active": True, "allowed": True,
                "reason": "operator --force override"}
    if not MAINTENANCE_WINDOW_SCRIPT.is_file():
        return {"checked": False, "active": False, "allowed": False,
                "reason": f"R323 script not found at {MAINTENANCE_WINDOW_SCRIPT}"}
    try:
        r = subprocess.run(
            [sys.executable, str(MAINTENANCE_WINDOW_SCRIPT),
             "can-run-now", window_name, "--json"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"checked": True, "active": False, "allowed": False,
                "reason": f"window-check subprocess failed: {e}"}
    if r.returncode == 0:
        return {"checked": True, "active": True, "allowed": True,
                "reason": f"window {window_name} is active"}
    if r.returncode == 1:
        return {"checked": True, "active": False, "allowed": False,
                "reason": f"window {window_name} is outside its scheduled time"}
    if r.returncode == 2:
        return {"checked": True, "active": False, "allowed": False,
                "reason": f"window {window_name} not declared"}
    return {"checked": True, "active": False, "allowed": False,
            "reason": f"window-check unexpected rc={r.returncode}"}


def run_apply_safe(
    *,
    verb: str,
    round_origin: str,
    apply_flag: bool,
    confirm_flag: bool,
    write_fn: Callable[[], None] | None = None,
    what_was_written: dict[str, Any] | None = None,
    target_path: str | None = None,
    env_var_name: str = "SOVEREIGN_OS_CONFIRM_DESTROY",
    env_var_value: str = "YES",
    confirm_flag_label: str = "--confirm-apply",
    maintenance_window: str | None = None,
    force: bool = False,
    audit_path_override: str | None = None,
) -> dict[str, Any]:
    """Run an apply with full ceremony: triple-gate + window-check +
    audit-write + write_fn invocation. Returns a structured result.

    NEVER raises. write_fn=None is a special mode for verbs that want
    only the gate evaluation + audit without an actual write (useful
    for `apply --dry-run` paths)."""
    gates, ok = evaluate_triple_gate(
        apply_flag, confirm_flag,
        env_var_name=env_var_name,
        env_var_value=env_var_value,
        confirm_flag_label=confirm_flag_label,
    )
    window = check_maintenance_window(maintenance_window, force=force)

    wrote = False
    write_error: str | None = None
    rc = 0

    will_write = ok and window["allowed"] and write_fn is not None
    if will_write:
        try:
            write_fn()
            wrote = True
        except (OSError, RuntimeError, ValueError) as e:
            wrote = False
            write_error = str(e)
            rc = 2

    audit_row = None
    if apply_audit is not None:
        audit_row = apply_audit.record_apply(
            verb=verb,
            round_origin=round_origin,
            gates_satisfied=ok and window["allowed"],
            gates_detail={
                **gates,
                f"maintenance-window:{maintenance_window or '(none)'}":
                    bool(window["allowed"]),
            },
            what_was_written=what_was_written or {},
            target_path=target_path,
            wrote=wrote,
            rc=rc,
            audit_path_override=audit_path_override,
        )

    return {
        "gates": gates,
        "gates_satisfied": ok,
        "maintenance_window": maintenance_window,
        "window_check": window,
        "would_write": ok and window["allowed"],
        "wrote": wrote,
        "write_error": write_error,
        "rc": rc,
        "audit_row": audit_row,
    }
