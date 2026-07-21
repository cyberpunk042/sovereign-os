#!/usr/bin/env python3
"""``sovereign-osctl chromofold`` — read-only, honest-degrade CLI for the
ChromoFold GPU-resident compressed-domain search engine (SDD-400).

Mirrors the native engine's ``chromofold info`` / ``chromofold selftest`` on the
sovereign-os side, with ZERO GPU and ZERO mutation:

* ``info``     — print the capability descriptor (which primitives the ABI
                 offers, the library/headers, the resolved engine root).
* ``selftest`` — the pure-seam, no-GPU round-trip: validate the committed
                 reference fixtures' header seam (4-byte magic + u32-LE version)
                 against the engine's own ``chromofold_capability.json``
                 (mirroring ``packaging/seam_check.c``).
* ``count`` / ``locate`` / ``predict`` — the CPU-native FM-index (provenance-B):
                 real compressed-domain search over a ``--corpus`` token stream,
                 by shelling the ``sovereign-chromofold`` Rust binary (no GPU, no
                 native library); honest-degrades (exit 3) when it is not built.

Source of truth is the native ``packaging/chromofold_capability.json`` in the
resident engine checkout, resolved from ``CHROMOFOLD_ROOT`` (else
``WARP_SHADERS_ROOT``) — the root contract the native descriptor declares
(SDD-400 Q-400-D). These are READ-ONLY diagnostics: when no checkout is resident
they **honestly report the offline state and exit 0** (a successful status
report, like ``warp status``) — never fabricating a capability or a search result
(SB-077). Only a resident-but-broken fixture makes ``selftest`` fail (exit 1).
Stdlib only; no GPU; no network; no mutation.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT_ENV = "CHROMOFOLD_ROOT"
ROOT_DEFAULT_ENV = "WARP_SHADERS_ROOT"
CAPABILITY_REL = "packaging/chromofold_capability.json"


def engine_root() -> Path | None:
    """Resolve the resident engine checkout: ``CHROMOFOLD_ROOT`` then
    ``WARP_SHADERS_ROOT``. ``None`` means honest-degrade (nothing resident)."""
    for key in (ROOT_ENV, ROOT_DEFAULT_ENV):
        val = os.environ.get(key, "").strip()
        if val:
            return Path(val)
    return None


def _capability_path(root: Path) -> Path:
    return root / CAPABILITY_REL


def load_capability(root: Path) -> dict | None:
    """Parse the native capability descriptor, or ``None`` if it isn't there."""
    path = _capability_path(root)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _offline_note() -> str:
    return (
        "chromofold: offline — no engine checkout resident "
        f"(${ROOT_ENV} / ${ROOT_DEFAULT_ENV} unset or missing "
        f"{CAPABILITY_REL}). Honest-degrade."
    )


def cmd_info(json_out: bool) -> int:
    root = engine_root()
    cap = load_capability(root) if root else None
    if root is None or cap is None:
        # honest offline status report — a successful read, exit 0.
        if json_out:
            print(json.dumps({"availability": "offline", "engine_root": None}))
        else:
            print(_offline_note())
        return 0

    resolved = {
        "engine_root": str(root),
        "library_present": (root / "build" / cap.get("library", "libchromofold.so")).is_file(),
        "availability": "resident",
    }
    if json_out:
        print(json.dumps({**cap, "resolved": resolved}, indent=2))
        return 0

    print(f"chromofold — {cap.get('note', '').split('.')[0]}")
    print(f"  abi_version : {cap.get('abi_version')}")
    print(f"  engine_root : {resolved['engine_root']}")
    print(f"  library     : {cap.get('library')} "
          f"({'built' if resolved['library_present'] else 'not built'})")
    print(f"  headers     : {cap.get('header_primary')}, {cap.get('header_search')}")
    print("  capabilities:")
    for c in cap.get("capabilities", []):
        first = "  <- sovereign-os first (Lane A)" if c.get("sovereign_os_first") else ""
        print(f"    - {c['id']:<16} {c['fn']:<28} [{c['header']}]{first}")
    return 0


