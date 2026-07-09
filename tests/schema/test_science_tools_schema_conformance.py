"""Layer 1 — science-tools catalog YAML schema conformance.

`config/science-tools.yaml` MUST validate against
`schemas/science-tools.schema.yaml`. The catalog materialises the operator's
"scientific / merge / specialist catalog" (Image 2, 2026-07-02 verbatim note) —
non-LLM domain compute tools (DNA / protein / particles). NVIDIA Warp
(`warp-lang`) is the first integrated tool; the rest are cataloged.
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
CATALOG_FILE = REPO_ROOT / "config" / "science-tools.yaml"
SCHEMA_FILE = REPO_ROOT / "schemas" / "science-tools.schema.yaml"

DOMAINS = {"dna", "protein", "particles"}


def _load_yaml(path: pathlib.Path):
    with path.open() as f:
        return yaml.safe_load(f)


def _tools():
    return _load_yaml(CATALOG_FILE)["catalog"]["tools"]


def test_schema_file_present():
    assert SCHEMA_FILE.exists(), f"schema missing: {SCHEMA_FILE}"


def test_catalog_file_present():
    assert CATALOG_FILE.exists(), f"catalog missing: {CATALOG_FILE}"


def test_catalog_validates_against_schema():
    schema = _load_yaml(SCHEMA_FILE)
    catalog = _load_yaml(CATALOG_FILE)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(catalog), key=lambda e: list(e.path))
    assert not errors, "\n".join(
        f"{list(e.path)}: {e.message}" for e in errors
    )


def test_tool_ids_are_unique():
    ids = [t["id"] for t in _tools()]
    dupes = {i for i in ids if ids.count(i) > 1}
    assert not dupes, f"duplicate tool ids: {dupes}"


def test_every_tool_declares_install_method_and_ref():
    """The catalog's whole point is to say HOW each tool is obtained."""
    bad = [
        t["id"]
        for t in _tools()
        if not (t.get("install") or {}).get("method")
        or not (t.get("install") or {}).get("ref")
    ]
    assert not bad, f"tools missing install.method/ref: {bad}"


def test_all_three_domains_present():
    """DNA + protein + particles — the operator's Image-2 grouping — must all
    be represented so the science surface stays honest."""
    domains = {t["domain"] for t in _tools()}
    assert DOMAINS <= domains, f"missing science domains: {DOMAINS - domains}"


def test_exactly_one_integrated_tool_is_warp():
    """This round integrates NVIDIA Warp and nothing else — pin that so a
    future edit can't silently claim another tool is shipped without a runner."""
    integrated = [t["id"] for t in _tools() if t["status"] == "integrated"]
    assert integrated == ["warp-lang"], (
        f"expected exactly one integrated tool (warp-lang), got {integrated}"
    )


def test_integrated_tool_is_cpu_capable():
    """An integrated tool must run on the GPU-less dev/test box (CPU fallback),
    otherwise it can't be verified off SAIN-01. (Schema enforces; this is the
    operator-readable cross-check.)"""
    for t in _tools():
        if t["status"] == "integrated":
            assert t["cpu_capable"] is True, (
                f"integrated tool {t['id']} must be cpu_capable"
            )


def test_warp_is_particles_python_cuda_library_via_pip():
    warp = next((t for t in _tools() if t["id"] == "warp-lang"), None)
    assert warp is not None, "warp-lang missing from the science-tools catalog"
    assert warp["domain"] == "particles"
    assert warp["kind"] == "python-cuda-library"
    assert warp["install"]["method"] == "pip"
    assert warp["install"]["ref"] == "warp-lang"


def test_cataloged_tools_declare_provenance():
    """A cataloged (not-yet-integrated) tool must point the operator at its
    real source so it's never a dead-end."""
    bad = [
        t["id"]
        for t in _tools()
        if t["status"] == "cataloged" and not t.get("source")
    ]
    assert not bad, f"cataloged tools missing source provenance: {bad}"
