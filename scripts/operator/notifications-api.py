#!/usr/bin/env python3
"""scripts/operator/notifications-api.py — read-only in-cockpit NOTIFICATIONS
inbox: the aggregation surface behind the header 🔔 badge + pane.

This is the "does the box need attention" rollup. It fans in signals that are
otherwise scattered across the operator surfaces and returns ONE uniform list of
items the app-shell renders as a badge (count) + a pane (each item deep-links to
the pane that fixes it). It is READ-ONLY (GET only) — it never mutates the box,
so it stays clear of the exec-rail/osctl-verb/sudoers chain.

Distinct from the notifykit 🔔 SETTINGS overlay (`/api/control/notifykit`), which
configures OUTBOUND channels. This is the inbox; that is the delivery config. The
optional outbound fan-out of THESE items lives in notifications-emit.py (opt-in),
never in this GET handler (a GET must be side-effect free).

Extensible by design: `PROVIDERS` is a list of callables, each returning a list
of items. `collect()` runs each in its own try/except so one bad source degrades
(returns nothing) instead of 500-ing or fabricating. Add a provider, done.

Item schema:   {id, source, severity, title, detail, remediation, deep_link}
Severity:      "attention" | "down"  (health-scan's vocabulary; down > attention).
               "ok" is implicit — a clean box simply yields no items.
Envelope:      {schema_version, generated_at, needs_attention, count_by_severity, items}

Endpoints:
  GET /api/notifications     the rollup envelope
  GET /version | /healthz | /

Env:
  NOTIFICATIONS_API_BIND (default 127.0.0.1) · NOTIFICATIONS_API_PORT (default 8149)
  NOTIFICATIONS_API_DRY_RUN · SOVEREIGN_OS_METRICS_DIR
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# scripts/operator on sys.path so `import setup` resolves when run standalone
# (control-exec-api relies on the same sibling-import convention).
sys.path.insert(0, str(Path(__file__).resolve().parent))

API_BIND = os.environ.get("NOTIFICATIONS_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("NOTIFICATIONS_API_PORT", "8149"))
DRY_RUN = bool(os.environ.get("NOTIFICATIONS_API_DRY_RUN"))
API_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"

METRICS_DIR = os.environ.get("SOVEREIGN_OS_METRICS_DIR", "/var/lib/node_exporter/textfile_collector")
METRIC_NAME = "sovereign_os_operator_notifications_api_request_total"

# first-boot oneshots whose FAIL should surface. Derived at runtime from the
# target's Wants= (authoritative — no drift from a hardcoded list) PLUS the two
# install units that are NOT in the target's Wants but still matter.
FIRSTBOOT_TARGET = "sovereign-firstboot.target"
FIRSTBOOT_EXTRA_UNITS = (
    "sovereign-openclaw-install.service",
    "sovereign-open-computer-install.service",
)
# The completion marker unit is not an "attention" signal on its own — exclude.
FIRSTBOOT_SKIP = {"sovereign-firstboot.service"}

SEV_ORDER = {"down": 0, "attention": 1}   # for sorting most-severe first


def _emit_metric(endpoint: str, result: str) -> None:
    if DRY_RUN:
        return
    try:
        os.makedirs(METRICS_DIR, exist_ok=True)
        prom = os.path.join(METRICS_DIR, "sovereign-os-notifications-api.prom")
        with open(prom, "a") as f:
            f.write(f'{METRIC_NAME}{{endpoint="{endpoint}",result="{result}"}} 1\n')
    except OSError:
        pass


def _run(cmd: list[str]) -> tuple[int, str]:
    """Run a read-only probe; degrade cleanly when the tool is absent (CI / a box
    without systemd) so a provider never raises out of collect()."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return p.returncode, (p.stdout or "").strip()
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return 127, ""


def _item(id_: str, source: str, severity: str, title: str,
          detail: str = "", remediation: str = "", deep_link: str | None = None) -> dict:
    return {
        "id": id_, "source": source, "severity": severity,
        "title": title, "detail": detail, "remediation": remediation,
        "deep_link": deep_link,
    }


# ── providers ───────────────────────────────────────────────────────────────
def provider_setup() -> list[dict]:
    """.env / integration configuration status — the driving example. Each
    unconfigured integration (that the operator owns; managed-by ones are
    informational) is an `attention` item deep-linking to the Setup overlay."""
    try:
        import setup as _setup  # sibling module
    except Exception:  # noqa: BLE001 — degrade: no setup module → no items
        return []
    st = _setup.status()
    items: list[dict] = []
    for it in st.get("integrations", []):
        if it.get("configured"):
            continue
        if it.get("managed_by"):
            continue  # e.g. anthropic — provisioned elsewhere, shown for visibility only
        label = it.get("label", it.get("id", "?"))
        items.append(_item(
            id_=f"setup:{it.get('id')}",
            source="setup",
            severity="attention",
            title=f"{label} not configured",
            detail=it.get("summary", "") or f"integration '{it.get('id')}' has unset required fields",
            remediation=f"Open Setup and set the required fields (writes /etc/sovereign-os/{it.get('env_file','*.env')})",
            deep_link="setup",
        ))
    # Fresh box that never ran `setup complete` — one higher-level nudge.
    if not st.get("first_setup_done"):
        items.append(_item(
            id_="setup:first-run",
            source="setup",
            severity="attention",
            title="Initial setup not completed",
            detail=f"{st.get('configured_count', 0)} of {st.get('integration_count', 0)} integrations configured",
            remediation="Open Setup, configure integrations, then mark setup complete",
            deep_link="setup",
        ))
    return items


