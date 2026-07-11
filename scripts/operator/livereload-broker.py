#!/usr/bin/env python3
"""scripts/operator/livereload-broker.py — dev live-reload broker (SDD-203, R559).

ONE lightweight file-watcher for the whole panel fleet. `make panel` starts it
on 127.0.0.1:8136; every open panel connects to it over Server-Sent Events and,
on a *real* change to something that panel depends on, is offered a refresh
(bottom-centre toast — see the live-reload client in
webapp/_shared/app-shell-snippet.html).

Why this shape:
  * Performant — a SINGLE mtime scan of webapp/ + scripts/ + config/ covers all
    ~50 panels, instead of one watcher per daemon. Event-driven SSE downstream:
    the browser does nothing until a change actually lands.
  * "Never for nothing" — each panel is notified ONLY for paths it depends on:
    its own webapp/<slug>/, the shared chrome (webapp/_shared/), its data
    daemon's source, and the scripts/config that daemon shells out to (parsed
    once from the daemon at startup). An unrelated edit stays silent.
  * No restart for the common case — panel daemons read their HTML fresh and
    re-run shelled scripts per request, so a static/script edit needs only a
    browser refresh. The daemon's OWN .py is reloaded in place, with no kill,
    by scripts/operator/lib/reload-run.py.

Read-only + loopback-only: this daemon watches files and streams change notices;
it never writes, never executes, never leaves 127.0.0.1. It is a DEV tool — it
is not shipped/enabled in the image (only `make panel` launches it).

Endpoints:
  GET /events[?panel=<slug>][&port=<n>]  — SSE stream; `event: reload` per change
  GET /healthz                           — liveness (always 200 {"ok":true})

Env:
  SOVEREIGN_OS_LIVERELOAD_PORT      bind port (default 8136)
  SOVEREIGN_OS_LIVERELOAD_POLL_MS   scan interval (default 700)
"""
from __future__ import annotations

import json
import os
import queue
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEBAPP = REPO / "webapp"
WATCH_ROOTS = [WEBAPP, REPO / "scripts", REPO / "config"]
WATCH_EXT = {".html", ".css", ".js", ".json", ".py", ".sh",
             ".yaml", ".yml", ".toml", ".md", ".env"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv",
             "dist", "build", ".mypy_cache", ".pytest_cache", ".ruff_cache"}

PORT = int(os.environ.get("SOVEREIGN_OS_LIVERELOAD_PORT", "8136"))
POLL_S = max(0.2, int(os.environ.get("SOVEREIGN_OS_LIVERELOAD_POLL_MS", "700")) / 1000.0)

# Regexes for one-time daemon introspection (stdlib-only, no YAML needed).
_WEBAPP_SLUG_RE = re.compile(r'["\']webapp["\']\s*/\s*["\']([a-z0-9][a-z0-9-]*)["\']')
_WEBAPP_PATH_RE = re.compile(r'webapp/([a-z0-9][a-z0-9-]*)/')
_PORT_RE = re.compile(r'_API_PORT["\']\s*,\s*["\'](\d{3,5})["\']')
_DEP_RE = re.compile(r'\b((?:scripts|config)/[A-Za-z0-9_][A-Za-z0-9_./-]*'
                     r'\.(?:py|sh|ya?ml|toml|json))')


class Registry:
    """Panel → dependency-set + port → slug maps, built once from the daemons."""

    def __init__(self) -> None:
        self.panels: set[str] = set()          # slugs that own a webapp/<slug>/
        self.slug_deps: dict[str, set[str]] = {}  # slug → repo-relative dep paths
        self.port_slug: dict[int, str] = {}    # own-port → slug
        self._build()

    def _rel(self, p: Path) -> str:
        try:
            return p.resolve().relative_to(REPO).as_posix()
        except ValueError:
            return p.as_posix()

    def _build(self) -> None:
        if WEBAPP.is_dir():
            for d in WEBAPP.iterdir():
                if d.is_dir() and (d / "index.html").is_file():
                    self.panels.add(d.name)
        op = REPO / "scripts" / "operator"
        for daemon in sorted(op.glob("*-api.py")):
            try:
                text = daemon.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            m = _WEBAPP_SLUG_RE.search(text) or _WEBAPP_PATH_RE.search(text)
            slug = m.group(1) if m else daemon.name[:-len("-api.py")]
            deps = set(_DEP_RE.findall(text))
            deps.add(self._rel(daemon))
            self.slug_deps.setdefault(slug, set()).update(deps)
            pm = _PORT_RE.search(text)
            if pm:
                self.port_slug[int(pm.group(1))] = slug

    def resolve(self, panel: str, port: str) -> str | None:
        """Map a connecting page to its canonical panel slug (or None → fail-open)."""
        if panel and panel in self.panels:
            return panel
        if panel and panel in self.slug_deps:
            return panel
        try:
            p = int(port)
        except (TypeError, ValueError):
            p = None
        if p is not None and p in self.port_slug:
            return self.port_slug[p]
        return None

    def relevant(self, slug: str | None, changed: list[str]) -> bool:
        """Is any changed repo-relative path something `slug` depends on?"""
        for path in changed:
            if path.startswith("webapp/_shared/"):
                return True  # shared chrome → every panel
            if slug is None:
                # Unknown page: fail-open on any watched source change so the
                # operator is never silently left on stale code.
                return True
            if path.startswith(f"webapp/{slug}/"):
                return True
            if path in self.slug_deps.get(slug, ()):  # its daemon + shelled deps
                return True
        return False


