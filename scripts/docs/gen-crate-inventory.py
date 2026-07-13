#!/usr/bin/env python3
"""gen-crate-inventory.py — generate the complete crate inventory doc.

Classifies, groups, and describes every one of the ~717 workspace crates into a
single reference (`docs/architecture/crate-inventory.md`). Descriptions are the
crates' own authoritative `Cargo.toml` `description` fields (never fabricated).

Classification:
  - binary vs library (has src/main.rs or src/bin/)
  - cockpit-* UX-state crate vs not
  - PRODUCTION-reachable (in the dependency closure of the three production
    binaries: gatewayd / telemetry / resource-control) vs demo-hub-reachable
    (sovereign-llm / sovereign-retrieval) vs other
  - for cockpit crates: wasm-bridge status (uniform macro / bespoke), read from
    cockpit-wasm/src/{bridges.rs, bespoke/*.rs}

Regenerate: `python3 scripts/docs/gen-crate-inventory.py`.
"""
from __future__ import annotations

import re
import sys
import tomllib
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CRATES = REPO / "crates"
OUT = REPO / "docs" / "architecture" / "crate-inventory.md"
COCKPIT_WASM = REPO / "cockpit-wasm" / "src"

PROD_ROOTS = ["sovereign-gatewayd", "sovereign-telemetry", "sovereign-resource-control"]
HUB_ROOTS = ["sovereign-llm", "sovereign-retrieval"]


def load() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for d in sorted(CRATES.glob("*/")):
        cargo = d / "Cargo.toml"
        if not cargo.is_file():
            continue
        data = tomllib.loads(cargo.read_text(encoding="utf-8"))
        pkg = data.get("package", {})
        name = pkg.get("name")
        if not name:
            continue
        desc = pkg.get("description")
        if isinstance(desc, dict):  # description.workspace = true (rare)
            desc = "(inherited workspace description)"
        src = d / "src"
        out[name] = {
            "desc": (desc or "").strip(),
            "bin": (src / "main.rs").is_file() or (src / "bin").is_dir(),
            "cockpit": name.startswith("sovereign-cockpit-"),
            "manifest": cargo.read_text(encoding="utf-8"),
        }
    return out


def closure(crates: dict[str, dict], roots: list[str]) -> set[str]:
    def deps(n: str) -> set[str]:
        return {
            m.group(1)
            for m in re.finditer(r"(?m)^\s*(sovereign-[a-z0-9-]+)\s*(=|\.)", crates.get(n, {}).get("manifest", ""))
            if m.group(1) in crates and m.group(1) != n
        }

    seen: set[str] = set()
    stack = [r for r in roots if r in crates]
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack.extend(deps(n))
    return seen


def bridge_status() -> dict[str, str]:
    """cockpit crate ident -> 'uniform' | 'bespoke' from the cockpit-wasm sources."""
    out: dict[str, str] = {}
    br = COCKPIT_WASM / "bridges.rs"
    if br.is_file():
        for ident in re.findall(r"sovereign_cockpit_(\w+)::", br.read_text(encoding="utf-8")):
            out["sovereign-cockpit-" + ident.replace("_", "-")] = "uniform"
    bd = COCKPIT_WASM / "bespoke"
    if bd.is_dir():
        for f in bd.glob("*.rs"):
            if f.name == "mod.rs":
                continue
            for ident in re.findall(r"use sovereign_cockpit_(\w+)::", f.read_text(encoding="utf-8")):
                out["sovereign-cockpit-" + ident.replace("_", "-")] = "bespoke"
    # banner-state is hand-bridged directly in lib.rs (the demo's crate)
    out.setdefault("sovereign-cockpit-banner-state", "hand (demo)")
    return out


def family(name: str, prefix: str) -> str:
    """Group key: the first slug token after `prefix` (e.g. alert-acknowledge -> alert)."""
    slug = name[len(prefix):] if name.startswith(prefix) else name
    return slug.split("-", 1)[0]


def emit_group(lines: list[str], crates: dict, names: list[str], prefix: str, tag=None, min_group: int = 3) -> None:
    """Sub-header only for families of >= min_group crates; the rest go in one
    flat 'assorted' list, so diverse sections don't fragment into 1-item headers."""
    fams: dict[str, list[str]] = defaultdict(list)
    for n in names:
        fams[family(n, prefix)].append(n)
    big = {f: m for f, m in fams.items() if len(m) >= min_group}
    assorted = sorted(n for f, m in fams.items() if len(m) < min_group for n in m)

    def line(n: str) -> str:
        t = f" — _{tag(n)}_" if tag else ""
        return f"- **`{n}`** — {crates[n]['desc']}{t}"

    for fam in sorted(big, key=lambda x: (-len(big[x]), x)):
        lines.append(f"\n#### `{fam}-·` ({len(big[fam])})\n")
        lines.extend(line(n) for n in sorted(big[fam]))
    if assorted:
        if big:
            lines.append(f"\n#### assorted ({len(assorted)})\n")
        lines.extend(line(n) for n in assorted)


