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
import os
import pathlib
import socketserver
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Any

log = logging.getLogger("sovereign-os.router")

# ---- Layer B metrics (SDD-016 — Prometheus textfile collector) ------------

# In-memory counters; flushed to disk on every routing decision.
# Cheap: the resulting .prom file is < 1KB. Concurrent flush is guarded
# by _METRICS_LOCK (writes are atomic via tempfile + rename).
_ROUTE_COUNTS: dict[str, int] = {t: 0 for t in (
    "pulse", "logic_engine", "oracle_core", "llama_old", "llama_fb"
)}
# R161 — task_type classification counter (closes R157 follow-up).
# Per-request task_type is computed by `classify_task_type()` and
# surfaced as Layer B label + as an X-Sovereign-Task-Type response
# header so operators can observe the gating signal end-to-end.
_TASK_TYPE_COUNTS: dict[str, int] = {t: 0 for t in (
    "code", "math", "conversational", "creative"
)}
# R215 — model-class classification counter. Composes with R212
# catalog taxonomy (class enum: llm/slm/rlm/ternary-lm/lora-adapter/
# embed/vision/multimodal/code/mixture/speculative/reranker). Operator
# supplies the intended class via `sovereign_os_class` in the request
# body; metrics cross-tab class × tier so fleet dashboards can answer
# "what fraction of traffic asked for class=rlm and routed to oracle?".
_CLASS_COUNTS: dict[str, int] = {c: 0 for c in (
    "llm", "slm", "rlm", "ternary-lm", "lora-adapter", "embed",
    "vision", "multimodal", "code", "mixture", "speculative",
    "reranker", "(unspecified)",
)}
_METRICS_LOCK = threading.Lock()
_METRICS_DIR = pathlib.Path(
    os.environ.get(
        "SOVEREIGN_OS_METRICS_DIR",
        "/var/lib/node_exporter/textfile_collector",
    )
)
_METRICS_FILE = _METRICS_DIR / "sovereign-os-inference-router.prom"
_METRICS_DISABLED = os.environ.get("SOVEREIGN_OS_METRICS_DISABLE") == "1"

# MS048 cross-repo: OPT-IN, ADVISORY-ONLY consultation of the selfdef
# Goldilocks Scheduler. Default OFF — when off, routing is unchanged (the
# runtime's own shape-based classify() is authoritative). When
# SOVEREIGN_OS_CONSULT_SCHEDULER=1, the router additionally asks the scheduler
# what hardware tier the box would prefer right now and surfaces it as an
# ADVISORY (log line + X-Sovereign-Scheduler-Advisory header) WITHOUT changing
# the route. This is the conservative half of the integration: capability +
# observability now; deferring the actual route to the scheduler stays a
# separate, explicit operator step. Fail-safe: any error → empty advisory,
# routing untouched.
_CONSULT_SCHEDULER = os.environ.get("SOVEREIGN_OS_CONSULT_SCHEDULER") == "1"
_SCHEDULER_PROFILE = os.environ.get("SOVEREIGN_OS_SCHEDULER_PROFILE", "production")
_bridge_mod = None  # lazily loaded scheduler-bridge module (hyphenated filename)


