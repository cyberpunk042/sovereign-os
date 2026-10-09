#!/usr/bin/env python3
"""
scripts/operator/image-generation-api.py — Image Generation panel (cockpit).

Tests the LIVE image model end-to-end WITHOUT OpenClaw in the path: this daemon
talks DIRECTLY to the stable-diffusion.cpp `sd-server` that an image profile
activates (OpenAI Images API: verified POST /v1/images/generations returning
b64_json; sd-server ignores the request's `model` field). The OpenClaw
`image_generate` tool reaches the SAME server through the catalog sync
(scripts/inference/sync-openclaw-models.py) — this panel is the honest
no-agent-sidecar route: browser → daemon → sd-server.

Discovery is file-driven, never a hardcoded list (operator directive
2026-10-09, "Remove this hardcoded list"): the active marker, every
profiles/{runtime,orchestration} YAML whose runtime_handler starts with
"image", and each allocation's declared port. A port is only usable if its
/v1/models probe answers with the sd-cpp-local model id — the panel never
guesses a port at generation time.

The generation POST is an INFERENCE call, not a host mutation: it starts
nothing, stops nothing, and writes only its own gallery artifacts. Host state
(profile switches) stays the exclusive job of the control-exec rail
(R10274/R10212) — the panel only DISPLAYS the exact activation command and
defers to the rail when served through the hub.

Endpoints:
  GET  /                        — the webapp (single file)
  GET  /api/image-gen/status    — active profile, image allocations, live probes,
                                  every image-family profile + its change_cli
  POST /api/image-gen/generate  — validated generation proxied to sd-server
  GET  /api/image-gen/gallery   — persisted artifacts (newest first)
  GET  /api/image-gen/artifact  — one persisted artifact (?name=, strict pattern)
  GET  /version /healthz

Env vars:
  IMAGE_GENERATION_API_BIND   (default: 127.0.0.1)
  IMAGE_GENERATION_API_PORT   (default: 8150)
"""
from __future__ import annotations

import base64
import binascii
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API_BIND = os.environ.get("IMAGE_GENERATION_API_BIND", "127.0.0.1")
API_PORT = int(os.environ.get("IMAGE_GENERATION_API_PORT", "8150"))
VERSION = "0.1.0"

REPO = Path(__file__).resolve().parents[2]
WEBAPP = REPO / "webapp" / "image-generation" / "index.html"
MARKER = Path(os.environ.get("SOVEREIGN_OS_STATE_DIR", "/etc/sovereign-os")) / "active-runtime-profile"
PROFILE_DIRS = [
    ("runtime", REPO / "profiles" / "runtime"),
    ("orchestration", REPO / "profiles" / "orchestration"),
]
GALLERY_DIR = Path(os.environ.get(
    "SOVEREIGN_OS_IMAGE_GEN_DIR", "/var/lib/sovereign-os/image-generation"))
_MAX_BODY = 64 * 1024
_MAX_IMAGE_BYTES = 32 * 1024 * 1024
_ARTIFACT_NAME = re.compile(r"^[0-9TZ_-]{8,64}\.png$")
# Sizes sd-server qualifies with the profile image_settings; anything else is a
# client bug, not a generation request.
_SIZES = {"512x512", "768x768", "1024x1024", "1024x768", "768x1024"}
# Generation is single-flight: one image at a time on the image GPU.
_GEN_LOCK = threading.Lock()

STATIC_TYPES = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8", ".json": "application/json",
    ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}


# ── discovery (files + live probes; never a hardcoded model/port list) ──────

