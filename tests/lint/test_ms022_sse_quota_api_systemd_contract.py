"""MS022 SSE quota API systemd unit — contract test.

Locks the shape of the systemd unit that drives the
ms022-sse-quota-api.py proxy daemon (shipped in
sovereign-os commit 71127b3). Pairs with the existing
sovereign-m060-health-api.service template so operators reading
either know the other.

No systemd / dpkg here — the unit file is include_str-style read
and asserted against the canonical shape.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UNIT_PATH = REPO_ROOT / "systemd" / "system" / "sovereign-ms022-sse-quota-api.service"
SIBLING_PATH = REPO_ROOT / "systemd" / "system" / "sovereign-m060-health-api.service"


def _unit() -> str:
    return UNIT_PATH.read_text()


def _sibling() -> str:
    return SIBLING_PATH.read_text()


def test_unit_file_present():
    assert UNIT_PATH.is_file(), f"missing unit: {UNIT_PATH}"


def test_unit_invokes_ms022_proxy_script():
    body = _unit()
    assert "ExecStart=" in body
    assert "ms022-sse-quota-api.py" in body, (
        "unit must invoke ms022-sse-quota-api.py — drift would mean the "
        "service launches the wrong proxy"
    )
    assert "/usr/bin/python3" in body, (
        "unit must invoke via /usr/bin/python3 (stdlib-only — no venv)"
    )


def test_unit_advertises_read_only_observability_doctrine():
    """The unit's [Unit] comment block MUST mark it as a READ-ONLY
    observability proxy + reference R10212 so operators don't grep
    `systemctl cat` looking for mutation surfaces that don't exist."""
    body = _unit()
    assert "READ-ONLY observability" in body
    assert "R10212" in body
    assert "selfdef_sse_subscribers_" in body, (
        "unit comments must reference the producer metric prefix so an "
        "operator reading the systemd unit doesn't have to grep the script"
    )


def test_unit_after_network_target():
    """Same After= shape as the sibling so both proxies surface their "
    "unreachable state cleanly during boot."""
    body = _unit()
    assert "After=network.target" in body


def test_unit_is_type_simple_with_restart_on_failure():
    body = _unit()
    assert "Type=simple" in body
    assert "Restart=on-failure" in body
    assert "RestartSec=3" in body, (
        "RestartSec=3 matches the m060-health-api sibling — operators "
        "don't have to remember two restart rhythms"
    )


def test_unit_binds_to_loopback_by_default():
    """The proxy MUST default to 127.0.0.1 — operators exposing it
    beyond loopback do so explicitly via a drop-in."""
    body = _unit()
    assert "MS022_SSE_QUOTA_API_BIND=127.0.0.1" in body


def test_unit_port_does_not_collide_with_sibling():
    """The MS022 port MUST differ from the m060-health-api port (8160)
    so the two daemons coexist on the same host."""
    unit_body = _unit()
    sibling_body = _sibling()
    # Extract port lines from both.
    ms022_port = None
    m060_port = None
    for line in unit_body.splitlines():
        if "MS022_SSE_QUOTA_API_PORT=" in line:
            ms022_port = int(line.split("=")[-1])
    for line in sibling_body.splitlines():
        if "M060_HEALTH_API_PORT=" in line:
            m060_port = int(line.split("=")[-1])
    assert ms022_port is not None, "MS022 unit must set its port via Environment="
    assert m060_port is not None, "m060 sibling must set its port via Environment="
    assert ms022_port != m060_port, (
        f"MS022 port {ms022_port} collides with m060 sibling port {m060_port}"
    )


def test_unit_selfdef_socket_path_matches_sibling():
    """Both proxies use the same SELFDEF_SOCKET default. Drift would
    mean operators have to maintain two override paths."""
    unit_body = _unit()
    sibling_body = _sibling()
    assert "SELFDEF_SOCKET=/run/selfdef.sock" in unit_body
    assert "SELFDEF_SOCKET=/run/selfdef.sock" in sibling_body


def test_unit_hardening_matches_sibling_template():
    """R171 defense-in-depth posture — every directive that ships on
    the m060-health-api sibling MUST also ship on this unit. Drift
    means the new daemon runs with weaker hardening than its peer."""
    unit_body = _unit()
    for directive in (
        "ProtectSystem=strict",
        "ProtectClock=true",
        "ProtectHostname=true",
        "RestrictSUIDSGID=true",
        "NoNewPrivileges=true",
        "PrivateTmp=true",
        "ProtectHome=true",
        "ProtectKernelTunables=true",
        "ProtectKernelModules=true",
        "ProtectControlGroups=true",
        "RestrictNamespaces=true",
        "RestrictRealtime=true",
        "LockPersonality=true",
        "SystemCallArchitectures=native",
    ):
        assert directive in unit_body, (
            f"unit missing R171 hardening directive: {directive!r}"
        )


def test_unit_restricts_address_families_to_unix_and_inet():
    """The proxy needs AF_UNIX (selfdef socket) + AF_INET (TCP fallback +
    HTTP listen). Drift to a wider set would expose the daemon to
    address-family-based exploit techniques."""
    body = _unit()
    assert "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6" in body


def test_unit_does_not_grant_read_write_paths():
    """The MS022 proxy is pure-parse — it serves JSON and never writes
    a textfile or any other persistent state. Drift here would mean
    we accidentally exposed a write surface (R10212 violation)."""
    body = _unit()
    assert "ReadWritePaths=" not in body, (
        "MS022 proxy MUST NOT declare ReadWritePaths — it is pure-read; "
        "drift would expose an accidental mutation surface (R10212)"
    )


def test_unit_install_section_wantedby_multi_user():
    body = _unit()
    assert "[Install]" in body
    assert "WantedBy=multi-user.target" in body


def test_unit_documentation_link_present():
    body = _unit()
    assert "Documentation=" in body
    assert "ms022-sse-quota-api.py" in body  # repeated in Documentation line
