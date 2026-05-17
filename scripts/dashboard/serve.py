#!/usr/bin/env python3
"""scripts/dashboard/serve.py — R225 (SDD-026 Z-1) dashboard SEED.

Operator-named (verbatim from the 2026-05-17 directive expansion):
"Always in the optic that this Debian 13 Sovereign OS is a non-GUI
by default. I will obviously be able to plug a screen or mainly
connect remotely to ssh and/or dashboard or API on whatsoever pot
for whatsoever dashbaords and modules and tools."

Minimal-stack HTTP server (stdlib http.server — no JS framework, no
npm chain, no template engine; the master spec ethos is "no bloat").
Serves a SINGLE page that aggregates every shipped Z-vector card:

  - GPU watt deviance  (R219 / Z-5 — scripts/hardware/gpu-watch.py)
  - Network state      (R220 / Z-7 — scripts/hardware/network-status.py)
  - CPU mode           (R221 / Z-4 — scripts/hardware/cpu-mode.py)
  - FS usage           (R222 / Z-10 — scripts/hardware/fs-insights.py)
  - RAID status        (R223 / Z-9 — scripts/hardware/raid-status.py)
  - Flex-profile state (R224 / Z-3 — scripts/hardware/profile-flex.py)

Each card invokes the underlying script's `--json` mode + renders a
small HTML block. Operator-readable. No mutations.

Endpoints:
  GET /             — full dashboard page
  GET /api/health   — aggregated JSON for all cards (machine-readable)
  GET /api/gpu      — single-card JSON (one per shipped Z-vector)
  GET /api/network
  GET /api/cpu
  GET /api/fs
  GET /api/raid
  GET /api/flex

Bind: 127.0.0.1:8443 by default. Operator opts in to exposure by
overriding --bind. Future round adds /etc/sovereign-os/dashboard.toml
allowlist + tailscale-only mode.

Run:
  sovereign-osctl dashboard serve            # blocks; Ctrl-C to stop
  sovereign-osctl dashboard serve --bind 0.0.0.0:8443 --json

Exit codes:
  0  clean shutdown
  2  usage error / bind failure

Tested via `--once` mode that handles ONE request + exits 0 (so the
L3 test can curl without spawning a separate process).
"""
from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------- card adapters


def _run_json(script: str, args: list[str]) -> dict[str, Any] | None:
    """Invoke a sibling script with --json and return parsed payload."""
    bin_path = REPO_ROOT / "scripts" / "hardware" / script
    if not bin_path.exists():
        return None
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), *args, "--json"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def card_gpu() -> dict[str, Any]:
    """R219 Z-5 — gpu-watch JSON."""
    data = _run_json("gpu-watch.py", []) or {"gpus": [], "any_deviance": False}
    return {"id": "gpu", "title": "GPU watt deviance (R219 / Z-5)", "data": data}


def card_network() -> dict[str, Any]:
    """R220 Z-7 — network-status JSON."""
    data = _run_json("network-status.py", []) or {"components": []}
    return {"id": "network", "title": "Network state (R220 / Z-7)", "data": data}


def card_cpu() -> dict[str, Any]:
    """R221 Z-4 — cpu-mode show JSON."""
    data = _run_json("cpu-mode.py", ["show"]) or {"cpus": {}}
    return {"id": "cpu", "title": "CPU mode (R221 / Z-4)", "data": data}


def card_fs() -> dict[str, Any]:
    """R222 Z-10 — fs-insights usage JSON."""
    data = _run_json("fs-insights.py", ["usage"]) or {"partitions": []}
    return {"id": "fs", "title": "Filesystem usage (R222 / Z-10)", "data": data}


def card_raid() -> dict[str, Any]:
    """R223 Z-9 — raid-status status JSON."""
    data = _run_json("raid-status.py", ["status"]) or {"arrays": [], "count": 0}
    return {"id": "raid", "title": "Software RAID (R223 / Z-9)", "data": data}


def card_flex() -> dict[str, Any]:
    """R224 Z-3 — profile-flex show JSON."""
    data = _run_json("profile-flex.py", ["show"]) or {"deltas": []}
    return {"id": "flex", "title": "Flex profile (R224 / Z-3)", "data": data}


