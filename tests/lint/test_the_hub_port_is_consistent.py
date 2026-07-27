"""Launcher, kiosk URL and service must agree on the hub port.

2026-07-27. Three things reference the dashboard hub:

  * the .desktop launcher (app menu, desktop icon, login autostart)
  * FRONTEND_KIOSK_URL, used by the kiosk frontend
  * sovereign-dashboards.service, which actually binds the port

DASH_PORT (SOVEREIGN_OS_DASHBOARD_PORT) drove the middle one only. The launcher
hardcoded 8100 and the unit hardcoded 8100, so a custom port produced a kiosk
pointing at nothing.

Rendering just the launcher would have swapped one mismatch for another — icon
on the custom port, service still on 8100. All three are now derived from
DASH_PORT, the service via a systemd drop-in.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASH = REPO_ROOT / "scripts" / "install" / "install-gui-dashboards.sh"
UNIT = REPO_ROOT / "systemd" / "system" / "sovereign-dashboards.service"
LAUNCHER = REPO_ROOT / "share" / "applications" / "sovereign-dashboards.desktop"


def body() -> str:
    return "\n".join(l for l in DASH.read_text(encoding="utf-8").splitlines()
                     if not l.lstrip().startswith("#"))


def test_the_shipped_defaults_agree():
    """With no override, all three must already be the same port."""
    unit_port = re.search(r"BUILD_CONFIGURATOR_API_PORT=(\d+)", UNIT.read_text(encoding="utf-8"))
    exec_port = re.search(r"Exec=xdg-open http://127\.0\.0\.1:(\d+)/",
                          LAUNCHER.read_text(encoding="utf-8"))
    default = re.search(r'DASH_PORT="\$\{SOVEREIGN_OS_DASHBOARD_PORT:-(\d+)\}"', body())
    assert unit_port and exec_port and default, "could not locate all three ports"
    assert unit_port.group(1) == exec_port.group(1) == default.group(1), (
        f"shipped ports disagree: unit={unit_port.group(1)} "
        f"launcher={exec_port.group(1)} default={default.group(1)}"
    )


def test_the_launcher_follows_a_custom_port():
    assert "Exec=xdg-open http://127.0.0.1:${DASH_PORT}/" in body(), (
        "the launcher URL must be rendered from DASH_PORT, or the desktop icon "
        "opens a port nothing listens on"
    )


def test_the_service_follows_a_custom_port():
    code = body()
    assert "sovereign-dashboards.service.d" in code and "BUILD_CONFIGURATOR_API_PORT" in code, (
        "the unit hardcodes the port; a custom DASH_PORT needs a drop-in, or "
        "rendering the launcher alone just moves the mismatch"
    )
    # ...and the drop-in must be written BEFORE the unit is enabled.
    assert code.index("sovereign-dashboards.service.d") < code.index("enable_unit sovereign-dashboards.service"), (
        "write the drop-in before enabling, so the first start already binds "
        "the configured port"
    )
