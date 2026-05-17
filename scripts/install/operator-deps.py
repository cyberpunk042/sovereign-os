#!/usr/bin/env python3
"""scripts/install/operator-deps.py — R284 (E7.M6).

Operator-named (§1b verbatim): "Allow to interoperate with an MCP via
tools calls and/or MCP. (e.g. I might install node, claude and
whatever deps and use it on it.)"

Declarative dep-install hook. Operator declares packages in
`/etc/sovereign-os/operator-deps.toml` (env override
SOVEREIGN_OS_OPERATOR_DEPS) split by package manager:

  [apt]
  install = ["jq", "ripgrep", "fd-find"]

  [pip]
  install = ["claude-cli", "huggingface_hub"]

  [npm]
  global = ["@anthropic-ai/claude-code"]

  [curl-shell]
  # Operator-trusted shell installs (Tailscale-style):
  # Each entry: name + url + sha256 expected
  installs = [
    { name = "tailscale", url = "https://tailscale.com/install.sh", verify = "skip" },
  ]

The verb walks the manifest, runs the appropriate install command per
package manager, and reports per-package outcomes. Idempotent: `apt
install` is no-op for already-installed packages; pip / npm same.

Triple-gate per the SOVEREIGN_OS_CONFIRM_DESTROY=YES convention:
  - DRY-RUN by default (prints what would run, doesn't execute)
  - --apply requires --confirm OR SOVEREIGN_OS_CONFIRM_DESTROY=YES
  - curl-shell installs ALWAYS require --confirm-curl-shell (these
    pipe untrusted code to bash; defense-in-depth)

CLI:
  operator-deps.py list [--json]                show declared deps
  operator-deps.py plan [--json]                show what would run
  operator-deps.py apply [--confirm] [--confirm-curl-shell] [--json]
                                                execute the plan

Exit codes:
  0  plan / apply succeeded (or dry-run)
  1  ≥1 install failed
  2  usage error / missing confirm
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

# Import the R283 overlay helper — first cross-repo adopter of SDD-030.
sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
from operator_overlay import load_with_overlay  # noqa: E402


DEFAULTS: dict[str, Any] = {
    "apt":         {"install": []},
    "pip":         {"install": []},
    "npm":         {"global": []},
    "curl_shell":  {"installs": []},
}


def detect_pms() -> dict[str, str | None]:
    """Which package managers are usable on this host?"""
    return {
        "apt":  shutil.which("apt-get") or shutil.which("apt"),
        "pip":  shutil.which("pip3") or shutil.which("pip"),
        "npm":  shutil.which("npm"),
        "curl": shutil.which("curl"),
        "bash": shutil.which("bash"),
    }


def _is_pkg_installed_apt(pkg: str) -> bool:
    if not shutil.which("dpkg-query"):
        return False
    try:
        r = subprocess.run(
            ["dpkg-query", "-W", "-f=${Status}", pkg],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return "install ok installed" in r.stdout


def _is_pkg_installed_pip(pkg: str) -> bool:
    if not shutil.which("pip") and not shutil.which("pip3"):
        return False
    pip_bin = shutil.which("pip3") or shutil.which("pip")
    try:
        r = subprocess.run(
            [pip_bin, "show", pkg],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return r.returncode == 0


def _is_pkg_installed_npm(pkg: str) -> bool:
    if not shutil.which("npm"):
        return False
    try:
        r = subprocess.run(
            ["npm", "list", "-g", pkg, "--depth=0", "--silent"],
            capture_output=True, text=True, timeout=8, check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return r.returncode == 0 and pkg in r.stdout


def plan_steps(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a step list from the cfg. Each step:
      {kind, name, action, command, currently_installed}
    """
    steps: list[dict[str, Any]] = []
    apt_pkgs = (cfg.get("apt") or {}).get("install") or []
    for pkg in apt_pkgs:
        steps.append({
            "kind": "apt",
            "name": pkg,
            "command": f"apt-get install -y {pkg}",
            "currently_installed": _is_pkg_installed_apt(pkg),
        })
    pip_pkgs = (cfg.get("pip") or {}).get("install") or []
    for pkg in pip_pkgs:
        steps.append({
            "kind": "pip",
            "name": pkg,
            "command": f"pip install {pkg}",
            "currently_installed": _is_pkg_installed_pip(pkg),
        })
    npm_pkgs = (cfg.get("npm") or {}).get("global") or []
    for pkg in npm_pkgs:
        steps.append({
            "kind": "npm",
            "name": pkg,
            "command": f"npm install -g {pkg}",
            "currently_installed": _is_pkg_installed_npm(pkg),
        })
    curl_installs = (cfg.get("curl_shell") or {}).get("installs") or []
    for entry in curl_installs:
        steps.append({
            "kind": "curl-shell",
            "name": entry.get("name", "?"),
            "url": entry.get("url"),
            "verify": entry.get("verify", "skip"),
            "command": f"curl -fsSL {entry.get('url')} | sh",
            "currently_installed": shutil.which(entry.get("name", "")) is not None,
            "elevated_confirm_required": True,
        })
    return steps


