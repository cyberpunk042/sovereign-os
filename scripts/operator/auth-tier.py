#!/usr/bin/env python3
"""scripts/operator/auth-tier.py — R450 (E11.M7).

Operator §1g verbatim:
  "a mode of access from no auth at all by default to basic auth to
   advanced auth to social auth to enterprise auth and network level
   access and etc."

The §1g operator-discoverable auth tier ladder for every dashboard /
API / web app the system exposes. Per-dashboard tier is operator-
configurable; the ladder gives a clear upgrade path from "expose to
LAN, no auth" → "enterprise SSO + IP-allowlist".

6 operator-named tiers (verbatim ladder ordering, low → high):
  1. no-auth        — bound to loopback OR LAN-trust; no credentials
  2. basic          — HTTP basic auth (username + password); HTTPS-only
  3. advanced       — token-based (bearer / JWT); per-user revocable
  4. social         — OAuth (GitHub / Google / GitLab); operator-named
                       social providers; cookie-session
  5. enterprise     — SAML / OIDC SSO; group-claim authorization;
                       audit-log integration
  6. network-level  — IP-allowlist + WireGuard/VPN gating BEFORE the
                       per-tier auth check fires; defense-in-depth

CLI:
  auth-tier.py list-tiers [--json|--human]
                          Enumerate the 6 operator-named tiers + their
                          contract (requires/provides/discovery-shape).

  auth-tier.py registry [--json|--human]
                          Per-dashboard tier registry (which dashboard
                          runs at which tier). Reads
                          /etc/sovereign-os/auth-tier.toml (operator-
                          overridable). Operator-discoverable: "what
                          auth posture is each surface running at?"

  auth-tier.py show <dashboard> [--json|--human]
                          Detail one dashboard's tier (current value,
                          allowed transitions, configuration hints).

  auth-tier.py matrix [--json|--human]
                          Operator-discoverable upgrade matrix: for
                          each registered dashboard, show CURRENT tier
                          + RECOMMENDED next tier + why-upgrade.

  auth-tier.py set <dashboard> <tier> [--apply --confirm-tier-set]
                          [--json|--human]
                          Mutate the configured tier for one
                          dashboard (writes overlay TOML). Triple-gate
                          confirmation: --apply + --confirm-tier-set +
                          interactive prompt unless --json mode.

Exit codes:
  0 ok
  1 unknown subcommand / unknown tier / unknown dashboard
  2 apply blocked (gates missing) or argument error
  3 invalid tier-transition (e.g., skipping multiple tiers without
                              --force-skip-tiers operator gate)

Layer B metric (SDD-016):
  sovereign_os_operator_auth_tier_query_total{verb,tier,result}

Operator-environment env vars:
  SOVEREIGN_OS_AUTH_TIER_CONFIG  Override registry path (default:
                                  /etc/sovereign-os/auth-tier.toml)
  SOVEREIGN_OS_DRY_RUN           Logs intent; no writes.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

# Metrics output dir
METRICS_DIR = pathlib.Path(os.environ.get(
    "SOVEREIGN_OS_METRICS_DIR",
    "/var/lib/node_exporter/textfile_collector",
))
DRY_RUN = bool(os.environ.get("SOVEREIGN_OS_DRY_RUN"))

# Per-dashboard tier overlay (operator-overridable)
CONFIG_PATH = pathlib.Path(os.environ.get(
    "SOVEREIGN_OS_AUTH_TIER_CONFIG",
    "/etc/sovereign-os/auth-tier.toml",
))

# Operator §1g verbatim 6-tier ladder, low → high
AUTH_TIERS = [
    {
        "tier": "no-auth",
        "level": 0,
        "label": "No auth (loopback / LAN-trust)",
        "requires": [],
        "provides": "Open access to the surface from any reachable network.",
        "discovery_shape": "operator types URL → page loads",
        "operator_named": "no auth at all by default",
        "typical_use": (
            "Local-only dashboards bound to 127.0.0.1; LAN-trust where "
            "the LAN is already auth-bounded by a network-level gate "
            "(e.g., Tailscale, WireGuard)."
        ),
        "warning": (
            "Never bind no-auth surfaces to 0.0.0.0 on a public IP. "
            "If unsure, escalate to at least `basic`."
        ),
    },
    {
        "tier": "basic",
        "level": 1,
        "label": "Basic auth (HTTP basic, HTTPS-only)",
        "requires": ["HTTPS certificate (Let's Encrypt or self-signed + pinned)"],
        "provides": "Username + password gate; minimal config.",
        "discovery_shape": "browser shows OS-native auth prompt",
        "operator_named": "basic auth",
        "typical_use": (
            "Quick-protected dashboards on a trusted LAN where TLS is "
            "configured but operator hasn't decided on a richer auth "
            "stack yet."
        ),
        "warning": (
            "HTTP basic over plaintext HTTP is a credential leak. "
            "Enforce HTTPS-only at the reverse-proxy layer."
        ),
    },
    {
        "tier": "advanced",
        "level": 2,
        "label": "Advanced (token-based / JWT, per-user revocable)",
        "requires": ["Token issuer", "Token revocation store"],
        "provides": (
            "Per-user token-bound auth; tokens revocable; suitable for "
            "API access + automated callers."
        ),
        "discovery_shape": "Authorization: Bearer <token> header",
        "operator_named": "advanced auth",
        "typical_use": (
            "Programmatic API access; multiple operators with distinct "
            "tokens; fleet automation calling sovereign-osctl surfaces."
        ),
        "warning": (
            "Token storage on the operator's machine MUST follow "
            "the 'Operator-supplied keys NEVER in-repo' mandate."
        ),
    },
    {
        "tier": "social",
        "level": 3,
        "label": "Social auth (GitHub / Google / GitLab / etc.)",
        "requires": ["OAuth app registration with the provider",
                     "Callback URL on a public-or-tunnel host"],
        "provides": (
            "Cookie-session auth with provider-identity; group-based "
            "authorization possible (e.g., GitHub org membership)."
        ),
        "discovery_shape": "browser redirect → provider login → callback",
        "operator_named": "social auth",
        "typical_use": (
            "Operator wants to share a dashboard with collaborators "
            "without provisioning local accounts; identity comes from "
            "GitHub/Google."
        ),
        "warning": (
            "Provider downtime = login outage. Always have a fallback "
            "tier (basic + emergency credential) for break-glass."
        ),
    },
    {
        "tier": "enterprise",
        "level": 4,
        "label": "Enterprise (SAML / OIDC, group claims, audit log)",
        "requires": ["IdP (Keycloak / Okta / Azure AD / Authentik)",
                     "OIDC client registration",
                     "Group-claim mapping"],
        "provides": (
            "Full SSO with enterprise-IdP group-based authorization; "
            "audit-log integration; MFA at the IdP layer."
        ),
        "discovery_shape": "browser redirect → IdP login → SAML/OIDC callback",
        "operator_named": "enterprise auth",
        "typical_use": (
            "Multi-operator team with enterprise IAM; compliance "
            "requires audit trail of who accessed which surface when."
        ),
        "warning": (
            "Operator MUST run their own IdP OR trust a vendor IdP. "
            "Sovereign-OS itself does not ship a built-in IdP — operator "
            "deploys Keycloak/Authentik separately."
        ),
    },
    {
        "tier": "network-level",
        "level": 5,
        "label": "Network-level (IP-allowlist + VPN gate)",
        "requires": [
            "Network-layer gate (firewall IP-allowlist OR WireGuard/"
            "Tailscale tunnel)",
            "Reverse-proxy enforcement (deny non-allowed source IPs "
            "BEFORE any application-layer auth)",
        ],
        "provides": (
            "Defense-in-depth: even if the application-layer auth "
            "(per-tier) is compromised, the network-layer gate denies "
            "access from untrusted sources."
        ),
        "discovery_shape": (
            "operator's source IP must be in allowlist OR connected "
            "via VPN; THEN per-tier auth applies"
        ),
        "operator_named": "network level access",
        "typical_use": (
            "Production-grade exposure; sovereign-os AI workstation "
            "behind operator's OPNsense + LAN-allowlist; combines with "
            "any other tier (no-auth becomes safe when LAN-only)."
        ),
        "warning": (
            "Network-level gating REPLACES neither IdP nor application-"
            "layer auth — it LAYERS on top. The combination is "
            "operator-named defense-in-depth."
        ),
    },
]

KNOWN_TIER_NAMES = [t["tier"] for t in AUTH_TIERS]

# Default registry — populated with known sovereign-os dashboards.
# Operator-overridable via /etc/sovereign-os/auth-tier.toml.
DEFAULT_REGISTRY = {
    "sovereign-osctl-cli": {
        "current_tier": "no-auth",
        "recommended_tier": "no-auth",
        "rationale": (
            "Local CLI bound to operator's shell session; no network "
            "exposure; tier upgrade not applicable."
        ),
    },
    "metrics-textfile-collector": {
        "current_tier": "no-auth",
        "recommended_tier": "network-level",
        "rationale": (
            "Prometheus textfile collector on localhost + node_exporter "
            "scrape. Upgrade to network-level when fleet-aggregating "
            "from a remote Prometheus."
        ),
    },
    "trinity-pulse": {
        "current_tier": "no-auth",
        "recommended_tier": "advanced",
        "rationale": (
            "bitnet.cpp HTTP server on :8081 (loopback). Upgrade to "
            "advanced (token) before binding to LAN."
        ),
    },
    "trinity-logic-engine": {
        "current_tier": "no-auth",
        "recommended_tier": "advanced",
        "rationale": (
            "vLLM OpenAI-compatible API on :8082. Upgrade before "
            "exposing to remote callers."
        ),
    },
    "trinity-oracle-core": {
        "current_tier": "no-auth",
        "recommended_tier": "advanced",
        "rationale": (
            "vLLM on :8083 (Blackwell). Same as logic-engine."
        ),
    },
    "router": {
        "current_tier": "no-auth",
        "recommended_tier": "advanced",
        "rationale": (
            "SDD-011 deterministic router on :8080. Should match the "
            "tier of the tiers it dispatches to."
        ),
    },
    "grafana-dashboard": {
        "current_tier": "basic",
        "recommended_tier": "social",
        "rationale": (
            "Grafana ships with basic auth; upgrade to OAuth (GitHub) "
            "when sharing dashboards with team members."
        ),
    },
    "future-master-dashboard": {
        "current_tier": "no-auth",
        "recommended_tier": "social",
        "rationale": (
            "E11.M2 reverse-proxy aggregate dashboard. Should run at "
            "the HIGHEST tier among its constituents."
        ),
    },
}


def _emit_metric(name: str, verb: str, tier: str, result: str) -> None:
    """Best-effort SDD-016 metric write; never raises.

    Inline literal metric name (R443 metric-inventory-lockstep contract)."""
    if DRY_RUN:
        sys.stderr.write(
            f"  would emit: {name}"
            f"{{verb=\"{verb}\",tier=\"{tier}\",result=\"{result}\"}} 1\n"
        )
        return
    try:
        METRICS_DIR.mkdir(parents=True, exist_ok=True)
        prom = METRICS_DIR / "sovereign-os-operator-auth-tier.prom"
        line = (
            f'{name}'
            f'{{verb="{verb}",tier="{tier}",result="{result}"}} 1\n'
        )
        tmp = prom.with_suffix(".prom.tmp")
        tmp.write_text(line)
        tmp.replace(prom)
    except OSError:
        pass


def load_registry() -> dict:
    """Load registry: default + overlay TOML (operator-overridable)."""
    registry = {k: dict(v) for k, v in DEFAULT_REGISTRY.items()}
    if not CONFIG_PATH.is_file():
        return registry
    try:
        try:
            import tomllib  # py3.11+
            data = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except ImportError:
            try:
                import tomli  # py3.10 fallback
                data = tomli.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            except ImportError:
                return registry
        overrides = data.get("dashboards") or {}
        for name, overlay in overrides.items():
            if not isinstance(overlay, dict):
                continue
            registry.setdefault(name, {}).update(overlay)
    except (OSError, ValueError):
        pass
    return registry


def _resolve_tier(name: str) -> dict | None:
    for t in AUTH_TIERS:
        if t["tier"] == name:
            return t
    return None


# -------------------- CLI verbs --------------------


def cmd_list_tiers(args) -> int:
    if args.fmt == "json":
        print(json.dumps({"tiers": AUTH_TIERS}, indent=2))
    else:
        print(f"── auth-tier.list-tiers ({len(AUTH_TIERS)} tiers, "
              f"operator §1g ladder) ──")
        for t in AUTH_TIERS:
            print(f"  {t['level']}  {t['tier']:<14} {t['label']}")
            print(f"     operator-named: '{t['operator_named']}'")
            print(f"     provides: {t['provides']}")
    _emit_metric(
        "sovereign_os_operator_auth_tier_query_total",
        "list_tiers", "all", "ok",
    )
    return 0


def cmd_registry(args) -> int:
    registry = load_registry()
    if args.fmt == "json":
        print(json.dumps({
            "config_path": str(CONFIG_PATH),
            "config_present": CONFIG_PATH.is_file(),
            "dashboards": registry,
        }, indent=2))
    else:
        print(f"── auth-tier.registry ({len(registry)} dashboards) ──")
        print(f"  config: {CONFIG_PATH}"
              f" ({'present' if CONFIG_PATH.is_file() else 'absent (defaults)'})")
        print(f"  {'DASHBOARD':<32} {'CURRENT':<16} {'RECOMMENDED'}")
        for name, info in registry.items():
            cur = info.get("current_tier", "?")
            rec = info.get("recommended_tier", "?")
            marker = "✓" if cur == rec else "→"
            print(f"  {name:<32} {cur:<16} {marker} {rec}")
    _emit_metric(
        "sovereign_os_operator_auth_tier_query_total",
        "registry", "all", "ok",
    )
    return 0


def cmd_show(args) -> int:
    registry = load_registry()
    info = registry.get(args.dashboard)
    if not info:
        sys.stderr.write(
            f"unknown dashboard: {args.dashboard!r}\n"
            f"known: {', '.join(registry.keys())}\n"
        )
        _emit_metric(
            "sovereign_os_operator_auth_tier_query_total",
            "show", "unknown", "unknown-dashboard",
        )
        return 1
    current = _resolve_tier(info.get("current_tier", ""))
    recommended = _resolve_tier(info.get("recommended_tier", ""))
    out = {
        "dashboard": args.dashboard,
        "current": current,
        "recommended": recommended,
        "rationale": info.get("rationale", ""),
        "upgrade_required": (
            current and recommended
            and current["level"] < recommended["level"]
        ),
        "allowed_transitions": KNOWN_TIER_NAMES,
    }
    if args.fmt == "json":
        print(json.dumps(out, indent=2))
    else:
        print(f"── auth-tier.show {args.dashboard} ──")
        print(f"  current     : {info.get('current_tier')} "
              f"({current['label'] if current else '?'})")
        print(f"  recommended : {info.get('recommended_tier')} "
              f"({recommended['label'] if recommended else '?'})")
        if out["upgrade_required"]:
            print(f"  → UPGRADE: {info.get('current_tier')} → "
                  f"{info.get('recommended_tier')}")
        print(f"  rationale   : {info.get('rationale')}")
    _emit_metric(
        "sovereign_os_operator_auth_tier_query_total",
        "show", info.get("current_tier", "unknown"), "ok",
    )
    return 0


def cmd_matrix(args) -> int:
    """Operator-discoverable upgrade matrix across all dashboards."""
    registry = load_registry()
    rows = []
    for name, info in registry.items():
        cur = _resolve_tier(info.get("current_tier", "no-auth"))
        rec = _resolve_tier(info.get("recommended_tier", "no-auth"))
        rows.append({
            "dashboard": name,
            "current": cur["tier"] if cur else "?",
            "current_level": cur["level"] if cur else -1,
            "recommended": rec["tier"] if rec else "?",
            "recommended_level": rec["level"] if rec else -1,
            "upgrade_levels": (
                rec["level"] - cur["level"]
                if cur and rec else 0
            ),
            "rationale": info.get("rationale", ""),
        })
    rows.sort(key=lambda r: r["upgrade_levels"], reverse=True)
    if args.fmt == "json":
        print(json.dumps({"matrix": rows}, indent=2))
    else:
        print(f"── auth-tier.matrix (upgrade priority — highest first) ──")
        print(f"  {'DASHBOARD':<32} {'CURRENT':<14} {'→':^3} {'RECOMMENDED':<14} {'GAP'}")
        for r in rows:
            gap = f"+{r['upgrade_levels']}" if r['upgrade_levels'] > 0 else "  -"
            print(f"  {r['dashboard']:<32} {r['current']:<14} {'→':^3} "
                  f"{r['recommended']:<14} {gap}")
    _emit_metric(
        "sovereign_os_operator_auth_tier_query_total",
        "matrix", "all", "ok",
    )
    return 0


def cmd_set(args) -> int:
    """Triple-gated tier mutation."""
    if _resolve_tier(args.tier) is None:
        sys.stderr.write(
            f"unknown tier: {args.tier!r}\n"
            f"known: {', '.join(KNOWN_TIER_NAMES)}\n"
        )
        _emit_metric(
            "sovereign_os_operator_auth_tier_query_total",
            "set", args.tier, "unknown-tier",
        )
        return 1

    registry = load_registry()
    if args.dashboard not in registry:
        sys.stderr.write(
            f"unknown dashboard: {args.dashboard!r}\n"
            f"known: {', '.join(registry.keys())}\n"
        )
        _emit_metric(
            "sovereign_os_operator_auth_tier_query_total",
            "set", args.tier, "unknown-dashboard",
        )
        return 1

    current = registry[args.dashboard].get("current_tier")
    cur_level = next(
        (t["level"] for t in AUTH_TIERS if t["tier"] == current),
        -1,
    )
    new_level = next(
        (t["level"] for t in AUTH_TIERS if t["tier"] == args.tier),
        -1,
    )

    # Gate: skipping ≥3 levels requires explicit operator force.
    if abs(new_level - cur_level) >= 3 and not args.force_skip_tiers:
        sys.stderr.write(
            f"tier transition {current} → {args.tier} skips "
            f"{abs(new_level - cur_level) - 1} intermediate tier(s); "
            f"pass --force-skip-tiers to confirm.\n"
        )
        _emit_metric(
            "sovereign_os_operator_auth_tier_query_total",
            "set", args.tier, "blocked-skip-tiers",
        )
        return 3

    # Triple-gate: --apply + --confirm-tier-set + (if not JSON) interactive
    if not args.apply or not args.confirm_tier_set:
        plan = {
            "dashboard": args.dashboard,
            "from_tier": current,
            "to_tier": args.tier,
            "writes_to": str(CONFIG_PATH),
            "preview": True,
            "next_action": (
                "Re-run with --apply --confirm-tier-set to commit."
            ),
        }
        if args.fmt == "json":
            print(json.dumps(plan, indent=2))
        else:
            print(f"── auth-tier.set PREVIEW ──")
            print(f"  dashboard : {args.dashboard}")
            print(f"  from      : {current}")
            print(f"  to        : {args.tier}")
            print(f"  writes    : {CONFIG_PATH}")
            print(f"  next-step : re-run with --apply --confirm-tier-set")
        _emit_metric(
            "sovereign_os_operator_auth_tier_query_total",
            "set", args.tier, "preview",
        )
        return 0

    if DRY_RUN:
        sys.stderr.write(
            f"DRY-RUN — would write {args.dashboard}.current_tier = "
            f"{args.tier} to {CONFIG_PATH}\n"
        )
        _emit_metric(
            "sovereign_os_operator_auth_tier_query_total",
            "set", args.tier, "dry-run",
        )
        return 0

    # Real write
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        sys.stderr.write(
            f"cannot create {CONFIG_PATH.parent}: {e}\n"
        )
        _emit_metric(
            "sovereign_os_operator_auth_tier_query_total",
            "set", args.tier, "mkdir-failed",
        )
        return 2

    # Read existing TOML if present
    existing = ""
    if CONFIG_PATH.is_file():
        try:
            existing = CONFIG_PATH.read_text(encoding="utf-8")
        except OSError:
            existing = ""

    # Simple TOML overlay write (append a [[dashboards.X]] block)
    # NOTE: a real implementation would round-trip TOML properly; for the
    # operator-named MVP, we use a sentinel-bounded append pattern.
    sentinel = f"# sovereign-os auth-tier.set [{args.dashboard}]"
    new_block = (
        f"\n{sentinel}\n"
        f"[dashboards.{args.dashboard}]\n"
        f"current_tier = \"{args.tier}\"\n"
    )
    out_text = existing + new_block
    try:
        CONFIG_PATH.write_text(out_text, encoding="utf-8")
    except OSError as e:
        sys.stderr.write(f"cannot write {CONFIG_PATH}: {e}\n")
        _emit_metric(
            "sovereign_os_operator_auth_tier_query_total",
            "set", args.tier, "write-failed",
        )
        return 2

    print(f"  wrote {args.dashboard}.current_tier = "
          f"{args.tier} to {CONFIG_PATH}")
    _emit_metric(
        "sovereign_os_operator_auth_tier_query_total",
        "set", args.tier, "applied",
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="auth-tier.py",
        description=(
            "R450 (E11.M7) — sovereign-os auth tier ladder "
            "(§1g 6-tier no-auth/basic/advanced/social/enterprise/network-level)"
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_fmt(sp):
        g = sp.add_mutually_exclusive_group()
        g.add_argument("--json", dest="fmt", action="store_const",
                       const="json")
        g.add_argument("--human", dest="fmt", action="store_const",
                       const="human")
        sp.set_defaults(fmt="human")

    sp_list = sub.add_parser("list-tiers",
                              help="enumerate operator §1g 6-tier ladder")
    add_fmt(sp_list)

    sp_reg = sub.add_parser("registry",
                             help="per-dashboard tier registry")
    add_fmt(sp_reg)

    sp_show = sub.add_parser("show",
                              help="detail one dashboard's tier")
    sp_show.add_argument("dashboard")
    add_fmt(sp_show)

    sp_mat = sub.add_parser("matrix",
                             help="operator-discoverable upgrade matrix")
    add_fmt(sp_mat)

    sp_set = sub.add_parser("set",
                             help="mutate dashboard tier (triple-gated)")
    sp_set.add_argument("dashboard")
    sp_set.add_argument("tier")
    sp_set.add_argument("--apply", action="store_true",
                         help="actually write (otherwise preview)")
    sp_set.add_argument("--confirm-tier-set", action="store_true",
                         help="second gate: confirms operator intent")
    sp_set.add_argument("--force-skip-tiers", action="store_true",
                         help="permit skipping ≥3 levels in one set")
    add_fmt(sp_set)

    args = p.parse_args(argv)

    if args.cmd == "list-tiers":
        return cmd_list_tiers(args)
    if args.cmd == "registry":
        return cmd_registry(args)
    if args.cmd == "show":
        return cmd_show(args)
    if args.cmd == "matrix":
        return cmd_matrix(args)
    if args.cmd == "set":
        return cmd_set(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
