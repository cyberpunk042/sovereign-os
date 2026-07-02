#!/usr/bin/env python3
"""scripts/cockpit/scheduler-status.py — MS048 M01166 cockpit consumer.

Reads the selfdef MS048 Goldilocks Scheduler textfile that M01174
binary writes (default
/var/lib/node_exporter/textfile_collector/selfdef-scheduler.prom)
and renders a cockpit-ready summary parallel to the 14 IPS queue
scripts that already feed serve.py.

This is the Python-side mirror of the M01163 Rust TUI panel + M01165
HTTP API — same data, different consumer. The IPS-quattuordectet
cockpit cards live alongside this one in the operator's single-pane
cockpit, but the scheduler is NOT an IPS axis (it's the runtime
routing layer; the 14 IPS axes are the enforcement layer). Both
contribute to the "ultimate sovereign AI workstation" at different
architectural altitudes per Peace Machine + Core Law.

Path overridable via SOVEREIGN_OS_SCHEDULER_TEXTFILE_PATH.

UX note: when the scheduler textfile is missing or stale, the card
correctly surfaces that as "observer wedged" or "observer silent"
— honest-offline pattern matching the 14 IPS observers' sentinel.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(
    os.environ.get(
        "SOVEREIGN_OS_SCHEDULER_TEXTFILE_PATH",
        "/var/lib/node_exporter/textfile_collector/selfdef-scheduler.prom",
    )
)

OBSERVER_SILENT_THRESHOLD_SECONDS = 300  # matches the Prometheus alert rule


def parse_textfile(text: str) -> dict[str, Any]:
    """Parse the M01168 Prometheus textfile into a structured dict.

    Mirrors the M01163 Rust parser's logic, including label-value-with-
    spaces handling for substrate_status reasons.
    """
    measurements: dict[str, float | int] = {}
    state: dict[str, bool] = {}
    substrate_health: dict[str, dict[str, Any]] = {
        "psi": {"healthy": True, "kind": None, "reason": None},
        "dcgm": {"healthy": True, "kind": None, "reason": None},
        "human_gate": {"healthy": True, "kind": None, "reason": None},
    }
    last_run_unix = 0
    textfile_emit_failed = False
    degraded_count = 0
    # MS048 decision metrics (selfdef_scheduler_decisions_*) — the route/
    # profile/hibernate gauges the M01174 binary now appends to the textfile.
    decisions: dict[str, Any] = {"in_ring": 0, "hibernate": 0, "by_route": {}}

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Two line shapes:
        #   <name> <value>
        #   <name>{<labels>} <value>
        # Labels can contain spaces (e.g. reason="kernel < 4.20"),
        # so split on '{' .. '}' for labeled gauges.
        match = re.match(
            r"^(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)(?:\{(?P<labels>[^}]*)\})?\s+(?P<value>.+)$",
            stripped,
        )
        if not match:
            continue
        name = match.group("name")
        labels_raw = match.group("labels") or ""
        value_raw = match.group("value").strip()
        labels = _parse_labels(labels_raw)

        if name == "selfdef_scheduler_cpu_psi":
            measurements["cpu_psi"] = float(value_raw)
        elif name == "selfdef_scheduler_mem_psi":
            measurements["mem_psi"] = float(value_raw)
        elif name == "selfdef_scheduler_io_psi":
            measurements["io_psi"] = float(value_raw)
        elif name == "selfdef_scheduler_blackwell_vram_util":
            measurements["blackwell_vram_util"] = float(value_raw)
        elif name == "selfdef_scheduler_gpu4090_util":
            measurements["gpu4090_util"] = float(value_raw)
        elif name == "selfdef_scheduler_human_gate_queue_depth":
            measurements["human_gate_queue_depth"] = int(float(value_raw))
        elif name == "selfdef_scheduler_cpu_pressure":
            state["cpu_pressure"] = value_raw == "1"
        elif name == "selfdef_scheduler_ram_pressure":
            state["ram_pressure"] = value_raw == "1"
        elif name == "selfdef_scheduler_io_pressure":
            state["io_pressure"] = value_raw == "1"
        elif name == "selfdef_scheduler_blackwell_vram_high":
            state["blackwell_vram_high"] = value_raw == "1"
        elif name == "selfdef_scheduler_gpu4090_busy":
            state["gpu4090_busy"] = value_raw == "1"
        elif name == "selfdef_scheduler_human_gate_queue_high":
            state["human_gate_queue_high"] = value_raw == "1"
        elif name == "selfdef_scheduler_substrate_healthy":
            source = labels.get("source")
            if source in substrate_health:
                substrate_health[source]["healthy"] = value_raw == "1"
        elif name == "selfdef_scheduler_substrate_status":
            source = labels.get("source")
            if source in substrate_health:
                substrate_health[source]["kind"] = labels.get("kind")
                substrate_health[source]["reason"] = labels.get("reason")
        elif name == "selfdef_scheduler_substrate_degraded_count":
            degraded_count = int(float(value_raw))
        elif name == "selfdef_scheduler_last_run_unix":
            last_run_unix = int(float(value_raw))
        elif name == "selfdef_scheduler_textfile_emit_failed":
            textfile_emit_failed = value_raw == "1"
        elif name == "selfdef_scheduler_decisions_in_ring":
            decisions["in_ring"] = int(float(value_raw))
        elif name == "selfdef_scheduler_decisions_hibernate":
            decisions["hibernate"] = int(float(value_raw))
        elif name == "selfdef_scheduler_decisions_by_route":
            route = labels.get("route")
            if route:
                decisions["by_route"][route] = int(float(value_raw))

    return {
        "measurements": measurements,
        "state": state,
        "substrate_health": substrate_health,
        "substrate_degraded_count": degraded_count,
        "last_run_unix": last_run_unix,
        "textfile_emit_failed": textfile_emit_failed,
        "decisions": decisions,
    }


def _parse_labels(labels_raw: str) -> dict[str, str]:
    """Parse key="value" pairs from a Prometheus label block.

    Handles values containing spaces and special characters. Does NOT
    handle escaped quotes inside values — that would require a more
    sophisticated tokenizer. For the M01168 emitter's escape pattern
    (\\\\ \\n \\") the renderer produces label values that round-trip
    through this parser for the substrate_status rows we care about.
    """
    out: dict[str, str] = {}
    # Match key="value" pairs allowing spaces inside value.
    pattern = re.compile(r'(\w+)="([^"]*)"')
    for m in pattern.finditer(labels_raw):
        out[m.group(1)] = m.group(2)
    return out


def derive_card_status(parsed: dict[str, Any]) -> str:
    """Reduce the structured parse to a single status string the cockpit
    can render as a colored badge.

    Status ladder:
      - "WEDGED"   — textfile_emit_failed (wrapper itself failed)
      - "SILENT"   — last_run_unix older than OBSERVER_SILENT_THRESHOLD_SECONDS
      - "BLIND"    — all 3 substrates degraded
      - "DEGRADED" — 1 or 2 substrates degraded
      - "PRESSURED"— any backpressure surface firing
      - "OK"       — healthy
    """
    if parsed["textfile_emit_failed"]:
        return "WEDGED"
    now = int(time.time())
    if parsed["last_run_unix"] and now - parsed["last_run_unix"] > OBSERVER_SILENT_THRESHOLD_SECONDS:
        return "SILENT"
    if parsed["substrate_degraded_count"] == 3:
        return "BLIND"
    # Substrate degradation (partial observability loss) outranks
    # backpressure (the scheduler working-but-busy) — per the ladder above
    # and the BLIND check directly above: 3 degraded substrates is BLIND
    # (top severity), so 1-2 degraded must be DEGRADED *before* PRESSURED is
    # considered. Checking PRESSURED first would mean adding a load signal to
    # a 2-degraded state DOWNGRADES the badge from DEGRADED to PRESSURED —
    # masking broken observability behind an expected-under-load indicator,
    # the wrong direction for a cockpit, and a discontinuity at the 3-vs-2
    # substrate boundary.
    if parsed["substrate_degraded_count"] > 0:
        return "DEGRADED"
    if any(parsed["state"].values()):
        return "PRESSURED"
    return "OK"


def render_human(parsed: dict[str, Any], status: str) -> str:
    lines = [f"MS048 Goldilocks Scheduler — status: {status}"]
    lines.append("─" * 72)
    sh = parsed["substrate_health"]
    for src in ("psi", "dcgm", "human_gate"):
        if sh[src]["healthy"]:
            lines.append(f"  {src:<12} [OK]")
        else:
            kind = sh[src]["kind"] or "degraded"
            reason = sh[src]["reason"] or "unknown"
            lines.append(f"  {src:<12} [{kind}] {reason}")
    lines.append("─" * 72)
    m = parsed["measurements"]
    if m:
        lines.append(
            f"  cpu={m.get('cpu_psi', 0)*100:.1f}% "
            f"mem={m.get('mem_psi', 0)*100:.1f}% "
            f"io={m.get('io_psi', 0)*100:.1f}% "
            f"bw_vram={m.get('blackwell_vram_util', 0)*100:.1f}% "
            f"gpu4090={m.get('gpu4090_util', 0)*100:.1f}% "
            f"hg={m.get('human_gate_queue_depth', 0)}"
        )
    fired = [k for k, v in parsed["state"].items() if v]
    if fired:
        lines.append(f"  backpressure firing: {', '.join(fired)}")
    else:
        lines.append("  backpressure firing: (none)")
    # MS048 decision metrics (routing outcomes from the ring window).
    dec = parsed.get("decisions") or {}
    in_ring = dec.get("in_ring", 0)
    if in_ring:
        by_route = dec.get("by_route", {})
        route_str = " ".join(
            f"{r}={by_route.get(r, 0)}"
            for r in ("blackwell", "rtx4090", "cpu", "hybrid", "hibernate")
        )
        lines.append(f"  decisions (ring={in_ring}): {route_str}")
        hib = dec.get("hibernate", 0)
        if hib:
            pct = 100.0 * hib / in_ring if in_ring else 0.0
            lines.append(f"  deferred (hibernate): {hib} ({pct:.0f}% of window)")
    else:
        lines.append("  decisions: (ring empty — no routing decisions recorded yet)")
    return "\n".join(lines) + "\n"


def render_json(parsed: dict[str, Any], status: str) -> str:
    out = {
        "status": status,
        **parsed,
    }
    return json.dumps(out, indent=2)


def load_textfile(path: Path = DEFAULT_PATH) -> dict[str, Any] | None:
    """Read + parse the textfile. Returns None on missing/unreadable
    (cockpit renders "WEDGED" when this happens)."""
    try:
        text = path.read_text()
    except (FileNotFoundError, PermissionError, IsADirectoryError):
        return None
    try:
        return parse_textfile(text)
    except (ValueError, KeyError):
        return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--json", action="store_true")
    p.add_argument("--path", default=str(DEFAULT_PATH))
    args = p.parse_args(argv)

    parsed = load_textfile(Path(args.path))
    if parsed is None:
        # Textfile missing → scheduler observer wedged from cockpit POV.
        parsed = {
            "measurements": {},
            "state": {},
            "substrate_health": {
                "psi": {"healthy": False, "kind": "absent", "reason": "textfile missing"},
                "dcgm": {"healthy": False, "kind": "absent", "reason": "textfile missing"},
                "human_gate": {"healthy": False, "kind": "absent", "reason": "textfile missing"},
            },
            "substrate_degraded_count": 3,
            "last_run_unix": 0,
            "textfile_emit_failed": True,
            "decisions": {"in_ring": 0, "hibernate": 0, "by_route": {}},
        }
        status = "WEDGED"
    else:
        status = derive_card_status(parsed)

    if args.json:
        print(render_json(parsed, status))
    else:
        sys.stdout.write(render_human(parsed, status))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
