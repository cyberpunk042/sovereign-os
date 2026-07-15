#!/usr/bin/env python3
"""scripts/operator/weaver-sub-agent-demo.py — Demo sub-agent that
subscribes to Weaver state-sync events.

E107 closure: demonstrates how a Podman sub-agent consumes the
WeaverStateService gRPC stream (or SSE fallback) and reacts to
CLAUDE.md mutations.

Usage:
  python3 scripts/operator/weaver-sub-agent-demo.py

Env vars:
  WEAVER_GRPC_ENDPOINT   (default: http://127.0.0.1:8103)
  SUB_FILTER_FILE        (default: CLAUDE.md — empty = all files)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

ENDPOINT = os.environ.get("WEAVER_GRPC_ENDPOINT", "http://127.0.0.1:8103")
FILTER = os.environ.get("SUB_FILTER_FILE", "CLAUDE.md")


def subscribe_sse() -> None:
    """Subscribe to the HTTP SSE fallback endpoint."""
    url = f"{ENDPOINT}/events"
    print(f"[*] subscribing to SSE stream: {url}")
    print(f"    filter: {FILTER or '(none — all files)'}")
    print()
    try:
        with urllib.request.urlopen(url, timeout=300) as resp:
            buffer = ""
            while True:
                chunk = resp.read(1024).decode("utf-8")
                if not chunk:
                    break
                buffer += chunk
                while "\n\n" in buffer:
                    part, buffer = buffer.split("\n\n", 1)
                    for line in part.splitlines():
                        if line.startswith("data: "):
                            data = line[6:]
                            try:
                                event = json.loads(data)
                            except json.JSONDecodeError:
                                continue
                            if FILTER and event.get("file_name") != FILTER:
                                continue
                            print(
                                f"  [EVENT] {event['file_name']} "
                                f"changed at {event['change_timestamp']}"
                            )
                            print(f"    trigger: {event.get('trigger', '?')}")
                            print(f"    sha256:  {event.get('content_sha256', '?')[:16]}...")
                            # Sub-agent reaction demo: re-read the file
                            ctx_path = os.path.join(
                                "/mnt/vault/context", event["file_name"]
                            )
                            if os.path.exists(ctx_path):
                                with open(ctx_path) as f:
                                    snippet = f.read().replace("\n", " ")[:120]
                                print(f"    preview: {snippet}...")
                            print()
    except KeyboardInterrupt:
        print("\n[*] demo subscriber shutting down.")


if __name__ == "__main__":
    subscribe_sse()
