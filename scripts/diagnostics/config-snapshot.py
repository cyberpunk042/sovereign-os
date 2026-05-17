#!/usr/bin/env python3
"""scripts/diagnostics/config-snapshot.py — R332 (E2.M23).

Operator-pull "preserve my host's full customization for backup or
migration to a new host." Captures complete operator-customized
state into ONE portable JSON.

Distinct from R322 state-snapshot (which probes RUNTIME state).
R332 captures CONFIG state — the operator-pinned posture that
survives reboots + can be replayed onto a fresh host:

  - every operator-overlay file body (R325 surface)
  - active maintenance windows declaration (R323)
  - audit-log tail (R327; last N rows of mutations)
  - hardware inventory (R317; operator-stable component declaration)
  - helper-library version manifest (R330; SDD-032 doctrine)

CLI:
  config-snapshot.py capture [--overlay-dir D] [--audit-tail N]
                              [--config P] [--json|--human]
                              capture full config snapshot

  config-snapshot.py audit   [--config P] [--json|--human]
                              size summary of what WOULD be captured

Output is intentionally JSON-only (operator pipes to a file +
ships off-host). --human mode prints a brief summary instead of
the full snapshot.

Operator-overlay (R283/SDD-030):
/etc/sovereign-os/config-snapshot.toml
  - overlay_dir            /etc/sovereign-os
  - audit_tail_count       100
  - include_inventory      true
  - include_audit          true
  - include_windows         true

Exit codes:
  0  captured
  2  usage error
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
try:
    from operator_overlay import load_with_overlay  # type: ignore
except Exception:  # pragma: no cover
    load_with_overlay = None

try:
    import apply_audit  # type: ignore
except Exception:  # pragma: no cover
    apply_audit = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R332"
SDD_VECTOR = "E2.M23"


DEFAULTS = {
    "overlay_dir": "/etc/sovereign-os",
    "audit_tail_count": 100,
    "include_inventory": True,
    "include_audit": True,
    "include_windows": True,
}


def load_state(overlay_path: Path | None) -> tuple[dict, dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    cfg = dict(DEFAULTS)
    if load_with_overlay is not None:
        loaded = load_with_overlay("config-snapshot", DEFAULTS,
                                    explicit_path=overlay_path)
        for k in DEFAULTS:
            if k in loaded:
                cfg[k] = loaded[k]
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
    return cfg, meta


def _hash_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def capture_overlays(overlay_dir: Path) -> list[dict[str, Any]]:
    """Capture every *.toml file in overlay_dir verbatim."""
    out: list[dict[str, Any]] = []
    if not overlay_dir.is_dir():
        return out
    for path in sorted(overlay_dir.glob("*.toml")):
        try:
            body = path.read_bytes()
            entry = {
                "overlay_file": path.name,
                "overlay_path": str(path),
                "size_bytes": len(body),
                "sha256": _hash_bytes(body),
                "body_b64": base64.b64encode(body).decode("ascii"),
            }
            out.append(entry)
        except OSError:
            continue
    return out


def _run_json(rel: str, args: list[str], timeout: int = 8) -> Any | None:
    bin_path = REPO_ROOT / rel
    if not bin_path.is_file():
        return None
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), *args],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def capture_inventory() -> Any | None:
    return _run_json("scripts/hardware/inventory-catalog.py",
                      ["list", "--json"])


def capture_windows() -> Any | None:
    return _run_json("scripts/lifecycle/maintenance-window.py",
                      ["list", "--json"])


def capture_audit_tail(n: int) -> list[dict[str, Any]]:
    if apply_audit is None:
        return []
    return apply_audit.query(limit=n)


def capture_helper_library_manifest() -> dict[str, Any]:
    """Per-helper-module: size + sha256 — operator audit of which
    versions were active when snapshot was taken."""
    lib_dir = REPO_ROOT / "scripts" / "lib"
    manifest = []
    if lib_dir.is_dir():
        for f in sorted(lib_dir.glob("*.py")):
            try:
                body = f.read_bytes()
                manifest.append({
                    "module": f.name,
                    "size_bytes": len(body),
                    "sha256": _hash_bytes(body),
                })
            except OSError:
                continue
    return {
        "lib_dir": str(lib_dir),
        "modules": manifest,
        "module_count": len(manifest),
    }


def build_capture(cfg: dict) -> dict[str, Any]:
    now = time.time()
    overlay_dir = Path(cfg["overlay_dir"])
    overlays = capture_overlays(overlay_dir)
    doc: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "captured_at_epoch": now,
        "host": socket.gethostname(),
        "overlay_dir": str(overlay_dir),
        "overlays": overlays,
        "overlay_count": len(overlays),
        "helper_library": capture_helper_library_manifest(),
    }
    if cfg.get("include_inventory", True):
        doc["inventory"] = capture_inventory()
    if cfg.get("include_windows", True):
        doc["maintenance_windows"] = capture_windows()
    if cfg.get("include_audit", True):
        tail = capture_audit_tail(int(cfg["audit_tail_count"]))
        doc["audit_tail"] = tail
        doc["audit_tail_count"] = len(tail)
    return doc


def render_human(doc: dict) -> str:
    lines = [f"── R332 sovereign-os config snapshot (E2.M23) ──",
             f"  captured_at: {doc['captured_at']}",
             f"  host:        {doc['host']}",
             f"  overlay_dir: {doc['overlay_dir']}", ""]
    lines.append(f"  overlays captured: {doc['overlay_count']}")
    for o in doc.get("overlays", [])[:10]:
        lines.append(f"    {o['overlay_file']:40s}  "
                      f"{o['size_bytes']:>6d}B  sha256={o['sha256'][:12]}…")
    if len(doc.get("overlays", [])) > 10:
        lines.append(f"    ... and {len(doc['overlays']) - 10} more")
    lines.append("")
    hl = doc.get("helper_library", {})
    lines.append(f"  helper-library modules: {hl.get('module_count', 0)}")
    for m in hl.get("modules", []):
        lines.append(f"    {m['module']:30s}  {m['size_bytes']:>6d}B  "
                      f"sha256={m['sha256'][:12]}…")
    if "inventory" in doc:
        inv = doc["inventory"] or {}
        n = inv.get("total_count") if isinstance(inv, dict) else None
        lines.append("")
        lines.append(f"  inventory components: {n}")
    if "audit_tail" in doc:
        lines.append(f"  audit-log tail rows:   {doc.get('audit_tail_count', 0)}")
    if "maintenance_windows" in doc:
        mw = doc["maintenance_windows"] or {}
        wc = mw.get("total_count") if isinstance(mw, dict) else None
        lines.append(f"  maintenance windows:   {wc}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="config-snapshot.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("capture")
    pc.add_argument("--overlay-dir", type=Path)
    pc.add_argument("--audit-tail", type=int)
    pc.add_argument("--config", type=Path)
    fc = pc.add_mutually_exclusive_group()
    fc.add_argument("--json", dest="fmt", action="store_const", const="json")
    fc.add_argument("--human", dest="fmt", action="store_const", const="human")
    pc.set_defaults(fmt="json")

    pa = sub.add_parser("audit")
    pa.add_argument("--overlay-dir", type=Path)
    pa.add_argument("--config", type=Path)
    fa = pa.add_mutually_exclusive_group()
    fa.add_argument("--json", dest="fmt", action="store_const", const="json")
    fa.add_argument("--human", dest="fmt", action="store_const", const="human")
    pa.set_defaults(fmt="json")

    args = p.parse_args(argv)
    cfg, meta = load_state(args.config)
    if args.overlay_dir:
        cfg["overlay_dir"] = str(args.overlay_dir)
    if getattr(args, "audit_tail", None):
        cfg["audit_tail_count"] = args.audit_tail

    if args.cmd == "audit":
        # Lightweight: just report what WOULD be captured.
        overlay_dir = Path(cfg["overlay_dir"])
        overlay_count = 0
        overlay_bytes = 0
        if overlay_dir.is_dir():
            for f in overlay_dir.glob("*.toml"):
                overlay_count += 1
                try:
                    overlay_bytes += f.stat().st_size
                except OSError:
                    pass
        hl = capture_helper_library_manifest()
        audit_planned = (int(cfg["audit_tail_count"])
                          if cfg.get("include_audit") else 0)
        report = {
            "schema_version": SCHEMA_VERSION,
            "round": ROUND,
            "sdd_vector": SDD_VECTOR,
            "overlay_dir": str(overlay_dir),
            "overlay_count": overlay_count,
            "overlay_bytes": overlay_bytes,
            "helper_library_modules": hl["module_count"],
            "audit_tail_planned": audit_planned,
            "include_inventory": cfg.get("include_inventory", True),
            "include_windows": cfg.get("include_windows", True),
            "overlay": meta,
        }
        if args.fmt == "json":
            print(json.dumps(report, indent=2))
        else:
            print(f"── R332 config-snapshot audit (E2.M23) ──")
            print(f"  overlay_dir:           {overlay_dir}")
            print(f"  overlay count:         {overlay_count}")
            print(f"  overlay bytes (sum):   {overlay_bytes}")
            print(f"  helper-library mods:   {hl['module_count']}")
            print(f"  audit-tail planned:    {audit_planned}")
            print(f"  include_inventory:     {cfg.get('include_inventory')}")
            print(f"  include_windows:       {cfg.get('include_windows')}")
        return 0

    # capture
    doc = build_capture(cfg)
    doc["overlay"] = meta
    if args.fmt == "json":
        print(json.dumps(doc, indent=2))
    else:
        print(render_human(doc), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
