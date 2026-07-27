""""Could not tell" must never render as "not there".

2026-07-27, the fourth and fifth instances of one root cause found the same day:

  * install logs      — packages read [MISSING] because a sudo grep failed
  * install logs      — display-manager read "<NOT SET>" because sudo readlink failed
  * flash-api         — a failed `findmnt /` dropped the RUNNING disk from the
                        protected set, offering it as a flash target
  * build-configurator— a failed systemctl read as "no sovereign units installed"
  * build-configurator— a failed dpkg-query read as "no packages installed"

The build API already returned None on failure (right design); two call sites
then wrote `_run(...) or ""`, collapsing the distinction again.

Fixing it exposed the mirror-image trap. `systemctl list-unit-files <pattern>`
exits 1 when NOTHING MATCHES — identical to a broken invocation — so treating
non-zero as failure made a clean machine report "probe failed". Usability is
probed separately (`systemctl --version`); only then does an empty result mean
genuinely empty.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
API = REPO_ROOT / "scripts" / "operator" / "build-configurator-api.py"


def load():
    spec = importlib.util.spec_from_file_location("bc_api", API)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass
    return mod


def test_an_empty_result_is_reported_as_absent_not_unknown():
    """This machine has systemctl and (probably) no sovereign units."""
    mod = load()
    mod._host_units()
    assert mod._host_units.probe_failed is False, (
        "systemctl works here, so an empty unit list means ABSENT — reporting "
        "'probe failed' sends the operator chasing a working tool"
    )


def test_an_unusable_tool_is_reported_as_unknown_not_absent():
    mod = load()
    real = mod._run
    mod._run = lambda a, *x, **k: None if a[:1] == ["systemctl"] else real(a, *x, **k)
    mod._host_units()
    assert mod._host_units.probe_failed is True, (
        "with systemctl unusable the unit state is UNKNOWN; reporting 'none "
        "installed' is a claim the code never verified"
    )


def test_the_flag_travels_beside_the_units_not_inside_them():
    """The panel renders `Object.keys(units).length + " unit(s) installed"`.

    A sentinel entry inside `units` would turn a failed probe into
    "1 unit installed" — swapping one false claim for another.
    """
    body = API.read_text(encoding="utf-8")
    assert "units_probe_failed" in body, (
        "the failure must be signalled alongside the unit map"
    )
    assert "_probe_failed\":" not in body, (
        "no sentinel entry may live inside the units map"
    )


def test_no_call_site_collapses_none_into_empty():
    """`_run(...) or ""` throws away the distinction the helper exists to make."""
    import re
    body = API.read_text(encoding="utf-8")
    # join continuations so `) or ""` on the next line is still seen
    # A collapse is allowed where the code has ALREADY established the tool
    # works — but it must say so, on the preceding line, so the reasoning is
    # reviewable rather than assumed.
    lines = body.splitlines()
    joined_idx, joined = [], []
    buf, start = "", None
    for i, l in enumerate(lines):
        if start is None:
            start = i
        buf += " " + l.strip()
        if l.rstrip().endswith((")", '""', "'")) or not l.strip().endswith(","):
            joined.append(buf); joined_idx.append(start); buf, start = "", None
    bad = []
    for text, i in zip(joined, joined_idx):
        if re.search(r'_run\([^)]*\)\s*or\s*""', text):
            window = "\n".join(lines[max(0, i - 4):i])
            if "probe-failure handled" not in window:
                bad.append(text.strip()[:90])
    assert not bad, (
        f"{len(bad)} call site(s) collapse a failed probe into an empty result: {bad[:2]}"
    )
