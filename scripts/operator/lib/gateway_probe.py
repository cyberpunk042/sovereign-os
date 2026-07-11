#!/usr/bin/env python3
"""
scripts/operator/lib/gateway_probe.py — shared, read-only probe of the live
Sovereign Gateway daemon (sovereign-gatewayd, M048 provider-inversion gateway
over the deterministic cortex engine; default 127.0.0.1:8787).

Why this exists: the per-panel api daemons (trinity-api, model-health-api, …)
are same-origin to the browser, but the gateway binds a DIFFERENT port, so a
panel's browser fetch to :8787 would be cross-origin and CORS-blocked. This
helper lets a same-origin daemon probe the gateway SERVER-SIDE and fold the
result into its own JSON feed — the cockpit thereby reflects the REAL running
brain (routing ledger, sovereignty tripwire, persisted memory) without the
browser ever touching :8787.

Read-only by construction: it issues only GET /health, GET /admin/ledger and
GET /manifest against the gateway, and it reads (never writes) the persisted
Memory-OS snapshot. It NEVER POSTs — a routing probe that learns is a separate,
explicit operator action, not a passive panel refresh.

Sovereignty (stdlib-only — zero added deps): urllib + json only. Every failure
degrades to a structured `{up: False, error: …}` so a panel renders "gateway
down" instead of 500ing.

Env vars:
  SOVEREIGN_GATEWAY_ADDR    host:port of the gateway   (default 127.0.0.1:8787)
  SOVEREIGN_GATEWAY_MEMORY  persisted snapshot path     (default
                            /var/lib/sovereign-os/memory/cortex.json)

CLI:
  python3 gateway_probe.py            # print the probe as JSON (for osctl/tests)
  python3 gateway_probe.py --addr 127.0.0.1:8790
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_ADDR = "127.0.0.1:8787"
DEFAULT_MEMORY = "/var/lib/sovereign-os/memory/cortex.json"


def _gateway_addr(addr: str | None) -> str:
    if addr:
        return addr
    return os.environ.get("SOVEREIGN_GATEWAY_ADDR", DEFAULT_ADDR)


def _memory_path() -> str:
    return os.environ.get("SOVEREIGN_GATEWAY_MEMORY", DEFAULT_MEMORY)


def _get_json(url: str, timeout: float) -> tuple[dict | None, str | None]:
    """GET a JSON body; return (payload, error). Never raises."""
    try:
        req = urllib.request.Request(url, method="GET",
                                     headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (loopback)
            raw = r.read().decode("utf-8", "replace")
        return json.loads(raw), None
    except urllib.error.URLError as e:
        return None, getattr(e, "reason", str(e)).__str__()
    except (OSError, ValueError, json.JSONDecodeError) as e:
        return None, str(e)


def _probe_memory(path: str) -> dict:
    """Read the persisted Memory-OS snapshot (read-only) → item counts + mtime.

    Works even when the gateway daemon is down, since the file is the durable
    state on disk. Makes the activation-#2 persistence milestone visible in the
    cockpit: how many learned/seed items the brain is carrying, and when it last
    snapshotted."""
    mem: dict = {"path": path, "exists": False, "items": None,
                 "cold": None, "capacity": None, "mtime": None, "error": None}
    try:
        st = os.stat(path)
        mem["exists"] = True
        mem["mtime"] = int(st.st_mtime)
    except OSError as e:
        mem["error"] = str(e)
        return mem
    try:
        with open(path, encoding="utf-8") as f:
            store = json.load(f)
        hot = store.get("hot")
        cold = store.get("cold")
        mem["items"] = len(hot) if isinstance(hot, list) else None
        mem["cold"] = len(cold) if isinstance(cold, dict) else None
        mem["capacity"] = store.get("capacity")
    except (OSError, ValueError, json.JSONDecodeError) as e:
        mem["error"] = str(e)
    return mem


def probe_gateway(addr: str | None = None, timeout: float = 2.0) -> dict:
    """Probe the live gateway + persisted memory. Never raises; always returns a
    structured dict a panel can render, up or down."""
    addr = _gateway_addr(addr)
    base = f"http://{addr}"
    out: dict = {
        "addr": addr,
        "up": False,
        "error": None,
        "health": None,
        "ledger": None,
        "doctrine": None,
        "surfaces": [],
        "memory": _probe_memory(_memory_path()),
    }

    health, herr = _get_json(f"{base}/health", timeout)
    if health is None:
        out["error"] = herr or "unreachable"
        return out  # daemon down — memory (from disk) is still populated above
    out["up"] = True
    out["health"] = health.get("health", health)

    ledger, _ = _get_json(f"{base}/admin/ledger", timeout)
    if ledger is not None:
        out["ledger"] = ledger.get("ledger", ledger)

    manifest, _ = _get_json(f"{base}/manifest", timeout)
    if manifest is not None:
        man = manifest.get("manifest", manifest)
        out["doctrine"] = man.get("doctrine")
        out["surfaces"] = man.get("surfaces", [])

    return out


def _human(d: dict) -> str:
    """A concise operator-readable summary of the probe."""
    lines = []
    up = d.get("up")
    lines.append(f"gateway {d.get('addr')}: "
                 + ("UP" if up else f"DOWN ({d.get('error')})"))
    if up:
        h = d.get("health") or {}
        L = d.get("ledger") or {}
        holds = (h.get("never_cloud_spill_holds") is not False
                 and (h.get("cloud_spills") or 0) == 0)
        if holds:
            fl = "on" if h.get("force_local") else "off"
            lines.append(f"  sovereignty: SOVEREIGN — 0 cloud spills, force-local {fl}")
        else:
            lines.append(f"  sovereignty: CLOUD SPILL ({h.get('cloud_spills')}) — invariant BROKEN")
        lines.append(
            f"  requests={L.get('total_requests', 0)} "
            f"committed={L.get('committed', 0)} learned={L.get('learned', 0)} "
            f"refused={L.get('refused', 0)}")
        by = L.get("by_role") or {}
        if by:
            lines.append("  by role: "
                         + ", ".join(f"{k}={v}" for k, v in by.items()))
        live = [s.get("surface") for s in d.get("surfaces", [])
                if s.get("state") == "live"]
        lines.append(f"  live surfaces: {len(live)}"
                     + (f" ({', '.join(live)})" if live else ""))
    mem = d.get("memory") or {}
    if mem.get("exists"):
        lines.append(f"  persisted memory: {mem.get('items')} items @ {mem.get('path')}")
    else:
        lines.append(f"  persisted memory: none @ {mem.get('path')}")
    return "\n".join(lines)


def main() -> int:
    addr = None
    argv = sys.argv[1:]
    if "--addr" in argv:
        i = argv.index("--addr")
        if i + 1 < len(argv):
            addr = argv[i + 1]
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    probe = probe_gateway(addr)
    if "--json" in argv:
        print(json.dumps(probe, indent=2))
    else:
        print(_human(probe))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
