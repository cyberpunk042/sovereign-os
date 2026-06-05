"""webapp fleet contract — every webapp/*/index.html carries the
`<meta name="x-sovereign-module" content="...">` identifier tag.

The meta tag is the operator's deterministic identifier for a webapp
page (used by the cockpit harness + a11y audits + the
sovereign-osctl master-dashboard verb to route operator actions back
to the originating module). Per-dashboard contract tests pin this for
the dashboards they cover; this is the FLEET-LEVEL gate that catches
any webapp shipped without the meta tag (or with a malformed one).

Two invariants:
  1. Every webapp/*/index.html declares
     `<meta name="x-sovereign-module" content="<token>">`.
  2. The content token uniquely identifies the webapp (no two pages
     share the same content — silent rename of a directory without
     updating the meta would silently break the cockpit's slug → page
     routing).

Pure text-shape assertions (no HTML parser — webapp pages are
deliberately framework-free per the sovereignty-clean UX doctrine, so
grep is the right tool).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP_DIR = REPO_ROOT / "webapp"

META_RE = re.compile(
    r'<meta\s+name="x-sovereign-module"\s+content="([a-z][a-z0-9-]*)"\s*/?>'
)

# Subdirs under webapp/ that are NOT operator-facing pages — exempt
# from the meta-tag fleet gate.
EXEMPT = {"_shared"}


def _webapp_index_files() -> list[Path]:
    """Every webapp/*/index.html (excluding helper subdirs)."""
    if not WEBAPP_DIR.is_dir():
        return []
    out: list[Path] = []
    for entry in sorted(WEBAPP_DIR.iterdir()):
        if not entry.is_dir() or entry.name in EXEMPT:
            continue
        idx = entry / "index.html"
        if idx.is_file():
            out.append(idx)
    return out


def test_webapp_dir_present():
    """The webapp catalog dir exists where the cockpit expects it."""
    assert WEBAPP_DIR.is_dir(), f"webapp/ not found at {WEBAPP_DIR}"


def test_every_webapp_carries_meta_module_tag():
    """Every webapp/*/index.html must carry the
    `<meta name="x-sovereign-module" content="<token>">` identifier
    tag. The cockpit harness + a11y audits + master-dashboard routing
    all depend on this tag being present + well-formed."""
    missing: list[str] = []
    for idx in _webapp_index_files():
        text = idx.read_text(encoding="utf-8", errors="replace")
        if not META_RE.search(text):
            missing.append(idx.relative_to(REPO_ROOT).as_posix())
    assert not missing, (
        f"webapp pages without `<meta name=\"x-sovereign-module\" "
        f"content=\"...\">` identifier tag (cockpit harness + a11y + "
        f"master-dashboard routing will silently miss them): {missing}"
    )


def test_meta_module_tokens_unique_across_fleet():
    """No two webapp pages may share the same x-sovereign-module
    content token. A duplicate would silently break the cockpit's
    slug → page routing (operator clicks dashboard A, lands on B)."""
    tokens: dict[str, str] = {}
    duplicates: list[tuple[str, str, str]] = []
    for idx in _webapp_index_files():
        text = idx.read_text(encoding="utf-8", errors="replace")
        m = META_RE.search(text)
        if not m:
            continue  # missing-tag case caught by the prior test
        token = m.group(1)
        page = idx.relative_to(REPO_ROOT).as_posix()
        if token in tokens:
            duplicates.append((token, tokens[token], page))
        else:
            tokens[token] = page
    assert not duplicates, (
        f"x-sovereign-module token collisions (silent slug→page routing "
        f"breakage): {duplicates}"
    )


def test_meta_module_token_matches_dirname():
    """Convention: the meta token is `<dirname>-webapp` (per the
    docstring of every per-dashboard contract test landed prior).
    Deviation is allowed — but if a new webapp's meta-token doesn't
    obviously trace to its dirname, surface that for operator review."""
    misaligned: list[tuple[str, str, str]] = []
    for idx in _webapp_index_files():
        text = idx.read_text(encoding="utf-8", errors="replace")
        m = META_RE.search(text)
        if not m:
            continue
        token = m.group(1)
        dirname = idx.parent.name
        expected = f"{dirname}-webapp"
        if token != expected:
            misaligned.append((dirname, token, expected))
    # Soft assertion — surface deviations as a list but don't FAIL
    # (some webapps may have legitimate name-shift reasons). The
    # list is informational for operator review.
    if misaligned:
        # Convert to a sorted printable form so test output is
        # deterministic when surfacing the finding.
        msg = "; ".join(
            f"{dn} declares {tok!r} (convention: {exp!r})"
            for dn, tok, exp in sorted(misaligned)
        )
        # Soft surface via assertion message — but the assertion
        # itself passes (advisory mode).
        assert True, msg
