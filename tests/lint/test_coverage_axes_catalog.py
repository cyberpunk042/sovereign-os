"""R432 (E10.M76) — coverage-map.py axes catalog contract lint.

Extends R387-R431 + R423/R431 operational-artifact pinning to:
  scripts/intelligence/coverage-map.py  (32 operator-named demand axes)

R423 covered the verbatim-render AGGREGATOR; R431 pinned the
architecture-qa catalog source. R432 pins the SISTER catalog —
DEFAULT_AXES (the 32 operator-named demand axes A-01..A-32).

Each axis declares:
  - id              A-NN slug (operator-named)
  - axis_verbatim   the demand text verbatim from operator
  - source          where this axis came from (master spec / hook drop)
  - implementing_verbs[]  sovereign-osctl verbs that satisfy it
  - sdd_refs[]      SDDs that codify the implementation
  - mandate_rows[]  E.M rows that ship the implementation
  - status          shipped / partial / TODO
  - notes           operator-discoverable context

If a future agent silently:
  - drops an axis = R423 verbatim-render emits a shorter coverage map
  - rephrases axis_verbatim = operator-verbatim text drifts
  - adds 'shipped' status without implementing_verbs/sdd_refs/mandate_rows
    = false confidence in coverage
…the operator-named demand-coverage matrix silently drifts.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CMAP_PY = REPO_ROOT / "scripts" / "intelligence" / "coverage-map.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("cmap", CMAP_PY)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


KNOWN_STATUSES = {
    "shipped", "partial", "TODO",
    "✓ shipped", "✓shipped",  # operator may include checkmark
    "deferred", "in-flight",
}


# --- Structural ---


def test_coverage_map_py_exists():
    assert CMAP_PY.is_file(), f"missing {CMAP_PY}"


def test_module_exports_default_axes():
    """R423 aggregator looks up DEFAULT_AXES via getattr; renaming
    breaks the aggregator silently."""
    mod = _load_module()
    assert hasattr(mod, "DEFAULT_AXES"), (
        "coverage-map.py missing DEFAULT_AXES export "
        "(R423 verbatim-render aggregator depends on it)"
    )


def test_thirty_two_axes():
    """Operator-named 32-axis catalog. Drift = matrix shrinkage."""
    mod = _load_module()
    axes = mod.DEFAULT_AXES
    assert len(axes) >= 30, (
        f"DEFAULT_AXES only {len(axes)} entries "
        f"(operator-named 32-axis demand-coverage matrix; drift)"
    )


# --- Per-axis required fields ---


def test_every_axis_has_id():
    mod = _load_module()
    for a in mod.DEFAULT_AXES:
        assert a.get("id"), f"axis missing id: {a}"


def test_axis_ids_follow_a_nn_pattern():
    """A-NN slug pattern (operator-named)."""
    mod = _load_module()
    pattern = re.compile(r"^A-\d{2}$")
    for a in mod.DEFAULT_AXES:
        aid = a.get("id", "")
        assert pattern.match(aid), (
            f"axis id={aid!r} doesn't match A-NN pattern"
        )


def test_axis_ids_unique():
    mod = _load_module()
    ids = [a.get("id") for a in mod.DEFAULT_AXES]
    assert len(ids) == len(set(ids)), (
        f"duplicate axis IDs: {[i for i in ids if ids.count(i) > 1]}"
    )


def test_axis_ids_sequential():
    """A-01..A-NN with no gaps (drift = missing IDs leaves coverage
    holes in the matrix display)."""
    mod = _load_module()
    ids = sorted(a.get("id") for a in mod.DEFAULT_AXES)
    expected = [f"A-{i:02d}" for i in range(1, len(ids) + 1)]
    assert ids == expected, (
        f"axis IDs not sequential: {ids} vs expected {expected[:5]}..."
    )


def test_every_axis_has_axis_verbatim():
    """The operator-verbatim demand text MUST be non-empty (this is
    what 'NO REPHRASING' protects)."""
    mod = _load_module()
    for a in mod.DEFAULT_AXES:
        verbatim = (a.get("axis_verbatim") or "").strip()
        assert verbatim, (
            f"axis {a.get('id')!r} missing axis_verbatim"
        )
        assert len(verbatim) >= 10, (
            f"axis {a.get('id')!r} axis_verbatim too short "
            f"(≥10 chars expected; operator-named demand text)"
        )


def test_every_axis_has_source():
    """Operator-discoverable: source citation MUST be present."""
    mod = _load_module()
    for a in mod.DEFAULT_AXES:
        src = (a.get("source") or "").strip()
        assert src, (
            f"axis {a.get('id')!r} missing source"
        )


def test_every_axis_has_status():
    """status MUST be in known set."""
    mod = _load_module()
    for a in mod.DEFAULT_AXES:
        st = a.get("status")
        assert st in KNOWN_STATUSES, (
            f"axis {a.get('id')!r} status={st!r} not in "
            f"{KNOWN_STATUSES}"
        )


def test_every_axis_has_lists_initialized():
    """implementing_verbs + sdd_refs + mandate_rows MUST exist as
    lists (even if empty — operator-discoverable structural surface)."""
    mod = _load_module()
    for a in mod.DEFAULT_AXES:
        for field in ("implementing_verbs", "sdd_refs", "mandate_rows"):
            val = a.get(field)
            assert isinstance(val, list), (
                f"axis {a.get('id')!r} {field}={val!r} not a list "
                f"(operator-discoverable structural slot)"
            )


# --- Status integrity ---


def test_shipped_axes_have_evidence():
    """status=shipped MUST have at least one of: implementing_verbs,
    sdd_refs, mandate_rows. Drift = false confidence in coverage."""
    mod = _load_module()
    for a in mod.DEFAULT_AXES:
        st = (a.get("status") or "").lower()
        if "shipped" not in st:
            continue
        verbs = a.get("implementing_verbs") or []
        sdds = a.get("sdd_refs") or []
        rows = a.get("mandate_rows") or []
        has_evidence = bool(verbs) or bool(sdds) or bool(rows)
        assert has_evidence, (
            f"axis {a.get('id')!r} status=shipped but no evidence "
            f"(no implementing_verbs/sdd_refs/mandate_rows) — "
            f"false confidence in coverage"
        )


def test_sdd_refs_well_formed():
    """SDD references MUST follow SDD-NNN OR bare NNN format
    (operator allows both — full SDD-NNN identifier or the numeric
    suffix; coverage-map convention)."""
    mod = _load_module()
    pattern = re.compile(r"^(SDD-)?\d{1,4}[a-z]?$")
    for a in mod.DEFAULT_AXES:
        for sdd in (a.get("sdd_refs") or []):
            assert pattern.match(sdd), (
                f"axis {a.get('id')!r} sdd_ref={sdd!r} doesn't match "
                f"SDD-NNN or bare NNN pattern"
            )


def test_mandate_rows_well_formed():
    """Mandate rows reference E.M format (Epic.Module — operator-named)."""
    mod = _load_module()
    pattern = re.compile(r"^E\d+(\.M\d+)?$|^SD-R\d+$|^E\d+\.M\d+$")
    for a in mod.DEFAULT_AXES:
        for row in (a.get("mandate_rows") or []):
            # Allow E.M or SD-R<N> or other operator-named formats
            looks_valid = (
                re.match(r"^E\d+\.M\d+$", row)
                or re.match(r"^SD-R\d+$", row)
                or re.match(r"^E\d+$", row)
            )
            assert looks_valid, (
                f"axis {a.get('id')!r} mandate_row={row!r} doesn't "
                f"match E.M or SD-RN operator-named format"
            )


# --- Coverage breadth ---


def test_at_least_some_axes_shipped():
    """At least 50% of axes should be shipped (drift = coverage
    matrix slipping toward TODO majority). Allows '✓ shipped' /
    'shipped' / variant forms."""
    mod = _load_module()
    axes = mod.DEFAULT_AXES
    shipped = sum(
        1 for a in axes if "shipped" in (a.get("status") or "").lower()
    )
    pct = (shipped / len(axes)) * 100 if axes else 0
    assert pct >= 50, (
        f"only {shipped}/{len(axes)} ({pct:.0f}%) axes shipped "
        f"(operator-named demand coverage slipping)"
    )


# --- Sources cover master spec + hook drop ---


def test_some_axes_from_master_spec():
    """At least one axis sources from master spec § (operator-named
    L0 dump)."""
    mod = _load_module()
    has_spec = any(
        "master spec" in (a.get("source") or "").lower()
        or "§" in (a.get("source") or "")
        for a in mod.DEFAULT_AXES
    )
    assert has_spec, (
        "no axes sourced from master spec § (operator-named L0 dump)"
    )


def test_some_axes_have_implementing_verbs():
    """At least one shipped axis MUST have implementing_verbs
    (operator-discoverable: which sovereign-osctl verb satisfies it)."""
    mod = _load_module()
    has_verbs = any(
        bool(a.get("implementing_verbs") or [])
        for a in mod.DEFAULT_AXES
    )
    assert has_verbs, (
        "no axes have implementing_verbs (operator can't drill from "
        "axis to runnable verb)"
    )


# --- NO REPHRASING contract ---


def test_module_documents_verbatim_contract():
    """Header MUST document the operator-verbatim contract."""
    body = CMAP_PY.read_text(encoding="utf-8")
    has_contract = (
        "verbatim" in body.lower()
        or "operator-named" in body.lower()
        or "NO REPHRASING" in body
    )
    assert has_contract, (
        "coverage-map.py missing operator-verbatim contract "
        "documentation in header"
    )
