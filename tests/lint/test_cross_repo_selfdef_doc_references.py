"""Cross-repo selfdef doc-reference integrity (sovereign-os operator docs
cite specific selfdef GitHub paths — those paths must exist on selfdef's
main branch, else the operator's deep-links 404).

Two `docs/operator/*.md` files currently reference selfdef paths via
GitHub blob URLs:
  - docs/operator/m060-deployment-guide.md →
    cyberpunk042/selfdef/blob/main/docs/operator/m060-cockpit-mirror-producers.md
  - docs/operator/ms022-sse-quota-cockpit.md →
    cyberpunk042/selfdef/blob/main/docs/operator/ms022-sse-subscriber-quota.md

The integrity contract: every referenced selfdef path must exist as a
real file in the adjacent selfdef repo (CI on either repo catches a
rename or deletion before operators hit a 404 deep-link).

SKIPs gracefully when the selfdef repo is not adjacent (dev envs without
both repos cloned); env var SOVEREIGN_OS_SELFDEF_REPO overrides default
../selfdef path.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "docs"

SELFDEF_REPO_DEFAULT = REPO_ROOT.parent / "selfdef"
SELFDEF_REPO = Path(os.environ.get("SOVEREIGN_OS_SELFDEF_REPO", str(SELFDEF_REPO_DEFAULT)))

# GitHub blob URLs to selfdef like
# cyberpunk042/selfdef/blob/<branch>/<repo-relative-path>[#optional-anchor]
URL_RE = re.compile(
    r"cyberpunk042/selfdef/blob/[a-z][a-z0-9_-]*/([^\s)\\#]+)",
)


def _extract_selfdef_paths() -> set[str]:
    """Walk every .md under docs/ and pull every selfdef-blob path out
    (URL fragment anchors stripped; file-path existence is what we
    check). Covers docs/operator/*.md + docs/src/**/*.md.
    """
    paths: set[str] = set()
    if not DOCS_ROOT.is_dir():
        return paths
    for md in sorted(DOCS_ROOT.rglob("*.md")):
        text = md.read_text(encoding="utf-8", errors="replace")
        paths.update(URL_RE.findall(text))
    return paths


def test_at_least_some_cross_repo_refs_present():
    """Sanity check the regex catches the known references."""
    paths = _extract_selfdef_paths()
    # Currently both known refs land docs/operator paths
    assert any(
        "docs/operator/m060" in p or "docs/operator/ms022" in p for p in paths
    ), f"expected to find at least the known m060/ms022 cross-repo refs; got {sorted(paths)}"


@pytest.mark.skipif(
    not SELFDEF_REPO.is_dir(),
    reason=f"selfdef repo not adjacent at {SELFDEF_REPO} (set SOVEREIGN_OS_SELFDEF_REPO to override)",
)
def test_every_cross_repo_selfdef_path_resolves():
    """Every selfdef path referenced from sovereign-os operator docs
    must exist on disk in the adjacent selfdef repo, so the operator's
    deep-link doesn't 404."""
    paths = _extract_selfdef_paths()
    missing: list[str] = []
    for p in sorted(paths):
        target = SELFDEF_REPO / p
        if not target.exists():
            missing.append(p)
    assert not missing, (
        f"sovereign-os operator docs reference selfdef paths that do not "
        f"exist in the adjacent selfdef repo (broken deep-links): {missing}. "
        f"Either restore the file on selfdef side, or update the sovereign-os "
        f"operator doc to point at the new location."
    )
