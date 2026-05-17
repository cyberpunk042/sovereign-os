#!/usr/bin/env python3
"""scripts/dashboard/serve.py — R225 (SDD-026 Z-1) dashboard SEED.

Operator-named (verbatim from the 2026-05-17 directive expansion):
"Always in the optic that this Debian 13 Sovereign OS is a non-GUI
by default. I will obviously be able to plug a screen or mainly
connect remotely to ssh and/or dashboard or API on whatsoever pot
for whatsoever dashbaords and modules and tools."

Minimal-stack HTTP server (stdlib http.server — no JS framework, no
npm chain, no template engine; the master spec ethos is "no bloat").
Serves a SINGLE page that aggregates every shipped Z-vector card:

  - GPU watt deviance  (R219 / Z-5 — scripts/hardware/gpu-watch.py)
  - Network state      (R220 / Z-7 — scripts/hardware/network-status.py)
  - CPU mode           (R221 / Z-4 — scripts/hardware/cpu-mode.py)
  - FS usage           (R222 / Z-10 — scripts/hardware/fs-insights.py)
  - RAID status        (R223 / Z-9 — scripts/hardware/raid-status.py)
  - Flex-profile state (R224 / Z-3 — scripts/hardware/profile-flex.py)

Each card invokes the underlying script's `--json` mode + renders a
small HTML block. Operator-readable. No mutations.

Endpoints:
  GET /             — full dashboard page
  GET /api/health   — aggregated JSON for all cards (machine-readable)
  GET /api/gpu      — single-card JSON (one per shipped Z-vector)
  GET /api/network
  GET /api/cpu
  GET /api/fs
  GET /api/raid
  GET /api/flex

Bind: 127.0.0.1:8443 by default. Operator opts in to exposure by
overriding --bind. Future round adds /etc/sovereign-os/dashboard.toml
allowlist + tailscale-only mode.

Run:
  sovereign-osctl dashboard serve            # blocks; Ctrl-C to stop
  sovereign-osctl dashboard serve --bind 0.0.0.0:8443 --json

Exit codes:
  0  clean shutdown
  2  usage error / bind failure

Tested via `--once` mode that handles ONE request + exits 0 (so the
L3 test can curl without spawning a separate process).
"""
from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


# R250 (SDD-026 Z-1 auth): per-process loaded auth config. Set by
# main() before the server starts; None means "no auth — same as
# cycle-8 SEED behavior, safe on loopback / tailscale-private binds".
AUTH_CONFIG: dict[str, Any] | None = None


def load_auth_config() -> dict[str, Any] | None:
    """R250: returns {token, allow_loopback, allow_ips} when config present.

    Path resolution: env SOVEREIGN_OS_DASHBOARD_AUTH_CONFIG overrides,
    then /etc/sovereign-os/dashboard-auth.toml, then the in-repo example
    file. Operator-supplied token is read from the env var named by
    `token_env` (operator secrets never in-repo per SDD-009).
    """
    env = os.environ.get("SOVEREIGN_OS_DASHBOARD_AUTH_CONFIG")
    candidate_paths: list[Path] = []
    if env:
        candidate_paths.append(Path(env))
    candidate_paths.append(Path("/etc/sovereign-os/dashboard-auth.toml"))
    candidate_paths.append(REPO_ROOT / "config" / "dashboard-auth.toml.example")
    cfg_path = next((p for p in candidate_paths if p.exists()), None)
    if cfg_path is None:
        return None
    try:
        with cfg_path.open("rb") as fh:
            doc = tomllib.load(fh)
    except OSError:
        return None
    token_env = doc.get("token_env")
    token = os.environ.get(token_env) if token_env else None
    return {
        "config_source": str(cfg_path),
        "token": token,
        "token_env": token_env,
        "allow_loopback": bool(doc.get("allow_loopback", True)),
        "allow_ips": [str(s) for s in (doc.get("allow_ips") or [])],
    }


def _is_loopback(addr: str) -> bool:
    return addr in {"127.0.0.1", "::1", "::ffff:127.0.0.1"}

REPO_ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------- card adapters


def _run_json(script: str, args: list[str]) -> dict[str, Any] | None:
    """Invoke a sibling script with --json and return parsed payload."""
    bin_path = REPO_ROOT / "scripts" / "hardware" / script
    if not bin_path.exists():
        return None
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), *args, "--json"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def card_gpu() -> dict[str, Any]:
    """R219 Z-5 — gpu-watch JSON."""
    data = _run_json("gpu-watch.py", []) or {"gpus": [], "any_deviance": False}
    return {"id": "gpu", "title": "GPU watt deviance (R219 / Z-5)", "data": data}


def card_network() -> dict[str, Any]:
    """R220 Z-7 — network-status JSON."""
    data = _run_json("network-status.py", []) or {"components": []}
    return {"id": "network", "title": "Network state (R220 / Z-7)", "data": data}


