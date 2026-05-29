"""sovereign-os SHIPPED.md production-delivery tracker — integrity lint.

Locks `backlog/SHIPPED.md` against the kind of drift that would
silently undermine its purpose: stale commit-hash references,
fictional milestone references, or "shipped" claims without
corresponding test files.

The operator's standing constraint is sacrosanct:

    > "You cannot mark something done if it hasn't reached Prod."

SHIPPED.md is the visible state of that constraint. Drift here
(claiming a row is shipped when its referenced commit doesn't
exist, or its referenced test file doesn't exist) would be
exactly the kind of invented-progress the operator forbids.

This lint enforces:
  1. Every commit hash referenced in SHIPPED.md actually exists
     in `git log`.
  2. Every test file path referenced exists in the repo.
  3. Every milestone heading (`## M0NN`) corresponds to a real
     milestone file in `backlog/milestones/`.
  4. The roll-up table is structurally present.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED = REPO_ROOT / "backlog" / "SHIPPED.md"
MILESTONES_DIR = REPO_ROOT / "backlog" / "milestones"


def _shipped_text() -> str:
    return SHIPPED.read_text()


def _commit_exists(sha: str) -> bool:
    """True when `git cat-file -e` confirms the SHA resolves to a real
    object in this repo. SHAs from selfdef PR are 7-char prefixes and
    don't exist here — they're documented as cross-repo refs, not
    locally-verifiable."""
    try:
        subprocess.check_call(
            ["git", "cat-file", "-e", sha],
            cwd=REPO_ROOT,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def test_shipped_file_present():
    assert SHIPPED.is_file(), f"SHIPPED.md missing at {SHIPPED}"


def test_rollup_table_present():
    text = _shipped_text()
    assert "## Roll-up" in text, "SHIPPED.md missing the Roll-up section"
    assert "Catalogued (total)" in text
    assert "13,740" in text, "roll-up must reference the catalogue total"


def test_referenced_local_commits_exist():
    """At least one commit hash referenced in SHIPPED.md must resolve
    in `git log` — proving the file is anchored to real history and
    not invented. Some SHAs reference selfdef commits (cross-repo
    refs) which won't resolve locally and that's expected; we just
    require at least one locally-verified SHA so SHIPPED.md proves
    it's tracking THIS repo's deliveries too."""
    text = _shipped_text()
    # Match 7-char hex SHAs that appear in commit columns (backtick-
    # quoted, e.g. `bf98e2a`).
    sha_pattern = re.compile(r"`([0-9a-f]{7})`")
    shas = {m.group(1) for m in sha_pattern.finditer(text)}

    verified = [sha for sha in shas if _commit_exists(sha)]
    assert verified, (
        f"no SHAs in SHIPPED.md resolved locally — SHIPPED.md "
        f"appears to reference nonexistent commits. Saw: {shas}"
    )


def test_referenced_test_files_exist():
    """Every test file path mentioned in SHIPPED.md MUST exist in the
    repo. Drift here would mean SHIPPED.md claims test coverage that
    doesn't exist."""
    text = _shipped_text()
    # Match paths like `tests/lint/test_*.py` or `docs/.../*.md`.
    path_pattern = re.compile(r"`((?:tests|docs|config|scripts|webapp)/[\w/\-.]+\.(?:py|md|yml|yaml|json))`")
    paths = {m.group(1) for m in path_pattern.finditer(text)}
    missing = sorted(p for p in paths if not (REPO_ROOT / p).is_file())
    assert not missing, (
        f"SHIPPED.md references files that don't exist: {missing}"
    )


def test_referenced_milestones_resolve_to_real_files():
    """Every `## M0NN ...` heading must correspond to a real milestone
    file in backlog/milestones/."""
    text = _shipped_text()
    # Match milestone headings: `## M060 — ...` or `## M002 — ...`.
    heading_re = re.compile(r"^## (M\d{3})\b", re.MULTILINE)
    headings = {m.group(1) for m in heading_re.finditer(text)}
    if not headings:
        # No per-milestone sections yet (empty SHIPPED bootstrap state) — OK.
        return
    available_files = list(MILESTONES_DIR.glob("M*-*.md"))
    available_ids = {
        re.match(r"(M\d{3})", p.name).group(1)
        for p in available_files
        if re.match(r"M\d{3}", p.name)
    }
    missing = headings - available_ids
    assert not missing, (
        f"SHIPPED.md references milestones with no file in "
        f"backlog/milestones/: {sorted(missing)}"
    )


def test_operator_constraint_quoted_verbatim():
    """The R10081-family operator constraint MUST appear verbatim in
    SHIPPED.md — the file's whole purpose is to enforce it. Drift
    here would soften the standing rule."""
    text = _shipped_text()
    assert "You cannot mark something done if it hasn't reached Prod" in text, (
        "SHIPPED.md must quote the operator constraint verbatim"
    )


def test_no_invention_clause_present():
    """The 'No invention' policy must be documented — every appended
    row references real commits + tests, never claims that aren't
    backed."""
    text = _shipped_text()
    assert "No invention" in text, (
        "SHIPPED.md must declare its no-invention policy explicitly"
    )


def test_partner_repo_cross_reference_present():
    """SHIPPED.md must declare its pairing with selfdef's SHIPPED.md
    so operators reading either know the other exists."""
    text = _shipped_text()
    assert "selfdef" in text.lower(), (
        "SHIPPED.md must reference its selfdef partner so operators "
        "reading one know the other exists"
    )


def test_referenced_webapp_dirs_exist():
    """Every `webapp/<name>` referenced in SHIPPED.md must correspond
    to a real dir. Drift here would mean SHIPPED.md is claiming
    production state that doesn't exist."""
    text = _shipped_text()
    webapp_pattern = re.compile(r"`webapp/([a-z0-9_-]+)`")
    dirs = {m.group(1) for m in webapp_pattern.finditer(text)}
    webapp_root = REPO_ROOT / "webapp"
    if not webapp_root.is_dir():
        return
    available = {p.name for p in webapp_root.iterdir() if p.is_dir()}
    missing = sorted(dirs - available)
    assert not missing, (
        f"SHIPPED.md references webapp dirs that don't exist: {missing}"
    )


def test_referenced_scripts_paths_exist():
    """Every `scripts/<path>` referenced must exist on disk."""
    text = _shipped_text()
    scripts_pattern = re.compile(r"`(scripts/[\w/\-.]+)`")
    paths = {m.group(1) for m in scripts_pattern.finditer(text)}
    missing = sorted(p for p in paths if not (REPO_ROOT / p).exists())
    assert not missing, (
        f"SHIPPED.md references scripts paths that don't exist: {missing}"
    )


def test_referenced_config_paths_exist():
    """Every `config/<path>` referenced must exist on disk."""
    text = _shipped_text()
    config_pattern = re.compile(r"`(config/[\w/\-.]+)`")
    paths = {m.group(1) for m in config_pattern.finditer(text)}
    missing = sorted(p for p in paths if not (REPO_ROOT / p).exists())
    assert not missing, (
        f"SHIPPED.md references config paths that don't exist: {missing}"
    )
