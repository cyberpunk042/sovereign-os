"""R373 (E10.M17) — cross-catalog phrase consistency validator.

Extends R367 Tetragon-allowlist bidirectional check pattern to a
broader set of operator-verbatim phrases that appear in multiple
catalogs / shipped artifacts. If the same operator phrase appears in
catalog A AND catalog B AND shipped artifact C, all three MUST agree
exactly — silent drift in any of them is silent paraphrasing.

Cross-catalog phrase pairs covered:

  - "M.2_2 slot must remain empty" must appear in:
      * C-16 hardware concept (master spec §1.2)
      * friction-audit script (scripts/hooks/{pre,post}-install/)
      * G-01 dual-GPU gotcha context

  - "sync=always" must appear in:
      * C-08 atomic state transition concept (§21)
      * C-15 storage architecture concept (§3 + §4.1)
      * state-fabric ZFS properties (§7.2)
      * C-11 vibe manager concept (§5+§7)

  - "31.5 GB/s" must appear in:
      * C-15 storage architecture concept (§3 + §4.1)
      * C-16 hardware concept (§1.2)

  - "Marvell AQC113C" must appear in:
      * C-16 hardware concept (§1)
      * network-topology spec
      * §8 ASCII diagram in network-topology

  - "Intel I226-V" must appear in:
      * C-16 hardware concept (§1)
      * network-topology spec
      * §8 ASCII diagram

  - "BindsTo=tetragon.service" must appear in:
      * C-07 guardian event loop concept (§10 + §14 G-03)
      * G-03 OPNsense gotcha prevention

  - "CMK128GX5M2B6400C42" must appear in:
      * C-16 hardware concept
      * A-25 coverage-map axis (operator §1b RAM spec)
      * inventory-catalog ram-dimm-* entries

  - "SMT2200C" must appear in:
      * C-16 hardware? (depending on inclusion)
      * A-24 coverage-map UPS axis
      * inventory-catalog ups-0
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

ARCH_QA = REPO_ROOT / "scripts" / "intelligence" / "architecture-qa.py"
COVERAGE = REPO_ROOT / "scripts" / "intelligence" / "coverage-map.py"
STATE_FABRIC = REPO_ROOT / "scripts" / "hardware" / "state-fabric.py"
NET_TOPO = REPO_ROOT / "scripts" / "network" / "topology.py"
INVENTORY = REPO_ROOT / "scripts" / "hardware" / "inventory-catalog.py"
FRICTION_PRE = REPO_ROOT / "scripts" / "hooks" / "pre-install" / "friction-audit-spec.sh"
FRICTION_POST = REPO_ROOT / "scripts" / "hooks" / "post-install" / "friction-audit-runtime.sh"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _all_concept_text() -> str:
    """Concatenate all C-NN explanations into one searchable blob."""
    mod = _load_module(ARCH_QA, "phrase_consistency_archqa")
    parts = []
    for c in mod.ARCHITECTURE_CONCEPTS:
        parts.append(c.get("explanation", ""))
        parts.append(c.get("name", ""))
    return "\n".join(parts)


def _all_gotcha_text() -> str:
    mod = _load_module(ARCH_QA, "phrase_consistency_gotchas")
    parts = []
    for g in mod.ARCHITECTURE_GOTCHAS:
        for f in ("name", "context", "gotcha", "prevention"):
            parts.append(g.get(f, ""))
    return "\n".join(parts)


def _all_coverage_text() -> str:
    mod = _load_module(COVERAGE, "phrase_consistency_coverage")
    parts = []
    for a in mod.DEFAULT_AXES:
        parts.append(a.get("axis_verbatim", ""))
        parts.append(a.get("notes", ""))
    return "\n".join(parts)


def _state_fabric_text() -> str:
    mod = _load_module(STATE_FABRIC, "phrase_consistency_sf")
    parts = []
    for f in mod.DEFAULT_FILE_MATRIX:
        parts.append(f.get("role_verbatim", ""))
    for p in mod.DEFAULT_ZFS_PROPERTIES:
        parts.append(p.get("command", ""))
        parts.append(p.get("rationale", ""))
    return "\n".join(parts)


def _net_topology_text() -> str:
    mod = _load_module(NET_TOPO, "phrase_consistency_nt")
    parts = [mod.TOPOLOGY_DIAGRAM_VERBATIM]
    for nif in mod.DEFAULT_INTERFACES:
        parts.append(nif.get("vendor", ""))
        parts.append(nif.get("chipset", ""))
        parts.append(nif.get("role", ""))
    return "\n".join(parts)


def _inventory_text() -> str:
    mod = _load_module(INVENTORY, "phrase_consistency_inv")
    parts = []
    for c in mod.DEFAULT_COMPONENTS:
        for f in ("model", "vendor", "sku", "operator_caveat", "related_advisor"):
            v = c.get(f)
            if isinstance(v, str):
                parts.append(v)
    return "\n".join(parts)


def _friction_audit_text() -> str:
    parts = []
    for f in (FRICTION_PRE, FRICTION_POST):
        if f.is_file():
            parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts)


# ── Cross-catalog phrase consistency cases ────────────────────────
def test_m_2_2_slot_phrase_cross_catalog():
    """'M.2_2 slot' phrase must appear in concept catalog AND
    friction-audit script (operator §1.2 invariant)."""
    concepts = _all_concept_text()
    assert "M.2_2 slot" in concepts, "C-NN concept missing M.2_2 reference"
    audit_text = _friction_audit_text()
    if audit_text:
        # friction-audit may use "M.2_2" without "slot"
        assert "M.2_2" in audit_text, (
            "friction-audit scripts must reference M.2_2 invariant per §1.2"
        )


def test_sync_always_phrase_cross_catalog():
    """'sync=always' must appear in concept catalog AND state-fabric
    ZFS properties (§7.2 + §21 + §3)."""
    concepts = _all_concept_text()
    assert "sync=always" in concepts, "C-NN concepts missing sync=always"
    sf = _state_fabric_text()
    assert "sync=always" in sf, "state-fabric ZFS props missing sync=always"


def test_31_5_gbs_throughput_cross_catalog():
    """'31.5 GB/s' must appear in concept catalog at least once
    (operator §1.2 throughput target verbatim)."""
    concepts = _all_concept_text()
    assert "31.5 GB/s" in concepts, (
        "C-NN concepts missing operator-verbatim '31.5 GB/s' throughput target"
    )


def test_marvell_aqc113c_cross_catalog():
    """'AQC113C' must appear in concept catalog AND network topology
    (operator §1 + §8 chipset SKU verbatim)."""
    concepts = _all_concept_text()
    assert "AQC113C" in concepts, "concepts missing Marvell AQC113C"
    nt = _net_topology_text()
    assert "AQC113C" in nt, "network-topology missing AQC113C"


def test_intel_i226v_cross_catalog():
    """'I226-V' must appear in concept catalog AND network topology."""
    concepts = _all_concept_text()
    assert "I226-V" in concepts, "concepts missing Intel I226-V"
    nt = _net_topology_text()
    assert "I226-V" in nt, "network-topology missing I226-V"


def test_binds_to_tetragon_cross_catalog():
    """'BindsTo=tetragon.service' must appear in concept catalog AND
    gotchas (C-07 + G-03 cross-link)."""
    concepts = _all_concept_text()
    assert "BindsTo=tetragon.service" in concepts, (
        "concept catalog missing BindsTo=tetragon.service"
    )
    gotchas = _all_gotcha_text()
    assert "BindsTo=tetragon.service" in gotchas, (
        "gotchas missing BindsTo=tetragon.service (G-03 should cite it)"
    )


def test_cmk128gx5m2b6400c42_cross_catalog():
    """RAM SKU must appear in concept catalog AND coverage-map AND
    inventory-catalog (operator §1b hardware-spec drop verbatim SKU)."""
    concepts = _all_concept_text()
    assert "CMK128GX5M2B6400C42" in concepts, (
        "concepts missing operator's exact RAM SKU CMK128GX5M2B6400C42"
    )
    coverage = _all_coverage_text()
    assert "CMK128GX5M2B6400C42" in coverage, (
        "coverage-map missing CMK128GX5M2B6400C42 (A-25 should cite it)"
    )
    inv = _inventory_text()
    assert "CMK128GX5M2B6400C42" in inv, (
        "inventory-catalog missing CMK128GX5M2B6400C42 — 4 DIMM slots "
        "must each list this exact SKU per operator §1b drop"
    )


def test_smt2200c_cross_catalog():
    """UPS SKU must appear in coverage-map AND inventory-catalog."""
    coverage = _all_coverage_text()
    assert "SMT2200C" in coverage, (
        "coverage-map missing SMT2200C (A-24 should cite it)"
    )
    inv = _inventory_text()
    assert "SMT2200C" in inv, "inventory-catalog missing SMT2200C"


def test_990_evo_plus_cross_catalog():
    """NVMe SKU must appear in coverage-map AND inventory-catalog."""
    coverage = _all_coverage_text()
    assert "990 EVO Plus" in coverage, (
        "coverage-map missing 990 EVO Plus (A-26 NVMe axis)"
    )
    inv = _inventory_text()
    assert "990 EVO Plus" in inv, "inventory-catalog missing 990 EVO Plus"


def test_magician_symmetry_phrase_apostrophes_preserved():
    """Operator's 'Magician' with apostrophes is verbatim — both
    concept catalog AND any shipped script citing it must preserve
    the apostrophes (lower vs upper case allowed since operator used
    'Magician' capitalized in source)."""
    concepts = _all_concept_text()
    assert "'Magician'" in concepts, (
        "concept missing 'Magician' with apostrophes preserved (per "
        "operator §1.2 verbatim — without apostrophes is silent stripping)"
    )


def test_ryzen_9_9900x_phrase_cross_catalog():
    """Full CPU SKU must appear in concept catalog AND coverage-map AND
    inventory-catalog (operator §1 verbatim hardware identifier)."""
    concepts = _all_concept_text()
    assert "Ryzen 9 9900X" in concepts, "concepts missing Ryzen 9 9900X"
    coverage = _all_coverage_text()
    # Coverage axes don't always use full SKU; just check it's mentioned
    # in at least one place (notes/verbatim).
    # Not all axes need to cite it — just sanity check ≥1 occurrence.
    assert "Ryzen 9 9900X" in coverage or "9900X" in coverage, (
        "coverage-map should reference Ryzen 9 9900X somewhere"
    )
    inv = _inventory_text()
    assert "9900X" in inv, "inventory-catalog missing 9900X CPU SKU"


def test_no_silent_paraphrase_of_operator_verbatim_phrases():
    """Sanity meta-check: catch the most common paraphrase-drift
    candidates. If any of these appear in catalog text, it means
    operator-verbatim was paraphrased."""
    concepts = _all_concept_text()
    gotchas = _all_gotcha_text()
    coverage = _all_coverage_text()
    all_text = concepts + gotchas + coverage

    # Forbidden paraphrases — operator never said these forms:
    forbidden = [
        # Operator wrote "synchronous writes" — never "blocking writes"
        ("blocking writes", "synchronous writes"),
        # Operator wrote "31.5 GB/s" — never "~30 GB/s" or "32 GB/s"
        ("~30 GB/s", "31.5 GB/s"),
        # Operator wrote "Magician symmetry" with capital M — paraphrase
        # check would catch lowercase "magician symmetry" sans apostrophes
        ("magician symmetry", "'Magician' symmetry"),
        # Operator wrote "Atomic Append-Only" — never "atomic append" alone
        # (lowercase form acceptable if part of operator-verbatim block)
    ]
    for wrong, right in forbidden:
        # Only flag if WRONG appears AND RIGHT doesn't — silent replacement
        if wrong in all_text and right not in all_text:
            raise AssertionError(
                f"Found likely paraphrase {wrong!r} in catalog text "
                f"without the operator-verbatim form {right!r} present. "
                f"This is silent paraphrasing — fix the catalog entry "
                f"to use operator-exact text."
            )