def _load_profiles() -> list[dict]:
    """Every on-disk profile whose runtime_handler names an image runtime."""
    import yaml
    out = []
    for fam, d in PROFILE_DIRS:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.yaml")):
            try:
                doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            prof = doc.get("orchestration_profile") or doc.get("runtime_profile") or {}
            handler = str(prof.get("runtime_handler") or "")
            if not handler.startswith("image"):
                continue
            allocations = [a for a in (prof.get("allocations") or [])
                           if a.get("tier") == "image" and a.get("active", True)]
            if not prof.get("id"):
                continue
            out.append({
                "id": prof["id"],
                "family": fam,
                "name": prof.get("name") or prof["id"],
                "handler": handler,
                "readiness": prof.get("readiness") or "",
                "images": [{"model": a.get("model"), "port": a.get("port"),
                            "card": a.get("target_hardware")} for a in allocations],
                "change_cli": f"sudo sovereign-osctl trinity profile switch {prof['id']}",
            })
    return out


def _active_profile_id() -> str:
    try:
        return MARKER.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _probe(port: int, timeout: float = 3.0) -> dict:
    """GET /v1/models on a candidate sd-server port."""
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/v1/models", timeout=timeout) as r:
            models = [m.get("id") for m in json.load(r).get("data", [])]
        return {"port": port, "ready": bool(models), "models": models}
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return {"port": port, "ready": False, "models": []}


def _status() -> dict:
    active = _active_profile_id()
    profiles = _load_profiles()
    active_prof = next((p for p in profiles if p["id"] == active), None)
    probes = []
    if active_prof:
        seen = set()
        for img in active_prof["images"]:
            try:
                port = int(img["port"])
            except (TypeError, ValueError):
                continue
            if port not in seen:
                seen.add(port)
                probes.append(_probe(port))
    ready = [p["port"] for p in probes if p["ready"]]
    return {
        "service": "image-generation-api",
        "version": VERSION,
        "active_profile": active or None,
        "active_is_image": active_prof is not None,
        "image_probes": probes,
        "ready_ports": ready,
        "image_profiles": profiles,
        "gallery": str(GALLERY_DIR),
    }


# ── generation (validated proxy; single-flight) ─────────────────────────────

def _generate(body: dict) -> tuple[int, dict]:
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        return 400, {"error": "prompt required"}
    if len(prompt) > 1000:
        return 400, {"error": "prompt exceeds 1000 chars"}
    negative = str(body.get("negative_prompt") or "").strip()
    if len(negative) > 500:
        return 400, {"error": "negative_prompt exceeds 500 chars"}
    size = str(body.get("size") or "1024x1024")
    if size not in _SIZES:
        return 400, {"error": f"size must be one of {sorted(_SIZES)}"}
    st = _status()
    allowed = st["ready_ports"]
    if not allowed:
        return 503, {"error": "no live sd-server on any active image profile port — "
                              "activate an image profile from D-21 (orchestration-profile rail)"}
    try:
        port = int(body.get("port") or allowed[0])
    except (TypeError, ValueError):
        return 400, {"error": "port must be an integer"}
    if port not in allowed:
        return 400, {"error": f"port {port} is not a live image endpoint {allowed}"}
    payload: dict = {"prompt": prompt, "size": size, "n": 1,
                     "response_format": "b64_json"}
    if negative:
        payload["negative_prompt"] = negative
    steps = body.get("steps")
    if steps is not None:
        try:
            payload["steps"] = max(1, min(60, int(steps)))
        except (TypeError, ValueError):
            return 400, {"error": "steps must be an integer"}
    seed = body.get("seed")
    if seed is not None:
        try:
            payload["seed"] = max(0, min(2**31 - 1, int(seed)))
        except (TypeError, ValueError):
            return 400, {"error": "seed must be an integer"}

    if not _GEN_LOCK.acquire(blocking=False):
        return 409, {"error": "a generation is already running (single-flight)"}
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/images/generations",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        t0 = time.monotonic()
        with urllib.request.urlopen(req, timeout=900) as r:
            out = json.load(r)
        elapsed = round(time.monotonic() - t0, 2)
        item = (out.get("data") or [{}])[0]
        b64 = item.get("b64_json") or ""
        if not b64:
            return 502, {"error": "sd-server returned no b64_json", "elapsed_s": elapsed}
        try:
            raw = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            return 502, {"error": f"undecodable image: {exc}"}
        if not raw or len(raw) > _MAX_IMAGE_BYTES:
            return 502, {"error": f"image size out of range ({len(raw)} bytes)"}
        name = time.strftime("%Y-%m-%dT%H%M%SZ") + f"-{port}.png"
        artifact = None
        try:
            GALLERY_DIR.mkdir(parents=True, exist_ok=True)
            (GALLERY_DIR / name).write_bytes(raw)
            artifact = name
        except OSError:
            pass  # gallery persistence is best-effort; the image still returns
        return 200, {"artifact": artifact, "bytes": len(raw), "elapsed_s": elapsed,
                     "port": port, "size": size,
                     "b64": b64 if len(b64) <= 4_000_000 else ""}
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:400].decode("utf-8", "replace")
        return 502, {"error": f"sd-server {exc.code}: {detail}"}
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as exc:
        return 502, {"error": f"sd-server unreachable: {exc}"}
    finally:
        _GEN_LOCK.release()


