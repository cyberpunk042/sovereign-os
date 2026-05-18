"""scripts/lib/inventory_consult.py — R348 (E9.M17, SDD-032 §4 helper).

Bridges hardware advisors to the R317 inventory-catalog operator-
actionable caveats. Promoted from R347 inline pattern (xmp-oc-room-
advisor) because R252 power-status, R313 psu-oc-mode, R257 memory-
profile, etc. all have catalog cross-refs that would surface buried
caveats to operator-pull verdicts the same way.

Public API (SDD-032 contract — covered by tests/lint/
test_inventory_consult_api.py):

  find_advisor_caveats(round_id: str) -> list[dict]
      Returns list of {slot, sku, model, category, caveat, severity}
      for catalog entries whose related_advisor field contains the
      given round_id (e.g. "R315") AND has a non-null operator_caveat.

      Severity tagging is heuristic on caveat text:
        warn → "may fail" / "exceed" / "instability" / "drop to"
        info → everything else

  caveats_matching(round_id, *, contains_any=None, contains_all=None)
      Returns find_advisor_caveats(round_id) filtered to caveat
      strings matching the given substring criteria (case-insensitive).
      Convenience for advisors surfacing specific sub-warnings.

NEVER-raise contract (SDD-032): every entrypoint returns [] (or its
empty equivalent) on missing catalog / OS error / malformed module.
Catalog liveness failure must NEVER take an advisor down.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Iterable

# Repo root resolves to the parent of "scripts/" — same convention all
# other helpers in scripts/lib/ follow.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_CATALOG_PATH = _REPO_ROOT / "scripts" / "hardware" / "inventory-catalog.py"


_WARN_KEYWORDS = ("may fail", "exceed", "instability", "drop to")


def _severity_for(caveat: str) -> str:
    low = (caveat or "").lower()
    return "warn" if any(k in low for k in _WARN_KEYWORDS) else "info"


def _load_components() -> list[dict[str, Any]]:
    """NEVER-raise import of R317 DEFAULT_COMPONENTS."""
    try:
        if not _CATALOG_PATH.is_file():
            return []
        spec = importlib.util.spec_from_file_location(
            "_inventory_catalog_consult", _CATALOG_PATH,
        )
        if spec is None or spec.loader is None:
            return []
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        components = getattr(mod, "DEFAULT_COMPONENTS", [])
        if not isinstance(components, list):
            return []
        return components
    except Exception:
        return []


def find_advisor_caveats(round_id: str) -> list[dict[str, Any]]:
    """Returns operator-actionable caveats from R317 catalog whose
    related_advisor field mentions round_id (e.g. 'R315')."""
    if not round_id:
        return []
    out: list[dict[str, Any]] = []
    for c in _load_components():
        if not isinstance(c, dict):
            continue
        related = c.get("related_advisor") or ""
        caveat = c.get("operator_caveat")
        if round_id not in related or not caveat:
            continue
        out.append({
            "slot": c.get("slot"),
            "sku": c.get("sku"),
            "model": c.get("model"),
            "category": c.get("category"),
            "caveat": caveat,
            "severity": _severity_for(caveat),
        })
    return out


def caveats_matching(
    round_id: str,
    *,
    contains_any: Iterable[str] | None = None,
    contains_all: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Filter find_advisor_caveats(round_id) by case-insensitive text
    match on the caveat field. contains_any → at least one substring
    present; contains_all → every substring present."""
    base = find_advisor_caveats(round_id)
    if not base:
        return []
    any_list = [s.lower() for s in (contains_any or [])]
    all_list = [s.lower() for s in (contains_all or [])]
    out: list[dict[str, Any]] = []
    for cv in base:
        low = (cv.get("caveat") or "").lower()
        if any_list and not any(s in low for s in any_list):
            continue
        if all_list and not all(s in low for s in all_list):
            continue
        out.append(cv)
    return out
