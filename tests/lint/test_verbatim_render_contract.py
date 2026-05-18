"""R423 (E10.M67) — verbatim-render catalog contract lint (R369 doctrine).

Extends R387-R422 + R381/R382 operational-artifact pinning to:
  scripts/intelligence/verbatim-render.py  (the catalog aggregator)
  docs/src/verbatim-surface.md             (the rendered output)

This script is the CENTRAL aggregator that pulls verbatim phrases from
6 source catalogs:
  - architecture-qa.py (concepts + gotchas + questions)
  - coverage-map.py (axes)
  - ccd-pinning.py (layer catalog)
  - state-fabric.py (state files + ZFS properties)
  - network/topology.py (interfaces + diagram)
  - repl.py (modes)

Operator-discoverable verbs:
  verbatim-render.py render    — emit markdown surface document
  verbatim-render.py summary   — print catalog counts
  verbatim-render.py manifest  — emit operator-runnable verb list

If a future agent silently:
  - drops a source catalog from _gather_catalogs() = items silently
    disappear from the rendered surface; operator loses discoverability
  - changes the CLI subcommand names = sovereign-osctl wrappers break
  - swallows an exception silently (NEVER-raises promise) but doesn't
    fall back to empty data = manifest emits half-rendered output
…the operator-discoverability surface silently shrinks.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RENDER_PY = REPO_ROOT / "scripts" / "intelligence" / "verbatim-render.py"
SURFACE_MD = REPO_ROOT / "docs" / "src" / "verbatim-surface.md"

EXPECTED_SOURCE_MODULES = [
    "architecture-qa.py",
    "coverage-map.py",
    "ccd-pinning.py",
    "state-fabric.py",
    "topology.py",
    "repl.py",
]

EXPECTED_SUBCOMMANDS = ["render", "summary", "manifest"]


def _read(p: Path) -> str:
    assert p.is_file(), f"missing {p}"
    return p.read_text(encoding="utf-8")


# --- Structural ---


def test_verbatim_render_script_exists():
    assert RENDER_PY.is_file(), f"missing {RENDER_PY}"


def test_verbatim_surface_md_exists():
    """The rendered markdown surface MUST exist (committed alongside
    the script; operator-discoverable artifact)."""
    assert SURFACE_MD.is_file(), (
        f"missing {SURFACE_MD} — regenerate via "
        f"`python3 scripts/intelligence/verbatim-render.py render "
        f"> docs/src/verbatim-surface.md`"
    )


# --- Catalog aggregator contract ---


def test_render_references_all_source_modules():
    """6 source catalogs MUST be referenced in _gather_catalogs.
    Drift dropping one = items silently disappear from manifest."""
    body = _read(RENDER_PY)
    for mod in EXPECTED_SOURCE_MODULES:
        assert mod in body, (
            f"verbatim-render.py missing reference to source module "
            f"{mod!r} (operator-discoverable verbatim source set)"
        )


def test_render_loads_architecture_qa_artifacts():
    """architecture-qa.py exports ARCHITECTURE_QUESTIONS,
    ARCHITECTURE_GOTCHAS, ARCHITECTURE_CONCEPTS. All 3 MUST be loaded."""
    body = _read(RENDER_PY)
    for attr in ("ARCHITECTURE_QUESTIONS",
                 "ARCHITECTURE_GOTCHAS",
                 "ARCHITECTURE_CONCEPTS"):
        assert attr in body, (
            f"verbatim-render.py missing reference to {attr} "
            f"(R369 catalog aggregator contract)"
        )


def test_render_loads_coverage_axes():
    body = _read(RENDER_PY)
    assert "DEFAULT_AXES" in body, (
        "verbatim-render.py missing DEFAULT_AXES reference "
        "(coverage-map catalog aggregator)"
    )


def test_render_loads_ccd_layers():
    body = _read(RENDER_PY)
    assert "DEFAULT_LAYER_CATALOG" in body, (
        "verbatim-render.py missing DEFAULT_LAYER_CATALOG reference "
        "(ccd-pinning catalog aggregator)"
    )


def test_render_loads_state_fabric():
    body = _read(RENDER_PY)
    for attr in ("DEFAULT_FILE_MATRIX", "DEFAULT_ZFS_PROPERTIES"):
        assert attr in body, (
            f"verbatim-render.py missing {attr} reference "
            f"(state-fabric catalog aggregator)"
        )


def test_render_loads_network_topology():
    body = _read(RENDER_PY)
    for attr in ("DEFAULT_INTERFACES", "TOPOLOGY_DIAGRAM_VERBATIM"):
        assert attr in body, (
            f"verbatim-render.py missing {attr} reference "
            f"(network/topology catalog aggregator)"
        )


def test_render_loads_repl_modes():
    body = _read(RENDER_PY)
    assert "DEFAULT_MODES" in body, (
        "verbatim-render.py missing DEFAULT_MODES reference "
        "(repl catalog aggregator)"
    )


# --- CLI subcommand contract ---


def test_all_three_subcommands_defined():
    """Subcommands MUST be: render / summary / manifest. Drift
    renaming a subcommand = sovereign-osctl wrappers break."""
    body = _read(RENDER_PY)
    for cmd in EXPECTED_SUBCOMMANDS:
        # The subcommand is added via sub.add_parser(cmd)
        assert f'"{cmd}"' in body or f"'{cmd}'" in body, (
            f"verbatim-render.py missing subcommand {cmd!r}"
        )


def test_render_subcommand_emits_markdown():
    """`render` MUST emit markdown via render_markdown()."""
    body = _read(RENDER_PY)
    assert "render_markdown" in body, (
        "verbatim-render.py missing render_markdown() function "
        "(subcommand 'render' = emit operator-discoverable surface)"
    )


def test_summary_subcommand_emits_counts():
    """`summary` MUST call render_summary() (catalog counts)."""
    body = _read(RENDER_PY)
    assert "render_summary" in body, (
        "verbatim-render.py missing render_summary() function"
    )


def test_manifest_subcommand_emits_verb_list():
    """`manifest` MUST call render_manifest() (operator-runnable verbs)."""
    body = _read(RENDER_PY)
    assert "render_manifest" in body, (
        "verbatim-render.py missing render_manifest() function"
    )


def test_manifest_entries_carry_sovereign_osctl_verbs():
    """Manifest entries MUST point at sovereign-osctl architecture-qa /
    coverage verbs (operator-discovery — clicking a manifest entry =
    runnable command)."""
    body = _read(RENDER_PY)
    assert "sovereign-osctl architecture-qa" in body, (
        "verbatim-render.py manifest missing sovereign-osctl "
        "architecture-qa verb (operator-runnable manifest entries)"
    )
    assert "sovereign-osctl coverage" in body, (
        "verbatim-render.py manifest missing sovereign-osctl coverage "
        "verb (operator-runnable manifest entries)"
    )


# --- Format options ---


def test_json_and_human_output_formats():
    """summary + manifest MUST support both --json and --human formats
    (operator-discoverable: JSON for piping, human for terminal)."""
    body = _read(RENDER_PY)
    assert "--json" in body and "--human" in body, (
        "verbatim-render.py missing --json/--human format flags"
    )


def test_argparse_used():
    """CLI built on argparse (operator-discoverable: -h works)."""
    body = _read(RENDER_PY)
    assert "argparse" in body, (
        "verbatim-render.py not using argparse (drift breaks -h surface)"
    )


# --- Never-raises promise ---


def test_gather_catalogs_documents_never_raises():
    """_gather_catalogs() comment says 'NEVER-raises'. The promise is
    that missing source modules return empty data, not exceptions.
    Operator-discoverable: partial catalog = partial render, not crash."""
    body = _read(RENDER_PY)
    assert "NEVER-raises" in body or "never raises" in body.lower(), (
        "verbatim-render.py _gather_catalogs() missing NEVER-raises "
        "promise (drift = missing module crashes the whole render)"
    )


def test_getattr_with_default_for_each_module():
    """The aggregator MUST use getattr(module, ATTR, default) so a
    missing attribute returns empty data instead of AttributeError."""
    body = _read(RENDER_PY)
    # Look for getattr(... , [], ...) patterns
    has_getattr_default = re.search(r"getattr\([^,]+,\s*\"[A-Z_]+\",\s*\[\]\)", body)
    assert has_getattr_default, (
        "verbatim-render.py missing getattr(mod, ATTR, []) defaults "
        "(drift = AttributeError crashes render on missing catalog)"
    )


# --- Schema-version pinning ---


def test_schema_version_constant_defined():
    """SCHEMA_VERSION constant MUST be defined (consumer tools key off it)."""
    body = _read(RENDER_PY)
    assert "SCHEMA_VERSION" in body, (
        "verbatim-render.py missing SCHEMA_VERSION constant "
        "(consumer tools depend on it for compatibility checks)"
    )


def test_round_constant_defined():
    """ROUND constant tracks which R-arc round produced this version
    of the rendered catalog (operator-discovery: which round's state
    is this surface)."""
    body = _read(RENDER_PY)
    assert "ROUND" in body, (
        "verbatim-render.py missing ROUND constant (R-arc traceability)"
    )


# --- Bidirectional consistency: rendered output exists + non-empty ---


def test_surface_md_non_empty():
    """The rendered surface MUST be non-trivial (drift to empty file =
    regenerator silently broke + nobody noticed)."""
    text = _read(SURFACE_MD)
    assert len(text) > 1000, (
        f"docs/src/verbatim-surface.md is too small ({len(text)} chars); "
        f"regenerator may be broken; rerun "
        f"`python3 scripts/intelligence/verbatim-render.py render`"
    )


def test_surface_md_references_master_spec():
    """Rendered surface SHOULD reference master spec sections
    (operator-discoverable: which spec section each verbatim item
    binds to)."""
    text = _read(SURFACE_MD)
    has_spec_ref = "§" in text or "Master spec" in text or "master spec" in text
    assert has_spec_ref, (
        "docs/src/verbatim-surface.md missing master spec § references "
        "(rendered surface lost operator-discovery context)"
    )
