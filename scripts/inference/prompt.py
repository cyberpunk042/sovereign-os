#!/usr/bin/env python3
"""scripts/inference/prompt.py — the M058 single-prompt inference engine (SDD-062).

The real `inference prompt <text>` verb + the shared engine the D-22 web chat proxy
reuses. Routes an operator prompt through the LOOPBACK router
(`SOVEREIGN_OS_ROUTER_URL/v1/chat/completions`, default 127.0.0.1:8080), which
`classify()`s the tier + proxies/streams the backend's response body
(`router.py`). Streams token deltas, measures `tokens_per_sec`, and publishes the
REAL measured telemetry to `/run/sovereign-os/model-state.json` (preserving the
SDD-049 `loaded` set) + `model-latency.json`, so D-22's device grid shows live stats.

SB-077: never fabricates — an unreachable router/backend yields a structured honest
error; telemetry reflects only real completions. R10212: a chat completion is a
NON-MUTATING read-compute to a local model (no host/state mutation, no shell, no new
process); the only host write is the numeric telemetry (read-modify-write, preserving
`loaded`). Loopback-only (forwards only to the configured router URL, never external).

  prompt.py "<text>" [--no-stream] [--timeout N] [--model M] [--no-telemetry]

stdlib-only. Exit: 0 ok · 1 router/backend error.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

_INFER = Path(__file__).resolve().parent

ROUTER_URL = os.environ.get("SOVEREIGN_OS_ROUTER_URL", "http://127.0.0.1:8080")
MODEL_STATE_PATH = Path(os.environ.get(
    "SOVEREIGN_OS_MODEL_STATE", "/run/sovereign-os/model-state.json"))
MODEL_LATENCY_PATH = Path(os.environ.get(
    "SOVEREIGN_OS_MODEL_LATENCY", "/run/sovereign-os/model-latency.json"))
MAX_PROMPT_CHARS = int(os.environ.get("SOVEREIGN_OS_MAX_PROMPT_CHARS", "8000"))
DEFAULT_TIMEOUT = int(os.environ.get("SOVEREIGN_OS_PROMPT_TIMEOUT", "300"))

# tier (router classify) → model-health role (model-state.json tokens_per_sec key).
_TIER_ROLE = {"pulse": "conductor", "logic_engine": "logic", "logic": "logic",
              "oracle_core": "oracle", "oracle": "oracle", "router": "logic"}


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _classify(body: dict[str, Any]) -> str:
    """Ask the router's own classify() which tier a prompt hits (single source of
    truth). Best-effort — unavailable → 'logic' (a safe default role)."""
    try:
        spec = importlib.util.spec_from_file_location("_router_for_prompt", _INFER / "router.py")
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return str(mod.classify(body))
    except Exception:  # noqa: BLE001 — classify is best-effort telemetry labelling
        return "logic"


def _atomic_write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".prompt-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        d = json.loads(path.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _stream_completion(body: dict[str, Any], timeout: int) -> Iterator[str]:
    """POST to the loopback router /v1/chat/completions (stream:true) and yield raw
    SSE `data:` payload strings. Isolated for testability (monkeypatch this)."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{ROUTER_URL}/v1/chat/completions", data=data,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if line.startswith("data:"):
                yield line[5:].strip()


