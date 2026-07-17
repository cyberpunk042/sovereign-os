#!/usr/bin/env python3
"""scripts/operator/lib/request_guard.py — shared request-authenticity guard
for the loopback operator daemons (F-2026-1xx CSRF/RCE hardening, 2026-07-17).

Several operator daemons expose privileged POST endpoints (jobs-api runs an
argv as root; build-configurator triggers a root OS build; flash-api writes a
USB device). They are meant to be reached only by the loopback osctl /
control-exec path, never a browser — but `_body()`-style handlers parse JSON
regardless of Content-Type, so before this guard a web page the operator
visited could drive them cross-origin (a "simple request" CSRF). This module
is the one place that decides whether a mutating request is authentic.

`guard()` is PURE over (headers, peer, flags) so it is unit-testable without a
live socket. The machine callers (osctl, the gateway, the VM bridge) send NO
Origin/Referer and connect over loopback, so they pass unchanged.
"""
from __future__ import annotations

import os
import urllib.parse


def is_loopback(host: str) -> bool:
    h = (host or "").strip().strip("[]")
    return h.startswith("127.") or h in ("::1", "localhost", "::ffff:127.0.0.1")


def origin_host(value: str) -> str:
    """Host of an Origin/Referer header value ('http://h:port/...' → 'h')."""
    try:
        return urllib.parse.urlsplit(value).hostname or ""
    except ValueError:
        return ""


def _allow_nonloopback() -> bool:
    return os.environ.get("SOVEREIGN_OS_OPERATOR_ALLOW_NONLOOPBACK") == "1"


def guard(headers, client_host: str, *, require_json: bool = True,
          allow_nonloopback: bool | None = None) -> tuple[int, str] | None:
    """Return (code, reason) to REFUSE a mutating request, or None to allow.

    Universal checks:
      * peer must be loopback (defense if a bind.conf exposes the port);
      * a cross-site Origin/Referer means a browser drove it → refuse;
      * when require_json, Content-Type must be application/json — this forces
        a CORS preflight for any cross-origin caller, which the daemon (no CORS
        headers) can never complete, closing the browser simple-request vector.
    """
    if allow_nonloopback is None:
        allow_nonloopback = _allow_nonloopback()
    if not allow_nonloopback and not is_loopback(client_host):
        return 403, "non-loopback peer refused"
    for h in ("Origin", "Referer"):
        v = headers.get(h)
        if v and not is_loopback(origin_host(v)):
            return 403, f"cross-site {h} refused (browser CSRF)"
    if require_json:
        ctype = (headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if ctype != "application/json":
            return 415, "this endpoint requires Content-Type: application/json"
    return None
