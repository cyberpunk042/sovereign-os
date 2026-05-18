#!/usr/bin/env python3
"""scripts/intelligence/architecture-qa.py — R355 (E10.M3).

Operator-pull entry-point for the SAIN-01 master spec's verbatim
§13 Architectural Q&A Matrix + §14 Critical Edge Cases & Operational
Gotchas. Surfaces operator-stated architectural rationale + per-board
edge cases as discoverable operator-pull verbs.

Until R355, operator's §13 rationale ("why Debian 13?", "why
sync=always?", "why -march=znver5?", "why bindeb-pkg?") + §14 gotchas
(dual-GPU lane asymmetry, Secure Boot MOK blockades, OPNsense
bridging + Tetragon disconnects) lived only in the master spec text
under docs/src/sain-01-master-spec.md. No operator-pull verb made
them queryable by topic.

R355 catalogs both:
  - Q&A items from §13 (operator-verbatim question + answer + tags)
  - Gotchas from §14 (operator-named edge case + prevention + tags)

CLI:
  architecture-qa.py questions          [--tag T] [--config P] [--json|--human]
  architecture-qa.py gotchas            [--tag T] [--config P] [--json|--human]
  architecture-qa.py show <id>          [--config P] [--json|--human]
  architecture-qa.py search <substring> [--config P] [--json|--human]

Operator-overlay (R283/SDD-030): /etc/sovereign-os/architecture-qa.toml
adds operator-authored Q&A or gotchas (e.g. operator notes a new
edge case from a hardware shift).

Exit codes:
  0  rendered
  1  unknown id / no matches
  2  usage
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
try:
    from operator_overlay import load_with_overlay  # type: ignore
except Exception:  # pragma: no cover
    load_with_overlay = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R355"
SDD_VECTOR = "E10.M3"


# ── §13 Architectural Q&A Matrix (verbatim from master spec) ─────
#
# Each entry binds:
#   - id              short slug (Q-NN)
#   - question        operator-verbatim question (NO REPHRASING)
#   - answer          operator-verbatim answer (NO REPHRASING)
#   - tags            searchable tags
#   - spec_ref        master spec section reference
ARCHITECTURE_QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "Q-01",
        "question": ("Why choose Debian 13 (Trixie) over enterprise-grade "
                      "Red Hat derivatives or bleeding-edge Arch Linux "
                      "distributions for an AI Orchestration Node?"),
        "answer": ("Arch Linux introduces excessive rolling upstream "
                    "entropy. A breaking package upgrade can compromise "
                    "out-of-tree kernel interfaces (like ZFS-DKMS or "
                    "proprietary NVIDIA compute stacks) at runtime "
                    "without warning. Conversely, enterprise Red Hat "
                    "variations backport heavily mutated patches into "
                    "antiquated kernels, generating artificial friction "
                    "during custom compilations. Debian 13 offers a "
                    "pristine upstream GNU foundation, combining modern "
                    "libraries (GCC 14) with a predictable development "
                    "baseline, making it the perfect substrate for "
                    "building optimized binaries."),
        "tags": ["distro-choice", "debian-13", "trixie", "stability",
                 "kernel-interfaces", "substrate"],
        "spec_ref": "master spec §13 (Q1 verbatim)",
    },
    {
        "id": "Q-02",
        "question": ("Why map the multi-agent context files (CLAUDE.md, "
                      "etc.) to a custom ZFS pool set to sync=always "
                      "instead of using standard ext4/XFS filesystems "
                      "with default parameters?"),
        "answer": ("Standard Linux filesystems utilize lazy write "
                    "page-caching mechanisms. If an agent writes an "
                    "explicit state update to CLAUDE.md and immediately "
                    "transfers control to a downstream execution agent, "
                    "the secondary agent could query the underlying "
                    "block file before the operating system kernel "
                    "physically flushes the dirty cache pages to NVMe "
                    "silicon. This introduces immediate context race "
                    "conditions. Forcing sync=always via ZFS enforces "
                    "synchronous write paths across the transactional "
                    "pipeline, ensuring that execution blocks do not "
                    "process downstream routines until the state is "
                    "physically secured onto the hardware layer."),
        "tags": ["zfs", "sync-always", "state-fabric", "context-race",
                 "tank-context", "multi-agent", "atomic-write"],
        "spec_ref": "master spec §13 (Q2 verbatim)",
    },
    {
        "id": "Q-03",
        "question": ("What is the specific performance yield of building "
                      "a custom kernel using -march=znver5 compared to "
                      "generic distribution kernels (-march=x86-64-v3)?"),
        "answer": ("Generic distribution kernels utilize "
                    "common-denominator instruction targets (x86-64-v3 "
                    "or v4) to maintain wide physical deployment "
                    "compatibility. This locks out the unique "
                    "microarchitectural advantages of the AMD Zen 5 "
                    "core layout. Compiling natively with -march=znver5 "
                    "exposes the full execution profile to the "
                    "compiler: it leverages specific instruction "
                    "latencies, branch prediction models, optimized "
                    "caching alignments, and natively executes code "
                    "inside single-cycle 512-bit wide AVX-512 vector "
                    "pipelines. For computational tasks processing "
                    "large local numerical models or parsing massive "
                    "context vectors via customized WASM/Assembly "
                    "runtimes, this bypasses the multi-cycle emulation "
                    "penalties incurred by lower instruction sets."),
        "tags": ["kernel-build", "znver5", "avx-512", "ryzen-9-9900x",
                 "march", "vectorization", "bitnet"],
        "spec_ref": "master spec §13 (Q3 verbatim)",
    },
    {
        "id": "Q-04",
        "question": ("How do we bypass the DKMS compilation failure loop "
                      "when booting a brand-new custom kernel version?"),
        "answer": ("When custom kernels are deployed via traditional "
                    "means, standard DKMS automations frequently fail "
                    "to bind properly due to missing version flags or "
                    "non-standard naming schemes inside your custom "
                    "/usr/src/linux-headers-* configurations. We "
                    "systematically negate this issue by outputting the "
                    "compilation directly into official internal "
                    "Debian-wrapped archive structures (bindeb-pkg). "
                    "This ensures the generated package implicitly "
                    "updates the system package registry with precise "
                    "dependency structures, ensuring that zfs-dkms "
                    "tracks, compiles, and injects its kernel modules "
                    "automatically on every system update."),
        "tags": ["dkms", "bindeb-pkg", "custom-kernel", "zfs-dkms",
                 "kernel-module", "package-registry"],
        "spec_ref": "master spec §13 (Q4 verbatim)",
    },
]


# ── §14 Critical Edge Cases & Operational Gotchas (verbatim) ─────
ARCHITECTURE_GOTCHAS: list[dict[str, Any]] = [
    {
        "id": "G-01",
        "name": "Dual GPU Lane Asymmetry & Bandwidth Throttle",
        "context": ("The ASUS ProArt X870E-Creator motherboard shares "
                     "internal high-speed PCIe lanes coming off the "
                     "Ryzen 9 9900X CPU. When you operate a dual GPU "
                     "layout (e.g., matching your future NVIDIA RTX PRO "
                     "6000 Blackwell with your current RTX 3090), the "
                     "physical top two PCIe 5.0 slots drop down from "
                     "an isolated x16 lanes execution mode to a shared "
                     "x8 / x8 execution topology."),
        "gotcha": ("If an agent tries to load a sprawling model across "
                    "both cards simultaneously, data passing through the "
                    "PCIe system bus will experience increased latency "
                    "compared to a single slot execution layout."),
        "prevention": ("You must hard-code model partitioning scripts "
                        "to optimize execution allocations based on "
                        "VRAM capacity. Load the core attention layers "
                        "and high-frequency context loops entirely "
                        "inside the primary card's high-speed VRAM "
                        "allocation window to prevent excessive data "
                        "bouncing over the shared x8 bus lane."),
        "tags": ["pcie", "dual-gpu", "x8-x8", "x870e-creator", "lane-split",
                 "bifurcation", "model-partitioning"],
        "spec_ref": "master spec §14 (gotcha 1 verbatim)",
        "related_verbs": [
            "sovereign-osctl pcie-lanes --json",
            "sovereign-osctl gpu-card-advisor --json",
            "sovereign-osctl model-build plan <base> --recipe quantize-awq-int4",
        ],
    },
    {
        "id": "G-02",
        "name": "Secure Boot Machine Owner Key (MOK) Blockades",
        "context": ("If your system motherboard has Secure Boot fully "
                     "initialized in the UEFI firmware subsystem, your "
                     "custom-built 6.12-znver5 kernel along with the "
                     "compiled ZFS/NVIDIA kernel modules will "
                     "immediately be rejected by the bootloader at "
                     "startup, causing a catastrophic kernel panic or "
                     "silent boot failure."),
        "gotcha": ("Third-party binary objects compiled outside "
                    "distribution automated code signers lack "
                    "recognized cryptographic validation keys."),
        "prevention": ("You must generate a local Machine Owner Key "
                        "(MOK) cryptographic pair using openssl. Enroll "
                        "the public certificate target into the "
                        "physical system firmware via the mokutil "
                        "console utility during initialization, and "
                        "force your custom build wrappers to sign the "
                        "resulting kernel image and DKMS artifacts "
                        "before reboot sequences are initiated."),
        "tags": ["secure-boot", "mok", "uefi", "custom-kernel",
                 "zfs-dkms", "nvidia-dkms", "signing", "mokutil"],
        "spec_ref": "master spec §14 (gotcha 2 verbatim)",
        "related_verbs": [
            "# openssl req -new -x509 -newkey rsa:2048 -keyout MOK.key "
            "-out MOK.crt -nodes -days 3650 -subj '/CN=Sovereign Node/'",
            "# mokutil --import MOK.crt",
            "sovereign-osctl bios-directives show secure-boot",
        ],
    },
    {
        "id": "G-03",
        "name": "OPNsense WAN/LAN Bridging and Tetragon Interface Dropouts",
        "context": ("Your network design separates management traffic "
                     "(Intel 2.5GbE) from data processing paths "
                     "(Marvell 10GbE). If your OPNsense/SD-WAN firewall "
                     "dynamically re-shuffles interface addresses or "
                     "drops a lease connection along the management "
                     "path, the system loopback hooks used by the "
                     "Tetragon socket stream can experience buffer "
                     "disconnects."),
        "gotcha": ("If Tetragon drops its connection to the system "
                    "logging pipeline during a network reconfiguration "
                    "event, the guardian-core script will stall on its "
                    "read loop, blinding your real-time exploit "
                    "containment system."),
        "prevention": ("The guardian-core.service systemd unit file "
                        "must include explicit service binding controls "
                        "(BindsTo=tetragon.service) and include health "
                        "checking routines that instantly restart the "
                        "security loop if the local UNIX socket "
                        "encounters an end-of-file (EOF) exception."),
        "tags": ["network", "opnsense", "tetragon", "guardian-core",
                 "binds-to", "eof", "socket", "dual-nic"],
        "spec_ref": "master spec §14 (gotcha 3 verbatim)",
        "related_verbs": [
            "sovereign-osctl tetragon-status --json",
            "sovereign-osctl net-state --json",
            "systemctl cat sovereign-guardian-core",
        ],
    },
]


# ── Loading + filtering ───────────────────────────────────────────
def load_state(overlay_path: Path | None) -> tuple[list[dict], list[dict], dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    questions = list(ARCHITECTURE_QUESTIONS)
    gotchas = list(ARCHITECTURE_GOTCHAS)
    if load_with_overlay is not None:
        loaded = load_with_overlay(
            "architecture-qa",
            {"questions": [], "gotchas": []},
            explicit_path=overlay_path,
        )
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
        if loaded.get("questions"):
            questions = list(loaded["questions"])
        if loaded.get("gotchas"):
            gotchas = list(loaded["gotchas"])
    return questions, gotchas, meta


def filter_tag(items: list[dict], tag: str | None) -> list[dict]:
    if not tag:
        return items
    return [x for x in items if isinstance(x, dict)
            and tag in (x.get("tags") or [])]


def resolve_by_id(
    questions: list[dict], gotchas: list[dict], item_id: str,
) -> tuple[dict | None, str]:
    """Returns (item_dict, kind) or (None, ''). kind ∈ {'question', 'gotcha'}."""
    for q in questions:
        if isinstance(q, dict) and q.get("id") == item_id:
            return q, "question"
    for g in gotchas:
        if isinstance(g, dict) and g.get("id") == item_id:
            return g, "gotcha"
    return None, ""


def search_items(
    questions: list[dict], gotchas: list[dict], needle: str,
) -> tuple[list[dict], list[dict]]:
    n = needle.lower()
    qm = [q for q in questions if isinstance(q, dict) and (
        n in (q.get("question") or "").lower()
        or n in (q.get("answer") or "").lower()
        or any(n in t for t in (q.get("tags") or []))
    )]
    gm = [g for g in gotchas if isinstance(g, dict) and (
        n in (g.get("name") or "").lower()
        or n in (g.get("context") or "").lower()
        or n in (g.get("gotcha") or "").lower()
        or n in (g.get("prevention") or "").lower()
        or any(n in t for t in (g.get("tags") or []))
    )]
    return qm, gm


# ── Renderers ─────────────────────────────────────────────────────
def render_questions_human(items: list[dict]) -> str:
    lines = ["── R355 architecture-qa questions (master spec §13 verbatim) ──"]
    for q in items:
        lines.append("")
        lines.append(f"  [{q.get('id')}]  {q.get('question')}")
        lines.append(f"    tags: {', '.join(q.get('tags') or [])}")
        lines.append(f"    spec: {q.get('spec_ref')}")
        lines.append(f"    → sovereign-osctl architecture-qa show {q.get('id')}")
    return "\n".join(lines) + "\n"


def render_gotchas_human(items: list[dict]) -> str:
    lines = ["── R355 architecture-qa gotchas (master spec §14 verbatim) ──"]
    for g in items:
        lines.append("")
        lines.append(f"  [{g.get('id')}]  {g.get('name')}")
        lines.append(f"    tags: {', '.join(g.get('tags') or [])}")
        lines.append(f"    spec: {g.get('spec_ref')}")
        lines.append(f"    → sovereign-osctl architecture-qa show {g.get('id')}")
    return "\n".join(lines) + "\n"


def render_question_show(q: dict) -> str:
    lines = [f"── R355 question: {q.get('id')} (master spec §13) ──"]
    lines.append("")
    lines.append("  QUESTION (operator verbatim):")
    for ln in (q.get("question") or "").split("\n"):
        lines.append(f"    {ln}")
    lines.append("")
    lines.append("  ANSWER (operator verbatim):")
    # word-wrap-ish for readability
    body = q.get("answer") or ""
    cur = "    "
    for word in body.split():
        if len(cur) + len(word) > 76 and cur.strip():
            lines.append(cur.rstrip())
            cur = "    "
        cur += word + " "
    if cur.strip():
        lines.append(cur.rstrip())
    lines.append("")
    lines.append(f"  spec ref: {q.get('spec_ref')}")
    lines.append(f"  tags:     {', '.join(q.get('tags') or [])}")
    return "\n".join(lines) + "\n"


def render_gotcha_show(g: dict) -> str:
    lines = [f"── R355 gotcha: {g.get('id')} — {g.get('name')} (master spec §14) ──"]
    for field, label in (
        ("context", "CONTEXT"),
        ("gotcha", "THE GOTCHA"),
        ("prevention", "PREVENTION"),
    ):
        body = g.get(field) or ""
        lines.append("")
        lines.append(f"  {label} (operator verbatim):")
        cur = "    "
        for word in body.split():
            if len(cur) + len(word) > 76 and cur.strip():
                lines.append(cur.rstrip())
                cur = "    "
            cur += word + " "
        if cur.strip():
            lines.append(cur.rstrip())
    if g.get("related_verbs"):
        lines.append("")
        lines.append("  RELATED OPERATOR VERBS:")
        for v in g["related_verbs"]:
            lines.append(f"    $ {v}")
    lines.append("")
    lines.append(f"  spec ref: {g.get('spec_ref')}")
    lines.append(f"  tags:     {', '.join(g.get('tags') or [])}")
    return "\n".join(lines) + "\n"


# ── Main ──────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="architecture-qa.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    for verb in ("questions", "gotchas"):
        sp = sub.add_parser(verb)
        sp.add_argument("--tag")
        sp.add_argument("--config", type=Path)
        spg = sp.add_mutually_exclusive_group()
        spg.add_argument("--json", dest="fmt", action="store_const", const="json")
        spg.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")

    ps = sub.add_parser("show")
    ps.add_argument("item_id")
    ps.add_argument("--config", type=Path)
    psg = ps.add_mutually_exclusive_group()
    psg.add_argument("--json", dest="fmt", action="store_const", const="json")
    psg.add_argument("--human", dest="fmt", action="store_const", const="human")
    ps.set_defaults(fmt="json")

    psr = sub.add_parser("search")
    psr.add_argument("needle")
    psr.add_argument("--config", type=Path)
    psrg = psr.add_mutually_exclusive_group()
    psrg.add_argument("--json", dest="fmt", action="store_const", const="json")
    psrg.add_argument("--human", dest="fmt", action="store_const", const="human")
    psr.set_defaults(fmt="json")

    args = p.parse_args(argv)
    questions, gotchas, meta = load_state(getattr(args, "config", None))

    if args.cmd == "questions":
        items = filter_tag(questions, getattr(args, "tag", None))
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "tag_filter": getattr(args, "tag", None),
                "question_count": len(items),
                "questions": items,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_questions_human(items), end="")
        return 0 if items else 1

    if args.cmd == "gotchas":
        items = filter_tag(gotchas, getattr(args, "tag", None))
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "tag_filter": getattr(args, "tag", None),
                "gotcha_count": len(items),
                "gotchas": items,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_gotchas_human(items), end="")
        return 0 if items else 1

    if args.cmd == "show":
        item, kind = resolve_by_id(questions, gotchas, args.item_id)
        if item is None:
            print(json.dumps({
                "error": f"unknown id: {args.item_id}",
                "known_questions": [q.get("id") for q in questions if isinstance(q, dict)],
                "known_gotchas":   [g.get("id") for g in gotchas if isinstance(g, dict)],
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 1
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "kind": kind,
                "item": item,
                "overlay": meta,
            }, indent=2))
        else:
            print((render_question_show if kind == "question"
                   else render_gotcha_show)(item), end="")
        return 0

    if args.cmd == "search":
        qm, gm = search_items(questions, gotchas, args.needle)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "needle": args.needle,
                "question_match_count": len(qm),
                "gotcha_match_count": len(gm),
                "matched_questions": qm,
                "matched_gotchas": gm,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R355 search: '{args.needle}' ──")
            print(f"  {len(qm)} question match(es), {len(gm)} gotcha match(es)")
            for q in qm:
                print(f"    [Q] {q.get('id')}: {(q.get('question') or '')[:60]}…")
            for g in gm:
                print(f"    [G] {g.get('id')}: {g.get('name')}")
        return 0 if (qm or gm) else 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
