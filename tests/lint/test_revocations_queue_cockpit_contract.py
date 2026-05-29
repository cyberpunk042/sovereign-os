"""SDD-067 MS5b — revocations-queue cockpit consumer contract test."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "cockpit" / "revocations-queue.py"
SERVE = REPO_ROOT / "scripts" / "dashboard" / "serve.py"


def _run(args: list[str], pending_path: Path | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if pending_path is not None:
        env["SOVEREIGN_OS_REVOCATIONS_PENDING_PATH"] = str(pending_path)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=10,
    )


def test_script_present_and_executable():
    assert SCRIPT.is_file()
    assert SCRIPT.stat().st_mode & 0o111


def test_default_pending_path_is_var_lib_selfdef_revocations():
    body = SCRIPT.read_text()
    assert "/var/lib/selfdef/revocations/pending-restores.json" in body


def test_honest_offline_when_pending_file_missing(tmp_path: Path):
    r = _run([], pending_path=tmp_path / "absent.json")
    assert r.returncode == 0
    assert "no pending" in r.stdout


def test_invalid_json_treated_as_empty(tmp_path: Path):
    bad = tmp_path / "g.json"
    bad.write_text("{not json")
    r = _run([], pending_path=bad)
    assert r.returncode == 0
    assert "no pending" in r.stdout


def test_json_mode_shape_with_real_entries(tmp_path: Path):
    pending = tmp_path / "p.json"
    pending.write_text(json.dumps([
        {"handle": {"Active": "rev-1"}, "user": "alice",
         "original_authority": "Responder",
         "original_reason": "anomaly", "seconds_remaining": 300,
         "scope": "Local"},
    ]))
    r = _run(["--json"], pending_path=pending)
    assert r.returncode == 0
    body = json.loads(r.stdout)
    assert body["count"] == 1
    e = body["queue"][0]
    assert e["user"] == "alice"
    assert e["restore_command"] == "selfdefctl restore-sessions 'rev-1'"


def test_queue_sorted_by_urgency_ascending(tmp_path: Path):
    pending = tmp_path / "p.json"
    pending.write_text(json.dumps([
        {"handle": {"Active": "a"}, "user": "u1",
         "original_authority": "Responder", "original_reason": "x",
         "seconds_remaining": 3000, "scope": "Local"},
        {"handle": {"Active": "b"}, "user": "u2",
         "original_authority": "Responder", "original_reason": "y",
         "seconds_remaining": 500, "scope": "Local"},
        {"handle": {"Active": "c"}, "user": "u3",
         "original_authority": "Responder", "original_reason": "z",
         "seconds_remaining": 1500, "scope": "Local"},
    ]))
    body = json.loads(_run(["--json"], pending_path=pending).stdout)
    users = [e["user"] for e in body["queue"]]
    secs = [e["seconds_remaining"] for e in body["queue"]]
    assert secs == [500, 1500, 3000]
    assert users == ["u2", "u3", "u1"]


def test_handle_with_apostrophe_safely_quoted(tmp_path: Path):
    pending = tmp_path / "p.json"
    pending.write_text(json.dumps([
        {"handle": {"Active": "rev-attacker's"}, "user": "alice",
         "original_authority": "Responder", "original_reason": "x",
         "seconds_remaining": 100, "scope": "Local"},
    ]))
    body = json.loads(_run(["--json"], pending_path=pending).stdout)
    cmd = body["queue"][0]["restore_command"]
    assert "rev-attacker'\\''s" in cmd


def test_source_ip_scope_displayed_in_human_mode(tmp_path: Path):
    """RevocationScope::SourceIp(addr) serializes as dict; the
    human renderer collapses to 'SrcIp' for the table column."""
    pending = tmp_path / "p.json"
    pending.write_text(json.dumps([
        {"handle": {"Active": "rev-x"}, "user": "alice",
         "original_authority": "Responder", "original_reason": "ip-scoped",
         "seconds_remaining": 60,
         "scope": {"SourceIp": "203.0.113.42"}},
    ]))
    r = _run([], pending_path=pending)
    assert r.returncode == 0
    assert "SrcIp" in r.stdout


def test_human_mode_shows_restore_command(tmp_path: Path):
    pending = tmp_path / "p.json"
    pending.write_text(json.dumps([
        {"handle": {"Active": "rev-z"}, "user": "alice",
         "original_authority": "Responder", "original_reason": "smoke",
         "seconds_remaining": 60, "scope": "Local"},
    ]))
    r = _run([], pending_path=pending)
    assert r.returncode == 0
    assert "restore: $ selfdefctl restore-sessions 'rev-z'" in r.stdout


def test_dashboard_serve_registers_revocations_queue_card():
    body = SERVE.read_text()
    assert "card_revocations_queue" in body
    assert "SDD-067 — pending session-revocation restore decisions" in body


def test_dashboard_card_invokes_cockpit_script_path():
    body = SERVE.read_text()
    assert "scripts\" / \"cockpit\" / \"revocations-queue.py\"" in body \
        or "scripts/cockpit/revocations-queue.py" in body
