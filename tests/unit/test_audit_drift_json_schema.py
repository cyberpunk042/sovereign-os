"""Layer 2 unit tests — sovereign-osctl audit drift --json schema (SDD-025).

SDD-025 § --json mode contract specifies that observability-family
verbs emitting --json have a stable schema; fields are additive only.
This test pins the `audit drift` JSON contract from Round 111.

Contract:
  { "summary": {"drifted": int, "unchanged": int, "not_deployed": int},
    "entries": [
      {"kind": "server"|"workstation",
       "file": <basename string>,
       "destination": <absolute path>,
       "state": "unchanged"|"drifted"|"not-deployed"|"source-missing"}, ...
    ]
  }

Empty state: still emits the full object with summary.drifted=0 +
empty/non-empty entries (NOT null, NOT error string)."""

from __future__ import annotations

import json
import pathlib
import subprocess

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

ALLOWED_KINDS = {"server", "workstation"}
ALLOWED_STATES = {"unchanged", "drifted", "not-deployed", "source-missing"}
REQUIRED_ENTRY_FIELDS = {"kind", "file", "destination", "state"}
REQUIRED_SUMMARY_FIELDS = {"drifted", "unchanged", "not_deployed"}


def _run_drift_json(dest_prefix: pathlib.Path) -> dict:
    env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": "/tmp",
        "SOVEREIGN_OS_HARDENING_DEST_PREFIX": str(dest_prefix),
    }
    result = subprocess.run(
        [str(OSCTL), "audit", "drift", "--json"],
        capture_output=True, text=True, env=env,
    )
    # Exit code: 0 if no drift, 1 if drift. Both are success for parsing.
    assert result.returncode in (0, 1), f"unexpected rc={result.returncode}: {result.stderr}"
    return json.loads(result.stdout), result.returncode


@pytest.fixture
def empty_target(tmp_path):
    """Empty destination tree → all not-deployed."""
    d = tmp_path / "empty"
    d.mkdir()
    return d


@pytest.fixture
def server_deployed_target(tmp_path):
    """Deploy all 5 server drop-ins; expect 5 unchanged + 1 workstation conflict."""
    d = tmp_path / "srv"
    for sub in ("etc/audit/rules.d", "etc/fail2ban/jail.d",
                "etc/apt/apt.conf.d", "etc/ssh/sshd_config.d",
                "etc/security/pwquality.conf.d"):
        (d / sub).mkdir(parents=True)
    cfg_server = REPO_ROOT / "config" / "server"
    (d / "etc/audit/rules.d/sovereign-os.rules").write_bytes(
        (cfg_server / "auditd.rules").read_bytes())
    (d / "etc/fail2ban/jail.d/sovereign-os.local").write_bytes(
        (cfg_server / "fail2ban-jail.local").read_bytes())
    (d / "etc/apt/apt.conf.d/52sovereign-os-unattended.conf").write_bytes(
        (cfg_server / "unattended-upgrades.conf").read_bytes())
    (d / "etc/ssh/sshd_config.d/50sovereign-os.conf").write_bytes(
        (cfg_server / "sshd.conf").read_bytes())
    (d / "etc/security/pwquality.conf.d/50sovereign-os.conf").write_bytes(
        (cfg_server / "pwquality.conf").read_bytes())
    return d


def test_empty_target_emits_full_object_not_null(empty_target):
    """Empty state STILL emits the full object — summary + entries.
    NEVER null, NEVER an error string."""
    data, rc = _run_drift_json(empty_target)
    assert isinstance(data, dict), "must be an object even when empty"
    assert "summary" in data and "entries" in data
    # All 6 drop-ins inventoried; all not-deployed for empty target
    assert data["summary"]["drifted"] == 0
    assert data["summary"]["unchanged"] == 0
    assert data["summary"]["not_deployed"] == 6
    assert rc == 0  # no drift → exit 0


def test_summary_has_required_fields(server_deployed_target):
    data, _ = _run_drift_json(server_deployed_target)
    missing = REQUIRED_SUMMARY_FIELDS - data["summary"].keys()
    assert not missing, f"summary missing required fields: {missing}"
    for k in REQUIRED_SUMMARY_FIELDS:
        assert isinstance(data["summary"][k], int), \
            f"summary.{k} MUST be int, got {type(data['summary'][k]).__name__}"


def test_entries_have_required_fields(server_deployed_target):
    data, _ = _run_drift_json(server_deployed_target)
    assert isinstance(data["entries"], list)
    for entry in data["entries"]:
        missing = REQUIRED_ENTRY_FIELDS - entry.keys()
        assert not missing, f"entry missing fields {missing}: {entry}"


def test_entry_kind_is_enum(server_deployed_target):
    data, _ = _run_drift_json(server_deployed_target)
    for entry in data["entries"]:
        assert entry["kind"] in ALLOWED_KINDS, \
            f"unknown kind {entry['kind']!r}; must be one of {ALLOWED_KINDS}"


def test_entry_state_is_enum(server_deployed_target):
    data, _ = _run_drift_json(server_deployed_target)
    for entry in data["entries"]:
        assert entry["state"] in ALLOWED_STATES, \
            f"unknown state {entry['state']!r}; must be one of {ALLOWED_STATES}"


def test_entry_destination_is_absolute_path(server_deployed_target):
    data, _ = _run_drift_json(server_deployed_target)
    for entry in data["entries"]:
        dst = entry["destination"]
        assert isinstance(dst, str) and len(dst) > 0
        # MUST be absolute — operators rely on this for grep / xargs
        assert dst.startswith("/"), f"destination not absolute: {dst}"


def test_exit_code_signals_drift(server_deployed_target):
    """SDD-025 exit code 1 = substantive non-error signal.
    server-deployed has 1 drifted (workstation sshd conflict)."""
    data, rc = _run_drift_json(server_deployed_target)
    if data["summary"]["drifted"] > 0:
        assert rc == 1, f"drift present but exit code is {rc}"
    else:
        assert rc == 0


def test_inventory_count_locked(empty_target):
    """The inventory (server+workstation drop-ins) is currently 6.
    Future additions are fine — this test catches accidental REMOVAL.
    Update the threshold when intentionally growing/shrinking."""
    data, _ = _run_drift_json(empty_target)
    assert len(data["entries"]) >= 6, \
        f"inventory shrank below 6 entries: {len(data['entries'])}"