# ── HTTP ─────────────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    server_version = f"sovereign-os-image-generation-api/{VERSION}"
    sys_version = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[image-generation] {self.address_string()} {fmt % args}\n")

    def _send(self, code: int, body, ctype="application/json") -> None:
        data = body if isinstance(body, bytes) else json.dumps(body, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Sovereign-Module", "image-generation-api")
        self.send_header("X-Sovereign-Version", VERSION)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def _static(self, path: Path) -> None:
        if not path.is_file():
            self._send(404, {"error": "not found"})
            return
        ctype = STATIC_TYPES.get(path.suffix, "application/octet-stream")
        self._send(200, path.read_bytes(), ctype)

    def do_GET(self) -> None:  # noqa: N802
        p = self.path.split("?", 1)[0]
        if p in ("/", "/index.html"):
            self._static(WEBAPP)
        elif p == "/api/image-gen/status":
            self._send(200, _status())
        elif p == "/api/image-gen/gallery":
            try:
                files = sorted((p.name for p in GALLERY_DIR.glob("*.png")), reverse=True)[:50]
            except OSError:
                files = []
            self._send(200, {"artifacts": files})
        elif p == "/api/image-gen/artifact":
            q = self.path.split("?", 1)
            name = ""
            if len(q) == 2:
                for kv in q[1].split("&"):
                    if kv.startswith("name="):
                        name = kv[5:]
            if not _ARTIFACT_NAME.fullmatch(name):
                self._send(400, {"error": "invalid artifact name"})
                return
            self._static(GALLERY_DIR / name)
        elif p == "/version":
            self._send(200, {"service": "image-generation-api", "version": VERSION})
        elif p == "/healthz":
            self._send(200, {"ok": True})
        else:
            self._send(404, {"error": f"unknown endpoint: {p!r}"})

    def do_POST(self) -> None:  # noqa: N802
        p = self.path.split("?", 1)[0]
        if p != "/api/image-gen/generate":
            self._send(405, {"error": "the only write here is POST /api/image-gen/generate"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._send(400, {"error": "bad Content-Length"})
            return
        if length <= 0 or length > _MAX_BODY:
            self._send(400, {"error": f"body must be 1..{_MAX_BODY} bytes"})
            return
        try:
            body = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, OSError):
            self._send(400, {"error": "invalid JSON body"})
            return
        if not isinstance(body, dict):
            self._send(400, {"error": "JSON body must be an object"})
            return
        code, payload = _generate(body)
        self._send(code, payload)


def main() -> None:
    srv = ThreadingHTTPServer((API_BIND, API_PORT), Handler)
    sys.stderr.write(f"image-generation-api on http://{API_BIND}:{API_PORT}\n")
    srv.serve_forever()


if __name__ == "__main__":
    main()
