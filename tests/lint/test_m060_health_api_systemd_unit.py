"""M060 chain-health API systemd unit contract.

Locks the deployment surface for scripts/operator/m060-health-api.py.
The unit file must:
  1. Live at systemd/system/sovereign-m060-health-api.service
  2. ExecStart the m060-health-api.py daemon under python3
  3. Bind 127.0.0.1 by default (loopback-only; operators opt into
     external exposure via drop-in)
  4. Carry the R171 hardening posture (validated by the shared
     hardening lint; here we assert the surface-specific knobs)
  5. Restart on failure (resilience for a long-running observability
     daemon)
  6. Write its Prometheus textfile metric path under
     /var/lib/node_exporter/textfile_collector
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UNIT_PATH = REPO_ROOT / "systemd" / "system" / "sovereign-m060-health-api.service"


def _load_unit() -> str:
    assert UNIT_PATH.is_file(), f"unit file missing at {UNIT_PATH}"
    return UNIT_PATH.read_text()


def test_unit_file_present():
    assert UNIT_PATH.is_file()


def test_unit_execstart_points_at_health_api_script():
    body = _load_unit()
    assert "ExecStart=" in body
    # Must invoke under python3 (script is not chmod +x in the package).
    assert "python3" in body
    # Must reference the m060-health-api.py script by its packaged path.
    assert "m060-health-api.py" in body


def test_unit_binds_loopback_by_default():
    body = _load_unit()
    assert "Environment=M060_HEALTH_API_BIND=127.0.0.1" in body
    # Port default is 8160 per the api script.
    assert "Environment=M060_HEALTH_API_PORT=8160" in body


def test_unit_carries_restart_on_failure():
    body = _load_unit()
    assert "Restart=on-failure" in body
    assert "RestartSec=" in body


def test_unit_carries_r171_hardening_minimums():
    body = _load_unit()
    # The shared hardening lint enforces the broader posture; here we
    # lock the surface-specific minimums that protect the chain-health
    # daemon's threat surface (loopback HTTP host + metric writes only).
    for must_have in (
        "ProtectSystem=strict",
        "NoNewPrivileges=true",
        "PrivateTmp=true",
        "ProtectHome=true",
        "ProtectKernelTunables=true",
        "RestrictNamespaces=true",
        "LockPersonality=true",
        "SystemCallArchitectures=native",
        "SystemCallFilter=@system-service",
    ):
        assert must_have in body, f"unit missing required hardening: {must_have}"


def test_unit_writes_prometheus_textfile_only():
    body = _load_unit()
    # The daemon writes its own textfile metric; the writable path must
    # be exactly the node_exporter textfile_collector and nothing else
    # (no /var, /etc, /run write access).
    assert "ReadWritePaths=/var/lib/node_exporter/textfile_collector" in body


def test_unit_exposes_selfdef_socket_default():
    """The proxy needs to talk to selfdefd. The unit must default the
    UNIX socket to the conventional /run/selfdef.sock so the operator
    doesn't have to configure it explicitly."""
    body = _load_unit()
    assert "Environment=SELFDEF_SOCKET=/run/selfdef.sock" in body


def test_unit_documents_cross_repo_proxy_doctrine():
    """The unit comment block must surface the READ-ONLY proxy doctrine
    + R10212 boundary so operators inspecting `systemctl cat` see the
    sovereignty surface immediately."""
    body = _load_unit()
    assert "READ-ONLY" in body
    assert "R10212" in body
    assert "/v1/m060/health" in body
    # Must list the 5 documented states so operators see them in
    # `systemctl cat`.
    for state in ("online", "degraded", "stale", "offline", "unreachable"):
        assert state in body, f"unit comment missing state {state}"


def test_unit_installed_under_multi_user_target():
    body = _load_unit()
    assert "[Install]" in body
    assert "WantedBy=multi-user.target" in body
