#!/usr/bin/env python3
"""scripts/operator/control-exec-api.py — the cockpit's sanctioned mutation
endpoint (R10274), the FUNCTIONAL realization of "features functional from the
panels / dashboard ... the manual command is only the alternative".

Every read-only per-panel daemon (`*-api.py`) still `_reject()`s writes with
405. This ONE dedicated daemon is the single place the web is allowed to
mutate — and only through the deterministic `_action_exec.execute()` primitive:
allowlisted control-id, options-validated placeholders, R10212 hard boundary
(selfdef/perimeter are NEVER executed locally — they stay a signed proxy), an
operator-key + type-to-confirm gate on privileged controls, an OCSF-5001 audit
span, single-flight lock, and DRY_RUN-by-default (nothing mutates the host
until the process opts in with SOVEREIGN_OS_ACTION_EXEC_LIVE=1).

So R10212 is preserved: the web still never *arbitrarily* mutates. It executes
only a fixed, validated, confirmed, audited set of sovereign-os-owned verbs —
exactly R10274's "mutation proxies via an MS003-signed request", now wired.

Per operator §1g (verbatim, sacrosanct): "We do not minimize anything."
Per operator directive (sacrosanct): "we will fix everything that is a manual
command so that the manual command is only the alternative but we will
otherwise do the features functional from the panels / dashboard."

Sovereignty (stdlib-only, zero deps):
  - http.server + BaseHTTPRequestHandler; loopback-bind by default
  - the ONLY write endpoint in the cockpit; every other daemon is read-only
  - same-origin; DRY_RUN default; boundary + confirm + audit in the primitive

Endpoints:
  GET  /api/control/registry     which controls execute-locally vs proxy-only
                                 (+ the control-systems list the UI renders)
  GET  /api/control/compat       ?control_id=X — per-option compat preview
                                 against best-effort current state (the rail
                                 GREYS force-incompatible options; warn/suggest
                                 annotate). Read-only; same registry truth as
                                 the execute() pre-change gate.
  POST /api/control/execute      body {control_id, args?, confirm?} ->
                                 _action_exec.execute() ; HTTP status mirrors
                                 the primitive's result code (200/400/403/404/409/…)
  GET  /version | /healthz | /

Env (all overridable):
  CONTROL_EXEC_API_BIND          (default 127.0.0.1 — loopback only)
  CONTROL_EXEC_API_PORT          (default 8130)
  CONTROL_EXEC_API_DRY_RUN       (set=1 → print config + exit; startup check)
  SOVEREIGN_OS_ACTION_EXEC_LIVE  (set=1 → the primitive actually executes;
                                  UNSET/0 → every execute is a safe dry-run)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# _action_exec + compat live beside this file (scripts/operator/). Import directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _action_exec  # noqa: E402

try:
    import compat as _compat  # noqa: E402 — the compat preview is optional
except Exception:  # noqa: BLE001 — a broken compat module never kills the rail
    _compat = None

# The Plan Mode / User Approval Auto-mode safety classifier (lib/). Import
# directly so this daemon can gate destructive controls before they execute.
import importlib.util  # noqa: E402

_pc_spec = importlib.util.spec_from_file_location(
    "_permission_classifier",
    Path(__file__).resolve().parent / "lib" / "permission_classifier.py")
_permission = importlib.util.module_from_spec(_pc_spec)
_pc_spec.loader.exec_module(_permission)

API_BIND = os.environ.get("CONTROL_EXEC_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("CONTROL_EXEC_API_PORT", "8130"))
DRY_RUN = bool(os.environ.get("CONTROL_EXEC_API_DRY_RUN"))
API_VERSION = "1.0.0"
_MAX_BODY = 64 * 1024  # a control action is tiny; cap the POST body hard.


def _registry_payload() -> dict:
    """The controls the UI renders + the authoritative execute-local vs
    proxy-only split (computed from the same SELFDEF_OWNED boundary the
    execute() primitive enforces — one source of truth)."""
    reg = _action_exec.load_registry()
    owned = _action_exec.owned_controls()
    controls = []
    for cid in sorted(reg):
        c = reg[cid]
        controls.append({
            "id": cid,
            "label": c.get("label", cid),
            "kind": c.get("kind"),
            "privileged": bool(c.get("privileged")),
            "options": c.get("options"),
            "change_cli": c.get("change_cli"),
            "applies_to": c.get("applies_to"),
            # AUTHORITATIVE: does the web execute this locally, or only proxy it?
            "execute_local": cid not in _action_exec.SELFDEF_OWNED,
        })
    return {
        "service": "control-exec-api",
        "version": API_VERSION,
        "standing_rule": "We do not minimize anything.",
        "live": os.environ.get("SOVEREIGN_OS_ACTION_EXEC_LIVE") == "1",
        "boundary": "R10212 — selfdef-owned controls are proxy-only (never executed locally)",
        "owned": owned,
        "controls": controls,
    }


class ControlExecAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-control-exec-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[control-exec] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "control-exec-api")
        self.send_header("X-Sovereign-Version", API_VERSION)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urllib.parse.urlsplit(self.path).path.rstrip("/") or "/"
        if path in ("/", "/healthz"):
            self._send_json(200, {"status": "ok", "version": API_VERSION})
            return
        if path == "/version":
            self._send_json(200, {"service": "control-exec-api", "version": API_VERSION,
                                  "standing_rule": "We do not minimize anything."})
            return
        if path == "/api/control/registry":
            self._send_json(200, _registry_payload())
            return
        if path == "/api/control/compat":
            qs = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            control_id = (qs.get("control_id") or [""])[0]
            if not control_id:
                self._send_json(400, {"error": "pass ?control_id=<id>"})
                return
            if _compat is None:
                self._send_json(503, {"error": "compat module unavailable",
                                      "control_id": control_id})
                return
            preview = _compat.option_preview(control_id)
            if preview is None:
                self._send_json(404, {"error": f"unknown control {control_id!r}"})
                return
            self._send_json(200, preview)
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/control/registry", "/api/control/compat",
                          "/api/control/execute (POST)", "/version", "/healthz"],
        })

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def do_POST(self) -> None:  # noqa: N802
        path = urllib.parse.urlsplit(self.path).path.rstrip("/") or "/"
        if path != "/api/control/execute":
            self._send_json(404, {
                "error": f"unknown write endpoint: {path!r}",
                "available": ["/api/control/execute"],
            })
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > _MAX_BODY:
            self._send_json(400, {"error": "missing or oversized JSON body "
                                           f"(0 < Content-Length <= {_MAX_BODY})"})
            return
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            self._send_json(400, {"error": f"invalid JSON body: {e}"})
            return
        if not isinstance(body, dict) or not body.get("control_id"):
            self._send_json(400, {"error": "body must be an object with a "
                                           "control_id (and optional args, confirm)"})
            return
        control_id = str(body["control_id"])
        args = body.get("args") or {}
        if not isinstance(args, dict):
            self._send_json(400, {"error": "args must be an object of "
                                           "placeholder -> value"})
            return
        confirm = bool(body.get("confirm"))
        # ── Plan Mode / User Approval permission gate ──────────────────────────
        # Classify this control's change_cli under the active permission mode.
        # AUTO auto-BLOCKS a destructive control before it can reach the primitive
        # (the safety-classifier guarantee); manual/bypass fall through to the
        # existing dry-run + operator-key + type-to-confirm gate. The verdict
        # rides on every response so the cockpit can show it.
        mode = _permission.default_mode()
        change_cli = (_action_exec.load_registry().get(control_id) or {}).get("change_cli", "")
        decision = _permission.decide(change_cli, mode)
        if decision["action"] == "block":
            self._send_json(403, {
                "code": 403, "ok": False, "blocked": True,
                "control_id": control_id, "permission": decision,
                "error": decision["message"],
            })
            return
        # dry_run is left to the primitive (SOVEREIGN_OS_ACTION_EXEC_LIVE gate) —
        # the daemon never forces a live execution.
        result = _action_exec.execute(
            control_id, {str(k): str(v) for k, v in args.items()},
            confirm=confirm, actor="cockpit-web",
        )
        if isinstance(result, dict):
            result["permission"] = decision
        self._send_json(int(result.get("code", 500)), result)

    def do_PUT(self) -> None:  # noqa: N802
        self._send_json(405, {"error": "use POST /api/control/execute",
                              "allowed": ["GET", "HEAD", "POST"]})

    def do_DELETE(self) -> None:  # noqa: N802
        self._send_json(405, {"error": "controls are not deletable via the web",
                              "allowed": ["GET", "HEAD", "POST"]})


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    httpd = ThreadingHTTPServer((bind, port), ControlExecAPIHandler)
    sys.stderr.write(
        f"[control-exec] serving on http://{bind}:{port} "
        f"(live={os.environ.get('SOVEREIGN_OS_ACTION_EXEC_LIVE') == '1'})\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    if DRY_RUN:
        print(json.dumps(_registry_payload(), indent=2))
        return 0
    return serve()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
