"""The sovereign units must be findable — and must NOT be switched on.

2026-07-26, two facts that pull in opposite directions:

1. `install logs --from` reported "first boot never wrote /var/lib/sovereign-os"
   because nothing ever ran. The 114 units ship to /opt/sovereign-os/systemd/system,
   where systemd does not look, so even a deliberate
   `systemctl enable sovereign-firstboot.target` fails with "unit not found".

2. Enabling that target is what hung a boot at "Reached Target
   sovereign-firstboot.target". It Wants= a dozen heavy services —
   nvidia-driver-install, tetragon-install, inference-model-provision — and an
   earlier appliance build had ~130 services in restart loops.

So: install them where systemd can see them, enable none of them. Presence is
not activation, and turning them on is a deliberate operator act taken once the
desktop is known good.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD = REPO_ROOT / "scripts" / "build" / "installer-cdd" / "build.sh"


def postinst_body() -> str:
    text = BUILD.read_text(encoding="utf-8")
    start = text.index("DEBIAN/postinst")
    return text[start:text.index("\nPOSTINST", start)]


def code_lines() -> list[str]:
    return [l for l in postinst_body().splitlines()
            if l.strip() and not l.lstrip().startswith("#")]


def test_the_units_reach_a_directory_systemd_reads():
    body = "\n".join(code_lines())
    assert "/lib/systemd/system" in body, (
        "units in /opt/sovereign-os/systemd/system are invisible to systemd; "
        "`systemctl enable` cannot find them at all"
    )
    assert "daemon-reload" in body, "systemd must be told the units appeared"


def test_the_postinst_enables_nothing():
    """A package install must never silently start a dozen services."""
    for line in code_lines():
        assert not re.search(r"systemctl\s+(enable|start)\b", line), (
            f"postinst activates a unit: {line.strip()!r}. Enabling "
            "sovereign-firstboot.target pulls in nvidia-driver-install, "
            "tetragon-install and inference-model-provision — that is the "
            "combination that hung a boot."
        )


def test_the_heredoc_cannot_execute_its_own_comments():
    """The postinst is written by a heredoc; if unquoted, $ and ` in a comment
    would expand while the package is being BUILT (this bit twice already)."""
    text = BUILD.read_text(encoding="utf-8")
    line = next(l for l in text.splitlines() if "DEBIAN/postinst" in l and "cat >" in l)
    assert "<<'POSTINST'" in line or '<<"POSTINST"' in line, (
        "the postinst heredoc must be QUOTED, or comments mentioning shell "
        f"syntax are evaluated at build time: {line.strip()!r}"
    )
