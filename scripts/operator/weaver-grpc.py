#!/usr/bin/env python3
"""scripts/operator/weaver-grpc.py — Weaver gRPC state-sync broadcast server.

E107 closure: implements the WeaverStateService gRPC contract from
proto/weaver_state.proto. Sub-agents subscribe to a stream of
StateSynced events that fire whenever IDENTITY.md / SOUL.md /
AGENTS.md / CLAUDE.md change.

Transport:
  - Primary: gRPC streaming (WeaverStateService.SubscribeStateChanges)
  - Fallback: HTTP SSE (Server-Sent Events) on /events if grpcio or
    generated proto modules are unavailable.

State detection:
  - Polls mtimes of the 4 state files every 2 seconds (no extra deps).
  - Also accepts push notifications via POST /_notify (atomic-state.py
    uses this for lower latency).

Env vars:
  WEAVER_GRPC_BIND        (default: 127.0.0.1:8103)
  WEAVER_CONTEXT_DIR      (default: /mnt/vault/context)
  WEAVER_GRPC_DRY_RUN     print intent + exit 0
"""
from __future__ import annotations

import http.server
import json
import os
import sys
import threading
import time
import urllib.parse
from pathlib import Path

# ---------------------------------------------------------------------------
# Optional grpcio import — the server degrades to HTTP SSE if unavailable
# ---------------------------------------------------------------------------
try:
    import grpc
    from proto import weaver_state_pb2, weaver_state_pb2_grpc
    _GRPC_AVAILABLE = True
except ImportError:
    _GRPC_AVAILABLE = False

BIND = os.environ.get("WEAVER_GRPC_BIND", "127.0.0.1:8103")
DRY_RUN = bool(os.environ.get("WEAVER_GRPC_DRY_RUN"))
CONTEXT_DIR = Path(os.environ.get("WEAVER_CONTEXT_DIR", "/mnt/vault/context"))
STATE_FILES = ("IDENTITY.md", "SOUL.md", "AGENTS.md", "CLAUDE.md")
POLL_INTERVAL = 2.0  # seconds

# Thread-safe subscriber queue for SSE fallback
_sse_subscribers: list[http.server.BaseHTTPRequestHandler] = []
_sse_lock = threading.Lock()

# In-memory last-known mtimes
_last_mt: dict[str, float | None] = {fn: None for fn in STATE_FILES}


def _hash_file(path: Path) -> str:
    import hashlib
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _poll_once() -> list[dict]:
    """Check mtimes; return list of changed-file events."""
    events = []
    for fn in STATE_FILES:
        p = CONTEXT_DIR / fn
        try:
            mtime = p.stat().st_mtime
        except OSError:
            mtime = None
        prev = _last_mt[fn]
        if prev is not None and mtime is not None and mtime != prev:
            events.append({
                "file_name": fn,
                "change_timestamp": int(mtime),
                "content_sha256": _hash_file(p),
                "trigger": "filesystem poll",
            })
        _last_mt[fn] = mtime
    return events


def _broadcast(event: dict) -> None:
    """Push event to all SSE subscribers and gRPC streams."""
    # SSE fallback
    with _sse_lock:
        dead = []
        for handler in _sse_subscribers:
            try:
                payload = json.dumps(event) + "\n\n"
                handler.wfile.write(payload.encode("utf-8"))
                handler.wfile.flush()
            except (OSError, BrokenPipeError):
                dead.append(handler)
        for d in dead:
            _sse_subscribers.remove(d)
    # gRPC streams
    if _GRPC_AVAILABLE:
        _grpc_broadcast(event)


# ---------------------------------------------------------------------------
# gRPC service (only when grpcio + generated modules available)
# ---------------------------------------------------------------------------
_grpc_streams: list[grpc.ServicerContext] = []
_grpc_stream_lock = threading.Lock()


