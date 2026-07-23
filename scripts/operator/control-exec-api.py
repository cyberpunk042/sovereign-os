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
                                 annotate). BARE (no control_id): the
                                 ⚖ Compatibility pane payload — every rule +
                                 current state + the findings it trips now +
                                 the checkable control inventory. Read-only;
                                 same registry truth as the execute()
                                 pre-change gate.
  GET  /api/control/notifykit    the effective notifykit settings (base TOML +
                                 JSON overlay) — the SAME payload as
                                 `sovereign-osctl notifykit show --json`, so
                                 the header 🔔 overlay prefills from live
                                 state instead of blank selects. Read-only.
  GET  /api/control/avx-mode     the M002 AVX-mode inventory — which mode is
                                 ACTIVE on the box + whether the bit-machine
                                 (custom/hybrid) is engaged + the mode ledger.
                                 SAME truth as `sovereign-osctl avx-mode
                                 inventory`, so the panel AVX select prefills
                                 to the live mode instead of the first option.
                                 Read-only.
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
import subprocess
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

# tools/notifykit lives at the repo root — the live-state payload for the
# header 🔔 overlay (same truth as `sovereign-osctl notifykit show --json`).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
try:
    from tools.notifykit import cli as _notifykit_cli  # noqa: E402
except Exception:  # noqa: BLE001 — optional; the overlay degrades to blanks
    _notifykit_cli = None

# scripts/operator/setup.py — the integration credential/config collector. The
# READ payload (per-integration configured-vs-not + first_setup_done) for the Setup
# panel — SAME truth as `sovereign-osctl setup status --json`. Never returns a
# secret value (setup.status masks them).
try:
    import setup as _setup  # noqa: E402  (scripts/operator is on sys.path via _action_exec)
except Exception:  # noqa: BLE001 — optional; the panel degrades to unavailable
    _setup = None

# scripts/hardware/avx-mode.py — the M002 AVX-mode inventory (active mode +
# built-state + submodes), the SAME truth as `sovereign-osctl avx-mode
# inventory --json`, so the panel's AVX hotswap select prefills to the mode
# ACTUALLY active on the box instead of always defaulting to the first option.
# Hyphenated filename → load by file path. Optional; the select degrades to
# its static default when this is absent (static / per-port read-only serving).
import importlib.util as _ilu  # noqa: E402

try:
    _avx_spec = _ilu.spec_from_file_location(
        "_avx_mode",
        Path(__file__).resolve().parents[2] / "scripts" / "hardware" / "avx-mode.py")
    _avx_mode = _ilu.module_from_spec(_avx_spec)
    _avx_spec.loader.exec_module(_avx_mode)
except Exception:  # noqa: BLE001 — a broken avx-mode module never kills the rail
    _avx_mode = None

# The Plan Mode / User Approval Auto-mode safety classifier (lib/). Import
# directly so this daemon can gate destructive controls before they execute.
import importlib.util  # noqa: E402

_pc_spec = importlib.util.spec_from_file_location(
    "_permission_classifier",
    Path(__file__).resolve().parent / "lib" / "permission_classifier.py")
_permission = importlib.util.module_from_spec(_pc_spec)
_pc_spec.loader.exec_module(_permission)

# SDD-509 Phase C — the step-up MFA surface (config pane + step-up modal). The
# pure logic is in lib/stepup.py; this daemon exposes the read-only status
# (GET /api/control/stepup) + the auth routes (POST verify / request-otp /
# enroll). Optional: a broken stepup module never kills the rail.
try:
    _su_spec = importlib.util.spec_from_file_location(
        "_stepup", Path(__file__).resolve().parent / "lib" / "stepup.py")
    _stepup = importlib.util.module_from_spec(_su_spec)
    _su_spec.loader.exec_module(_stepup)
except Exception:  # noqa: BLE001
    _stepup = None


def _stepup_dir() -> Path:
    return Path(os.environ.get("SOVEREIGN_OS_STEPUP_DIR", "/run/sovereign-os/stepup"))


def _stepup_notify_config() -> Path:
    return Path(os.environ.get(
        "SOVEREIGN_OS_NOTIFYKIT_CONFIG",
        Path(__file__).resolve().parents[2] / "config" / "notifykit.toml"))


