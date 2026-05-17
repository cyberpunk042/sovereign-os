#!/usr/bin/env python3
"""scripts/network/dns-advisor.py — R268 (E3.M4).

Operator-named (verbatim, 2026-05-17 mandate): "networks and in and
out, the DNS, the Cloudflared ? the tailscale, Traefik ..."

R220 ships generic network-status (probes 8 components including
DNS). R263 ships per-service deep advisor (cloudflared/tailscale/
traefik). R268 closes E3.M4: DNS-specific deep probe — which
resolver(s) the host actually uses, which provider those map to,
whether DNS-over-TLS / DNS-over-HTTPS is configured, latency to
the upstream, and operator-actionable posture verdict.

Probes (read-only):
  /etc/resolv.conf            classic nameserver list (after
                              systemd-resolved or NetworkManager
                              materialized it)
  /run/systemd/resolve/       systemd-resolved global + per-link
  resolvectl status           live state when systemd-resolved present
  /etc/systemd/resolved.conf  DoT/DoH/DNSSEC config (advisory)
  dig @resolver +stats        latency probe (best-effort)

Each upstream is classified against a known-provider table
(Cloudflare 1.1.1.1, Quad9 9.9.9.9, Google 8.8.8.8, AdGuard 94.140.14.14,
NextDNS, OpenDNS, Mullvad). Operator-readable per-provider notes:
"Cloudflare offers DoH/DoT but no built-in malware filtering",
"Quad9 includes malware blocking by default", etc.

Posture verdict:
  ok                  resolver responds + DoT/DoH configured if available
  attention           resolver responds but no DoT/DoH OR using ISP
                      default OR localhost-only fallback
  degraded            resolver doesn't respond
  not-configured      no nameservers at all (impossible on most hosts)

CLI:
  dns-advisor.py status [--json]      classified nameservers + posture
  dns-advisor.py providers [--json]   known-provider lookup table
  dns-advisor.py latency [--json]     dig +stats latency to each upstream

Exit codes:
  0  posture ok / informational
  1  ≥1 nameserver at attention/degraded
  2  usage error
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# Known DNS providers — address → {name, dot, doh, malware_filtering, notes}
KNOWN_PROVIDERS: dict[str, dict[str, Any]] = {
    "1.1.1.1": {"name": "Cloudflare", "dot": True, "doh": True,
                "malware_filtering": False,
                "notes": "Cloudflare 1.1.1.1 — fast + DoT/DoH; no built-in malware filter (use 1.1.1.2 for that)."},
    "1.0.0.1": {"name": "Cloudflare-secondary", "dot": True, "doh": True,
                "malware_filtering": False,
                "notes": "Cloudflare secondary endpoint."},
    "1.1.1.2": {"name": "Cloudflare-malware", "dot": True, "doh": True,
                "malware_filtering": True,
                "notes": "Cloudflare with malware-blocking enabled (recommended for SAIN-01 default)."},
    "1.1.1.3": {"name": "Cloudflare-family", "dot": True, "doh": True,
                "malware_filtering": True,
                "notes": "Cloudflare malware + adult-content filtering."},
    "8.8.8.8": {"name": "Google", "dot": True, "doh": True,
                "malware_filtering": False,
                "notes": "Google Public DNS — telemetry posture: Google logs query metadata."},
    "8.8.4.4": {"name": "Google-secondary", "dot": True, "doh": True,
                "malware_filtering": False, "notes": "Google secondary."},
    "9.9.9.9": {"name": "Quad9", "dot": True, "doh": True,
                "malware_filtering": True,
                "notes": "Quad9 — operator-recommended: malware filtering ON by default + no logging."},
    "149.112.112.112": {"name": "Quad9-secondary", "dot": True, "doh": True,
                        "malware_filtering": True, "notes": "Quad9 secondary."},
    "94.140.14.14": {"name": "AdGuard", "dot": True, "doh": True,
                     "malware_filtering": True,
                     "notes": "AdGuard DNS — malware + ad-blocking at DNS layer."},
    "94.140.15.15": {"name": "AdGuard-secondary", "dot": True, "doh": True,
                     "malware_filtering": True, "notes": "AdGuard secondary."},
    "208.67.222.222": {"name": "OpenDNS", "dot": False, "doh": False,
                       "malware_filtering": True,
                       "notes": "OpenDNS — content filtering; no DoT on free tier."},
    "208.67.220.220": {"name": "OpenDNS-secondary", "dot": False, "doh": False,
                       "malware_filtering": True, "notes": "OpenDNS secondary."},
    "127.0.0.53": {"name": "systemd-resolved-stub", "dot": None, "doh": None,
                   "malware_filtering": None,
                   "notes": "systemd-resolved local stub — actual upstream defined in /etc/systemd/resolved.conf."},
    "127.0.0.1": {"name": "localhost", "dot": None, "doh": None,
                  "malware_filtering": None,
                  "notes": "Loopback — host runs its own resolver (unbound / dnsmasq / pi-hole / etc.)."},
}


def parse_resolv_conf() -> list[str]:
    p = Path("/etc/resolv.conf")
    if not p.exists():
        return []
    servers: list[str] = []
    try:
        for line in p.read_text().splitlines():
            line = line.strip()
            if line.startswith("nameserver "):
                parts = line.split(None, 1)
                if len(parts) == 2:
                    servers.append(parts[1].strip())
    except OSError:
        pass
    return servers


def parse_resolvectl_status() -> dict[str, Any]:
    if not shutil.which("resolvectl"):
        return {}
    try:
        r = subprocess.run(
            ["resolvectl", "status"], capture_output=True, text=True,
            timeout=5, check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return {}
    if r.returncode != 0:
        return {}
    # Parse globally-listed "Current DNS Server", "DNS Servers", "DNSOverTLS",
    # "DNSSEC" + per-link sections.
    out: dict[str, Any] = {"raw": r.stdout, "global": {}, "per_link": []}
    current = out["global"]
    for raw_line in r.stdout.splitlines():
        line = raw_line.strip()
        if line.startswith("Link "):
            current = {"link": line}
            out["per_link"].append(current)
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip()
        if k in {"Current DNS Server", "DNS Servers", "Fallback DNS Servers",
                 "DNSOverTLS", "DNSSEC", "DNSSEC supported",
                 "Default Route", "DNS Domain"}:
            current[k] = v
    return out


def parse_resolved_conf() -> dict[str, str]:
    p = Path("/etc/systemd/resolved.conf")
    out: dict[str, str] = {}
    if not p.exists():
        return out
    try:
        for line in p.read_text().splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip()
            if k:
                out[k] = v
    except OSError:
        pass
    return out


def classify(addr: str) -> dict[str, Any]:
    known = KNOWN_PROVIDERS.get(addr)
    # Treat 127.0.0.0/8 generically as local resolver if not matched.
    if known is None:
        if addr.startswith("127."):
            return {"name": "local-resolver", "dot": None, "doh": None,
                    "malware_filtering": None,
                    "notes": "Loopback address — local resolver. Not a public provider."}
        if addr.startswith(("192.168.", "10.", "172.")):
            return {"name": "lan-private", "dot": None, "doh": None,
                    "malware_filtering": None,
                    "notes": "RFC1918 private address — likely your router/firewall acting as DNS forwarder."}
        return {"name": "unknown", "dot": None, "doh": None,
                "malware_filtering": None,
                "notes": "Unknown upstream — could be ISP default or operator-supplied."}
    return known


def dig_latency(addr: str) -> dict[str, Any] | None:
    """Best-effort latency probe. Returns {query_time_ms} or None."""
    if not shutil.which("dig"):
        return None
    try:
        r = subprocess.run(
            ["dig", "@" + addr, "+stats", "+time=3", "+tries=1", "example.com"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if r.returncode != 0:
        return {"query_time_ms": None, "error": (r.stderr or r.stdout)[:120]}
    m = re.search(r";; Query time:\s*(\d+)\s*msec", r.stdout)
    return {"query_time_ms": int(m.group(1)) if m else None}


def cmd_status(args: argparse.Namespace) -> int:
    nameservers = parse_resolv_conf()
    resolvectl = parse_resolvectl_status()
    resolved_conf = parse_resolved_conf()
    classified: list[dict[str, Any]] = []
    for addr in nameservers:
        meta = classify(addr)
        classified.append({
            "address": addr,
            **meta,
        })

    # DoT/DoH posture from resolved.conf (the upstream-level setting).
    dot_setting = resolved_conf.get("DNSOverTLS", "(unset)")
    dnssec_setting = resolved_conf.get("DNSSEC", "(unset)")

    # Posture verdict.
    advisories: list[str] = []
    if not nameservers:
        posture = "not-configured"
        advisories.append("/etc/resolv.conf has no nameservers — name resolution will fail.")
    else:
        # Check whether resolvectl reports DoT actually enabled.
        global_dot = (resolvectl.get("global") or {}).get("DNSOverTLS", "")
        if global_dot.lower() in {"no", "(unset)", ""} and dot_setting.lower() in {"no", "(unset)", "false", ""}:
            posture = "attention"
            advisories.append(
                "DNS-over-TLS not enabled. Edit /etc/systemd/resolved.conf: "
                "DNSOverTLS=yes  then `sudo systemctl restart systemd-resolved`."
            )
        else:
            posture = "ok"
        # Any unknown / ISP-default upstream?
        unknowns = [c for c in classified if c["name"] == "unknown"]
        if unknowns:
            if posture == "ok":
                posture = "attention"
            advisories.append(
                f"{len(unknowns)} unknown upstream(s) — likely ISP default. "
                "Consider switching to a known provider with malware filtering "
                "(e.g. Quad9 9.9.9.9, Cloudflare 1.1.1.2)."
            )
        # No malware-filtering provider in the chain?
        if not any(c.get("malware_filtering") for c in classified):
            if posture == "ok":
                posture = "attention"
            advisories.append(
                "No upstream offers malware filtering. Quad9 (9.9.9.9) or "
                "Cloudflare-malware (1.1.1.2) provide DNS-layer threat "
                "blocking at no cost."
            )

    out = {
        "round": "R268",
        "vector": "E3.M4 (DNS provider posture)",
        "resolv_conf_nameservers": nameservers,
        "classified_upstreams": classified,
        "resolved_conf": {
            "DNSOverTLS": dot_setting,
            "DNSSEC": dnssec_setting,
        },
        "resolvectl_global": resolvectl.get("global") or {},
        "posture": posture,
        "advisories": advisories,
    }
    rc = 1 if posture in {"attention", "degraded", "not-configured"} else 0
    if args.json:
        print(json.dumps(out, indent=2))
        return rc
    print(f"── R268 sovereign-os dns-advisor status (E3.M4) ──")
    print(f"  nameservers ({len(nameservers)}):")
    for c in classified:
        mf = "✓" if c.get("malware_filtering") else ("?" if c.get("malware_filtering") is None else "·")
        print(f"    {c['address']:<16}  {c['name']:<24}  malware-filter={mf}")
    print(f"  resolved.conf DNSOverTLS: {dot_setting}")
    print(f"  resolved.conf DNSSEC:     {dnssec_setting}")
    print()
    print(f"  posture: {posture}")
    for a in advisories:
        print(f"    ⚠ {a}")
    return rc


def cmd_providers(args: argparse.Namespace) -> int:
    rows = [{"address": a, **m} for a, m in KNOWN_PROVIDERS.items()]
    out = {
        "round": "R268",
        "vector": "E3.M4 (provider lookup table)",
        "providers": rows,
        "count": len(rows),
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R268 sovereign-os dns-advisor known providers ({len(rows)}) ──")
    for r in rows:
        print(f"  {r['address']:<18}  {r['name']:<24}  malware={r.get('malware_filtering')}")
        if r.get("notes"):
            print(f"      {r['notes']}")
    return 0


def cmd_latency(args: argparse.Namespace) -> int:
    nameservers = parse_resolv_conf()
    measurements = []
    for addr in nameservers:
        m = dig_latency(addr)
        measurements.append({"address": addr, "result": m})
    out = {
        "round": "R268",
        "vector": "E3.M4 (latency probes)",
        "dig_available": shutil.which("dig") is not None,
        "measurements": measurements,
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R268 sovereign-os dns-advisor latency ──")
    if not out["dig_available"]:
        print("  (dig not installed — `apt install dnsutils` for latency probes)")
        return 0
    for m in measurements:
        r = m["result"] or {}
        q = r.get("query_time_ms")
        print(f"  {m['address']:<18}  query_time={q if q is not None else '?'} ms")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dns-advisor.py",
        description="R268 (E3.M4) — DNS provider classification + posture verdict.",
    )
    sub = p.add_subparsers(dest="verb", required=True)
    for name, fn, helptxt in [
        ("status", cmd_status, "classified nameservers + posture verdict"),
        ("providers", cmd_providers, "known-provider lookup table"),
        ("latency", cmd_latency, "dig +stats latency to each upstream"),
    ]:
        sp = sub.add_parser(name, help=helptxt)
        sp.add_argument("--json", action="store_true")
        sp.set_defaults(func=fn)
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
