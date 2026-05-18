#!/usr/bin/env python3
"""scripts/intelligence/module-state.py — R351 (E2.M34).

Operator-named (§1b verbatim hook drop, double-pasted at lines 179 +
359 of the mandate file):
  "dashboard, installs, non-configured, modules or features and how
   configure them"

The "what have I installed but not yet configured?" operator-pull
verb. Until now, the operator had no single place to see:
  - Which modules ship default overlay knobs?
  - Which of those have an /etc/sovereign-os/<name>.toml present?
  - Which systemd units exist? Which are enabled? Active?
  - For each gap: what verb does operator run to close it?

R351 catalogs every shipped module + probes 4 signals per module:
  1. has_example_config  → config/<name>.toml.example exists in repo
  2. has_etc_config      → /etc/sovereign-os/<name>.toml exists on host
  3. has_systemd_unit    → systemd/system/<unit>.service exists
  4. unit_enabled+active → systemctl probe (best-effort; NEVER-raise)

Per-module verdict:
  - "fully-configured" → has_etc_config AND (no-unit OR active)
  - "installed-not-configured" → has_example AND not has_etc
  - "config-only-no-runtime" → has_etc AND has_unit AND not active
  - "running-without-overlay" → has_unit AND active AND not has_etc
                                (operator running stock defaults)
  - "shipped-but-untouched" → none of the above (operator has not
                              engaged this module yet)

CLI:
  module-state.py list      [--axis X] [--state S] [--etc-dir P] [--json|--human]
  module-state.py show      <module>     [--etc-dir P] [--json|--human]
  module-state.py recommend                [--etc-dir P] [--json|--human]
                            ranked list of operator-attention modules
                            with the verb to close each gap

Operator-overlay (R283/SDD-030): /etc/sovereign-os/module-state.toml
— operator can add custom modules to track or annotate existing ones.

Exit codes:
  0  rendered, no operator-attention items
  1  one or more modules in "installed-not-configured" state
  2  usage error / unknown module
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

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
try:
    from operator_overlay import load_with_overlay  # type: ignore
except Exception:  # pragma: no cover
    load_with_overlay = None


SCHEMA_VERSION = "1.0.0"
ROUND = "R351"
SDD_VECTOR = "E2.M34"


# Default etc dir — override via env or --etc-dir for tests.
DEFAULT_ETC_DIR = "/etc/sovereign-os"


# ── Module registry ────────────────────────────────────────────────
#
# Each entry binds (toml_basename, axis, configure_verb, systemd_unit).
# `configure_verb` is the operator-runnable command to start
# configuring the module (typically `cp <example> /etc/...`).
# `systemd_unit` is None for modules with no runtime (advisors).
DEFAULT_MODULES: list[dict[str, Any]] = [
    # ── Power / UPS ──────────────────────────────────────────────
    {"module": "power", "axis": "power",
     "configure_verb":
        "cp config/power.toml.example /etc/sovereign-os/power.toml",
     "systemd_unit": None},
    {"module": "power-profiles", "axis": "power",
     "configure_verb":
        "cp config/power-profiles.toml.example /etc/sovereign-os/power-profiles.toml",
     "systemd_unit": None},
    {"module": "shutdown-manifest", "axis": "power",
     "configure_verb":
        "cp config/shutdown-manifest.toml.example /etc/sovereign-os/shutdown-manifest.toml",
     "systemd_unit": "sovereign-power-shutdown-guard"},
    {"module": "psu-oc", "axis": "power",
     "configure_verb":
        "cp config/psu-oc.toml.example /etc/sovereign-os/psu-oc.toml",
     "systemd_unit": None},
    # ── Hardware / OC ────────────────────────────────────────────
    {"module": "oc-headroom", "axis": "hardware",
     "configure_verb":
        "cp config/oc-headroom.toml.example /etc/sovereign-os/oc-headroom.toml",
     "systemd_unit": None},
    {"module": "gpu-policy", "axis": "hardware",
     "configure_verb":
        "cp config/gpu-policy.toml.example /etc/sovereign-os/gpu-policy.toml",
     "systemd_unit": None},
    {"module": "ram", "axis": "hardware",
     "configure_verb":
        "cp config/ram.toml.example /etc/sovereign-os/ram.toml",
     "systemd_unit": None},
    {"module": "kernel-tuning", "axis": "kernel",
     "configure_verb":
        "cp config/kernel-tuning.toml.example /etc/sovereign-os/kernel-tuning.toml",
     "systemd_unit": None},
    {"module": "known-boards", "axis": "hardware",
     "configure_verb":
        "cp config/known-boards.toml.example /etc/sovereign-os/known-boards.toml",
     "systemd_unit": None},
    # ── Lifecycle / Workflow ─────────────────────────────────────
    {"module": "lifecycle-profiles", "axis": "ai",
     "configure_verb":
        "cp config/lifecycle-profiles.toml.example /etc/sovereign-os/lifecycle-profiles.toml",
     "systemd_unit": None},
    {"module": "workflow-profiles", "axis": "ai",
     "configure_verb":
        "cp config/workflow-profiles.toml.example /etc/sovereign-os/workflow-profiles.toml",
     "systemd_unit": None},
    # ── Networking / install ─────────────────────────────────────
    {"module": "install-layers", "axis": "install",
     "configure_verb":
        "cp config/install-layers.toml.example /etc/sovereign-os/install-layers.toml",
     "systemd_unit": None},
    {"module": "operator-deps", "axis": "install",
     "configure_verb":
        "cp config/operator-deps.toml.example /etc/sovereign-os/operator-deps.toml",
     "systemd_unit": None},
    # ── Dashboard / observability ────────────────────────────────
    {"module": "dashboard-auth", "axis": "dashboard",
     "configure_verb":
        "cp config/dashboard-auth.toml.example /etc/sovereign-os/dashboard-auth.toml",
     "systemd_unit": "sovereign-router"},
    {"module": "notify", "axis": "notification",
     "configure_verb":
        "cp config/notify.toml.example /etc/sovereign-os/notify.toml",
     "systemd_unit": "sovereign-notify-dispatch"},
    # ── Intelligence / research ──────────────────────────────────
    {"module": "research-loop", "axis": "intelligence",
     "configure_verb":
        "cp config/research-loop.toml.example /etc/sovereign-os/research-loop.toml",
     "systemd_unit": None},
]


# ── Probing ────────────────────────────────────────────────────────
def _example_exists(module: str) -> bool:
    return (REPO_ROOT / "config" / f"{module}.toml.example").is_file()


def _etc_exists(module: str, etc_dir: Path) -> bool:
    return (etc_dir / f"{module}.toml").is_file()


def _unit_path(unit: str | None) -> Path | None:
    if not unit:
        return None
    return REPO_ROOT / "systemd" / "system" / f"{unit}.service"


def _unit_exists(unit: str | None) -> bool:
    p = _unit_path(unit)
    return bool(p and p.is_file())


def _systemctl_state(unit: str | None) -> dict[str, Any]:
    """Returns {enabled, active, probed} — NEVER raises. probed=False
    when systemctl unavailable (containers / tests)."""
    out = {"enabled": None, "active": None, "probed": False}
    if not unit:
        return out
    if not shutil.which("systemctl"):
        return out
    try:
        en = subprocess.run(
            ["systemctl", "is-enabled", f"{unit}.service"],
            capture_output=True, text=True, timeout=3,
        )
        ac = subprocess.run(
            ["systemctl", "is-active", f"{unit}.service"],
            capture_output=True, text=True, timeout=3,
        )
        # If systemctl cannot reach a real PID 1 (containers, tests),
        # treat as un-probed rather than "active=<error blurb>".
        en_text = en.stdout.strip() or en.stderr.strip() or ""
        ac_text = ac.stdout.strip() or ac.stderr.strip() or ""
        unreachable = ("not been booted" in en_text + ac_text
                       or "Host is down" in en_text + ac_text
                       or "Failed to connect" in en_text + ac_text)
        if unreachable:
            return out
        out["enabled"] = en_text or None
        out["active"] = ac_text or None
        out["probed"] = True
    except Exception:
        pass
    return out


def derive_state(m: dict, etc_dir: Path) -> dict[str, Any]:
    """Compute the per-module verdict + signals."""
    name = m["module"]
    unit = m.get("systemd_unit")
    has_example = _example_exists(name)
    has_etc = _etc_exists(name, etc_dir)
    has_unit = _unit_exists(unit)
    sd = _systemctl_state(unit) if has_unit else {
        "enabled": None, "active": None, "probed": False,
    }
    is_active = (sd["active"] == "active") if sd["probed"] else False
    # Verdict precedence (highest information first):
    if has_etc and (not has_unit or is_active or not sd["probed"]):
        verdict = "fully-configured"
    elif has_example and not has_etc and has_unit:
        verdict = "running-without-overlay" if is_active else (
            "installed-not-configured")
    elif has_example and not has_etc:
        verdict = "installed-not-configured"
    elif has_etc and has_unit and not is_active and sd["probed"]:
        verdict = "config-only-no-runtime"
    elif has_unit and is_active and not has_etc:
        verdict = "running-without-overlay"
    else:
        verdict = "shipped-but-untouched"
    return {
        "module": name,
        "axis": m.get("axis"),
        "has_example_config": has_example,
        "has_etc_config": has_etc,
        "has_systemd_unit": has_unit,
        "systemd_enabled": sd["enabled"],
        "systemd_active": sd["active"],
        "systemd_probed": sd["probed"],
        "verdict": verdict,
        "configure_verb": m.get("configure_verb"),
    }


def needs_attention(state: dict) -> bool:
    return state["verdict"] in ("installed-not-configured",
                                 "running-without-overlay",
                                 "config-only-no-runtime")


# ── Loading ────────────────────────────────────────────────────────
def load_modules(overlay_path: Path | None) -> tuple[list[dict], dict]:
    meta = {"_source": "(defaults)", "_overlay_keys": []}
    modules = list(DEFAULT_MODULES)
    if load_with_overlay is not None:
        loaded = load_with_overlay(
            "module-state", {"modules": []}, explicit_path=overlay_path,
        )
        meta["_source"] = loaded.get("_source", meta["_source"])
        meta["_overlay_keys"] = loaded.get("_overlay_keys", [])
        if loaded.get("_parse_error"):
            meta["_parse_error"] = loaded["_parse_error"]
        if loaded.get("modules"):
            modules = list(loaded["modules"])
    return modules, meta


def filter_axis(modules: list[dict], axis: str | None) -> list[dict]:
    if not axis:
        return modules
    return [m for m in modules if isinstance(m, dict)
            and m.get("axis") == axis]


# ── Renderers ──────────────────────────────────────────────────────
def render_list_human(states: list[dict]) -> str:
    lines = ["── R351 sovereign-os module-state (E2.M34) ──"]
    by_verdict: dict[str, list[str]] = {}
    for s in states:
        by_verdict.setdefault(s["verdict"], []).append(s["module"])
    for verdict in ("installed-not-configured", "running-without-overlay",
                     "config-only-no-runtime", "fully-configured",
                     "shipped-but-untouched"):
        names = by_verdict.get(verdict)
        if not names:
            continue
        lines.append(f"  {verdict} ({len(names)}):")
        for n in names:
            lines.append(f"    - {n}")
    return "\n".join(lines) + "\n"


def render_recommend_human(states: list[dict]) -> str:
    attn = [s for s in states if needs_attention(s)]
    lines = [f"── R351 module-state recommend (E2.M34) — "
             f"{len(attn)} item(s) need attention ──"]
    if not attn:
        lines.append("  ✓ All modules are either fully-configured or "
                      "untouched-by-design.")
        return "\n".join(lines) + "\n"
    for s in attn:
        lines.append("")
        lines.append(f"  ⚠ {s['module']} [{s['verdict']}]")
        lines.append(f"    axis:        {s['axis']}")
        lines.append(f"    has_example: {s['has_example_config']}")
        lines.append(f"    has_etc:     {s['has_etc_config']}")
        if s.get("has_systemd_unit"):
            lines.append(f"    unit:        active={s['systemd_active']} "
                          f"enabled={s['systemd_enabled']}")
        lines.append(f"    next step:   $ {s['configure_verb']}")
    return "\n".join(lines) + "\n"


# ── Main ──────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="module-state.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    for verb in ("list", "show", "recommend"):
        sp = sub.add_parser(verb)
        if verb == "show":
            sp.add_argument("module")
        if verb == "list":
            sp.add_argument("--axis")
            sp.add_argument("--state")
        sp.add_argument("--etc-dir", type=Path, default=None,
                         dest="etc_dir")
        sp.add_argument("--config", type=Path)
        sf = sp.add_mutually_exclusive_group()
        sf.add_argument("--json", dest="fmt", action="store_const", const="json")
        sf.add_argument("--human", dest="fmt", action="store_const", const="human")
        sp.set_defaults(fmt="json")

    args = p.parse_args(argv)
    etc_dir = (args.etc_dir
               or Path(os.environ.get("SOVEREIGN_OS_ETC_DIR",
                                       DEFAULT_ETC_DIR)))
    modules, meta = load_modules(getattr(args, "config", None))

    states = [derive_state(m, etc_dir) for m in modules
              if isinstance(m, dict) and "module" in m]
    attention_count = sum(1 for s in states if needs_attention(s))

    if args.cmd == "list":
        filtered_modules = filter_axis(modules, getattr(args, "axis", None))
        filtered_states = [derive_state(m, etc_dir) for m in filtered_modules
                            if isinstance(m, dict)]
        if args.state:
            filtered_states = [s for s in filtered_states
                                if s["verdict"] == args.state]
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "etc_dir": str(etc_dir),
                "axis_filter": getattr(args, "axis", None),
                "state_filter": args.state,
                "module_count": len(filtered_states),
                "attention_count":
                    sum(1 for s in filtered_states if needs_attention(s)),
                "modules": filtered_states,
                "overlay": meta,
            }, indent=2))
        else:
            print(render_list_human(filtered_states), end="")
        return 1 if attention_count > 0 else 0

    if args.cmd == "show":
        m = next((x for x in modules if isinstance(x, dict)
                  and x.get("module") == args.module), None)
        if m is None:
            print(json.dumps({
                "error": f"unknown module: {args.module}",
                "known": [x.get("module") for x in modules
                          if isinstance(x, dict)],
                "round": ROUND,
            }, indent=2), file=sys.stderr)
            return 2
        s = derive_state(m, etc_dir)
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "etc_dir": str(etc_dir),
                "state": s,
                "overlay": meta,
            }, indent=2))
        else:
            print(f"── R351 module-state: {args.module} (E2.M34) ──")
            for k, v in s.items():
                print(f"  {k}: {v}")
        return 1 if needs_attention(s) else 0

    if args.cmd == "recommend":
        if args.fmt == "json":
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "round": ROUND,
                "sdd_vector": SDD_VECTOR,
                "etc_dir": str(etc_dir),
                "attention_count": attention_count,
                "attention_items":
                    [s for s in states if needs_attention(s)],
                "all_modules_summary":
                    {s["module"]: s["verdict"] for s in states},
                "overlay": meta,
            }, indent=2))
        else:
            print(render_recommend_human(states), end="")
        return 1 if attention_count > 0 else 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
