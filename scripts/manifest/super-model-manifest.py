#!/usr/bin/env python3
"""scripts/manifest/super-model-manifest.py — super-model manifest core
(M060 D-19 / R10124-R10125).

The data model behind the D-19 super-model-manifest cockpit dashboard. This is
sovereign-os-NATIVE (the super-model manifest IS sovereign-os's own version +
module-version table — not a selfdef mirror). It computes the LIVE manifest
from the repo:

  - super-model version   git HEAD short SHA + commit date → sovereign-os@<date>-<sha>
  - module-version table  every backlog/milestones/M###-*.md milestone, with
                          its title (from the `# M### — ...` header) + live
                          R-row count (`^| R` rows) — 100% read from the catalog,
                          never invented.
  - editorial overlay     config/super-model-manifest.toml (operator-curated):
                          M053 11 build-phase status + per-milestone family/
                          status/tag. Milestones in the catalog but absent from
                          the manifest default to family=runtime/status=
                          catalogued so the table never goes stale.
  - counts                milestone_count · rrow total · MS007 mirror count
                          (scripts/mirror/*) · shipped-dashboard count.

Sovereignty: stdlib-only (tomllib for the editorial overlay). Absent catalog/
git/manifest → degrades gracefully (empty table / unknown version), NEVER a
crash. This is the `core` surface; `scripts/operator/super-model-api.py` serves
it, `sovereign-osctl super-model` drives it, the D-19 webapp renders it.

  super-model-manifest.py snapshot [--json]   full dashboard model
  super-model-manifest.py version  [--json]   the super-model identity block
  super-model-manifest.py milestones [--json]  the module-version table
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

_REPO_ROOT = Path(__file__).resolve().parents[2]
MILESTONES_DIR = Path(os.environ.get(
    "SOVEREIGN_OS_MILESTONES_DIR", str(_REPO_ROOT / "backlog" / "milestones")))
MANIFEST_TOML = Path(os.environ.get(
    "SOVEREIGN_OS_SUPER_MODEL_MANIFEST", str(_REPO_ROOT / "config" / "super-model-manifest.toml")))
MIRROR_DIR = _REPO_ROOT / "scripts" / "mirror"

_MS_FILE_RE = re.compile(r"^(M\d{3})-.*\.md$")
_HEADER_RE = re.compile(r"^#\s*M\d{3}\s*[—\-–]\s*(.+?)\s*$")


def _run(cmd: list[str], timeout: float = 4.0) -> str | None:
    if shutil.which(cmd[0]) is None:
        return None
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, check=False, cwd=str(_REPO_ROOT))
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def _load_manifest(path: Path = MANIFEST_TOML) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError, ValueError):
        return {}


def _parse_milestone(p: Path) -> dict[str, Any] | None:
    m = _MS_FILE_RE.match(p.name)
    if not m:
        return None
    ms = m.group(1)
    title = ""
    rrows = 0
    try:
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if not title:
                h = _HEADER_RE.match(line)
                if h:
                    title = h.group(1).strip()
            if line.startswith("| R"):
                rrows += 1
    except OSError:
        return None
    return {"ms": ms, "title": title or ms, "rrows": rrows}


def milestones(manifest: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Every M### milestone from the live catalog, enriched with the editorial
    manifest overlay (family/status/tag) where present."""
    man = manifest if manifest is not None else _load_manifest()
    overlay = man.get("milestones", {}) if isinstance(man, dict) else {}
    rows = []
    if MILESTONES_DIR.is_dir():
        for p in sorted(MILESTONES_DIR.glob("M[0-9]*.md")):
            parsed = _parse_milestone(p)
            if not parsed:
                continue
            ed = overlay.get(parsed["ms"], {}) if isinstance(overlay, dict) else {}
            rows.append({
                "ms": parsed["ms"],
                # prefer the live catalog title; fall back to editorial
                "title": parsed["title"] or ed.get("title", parsed["ms"]),
                "family": ed.get("family", "runtime"),
                "status": ed.get("status", "catalogued"),
                "rrows": parsed["rrows"],
                "tag": ed.get("tag", ""),
            })
    return rows


def _phases(manifest: dict[str, Any]) -> list[dict[str, str]]:
    raw = manifest.get("phases")
    if not isinstance(raw, list):
        return []
    out = []
    for p in raw:
        if isinstance(p, dict) and p.get("label"):
            st = p.get("status")
            out.append({"label": str(p["label"]),
                        "status": st if st in ("done", "current", "future") else "future"})
    return out


def _cross_refs(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    raw = manifest.get("cross_refs")
    if not isinstance(raw, list):
        return []
    return [{"ms": c.get("ms", "?"), "title": c.get("title", ""),
             "family": c.get("family", "runtime"), "status": c.get("status", "shipped")}
            for c in raw if isinstance(c, dict)]


def version(ms_rows: list[dict[str, Any]] | None = None,
            manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    man = manifest if manifest is not None else _load_manifest()
    rows = ms_rows if ms_rows is not None else milestones(man)
    name = ((man.get("identity") or {}).get("name") if isinstance(man, dict) else None) or "sovereign-os"
    gv = _run(["git", "log", "-1", "--format=%h %cd", "--date=short"])
    if gv:
        sha, _, date = gv.strip().partition(" ")
        super_model_id = f"{name}@{date}-{sha}"
    else:
        super_model_id = f"{name}@unknown"
    mirror_count = len(list(MIRROR_DIR.glob("selfdef-*-mirror.py"))) if MIRROR_DIR.is_dir() else 0
    return {
        "super_model_id": super_model_id,
        "milestone_count": len(rows),
        "rrow_count": sum(r["rrows"] for r in rows),
        "mirror_count": mirror_count,
        "shipped_count": sum(1 for r in rows if r["status"] == "shipped"),
    }


def snapshot() -> dict[str, Any]:
    """The full D-19 dashboard model."""
    man = _load_manifest()
    rows = milestones(man)
    return {
        "schema_version": SCHEMA_VERSION,
        "version": version(rows, man),
        "phases": _phases(man),
        "milestones": rows,
        "cross_refs": _cross_refs(man),
    }


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="super-model manifest core (M060 D-19)")
    sub = p.add_subparsers(dest="cmd")
    for name in ("snapshot", "version", "milestones"):
        sp = sub.add_parser(name)
        sp.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    cmd = args.cmd or "snapshot"
    if cmd == "version":
        _print(version())
    elif cmd == "milestones":
        _print(milestones())
    else:
        _print(snapshot())
    return 0


if __name__ == "__main__":
    sys.exit(main())
