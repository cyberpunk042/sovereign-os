"""scripts/lifecycle/maintenance-window.py CLI verb contract.

Per the maintenance-window's own docstring, it ships 4 operator-runnable
CLI verbs (R323 / E2.M19):

  list                  — enumerate declared windows
  show <window>         — show one window's full schedule
  can-run-now <window>  — rc=0/1/2 query for advisors
  active                — list windows active right now

Other advisors (R308 autohealth / R318 heat-oc-throttle) query
`can-run-now <window>` before mutating any state. A silent rename
of any verb breaks the discipline contract across the whole graceful-
action surface — operator-facing CLI consumed by sovereign-osctl + by
peer Python scripts at runtime. This lint test pins those verbs at
commit time, complementing the runtime test at
tests/nspawn/test_maintenance_window.sh.

Pure text-shape assertions (no script invocation).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "lifecycle" / "maintenance-window.py"


def test_script_present():
    assert SCRIPT.is_file(), f"maintenance-window script not found at {SCRIPT}"


def test_script_is_executable_or_has_shebang():
    """Operator runs it directly: needs either +x or a Python shebang."""
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env python3") or text.startswith("#!/usr/bin/python3"), (
        "maintenance-window.py missing Python shebang (operator-direct invocation broken)"
    )


def test_docstring_documents_all_four_verbs():
    """The header docstring is the operator-readable manual; it must
    document each shipped verb. A silent verb rename without updating
    the docstring strands operators reading the file."""
    text = SCRIPT.read_text(encoding="utf-8")
    # Look at the top-of-file docstring (first triple-quoted block)
    m = re.search(r'"""(.*?)"""', text, flags=re.DOTALL)
    assert m, "no top-level docstring found in maintenance-window.py"
    docstring = m.group(1)
    for verb in ("list", "show", "can-run-now", "active"):
        assert verb in docstring, (
            f"docstring does not document the {verb!r} verb — operator-facing "
            f"manual stale"
        )


def test_argparse_carries_all_four_verbs():
    """The argparse setup must register each of the 4 verbs as a real
    subparser/choice. The docstring + the actual command surface MUST
    agree — silent docstring drift OR silent argparse drift produces
    operator-facing or script-facing breakage respectively."""
    text = SCRIPT.read_text(encoding="utf-8")
    # Look for add_parser("<verb>") or similar argparse patterns. The
    # script may use add_subparsers + add_parser, or choices=[...].
    for verb in ("list", "show", "can-run-now", "active"):
        # Check for either a quoted verb literal (covers add_parser(
        # "verb"...) AND choices=["verb"] AND if cmd == "verb"
        # — all the common argparse + dispatcher patterns).
        assert f'"{verb}"' in text or f"'{verb}'" in text, (
            f"the {verb!r} verb is not present as a quoted string "
            f"anywhere in the script — argparse setup or dispatcher "
            f"likely doesn't register it"
        )


def test_can_run_now_documents_three_return_codes():
    """The docstring documents `can-run-now`'s 3-way return code contract:
      rc=0 if window is active
      rc=1 if outside window
      rc=2 if unknown window
    Peer scripts (R308/R318) rely on this 3-way semantic. A silent
    change to a 2-way semantic would break the unknown-window
    distinction operators rely on."""
    text = SCRIPT.read_text(encoding="utf-8")
    m = re.search(r'"""(.*?)"""', text, flags=re.DOTALL)
    docstring = m.group(1)
    for rc_desc in ("rc=0", "rc=1", "rc=2"):
        assert rc_desc in docstring, (
            f"docstring missing {rc_desc!r} from can-run-now's 3-way "
            f"return code contract"
        )


def test_operator_overlay_path_documented():
    """The R283/SDD-030 operator-overlay path
    `/etc/sovereign-os/maintenance-window.toml` is the operator's
    point of customization. A silent rename / removal would force
    operators to dig into source to find where their config lives."""
    text = SCRIPT.read_text(encoding="utf-8")
    assert "/etc/sovereign-os/maintenance-window.toml" in text, (
        "operator-overlay path /etc/sovereign-os/maintenance-window.toml "
        "not referenced — R283/SDD-030 overlay contract drift"
    )
