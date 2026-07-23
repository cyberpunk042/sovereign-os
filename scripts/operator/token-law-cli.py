#!/usr/bin/env python3
"""scripts/operator/token-law-cli.py — the `sovereign-osctl token-law` verb
(M00155 F00795, SDD-510). The operator handle on the M00117 token-law engine's
**mask-layer selection**: which named laws (grammar / schema / tool / safety /
policy) are active, and — over a live `sovereign-gatewayd` — what mask they fuse
to at a prefix.

The fusion is checkpoint-free (no model): it depends only on the layer sources +
the supplied vocab, so `token-law fuse` inspects the deterministic-cortex
DECISION directly, via the sanctioned `POST /v1/data-plane/token-law/fuse` route
(F00797). `token-law layers` needs no daemon at all — it just resolves + prints
the active selection.

Mask-layer selection precedence (F00793/F00794/F00795):
  --token-law-mask-layers <csv>   (this flag)                      highest
  SOVEREIGN_TOKEN_LAW_MASK_LAYERS  (env var)
  token_law_engine_mask_layers     (the active runtime profile knob)
  all layers                       (default)                       lowest

Layer names: the engine's real planes `grammar` / `regex` / `denylist` /
`regex_denylist` / `policy`, with the milestone aliases `schema`→grammar,
`tool`→regex, `safety`→denylist+regex_denylist.

Sovereignty: stdlib + the repo's YAML only (for the profile read); urllib for
the loopback probe. Every daemon failure degrades to a structured error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
DEFAULT_ADDR = "127.0.0.1:8787"

# name (real or milestone alias) → the canonical planes it enables
_ALIASES = {
    "grammar": ["grammar"], "schema": ["grammar"],
    "regex": ["regex"], "tool": ["regex"],
    "denylist": ["denylist"],
    "regex_denylist": ["regex_denylist"], "regex-denylist": ["regex_denylist"],
    "safety": ["denylist", "regex_denylist"],
    "policy": ["policy"],
}
_CANON = ["grammar", "regex", "denylist", "regex_denylist", "policy"]


def _resolve_selection(flag: str | None) -> tuple[list[str], str]:
    """Resolve the active mask layers + the source that won, per precedence.
    Returns (canonical_layer_names_in_order, source). An empty/absent value at a
    level falls through to the next; the final fallback is all layers."""
    csv, source = None, "default(all)"
    if flag is not None:
        csv, source = flag, "--token-law-mask-layers"
    elif os.environ.get("SOVEREIGN_TOKEN_LAW_MASK_LAYERS"):
        csv, source = os.environ["SOVEREIGN_TOKEN_LAW_MASK_LAYERS"], "env"
    else:
        prof = _profile_knob()
        if prof:
            csv, source = prof, "profile"
    active: set[str] = set()
    if csv is None or not csv.strip():
        active = set(_CANON)
        if source not in ("--token-law-mask-layers", "env", "profile"):
            source = "default(all)"
    else:
        for tok in csv.split(","):
            t = tok.strip().lower()
            if not t:
                continue
            if t not in _ALIASES:
                raise ValueError(
                    f"unknown mask layer {t!r}; valid: "
                    "grammar, schema, tool, regex, denylist, regex_denylist, safety, policy")
            active.update(_ALIASES[t])
    return [c for c in _CANON if c in active], source


def _profile_knob() -> str | None:
    """Read `token_law_engine_mask_layers` from the active runtime profile
    (`SOVEREIGN_OS_RUNTIME_PROFILE`, default high-concurrency-burst). Returns None
    if unset / unreadable — the resolver then falls through to 'all'."""
    try:
        import yaml
        pid = os.environ.get("SOVEREIGN_OS_RUNTIME_PROFILE", "high-concurrency-burst")
        p = _REPO / "profiles" / "runtime" / f"{pid}.yaml"
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        rp = data.get("runtime_profile", {})
        v = rp.get("token_law_engine_mask_layers")
        if isinstance(v, list):
            return ",".join(str(x) for x in v)
        return str(v) if v else None
    except Exception:
        return None


def _gateway_addr(addr: str | None) -> str:
    return addr or os.environ.get("SOVEREIGN_GATEWAY_ADDR", DEFAULT_ADDR)


def _cmd_layers(args) -> int:
    try:
        active, source = _resolve_selection(args.token_law_mask_layers)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"active": active, "source": source,
                          "all_layers": _CANON}, indent=2))
    else:
        print(f"active mask layers: {', '.join(active)}")
        print(f"resolved from:      {source}")
    return 0


def _read_vocab(args) -> list[str]:
    if args.vocab_file:
        txt = Path(args.vocab_file).read_text(encoding="utf-8")
        txt = txt.strip()
        if txt.startswith("["):
            return list(json.loads(txt))
        return [ln for ln in txt.splitlines() if ln]
    if args.vocab:
        return [t for t in args.vocab.split(",") if t]
    return []


def _cmd_fuse(args) -> int:
    try:
        active, source = _resolve_selection(args.token_law_mask_layers)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    vocab = _read_vocab(args)
    if not vocab:
        print("token-law fuse needs a vocab (--vocab a,b,c or --vocab-file F)", file=sys.stderr)
        return 2
    req: dict = {"vocab": vocab, "generated": args.generated or "",
                 "mask_layers": active}
    if args.schema_file:
        req["schema"] = json.loads(Path(args.schema_file).read_text(encoding="utf-8"))
    if args.regex:
        req["regex"] = args.regex
    if args.denylist:
        req["denylist"] = [t for t in args.denylist.split(",") if t]
    if args.regex_denylist:
        req["regex_denylist"] = [t for t in args.regex_denylist.split(",") if t]
    addr = _gateway_addr(args.addr)
    body = json.dumps(req).encode("utf-8")
    url = f"http://{addr}/v1/data-plane/token-law/fuse"
    try:
        r = urllib.request.Request(url, data=body, method="POST",
                                   headers={"Content-Type": "application/json",
                                            "Accept": "application/json"})
        with urllib.request.urlopen(r, timeout=args.timeout) as resp:  # noqa: S310 (loopback)
            out = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        print(f"gateway {addr} refused ({e.code}): {detail}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"gateway {addr} unreachable: {e}\n"
              f"(start sovereign-gatewayd, or set SOVEREIGN_GATEWAY_ADDR)", file=sys.stderr)
        return 1
    if args.json:
        out["_selection"] = {"active": active, "source": source}
        print(json.dumps(out, indent=2))
    else:
        la = ", ".join(out.get("layers_active", [])) or "(none)"
        print(f"mask layers active:  {la}   [selection: {', '.join(active)} via {source}]")
        print(f"allowed tokens:      {out.get('allowed_tokens')} / {len(vocab)}")
        pl = out.get("per_layer", [])
        if pl:
            print("per layer:           "
                  + ", ".join(f"{c['layer']}={c['allowed']}" for c in pl))
        print(f"stop:                {out.get('stop')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="sovereign-osctl token-law",
        description="Token-law engine mask-layer selection + checkpoint-free fusion probe (SDD-510).")
    sub = ap.add_subparsers(dest="verb", required=True)

    pl = sub.add_parser("layers", help="resolve + show the active mask-layer selection (no daemon)")
    pl.add_argument("--token-law-mask-layers", dest="token_law_mask_layers", default=None,
                    help="csv of layers (grammar,schema,tool,safety,regex,denylist,regex_denylist,policy)")
    pl.add_argument("--json", action="store_true")
    pl.set_defaults(fn=_cmd_layers)

    pf = sub.add_parser("fuse", help="fuse the named laws at a prefix over a vocab (probes the gateway)")
    pf.add_argument("--token-law-mask-layers", dest="token_law_mask_layers", default=None,
                    help="restrict which layers are active for this fuse")
    pf.add_argument("--vocab", help="comma-separated vocabulary (token strings)")
    pf.add_argument("--vocab-file", help="vocab file (JSON array, or one token per line)")
    pf.add_argument("--schema-file", help="JSON-schema file (grammar plane)")
    pf.add_argument("--regex", help="positive-regex plane (tool allow-list)")
    pf.add_argument("--denylist", help="comma-separated literal denylist (safety)")
    pf.add_argument("--regex-denylist", dest="regex_denylist", help="comma-separated negated-regex (safety)")
    pf.add_argument("--generated", help="the committed prefix (default empty)")
    pf.add_argument("--addr", help="gateway host:port (default env SOVEREIGN_GATEWAY_ADDR or 127.0.0.1:8787)")
    pf.add_argument("--timeout", type=float, default=3.0)
    pf.add_argument("--json", action="store_true")
    pf.set_defaults(fn=_cmd_fuse)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
