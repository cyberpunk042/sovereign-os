#!/usr/bin/env python3
"""scripts/operator/_api_daemon.py — shared read-only loopback JSON+webapp
daemon scaffold (F-2026-070).

The F-2026-070 audit found the "networking triplet" is NOT a fork to merge —
network-edge-api.py and edge-firewall-api.py are concern-distinct daemons whose
domain surfaces (endpoints, payloads, ports, units, panels) are genuinely
different, and d-12-networking is an unrelated master-dashboard tile. The ONE
real duplication was the ~170-line HTTP daemon scaffold each carried verbatim:
the metric emitter, the BaseHTTPRequestHandler boilerplate (log_message /
_send_json / _send_webapp / do_HEAD / the mutation-reject quartet), and serve().
That scaffold is in fact repeated across ~30 sovereign-*-api daemons, so this is
the "fix it at the root" dedup — each daemon keeps its own identity, port, unit,
routes, and 405 message; only the mechanical HTTP plumbing lives here.

Doctrine-preserving:
  * stdlib-only (http.server), zero added deps;
  * loopback-bind by default; a non-loopback bind prints the explicit operator
    warning exactly as before;
  * read-only — every mutating method returns the daemon's own 405 message;
  * every response carries the same X-Sovereign-Module / -Version + framing
    headers the hand-written daemons emitted.

A daemon builds a `DaemonSpec` with its module-specific values and calls
`serve(spec, bind, port)`. Routes map a path to `(metric_label, fn)` where
`fn(query: dict) -> (status: int, payload: dict)` — a plain GET returns
`(200, payload)`, and a richer endpoint (edge-firewall's /install-plan) returns
`(400|404|200, payload)` from the same signature, so both daemons' behavior is
expressed without special-casing.
"""
from __future__ import annotations

import json
import os
import urllib.parse
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable
import sys

# The set of paths (after rstrip('/')) that serve the single-file webapp.
_WEBAPP_PATHS = {"/webapp", "/webapp/index.html"}


@dataclass
class DaemonSpec:
    """Everything module-specific for one read-only API daemon."""
    module: str                      # e.g. "network-edge-api"
    webapp_module: str               # e.g. "network-edge-webapp"
    version: str
    metric_name: str
    prom_basename: str               # e.g. "sovereign-os-network-edge-api.prom"
    metrics_dir: str
    webapp_path: os.PathLike | str
    data_source: str                 # path to the backing core module (banner)
    endpoints_line: str              # serve() banner "endpoints: ..." line
    reject_error: str                # the 405 error message body
    available: list[str]             # the 404 "available" endpoint list
    # path -> (metric_label, fn(query)->(status, payload))
    routes: dict[str, tuple[str, Callable[[dict], tuple[int, dict]]]]
    is_dry_run: Callable[[], bool]   # reads the daemon's live DRY_RUN
    extra_banner: list[str] = field(default_factory=list)

    def emit(self, endpoint: str, result: str) -> None:
        """Best-effort textfile-collector metric emit (Layer B, SDD-016)."""
        if self.is_dry_run():
            sys.stderr.write(
                f"  would emit: {self.metric_name}"
                f'{{endpoint="{endpoint}",result="{result}"}} 1\n'
            )
            return
        try:
            os.makedirs(self.metrics_dir, exist_ok=True)
            prom_path = os.path.join(self.metrics_dir, self.prom_basename)
            line = (
                f'{self.metric_name}{{endpoint="{endpoint}",'
                f'result="{result}"}} 1\n'
            )
            with open(prom_path, "a") as f:
                f.write(line)
        except OSError:
            pass


def _err_label(path: str) -> str:
    return path.lstrip("/").replace("-", "_").replace("/", "_") or "unknown"


def make_handler(spec: DaemonSpec) -> type[BaseHTTPRequestHandler]:
    """Build the BaseHTTPRequestHandler subclass bound to `spec`."""

    class _Handler(BaseHTTPRequestHandler):
        server_version = f"sovereign-os-{spec.module}/{spec.version}"
        sys_version = ""  # don't leak the Python version to clients

        def log_message(self, fmt: str, *args) -> None:  # noqa: A002
            sys.stderr.write(f"[api] {self.address_string()} {fmt % args}\n")

        def _send_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Sovereign-Module", spec.module)
            self.send_header("X-Sovereign-Version", spec.version)
            self.end_headers()
            self.wfile.write(body)

        def _send_webapp(self) -> None:
            try:
                body = os.fspath(spec.webapp_path)
                data = open(body, "rb").read()
            except OSError as e:
                self._send_json(500, {
                    "error": f"webapp asset unreadable: {e}",
                    "expected_path": str(spec.webapp_path),
                })
                spec.emit("webapp", "500")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Sovereign-Module", spec.webapp_module)
            self.send_header("X-Sovereign-Version", spec.version)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(data)
            spec.emit("webapp", "ok")

        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlsplit(self.path)
            path = parsed.path.rstrip("/") or "/"
            query = urllib.parse.parse_qs(parsed.query)

            if path == "/healthz" or path == "/":
                self._send_json(200, {"status": "ok", "version": spec.version})
                spec.emit("healthz" if path == "/healthz" else "root", "ok")
                return

            if path in _WEBAPP_PATHS:
                self._send_webapp()
                return

            route = spec.routes.get(path)
            if route is not None:
                label, fn = route
                try:
                    status, payload = fn(query)
                except Exception as e:  # noqa: BLE001
                    self._send_json(500, {"error": str(e)})
                    spec.emit(label, "500")
                    return
                self._send_json(status, payload)
                spec.emit(label, "ok" if status == 200 else str(status))
                return

            self._send_json(404, {
                "error": f"unknown endpoint: {path!r}",
                "available": spec.available,
            })
            spec.emit(_err_label(path), "404")

        def do_HEAD(self) -> None:  # noqa: N802
            self.do_GET()

        def do_POST(self):    self._reject_mutation()   # noqa: E704 N802
        def do_PUT(self):     self._reject_mutation()   # noqa: E704 N802
        def do_DELETE(self):  self._reject_mutation()   # noqa: E704 N802
        def do_PATCH(self):   self._reject_mutation()   # noqa: E704 N802

        def _reject_mutation(self) -> None:
            self._send_json(405, {
                "error": spec.reject_error,
                "allowed": ["GET", "HEAD"],
            })
            spec.emit(self.command.lower(), "405")

    return _Handler


def serve(spec: DaemonSpec, bind: str, port: int) -> int:
    """Run the daemon (or validate + exit under dry-run)."""
    print(f"[*] {spec.module} {spec.version} listening on "
          f"http://{bind}:{port}/", flush=True)
    print(f"  data source: {spec.data_source}", flush=True)
    print(f"  endpoints:   {spec.endpoints_line}", flush=True)
    for extra in spec.extra_banner:
        print(extra, flush=True)
    if bind != "127.0.0.1":
        print(f"  WARNING: bind={bind!r} is NOT loopback — operator "
              f"explicitly exposed this surface beyond the host.", flush=True)
    if spec.is_dry_run():
        print("  DRY-RUN: configuration validated, not serving.", flush=True)
        return 0

    try:
        httpd = HTTPServer((bind, port), make_handler(spec))
    except OSError as e:
        sys.stderr.write(
            f"[FATAL STRUCTURAL FRICTION] cannot bind {bind}:{port} — {e}\n"
        )
        return 1

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"\n[*] {spec.module} shutdown requested.", flush=True)
        httpd.server_close()
        return 0