def main() -> int:
    crates = load()
    total = len(crates)
    prod = closure(crates, PROD_ROOTS)
    hub = closure(crates, HUB_ROOTS) - prod
    bstat = bridge_status()

    binaries = sorted(n for n, c in crates.items() if c["bin"])
    cockpit = sorted(n for n, c in crates.items() if c["cockpit"] and not c["bin"])
    prod_libs = sorted(n for n in prod if not crates[n]["bin"] and not crates[n]["cockpit"])
    other_libs = sorted(
        n for n, c in crates.items()
        if not c["bin"] and not c["cockpit"] and n not in prod
    )
    hub_libs = sorted(n for n in other_libs if n in hub)
    misc_libs = sorted(n for n in other_libs if n not in hub)

    L: list[str] = []
    L.append("# Crate inventory — all sovereign-os workspace crates")
    L.append("")
    L.append("> GENERATED by `scripts/docs/gen-crate-inventory.py` — do not edit by hand.")
    L.append("> Descriptions are each crate's own `Cargo.toml` `description`. Regenerate after adding crates.")
    L.append("")
    L.append("The workspace is large — most of it does not run yet. This is the complete map: "
             "what every crate is, and whether anything actually reaches it. **Connection** is the "
             "open question the audit (F-2026-001) and the cockpit-wasm bridge (SDD-974) are chipping at.")
    L.append("")
    L.append("| bucket | count | connection state |")
    L.append("|---|---:|---|")
    L.append(f"| Binaries (`main.rs`/`bin/`) | {len(binaries)} | the executables; a few run in prod, the rest are dev/demo/config-gen |")
    L.append(f"| Production libraries | {len(prod_libs)} | run inside the gatewayd / telemetry / resource-control closure |")
    L.append(f"| Cockpit UX-state crates | {len(cockpit)} | wasm-bridged in source (SDD-974); **0 of ~55 panels wired** |")
    L.append(f"| Demo-hub-only libraries | {len(hub_libs)} | reached only via `sovereign-llm` / `sovereign-retrieval` (nothing runs them) |")
    L.append(f"| Other libraries | {len(misc_libs)} | reached only through other non-production trees |")
    L.append(f"| **Total** | **{total}** | **{len(prod)} crates ({100*len(prod)//total}%) are production-reachable today** |")
    L.append("")
    L.append("Families below cluster by the first token of the crate name (`alert-*`, `zfs-*`, …).")

    L.append("\n---\n\n## 1. Binaries — the executable surface\n")
    L.append("Full runtime role + how each is invoked lives in [`docs/src/binaries.md`](../src/binaries.md); "
             "this lists them with their own one-line descriptions.")
    prod_bins = [n for n in binaries if n in prod]
    other_bins = [n for n in binaries if n not in prod]
    L.append(f"\n### Production / runtime ({len(prod_bins)})\n")
    emit_group(L, crates, prod_bins, "sovereign-")
    L.append(f"\n### Dev / demo / config-generators ({len(other_bins)})\n")
    emit_group(L, crates, other_bins, "sovereign-")

    L.append(f"\n---\n\n## 2. Production libraries ({len(prod_libs)}) — these actually run\n")
    L.append("In the dependency closure of the three production binaries, so they execute today.")
    emit_group(L, crates, prod_libs, "sovereign-")

    L.append(f"\n---\n\n## 3. Cockpit UX-state crates ({len(cockpit)})\n")
    L.append("Typed, tested UI-state models. Compiled to wasm by `cockpit-wasm` (SDD-974) so a panel "
             "*could* call the real Rust — but **no production panel is wired to the bridge yet** "
             "(only the standalone demo). Tag = wasm-bridge kind.")
    emit_group(L, crates, cockpit, "sovereign-cockpit-",
               tag=lambda n: f"bridge: {bstat.get(n, 'unbridged')}")

    L.append(f"\n---\n\n## 4. Demo-hub-only libraries ({len(hub_libs)}) — reached only via the island hubs\n")
    L.append("Consumed only through `sovereign-llm` / `sovereign-retrieval`, which the daemon does not "
             "use — so nothing that runs reaches them. Wiring a hub into production, or giving these real "
             "consumers, is the open work (audit F-2026-083/088/089).")
    emit_group(L, crates, hub_libs, "sovereign-")

    L.append(f"\n---\n\n## 5. Other libraries ({len(misc_libs)}) — reached only through non-production trees\n")
    emit_group(L, crates, misc_libs, "sovereign-")
    L.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}: {total} crates "
          f"({len(binaries)} bin, {len(prod_libs)} prod-lib, {len(cockpit)} cockpit, "
          f"{len(hub_libs)} hub, {len(misc_libs)} other)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
