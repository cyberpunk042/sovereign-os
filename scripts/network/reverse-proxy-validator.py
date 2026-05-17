#!/usr/bin/env python3
"""scripts/network/reverse-proxy-validator.py — R275 (E3.M5).

Operator-named (verbatim, 2026-05-17 mandate): "Cloudflared ? the
tailscale, Traefik, non docker vs docker install ?".

R220 ships network-status probes (component up/down). R263 ships
per-service posture advisor. R275 closes E3.M5: read-only config
validator for reverse-proxy stacks (Traefik / Caddy / nginx) —
syntax check + operator-readable warnings on common
misconfigurations.

Validation is BEST-EFFORT static analysis. We do NOT actually
restart proxies or hit their admin endpoints; we read the on-disk
config + invoke the proxy binary's --validate mode when available.

Stacks supported:
  traefik     /etc/traefik/traefik.yml + /etc/traefik/dynamic/*.yml
              + traefik --configfile=... --check (if binary present)
  caddy       /etc/caddy/Caddyfile + caddy validate (if binary)
  nginx       /etc/nginx/nginx.conf + nginx -t (if binary)

CLI:
  reverse-proxy-validator.py status [--json]         all 3 stacks
  reverse-proxy-validator.py traefik|caddy|nginx [--json]
                                                     per-stack detail
  reverse-proxy-validator.py advisory [--json]       actionable hints
                                                     for misconfigs

Exit codes:
  0  every detected stack validates clean
  1  ≥1 stack fails validation
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


def _safe_run(argv: list[str], timeout: int = 8) -> dict[str, Any]:
    if not shutil.which(argv[0]):
        return {"ok": False, "rc": 127, "stderr": "binary not on PATH", "stdout": ""}
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    except (subprocess.TimeoutExpired, OSError) as e:
        return {"ok": False, "rc": 124, "stderr": str(e), "stdout": ""}
    return {
        "ok": r.returncode == 0,
        "rc": r.returncode,
        "stderr": r.stderr,
        "stdout": r.stdout,
    }


def probe_traefik() -> dict[str, Any]:
    binary = shutil.which("traefik")
    config_dir = Path("/etc/traefik")
    config_file = config_dir / "traefik.yml"
    dynamic_dir = config_dir / "dynamic"
    warnings: list[str] = []
    config_present = config_file.exists()
    dynamic_count = 0
    if dynamic_dir.is_dir():
        dynamic_count = len(list(dynamic_dir.glob("*.yml"))) + len(list(dynamic_dir.glob("*.yaml")))
    validate = {"ok": True, "rc": 0, "stderr": "", "stdout": ""}
    if binary and config_present:
        validate = _safe_run([binary, "--configfile", str(config_file), "--check"])
    # Static warning: dynamic configs ignored if no providers.file.directory
    if config_present:
        try:
            body = config_file.read_text(errors="replace")
            if "providers:" not in body:
                warnings.append("traefik.yml has no `providers:` block — no routers will load.")
            if "entryPoints" not in body:
                warnings.append("traefik.yml has no `entryPoints:` — operator must declare at minimum :443/:80.")
            if "api:" in body and "insecure: true" in body:
                warnings.append(
                    "api.insecure=true detected — Traefik dashboard exposed without auth. "
                    "Bind it to loopback OR put it behind an auth middleware."
                )
        except OSError:
            pass
    posture = "ok"
    if not binary and dynamic_count == 0 and not config_present:
        posture = "not-installed"
    elif not config_present and binary:
        posture = "attention"
        warnings.append(
            "traefik binary present but /etc/traefik/traefik.yml missing. "
            "Drop a static config OR run as a docker container with --providers.docker."
        )
    elif not validate["ok"] and binary:
        posture = "degraded"
        warnings.append(f"traefik --check failed: {(validate.get('stderr') or '').strip()[:200]}")
    return {
        "stack": "traefik",
        "binary_path": binary,
        "config_file": str(config_file),
        "config_present": config_present,
        "dynamic_config_count": dynamic_count,
        "validate": validate,
        "posture": posture,
        "warnings": warnings,
    }


def probe_caddy() -> dict[str, Any]:
    binary = shutil.which("caddy")
    caddyfile = Path("/etc/caddy/Caddyfile")
    config_present = caddyfile.exists()
    warnings: list[str] = []
    validate = {"ok": True, "rc": 0, "stderr": "", "stdout": ""}
    if binary and config_present:
        validate = _safe_run([binary, "validate", "--config", str(caddyfile), "--adapter", "caddyfile"])
    if config_present:
        try:
            body = caddyfile.read_text(errors="replace")
            # tls operator-supplied vs ACME auto
            if "tls internal" in body:
                warnings.append(
                    "tls internal directive present — Caddy issues self-signed certs. "
                    "Fine for private/lab use; browsers will warn. Use a real "
                    "domain + ACME for public endpoints."
                )
            # Admin endpoint on 0.0.0.0
            m = re.search(r"admin\s+([\w.:]+)", body)
            if m and not m.group(1).startswith(("127.", "localhost", "[::1]")):
                warnings.append(
                    f"caddy admin endpoint bound to {m.group(1)} — operator-readable: "
                    "the admin API can reload + read config remotely. Keep it on loopback "
                    "unless explicitly intended."
                )
        except OSError:
            pass
    if not binary and not config_present:
        posture = "not-installed"
    elif not config_present and binary:
        posture = "attention"
        warnings.append(
            "caddy binary present but /etc/caddy/Caddyfile missing — operator must "
            "supply a config OR use caddy in container with --config-file."
        )
    elif not validate["ok"] and binary:
        posture = "degraded"
        warnings.append(f"caddy validate failed: {(validate.get('stderr') or '').strip()[:200]}")
    else:
        posture = "ok"
    return {
        "stack": "caddy",
        "binary_path": binary,
        "config_file": str(caddyfile),
        "config_present": config_present,
        "validate": validate,
        "posture": posture,
        "warnings": warnings,
    }


def probe_nginx() -> dict[str, Any]:
    binary = shutil.which("nginx")
    config_file = Path("/etc/nginx/nginx.conf")
    sites_enabled = Path("/etc/nginx/sites-enabled")
    config_present = config_file.exists()
    sites_count = 0
    if sites_enabled.is_dir():
        sites_count = sum(1 for _ in sites_enabled.iterdir())
    warnings: list[str] = []
    validate = {"ok": True, "rc": 0, "stderr": "", "stdout": ""}
    if binary and config_present:
        validate = _safe_run([binary, "-t", "-c", str(config_file)])
    if config_present:
        try:
            body = config_file.read_text(errors="replace")
            # ssl_protocols pin
            if "ssl_protocols" not in body and config_present:
                # Check sites-enabled too.
                pass  # less invasive — would scan included files
            # server_tokens off?
            if "server_tokens" not in body:
                warnings.append(
                    "server_tokens directive absent — nginx leaks its version "
                    "in the `Server:` response header. Add `server_tokens off;` "
                    "to nginx.conf http block."
                )
        except OSError:
            pass
    if not binary and not config_present:
        posture = "not-installed"
    elif not validate["ok"] and binary:
        posture = "degraded"
        warnings.append(f"nginx -t failed: {(validate.get('stderr') or '').strip()[:200]}")
    elif not config_present and binary:
        posture = "attention"
        warnings.append("nginx binary present but /etc/nginx/nginx.conf missing.")
    else:
        posture = "ok"
    return {
        "stack": "nginx",
        "binary_path": binary,
        "config_file": str(config_file),
        "config_present": config_present,
        "sites_enabled_count": sites_count,
        "validate": validate,
        "posture": posture,
        "warnings": warnings,
    }


PROBES = {
    "traefik": probe_traefik,
    "caddy": probe_caddy,
    "nginx": probe_nginx,
}


def _verdict(report: dict[str, Any]) -> str:
    p = report.get("posture")
    return p if isinstance(p, str) else "unknown"


def cmd_status(args: argparse.Namespace) -> int:
    results = {name: fn() for name, fn in PROBES.items()}
    counts = {
        "ok": sum(1 for r in results.values() if _verdict(r) == "ok"),
        "attention": sum(1 for r in results.values() if _verdict(r) == "attention"),
        "degraded": sum(1 for r in results.values() if _verdict(r) == "degraded"),
        "not_installed": sum(1 for r in results.values() if _verdict(r) == "not-installed"),
    }
    out = {
        "round": "R275",
        "vector": "E3.M5 (reverse-proxy-validator)",
        "results": results,
        "counts": counts,
    }
    rc = 1 if (counts["degraded"] > 0 or counts["attention"] > 0) else 0
    if args.json:
        print(json.dumps(out, indent=2))
        return rc
    print(f"── R275 sovereign-os reverse-proxy-validator status (E3.M5) ──")
    for name, r in results.items():
        glyph = {"ok": "✓", "attention": "⚠", "degraded": "⛔",
                 "not-installed": "·"}.get(_verdict(r), "?")
        print(f"  {glyph} {name:<10}  posture={_verdict(r):<14} config={r.get('config_present')}")
        for w in r.get("warnings", []):
            print(f"      ⚠ {w}")
    return rc


def cmd_stack(name: str, args: argparse.Namespace) -> int:
    fn = PROBES[name]
    r = fn()
    out = {
        "round": "R275",
        "vector": f"E3.M5 ({name}-validator)",
        **r,
    }
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"── R275 sovereign-os reverse-proxy-validator {name} (E3.M5) ──")
        print(f"  binary:  {r.get('binary_path')}")
        print(f"  config:  {r.get('config_file')}  (present={r.get('config_present')})")
        print(f"  posture: {_verdict(r)}")
        for w in r.get("warnings", []):
            print(f"  ⚠ {w}")
    return 1 if _verdict(r) in {"attention", "degraded"} else 0


def cmd_advisory(args: argparse.Namespace) -> int:
    results = {name: fn() for name, fn in PROBES.items()}
    advisories: list[dict[str, str]] = []
    for name, r in results.items():
        for w in r.get("warnings", []):
            advisories.append({"stack": name, "warning": w})
    out = {
        "round": "R275",
        "vector": "E3.M5 (reverse-proxy-advisories)",
        "advisory_count": len(advisories),
        "advisories": advisories,
    }
    rc = 1 if advisories else 0
    if args.json:
        print(json.dumps(out, indent=2))
        return rc
    print(f"── R275 sovereign-os reverse-proxy-validator advisory (E3.M5) ──")
    if not advisories:
        print("  (no reverse-proxy advisories — install state OR no warnings)")
        return rc
    for a in advisories:
        print(f"  [{a['stack']}]  {a['warning']}")
    return rc


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="reverse-proxy-validator.py",
        description="R275 (E3.M5) — Traefik / Caddy / nginx config validator.",
    )
    sub = p.add_subparsers(dest="verb", required=True)
    ps = sub.add_parser("status", help="3-stack aggregate")
    ps.add_argument("--json", action="store_true")
    ps.set_defaults(func=cmd_status)
    for name in PROBES:
        sp = sub.add_parser(name, help=f"{name} detail")
        sp.add_argument("--json", action="store_true")
        sp.set_defaults(func=lambda a, n=name: cmd_stack(n, a))
    pa = sub.add_parser("advisory", help="all warnings across stacks")
    pa.add_argument("--json", action="store_true")
    pa.set_defaults(func=cmd_advisory)
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
