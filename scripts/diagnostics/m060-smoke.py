#!/usr/bin/env python3
"""M060 cross-repo mirror chain smoke check — operator-runnable, read-only.

Pings each of the 8 M060 mirror domains' /api/d-NN/snapshot endpoints
through the sovereign-os api proxy and reports per-domain status:

    domain                 status   detail
    ──────────────────     ──────   ──────
    D-02 active-profile    ONLINE   active=autonomous · captured 2027-01-15T08:00:00Z
    D-12 rules             OFFLINE  no resident store — daemon-populated by nft collector
    D-13 grants            ONLINE   2 grants · 1 pending · captured 2027-01-15T08:00:00Z
    D-14 capability-tokens OFFLINE  no resident store — selfdefctl capability-tokens issue
    D-15 sandboxes         OFFLINE  no resident store — selfdefctl sandboxes allocate
    D-16 audit-chain       OFFLINE  chain empty — daemon-built append-only by MS016
    D-17 quarantine        OFFLINE  no resident store — daemon-populated by MS042 detection
    D-18 trust-scores      OFFLINE  no resident store — daemon-populated by scoring

Exit code:
    0  if all 8 endpoints reachable (any/all may legitimately be offline)
    1  if ≥1 endpoint is unreachable (proxy down / api daemon not running)

Use --strict to require all 8 mirror_status == "online" (exit 1 otherwise).

  --base-url  base URL (default http://localhost; honors $SOVEREIGN_OS_BASE_URL)
  --strict    require online for all 8 (else any online/offline ok if reachable)
  --json      machine-readable JSON output instead of the table

Sovereignty: stdlib-only (no requests/httpx dep). Read-only — never mutates
anything (web-is-read-only doctrine MS043 R10212 + R10115).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

# (id, label, endpoint, fields the table summarizer mines from the JSON)
DOMAINS = [
    ("D-02", "active-profile",    "/api/profile/show"),
    ("D-12", "rules",             "/api/d-12/snapshot"),
    ("D-13", "grants",            "/api/d-13/snapshot"),
    ("D-14", "capability-tokens", "/api/d-14/snapshot"),
    ("D-15", "sandboxes",         "/api/d-15/snapshot"),
    ("D-16", "audit-chain",       "/api/d-16/snapshot"),
    ("D-17", "quarantine",        "/api/d-17/snapshot"),
    ("D-18", "trust-scores",      "/api/d-18/snapshot"),
]

# Per-domain offline-hint pointing at the selfdef knob/verb that populates it.
OFFLINE_HINT = {
    "D-02": "always-online once selfdefd runs with selfdef_mirror_dir set",
    "D-12": "no resident store — daemon-populated by nft collector (rules installed via selfdefctl + nft at the IPS layer)",
    "D-13": "no resident store — selfdefctl grants issue ...",
    "D-14": "no resident store — selfdefctl capability-tokens issue ...",
    "D-15": "no resident store — selfdefctl sandboxes allocate ...",
    "D-16": "chain empty — daemon-built append-only by MS016 (no operator append surface)",
    "D-17": "no resident store — daemon-populated by MS042 detection",
    "D-18": "no resident store — daemon-populated by scoring (or admit via selfdefctl trust-scores admit)",
}


def probe(base_url: str, endpoint: str, timeout: float = 3.0) -> dict:
    """Returns {"reachable", "mirror_status", "raw"} for one mirror probe."""
    url = base_url.rstrip("/") + endpoint
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            body = r.read().decode("utf-8")
            raw = json.loads(body)
            return {
                "reachable": True,
                "http_status": r.status,
                "mirror_status": raw.get("mirror_status", "unknown"),
                "raw": raw,
            }
    except urllib.error.HTTPError as e:
        return {"reachable": False, "http_status": e.code, "error": str(e)}
    except (urllib.error.URLError, ConnectionError, OSError) as e:
        return {"reachable": False, "http_status": None, "error": str(e)}
    except json.JSONDecodeError as e:
        return {"reachable": False, "http_status": None, "error": "non-JSON: " + str(e)}


def summarize(dom_id: str, label: str, probe_result: dict) -> str:
    """One-line operator-readable summary for the table."""
    if not probe_result["reachable"]:
        return f"UNREACHABLE  http={probe_result.get('http_status')} · {probe_result.get('error', '?')[:60]}"
    raw = probe_result["raw"]
    ms = probe_result["mirror_status"]
    if ms != "online":
        return f"OFFLINE      {OFFLINE_HINT.get(dom_id, '')}"
    # online: per-domain summary
    captured = raw.get("captured_at", "?")
    if dom_id == "D-02":
        return f"ONLINE       active={raw.get('active', '?')} · captured {captured}"
    if dom_id == "D-13":
        n = len(raw.get("grants", []))
        p = len(raw.get("pending", []))
        return f"ONLINE       {n} grants · {p} pending · captured {captured}"
    if dom_id == "D-14":
        n = len(raw.get("tokens", []))
        return f"ONLINE       {n} tokens · captured {captured}"
    if dom_id == "D-12":
        n = len(raw.get("rules", []))
        rings = len(raw.get("summaries", []))
        return f"ONLINE       {n} rules · {rings} rings populated · captured {captured}"
    if dom_id == "D-15":
        n = len(raw.get("allocations", []))
        return f"ONLINE       {n} allocations · captured {captured}"
    if dom_id == "D-16":
        n = len(raw.get("spans", []))
        integ = raw.get("integrity", {}) or {}
        total = integ.get("total_entries", 0)
        cont = "continuous" if integ.get("continuous", True) else "BROKEN"
        return f"ONLINE       {n} tail spans · {total} chain entries · {cont} · captured {captured}"
    if dom_id == "D-17":
        n = len(raw.get("entries", []))
        return f"ONLINE       {n} quarantine entries · captured {captured}"
    if dom_id == "D-18":
        n = len(raw.get("tools", []))
        return f"ONLINE       {n} scored tools · captured {captured}"
    return f"ONLINE       captured {captured}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--base-url",
        default=os.environ.get("SOVEREIGN_OS_BASE_URL", "http://localhost"),
        help="base URL of the sovereign-os master-dashboard api (default http://localhost)",
    )
    p.add_argument(
        "--strict", action="store_true",
        help="require mirror_status=online for all 8 (exit 1 otherwise)",
    )
    p.add_argument("--json", action="store_true", help="machine-readable JSON output")
    args = p.parse_args(argv)

    results = []
    for dom_id, label, endpoint in DOMAINS:
        pr = probe(args.base_url, endpoint)
        results.append({
            "id": dom_id, "label": label, "endpoint": endpoint,
            "reachable": pr["reachable"],
            "mirror_status": pr.get("mirror_status"),
            "summary": summarize(dom_id, label, pr),
        })

    unreachable = [r for r in results if not r["reachable"]]
    offline = [r for r in results if r["reachable"] and r["mirror_status"] != "online"]
    online = [r for r in results if r["mirror_status"] == "online"]

    if args.json:
        print(json.dumps({
            "base_url": args.base_url,
            "results": results,
            "totals": {
                "online": len(online),
                "offline": len(offline),
                "unreachable": len(unreachable),
                "total": len(results),
            },
        }, indent=2))
    else:
        print(f"M060 cross-repo mirror chain smoke @ {args.base_url}")
        print(f"{'domain':<22} {'status / detail':<60}")
        print(f"{'─' * 22} {'─' * 60}")
        for r in results:
            label = f"{r['id']} {r['label']}"
            print(f"{label:<22} {r['summary']}")
        print(f"{'─' * 22} {'─' * 60}")
        print(
            f"summary: {len(online)} online · {len(offline)} offline · "
            f"{len(unreachable)} unreachable / {len(results)} total"
        )

    # Exit logic:
    # - unreachable (any) → 1 (the proxy / api daemon is down)
    # - --strict + any offline → 1
    # - else → 0 (every endpoint at least responded)
    if unreachable:
        return 1
    if args.strict and offline:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
