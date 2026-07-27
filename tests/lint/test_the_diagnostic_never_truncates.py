"""One failing pipeline must not cost the operator the rest of the report.

2026-07-27. `sovereign-osctl install logs --from <disk>` is the only feedback
loop for a machine that will not boot — it reads first-boot markers, the
display stack, the desktop packages, the kernel entries, the module blacklists,
the apt sources and the journal off an unmounted disk.

sovereign-osctl runs under `set -euo pipefail`. A grep that matches nothing, or
a tail on a file that vanished, aborts the verb — and every section AFTER it is
simply absent. Not an error the operator can see: a silently shorter report,
which reads exactly like "that thing isn't there".

Verified by construction: an unguarded `grep | sed` with no match under
`set -e` never reaches the next echo.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OSCTL = REPO_ROOT / "scripts" / "sovereign-osctl"

# Commands that routinely "fail" simply by finding nothing.
FALLIBLE = re.compile(r"^\s*(sudo|grep|find|readlink|ls|cat|journalctl|tail)\b")


def diagnostic_statements() -> list[tuple[int, str]]:
    """Whole statements (continuations joined) inside the install-logs verb."""
    lines = OSCTL.read_text(encoding="utf-8").splitlines()
    start = next(i for i, l in enumerate(lines)
                 if "read-only, journal NOT replayed" in l)
    out, buf, first = [], "", None
    for i in range(start, min(start + 220, len(lines))):
        if first is None:
            first = i
        buf += lines[i].rstrip("\\").rstrip() + " "
        if not lines[i].rstrip().endswith("\\"):
            out.append((first + 1, buf.strip()))
            buf, first = "", None
    return out


def test_the_verb_runs_under_set_e():
    """Guard the premise — if this changes, the whole lint is moot."""
    head = OSCTL.read_text(encoding="utf-8")[:2000]
    assert re.search(r"^set -euo pipefail", head, re.M), (
        "sovereign-osctl no longer sets -e; revisit whether guarding is needed"
    )


def test_no_statement_can_abort_the_report():
    risky = [
        (ln, st[:90]) for ln, st in diagnostic_statements()
        if FALLIBLE.match(st)
        and "||" not in st
        and "&&" not in st
        and not st.strip().startswith(("if ", "for ", "while "))
    ]
    assert not risky, (
        "these statements can abort `install logs` and silently drop every "
        f"section after them:\n  " + "\n  ".join(f"line {ln}: {st}" for ln, st in risky)
    )


def test_an_unguarded_pipeline_really_does_truncate():
    """Demonstrate the failure mode, so the lint's premise is not folklore."""
    unguarded = subprocess.run(
        ["bash", "-c", 'set -euo pipefail\necho A\n'
                       'grep -hE "no-match" /etc/hostname 2>/dev/null | sed "s/^//"\necho B'],
        capture_output=True, text=True)
    assert "B" not in unguarded.stdout, (
        "expected an unguarded no-match pipeline to abort under set -e"
    )
    guarded = subprocess.run(
        ["bash", "-c", 'set -euo pipefail\necho A\n'
                       'grep -hE "no-match" /etc/hostname 2>/dev/null | sed "s/^//" || true\necho B'],
        capture_output=True, text=True)
    assert "B" in guarded.stdout, "the guarded form must continue"
