"""F-2026-093 — rustdoc-panel contract.

Build local rustdoc as a panel: a catalog of all workspace crates with
search/filter, descriptions, and source links. The panel is static HTML
plus a generated catalog.json; it follows the same app-shell + a11y + nav +
course snippet discipline as every other cockpit panel.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PANEL_HTML = REPO_ROOT / "webapp" / "rustdoc-panel" / "index.html"
CATALOG_JSON = REPO_ROOT / "webapp" / "rustdoc-panel" / "catalog.json"
GENERATOR = REPO_ROOT / "scripts" / "webapp" / "gen-rustdoc-panel-catalog.py"
CRATES_DIR = REPO_ROOT / "crates"


def test_panel_html_exists():
    assert PANEL_HTML.is_file(), f"rustdoc-panel missing: {PANEL_HTML}"


def test_catalog_json_exists_and_parses():
    assert CATALOG_JSON.is_file(), f"catalog.json missing: {CATALOG_JSON}"
    data = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
    assert "crates" in data, "catalog.json missing 'crates' key"
    assert isinstance(data["crates"], list), "catalog.json 'crates' must be a list"


def test_catalog_counts_match_workspace():
    """The catalog must list every crate directory (no more, no less)."""
    data = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
    catalog_count = data.get("count", 0)
    on_disk = len([p for p in CRATES_DIR.iterdir() if (p / "Cargo.toml").is_file()])
    assert catalog_count == on_disk, (
        f"catalog count ({catalog_count}) != crates on disk ({on_disk}); "
        f"run: python3 {GENERATOR}"
    )


def test_catalog_entries_have_name_and_description():
    data = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
    for crate in data["crates"]:
        assert crate.get("name"), f"catalog entry missing name: {crate!r}"
        # description may be empty for some crates, but the key must exist
        assert "description" in crate, f"catalog entry missing description key: {crate!r}"


def test_generator_check_passes():
    """The committed catalog.json must be in sync with the workspace.
    Running the generator with --check must exit 0."""
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"gen-rustdoc-panel-catalog.py --check failed:\n{result.stdout}\n{result.stderr}"
    )


def test_panel_embeds_catalog_loader():
    """The panel HTML must fetch ./catalog.json and render crates."""
    html = PANEL_HTML.read_text(encoding="utf-8")
    assert "catalog.json" in html, "panel must reference catalog.json"
    assert 'id="grid"' in html, "panel must have a #grid render target"
    assert 'id="search"' in html, "panel must have a #search input"


def test_panel_links_to_github_source():
    """Each crate links to the GitHub source tree (SDD-960 repointing)."""
    html = PANEL_HTML.read_text(encoding="utf-8")
    assert "github.com/cyberpunk042/sovereign-os" in html, (
        "panel must link to GitHub source per SDD-960"
    )


def test_panel_has_footer_with_generator_ref():
    html = PANEL_HTML.read_text(encoding="utf-8")
    assert "gen-rustdoc-panel-catalog.py" in html, (
        "panel footer must reference the generator script"
    )
