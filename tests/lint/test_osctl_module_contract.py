"""Contracts for the first sovereign-osctl verb module (F-2026-025)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

REPO = Path(__file__).resolve().parents[2]
OSCTL = REPO / "scripts" / "sovereign-osctl"
MODULE = REPO / "scripts" / "osctl.d" / "version.sh"


def test_version_is_owned_only_by_the_module():
    dispatcher = OSCTL.read_text(encoding="utf-8")
    module = MODULE.read_text(encoding="utf-8")
    assert "_source_osctl_module version" in dispatcher
    assert "\ncmd_version() {" not in dispatcher
    assert "\n_sovereign_os_version() {" not in dispatcher
    assert "cmd_version() {" in module
    assert "_sovereign_os_version() {" in module


def test_make_install_packages_osctl_modules():
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    assert '$(SOVEREIGN_OS_LIB)/osctl.d' in makefile
    assert 'scripts/osctl.d/*.sh' in makefile


def test_version_module_executes_through_dispatcher(tmp_path):
    version = tmp_path / "VERSION"
    version.write_text("9.8.7-test+contract\n", encoding="utf-8")
    env = os.environ.copy()
    env.update(
        SOVEREIGN_OS_VERSION_FILE=str(version),
        SOVEREIGN_OS_PROFILE="contract-profile",
    )
    proc = subprocess.run(
        ["bash", str(OSCTL), "version", "--json"],
        cwd=REPO,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["sovereign_osctl_version"] == "9.8.7-test+contract"
    assert payload["active_profile"] == "contract-profile"