def _firstboot_units() -> list[str]:
    rc, out = _run(["systemctl", "show", FIRSTBOOT_TARGET, "-p", "Wants", "--value"])
    units: list[str] = []
    if rc == 0 and out:
        units = [u for u in out.split() if u.endswith(".service")]
    for extra in FIRSTBOOT_EXTRA_UNITS:
        if extra not in units:
            units.append(extra)
    return [u for u in units if u not in FIRSTBOOT_SKIP]


def provider_firstboot() -> list[dict]:
    """Failed first-boot oneshots. `systemctl is-failed <unit>` prints 'failed'
    for a unit in the failed state; anything else (active/inactive/unknown) is not
    an attention item. Read-only. Degrades to nothing without systemd."""
    items: list[dict] = []
    for unit in _firstboot_units():
        rc, out = _run(["systemctl", "is-failed", unit])
        if out == "failed":
            items.append(_item(
                id_=f"firstboot:{unit}",
                source="firstboot",
                severity="down",
                title=f"first-boot unit failed: {unit}",
                detail="systemd reports this first-boot unit in the failed state",
                remediation=f"Inspect: systemctl status {unit} ; journalctl -u {unit}",
                deep_link="d-26-friction-audit",
            ))
    return items


# Extensible registry — append a callable returning list[item] to add a source.
PROVIDERS = [provider_setup, provider_firstboot]


def collect() -> dict:
    """Run every provider (isolated), assemble the rollup envelope. Importable by
    notifications-emit.py so the outbound fan-out uses the SAME truth without an
    HTTP self-call. Honesty rule: a provider that raises contributes nothing —
    never a fabricated item, never a 500."""
    items: list[dict] = []
    for prov in PROVIDERS:
        try:
            items.extend(prov() or [])
        except Exception:  # noqa: BLE001 — one bad source must not sink the inbox
            continue
    items.sort(key=lambda i: (SEV_ORDER.get(i.get("severity"), 9), i.get("id", "")))
    counts: dict[str, int] = {}
    for i in items:
        counts[i["severity"]] = counts.get(i["severity"], 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": int(time.time()),
        "needs_attention": bool(items),
        "count_by_severity": counts,
        "items": items,
    }


def _version_payload() -> dict:
    return {
        "service": "notifications-api",
        "version": API_VERSION,
        "module": "notifications",
        "providers": [p.__name__ for p in PROVIDERS],
        "severity_vocabulary": ["down", "attention"],
        "surfaces": ["core", "api"],
        "standing_rule": "read-only inbox; providers degrade, never fabricate. Outbound fan-out is opt-in (notifications-emit.py).",
    }


class NotificationsAPIHandler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-notifications-api/{API_VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Sovereign-Module", "notifications-api")
        self.send_header("X-Sovereign-Version", API_VERSION)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urllib.parse.urlsplit(self.path).path.rstrip("/") or "/"
        if path in ("/", "/healthz"):
            self._send_json(200, {"status": "ok", "version": API_VERSION})
            _emit_metric("healthz" if path == "/healthz" else "root", "ok")
            return
        try:
            if path == "/version":
                self._send_json(200, _version_payload())
                _emit_metric("version", "ok")
                return
            if path == "/api/notifications":
                self._send_json(200, collect())
                _emit_metric("notifications", "ok")
                return
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
            _emit_metric(path.lstrip("/") or "unknown", "500")
            return
        self._send_json(404, {
            "error": f"unknown endpoint: {path!r}",
            "available": ["/api/notifications", "/version", "/healthz"],
        })
        _emit_metric(path.lstrip("/") or "unknown", "404")

    def do_HEAD(self) -> None:  # noqa: N802
        self._send_json(200, {"status": "ok"})

    def _reject(self) -> None:
        self._send_json(405, {
            "error": "read-only inbox — items are aggregated from live state; "
                     "outbound fan-out is opt-in via notifications-emit.py",
            "allowed": ["GET", "HEAD"],
        })
        _emit_metric(self.command.lower(), "405")

    def do_POST(self):    self._reject()  # noqa: E704 N802
    def do_PUT(self):     self._reject()  # noqa: E704 N802
    def do_DELETE(self):  self._reject()  # noqa: E704 N802


def serve(bind: str = API_BIND, port: int = API_PORT) -> int:
    print(f"[*] notifications-api {API_VERSION} on http://{bind}:{port}/", flush=True)
    httpd = ThreadingHTTPServer((bind, port), NotificationsAPIHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] shutting down", flush=True)
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="notifications read-only aggregation API")
    p.add_argument("--bind", default=API_BIND)
    p.add_argument("--port", type=int, default=API_PORT)
    p.add_argument("--self-check", action="store_true", help="build one rollup, print it, and exit 0 (CI smoke)")
    args = p.parse_args(argv)
    if args.self_check or DRY_RUN:
        print(json.dumps({"config": _version_payload(), "sample_rollup": collect()}, indent=2))
        return 0
    return serve(args.bind, args.port)


if __name__ == "__main__":
    sys.exit(main())
