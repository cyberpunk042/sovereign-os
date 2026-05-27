#!/usr/bin/env python3
"""scripts/manifest/dashboard-toggles.py — operator dashboard on/off toggle core
(M060 R10038 + R10129-R10132).

Materializes the operator's standing direction (verbatim, 2026-05-19):
"there is over 20 dashboards and a main one and EVERYTHING CAN BE TURNED ON AND
OFF". Every cockpit dashboard can be toggled on/off; the toggle state persists
in /etc/sovereign-os/dashboards.toml (R10130); enable/disable is an operator CLI
action (R10131 — MS003-signed path, never the web surface); each toggle change
emits an M049 trace + OCSF Configuration Change class 5001 (R10132) into the
span log the D-05 traces dashboard reads.

  catalog        the real shipped dashboards = webapp/*/ dirs (D-00..D-20 +
                 the orthogonal operator surfaces). Never invented.
  toggle state   /etc/sovereign-os/dashboards.toml [dashboards] slug = true|false.
                 Absent slug → enabled (dashboards ship ON; the operator opts
                 OUT). Absent file → everything enabled.
  enforcement    is_enabled(slug) is consulted by the master-dashboard
                 aggregator (the operator entry point) + each dashboard's own
                 render path (SDD-040 D-040.5).

Sovereignty: stdlib-only (tomllib read; minimal TOML writer). Read-only by
default; set_enabled() is the operator mutation (writes the toml + emits the
OCSF 5001 span). Absent/malformed toml → all enabled (graceful), never a crash.

  dashboard-toggles.py list    [--json]             every dashboard + enabled bit
  dashboard-toggles.py status  <slug> [--json]       one dashboard's enabled bit
  dashboard-toggles.py enable  <slug>                turn a dashboard ON  (operator)
  dashboard-toggles.py disable <slug> [--rationale]  turn a dashboard OFF (operator)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

_REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARDS_TOML = Path(os.environ.get(
    "SOVEREIGN_OS_DASHBOARDS_TOML", "/etc/sovereign-os/dashboards.toml"))
WEBAPP_DIR = Path(os.environ.get(
    "SOVEREIGN_OS_WEBAPP_DIR", str(_REPO_ROOT / "webapp")))
# OCSF 5001 Configuration Change spans land in the M049 span log (D-05 reads it).
SPAN_LOG = Path(os.environ.get(
    "SOVEREIGN_OS_SPAN_STORE", "/var/log/sovereign-os/spans.jsonl"))


def catalog() -> list[str]:
    """The real shipped dashboards: every webapp/<slug>/index.html. Sorted."""
    if not WEBAPP_DIR.is_dir():
        return []
    out = []
    for p in sorted(WEBAPP_DIR.iterdir()):
        if p.is_dir() and (p / "index.html").is_file():
            out.append(p.name)
    return out


def _read_toggles_raw(path: Path = DASHBOARDS_TOML) -> dict[str, bool]:
    """The explicit toggle overrides from the toml (slug → bool). Absent →
    empty (everything defaults enabled)."""
    if not path.is_file():
        return {}
    try:
        with path.open("rb") as fh:
            doc = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError, ValueError):
        return {}
    raw = doc.get("dashboards") if isinstance(doc.get("dashboards"), dict) else doc
    out = {}
    for k, v in raw.items():
        if isinstance(v, bool):
            out[str(k)] = v
    return out


def is_enabled(slug: str, path: Path = DASHBOARDS_TOML) -> bool:
    """A dashboard is enabled unless the operator explicitly set it false."""
    return _read_toggles_raw(path).get(slug, True)


def toggles(path: Path = DASHBOARDS_TOML) -> dict[str, Any]:
    """Every catalogued dashboard + its enabled bit + counts."""
    overrides = _read_toggles_raw(path)
    cat = catalog()
    # include any toml slugs not on disk (operator may pre-stage), but mark them
    known = list(dict.fromkeys(cat + [s for s in overrides if s not in cat]))
    rows = [{"slug": s, "enabled": overrides.get(s, True),
             "on_disk": s in cat} for s in known]
    return {
        "schema_version": SCHEMA_VERSION,
        "toml_path": str(path),
        "toml_present": path.is_file(),
        "dashboards": rows,
        "total": len(rows),
        "enabled_count": sum(1 for r in rows if r["enabled"]),
        "disabled_count": sum(1 for r in rows if not r["enabled"]),
    }


def _write_toggles(overrides: dict[str, bool], path: Path = DASHBOARDS_TOML) -> None:
    """Write the [dashboards] table. Creates the parent dir if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# /etc/sovereign-os/dashboards.toml — operator dashboard on/off toggles",
        "# (M060 R10129-R10132). A dashboard absent here is ENABLED (ships ON);",
        "# the operator opts OUT by setting <slug> = false. Edited via",
        "# `sovereign-osctl dashboards {enable,disable}` (operator CLI, R10131).",
        "",
        "[dashboards]",
    ]
    for slug in sorted(overrides):
        lines.append(f"{slug} = {'true' if overrides[slug] else 'false'}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _emit_ocsf_5001(slug: str, enabled: bool, rationale: str) -> bool:
    """Emit the M049 trace + OCSF Configuration Change (class 5001) span for the
    toggle change (R10132) into the span log the D-05 dashboard reads. Best
    effort — a missing log dir never blocks the toggle."""
    now = datetime.now(tz=timezone.utc)
    span = {
        "trace_id": f"toggle-{int(time.time()*1000):x}",
        "span_id": f"dt-{slug}-{int(time.time()*1000):x}",
        "parent_span_id": None,
        "operation": "dashboard_toggle",
        "start_ts": now.isoformat(),
        "duration_ms": 0,
        "severity": "info",
        "actor": "operator",
        "profile": os.environ.get("SOVEREIGN_OS_ACTIVE_PROFILE", "private"),
        "ocsf_class": "5001",
        "ocsf_payload": {"class_uid": 5001, "activity": "Update",
                         "dashboard": slug, "enabled": enabled, "rationale": rationale},
        "attributes": {"dashboard": slug, "enabled": enabled, "rationale": rationale},
        "schema_version": "1.0.0",
    }
    try:
        SPAN_LOG.parent.mkdir(parents=True, exist_ok=True)
        with SPAN_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(span) + "\n")
        return True
    except OSError:
        return False


