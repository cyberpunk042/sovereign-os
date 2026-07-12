"""context.md counts-as-contract lint (F-2026-030 / SDD-952).

`context.md` is the operator-mandated "read me first" re-orientation surface;
its own banner says *"if anything below is stale, fix it before continuing —
never silently let it drift."* It drifted anyway (the Phase-1 audit found it ~6
weeks stale and self-contradictory: 29 vs 476 crates when the tree had 714; "17
of 21 dashboards"; "29 SDDs").

The durable fix is not a one-time refresh — it's this lint. `context.md` carries
a machine-parseable COUNTS-CONTRACT block; here we parse it and assert every
count against the actual filesystem. A drift now fails CI, so the surface can't
silently rot again.

To update after the tree changes: edit the numbers in the COUNTS-CONTRACT block
in `context.md`. Do NOT rename the row labels (matched here).
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTEXT = REPO_ROOT / "context.md"

_BLOCK = re.compile(
    r"<!--\s*COUNTS-CONTRACT.*?-->(?P<body>.*?)<!--\s*END COUNTS-CONTRACT\s*-->",
    re.S,
)
# A markdown table row: | label | number | ... |  (number may carry commas)
_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([\d,]+)\s*\|", re.M)


def _computed() -> dict[str, int]:
    """The ground-truth counts, computed from the tree."""
    crates = REPO_ROOT / "crates"
    webapp = REPO_ROOT / "webapp"
    sdd = REPO_ROOT / "docs" / "sdd"
    milestones = REPO_ROOT / "backlog" / "milestones"
    return {
        "workspace crates": sum(1 for p in crates.iterdir() if p.is_dir()),
        "dashboards (d-nn)": sum(
            1 for p in webapp.iterdir() if p.is_dir() and p.name.startswith("d-")
        ),
        "cockpit panels (total)": sum(1 for _ in webapp.glob("*/index.html")),
        "sdd files": sum(
            1 for p in sdd.glob("*.md") if re.match(r"\d+-", p.name)
        ),
        "milestone files": sum(1 for _ in milestones.glob("*.md")),
    }


def _stated() -> dict[str, int]:
    """The counts declared in context.md's COUNTS-CONTRACT block."""
    text = CONTEXT.read_text(encoding="utf-8")
    m = _BLOCK.search(text)
    assert m, (
        "context.md is missing its COUNTS-CONTRACT block "
        "(<!-- COUNTS-CONTRACT ... --> ... <!-- END COUNTS-CONTRACT -->). "
        "It is the machine-verified re-orientation surface (SDD-952)."
    )
    stated: dict[str, int] = {}
    for label, num in _ROW.findall(m.group("body")):
        stated[label.strip().lower()] = int(num.replace(",", ""))
    return stated


def test_context_md_has_the_counts_contract_block():
    stated = _stated()
    expected_labels = set(_computed())
    missing = expected_labels - set(stated)
    assert not missing, (
        f"context.md COUNTS-CONTRACT block is missing rows for {sorted(missing)}. "
        f"Every tracked metric must be declared so the lint can verify it."
    )


def test_context_md_counts_match_the_filesystem():
    stated = _stated()
    computed = _computed()
    drift = {
        label: (stated.get(label), actual)
        for label, actual in computed.items()
        if stated.get(label) != actual
    }
    assert not drift, (
        "context.md COUNTS-CONTRACT has DRIFTED from the tree "
        "(stated -> actual): "
        + "; ".join(f"{k}: {s} -> {a}" for k, (s, a) in sorted(drift.items()))
        + ". Update the numbers in context.md's COUNTS-CONTRACT block."
    )
