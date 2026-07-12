#!/usr/bin/env python3
"""sovereign-osctl model-serve — launch / stop / list a GPU serve-process model.

The ergonomic front to the jobs-api `model-serve` job kind (SDD-902): one command
places a model on a GPU by live free VRAM (the compute plane), launches
llama-server / vLLM, and registers it as a gateway PROXY backend so `/v1/messages`
+ the OpenAI shim reach it. `start` / `stop` / `background` are ACTIONS on the
loopback runtime (the cockpit routes them through control-exec); `list` is read-only.

  model-serve start <id> --model <path> [--engine llama-server|vllm] --vram N
      [--port P] [--dialect openai|anthropic] [--device auto|logic|oracle] [--ready-timeout S]
  model-serve stop <id>
  model-serve list
  model-serve background [<id> | --clear]

Stdlib only — it shells nothing; it POSTs JSON to jobs-api (:8142) and the gateway
(:8787) over loopback. The serve-process itself is launched by the jobs-api runner,
never here.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

JOBS_ADDR = os.environ.get("SOVEREIGN_JOBS_API_ADDR", "127.0.0.1:8142")
GATEWAY = os.environ.get("SOVEREIGN_OS_ROUTER_URL", "http://127.0.0.1:8787")


def _call(base: str, method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{base}{path}", data=data,
        headers={"Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310 (loopback)
            return json.loads(r.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8", "replace"))
            return {"error": payload.get("error") or payload.get("message") or f"HTTP {e.code}"}
        except (ValueError, OSError):
            return {"error": f"HTTP {e.code}"}
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {"error": f"unreachable at {base}: {e}"}


def _jobs(method: str, path: str, body: dict | None = None) -> dict:
    return _call(f"http://{JOBS_ADDR}", method, path, body)


def _gw(method: str, path: str, body: dict | None = None) -> dict:
    return _call(GATEWAY, method, path, body)


def serve_command(engine: str, model_path: str, port: int) -> list[str]:
    """The serve-process argv (no shell) for `engine`. Both expose an OpenAI-
    compatible `/v1/chat/completions` on `127.0.0.1:<port>`."""
    if engine == "llama-server":
        # -ngl 999 offloads every layer to the GPU (the plane placed it there).
        return ["llama-server", "--model", model_path, "--host", "127.0.0.1",
                "--port", str(port), "--n-gpu-layers", "999"]
    if engine == "vllm":
        return ["vllm", "serve", model_path, "--host", "127.0.0.1", "--port", str(port)]
    raise ValueError(f"unknown engine {engine!r} (want llama-server|vllm)")


def main(argv: list[str]) -> int:
    # --json is accepted both before and after the subcommand (a shared parent).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="machine-readable output")
    ap = argparse.ArgumentParser(
        prog="sovereign-osctl model-serve", parents=[common],
        description="launch a GPU serve-process model (places by VRAM, registers a gateway proxy)")
    sub = ap.add_subparsers(dest="cmd")

    ps = sub.add_parser("start", parents=[common], help="place + launch + register a GPU model")
    ps.add_argument("id", help="the model id the gateway serves it under")
    ps.add_argument("--model", required=True, help="model path / repo the engine loads")
    ps.add_argument("--engine", choices=["llama-server", "vllm"], default="llama-server")
    ps.add_argument("--vram", type=float, required=True, help="VRAM (GB) to claim on the plane")
    ps.add_argument("--port", type=int, default=8090, help="port the serve-process listens on")
    ps.add_argument("--dialect", choices=["openai", "anthropic"], default="openai")
    ps.add_argument("--device", default="auto", help="plane device hint: auto|logic|oracle")
    ps.add_argument("--ready-timeout", type=float, default=120.0,
                    help="seconds to wait for the endpoint before failing")

    pst = sub.add_parser("stop", parents=[common], help="cancel the serving job for <id>")
    pst.add_argument("id")

    sub.add_parser("list", parents=[common], help="serving jobs + the gateway's loaded models")

    pb = sub.add_parser("background", parents=[common], help="designate (or clear) the background model")
    pb.add_argument("id", nargs="?", help="the loaded model id the 'background' alias routes to")
    pb.add_argument("--clear", action="store_true", help="clear the designation (→ primary)")

    args = ap.parse_args(argv)
    cmd = args.cmd or "list"

    if cmd == "start":
        try:
            command = serve_command(args.engine, args.model, args.port)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        meta = {"command": command, "endpoint": f"127.0.0.1:{args.port}",
                "model_id": args.id, "dialect": args.dialect, "vram_gb": args.vram,
                "ready_timeout": args.ready_timeout}
        r = _jobs("POST", "/jobs", {"kind": "model-serve", "title": args.id,
                                    "device": args.device, "meta": meta})
        if args.json:
            print(json.dumps(r, indent=2))
            return 1 if r.get("error") else 0
        if r.get("error"):
            print(f"error: {r['error']}", file=sys.stderr)
            return 1
        jid = r.get("id", "?")
        print(f"model-serve {args.id}: job {jid} submitted — {args.engine} claiming "
              f"{args.vram:g}GB on '{args.device}', serving 127.0.0.1:{args.port} ({args.dialect})")
        print("  the plane places it on a device by free VRAM, launches it, then registers a gateway proxy.")
        print(f"  watch:  sovereign-osctl jobs status {jid}")
        print(f"  stop:   sovereign-osctl model-serve stop {args.id}")
        return 0

    if cmd == "stop":
        d = _jobs("GET", "/jobs.json")
        if d.get("error"):
            print(f"error: {d['error']}", file=sys.stderr)
            return 1
        matches = [j for j in d.get("jobs", [])
                   if j.get("kind") == "model-serve" and j.get("state") in ("running", "queued")
                   and (j.get("title") == args.id or (j.get("meta") or {}).get("model_id") == args.id)]
        if not matches:
            print(f"no running model-serve job for '{args.id}'", file=sys.stderr)
            return 1
        out = [_jobs("POST", f"/jobs/{j['id']}/cancel") for j in matches]
        if args.json:
            print(json.dumps(out, indent=2))
            return 0
        for j in matches:
            print(f"stopped model-serve {args.id} (job {j['id']}) — the proxy is unregistered + VRAM released")
        return 0

    if cmd == "list":
        jobs = _jobs("GET", "/jobs.json")
        models = _gw("GET", "/v1/models")
        serving = [j for j in jobs.get("jobs", []) if j.get("kind") == "model-serve"]
        if args.json:
            print(json.dumps({"serving": serving, "models": models}, indent=2))
            return 0
        print(f"serving jobs — {len(serving)}")
        for j in serving:
            ep = (j.get("meta") or {}).get("endpoint", "")
            print(f"  {j.get('state', '?'):<9} {j.get('title', '?'):<20} {ep:<20} {j.get('output', '')}")
        if models.get("error"):
            print(f"gateway registry: {models['error']}")
        else:
            print(f"gateway models — background → {models.get('background') or 'none'}")
            for m in models.get("data", []):
                vram = m.get("vram_gb")
                vram = f"{vram:g}GB" if isinstance(vram, (int, float)) and vram else ""
                print(f"  {m.get('id', ''):<20} {m.get('device', ''):<8} {vram}")
        return 0

    if cmd == "background":
        if not args.clear and not args.id:
            print("error: give a model id or --clear", file=sys.stderr)
            return 2
        body = {"id": None} if args.clear else {"id": args.id}
        r = _gw("POST", "/v1/models/background", body)
        if args.json:
            print(json.dumps(r, indent=2))
            return 1 if r.get("error") else 0
        if r.get("error"):
            print(f"error: {r['error']}", file=sys.stderr)
            return 1
        print(f"background model → {r.get('active') or 'none (falls back to the primary)'}")
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
