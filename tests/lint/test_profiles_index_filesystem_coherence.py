"""profiles/INDEX.md ↔ filesystem coherence — the profile catalog
discoverability contract.

profiles/INDEX.md is the catalog entry-point for the OS profile set.
Per its own preamble: "Catalog of declared OS profiles. Each profile
MUST validate against ../schemas/profile.schema.yaml". The contract is
bidirectional:

  1. Every profile YAML referenced from INDEX.md must exist on disk
     (else operators click a row, hit 404 / dead link).
  2. Every active profile YAML in profiles/*.yaml must be listed in
     INDEX.md (else operators following the canonical catalog
     entry-point miss the profile).

Schema-conformance is already gated by tests/schema/test_profile_schema_
conformance.py — this test pins the discoverability contract on top.

Pure text-shape assertions (no schema engine, no YAML parsing — just
grep + filesystem checks).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILES_DIR = REPO_ROOT / "profiles"
INDEX = PROFILES_DIR / "INDEX.md"

# Markdown link form expected in the catalog: [`<id>`](<id>.yaml)
INDEX_LINK_RE = re.compile(r"\[`([a-z][a-z0-9-]*)`\]\(([a-z][a-z0-9-]*\.yaml)\)")

# Mixins/runtime live in subdirs and are NOT top-level profiles —
# don't expect them in INDEX.md.
EXEMPT_SUBDIRS = {"mixins", "runtime"}


def _index_referenced_profile_ids() -> set[str]:
    """Pull every `[<id>](<id>.yaml)` link from INDEX.md."""
    if not INDEX.is_file():
        return set()
    text = INDEX.read_text(encoding="utf-8")
    return {m.group(1) for m in INDEX_LINK_RE.finditer(text)}


def _filesystem_profile_ids() -> set[str]:
    """Every top-level <stem>.yaml under profiles/ (excluding subdirs
    like mixins/ and runtime/ — those are mixin libraries, not
    top-level profiles)."""
    if not PROFILES_DIR.is_dir():
        return set()
    ids: set[str] = set()
    for entry in PROFILES_DIR.iterdir():
        if entry.is_dir() and entry.name in EXEMPT_SUBDIRS:
            continue
        if entry.is_file() and entry.suffix == ".yaml":
            ids.add(entry.stem)
    return ids


def test_profiles_index_exists():
    """The catalog entry-point file is present."""
    assert INDEX.is_file(), f"profiles/INDEX.md not found at {INDEX}"


def test_every_index_link_resolves():
    """Every `[<id>](<id>.yaml)` link in INDEX.md must point at a real
    on-disk YAML file (else operators clicking the link hit 404)."""
    text = INDEX.read_text(encoding="utf-8")
    missing: list[str] = []
    for match in INDEX_LINK_RE.finditer(text):
        link_path = match.group(2)
        if not (PROFILES_DIR / link_path).is_file():
            missing.append(link_path)
    assert not missing, (
        f"profiles/INDEX.md references profile YAMLs that do not exist "
        f"on disk: {missing}"
    )


def test_every_filesystem_profile_listed_in_index():
    """Every top-level profile YAML on disk must have an INDEX.md row
    (else operators using the catalog entry-point cannot discover the
    profile)."""
    referenced = _index_referenced_profile_ids()
    on_disk = _filesystem_profile_ids()
    orphans = on_disk - referenced
    assert not orphans, (
        f"profile YAMLs on disk but NOT listed in profiles/INDEX.md "
        f"(operator can't discover via catalog entry-point): "
        f"{sorted(orphans)}"
    )


def test_index_carries_schema_pointer():
    """INDEX.md's preamble must continue to point at the profile
    schema (else operators can't validate profiles independently)."""
    text = INDEX.read_text(encoding="utf-8")
    assert "profile.schema.yaml" in text, (
        "profiles/INDEX.md does not reference the profile schema "
        "(schema-conformance entry-point lost)"
    )


def test_at_least_the_known_seed_profiles_present():
    """SDD-005 documents the initial profile seed set (sain-01,
    old-workstation, minimal, developer, headless). All five must
    remain referenced from INDEX.md and present on disk — silent
    deletion of a seed profile would break the documented baseline."""
    referenced = _index_referenced_profile_ids()
    on_disk = _filesystem_profile_ids()
    for seed in ("sain-01", "old-workstation", "minimal", "developer", "headless"):
        assert seed in referenced, (
            f"seed profile {seed!r} missing from INDEX.md "
            f"(SDD-005 baseline broken)"
        )
        assert seed in on_disk, (
            f"seed profile {seed}.yaml missing from filesystem "
            f"(SDD-005 baseline broken)"
        )
