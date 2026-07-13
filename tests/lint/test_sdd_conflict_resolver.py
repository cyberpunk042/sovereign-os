#!/usr/bin/env python3
"""
tests/lint/test_sdd_conflict_resolver.py — functional test of the parallel-session
SDD-collision auto-resolver (`scripts/git/sdd_conflict_resolver.py`, SDD-980).

Builds a hermetic git fixture with a planted collision and asserts the resolver's
contract ("auto-apply, verify, warn on doubt"):

  * happy path (no collision)        → exit 0, silent, no writes;
  * unambiguous collision + verify OK → intruder renumbered into its own band,
    owner keeps the number, a RESOLUTION-LOG entry is written;
  * verify FAILS                      → the renumber is reverted (owner + intruder
    both restored) — never a half-applied unverified state;
  * ambiguous (intruder declares no band) → nothing renamed, warn, exit non-zero.

`_verify` (which shells out to pytest over the real repo's lints) is monkeypatched
to controllable outcomes so the fixture stays minimal and the test pins the
plan/apply/revert/warn LOGIC deterministically. The real verify is exercised by
the live run recorded in SDD-980 and by CI.

Stdlib + pytest only.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

RESOLVER = Path(__file__).resolve().parents[2] / "scripts" / "git" / "sdd_conflict_resolver.py"

SESSIONS_MD = """# sessions
| session-id | band | e11 | branch | purpose | status |
|---|---|---|---|---|---|
| phase-1-audit | 950–999 | E11.M950–M999 | claude/audit | audit | active |
| cockpit-wasm | 800–899 | E11.M800–M899 | claude/cockpit-wasm | bridge | active |
"""

INDEX_MD = """# INDEX
| n | title | status | phase | notes | owner | band |
|---|---|---|---|---|---|---|
| 800 | cockpit base | draft | x | note | op | SDD-800 (cockpit-wasm session) |
| 979 | audit owner | draft | x | note | op | SDD-979 (this session) |
"""

MANDATE_MD = """# mandate
| id | desc | owner | ref |
|---|---|---|---|
| E11.M800 | cockpit base (SDD-800) | op | SDD-800 on branch claude/cockpit-wasm |
| E11.M979 | audit owner (SDD-979) | op | SDD-979 on branch claude/audit |
"""

CONTEXT_MD = """# context
<!-- COUNTS-CONTRACT -->
| sdd files | 0 | x |
<!-- END COUNTS-CONTRACT -->
"""


def _sdd(n: int, band: str | None) -> str:
    band_line = f"> Number band: **{band}** per SDD-100.\n" if band else ""
    return f"# SDD-{n} — demo\n\n> Status: draft\n{band_line}> Mandate module: **E11.M{n}**.\n\nSelf-ref SDD-{n} / E11.M{n}.\n"


def _load(repo: Path):
    spec = importlib.util.spec_from_file_location("sdd_resolver_under_test", RESOLVER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.REPO = repo
    mod.SDD_DIR = repo / "docs" / "sdd"
    mod.INDEX = mod.SDD_DIR / "INDEX.md"
    mod.SESSIONS = mod.SDD_DIR / "SESSIONS.md"
    mod.RESOLUTION_LOG = mod.SDD_DIR / "RESOLUTION-LOG.md"
    mod.MANDATE = repo / "docs" / "standing-directives" / "mandate.md"
    mod.CONTEXT = repo / "context.md"
    mod.GEN_CATALOG = repo / "does-not-exist.py"  # skip catalog regen
    return mod


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True, text=True)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "fix"
    (r / "docs" / "sdd").mkdir(parents=True)
    (r / "docs" / "standing-directives").mkdir(parents=True)
    (r / "docs" / "sdd" / "SESSIONS.md").write_text(SESSIONS_MD)
    (r / "docs" / "sdd" / "INDEX.md").write_text(INDEX_MD)
    (r / "docs" / "standing-directives" / "mandate.md").write_text(MANDATE_MD)
    (r / "context.md").write_text(CONTEXT_MD)
    (r / "docs" / "sdd" / "800-cockpit-base.md").write_text(_sdd(800, "800–899 (cockpit-wasm bridge session)"))
    (r / "docs" / "sdd" / "979-audit-owner.md").write_text(_sdd(979, "950–999 (phase-1 audit session)"))
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "base")
    return r


def test_happy_path_is_silent_noop(repo, capsys):
    mod = _load(repo)
    assert mod.run("apply") == 0
    out = capsys.readouterr()
    assert out.out == "" and out.err == ""
    assert not mod.RESOLUTION_LOG.exists() or "## " not in mod.RESOLUTION_LOG.read_text()


def _plant_cockpit_979(repo: Path) -> None:
    """A cockpit-wasm session took SDD-979 (out of its 800–899 band) — the
    intruder — and it landed on main via a merge (committed)."""
    (repo / "docs" / "sdd" / "979-cockpit-intruder.md").write_text(
        _sdd(979, "800–899 (cockpit-wasm bridge session)"))
    idx = repo / "docs" / "sdd" / "INDEX.md"
    idx.write_text(idx.read_text() +
                   "| 979 | cockpit intruder | draft | x | note | op | SDD-979 (cockpit-wasm session) |\n")
    man = repo / "docs" / "standing-directives" / "mandate.md"
    man.write_text(man.read_text() +
                   "| E11.M979 | cockpit intruder (SDD-979) | op | SDD-979 on branch claude/cockpit-wasm |\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "merge intruder")


def test_unambiguous_collision_is_resolved_and_logged(repo, monkeypatch):
    mod = _load(repo)
    monkeypatch.setattr(mod, "_verify", lambda: (True, "stub-green"))
    _plant_cockpit_979(repo)

    assert mod.duplicate_numbers() == [979]
    rc = mod.run("apply")
    assert rc == 0
    # intruder renumbered into its own band's next free slot (800 used → 801)
    assert (mod.SDD_DIR / "801-cockpit-intruder.md").is_file()
    assert not (mod.SDD_DIR / "979-cockpit-intruder.md").exists()
    # owner keeps 979
    assert (mod.SDD_DIR / "979-audit-owner.md").is_file()
    # registries: exactly one 979 row (owner), a new 801 row (intruder)
    idx = mod.INDEX.read_text()
    assert idx.count("\n| 979 |") == 1 and "\n| 801 |" in idx
    man = mod.MANDATE.read_text()
    assert man.count("| E11.M979 |") == 1 and "| E11.M801 |" in man
    # the intruder file's own self-refs were renumbered
    body = (mod.SDD_DIR / "801-cockpit-intruder.md").read_text()
    assert "SDD-801" in body and "SDD-979" not in body
    # a ledger entry was written
    assert "SDD-979 → SDD-801" in mod.RESOLUTION_LOG.read_text()


def test_verify_failure_reverts_the_renumber(repo, monkeypatch):
    mod = _load(repo)
    monkeypatch.setattr(mod, "_verify", lambda: (False, "stub-red: still dup"))
    _plant_cockpit_979(repo)

    rc = mod.run("apply")
    assert rc != 0  # unresolved
    # revert restored the committed state: intruder is 979 again, no 801 leaked
    assert (mod.SDD_DIR / "979-cockpit-intruder.md").is_file()
    assert not (mod.SDD_DIR / "801-cockpit-intruder.md").exists()
    assert (mod.SDD_DIR / "979-audit-owner.md").is_file()


def test_ambiguous_intruder_warns_and_touches_nothing(repo, monkeypatch, capsys):
    mod = _load(repo)
    monkeypatch.setattr(mod, "_verify", lambda: (True, "unused"))
    # intruder declares NO band → unattributable
    (repo / "docs" / "sdd" / "979-mystery.md").write_text(_sdd(979, None))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "merge mystery")

    rc = mod.run("apply")
    assert rc != 0
    # nothing renamed — both 979 files remain
    assert (mod.SDD_DIR / "979-mystery.md").is_file()
    assert (mod.SDD_DIR / "979-audit-owner.md").is_file()
    err = capsys.readouterr().err
    assert "could NOT resolve" in err and "no `Number band:`" in err