def set_enabled(slug: str, enabled: bool, rationale: str = "",
                path: Path = DASHBOARDS_TOML) -> dict[str, Any]:
    """Operator toggle (R10129-R10132). Validates the slug against the live
    catalog, persists the bit, emits the OCSF 5001 trace. Returns the change."""
    cat = catalog()
    if cat and slug not in cat:
        return {"ok": False, "error": f"unknown dashboard slug: {slug!r}",
                "known": cat}
    overrides = _read_toggles_raw(path)
    was = overrides.get(slug, True)
    overrides[slug] = enabled
    _write_toggles(overrides, path)
    traced = _emit_ocsf_5001(slug, enabled, rationale)
    return {"ok": True, "slug": slug, "was": was, "now": enabled,
            "changed": was != enabled, "ocsf_5001_traced": traced,
            "toml_path": str(path)}


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="operator dashboard on/off toggles (M060 R10129-R10132)")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("list").add_argument("--json", action="store_true")
    sp_st = sub.add_parser("status")
    sp_st.add_argument("slug")
    sp_st.add_argument("--json", action="store_true")
    sp_en = sub.add_parser("enable")
    sp_en.add_argument("slug")
    sp_en.add_argument("--rationale", default="")
    sp_di = sub.add_parser("disable")
    sp_di.add_argument("slug")
    sp_di.add_argument("--rationale", default="")
    args = p.parse_args(argv)
    cmd = args.cmd or "list"
    if cmd == "status":
        _print({"slug": args.slug, "enabled": is_enabled(args.slug)})
    elif cmd == "enable":
        r = set_enabled(args.slug, True, args.rationale)
        _print(r)
        return 0 if r.get("ok") else 2
    elif cmd == "disable":
        r = set_enabled(args.slug, False, args.rationale)
        _print(r)
        return 0 if r.get("ok") else 2
    else:
        _print(toggles())
    return 0


if __name__ == "__main__":
    sys.exit(main())