def execute_step(step: dict[str, Any], dry_run: bool, allow_curl_shell: bool) -> dict[str, Any]:
    started_at_cmd = step["command"]
    out = {
        "kind": step["kind"],
        "name": step["name"],
        "command": started_at_cmd,
        "outcome": "dry-run",
        "detail": "",
    }
    if step.get("currently_installed"):
        out["outcome"] = "already-installed"
        out["detail"] = "package already present; idempotent no-op"
        return out
    if dry_run:
        out["outcome"] = "dry-run"
        out["detail"] = "would run (dry-run)"
        return out
    if step["kind"] == "curl-shell" and not allow_curl_shell:
        out["outcome"] = "skipped"
        out["detail"] = "curl-shell installs require --confirm-curl-shell"
        return out
    # Real execution.
    kind = step["kind"]
    if kind == "apt":
        cmd = ["apt-get", "install", "-y", step["name"]]
    elif kind == "pip":
        pip_bin = shutil.which("pip3") or shutil.which("pip")
        if not pip_bin:
            out["outcome"] = "failed"
            out["detail"] = "pip not on PATH"
            return out
        cmd = [pip_bin, "install", step["name"]]
    elif kind == "npm":
        if not shutil.which("npm"):
            out["outcome"] = "failed"
            out["detail"] = "npm not on PATH"
            return out
        cmd = ["npm", "install", "-g", step["name"]]
    elif kind == "curl-shell":
        url = step.get("url", "")
        if not url:
            out["outcome"] = "failed"
            out["detail"] = "missing url"
            return out
        cmd = ["bash", "-c", f"curl -fsSL {url} | sh"]
    else:
        out["outcome"] = "failed"
        out["detail"] = f"unknown kind: {kind}"
        return out
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
    except (subprocess.TimeoutExpired, OSError) as e:
        out["outcome"] = "failed"
        out["detail"] = str(e)
        return out
    out["outcome"] = "ok" if r.returncode == 0 else "failed"
    out["detail"] = (r.stderr or r.stdout)[:300]
    return out


