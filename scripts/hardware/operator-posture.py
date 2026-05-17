#!/usr/bin/env python3
"""scripts/hardware/operator-posture.py — R300 (E1.M25).

Operator-named (§1b mandate row, verbatim): "Everything via dashboard/
UInterface or terminal tools OR AI". Closes E1.M25.

ONE operator-pull holistic posture rollup — synthesizes the per-axis
verdicts the recent rounds shipped:

  - R292 oc-headroom        →  XMP/OC PSU headroom
  - R294 psu-oc             →  PSU OC-mode + spec match
  - R296 thermal-oc-budget  →  thermal × PSU combined
  - R298 storage-health     →  logs + raid + partitions + journal
  - R299 bios-directives    →  BIOS-setting probe match-rate

Combined posture verdict: ok / watch / degraded — picks the worst
axis verdict (or empties when an axis probe is unavailable).

The dashboard's `card_operator_posture` consumes this same JSON
shape (R225 card framework). Terminal operators run `sovereign-osctl
operator-posture status [--json]` for the same info.

CLI:
  operator-posture.py status   [--json|--human]
  operator-posture.py advisory [--json|--human]

Exit codes:
  0  ok
  1  watch (≥1 axis warning)
  2  degraded (≥1 axis critical)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


SCHEMA_VERSION = "1.0.0"
ROUND = "R300"
SDD_VECTOR = "E1.M25"


def _run_json(rel_path: str, args: list[str]) -> dict[str, Any] | None:
    bin_path = REPO_ROOT / rel_path
    if not bin_path.is_file():
        return None
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), *args],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode not in (0, 1, 2):
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


# ── Axis adapters — translate per-probe verdict to our 3-level ─────
def _classify(verdict: str) -> str:
    """Map per-probe verdict vocab into our 3-level posture vocab."""
    if verdict is None:
        return "unknown"
    v = verdict
    safe = {"safe", "ok", "healthy", "headroom-safe", "no-breach",
            "matches-baseline", "no-raid", "applies-on-any-host"}
    watch = {"watch", "tight", "psu-watch", "thermal-watch", "both-tight",
             "headroom-tight", "drift", "warn", "probes-unavailable",
             "probe-unavailable", "baseline-unset", "unknown",
             "version-unknown", "skipped"}
    degraded = {"degraded", "critical", "over-budget", "pull-oc-now",
                "thermal-critical"}
    if v in safe:
        return "ok"
    if v in degraded:
        return "degraded"
    if v in watch:
        return "watch"
    return "unknown"


def probe_axes() -> dict[str, dict[str, Any]]:
    axes: dict[str, dict[str, Any]] = {}

    oc = _run_json("scripts/hardware/oc-headroom.py", ["status", "--json"])
    if oc is not None:
        axes["oc_headroom"] = {
            "probe": "scripts/hardware/oc-headroom.py",
            "verdict": oc.get("verdict"),
            "posture": _classify(oc.get("verdict")),
            "message": oc.get("message"),
        }
    else:
        axes["oc_headroom"] = {"probe": "(unavailable)",
                                "verdict": None, "posture": "unknown",
                                "message": None}

    psu = _run_json("scripts/hardware/psu-oc.py", ["state", "--json"])
    if psu is not None:
        # psu-oc doesn't emit verdict; classify by spec presence.
        spec_present = psu.get("operator_psu_spec") is not None
        axes["psu_oc"] = {
            "probe": "scripts/hardware/psu-oc.py",
            "verdict": "spec-found" if spec_present else "spec-missing",
            "posture": "ok" if spec_present else "watch",
            "message": (f"operator PSU `{psu.get('operator_psu_model')}` "
                        f"resolved in known_psus") if spec_present
                       else "operator PSU not in known_psus catalog",
        }
    else:
        axes["psu_oc"] = {"probe": "(unavailable)",
                          "verdict": None, "posture": "unknown",
                          "message": None}

    th = _run_json("scripts/hardware/thermal-oc-budget.py", ["status", "--json"])
    if th is not None:
        axes["thermal_oc"] = {
            "probe": "scripts/hardware/thermal-oc-budget.py",
            "verdict": th.get("verdict"),
            "posture": _classify(th.get("verdict")),
            "message": th.get("message"),
        }
    else:
        axes["thermal_oc"] = {"probe": "(unavailable)",
                              "verdict": None, "posture": "unknown",
                              "message": None}

    st = _run_json("scripts/hardware/storage-health-rollup.py", ["status", "--json"])
    if st is not None:
        axes["storage_health"] = {
            "probe": "scripts/hardware/storage-health-rollup.py",
            "verdict": st.get("verdict"),
            "posture": _classify(st.get("verdict")),
            "message": st.get("message"),
        }
    else:
        axes["storage_health"] = {"probe": "(unavailable)",
                                  "verdict": None, "posture": "unknown",
                                  "message": None}

    bd = _run_json("scripts/hardware/bios-directives.py", ["check", "--json"])
    if bd is not None:
        any_mm = bd.get("any_mismatch", False)
        axes["bios_directives"] = {
            "probe": "scripts/hardware/bios-directives.py",
            "verdict": "any-mismatch" if any_mm else "all-match",
            "posture": "watch" if any_mm else "ok",
            "message": ("≥1 BIOS directive mismatch — run "
                        "`sovereign-osctl bios-directives check`" if any_mm
                        else "All probable BIOS directives match recommended."),
        }
    else:
        axes["bios_directives"] = {"probe": "(unavailable)",
                                   "verdict": None, "posture": "unknown",
                                   "message": None}

    return axes


def combine_posture(axes: dict[str, dict]) -> dict[str, Any]:
    weight = {"ok": 0, "unknown": 1, "watch": 1, "degraded": 2}
    sev = max(weight.get(a["posture"], 1) for a in axes.values())
    if sev >= 2:
        return {"verdict": "degraded", "rc": 2,
                "message": "≥1 axis is critical — operator must intervene."}
    if sev >= 1:
        return {"verdict": "watch", "rc": 1,
                "message": "≥1 axis is warning / unknown — investigate."}
    return {"verdict": "ok", "rc": 0,
            "message": "All operator-posture axes ok."}


def render_human(doc: dict) -> str:
    lines = ["── R300 sovereign-os operator-posture rollup (E1.M25) ──"]
    lines.append(f"  verdict:    {doc['verdict']} (rc={doc['rc']})")
    lines.append(f"  message:    {doc['message']}")
    lines.append("")
    for name, axis in doc["axes"].items():
        posture = axis["posture"]
        mark = {"ok": "OK", "watch": "??", "degraded": "!!",
                "unknown": "--"}.get(posture, "??")
        lines.append(f"  [{mark}] {name:17s} posture={posture}, verdict={axis.get('verdict')}")
        if axis.get("message"):
            lines.append(f"            {axis['message']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="operator-posture.py")
    sub = p.add_subparsers(dest="verb", required=True)
    for verb in ("status", "advisory"):
        sp = sub.add_parser(verb)
        fmt = sp.add_mutually_exclusive_group()
        fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
        fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")
    args = p.parse_args(argv)

    axes = probe_axes()
    combined = combine_posture(axes)
    doc = {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        "axes": axes,
        "verdict": combined["verdict"],
        "rc": combined["rc"],
        "message": combined["message"],
    }

    if args.verb == "advisory":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "verdict": doc["verdict"],
                "rc": doc["rc"],
                "message": doc["message"],
                "axes_summary": {k: v["posture"] for k, v in axes.items()},
            }, indent=2))
        else:
            print(f"verdict: {doc['verdict']}")
            print(f"  {doc['message']}")
        return doc["rc"]

    if args.fmt == "json":
        print(json.dumps(doc, indent=2))
    else:
        print(render_human(doc), end="")
    return doc["rc"]


if __name__ == "__main__":
    sys.exit(main())
