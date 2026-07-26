"""A mandatory ReadWritePaths= must have something that CREATES the directory.

Operator's flashed box, 2026-07-26. The first-boot journal was ~130 repetitions of:

    sovereign-jobs-api.service: Failed to set up mount namespacing:
      /var/lib/sovereign-os/jobs: No such file or directory
    sovereign-jobs-api.service: Failed at step NAMESPACE spawning /usr/bin/python3

`ReadWritePaths=/var/lib/sovereign-os/jobs` has no `-` prefix, so systemd treats
it as mandatory: if the path does not exist, building the mount namespace FAILS
and the service never execs. With `Restart=on-failure` + `RestartSec=3` that
retried for the entire boot, and the noise buried every other error — the real
failures (nvidia, tetragon, UPS) were invisible underneath it.

Nothing created that directory. `sovereign-openclaw.service` had the right shape
all along — `StateDirectory=sovereign-os/openclaw` — so systemd makes the
directory before the namespace exists. Two units missed it.

The rule: every mandatory ReadWritePaths under /var/lib/sovereign-os/ must be
covered by a StateDirectory=, or be marked optional with a `-` prefix when the
service genuinely tolerates its absence.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
UNITS = sorted((REPO_ROOT / "systemd" / "system").glob("*.service"))
STATE_ROOT = "/var/lib/"


def _directives(text: str, key: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#") or not s.startswith(f"{key}="):
            continue
        out.extend(s.split("=", 1)[1].split())
    return out


# Directories that already exist before any unit starts, so a mandatory
# ReadWritePaths on them is safe. Each entry is JUSTIFIED, not assumed:
#   /var/lib/sovereign-os  — provision-bake.sh does `mkdir -p /var/lib/sovereign-os`
#                            at bake time (asserted by test_state_root_is_baked)
#   /var/lib/apt           — shipped by the apt package itself
PRE_EXISTING = ("/var/lib/sovereign-os", "/var/lib/apt")


def _covered(path: str, state_dirs: list[str]) -> bool:
    """True if `path` is pre-created, or a StateDirectory= creates it."""
    if path.rstrip("/") in PRE_EXISTING:
        return True
    rel = path[len(STATE_ROOT):]
    for sd in state_dirs:
        sd = sd.strip("/")
        if rel == sd or rel.startswith(sd + "/"):
            return True
    return False


def test_state_root_is_baked():
    """The exemption above is only valid while the bake really creates it."""
    bake = (REPO_ROOT / "scripts" / "build" / "provision-bake.sh").read_text(encoding="utf-8")
    assert "mkdir -p /var/lib/sovereign-os" in bake, (
        "units take a mandatory ReadWritePaths=/var/lib/sovereign-os on the "
        "assumption the bake creates it — if that goes away, every one of them "
        "starts failing at NAMESPACE"
    )


def test_there_are_units_to_check():
    assert UNITS, "no units found — this lint would silently pass"


@pytest.mark.parametrize("unit", UNITS, ids=lambda p: p.name)
def test_mandatory_state_paths_are_created(unit: Path):
    text = unit.read_text(encoding="utf-8")
    if "ProtectSystem=strict" not in text and "ReadWritePaths=" not in text:
        return
    state_dirs = _directives(text, "StateDirectory")
    offenders = []
    for p in _directives(text, "ReadWritePaths"):
        if p.startswith("-"):
            continue                      # explicitly optional — fine
        if not p.startswith(STATE_ROOT):
            continue                      # outside /var/lib (node_exporter etc.)
        if p.startswith("/var/lib/node_exporter"):
            continue                      # created by the exporter's own package
        if not _covered(p, state_dirs):
            offenders.append(p)
    assert not offenders, (
        f"{unit.name}: ReadWritePaths {offenders} are MANDATORY (no `-` prefix) "
        f"but no StateDirectory= creates them (StateDirectory={state_dirs or 'none'}). "
        "systemd fails to build the mount namespace and the service never execs — "
        "with Restart=on-failure that is an infinite loop that floods the journal. "
        "Add StateDirectory=<path under /var/lib>, or prefix the path with `-` if "
        "the service truly tolerates it being absent."
    )


def test_the_two_units_from_the_incident_are_fixed():
    """Explicit regression guard for the exact units that looped."""
    for name, want in (
        ("sovereign-jobs-api.service", "sovereign-os/jobs"),
        ("sovereign-open-computer.service", "sovereign-os/open-computer"),
    ):
        text = (REPO_ROOT / "systemd" / "system" / name).read_text(encoding="utf-8")
        assert want in _directives(text, "StateDirectory"), (
            f"{name} must declare StateDirectory={want}"
        )


def test_no_unit_combines_a_fast_restart_with_an_uncreated_state_dir():
    """It is the COMBINATION that floods a boot log, not either half.

    ~60 panel daemons use Restart=on-failure + RestartSec=3 deliberately, and
    that is fine on its own. What made jobs-api unreadable was pairing it with a
    mandatory ReadWritePaths nothing created: the service can NEVER start, so it
    retries forever. Note systemd's default rate limit (5 starts / 10s) does not
    catch RestartSec=3 — only ~3 restarts fit in the window — which is precisely
    why it ran for the entire boot.

    Flagging RestartSec=3 alone would fail 66 units and teach nobody anything.
    """
    offenders = []
    for unit in UNITS:
        text = unit.read_text(encoding="utf-8")
        if "Restart=on-failure" not in text:
            continue
        sec = re.search(r"^RestartSec=(\d+)", text, re.M)
        if not sec or int(sec.group(1)) > 5:
            continue
        state_dirs = _directives(text, "StateDirectory")
        for p in _directives(text, "ReadWritePaths"):
            if p.startswith("-") or not p.startswith(STATE_ROOT):
                continue
            if p.startswith("/var/lib/node_exporter"):
                continue
            if not _covered(p, state_dirs):
                offenders.append(f"{unit.name} → {p} (RestartSec={sec.group(1)})")
    assert not offenders, (
        "these units can never start AND retry every few seconds, so they flood "
        f"the journal for the whole boot and bury every other error: {offenders}"
    )