def run(text: str, *, stream: bool = True, timeout: int = DEFAULT_TIMEOUT,
        model: str = "auto") -> Iterator[dict[str, Any]]:
    """Run a single prompt through the router. Yields event dicts:
    {"type":"token","text":…} per delta, then a final
    {"type":"done","tokens":N,"elapsed_s":T,"tokens_per_sec":R,"tier":…}, or a single
    {"type":"error","error":…} on an unreachable/failed backend (never fabricated)."""
    text = text or ""
    if not text.strip():
        yield {"type": "error", "error": "empty prompt"}
        return
    if len(text) > MAX_PROMPT_CHARS:
        yield {"type": "error",
               "error": f"prompt exceeds {MAX_PROMPT_CHARS} chars (bounded read-compute)"}
        return
    body = {"model": model, "messages": [{"role": "user", "content": text}],
            "stream": True, "stream_options": {"include_usage": True}}
    tier = _classify(body)
    started = time.monotonic()
    tokens = 0
    try:
        for payload in _stream_completion(body, timeout):
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
            except (json.JSONDecodeError, ValueError):
                continue
            usage = chunk.get("usage")
            if isinstance(usage, dict) and usage.get("completion_tokens"):
                tokens = int(usage["completion_tokens"])
            choices = chunk.get("choices") or []
            if choices:
                delta = (choices[0].get("delta") or {}).get("content")
                if delta:
                    tokens += 0 if usage else 1  # count deltas only w/o usage
                    yield {"type": "token", "text": delta}
    except (urllib.error.URLError, ConnectionError, OSError, TimeoutError) as e:
        yield {"type": "error", "tier": tier,
               "error": f"router unreachable at {ROUTER_URL} ({e}) — start it: "
               "`sovereign-osctl inference start router` (backend is hardware-gated)"}
        return
    elapsed = max(time.monotonic() - started, 1e-6)
    tps = round(tokens / elapsed, 2) if tokens else 0.0
    yield {"type": "done", "tokens": tokens, "elapsed_s": round(elapsed, 3),
           "tokens_per_sec": tps, "tier": tier}


def publish_telemetry(tier: str, tokens_per_sec: float, latency_ms: float | None = None,
                      *, model: str = "chat") -> dict[str, Any]:
    """Record the REAL measured telemetry (read-modify-write): set
    model-state.json tokens_per_sec[role] + updated_ts, PRESERVING the SDD-049
    `loaded` set; append a model-latency.json record. Never fabricates."""
    role = _TIER_ROLE.get(tier, "logic")
    state = _read_json(MODEL_STATE_PATH)
    tps = state.get("tokens_per_sec")
    if not isinstance(tps, dict):
        tps = {}
    tps[role] = tokens_per_sec
    state["tokens_per_sec"] = tps
    state["updated_ts"] = _now()
    # `loaded` (SDD-049) is preserved untouched — we never write it here.
    try:
        _atomic_write(MODEL_STATE_PATH, state)
    except OSError as e:
        return {"ok": False, "error": f"model-state write failed: {e}"}
    if latency_ms is not None:
        lat = _read_json(MODEL_LATENCY_PATH)
        models = lat.get("models")
        if not isinstance(models, list):
            models = []
        models.append({"model": model, "role": role, "p50_ms": round(latency_ms, 1),
                       "ts": _now()})
        lat["models"] = models[-500:]  # bounded ring
        try:
            _atomic_write(MODEL_LATENCY_PATH, lat)
        except OSError:
            pass
    return {"ok": True, "role": role, "tokens_per_sec": tokens_per_sec}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="M058 single-prompt inference (SDD-062)")
    ap.add_argument("text", nargs="+", help="the prompt")
    ap.add_argument("--no-stream", action="store_true")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    ap.add_argument("--model", default="auto")
    ap.add_argument("--no-telemetry", action="store_true")
    args = ap.parse_args(argv)
    text = " ".join(args.text)
    done: dict[str, Any] | None = None
    err: dict[str, Any] | None = None
    for ev in run(text, stream=not args.no_stream, timeout=args.timeout, model=args.model):
        if ev["type"] == "token":
            sys.stdout.write(ev["text"])
            sys.stdout.flush()
        elif ev["type"] == "done":
            done = ev
        elif ev["type"] == "error":
            err = ev
    if err is not None:
        sys.stdout.write("\n")
        print(json.dumps(err, indent=2), file=sys.stderr)
        return 1
    sys.stdout.write("\n")
    if done and not args.no_telemetry and done["tokens"]:
        latency = (done["elapsed_s"] * 1000.0 / done["tokens"]) if done["tokens"] else None
        publish_telemetry(done["tier"], done["tokens_per_sec"], latency)
    if done:
        print(json.dumps({"tier": done["tier"], "tokens": done["tokens"],
                          "tokens_per_sec": done["tokens_per_sec"],
                          "elapsed_s": done["elapsed_s"]}, indent=2), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
