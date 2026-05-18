"""R383 (E10.M27) — osctl --help R-arc verb discoverability lint.

Every verb shipped in the R355-R382 verbatim-preservation arc MUST
appear in `sovereign-osctl --help` output. Catches: agent adds a new
verb to the dispatch case statement but forgets to wire it into the
help text — operator can't discover it.

Verbs to check:
  - architecture-qa (R355+, multi-round)
  - ccd-pinning (R356)
  - state-fabric (R358)
  - network-topology (R359)
  - coverage (R365)
  - repl (R366)
  - verbatim-render (R369)
  - doctrine-status (R376)
  - quarterly-review (R377)
  - layers (R382)

Plus the dispatch case for each MUST exist in osctl. (R372 already
covers this from the catalog-citation direction; R383 covers the
operator-discovery direction.)
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"


R_ARC_VERBS_IN_HELP = [
    "architecture-qa",
    "ccd-pinning",
    "state-fabric",
    "network-topology",
    "coverage",
    "repl",
    "verbatim-render",
    "doctrine-status",
    "quarterly-review",
    "layers",
]


def _help_output() -> str:
    """Run `sovereign-osctl --help` and return its stdout. NEVER-raises."""
    try:
        cp = subprocess.run(
            [str(OSCTL), "--help"],
            capture_output=True, text=True, timeout=10, cwd=REPO_ROOT,
        )
    except Exception:
        return ""
    return cp.stdout + cp.stderr


def test_osctl_help_runs():
    """osctl --help executes + produces output."""
    out = _help_output()
    assert out, "osctl --help produced no output"
    assert len(out) >= 1000, f"help output too short: {len(out)} chars"


def test_help_lists_every_r_arc_verb():
    """Every R355-R382 arc verb MUST appear in --help output."""
    out = _help_output()
    missing: list[str] = []
    for verb in R_ARC_VERBS_IN_HELP:
        # Look for `<verb> [sub]` or `<verb>  ` (verb name as a help row)
        pattern = re.compile(r"\b" + re.escape(verb) + r"\b")
        if not pattern.search(out):
            missing.append(verb)
    assert not missing, (
        f"osctl --help missing R355-R382 arc verbs: {missing}. "
        f"Add help entry for each in scripts/sovereign-osctl cmd_help() "
        f"OR remove the dispatch case if the verb was deleted."
    )


def test_help_documents_r355_arc_anchor():
    """The R355-R382 arc section header MUST appear (sanity check that
    the documentation block is intact, not stripped accidentally)."""
    out = _help_output()
    assert "R355" in out and "R382" in out and "/goal" in out.lower(), (
        "osctl --help missing R355-R382 arc anchor section header. "
        "The 'R355-R382 /goal contract enforcement' block must appear "
        "in cmd_help() output."
    )


def test_help_examples_section_includes_r_arc():
    """The EXAMPLES section MUST include ≥1 R-arc verb example
    (operator-friendly entry point)."""
    out = _help_output()
    # At least one of: architecture-qa / coverage / quarterly-review
    arc_examples = sum(
        1 for verb in ("architecture-qa", "coverage", "quarterly-review")
        if verb in out
    )
    assert arc_examples >= 1, (
        "osctl --help EXAMPLES section should include ≥1 R-arc verb "
        "(architecture-qa / coverage / quarterly-review)"
    )


def test_every_help_verb_has_dispatch_case():
    """Inverse direction: every R-arc verb listed in help MUST have
    a dispatch case in osctl. (Overlap with R372 but operator-help
    direction.)"""
    body = OSCTL.read_text(encoding="utf-8")
    for verb in R_ARC_VERBS_IN_HELP:
        # Look for `  <verb>)` case line
        pattern = re.compile(r"^\s+" + re.escape(verb) + r"\)", re.M)
        assert pattern.search(body), (
            f"osctl has no dispatch case for {verb!r} but help lists it"
        )


def test_help_section_is_well_formed():
    """The R355-R382 arc section in help has consistent formatting
    (verb name + ' [sub]' marker + description with R-number)."""
    out = _help_output()
    arc_section_match = re.search(
        r"R355-R382[^\n]*\n(.*?)\nENV VARS",
        out, re.S
    )
    assert arc_section_match, "could not locate R-arc section in help"
    arc_section = arc_section_match.group(1)
    # Count entries: each entry starts with 2 spaces + verb + ` [sub]`
    entries = re.findall(r"^  (\w[\w-]+) \[sub\]", arc_section, re.M)
    assert len(entries) >= 10, (
        f"R-arc section has only {len(entries)} entries; expected ≥10"
    )
    # Each entry should mention its R-number
    body_lines = arc_section.split("\n")
    r_number_lines = [
        l for l in body_lines if re.search(r"R\d{3}[+:]?\s", l)
    ]
    assert len(r_number_lines) >= 10, (
        f"R-arc section has only {len(r_number_lines)} lines with "
        f"R-number annotations; expected ≥10"
    )