def cmd_list(args: argparse.Namespace) -> int:
    cfg = load_with_overlay("operator-deps", DEFAULTS, args.config)
    out = {
        "round": "R284",
        "vector": "E7.M6 (operator-deps list)",
        "config_source": cfg.get("_source"),
        "overlay_keys": cfg.get("_overlay_keys", []),
        "package_managers_available": detect_pms(),
        "declared": {
            "apt":        (cfg.get("apt") or {}).get("install") or [],
            "pip":        (cfg.get("pip") or {}).get("install") or [],
            "npm":        (cfg.get("npm") or {}).get("global")  or [],
            "curl_shell": (cfg.get("curl_shell") or {}).get("installs") or [],
        },
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R284 sovereign-os operator-deps list (E7.M6) ──")
    print(f"  config: {cfg.get('_source')}")
    print(f"  pms:    {out['package_managers_available']}")
    for kind, items in out["declared"].items():
        print(f"  [{kind}] {len(items)} declared")
        for item in items:
            if isinstance(item, dict):
                print(f"    - {item.get('name', '?')} ({item.get('url', '')})")
            else:
                print(f"    - {item}")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    cfg = load_with_overlay("operator-deps", DEFAULTS, args.config)
    steps = plan_steps(cfg)
    counts = {
        "total":               len(steps),
        "already_installed":   sum(1 for s in steps if s.get("currently_installed")),
        "would_install":       sum(1 for s in steps if not s.get("currently_installed")),
        "curl_shell_count":    sum(1 for s in steps if s["kind"] == "curl-shell"),
    }
    out = {
        "round": "R284",
        "vector": "E7.M6 (operator-deps plan)",
        "config_source": cfg.get("_source"),
        "counts": counts,
        "steps": steps,
    }
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"── R284 operator-deps plan (E7.M6) ──")
    print(f"  total={counts['total']}  already={counts['already_installed']}  "
          f"would_install={counts['would_install']}  curl-shell={counts['curl_shell_count']}")
    for s in steps:
        mark = "✓" if s.get("currently_installed") else "+"
        elevated = "  ⚠ requires --confirm-curl-shell" if s["kind"] == "curl-shell" else ""
        print(f"  {mark} [{s['kind']:<11}] {s['name']:<30} {s['command']}{elevated}")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    cfg = load_with_overlay("operator-deps", DEFAULTS, args.config)
    dry = bool(args.dry_run) or os.environ.get("SOVEREIGN_OS_DRY_RUN")
    confirm_env = os.environ.get("SOVEREIGN_OS_CONFIRM_DESTROY") == "YES"
    if not dry and not args.confirm and not confirm_env:
        print(
            "ERROR apply without --confirm OR SOVEREIGN_OS_CONFIRM_DESTROY=YES. "
            "Add --confirm to acknowledge that apply mutates the host.",
            file=sys.stderr,
        )
        return 2
    steps = plan_steps(cfg)
    results: list[dict[str, Any]] = []
    failures = 0
    for s in steps:
        r = execute_step(s, dry_run=bool(dry), allow_curl_shell=args.confirm_curl_shell)
        results.append(r)
        if r["outcome"] == "failed":
            failures += 1
    out = {
        "round": "R284",
        "vector": "E7.M6 (operator-deps apply)",
        "dry_run": bool(dry),
        "confirmed": bool(args.confirm) or confirm_env,
        "confirm_curl_shell": bool(args.confirm_curl_shell),
        "step_count": len(steps),
        "executed_count": len(results),
        "failure_count": failures,
        "results": results,
    }
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"── R284 operator-deps apply (dry_run={bool(dry)}) ──")
        for r in results:
            mark = {"ok": "OK ", "dry-run": "DRY", "already-installed": "SKIP",
                    "skipped": "SKIP", "failed": "FAIL"}.get(r["outcome"], "?")
            print(f"  [{mark}] {r['kind']:<11} {r['name']:<30} {r['outcome']:<18} {r['detail'][:60]}")
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="operator-deps.py",
        description="R284 (E7.M6) — operator-supplied dep install hooks (apt/pip/npm/curl-shell).",
    )
    p.add_argument("--config", type=Path)
    sub = p.add_subparsers(dest="verb", required=True)
    pl = sub.add_parser("list", help="show declared deps")
    pl.add_argument("--json", action="store_true")
    pl.set_defaults(func=cmd_list)
    pp = sub.add_parser("plan", help="show what would run")
    pp.add_argument("--json", action="store_true")
    pp.set_defaults(func=cmd_plan)
    pa = sub.add_parser("apply", help="execute the install plan (requires --confirm)")
    pa.add_argument("--confirm", action="store_true")
    pa.add_argument("--dry-run", action="store_true")
    pa.add_argument("--confirm-curl-shell", action="store_true",
                    help="also allow curl|sh installs (defense-in-depth opt-in)")
    pa.add_argument("--json", action="store_true")
    pa.set_defaults(func=cmd_apply)
    return p


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
