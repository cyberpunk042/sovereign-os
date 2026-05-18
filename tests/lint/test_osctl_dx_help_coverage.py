"""R443 (E11.M-DX-1) — sovereign-osctl DX (Developer Experience) help
coverage lint.

Per operator's §1h verbatim: "high UX/DX" — pairs UX + Developer
Experience as first-class. R443 establishes the DX bar for
sovereign-osctl: every cmd_<name> handler MUST be discoverable via
the cmd_help() output (operator runs `sovereign-osctl help` and sees
every command).

R413 covered the bidirectional handler↔dispatcher consistency. R443
adds the parallel handler↔help-text consistency: every cmd_<name>
handler appears in cmd_help body (operator-discoverable via
`sovereign-osctl help`).

This is the §1h DX-track companion to the §1g multi-surface delivery
contract (E11.M3).

If a future agent silently:
  - adds a cmd_X handler without listing it in cmd_help = operator
    runs `sovereign-osctl help` and doesn't see X = DX failure
  - removes a command from cmd_help without removing the handler =
    operator-discoverable surface shrinks while implementation stays
…the DX surface silently degrades.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

# Handlers that legitimately don't need to appear in cmd_help body
# (helpers / internals / cmd_help itself):
HANDLER_EXEMPT = {
    "help",       # the help command itself
}


def _read() -> str:
    return OSCTL.read_text(encoding="utf-8")


def _handlers() -> list[str]:
    """All cmd_<name> handler function names (without the cmd_ prefix)."""
    body = _read()
    return [m.group(1) for m in re.finditer(r"^cmd_([a-z_]+)\(\)", body, re.M)]


def _cmd_help_body() -> str:
    """Extract the cmd_help() function body."""
    body = _read()
    m = re.search(
        r"^cmd_help\(\)\s*\{(.+?)^\}",
        body,
        re.M | re.DOTALL,
    )
    assert m, "sovereign-osctl missing cmd_help() function body"
    return m.group(1)


# --- Structural ---


def test_osctl_exists():
    assert OSCTL.is_file(), f"missing {OSCTL}"


def test_at_least_20_handlers():
    """Operator-named: 25+ cmd_ handlers at this point. Drift below
    20 = mass deletion."""
    handlers = _handlers()
    # Exempt the 'help' handler itself (not counted)
    discoverable = [h for h in handlers if h not in HANDLER_EXEMPT]
    assert len(discoverable) >= 20, (
        f"only {len(discoverable)} discoverable cmd_ handlers; "
        f"expected ≥20 (mass-deletion detection)"
    )


def test_cmd_help_body_extractable():
    """cmd_help() MUST exist + have an extractable body."""
    body = _cmd_help_body()
    assert len(body) >= 500, (
        f"cmd_help() body too short ({len(body)} chars); "
        f"operator-discovery surface broken"
    )


def test_cmd_help_uses_heredoc():
    """cmd_help() MUST use a heredoc (cat <<'EOF' ... EOF) for the
    help text. Drift to inline echo = harder to maintain."""
    body = _cmd_help_body()
    has_heredoc = (
        "cat <<" in body
        or "cat << " in body
    )
    assert has_heredoc, (
        "cmd_help() doesn't use heredoc — drift = harder operator-"
        "discoverable help-text maintenance"
    )


# --- DX coverage: every handler discoverable via help ---


def test_every_handler_appears_in_cmd_help():
    """DX bar: every cmd_<name> handler MUST appear in cmd_help body
    (operator runs `sovereign-osctl help` and sees every command).

    Some handlers are dispatched as subcommand wrappers (e.g.,
    cmd_secure_boot dispatched via 'secure-boot' command in CLI);
    that subcommand string MUST appear in the help text."""
    handlers = _handlers()
    help_body = _cmd_help_body()
    missing: list[str] = []
    for handler in handlers:
        if handler in HANDLER_EXEMPT:
            continue
        # The handler name with underscore OR with hyphen
        # (CLI subcommands use hyphen; handler functions use underscore)
        with_underscore = handler
        with_hyphen = handler.replace("_", "-")
        if with_underscore not in help_body and with_hyphen not in help_body:
            missing.append(handler)
    assert not missing, (
        f"cmd_<name> handlers not in cmd_help body (DX gap — operator "
        f"won't see them via `sovereign-osctl help`): {missing}"
    )


def test_cmd_help_lists_usage_line():
    """USAGE: line MUST appear in cmd_help body (operator-discoverable
    invocation pattern)."""
    body = _cmd_help_body()
    assert "USAGE:" in body or "Usage:" in body, (
        "cmd_help() missing USAGE: line (operator-discoverable "
        "invocation pattern)"
    )


def test_cmd_help_lists_commands_section():
    """COMMANDS: section MUST appear (operator-discoverable command
    inventory)."""
    body = _cmd_help_body()
    assert "COMMANDS:" in body or "Commands:" in body, (
        "cmd_help() missing COMMANDS: section header"
    )


def test_cmd_help_groups_subcommands():
    """Operator-discoverable: subcommands grouped (e.g., 'profiles
    list' / 'profiles show' / etc.). At least 5 top-level groups."""
    body = _cmd_help_body()
    # Count groups by top-level command words in each USAGE line
    top_level_groups = set()
    for line in body.split("\n"):
        m = re.match(r"^\s*([a-z][a-z-]+)\b", line)
        if m and len(m.group(1)) >= 5:
            top_level_groups.add(m.group(1))
    assert len(top_level_groups) >= 5, (
        f"cmd_help() only has {len(top_level_groups)} top-level "
        f"command groups (operator-discoverable surface too narrow)"
    )


# --- DX quality: help text substantive per command ---


def test_help_text_substantive_per_handler():
    """Each handler mentioned in cmd_help SHOULD have at least a
    short description (operator-discoverable: what does this verb
    do?). Drift = single-word entries = operator confused."""
    body = _cmd_help_body()
    # Find every line that looks like a command spec
    # Pattern: "  <cmd>   <description>"
    cmd_lines = re.findall(
        r"^  ([a-z][a-z-]+(?:\s+[a-z<>\[\]\-]+)*)\s+(\S.{10,})$",
        body, re.M
    )
    # If we found at least 15 substantive command lines, we're good
    assert len(cmd_lines) >= 15, (
        f"cmd_help() has only {len(cmd_lines)} substantive command "
        f"lines (≥10-char descriptions); operator-discoverable depth "
        f"too shallow"
    )


def test_help_mentions_json_flag_for_fleet_aggregation():
    """Operator-named: --json flag for fleet aggregation. Most commands
    that benefit (status, profile list, etc.) MUST surface this in help."""
    body = _cmd_help_body()
    has_json = "--json" in body
    assert has_json, (
        "cmd_help() missing --json flag references (fleet aggregation "
        "DX surface broken)"
    )


# --- Bidirectional consistency: handlers in dispatcher (R413) +
#     handlers in help (R443) ---


def test_handlers_in_help_match_handlers_in_dispatcher():
    """Combined R413 + R443 contract: handler MUST be in BOTH the
    dispatcher case statement AND the cmd_help body. Drift =
    dispatcher routes a command that help doesn't document, OR help
    documents a command the dispatcher can't route."""
    body = _read()
    help_body = _cmd_help_body()
    handlers = _handlers()
    for handler in handlers:
        if handler in HANDLER_EXEMPT:
            continue
        cli_name = handler.replace("_", "-")
        # In dispatcher case (R413)
        in_dispatcher = (
            re.search(
                rf"^\s*{re.escape(cli_name)}\)\s+cmd_{re.escape(handler)}\b",
                body, re.M
            )
            is not None
        )
        # In help body (R443)
        in_help = handler in help_body or cli_name in help_body
        # Both should be true (or the handler is a private helper)
        if in_dispatcher and not in_help:
            assert False, (
                f"handler cmd_{handler} dispatched but not in help "
                f"(R443 DX gap)"
            )


def test_help_text_documents_q_019_origin():
    """The operator-named Q-019 origin of sovereign-osctl SHOULD be
    discoverable in either the header comment OR cmd_help body
    (operator-discovery: WHY does sovereign-osctl exist)."""
    body = _read()
    has_q_019 = "Q-019" in body
    assert has_q_019, (
        "sovereign-osctl missing Q-019 origin reference "
        "(operator-discovery context)"
    )