def card_cpu() -> dict[str, Any]:
    """R221 Z-4 — cpu-mode show JSON."""
    data = _run_json("cpu-mode.py", ["show"]) or {"cpus": {}}
    return {"id": "cpu", "title": "CPU mode (R221 / Z-4)", "data": data}


def card_fs() -> dict[str, Any]:
    """R222 Z-10 — fs-insights usage JSON."""
    data = _run_json("fs-insights.py", ["usage"]) or {"partitions": []}
    return {"id": "fs", "title": "Filesystem usage (R222 / Z-10)", "data": data}


def card_raid() -> dict[str, Any]:
    """R223 Z-9 — raid-status status JSON."""
    data = _run_json("raid-status.py", ["status"]) or {"arrays": [], "count": 0}
    return {"id": "raid", "title": "Software RAID (R223 / Z-9)", "data": data}


def card_flex() -> dict[str, Any]:
    """R224 Z-3 — profile-flex show JSON."""
    data = _run_json("profile-flex.py", ["show"]) or {"deltas": []}
    return {"id": "flex", "title": "Flex profile (R224 / Z-3)", "data": data}


def card_health() -> dict[str, Any]:
    """R226 Z-6 — composite health-scan JSON."""
    data = _run_json("health-scan.py", []) or {
        "probes": [], "summary": {}, "needs_attention": False
    }
    return {
        "id": "health",
        "title": "Health scan (R226 / Z-6)",
        "data": data,
    }


def _run_models_script(script: str, args: list[str]) -> dict[str, Any] | None:
    """Variant of _run_json for scripts/models/*.py."""
    bin_path = REPO_ROOT / "scripts" / "models" / script
    if not bin_path.exists():
        return None
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), *args, "--json"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def card_models() -> dict[str, Any]:
    """R227 Z-2 — Models tab (LM-Studio-equivalent surface).

    Aggregates the R212 catalog query + R214 profile-aware suggester
    into ONE dashboard card. Operators browse the curated model
    matrix (class × quantization × size × purpose) + see for each
    runtime profile which allocations are flagged.

    Data shape:
      catalog_count        — total catalog entries
      verified_real_count  — operator-pullable today
      aspirational_count   — catalog declares but no real repo
      by_class             — taxonomy histogram
      by_quantization      — quant histogram
      suggester            — per-runtime-profile flag summary
    """
    catalog = _run_models_script("catalog-query.py", []) or {}
    models = catalog.get("models") or []
    by_class: dict[str, int] = {}
    by_quant: dict[str, int] = {}
    verified = 0
    aspirational = 0
    for m in models:
        if m.get("class"):
            by_class[m["class"]] = by_class.get(m["class"], 0) + 1
        if m.get("quantization"):
            by_quant[m["quantization"]] = by_quant.get(m["quantization"], 0) + 1
        if m.get("status") == "verified-real":
            verified += 1
        elif m.get("status") == "aspirational":
            aspirational += 1
    # Per-runtime-profile suggester rollup (R214)
    suggester_rollup: list[dict[str, Any]] = []
    for pid in ("ultra-sovereign-efficiency", "high-concurrency-burst", "deep-context-synthesis"):
        s = _run_models_script("suggest-by-profile.py", ["--runtime-profile", pid])
        if s is not None:
            allocations = s.get("allocations") or []
            flagged = sum(1 for a in allocations if a.get("flags"))
            suggester_rollup.append({
                "profile_id": pid,
                "allocations_total": len(allocations),
                "allocations_flagged": flagged,
                "any_flagged": s.get("any_flagged", False),
            })
    data: dict[str, Any] = {
        "catalog_count": len(models),
        "verified_real_count": verified,
        "aspirational_count": aspirational,
        "by_class": by_class,
        "by_quantization": by_quant,
        "suggester_per_profile": suggester_rollup,
    }
    return {
        "id": "models",
        "title": "Models — catalog × profile (R227 / Z-2)",
        "data": data,
    }


