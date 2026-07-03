"""Dashboard-catalog completeness + description lockstep.

config/dashboard-catalog.yaml is the single source of truth the global
index (/panels) renders — every webapp/<panel>/ dir MUST have a described
entry, every entry MUST carry a real description, and every category
referenced MUST exist. This keeps the operator's global view honest: no
panel ships without an explanation, and no described panel points at a
dir that isn't there.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG = REPO_ROOT / "config" / "dashboard-catalog.yaml"
WEBAPP = REPO_ROOT / "webapp"


def _catalog() -> dict:
    return yaml.safe_load(CATALOG.read_text())


def _panel_dirs() -> set[str]:
    return {p.name for p in WEBAPP.iterdir()
            if (p / "index.html").is_file() and not p.name.startswith("_")}


def test_catalog_present_and_parses():
    assert CATALOG.is_file(), f"missing {CATALOG}"
    c = _catalog()
    assert c.get("dashboards"), "catalog has no dashboards"
    assert c.get("categories"), "catalog has no categories"


def test_every_panel_dir_has_a_catalog_entry():
    """No webapp panel ships without a described catalog entry."""
    slugs = {d["slug"] for d in _catalog()["dashboards"]}
    missing = sorted(_panel_dirs() - slugs)
    assert not missing, (
        f"webapp panels with NO dashboard-catalog entry (add one with a "
        f"description): {missing}"
    )


def test_every_paneled_entry_points_at_a_real_dir():
    """An entry with a path must correspond to a real webapp dir."""
    dirs = _panel_dirs()
    bad = [d["slug"] for d in _catalog()["dashboards"]
           if d.get("path") and d["slug"] not in dirs]
    assert not bad, f"catalog entries with a path but no webapp/<slug>/ dir: {bad}"


def test_every_entry_has_a_substantive_description():
    for d in _catalog()["dashboards"]:
        desc = (d.get("description") or "").strip()
        assert len(desc) >= 30, (
            f"catalog entry {d['slug']!r} description too short/absent "
            f"(every surface needs a real explanation): {desc!r}"
        )


def test_categories_are_defined_and_used():
    cat = _catalog()
    defined = {c["id"] for c in cat["categories"]}
    used = {d["category"] for d in cat["dashboards"]}
    unknown = sorted(used - defined)
    assert not unknown, f"dashboards reference undefined categories: {unknown}"
    for c in cat["categories"]:
        assert (c.get("label") and c.get("blurb")), f"category {c['id']} needs label+blurb"


def test_un_paneled_domains_carry_cli_access():
    """A 'planned' (no-panel-yet) entry MUST tell the operator how to reach
    the feature TODAY (its CLI/API), so nothing is a dead reference."""
    for d in _catalog()["dashboards"]:
        if d.get("status") == "planned":
            assert d.get("cli"), (
                f"planned surface {d['slug']!r} has no `cli:` — the operator "
                f"needs a way to reach it now"
            )
