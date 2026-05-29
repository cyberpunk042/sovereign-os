#!/usr/bin/env python3
"""M060 cross-repo mirror chain smoke check — operator-runnable, read-only.

Pings each of the 10 M060 mirror domains' snapshot endpoints (the 8 D-NN
dashboards + the 2 cross-cutting MS007 mirrors TUI-layout / CLI-schema)
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
    0  if all 10 endpoints reachable (any/all may legitimately be offline)
    1  if ≥1 endpoint is unreachable (proxy down / api daemon not running)

Use --strict to require all 10 mirror_status == "online" (exit 1 otherwise).

  --base-url  base URL (default http://localhost; honors $SOVEREIGN_OS_BASE_URL)
  --strict    require online for all 10 (else any online/offline ok if reachable)
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
    # MS007 cross-cutting mirrors (not tied to a single D-NN slot).
    ("TUI",  "tui-layout",        "/api/tui/snapshot"),
    ("CLI",  "cli-schema",        "/api/cli/snapshot"),
]

# Chain-health endpoint covers the whole 10-mirror set; probed
# separately so a partial-population state surfaces in the smoke output.
HEALTH_ENDPOINT = "/api/m060/health"

# Selfdef-side doctor textfile metric prefixes. The
# selfdef-cli-mirror-doctor.timer + selfdef-m060-doctor.timer one-shots
# (selfdef commits e9ab056 + ce58154) write these to the host's
# node_exporter textfile_collector dir. Probed via the
# node_exporter /metrics endpoint so the smoke can verify the
# observers' freshness end-to-end.
DOCTOR_TEXTFILE_PREFIXES = [
    ("cli-mirror", "selfdef_cli_mirror_doctor"),
    ("m060-chain", "selfdef_m060_doctor"),
]
DEFAULT_NODE_EXPORTER_URL = os.environ.get(
    "SOVEREIGN_OS_NODE_EXPORTER_URL", "http://localhost:9100/metrics",
)

# MS022 SSE quota proxy daemon (sovereign-ms022-sse-quota-api.service)
# bound default :7711 — locked by the systemd-unit contract test. Same
# probe shape as the m060-health-api: hit /api/ms022/state, classify.
DEFAULT_MS022_PROXY_URL = os.environ.get(
    "SOVEREIGN_OS_MS022_PROXY_URL", "http://localhost:7711",
)
MS022_STATE_ENDPOINT = "/api/ms022/state"

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
    "TUI":  "always-online once selfdefd is running (canonical static layout, R10141)",
    "CLI":  "selfdefctl not on PATH on the daemon host (shell-out fails); install selfdefctl alongside selfdefd",
}


def probe_node_exporter_textfile(
    node_exporter_url: str,
    metric_prefix: str,
    timeout: float = 3.0,
) -> dict:
    """Probe one doctor textfile via node_exporter's /metrics. Returns
    a dict carrying the worst-severity gauge value + observer age
    (from last_run_unix) + 'reachable' indicator. Honest-offline
    when the textfile is absent (operator hasn't deployed the
    doctor systemd timer); never crashes."""
    out = {
        "reachable":   False,
        "worst":       None,
        "age_seconds": None,
        "error":       None,
    }
    try:
        with urllib.request.urlopen(node_exporter_url, timeout=timeout) as r:
            body = r.read().decode("utf-8")
    except (urllib.error.HTTPError, urllib.error.URLError,
            ConnectionError, OSError) as e:
        out["error"] = str(e)
        return out

    out["reachable"] = True
    import time as _time
    now = int(_time.time())

    worst_key = f"{metric_prefix}_worst_severity"
    last_run_key = f"{metric_prefix}_last_run_unix"
    for line in body.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        # Lines have the shape `metric{labels} value` or `metric value`.
        # Strip labels for the simple gauge case.
        head, _, value_str = line.partition(" ")
        metric_name = head.split("{", 1)[0]
        try:
            value = float(value_str.split()[0])
        except (ValueError, IndexError):
            continue
        if metric_name == worst_key and out["worst"] is None:
            out["worst"] = int(value)
        elif metric_name == last_run_key and out["age_seconds"] is None:
            out["age_seconds"] = max(0, now - int(value))
    return out


def probe_ms022_state(proxy_url: str, timeout: float = 3.0) -> dict:
    """Hit the MS022 SSE quota proxy daemon's /api/ms022/state. Returns
    {reachable, state, error} matching the probe convention. State is
    one of ok/approaching/saturated/unreachable per the proxy classifier
    (which uses the same 0.85+1.0 thresholds as the alert rules, locked
    by the threshold-lockstep contract test)."""
    url = proxy_url.rstrip("/") + MS022_STATE_ENDPOINT
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            body = r.read().decode("utf-8")
            raw = json.loads(body)
            return {
                "reachable": True,
                "state": str(raw.get("state", "unknown")),
                "error": None,
            }
    except urllib.error.HTTPError as e:
        return {"reachable": False, "state": None, "error": f"HTTP {e.code}"}
    except (urllib.error.URLError, ConnectionError, OSError) as e:
        return {"reachable": False, "state": None, "error": str(e)}
    except json.JSONDecodeError as e:
        return {"reachable": False, "state": None, "error": "non-JSON: " + str(e)}


def summarize_ms022(result: dict) -> str:
    """One-line MS022 state summary for the operator triage row."""
    if not result["reachable"]:
        return (
            f"UNREACHABLE  proxy daemon down · {result.get('error', '?')[:50]}"
        )
    state = result["state"]
    if state == "ok":
        return "OK           quota healthy (saturation ≤ 85%)"
    if state == "approaching":
        return "WARN         quota approaching (sat > 85% OR ≥1 token at cap)"
    if state == "saturated":
        return "FAIL         quota SATURATED — clients getting 429"
    if state == "unreachable":
        return "WARN         proxy reachable but selfdefd /metrics unreachable"
    return f"UNKNOWN      proxy reports state={state!r}"


def summarize_doctor(label: str, result: dict) -> str:
    """One-line summary for the doctor observer table row."""
    if not result["reachable"]:
        return f"UNREACHABLE  node_exporter /metrics not served · {result.get('error', '?')[:40]}"
    if result["worst"] is None:
        return "ABSENT       textfile not emitted (doctor timer not deployed?)"
    sev_label = {0: "OK     ", 1: "WARN   ", 2: "FAIL   "}.get(result["worst"], "UNK    ")
    age = result["age_seconds"]
    age_str = f"{age}s old" if age is not None else "age=?"
    return f"{sev_label}    severity={result['worst']} · last fire {age_str}"


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
    if dom_id == "TUI":
        n = len(raw.get("panels", []))
        return f"ONLINE       {n} panels (canonical 4 expected) · captured {captured}"
    if dom_id == "CLI":
        n = len(raw.get("subcommands", []))
        return f"ONLINE       {n} subcommands · captured {captured}"
    return f"ONLINE       captured {captured}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--base-url",
        default=os.environ.get("SOVEREIGN_OS_BASE_URL", "http://localhost"),
        help="base URL of the sovereign-os master-dashboard api (default http://localhost)",
    )
    p.add_argument(
        "--node-exporter-url",
        default=DEFAULT_NODE_EXPORTER_URL,
        help=(
            "node_exporter /metrics URL for probing the selfdef-side "
            "doctor textfile observers (default http://localhost:9100/metrics; "
            "honors $SOVEREIGN_OS_NODE_EXPORTER_URL)"
        ),
    )
    p.add_argument(
        "--strict", action="store_true",
        help="require mirror_status=online for all 10 (exit 1 otherwise)",
    )
    p.add_argument(
        "--skip-doctor-observers", action="store_true",
        help=(
            "skip probing the selfdef-cli-mirror-doctor + selfdef-m060-doctor "
            "textfile observers via node_exporter (use when node_exporter is "
            "not reachable from the smoke host)"
        ),
    )
    p.add_argument(
        "--ms022-proxy-url",
        default=DEFAULT_MS022_PROXY_URL,
        help=(
            "MS022 SSE-quota proxy daemon URL (default http://localhost:7711; "
            "honors $SOVEREIGN_OS_MS022_PROXY_URL). The smoke also verifies "
            "the MS022 chain alongside the M060 chain"
        ),
    )
    p.add_argument(
        "--skip-ms022", action="store_true",
        help=(
            "skip probing the MS022 SSE-quota proxy daemon (use when MS022 "
            "is not deployed on this host)"
        ),
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

    # Daemon-side chain-health probe (separate from per-domain mirrors;
    # exposes the publish-freshness state which the per-domain probes
    # cannot detect — e.g. all artifacts present but all > 5 min stale).
    health_pr = probe(args.base_url, HEALTH_ENDPOINT)
    chain_state = "unreachable"
    chain_summary = None
    if health_pr["reachable"]:
        raw = health_pr["raw"]
        chain_state = str(raw.get("state") or "unknown")
        present = raw.get("artifacts_present", 0)
        expected = raw.get("artifacts_expected", 10)
        age = raw.get("newest_age_seconds")
        chain_summary = (
            f"{chain_state.upper()}  {present}/{expected} mirrors · "
            f"newest age {age if age is not None else '—'}s"
        )

    # Selfdef-side doctor textfile probes (one for each shipped
    # observer: cli-mirror-doctor + m060-chain doctor). Skipped if the
    # operator passed --skip-doctor-observers or node_exporter is on
    # an unreachable host.
    doctor_results: list[dict] = []
    if not args.skip_doctor_observers:
        for label, prefix in DOCTOR_TEXTFILE_PREFIXES:
            pr = probe_node_exporter_textfile(args.node_exporter_url, prefix)
            doctor_results.append({
                "id":          label,
                "prefix":      prefix,
                "reachable":   pr["reachable"],
                "worst":       pr["worst"],
                "age_seconds": pr["age_seconds"],
                "summary":     summarize_doctor(label, pr),
            })

    # MS022 SSE-quota chain probe. Skipped when the operator passes
    # --skip-ms022 (e.g. on hosts without the MS022 proxy deployed).
    ms022_result: dict | None = None
    if not args.skip_ms022:
        ms022_pr = probe_ms022_state(args.ms022_proxy_url)
        ms022_result = {
            "proxy_url": args.ms022_proxy_url,
            "reachable": ms022_pr["reachable"],
            "state":     ms022_pr["state"],
            "summary":   summarize_ms022(ms022_pr),
        }

    unreachable = [r for r in results if not r["reachable"]]
    offline = [r for r in results if r["reachable"] and r["mirror_status"] != "online"]
    online = [r for r in results if r["mirror_status"] == "online"]
    doctor_failed = [
        r for r in doctor_results
        if r["worst"] is not None and r["worst"] >= 2
    ]
    # MS022 saturated is a chain-fail signal — mirrors the doctor-fail
    # exit-code contract so CI scripts can rely on a single exit code
    # for "any observability vertical reports critical state".
    ms022_failed = bool(
        ms022_result is not None
        and ms022_result["reachable"]
        and ms022_result["state"] == "saturated"
    )

    if args.json:
        print(json.dumps({
            "base_url": args.base_url,
            "results": results,
            "chain_health": {
                "endpoint":     HEALTH_ENDPOINT,
                "reachable":    health_pr["reachable"],
                "state":        chain_state,
                "raw":          health_pr.get("raw") if health_pr["reachable"] else None,
            },
            "doctor_observers": {
                "node_exporter_url": args.node_exporter_url,
                "skipped":           args.skip_doctor_observers,
                "results":           doctor_results,
            },
            "ms022_sse_quota": {
                "skipped": args.skip_ms022,
                "result":  ms022_result,
                "failed":  ms022_failed,
            },
            "totals": {
                "online": len(online),
                "offline": len(offline),
                "unreachable": len(unreachable),
                "doctor_failed": len(doctor_failed),
                "ms022_failed": int(ms022_failed),
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
        if chain_summary is not None:
            print(f"{'chain health':<22} {chain_summary}")
        else:
            print(f"{'chain health':<22} UNREACHABLE  {HEALTH_ENDPOINT} not served (m060-health-api daemon down?)")
        if doctor_results:
            print(f"{'─' * 22} {'─' * 60}")
            for r in doctor_results:
                label = f"doctor {r['id']}"
                print(f"{label:<22} {r['summary']}")
        elif args.skip_doctor_observers:
            print(f"{'─' * 22} {'─' * 60}")
            print(f"{'doctor observers':<22} SKIPPED (--skip-doctor-observers)")
        # MS022 row — same cross-bar visual style as the M060 rows.
        print(f"{'─' * 22} {'─' * 60}")
        if ms022_result is not None:
            print(f"{'MS022 SSE quota':<22} {ms022_result['summary']}")
        else:
            print(f"{'MS022 SSE quota':<22} SKIPPED (--skip-ms022)")
        print(f"{'─' * 22} {'─' * 60}")
        print(
            f"summary: {len(online)} online · {len(offline)} offline · "
            f"{len(unreachable)} unreachable / {len(results)} total · "
            f"chain={chain_state} · doctor_failed={len(doctor_failed)} · "
            f"ms022_failed={int(ms022_failed)}"
        )

    # Exit logic:
    # - unreachable (any) → 1 (the proxy / api daemon is down)
    # - any doctor textfile reports worst=2 (FAIL) → 1
    # - MS022 reports state=saturated → 1 (mirrors the doctor-fail exit
    #   contract for the second observability vertical)
    # - chain state == unreachable/offline/stale under --strict → 1
    # - --strict + any per-domain offline → 1
    # - else → 0 (every endpoint at least responded)
    if unreachable:
        return 1
    if doctor_failed:
        return 1
    if ms022_failed:
        return 1
    if args.strict and chain_state in ("unreachable", "offline", "stale"):
        return 1
    if args.strict and offline:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