def card_insights() -> dict[str, Any]:
    """R235 (SDD-026 Z-10 dashboard surface) — Insights card.

    Calls R234 `insights synthesize` and renders the top-3 highest-
    severity findings as a card. needs_attention is surfaced into the
    card payload so dashboard CSS can color the section header.
    """
    bin_path = REPO_ROOT / "scripts" / "insights" / "synthesize.py"
    fallback: dict[str, Any] = {
        "round": "R235",
        "vector": "SDD-026 Z-10 dashboard",
        "needs_attention": False,
        "counts": {"critical": 0, "attention": 0, "informational": 0, "total": 0},
        "top": [],
        "summary": "synthesize.py unavailable",
    }
    if not bin_path.exists():
        fallback["summary"] = "synthesize.py not shipped"
        return {
            "id": "insights",
            "title": "Insights (R234 / Z-10)",
            "data": fallback,
        }
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), "--json"],
            capture_output=True,
            text=True,
            timeout=25,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        fallback["summary"] = f"invocation failed: {e}"
        return {"id": "insights", "title": "Insights (R234 / Z-10)", "data": fallback}
    if r.returncode not in (0, 1):
        fallback["summary"] = f"synthesize rc={r.returncode}"
        return {"id": "insights", "title": "Insights (R234 / Z-10)", "data": fallback}
    try:
        report = json.loads(r.stdout)
    except json.JSONDecodeError:
        fallback["summary"] = "synthesize emitted non-JSON"
        return {"id": "insights", "title": "Insights (R234 / Z-10)", "data": fallback}
    top = report.get("insights") or []
    counts = report.get("counts") or {}
    data = {
        "round": "R235",
        "vector": "SDD-026 Z-10 dashboard",
        "needs_attention": report.get("needs_attention", False),
        "counts": counts,
        "top": [
            {
                "severity": i.get("severity"),
                "title": i.get("title"),
                "action": i.get("action"),
            }
            for i in top[:3]
        ],
        "summary": (
            f"{counts.get('critical', 0)} critical, "
            f"{counts.get('attention', 0)} attention, "
            f"{counts.get('informational', 0)} informational"
        ),
    }
    return {
        "id": "insights",
        "title": "Insights (R234 / Z-10)",
        "data": data,
    }


def card_install_paths() -> dict[str, Any]:
    """R238 (SDD-026 Z-8 dashboard surface) — Install-paths card.

    Calls R237 `install-paths show --json` and renders a per-feature
    install-layer verdict (installable / alternative / blocked). Drives
    the dashboard's grey-out UX: blocked features render with a
    'requires X which is down' label + the alternative offer when one
    is available.
    """
    bin_path = REPO_ROOT / "scripts" / "install" / "paths.py"
    fallback: dict[str, Any] = {
        "round": "R238",
        "vector": "SDD-026 Z-8 dashboard",
        "summary": "paths.py unavailable",
        "features": [],
        "counts": {"installable": 0, "alternative": 0, "blocked": 0, "total": 0},
    }
    if not bin_path.exists():
        return {
            "id": "install-paths",
            "title": "Install paths (R237 / Z-8)",
            "data": fallback,
        }
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), "show", "--json"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        fallback["summary"] = f"invocation failed: {e}"
        return {
            "id": "install-paths",
            "title": "Install paths (R237 / Z-8)",
            "data": fallback,
        }
    if r.returncode not in (0, 1):
        fallback["summary"] = f"paths.py rc={r.returncode}"
        return {
            "id": "install-paths",
            "title": "Install paths (R237 / Z-8)",
            "data": fallback,
        }
    try:
        report = json.loads(r.stdout)
    except json.JSONDecodeError:
        fallback["summary"] = "paths.py emitted non-JSON"
        return {
            "id": "install-paths",
            "title": "Install paths (R237 / Z-8)",
            "data": fallback,
        }
    counts = report.get("counts", {})
    return {
        "id": "install_paths",
        "title": "Install paths (R237 / Z-8)",
        "data": {
            "round": "R238",
            "vector": "SDD-026 Z-8 dashboard",
            "counts": counts,
            "features": [
                {
                    "feature": f.get("feature"),
                    "summary": f.get("summary"),
                    "verdict": f.get("verdict"),
                    "default_layer": f.get("default_layer"),
                    "recommended_layer": f.get("recommended_layer"),
                    "reason": f.get("reason"),
                    # Grey-out signal: any layer with unmet deps.
                    "blocked_layers": [
                        layer["layer"]
                        for layer in (f.get("layers") or [])
                        if not layer.get("available")
                    ],
                }
                for f in (report.get("features") or [])
            ],
            "summary": (
                f"{counts.get('installable', 0)} installable, "
                f"{counts.get('alternative', 0)} alternative, "
                f"{counts.get('blocked', 0)} blocked"
            ),
            "needs_attention": counts.get("blocked", 0) > 0,
        },
    }


