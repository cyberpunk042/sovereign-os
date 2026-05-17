#!/usr/bin/env python3
"""scripts/research/loop.py — R287 (E1.M19).

Operator-named (§1b mandate row, verbatim): "Hardware-exploit-to-the-
max research loop (continuously evolving SDD + TDD as new BitNet /
DFlash / VPDPBUSD findings land; 'research mode' verb that surfaces
upstream changes from bitnet.cpp + transformers + vllm)".

The verb is operator-pull "what's worth investigating right now"
across the AVX-512 / Zen5 fast-path stack — bitnet.cpp (ternary
VPDPBUSD), DFlash (speculative decoding), transformers, vllm, trl,
Wasmtime (znver5 AOT), and the operator's choice of additional
upstreams via overlay.

Read-only by default. Two modes:

  research-loop status  → for each tracked upstream, compare the
                          declared "operator baseline" version against
                          what's installed on this host RIGHT NOW.
                          Surface drift / stale / unknown findings as
                          a structured JSON report. No network calls.

  research-loop topics  → enumerate research topics (operator-pull
                          investigation prompts) with anchor links to
                          the relevant SDDs + mandate Modules. Helps
                          an agent's CoT pick what to investigate next.

Operator-overlay (R283 / SDD-030 adoption): the baseline pinning
file lives at `/etc/sovereign-os/research-loop.toml` (or
`SOVEREIGN_OS_OVERLAY_RESEARCH_LOOP=<path>` env, or `--config <p>`).
DEFAULTS shipped in this script are a sensible starting list; the
operator can add/remove/replace entirely.

No-network-required: status mode runs entirely against the local
host (`pip show`, `dpkg-query`, `git -C <clone> describe`, etc).
A future round can add an `--online` flag that does HTTP HEAD against
upstream tag endpoints; out of scope for R287.

Exit codes:
  0  report emitted
  1  ≥1 tracked component is in a "stale" verdict (operator wants
     to investigate)
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
try:
    from operator_overlay import load_with_overlay  # type: ignore
except Exception:  # pragma: no cover - helper is shipped in-repo
    load_with_overlay = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R287"
SDD_VECTOR = "E1.M19"


# ── Default tracked upstreams (operator-overlay can replace) ─────────
#
# Each entry: name, kind (pip / apt / binary / git), id (package/binary
# name or clone path), baseline (operator-pinned "known good"), notes.
# Keep this tight — the operator overlay grows it.
#
# Operator pinned baselines reflect the version that the in-repo
# scripts have been smoke-tested against. Drift = something to look
# at; not necessarily broken.
DEFAULT_TRACK = [
    # Master-spec § 17.1 ternary fast-path (bitnet.cpp + T-MAC kernels).
    {
        "name": "bitnet-cpp",
        "kind": "binary",
        "id": "bitnet-cli",
        "baseline": "(not yet pinned — install drives the first round)",
        "notes": "ternary VPDPBUSD fast path; build via scripts/pulse/build-bitnet.sh",
    },
    # Master-spec § 20 Wasm-AOT pipeline (Wasmtime znver5).
    {
        "name": "wasmtime",
        "kind": "binary",
        "id": "wasmtime",
        "baseline": "30.0.0",
        "notes": "znver5 AOT target; enforced via WASMTIME_COMPARE_OPTIONS",
    },
    # HF reference runtimes.
    {
        "name": "transformers",
        "kind": "pip",
        "id": "transformers",
        "baseline": "4.50.0",
        "notes": "HF reference runtime; pinned via operator-deps.toml",
    },
    {
        "name": "vllm",
        "kind": "pip",
        "id": "vllm",
        "baseline": "0.7.0",
        "notes": "Oracle-tier RLM serving",
    },
    {
        "name": "trl",
        "kind": "pip",
        "id": "trl",
        "baseline": "0.13.0",
        "notes": "SFT/DPO training pipeline",
    },
    {
        "name": "huggingface_hub",
        "kind": "pip",
        "id": "huggingface_hub",
        "baseline": "0.29.0",
        "notes": "model fetcher",
    },
    {
        "name": "lm-eval",
        "kind": "pip",
        "id": "lm-eval",
        "baseline": "0.4.4",
        "notes": "R232 eval harness",
    },
    {
        "name": "selfdef-cli",
        "kind": "binary",
        "id": "selfdefctl",
        "baseline": "(operator-built from selfdef checkout)",
        "notes": "selfdef control plane; provides MCP TCP per SD-R94",
    },
]


# ── Default research topics (operator-overlay can replace) ───────────
#
# Each topic: name, mandate_anchor (which mandate Module), sdd_anchor
# (which SDD documents it), question (what to investigate), signal
# (what to look at locally before going online). Topics are operator-
# pull — surfacing the question is the value.
DEFAULT_TOPICS = [
    {
        "name": "bitnet-cpp-upstream-deltas",
        "mandate_anchor": "E1.M18 (1-bit/ternary ZMM probe)",
        "sdd_anchor": "SDD-027 (Pulse algorithmic foundation)",
        "question": "Has bitnet.cpp shipped new ternary kernels since R280? Faster VPDPBUSD path?",
        "signal": "git -C $REPO log --oneline --since=4w in the bitnet.cpp clone; cross-ref scripts/hardware/zmm-ternary-probe.py.",
    },
    {
        "name": "wasmtime-znver5-target-stability",
        "mandate_anchor": "E1.M17 (Wasm-to-AVX-512 AOT)",
        "sdd_anchor": "SDD-029 (Hardware-stack consolidation Z-17)",
        "question": "Is wasmtime --target znver5 still the recommended cwasm target for Zen 5? Cranelift opcode coverage growing?",
        "signal": "wasmtime --version + scripts/hardware/wasm-aot-enforcer.py output. Cross-ref WASMTIME_COMPARE_OPTIONS env enforcement.",
    },
    {
        "name": "transformers-avx512-codepath",
        "mandate_anchor": "E1.M14 (AVX-512 utilization probe)",
        "sdd_anchor": "SDD-029 (Hardware-stack consolidation)",
        "question": "Does transformers >= baseline now use AVX-512 VNNI in any default codepath we're missing?",
        "signal": "pip show transformers; check for cpu-extension-aware imports in transformers/utils.",
    },
    {
        "name": "vllm-tensor-parallel-dual-gpu",
        "mandate_anchor": "E1.M13 (RTX 3090 + RTX PRO 6000 dual-card)",
        "sdd_anchor": "SDD-029 (Hardware-stack consolidation Z-18)",
        "question": "Does vllm support the asymmetric VRAM split (24 GB + 98 GB) for tensor-parallel serving without manual layer pinning?",
        "signal": "vllm version + scripts/hardware/gpu-card-advisor.py output.",
    },
    {
        "name": "dflash-spec-decode-integration",
        "mandate_anchor": "E5.M8 (Speculative-decoding integration, ✓ prior)",
        "sdd_anchor": "scripts/inference/dflash-wrap.sh",
        "question": "Has DFlash shipped operator-facing tunables since R157? Worth re-pinning?",
        "signal": "scripts/inference/dflash-wrap.sh --help; cross-ref scripts/inference/router.py routing weights.",
    },
    {
        "name": "asus-x870e-bios-microcode-deltas",
        "mandate_anchor": "E1.M2 (BIOS + ASUS X870E-CREATOR WIFI advisories)",
        "sdd_anchor": "SDD-029 (Hardware-stack consolidation Z-14)",
        "question": "ASUS BIOS releases since R251 — XMP/EXPO behaviour deltas? PCIe 5.0 stability fixes? OC headroom changes?",
        "signal": "sovereign-osctl bios-info --json + scripts/hardware/known-boards lookup vs ASUS support page (operator-driven online).",
    },
    {
        "name": "psu-oc-mode-real-world-deviance",
        "mandate_anchor": "E1.M5 (PSU + UPS + wattage budget + OC mode)",
        "sdd_anchor": "SDD-029 (Hardware-stack consolidation Z-19)",
        "question": "be Quiet! Dark Power Pro 13 1600W in OC-mode — how does the real-time wattage sampler (R258) deviate from the rated budget under dual-GPU + CPU + DDR5 load?",
        "signal": "sovereign-osctl power-status --json + R258 sampler 24h rollup.",
    },
    {
        "name": "ternary-quant-quality-vs-fp16",
        "mandate_anchor": "E5.M7 (Model variants + quantizations)",
        "sdd_anchor": "SDD-027 (Pulse algorithmic foundation)",
        "question": "For models in our registry, what's the eval gap between FP16 baseline and ternary (1.58-bit)? Worth fast-path-only on which workloads?",
        "signal": "lm-eval results vs FP16 ref on the operator's eval set.",
    },
]


# ── Local-state probes (no-network) ──────────────────────────────────
def _pip_show(pkg: str) -> dict[str, Any]:
    if shutil.which("pip") is None and shutil.which("pip3") is None:
        return {"installed": None, "version": None, "error": "pip not found"}
    pip_bin = shutil.which("pip3") or shutil.which("pip")
    try:
        r = subprocess.run(
            [pip_bin, "show", pkg],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"installed": None, "version": None, "error": f"pip-show: {e}"}
    if r.returncode != 0:
        return {"installed": False, "version": None}
    version = None
    for line in r.stdout.splitlines():
        if line.startswith("Version:"):
            version = line.split(":", 1)[1].strip()
            break
    return {"installed": True, "version": version}


def _binary_version(name: str) -> dict[str, Any]:
    path = shutil.which(name)
    if not path:
        return {"installed": False, "version": None, "path": None}
    version = None
    for flag in ("--version", "-V", "version"):
        try:
            r = subprocess.run(
                [path, flag],
                capture_output=True, text=True, timeout=5, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        out = (r.stdout or r.stderr or "").strip().splitlines()
        if out:
            version = out[0].strip()
            break
    return {"installed": True, "version": version, "path": path}


def _dpkg_query(pkg: str) -> dict[str, Any]:
    if shutil.which("dpkg-query") is None:
        return {"installed": None, "version": None, "error": "dpkg-query not found"}
    try:
        r = subprocess.run(
            ["dpkg-query", "-W", "-f=${Version}", pkg],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"installed": None, "version": None, "error": str(e)}
    if r.returncode != 0:
        return {"installed": False, "version": None}
    return {"installed": True, "version": r.stdout.strip() or None}


def _git_describe(repo_dir: Path) -> dict[str, Any]:
    if not (repo_dir / ".git").exists():
        return {"installed": False, "version": None, "error": "not a git clone"}
    try:
        r = subprocess.run(
            ["git", "-C", str(repo_dir), "describe", "--always", "--dirty"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"installed": None, "version": None, "error": str(e)}
    if r.returncode != 0:
        return {"installed": False, "version": None}
    return {"installed": True, "version": r.stdout.strip() or None, "path": str(repo_dir)}


def probe(entry: dict) -> dict[str, Any]:
    kind = entry["kind"]
    ident = entry["id"]
    if kind == "pip":
        return _pip_show(ident)
    if kind == "binary":
        return _binary_version(ident)
    if kind == "apt":
        return _dpkg_query(ident)
    if kind == "git":
        return _git_describe(Path(ident).expanduser())
    return {"installed": None, "version": None, "error": f"unknown kind: {kind}"}


# ── Verdict logic ────────────────────────────────────────────────────
def verdict_for(entry: dict, probe_result: dict) -> str:
    """Operator-readable verdict from probe vs baseline."""
    baseline = entry.get("baseline", "")
    if probe_result.get("error"):
        return "probe-error"
    inst = probe_result.get("installed")
    if inst is False:
        return "not-installed"
    if inst is None:
        return "probe-unavailable"
    version = probe_result.get("version") or ""
    if baseline.startswith("("):  # "(not yet pinned ...)" etc.
        return "baseline-unset"
    if not version:
        return "version-unknown"
    if version.split()[0] == baseline:
        return "matches-baseline"
    return "drift"  # operator wants to investigate


# ── Topic resolution (operator-pull list of research prompts) ────────
def topics(overlay_topics: list[dict] | None) -> list[dict]:
    if overlay_topics is None:
        return list(DEFAULT_TOPICS)
    return list(overlay_topics)


# ── Manifest assembly ────────────────────────────────────────────────
def build_status(overlay_path: Path | None) -> dict[str, Any]:
    overlay_meta = {"_source": "(defaults)", "_overlay_keys": []}
    track = list(DEFAULT_TRACK)
    if load_with_overlay is not None:
        cfg = load_with_overlay(
            "research-loop",
            {"track": [], "topics": []},
            explicit_path=overlay_path,
        )
        overlay_meta["_source"] = cfg.get("_source", overlay_meta["_source"])
        overlay_meta["_overlay_keys"] = cfg.get("_overlay_keys", [])
        if cfg.get("_parse_error"):
            overlay_meta["_parse_error"] = cfg["_parse_error"]
        if cfg.get("track"):
            track = list(cfg["track"])

    rows = []
    stale_seen = False
    for e in track:
        p = probe(e)
        v = verdict_for(e, p)
        if v == "drift":
            stale_seen = True
        rows.append(
            {
                "name": e["name"],
                "kind": e["kind"],
                "id": e["id"],
                "baseline": e.get("baseline", ""),
                "notes": e.get("notes", ""),
                "probe": p,
                "verdict": v,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        "tracked_count": len(rows),
        "stale": stale_seen,
        "tracked": rows,
        "overlay": overlay_meta,
    }


def build_topics(overlay_path: Path | None) -> dict[str, Any]:
    overlay_meta = {"_source": "(defaults)", "_overlay_keys": []}
    topic_list = list(DEFAULT_TOPICS)
    if load_with_overlay is not None:
        cfg = load_with_overlay(
            "research-loop",
            {"track": [], "topics": []},
            explicit_path=overlay_path,
        )
        overlay_meta["_source"] = cfg.get("_source", overlay_meta["_source"])
        overlay_meta["_overlay_keys"] = cfg.get("_overlay_keys", [])
        if cfg.get("_parse_error"):
            overlay_meta["_parse_error"] = cfg["_parse_error"]
        if cfg.get("topics"):
            topic_list = list(cfg["topics"])
    return {
        "schema_version": SCHEMA_VERSION,
        "round": ROUND,
        "sdd_vector": SDD_VECTOR,
        "topic_count": len(topic_list),
        "topics": topic_list,
        "overlay": overlay_meta,
    }


# ── Human render ─────────────────────────────────────────────────────
def render_status_human(doc: dict) -> str:
    lines = ["── R287 sovereign-os research-loop status (E1.M19) ──"]
    lines.append(f"  schema_version: {doc['schema_version']}")
    lines.append(f"  tracked:        {doc['tracked_count']}")
    lines.append(f"  stale:          {doc['stale']}")
    lines.append("")
    for r in doc["tracked"]:
        mark = {
            "matches-baseline": "OK ",
            "drift": "?? ",
            "not-installed": "-- ",
            "baseline-unset": ".. ",
            "probe-error": "!! ",
            "probe-unavailable": "?? ",
            "version-unknown": "?? ",
        }.get(r["verdict"], "?? ")
        vsn = (r["probe"].get("version") or "").strip()
        lines.append(f"  [{mark}] {r['name']:24s} kind={r['kind']:6s} "
                     f"baseline={r['baseline']:20s} got={vsn}")
        if r["notes"]:
            lines.append(f"             notes: {r['notes']}")
    return "\n".join(lines) + "\n"


def render_topics_human(doc: dict) -> str:
    lines = ["── R287 sovereign-os research-loop topics (E1.M19) ──"]
    lines.append(f"  topic_count: {doc['topic_count']}")
    lines.append("")
    for t in doc["topics"]:
        lines.append(f"  • {t['name']}")
        lines.append(f"      mandate: {t.get('mandate_anchor', '')}")
        lines.append(f"      sdd:     {t.get('sdd_anchor', '')}")
        lines.append(f"      Q:       {t.get('question', '')}")
        lines.append(f"      signal:  {t.get('signal', '')}")
        lines.append("")
    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="research-loop.py")
    sub = p.add_subparsers(dest="verb", required=True)

    ps = sub.add_parser("status", help="tracked-upstream local-state report")
    ps.add_argument("--config", type=Path, metavar="PATH")
    fmt = ps.add_mutually_exclusive_group()
    fmt.add_argument("--json", dest="fmt", action="store_const", const="json")
    fmt.add_argument("--human", dest="fmt", action="store_const", const="human")
    ps.set_defaults(fmt="json")

    pt = sub.add_parser("topics", help="research-topic enumeration")
    pt.add_argument("--config", type=Path, metavar="PATH")
    fmt2 = pt.add_mutually_exclusive_group()
    fmt2.add_argument("--json", dest="fmt", action="store_const", const="json")
    fmt2.add_argument("--human", dest="fmt", action="store_const", const="human")
    pt.set_defaults(fmt="json")

    args = p.parse_args(argv)

    if args.verb == "status":
        doc = build_status(args.config)
        if args.fmt == "json":
            print(json.dumps(doc, indent=2))
        else:
            print(render_status_human(doc), end="")
        return 1 if doc["stale"] else 0

    if args.verb == "topics":
        doc = build_topics(args.config)
        if args.fmt == "json":
            print(json.dumps(doc, indent=2))
        else:
            print(render_topics_human(doc), end="")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
