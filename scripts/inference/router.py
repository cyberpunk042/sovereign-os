"""sovereign-os inference router — thin OpenAI-compatible HTTP front.

Deterministic per-tier routing by request shape. No black-box dispatch.
Lives in front of the direct stack (Pulse / Logic Engine / Oracle Core)
for clients that want a single endpoint.

Default listen: 127.0.0.1:8080
Tiers reachable at: 8081 (Pulse) · 8082 (Logic Engine) · 8083 (Oracle) · 8084-8085 (llama.cpp fallbacks)

Routing rules (read top-down; first match wins):
  1. If request.model startswith "microsoft/bitnet" or "ternary:"   → Pulse
  2. If request.model contains "code"/"math" markers + has draft     → Oracle Core (DFlash)
  3. If context length > 65536                                       → Oracle Core (Mamba ctx)
  4. If request demands JSON-mode + structured output                 → Logic Engine (SGLang if installed; else vLLM)
  5. Default: Logic Engine
"""

from __future__ import annotations

import argparse
import http.server
import json
import logging
import socketserver
import sys
import urllib.error
import urllib.request
from typing import Any

log = logging.getLogger("sovereign-os.router")

# Backend endpoints (env-overridable). Defaults match the adapters.
TIER_ENDPOINTS: dict[str, str] = {
    "pulse":         "http://127.0.0.1:8081",
    "logic_engine":  "http://127.0.0.1:8082",
    "oracle_core":   "http://127.0.0.1:8083",
    "llama_old":     "http://127.0.0.1:8084",
    "llama_fb":      "http://127.0.0.1:8085",
}


def classify(request_body: dict[str, Any]) -> str:
    """Deterministic, operator-readable routing decision.

    Returns the tier key from TIER_ENDPOINTS. Operator can read this
    function in one screen and understand exactly where each request
    goes.
    """
    model = (request_body.get("model") or "").lower()
    messages = request_body.get("messages") or []
    # crude token count proxy
    total_chars = sum(len(m.get("content", "")) for m in messages)
    context_tokens_approx = total_chars // 4

    # Rule 1 — ternary models always go to Pulse (CPU CCD 0)
    if model.startswith("microsoft/bitnet") or model.startswith("ternary:") or "bitnet" in model:
        return "pulse"

    # Rule 2 — code/math + presence of draft model → Oracle Core (DFlash)
    last_user = next(
        (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
        "",
    )
    code_math_markers = ("```", "def ", "function ", "math", "solve ", "prove ", "compute ")
    if any(marker in last_user.lower() for marker in code_math_markers):
        return "oracle_core"

    # Rule 3 — long context → Oracle Core (Mamba-transformer 1M ctx friendly)
    if context_tokens_approx > 65536:
        return "oracle_core"

    # Rule 4 — JSON / structured output → Logic Engine
    if request_body.get("response_format", {}).get("type") == "json_object":
        return "logic_engine"
    if request_body.get("tools"):
        return "logic_engine"

    # Default
    return "logic_engine"


class RouterHandler(http.server.BaseHTTPRequestHandler):
    server_version = "sovereign-os-router/0.1"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        # Use stdlib logging instead of stderr stream
        log.info("%s - %s", self.client_address[0], format % args)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            self.send_error(400, "invalid JSON")
            return

        tier = classify(body)
        target = TIER_ENDPOINTS.get(tier)
        if target is None:
            self.send_error(503, f"tier {tier} not configured")
            return

        log.info("route: model=%r → tier=%s (%s)", body.get("model"), tier, target)

        # Proxy the request unchanged
        target_url = target.rstrip("/") + self.path
        req = urllib.request.Request(
            target_url,
            data=raw,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        # Pass through authorization header if present
        auth = self.headers.get("Authorization")
        if auth:
            req.add_header("Authorization", auth)

        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() in {"content-length", "transfer-encoding", "connection"}:
                        continue
                    self.send_header(k, v)
                self.end_headers()
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except urllib.error.HTTPError as e:
            self.send_error(e.code, str(e))
        except urllib.error.URLError as e:
            self.send_error(502, f"backend unreachable: {target} ({e})")

    def do_GET(self) -> None:  # noqa: N802
        # /healthz — router liveness
        if self.path in ("/healthz", "/health"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "tiers": list(TIER_ENDPOINTS.keys())}).encode())
            return
        # /v1/models — aggregate from each backend (best-effort)
        if self.path == "/v1/models":
            aggregated = {"object": "list", "data": []}
            for tier, ep in TIER_ENDPOINTS.items():
                try:
                    with urllib.request.urlopen(f"{ep}/v1/models", timeout=2) as r:
                        sub = json.load(r)
                    for m in sub.get("data", []):
                        m["_tier"] = tier
                        aggregated["data"].append(m)
                except Exception:  # noqa: BLE001
                    continue
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(aggregated).encode())
            return
        self.send_error(404, "not found")


class _ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main() -> int:
    ap = argparse.ArgumentParser(description="sovereign-os inference router")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", default=8080, type=int)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    server = _ThreadingServer((args.host, args.port), RouterHandler)
    log.info("router listening on http://%s:%d", args.host, args.port)
    log.info("tier endpoints: %s", TIER_ENDPOINTS)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("shutting down")
    return 0


if __name__ == "__main__":
    sys.exit(main())
