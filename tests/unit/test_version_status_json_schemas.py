"""Layer 2 unit tests — sovereign-osctl `version --json` + `status --json`
JSON contracts (Round 120; locks SDD-025 § --json mode contract for
two older surfaces).

Round 64 added `version --json` (7-key contract).
Round 83 added `status --json` (8-key contract).

Both --json contracts were behaviorally tested via L3 (the dispatch
surface test + version-prefix grep). Neither had a dedicated L2 schema
test, so silent field additions/removals could ship if the L3 tests
didn't happen to assert on the changed field.

These tests pin:
  • All required keys are present
  • Types are correct (string vs bool vs int)
  • The 'version' value matches the documented major.minor.patch shape
  • Adding fields stays backward-compatible (test asserts ⊇, not ==)
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"


def _run_json(args: list[str]) -> dict:
    env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": "/tmp",
    }
    result = subprocess.run(
        [str(OSCTL), *args], capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, \
        f"{' '.join(args)} failed: rc={result.returncode}; stderr={result.stderr}"
    return json.loads(result.stdout)


# ---------- version --json ----------

VERSION_REQUIRED_KEYS = {
    "sovereign_osctl_version",
    "phase",
    "active_profile",
    "active_whitelabel",
    "kernel_release",
    "os_pretty_name",
    "repo",
}

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def test_version_json_has_required_keys():
    data = _run_json(["version", "--json"])
    missing = VERSION_REQUIRED_KEYS - data.keys()
    assert not missing, f"version --json missing keys: {missing}"


def test_version_json_version_field_is_semver():
    data = _run_json(["version", "--json"])
    v = data["sovereign_osctl_version"]
    assert isinstance(v, str), f"version MUST be string: {type(v).__name__}"
    assert SEMVER_RE.match(v), f"version MUST be major.minor.patch: got {v!r}"


def test_version_json_repo_is_https_url():
    data = _run_json(["version", "--json"])
    r = data["repo"]
    assert isinstance(r, str)
    assert r.startswith("https://"), f"repo MUST be https URL: {r}"


def test_version_json_string_fields():
    """All required version fields are strings (no None / int / bool)."""
    data = _run_json(["version", "--json"])
    for key in VERSION_REQUIRED_KEYS:
        v = data[key]
        assert isinstance(v, str), \
            f"version.{key} MUST be string, got {type(v).__name__}: {v!r}"


# ---------- status --json ----------

STATUS_REQUIRED_KEYS = {
    "profile",
    "active_whitelabel",
    "kernel_release",
    "os_pretty_name",
    "zfs_pool_state",
    "tetragon_state",
    "first_boot_complete",
    "timestamp",
}


def test_status_json_has_required_keys():
    data = _run_json(["status", "--json"])
    missing = STATUS_REQUIRED_KEYS - data.keys()
    assert not missing, f"status --json missing keys: {missing}"


def test_status_json_first_boot_complete_is_bool():
    data = _run_json(["status", "--json"])
    v = data["first_boot_complete"]
    assert isinstance(v, bool), \
        f"first_boot_complete MUST be bool, got {type(v).__name__}: {v!r}"


def test_status_json_timestamp_is_int_unix_epoch():
    data = _run_json(["status", "--json"])
    ts = data["timestamp"]
    assert isinstance(ts, int) and not isinstance(ts, bool), \
        f"timestamp MUST be int, got {type(ts).__name__}: {ts!r}"
    # Sanity: reasonable unix epoch (after 2020 but in the next ~50 years)
    assert 1577836800 <= ts <= 4102444800, f"timestamp implausible: {ts}"


def test_status_json_zfs_state_is_enum():
    data = _run_json(["status", "--json"])
    v = data["zfs_pool_state"]
    assert v in ("online", "degraded", "absent"), \
        f"zfs_pool_state must be enum, got {v!r}"


def test_status_json_tetragon_state_is_enum():
    data = _run_json(["status", "--json"])
    v = data["tetragon_state"]
    assert v in ("active", "inactive", "not-installed"), \
        f"tetragon_state must be enum, got {v!r}"
