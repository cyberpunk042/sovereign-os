"""R447 (E11.M6) — bashrc-install verb contract lint.

Extends R387-R446 + R413 (osctl handlers) + R443 (osctl help) +
R445 (E11 UX surfaces) operational-artifact pinning to:
  scripts/operator/bashrc-install.sh
  scripts/sovereign-osctl (bashrc dispatch + help text)

Per operator §1g verbatim: "the bashrc we can offer to configure it
too and we can add our autocompletes and aliases and manual / helps
and menus".

This is the first SUBSTANTIVE feature shipping a §1g E11.M Module
(R446 was research+catalog enrichment for E11.M4; R447 is a full
feature shipping E11.M6).

If a future agent silently:
  - removes the sentinel pattern = bashrc edits become destructive
  - drops the idempotency check = re-install duplicates the block
  - removes aliases = operator-discoverable surface shrinks
  - drops the soshelp-menu function = operator quick-help broken
…the operator-named E11.M6 contract silently degrades.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASHRC_SH = REPO_ROOT / "scripts" / "operator" / "bashrc-install.sh"
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --- Structural ---


def test_bashrc_script_exists():
    assert BASHRC_SH.is_file(), f"missing {BASHRC_SH}"


def test_bashrc_script_executable():
    """Operator-discoverable: bashrc script MUST be executable
    (operator can chmod +x by hand but default should be ready)."""
    assert os.access(BASHRC_SH, os.X_OK), (
        f"{BASHRC_SH} not executable"
    )


def test_set_euo_pipefail():
    body = _read(BASHRC_SH)
    assert "set -euo pipefail" in body, (
        "bashrc-install.sh missing 'set -euo pipefail' bash strict"
    )


# --- §1g operator-verbatim binding ---


def test_documents_e11_m6_origin():
    body = _read(BASHRC_SH)
    assert "E11.M6" in body, (
        "bashrc-install.sh missing E11.M6 binding"
    )
    assert "§1g" in body, (
        "bashrc-install.sh missing §1g reference"
    )


def test_quotes_operator_verbatim():
    body = _read(BASHRC_SH)
    has_verbatim = (
        "autocompletes" in body
        and "aliases" in body
        and "menus" in body
    )
    assert has_verbatim, (
        "bashrc-install.sh missing §1g operator-verbatim phrases "
        "(autocompletes + aliases + menus)"
    )


# --- Idempotency + reversibility ---


def test_has_sentinel_begin_and_end():
    """Sentinel-bounded block lets operator edits outside the
    sentinels survive install/uninstall cycles."""
    body = _read(BASHRC_SH)
    assert "SENTINEL_BEGIN=" in body, (
        "bashrc-install.sh missing SENTINEL_BEGIN constant"
    )
    assert "SENTINEL_END=" in body, (
        "bashrc-install.sh missing SENTINEL_END constant"
    )


def test_sentinel_strings_distinct():
    """BEGIN + END sentinels MUST be distinct strings."""
    body = _read(BASHRC_SH)
    # Check that 'BEGIN' and 'END' appear in distinct sentinel lines
    has_begin = "BEGIN" in body and "managed by sovereign-osctl bashrc" in body
    has_end = "END" in body and "managed by sovereign-osctl bashrc" in body
    assert has_begin and has_end, (
        "BEGIN/END sentinels not distinct or missing markers"
    )


def test_install_action_present():
    body = _read(BASHRC_SH)
    assert "install)" in body, (
        "bashrc-install.sh missing install subcommand"
    )


def test_uninstall_action_present():
    body = _read(BASHRC_SH)
    assert "uninstall)" in body, (
        "bashrc-install.sh missing uninstall subcommand"
    )


def test_status_action_present():
    body = _read(BASHRC_SH)
    assert "status)" in body, (
        "bashrc-install.sh missing status subcommand"
    )


def test_dump_action_present():
    """dump prints the block to stdout — operator can pipe to other
    rc files (e.g., ~/.zshrc)."""
    body = _read(BASHRC_SH)
    assert "dump)" in body, (
        "bashrc-install.sh missing dump subcommand"
    )


def test_combo_action_present():
    """R468: combo verb chains sovereign-os + selfdef bashrc
    installers (cross-repo to SD-R-BASHRC-1)."""
    body = _read(BASHRC_SH)
    assert "combo)" in body
    assert "SD-R-BASHRC-1" in body


def test_combo_probes_adjacent_selfdef_checkout():
    """R468: combo MUST autodetect a sibling selfdef checkout."""
    body = _read(BASHRC_SH)
    assert "../selfdef/packaging/bash/selfdefctl-bashrc-install.sh" in body


def test_combo_env_override_documented():
    """R468: SELFDEF_BASHRC_INSTALL_PATH env-override MUST be present
    AND documented in the help block."""
    body = _read(BASHRC_SH)
    assert body.count("SELFDEF_BASHRC_INSTALL_PATH") >= 2, (
        "expected env var in both impl AND help text"
    )


def test_combo_dry_run_smoke():
    """R468 end-to-end: combo --DRY_RUN with explicit selfdef path."""
    import os as _os
    import subprocess as _sp
    import tempfile as _tf
    with _tf.TemporaryDirectory() as td:
        fake_selfdef = Path(td) / "selfdef-installer.sh"
        fake_selfdef.write_text(
            '#!/usr/bin/env bash\n'
            'echo "fake selfdef installer ran (verb=$1)"\n'
            'exit 0\n'
        )
        _os.chmod(fake_selfdef, 0o755)
        rc_file = Path(td) / ".bashrc"
        rc_file.write_text("")
        result = _sp.run(
            ["bash", str(BASHRC_SH), "combo"],
            capture_output=True, text=True, timeout=10,
            env={**_os.environ,
                 "SOVEREIGN_OS_DRY_RUN": "1",
                 "SOVEREIGN_OS_BASHRC_PATH": str(rc_file),
                 "SELFDEF_BASHRC_INSTALL_PATH": str(fake_selfdef)},
        )
        assert result.returncode == 0, (
            f"combo failed: stderr={result.stderr[:300]}"
        )
        combined = result.stdout + result.stderr
        assert "combo step 1/2" in combined
        assert "combo step 2/2" in combined
        assert "fake selfdef installer ran" in combined


def test_combo_graceful_when_selfdef_absent():
    """R468: combo without a reachable selfdef installer warns +
    completes (sovereign-os still installs)."""
    import os as _os
    import subprocess as _sp
    import tempfile as _tf
    with _tf.TemporaryDirectory() as td:
        rc_file = Path(td) / ".bashrc"
        rc_file.write_text("")
        env = {k: v for k, v in _os.environ.items()
               if not k.startswith("SELFDEF_")}
        env.update({
            "SOVEREIGN_OS_DRY_RUN": "1",
            "SOVEREIGN_OS_BASHRC_PATH": str(rc_file),
            "SELFDEF_BASHRC_INSTALL_PATH": "/nonexistent/selfdef.sh",
        })
        result = _sp.run(
            ["bash", str(BASHRC_SH), "combo"],
            capture_output=True, text=True, timeout=10,
            env=env,
        )
        assert result.returncode == 0
        combined = result.stdout + result.stderr
        assert "SKIPPED" in combined
        assert "selfdef installer not found" in combined


def test_install_idempotent_via_sed_delete():
    """Idempotency: install MUST remove existing block before
    appending new one. sed -i / awk-based delete pattern present."""
    body = _read(BASHRC_SH)
    has_idempotent = (
        "sed -i" in body
        and "SENTINEL_BEGIN" in body
        and "SENTINEL_END" in body
    )
    assert has_idempotent, (
        "bashrc-install.sh install missing idempotent-replace pattern"
    )


def test_uninstall_keeps_backup():
    """Uninstall MUST create a .sovereign-os-bak backup of the rc
    file (operator-anti-destruction)."""
    body = _read(BASHRC_SH)
    assert ".sovereign-os-bak" in body, (
        "bashrc-install.sh missing .sovereign-os-bak backup pattern"
    )


# --- Block contents (operator-discoverable aliases + menu + completion) ---


def test_block_provides_sosctl_alias():
    """Operator-discoverable: sosctl alias = sovereign-osctl shortcut."""
    body = _read(BASHRC_SH)
    assert "alias sosctl=" in body, (
        "block missing sosctl alias"
    )


def test_block_provides_multiple_aliases():
    """Block ships ≥8 aliases (operator-discoverable surface breadth)."""
    body = _read(BASHRC_SH)
    aliases = re.findall(r"alias (\w+)=", body)
    assert len(aliases) >= 8, (
        f"block ships only {len(aliases)} aliases (≥8 expected)"
    )


def test_block_provides_help_menu_function():
    body = _read(BASHRC_SH)
    assert "soshelp-menu()" in body, (
        "block missing soshelp-menu() function (operator quick-help)"
    )


def test_block_provides_bash_completion_function():
    body = _read(BASHRC_SH)
    has_completion = (
        "_sovereign_osctl_complete" in body
        or "_sovereign_osctl_complete()" in body
    )
    assert has_completion, (
        "block missing bash completion function"
    )


def test_completion_uses_complete_builtin():
    """The completion function MUST be registered via the bash
    `complete` builtin."""
    body = _read(BASHRC_SH)
    assert "complete -F " in body, (
        "block missing `complete -F` registration"
    )


def test_completion_covers_top_level_subcommands():
    """Tab-completion MUST consume the canonical command registry."""
    body = _read(BASHRC_SH)
    assert "sovereign-osctl commands --format words" in body
    assert 'opts="status overview doctor' not in body


# --- DRY_RUN safety ---


def test_honors_dry_run():
    """SOVEREIGN_OS_DRY_RUN MUST short-circuit (operator-named
    CI/preview safety)."""
    body = _read(BASHRC_SH)
    assert "SOVEREIGN_OS_DRY_RUN" in body, (
        "bashrc-install.sh missing SOVEREIGN_OS_DRY_RUN handling"
    )


# --- Observability ---


def test_emits_layer_b_metric():
    """SDD-016: sovereign_os_operator_bashrc_install_total counter
    with {action,result} labels."""
    body = _read(BASHRC_SH)
    assert "sovereign_os_operator_bashrc_install_total" in body, (
        "bashrc-install.sh missing operator_bashrc_install_total metric"
    )


# --- osctl dispatcher + help text integration ---


def test_osctl_dispatches_bashrc():
    """sovereign-osctl MUST route `bashrc` to scripts/operator/
    bashrc-install.sh."""
    body = _read(OSCTL)
    has_dispatch = (
        "bashrc)" in body
        and "bashrc-install.sh" in body
    )
    assert has_dispatch, (
        "sovereign-osctl doesn't dispatch bashrc to bashrc-install.sh"
    )


def test_osctl_help_documents_bashrc_subcommands():
    """cmd_help() body MUST document bashrc subcommands (DX bar —
    R443)."""
    body = _read(OSCTL)
    # All 4 subcommands should appear in help
    for sub in ("bashrc install", "bashrc uninstall",
                "bashrc status", "bashrc dump"):
        assert sub in body, (
            f"sovereign-osctl help missing {sub!r}"
        )


def test_osctl_help_references_e11_m6():
    """Help text SHOULD reference E11.M6 (operator-discoverable
    binding to the §1g Module)."""
    body = _read(OSCTL)
    assert "E11.M6" in body, (
        "sovereign-osctl help missing E11.M6 reference"
    )


# --- Cross-shell support (operator-discoverable extensibility) ---


def test_supports_custom_rc_path():
    """SOVEREIGN_OS_BASHRC_PATH env override (operator can target
    ~/.zshrc for zsh integration via dump-pipe pattern OR direct
    install)."""
    body = _read(BASHRC_SH)
    assert "SOVEREIGN_OS_BASHRC_PATH" in body, (
        "bashrc-install.sh missing SOVEREIGN_OS_BASHRC_PATH env"
    )


def test_help_documents_zsh_path():
    """Operator-discoverable: ~/.zshrc as alternative target."""
    body = _read(BASHRC_SH)
    assert "zshrc" in body or "zsh" in body, (
        "bashrc-install.sh missing zsh integration documentation"
    )