def _grpc_broadcast(event: dict) -> None:
    if not _GRPC_AVAILABLE:
        return
    msg = weaver_state_pb2.StateSynced(
        file_name=event["file_name"],
        change_timestamp=event["change_timestamp"],
        content_sha256=event["content_sha256"],
        trigger=event["trigger"],
    )
    with _grpc_stream_lock:
        dead = []
        for ctx in _grpc_streams:
            try:
                ctx.write(msg)
            except Exception:
                dead.append(ctx)
        for d in dead:
            _grpc_streams.remove(d)


class WeaverStateServicer(weaver_state_pb2_grpc.WeaverStateServiceServicer):
    def SubscribeStateChanges(self, request, context):
        if not _GRPC_AVAILABLE:
            context.abort(grpc.StatusCode.UNIMPLEMENTED, "grpcio unavailable")
            return
        with _grpc_stream_lock:
            _grpc_streams.append(context)
        try:
            while context.is_active():
                time.sleep(0.5)
        finally:
            with _grpc_stream_lock:
                if context in _grpc_streams:
                    _grpc_streams.remove(context)


# ---------------------------------------------------------------------------
# HTTP fallback + notification receiver
# ---------------------------------------------------------------------------
class WeaverHTTPHandler(http.server.BaseHTTPRequestHandler):
    server_version = "sovereign-os-weaver-grpc/0.1"
    sys_version = ""

    def log_message(self, format: str, *args) -> None:
        sys.stderr.write(f"[weaver-grpc] {format % args}\n")

    def do_POST(self) -> None:
        if self.path == "/_notify":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            try:
                event = json.loads(body)
                _broadcast(event)
                self.send_response(204)
                self.end_headers()
            except json.JSONDecodeError:
                self.send_response(400)
                self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            with _sse_lock:
                _sse_subscribers.append(self)
            try:
                while True:
                    time.sleep(1)
            except (OSError, BrokenPipeError):
                pass
            finally:
                with _sse_lock:
                    if self in _sse_subscribers:
                        _sse_subscribers.remove(self)
            return
        if self.path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "grpc_ready": _GRPC_AVAILABLE}).encode())
            return
        self.send_response(404)
        self.end_headers()


def _poller() -> None:
    """Background thread: poll mtimes and broadcast changes."""
    # Initialize mtimes
    for fn in STATE_FILES:
        p = CONTEXT_DIR / fn
        try:
            _last_mt[fn] = p.stat().st_mtime
        except OSError:
            _last_mt[fn] = None
    while True:
        time.sleep(POLL_INTERVAL)
        for ev in _poll_once():
            _broadcast(ev)


def serve() -> int:
    host, port_str = BIND.rsplit(":", 1)
    port = int(port_str)

    print(f"[*] weaver-grpc listening on {BIND}", flush=True)
    print(f"  context dir: {CONTEXT_DIR}", flush=True)
    print(f"  grpc ready:  {_GRPC_AVAILABLE}", flush=True)

    if DRY_RUN:
        print("  DRY-RUN: not starting servers.", flush=True)
        return 0

    # Start mtime poller
    threading.Thread(target=_poller, daemon=True, name="weaver-poller").start()

    # Start gRPC server if available
    if _GRPC_AVAILABLE:
        grpc_server = grpc.server(threading.ThreadPoolExecutor(max_workers=10))
        weaver_state_pb2_grpc.add_WeaverStateServiceServicer_to_server(
            WeaverStateServicer(), grpc_server
        )
        grpc_server.add_insecure_port(BIND)
        grpc_server.start()
        print("  gRPC service started.", flush=True)
    else:
        # Fallback: HTTP SSE server on the same bind
        print("  grpcio unavailable; falling back to HTTP SSE on /events", flush=True)
        httpd = http.server.HTTPServer((host, port), WeaverHTTPHandler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] weaver-grpc shutdown.", flush=True)
        if _GRPC_AVAILABLE:
            grpc_server.stop(5)
    return 0


if __name__ == "__main__":
    sys.exit(serve())