def card_services() -> dict[str, Any]:
    """R241 (SDD-026 Z-15 dashboard surface) — Services card.

    Calls R240 `services shipped --json` so the operator sees in the
    browser which sovereign-os-declared systemd units are loaded on
    this host. Top-5 not-loaded units surface in the card body as
    operator-enable hints.
    """
    bin_path = REPO_ROOT / "scripts" / "services" / "inventory.py"
    fallback: dict[str, Any] = {
        "round": "R241",
        "vector": "SDD-026 Z-15 dashboard",
        "counts": {"total": 0, "loaded": 0, "missing": 0},
        "missing_top": [],
        "summary": "inventory.py unavailable",
    }
    if not bin_path.exists():
        return {"id": "services", "title": "Services (R240 / Z-15)", "data": fallback}
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), "shipped", "--json"],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        fallback["summary"] = f"invocation failed: {e}"
        return {"id": "services", "title": "Services (R240 / Z-15)", "data": fallback}
    if r.returncode not in (0, 1):
        fallback["summary"] = f"inventory.py rc={r.returncode}"
        return {"id": "services", "title": "Services (R240 / Z-15)", "data": fallback}
    try:
        report = json.loads(r.stdout)
    except json.JSONDecodeError:
        fallback["summary"] = "inventory.py emitted non-JSON"
        return {"id": "services", "title": "Services (R240 / Z-15)", "data": fallback}
    total = report.get("count", 0)
    loaded = report.get("loaded_count", 0)
    missing = report.get("missing_count", 0)
    units = report.get("units") or []
    missing_top = [
        {"name": u.get("name"), "description": u.get("description")}
        for u in units
        if not u.get("loaded_on_this_host")
    ][:5]
    return {
        "id": "services",
        "title": "Services (R240 / Z-15)",
        "data": {
            "round": "R241",
            "vector": "SDD-026 Z-15 dashboard",
            "counts": {"total": total, "loaded": loaded, "missing": missing},
            "missing_top": missing_top,
            "summary": f"{loaded}/{total} loaded, {missing} not enabled",
            "needs_attention": missing > 0,
        },
    }


def card_kernel() -> dict[str, Any]:
    """R241 (SDD-026 Z-14 dashboard surface) — Kernel-tuning card.

    Calls R239 `kernel list --json` to surface available presets, then
    `kernel show --json` (no preset filter) to capture per-preset
    diverge counts. Operator sees in the browser which preset matches
    the live host best + how many keys diverge from each.
    """
    bin_path = REPO_ROOT / "scripts" / "kernel" / "tuning.py"
    fallback: dict[str, Any] = {
        "round": "R241",
        "vector": "SDD-026 Z-14 dashboard",
        "presets": [],
        "summary": "tuning.py unavailable",
    }
    if not bin_path.exists():
        return {"id": "kernel", "title": "Kernel tuning (R239 / Z-14)", "data": fallback}
    # Single call: `show` gives us per-preset diverge counts.
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), "show", "--json"],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        fallback["summary"] = f"invocation failed: {e}"
        return {"id": "kernel", "title": "Kernel tuning (R239 / Z-14)", "data": fallback}
    if r.returncode not in (0, 1):
        fallback["summary"] = f"tuning.py rc={r.returncode}"
        return {"id": "kernel", "title": "Kernel tuning (R239 / Z-14)", "data": fallback}
    try:
        report = json.loads(r.stdout)
    except json.JSONDecodeError:
        fallback["summary"] = "tuning.py emitted non-JSON"
        return {"id": "kernel", "title": "Kernel tuning (R239 / Z-14)", "data": fallback}
    presets = []
    for name, p in (report.get("presets") or {}).items():
        c = p.get("counts", {})
        presets.append(
            {
                "preset": name,
                "summary": p.get("summary", ""),
                "match": c.get("match", 0),
                "diverges": c.get("diverges", 0),
                "unreadable": c.get("unreadable", 0),
            }
        )
    # Best-matched preset = max(match) - prefer the one closest to live.
    if presets:
        best = max(presets, key=lambda p: p["match"])
        best_name = best["preset"]
        best_match = best["match"]
    else:
        best_name = None
        best_match = 0
    return {
        "id": "kernel",
        "title": "Kernel tuning (R239 / Z-14)",
        "data": {
            "round": "R241",
            "vector": "SDD-026 Z-14 dashboard",
            "presets": presets,
            "best_match_preset": best_name,
            "best_match_keys": best_match,
            "summary": (
                f"{len(presets)} preset(s); best match: "
                f"{best_name or '(none)'} ({best_match} key(s) align)"
            ),
            "needs_attention": any(p["diverges"] > 0 for p in presets),
        },
    }


