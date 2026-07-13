"""systemd install-coverage contract (F-2026-051 / SDD-964).

The 111 systemd units (91 service / 19 timer / 1 target) are the boot-time fleet.
Their `ExecStart*` lines reference scripts under two install roots by ownership:

  * operator-API scripts  -> /usr/local/lib/sovereign-os/scripts/operator   (FHS)
  * hook/inference/hardware -> /opt/sovereign-os/scripts/{hooks,inference,hardware}

`make install-units` stages the unit files + those three script trees so a booted
box actually has every script an ExecStart points at. This lint keeps that whole
arrangement honest — it fails if:

  * any unit's ExecStart script does NOT resolve to a real in-repo file
    (a unit pointing at a phantom script would install a broken fleet);
  * a unit references a script root outside the two documented prefixes
    (an undocumented third prefix creeping in — the exact drift F-2026-051 found);
  * `make install-units` stops staging one of the three script trees or the units;
  * systemd/system/README.md's stated fleet counts drift from the tree.

So `make install-units` provably stages a working fleet, and the two-prefix
doctrine can't silently rot. This is the objective, file-side core of F-2026-051;
the deeper *prefix unification* (collapsing /opt into /usr/local/lib) is scoped as
an operator decision (Q-964-A in SDD-964), not done here.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UNIT_DIR = REPO_ROOT / "systemd" / "system"
README = UNIT_DIR / "README.md"
MAKEFILE = REPO_ROOT / "Makefile"

# The two documented install roots (systemd/system/README.md "two-prefix doctrine").
# Maps the absolute install prefix -> the in-repo tree it is staged from.
PREFIX_TO_REPO = {
    "/usr/local/lib/sovereign-os/scripts/": "scripts/",
    "/opt/sovereign-os/scripts/": "scripts/",
}

# Any script path an ExecStart* references under a sovereign-os install root.
_SCRIPT_RE = re.compile(r"/(?:opt|usr/local/lib)/sovereign-os/scripts/[A-Za-z0-9_./-]+")


def _unit_files() -> list[Path]:
    return sorted(
        [*UNIT_DIR.glob("*.service"), *UNIT_DIR.glob("*.timer"), *UNIT_DIR.glob("*.target")]
    )


def _referenced_scripts() -> dict[Path, set[str]]:
    """unit -> set of sovereign-os script install-paths its Exec* lines reference."""
    out: dict[Path, set[str]] = {}
    for u in _unit_files():
        body = u.read_text(encoding="utf-8")
        paths = set(_SCRIPT_RE.findall(body))
        if paths:
            out[u] = paths
    return out


def _install_path_to_repo(p: str) -> str | None:
    for prefix, repo in PREFIX_TO_REPO.items():
        if p.startswith(prefix):
            return repo + p[len(prefix):]
    return None


def test_every_execstart_script_exists_in_repo():
    """A unit must never point ExecStart at a script that isn't in the repo —
    else install-units stages a fleet that can't run."""
    missing: list[str] = []
    for unit, paths in _referenced_scripts().items():
        for p in sorted(paths):
            repo = _install_path_to_repo(p)
            assert repo is not None, f"{unit.name}: {p} is under no documented prefix"
            if not (REPO_ROOT / repo).is_file():
                missing.append(f"{unit.name} -> {p} (repo: {repo})")
    assert not missing, "systemd units reference scripts that don't exist in-repo:\n" + "\n".join(missing)


def test_all_referenced_prefixes_are_documented():
    """Every referenced script root is one of the two documented prefixes, and the
    README documents both roots (the two-prefix doctrine)."""
    for unit, paths in _referenced_scripts().items():
        for p in sorted(paths):
            assert any(p.startswith(pref) for pref in PREFIX_TO_REPO), (
                f"{unit.name}: {p} is under an undocumented install prefix"
            )
    readme = README.read_text(encoding="utf-8")
    for pref in ("/usr/local/lib/sovereign-os/scripts/operator", "/opt/sovereign-os/scripts/"):
        assert pref in readme, f"systemd/system/README.md does not document the install root {pref}"


def test_install_units_stages_the_trees_and_units():
    """`make install-units` must install the unit files + all three script trees."""
    mk = MAKEFILE.read_text(encoding="utf-8")
    assert re.search(r"(?m)^install-units:", mk), "Makefile has no `install-units` target"
    # unit files installed
    assert re.search(r"install .*systemd/system/\*\.service", mk), (
        "install-units does not install systemd/system/*.service"
    )
    # each of the three script trees staged
    for tree in ("scripts/operator", "scripts/hooks", "scripts/inference", "scripts/hardware"):
        assert re.search(rf"cp -r {re.escape(tree)}/\*", mk), (
            f"install-units does not stage {tree}/ into its install root"
        )


def test_readme_fleet_counts_match_tree():
    """The README's stated fleet counts (service/timer/target) match the filesystem —
    counts-as-contract, so the doc can't over- or under-claim the fleet size."""
    n_service = len(list(UNIT_DIR.glob("*.service")))
    n_timer = len(list(UNIT_DIR.glob("*.timer")))
    n_target = len(list(UNIT_DIR.glob("*.target")))
    total = n_service + n_timer + n_target
    readme = README.read_text(encoding="utf-8")
    for n, label in ((total, "total"), (n_service, "service"), (n_timer, "timer"), (n_target, "target")):
        assert re.search(rf"\b{n}\b", readme), (
            f"systemd/system/README.md does not state the {label} unit count ({n}); "
            "update the fleet counts in the README"
        )
