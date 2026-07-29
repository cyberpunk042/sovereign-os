"""The readiness preflight must know about every path the build can take.

2026-07-28. Nothing checked whether the BUILD HOST could finish a build. The
pre-install hooks check the TARGET machine (network/storage/TPM); the gaps that
actually stop a build — no kernel .debs, no signing key, no simple-cdd — were
each discovered the expensive way, after a 30-minute kernel compile or a
multi-GB mirror download.

`build-readiness.sh` closes that. It is only useful if it stays in step with the
pipeline, so this applies the same discipline as
test_every_substrate_is_handled_end_to_end.py: a substrate the orchestrator can
SELECT must be a substrate readiness can CHECK. Otherwise adding one silently
produces a preflight that reports READY for a path it knows nothing about — and
a preflight that lies is worse than none.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
READY = REPO_ROOT / "scripts" / "build" / "build-readiness.sh"
ORCHESTRATE = REPO_ROOT / "scripts" / "build" / "orchestrate.sh"
MAKEFILE = REPO_ROOT / "Makefile"


def selectable_substrates() -> set[str]:
    text = ORCHESTRATE.read_text(encoding="utf-8")
    subs = set(re.findall(r"SOVEREIGN_OS_SUBSTRATE=([a-z0-9-]+)", text))
    m = re.search(r"SOVEREIGN_OS_SUBSTRATE:=([a-z0-9-]+)", text)
    if m:
        subs.add(m.group(1))
    return subs


def test_it_is_executable():
    assert os.access(READY, os.X_OK), f"{READY.name} must be executable"


@pytest.mark.parametrize("substrate", sorted(selectable_substrates()))
def test_readiness_checks_every_selectable_substrate(substrate: str):
    body = READY.read_text(encoding="utf-8")
    assert substrate in body, (
        f"build-readiness.sh never mentions {substrate!r}, which the orchestrator "
        f"can select. It would report on a path it does not actually check."
    )


def test_it_resolves_the_same_substrate_the_orchestrator_would():
    """A preflight that checks a DIFFERENT path than the build runs is a lie."""
    body = READY.read_text(encoding="utf-8")
    for artifact_distro, substrate in (
        ("installer:ubuntu", "ubuntu-autoinstall"),
        ("installer:*", "installer-cdd"),
        ("installer-live:*", "live-build"),
    ):
        assert re.search(rf"{re.escape(artifact_distro)}\)\s+SUBSTRATE={substrate}", body), (
            f"readiness must map {artifact_distro} to {substrate}, matching "
            "orchestrate.sh's own ARTIFACT×DISTRO case"
        )


def test_it_is_reachable_from_the_orchestrator_and_make():
    orch = ORCHESTRATE.read_text(encoding="utf-8")
    assert re.search(r"^\s*ready\)\s+cmd_ready", orch, re.M), (
        "orchestrate.sh must dispatch a `ready` subcommand"
    )
    assert "#   ready" in orch, "`ready` must appear in the help text, or nobody finds it"
    assert re.search(r"^ready:", MAKEFILE.read_text(encoding="utf-8"), re.M), (
        "the Makefile must expose a `ready` target"
    )


def test_it_never_mutates_the_host():
    """A preflight must be safe to run at any time, by anyone.

    One that installs packages or mounts filesystems is not a preflight — and an
    operator who cannot trust it will not run it before the long build, which is
    the only moment it helps.
    """
    # MENTIONING a mutating command is fine and in fact required — the whole
    # value of this preflight is printing the exact fix. What matters is whether
    # it EXECUTES one. So ignore lines that merely hand text to a reporting
    # helper, and check the rest.
    # Strip DOUBLE-QUOTED spans: every fix hint is a quoted argument to
    # blocker/warn, while a command the script actually runs is unquoted. A
    # first-word check is not enough — the hints sit mid-line after shell
    # keywords, e.g. `else blocker "..." "sudo apt install $2"; fi`.
    violations = []
    for n, line in enumerate(READY.read_text(encoding="utf-8").splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        bare = re.sub(r'"[^"]*"', "", s)   # drop quoted text = drop the hints
        for forbidden in ("apt-get install", "apt install", "mount -", "mkfs",
                          "dd if=", "rm -rf", "systemctl start", "systemctl enable"):
            if forbidden in bare:
                violations.append(f"{n}: {s}")
    assert not violations, (
        "build-readiness.sh appears to EXECUTE a mutating command:\n  "
        + "\n  ".join(violations)
        + "\nIt must be strictly read-only — report the gap and the fix command, "
          "never apply it. (Printing the command inside a blocker/warn hint is fine.)"
    )


def test_it_reports_not_ready_when_a_blocker_exists(tmp_path: Path):
    """The whole point: blockers must produce a non-zero exit.

    The first --all implementation ran each path in a subshell, so the counters
    never reached the summary and it printed "READY — 0 warnings" directly under
    eight BLOCK lines. Exit status is what CI and the panel key on.
    """
    env = dict(os.environ)
    env.update({
        "SOVEREIGN_OS_ARTIFACT": "installer",
        # A kernel-deb dir that is certain to be empty ⇒ guaranteed blocker.
        "SOVEREIGN_OS_KERNEL_DEBS_DIR": str(tmp_path),
        "SOVEREIGN_OS_KEY_DIR": str(tmp_path / "keys"),
    })
    r = subprocess.run([str(READY)], cwd=REPO_ROOT, env=env,
                       capture_output=True, text=True)
    assert r.returncode != 0, (
        "readiness reported success with no kernel .debs present:\n" + r.stdout
    )
    assert "NOT READY" in r.stdout
    assert "BLOCK" in r.stdout


def test_the_all_mode_aggregates_instead_of_reporting_the_last_path(tmp_path: Path):
    """--all must not inherit its verdict from whichever path ran last."""
    body = READY.read_text(encoding="utf-8")
    assert "not_ready" in body, (
        "--all must aggregate per-path results; subshell counters do not "
        "propagate to the summary"
    )
    env = dict(os.environ)
    env["SOVEREIGN_OS_KERNEL_DEBS_DIR"] = str(tmp_path)
    r = subprocess.run([str(READY), "--all"], cwd=REPO_ROOT, env=env,
                       capture_output=True, text=True)
    assert r.returncode != 0 and "NOT READY" in r.stdout, (
        "--all reported READY while individual paths were blocked:\n" + r.stdout[-2000:]
    )
