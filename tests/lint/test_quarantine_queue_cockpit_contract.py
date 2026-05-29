"""SDD-066 MS5b — quarantine-queue cockpit consumer contract test."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "cockpit" / "quarantine-queue.py"
SERVE = REPO_ROOT / "scripts" / "dashboard" / "serve.py"


def _run(args: list[str], pending_path: Path | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if pending_path is not None:
        env["SOVEREIGN_OS_QUARANTINE_PENDING_PATH"] = str(pending_path)
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


def test_default_pending_path_is_var_lib_selfdef_quarantine():
    body = SCRIPT.read_text()
    assert "/var/lib/selfdef/quarantine/pending-releases.json" in body


def test_honest_offline_when_pending_file_missing(tmp_path: Path):
    r = _run([], pending_path=tmp_path / "absent.json")
    assert r.returncode == 0
    assert "no pending" in r.stdout


def test_invalid_json_treated_as_empty(tmp_path: Path):
    bad = tmp_path / "garbage.json"
    bad.write_text("{not json")
    r = _run([], pending_path=bad)
    assert r.returncode == 0
    assert "no pending" in r.stdout


def test_json_mode_shape_with_real_entries(tmp_path: Path):
    pending = tmp_path / "p.json"
    pending.write_text(json.dumps([
        {"handle": {"Active": "qpr-1"}, "pid": 12345,
         "original_authority": "Responder",
         "original_reason": "anomaly",
         "seconds_remaining": 300,
         "scope": "Process"},
    ]))
    r = _run(["--json"], pending_path=pending)
    assert r.returncode == 0
    body = json.loads(r.stdout)
    assert body["count"] == 1
    e = body["queue"][0]
    assert e["pid"] == 12345
    # Both release + kill commands pre-rendered.
    assert "selfdefctl release-pid 'qpr-1'" == e["release_command"]
    assert "selfdefctl kill-quarantined 'qpr-1' --signal TERM" == e["kill_term_command"]
    assert "selfdefctl kill-quarantined 'qpr-1' --signal KILL" == e["kill_kill_command"]


def test_queue_sorted_by_urgency_ascending(tmp_path: Path):
    pending = tmp_path / "p.json"
    pending.write_text(json.dumps([
        {"handle": {"Active": "a"}, "pid": 1,
         "original_authority": "Responder", "original_reason": "x",
         "seconds_remaining": 3000, "scope": "Process"},
        {"handle": {"Active": "b"}, "pid": 2,
         "original_authority": "Responder", "original_reason": "y",
         "seconds_remaining": 500, "scope": "Process"},
        {"handle": {"Active": "c"}, "pid": 3,
         "original_authority": "Responder", "original_reason": "z",
         "seconds_remaining": 1500, "scope": "Process"},
    ]))
    body = json.loads(_run(["--json"], pending_path=pending).stdout)
    pids = [e["pid"] for e in body["queue"]]
    secs = [e["seconds_remaining"] for e in body["queue"]]
    assert secs == [500, 1500, 3000]
    assert pids == [2, 3, 1]


def test_handle_with_apostrophe_safely_quoted(tmp_path: Path):
    pending = tmp_path / "p.json"
    pending.write_text(json.dumps([
        {"handle": {"Active": "qpr-attacker's"}, "pid": 99,
         "original_authority": "Responder", "original_reason": "x",
         "seconds_remaining": 100, "scope": "Process"},
    ]))
    body = json.loads(_run(["--json"], pending_path=pending).stdout)
    cmd = body["queue"][0]["release_command"]
    # bash escape of single-quote inside single-quoted string.
    assert "qpr-attacker'\\''s" in cmd


def test_human_mode_shows_both_release_and_kill_commands(tmp_path: Path):
    pending = tmp_path / "p.json"
    pending.write_text(json.dumps([
        {"handle": {"Active": "qpr-z"}, "pid": 4242,
         "original_authority": "Responder", "original_reason": "smoke",
         "seconds_remaining": 60, "scope": "Process"},
    ]))
    r = _run([], pending_path=pending)
    assert r.returncode == 0
    assert "release: $ selfdefctl release-pid" in r.stdout
    assert "kill:    $ selfdefctl kill-quarantined" in r.stdout
    assert "--signal TERM" in r.stdout


def test_scope_tree_displayed(tmp_path: Path):
    pending = tmp_path / "p.json"
    pending.write_text(json.dumps([
        {"handle": {"Active": "qpr-tree"}, "pid": 1,
         "original_authority": "Responder", "original_reason": "tree-test",
         "seconds_remaining": 120, "scope": "Tree"},
    ]))
    r = _run([], pending_path=pending)
    assert "Tree" in r.stdout


def test_dashboard_serve_registers_quarantine_queue_card():
    body = SERVE.read_text()
    assert "card_quarantine_queue" in body
    assert "SDD-066 — pending process-quarantine release decisions" in body


def test_dashboard_card_invokes_cockpit_script_path():
    body = SERVE.read_text()
    assert "scripts\" / \"cockpit\" / \"quarantine-queue.py\"" in body \
        or "scripts/cockpit/quarantine-queue.py" in body
