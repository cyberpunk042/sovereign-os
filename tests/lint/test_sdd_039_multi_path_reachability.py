"""R549 (E5++) — SDD-039 multi-path reachability lint.

SDD-039 codifies the operator §1g 8-surface delivery contract — a
load-bearing architectural doctrine spanning the R453-R547
implementation lattice. Per the SDD's own R456-anchored STANDING
RULE verbatim (sacrosanct):

  "If you think something is really already done, ask yourself if
   you covered all angles and levels and layers and even if then
   improve it. Do not minimize or settle for less."

A SINGLE reachability path (mandate citation, the R548 closure)
is NOT enough — defense-in-depth requires SDD-039 to be reachable
via MULTIPLE catalog paths so operators arriving from different
discovery surfaces (architecture-qa concepts / coverage-map axes /
mandate rows / SDD INDEX) ALL converge on the same doctrine.

R549 wires SDD-039 into:
  (a) architecture-qa.py concept C-28 — operator-facing concept
      with verbatim R453 anchor + R456 STANDING RULE quote
  (b) coverage-map.py axis A-33 — operator-pull axis with verbatim
      R453 phrase + implementing_verbs across 9 sovereign-osctl
      surfaces + sdd_refs ['037', '038', '039']
  (c) mandate row E10.M110 — already wired in R548

This lint pins the multi-path reachability so a future "tidy-up"
pass can't silently drop the catalog wiring on either side.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCH_QA = REPO_ROOT / "scripts" / "intelligence" / "architecture-qa.py"
COVERAGE = REPO_ROOT / "scripts" / "intelligence" / "coverage-map.py"
MANDATE = (REPO_ROOT / "docs" / "standing-directives"
           / "2026-05-17-operator-mandate.md")


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _archqa():
    return _load_module(ARCH_QA, "r549_archqa")


def _coverage():
    return _load_module(COVERAGE, "r549_coverage")


def test_architecture_qa_has_c28_concept():
    """architecture-qa must carry a C-28 concept anchoring SDD-039."""
    mod = _archqa()
    ids = [c.get("id") for c in mod.ARCHITECTURE_CONCEPTS]
    assert "C-28" in ids, (
        f"architecture-qa.py must carry concept C-28 "
        f"(SDD-039 / §1g 8-surface delivery contract); got ids {ids}"
    )


def test_c28_cites_sdd_039_and_r548():
    """The C-28 concept must cite SDD-039 and R548 explicitly so the
    SDD reachability scanner (regex SDD[- ](\\d{3}) over spec_ref +
    explanation + notes fields) sees the reference."""
    mod = _archqa()
    c28 = next(
        c for c in mod.ARCHITECTURE_CONCEPTS if c.get("id") == "C-28"
    )
    blob = " ".join(
        str(c28.get(k, "")) for k in (
            "name", "explanation", "spec_ref", "tags",
        )
    )
    assert "SDD-039" in blob, (
        f"C-28 must cite SDD-039 in name/explanation/spec_ref/tags"
    )
    assert "R548" in blob, "C-28 must cite R548"


def test_c28_quotes_r453_verbatim_anchor():
    """C-28 must preserve the R453 operator §1g 8-surface verbatim
    anchor — sacrosanct, no paraphrase tolerated."""
    mod = _archqa()
    c28 = next(
        c for c in mod.ARCHITECTURE_CONCEPTS if c.get("id") == "C-28"
    )
    expl = c28.get("explanation", "")
    anchor = (
        "everything is not just core, not just cli, not just TUI, "
        "not just API, not just tool and MCP but also Dashboards "
        "and Web Apps and Services"
    )
    assert anchor in expl, (
        "C-28 must quote the R453 operator §1g 8-surface anchor "
        "VERBATIM (no paraphrase)"
    )


def test_c28_quotes_r456_standing_rule_verbatim():
    """C-28 must preserve the R456 STANDING RULE verbatim."""
    mod = _archqa()
    c28 = next(
        c for c in mod.ARCHITECTURE_CONCEPTS if c.get("id") == "C-28"
    )
    expl = c28.get("explanation", "")
    rule = (
        "If you think something is really already done, ask "
        "yourself if you covered all angles and levels and "
        "layers and even if then improve it. Do not minimize or "
        "settle for less."
    )
    assert rule in expl, (
        "C-28 must quote the R456 operator §1g STANDING RULE "
        "VERBATIM (no paraphrase)"
    )


def test_c28_enumerates_8_surfaces_in_order():
    """C-28 must enumerate the 8-surface taxonomy in verbatim §1g
    order: core → cli → tui → api → mcp → dashboard → webapp →
    service."""
    mod = _archqa()
    c28 = next(
        c for c in mod.ARCHITECTURE_CONCEPTS if c.get("id") == "C-28"
    )
    expl = c28.get("explanation", "")
    # Find the ordered chain
    chain = "core → cli → tui → api → mcp → dashboard → webapp → service"
    assert chain in expl, (
        f"C-28 must enumerate the 8-surface chain {chain!r} in §1g order"
    )


def test_coverage_map_has_a33_axis():
    """coverage-map must carry an A-33 axis anchoring the §1g
    8-surface delivery contract."""
    mod = _coverage()
    ids = [a.get("id") for a in mod.DEFAULT_AXES]
    assert "A-33" in ids, (
        f"coverage-map.py must carry axis A-33 "
        f"(SDD-039 / §1g 8-surface delivery contract); got ids {ids}"
    )


def test_a33_cites_sdd_039_in_sdd_refs():
    """A-33 must list SDD-039 in its sdd_refs so the SDD reachability
    scanner picks it up via the coverage_referenced_sdds path."""
    mod = _coverage()
    a33 = next(a for a in mod.DEFAULT_AXES if a.get("id") == "A-33")
    sdd_refs = a33.get("sdd_refs") or []
    assert "039" in sdd_refs, (
        f"A-33 sdd_refs must include '039'; got {sdd_refs}"
    )


def test_a33_axis_verbatim_is_r453_anchor():
    """A-33 axis_verbatim must be the R453 operator §1g 8-surface
    anchor — sacrosanct."""
    mod = _coverage()
    a33 = next(a for a in mod.DEFAULT_AXES if a.get("id") == "A-33")
    av = a33.get("axis_verbatim", "")
    anchor = (
        "everything is not just core, not just cli, not just TUI, "
        "not just API, not just tool and MCP but also Dashboards "
        "and Web Apps and Services"
    )
    assert anchor in av, (
        "A-33 axis_verbatim must be the R453 §1g anchor VERBATIM"
    )


def test_a33_implementing_verbs_cover_4_instrument_suite():
    """A-33 must surface the 4-instrument compliance suite
    (surface-map / doc-coverage / anti-minimization-audit /
    ux-design-audit + R458 compliance rollup) via implementing_verbs."""
    mod = _coverage()
    a33 = next(a for a in mod.DEFAULT_AXES if a.get("id") == "A-33")
    verbs = " ".join(a33.get("implementing_verbs", []))
    for required in (
        "surface-map", "doc-coverage", "anti-minimization-audit",
        "ux-design-audit", "compliance",
    ):
        assert required in verbs, (
            f"A-33 implementing_verbs must include {required!r}; "
            f"got {verbs!r}"
        )


def test_a33_mandate_rows_cite_e10m110():
    """A-33 mandate_rows must cite E10.M110 (the R548 mandate row that
    closed the SDD-039 reachability via mandate path)."""
    mod = _coverage()
    a33 = next(a for a in mod.DEFAULT_AXES if a.get("id") == "A-33")
    rows = a33.get("mandate_rows", [])
    assert "E10.M110" in rows, (
        f"A-33 mandate_rows must include E10.M110 (R548 closure); "
        f"got {rows}"
    )


def test_sdd_039_reachable_via_all_4_paths():
    """End-to-end multi-path reachability: SDD-039 must be discoverable
    via ALL of {architecture-qa, coverage-map, mandate, SUMMARY}.

    SUMMARY.md path is allowed to be absent in R549 (the SUMMARY
    discipline is deferred to a later round — see Q-039-* open
    questions); the other 3 paths are MANDATORY post-R549."""
    archqa_blob = ARCH_QA.read_text(encoding="utf-8")
    coverage_blob = COVERAGE.read_text(encoding="utf-8")
    mandate_blob = MANDATE.read_text(encoding="utf-8")

    for label, blob in (
        ("architecture-qa.py", archqa_blob),
        ("coverage-map.py", coverage_blob),
        ("operator-mandate.md", mandate_blob),
    ):
        assert re.search(r"SDD[- ]039", blob), (
            f"R549: SDD-039 must be cited in {label} "
            f"(SDD reachability scanner reads via "
            f"SDD[- ](\\d{{3}}) regex)"
        )