def card_toolchains() -> dict[str, Any]:
    """R243 (SDD-026 Z-2 dashboard surface) — Toolchains card.

    Calls R242 `toolchains list --json` to surface inference + fine-
    tune + eval toolchain inventory. Drives the dashboard's "what
    LM-Studio-equivalents are installed?" answer.
    """
    bin_path = REPO_ROOT / "scripts" / "models" / "toolchains.py"
    fallback: dict[str, Any] = {
        "round": "R243",
        "vector": "SDD-026 Z-2 dashboard",
        "counts": {"total": 0, "installed": 0, "absent": 0, "by_kind": {}},
        "installed_names": [],
        "absent_names": [],
        "summary": "toolchains.py unavailable",
    }
    if not bin_path.exists():
        return {"id": "toolchains", "title": "Toolchains (R242 / Z-2)", "data": fallback}
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), "list", "--json"],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        fallback["summary"] = f"invocation failed: {e}"
        return {"id": "toolchains", "title": "Toolchains (R242 / Z-2)", "data": fallback}
    if r.returncode != 0:
        fallback["summary"] = f"toolchains.py rc={r.returncode}"
        return {"id": "toolchains", "title": "Toolchains (R242 / Z-2)", "data": fallback}
    try:
        report = json.loads(r.stdout)
    except json.JSONDecodeError:
        fallback["summary"] = "toolchains.py emitted non-JSON"
        return {"id": "toolchains", "title": "Toolchains (R242 / Z-2)", "data": fallback}
    rows = report.get("toolchains") or []
    installed_names = [t["name"] for t in rows if t.get("installed")]
    absent_names = [t["name"] for t in rows if not t.get("installed")]
    return {
        "id": "toolchains",
        "title": "Toolchains (R242 / Z-2)",
        "data": {
            "round": "R243",
            "vector": "SDD-026 Z-2 dashboard",
            "counts": report.get("counts", {}),
            "installed_names": installed_names,
            "absent_names": absent_names,
            "summary": (
                f"{len(installed_names)} installed, "
                f"{len(absent_names)} absent (operator can install via "
                "scripts/models/toolchains.py info <name>)"
            ),
            # Surface up to 5 not-yet-installed entries with their install hints
            # so operators see actionable next-steps right in the card.
            "install_hints_top": [
                {"name": t["name"], "install_hint": t["install_hint"]}
                for t in rows
                if not t.get("installed")
            ][:5],
        },
    }


