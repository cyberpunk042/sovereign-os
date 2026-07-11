"""App-shell ⌘K palette + sidebar coverage guard (SDD-136).

The ⌘K command palette (`CMDK`) and the left sidebar (`buildSidemenu`) are BOTH
built from the same `GROUPS` catalog in webapp/_shared/app-shell-snippet.html.
Coverage is complete today — every webapp panel is in GROUPS, reachable by slug
(`cmdkFilter` matches id/label/dir/grp) — but nothing ENFORCED that invariant:

  - test_app_shell_contract.py checks only the D-00..D-25 *id strings* (not the
    27 slug panels, not the dir set);
  - ADOPTED_APP_SHELL_PANELS is a hand-maintained list, not derived from disk;
  - test_dashboard_catalog_complete.py locks disk ⊆ dashboard-catalog.yaml (a
    *different* catalog);
  - test_cross_panel_links_resolve.py (SDD-135) locks GROUPS→disk (real), not
    disk→GROUPS (complete).

So a new panel added on disk with a non-D `id` could ship ABSENT from GROUPS —
invisible in both the palette and the sidebar — while every existing lint stays
green. This guard closes that hole: the GROUPS `dir` set must be a bijection with
the on-disk panels, and the byte-identical embed list must equal disk too.
"""
from __future__ import annotations

import re
from pathlib import Path

from tests.lint.test_app_shell_contract import ADOPTED_APP_SHELL_PANELS, BEGIN, END

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBAPP = REPO_ROOT / "webapp"
SHARED = WEBAPP / "_shared" / "app-shell-snippet.html"

_BLOCK_RE = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL)


def _panel_dirs() -> set[str]:
    # mirrors tests/lint/test_dashboard_catalog_complete.py::_panel_dirs
    return {p.name for p in WEBAPP.iterdir()
            if (p / "index.html").is_file() and not p.name.startswith("_")}


def _groups_block() -> str:
    src = SHARED.read_text(encoding="utf-8")
    m = _BLOCK_RE.search(src)
    assert m, f"canonical app-shell block markers missing in {SHARED}"
    return m.group(0)


def _groups_entries() -> list[tuple[str, str]]:
    """(id, dir) for every GROUPS catalog item, parsed from the shared block."""
    block = _groups_block()
    return re.findall(r"\{id:'([^']*)',\s*dir:'([^']+)'", block)


def _group_dirs() -> set[str]:
    return {d for _id, d in _groups_entries()}


def test_palette_catalog_is_a_bijection_with_disk_panels():
    """GROUPS (⌘K palette + sidebar source) must list EXACTLY the on-disk
    panels — no more, no less. A disk panel missing here is invisible in both
    the palette and the sidebar; a GROUPS dir with no panel is a dead nav row."""
    groups = _group_dirs()
    disk = _panel_dirs()
    missing_from_groups = sorted(disk - groups)
    dead_in_groups = sorted(groups - disk)
    assert not missing_from_groups, (
        "panels on disk but NOT in the app-shell GROUPS catalog — they'd be "
        f"unreachable from the ⌘K palette AND the sidebar (add them to GROUPS): {missing_from_groups}"
    )
    assert not dead_in_groups, (
        f"GROUPS catalog dirs with no webapp/<slug>/ panel (dead nav rows): {dead_in_groups}"
    )


def test_every_group_entry_is_reachable_by_a_typeable_token():
    """cmdkFilter matches id/label/dir/grp, so a non-empty `dir` (the slug) makes
    every panel reachable — including the 27 `id:'—'` panels with no D-number."""
    bad = [d for _id, d in _groups_entries() if not d.strip()]
    assert not bad, f"GROUPS entries with an empty dir (unreachable by slug): {bad}"


def test_adopted_embed_list_equals_disk_panels():
    """The byte-identical app-shell embed contract (test_app_shell_contract.py)
    checks only ADOPTED_APP_SHELL_PANELS. If that list drifts from disk, a new
    panel could ship without the shared chrome (no palette/sidebar/assistant) and
    the embed test would never notice. Pin ADOPTED == disk."""
    adopted = set(ADOPTED_APP_SHELL_PANELS)
    disk = _panel_dirs()
    not_adopted = sorted(disk - adopted)
    not_on_disk = sorted(adopted - disk)
    assert not not_adopted, (
        "disk panels missing from ADOPTED_APP_SHELL_PANELS — the embed contract "
        f"skips them (add them + re-run sync-app-shell.py --apply): {not_adopted}"
    )
    assert not not_on_disk, (
        f"ADOPTED_APP_SHELL_PANELS entries with no webapp/<slug>/ dir: {not_on_disk}"
    )
