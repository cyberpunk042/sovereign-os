#!/usr/bin/env python3
"""scripts/mirror/selfdef-trust-score-mirror.py — READ-ONLY consumer of the
selfdef tool trust-score mirror (M060 D-18 / R10123).

The data model behind the D-18 trust-scores cockpit dashboard. CROSS-REPO
MIRROR: the authoritative per-tool trust scores live in selfdef (the IPS) —
MS042 trust-score tracker (M01095), declaration-fidelity accumulation +
asymmetric decay, exposed by the selfdef `/v1/trust-scores` model surface
(SDD-064, shipped) and published as live per-tool scores through the MS007
typed-mirror crate `selfdef-trust-score-mirror`. sovereign-os renders it
READ-ONLY. Score reset is a selfdefctl + MS003 verb on the IPS side ONLY
(MS043 R10212). sovereign-os NEVER mutates IPS state.

Mirror artifact (selfdef-trust-score-mirror::TrustScoreMirrorSnapshot 1.0.0):
  schema_version · captured_at · tools[{tool,declarer,current_score(0-1000),
  band,first_admitted_at,last_delta_at,executions_total,mismatches_total,
  history[{applied_at,reason,delta,score_after,trace_id,signature}],
  last_trace_id,signature}]

Sovereignty: stdlib-only. Absent artifact → empty tools + mirror_status=
"offline" (graceful), NEVER a crash. The band is derived from the score on the
selfdef 0-1000 scale when not published (≥800 trusted / ≥500 watched /
≥200 suspect / else untrusted).

  selfdef-trust-score-mirror.py snapshot [--json]   full dashboard model
  selfdef-trust-score-mirror.py bands    [--json]    per-band tool counts
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

TRUST_MIRROR = Path(os.environ.get(
    "SOVEREIGN_OS_SELFDEF_TRUST_MIRROR",
    "/run/sovereign-os/selfdef-mirror/trust-scores.json",
))

# selfdef trust bands on the published 0-1000 scale (D-18 dashboard contract).
BANDS = ("trusted", "watched", "suspect", "untrusted")


def _read_mirror(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        d = json.loads(path.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _band_for(score: float) -> str:
    if score >= 800:
        return "trusted"
    if score >= 500:
        return "watched"
    if score >= 200:
        return "suspect"
    return "untrusted"


def _history(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out = []
    for h in raw:
        if not isinstance(h, dict):
            continue
        out.append({
            "applied_at": h.get("applied_at"),
            "reason": h.get("reason", ""),
            "delta": h.get("delta", 0),
            "score_after": h.get("score_after", 0),
            "trace_id": h.get("trace_id"),
            "signature": h.get("signature"),
        })
    return out


def _tools(mirror: dict[str, Any]) -> list[dict[str, Any]]:
    raw = mirror.get("tools")
    if not isinstance(raw, list):
        return []
    out = []
    for t in raw:
        if not isinstance(t, dict) or not t.get("tool"):
            continue
        score = t.get("current_score")
        score = float(score) if isinstance(score, (int, float)) else 0.0
        band = t.get("band")
        if band not in BANDS:
            band = _band_for(score)
        out.append({
            "tool": str(t["tool"]),
            "declarer": t.get("declarer", "unknown"),
            "current_score": int(score),
            "band": band,
            "first_admitted_at": t.get("first_admitted_at"),
            "last_delta_at": t.get("last_delta_at"),
            "executions_total": int(t.get("executions_total") or 0),
            "mismatches_total": int(t.get("mismatches_total") or 0),
            "history": _history(t.get("history")),
            "last_trace_id": t.get("last_trace_id"),
            "signature": t.get("signature"),
        })
    return out


def snapshot() -> dict[str, Any]:
    """The full D-18 dashboard model, projected from the selfdef mirror."""
    mirror = _read_mirror(TRUST_MIRROR)
    return {
        "schema_version": SCHEMA_VERSION,
        "mirror_status": "online" if mirror else "offline",
        "mirror_source": "selfdef-trust-score-mirror (MS007 typed mirror, read-only)",
        "captured_at": mirror.get("captured_at"),
        "summaries": [],  # the D-18 dashboard derives band tiles client-side
        "tools": _tools(mirror),
    }


def _bands(tools: list[dict[str, Any]]) -> dict[str, int]:
    counts = {b: 0 for b in BANDS}
    for t in tools:
        counts[t["band"]] = counts.get(t["band"], 0) + 1
    return counts


def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="selfdef trust-score mirror consumer (M060 D-18)")
    sub = p.add_subparsers(dest="cmd")
    for name in ("snapshot", "bands"):
        sp = sub.add_parser(name)
        sp.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    cmd = args.cmd or "snapshot"
    if cmd == "bands":
        _print(_bands(snapshot()["tools"]))
    else:
        _print(snapshot())
    return 0


if __name__ == "__main__":
    sys.exit(main())
