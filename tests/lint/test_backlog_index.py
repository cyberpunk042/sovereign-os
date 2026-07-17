"""Backlog milestone-index sync contract (2026-07-17 drift closure).

`backlog/INDEX.md` long CLAIMED "auto-generated" but had no generator and no
CI lock — so it drifted silently: header totals wrong (82/14,080 vs the real
84 files / 14,079 distinct R-rows), M085/M086 absent from the table, ~14
per-milestone counts stale. `scripts/backlog/gen-index.py` now generates it
with the SAME distinct-R-row metric as SHIPPED-ROLLUP.md; this lint keeps it
honest the same way test_shipped_rollup.py does:
  * regen-and-compare — committed INDEX == fresh generation;
  * completeness — every milestone file appears;
  * cross-catalog totals agreement — INDEX and SHIPPED-ROLLUP report the
    same milestone-file count and R-row grand total.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GEN = REPO_ROOT / "scripts" / "backlog" / "gen-index.py"
OUT = REPO_ROOT / "backlog" / "INDEX.md"
ROLLUP = REPO_ROOT / "backlog" / "SHIPPED-ROLLUP.md"
MILESTONES = REPO_ROOT / "backlog" / "milestones"


def _load_generator():
    spec = importlib.util.spec_from_file_location("gen_backlog_index", GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_generator_and_output_exist():
    assert GEN.is_file(), f"missing {GEN}"
    assert OUT.is_file(), f"missing {OUT} — run `python3 {GEN.relative_to(REPO_ROOT)}`"


def test_index_is_not_stale():
    mod = _load_generator()
    expected = mod.render()
    actual = OUT.read_text(encoding="utf-8")
    assert actual == expected, (
        f"{OUT.relative_to(REPO_ROOT)} is stale — regenerate with "
        f"`python3 {GEN.relative_to(REPO_ROOT)}` after a milestone change"
    )


def test_every_milestone_is_in_the_index():
    body = OUT.read_text(encoding="utf-8")
    missing = []
    for f in sorted(MILESTONES.glob("M*.md")):
        if f.name == "INDEX.md":
            continue
        if f"(milestones/{f.name})" not in body:
            missing.append(f.name)
    assert not missing, f"milestones missing from INDEX.md: {missing}"


def test_totals_agree_with_shipped_rollup():
    """INDEX.md and SHIPPED-ROLLUP.md are generated from the same tree with
    the same distinct-R-row metric — their totals MUST agree. Disagreement
    means one generator's metric drifted (the pre-2026-07-17 failure shape:
    three different catalog sizes across backlog docs)."""
    index_body = OUT.read_text(encoding="utf-8")
    rollup_body = ROLLUP.read_text(encoding="utf-8")

    m = re.search(r"(\d+) milestone files · \*\*([\d,]+) distinct R-rows", index_body)
    assert m, "INDEX.md missing the generated totals line"
    idx_files, idx_rrows = int(m.group(1)), int(m.group(2).replace(",", ""))

    n_files = len([p for p in MILESTONES.glob("M*.md") if p.name != "INDEX.md"])
    assert idx_files == n_files, (
        f"INDEX.md claims {idx_files} milestone files; tree has {n_files}"
    )

    rm = re.search(
        r"\|\s*Catalogued R-rows \(distinct, all milestones\)\s*\|\s*([\d,]+)\s*\|",
        rollup_body,
    )
    assert rm, "SHIPPED-ROLLUP.md missing its 'Catalogued R-rows' grand-total row"
    rollup_rrows = int(rm.group(1).replace(",", ""))
    assert idx_rrows == rollup_rrows, (
        f"INDEX.md total {idx_rrows} != SHIPPED-ROLLUP.md total "
        f"{rollup_rrows} (same tree, same metric — a generator drifted)"
    )