def card_health() -> dict[str, Any]:
    """R226 Z-6 — composite health-scan JSON."""
    data = _run_json("health-scan.py", []) or {
        "probes": [], "summary": {}, "needs_attention": False
    }
    return {
        "id": "health",
        "title": "Health scan (R226 / Z-6)",
        "data": data,
    }


def _run_models_script(script: str, args: list[str]) -> dict[str, Any] | None:
    """Variant of _run_json for scripts/models/*.py."""
    bin_path = REPO_ROOT / "scripts" / "models" / script
    if not bin_path.exists():
        return None
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), *args, "--json"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def card_models() -> dict[str, Any]:
    """R227 Z-2 — Models tab (LM-Studio-equivalent surface).

    Aggregates the R212 catalog query + R214 profile-aware suggester
    into ONE dashboard card. Operators browse the curated model
    matrix (class × quantization × size × purpose) + see for each
    runtime profile which allocations are flagged.

    Data shape:
      catalog_count        — total catalog entries
      verified_real_count  — operator-pullable today
      aspirational_count   — catalog declares but no real repo
      by_class             — taxonomy histogram
      by_quantization      — quant histogram
      suggester            — per-runtime-profile flag summary
    """
    catalog = _run_models_script("catalog-query.py", []) or {}
    models = catalog.get("models") or []
    by_class: dict[str, int] = {}
    by_quant: dict[str, int] = {}
    verified = 0
    aspirational = 0
    for m in models:
        if m.get("class"):
            by_class[m["class"]] = by_class.get(m["class"], 0) + 1
        if m.get("quantization"):
            by_quant[m["quantization"]] = by_quant.get(m["quantization"], 0) + 1
        if m.get("status") == "verified-real":
            verified += 1
        elif m.get("status") == "aspirational":
            aspirational += 1
    # Per-runtime-profile suggester rollup (R214)
    suggester_rollup: list[dict[str, Any]] = []
    for pid in ("ultra-sovereign-efficiency", "high-concurrency-burst", "deep-context-synthesis"):
        s = _run_models_script("suggest-by-profile.py", ["--runtime-profile", pid])
        if s is not None:
            allocations = s.get("allocations") or []
            flagged = sum(1 for a in allocations if a.get("flags"))
            suggester_rollup.append({
                "profile_id": pid,
                "allocations_total": len(allocations),
                "allocations_flagged": flagged,
                "any_flagged": s.get("any_flagged", False),
            })
    data: dict[str, Any] = {
        "catalog_count": len(models),
        "verified_real_count": verified,
        "aspirational_count": aspirational,
        "by_class": by_class,
        "by_quantization": by_quant,
        "suggester_per_profile": suggester_rollup,
    }
    return {
        "id": "models",
        "title": "Models — catalog × profile (R227 / Z-2)",
        "data": data,
    }


CARDS = [
    card_gpu,
    card_network,
    card_cpu,
    card_fs,
    card_raid,
    card_flex,
    card_health,
    card_models,
]


# --------------------------------------------------------- rendering