def cmd_selftest(json_out: bool) -> int:
    root = engine_root()
    cap = load_capability(root) if root else None
    if root is None or cap is None:
        # nothing resident to verify — honest offline, not a failure (exit 0),
        # mirroring the Rust `chromofold selftest` honest-degrade PASS.
        if json_out:
            print(json.dumps({"selftest": "offline", "engine_root": None}))
        else:
            print(f"chromofold selftest: OFFLINE — nothing resident to verify. {_offline_note()}")
        return 0

    failures: list[str] = []
    checked = 0
    for ref in cap.get("reference_fixtures", []):
        rel = ref.get("fixture")
        magic = ref.get("magic", "")
        version = ref.get("version")
        if not rel or not magic or version is None:
            continue
        path = root / rel
        try:
            head = path.read_bytes()[:8]
        except OSError as e:
            failures.append(f"{rel}: unreadable ({e})")
            continue
        if len(head) < 8:
            failures.append(f"{rel}: short header ({len(head)} bytes)")
            continue
        got_magic = head[:4].decode("ascii", errors="replace")
        got_version = int.from_bytes(head[4:8], "little")
        if got_magic != magic:
            failures.append(f"{rel}: magic {got_magic!r} != {magic!r}")
        elif got_version != version:
            failures.append(f"{rel}: version {got_version} != {version}")
        else:
            checked += 1

    passed = not failures
    if json_out:
        print(json.dumps({"selftest": "pass" if passed else "fail",
                          "checked": checked, "failures": failures}))
        return 0 if passed else 1
    if passed:
        print(f"chromofold selftest: PASS — {checked} reference fixture header(s) "
              f"match the capability contract (no GPU)")
        return 0
    print("chromofold selftest: FAIL", file=sys.stderr)
    for f in failures:
        print(f"  - {f}", file=sys.stderr)
    return 1


def fm_binary() -> str | None:
    """Locate the `sovereign-chromofold` Rust binary (the CPU FM-index,
    provenance-B). An explicit ``$CHROMOFOLD_FM_BIN`` wins (and is honoured
    strictly — a set-but-missing path honest-degrades rather than silently
    falling back); otherwise the repo `target/{release,debug}` build is used."""
    env = os.environ.get("CHROMOFOLD_FM_BIN", "").strip()
    if env:
        return env if Path(env).is_file() else None
    repo = Path(__file__).resolve().parents[2]
    for prof in ("release", "debug"):
        cand = repo / "target" / prof / "sovereign-chromofold"
        if cand.is_file():
            return str(cand)
    return None


def cmd_fm(kind: str, corpus: str | None, query: str | None, json_out: bool) -> int:
    """count / locate / predict via the CPU FM-index binary, or honest-degrade."""
    binp = fm_binary()
    if binp is None:
        if json_out:
            print(json.dumps({kind: "unavailable", "reason": "fm-binary-not-built"}))
        else:
            print(
                "chromofold: CPU FM-index binary not built — run "
                "`cargo build -p sovereign-chromofold` or set $CHROMOFOLD_FM_BIN. "
                "Honest-degrade (no fabricated result).",
                file=sys.stderr,
            )
        return 3  # honest-degrade: the search tool is not present (warp-render pattern)
    query_key = "--context" if kind == "predict" else "--pattern"
    if not corpus:
        print(f"chromofold {kind}: --corpus <file> is required", file=sys.stderr)
        return 1
    if not query:
        print(f"chromofold {kind}: {query_key} \"<token ids>\" is required", file=sys.stderr)
        return 1
    cmd = [binp, kind, "--corpus", corpus, query_key, query]
    if json_out:
        cmd.append("--json")
    try:
        return subprocess.run(cmd, check=False).returncode
    except OSError as e:
        print(f"chromofold {kind}: could not run {binp}: {e}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sovereign-osctl chromofold", description=__doc__)
    p.add_argument(
        "command",
        nargs="?",
        default="info",
        choices=["info", "selftest", "count", "locate", "predict"],
    )
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--corpus", help="token-stream file (whitespace/comma-separated u32 ids)")
    p.add_argument("--pattern", help="pattern token ids (count/locate)")
    p.add_argument("--context", help="context token ids (predict)")
    args = p.parse_args(argv)
    if args.command == "selftest":
        return cmd_selftest(args.json)
    if args.command in ("count", "locate", "predict"):
        query = args.context if args.command == "predict" else args.pattern
        return cmd_fm(args.command, args.corpus, query, args.json)
    return cmd_info(args.json)


if __name__ == "__main__":
    sys.exit(main())
