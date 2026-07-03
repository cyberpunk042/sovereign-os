"""panel.sh collision guard — the configurator's :8100 is sacrosanct.

Caught 2026-07-03: `sovereign-ux-design-audit-api` ships `PORT=8100`, the same
port the build configurator binds. Once panel.sh's API-discovery loop ran to
completion, it started that data API on :8100, and start_server's takeover
EVICTED the configurator — leaving the wrong daemon on :8100 so EVERY panel
answered "unknown endpoint". The guard makes panel.sh never start a data API
on a port owned by one of the two main servers (configurator / runtime
dashboard); the configurator serves that panel statically regardless.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PANEL = REPO / "scripts" / "operator" / "panel.sh"


def test_panel_guards_the_configurator_and_dashboard_ports():
    body = PANEL.read_text(encoding="utf-8")
    assert "collision guard" in body.lower(), (
        "panel.sh must carry the configurator-port collision guard"
    )
    # the guard skips any api whose resolved port equals a main-server port
    assert '"${port}" = "${CFG_PORT}"' in body, (
        "guard must compare the api port against the configurator port"
    )
    assert '"${port}" = "${DASH_PORT}"' in body, (
        "guard must compare the api port against the runtime-dashboard port"
    )
