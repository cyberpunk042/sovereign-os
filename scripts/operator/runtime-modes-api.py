#!/usr/bin/env python3
"""scripts/operator/runtime-modes-api.py — read-only HTTP API host for
the M076 three-load-balancing-profiles operator cockpit.

CROSS-CUTTING — exposes the 3 already-shipped runtime profiles
(profiles/runtime/{ultra-sovereign-efficiency,high-concurrency-burst,
deep-context-synthesis}.yaml — audited in backlog/SHIPPED.md M076
section, commit `999c133`) as a compact JSON envelope the
`/runtime-modes/` operator cockpit page consumes.

Project boundary R10212: read-only profile inspection. This proxy
NEVER mutates the on-disk YAMLs or the runtime state — the operator
selects a mode via the existing `selfdefctl modules apply` or
`scripts/lifecycle/runtime-mode-switch.sh` path (out of scope for
this proxy).

Endpoints (the contract webapp/runtime-modes/index.html fetches):
  GET /api/runtime-modes/list      list all 3 profile summaries
  GET /api/runtime-modes/<id>      full profile detail (YAML body)
  GET /api/runtime-modes/active    currently-active mode id
                                   (best-effort hint; absent when
                                   no marker file exists)
  GET /version | /healthz | /

Sovereignty: stdlib-only. Absent profile YAML → 404 (graceful,
never a crash).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

API_VERSION = "1.0.0"
API_BIND = os.environ.get("RUNTIME_MODES_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("RUNTIME_MODES_API_PORT", "7713"))
DRY_RUN = bool(os.environ.get("RUNTIME_MODES_API_DRY_RUN"))

DEFAULT_PROFILES_DIR = Path(os.environ.get(
    "SOVEREIGN_OS_PROFILES_RUNTIME_DIR",
    "/usr/share/sovereign-os/profiles/runtime",
))
ACTIVE_MODE_MARKER = Path(os.environ.get(
    "SOVEREIGN_OS_ACTIVE_RUNTIME_MODE_MARKER",
    "/run/sovereign-os/active-runtime-mode",
))

# The canonical 3 profile ids — locked here so drift in the
# profiles directory (an operator dropping a 4th profile) doesn't
# silently expand the cockpit's mode selector. Adding a 4th mode
# is an intentional change that requires updating this list.
CANONICAL_MODE_IDS = (
    "ultra-sovereign-efficiency",
    "high-concurrency-burst",
    "deep-context-synthesis",
)


def _profiles_dir() -> Path:
    """Resolve the profiles directory. Honors the env override; falls
    back to the dev-checkout path when the production install path
    is absent."""
    if DEFAULT_PROFILES_DIR.is_dir():
        return DEFAULT_PROFILES_DIR
    # Dev-checkout fallback — walk up from this script's location.
    here = Path(__file__).resolve().parent
    for ancestor in (here, here.parent, here.parent.parent):
        candidate = ancestor / "profiles" / "runtime"
        if candidate.is_dir():
            return candidate
    return DEFAULT_PROFILES_DIR  # honest absent — caller handles


def _summarize_profile(yaml_path: Path) -> dict[str, Any] | None:
    """Extract the 5 canonical summary fields from a profile YAML
    without requiring PyYAML (stdlib-only)."""
    if not yaml_path.is_file():
        return None
    body = yaml_path.read_text()
    out: dict[str, Any] = {
        "id": None,
        "name": None,
        "description_oneline": None,
        "verbatim_framing": None,
        "yaml_path": str(yaml_path),
    }
    lines = body.splitlines()
    desc_collecting = False
    desc_lines: list[str] = []
    verbatim_collecting = False
    verbatim_lines: list[str] = []
    for line in lines:
        s = line.strip()
        if s.startswith("Verbatim master spec framing:"):
            verbatim_collecting = True
            continue
        if verbatim_collecting:
            if s.startswith('#   "'):
                verbatim_lines.append(s[5:].rstrip('"'))
                continue
            if s.startswith("#"):
                if s.startswith('#    '):  # continuation
                    verbatim_lines.append(s[5:].rstrip('"'))
                    continue
            if not s.startswith("#"):
                verbatim_collecting = False
        if s.startswith("id:") and out["id"] is None:
            out["id"] = s.split(":", 1)[1].strip()
        elif s.startswith("name:") and out["name"] is None:
            out["name"] = s.split(":", 1)[1].strip().strip('"')
        elif s.startswith("description:") and not desc_collecting:
            rest = s.split(":", 1)[1].strip()
            if rest == "|":
                desc_collecting = True
            elif rest:
                out["description_oneline"] = rest
        elif desc_collecting:
            if line.startswith("    ") or line.startswith("\t"):
                desc_lines.append(line.strip())
            elif s and not s.startswith("#"):
                desc_collecting = False
    if desc_lines:
        out["description_oneline"] = " ".join(desc_lines)
    if verbatim_lines:
        out["verbatim_framing"] = " ".join(verbatim_lines).strip()
    return out


def _list_profiles() -> list[dict[str, Any]]:
    """Return the 3 canonical profile summaries in catalogue order."""
    out: list[dict[str, Any]] = []
    dir_ = _profiles_dir()
    for mode_id in CANONICAL_MODE_IDS:
        summary = _summarize_profile(dir_ / f"{mode_id}.yaml")
        if summary is not None:
            out.append(summary)
        else:
            # Honest-offline: profile YAML absent on this host.
            out.append({
                "id": mode_id,
                "name": None,
                "description_oneline": None,
                "verbatim_framing": None,
                "yaml_path": str(dir_ / f"{mode_id}.yaml"),
                "absent": True,
            })
    return out


def _active_mode() -> str | None:
    """Best-effort read of the active-mode marker file. Returns None
    when the marker doesn't exist (no mode applied yet) — the cockpit
    renders an UNKNOWN state in that case rather than guessing."""
    if not ACTIVE_MODE_MARKER.is_file():
        return None
    body = ACTIVE_MODE_MARKER.read_text().strip()
    if body in CANONICAL_MODE_IDS:
        return body
    return None


def _profile_detail(mode_id: str) -> dict[str, Any] | None:
    """Return the raw YAML body for a single profile, sufficient for
    the cockpit to render the full hardware allocation + tier
    breakdown. Stdlib-only — no YAML parsing here, just file read."""
    if mode_id not in CANONICAL_MODE_IDS:
        return None
    yaml_path = _profiles_dir() / f"{mode_id}.yaml"
    if not yaml_path.is_file():
        return None
    return {
        "id": mode_id,
        "yaml_path": str(yaml_path),
        "yaml_body": yaml_path.read_text(),
        "summary": _summarize_profile(yaml_path),
    }


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("runtime-modes-api: " + (fmt % args) + "\n")

    def _send_json(self, payload: dict[str, Any], code: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 — http.server protocol
        path = self.path.split("?", 1)[0]
        if path == "/api/runtime-modes/list":
            self._send_json({
                "modes": _list_profiles(),
                "canonical_ids": list(CANONICAL_MODE_IDS),
                "version": API_VERSION,
            })
        elif path == "/api/runtime-modes/active":
            self._send_json({
                "active": _active_mode(),
                "marker_path": str(ACTIVE_MODE_MARKER),
                "version": API_VERSION,
            })
        elif path.startswith("/api/runtime-modes/") and path != "/api/runtime-modes/":
            mode_id = path[len("/api/runtime-modes/"):].rstrip("/")
            detail = _profile_detail(mode_id)
            if detail is None:
                self._send_json({"error": "mode not found"}, code=404)
            else:
                self._send_json(detail)
        elif path == "/healthz":
            self._send_json({"status": "ok", "version": API_VERSION})
        elif path == "/version":
            self._send_json({
                "version": API_VERSION,
                "endpoints": [
                    "/api/runtime-modes/list",
                    "/api/runtime-modes/active",
                    "/api/runtime-modes/<id>",
                ],
                "canonical_mode_ids": list(CANONICAL_MODE_IDS),
            })
        elif path == "/":
            self._send_json({
                "service": "runtime-modes-api",
                "version": API_VERSION,
                "milestone": "M076 — three load-balancing profiles",
                "endpoints": [
                    "/api/runtime-modes/list",
                    "/api/runtime-modes/<id>",
                    "/api/runtime-modes/active",
                    "/version", "/healthz", "/",
                ],
            })
        else:
            self._send_json({"error": "not found"}, code=404)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--bind", default=API_BIND,
        help="bind address (default 127.0.0.1; honors $RUNTIME_MODES_API_BIND)",
    )
    p.add_argument(
        "--port", type=int, default=API_PORT,
        help="bind port (default 7713; honors $RUNTIME_MODES_API_PORT)",
    )
    p.add_argument(
        "--list-once", action="store_true",
        help="print the list envelope to stdout once and exit (testing / CI)",
    )
    args = p.parse_args(argv)

    if args.list_once:
        print(json.dumps({
            "modes": _list_profiles(),
            "canonical_ids": list(CANONICAL_MODE_IDS),
            "version": API_VERSION,
        }, indent=2))
        return 0
    if DRY_RUN:
        print(f"DRY_RUN: would bind {args.bind}:{args.port}")
        return 0

    srv = ThreadingHTTPServer((args.bind, args.port), _Handler)
    sys.stderr.write(
        f"runtime-modes-api: listening on http://{args.bind}:{args.port}\n"
    )
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
