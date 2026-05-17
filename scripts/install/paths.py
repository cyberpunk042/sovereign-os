#!/usr/bin/env python3
"""scripts/install/paths.py — R237 (SDD-026 Z-8).

Operator-named (verbatim, 2026-05-17 expansion): "non docker vs docker
install ? possible ? greyout the option that require it and/or offer
the alternative and warn of the potential risk or failure or such
and/or offer to re-enable it if the user want the feature. container
level vs system level."

R220 (network-status) probes component reachability (docker / tailscale
/ cloudflared / traefik / dns / internet). R237 ties those probes back
into the FEATURE matrix: for each optional feature, declare its
supported install layers + per-layer dependency components. The matrix
folds the live network-status into a per-feature verdict:

  installable     default layer's dependencies all OK
  alternative     default layer blocked but another layer works
  blocked         no layer works (operator sees the missing deps)

Drives:
  - dashboard grey-out UX: blocked features render greyed-out with
    "X requires Y which is down" hover
  - terminal alternatives: `install-paths grey-out` prints the
    actionable "install Y to unblock X, or switch X to layer Z"

CLI:
  paths.py show [--feature F] [--json]   per-feature install matrix
  paths.py grey-out [--json]             features currently blocked
  paths.py choose <feature> --layer L    advisory check before installing

Config: /etc/sovereign-os/install-layers.toml (overridable via
SOVEREIGN_OS_INSTALL_LAYERS env). The repo ships
config/install-layers.toml.example as the operator template.

Exit codes:
  0  matrix rendered (informational)
  1  ≥1 feature is fully blocked (grey-out signal)
  2  usage error / config missing / unknown feature
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = Path("/etc/sovereign-os/install-layers.toml")
DEV_CONFIG = REPO_ROOT / "config" / "install-layers.toml.example"


def resolve_config_path(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit
    env = os.environ.get("SOVEREIGN_OS_INSTALL_LAYERS")
    if env:
        return Path(env)
    if DEFAULT_CONFIG.exists():
        return DEFAULT_CONFIG
    if DEV_CONFIG.exists():
        return DEV_CONFIG
    return None


def load_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"features": {}, "_source": "(missing)"}
    with path.open("rb") as fh:
        doc = tomllib.load(fh)
    if "features" not in doc:
        doc["features"] = {}
    doc["_source"] = str(path)
    return doc


def fetch_network_status() -> dict[str, str]:
    """Returns {component_id: status_string}.

    Statuses: ok / warn / down / not-installed / unknown. The matrix
    treats `ok` as 'requires satisfied' and everything else as 'not
    available'.
    """
    bin_path = REPO_ROOT / "scripts" / "hardware" / "network-status.py"
    if not bin_path.exists():
        return {}
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), "--json"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return {}
    if r.returncode not in (0, 1):
        return {}
    try:
        doc = json.loads(r.stdout)
    except json.JSONDecodeError:
        return {}
    out: dict[str, str] = {}
    for c in doc.get("components", []):
        cid = c.get("component") or c.get("id")
        st = c.get("status", "unknown")
        if cid:
            out[cid] = st
    return out


def classify_feature(
    feature_name: str,
    feature_cfg: dict[str, Any],
    network: dict[str, str],
) -> dict[str, Any]:
    layers = feature_cfg.get("layers") or []
    default_layer = feature_cfg.get("default") or (layers[0] if layers else None)
    meta = feature_cfg.get("layers_meta") or {}

    per_layer: list[dict[str, Any]] = []
    for layer in layers:
        m = meta.get(layer) or {}
        requires = list(m.get("requires") or [])
        warns = list(m.get("warns") or [])
        unmet = [r for r in requires if network.get(r) != "ok"]
        per_layer.append(
            {
                "layer": layer,
                "requires": requires,
                "unmet": unmet,
                "warns": warns,
                "available": len(unmet) == 0,
                "is_default": layer == default_layer,
            }
        )

    default_avail = next(
        (l_ for l_ in per_layer if l_["is_default"] and l_["available"]),
        None,
    )
    any_avail = [l_ for l_ in per_layer if l_["available"]]

    if default_avail is not None:
        verdict = "installable"
        recommended = default_layer
        reason = f"default layer '{default_layer}' satisfied"
    elif any_avail:
        verdict = "alternative"
        recommended = any_avail[0]["layer"]
        reason = (
            f"default '{default_layer}' blocked — use '{recommended}' instead"
        )
    else:
        verdict = "blocked"
        recommended = None
        missing = sorted({u for l_ in per_layer for u in l_["unmet"]})
        reason = (
            f"no layer satisfied; missing components: {', '.join(missing) or '(none)'}"
        )

    return {
        "feature": feature_name,
        "summary": feature_cfg.get("summary", ""),
        "verdict": verdict,
        "default_layer": default_layer,
        "recommended_layer": recommended,
        "reason": reason,
        "layers": per_layer,
    }


def build_matrix(
    config: dict[str, Any], network: dict[str, str]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, cfg in (config.get("features") or {}).items():
        if not isinstance(cfg, dict):
            continue
        rows.append(classify_feature(name, cfg, network))
    rows.sort(key=lambda r: r["feature"])
    return rows


def cmd_show(args: argparse.Namespace) -> int:
    cfg_path = resolve_config_path(args.config)
    config = load_config(cfg_path)
    network = fetch_network_status()
    rows = build_matrix(config, network)
    if args.feature:
        rows = [r for r in rows if r["feature"] == args.feature]
        if not rows:
            print(f"ERROR unknown feature {args.feature!r}", file=sys.stderr)
            return 2
    counts = {
        "installable": sum(1 for r in rows if r["verdict"] == "installable"),
        "alternative": sum(1 for r in rows if r["verdict"] == "alternative"),
        "blocked": sum(1 for r in rows if r["verdict"] == "blocked"),
        "total": len(rows),
    }
    report = {
        "round": "R237",
        "vector": "SDD-026 Z-8 (install-layer matrix)",
        "config_source": config.get("_source"),
        "network_components_seen": sorted(network.keys()),
        "counts": counts,
        "features": rows,
    }
    if args.json:
        print(json.dumps(report, indent=2))
        return 1 if counts["blocked"] > 0 else 0
    print("── R237 sovereign-os install-paths show (SDD-026 Z-8) ──")
    print(f"  config:   {report['config_source']}")
    print(
        f"  network:  {len(network)} component(s) seen "
        f"({', '.join(report['network_components_seen']) or '(none)'})"
    )
    print(
        f"  totals:   installable={counts['installable']}  "
        f"alternative={counts['alternative']}  blocked={counts['blocked']}"
    )
    print()
    for r in rows:
        glyph = {
            "installable": "✓",
            "alternative": "↔",
            "blocked": "⛔",
        }.get(r["verdict"], "?")
        print(f"  {glyph} {r['feature']:<20} ({r['verdict']:<11}) — {r['reason']}")
        for layer in r["layers"]:
            mark = " " if layer["available"] else "x"
            star = "*" if layer["is_default"] else " "
            unmet = (
                f"  unmet: {','.join(layer['unmet'])}" if layer["unmet"] else ""
            )
            print(f"      [{mark}]{star} layer={layer['layer']:<10}{unmet}")
            for w in layer["warns"]:
                print(f"          warn: {w}")
    return 1 if counts["blocked"] > 0 else 0


def cmd_grey_out(args: argparse.Namespace) -> int:
    cfg_path = resolve_config_path(args.config)
    config = load_config(cfg_path)
    network = fetch_network_status()
    rows = build_matrix(config, network)
    blocked = [r for r in rows if r["verdict"] == "blocked"]
    if args.json:
        print(
            json.dumps(
                {
                    "round": "R237",
                    "vector": "SDD-026 Z-8 (grey-out)",
                    "blocked_count": len(blocked),
                    "blocked": blocked,
                },
                indent=2,
            )
        )
        return 1 if blocked else 0
    print("── R237 sovereign-os install-paths grey-out ──")
    if not blocked:
        print("  (no blocked features — everything is installable)")
        return 0
    print(f"  {len(blocked)} feature(s) blocked:")
    for r in blocked:
        missing = sorted(
            {u for layer in r["layers"] for u in layer["unmet"]}
        )
        print(f"  ⛔ {r['feature']:<20} blocked — needs: {', '.join(missing)}")
        print(f"      reason: {r['reason']}")
        print(f"      fix:    install {', '.join(missing)} OR switch to a different layer")
    return 1


def cmd_choose(args: argparse.Namespace) -> int:
    cfg_path = resolve_config_path(args.config)
    config = load_config(cfg_path)
    network = fetch_network_status()
    feat_cfg = (config.get("features") or {}).get(args.feature)
    if feat_cfg is None:
        print(f"ERROR unknown feature {args.feature!r}", file=sys.stderr)
        return 2
    layers = feat_cfg.get("layers") or []
    if args.layer not in layers:
        print(
            f"ERROR layer {args.layer!r} not declared for "
            f"feature {args.feature!r}; available: {layers}",
            file=sys.stderr,
        )
        return 2
    row = classify_feature(args.feature, feat_cfg, network)
    chosen = next((l_ for l_ in row["layers"] if l_["layer"] == args.layer), None)
    if chosen is None:
        return 2
    out = {
        "round": "R237",
        "feature": args.feature,
        "requested_layer": args.layer,
        "available": chosen["available"],
        "unmet": chosen["unmet"],
        "warns": chosen["warns"],
        "fallback_recommended": row["recommended_layer"]
        if not chosen["available"]
        else None,
    }
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        if chosen["available"]:
            print(
                f"OK: {args.feature} on layer '{args.layer}' is installable. "
                f"warns: {chosen['warns'] or 'none'}"
            )
        else:
            print(
                f"BLOCKED: {args.feature} on layer '{args.layer}' needs "
                f"{','.join(chosen['unmet'])}. fallback: {row['recommended_layer'] or 'none'}"
            )
    return 0 if chosen["available"] else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="paths.py",
        description="R237 (SDD-026 Z-8) — feature install-layer matrix.",
    )
    p.add_argument("--config", type=Path, default=None)
    sub = p.add_subparsers(dest="verb", required=True)

    ps = sub.add_parser("show", help="render the full matrix")
    ps.add_argument("--feature")
    ps.add_argument("--json", action="store_true")
    ps.set_defaults(func=cmd_show)

    pg = sub.add_parser("grey-out", help="show only currently-blocked features")
    pg.add_argument("--json", action="store_true")
    pg.set_defaults(func=cmd_grey_out)

    pc = sub.add_parser("choose", help="advisory check for one feature+layer")
    pc.add_argument("feature")
    pc.add_argument("--layer", required=True)
    pc.add_argument("--json", action="store_true")
    pc.set_defaults(func=cmd_choose)

    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
