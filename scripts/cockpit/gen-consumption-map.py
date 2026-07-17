#!/usr/bin/env python3
"""gen-cockpit-consumption-map.py — make the sovereign-cockpit-* crate family's
consumption VISIBLE (2026-07-17).

The family is 418 real, tested micro-crates, all compiled by CI (`members =
["crates/*"]`) — but a July-2026 audit found only ~30-40 are actually consumed
in a product path; the rest are compiled+tested shelfware, with a handful of
true near-duplicate pairs. The project's "we do not minimize" doctrine means we
do NOT delete them — but "compiled != consumed" was invisible, so nobody could
make an informed keep/wire/retire decision. This generator surfaces it:

Per crate, the STRONGEST consumption tier:
  wasm-compute    — a hand-written wasm bridge in cockpit-wasm/src/{compute,bespoke}/
                    (real compute reaches the browser)
  rust-consumer   — another crate depends on it in Cargo.toml (in a build graph)
  validate-bridge — a generated `<slug>_validate` export in cockpit-wasm bridges.rs
                    (validation reaches the browser; the bulk tier)
  compiled-only   — none of the above: CI compiles + tests it, nothing consumes it
                    (the honest "shelfware" tier — a keep/wire/retire candidate)

Plus duplicate clusters: crates whose slug shares a stem with another (the
text-truncate/text-truncation, undo-stack/undo-redo-stack family) — flagged with
which member is consumed, so a retire decision is one-glance informed.

Emits docs/cockpit/consumption-map.md. `--check` exits non-zero if stale
(tests/lint/test_cockpit_consumption_map.py enforces it). NON-DESTRUCTIVE:
this only reports; any retire/wire action is an operator decision.
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CRATES = REPO / "crates"
WASM = REPO / "cockpit-wasm"
OUT = REPO / "docs" / "cockpit" / "consumption-map.md"

PREFIX = "sovereign-cockpit-"


def _cockpit_crates() -> list[str]:
    return sorted(
        p.name for p in CRATES.glob(f"{PREFIX}*") if (p / "Cargo.toml").is_file()
    )


def _slug(crate: str) -> str:
    return crate[len(PREFIX):]


def _snake(slug: str) -> str:
    return slug.replace("-", "_")


def _handwritten_bridge_slugs() -> set[str]:
    out: set[str] = set()
    for sub in ("compute", "bespoke"):
        d = WASM / "src" / sub
        if d.is_dir():
            for f in d.glob("*.rs"):
                if f.stem != "mod":
                    out.add(f.stem)  # snake
    return out


def _validate_bridge_slugs() -> set[str]:
    b = WASM / "src" / "bridges.rs"
    if not b.is_file():
        return set()
    text = b.read_text(encoding="utf-8")
    # bridge_validate!(<snake>_validate, sovereign_cockpit_<snake>::Type)
    return {
        m.group(1)
        for m in re.finditer(r"bridge_validate!\(\s*([a-z0-9_]+)_validate", text)
    }


def _rust_consumers() -> dict[str, list[str]]:
    """cockpit crate → sorted list of OTHER crates that depend on it."""
    consumers: dict[str, set[str]] = defaultdict(set)
    for cargo in CRATES.glob("*/Cargo.toml"):
        owner = cargo.parent.name
        for dep in re.findall(rf"{PREFIX}[a-z0-9-]+", cargo.read_text(encoding="utf-8")):
            if dep != owner and (CRATES / dep).is_dir():
                consumers[dep].add(owner)
    return {k: sorted(v) for k, v in consumers.items()}


def _duplicate_clusters(crates: list[str]) -> dict[str, list[str]]:
    """Group crates whose slug shares a normalized stem (drop a trailing
    -state/-stack/-region/-section/-list/-loader/-template/-tray/-status
    /-position/-truncate(ion) qualifier). Only clusters with >1 member are
    returned — the near-duplicate surface."""
    _QUAL = re.compile(
        r"-(state|stack|region|section|list|loader|template|tray|status|"
        r"position|truncate|truncation|redo)$"
    )

    def stem(slug: str) -> str:
        s = slug
        # peel up to two trailing qualifiers (undo-redo-stack → undo)
        for _ in range(2):
            s2 = _QUAL.sub("", s)
            if s2 == s:
                break
            s = s2
        return s

    groups: dict[str, list[str]] = defaultdict(list)
    for c in crates:
        groups[stem(_slug(c))].append(c)
    return {k: v for k, v in sorted(groups.items()) if len(v) > 1}


def _classify(crates: list[str]):
    hw = _handwritten_bridge_slugs()
    vb = _validate_bridge_slugs()
    rc = _rust_consumers()
    tier: dict[str, str] = {}
    for c in crates:
        snake = _snake(_slug(c))
        if snake in hw:
            tier[c] = "wasm-compute"
        elif c in rc:
            tier[c] = "rust-consumer"
        elif snake in vb:
            tier[c] = "validate-bridge"
        else:
            tier[c] = "compiled-only"
    return tier, rc


def render() -> str:
    crates = _cockpit_crates()
    tier, rc = _classify(crates)
    clusters = _duplicate_clusters(crates)

    counts = defaultdict(int)
    for t in tier.values():
        counts[t] += 1
    order = ["wasm-compute", "rust-consumer", "validate-bridge", "compiled-only"]
    # "live-consumed" = a real product path calls into it: a hand-written
    # compute bridge OR a build-graph rust dependency. A validate-bridge is
    # only an EXPORTED validator — the committed webapp build invokes almost
    # none of them (the full bridge cockpit_wasm_full.js is not committed), so
    # it is latent, not live. That distinction is the whole point of the map.
    live = counts["wasm-compute"] + counts["rust-consumer"]
    latent = counts["validate-bridge"]

    L: list[str] = []
    L.append("# sovereign-cockpit-* consumption map")
    L.append("")
    L.append(
        "> **Generated by `scripts/cockpit/gen-consumption-map.py`** "
        "(CI-locked by `tests/lint/test_cockpit_consumption_map.py`). "
        "Makes visible which of the cockpit micro-crates are actually consumed "
        "vs compiled-and-tested-only. **Non-destructive** — the \"we do not "
        "minimize\" doctrine stands; this is the decision surface for any "
        "operator-ratified wire/retire, not an action. Regenerate: "
        "`python3 scripts/cockpit/gen-consumption-map.py`."
    )
    L.append("")
    L.append(
        f"**{len(crates)} cockpit crates** · **{live} live-consumed** (a real "
        f"product path calls in) · **{latent} export-only** (a `validate` "
        f"bridge is exported but the committed webapp invokes ~none — the full "
        f"bridge `cockpit_wasm_full.js` is not committed) · "
        f"**{counts['compiled-only']} compiled-only** (nothing references them "
        f"at all)."
    )
    L.append("")
    L.append(
        "> The July-2026 audit's \"~380 shelfware\" figure ≈ the export-only + "
        "compiled-only tiers: crates CI builds and tests but that no shipped "
        "panel actually drives. They are not dead (validators run in tests) and "
        "not deleted (\"we do not minimize\") — they are the wire-or-retire "
        "backlog this map makes queryable."
    )
    L.append("")
    L.append("| Tier | Meaning | Count |")
    L.append("|---|---|---:|")
    meanings = {
        "wasm-compute": "hand-written wasm bridge (real compute → browser)",
        "rust-consumer": "another crate depends on it (in a build graph)",
        "validate-bridge": "generated `<slug>_validate` export (validation → browser)",
        "compiled-only": "compiled + tested by CI; **not consumed anywhere**",
    }
    for t in order:
        L.append(f"| `{t}` | {meanings[t]} | {counts[t]} |")
    L.append("")

    L.append("## Duplicate / overlapping clusters")
    L.append("")
    L.append(
        "Crates whose slug shares a stem. The **✓ consumed** column shows which "
        "member is wired — a cluster where only one member is consumed is the "
        "clearest operator retire-candidate (the sibling is compiled-only)."
    )
    L.append("")
    L.append("| Stem | Members (tier · ✓=consumed) |")
    L.append("|---|---|")
    for stem, members in clusters.items():
        cells = []
        for m in members:
            mark = "✓" if tier[m] != "compiled-only" else "·"
            cells.append(f"`{_slug(m)}` ({tier[m]} {mark})")
        L.append(f"| `{stem}` | {' — '.join(cells)} |")
    L.append("")

    L.append("## compiled-only crates (the shelfware tier)")
    L.append("")
    L.append(
        "Every one is real + tested; none is consumed by the wasm bridge, the "
        "webapp, or another crate today. Listed in full (no minimization) so the "
        "operator can decide per crate: wire it into a panel, or retire it."
    )
    L.append("")
    compiled_only = [c for c in crates if tier[c] == "compiled-only"]
    for c in compiled_only:
        L.append(f"- `{c}`")
    L.append("")

    L.append("## rust-consumer detail")
    L.append("")
    L.append("| Crate | Depended on by |")
    L.append("|---|---|")
    for c in crates:
        if tier[c] == "rust-consumer":
            L.append(f"| `{_slug(c)}` | {', '.join('`'+d+'`' for d in rc[c])} |")
    L.append("")
    return "\n".join(L)


def main() -> int:
    content = render()
    if "--check" in sys.argv:
        if not OUT.is_file() or OUT.read_text(encoding="utf-8") != content:
            print(f"STALE: {OUT.relative_to(REPO)} — regenerate with "
                  f"python3 scripts/cockpit/gen-consumption-map.py", file=sys.stderr)
            return 1
        print(f"OK: {OUT.relative_to(REPO)} is current")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(content, encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
