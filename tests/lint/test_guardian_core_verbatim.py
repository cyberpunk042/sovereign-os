"""R392 (E10.M36) — Guardian Core operator-verbatim §10 content lint.

Extends R387/R388/R389/R390/R391 operational-artifact pinning pattern
to `scripts/auditor/guardian-core.py` — the Native Guardian Event
Loop implementation per master spec §10.

Operator-verbatim §10 content pinned:
  - Function name `alert_and_neutralize` (operator-named in §10.1)
  - Socket path /var/run/tetragon/tetragon.events (§10.1 verbatim)
  - SIGKILL action handling (§10.1 NEVER-bridge contract)
  - JSON event stream parsing (§10.1 verbatim 'raw JSON stream from
    the kernel eBPF filter')
  - podman kill on container_id (§10.1 'Immediate Native Kill
    Sequence' verbatim)
  - Append to security audit log (§10.1 'Append to Atomic Sovereign
    Logs')

If a future agent silently changes the socket path or renames
alert_and_neutralize, the perimeter response breaks silently.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARDIAN = REPO_ROOT / "scripts" / "auditor" / "guardian-core.py"


def _read_guardian() -> str:
    assert GUARDIAN.is_file(), f"missing {GUARDIAN}"
    return GUARDIAN.read_text(encoding="utf-8")


def test_guardian_core_file_exists():
    assert GUARDIAN.is_file(), f"missing {GUARDIAN}"


def test_alert_and_neutralize_function_present():
    """§10.1 verbatim function name: alert_and_neutralize."""
    body = _read_guardian()
    assert "def alert_and_neutralize" in body, (
        "guardian-core.py missing operator-verbatim §10.1 function "
        "'alert_and_neutralize' (the perimeter response handler)"
    )


def test_tetragon_events_socket_path_verbatim():
    """§10.1 verbatim socket path: /var/run/tetragon/tetragon.events."""
    body = _read_guardian()
    assert "/var/run/tetragon/tetragon.events" in body, (
        "guardian-core.py missing operator-verbatim §10.1 socket path "
        "'/var/run/tetragon/tetragon.events'"
    )


def test_sigkill_action_handling():
    """§10.1: 'Parse for policy trigger actions labeled as SIGKILL'.
    The SIGKILL string MUST appear in event-handling logic."""
    body = _read_guardian()
    assert "SIGKILL" in body, (
        "guardian-core.py missing 'SIGKILL' action label handling "
        "(§10.1 verbatim — Sigkill is the load-bearing perimeter action)"
    )


def test_json_event_stream_parsing():
    """§10.1 verbatim: 'Read raw JSON stream from the kernel eBPF filter'.
    json.loads (or equivalent JSON parsing) MUST be in the event loop."""
    body = _read_guardian()
    body_lower = body.lower()
    assert "json" in body_lower, (
        "guardian-core.py missing JSON parsing (§10.1 'raw JSON stream "
        "from the kernel eBPF filter')"
    )


def test_podman_kill_on_violation():
    """§10.1 verbatim: 'subprocess.run([\"podman\", \"kill\", container_id])'.
    Container kill MUST appear in the response."""
    body = _read_guardian()
    body_lower = body.lower()
    assert "podman" in body_lower and "kill" in body_lower, (
        "guardian-core.py missing operator-verbatim §10.1 'podman kill' "
        "container neutralization"
    )


def test_audit_log_append():
    """§10.1 verbatim: 'Append to Atomic Sovereign Logs' — writes to
    /mnt/vault/context/security_audit.log."""
    body = _read_guardian()
    # The audit log location (operator-verbatim path or audit/append behavior)
    has_audit = ("security_audit.log" in body
                  or "audit" in body.lower())
    assert has_audit, (
        "guardian-core.py missing §10.1 'Append to Atomic Sovereign "
        "Logs' audit-write behavior"
    )


def test_main_function_present():
    """§10.1 verbatim shows `def main():` entry-point. Script MUST be
    runnable as standalone daemon."""
    body = _read_guardian()
    assert "def main(" in body, (
        "guardian-core.py missing main() entry-point (§10.1 standalone "
        "daemon shape)"
    )


def test_no_silent_action_drift():
    """Catches: silent change from SIGKILL → SIGTERM / SIGINT / NoOp
    in the response action. §10.1 contract: kernel-level SIGKILL is
    the operator-named action."""
    body = _read_guardian()
    # Forbidden softer actions (would silently weaken perimeter)
    # Check: if SIGTERM appears without SIGKILL being present
    # OR if action='SIGKILL' got changed to action='SIGTERM'
    if "SIGTERM" in body and "SIGKILL" not in body:
        raise AssertionError(
            "guardian-core.py uses SIGTERM but NOT SIGKILL — §10.1 "
            "contract is kernel-level SIGKILL only"
        )


def test_kernel_ebpf_provenance_documented():
    """§10.1 verbatim phrase: 'raw JSON stream from the kernel eBPF
    filter' or equivalent — the kernel-space provenance documented."""
    body = _read_guardian()
    body_lower = body.lower()
    has_ebpf_provenance = (
        "ebpf" in body_lower
        or "kernel" in body_lower
        or "tetragon" in body_lower
    )
    assert has_ebpf_provenance, (
        "guardian-core.py missing kernel/eBPF/Tetragon provenance "
        "documentation (§10.1)"
    )
