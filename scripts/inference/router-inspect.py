#!/usr/bin/env python3
"""scripts/inference/router-inspect.py — R517 (E5++) JSON inspection
helper for the inference router (SDD-011).

Per operator §1g verbatim (sacrosanct):

  "We do not minimize anything."

Backs the `--json` mode of `sovereign-osctl router {status, rules,
metrics}` so the MCP surface (R517) and any automation can consume
structured router state instead of pretty-printed text.

Read-only by design — the inspection helper observes router state
without mutating it. The router itself is the sovereignty boundary;
mutation lives at request-routing time, not in the inspection
surface.

Usage:
  router-inspect.py status
  router-inspect.py rules
  router-inspect.py metrics
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

ROUTER_PORT = 8080
ROUTER_SERVICE = "sovereign-router.service"

# 5 SDD-011 routing rules — verbatim from scripts/inference/router.py.
SDD_011_RULES = [
    {
        "n": 1,
        "match": 'request.model startswith "microsoft/bitnet" or "ternary:"',
        "tier": "pulse",
    },
    {
        "n": 2,
        "match": 'request.model contains "code"/"math" markers + has draft',
        "tier": "oracle-core",
    },
    {
        "n": 3,
        "match": "context length > 65536",
        "tier": "oracle-core",
    },
    {
        "n": 4,
        "match": "request demands JSON-mode + structured output",
        "tier": "logic-engine",
    },
    {
        "n": 5,
        "match": "default",
        "tier": "logic-engine",
    },
]

METRICS_DIR_DEFAULT = "/var/lib/node_exporter/textfile_collector"


def _systemctl_active(unit: str) -> bool:
    try:
        cp = subprocess.run(
            ["systemctl", "is-active", "--quiet", unit],
            timeout=3,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        return False
    return cp.returncode == 0


def _tcp_listen(port: int, host: str = "127.0.0.1") -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.3)
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def status_payload() -> dict:
    return {
        "module": "router",
        "spec_ref": "SDD-011",
        "service": {
            "name": ROUTER_SERVICE,
            "active": _systemctl_active(ROUTER_SERVICE),
        },
        "listen": {
            "host": "127.0.0.1",
            "port": ROUTER_PORT,
            "open": _tcp_listen(ROUTER_PORT),
        },
        "backends": {
            "pulse":        {"port": 8081, "backend": "bitnet.cpp (CCD0)"},
            "logic-engine": {"port": 8082, "backend": "vLLM / llama.cpp"},
            "oracle-core":  {"port": 8083, "backend": "vLLM + DFlash"},
        },
        "standing_rule": "We do not minimize anything.",
    }


def rules_payload() -> dict:
    return {
        "module": "router",
        "spec_ref": "SDD-011",
        "rules": SDD_011_RULES,
        "match_order": "first match wins",
        "standing_rule": "We do not minimize anything.",
    }


def _read_route_metric() -> dict:
    """Best-effort read of the router Layer B textfile.

    The router emits sovereign_os_inference_route_total{tier,...}
    counters when it routes. Read whichever file the operator's
    deployment surfaces. Returns the count-per-tier mapping (empty if
    no file is found — read-only inspection, no fabrication).
    """
    metrics_dir = Path(os.environ.get(
        "SOVEREIGN_OS_METRICS_DIR", METRICS_DIR_DEFAULT,
    ))
    counts: dict[str, int] = {}
    classes: dict[str, int] = {}
    task_types: dict[str, int] = {}
    seen_files: list[str] = []
    if not metrics_dir.is_dir():
        return {
            "tier_counts": counts,
            "class_counts": classes,
            "task_type_counts": task_types,
            "metrics_dir": str(metrics_dir),
            "files_read": seen_files,
        }
    for path in sorted(metrics_dir.glob("sovereign*inference*route*.prom")):
        seen_files.append(path.name)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # naïve label-extractor for tier="..." class="..." task_type="..."
            try:
                metric, value = line.rsplit(" ", 1)
                v = int(float(value))
            except (ValueError, IndexError):
                continue
            tier = _extract_label(metric, "tier")
            cls = _extract_label(metric, "class")
            tt = _extract_label(metric, "task_type")
            if tier:
                counts[tier] = counts.get(tier, 0) + v
            if cls:
                classes[cls] = classes.get(cls, 0) + v
            if tt:
                task_types[tt] = task_types.get(tt, 0) + v
    return {
        "tier_counts": counts,
        "class_counts": classes,
        "task_type_counts": task_types,
        "metrics_dir": str(metrics_dir),
        "files_read": seen_files,
    }


def _extract_label(metric_with_labels: str, label: str) -> str:
    needle = label + '="'
    idx = metric_with_labels.find(needle)
    if idx < 0:
        return ""
    start = idx + len(needle)
    end = metric_with_labels.find('"', start)
    if end < 0:
        return ""
    return metric_with_labels[start:end]


def metrics_payload() -> dict:
    body = _read_route_metric()
    body["module"] = "router"
    body["spec_ref"] = "SDD-016 Layer B (Prometheus textfile collector)"
    body["standing_rule"] = "We do not minimize anything."
    return body


VERBS = {
    "status":  status_payload,
    "rules":   rules_payload,
    "metrics": metrics_payload,
}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        sys.stderr.write(
            "usage: router-inspect.py {status|rules|metrics}\n"
        )
        return 0 if (len(argv) >= 2 and argv[1] in ("-h", "--help")) else 2
    verb = argv[1]
    fn = VERBS.get(verb)
    if fn is None:
        sys.stderr.write(f"unknown verb: {verb!r}\n")
        sys.stderr.write(f"available: {sorted(VERBS)}\n")
        return 2
    print(json.dumps(fn(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