def card_fine_tune() -> dict[str, Any]:
    """R247 (SDD-026 Z-2 fine-tune dashboard surface) — Fine-tune card.

    Calls R244 `fine-tune list-methods` + `fine-tune history` to surface
    available methods + recent runs. Drives the dashboard's "what
    LoRA/SFT/DPO runs have I done?" answer + an inline list of the
    4 methods with their vram floors.
    """
    bin_path = REPO_ROOT / "scripts" / "models" / "fine_tune.py"
    fallback: dict[str, Any] = {
        "round": "R247",
        "vector": "SDD-026 Z-2 fine-tune dashboard",
        "methods": [],
        "recent_runs": [],
        "summary": "fine_tune.py unavailable",
    }
    if not bin_path.exists():
        return {"id": "fine_tune", "title": "Fine-tune (R244 / Z-2)", "data": fallback}
    try:
        r_methods = subprocess.run(
            [sys.executable, str(bin_path), "list-methods", "--json"],
            capture_output=True, text=True, timeout=15, check=False,
        )
        r_history = subprocess.run(
            [sys.executable, str(bin_path), "history", "--limit", "5", "--json"],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        fallback["summary"] = f"invocation failed: {e}"
        return {"id": "fine_tune", "title": "Fine-tune (R244 / Z-2)", "data": fallback}
    methods: list[dict[str, Any]] = []
    recent: list[dict[str, Any]] = []
    try:
        m_doc = json.loads(r_methods.stdout) if r_methods.returncode == 0 else {}
        for key, m in (m_doc.get("methods") or {}).items():
            methods.append(
                {
                    "key": key,
                    "name": m.get("name"),
                    "harness": m.get("harness"),
                    "applicable_base_classes": m.get("applicable_base_classes"),
                    "vram_floor_gib": m.get("vram_gib_required_min"),
                    "cost_hours": m.get("cost_estimate_hours"),
                }
            )
    except json.JSONDecodeError:
        pass
    try:
        h_doc = json.loads(r_history.stdout) if r_history.returncode == 0 else {}
        recent = h_doc.get("rows") or []
    except json.JSONDecodeError:
        pass
    return {
        "id": "fine_tune",
        "title": "Fine-tune (R244 / Z-2)",
        "data": {
            "round": "R247",
            "vector": "SDD-026 Z-2 fine-tune dashboard",
            "methods": methods,
            "recent_runs": recent,
            "summary": f"{len(methods)} method(s); {len(recent)} recent run(s)",
            "needs_attention": False,  # informational only
        },
    }


def card_events() -> dict[str, Any]:
    """R247 (SDD-026 Z-16 dashboard surface) — Events timeline card.

    Calls R246 `events summary` for per-source counts + `events
    timeline --limit 5` for most-recent events. Operator's "what's
    been happening?" surface in the browser.
    """
    bin_path = REPO_ROOT / "scripts" / "history" / "aggregate.py"
    fallback: dict[str, Any] = {
        "round": "R247",
        "vector": "SDD-026 Z-16 dashboard",
        "total_events": 0,
        "sources": {},
        "recent": [],
        "summary": "aggregate.py unavailable",
    }
    if not bin_path.exists():
        return {"id": "events", "title": "Events (R246 / Z-16)", "data": fallback}
    try:
        r_sum = subprocess.run(
            [sys.executable, str(bin_path), "summary", "--json"],
            capture_output=True, text=True, timeout=15, check=False,
        )
        r_tl = subprocess.run(
            [sys.executable, str(bin_path), "timeline", "--limit", "5", "--json"],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        fallback["summary"] = f"invocation failed: {e}"
        return {"id": "events", "title": "Events (R246 / Z-16)", "data": fallback}
    sources: dict[str, Any] = {}
    total = 0
    recent: list[dict[str, Any]] = []
    try:
        s_doc = json.loads(r_sum.stdout) if r_sum.returncode == 0 else {}
        sources = s_doc.get("sources", {})
        total = s_doc.get("total_events", 0)
    except json.JSONDecodeError:
        pass
    try:
        tl_doc = json.loads(r_tl.stdout) if r_tl.returncode == 0 else {}
        recent = tl_doc.get("events") or []
    except json.JSONDecodeError:
        pass
    return {
        "id": "events",
        "title": "Events (R246 / Z-16)",
        "data": {
            "round": "R247",
            "vector": "SDD-026 Z-16 dashboard",
            "total_events": total,
            "sources": sources,
            "recent": recent,
            "summary": (
                f"{total} events across {len(sources)} source(s); "
                f"showing 5 most-recent"
            ),
            "needs_attention": False,  # informational
        },
    }


def card_power() -> dict[str, Any]:
    """R254 (SDD-026 Z-18 dashboard) — Power + PSU + UPS card.

    Calls R252 `power-status psu` + `budget` + `advisories` JSON to
    surface the operator-declared PSU, the live wattage budget vs
    estimated load, and the graceful-shutdown verdict (with rc=1
    when critical).
    """
    bin_path = REPO_ROOT / "scripts" / "hardware" / "power-status.py"
    fallback: dict[str, Any] = {
        "round": "R254",
        "vector": "SDD-026 Z-18 dashboard",
        "summary": "power-status.py unavailable",
    }
    if not bin_path.exists():
        return {"id": "power", "title": "Power (R252 / Z-18)", "data": fallback}

    def _call(verb: str) -> dict[str, Any]:
        try:
            r = subprocess.run(
                [sys.executable, str(bin_path), verb, "--json"],
                capture_output=True, text=True, timeout=15, check=False,
            )
        except (subprocess.TimeoutExpired, OSError):
            return {}
        if r.returncode not in (0, 1):
            return {}
        try:
            return json.loads(r.stdout) or {}
        except json.JSONDecodeError:
            return {}

    psu = _call("psu")
    budget = _call("budget")
    advisories = _call("advisories")
    util = budget.get("utilization_pct")
    needs_attention = bool(
        (util is not None and util >= 85)
        or advisories.get("verdict") in {"critical", "attention"}
    )
    data = {
        "round": "R254",
        "vector": "SDD-026 Z-18 dashboard",
        "psu": (psu or {}).get("psu") or {},
        "sustained_budget_watts": (psu or {}).get("sustained_budget_watts"),
        "budget": {
            "estimated_load_watts": (budget or {}).get("estimated_load_watts"),
            "utilization_pct": util,
            "headroom_watts": (budget or {}).get("headroom_watts"),
            "warnings": (budget or {}).get("warnings") or [],
        },
        "advisories": {
            "verdict": (advisories or {}).get("verdict"),
            "advisories": (advisories or {}).get("advisories") or [],
            "ups_present": (advisories or {}).get("ups_present"),
        },
        "needs_attention": needs_attention,
        "summary": (
            f"PSU {(psu or {}).get('psu', {}).get('rated_watts','?')} W; "
            f"load {((budget or {}).get('estimated_load_watts') or 0):.0f} W; "
            f"verdict {(advisories or {}).get('verdict') or '?'}"
        ),
    }
    return {"id": "power", "title": "Power (R252 / Z-18)", "data": data}


def card_bios() -> dict[str, Any]:
    """R254 (SDD-026 Z-17 dashboard) — BIOS + board + memory card.

    Calls R251 `bios-info show --json` to surface BIOS, baseboard,
    DIMM count + speed mix, and board-specific advisory count.
    """
    bin_path = REPO_ROOT / "scripts" / "hardware" / "bios-info.py"
    fallback: dict[str, Any] = {
        "round": "R254",
        "vector": "SDD-026 Z-17 dashboard",
        "summary": "bios-info.py unavailable",
    }
    if not bin_path.exists():
        return {"id": "bios", "title": "BIOS + memory (R251 / Z-17)", "data": fallback}
    try:
        r = subprocess.run(
            [sys.executable, str(bin_path), "show", "--json"],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        fallback["summary"] = f"invocation failed: {e}"
        return {"id": "bios", "title": "BIOS + memory (R251 / Z-17)", "data": fallback}
    if r.returncode != 0:
        fallback["summary"] = f"bios-info.py rc={r.returncode}"
        return {"id": "bios", "title": "BIOS + memory (R251 / Z-17)", "data": fallback}
    try:
        report = json.loads(r.stdout)
    except json.JSONDecodeError:
        fallback["summary"] = "bios-info.py emitted non-JSON"
        return {"id": "bios", "title": "BIOS + memory (R251 / Z-17)", "data": fallback}
    bios = report.get("bios", {})
    bb = report.get("baseboard", {})
    mem = report.get("memory", {})
    adv = report.get("advisories", {})
    return {
        "id": "bios",
        "title": "BIOS + memory (R251 / Z-17)",
        "data": {
            "round": "R254",
            "vector": "SDD-026 Z-17 dashboard",
            "bios_vendor": bios.get("vendor"),
            "bios_version": bios.get("version"),
            "baseboard_product": bb.get("product"),
            "baseboard_vendor": bb.get("vendor"),
            "dimm_count": mem.get("dimm_count", 0),
            "matched_board": adv.get("matched_board"),
            "advisory_count": len(adv.get("advisories") or []),
            "summary": (
                f"{bb.get('product') or '?'}; "
                f"{mem.get('dimm_count', 0)} DIMM(s); "
                f"{len(adv.get('advisories') or [])} advisory(ies)"
            ),
            "needs_attention": False,  # informational
        },
    }


CARDS = [
    card_gpu,
    card_network,
    card_cpu,
    card_fs,
    card_raid,
    card_flex,
    card_health,
    card_models,
    card_insights,
    card_install_paths,
    card_services,
    card_kernel,
    card_toolchains,
    card_fine_tune,
    card_events,
    card_power,
    card_bios,
]


# --------------------------------------------------------- rendering


def render_html(cards: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    parts.append("<!doctype html>")
    parts.append("<html><head><title>sovereign-os dashboard (R225)</title>")
    parts.append("<style>")
    parts.append("  body{font:14px/1.4 monospace;background:#0d1117;color:#c9d1d9;padding:1em;margin:0;}")
    parts.append("  h1{font-size:1.2em;border-bottom:1px solid #30363d;padding-bottom:.3em;}")
    parts.append("  .card{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:1em;margin:1em 0;}")
    parts.append("  .card h2{font-size:1em;margin:0 0 .5em 0;color:#79c0ff;}")
    parts.append("  pre{background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:.5em;overflow:auto;white-space:pre-wrap;}")
    parts.append("  footer{margin-top:2em;color:#8b949e;font-size:.9em;}")
    parts.append("  .ok{color:#3fb950;} .warn{color:#d29922;} .down{color:#f85149;}")
    parts.append("</style></head><body>")
    parts.append("<h1>sovereign-os dashboard — R225 / SDD-026 Z-1 SEED</h1>")
    parts.append(
        "<p>Every card reads the same script the operator runs via "
        "<code>sovereign-osctl</code>. Read-only; no mutations.</p>"
    )
    for c in cards:
        parts.append(f'<section class="card" id="card-{html.escape(c["id"])}">')
        parts.append(f"<h2>{html.escape(c['title'])}</h2>")
        body = json.dumps(c["data"], indent=2)
        parts.append(f"<pre>{html.escape(body)}</pre>")
        parts.append("</section>")
    parts.append('<footer>')
    parts.append('  Operator note: read-only mirror of the terminal cards.')
    parts.append('  Mutations stay on the CLI (or the future MCP server SD-R84+).')
    parts.append('  JSON endpoint: <code>/api/health</code> · per-card: ')
    for c in cards:
        parts.append(f'<code>/api/{html.escape(c["id"])}</code> · ')
    parts.append('</footer></body></html>')
    return "".join(parts)


def gather_all() -> list[dict[str, Any]]:
    return [c() for c in CARDS]


# --------------------------------------------------------- HTTP layer


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "sovereign-os-dashboard/R225"

    # Quiet stderr (the L3 test would otherwise see request log noise).
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, body_str: str, status: int = 200) -> None:
        body = body_str.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _check_auth(self) -> bool:
        """R250 (SDD-026 Z-1 auth): IP allowlist + Bearer-token check.

        Returns True when the request is authorized; False after
        sending a 401/403 response (do_GET caller short-circuits).
        Default (AUTH_CONFIG is None) = always-True (cycle-8 SEED
        behavior — safe on loopback / tailscale-private binds).
        """
        if AUTH_CONFIG is None:
            return True
        peer_ip = self.client_address[0] if self.client_address else ""
        # Loopback shortcut.
        if AUTH_CONFIG.get("allow_loopback") and _is_loopback(peer_ip):
            return True
        # IP allowlist gate first (don't even disclose token shape to
        # off-list clients).
        if peer_ip not in (AUTH_CONFIG.get("allow_ips") or []):
            self._send_json(
                {
                    "error": "forbidden",
                    "round": "R250",
                    "reason": "client IP not in dashboard-auth allowlist",
                    "peer": peer_ip,
                },
                status=403,
            )
            return False
        # Token gate.
        expected = AUTH_CONFIG.get("token")
        if not expected:
            self._send_json(
                {
                    "error": "server-misconfig",
                    "round": "R250",
                    "reason": "dashboard-auth.toml present but token_env "
                              "resolved to empty — operator must export the env var",
                },
                status=500,
            )
            return False
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth[len("Bearer "):] != expected:
            self._send_json(
                {
                    "error": "unauthorized",
                    "round": "R250",
                    "reason": "missing or invalid Bearer token",
                },
                status=401,
            )
            return False
        return True

    def do_GET(self) -> None:  # noqa: N802
        if not self._check_auth():
            return
        path = self.path
        if path == "/" or path == "/index.html":
            self._send_html(render_html(gather_all()))
            return
        if path == "/api/health":
            self._send_json({"cards": gather_all(), "round": "R225", "sdd_vector": "SDD-026 Z-1"})
            return
        # R233 (SDD-026 Z-2): per-model detail endpoint. Drives the
        # dashboard's "click on a model card → see full detail" UX
        # by proxying the R231 `models info <slug>` JSON. The slug
        # follows after /api/models/ so URL-safe slugs work directly.
        models_prefix = "/api/models/"
        if path.startswith(models_prefix):
            slug = path[len(models_prefix):]
            # Defensive: reject path separators / control chars even
            # though subprocess argv is shell-safe; keep slug semantics
            # tight (model ids in the catalog are alnum + - + .).
            if slug and all(c.isalnum() or c in "-_." for c in slug):
                detail = _run_models_script("info.py", [slug])
                if detail is not None:
                    self._send_json(detail)
                    return
                self._send_json(
                    {
                        "error": "unknown model slug",
                        "slug": slug,
                        "round": "R233",
                        "hint": "list available ids via /api/models or "
                                "`sovereign-osctl models query --json`",
                    },
                    status=404,
                )
                return
            self._send_json(
                {
                    "error": "invalid model slug",
                    "slug": slug,
                    "round": "R233",
                },
                status=400,
            )
            return
        for c in CARDS:
            card_id = c.__name__.removeprefix("card_")
            if path == f"/api/{card_id}":
                self._send_json(c())
                return
        self._send_json(
            {"error": "not found", "path": path, "round": "R225"},
            status=404,
        )


def parse_bind(s: str) -> tuple[str, int]:
    if ":" not in s:
        raise ValueError(f"--bind must be HOST:PORT (got {s!r})")
    host, port_str = s.rsplit(":", 1)
    try:
        port = int(port_str)
    except ValueError as e:
        raise ValueError(f"--bind port not an int: {port_str!r}") from e
    return host or "127.0.0.1", port


def main() -> int:
    p = argparse.ArgumentParser(description="R225 (SDD-026 Z-1) dashboard SEED.")
    p.add_argument(
        "--bind",
        default="127.0.0.1:8443",
        help="bind address HOST:PORT (default %(default)s)",
    )
    p.add_argument(
        "--once",
        action="store_true",
        help="handle exactly one request and exit (used by L3 tests)",
    )
    p.add_argument(
        "--render-only",
        action="store_true",
        help=(
            "DO NOT bind a socket; render the dashboard HTML to stdout "
            "and exit. Used for offline-rendering tests + a future static "
            "snapshot path."
        ),
    )
    args = p.parse_args()

    if args.render_only:
        sys.stdout.write(render_html(gather_all()))
        return 0

    try:
        host, port = parse_bind(args.bind)
    except ValueError as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 2
    # R250: load auth config BEFORE binding so the operator sees the
    # "auth enabled" banner alongside the bind announcement.
    global AUTH_CONFIG
    AUTH_CONFIG = load_auth_config()
    try:
        srv = HTTPServer((host, port), DashboardHandler)
    except OSError as e:
        print(f"ERROR bind {host}:{port}: {e}", file=sys.stderr)
        return 2
    auth_banner = "no-auth (cycle-8 SEED)"
    if AUTH_CONFIG is not None:
        token_state = "token-present" if AUTH_CONFIG.get("token") else "token-MISSING-from-env"
        auth_banner = (
            f"auth-enabled via {AUTH_CONFIG['config_source']} "
            f"({token_state}, allow_loopback={AUTH_CONFIG['allow_loopback']}, "
            f"allow_ips={len(AUTH_CONFIG['allow_ips'])})"
        )
    print(f"# R225 sovereign-os dashboard serving http://{host}:{port}/")
    print(f"# R250 auth: {auth_banner}")
    try:
        if args.once:
            srv.handle_request()
        else:
            srv.serve_forever()
    except KeyboardInterrupt:
        print()
        print("# R225 shutdown via SIGINT")
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
