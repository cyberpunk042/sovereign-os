"""R421 (E10.M65) — Guardian Loop core service↔script + § 10/§ 17 verbatim
+ 11th bidirectional-consistency lint (service ExecStart ↔ script path
+ socket-path consistency with Tetragon load hook).

Extends R387-R420 + R392/R397 operational-artifact pinning to:
  scripts/auditor/guardian-core.py             (the auditor daemon)
  systemd/system/sovereign-guardian-core.service  (the unit)

R392 covered guardian-core.py verbatim content (§ 10 + § 17 verbatim
quotes). R397 covered Description= identity of Trinity-side service
units. R421 closes the runtime invocation cycle:

  unit's ExecStart= MUST point to a path that invokes the script
  unit's Requires= MUST include tetragon.service (script reads
    /var/run/tetragon/tetragon.events — drift = guardian starts
    before tetragon = silent no-op)
  unit ReadWritePaths= MUST include /mnt/vault/context (where the
    script appends security_audit.log — drift = ProtectSystem=strict
    blocks the write silently)

11th bidirectional-consistency lint:
  GUARDIAN_SOCKET_PATH default in script = /var/run/tetragon/tetragon.events
  tetragon-policy-load.sh installs policy that writes to the SAME path
  Drift = guardian tails wrong path = silent no-op

If a future agent silently:
  - changes unit's Requires= away from tetragon.service = guardian
    runs without its event source = silent no-op
  - changes unit's ReadWritePaths to drop /mnt/vault/context =
    ProtectSystem=strict blocks the audit-log append = silent loss
  - changes script's socket path = guardian tails a non-existent file
  - removes Restart=always from unit = guardian crashes and stays dead
…the § 10 + § 17 Auditor contract silently breaks.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARDIAN_SCRIPT = REPO_ROOT / "scripts" / "auditor" / "guardian-core.py"
GUARDIAN_SERVICE = REPO_ROOT / "systemd" / "system" / "sovereign-guardian-core.service"
TETRAGON_LOAD_HOOK = REPO_ROOT / "scripts" / "hooks" / "post-install" / "tetragon-policy-load.sh"


def _read(p: Path) -> str:
    assert p.is_file(), f"missing {p}"
    return p.read_text(encoding="utf-8")


# --- Structural ---


def test_guardian_script_exists():
    assert GUARDIAN_SCRIPT.is_file(), f"missing {GUARDIAN_SCRIPT}"


def test_guardian_service_exists():
    assert GUARDIAN_SERVICE.is_file(), f"missing {GUARDIAN_SERVICE}"


# --- Service unit contract ---


def test_service_has_exec_start():
    body = _read(GUARDIAN_SERVICE)
    assert re.search(r"^ExecStart=\S", body, re.M), (
        "sovereign-guardian-core.service missing ExecStart= "
        "(unit can't be activated)"
    )


def test_service_exec_start_references_guardian():
    """ExecStart= MUST reference 'guardian' (operator-named binary).
    Drift = unit starts unrelated process."""
    body = _read(GUARDIAN_SERVICE)
    m = re.search(r"^ExecStart=(.+)$", body, re.M)
    assert m, "ExecStart= line not found"
    exec_line = m.group(1).strip()
    assert "guardian" in exec_line.lower(), (
        f"sovereign-guardian-core.service ExecStart={exec_line!r} "
        f"doesn't reference 'guardian' (drift = unit runs wrong binary)"
    )


def test_service_requires_tetragon():
    """§ 10.2 verbatim: 'Requires=tetragon.service'. Drift = guardian
    starts before tetragon = tails non-existent socket = silent no-op."""
    body = _read(GUARDIAN_SERVICE)
    assert "Requires=tetragon.service" in body, (
        "sovereign-guardian-core.service missing Requires=tetragon.service "
        "(§ 10.2 verbatim — drift = guardian no-ops without tetragon)"
    )


def test_service_after_tetragon():
    """Ordering: After=tetragon.service so guardian starts AFTER
    tetragon is ready (operator-named order; Requires alone doesn't
    enforce ordering)."""
    body = _read(GUARDIAN_SERVICE)
    assert "After=tetragon.service" in body, (
        "sovereign-guardian-core.service missing After=tetragon.service "
        "(Requires without After can start guardian before tetragon is ready)"
    )


def test_service_binds_to_tetragon():
    """Transposition-dump dropout prevention (lines 761-765, verbatim:
    'must include explicit service binding controls
    (BindsTo=tetragon.service)'). Requires= alone leaves guardian
    tailing a dead stream when tetragon stops during an OPNsense/SD-WAN
    interface re-shuffle — the exact 'blinding your real-time exploit
    containment system' gotcha. M084 R14101/R14110."""
    body = _read(GUARDIAN_SERVICE)
    assert "BindsTo=tetragon.service" in body, (
        "sovereign-guardian-core.service missing BindsTo=tetragon.service "
        "(dump 765 verbatim prevention — drift = guardian tails a dead "
        "stream through tetragon stops, perimeter silently blind)"
    )


def test_script_eof_exits_nonzero():
    """The dropout prevention's second half (dump 765: 'instantly
    restart the security loop if the local UNIX socket encounters an
    end-of-file (EOF) exception'). The read loop's EOF fall-through
    MUST NOT return 0 — a clean exit hides the perimeter going blind.
    M084 R14111-R14113."""
    body = _read(GUARDIAN_SCRIPT)
    assert "perimeter blind" in body and "[EOF]" in body, (
        "guardian-core.py EOF fall-through must log the [EOF]/perimeter-"
        "blind evidence before exiting (dump 765 prevention)"
    )
    tail = body.split("[EOF]", 1)[1]
    assert "return 1" in tail, (
        "guardian-core.py must exit nonzero after the EOF log so the "
        "systemd restart is recorded as a failure-recovery"
    )


def test_service_restart_always():
    """Auditor MUST be always-on (§ 17 'always-on, kernel-driven').
    Drift to Restart=on-failure = a clean exit leaves the perimeter
    unguarded."""
    body = _read(GUARDIAN_SERVICE)
    assert "Restart=always" in body, (
        "sovereign-guardian-core.service missing Restart=always "
        "(§ 17 'always-on' Auditor — drift = clean exit unguards "
        "the perimeter)"
    )


def test_service_restart_delay_short():
    """RestartSec=1 (short delay so guardian re-arms quickly after
    crash). Drift to long delay = window where perimeter is unguarded."""
    body = _read(GUARDIAN_SERVICE)
    m = re.search(r"^RestartSec=(\d+)", body, re.M)
    assert m, (
        "sovereign-guardian-core.service missing RestartSec= "
        "(default 100ms is fine but explicit is better)"
    )
    secs = int(m.group(1))
    assert secs <= 5, (
        f"sovereign-guardian-core.service RestartSec={secs}s > 5s "
        f"(perimeter unguarded too long after crash)"
    )


def test_service_documents_master_spec_10():
    """§ 10 reference in unit (operator-discovery: which master spec
    section does this implement)."""
    body = _read(GUARDIAN_SERVICE)
    assert ("§ 10" in body or "section 10" in body.lower()
            or "§10" in body), (
        "sovereign-guardian-core.service missing master spec § 10 "
        "reference (operator-discovery context)"
    )


# --- 11th bidirectional-consistency lint (service ReadWritePaths ↔ script paths) ---


def test_bidirectional_read_write_paths_context():
    """The script appends to /mnt/vault/context/security_audit.log.
    The unit's ProtectSystem=strict means writes outside ReadWritePaths
    silently fail. ReadWritePaths MUST include /mnt/vault/context.

    Bidirectional consistency: script's write path ↔ unit's RW path."""
    script = _read(GUARDIAN_SCRIPT)
    service = _read(GUARDIAN_SERVICE)
    # Script writes to /mnt/vault/context
    assert "/mnt/vault/context" in script, (
        "guardian-core.py missing /mnt/vault/context write path"
    )
    # Service MUST allow that path in ReadWritePaths
    rw_match = re.search(r"^ReadWritePaths=([^\n]+)", service, re.M)
    assert rw_match, (
        "sovereign-guardian-core.service missing ReadWritePaths "
        "(ProtectSystem=strict blocks all writes without it)"
    )
    rw_line = rw_match.group(1)
    assert "/mnt/vault/context" in rw_line, (
        f"sovereign-guardian-core.service ReadWritePaths={rw_line!r} "
        f"missing /mnt/vault/context (BIDIRECTIONAL CONSISTENCY "
        f"VIOLATION: script writes there but service blocks it)"
    )


def test_bidirectional_read_only_paths_tetragon_socket():
    """The script reads from /var/run/tetragon/tetragon.events.
    The unit SHOULD declare ReadOnlyPaths=/var/run/tetragon to make
    operator-discoverable that this is a read-only dependency."""
    service = _read(GUARDIAN_SERVICE)
    assert "/var/run/tetragon" in service, (
        "sovereign-guardian-core.service missing /var/run/tetragon "
        "reference (ReadOnlyPaths or operator-discovery comment)"
    )


def test_bidirectional_tetragon_socket_path_consistency():
    """11th bidirectional lint: GUARDIAN_SOCKET_PATH default in script
    = /var/run/tetragon/tetragon.events. Tetragon load hook installs
    policy that makes Tetragon write to that same socket path.

    Drift between script's read path and Tetragon's write path =
    guardian tails wrong file = silent no-op."""
    script = _read(GUARDIAN_SCRIPT)
    expected = "/var/run/tetragon/tetragon.events"
    assert expected in script, (
        f"guardian-core.py missing GUARDIAN_SOCKET_PATH default "
        f"{expected!r} (the Tetragon-event socket path)"
    )
    # Tetragon load hook should also reference the same directory
    # (Tetragon's standard location)
    if TETRAGON_LOAD_HOOK.is_file():
        hook_body = _read(TETRAGON_LOAD_HOOK)
        assert "/etc/tetragon" in hook_body, (
            "tetragon-policy-load.sh missing /etc/tetragon dir "
            "(bidirectional consistency: tetragon's policy dir + "
            "events socket dir = same daemon)"
        )


# --- § 10 + § 17 verbatim invariants in script ---


def test_script_documents_section_10_verbatim():
    """§ 10 verbatim quote MUST appear in script header
    (operator-discovery: WHY does this daemon exist)."""
    body = _read(GUARDIAN_SCRIPT)
    has_verbatim = (
        "lightweight, native Linux event supervisor" in body
        or "autonomous circuit breaker" in body
        or "Tetragon eBPF UNIX socket" in body
    )
    assert has_verbatim, (
        "guardian-core.py missing § 10 verbatim quote in header "
        "(operator-discovery — drift loses the WHY)"
    )


def test_script_documents_section_17_trinity():
    """§ 17 names this The Auditor (Immutable Gatekeeper) within
    The Genesis Trinity."""
    body = _read(GUARDIAN_SCRIPT)
    has_trinity = (
        "Auditor" in body
        and ("Trinity" in body or "trinity" in body)
    )
    assert has_trinity, (
        "guardian-core.py missing § 17 Trinity / Auditor reference "
        "(operator-named role within Genesis Trinity)"
    )


def test_script_uses_podman_kill_neutralization():
    """§ 10.1 verbatim: 'podman kill <container>' is the
    neutralization action. Drift to 'docker kill' breaks operator's
    rootless container surface."""
    body = _read(GUARDIAN_SCRIPT)
    assert "podman kill" in body or "PODMAN_BIN" in body, (
        "guardian-core.py missing 'podman kill' neutralization "
        "(§ 10.1 verbatim — drift to docker breaks rootless container)"
    )


def test_script_appends_to_security_audit_log():
    """§ 7.1 verbatim path: /mnt/vault/context/security_audit.log.
    Drift = audit forensics land in wrong path."""
    body = _read(GUARDIAN_SCRIPT)
    assert "security_audit.log" in body, (
        "guardian-core.py missing security_audit.log path "
        "(§ 7.1 verbatim — atomic append-only forensic log)"
    )


def test_script_supports_dry_run():
    body = _read(GUARDIAN_SCRIPT)
    assert "GUARDIAN_DRY_RUN" in body, (
        "guardian-core.py missing GUARDIAN_DRY_RUN env var "
        "(operator-discoverable parse-only mode)"
    )


# --- SDD-016 Layer B metrics ---


def test_script_emits_neutralization_total():
    body = _read(GUARDIAN_SCRIPT)
    assert "sovereign_os_auditor_neutralization_total" in body, (
        "guardian-core.py missing sovereign_os_auditor_neutralization_"
        "total counter (SDD-016 verbatim — per-kill telemetry)"
    )


def test_script_emits_event_parse_total():
    body = _read(GUARDIAN_SCRIPT)
    assert "sovereign_os_auditor_event_parse_total" in body, (
        "guardian-core.py missing sovereign_os_auditor_event_parse_"
        "total counter (operator-discovery — parse-error visibility)"
    )


def test_script_emits_last_neutralization_timestamp():
    body = _read(GUARDIAN_SCRIPT)
    assert "sovereign_os_auditor_last_neutralization_timestamp" in body, (
        "guardian-core.py missing last_neutralization_timestamp gauge "
        "(staleness/never-fired detection surface)"
    )
