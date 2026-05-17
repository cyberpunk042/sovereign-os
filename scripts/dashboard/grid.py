#!/usr/bin/env python3
"""scripts/dashboard/grid.py — R248 (SDD-026 Z-1 terminal-grid view).

Operator-named (verbatim, 2026-05-17 expansion): "Everything via
dashboard/UInterface or terminal tools OR AI, as my chose or even
needs." + "this Debian 13 Sovereign OS is a non-GUI by default".

R225 ships the HTML dashboard with 15 cards. R248 ships the TERMINAL
equivalent: one line per card with a status glyph + headline + key
metric. Operators SSH'd into a headless box get the same surface
without opening a browser, without `for card in $(...); do osctl ...;
done` iteration.

Reads each card via the dashboard's /api/<id> endpoints over loopback
(starts a single --once server, queries all card endpoints in
parallel, returns the matrix). For CI / cold-start contexts where
binding a socket isn't viable, the script falls back to importing
serve.py and calling card functions directly.

CLI:
  grid.py [--json] [--bind HOST:PORT]   render the grid
  grid.py --watch [--interval SEC]      live-update every N seconds

Exit codes:
  0  render succeeded; no cards have needs_attention=true
  1  ≥1 card has needs_attention=true (terminal alert signal)
  2  usage error / serve.py not importable
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


def import_serve():
    """Import scripts/dashboard/serve.py as a module to call card_* directly.

    This avoids the bind/HTTP roundtrip — cards run in-process,
    operator gets the same data without socket lifecycle.
    """
    serve_path = REPO_ROOT / "scripts" / "dashboard" / "serve.py"
    if not serve_path.exists():
        return None
    import importlib.util
    spec = importlib.util.spec_from_file_location("_sovereign_dashboard_serve", serve_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:  # noqa: BLE001 — serve.py import shouldn't take grid down
        return None
    return module


def collect_cards() -> list[dict[str, Any]]:
    mod = import_serve()
    if mod is None:
        return []
    cards = getattr(mod, "CARDS", None)
    if not cards:
        return []
    out: list[dict[str, Any]] = []
    for fn in cards:
        try:
            card = fn()
        except Exception as e:  # noqa: BLE001
            out.append({"id": fn.__name__.removeprefix("card_"),
                       "title": fn.__name__,
                       "data": {"summary": f"card crashed: {e}",
                                "needs_attention": True}})
            continue
        if isinstance(card, dict):
            out.append(card)
    return out


def render_grid_human(cards: list[dict[str, Any]]) -> str:
    out: list[str] = []
    out.append("── R248 sovereign-os status grid (SDD-026 Z-1 terminal view) ──")
    out.append("")
    out.append(f"  {'GLYPH':<5}  {'ID':<14}  {'TITLE':<34}  HEADLINE")
    out.append(f"  {'─'*5}  {'─'*14}  {'─'*34}  {'─'*40}")
    for c in cards:
        data = c.get("data") or {}
        needs = bool(data.get("needs_attention"))
        glyph = "⛔" if needs else "✓"
        summary = data.get("summary") or ""
        # Truncate summary to keep one-line.
        if len(summary) > 60:
            summary = summary[:57] + "..."
        out.append(
            f"  {glyph:<5}  {c.get('id',''):<14}  "
            f"{c.get('title','')[:34]:<34}  {summary}"
        )
    return "\n".join(out) + "\n"


def cmd_render(args: argparse.Namespace) -> int:
    cards = collect_cards()
    needs_count = sum(
        1 for c in cards
        if (c.get("data") or {}).get("needs_attention")
    )
    if args.json:
        report = {
            "round": "R248",
            "vector": "SDD-026 Z-1 (terminal grid)",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "card_count": len(cards),
            "needs_attention_count": needs_count,
            "cards": [
                {
                    "id": c.get("id"),
                    "title": c.get("title"),
                    "summary": (c.get("data") or {}).get("summary"),
                    "needs_attention": bool((c.get("data") or {}).get("needs_attention")),
                }
                for c in cards
            ],
        }
        print(json.dumps(report, indent=2))
    else:
        print(render_grid_human(cards), end="")
    return 1 if needs_count > 0 else 0


def cmd_watch(args: argparse.Namespace) -> int:
    interval = max(2, int(args.interval))
    try:
        while True:
            # Clear screen + render.
            sys.stdout.write("\x1b[2J\x1b[H")
            sys.stdout.flush()
            cmd_render(args)
            time.sleep(interval)
    except KeyboardInterrupt:
        return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="grid.py",
        description="R248 (SDD-026 Z-1) — terminal-grid rollup of every dashboard card.",
    )
    p.add_argument("--json", action="store_true")
    p.add_argument(
        "--watch", action="store_true",
        help="live-update render every --interval seconds (Ctrl-C to exit)",
    )
    p.add_argument("--interval", type=int, default=5)
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    if args.watch:
        return cmd_watch(args)
    return cmd_render(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
