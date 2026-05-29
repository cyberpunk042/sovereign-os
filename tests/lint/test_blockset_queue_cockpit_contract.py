"""SDD-065 MS5b — blockset-queue cockpit consumer contract test."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "cockpit" / "blockset-queue.py"
SERVE = REPO_ROOT / "scripts" / "dashboard" / "serve.py"


def _run(args: list[str], pending_path: Path | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if pending_path is not None:
        env["SOVEREIGN_OS_BLOCKSET_PENDING_PATH"] = str(pending_path)
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


def test_default_pending_path_is_var_lib_selfdef():
    body = SCRIPT.read_text()
    assert "/var/lib/selfdef/blockset/pending-extensions.json" in body


def test_honest_offline_when_pending_file_missing(tmp_path: Path):
    """Missing snapshot → human says 'no pending', exit 0."""
    missing = tmp_path / "absent.json"
    r = _run([], pending_path=missing)
    assert r.returncode == 0
    assert "no pending" in r.stdout


def test_invalid_json_treated_as_empty_queue(tmp_path: Path):
    bad = tmp_path / "garbage.json"
    bad.write_text("{not json{")
    r = _run([], pending_path=bad)
    assert r.returncode == 0
    assert "no pending" in r.stdout


def test_json_mode_shape_with_real_entries(tmp_path: Path):
    pending = tmp_path / "pending.json"
    pending.write_text(json.dumps([
        {
            "handle": {"Active": "h-1"},
            "addr": "203.0.113.42",
            "original_authority": "Responder",
            "original_reason": "sshd brute force",
            "seconds_remaining": 320,
        },
    ]))
    r = _run(["--json"], pending_path=pending)
    assert r.returncode == 0
    body = json.loads(r.stdout)
    assert body["count"] == 1
    assert body["queue"][0]["addr"] == "203.0.113.42"
    # Pre-rendered command is the value-add.
    cmd = body["queue"][0]["extend_24h_command"]
    assert "selfdefctl block-ip 203.0.113.42" in cmd
    assert "--duration 24h" in cmd
    assert "--authority operator-overridden" in cmd
    assert "sshd brute force" in cmd


def test_queue_sorted_by_urgency_ascending(tmp_path: Path):
    """Same ordering invariant as selfdef-blockset-backend."""
    pending = tmp_path / "pending.json"
    pending.write_text(json.dumps([
        {"handle": {"Active": "h-a"}, "addr": "10.0.0.1",
         "original_authority": "Responder", "original_reason": "x",
         "seconds_remaining": 3000},
        {"handle": {"Active": "h-b"}, "addr": "10.0.0.2",
         "original_authority": "Responder", "original_reason": "y",
         "seconds_remaining": 500},
        {"handle": {"Active": "h-c"}, "addr": "10.0.0.3",
         "original_authority": "Responder", "original_reason": "z",
         "seconds_remaining": 1500},
    ]))
    r = _run(["--json"], pending_path=pending)
    body = json.loads(r.stdout)
    secs = [e["seconds_remaining"] for e in body["queue"]]
    assert secs == [500, 1500, 3000]


def test_extend_command_quote_escapes_apostrophes(tmp_path: Path):
    """The reason field can contain ' — must round-trip safely
    through the bash $'...' quoting form."""
    pending = tmp_path / "pending.json"
    pending.write_text(json.dumps([
        {"handle": {"Active": "h-q"}, "addr": "10.0.0.99",
         "original_authority": "Responder",
         "original_reason": "attacker's shell",
         "seconds_remaining": 100},
    ]))
    r = _run(["--json"], pending_path=pending)
    body = json.loads(r.stdout)
    cmd = body["queue"][0]["extend_24h_command"]
    # The single quote is escaped via the bash '\'' idiom.
    assert "attacker'\\''s shell" in cmd


def test_human_mode_shows_pre_rendered_command_per_entry(tmp_path: Path):
    pending = tmp_path / "pending.json"
    pending.write_text(json.dumps([
        {"handle": {"Active": "h-1"}, "addr": "10.1.1.1",
         "original_authority": "Responder",
         "original_reason": "smoke",
         "seconds_remaining": 60},
    ]))
    r = _run([], pending_path=pending)
    assert r.returncode == 0
    assert "$ selfdefctl block-ip 10.1.1.1" in r.stdout
    assert "--authority operator-overridden" in r.stdout


def test_dashboard_serve_registers_blockset_queue_card():
    """The card is wired into the dashboard."""
    body = SERVE.read_text()
    assert "card_blockset_queue" in body
    assert "SDD-065 — pending IP-block extension decisions" in body


def test_dashboard_card_invokes_cockpit_script_path():
    body = SERVE.read_text()
    assert "scripts/cockpit/blockset-queue.py" in body or \
           "scripts\" / \"cockpit\" / \"blockset-queue.py\"" in body
