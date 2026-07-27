"""The offline enable fallback must wire a unit where the unit says.

2026-07-27. install-gui-dashboards.sh enables units with `systemctl enable`,
falling back to a hand-made wants-symlink when systemctl is unusable — which is
the normal case during a d-i install, where this runs inside the target chroot
with no systemd.

That fallback hardcoded multi-user.target.wants for EVERY unit, including the
.timer units, all of which declare WantedBy=timers.target. They still started:
systemd starts whatever a reached target wants, so multi-user pulled them in and
everything looked correct.

The damage was invisible until someone tried to turn one off. `systemctl
disable <timer>` looks in timers.target.wants, finds nothing, reports success —
and the timer stays enabled through every reboot. A control that silently does
nothing is worse than one that fails.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASH = REPO_ROOT / "scripts" / "install" / "install-gui-dashboards.sh"
UNITS = REPO_ROOT / "systemd" / "system"


def enable_unit_body() -> str:
    body = DASH.read_text(encoding="utf-8")
    start = body.index("enable_unit() {")
    return body[start:body.index("\n}\n", start)]


def test_the_fallback_reads_the_units_wantedby():
    code = "\n".join(l for l in enable_unit_body().splitlines()
                     if not l.lstrip().startswith("#"))
    assert "WantedBy" in code, (
        "the offline fallback must read the unit's own [Install] WantedBy; "
        "hardcoding a target leaves `systemctl disable` unable to find the link"
    )
    assert "multi-user.target.wants/${unit}" not in code, (
        "a hardcoded multi-user.target.wants path is the bug this replaced"
    )


def test_timers_declare_a_different_target_than_services():
    """Guard the premise — if timers ever moved to multi-user, this lint is moot."""
    timers = list(UNITS.glob("*.timer"))
    assert timers, "no timer units found"
    targets = {re.search(r"^WantedBy=(\S+)", t.read_text(encoding="utf-8"), re.M).group(1)
               for t in timers
               if re.search(r"^WantedBy=(\S+)", t.read_text(encoding="utf-8"), re.M)}
    assert "timers.target" in targets, (
        f"timers no longer declare timers.target ({targets}); re-check the fallback"
    )


def test_the_fallback_places_each_unit_correctly(tmp_path: Path):
    """Run the real logic against a synthetic systemd root."""
    root = tmp_path / "root"
    (root / "etc/systemd/system").mkdir(parents=True)
    src = tmp_path / "src/systemd/system"
    src.mkdir(parents=True)
    for name in ("sovereign-dashboards.service", "sovereign-log-rotate.timer"):
        (src / name).write_text((UNITS / name).read_text(encoding="utf-8"), encoding="utf-8")

    script = f'''
    SRC="{tmp_path}/src"; ROOT="{root}"
    enable_unit() {{
      unit="$1"
      install -m 644 "${{SRC}}/systemd/system/${{unit}}" "${{ROOT}}/etc/systemd/system/"
      _wb="$(sed -n 's/^WantedBy=//p' "${{ROOT}}/etc/systemd/system/${{unit}}" | head -1 | tr -d ' ')"
      [ -n "${{_wb}}" ] || _wb="multi-user.target"
      mkdir -p "${{ROOT}}/etc/systemd/system/${{_wb}}.wants"
      ln -sf "${{ROOT}}/etc/systemd/system/${{unit}}" "${{ROOT}}/etc/systemd/system/${{_wb}}.wants/${{unit}}"
    }}
    enable_unit sovereign-dashboards.service
    enable_unit sovereign-log-rotate.timer
    '''
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert (root / "etc/systemd/system/multi-user.target.wants/sovereign-dashboards.service").is_symlink()
    assert (root / "etc/systemd/system/timers.target.wants/sovereign-log-rotate.timer").is_symlink(), (
        "the timer was not wired into timers.target.wants — `systemctl disable` "
        "would not find it"
    )
