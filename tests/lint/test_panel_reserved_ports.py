#!/usr/bin/env python3
"""
tests/lint/test_panel_reserved_ports.py — no panel data-API unit may claim a port
reserved by one of panel.sh's own main servers (F-2026-075 / SDD-988).

`scripts/operator/panel.sh` starts three long-lived main servers on reserved
ports — the build configurator (`CFG_PORT`, default 8100), the runtime dashboard
(`DASH_PORT` from `DASH_BIND`, default 8443), and the live-reload broker
(`LR_PORT`, default 8136) — then loops over `scripts/operator/*-api.py`, starting
each on the port declared in its systemd unit. It carries a *runtime* collision
guard (skip any data API whose unit port equals `CFG_PORT`/`DASH_PORT`) that
exists only because of a real incident: `sovereign-ux-design-audit-api` shipped
`PORT=8100 == CFG_PORT`, and `start_server`'s takeover evicted the configurator so
every panel 404'd (2026-07-03). That guard is load-bearing tribal knowledge in a
comment; this promotes it to a CI-time contract.

It reads the reserved ports from **panel.sh itself** (its `VAR="${ENV:-DEFAULT}"`
defaults — the same single source the runtime guard uses, so the two can't drift)
and fails if any `sovereign-*-api.service` unit declares one. The owning services
(`sovereign-dashboards.service` on 8100, etc.) are NOT `*-api.service` units, so
they are correctly excluded. Pairs with
`test_dashboard_port_and_reference_integrity.py` (no two units share a port); this
adds the orthogonal "no data-API unit sits on a reserved main-server port."

Stdlib + pytest only.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PANEL = REPO / "scripts" / "operator" / "panel.sh"
UNITS = REPO / "systemd" / "system"

# var name -> human label; each is defined in panel.sh as VAR="${ENV:-DEFAULT}"
# where DEFAULT is either a bare port or host:port.
_RESERVED_VARS = {
    "CFG_PORT": "build configurator",
    "DASH_BIND": "runtime dashboard",
    "LR_PORT": "live-reload broker",
}


def _reserved_ports() -> dict[int, str]:
    text = PANEL.read_text(encoding="utf-8")
    out: dict[int, str] = {}
    for var, label in _RESERVED_VARS.items():
        m = re.search(rf'{var}="\$\{{[A-Z_]+:-([0-9.:]+)\}}"', text)
        assert m, (
            f"could not parse panel.sh's {var} default — the reserved-port "
            f"contract can't verify what it can't read (did panel.sh's format change?)"
        )
        port = int(m.group(1).split(":")[-1])  # host:port -> port, or bare port
        out[port] = label
    return out


def _api_unit_ports() -> dict[int, list[str]]:
    ports: dict[int, list[str]] = {}
    for f in sorted(UNITS.glob("sovereign-*-api.service")):
        m = re.search(r"Environment=[A-Z0-9_]*PORT=(\d+)", f.read_text(encoding="utf-8"))
        if m:
            ports.setdefault(int(m.group(1)), []).append(f.stem)
    return ports


def test_reserved_ports_are_readable():
    """All three reserved ports must parse — so a panel.sh format change that
    breaks parsing fails loudly here instead of silently passing the contract."""
    reserved = _reserved_ports()
    assert len(reserved) == len(_RESERVED_VARS), (
        f"parsed {len(reserved)} reserved ports, expected {len(_RESERVED_VARS)}"
    )


def test_no_api_unit_claims_a_reserved_port():
    reserved = _reserved_ports()
    api_ports = _api_unit_ports()
    clashes = {
        p: (reserved[p], units) for p, units in api_ports.items() if p in reserved
    }
    assert not clashes, (
        "panel data-API systemd unit(s) declare a port reserved by a panel.sh "
        "main server — start_server's takeover would evict the main server "
        "(the 2026-07-03 ux-design-audit-api:8100 incident):\n  "
        + "\n  ".join(
            f":{p} (reserved for the {label}) claimed by {', '.join(units)}"
            for p, (label, units) in sorted(clashes.items())
        )
        + "\n\nGive the data API a free port in its systemd unit "
        "(F-2026-075 / SDD-988)."
    )
