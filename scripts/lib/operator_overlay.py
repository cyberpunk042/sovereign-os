"""scripts/lib/operator_overlay.py — R283 (E5.M11).

Operator-named (§1a verbatim):
  "endless flexibility and fine-tuning and adapting possible"

Shared helper for layering operator TOML overlays on top of a
script's compiled-in defaults. Doctrine:

  1. Each script declares a defaults dict in-source.
  2. Operator drops a TOML file at /etc/sovereign-os/<script-name>.toml
     (env override: SOVEREIGN_OS_OVERLAY_<SCRIPT_NAME>).
  3. The helper deep-merges TOML on top of defaults — operator keys
     win; un-set operator keys fall through to defaults.
  4. The resolved config carries `_source` metadata + `_overlay_keys`
     (which keys came from TOML vs defaults) so JSON output is
     auditable.

This is the FLEXIBILITY-AT-SCALE pattern from §1a: every script
becomes operator-tunable without per-script flag explosion. Future
rounds retrofit existing scripts to consume the helper.

Usage:
    from operator_overlay import load_with_overlay

    DEFAULTS = {"threshold_pct": 25, "max_attempts": 3}
    cfg = load_with_overlay("my-script", DEFAULTS)
    # cfg["threshold_pct"] == 25 unless operator overrode
    # cfg["_source"] is "/etc/sovereign-os/my-script.toml" or "(defaults)"
    # cfg["_overlay_keys"] is the set of keys overridden by TOML

Env var precedence (highest wins):
    SOVEREIGN_OS_OVERLAY_<SCRIPT_NAME>  (script-specific override)
    /etc/sovereign-os/<script-name>.toml  (system-level)
    config/<script-name>.toml.example     (in-repo fallback for dev)
    DEFAULTS                              (compiled-in)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ETC = Path("/etc/sovereign-os")


def _env_var_name(script_name: str) -> str:
    """`ram-advisor` → `SOVEREIGN_OS_OVERLAY_RAM_ADVISOR`."""
    safe = script_name.upper().replace("-", "_").replace(".", "_")
    return f"SOVEREIGN_OS_OVERLAY_{safe}"


def resolve_overlay_path(script_name: str, explicit: Path | None = None) -> Path | None:
    """Find the operator overlay file for this script.

    Precedence:
      1. `explicit` arg (operator passed --config)
      2. `SOVEREIGN_OS_OVERLAY_<SCRIPT>` env var
      3. `/etc/sovereign-os/<script>.toml`
      4. `config/<script>.toml.example` (dev fallback)
      5. None (operator didn't supply one)
    """
    if explicit is not None:
        return explicit if explicit.exists() else None
    env_var = _env_var_name(script_name)
    env_val = os.environ.get(env_var)
    if env_val:
        p = Path(env_val)
        return p if p.exists() else None
    system_path = DEFAULT_ETC / f"{script_name}.toml"
    if system_path.exists():
        return system_path
    dev_path = REPO_ROOT / "config" / f"{script_name}.toml.example"
    if dev_path.exists():
        return dev_path
    return None


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Operator-key-wins recursive merge. Lists are REPLACED (not
    concatenated) so operator can explicitly clear a default list."""
    out: dict[str, Any] = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def collect_overlay_keys(overlay: dict[str, Any], prefix: str = "") -> set[str]:
    """Dotted-path keys present in the overlay (for audit surface)."""
    keys: set[str] = set()
    for k, v in overlay.items():
        path = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys |= collect_overlay_keys(v, path)
        else:
            keys.add(path)
    return keys


def load_with_overlay(
    script_name: str,
    defaults: dict[str, Any],
    explicit_path: Path | None = None,
) -> dict[str, Any]:
    """Layer the operator TOML overlay on top of `defaults`.

    Returns the merged config with two metadata fields:
      _source         the overlay path used, or "(defaults)" when none
      _overlay_keys   list of dotted-path keys overridden by TOML

    Defaults pass through 1:1 when no overlay exists — so scripts can
    safely call this even on operator-clean hosts.
    """
    path = resolve_overlay_path(script_name, explicit_path)
    if path is None:
        result = dict(defaults)
        result["_source"] = "(defaults — no overlay file)"
        result["_overlay_keys"] = []
        return result
    try:
        with path.open("rb") as fh:
            overlay = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as e:
        result = dict(defaults)
        result["_source"] = str(path)
        result["_overlay_keys"] = []
        result["_parse_error"] = str(e)
        return result
    merged = deep_merge(defaults, overlay)
    merged["_source"] = str(path)
    merged["_overlay_keys"] = sorted(collect_overlay_keys(overlay))
    return merged
