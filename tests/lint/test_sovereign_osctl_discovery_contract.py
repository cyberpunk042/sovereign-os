"""Contracts for registry-backed command discovery and completion."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "scripts" / "sovereign-osctl"
HELPER = ROOT / "scripts" / "operator" / "command-discovery.py"
REGISTRY = ROOT / "docs" / "man" / "sovereign-osctl-command-topics.json"
BUILTINS = {"help", "version"}


def _registry_pages() -> dict[str, list[str]]:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))["pages"]


def _owned_commands() -> set[str]:
    return {command for commands in _registry_pages().values() for command in commands}


def _run_helper(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(HELPER), "--registry", str(REGISTRY), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def test_helper_is_executable_and_syntax_valid():
    assert HELPER.is_file()
    assert os.access(HELPER, os.X_OK)
    result = subprocess.run(
        ["python3", "-m", "py_compile", str(HELPER)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_machine_inventory_is_complete_and_unique():
    result = _run_helper("commands", "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    expected = _owned_commands() | BUILTINS
    emitted = set(payload["builtins"])
    emitted.update(command for commands in payload["topics"].values() for command in commands)
    assert emitted == expected
    assert payload["command_count"] == len(expected)
    assert len(expected) == len(_owned_commands()) + len(BUILTINS)


def test_words_inventory_has_every_command_once():
    result = _run_helper("commands", "--format", "words")
    assert result.returncode == 0, result.stderr
    words = result.stdout.split()
    assert len(words) == len(set(words))
    assert set(words) == _owned_commands() | BUILTINS


def test_contextual_help_resolves_every_command_to_its_owner():
    for topic, commands in _registry_pages().items():
        expected = f"sovereign-osctl-{topic}"
        topic_result = _run_helper("help", topic, "--print-target")
        assert topic_result.returncode == 0, topic_result.stderr
        assert topic_result.stdout.splitlines()[0] == expected
        for command in commands:
            result = _run_helper("help", command, "--print-target")
            assert result.returncode == 0, result.stderr
            assert result.stdout.splitlines()[0] == expected

    for command in BUILTINS:
        result = _run_helper("help", command, "--print-target")
        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines()[0] == "sovereign-osctl"


def test_unknown_contextual_help_fails_with_a_suggestion():
    result = _run_helper("help", "thermls", "--print-target")
    assert result.returncode == 2
    assert "unknown command or topic" in result.stderr
    assert "thermals" in result.stderr


def test_shell_completions_are_generated_from_the_complete_inventory():
    expected = _owned_commands() | BUILTINS
    for shell in ("bash", "zsh", "fish"):
        result = _run_helper("completion", shell)
        assert result.returncode == 0, result.stderr
        assert "sovereign-osctl" in result.stdout
        for command in expected:
            if shell == "bash":
                # Bash deliberately resolves the registry at completion time.
                assert "commands --format words" in result.stdout
                break
            assert re.search(rf"\b{re.escape(command)}\b", result.stdout)


def test_cli_dispatches_discovery_and_contextual_help():
    body = CLI.read_text(encoding="utf-8")
    assert "commands) _run_command_discovery commands" in body
    assert "completion) _run_command_discovery completion" in body
    assert 'help|--help|-h|"") _contextual_help "$@"' in body
    assert "scripts/operator/command-discovery.py" in body
    assert "operator/command-discovery.py" in body


def test_bashrc_completion_does_not_carry_a_second_command_registry():
    body = (ROOT / "scripts/operator/bashrc-install.sh").read_text(encoding="utf-8")
    assert "sovereign-osctl commands --format words" in body
    assert 'opts="status overview doctor' not in body


def test_staged_install_and_uninstall_are_symmetric(tmp_path: Path):
    prefix = "/usr"
    install = subprocess.run(
        ["make", "install", f"DESTDIR={tmp_path}", f"PREFIX={prefix}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert install.returncode == 0, install.stdout + install.stderr

    staged = tmp_path / "usr"
    cli = staged / "bin/sovereign-osctl"
    lib = staged / "lib/sovereign-os"
    expected_files = (
        cli,
        lib / "VERSION",
        lib / "operator/command-discovery.py",
        lib / "share/sovereign-osctl-command-topics.json",
        staged / "share/bash-completion/completions/sovereign-osctl",
        staged / "share/zsh/site-functions/_sovereign-osctl",
        staged / "share/fish/vendor_completions.d/sovereign-osctl.fish",
    )
    for path in expected_files:
        assert path.is_file(), f"missing installed discovery artifact: {path}"
    assert len(tuple((staged / "share/man/man1").glob("sovereign-osctl*.1"))) >= 8

    env = os.environ.copy()
    env["SOVEREIGN_OS_LIB"] = str(lib)
    inventory = subprocess.run(
        [str(cli), "commands", "--json"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert inventory.returncode == 0, inventory.stderr
    assert json.loads(inventory.stdout)["command_count"] == len(_owned_commands() | BUILTINS)

    version = subprocess.run(
        [str(cli), "version", "--json"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert version.returncode == 0, version.stderr
    assert json.loads(version.stdout)["sovereign_osctl_version"] == (lib / "VERSION").read_text().strip()

    uninstall = subprocess.run(
        ["make", "uninstall", f"DESTDIR={tmp_path}", f"PREFIX={prefix}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert uninstall.returncode == 0, uninstall.stdout + uninstall.stderr
    for path in expected_files:
        assert not path.exists(), f"uninstall left discovery artifact: {path}"
