#!/usr/bin/env python3
"""SDD-903 Phase 1b — PURE core: derive gatewayd routing from an orchestration
profile's allocations.

This is the logic that will replace `84-gpu-route.sh`'s hardcoded `_TIERS`. It is
kept as a pure, side-effect-free, unit-tested library on purpose: `84-gpu-route`
is the module whose tier misregistration caused the week-long 256-wedge total-
inference outage, so WIRING this into it is integration-gated (nspawn/qemu + a
live gatewayd apply). This module proves the derivation is a faithful drop-in
first — nothing here touches the running system.

Model→card placement in a profile becomes three gatewayd facts:
  * generative tiers (logic / oracle) → chat PROXY records
        `<proxy-id>@<endpoint>@<device>@<vram_gb>` (POST /v1/models/register)
  * an `embed` tier → SOVEREIGN_GATEWAY_EMBED_ENDPOINT/MODEL (NOT a proxy:
        /v1/embeddings resolves it by env, never resolve_proxy())
  * a `rerank` tier → an extra allowed endpoint
plus the SSRF allowlist = every endpoint above.

The tier→serving conventions below mirror today's hardcoded `84-gpu-route`
values, so a profile that matches the current box derives byte-identical routing
(see the round-trip test).
"""
from __future__ import annotations

GENERATIVE_TIERS = ("logic", "oracle")
POOLING_TIERS = ("embed", "rerank")

# Defaults that reproduce today's hardcoded 84-gpu-route constants.
DEFAULT_PORTS = {"logic": 8082, "oracle": 8083, "embed": 8084, "rerank": 8085}
DEFAULT_VRAM_GB = {"logic": 32, "oracle": 96}
_GIB = 1024 ** 3


def _profile_body(profile: dict) -> dict:
    return profile.get("orchestration_profile") or profile.get("runtime_profile") or {}


def _endpoint(alloc: dict) -> str:
    port = alloc.get("port") or DEFAULT_PORTS.get(alloc.get("tier"))
    if port is None:
        raise ValueError(
            f"allocation {alloc.get('agent_id')!r} tier {alloc.get('tier')!r} has "
            f"no port and no default — cannot form an endpoint"
        )
    return f"127.0.0.1:{port}"


def _vram_gb(alloc: dict) -> int:
    lim = alloc.get("vram_limit_bytes")
    if lim:
        return int(lim) // _GIB
    return DEFAULT_VRAM_GB.get(alloc.get("tier"), 0)


def derive_routing(profile: dict) -> dict:
    """Return {proxy_tiers, embed, rerank, allow} for the ACTIVE GPU allocations.

    CPU tiers (pulse) are skipped — they are not GPU routes. Inactive allocations
    (active: false) are skipped. Pure: no I/O, no globals mutated.
    """
    body = _profile_body(profile)
    proxy_tiers: list[dict] = []
    embed: dict | None = None
    rerank: dict | None = None
    allow: list[str] = []

    for a in body.get("allocations") or []:
        if not a.get("active", True):
            continue
        hw = a.get("target_hardware", "")
        if not hw.startswith("cuda:"):
            continue  # CPU / non-GPU tiers are not GPU proxy routes
        tier = a.get("tier")
        ep = _endpoint(a)
        allow.append(ep)
        if tier in GENERATIVE_TIERS:
            proxy_tiers.append({
                "proxy_id": f"gpu-{tier}",
                "endpoint": ep,
                "device": tier,
                "vram_gb": _vram_gb(a),
            })
        elif tier == "embed":
            embed = {"endpoint": ep, "model": "gpu-embed"}
        elif tier == "rerank":
            rerank = {"endpoint": ep}
        # other cuda tiers (e.g. a future 'router' on GPU) fall through: allowed
        # but not auto-registered as a chat proxy — same conservative stance as
        # today's module (a pooling/aux model must never become an "auto" target).

    return {"proxy_tiers": proxy_tiers, "embed": embed, "rerank": rerank, "allow": allow}


def tiers_string(proxy_tiers: list[dict]) -> str:
    """The comma-separated GPU_ROUTE_TIERS value 84-gpu-route consumes."""
    return ",".join(
        f"{t['proxy_id']}@{t['endpoint']}@{t['device']}@{t['vram_gb']}"
        for t in proxy_tiers
    )


def validate(profile: dict, card_vram_bytes: dict | None = None) -> list[str]:
    """Return a list of human-readable errors (empty = OK). The reconciler runs
    this BEFORE applying a layout so an overcommit or a port clash is refused
    rather than half-applied. `card_vram_bytes` maps target_hardware ->
    capacity; when omitted, only the port-collision check runs.
    """
    body = _profile_body(profile)
    errors: list[str] = []
    ports_by_card: dict[tuple[str, int], str] = {}
    vram_by_card: dict[str, int] = {}

    for a in body.get("allocations") or []:
        if not a.get("active", True):
            continue
        hw = a.get("target_hardware", "")
        port = a.get("port")
        if port is not None:
            key = (hw, port)
            if key in ports_by_card:
                errors.append(
                    f"port {port} reused on {hw} by {a.get('agent_id')!r} and "
                    f"{ports_by_card[key]!r}"
                )
            ports_by_card[key] = a.get("agent_id")
        if a.get("vram_limit_bytes"):
            vram_by_card[hw] = vram_by_card.get(hw, 0) + int(a["vram_limit_bytes"])

    if card_vram_bytes:
        for hw, used in vram_by_card.items():
            cap = card_vram_bytes.get(hw)
            if cap is not None and used > cap:
                errors.append(
                    f"{hw} overcommitted: {used} bytes requested > {cap} capacity"
                )
    return errors


def emit_shell(profile: dict) -> str:
    """Shell-consumable single-quoted assignments for 84-gpu-route to capture.
    Empty values are omitted so the bash side can fall back to its defaults."""
    r = derive_routing(profile)
    out: list[str] = []
    tiers = tiers_string(r["proxy_tiers"])
    if tiers:
        out.append(f"GPU_ROUTE_TIERS='{tiers}'")
    if r["embed"]:
        out.append(f"GPU_ROUTE_EMBED_EP='{r['embed']['endpoint']}'")
        out.append(f"GPU_ROUTE_EMBED_MODEL='{r['embed']['model']}'")
    if r["rerank"]:
        out.append(f"GPU_ROUTE_RERANK_EP='{r['rerank']['endpoint']}'")
    if r["allow"]:
        out.append(f"GPU_ROUTE_ALLOW='{','.join(r['allow'])}'")
    return "\n".join(out)


if __name__ == "__main__":  # read-only, no side effects
    import sys, yaml  # noqa: E401
    args = sys.argv[1:]
    emit = "--emit-shell" in args
    path = [a for a in args if not a.startswith("-")][0]
    prof = yaml.safe_load(open(path))
    if emit:
        print(emit_shell(prof))
    else:
        r = derive_routing(prof)
        print("GPU_ROUTE_TIERS =", tiers_string(r["proxy_tiers"]))
        print("embed  =", r["embed"])
        print("rerank =", r["rerank"])
        print("allow  =", ",".join(r["allow"]))
        print("validate:", validate(prof) or "OK")
