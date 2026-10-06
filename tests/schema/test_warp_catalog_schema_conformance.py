"""Layer 1 — warp-catalog YAML schema conformance (SDD-300 Warp management panel).

`config/warp-catalog.yaml` MUST validate against
`schemas/warp-catalog.schema.yaml`. The catalog is a GENERATED snapshot of the
warp-solar-system-shaders project (scenes + libs + the scene→lib / lib→lib
relation graph) that the Warp management panel surfaces. It is the committed
CI-safe source of truth; a resident checkout (canonical home
/opt/warp-solar-system-shaders via `warp sync`, SDD-303) supplies execution and
the freshness marker `source_git_rev` compared against the checkout HEAD.

Beyond raw schema validation this pins the invariants the panel + exec-rail
rely on: counts match the arrays, scene→lib edges reference declared libs, and
the runner ids cover the executable surface (render/bench).
"""

from __future__ import annotations

import pathlib

import pytest

try:
    import yaml
except ImportError:
    pytest.skip("python3-yaml not installed", allow_module_level=True)

try:
    import jsonschema
except ImportError:
    pytest.skip("python3-jsonschema not installed", allow_module_level=True)


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
CATALOG_FILE = REPO_ROOT / "config" / "warp-catalog.yaml"
SCHEMA_FILE = REPO_ROOT / "schemas" / "warp-catalog.schema.yaml"


def _load_yaml(path: pathlib.Path):
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _catalog():
    return _load_yaml(CATALOG_FILE)["catalog"]


def test_schema_file_present():
    assert SCHEMA_FILE.exists(), f"schema missing: {SCHEMA_FILE}"


def test_catalog_file_present():
    assert CATALOG_FILE.exists(), f"catalog missing: {CATALOG_FILE}"


def test_catalog_validates_against_schema():
    schema = _load_yaml(SCHEMA_FILE)
    doc = _load_yaml(CATALOG_FILE)
    jsonschema.validate(instance=doc, schema=schema)


def test_freshness_marker_present():
    """SDD-303: the committed catalog carries the 40-hex rev it was generated
    from — the marker `warp status` compares against the checkout HEAD."""
    import re
    cat = _catalog()
    rev = cat.get("source_git_rev")
    assert rev and re.fullmatch(r"[0-9a-f]{40}", rev), \
        "regenerate with gen_catalog.py from a git checkout (freshness marker missing)"


def test_counts_match_arrays():
    cat = _catalog()
    assert cat["counts"]["scenes"] == len(cat["scenes"]), "scene count drift"
    assert cat["counts"]["libs"] == len(cat["libs"]), "lib count drift"


def test_scene_lib_edges_reference_declared_libs():
    """Every scene→lib edge must point at a lib declared in libs[] — otherwise
    the panel's relation graph would draw dangling edges."""
    cat = _catalog()
    declared = {lib["id"] for lib in cat["libs"]}
    for scene in cat["scenes"]:
        unknown = set(scene["libs"]) - declared
        assert not unknown, (
            f"scene {scene['name']!r} references undeclared libs {sorted(unknown)}")


def test_lib_depends_on_reference_declared_libs():
    cat = _catalog()
    declared = {lib["id"] for lib in cat["libs"]}
    for lib in cat["libs"]:
        unknown = set(lib["depends_on"]) - declared
        assert not unknown, (
            f"lib {lib['id']!r} depends_on undeclared libs {sorted(unknown)}")


def test_scene_names_unique():
    cat = _catalog()
    names = [s["name"] for s in cat["scenes"]]
    dupes = sorted({n for n in names if names.count(n) > 1})
    assert not dupes, f"duplicate scene names: {dupes}"


def test_runners_cover_executable_surface():
    """The exec-rail wires render + bench; both must be declared runners."""
    cat = _catalog()
    ids = {r["id"] for r in cat["runners"]}
    assert {"render", "bench"} <= ids, f"missing executable runners: {ids}"