def _scheduler_bridge():
    """Lazily load scripts/inference/scheduler-bridge.py (hyphenated → importlib)."""
    global _bridge_mod
    if _bridge_mod is None:
        import importlib.util

        path = pathlib.Path(__file__).resolve().parent / "scheduler-bridge.py"
        spec = importlib.util.spec_from_file_location("scheduler_bridge", path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _bridge_mod = mod
    return _bridge_mod


def _scheduler_advisory(body: dict[str, Any]) -> str:
    """Return the scheduler's advised runtime service for the current substrate
    (e.g. "Oracle Core" / "Logic Engine" / "Pulse" / "defer"), or "" when the
    feature is off or the scheduler is unavailable. NEVER raises — advisory
    only, routing is never affected."""
    if not _CONSULT_SCHEDULER:
        return ""
    try:
        bridge = _scheduler_bridge()
        if bridge is None:
            return ""
        # neutral model axes — the advisory reflects the live hardware
        # substrate + active profile, which is what the tier hint is about.
        task = bridge.build_task(_SCHEDULER_PROFILE)
        verdict = bridge.consult(task)
        if not verdict.get("scheduler_available"):
            return ""
        if verdict.get("defer"):
            return "defer"
        return verdict.get("runtime_service") or verdict.get("backend_tier") or ""
    except Exception as e:  # noqa: BLE001 — advisory must never break routing
        log.debug("scheduler advisory failed (non-fatal): %s", e)
        return ""


def _record_route(tier: str, task_type: str = "", model_class: str = "") -> None:
    """Increment the per-tier counter + flush the .prom file atomically.

    R161: also increments the task_type counter and emits its label
    set so operators can observe which task_type each request resolved
    to (closes R157 follow-up: task_type signal flows through router).

    R215: also increments the model-class counter (R212 catalog
    taxonomy: llm / slm / rlm / ternary-lm / etc.) so operators can
    observe cross-tabbed class × tier demand.
    """
    if _METRICS_DISABLED:
        return
    with _METRICS_LOCK:
        _ROUTE_COUNTS[tier] = _ROUTE_COUNTS.get(tier, 0) + 1
        if task_type:
            _TASK_TYPE_COUNTS[task_type] = _TASK_TYPE_COUNTS.get(task_type, 0) + 1
        # R215: tally the class label (default to "(unspecified)" so
        # operator missing the field is still observable).
        class_label = model_class or "(unspecified)"
        _CLASS_COUNTS[class_label] = _CLASS_COUNTS.get(class_label, 0) + 1
        try:
            _METRICS_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            return  # graceful skip — metrics dir not provisioned
        lines = [
            "# HELP sovereign_os_inference_route_total Per-tier routing decisions",
            "# TYPE sovereign_os_inference_route_total counter",
        ]
        for t, n in sorted(_ROUTE_COUNTS.items()):
            lines.append(f'sovereign_os_inference_route_total{{tier="{t}"}} {n}')
        lines.append("# HELP sovereign_os_inference_router_task_type_total Per-task-type routing classification (R161, closes R157 follow-up)")
        lines.append("# TYPE sovereign_os_inference_router_task_type_total counter")
        for t, n in sorted(_TASK_TYPE_COUNTS.items()):
            lines.append(f'sovereign_os_inference_router_task_type_total{{task_type="{t}"}} {n}')
        # R215 — model-class counter.
        lines.append(
            "# HELP sovereign_os_inference_router_class_total Per-model-class "
            "routing classification (R215, composes with R212 catalog taxonomy)"
        )
        lines.append("# TYPE sovereign_os_inference_router_class_total counter")
        for c, n in sorted(_CLASS_COUNTS.items()):
            lines.append(
                f'sovereign_os_inference_router_class_total{{class="{c}"}} {n}'
            )
        lines.append("# HELP sovereign_os_inference_router_last_route_timestamp Unix timestamp of last routing decision")
        lines.append("# TYPE sovereign_os_inference_router_last_route_timestamp gauge")
        lines.append(f"sovereign_os_inference_router_last_route_timestamp {int(time.time())}")
        tmp = _METRICS_FILE.with_suffix(".prom.tmp")
        try:
            tmp.write_text("\n".join(lines) + "\n")
            tmp.replace(_METRICS_FILE)
        except OSError:
            try:
                tmp.unlink()
            except OSError:
                pass

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


def classify_task_type(request_body: dict[str, Any]) -> str:
    """R161 — closes R157 follow-up. Classify request task_type so DFlash
    gating + per-task metric labels can be applied downstream.

    Precedence:
      1. Explicit `request_body['sovereign_os_task_type']` if a known
         value (caller-asserted; operator escape hatch).
      2. Structured-output hints (response_format=json_object or tools)
         → 'code' (DFlash benefits both per R157).
      3. Code markers in the last user message (```/def/function ...)
         → 'code'.
      4. Math markers (solve/prove/compute/math) → 'math'.
      5. Creative cues (story/poem/imagine/write a) → 'creative'
         (DFlash is gated OFF per operator-verbatim § Block 7).
      6. Default → 'conversational'.

    Keep this function readable in one screen — operators trace the
    classification path directly. NO ML model; deterministic rules.
    """
    known = ("code", "math", "conversational", "creative")
    explicit = (request_body.get("sovereign_os_task_type") or "").lower()
    if explicit in known:
        return explicit

    if request_body.get("response_format", {}).get("type") == "json_object":
        return "code"
    if request_body.get("tools"):
        return "code"

    messages = request_body.get("messages") or []
    last_user = next(
        (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
        "",
    ).lower()

    code_markers = ("```", "def ", "function ", "class ", "import ", "package ", "#include")
    if any(marker in last_user for marker in code_markers):
        return "code"

    math_markers = ("solve ", "prove ", "compute ", "integral", "derivative", "math problem", "equation")
    if any(marker in last_user for marker in math_markers):
        return "math"

    creative_markers = (
        "story", "poem", "haiku", "lyric", "imagine ",
        "write a ", "write me a ", "compose a ", "creative ",
    )
    if any(marker in last_user for marker in creative_markers):
        return "creative"

    return "conversational"


# R215 — model-class classification. Operators supply
# `sovereign_os_class` directly when they want explicit control; the
# router falls back to inferring from the `model` field (matching the
# R212 catalog's known ids → class).
_KNOWN_CLASSES: set[str] = {
    "llm", "slm", "rlm", "ternary-lm", "lora-adapter", "embed",
    "vision", "multimodal", "code", "mixture", "speculative", "reranker",
}

# Heuristics for inferring class from the `model` field — keyed by
# substring matches against well-known id patterns. Operator-readable
# table; ordering matters (first match wins).
_MODEL_ID_CLASS_HINTS: list[tuple[str, str]] = [
    ("bitnet", "ternary-lm"),
    ("ternary", "ternary-lm"),
    ("embed", "embed"),
    ("reranker", "reranker"),
    ("rerank", "reranker"),
    ("speculative", "speculative"),
    ("vl-", "vision"),
    ("-vl", "vision"),
    ("vision", "vision"),
    ("nemotron-3-nano-omni", "multimodal"),
    ("omni", "multimodal"),
    ("lora", "lora-adapter"),
    ("adapter", "lora-adapter"),
    ("v3", "mixture"),
    ("mixtral", "mixture"),
    ("moe", "mixture"),
    ("coder", "code"),
    ("r1-distill", "rlm"),
    ("deepseek-r1", "rlm"),
    ("reasoning", "rlm"),
    ("1.7b", "slm"),
    ("phi-4-mini", "slm"),
    ("phi-4", "slm"),
    ("0.5b", "slm"),
]


def classify_model_class(request_body: dict[str, Any]) -> str:
    """R215 — classify a request's intended model class.

    Precedence:
      1. `sovereign_os_class` field (operator-asserted).
      2. Inference from the `model` string against
         `_MODEL_ID_CLASS_HINTS` (first matching substring wins).
      3. Empty string → counter rolls into "(unspecified)" bucket.
    """
    explicit = (request_body.get("sovereign_os_class") or "").lower().strip()
    if explicit in _KNOWN_CLASSES:
        return explicit
    model = (request_body.get("model") or "").lower()
    for needle, cls in _MODEL_ID_CLASS_HINTS:
        if needle in model:
            return cls
    return ""


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
        # R161: classify task_type alongside tier; both surface in metrics
        # and the task_type also lands in the response header so operators
        # can curl -v and see what the router decided.
        task_type = classify_task_type(body)
        # R215: classify model class (R212 taxonomy); also surfaces in
        # metrics and as an X-Sovereign-Model-Class response header.
        model_class = classify_model_class(body)

        # MS048: OPT-IN advisory — the scheduler's preferred hardware tier for
        # the current substrate. Does NOT change `tier` (routing stays the
        # runtime's decision); surfaced as a header for observability.
        scheduler_advisory = _scheduler_advisory(body)

        target = TIER_ENDPOINTS.get(tier)
        if target is None:
            self.send_error(503, f"tier {tier} not configured")
            return

        log.info(
            "route: model=%r → tier=%s task_type=%s class=%s (%s)",
            body.get("model"), tier, task_type, model_class or "?", target,
        )
        _record_route(tier, task_type, model_class)

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
                # R161: surface routing decision in response headers for
                # end-to-end operator observability.
                self.send_header("X-Sovereign-Routed-Tier", tier)
                self.send_header("X-Sovereign-Task-Type", task_type)
                # R215: model-class header (R212 taxonomy). Empty when
                # the router couldn't infer + operator didn't assert.
                self.send_header("X-Sovereign-Model-Class", model_class or "")
                # MS048: scheduler's hardware-tier advisory (empty unless
                # SOVEREIGN_OS_CONSULT_SCHEDULER=1 + scheduler reachable).
                # Advisory only — the routed tier above is authoritative.
                if scheduler_advisory:
                    self.send_header("X-Sovereign-Scheduler-Advisory", scheduler_advisory)
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