def render_html(cards: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    parts.append("<!doctype html>")
    parts.append("<html><head><title>sovereign-os dashboard (R225)</title>")
    parts.append("<style>")
    parts.append("  body{font:14px/1.4 monospace;background:#0d1117;color:#c9d1d9;padding:1em;margin:0;}")
    parts.append("  h1{font-size:1.2em;border-bottom:1px solid #30363d;padding-bottom:.3em;}")
    parts.append("  .card{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:1em;margin:1em 0;}")
    parts.append("  .card h2{font-size:1em;margin:0 0 .5em 0;color:#79c0ff;}")
    parts.append("  pre{background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:.5em;overflow:auto;white-space:pre-wrap;}")
    parts.append("  footer{margin-top:2em;color:#8b949e;font-size:.9em;}")
    parts.append("  .ok{color:#3fb950;} .warn{color:#d29922;} .down{color:#f85149;}")
    parts.append("</style></head><body>")
    parts.append("<h1>sovereign-os dashboard — R225 / SDD-026 Z-1 SEED</h1>")
    parts.append(
        "<p>Every card reads the same script the operator runs via "
        "<code>sovereign-osctl</code>. Read-only; no mutations.</p>"
    )
    for c in cards:
        parts.append(f'<section class="card" id="card-{html.escape(c["id"])}">')
        parts.append(f"<h2>{html.escape(c['title'])}</h2>")
        body = json.dumps(c["data"], indent=2)
        parts.append(f"<pre>{html.escape(body)}</pre>")
        parts.append("</section>")
    parts.append('<footer>')
    parts.append('  Operator note: read-only mirror of the terminal cards.')
    parts.append('  Mutations stay on the CLI (or the future MCP server SD-R84+).')
    parts.append('  JSON endpoint: <code>/api/health</code> · per-card: ')
    for c in cards:
        parts.append(f'<code>/api/{html.escape(c["id"])}</code> · ')
    parts.append('</footer></body></html>')
    return "".join(parts)


def gather_all() -> list[dict[str, Any]]:
    return [c() for c in CARDS]


# --------------------------------------------------------- HTTP layer


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "sovereign-os-dashboard/R225"

    # Quiet stderr (the L3 test would otherwise see request log noise).
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, body_str: str, status: int = 200) -> None:
        body = body_str.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path
        if path == "/" or path == "/index.html":
            self._send_html(render_html(gather_all()))
            return
        if path == "/api/health":
            self._send_json({"cards": gather_all(), "round": "R225", "sdd_vector": "SDD-026 Z-1"})
            return
        # R233 (SDD-026 Z-2): per-model detail endpoint. Drives the
        # dashboard's "click on a model card → see full detail" UX
        # by proxying the R231 `models info <slug>` JSON. The slug
        # follows after /api/models/ so URL-safe slugs work directly.
        models_prefix = "/api/models/"
        if path.startswith(models_prefix):
            slug = path[len(models_prefix):]
            # Defensive: reject path separators / control chars even
            # though subprocess argv is shell-safe; keep slug semantics
            # tight (model ids in the catalog are alnum + - + .).
            if slug and all(c.isalnum() or c in "-_." for c in slug):
                detail = _run_models_script("info.py", [slug])
                if detail is not None:
                    self._send_json(detail)
                    return
                self._send_json(
                    {
                        "error": "unknown model slug",
                        "slug": slug,
                        "round": "R233",
                        "hint": "list available ids via /api/models or "
                                "`sovereign-osctl models query --json`",
                    },
                    status=404,
                )
                return
            self._send_json(
                {
                    "error": "invalid model slug",
                    "slug": slug,
                    "round": "R233",
                },
                status=400,
            )
            return
        for c in CARDS:
            card_id = c.__name__.removeprefix("card_")
            if path == f"/api/{card_id}":
                self._send_json(c())
                return
        self._send_json(
            {"error": "not found", "path": path, "round": "R225"},
            status=404,
        )


def parse_bind(s: str) -> tuple[str, int]:
    if ":" not in s:
        raise ValueError(f"--bind must be HOST:PORT (got {s!r})")
    host, port_str = s.rsplit(":", 1)
    try:
        port = int(port_str)
    except ValueError as e:
        raise ValueError(f"--bind port not an int: {port_str!r}") from e
    return host or "127.0.0.1", port


def main() -> int:
    p = argparse.ArgumentParser(description="R225 (SDD-026 Z-1) dashboard SEED.")
    p.add_argument(
        "--bind",
        default="127.0.0.1:8443",
        help="bind address HOST:PORT (default %(default)s)",
    )
    p.add_argument(
        "--once",
        action="store_true",
        help="handle exactly one request and exit (used by L3 tests)",
    )
    p.add_argument(
        "--render-only",
        action="store_true",
        help=(
            "DO NOT bind a socket; render the dashboard HTML to stdout "
            "and exit. Used for offline-rendering tests + a future static "
            "snapshot path."
        ),
    )
    args = p.parse_args()

    if args.render_only:
        sys.stdout.write(render_html(gather_all()))
        return 0

    try:
        host, port = parse_bind(args.bind)
    except ValueError as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 2
    try:
        srv = HTTPServer((host, port), DashboardHandler)
    except OSError as e:
        print(f"ERROR bind {host}:{port}: {e}", file=sys.stderr)
        return 2
    print(f"# R225 sovereign-os dashboard serving http://{host}:{port}/")
    try:
        if args.once:
            srv.handle_request()
        else:
            srv.serve_forever()
    except KeyboardInterrupt:
        print()
        print("# R225 shutdown via SIGINT")
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