class Hub:
    """Fan-out of change events to connected SSE clients."""

    def __init__(self, registry: Registry) -> None:
        self.registry = registry
        self._clients: list[dict] = []
        self._lock = threading.Lock()
        self._epoch = 0

    def add(self, slug: str | None) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=64)
        with self._lock:
            self._clients.append({"q": q, "slug": slug})
        return q

    def remove(self, q: queue.Queue) -> None:
        with self._lock:
            self._clients = [c for c in self._clients if c["q"] is not q]

    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)

    def dispatch(self, changed: list[str]) -> None:
        self._epoch += 1
        payload = json.dumps({
            "epoch": self._epoch,
            "count": len(changed),
            "paths": changed[:8],
        })
        with self._lock:
            targets = list(self._clients)
        for c in targets:
            if self.registry.relevant(c["slug"], changed):
                try:
                    c["q"].put_nowait(payload)
                except queue.Full:
                    pass  # slow client — it will catch up on the next event


HUB = None  # type: ignore[assignment]  # a Hub instance, set in main()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # quiet loopback daemon
        pass

    def _cors_origin(self) -> str:
        origin = self.headers.get("Origin", "")
        return origin if origin.startswith("http://127.0.0.1:") \
            or origin.startswith("http://localhost:") else "*"

    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path == "/healthz":
            body = json.dumps({"ok": True, "clients": HUB.client_count()}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        if path == "/events":
            return self._events()
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _query(self) -> dict[str, str]:
        from urllib.parse import parse_qs, urlparse
        return {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}

    def _events(self):
        q = self._query()
        slug = HUB.registry.resolve(q.get("panel", ""), q.get("port", ""))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", self._cors_origin())
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        client_q = HUB.add(slug)
        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while True:
                try:
                    payload = client_q.get(timeout=20.0)
                    frame = f"event: reload\ndata: {payload}\n\n".encode()
                except queue.Empty:
                    frame = b": ping\n\n"  # heartbeat / dead-socket probe
                self.wfile.write(frame)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass  # client navigated away / refreshed
        finally:
            HUB.remove(client_q)


def _scan() -> dict[str, float]:
    """Repo-relative path → mtime for every watched source file."""
    out: dict[str, float] = {}
    for root in WATCH_ROOTS:
        if not root.is_dir():
            continue
        stack = [root]
        while stack:
            d = stack.pop()
            try:
                entries = list(os.scandir(d))
            except OSError:
                continue
            for e in entries:
                if e.name.startswith(".") and e.name not in (".env",):
                    if e.is_dir(follow_symlinks=False):
                        continue
                try:
                    if e.is_dir(follow_symlinks=False):
                        if e.name not in SKIP_DIRS:
                            stack.append(Path(e.path))
                        continue
                    if os.path.splitext(e.name)[1] not in WATCH_EXT:
                        continue
                    rel = os.path.relpath(e.path, REPO)
                    out[rel] = e.stat().st_mtime
                except OSError:
                    continue
    return out


def _watch_loop() -> None:
    prev = _scan()  # baseline — startup state never fires an event
    while True:
        time.sleep(POLL_S)
        try:
            cur = _scan()
        except Exception:  # noqa: BLE001 — a transient FS error must not kill the loop
            continue
        changed = [p for p, m in cur.items()
                   if p not in prev or m > prev[p] + 1e-6]
        changed += [p for p in prev if p not in cur]  # deletions
        prev = cur
        if changed and HUB.client_count():
            HUB.dispatch(sorted(set(changed)))


def main() -> int:
    global HUB
    registry = Registry()
    HUB = Hub(registry)
    threading.Thread(target=_watch_loop, name="livereload-watch",
                     daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    srv.daemon_threads = True
    sys.stderr.write(
        f"[livereload-broker] watching {len(registry.slug_deps)} daemons / "
        f"{len(registry.panels)} panels on 127.0.0.1:{PORT} "
        f"(poll {int(POLL_S * 1000)}ms)\n")
    sys.stderr.flush()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