# The cockpit is one actor over the loopback daemon — its elevations are keyed
# under this session id (mirrors the actor _action_exec.execute() consumes).
_STEPUP_ACTOR = "cockpit-web"

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
            if _compat is None:
                self._send_json(503, {"error": "compat module unavailable",
                                      "control_id": control_id})
                return
            if not control_id:
                # Bare path — the ⚖ Compatibility pane payload: rules +
                # current state + live findings + checkable inventory.
                self._send_json(200, _compat.state_report())
                return
            preview = _compat.option_preview(control_id)
            if preview is None:
                self._send_json(404, {"error": f"unknown control {control_id!r}"})
                return
            self._send_json(200, preview)
            return
        if path == "/api/control/notifykit":
            if _notifykit_cli is None:
                self._send_json(503, {"error": "notifykit module unavailable"})
                return
            try:
                self._send_json(200, _notifykit_cli.show_payload())
            except Exception as e:  # noqa: BLE001 — read path must not crash the daemon
                self._send_json(500, {"error": f"notifykit state unreadable: {e}"})
            return
        if path == "/api/control/setup":
            # The integration setup payload the Setup panel prefills from — which
            # credentials/config each integration needs + configured-vs-not +
            # first_setup_done. Read-only; SAME truth as `sovereign-osctl setup
            # status --json`. No secret VALUE is ever returned (only set/unset).
            if _setup is None:
                self._send_json(503, {"error": "setup module unavailable"})
                return
            try:
                self._send_json(200, _setup.status())
            except Exception as e:  # noqa: BLE001 — read path must not crash the daemon
                self._send_json(500, {"error": f"setup state unreadable: {e}"})
            return
        if path == "/api/control/avx-mode":
            # The M002 AVX-mode inventory: which mode is ACTIVE on the box +
            # whether the bit-machine (custom/hybrid) is engaged + the mode
            # ledger. Read-only; the SAME truth as `avx-mode inventory`. The
            # panel select prefills from `active` so it shows live state.
            if _avx_mode is None:
                self._send_json(503, {"error": "avx-mode module unavailable"})
                return
            try:
                inv = _avx_mode.inventory()
                inv["available"] = True
                # The M002 bit-machine is the active path only under custom/hybrid
                # (opt-in) — the same gate as runs_bit_machine() in the crate/service.
                inv["runs_bit_machine"] = inv.get("active") in ("custom", "hybrid")
                self._send_json(200, inv)
            except Exception as e:  # noqa: BLE001 — read path must not crash the daemon
                self._send_json(500, {"error": f"avx-mode state unreadable: {e}"})
            return
        if path == "/api/control/stepup":
            # SDD-509 Phase C: the read-only step-up status the config pane +
            # the step-up modal prefill from — enrollment state, offerable
            # factors, break-glass codes left, elevation window, and which
            # controls sit at the step-up tier. No secret is ever exposed.
            if _stepup is None:
                self._send_json(503, {"error": "stepup module unavailable"})
                return
            try:
                reg = _action_exec.load_registry()
                controls = [{"id": cid, **reg[cid]} for cid in reg]
                self._send_json(200, _stepup.status(
                    _stepup_dir(), _stepup_notify_config(), controls=controls))
            except Exception as e:  # noqa: BLE001 — read path must not crash the daemon
                self._send_json(500, {"error": f"stepup state unreadable: {e}"})
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/control/registry", "/api/control/compat",
                          "/api/control/notifykit", "/api/control/avx-mode",
                          "/api/control/stepup", "/api/control/setup",
                          "/api/control/execute (POST; step-up auth rides a "
                          "'stepup' body key)",
                          "/version", "/healthz"],
        })

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _read_json_body(self):
        """Read + parse the JSON POST body; return (body, None) or (None, err)
        where err is an already-sent flag (the method sent the 400 itself)."""
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > _MAX_BODY:
            self._send_json(400, {"error": "missing or oversized JSON body "
                                           f"(0 < Content-Length <= {_MAX_BODY})"})
            return None, True
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            self._send_json(400, {"error": f"invalid JSON body: {e}"})
            return None, True
        if not isinstance(body, dict):
            self._send_json(400, {"error": "body must be a JSON object"})
            return None, True
        return body, None

    def _handle_stepup(self, su: dict) -> None:
        """SDD-509 Phase C step-up auth sub-actions, carried on the ONE write
        endpoint (a ``stepup`` key on the /api/control/execute body — the
        cockpit's single-POST doctrine). Each is gated by possession of a valid
        factor (or, for re-enrollment, a live elevation), so an attacker without
        a code gets nothing. Loopback-only.

          {"stepup": {"action": "verify",      "factor": .., "code": ..}}
          {"stepup": {"action": "request_otp", "factor": "sms"|"email"}}
          {"stepup": {"action": "enroll",      "account": ..?}}
          {"stepup": {"action": "regenerate_break_glass"}}
        """
        if _stepup is None:
            self._send_json(503, {"error": "stepup module unavailable"})
            return
        action = str(su.get("action") or "")
        d = _stepup_dir()
        nc = _stepup_notify_config()
        if action == "verify":
            factor = str(su.get("factor") or "")
            code = str(su.get("code") or "")
            if not factor or not code:
                self._send_json(400, {"error": "verify needs {factor, code}"})
                return
            try:
                res = _stepup.verify_factor_and_elevate(d, nc, _STEPUP_ACTOR, factor, code)
            except Exception as e:  # noqa: BLE001
                self._send_json(500, {"error": f"verify failed: {e}"})
                return
            if res is None:
                self._send_json(400, {"ok": False, "elevated": False,
                                      "error": f"factor {factor!r} is not set up"})
                return
            self._send_json(200 if res else 401,
                            {"ok": bool(res), "elevated": bool(res), "factor": factor,
                             "error": None if res else "invalid code"})
            return
        if action == "request_otp":
            factor = str(su.get("factor") or "")
            if factor not in ("sms", "email"):
                self._send_json(400, {"error": "request_otp needs factor sms|email"})
                return
            try:
                ok, detail = _stepup.request_otp_and_deliver(d, nc, _STEPUP_ACTOR, factor)
            except Exception as e:  # noqa: BLE001
                self._send_json(500, {"ok": False, "error": f"otp request failed: {e}"})
                return
            self._send_json(200 if ok else 503, {"ok": ok, "factor": factor, "detail": detail})
            return
        if action in ("set_tier", "clear_tier"):
            # Curating which controls need step-up is itself a step-up op — an
            # attacker who could freely lower a control's tier via the pane
            # defeats the gate. Requires a live elevation once enrolled.
            cid = str(su.get("control_id") or "")
            if not cid:
                self._send_json(400, {"error": "set_tier/clear_tier need a control_id"})
                return
            # never let selfdef/perimeter be curated off proxy-only (checked
            # before the elevation gate — it's an invariant, not a permission).
            if cid in ("selfdef", "perimeter"):
                self._send_json(400, {"ok": False,
                                      "error": f"{cid} is proxy-only and not curatable"})
                return
            if _stepup.is_enrolled(d) and not _stepup.ElevationStore(
                    d / "elevations.json").consume(_STEPUP_ACTOR, "step-up"):
                self._send_json(401, {"ok": False, "step_up_required": True,
                                      "tier": "step-up",
                                      "error": "changing a control's tier requires a live "
                                               "step-up elevation (verify a current factor first)",
                                      "factors": _stepup.status(d, nc)["factors"]})
                return
            try:
                if action == "clear_tier":
                    _stepup.clear_tier_override(d, cid)
                    ok = True
                else:
                    ok = _stepup.set_tier_override(d, cid, str(su.get("tier") or ""))
            except Exception as e:  # noqa: BLE001
                self._send_json(500, {"ok": False, "error": f"tier update failed: {e}"})
                return
            if not ok:
                self._send_json(400, {"ok": False,
                                      "error": "tier must be none|operator-present|step-up"})
                return
            self._send_json(200, {"ok": True, "control_id": cid})
            return
        if action in ("enroll", "regenerate_break_glass"):
            # Bootstrap enrollment is open only on a fresh box; RE-enrolling or
            # rotating recovery codes (an attacker rotating your secret =
            # takeover) requires a live elevation — changing a step-up setting
            # is itself a step-up op.
            already = _stepup.is_enrolled(d)
            needs_elevation = action == "regenerate_break_glass" or already
            if needs_elevation and not _stepup.ElevationStore(
                    d / "elevations.json").consume(_STEPUP_ACTOR, "step-up"):
                self._send_json(401, {"ok": False, "step_up_required": True,
                                      "tier": "step-up",
                                      "error": "this change requires a live step-up "
                                               "elevation (verify a current factor first)",
                                      "factors": _stepup.status(d, nc)["factors"]})
                return
            try:
                if action == "regenerate_break_glass":
                    recovery = _stepup.generate_break_glass(d)
                    self._send_json(200, {"ok": True, "recovery_codes": recovery})
                    return
                account = str(su.get("account") or "operator@sain-01")
                secret, uri = _stepup.enroll(d, account)
                recovery = _stepup.generate_break_glass(d)
            except Exception as e:  # noqa: BLE001
                self._send_json(500, {"ok": False, "error": f"enroll failed: {e}"})
                return
            # secret + recovery codes are returned ONCE (the operator saves them);
            # they are never persisted in plaintext or re-served.
            self._send_json(200, {"ok": True, "secret": secret,
                                  "provisioning_uri": uri, "recovery_codes": recovery,
                                  "reenrolled": already})
            return
        self._send_json(400, {"error": f"unknown stepup action {action!r}",
                              "actions": ["verify", "request_otp", "enroll",
                                          "regenerate_break_glass"]})

    def _handle_setup_write(self) -> None:
        """Write an integration value from the Setup pane. DELIBERATE, DOCUMENTED
        exception to the 'all mutation via _action_exec.execute()' doctrine: that
        rail validates args against option ENUMS (a secret has none) and LOGS the
        argv (a secret must never hit a log). So this dedicated path (a) validates
        NAME against the registry, (b) passes VALUE as a discrete argv element to
        `sovereign-osctl setup set` under `sudo -n` (no shell), and (c) NEVER logs,
        echoes, or returns the value. Only NAME + ok/err leave this method."""
        if _setup is None:
            self._send_json(503, {"ok": False, "error": "setup module unavailable"})
            return
        body, err = self._read_json_body()
        if err:
            return
        action = str(body.get("action") or "")
        if action not in ("set", "unset", "complete"):
            self._send_json(400, {"ok": False, "error": "action must be set|unset|complete"})
            return
        name = ""
        if action in ("set", "unset"):
            name = str(body.get("name") or "")
            idx = _setup._field_index()
            if name not in idx:
                self._send_json(400, {"ok": False, "error": f"unknown variable {name!r}"})
                return
            it, field = idx[name]
            if field.get("readonly") or it.get("managed_by"):
                self._send_json(400, {"ok": False, "error": f"{name} is managed elsewhere",
                                      "hint": it.get("managed_by", "")})
                return
        osctl = os.environ.get("SOVEREIGN_OS_OSCTL", "sovereign-osctl")
        if action == "set":
            argv = [osctl, "setup", "set", name, str(body.get("value", ""))]
        elif action == "unset":
            argv = [osctl, "setup", "unset", name]
        else:
            argv = [osctl, "setup", "complete"]
        argv = _action_exec._privileged_argv(argv, True)
        try:
            p = subprocess.run(argv, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as e:
            self._send_json(500, {"ok": False, "error": f"setup write failed: {e}"})
            return
        ok = p.returncode == 0
        resp: dict = {"ok": ok, "action": action}
        if name:
            resp["name"] = name
        if not ok:
            # setup.py never prints the value; stderr is safe to surface (redacted by design).
            resp["error"] = (p.stderr or p.stdout or "setup write failed").strip()[:300]
        self._send_json(200 if ok else 500, resp)

    def do_POST(self) -> None:  # noqa: N802
        path = urllib.parse.urlsplit(self.path).path.rstrip("/") or "/"
        if path == "/api/control/setup":
            self._handle_setup_write()
            return
        if path != "/api/control/execute":
            self._send_json(404, {
                "error": f"unknown write endpoint: {path!r}",
                "available": ["/api/control/execute", "/api/control/setup"],
            })
            return
        body, err = self._read_json_body()
        if err:
            return
        # SDD-509 Phase C: a step-up auth sub-action rides the same write
        # endpoint (single-POST doctrine) — dispatch it before control execution.
        su = body.get("stepup")
        if isinstance(su, dict):
            self._handle_stepup(su)
            return
        if not body.get("control_id"):
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
